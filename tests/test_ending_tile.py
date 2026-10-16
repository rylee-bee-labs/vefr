"""A pack's ending room scale: `display.ending_tile` is checked and baked.

The one room a pack may scale itself is the ending room - the room under
the end card a `complete-act` rule opens (cottage-of-the-breeze#166).
`world.json`'s `display` names its drawn tile as `ending_tile`, and the
validator holds it to whole-number pixel steps: a whole multiple of
`display.pixel_art.native_tile`, beside it. Three claims:

1. the validator accepts a whole multiple of the art's native tile (64
   for a native tile of 32) and refuses any other value (48), naming
   `display.ending_tile` and the multiple rule in the sentence;
2. a value the table refuses on its own (a wrong type, a number out of
   range) is answered once, by that sentence, and never twice;
3. the value rides the loaded pack and the woven world unchanged, and a
   pack that names no `ending_tile` is never asked about at all.

The drawing itself - the end card's room at that tile, stepped down to
the largest multiple that fits the window - is checked in the browser
suite (tests/browser/test_ending_tile.py).
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


@pytest.mark.parametrize("ending", [32, 64, 96])
def test_a_whole_multiple_of_the_native_tile_is_accepted(ending):
    assert _errors({"pixel_art": {"native_tile": 32}, "ending_tile": ending}) == []


def test_48_for_a_native_tile_of_32_is_refused_naming_the_multiple():
    (line,) = _errors({"pixel_art": {"native_tile": 32}, "ending_tile": 48})
    assert line.startswith("world.json: /display/ending_tile")
    assert "display.ending_tile" in line
    assert "whole multiple of display.pixel_art.native_tile" in line
    assert "64 for a native_tile of 32" in line


def test_ending_tile_without_pixel_art_is_refused():
    (line,) = _errors({"ending_tile": 64})
    assert line.startswith("world.json: /display/ending_tile")
    assert "whole multiple of display.pixel_art.native_tile" in line
    assert "declares no pixel_art" in line


def test_a_value_out_of_range_is_answered_once_by_the_table():
    (line,) = _errors({"pixel_art": {"native_tile": 32}, "ending_tile": 600})
    assert "display.ending_tile" in line
    assert "from 8 to 512" in line


@pytest.mark.parametrize("bad", [32.0, True, "64", None])
def test_a_value_that_is_not_a_whole_number_is_answered_once(bad):
    (line,) = _errors({"pixel_art": {"native_tile": 32}, "ending_tile": bad})
    assert "display.ending_tile" in line
    assert "whole number of CSS pixels" in line


def test_a_native_tile_the_table_refused_is_not_stepped_against():
    """One sentence per key: the art's own range error speaks, and the
    multiple check does not pile a second sentence about it on."""
    (line,) = _errors({"pixel_art": {"native_tile": 100}, "ending_tile": 64})
    assert "display.pixel_art.native_tile" in line
    assert "display.ending_tile" not in line


def test_a_pack_with_ending_tile_loads_validates_and_bakes_it(tmp_path):
    display = {"pixel_art": {"native_tile": 32}, "ending_tile": 64}
    pack = _pack(tmp_path, display)
    assert maplab.load_pack(pack)["display"] == display
    assert maplab.validate(maplab.load_pack(pack), pack_dir=pack) == []
    assert _baked_world(cli.weave_html(pack))["display"] == display


def test_a_pack_that_names_no_ending_tile_is_never_asked_about():
    assert _errors({}) == []
    assert _errors({"pixel_art": {"native_tile": 32}}) == []
    assert _errors({"phone_tile": 52, "look": "plain"}) == []