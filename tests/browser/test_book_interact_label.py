"""The Interact button names the note on the ground, in a real browser
(Chromium).

The same fixture shape as tests/browser/test_interact_button.py's
`woven` - build a single-file player, serve it over http, click Begin,
wait for window.VEFR_COMBAT - with one deliberate deviation: this weaves
the book-label fixture pack (tests/fixtures/make_book_label_pack.py)
instead of the sample world, because the label needs a `found: map`
book lying on the map and nothing else in reach to say instead.

The keys are sent as real browser key events (page.keyboard.press),
never synthetic DOM events, and the active element is blurred first.

Without `uv run playwright install chromium` these skip - that is the
expected result on a machine with no browser (conftest's browser
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
MAKE = ROOT / "tests" / "fixtures" / "make_book_label_pack.py"

ARROW = {"up": "ArrowUp", "down": "ArrowDown",
         "left": "ArrowLeft", "right": "ArrowRight"}
# The pinned town of make_book_label_pack.py: hero [1, 1], the note at
# [3, 1]. One press right stands beside it facing it; two stand on it.
TO_BESIDE = ["right"]
TO_ON_IT = TO_BESIDE + ["right"]
TO_EMPTY = ["down"]

READ = "Read A Note Left at the Door"
NOTHING_HINT = "Nothing near you to use yet."


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """A woven single-file player for the book fixture pack, served over
    http (so localStorage behaves the way it does for a player)."""
    home = tmp_path_factory.mktemp("book-label-home")
    made = subprocess.run(
        [sys.executable, str(MAKE), str(home)],
        capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    pack = Path(made.stdout.strip())
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / "book.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/book.html"
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
    return page.evaluate("window.VEFR_COMBAT.hero.at")


def txt(page, element_id):
    return page.text_content(f"#{element_id}")


def words(page):
    """The words the verb shows before a press: hint line and button
    label."""
    return {"hint": txt(page, "use-hint"),
            "label": txt(page, "interact-label")}


def press(page, key):
    """One real keydown of an interact key, with focus cleared first."""
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.keyboard.press(key)


def reader_open(page):
    return page.eval_on_selector("#reader", "el => el.hidden") is False


def test_standing_on_the_note_the_button_names_and_reads_it(page, woven):
    """Standing on the note the button says "Read A Note Left at the
    Door" - not the generic Interact - and one E opens the reader on
    that title."""
    open_woven(page, woven)
    walk(page, TO_ON_IT)
    assert hero_at(page) == [3, 1]
    # Stepping on the note has already opened the reader; close it and
    # the words behind it are the point of this slice.
    page.wait_for_function("() => !document.getElementById('reader').hidden")
    assert txt(page, "reader-title") == "A Note Left at the Door"
    page.click("#reader-close")
    before = words(page)
    assert before["label"] == READ
    assert before["hint"] == READ
    assert page.eval_on_selector(
        "#interact", "el => el.classList.contains('gbtn--dim')") is False
    press(page, "e")
    page.wait_for_function("() => !document.getElementById('reader').hidden")
    assert txt(page, "reader-title") == "A Note Left at the Door"


def test_standing_beside_the_note_facing_it_says_the_same(page, woven):
    """One tile short, facing the note, the same words - and the press
    finds the note and reads it, never having stood on it."""
    open_woven(page, woven)
    walk(page, TO_BESIDE)
    assert hero_at(page) == [2, 1]
    assert reader_open(page) is False
    before = words(page)
    assert before["label"] == READ
    assert before["hint"] == READ
    press(page, "e")
    page.wait_for_function("() => !document.getElementById('reader').hidden")
    assert txt(page, "reader-title") == "A Note Left at the Door"
    assert txt(page, "reader-page-num") == "Page 1 of 2"


def test_away_from_the_note_the_words_are_the_idle_ones(page, woven):
    """Out of reach of the note the label falls back to Interact and the
    hint to the idle line, and the button dims: the naming is reach, not
    the map."""
    open_woven(page, woven)
    walk(page, TO_EMPTY)
    assert hero_at(page) == [1, 2]
    idle = words(page)
    assert idle["label"] == "Interact"
    assert idle["hint"] == NOTHING_HINT
    assert page.eval_on_selector(
        "#interact", "el => el.classList.contains('gbtn--dim')") is True