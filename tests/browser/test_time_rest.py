"""Time that costs something, in a real browser (vefr E3).

The pack under test declares `"time": {"rest": true, "rail": "locked",
"persist": true}`; a second, otherwise identical pack declares none. The
three answers are checked as a player meets them:

  * one press of Rest turns the watch on by exactly one phase, and fires
    the same `phase-changes` event the rail fires;
  * a locked rail has no jump left to press;
  * a rule that reads the STANDING phase fires only in that phase,
    whatever the event that woke it was;
  * with `persist`, a reload comes back to the phase the last rest left
    at, under one new save key - and a pack with no `time` block plays
    and saves exactly as before.

Every read is a published snapshot (`window.VEFR_TIME`, `window.VEFR_WHY`)
or what the page shows, never a private variable.

Skips without chromium, like the rest of tests/browser.
"""

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_time_pack  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(home: Path, name: str):
    """Serve `home` over http; return the URL of `name` inside it and the
    http process, so the caller can stop it when the module is done."""
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/{name}"
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    return url, proc


def _weave(tmp_path_factory, name: str, **kw):
    home = tmp_path_factory.mktemp(f"time-{name}")
    pack = make_time_pack.build(home, name=name, **kw)
    (home / f"{name}.html").write_text(cli.weave_html(pack), encoding="utf-8")
    return _serve(home, f"{name}.html")


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """The opt-in pack woven and served (Rest, a locked rail, persist)."""
    url, proc = _weave(tmp_path_factory, "time-test")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def plain(tmp_path_factory):
    """The same pack with no `time` block at all."""
    url, proc = _weave(tmp_path_factory, "no-time-test", time_block=None)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def enter(page, url):
    """Enter the woven game the way a player enters it."""
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    if page.is_visible("#config"):     # first run asks before it plays
        page.click("#cfg-offline")
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")


def standing(page) -> dict:
    return page.evaluate("() => window.VEFR_TIME()")


def why_ids(page) -> list:
    return page.evaluate("() => (window.VEFR_WHY || []).map(function (e) { return e.id; })")


def press_rest(page):
    """One press of the Rest verb's own key, the way a player presses it."""
    page.keyboard.press("r")
    page.wait_for_timeout(120)


def menu_is_open(page) -> bool:
    return page.locator("#menu").is_visible()


def open_menu(page):
    """Open the pause menu on its Display panel, which is where the phase
    rail sits."""
    page.keyboard.press("Escape")
    page.locator("#menu").wait_for(state="visible")
    page.locator('[data-panel="display"]').click()
    page.locator('[data-panel-body="display"]').wait_for(state="visible")


def walk_to_the_watcher(page):
    """One step right: the hero stands at [2, 1], one tile from the
    watcher at [3, 1], which is the `comes-near` reach the rule declares."""
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(150)


def talk(page):
    """The Talk button, which is the road that fires `comes-near`, then
    close the speech box it opened."""
    page.locator("#talk").click()
    page.wait_for_timeout(150)
    page.locator("#npc-close").click()
    page.wait_for_timeout(150)


# ---- Rest ----


def test_rest_turns_the_watch_on_by_one_phase_and_fires_the_event(page, woven):
    """One press of Rest moves the watch exactly one phase and fires
    `phase-changes` (the rule on that event says its line). A held key
    is not a second press, and the button on the row does the same."""
    enter(page, woven)
    assert standing(page)["phase"] == "whispers"
    assert standing(page)["rest"] is True
    assert why_ids(page) == []
    press_rest(page)
    assert standing(page)["phase"] == "lowwater", "Rest did not turn the watch"
    assert "the-watch-turns" in why_ids(page), \
        "Rest did not fire the phase-changes event"
    # One press, one phase: the auto-repeat a held key sends is not a
    # second press.
    page.keyboard.press("r")
    page.wait_for_timeout(120)
    assert standing(page)["phase"] == "highwater"
    page.evaluate(
        "() => document.dispatchEvent(new KeyboardEvent('keydown', "
        "{ key: 'r', repeat: true, bubbles: true }))")
    page.wait_for_timeout(120)
    assert standing(page)["phase"] == "highwater", "a held key turned two phases"
    # The button on the action row is the same one press, and it prints
    # the key letter from the one keybinds table.
    assert page.locator("#rest kbd").inner_text() == "R"
    page.locator("#rest").click()
    page.wait_for_timeout(150)
    assert standing(page)["phase"] == "whispers", \
        "one press past the last phase did not come round to the first"
    # A second click while the first is still held off is not a second phase.
    page.locator("#rest").click(timeout=2000, force=True)
    page.wait_for_timeout(150)
    assert standing(page)["phase"] == "whispers", "one press turned two phases"
    page.wait_for_timeout(400)
    page.locator("#rest").click()
    page.wait_for_timeout(150)
    assert standing(page)["phase"] == "lowwater"


# ---- the locked rail ----


def test_a_locked_rail_has_no_jump(page, woven):
    """With `"rail": "locked"` the rail shows no button to press and
    takes up no room: time moves by resting, and by rules."""
    enter(page, woven)
    assert standing(page)["railLocked"] is True
    open_menu(page)
    assert page.locator("#phase button").count() == 0
    assert not page.locator("#phase").is_visible(), \
        "the locked rail is still on screen"
    page.keyboard.press("Escape")
    assert not menu_is_open(page)
    # Nothing else in the game is a phase jump either.
    press_rest(page)
    assert standing(page)["phase"] == "lowwater"


# ---- the standing-phase condition ----


def test_a_rule_reading_the_standing_phase_fires_only_in_that_phase(page, woven):
    """A rule whose `if` reads the phase waits for the right hour: the
    same `comes-near` press is silent in two phases and speaks in the
    third, with nothing else about the event changed."""
    enter(page, woven)
    walk_to_the_watcher(page)
    talk(page)
    assert "boats-may-come-in" not in why_ids(page), \
        "the phase rule fired while the watch stood at whispers"
    press_rest(page)          # lowwater
    talk(page)
    assert "boats-may-come-in" not in why_ids(page), \
        "the phase rule fired while the watch stood at lowwater"
    press_rest(page)          # highwater
    talk(page)
    assert "boats-may-come-in" in why_ids(page), \
        "the phase rule stayed quiet in the phase it names"
    # And the line the rule said is on screen, on the live combat line.
    assert "The boats can come in now." in page.locator("#combat-live").inner_text()


# ---- persist ----


def test_persist_keeps_the_phase_across_a_reload(page, woven):
    """With `"persist": true` the standing phase is saved under its own
    per-world key and a reload starts where the last rest left off."""
    enter(page, woven)
    assert page.evaluate("() => localStorage.getItem('vefr-time-time-test')") is None
    press_rest(page)
    press_rest(page)
    assert standing(page)["phase"] == "highwater"
    assert page.evaluate(
        "() => JSON.parse(localStorage.getItem('vefr-time-time-test'))") \
        == {"v": 1, "phase": "highwater"}
    enter(page, woven)         # a reload, then Begin again
    assert standing(page)["phase"] == "highwater", \
        "a reload forgot the standing phase"
    assert standing(page)["persist"] is True


# ---- a pack that never opted in ----


def test_a_pack_with_no_time_block_plays_and_saves_exactly_as_before(page, plain):
    """No `time` block: no Rest verb, no Rest row in the Controls panel,
    a free jump in the phase rail, R meaning nothing - and not one extra
    byte written to storage when the phase changes."""
    enter(page, plain)
    t = standing(page)
    assert (t["rest"], t["railLocked"], t["persist"]) == (False, False, False)
    assert t["phase"] == "whispers"
    assert page.locator("#rest").count() == 0
    open_menu(page)
    assert page.locator("#phase button").count() == 3
    assert page.locator("#phase").is_visible()
    # The rail is still a free jump, exactly as it always was.
    page.locator("#phase button", has_text="highwater").click()
    page.wait_for_timeout(150)
    assert standing(page)["phase"] == "highwater"
    page.keyboard.press("Escape")
    assert not menu_is_open(page)
    # R is nobody's key in this pack.
    page.keyboard.press("r")
    page.wait_for_timeout(150)
    assert standing(page)["phase"] == "highwater"
    # And no time save was written, before or after the jump.
    keys = page.evaluate(
        "() => Object.keys(localStorage).filter(function (k) {"
        " return k.indexOf('vefr-time') === 0; })")
    assert keys == [], f"a pack with no time block wrote {keys}"
    # The Controls panel lists no Rest row either.
    page.keyboard.press("Escape")
    page.locator('[data-panel="controls"]').click()
    page.locator('[data-panel-body="controls"]').wait_for(state="visible")
    assert page.locator('[data-keybind-keys="rest"]').count() == 0