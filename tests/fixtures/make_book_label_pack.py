"""Build the neutral book-label fixture pack (sample-world + one map
book on the town map) for tests and local playtests. Neutral engine-test
canon only: no people, no doors, nothing to do but pick a note off the
ground and read it, so every word the Interact button shows in the
browser test comes from the book alone."""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

# PINNED COORDINATES (x, y):
#
#   hero start ............. [1, 1]
#   book "A Note Left at the Door" . [3, 1]
#   spot beside it ........ [2, 1]  facing right: the note is in reach
#   empty spot ............. [1, 3]  nothing in reach in any direction
#
# The note is a `found: map` book with no `chest: yes`, so it lies on
# the ground like the sample world's own note and is not a chest.
TOWN_MAP = [
    "#####",
    "#...#",
    "#...#",
    "#####",
]

# The one book: a note on the town map, at the pinned tile above.
BOOK = (
    "---\ntitle: A Note Left at the Door\nfound: map\nat: [3, 1]\n"
    "kind: note\n---\n"
    "Somebody knocked and nobody answered.\n"
    "\n* * *\n"
    "\nThe rest of the page is blank.\n"
)


def _legend() -> dict:
    return {
        ".": {"base": ["#212a20"]},
        "#": {"base": ["#2a2e33"], "solid": True},
    }


def build(dest: Path) -> Path:
    pack = dest / "worlds" / "book-label-test"
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    # Engine-test canon only: the sample's own books lie on the sample's
    # map, so they are not the fixture's. The fixture's map has exactly
    # one note on it, and no chest.
    lib = pack / "library"
    if lib.exists():
        shutil.rmtree(lib)
    lib.mkdir()
    (lib / "a-note-left-at-the-door.md").write_text(BOOK, encoding="utf-8")

    # The hero's numbers and its wake point: three hearts, no fight in
    # this fixture, but the surface reads them all the same.
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["player"] = {
        "hp": 3, "atk": 2, "gold": 0,
        "wake": {"region": "town", "at": [1, 1]},
    }
    world_json.write_text(json.dumps(world), encoding="utf-8")

    # One region and nothing in it: no speakers, no transitions, no
    # monsters. The sample's keeper is replaced so the fixture's map is
    # empty of everything but the note.
    act_dir = pack / "acts" / "act-1"
    act = json.loads((act_dir / "world.json").read_text(encoding="utf-8"))
    act["regions"] = ["town"]
    act["transitions"] = []
    act["speakers"] = {}
    (act_dir / "world.json").write_text(json.dumps(act), encoding="utf-8")

    region = act_dir / "town"
    if region.exists():
        shutil.rmtree(region)
    region.mkdir(parents=True)
    (region / "map.md").write_text("\n".join(TOWN_MAP) + "\n", encoding="utf-8")
    contract = {
        "tile": 32, "bg": "#131311", "hero_start": [1, 1],
        "sanctuary_tiles": ["."],
        "water_by_phase": {"dusk": "low", "dawn": "low"},
        "flood_tiles": [], "pois": {}, "legend": _legend(),
    }
    (region / "contract.json").write_text(
        json.dumps(contract), encoding="utf-8")
    return pack


if __name__ == "__main__":
    print(str(build(Path(sys.argv[1]))))