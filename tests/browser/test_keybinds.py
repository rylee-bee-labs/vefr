"""The keybinds table, in a real browser (vefr #508).

Rylee's decision (2026-10-16, option B): the keys for gameplay, reading,
the Journal, the menu and the always-layer are the player's to change,
with accessible defaults, collision warnings, reset and verification.
This file is the verification: one test per named context, a collision,
a reset, and a save written before the table existed loading as itself.

The woven files are served over http so localStorage behaves the way it
does for a player. Every key is changed the way a player changes one -
Menu, Controls, Change, press - and then played for real: the new key
does the thing, the old key does nothing, and E still answers for
Interact after Interact's own key is replaced (the 2026-10-14 decision,
Rylee, vefr#467, lives on the same road).

Skips without chromium, like the rest of tests/browser.
"""

import argparse
import importlib.util
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
import make_interact_pack  # noqa: E402

MAKE_BOOK = ROOT / "tests" / "fixtures" / "make_book_label_pack.py"

# A note long enough that the reader paginates it, so turning the page
# is a thing the reading keys can be seen to do (the same shape
# tests/browser/test_reader_long_note.py reads).
LONG_NOTE = (
    "---\ntitle: A Note Left at the Door\nfound: map\nat: [3, 1]\n"
    "kind: note\n---\n"
    + "\n\n".join(
        "Somebody knocked and nobody answered, and the knocking went on "
        "through the long grey evening until the lamps were lit. " * 4
        for _ in range(6))
    + "\n\n* * *\n\nThe rest is blank.\n")


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


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """The interact fixture pack (a porter to talk to, a rat to spare),
    woven and served, plus its http process to stop at the end."""
    home = tmp_path_factory.mktemp("keybinds-home")
    html = home / "interact.html"
    html.write_text(cli.weave_html(make_interact_pack.build(home)), encoding="utf-8")
    url, proc = _serve(home, "interact.html")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    """The book-label fixture pack with one LONG note, woven and served,
    so the reading keys have pages to turn (the same fixture shape
    test_reader_long_note.py plays)."""
    home = tmp_path_factory.mktemp("keybinds-book")
    spec = importlib.util.spec_from_file_location("make_book_label_pack", MAKE_BOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BOOK = LONG_NOTE
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(mod.build(home)), out=str(home / "book.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    url, proc = _serve(home, "book.html")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def enter(page, url):
    """Enter the woven game the way a player enters it."""
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    if page.is_visible("#config"):     # first run asks before it plays
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")


def open_controls(page):
    """Open the pause menu, then its Controls panel."""
    page.keyboard.press("Escape")
    page.locator('[data-panel="controls"]').click()
    page.locator('[data-panel-body="controls"]').wait_for(state="visible")


def change_key(page, action, key):
    """Change one action's key the way a player does: Change, press."""
    page.locator(f'button.keybind-change[data-keybind="{action}"]').click()
    page.keyboard.press(key)


def activate_change_with(page, action, key):
    """Focus and activate Change through its native keyboard path."""
    button = page.locator(f'button.keybind-change[data-keybind="{action}"]')
    button.focus()
    page.keyboard.press(key)


def live_text(page) -> str:
    return page.locator("#keybind-live").inner_text()


def keys_of(page, action):
    return page.evaluate(f"() => window.VEFR_KEYBINDS()['{action}']")


def saved_delta(page):
    return page.evaluate(
        "() => JSON.parse(localStorage.getItem('vefr-keybinds') || 'null')")


def walk(page, route):
    """Press the walking keys in `route` (a list of key names), gently."""
    for key in route:
        page.keyboard.press(key)
        page.wait_for_timeout(150)


def hero(page):
    return page.evaluate("() => window.VEFR_COMBAT.hero")


def menu_is_open(page) -> bool:
    return page.locator("#menu").is_visible()


# The pinned walk to the porter's spot [4, 2] (the same route the play
# kit's specs walk), clear of the storeroom rat at [2, 1].
TO_PORTER = ["ArrowDown", "ArrowDown", "ArrowRight", "ArrowRight",
             "ArrowUp", "ArrowRight"]


# ---- gameplay ----


def test_the_gameplay_keys_answer_to_the_players_choice(page, woven):
    """Move down is remapped: the new key walks, and the whole default row
    it replaces (ArrowDown and S) no longer does."""
    enter(page, woven)
    open_controls(page)
    change_key(page, "down", "z")
    assert live_text(page) == "Move down now answers to Z."
    assert keys_of(page, "down") == ["z"]
    assert saved_delta(page) == {"down": ["z"]}
    # The panel is closed with the menu key, and then the map is played.
    page.keyboard.press("Escape")
    assert not menu_is_open(page)
    page.keyboard.press("z")
    assert hero(page)["at"] == [1, 2], "the chosen key did not walk"
    page.keyboard.press("ArrowDown")
    page.keyboard.press("s")
    assert hero(page)["at"] == [1, 2], "a replaced default key still walked"


# ---- reading ----


def test_the_reading_keys_answer_to_the_players_choice(page, book):
    """Turn the page forward is remapped: the chosen key turns the note's
    page, and the defaults it replaced (ArrowRight and D) no longer do."""
    enter(page, book)
    open_controls(page)
    change_key(page, "pageForward", "z")
    page.keyboard.press("Escape")
    walk(page, ["ArrowRight", "ArrowRight"])
    page.locator("#reader").wait_for(state="visible")
    assert page.locator("#reader-page-num").inner_text().startswith("Page 1")
    page.keyboard.press("z")
    assert page.locator("#reader-page-num").inner_text().startswith("Page 2"), \
        "the chosen key did not turn the page"
    page.keyboard.press("d")
    page.keyboard.press("ArrowRight")
    assert page.locator("#reader-page-num").inner_text().startswith("Page 2"), \
        "a replaced default key still turned the page"
    page.locator("#reader-close").click()


# ---- Journal ----


def test_the_journal_key_opens_the_journal(page, woven):
    """Open the Journal is remapped: the chosen key opens the menu on its
    Journal panel, and the key it replaced no longer opens anything."""
    enter(page, woven)
    open_controls(page)
    change_key(page, "journal", "n")
    page.keyboard.press("Escape")
    assert not menu_is_open(page)
    page.keyboard.press("j")
    assert not menu_is_open(page), "the replaced key still opened the Journal"
    page.keyboard.press("n")
    assert menu_is_open(page)
    assert page.locator('[data-panel-body="journal"]').is_visible(), \
        "the Journal key opened the menu somewhere other than the Journal"
    assert not page.locator('[data-panel-body="controls"]').is_visible()


# ---- menu ----


def test_the_menu_key_opens_and_closes_on_the_chosen_key(page, woven):
    """The menu key is remapped: the chosen key opens and closes the menu,
    and Escape - the default it replaced - no longer does either."""
    enter(page, woven)
    open_controls(page)
    change_key(page, "menu", "m")
    page.keyboard.press("m")           # the new key closes the menu itself
    assert not menu_is_open(page)
    page.keyboard.press("Escape")
    assert not menu_is_open(page), "the replaced key still opened the menu"
    page.keyboard.press("m")
    assert menu_is_open(page)
    page.keyboard.press("m")
    assert not menu_is_open(page)


# ---- the always-layer ----


def test_the_interact_key_works_on_every_surface_after_replacing_f(page, woven):
    """Interact is the always-layer: one chosen key that talks to the
    porter, continues his speech, and the shipped key letter follows it.
    F no longer answers, and E still does - the unadvertised alias rides
    the same Interact check after the remap as before it."""
    enter(page, woven)
    open_controls(page)
    change_key(page, "interact", "g")
    assert page.locator("#interact kbd").inner_text() == "G"
    assert page.locator("#talk").get_attribute("title") == "Talk (G)"
    page.keyboard.press("Escape")
    assert not menu_is_open(page)
    walk(page, TO_PORTER)
    page.keyboard.press("f")
    assert page.locator("#npc-box").is_hidden(), \
        "F still answered for Interact after being replaced"
    page.keyboard.press("g")
    page.locator("#npc-box").wait_for(state="visible")
    assert page.locator("#npc-name").inner_text() == "THE PORTER"
    # The same chosen key continues the speech: it means the same thing
    # on the panel as it did on the map.
    page.keyboard.press("g")
    page.locator("#npc-box").wait_for(state="hidden")
    # And E, never in the table and never advertised, still answers.
    page.keyboard.press("e")
    page.locator("#npc-box").wait_for(state="visible")
    assert page.locator("#npc-name").inner_text() == "THE PORTER"


# ---- collision ----


def test_a_key_another_action_answers_to_is_refused_with_the_reason(page, woven):
    """A key that already answers for something on a shared surface is
    refused with a sentence that says why - and B, already the bag's,
    refuses the whisper row without changing it. Esc cancels a capture
    and changes nothing; E is refused for any action, kept for Interact."""
    enter(page, woven)
    open_controls(page)
    # Esc stands a capture down: nothing changed, nothing saved.
    page.locator('button.keybind-change[data-keybind="whisper"]').click()
    page.keyboard.press("Escape")
    assert live_text(page) == "Cancelled. Nothing was changed."
    assert saved_delta(page) is None
    change_key(page, "whisper", "b")
    assert live_text(page) == "B already answers for Open the bag. Choose a different key."
    assert keys_of(page, "whisper") == ["q"], "the refused key was taken anyway"
    assert saved_delta(page) is None
    change_key(page, "whisper", "e")
    assert live_text(page) == "That key is kept for Interact. Choose a different key."
    assert saved_delta(page) is None
    # The way out is in the same breath: a different key is taken.
    change_key(page, "whisper", "p")
    assert live_text(page) == "Listen for a rumor now answers to P."
    assert saved_delta(page) == {"whisper": ["p"]}


def test_reserved_browser_shortcuts_leave_capture_waiting(page, woven):
    """F5 and Ctrl+R are the browser's own, so the capture passes them by:
    it says why, binds nothing, and goes on waiting for a key that is
    the player's to give."""
    enter(page, woven)
    open_controls(page)
    change = page.locator('button.keybind-change[data-keybind="whisper"]')
    change.click()
    page.keyboard.press("F5")
    assert "F5" in live_text(page)
    page.keyboard.press("Control+r")
    assert keys_of(page, "whisper") == ["q"], "a reserved key was bound anyway"
    assert change.inner_text().strip().lower() == "press a new key", \
        "the capture stood down on a key the browser keeps"
    page.keyboard.press("p")
    assert keys_of(page, "whisper") == ["p"]


@pytest.mark.parametrize("activation", ["Enter", "Space"])
def test_native_activation_key_does_not_end_capture(page, woven, activation):
    """A Change button opened the way a keyboard opens it - Enter or Space
    on the focused button - is still waiting for a key when that press is
    over, including when the key was held down and auto-repeated."""
    enter(page, woven)
    open_controls(page)
    button = page.locator('button.keybind-change[data-keybind="whisper"]')
    activate_change_with(page, "whisper", activation)
    assert keys_of(page, "whisper") == ["q"], \
        "the activating key was bound instead of being waited out"
    assert button.inner_text().strip().lower() == "press a new key", \
        "the capture ended on the press that opened it"
    page.keyboard.press("p")
    assert keys_of(page, "whisper") == ["p"]


def test_a_held_activation_key_does_not_end_capture(page, woven):
    """An Enter that is held down goes on sending keydowns while it is
    held. The capture waits that press out instead of answering the first
    repeat with the Space-and-Enter refusal, which used to stand the
    capture the player had just opened back down."""
    enter(page, woven)
    open_controls(page)
    button = page.locator('button.keybind-change[data-keybind="whisper"]')
    button.focus()
    page.keyboard.down("Enter")
    page.keyboard.down("Enter")
    page.keyboard.up("Enter")
    assert button.inner_text().strip().lower() == "press a new key", \
        "the capture ended while the key that opened it was still down"
    page.keyboard.press("p")
    assert keys_of(page, "whisper") == ["p"]


def test_a_phone_changes_a_key_the_same_way(phone, woven):
    """The same capture on a phone-sized screen: tap Change, press a key,
    and the row answers to it. A capture that only armed itself from the
    keyboard road would swallow every key here."""
    enter(phone, woven)
    open_controls(phone)
    change_key(phone, "whisper", "p")
    assert live_text(phone) == "Listen for a rumor now answers to P."
    assert keys_of(phone, "whisper") == ["p"]


# ---- reset ----


def test_reset_puts_every_default_back(page, woven):
    """One button puts every key back the way it came: the save is gone,
    the rows say their defaults, and the shipped keys walk again while
    the chosen ones no longer do anything."""
    enter(page, woven)
    open_controls(page)
    change_key(page, "whisper", "p")
    change_key(page, "down", "z")
    assert saved_delta(page) == {"whisper": ["p"], "down": ["z"]}
    page.locator("#keybind-reset").click()
    assert live_text(page) == "Every key is back the way it came."
    assert saved_delta(page) is None
    assert keys_of(page, "whisper") == ["q"]
    assert keys_of(page, "down") == ["ArrowDown", "s"]
    page.keyboard.press("Escape")
    assert not menu_is_open(page)
    page.keyboard.press("ArrowDown")
    assert hero(page)["at"] == [1, 2], "the default key did not come back"
    page.keyboard.press("z")
    page.keyboard.press("p")
    assert hero(page)["at"] == [1, 2], "a chosen key outlived the reset"


# ---- a save written before the table existed ----

# Saves a player already has when this part arrives: the hp and slain
# lists the game itself writes, the one-time lesson already done, and a
# keybinds blob from a version that knew a row this one does not.
OLD_SAVES = """() => {
  localStorage.setItem('vefr-hp-interact-test', '2');
  // The player remembers a kill as `id#signature` (name|at|hp|atk|drops),
  // so a bare id is no save at all; write it the way the game does.
  var rat = window.VEFR_ENEMIES.town.filter(function (e) {
    return e.id === 'storeroom-rat';
  })[0];
  var sig = [rat.name, rat.at.join(','), rat.hp, rat.atk,
             (rat.drops || []).map(function (d) {
               return typeof d === 'string' ? d
                 : (d.item || '') + ':' + (d.rarity || '');
             }).join(',')].join('|');
  localStorage.setItem('vefr-slain-interact-test-town',
                       JSON.stringify([rat.id + '#' + sig]));
  localStorage.setItem('vefr-tutorial-interact-test', '1');
  localStorage.setItem('vefr-keybinds',
                       '{"a-row-from-a-newer-version": ["z"]}');
}"""


def test_an_old_save_loads_as_itself(page, woven):
    """A save from before the table existed boots as itself: the old keys
    are honored (the health, the slain rat, the lesson done), every
    action answers to its default, and the unknown row another version
    wrote is kept, not read and not erased."""
    page.goto(woven)
    page.evaluate(OLD_SAVES)
    page.get_by_role("button", name="Begin").click()
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    # The old save's own keys are honored exactly as before.
    assert hero(page)["hp"] == 2
    # VEFR_COMBAT.enemies keeps the dead on the roster (alive: false); the save is honored when none is alive
    assert page.evaluate("() => window.VEFR_COMBAT.enemies.filter(e => e.alive)") == [], \
        "the slain rat from the old save came back"
    assert page.locator("#status").get_attribute("data-tutorial") is None, \
        "the one-time lesson the old save already took is being taught again"
    # And the keys are the shipped defaults, playable as they always were.
    assert keys_of(page, "interact") == ["f"]
    assert keys_of(page, "menu") == ["Escape"]
    page.keyboard.press("ArrowDown")
    assert hero(page)["at"] == [1, 2]
    page.keyboard.press("z")
    assert hero(page)["at"] == [1, 2], "an unknown saved row answered to a key"
    # The row this version knows nothing about is kept as it came.
    assert saved_delta(page) == {"a-row-from-a-newer-version": ["z"]}
