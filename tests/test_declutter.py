"""The declutter (Rylee, 2026-10-02): Interact is the one big button, the rest are small, the
Dusk/Dawn rail lives in the Menu, and the top bar is just the Menu button.

The REAL woven player is driven in jsdom (tests/fixtures/declutter_harness.mjs). Layout itself
(no overlap, 44 px targets) is measured in a real browser by `vefr look`; here we pin the
structure and the CSS numbers.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "packaged.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def seen(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    home = tmp_path_factory.mktemp("declutter")
    out = home / "w.html"
    out.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    run = subprocess.run(["node", str(ROOT / "tests/fixtures/declutter_harness.mjs"), str(out)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr + run.stdout
    return json.loads(run.stdout)


def test_the_rail_moved_into_the_menu_and_still_works(seen):
    assert seen["railInDisplayPanel"] is True and seen["railInTopBar"] is False
    assert seen["phaseCount"] >= 2 and seen["railButtons"] == seen["phaseCount"]
    assert seen["pressedAfterClick"] == "true" and seen["firstUnpressed"] == "false"


def test_the_top_bar_is_just_the_menu_button(seen):
    assert seen["topBarChildren"] == ["menu-open"]


def test_interact_is_the_one_big_button(seen):
    assert seen["mainButtons"] == ["interact"]


@pytest.mark.parametrize("bid,word,key", [("talk", "Talk", "F"), ("whisper", "Listen", "Q"),
                                          ("bagbtn", "Bag", "B"), ("explore", "Explore", "O")])
def test_each_small_button_keeps_its_word_its_key_and_a_hidden_icon(seen, bid, word, key):
    t = seen["tools"][bid]
    assert t["isTool"] and t["svgHidden"] and not t["gold"]
    assert t["word"] == word                      # the word a screen reader hears
    assert t["key"] == key and f"({key})" in t["title"] and word in t["title"]


def test_explore_keeps_its_pressed_state(seen):
    assert seen["explorePressedAttr"] == "false"


def test_the_small_buttons_meet_the_44px_floor_on_desktop_and_phone():
    rule = re.search(r"\.gbtn--tool \{([^}]*)\}", HTML).group(1)
    assert "min-height: 44px" in rule and "width: 46px" in rule and "height: 46px" in rule
    phone = re.search(r"\.acts \.gbtn--tool \{([^}]*)\}", HTML).group(1)
    assert "width: 48px" in phone and "height: 48px" in phone


def test_the_left_hud_leaves_room_for_the_menu_button():
    """On a phone the health, level and gold row ran under the Menu button (8-38 px, measured).
    The --sai-left/--sai-right come off the width too, so the rounded corners
    the OS keeps at the sides are given back to the row as well."""
    assert re.search(
        r"\.hud--tl \{[^}]*max-width: calc\(100% - 124px - var\(--sai-left\) - var\(--sai-right\)\)", HTML)


def test_a_screen_reader_only_line_takes_no_room():
    """It kept the toast padding and became an invisible 20x10 box over the Messages button."""
    assert re.search(r"\.sr-only, \.quiet[^{]*\{[^}]*padding: 0 !important", HTML)


def test_on_a_phone_the_messages_panel_starts_below_the_wrapped_hud():
    block = HTML[HTML.index("@media (pointer: coarse), (max-width: 700px)"):]
    # The 108 px is the "wrapped HUD" floor; --sai-top is added on top
    # of it so the panel keeps clear of the status bar on phones.
    assert re.search(r"\.toasts \{ top: calc\(108px \+ var\(--sai-top\)\)", block[:2500])


def test_on_the_narrowest_phones_the_messages_panel_makes_room_for_three_hud_rows():
    # The 150 px is the "three HUD rows" floor; --sai-top is added on
    # top of it so the panel keeps clear of the status bar on phones.
    assert re.search(r"@media \(max-width: 400px\) \{ \.toasts \{ top: calc\(150px \+ var\(--sai-top\)\); \} \}", HTML)


def test_the_in_app_help_matches_the_controls():
    """The How to play panel is what a player reads; it was stale after WASD and the declutter."""
    block = HTML[HTML.index('data-panel-body="help"'):]
    block = block[:block.index("</ul>")]
    for needle in ("<kbd>W</kbd>", "<kbd>D</kbd>", "Bag button", "Time of day", "close a shop", "big Interact button"):
        assert needle in block, needle
