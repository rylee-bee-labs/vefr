"""A pack's `display.palette`: the look a new player starts on
(docs/guides/world-creation.md).

`"dark"` or `"parchment"` names the one, and the player's own pick in Display
wins over it from then on. Left out, the engine takes no side and the device's
light or dark setting decides, so a pack that says nothing still validates and
plays exactly as it did. Anything else is one plain sentence naming
`display.palette`.

This is the pack-contract half; the setting itself and its three answers are
tests/browser/test_player_look.py.
"""

import pytest

from vefr import maplab

import play_kit


def display_problems(tmp_path, display):
    pack = play_kit.pack(tmp_path, "lock", {"world.json": {"display": display}})
    return maplab.display_errors(maplab.load_pack(pack))


@pytest.mark.parametrize("palette", ["dark", "parchment"])
def test_a_named_palette_validates(tmp_path, palette):
    assert display_problems(tmp_path, {"palette": palette}) == []


@pytest.mark.parametrize("bad", ["sepia", "Plain", "", 1, True])
def test_any_other_palette_is_named(tmp_path, bad):
    errs = display_problems(tmp_path, {"palette": bad})
    assert errs and all("display" in e and "palette" in e for e in errs), errs


def test_a_pack_may_name_both_the_pictures_and_the_palette(tmp_path):
    """`look` is the pack's pictures and `palette` its colours: two different
    choices, and a pack is free to set either or both."""
    assert display_problems(tmp_path, {"look": "plain", "palette": "parchment"}) == []