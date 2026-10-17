"""A neutral pack whose items hand the hero verbs (the item-grants slice, E1).

`build(dest, grants=True)` copies the sample world and adds:

  * `mallet-1` - grants the verb `mend`, and `changes` gives that verb 2
    extra attack while it is carried;
  * `glove-1` - a wearable thing that grants `reef`, so a granted verb has
    to survive being worn (a worn thing is out of the bag list);
  * `chalk-1` - grants `chalk`, and the pack's own rule takes it back the
    moment that verb is used (`takes` is `give`'s pair), so a granted verb
    has to leave the row when the thing that granted it is spent;
  * one rule per fact the browser tests read: `starts` hands the hero all
    three, and each verb has a rule of its own so a test can see the press
    arrive as `uses-verb`.

`grants=False` builds the same three items with neither `grants` nor
`changes`: the pack a test weaves to prove that an item with no grant
changes nothing at all. Only the `starts` rule is kept, so the hero is
really carrying all three - what those three grant is gone, and with it
the `uses-verb` rules, which could only ever fire on a granted verb.

The town also gets one asleep rat one tile right of the hero's start, so
`changes` has something to change a blow against: `sight: 0` means it never
walks, and its health is high enough that one blow never ends it.

Everything here is neutral engine-test canon - a mallet, a glove, a stick
of chalk and a rat, and no words from any pitch.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

GRANTING_ITEMS = {
    "mallet-1": {
        "name": "a caulking mallet",
        "grants": [{"verb": "mend", "label": "Mend the hull"}],
        "changes": {"mend": {"atk": 2}},
    },
    "glove-1": {
        "name": "a sailor's glove",
        "slot": "hand",
        "mods": {"atk": 1},
        "grants": [{"verb": "reef", "label": "Reef the sail"}],
    },
    "chalk-1": {
        "name": "a stick of hull chalk",
        "use": "chalk",
        "grants": [{"verb": "chalk", "label": "Chalk the hull"}],
    },
}

# The same catalog with the grants taken out: the objects still exist, the
# hero still carries them, and nothing they own reaches the verb row.
PLAIN_ITEMS = {
    "mallet-1": {"name": "a caulking mallet"},
    "glove-1": {"name": "a sailor's glove", "slot": "hand", "mods": {"atk": 1}},
    "chalk-1": {"name": "a stick of hull chalk", "use": "chalk"},
}

# One hazard, asleep beside the hero's start [3, 4]: `sight: 0` keeps it
# where it is, and 9 health means the blow a test measures never ends it.
TOWN_RAT = {"id": "store-rat", "name": "a store rat", "at": [4, 4],
            "hp": 9, "atk": 1, "sight": 0}

FLAGS = {
    "tooled": "the tool bag was handed over",
    "mended": "the hull was mended",
    "reefed": "the sail was reefed",
    "chalked": "the hull was chalked",
}

RULES = [
    {"id": "the-tool-bag", "when": {"starts": {}},
     "then": [{"set": "tooled"}, {"give": "mallet-1"}, {"give": "glove-1"},
              {"give": "chalk-1"}], "once": True},
    {"id": "the-mallet-spoke", "when": {"uses-verb": {"verb": "mend"}},
     "then": [{"set": "mended"}], "once": False},
    {"id": "the-glove-spoke", "when": {"uses-verb": {"verb": "reef"}},
     "then": [{"set": "reefed"}], "once": False},
    {"id": "the-chalk-spoke", "when": {"uses-verb": {"verb": "chalk"}},
     "then": [{"set": "chalked"}], "once": False},
    # The chalk is spent on use, and the pack says so itself: the verb it
    # granted is the press that spends it, so the verb has to leave the row
    # it was on.
    {"id": "the-chalk-was-used", "when": {"uses-verb": {"verb": "chalk"}},
     "then": [{"takes": "chalk-1"}], "once": False},
]


def build(dest: Path, grants: bool = True, name: str = None) -> Path:
    """The fixture pack, at `dest`, and its directory."""
    pack = dest / "worlds" / (name or ("grants-test" if grants else "grants-none"))
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["name"] = pack.name
    catalog = dict(world.get("items") or {})
    catalog.update(json.loads(json.dumps(GRANTING_ITEMS if grants else PLAIN_ITEMS)))
    world["items"] = catalog
    world["flags"] = json.loads(json.dumps(FLAGS))
    world["rules"] = json.loads(json.dumps(RULES if grants else [RULES[0]]))
    world_json.write_text(json.dumps(world), encoding="utf-8")
    # The rat, in the act's own town contract: the sample's map is kept as
    # it ships, so the hero's start and this one tile beside it are the
    # coordinates the tests stand on.
    contract_path = pack / "acts" / "act-1" / "town" / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["enemies"] = json.loads(json.dumps([TOWN_RAT]))
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    return pack


if __name__ == "__main__":
    print(str(build(Path(sys.argv[1]), grants=(len(sys.argv) < 3
                                               or sys.argv[2] != "none"))))