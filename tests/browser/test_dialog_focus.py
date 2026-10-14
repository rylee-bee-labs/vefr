"""In Chromium, Tab stays inside an open dialog and focus comes back on close.

Issue #462: with a dialog open, one Tab walked out of the box and into the page
behind it - Menu, Messages, Talk, Whisper, Bag, Explore. run-004 recorded it
("keyboard focus during dialogs often drifted to underlying page buttons"), and
run-002 and run-003 found Close and Read on several Tabs away.

The jsdom harness (tests/test_dialog_focus.py) covers the rule; this is the one
that presses a real Tab in a real browser, where the browser itself moves the
focus and nothing about the answer comes from the harness. Two dialogs, opened
the way a player opens them: the pause menu, and a book from the Books panel.
"""

import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_library_pack  # noqa: E402

# The controls of the page behind every dialog: the ones the runs named.
PAGE_CONTROLS = {"menu-open", "toasts-toggle", "talk", "whisper", "bagbtn",
                 "explore", "interact"}

# Where the focus is, and whether it is inside the given box. `label` names the
# control by its words as well as its id, because most buttons in a dialog carry
# no id at all.
WHERE = """(id) => {
  const a = document.activeElement;
  const box = document.getElementById(id);
  return {id: a ? (a.id || '') : 'nothing',
          label: a ? (a.id || (a.textContent || '').trim().slice(0, 24)
                       || a.tagName.toLowerCase()) : 'nothing',
          inside: !!(box && a && box.contains(a) && a !== box),
          inBox: !!(box && a && box.contains(a))};
}"""


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """A woven game with a book on the shelf, woven once for the whole module."""
    d = tmp_path_factory.mktemp("dialog-focus")
    html = d / "library.html"
    html.write_text(cli.weave_html(make_library_pack.build(d)), encoding="utf-8")
    return html


@pytest.fixture
def playing(browser, woven):
    """The woven game, entered as a player enters it."""
    ctx = browser.new_context(viewport={"width": 1100, "height": 1400})
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        page.click("#ts-enter")
        if page.is_visible("#config"):     # first run asks before it plays
            page.click("#cfg-save")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        yield page
    finally:
        ctx.close()


def _tab_walk(page, box, times, shift=False):
    """Press Tab `times` times; return where the focus was after each press."""
    seen = []
    for _ in range(times):
        page.keyboard.press("Shift+Tab" if shift else "Tab")
        seen.append(page.evaluate(WHERE, box))
    return seen


def test_tab_never_leaves_the_pause_menu(playing):
    """The page behind the menu is still focusable; Tab must not walk into it."""
    playing.click("#menu-open")
    playing.wait_for_selector("#menu .carved", state="visible")
    seen = _tab_walk(playing, "menu", 14)
    escaped = [w["label"] for w in seen if not w["inside"] or w["id"] in PAGE_CONTROLS]
    assert not escaped, (
        "Tab left the open menu and landed on: " + str(escaped)
        + " - the page behind a dialog is not where Tab goes (issue #462)")
    assert len({w["label"] for w in seen}) > 1, (
        "every Tab landed on the same control, so the dialog is not being walked: "
        + str(seen))
    # Shift+Tab walks the other way, and it walks the same box.
    back = _tab_walk(playing, "menu", 6, shift=True)
    assert all(w["inside"] for w in back), "Shift+Tab left the open menu: " + str(back)


def test_a_book_keeps_the_focus_and_hands_it_back(playing):
    """Read a book from the Books panel: Tab stays in the reader, and closing
    the book puts the focus back on the control that opened it."""
    playing.click("#menu-open")
    playing.click('#menu [data-panel="books"]')
    playing.click("#book-list button")
    playing.wait_for_selector("#reader .reader-card", state="visible")
    seen = _tab_walk(playing, "reader", 6)
    escaped = [w["label"] for w in seen if not w["inside"] or w["id"] in PAGE_CONTROLS]
    assert not escaped, (
        "Tab left the open book and landed on: " + str(escaped)
        + " - Close and Read on are steps inside the reader (issue #462)")
    assert len({w["label"] for w in seen}) > 1, (
        "every Tab landed on the same control, so the reader is not being walked: "
        + str(seen))
    # Closing a book can earn another (a book that unlocks on `book:<id>`), and
    # the library opens that one straight away; close each until the reader stays shut.
    for _ in range(4):
        playing.click("#reader-close")
        playing.wait_for_timeout(200)
        if playing.is_hidden("#reader"):
            break
    playing.wait_for_selector("#reader", state="hidden")
    where = playing.evaluate(WHERE, "reader")
    assert not where["inBox"] and where["label"] not in ("nothing", "body", "html"), (
        "the focus is still on the closed book, or fell off the page: " + str(where))
    assert where["id"] == "menu-open", (
        "closing a book does not hand the focus back to the control that opened it "
        "(the Menu button): " + str(where))