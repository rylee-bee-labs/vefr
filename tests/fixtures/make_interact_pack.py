"""Build the neutral interact fixture pack (sample-world + one of each
thing the one-button Interact verb can act on) for tests and local
playtests. Neutral engine-test canon only: a resident, a trader, a
chest, a door to a cellar, and one rat asleep beside the hero."""

import base64
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

# PINNED COORDINATES (x, y) - every harness walk stands on these exact
# tiles, and the tests pin the words each spot produces:
#
#   hero start ............. [1, 1]
#   enemy (a storeroom rat) . [2, 1]  one tile right of the hero: bump it
#   resident "the porter" ... [4, 3]  talk reach 2
#   resident spot ........... [4, 2]  stand -> "Talk to the porter"
#   place spot .............. [5, 5]  stand -> "Look at the old market cross";
#                                    the peddler at [6, 5] is in reach, a
#                                    place under the hero must win the pick
#   chest "The Gate Ledger". [7, 1]  touch reach 1
#   chest spot .............. [7, 2]  stand -> "Open the chest"
#   door tile ............... [9, 3]  town -> cellar transition
#   door spot ............... [9, 4]  stand -> "Go through the door"
#   trader "the peddler" .... [6, 5]  shop: "true", talk reach 2
#   trader spot ............. [6, 4]  stand -> "Trade with the peddler"
#   cat "the cat" ........... [9, 1]  seeds only, no fragments: offline talk
#   stranger "the stranger" . [8, 5]  no seeds, no fragments: no offline line
#   empty spot .............. [1, 5]  nothing in reach in any direction
#   cellar arrival .......... [1, 1]  where the door drops the hero
#
# The rat has `sight: 0`: it never steps on its own, so every pinned
# tile above stays pinned no matter how much the tests walk; it
# only fights when the hero bumps it. The walk routes (see
# interact_play_harness.mjs) never pass the rat's own neighbours
# [1, 1], [3, 1] or [2, 2], so it never attacks outside the bump test.
TOWN_MAP = [
    "###########",
    "#.........#",
    "#.........#",
    "#.........#",
    "#.........#",
    "#.........#",
    "###########",
]
CELLAR_MAP = [
    "#####",
    "#...#",
    "#####",
]

# A named place under the hero's feet at [5, 5], with the peddler one
# tile east: the fixture that proves an own-tile place beats a resident
# merely in talk reach (and is not itself the hero's start).
TOWN_POIS = {"5,5": "the old market cross"}
TOWN_POI_TEXT = {
    "5,5": "A knot in the boards marks where the market cross stood.",
}

# The one hazard, asleep beside the hero's start. `sight: 0` is the
# whole trick: hold still until bumped, so coordinates stay honest.
TOWN_ENEMIES = [
    {"id": "storeroom-rat", "name": "a storeroom rat", "at": [2, 1],
     "hp": 4, "atk": 1, "sight": 0, "sprite": "rat"},
]

# The item catalog: the chest's `drops` must name catalog ids, and
# both carry a sprite so the bag and the marker draw a picture.
ITEMS = {
    "cloudy-potion": {"name": "a cloudy potion", "sprite": "potion",
                      "value": 8, "heal": 3, "use": "drink"},
    "brass-ring": {"name": "a plain brass ring", "sprite": "ring",
                   "value": 3},
}

# The two people: a plain resident within talk reach of [4, 2], and
# the region's trader (`shop: "true"`) within talk reach of [6, 4].
# No `region` key, so both belong to the first region (the town).
SPEAKERS = {
    "porter": {
        "name": "the porter",
        "at": [4, 3],
        "near": "the gate stone",
        "seeds": {
            "dusk": "The gate is shut until dawn.",
            "dawn": "Daylight. The gate is opening.",
        },
    },
    "peddler": {
        "name": "the peddler",
        "at": [6, 5],
        "near": "the blue stall",
        "shop": "true",
        "seeds": {
            "dusk": "Cheap now, dearer after dark.",
            "dawn": "Fresh stock, fair prices.",
        },
    },
    "cat": {
        "name": "the cat",
        "at": [9, 1],
        "near": "the hearth",
        "seeds": {
            "dusk": "The cat looks at you, then away.",
            "dawn": "The cat stretches in the first light.",
        },
    },
    "stranger": {
        "name": "the stranger",
        "at": [8, 5],
        "near": "the wall",
    },
}

# A chest book at [7, 1], holding a note and two items. A chest is
# used, not stepped on, and the walk routes never stand on its tile.
CHEST_BOOK = (
    "---\ntitle: The Gate Ledger\nfound: map\nat: [7, 1]\n"
    "chest: yes\ndrops: cloudy-potion, brass-ring\nkind: note\n---\n"
    "A tally of every gate this town has ever shut.\n"
)

# The resident's offline fragment bank: with no model and no woven
# pool, talkToSpeaker's fallback splices these lines into the speech
# box, so the box opens with a real line in every offline test.
PORTER_FRAGMENTS = (
    "- The gate is heavy, but it opens for anyone who knocks.\n"
    "- Coins pass through this town every day of the year.\n"
    "- Ask me again at dawn, when the lock is warm.\n"
)

# The door: an act transition from the town's [9, 3] to the cellar,
# arriving at the cellar's [1, 1].
DOOR = {"from": "town", "at": [9, 3], "to": "cellar", "to_at": [1, 1]}

# A 1x1 transparent PNG - enough for the bake to inline a sprite.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _legend() -> dict:
    return {
        ".": {"base": ["#212a20"]},
        "#": {"base": ["#2a2e33"], "solid": True},
    }


def _write_region(region: Path, rows: list, enemies: list,
                  pois: dict | None = None,
                  poi_text: dict | None = None) -> None:
    region.mkdir(parents=True, exist_ok=True)
    (region / "map.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    contract = {
        "tile": 32, "bg": "#131311", "hero_start": [1, 1],
        "sanctuary_tiles": ["."],
        "water_by_phase": {"dusk": "low", "dawn": "low"},
        "flood_tiles": [], "pois": pois or {},
        "poi_text": poi_text or {}, "legend": _legend(),
    }
    if enemies:
        contract["enemies"] = enemies
    (region / "contract.json").write_text(
        json.dumps(contract), encoding="utf-8")


def build(dest: Path) -> Path:
    pack = dest / "worlds" / "interact-test"
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    # Engine-test canon only: the sample's books lie on the sample's
    # own map, so they are not the fixture's. The fixture's own chest
    # holds the note and the items its `drops` names.
    lib = pack / "library"
    if lib.exists():
        shutil.rmtree(lib)
    lib.mkdir()
    (lib / "gate-ledger.md").write_text(CHEST_BOOK, encoding="utf-8")

    # The resident's offline lines, so the speech box opens offline.
    (pack / "voices" / "porter.fragments.md").write_text(
        PORTER_FRAGMENTS, encoding="utf-8")

    # The hero's numbers, its pictures, and the wake point.
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["items"] = ITEMS
    world["player"] = {
        "hp": 3, "atk": 2, "gold": 5,
        "sprites": {"rat": "sprites/rat.png",
                    "potion": "sprites/potion.png",
                    "ring": "sprites/ring.png"},
        "wake": {"region": "town", "at": [1, 1]},
    }
    world_json.write_text(json.dumps(world), encoding="utf-8")

    # A two-region act: the town (every interact target) and an empty
    # cellar the door opens onto. The sample's own keeper is replaced
    # so the fixture's pinned coordinates are the only speakers here.
    act_dir = pack / "acts" / "act-1"
    act = json.loads((act_dir / "world.json").read_text(encoding="utf-8"))
    act["regions"] = ["town", "cellar"]
    act["transitions"] = [DOOR]
    act["speakers"] = SPEAKERS
    (act_dir / "world.json").write_text(json.dumps(act), encoding="utf-8")

    _write_region(act_dir / "town", TOWN_MAP, TOWN_ENEMIES,
                  pois=TOWN_POIS, poi_text=TOWN_POI_TEXT)
    _write_region(act_dir / "cellar", CELLAR_MAP, [])

    sprites = pack / "sprites"
    sprites.mkdir(exist_ok=True)
    (sprites / "rat.png").write_bytes(_PNG)
    (sprites / "potion.png").write_bytes(_PNG)
    (sprites / "ring.png").write_bytes(_PNG)
    return pack


if __name__ == "__main__":
    print(str(build(Path(sys.argv[1]))))
