"""Build the stakes fixture pack (sample-world + one rule + one stake) for tests.

vefr#504: stakes as a real mechanic, one small reversible example.

Neutral engine-test canon only, the sample's own: the hero's start, a
toll the hero walks up to one step right of it, and one stake put to
them there - put the pitch torch at risk, and the chalked map may be
gained. One rule (on `starts`) hands the hero the torch, so the risk is
something they really hold when the toll asks; nothing else changes.

`stakes=` overrides the block, so a test can bake a malformed offer and
see it dropped whole.
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

# The one rule: the hero is handed the torch at Begin, so the stake's
# risk is in the bag when the toll asks for it. Both ids are already in
# the sample's item catalog, so the bag can name them.
RULES = [
    {"id": "the-torch-is-handed-over",
     "when": {"starts": {}},
     "then": [{"give": "torch"}],
     "once": True},
]

# The one stake. `when` is a rule's `when`, verbatim in shape: the hero
# came within one tile of the POI named "the toll".
STAKES = [
    {"id": "the-tolls-price",
     "when": {"comes-near": {"who": "the toll", "distance": 1}},
     "risk": "torch",
     "reward": "chalked-map",
     "say": "The toll-keeper holds out her hand. Leave the torch here, "
            "and the chalked map is yours."},
]


def build(dest: Path, stakes=None) -> Path:
    """Copy the sample pack into `dest` and give it the rule and the stake."""
    pack = dest / "worlds" / "stakes-test"
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["rules"] = json.loads(json.dumps(RULES))
    world["stakes"] = json.loads(json.dumps(STAKES if stakes is None else stakes))
    world_json.write_text(json.dumps(world), encoding="utf-8")

    # A named place one step right of the hero's start: [3, 4] -> [4, 4],
    # a walkable 'p' tile in the sample's town map. Walking there fires
    # the comes-near the stake is written against.
    contract_path = pack / "acts" / "act-1" / "town" / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    pois = dict(contract.get("pois") or {})
    pois["4,4"] = "the toll"
    contract["pois"] = pois
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    return pack


# The offers a bake must refuse, each one missing a single thing the
# player could not act on: no id, no `when`, a `when` in a shape the
# engine never matches, nothing to risk, nothing to gain, no line.
BROKEN = [
    {"when": {"comes-near": {"who": "the toll", "distance": 1}},
     "risk": "torch", "reward": "chalked-map", "say": "no id at all"},
    {"id": "no-when", "risk": "torch", "reward": "chalked-map", "say": "never asks"},
    {"id": "wrong-when", "when": {"comes-near": {"who": "the toll"}},
     "risk": "torch", "reward": "chalked-map", "say": "a payload key missing"},
    {"id": "nothing-to-risk", "when": {"starts": {}},
     "reward": "chalked-map", "say": "asks for nothing"},
    {"id": "nothing-to-gain", "when": {"starts": {}},
     "risk": "torch", "say": "promises nothing"},
    {"id": "no-line", "when": {"starts": {}},
     "risk": "torch", "reward": "chalked-map"},
    "not even a dict",
]