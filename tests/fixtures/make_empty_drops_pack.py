"""Build the empty-drops fixture packs for `tests/test_empty_enemy_drops.py`.

The sample pack's own town, with five hazards added - each a different way
a `drops` line can fail to pay the player, and one that does not:

    cellar-rat      a `drops` line naming no id at all
    hollow-moth     every id resolves to no declared item
    half-paid       one dead id beside one that answers (refused by name)
    brass-golem     every id answers (legal - the control)
    nameless-one    an id under an item entry with no `name`

and a second pack built from the same bytes with the `items` block
removed, so the pack-with-no-catalog case is proven on a whole pack
rather than on a dict.

The town map, the keeper and every other byte are the sample's own: this
fixture is about `drops` on enemies and must validate clean apart from
the sentences it is here to raise.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

# (id, name, at, drops), all on open floor of the sample's own town row 1.
# The golem is the control: every id answers, so the kill pays and no
# sentence is raised. `half-paid` is the one that used to be legal here and
# is not: a list where one id resolves to nothing still hands over nothing
# the author named, and the chest check has always refused it.
HAZARDS = [
    ("cellar-rat", "a cellar rat", [4, 1], []),
    ("hollow-moth", "a hollow moth", [5, 1], ["chalked-map", "chalked-key"]),
    ("half-paid", "a half-paid toll", [6, 1], ["cloudy-potion", "chalked-map"]),
    ("brass-golem", "a brass golem", [7, 1], ["cloudy-potion"]),
    ("nameless-one", "a nameless one", [8, 1], ["ghost-thread"]),
]

# `ghost-thread` has no `name`, so `cli._player_items` drops it and the
# weave never bakes it - an id under it is an id no drop can hand over.
ITEMS = {
    "cloudy-potion": {"name": "a cloudy potion", "value": 8, "heal": 3},
    "ghost-thread": {"sprite": "thread"},
}


def build(dest: Path) -> Path:
    """Write the bad-drop pack at `dest/worlds/empty-drops-test`."""
    pack = dest / "worlds" / "empty-drops-test"
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    # The sample's books lie on the sample's own map and carry their own
    # `drops`; this fixture is about enemy drops, so the shelf goes.
    lib = pack / "library"
    if lib.exists():
        shutil.rmtree(lib)
    lib.mkdir()

    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["items"] = ITEMS
    world_json.write_text(json.dumps(world), encoding="utf-8")

    contract = pack / "acts" / "act-1" / "town" / "contract.json"
    town = json.loads(contract.read_text(encoding="utf-8"))
    town["enemies"] = [
        {"id": eid, "name": name, "at": at, "hp": 4, "atk": 1, "drops": drops}
        for eid, name, at, drops in HAZARDS
    ]
    contract.write_text(json.dumps(town), encoding="utf-8")
    return pack


def build_no_catalog(dest: Path) -> Path:
    """The same pack with no `items` at all: it declares nothing."""
    built = build(dest)
    pack = dest / "worlds" / "no-catalog-test"
    if pack.exists():
        shutil.rmtree(pack)
    shutil.copytree(built, pack)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world.pop("items", None)
    world_json.write_text(json.dumps(world), encoding="utf-8")
    return pack


if __name__ == "__main__":
    print(str(build(Path(sys.argv[1]))))