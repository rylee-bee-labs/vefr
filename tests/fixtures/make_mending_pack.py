"""Build the mending fixture pack (sample-world + recipes) for tests.

Neutral engine-test canon only: the sample's own town, four plain items
(two that mend into one, one that fits no recipe), one recipe, and one
rule that reacts to the mend. No story text from any pitch - a torn net
and a loose peg are engine fixtures, not canon.
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

ITEMS = {
    "torn-net": {"name": "a torn net"},
    "loose-peg": {"name": "a loose peg"},
    "whole-net": {"name": "a whole net"},
    "dry-driftwood": {"name": "a piece of dry driftwood"},
}

RECIPES = [
    {"id": "mend-the-net", "inputs": ["torn-net", "loose-peg"],
     "output": "whole-net", "say": "The net is whole again."},
]

RULES = [
    {"id": "the-yard-notices", "when": {"mends": {"recipe": "mend-the-net"}},
     "once": False, "then": [{"say": "The yard trusts you a little more."}]},
]


def build(dest: Path) -> Path:
    pack = dest / "worlds" / "mending-test"
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    # The catalog keys at the pack root - the one place load_pack, the
    # validator and the bake all read them from.
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["name"] = "mending-test"
    world["items"].update(ITEMS)
    world["recipes"] = json.loads(json.dumps(RECIPES))
    world["rules"] = json.loads(json.dumps(RULES))
    world_json.write_text(json.dumps(world), encoding="utf-8")
    return pack