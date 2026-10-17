"""Stakes, in play (vefr#504): the offer, and walking away from it.

The player-visible proof of the one small reversible example this slice
built. The pack is the stakes fixture: the sample town with a toll one
step east of the hero's start, one rule that hands the hero a pitch
torch at Begin, and one stake put to them at the toll - leave the torch
down, and the chalked map may be gained.

What the browser has to show, because a claim in a commit message is not
evidence:

  - the offer is made where the pack's `when` says, in the game's own
    line, naming both costs and the two keys that answer;
  - WALKING AWAY COSTS NOTHING: the hero still holds the torch, has not
    gained the map, and is asked again the next time the toll matches -
    a refusal is not remembered as a refusal, which is what makes this
    reversible rather than a punishment;
  - only the player's own Y stakes it: the torch goes down and the map
    comes into the bag, in the bag panel the player can open and read;
  - a pack that declares no stakes is never asked at all.

State is read the published way: window.VEFR_STAKES_STATE() for the
stakes, and the bag panel's own rows for what is carried - never the
player's private variables.

And the phone (vefr#504): the offer is answered with two on-screen
buttons as well as with Y and N, because a phone has no keys. What
the browser has to show is that a tap on "Walk away" changes nothing
and is asked again, a tap on "Take the stake" moves the risk and the
reward, the buttons are big enough to hit (48px), and the desktop keys
still answer exactly as they did.

Run with: uv run pytest tests/browser/test_stakes.py
"""

import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_stakes_pack  # noqa: E402

PHONE = {"width": 390, "height": 844}

DESKTOP = {"width": 1280, "height": 720}

TORCH = "a pitch torch"
MAP = "a chalked map"

# The one line the game says while asking, as the pack wrote it: the
# `say`, then the two costs and the two keys, in the game's own words.
ASK = make_stakes_pack.STAKES[0]["say"]

# What the player reads after each answer.
WALKED = "You walk away from it. Nothing is lost."
TAKEN = "You put " + TORCH + " down. You take " + MAP + "."


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """The stakes fixture pack, woven: the toll, the torch, the one offer."""
    d = tmp_path_factory.mktemp("stakes")
    pack = make_stakes_pack.build(d)
    out = d / "woven.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    return out


@pytest.fixture(scope="module")
def plain_woven(tmp_path_factory):
    """The sample pack as it ships: no `stakes` key at all."""
    d = tmp_path_factory.mktemp("no-stakes")
    out = d / "woven.html"
    out.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    return out


def enter(page):
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    page.wait_for_timeout(300)


@contextmanager
def playing(browser, html, size=DESKTOP, touch=False):
    ctx = browser.new_context(viewport=size, has_touch=touch, is_mobile=touch)
    page = ctx.new_page()
    try:
        page.goto(html.as_uri())
        enter(page)
        yield page
    finally:
        ctx.close()


@contextmanager
def on_a_phone(browser, html):
    """A 390x844 phone with a touchscreen: the frame the buttons exist for."""
    with playing(browser, html, size=PHONE, touch=True) as page:
        yield page


def stakes(page):
    """The published snapshot, as the player could not see it but as the
    game publishes it."""
    return page.evaluate("() => window.VEFR_STAKES_STATE()")


def said(page):
    """The game's own line for this moment."""
    return page.evaluate(
        "() => { const el = document.getElementById('combat-live');"
        " return el ? el.textContent : ''; }")


def carried(page):
    """What the bag panel lists, read off its own rows: the names a player
    sees when they open the bag."""
    page.evaluate("() => window.openBag()")
    page.wait_for_timeout(120)
    names = page.evaluate(
        """() => Array.from(document.querySelectorAll('#bag-list .bag-row-name'))
             .map((el) => el.textContent.trim())""")
    page.evaluate("() => window.closeMenu()")
    page.wait_for_timeout(120)
    return names


def walk_to_the_toll(page):
    """One step east puts the hero on the toll, which is what the stake's
    `when` is written against."""
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(250)


def test_the_offer_is_asked_where_the_pack_wrote_it(browser, woven):
    with playing(browser, woven) as page:
        # The rule handed the hero the torch at Begin, so the risk is
        # something they really hold before the toll asks for it.
        assert carried(page) == [TORCH], "the fixture did not hand the hero its torch"

        walk_to_the_toll(page)
        state = stakes(page)
        assert state["declared"] == 1, state
        assert state["pending"] == "the-tolls-price", (
            f"the toll did not put its offer to the player: {state}")
        assert state["taken"] == [], state

        # The line says what the pack wrote, and names both costs and the
        # two keys that answer - a player is never asked blind.
        line = said(page)
        assert line.startswith(ASK), line
        for wanted in (TORCH, MAP, "[Y]", "[N]"):
            assert wanted in line, f"the offer never named {wanted!r}: {line}"


def test_walking_away_loses_nothing_and_the_offer_is_asked_again(browser, woven):
    with playing(browser, woven) as page:
        walk_to_the_toll(page)
        assert stakes(page)["pending"] == "the-tolls-price"

        page.keyboard.press("n")
        page.wait_for_timeout(200)
        assert said(page) == WALKED, said(page)
        state = stakes(page)
        assert state["pending"] is None, state
        assert state["taken"] == [], state
        # THE REVERSAL: nothing left the bag and nothing came into it.
        assert carried(page) == [TORCH], (
            f"walking away changed what the hero carries: {carried(page)}")

        # Step back and come to the toll again: the player is asked again.
        # A refusal is not held against them, and the offer costs nothing
        # to hear a second time.
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(200)
        walk_to_the_toll(page)
        assert stakes(page)["pending"] == "the-tolls-price", (
            "the toll did not ask again after the hero walked away once")
        assert carried(page) == [TORCH], "asking again cost the hero something"


def test_only_the_players_own_key_stakes_the_risk(browser, woven):
    with playing(browser, woven) as page:
        walk_to_the_toll(page)
        assert stakes(page)["pending"] == "the-tolls-price"

        # The whole risk, and the whole reward, on one press of the
        # player's own: nothing else in the game takes either away.
        page.keyboard.press("y")
        page.wait_for_timeout(250)
        assert said(page) == TAKEN, said(page)
        state = stakes(page)
        assert state["pending"] is None and state["taken"] == ["the-tolls-price"], state
        assert carried(page) == [MAP], (
            f"staking the risk did not put the reward in the bag: {carried(page)}")

        # And the toll asks no more: the risk is gone, so there is nothing
        # left to ask about.
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(200)
        walk_to_the_toll(page)
        assert stakes(page)["pending"] is None, (
            "the toll asked again after the hero had already staked the torch")
        assert carried(page) == [MAP]


def test_a_pack_that_declares_no_stakes_is_never_asked(browser, plain_woven):
    """The default, proven on the sample pack as it ships: no `stakes`
    key, no bake, no offer - and the hero walks the same toll tile
    without a word about a torch."""
    with playing(browser, plain_woven) as page:
        assert page.evaluate("() => window.VEFR_STAKES") is None, (
            "a pack that declared no stakes baked some")
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(250)
        state = stakes(page)
        assert state == {"declared": 0, "pending": None, "taken": []}, state
        assert "Risk" not in said(page), f"an unasked offer was said anyway: {said(page)}"


def test_the_woven_file_asks_only_what_the_pack_wrote(browser, woven):
    """The same offer, read out of the file itself - the bake is the pack's
    words and nothing is invented on the way in."""
    with playing(browser, woven) as page:
        baked = page.evaluate("() => window.VEFR_STAKES")
        assert baked == make_stakes_pack.STAKES, baked
        assert json.loads(json.dumps(baked)) == json.loads(
            page.evaluate("() => JSON.stringify(window.VEFR_STAKES)"))

# ---- the offer on a phone (vefr#504) ----
# The gap this closes, in one line: Y and N are keys, and a phone has
# neither. Before the buttons, a phone player could read the offer and
# could not answer it at all. So the proof here is a finger.

TAKE = "#stake-take"
WALK = "#stake-walk"


def offered(page):
    """The two answers, as a player sees them: what is on screen, in the
    order it is on screen, and where the focus is."""
    return page.evaluate(
        """() => ({ buttons: Array.from(document.querySelectorAll('#stake-ask button'))
             .map((el) => ({ id: el.id, text: el.textContent.trim(),
                             name: el.getAttribute('aria-label') })),
             focused: document.activeElement ? document.activeElement.id : null })""")


def height_of(page, selector):
    return page.evaluate(
        "(sel) => { const el = document.querySelector(sel);"
        " return el ? el.getBoundingClientRect().height : 0; }", selector)


def boxes(page):
    """Where the offer's buttons sit, and where the fight verbs sit, as
    rectangles, so the two can be compared rather than trusted."""
    return page.evaluate(
        """() => { const one = (el) => { const r = el.getBoundingClientRect();
             return { x: r.x, y: r.y, w: r.width, h: r.height }; };
             const verbs = Array.from(document.querySelectorAll('#verb-row button'))
               .filter((el) => el.offsetParent !== null).map(one);
             const acts = Array.from(document.querySelectorAll('.acts button'))
               .filter((el) => el.offsetParent !== null).map(one);
             const ask = Array.from(document.querySelectorAll('#stake-ask button'))
               .map(one);
             return { ask: ask, others: verbs.concat(acts) }; }""")


def overlaps(a, b):
    return (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
            and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])


def test_a_phone_is_asked_the_offer_with_two_buttons_under_the_line(browser, woven):
    with on_a_phone(browser, woven) as page:
        assert offered(page)["buttons"] == [], "an offer was on screen before one was made"
        walk_to_the_toll(page)
        assert stakes(page)["pending"] == "the-tolls-price"

        on_screen = offered(page)
        assert [b["id"] for b in on_screen["buttons"]] == ["stake-take", "stake-walk"], on_screen
        assert [b["text"] for b in on_screen["buttons"]] == ["Take the stake", "Walk away"], on_screen
        # Each button says what its own answer costs, for a screen reader.
        for button in on_screen["buttons"]:
            assert button["name"].startswith(button["text"] + ":"), button
        # The focus opens on the answer that costs nothing.
        assert on_screen["focused"] == "stake-walk", (
            f"the offer did not put the focus on the safe answer: {on_screen}")


def test_the_answers_are_big_enough_to_hit_and_stand_clear_of_the_verbs(browser, woven):
    with on_a_phone(browser, woven) as page:
        walk_to_the_toll(page)
        for selector in (TAKE, WALK):
            high = height_of(page, selector)
            assert high >= 48, f"{selector} is {high}px tall: too small to tap with a thumb"

        placed = boxes(page)
        assert placed["ask"], "the offer drew no buttons to place"
        for ask in placed["ask"]:
            for other in placed["others"]:
                assert not overlaps(ask, other), (
                    f"the offer's buttons stand over a verb the player may want next: "
                    f"{ask} over {other}")

    # The same two facts on a desktop frame, where the verb row and the
    # action row really are on the page: there the offer's buttons must
    # not be drawn over them either.
    with playing(browser, woven) as page:
        walk_to_the_toll(page)
        placed = boxes(page)
        assert placed["others"], "no verb was on screen to stand clear of"
        for ask in placed["ask"]:
            for other in placed["others"]:
                assert not overlaps(ask, other), (
                    f"the offer's buttons cover a verb: {ask} over {other}")


def test_tapping_walk_away_on_a_phone_loses_nothing_and_is_asked_again(browser, woven):
    with on_a_phone(browser, woven) as page:
        walk_to_the_toll(page)
        assert stakes(page)["pending"] == "the-tolls-price"

        page.tap(WALK)
        page.wait_for_timeout(250)
        assert said(page) == WALKED, said(page)
        state = stakes(page)
        assert state["pending"] is None and state["taken"] == [], state
        # THE REVERSAL, with a finger this time: nothing left the bag,
        # nothing came into it, and the buttons are gone with the offer.
        assert carried(page) == [TORCH], (
            f"walking away on a phone changed what the hero carries: {carried(page)}")
        assert offered(page)["buttons"] == [], (
            "the buttons stayed on screen after the offer was answered")

        # Asked again the next time the toll matches: a tap costs nothing.
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(200)
        walk_to_the_toll(page)
        assert stakes(page)["pending"] == "the-tolls-price", (
            "the toll did not ask again after the hero walked away on a phone")
        assert carried(page) == [TORCH], "asking again cost the hero something"


def test_taking_the_stake_on_a_phone_moves_the_risk_and_the_reward(browser, woven):
    with on_a_phone(browser, woven) as page:
        walk_to_the_toll(page)
        assert carried(page) == [TORCH]

        page.tap(TAKE)
        page.wait_for_timeout(300)
        assert said(page) == TAKEN, said(page)
        state = stakes(page)
        assert state["pending"] is None and state["taken"] == ["the-tolls-price"], state
        assert carried(page) == [MAP], (
            f"tapping Take the stake did not put the reward in the bag: {carried(page)}")
        assert offered(page)["buttons"] == [], (
            "the buttons stayed on screen after the offer was answered")

        # And the toll asks no more: the risk is gone from the bag.
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(200)
        walk_to_the_toll(page)
        assert stakes(page)["pending"] is None, (
            "the toll asked again after the hero had already staked the torch")


def test_the_keys_still_answer_the_offer_on_a_desktop(browser, woven):
    """The buttons are an addition, not a replacement: Y and N answer
    exactly as they did, and they answer the offer the buttons show."""
    with playing(browser, woven) as page:
        walk_to_the_toll(page)
        assert [b["id"] for b in offered(page)["buttons"]] == ["stake-take", "stake-walk"]

        page.keyboard.press("n")
        page.wait_for_timeout(200)
        assert said(page) == WALKED, said(page)
        assert offered(page)["buttons"] == [], "the buttons outlived the answer"

        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(200)
        walk_to_the_toll(page)
        assert stakes(page)["pending"] == "the-tolls-price"

        page.keyboard.press("y")
        page.wait_for_timeout(250)
        assert said(page) == TAKEN, said(page)
        assert carried(page) == [MAP], carried(page)
        assert offered(page)["buttons"] == []
