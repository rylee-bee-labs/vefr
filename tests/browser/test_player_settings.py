"""The player settings in Display: larger text, reduced motion, and the volume
slider that sits under the Sound switch.

Each one is checked the way the touch settings are (test_touch_controls.py):
turn it on in the panel, prove the page changed, reload, prove it is still on.
Larger text and reduced motion are remembered per world, so the key each one
writes carries the world's name, exactly as the sound and the look keys do.

The volume slider is built only when the pack opted in to sound, like the
switch beside it, so that half runs on a fixture pack that opted in and the
"no slider at all" half on the sample world, which did not.

The last test is the readability floor the approved type scale sets: body at
16px and up, nothing at all under 13px, and the line someone has to read on a
phone (a spoken line) at 16px. Every selector here is one of the rules that
floor was written against.
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

# What one bit of text reads at right now, in px.
PX = """sel => { const el = document.querySelector(sel);
              return el ? parseFloat(getComputedStyle(el).fontSize) : null; }"""

# The body and one label that is sized in rem, so both move together.
SIZES = """() => ({ body: parseFloat(getComputedStyle(document.body).fontSize),
                     tab: parseFloat(getComputedStyle(document.querySelector('#menu .pm button')).fontSize) })"""

# What the store holds, under the world's own name.
STORED = """key => localStorage.getItem(key + '-'
           + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world'))"""

# The volume's key is the sound key with one word on the end, so it is spelled
# out here rather than glued together from the wrong side.
SOUND_VOLUME_KEY = """() => localStorage.getItem('vefr-sound-'
  + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world') + '-volume')"""

TEXT_KEY = "vefr-textsize"
MOTION_KEY = "vefr-reducedmotion"
SOUND_VOLUME = "() => window.VEFR_SOUND_VOLUME"

TRANSITION = """() => getComputedStyle(document.getElementById('toasts')).transitionDuration"""

LIFT = 1.2


@pytest.fixture(scope="module")
def woven_sample(tmp_path_factory):
    """The sample world as shipped: no sound, so no Sound block to find."""
    d = tmp_path_factory.mktemp("settings-sample")
    html = d / "sample.html"
    html.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    return html


@pytest.fixture(scope="module")
def woven_sound(tmp_path_factory):
    """A pack that opted in to sound, so Display builds the switch and the slider."""
    d = tmp_path_factory.mktemp("settings-sound")
    pack = play_kit.pack(d, "interact", {"world.json": {"sound": {"theme": "soft"}}})
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


def open_display(page):
    page.click("#menu-open")
    page.click('[data-panel="display"]')


def test_larger_text_grows_the_body_and_the_labels_and_survives_a_reload(browser, woven_sample):
    with playing(browser, woven_sample) as page:
        open_display(page)
        before = page.evaluate(SIZES)
        assert before["body"] == pytest.approx(16, abs=0.2), before
        page.check("#text-large")
        after = page.evaluate(SIZES)
        assert after["body"] == pytest.approx(before["body"] * LIFT, abs=0.3), \
            f"larger text left the body at {after['body']}px, not a fifth more than {before['body']}px"
        assert after["tab"] == pytest.approx(before["tab"] * LIFT, abs=0.3), \
            f"larger text left a label at {after['tab']}px, not a fifth more than {before['tab']}px"
        assert page.evaluate(STORED, TEXT_KEY) == "1", "the choice was not saved for this world"
        page.reload()
        enter(page)
        open_display(page)
        assert page.is_checked("#text-large"), "larger text did not survive a reload"
        again = page.evaluate(SIZES)
        assert again["body"] == pytest.approx(after["body"], abs=0.3), \
            f"the body reads {again['body']}px after a reload, not {after['body']}px"


def test_reduced_motion_stills_the_page_and_survives_a_reload(browser, woven_sample):
    """On a phone, where the messages fade: with the switch on, the fade is
    gone. The same choice the OS media query would have made, from the panel."""
    with playing(browser, woven_sample, PHONE, touch=True) as page:
        assert page.evaluate(TRANSITION) == "0.25s", \
            f"the messages do not fade at all here: {page.evaluate(TRANSITION)}"
        open_display(page)
        page.check("#reduced-motion")
        assert page.evaluate("document.body.classList.contains('reduced-motion')"), \
            "the switch did not reach the page"
        assert page.evaluate(TRANSITION) == "0s", \
            f"something is still fading with reduced motion on: {page.evaluate(TRANSITION)}"
        assert page.evaluate(STORED, MOTION_KEY) == "1", "the choice was not saved for this world"
        page.reload()
        enter(page)
        assert page.evaluate("document.body.classList.contains('reduced-motion')"), \
            "reduced motion did not survive a reload"
        assert page.evaluate(TRANSITION) == "0s", \
            f"something fades again after a reload: {page.evaluate(TRANSITION)}"


def test_the_volume_slider_only_exists_with_sound_and_is_remembered(browser, woven_sound, woven_sample):
    with playing(browser, woven_sound) as page:
        open_display(page)
        assert page.inner_text("#sound-volume-out") == "100%", "the slider is not full by default"
        page.fill("#sound-volume", "40")
        assert page.inner_text("#sound-volume-out") == "40%"
        assert page.evaluate(SOUND_VOLUME) == pytest.approx(0.4), \
            f"the page still thinks the volume is {page.evaluate(SOUND_VOLUME)}"
        assert page.evaluate(SOUND_VOLUME_KEY) == "40", \
            "the volume was not saved for this world"
        page.reload()
        enter(page)
        open_display(page)
        assert page.input_value("#sound-volume") == "40", "the volume did not survive a reload"
        assert page.evaluate(SOUND_VOLUME) == pytest.approx(0.4)
    # A pack that never opted in has no sound block at all, so nothing to find.
    with playing(browser, woven_sample) as page:
        open_display(page)
        assert page.evaluate("document.getElementById('sound-volume')") is None, \
            "a pack without sound was given a volume slider"
        assert page.evaluate("document.getElementById('sound-toggle')") is None, \
            "a pack without sound was given a Sound switch"


# The approved floor: the body reads at 16px and up, nothing reads under 13px,
# and the spoken line on a phone - the one piece of text a player has to read
# to play - is a full 16px.
FLOORS = [
    (False, "body", 16.0),        # the body itself
    (False, "#menu-open", 13.0),
    (False, "#interact", 13.0),
    (False, "#menu .pm button", 13.0),
    (False, "kbd", 13.0),
    (True, ".npc-line", 16.0),    # what someone says, on a phone
    (True, ".npc-box .speaker", 13.0),
    (True, "#touch-smart .cap", 13.0),
]


@pytest.mark.parametrize("phone,selector,floor", FLOORS, ids=[f"{'phone' if p else 'desk'}-{s}" for p, s, _ in FLOORS])
def test_nothing_reads_under_the_approved_floor(browser, woven_sample, phone, selector, floor):
    size, touch = (PHONE, True) if phone else (DESKTOP, False)
    with playing(browser, woven_sample, size, touch) as page:
        got = page.evaluate(PX, selector)
        assert got is not None, f"{selector} is not on the page at all"
        assert got >= floor, f"{selector} reads at {got}px, under the {floor}px floor"


def test_the_floor_holds_on_the_title_screen_too(browser, woven_sample):
    """The title screen's own words, read on a page nobody has entered."""
    ctx = browser.new_context(viewport=DESKTOP)
    page = ctx.new_page()
    try:
        page.goto(woven_sample.as_uri())
        assert page.evaluate(PX, ".ts-byline") >= 13.0
        assert page.evaluate(PX, "#ts-enter") >= 16.0
    finally:
        ctx.close()