"""Build the fire/burning fixture pack (the prototype encounter, vefr#497).

Neutral engine-test canon only. `build(dest, resist=None, immune=None,
dmg_type='fire', burns=...)` copies the sample world and stands ONE hazard
beside the hero's start, so a single press of a direction is the whole
encounter:

    {"id": "ember-hound", "name": "an ember hound", "at": [2, 4],
     "hp": 5, "atk": 3, "dmg_type": "fire", "burns": {"turns": 2, "tick": 2}}

Every part of it is optional, so one call with all of them None is the
pack that has not opted in at all - the one that must weave and play
exactly as it always did.

The name is the pack's own and means nothing outside this fixture.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

# The hazard's whole data. `dmg_type` is what the blow IS, and `burns`
# is the state it leaves: a duration in turns and a tick.
HOUND = {"id": "ember-hound", "name": "an ember hound", "at": [2, 4],
         "hp": 5, "atk": 3}


def build(dest: Path, name="element-test", hp=8, atk=2, resist=None,
          immune=None, dmg_type="fire", burns=None, hound_hp=5,
          hound_atk=3) -> Path:
    pack = dest / "worlds" / name
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["name"] = name
    player = {"hp": hp, "atk": atk, "gold": 0}
    if resist is not None:
        player["resist"] = json.loads(json.dumps(resist))
    if immune is not None:
        player["immune"] = json.loads(json.dumps(immune))
    world["player"] = player
    world_json.write_text(json.dumps(world), encoding="utf-8")

    contract_path = pack / "acts" / "act-1" / "town" / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    hound = dict(HOUND, hp=hound_hp, atk=hound_atk)
    if dmg_type is not None:
        hound["dmg_type"] = dmg_type
    if burns is not None:
        hound["burns"] = json.loads(json.dumps(burns))
    contract["enemies"] = [hound]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    return pack


# What the play test plays: a hazard that deals fire and leaves the hero
# burning for two turns, two a turn. Nothing resists it unless a test
# says so.
BURNING = {"turns": 2, "tick": 2}

if __name__ == "__main__":
    print(build(Path(sys.argv[1])))