"""A pack's `display.phone_tile`: the drawn tile of a touch phone whose map is too big to fit (P2CAM).

A pack opts in with `"display": {"phone_tile": N}` in world.json, N a whole number from 32 to 72. Anything else is
one plain sentence naming `display`. A pack without it is unchanged, and the woven player carries the number only
when the pack declares it.
"""

import re

import pytest

from vefr import maplab, shapes

import play_kit


def build(tmp_path, display=None):
    patch = {"world.json": {"display": display}} if display is not None else None
    return play_kit.pack(tmp_path, "lock", patch)


def display_problems(tmp_path, display):
    pack = build(tmp_path, display)
    return maplab.display_errors(maplab.load_pack(pack))


@pytest.mark.parametrize("n", [32, 52, 72])
def test_a_phone_tile_in_range_validates(tmp_path, n):
    assert display_problems(tmp_path, {"phone_tile": n}) == []


@pytest.mark.parametrize("bad", [31, 73, 0, 52.5, "52", True, [52]])
def test_a_phone_tile_out_of_range_or_wrong_type_is_named(tmp_path, bad):
    errs = display_problems(tmp_path, {"phone_tile": bad})
    assert errs and all("display" in e and "phone_tile" in e for e in errs), errs


def test_an_unknown_display_key_is_named(tmp_path):
    errs = display_problems(tmp_path, {"phone_tile": 52, "zoom": 2})
    assert errs and "zoom" in errs[0], errs


def test_a_pack_without_display_is_unchanged(tmp_path):
    assert display_problems(tmp_path, None) == []


def test_the_range_is_the_shape_table(tmp_path):
    key = next(k for k in shapes.DISPLAY.keys if k.name == "phone_tile")
    assert (key.lo, key.hi) == (32, 72)


def test_the_woven_player_carries_phone_tile_only_when_declared(tmp_path):
    with_tile = play_kit.weave(build(tmp_path / "a", {"phone_tile": 52}), tmp_path / "a")
    assert re.search(r'"phone_tile"\s*:\s*52', with_tile.read_text(encoding="utf-8"))
    without = play_kit.weave(build(tmp_path / "b"), tmp_path / "b")
    assert '"phone_tile"' not in without.read_text(encoding="utf-8")
