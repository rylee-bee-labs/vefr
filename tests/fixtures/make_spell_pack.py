"""Build a spell fixture pack (sample world + a level table + a tome).

Neutral engine-test canon only. `build(dest, spells=..., growth=..., xp=...)`
copies the sample world, gives the hero hp 8 / atk 2, writes the pack's own
`spells` block and adds ONE spellbook to the item catalog, so a monster's
drop can hand the hero a spell.

The names are the pack's own and mean nothing outside this fixture: `ember`
and `tide` are schools, `ember-bolt` is learned at level 1, `tide-mend` at
level 2 (which the level table reaches) and `deep-call` at level 9 - past
the cap, so a spell nothing can teach by level unless a book does.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

# Three levels, so `tide-mend` (level 2) is reachable and `deep-call`
# (level 9) is not.
LEVELS = {"mode": "levels",
          "levels": {"xp": [0, 3, 6], "gain": {"hp": 2, "atk": 1}}}

SPELLS = {
    "schools": ["ember", "tide"],
    "spells": [
        {"id": "ember-bolt", "name": "an ember bolt", "school": "ember",
         "level": 1, "heal": 3},
        {"id": "tide-mend", "name": "a mending tide", "school": "tide",
         "level": 2, "heal": 5},
        {"id": "deep-call", "name": "a deep call", "school": "tide",
         "level": 9},
    ],
}

# The one book: an ordinary item that teaches `tide-mend` when it is read.
# Nothing else about it is special, and `vefr check` holds it to nothing
# more than any other item.
TOME = {"name": "a tide-bound tome", "sprite": "", "use": "read",
        "spell": "tide-mend", "value": 3}


def build(dest: Path, spells=None, growth=None, xp=None, rat_hp=2,
          tome=True, name="spell-test") -> Path:
    pack = dest / "worlds" / name
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["name"] = name
    world["player"] = {"hp": 8, "atk": 2, "gold": 0}
    if spells is not None:
        world["spells"] = json.loads(json.dumps(spells))
    if growth is not None:
        world["growth"] = json.loads(json.dumps(growth))
    if tome:
        catalog = world.setdefault("items", {})
        catalog["tide-tome"] = json.loads(json.dumps(TOME))
    world_json.write_text(json.dumps(world), encoding="utf-8")

    contract_path = pack / "acts" / "act-1" / "town" / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    rat = {"id": "rat-1", "name": "the cellar rat", "at": [2, 4],
           "hp": rat_hp, "atk": 1}
    if xp is not None:
        rat["xp"] = xp
    contract["enemies"] = [rat]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    return pack


if __name__ == "__main__":
    print(build(Path(sys.argv[1])))