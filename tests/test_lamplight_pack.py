"""The pack's optional `light` block: what it may hold and every way it can be wrong.

A pack without one validates exactly as before. One with it names the tiles that stand up and how tall, the darkness
per phase, an optional light the hero carries, and lamps per region, each lit by an optional rule flag. The player side
is `tests/test_lamplight_player.py` and `tests/browser/test_lamplight.py`.
"""

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import maplab

SAMPLE = Path(__file__).resolve().parents[1] / "worlds" / "sample-world"


@pytest.fixture(scope="module")
def sample():
    return maplab.load_pack(SAMPLE)


def lit(sample, light, flags=None):
    w = copy.deepcopy(sample)
    w["flags"] = flags if flags is not None else {"lamp-lit": "The lamp by the door is lit."}
    w["light"] = light
    return w


WHOLE = {
    "stand": {"stone-wall": 1, "rock": 0.5},
    "ambient": {"dusk": "#14141f", "dawn": "#6a6670"},
    "hero": {"reach": 1.5, "height": 1.3, "intensity": 2, "color": "#ffd694"},
    "lamps": {"town": [{"at": [1, 1], "height": 2.2, "reach": 2.4, "intensity": 2.4, "color": "#ffdb99",
                        "flag": "lamp-lit"},
                       {"at": [10, 8]}]},
}


def test_a_pack_without_light_has_no_light_errors(sample):
    assert maplab.light_errors({}) == []
    assert maplab.light_errors(sample) == []


def test_a_whole_light_block_is_clean(sample):
    w = lit(sample, WHOLE)
    assert maplab.light_errors(w) == []
    assert maplab.validate(w) == []


def test_one_colour_may_darken_every_phase(sample):
    assert maplab.light_errors(lit(sample, {"ambient": "#101018"})) == []


def _said(w) -> str:
    return "\n".join(maplab.light_errors(w))


def test_unknown_keys_and_wrong_types_are_named(sample):
    assert "glow" in _said(lit(sample, {"glow": 1}))
    assert "light.stand" in _said(lit(sample, {"stand": {"stone-wall": "tall"}}))
    assert "#rrggbb" in _said(lit(sample, {"ambient": {"dusk": "orange"}}))
    assert "#rrggbb" in _said(lit(sample, {"hero": {"color": "warm"}}))
    assert "light.hero" in _said(lit(sample, {"hero": {"wattage": 60}}))
    assert "light" in _said(lit(sample, ["not", "an", "object"]))


def test_heights_are_a_quarter_to_three_tiles_and_at_most_three_of_them(sample):
    assert "stone-wall" in _said(lit(sample, {"stand": {"stone-wall": 0.1}}))
    assert "stone-wall" in _said(lit(sample, {"stand": {"stone-wall": 3.5}}))
    four = {"stone-wall": 1, "rock": 0.5, "crate": 0.75, "tower": 2}
    assert "at most three heights" in _said(lit(sample, {"stand": four}))
    assert maplab.light_errors(lit(sample, {"stand": {"stone-wall": 1, "rock": 1, "crate": 0.5, "tower": 2}})) == []


def test_lamps_name_a_declared_region_a_tile_on_its_map_and_a_declared_flag(sample):
    assert "harbour" in _said(lit(sample, {"lamps": {"harbour": [{"at": [1, 1]}]}}))
    assert "off the map" in _said(lit(sample, {"lamps": {"town": [{"at": [12, 1]}]}}))
    assert "off the map" in _said(lit(sample, {"lamps": {"town": [{"at": [1, 10]}]}}))
    said = _said(lit(sample, {"lamps": {"town": [{"at": [1, 1], "flag": "lamp-out"}]}}))
    assert "lamp-out" in said and "flag" in said
    assert "light.lamps.town[0].at" in _said(lit(sample, {"lamps": {"town": [{"at": [1]}]}}))
    assert "light.lamps.town" in _said(lit(sample, {"lamps": {"town": {"at": [1, 1]}}}))


def test_a_lamp_flag_needs_the_pack_to_declare_flags(sample):
    w = lit(sample, {"lamps": {"town": [{"at": [1, 1], "flag": "lamp-lit"}]}}, flags={})
    assert "lamp-lit" in _said(w)


def test_ambient_names_only_declared_phases(sample):
    said = _said(lit(sample, {"ambient": {"noon": "#000000"}}))
    assert "noon" in said and "phase" in said


def test_the_explain_table_knows_light():
    from vefr import cli

    assert "light" in cli._explain_blocks()


def test_norns_validate_passes_the_sample_world():
    r = subprocess.run([sys.executable, "-c", "import sys; from vefr.cli import norns_main; sys.exit(norns_main())", "validate", "--pack", str(SAMPLE)],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
