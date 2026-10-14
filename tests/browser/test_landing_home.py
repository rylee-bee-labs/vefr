"""vefr#366 in Chromium: a deep landing's up-stair is the way home.

The descent fixture's cellar is `entry, landing, warden` and its hollow
takes the engine's pattern, whose first slot is `entry`: depth 2 and depth
4 are landings below floor one. The hero walks down to depth 4, takes its
up-stair, and arrives in the town on the descent's entry tile - not on
depth 3. The landings reached are in the save's `flags.landing`, and they
are still there after a reload.
"""

from vefr import delve

from .test_descent_reload import DESCENT, descend_to, open_woven, woven  # noqa: F401

ENTRY = DESCENT["entry"]


def _hero(page):
    return page.evaluate(
        "() => ({region: window.VEFR_COMBAT.region, at: window.VEFR_COMBAT.hero.at})")


KEYS = {"up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight"}


def _step_off_and_back(page, plan):
    """A stair does not answer on the tile it dropped the hero on (vefr#465):
    one step off the landing, in an open direction, and one step back."""
    up = plan["anchors"]["up"]
    rows = plan["rows"]
    back = {"up": "down", "down": "up", "left": "right", "right": "left"}
    moves = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
    away = next(name for name, (dx, dy) in moves.items()
                if rows[up[1] + dy][up[0] + dx] != "#")
    page.keyboard.press(KEYS[away])
    page.wait_for_timeout(200)
    page.keyboard.press(KEYS[back[away]])
    page.wait_for_timeout(200)
    assert _hero(page)["at"] == up


def test_a_deep_landings_stair_climbs_to_town_and_the_landing_is_kept(page, woven):  # noqa: F811
    open_woven(page, woven)
    descend_to(page, 3)
    page.locator("#interact").click()
    four = delve.floor_plan(DESCENT, 4)
    page.wait_for_function(
        "() => window.VEFR_COMBAT && window.VEFR_COMBAT.region === '%s'" % four["name"])
    assert _hero(page)["at"] == four["anchors"]["up"]

    _step_off_and_back(page, four)
    page.locator("#interact").click()
    page.wait_for_function(
        "() => window.VEFR_COMBAT && window.VEFR_COMBAT.region === '%s'" % ENTRY["region"])
    assert _hero(page) == {"region": ENTRY["region"], "at": ENTRY["at"]}
    assert page.evaluate("() => window.VEFR_DESCENT.landings()") == [1, 2, 4]

    page.reload()
    open_woven(page, woven)
    assert page.evaluate("() => window.VEFR_DESCENT.doc.flags.landing") == [1, 2, 4]


def test_an_ordinary_floor_below_a_landing_climbs_one_floor(page, woven):  # noqa: F811
    open_woven(page, woven)
    # Depth 3 is the cellar's warden floor, not a landing: its stair climbs
    # one floor, to depth 2's down stair.
    descend_to(page, 2)
    page.locator("#interact").click()
    three = delve.floor_plan(DESCENT, 3)
    two = delve.floor_plan(DESCENT, 2)
    page.wait_for_function(
        "() => window.VEFR_COMBAT && window.VEFR_COMBAT.region === '%s'" % three["name"])
    _step_off_and_back(page, three)
    page.locator("#interact").click()
    page.wait_for_function(
        "() => window.VEFR_COMBAT && window.VEFR_COMBAT.region === '%s'" % two["name"])
    assert _hero(page)["at"] == two["anchors"]["down"]
