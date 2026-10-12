"""A pack's pixel art: `display.pixel_art` is checked, carried, and baked.

The engine draws a pack's art crisply only when the pack says its native
tile size (`world.json`'s `display`). Three claims:

1. the validator accepts a whole number from 8 to 64 and refuses any other
   value, naming `display.pixel_art` in the sentence;
2. the value rides the loaded pack and the woven world, so the player can
   read it;
3. a pack that declares no `display` is never asked about and bakes none.

The player's own snapping and smoothing are checked in the browser suite
(tests/browser/test_pixel_art.py).
"""

import json
import re
import shutil
from pathlib import Path

import pytest

from vefr import cli, maplab

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"


def _baked_world(html: str) -> dict:
    body = re.search(r"window\.VEFR_WORLD = (\{.*\});", html).group(1)
    return json.loads(body)


def _pack(tmp_path, display=None) -> Path:
    """A copy of the shipped sample, with the given `display` block."""
    pack = tmp_path / "a-pack"
    shutil.copytree(SAMPLE, pack)
    if display is not None:
        cfg = json.loads((pack / "world.json").read_text(encoding="utf-8"))
        cfg["display"] = display
        (pack / "world.json").write_text(json.dumps(cfg), encoding="utf-8")
    return pack


def _errors(display) -> list[str]:
    return maplab.display_errors({"display": display})


def test_the_sample_pack_has_no_display_and_is_never_asked_about():
    assert "display" not in maplab.load_pack(SAMPLE)
    assert maplab.validate(maplab.load_pack(SAMPLE), pack_dir=SAMPLE) == []
    assert maplab.display_errors({}) == []


@pytest.mark.parametrize("native", [8, 32, 64])
def test_a_whole_number_from_8_to_64_is_accepted(native):
    assert _errors({"pixel_art": {"native_tile": native}}) == []


@pytest.mark.parametrize("native", [7, 65, 0, -32])
def test_a_number_out_of_range_is_refused_naming_the_key(native):
    (line,) = _errors({"pixel_art": {"native_tile": native}})
    assert "display.pixel_art.native_tile" in line
    assert "from 8 to 64" in line


@pytest.mark.parametrize("native", [32.0, True, "32", None])
def test_a_value_that_is_not_a_whole_number_is_refused_naming_the_key(native):
    (line,) = _errors({"pixel_art": {"native_tile": native}})
    assert "display.pixel_art.native_tile" in line
    assert "whole number" in line


def test_a_pixel_art_block_that_holds_no_size_is_refused():
    (line,) = _errors({"pixel_art": {}})
    assert line.startswith("world.json: /display/pixel_art/native_tile")
    assert "display.pixel_art must hold a native_tile" in line


def test_a_display_that_is_not_an_object_is_refused():
    (line,) = _errors({"pixel_art": 32})
    assert "display.pixel_art must be an object" in line


def test_a_pack_with_pixel_art_loads_validates_and_bakes_it(tmp_path):
    display = {"pixel_art": {"native_tile": 32}}
    pack = _pack(tmp_path, display)
    assert maplab.load_pack(pack)["display"] == display
    assert maplab.validate(maplab.load_pack(pack), pack_dir=pack) == []
    assert _baked_world(cli.weave_html(pack))["display"] == display


def test_a_pack_with_no_display_bakes_none(tmp_path):
    pack = _pack(tmp_path)
    assert "display" not in maplab.load_pack(pack)
    assert '"display":' not in cli.weave_html(pack)
