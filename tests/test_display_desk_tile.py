"""A pack's `display.desk_tile`: the follow camera on a screen with a mouse (docs/guides/world-creation.md)."""

import pytest

from vefr import maplab

import play_kit


def display_problems(tmp_path, display):
    pack = play_kit.pack(tmp_path, "lock", {"world.json": {"display": display}})
    return maplab.display_errors(maplab.load_pack(pack))


@pytest.mark.parametrize("n", [32, 48, 96])
def test_a_desk_tile_in_range_validates(tmp_path, n):
    assert display_problems(tmp_path, {"desk_tile": n}) == []


@pytest.mark.parametrize("bad", [31, 97, "48", 4.5])
def test_a_desk_tile_out_of_range_or_wrong_type_is_named(tmp_path, bad):
    errs = display_problems(tmp_path, {"desk_tile": bad})
    assert errs and all("display" in e and "desk_tile" in e for e in errs), errs
