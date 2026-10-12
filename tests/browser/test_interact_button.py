"""The one-button Interact verb, played in a real browser (Chromium).

The same fixture shape as tests/browser/test_one_step.py's `woven` -
build a single-file player, serve it over http, click Begin, wait for
window.VEFR_COMBAT - with one deliberate deviation: this weaves the
interact fixture pack (tests/fixtures/make_interact_pack.py) instead of
the sample world, because the verb needs a resident, a door, a chest
and a trader standing on pinned tiles. Routes, spot coordinates and
every pinned string match tests/test_interact_play.py's jsdom run, so
the two files pin the same numbers through two different engines.

The keys are sent as real browser key events (page.keyboard.press),
never synthetic DOM events, and the active element is blurred first:
the dpad and the title buttons are real BUTTONs, and Space/Enter on a
focused button belongs to the button, not to the player's keydown
handler.

Without `uv run playwright install chromium` these skip - that is the
expected result on a machine with no browser (fixtures.py's browser
fixture), not a failure.
"""

import argparse
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
MAKE = ROOT / "tests" / "fixtures" / "make_interact_pack.py"

# The four keys the verb answers to, under the names this file logs
# them by; the value is what page.keyboard.press() sends.
KEYS = ["e", "space", "enter", "f"]
PRESS = {"e": "e", "space": "Space", "enter": "Enter", "f": "f"}

NUDGE = "Nothing to use here. Walk up to something and try again."
NOTHING_HINT = "Nothing near you to use yet."
LINE_A = ("Ask me again at dawn, when the lock is warm. "
          "The gate is heavy, but it opens for anyone who knocks.")
LINE_B = ("The gate is heavy, but it opens for anyone who knocks. "
          "Ask me again at dawn, when the lock is warm.")
RESIDENT_LINES = {"e": LINE_A, "space": LINE_A,
                  "enter": LINE_B, "f": LINE_B}

# Walk routes over the pinned town (see make_interact_pack.py); each
# ends on that target's standing spot. The same walks the jsdom
# harness takes, one arrow keypress per tile.
ARROW = {"up": "ArrowUp", "down": "ArrowDown",
         "left": "ArrowLeft", "right": "ArrowRight"}
TO_RESIDENT = ["down", "down", "right", "right", "up", "right"]   # [4, 2]
TO_CHEST = TO_RESIDENT + ["right", "right", "right"]              # [7, 2]
TO_DOOR = TO_CHEST + ["down", "down", "right", "right"]           # [9, 4]
TO_TRADER = TO_DOOR + ["left", "left", "left"]                    # [6, 4]
TO_EMPTY = TO_TRADER + ["left"] * 5 + ["down"]                    # [1, 5]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """A woven single-file player for the interact fixture pack, served
    over http (so localStorage behaves the way it does for a player)."""
    home = tmp_path_factory.mktemp("interact-button-home")
    made = subprocess.run(
        [sys.executable, str(MAKE), str(home)],
        capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    pack = Path(made.stdout.strip())
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / "interact.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/interact.html"
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def open_woven(page, url):
    """Open the woven file, pin the save seed, step through the title
    screen, and leave the page with no focused button (Space and Enter
    belong to the player only when a BUTTON does not hold focus)."""
    page.goto(url)
    page.evaluate("localStorage.setItem('vefr-save-seed', '42')")
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    page.evaluate("document.activeElement && document.activeElement.blur()")


def walk(page, dirs):
    """One arrow keypress per tile, along the pinned route."""
    for d in dirs:
        page.keyboard.press(ARROW[d])
    page.evaluate(
        "() => new Promise(r => "
        "requestAnimationFrame(() => requestAnimationFrame(r)))")


def hero_at(page):
    """The hero's tile, from the same snapshot the browser suite reads."""
    return page.evaluate("window.VEFR_COMBAT.hero.at")


def snap(page):
    return page.evaluate("JSON.parse(JSON.stringify(window.VEFR_COMBAT))")


def txt(page, element_id):
    return page.text_content(f"#{element_id}")


def words(page):
    """The words the verb shows before a press: hint line, button
    label, and the button's hidden/disabled flags."""
    return {
        "hint": txt(page, "use-hint"),
        "label": txt(page, "interact-label"),
        "hidden": page.eval_on_selector("#interact", "el => el.hidden"),
        "disabled": page.eval_on_selector("#interact", "el => el.disabled"),
    }


def press(page, key):
    """One real keydown of an interact key, with focus cleared first."""
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.keyboard.press(PRESS[key])


def test_the_four_keys_each_talk_to_the_resident(page, woven):
    """On the resident's pinned spot [4, 2], E, Space, Enter and F each
    open the speech box in a real browser: hint and button both name
    the porter before every press, the note says where the line came
    from, #near stays clear, and not one turn passes."""
    open_woven(page, woven)
    walk(page, TO_RESIDENT)
    assert hero_at(page) == [4, 2]
    for k in KEYS:
        before = words(page)
        assert before["hint"] == "Talk to the porter", k
        assert before["label"] == "Talk to the porter", k
        assert before["hidden"] is False, k
        assert before["disabled"] is False, k
        state = snap(page)
        press(page, k)
        page.wait_for_function(
            "() => !document.getElementById('npc-box').hidden")
        assert txt(page, "npc-name") == "the porter", k
        assert txt(page, "npc-line") == RESIDENT_LINES[k], k
        assert txt(page, "npc-note") == "From this character's own lines.", k
        assert txt(page, "near") == "", k
        assert words(page)["hint"] == "Talk to the porter", k
        assert words(page)["label"] == "Talk to the porter", k
        # Talking is not a turn: the whole fight state is untouched.
        assert snap(page) == state, k
        page.click("#npc-close")


@pytest.mark.parametrize("k", KEYS, ids=KEYS)
def test_each_key_goes_through_the_door(page, woven, k):
    """Each of the four keys walks through: region cellar, arrival at
    the cellar's pinned [1, 1], and the words behind fall back to idle."""
    open_woven(page, woven)
    walk(page, TO_DOOR)
    assert hero_at(page) == [9, 4]
    before = words(page)
    assert before["hint"] == "Go through the door"
    assert before["label"] == "Go through the door"
    assert before["hidden"] is False
    assert before["disabled"] is False
    press(page, k)
    state = snap(page)
    assert state["region"] == "cellar", k
    assert state["hero"]["at"] == [1, 1], k
    assert txt(page, "use-hint") == NOTHING_HINT, k
    assert txt(page, "interact-label") == "Interact", k


@pytest.mark.parametrize("k", KEYS, ids=KEYS)
def test_each_key_opens_the_chest(page, woven, k):
    """Each of the four keys opens the reader on The Gate Ledger and
    gives both drops, with #near clear and the button still shown."""
    open_woven(page, woven)
    walk(page, TO_CHEST)
    assert hero_at(page) == [7, 2]
    before = words(page)
    assert before["hint"] == "Open the chest"
    assert before["label"] == "Open the chest"
    assert before["hidden"] is False
    assert before["disabled"] is False
    press(page, k)
    assert page.eval_on_selector("#reader", "el => el.hidden") is False, k
    assert txt(page, "reader-title") == "The Gate Ledger", k
    assert snap(page)["bag"] == ["cloudy-potion", "brass-ring"], k
    assert txt(page, "near") == "", k
    assert txt(page, "use-hint") == NOTHING_HINT, k
    assert txt(page, "interact-label") == "Interact", k


@pytest.mark.parametrize("k", KEYS, ids=KEYS)
def test_each_key_opens_the_trade_panel(page, woven, k):
    """Each of the four keys opens the trade panel on the trader's own
    name, the words after the press still offer the trade, and opening
    a panel spends no turn."""
    open_woven(page, woven)
    walk(page, TO_TRADER)
    assert hero_at(page) == [6, 4]
    before = words(page)
    assert before["hint"] == "Trade with the peddler"
    assert before["label"] == "Trade with the peddler"
    assert before["hidden"] is False
    assert before["disabled"] is False
    state = snap(page)
    press(page, k)
    assert page.eval_on_selector("#trade", "el => el.hidden") is False, k
    assert txt(page, "trade-title") == "the peddler", k
    assert txt(page, "use-hint") == "Trade with the peddler", k
    assert txt(page, "interact-label") == "Trade with the peddler", k
    assert snap(page) == state, k


def test_with_nothing_in_reach_the_keys_nudge_and_spend_no_turn(page, woven):
    """On the empty spot [1, 5] the hint is the idle line and the
    button carries its dim class; every one of the four keys writes the
    friendly nudge into #near, and full snapshots either side prove not
    one turn slipped through."""
    open_woven(page, woven)
    walk(page, TO_EMPTY)
    assert hero_at(page) == [1, 5]
    idle = words(page)
    assert idle["hint"] == NOTHING_HINT
    assert idle["label"] == "Interact"
    assert idle["hidden"] is False
    assert idle["disabled"] is False
    assert page.eval_on_selector(
        "#interact", "el => el.classList.contains('gbtn--dim')") is True
    state = snap(page)
    for k in KEYS:
        press(page, k)
        page.wait_for_function(
            "() => document.getElementById('near').textContent.length > 0")
        assert txt(page, "near") == NUDGE, k
        assert txt(page, "use-hint") == NOTHING_HINT, k
        assert txt(page, "interact-label") == "Interact", k
        assert snap(page) == state, k


def test_the_interact_button_itself_opens_the_chest(page, woven):
    """Clicking #interact itself - the mouse, not a key - still opens
    the reader on The Gate Ledger and gives both drops: the button
    never went hidden or disabled under the wiring."""
    open_woven(page, woven)
    walk(page, TO_CHEST)
    before = words(page)
    assert before["hidden"] is False
    assert before["disabled"] is False
    page.click("#interact")
    assert page.eval_on_selector("#reader", "el => el.hidden") is False
    assert txt(page, "reader-title") == "The Gate Ledger"
    assert snap(page)["bag"] == ["cloudy-potion", "brass-ring"]


def test_the_talk_button_still_talks(page, woven):
    """The old Talk button takes the same nearest-speaker road in a
    real browser: pressed on the resident's spot, the speech box opens
    and names the porter, with nothing nagging in #near."""
    open_woven(page, woven)
    walk(page, TO_RESIDENT)
    assert hero_at(page) == [4, 2]
    page.click("#talk")
    page.wait_for_function(
        "() => !document.getElementById('npc-box').hidden")
    assert txt(page, "npc-name") == "the porter"
    assert txt(page, "near") == ""
