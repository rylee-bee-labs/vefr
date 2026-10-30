"""Build the RPG-core fixture pack (ADR 0021).

Neutral engine-test canon only. `build(dest, ...)` copies the sample world
and stands ONE hazard beside the hero's start, the way the elements
fixture does, so a single press of a direction is a whole exchange:

    {"id": "ember-hound", "name": "an ember hound", "at": [2, 4],
     "hp": 5, "atk": 3}

Every ADR 0021 key is a keyword, and every one defaults to None, so one
call with none of them is the pack that has not opted in at all - the one
that must weave and play exactly as it always did.

The names are the pack's own and mean nothing outside this fixture.
"""

import copy
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

HOUND = {"id": "ember-hound", "name": "an ember hound", "at": [2, 4],
         "hp": 5, "atk": 3}

# A few things to wear, drink and carry, used by the tests that need them.
ITEMS = {
    "potion": {"name": "a cloudy potion", "value": 5, "heal": 2, "use": "drink"},
    "keen-blade": {"name": "a keen blade", "slot": "hand", "mods": {"atk": 1},
                   "traits": ["keen", "warming"], "value": 9},
    "plain-ring": {"name": "a plain ring", "slot": "charm", "value": 4},
    "warded-coat": {"name": "a warded coat", "slot": "body", "mods": {"guard": 1}},
    "gem": {"name": "a cut gem", "value": 7},
}

SPELLS = {
    "schools": ["ember"],
    "spells": [
        {"id": "bolt", "name": "an ember bolt", "school": "ember", "level": 1,
         "mana": 2, "harm": 3},
        {"id": "ward", "name": "a warding word", "school": "ember", "level": 1,
         "mana": 1, "ward": {"guard": 2, "turns": 2}},
    ],
}

GROWTH = {"mode": "levels", "levels": {"xp": [0, 50], "gain": {"hp": 1, "atk": 1}}}

TRAITS = {
    "keen": {"atk": 1},
    "warming": {"kill_heal": 2},
    "reckless": {"atk": 3, "sting": 1, "curse": True},
}


def build(dest: Path, name="rpg-test", player=None, fight=None, traits=None,
          items=None, spells=None, growth=None, time=None, hound=None,
          keeper=None, verbs=None, display=None) -> Path:
    pack = dest / "worlds" / name
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["name"] = name
    world["player"] = dict({"hp": 8, "atk": 2, "gold": 0}, **(player or {}))
    world["items"] = {**(world.get("items") or {}), **copy.deepcopy(items or {})}
    for key, value in (("fight", fight), ("traits", traits), ("spells", spells),
                       ("growth", growth), ("time", time), ("display", display)):
        if value is not None:
            world[key] = copy.deepcopy(value)
    world_json.write_text(json.dumps(world), encoding="utf-8")

    act_path = pack / "acts" / "act-1" / "world.json"
    act = json.loads(act_path.read_text(encoding="utf-8"))
    if keeper is not None:
        act["speakers"]["keeper"].update(copy.deepcopy(keeper))
    if verbs is not None:
        act["verbs"] = copy.deepcopy(verbs)
    act_path.write_text(json.dumps(act), encoding="utf-8")

    contract_path = pack / "acts" / "act-1" / "town" / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["enemies"] = [] if hound is False else [dict(HOUND, **(hound or {}))]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    return pack


if __name__ == "__main__":
    print(build(Path(sys.argv[1])))
