"""The Journal's quiet page and the calm fall card (vefr#484, mockup C).

The Journal panel is one quiet page: every line the world said, newest at
the top, older lines quieter but never lighter than the 4.5:1 floor, and
whispers and falls plain lines among them - no tabs, no chips, no
grouping. One Close at the top, and a Listen for a whisper button beside
the page. The fall is a warm hush: the world dims deep, one small quiet
card near the bottom holds the words the game already says, any key,
tap or button continues, the focus moves onto the card and comes back,
and the reduced-motion blankets make the dim instant.

The pack is the combat fixture (the sample town with a small fight in
it): a merchant stands two tiles away to talk to, a rat beside the hero
to bump, and a pale thing across the room whose hit is the fall. The
hero's health is 3, the rat hits for 1 and the pale thing for 2, so the
walk east is: two bumps that kill the rat, one step onto its drop, and
a step or two more before the pale thing is close enough to strike the
second time - the loop presses east until the card is on screen.

Run with: uv run pytest tests/browser/test_quiet_page.py
"""

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from vefr import cli  # noqa: F401  (weave_html, via play_kit)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
import play_kit  # noqa: E402
from test_teal_contrast import contrast  # noqa: E402  (the WCAG maths, used as it is)

PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 720}

# WCAG 2.1: 4.5 for body text. The page's lines are body text, and the
# quietest line on the page must still clear it.
BODY_FLOOR = 4.5

# The words the game already says, exactly as the costume prints them.
MERCHANT_WHO = "a dusty merchant"
MERCHANT_LINE = "Coin for coin, friend. Nothing here is free."
FALL_LINE = "You fell. You wake in the temple. You lost nothing that mattered."

# The quiet page's own reading, newest first: each line's words, the name
# it was said under (empty for the world's own lines), and whether it is
# the newest one.
LINES = """() => Array.from(document.querySelectorAll('#journal-page li')).map((li) => {
  const q = li.querySelector('q');
  return { words: (q ? q.textContent : li.textContent).trim(),
           who: li.querySelector('.who') ? li.querySelector('.who').textContent.trim() : '',
           newest: li.classList.contains('newest') };
})"""

# What one piece of text reads at, in px.
PX = """sel => { const el = document.querySelector(sel);
              return el ? parseFloat(getComputedStyle(el).fontSize) : null; }"""

# One piece of text and the face behind it: the nearest ancestor that
# paints a background at all, so a line on a transparent list item is
# read against the panel it sits on.
SEEN = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  let face = null;
  for (let cur = el; cur; cur = cur.parentElement) {
    const bg = getComputedStyle(cur).backgroundColor;
    if (bg && bg !== 'rgba(0, 0, 0, 0)') { face = bg; break; }
  }
  const cs = getComputedStyle(el);
  return { color: cs.color, face: face, size: cs.fontSize };
}"""


def _hex(colour: str) -> str:
    """`rgb(r, g, b)` as the `#RRGGBB` the WCAG maths takes."""
    n = [round(float(v)) for v in colour[colour.index("(") + 1:colour.index(")")].split(",")[:3]]
    return "#{:02X}{:02X}{:02X}".format(*n)


def _readable(page, sel: str, what: str) -> None:
    """One piece of the page clears the contrast floor, with the reading."""
    seen = page.evaluate(SEEN, sel)
    assert seen, f"{what} is not on the page at all"
    assert seen["face"], f"{what} has no painted face behind it"
    got = contrast(_hex(seen["color"]), _hex(seen["face"]))
    assert got >= BODY_FLOOR, (
        f"{what} is unreadable: {seen['color']} on {seen['face']} is {got}:1, "
        f"under the {BODY_FLOOR}:1 floor - the words are there but nobody can see them")


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """The combat fixture pack, woven: a merchant to talk to and a fight
    that ends in the fall."""
    d = tmp_path_factory.mktemp("quiet-page")
    pack = play_kit.pack(d, "combat")
    return play_kit.weave(pack, d)


def enter(page):
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    page.wait_for_timeout(300)


@contextmanager
def playing(browser, woven, size=DESKTOP, touch=False):
    ctx = browser.new_context(viewport=size, has_touch=touch, is_mobile=touch)
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        enter(page)
        yield page
    finally:
        ctx.close()


def open_journal(page):
    """The menu opens on the Journal, the way the Bag opens on the Bag."""
    page.click("#menu-open")
    assert page.is_visible('#menu-panel [data-panel-body="journal"]')


def walk_to_a_fall(page):
    """Press east until the pale thing strikes the hero down. The card
    opens inside the press that lands the hit, so the check before each
    press never walks one key into the open card."""
    for _ in range(16):
        if page.evaluate("() => !document.getElementById('fall').hidden"):
            return
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(120)
    pytest.fail("the hero never fell: the walk east found no pale thing")


@pytest.mark.parametrize("size,touch", [(PHONE, True), (DESKTOP, False)],
                         ids=["phone", "desktop"])
def test_every_line_lands_on_the_page_newest_first_and_older_lines_stay_readable(
        browser, woven, size, touch):
    with playing(browser, woven, size, touch) as page:
        # Before anything has been said: one honest empty line, and the
        # page's own two buttons - Close and Listen - and nothing else.
        open_journal(page)
        lines = page.evaluate(LINES)
        assert len(lines) == 1 and lines[0]["words"].startswith("Nothing yet."), lines
        buttons = page.evaluate(
            """() => document.querySelectorAll(
                 '#menu-panel [data-panel-body="journal"] button').length""")
        assert buttons == 2, "the quiet page grew more than Close and Listen"
        page.click("#menu-close")

        # A merchant speaks: the line lands on the page with its name.
        page.eval_on_selector("#talk", "el => el.click()")
        page.wait_for_function("!document.getElementById('npc-box').hidden", timeout=5000)
        page.click("#npc-close")

        # The fight says its lines: a bump is answered, and both lines
        # land, the newest at the top and the older one quieter.
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(150)
        open_journal(page)
        lines = page.evaluate(LINES)
        assert [ln["words"] for ln in lines] == [
            "a cellar rat hits you for 1.", "You hit a cellar rat for 2.", MERCHANT_LINE], lines
        assert lines[0]["newest"] and not lines[1]["newest"] and not lines[2]["newest"], lines
        assert lines[2]["who"] == MERCHANT_WHO, "the spoken line lost its name"
        assert not lines[0]["who"] and not lines[1]["who"], \
            "the fight's lines grew names they were not said with"
        # The newest line and the older, quieter ones all clear the floor.
        _readable(page, "#journal-page li.newest", "the newest line")
        _readable(page, "#journal-page li:not(.newest)", "an older line")
        _readable(page, "#journal-page li .who", "a spoken line's name")

        # The page is the world's own record: it survives a reload.
        page.reload()
        enter(page)
        open_journal(page)
        again = page.evaluate(LINES)
        assert again == lines, "the quiet page did not survive the reload"


def test_a_whisper_and_a_fall_are_plain_lines_on_one_page(browser, woven):
    """The Listen button on the page asks for a whisper, and a whisper and
    a fall sit on the one page as plain lines - interleaved, not grouped."""
    with playing(browser, woven, PHONE, touch=True) as page:
        open_journal(page)
        page.tap("#journal-whisper")
        page.wait_for_function("!document.getElementById('npc-box').hidden", timeout=6000)
        assert page.evaluate("document.getElementById('menu').hidden"), \
            "the menu stayed open over the whisper's speech box"
        page.click("#npc-close")

        walk_to_a_fall(page)
        page.keyboard.press("x")            # any key continues
        page.wait_for_timeout(100)
        open_journal(page)
        lines = page.evaluate(LINES)
        assert lines[0]["words"] == FALL_LINE and lines[0]["newest"], lines
        assert not lines[0]["who"], "the fall's line grew a name it was not said with"
        # The whisper and the fall sit on the one page as plain lines,
        # interleaved with the fight's own lines - not grouped apart.
        assert any(ln["who"].startswith("You overhear ") for ln in lines), \
            f"the whisper never landed on the page: {lines}"
        assert len(lines) > 3, f"the fight's lines were not kept: {lines}"
        # No tabs, no chips, no grouping: one list, nothing else on the page.
        assert not page.evaluate(
            """() => document.querySelectorAll(
                 '#menu-panel [data-panel-body="journal"] ul, '
                 + '#menu-panel [data-panel-body="journal"] [role="tab"]').length""")


def test_the_fall_card_is_a_warm_hush(browser, woven):
    """The fall dims the world deep, holds the words the game already
    says in one small quiet card near the bottom, moves the focus onto
    it and back, and any key continues."""
    with playing(browser, woven) as page:
        page.focus("#interact")
        walk_to_a_fall(page)
        page.wait_for_timeout(300)    # let the dim's fade finish before reading it

        # The card says the words the game already says, with the fall
        # named first - status in words, nothing red, nothing counting.
        assert page.text_content("#fall-line").strip() == FALL_LINE
        # The focus moved onto the card, onto its one button.
        assert page.evaluate(
            "() => document.activeElement && document.activeElement.id") == "fall-keep"
        # The fight is over: the verb row is closed behind the dim.
        assert page.evaluate("() => document.getElementById('verb-row').hidden")

        # The dim: deep and quiet, fading in over a moment.
        dim = page.evaluate("""() => {
          const cs = getComputedStyle(document.getElementById('fall'));
          return { bg: cs.backgroundColor, anim: cs.animationName };
        }""")
        assert dim["bg"] == "rgba(6, 7, 9, 0.78)", f"the world is not dimmed deep: {dim}"
        assert dim["anim"] == "fall-dim", f"the dim does not fade in: {dim}"

        # One small quiet card near the bottom, centred, clear of the
        # verbs at the foot, at the mockup's own size.
        card = page.locator(".fcard").bounding_box()
        pad = page.evaluate(
            "() => parseFloat(getComputedStyle(document.getElementById('fall')).paddingBottom)")
        assert card, "the card is not on the page at all"
        bottom = card["y"] + card["height"]
        assert card["width"] <= 300, f"the card grew past 300px: {card}"
        assert abs((720 - pad) - bottom) <= 2, \
            f"the card does not sit near the bottom: {card}"
        assert bottom - card["height"] / 2 > 720 / 2, f"the card is not in the lower half: {card}"
        assert abs((card["x"] + card["width"] / 2) - 1280 / 2) <= 24, \
            f"the card is not centred: {card}"
        # The card's own words clear the floor, both the line and the note.
        _readable(page, ".fcard .fall-line", "the fall card's line")
        _readable(page, ".fcard .fall-note", "the fall card's note")

        # Any key continues, and the focus comes back to the control
        # that had it.
        page.keyboard.press("x")
        page.wait_for_timeout(100)
        assert page.evaluate("() => document.getElementById('fall').hidden")
        assert page.evaluate(
            "() => document.activeElement && document.activeElement.id") == "interact"


def test_the_fall_is_instant_under_reduced_motion(browser, woven):
    """The player's own reduced-motion switch makes the dim instant: the
    card is simply there, and a tap on the hush continues it."""
    with playing(browser, woven, PHONE, touch=True) as page:
        page.click("#menu-open")
        page.click('[data-panel="display"]')
        page.check("#reduced-motion")
        page.click("#menu-close")
        walk_to_a_fall(page)

        still = page.evaluate("""() => {
          const f = document.getElementById('fall'), c = document.querySelector('.fcard');
          return { dimAnim: getComputedStyle(f).animationName,
                   dimTrans: getComputedStyle(f).transitionDuration,
                   cardAnim: getComputedStyle(c).animationName,
                   cardTrans: getComputedStyle(c).transitionDuration };
        }""")
        assert still == {"dimAnim": "none", "dimTrans": "0s",
                         "cardAnim": "none", "cardTrans": "0s"}, \
            f"the fall card still moves under reduced motion: {still}"

        # A tap anywhere on the hush continues it.
        page.tap("#fall", position={"x": 30, "y": 30})
        page.wait_for_timeout(100)
        assert page.evaluate("() => document.getElementById('fall').hidden")


def test_the_card_and_the_page_read_a_fifth_larger(browser, woven):
    """With larger text on, the page's lines and the card's words grow by
    the same fifth as everything else, and every target stays a 48px
    target."""
    with playing(browser, woven) as page:
        page.click("#menu-open")
        page.click('[data-panel="display"]')
        page.check("#text-large")
        page.click("#menu-close")

        open_journal(page)
        assert page.evaluate(PX, "#journal-page li") == pytest.approx(17 * 1.2, abs=0.3), \
            "the page's lines did not grow a fifth under larger text"
        for sel in ("#journal-close", "#journal-whisper"):
            box = page.locator(sel).bounding_box()
            assert box and box["height"] >= 48, f"{sel} is not a 48px target: {box}"
        page.click("#menu-close")

        walk_to_a_fall(page)
        assert page.evaluate(PX, ".fcard .fall-line") == pytest.approx(17 * 1.2, abs=0.3), \
            "the card's line did not grow a fifth under larger text"
        assert page.evaluate(PX, ".fcard .fall-note") == pytest.approx(13 * 1.2, abs=0.3), \
            "the card's note did not grow a fifth under larger text"
        box = page.locator("#fall-keep").bounding_box()
        assert box and box["height"] >= 48 and box["width"] >= 48, \
            f"the card's one button is not a 48px target: {box}"
        page.click("#fall-keep")
        assert page.evaluate("() => document.getElementById('fall').hidden")