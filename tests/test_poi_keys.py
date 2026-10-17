"""A poi is keyed "x,y" with its label as the value. A pack that keys it by
name gets a validation error naming the shape, not a traceback that stops
`vefr check` (found building The Mending Shift pack, 2026-10-17)."""

import json
import sys
from pathlib import Path

from vefr import maplab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_time_pack as mk  # noqa: E402


def errors_with_pois(tmp_path, pois):
    pack = mk.build(tmp_path)
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["town"]["pois"] = pois
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
    return maplab.validate(maplab.load_pack(pack), pack_dir=pack)


def test_a_name_keyed_poi_is_an_error_not_a_crash(tmp_path):
    errors = errors_with_pois(tmp_path, {"the mooring post": [1, 1]})
    assert any("poi key 'the mooring post' must be \"x,y\"" in e for e in errors), errors


def test_a_coordinate_keyed_poi_still_passes(tmp_path):
    errors = errors_with_pois(tmp_path, {"1,1": "the mooring post"})
    assert not any("poi" in e for e in errors), errors
