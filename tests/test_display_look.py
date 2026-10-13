"""A pack's `display.look`: the look a skinned pack starts on (docs/guides/world-creation.md).

`"plain"` starts on the engine's dark look with the skin one tap away in Display; `"skin"`, or no look at all,
starts painted. Anything else is one plain sentence naming `display.look`.
"""

import pytest

from vefr import maplab

import play_kit


def display_problems(tmp_path, display):
    pack = play_kit.pack(tmp_path, "lock", {"world.json": {"display": display}})
    return maplab.display_errors(maplab.load_pack(pack))


@pytest.mark.parametrize("look", ["plain", "skin"])
def test_a_named_look_validates(tmp_path, look):
    assert display_problems(tmp_path, {"look": look}) == []


@pytest.mark.parametrize("bad", ["dark", "", 1, True])
def test_any_other_look_is_named(tmp_path, bad):
    errs = display_problems(tmp_path, {"look": bad})
    assert errs and all("display" in e and "look" in e for e in errs), errs
