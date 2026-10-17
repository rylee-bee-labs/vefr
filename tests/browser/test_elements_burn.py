"""The burn, played in a real browser: WHERE it ticks, and WHAT it says.

The two findings of the vefr#528 review, both proved on a woven file a
player could open, driven by arrow keys:

  * the turn order. The hero acts, the monsters act, and only then do
    the states their blows left tick - the order every pack has always
    had, and the one place the hero's own damage resolves. The case
    pinned here is the review's own: the hero on their last health with
    a burn ticking, an awake hazard beside them. Under the old order the
    fire felled them before the monsters moved and the hazard's blow
    never landed at all; here the hazard strikes first and the `falls`
    event names the hound, not the burning.
  * the words. #hud-state is the line that says a burn is on the hero,
    and it is hidden outright on the `plain` and `investigation`
    surfaces - so an opted-in pack on those surfaces told the player
    nothing at all. Here the pack wears `plain` and the line is shown,
    with the same words the live region says, because a signal that is
    only there for the players who happen to be on another surface is
    not a signal.

The engine half is in tests/test_elements.py; the jsdom play-through
(the same encounter, without a browser) is tests/test_elements_play.py.
Everything read here is what a player and a screen reader get: the
health and the position through the file's own VEFR_COMBAT snapshot,
and the words through #combat-live and #hud-state.
"""

import argparse
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_element_pack as mk  # noqa: E402

# The hazard stands at [2, 4] and the hero wakes at [3, 4], so one press
# of ArrowLeft is the whole encounter: a bump, which strikes.
LEFT = "ArrowLeft"


def _weave(pack: Path, out: Path) -> Path:
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(out), pool=0, with_bundle=False, from_live=None))
    assert rc == 0
    return out


@pytest.fixture(scope="module")
def woven_files(tmp_path_factory):
    """Two woven players on disk: the turn-order fight, and the same
    fight on a `plain` surface."""
    home = tmp_path_factory.mktemp("burn-home")
    packs = {
        # The review's failure case. Three health, the hazard's blow of 1
        # and a burn that ticks 1 leave the hero on their last health
        # with the fire still on them and the hound awake beside them -
        # exactly the state the old order resolved wrongly.
        "order": mk.build(home, name="burn-order", hp=3, atk=2,
                          hound_hp=5, hound_atk=1,
                          burns={"turns": 3, "tick": 1}, rules=mk.FELLED),
        # The same encounter on the quiet surface: the health pill and
        # the level are hidden there, and the state line must not be.
        "plain": mk.build(home, name="burn-plain", hp=8, atk=2,
                          burns=mk.BURNING, surface="plain"),
    }
    return {f"{key}.html": _weave(pack, home / f"{key}.html")
            for key, pack in packs.items()}


@pytest.fixture
def woven(page, woven_files):
    """The two woven files served over http, with nothing else listening.

    A page is answered from the request's own path, so the page's origin
    is a real http one - localStorage and the file's own fetches behave
    the way they do for a player, which a file:// page does not manage.
    No server process, so the same test runs anywhere pytest runs.
    """
    def answer(route):
        name = route.request.url.split("?")[0].rsplit("/", 1)[-1]
        if name not in woven_files:
            return route.fulfill(status=404, content_type="text/plain",
                                 body="not in this woven file")
        return route.fulfill(status=200, content_type="text/html; charset=utf-8",
                             body=woven_files[name].read_text(encoding="utf-8"))

    page.route("**/*", answer)
    yield "http://woven.test"
    page.unroute("**/*")


def open_woven(page, base, key):
    """Open the woven file and step through its title screen."""
    page.goto(f"{base}/{key}.html")
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")


def step(page, key=LEFT):
    """One turn: a keypress, then a frame to let the turn finish."""
    page.keyboard.press(key)
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def state(page):
    return page.evaluate("window.VEFR_COMBAT")


def said(page):
    return page.locator("#combat-live").inner_text()


def burn_words(page):
    return page.locator("#hud-state").inner_text()


# ------------------------------------------------------- 1. where it ticks

def test_the_monsters_act_before_the_burn_ticks(page, woven):
    """The review's failure case, in the order the game has always had.

    Turn one: the hound's blow and the burn it lit both land - the hero
    is on 1 of 3, and the fire has already taken one of its three turns,
    because the tick ran after the monsters rather than before them.

    Turn two, the case the review named: 1 HP, a burn that ticks 1, and
    an awake hazard beside the hero. The hazard strikes - it is the
    hazard's blow that fells the hero, and the pack's own `falls` rule
    says so out loud. The fire never gets its turn on a hero who has
    already woken elsewhere, and the hound's turn is not swallowed.
    """
    open_woven(page, woven, "order")
    start = state(page)
    assert start["hero"] == {"hp": 3, "max": 3, "atk": 2, "at": [3, 4]}
    hound = start["enemies"][0]
    assert hound["id"] == "ember-hound" and hound["at"] == [2, 4]

    # One bump: the hero strikes, the hound answers with 1 and lights a
    # fire that ticks 1 for three turns, and then that fire takes its
    # turn in the same breath - so the hero ends the turn on 1 of 3 with
    # two turns of burning left.
    step(page)
    after = state(page)
    assert after["hero"]["hp"] == 1, after["hero"]
    assert after["hero"]["at"] == [3, 4], after["hero"]
    assert after["statuses"] == [{"effect": "burning", "type": "fire",
                                  "turns": 2, "tick": 1}], after.get("statuses")
    assert burn_words(page) == "Burning (fire, 2 turns left)"

    # And now the review's case exactly: 1 HP, a burn that ticks 1, an
    # awake hazard on the tile beside the hero.
    step(page)
    fell = state(page)
    assert said(page) == "The ember hound felled you.", said(page)
    # The hero is awake and whole again - nothing is left of the fire,
    # which is why the tick below finds nothing to tick.
    assert fell["hero"]["hp"] == 3, fell["hero"]
    assert fell.get("statuses") in (None, []), fell.get("statuses")
    assert burn_words(page) == ""


def test_the_burn_is_never_the_only_thing_that_happens_in_a_turn(page, woven):
    """The control for the case above: on the turn the fire is applied it
    still ticks, because a turn is a turn - it just ticks after the
    monsters have had theirs, and says so while saying what it took."""
    open_woven(page, woven, "order")
    step(page)
    # The hound's blow is said, then the fire it lit, and then the tick:
    # the last of them is the newest thing the live region holds, so the
    # tick is what a player hears last in the turn.
    assert "The fire takes 1 from you." in said(page), said(page)
    assert state(page)["hero"]["hp"] == 1


# -------------------------------------------------------- 2. the words shown

def test_a_plain_surface_still_says_the_burn_in_words(page, woven):
    """The quiet surface hides the health pill and the level. It does not
    hide the line that says a burn is on the hero - and it does not hide
    it only until there is something to say."""
    open_woven(page, woven, "plain")
    assert page.evaluate("document.body.getAttribute('data-surface')") == "plain"

    # With nothing on the hero there is nothing to say, and the line is
    # hidden exactly as it is on any other surface.
    line = page.locator("#hud-state")
    assert not line.is_visible()
    assert not page.locator("#hud-hp").is_visible()   # the quiet surface, on purpose

    step(page)
    lit = state(page)
    assert lit["statuses"], lit
    # THE finding: the line was `display: none` on this surface, so a
    # burning hero here was signalled by nothing at all.
    assert line.is_visible(), "the burn is on the hero and nothing says so"
    assert line.inner_text() == "Burning (fire, 1 turn left)"
    # And the live region says the whole of it in the same turn - the blow
    # that lit the fire, the lighting, and the fire's own tick - so the
    # signal is words for the eye and for a screen reader either way.
    assert "sets you alight" in said(page), said(page)
    assert "The fire takes 2 from you." in said(page), said(page)
    assert lit["hero"]["hp"] == 3, lit["hero"]        # 8, less 3 and less 2

    # The line goes when the fire does, and takes no room while it is empty.
    step(page)
    out_ = state(page)
    assert out_.get("statuses") in (None, []), out_.get("statuses")
    assert not line.is_visible()