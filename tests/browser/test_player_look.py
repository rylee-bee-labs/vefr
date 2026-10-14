"""The Look setting in Display: Dark and Parchment.

Two looks, the same interface in two faces, and a player setting like any
other: chosen in the panel, proved on the page, remembered over a reload.

The order the three answers can come from is the point of most of this file:

  1. the player's own pick, remembered per world (the key carries the
     world's name, exactly as the text size and the sound keys do);
  2. the pack's starting look, world.json display.palette - a pack that
     names nothing is left alone;
  3. nothing at all, and then the engine takes no side: no attribute on the
     body and the sheet's own default, so the device's own light or dark
     setting decides, exactly as it did before this setting existed.

The last test is the one that keeps that third answer honest: a pack with no
palette and a device in light mode still comes up light, because "Dark is the
default" is where Cottage starts, not a house style VEFR imposes on anyone.
"""

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
import play_kit  # noqa: E402

PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 720}

# What face the page is in: the attribute the setting writes, and the two
# colours that say so on screen (the page's ground and the words on it).
LOOK = """() => { const s = getComputedStyle(document.body);
           return { attr: document.body.getAttribute('data-look'),
                    bg: s.backgroundColor, ink: s.color }; }"""

STORED = """key => localStorage.getItem(key + '-'
           + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world'))"""

LOOK_KEY = "vefr-lookpalette"

# The two grounds, as the browser writes them.
DARK_BG = "rgb(11, 12, 14)"        # #0B0C0E
PARCHMENT_BG = "rgb(231, 215, 180)"  # #e7d7b4
NEUTRAL_LIGHT_BG = "rgb(238, 234, 224)"  # #EEEAE0, the engine's light scheme


@pytest.fixture(scope="module")
def woven_sample(tmp_path_factory):
    """The sample world as shipped: it names no palette, so the engine's own
    neutral default is what a new player gets."""
    d = tmp_path_factory.mktemp("look-sample")
    html = d / "sample.html"
    html.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    return html


@pytest.fixture(scope="module")
def woven_dark(tmp_path_factory):
    """A pack that starts on Dark, the way Cottage does."""
    d = tmp_path_factory.mktemp("look-dark")
    pack = play_kit.pack(d, "interact", {"world.json": {"display": {"palette": "dark"}}})
    return play_kit.weave(pack, d)


@pytest.fixture(scope="module")
def woven_parchment(tmp_path_factory):
    """A pack that starts on Parchment."""
    d = tmp_path_factory.mktemp("look-parchment")
    pack = play_kit.pack(d, "interact", {"world.json": {"display": {"palette": "parchment"}}})
    return play_kit.weave(pack, d)


def enter(page):
    """Through the title screen and into the world, the way the other browser
    tests do it (the endpoint box appears on a first visit and not after)."""
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    page.wait_for_timeout(300)


@contextmanager
def playing(browser, woven, size=DESKTOP, touch=False, scheme=None):
    ctx = browser.new_context(viewport=size, has_touch=touch, is_mobile=touch,
                              color_scheme=scheme)
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        enter(page)
        yield page
    finally:
        ctx.close()


def open_display(page):
    page.click("#menu-open")
    page.click('[data-panel="display"]')


def test_the_look_is_offered_to_everyone_and_switches_the_page(browser, woven_sample):
    with playing(browser, woven_sample) as page:
        open_display(page)
        assert page.is_visible("#look-palette"), "the Look row is not on the panel"
        assert page.locator('#look-palette input[name="look-palette"]').count() == 2, \
            "the Look row is not the two looks"
        before = page.evaluate(LOOK)
        page.check('#look-palette input[value="parchment"]')
        after = page.evaluate(LOOK)
        assert after["attr"] == "parchment", f"the pick did not reach the page: {after}"
        assert after["bg"] != before["bg"], "the ground did not change with the look"
        assert page.evaluate(STORED, LOOK_KEY) == "parchment", \
            "the choice was not saved for this world"


def test_the_look_survives_a_reload(browser, woven_sample):
    with playing(browser, woven_sample) as page:
        open_display(page)
        page.check('#look-palette input[value="parchment"]')
        page.reload()
        enter(page)
        assert page.evaluate(LOOK)["attr"] == "parchment", "the look did not survive a reload"
        open_display(page)
        assert page.is_checked('#look-palette input[value="parchment"]'), \
            "the panel does not show the look that is on"


def test_a_pack_says_which_look_it_starts_on(browser, woven_dark, woven_parchment):
    with playing(browser, woven_dark) as page:
        got = page.evaluate(LOOK)
        assert got["attr"] == "dark", f"a pack that names Dark started on {got}"
        assert got["bg"] == DARK_BG, f"Dark is not the charcoal ground: {got}"
    with playing(browser, woven_parchment) as page:
        got = page.evaluate(LOOK)
        assert got["attr"] == "parchment", f"a pack that names Parchment started on {got}"
        assert got["bg"] == PARCHMENT_BG, f"Parchment is not the cream ground: {got}"


def test_the_players_pick_wins_over_the_packs_starting_look(browser, woven_dark):
    with playing(browser, woven_dark) as page:
        assert page.evaluate(LOOK)["attr"] == "dark"
        open_display(page)
        page.check('#look-palette input[value="parchment"]')
        assert page.evaluate(LOOK)["attr"] == "parchment", \
            "the pack's default came back over the player's own pick"
        page.reload()
        enter(page)
        assert page.evaluate(LOOK)["attr"] == "parchment", \
            "the pack's default came back over the player's pick after a reload"


def test_a_pack_that_says_nothing_leaves_the_device_to_decide(browser, woven_sample):
    """The engine's own default takes no side. On a device in light mode a
    pack that named no palette is still light: 'Dark is the default' is where
    Cottage starts, not something VEFR imposes on every game."""
    with playing(browser, woven_sample, DESKTOP, scheme="light") as page:
        got = page.evaluate(LOOK)
        assert got["attr"] is None, f"the engine chose a look for a neutral pack: {got}"
        assert got["bg"] == NEUTRAL_LIGHT_BG, \
            f"a neutral pack on a light device is not light any more: {got}"
    with playing(browser, woven_sample, DESKTOP, scheme="dark") as page:
        got = page.evaluate(LOOK)
        assert got["attr"] is None, f"the engine chose a look for a neutral pack: {got}"
        assert got["bg"] == DARK_BG, f"a neutral pack on a dark device is not dark: {got}"


def test_parchment_reaches_the_panels_over_the_world_not_only_the_page(browser, woven_parchment):
    """The look paints the game's own panels, not only the page behind them:
    the menu panel and the speech box are cream with dark words on Parchment,
    charcoal with cream ones on Dark. The speech box is measured while it is
    closed - a hidden box still computes its own face, which is the point: the
    panel someone hears is on the look they chose before anyone speaks."""
    faces = """() => { const s = getComputedStyle;
             const box = s(document.querySelector('.npc-box'));
             const panel = s(document.getElementById('menu-panel'));
             return { box: box.backgroundColor, boxInk: box.color,
                      panel: panel.backgroundColor, panelInk: panel.color }; }"""
    dark = {"box": "rgba(21, 24, 29, 0.95)", "boxInk": "rgb(244, 238, 221)",
            "panel": "rgb(21, 24, 29)", "panelInk": "rgb(232, 229, 223)"}
    parchment = {"box": "rgba(244, 236, 216, 0.96)", "boxInk": "rgb(43, 33, 24)",
                 "panel": "rgb(244, 236, 216)", "panelInk": "rgb(43, 33, 24)"}
    with playing(browser, woven_parchment) as page:
        assert page.locator(".npc-box").count() == 1, "the speech box is not on the page at all"
        assert page.evaluate(faces) == parchment, \
            f"a Parchment pack did not paint its panels on cream: {page.evaluate(faces)}"
        open_display(page)
        page.check('#look-palette input[value="dark"]')
        got = page.evaluate(faces)
        assert got == dark, f"switching to Dark left the panels as they were: {got}"