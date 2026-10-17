"""Issue #502, first step: the optional ambient bed in the always-layer.

Read the way the player's own seams are read (tests/test_sound.py does the
same for the cues): from the published `window.VEFR_*` snapshots and the
Display panel, in a real Chromium, never from the player's private
variables.

What the recorded owner decision asks of this slice, and what is pinned
here: a pack opts in with its own `music` block; the bed is OFF at boot
and nothing is scheduled before the player touches the page (no
unexpected autoplay); the switch and the volume slider are real, keyboard
reachable controls in Display; a pack that did not opt in grows no music
row and no snapshot at all.

Chromium is needed, not node: without a browser these skip unless
VEFR_BROWSER_REQUIRED=1.
"""

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
import play_kit  # noqa: E402

MUSIC = "() => window.VEFR_MUSIC"
MUSIC_VOLUME = "() => window.VEFR_MUSIC_VOLUME"
STORED = """key => localStorage.getItem(key + '-'
           + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world'))"""
# The volume's key is the music key with one word on the end, so it is
# spelled out here rather than glued together from the wrong side.
STORED_VOLUME = """() => localStorage.getItem('vefr-music-'
  + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world') + '-volume')"""
MUSIC_KEY = "vefr-music"

TRACK = {"track": "shore"}


@pytest.fixture(scope="module")
def woven_music(tmp_path_factory):
    """A pack that opted in, so Display builds the music switch and slider."""
    d = tmp_path_factory.mktemp("music-on")
    pack = play_kit.pack(d, "interact", {"world.json": {"music": TRACK}})
    return play_kit.weave(pack, d)


@pytest.fixture(scope="module")
def woven_bare(tmp_path_factory):
    """The same pack without the block: no snapshot, no rows."""
    d = tmp_path_factory.mktemp("music-off")
    return play_kit.weave(play_kit.pack(d, "interact"), d)


@contextmanager
def playing(browser, woven):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        page.click("#ts-enter")
        if page.is_visible("#config"):
            page.click("#cfg-save")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        page.wait_for_timeout(300)
        yield page
    finally:
        ctx.close()


def open_display(page):
    page.click("#menu-open")
    page.click('[data-panel="display"]')


def test_nothing_sounds_until_the_player_asks(browser, woven_music):
    """No unexpected autoplay: the bed is off at boot, however the store
    was left, and no pass of it has been scheduled."""
    with playing(browser, woven_music) as page:
        snap = page.evaluate(MUSIC)
        assert snap == {"track": "shore", "on": False, "playing": False, "starts": 0}, snap
        open_display(page)
        assert page.locator("#music-toggle").is_visible()
        assert not page.is_checked("#music-toggle")


def test_the_switch_starts_the_bed_and_the_bed_loops(browser, woven_music):
    with playing(browser, woven_music) as page:
        open_display(page)
        page.check("#music-toggle")
        page.wait_for_timeout(200)
        snap = page.evaluate(MUSIC)
        assert snap["on"] is True and snap["playing"] is True, snap
        assert snap["starts"] >= 1, snap
        assert page.evaluate(STORED, MUSIC_KEY) == "on"
        # The loop re-arms itself: a second pass is scheduled without any
        # further gesture. The bed is six seconds, so wait past one.
        page.wait_for_timeout(6500)
        assert page.evaluate(MUSIC)["starts"] >= 2, page.evaluate(MUSIC)


def test_unchecking_it_stops_the_bed_and_is_remembered(browser, woven_music):
    with playing(browser, woven_music) as page:
        open_display(page)
        page.check("#music-toggle")
        page.wait_for_timeout(200)
        page.uncheck("#music-toggle")
        page.wait_for_timeout(200)
        snap = page.evaluate(MUSIC)
        assert snap["on"] is False and snap["playing"] is False, snap
        assert page.evaluate(STORED, MUSIC_KEY) == "off"
        # And the choice survives a reload - which still sounds nothing
        # by itself, because the bed waits for this boot's first touch.
        page.reload()
        page.click("#ts-enter")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        page.wait_for_timeout(300)
        snap = page.evaluate(MUSIC)
        assert snap["on"] is False and snap["playing"] is False and snap["starts"] == 0, snap


def test_a_remembered_on_waits_for_this_boots_first_touch(browser, woven_music):
    """The player asked for music last time: the switch comes back ticked
    and the volume comes back too, but the page makes no sound at all
    until this boot's first touch - entering the game is that touch."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()
    try:
        page.goto(woven_music.as_uri())
        page.wait_for_function("window.VEFR_MUSIC", timeout=15000)
        page.evaluate("k => localStorage.setItem(k + '-' + window.VEFR_WORLD.name, 'on')",
                      MUSIC_KEY)
        page.evaluate("k => localStorage.setItem(k + '-' + window.VEFR_WORLD.name + '-volume', '15')",
                      MUSIC_KEY)
        page.reload()
        page.wait_for_function("window.VEFR_MUSIC", timeout=15000)
        page.wait_for_timeout(400)
        snap = page.evaluate(MUSIC)
        assert snap["on"] is True, snap
        assert snap["playing"] is False and snap["starts"] == 0, \
            f"the bed sounded before anyone touched the page: {snap}"
        assert page.evaluate(MUSIC_VOLUME) == pytest.approx(0.15, abs=0.001)
        page.click("#ts-enter")           # the first touch of this boot
        page.wait_for_timeout(400)
        assert page.evaluate(MUSIC)["playing"] is True, page.evaluate(MUSIC)
    finally:
        ctx.close()


def test_the_volume_slider_is_a_control_and_is_remembered(browser, woven_music):
    with playing(browser, woven_music) as page:
        open_display(page)
        # Quiet by default: the slider does not start at full.
        assert page.eval_on_selector("#music-volume", "el => el.value") == "40"
        page.eval_on_selector("#music-volume",
                              "el => { el.value = '70'; el.dispatchEvent(new Event('input')); }")
        assert page.evaluate(MUSIC_VOLUME) == pytest.approx(0.70, abs=0.001)
        assert page.evaluate(STORED_VOLUME) == "70"
        assert page.text_content("#music-volume-out") == "70%"


def test_a_pack_that_did_not_opt_in_has_no_music_at_all(browser, woven_bare):
    with playing(browser, woven_bare) as page:
        assert page.evaluate(MUSIC) is None
        open_display(page)
        assert page.locator("#music-toggle").count() == 0
        assert page.locator("#music-volume").count() == 0