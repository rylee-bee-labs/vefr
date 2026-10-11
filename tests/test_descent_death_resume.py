"""vefr#350, the first half: a death on a generated floor is not a trip home.

Cozy death woke the hero wherever the pack's own `wake` said - and that
is a baked region, so a fall three floors into a descent threw the run
away and sent the hero back to the town to start again. The descent now
answers for its own floors: the hero wakes whole on the floor they fell
on, at its up-stair, with the kills, the drops, the bag and the stairs
they left behind.

Played through the REAL woven file in jsdom, against the floor the
generator drew: every step of the walk is planned from `delve.floor_plan`,
so each one is a tile the hero can reach. The hero walks out of the town,
down cellar 1-3 and into the hollow. Every monster the walk bumps dies to
that bump, so on the way down the hero kills the vermin it passes and
takes their pebbles. The brute on the acceptance floor is what falls the
hero: the walk ends bumping it, and the harness stops pressing the moment
the hero wakes, because a hero that wakes and then keeps walking says
nothing about where they woke.

Where the brute is placed is not a detail, and it is spelled out below:
a Section carries ONE family table for all of its floors, so a brute
planted on the cellar is a brute the hero must cross as well as fight,
and crossing is not a fight the hero can win. The brutes go on the
hollow - the last Section of the descent, four floors down - so the walk
down is a walk past the fixture's own harmless families and the only
brute in the run is the one the hero walks into on purpose.

The last test is the other half of that promise - a pack with no descent
at all wakes its hero exactly where it did before, because the fix has
nothing to say about a region it does not own.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import play_kit
from vefr import delve

from test_descent_deltas import DIRS, TOWN, TOWN_HERO, _path
from test_descent_floors import DESCENT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "descent_death_harness.mjs"

# The floor of the acceptance criterion: `hollow-0-2`, the second floor
# of the fixture descent's second Section and the deepest floor these
# tests reach. Four floors down from the town, which is the case the bug
# report is about: a fall far into a descent.
DEPTH = 5
FLOOR = "hollow-0-2"
BELOW = "cellar-1-1"

# The hero is given three hundred hit points and the monster it falls to
# has ten, so the fall takes thirty of its blows. The descent is walked
# before anything is staged, so the same numbers have to survive the walk
# too - see the Section note below for why the walk is a walk past
# monsters worth one hit point, and the fight is the only fight in it.
HERO_HP = 300
PRESSES = 60

# Two families, and both go on the SECOND Section. A Section carries one
# family table for every floor it has (`vefr.sections.families` merges
# that table; nothing in the generator reads a per-floor one), so a brute
# planted on the cellar is a brute the hero must CROSS as well as fight -
# and the crossing cannot be budgeted at all:
#
#   - the hero's four points a bump take against a hundred and fifty, so
#     clearing one brute is thirty-eight turns, and the brute hits back
#     on every one of them: three hundred and eighty of the hero's three
#     hundred. A single block on the way down kills the hero outright,
#     and `cellar-0-2` draws one a tile off the walked path.
#   - so the hero has to be given more health than that, and then the
#     fight stops working: the brute falls at the thirty-eighth bump, and
#     a hero carrying more than three hundred hit points is still standing
#     when it does. Raise the brute's health so it outlives the fight and
#     the price of blocking one on the way down rises with it. No pair of
#     numbers both clears a brute on the way and dies to one at the end:
#     the two bounds are the same number, `hp / atk * atk`.
#
# The hollow is the last Section of the descent, so the hero walks down
# through the cellar and hollow-0-1 first, and every monster on those
# floors is the fixture's own - one hit point, one point of attack - so a
# block on the way down there costs one turn and one hit point. The brute
# is on the floor the hero is meant to fall on, and nowhere else.
#
# The brute is what kills the hero, and it outlives the fight: the hero's
# four points a bump take thirty of its hundred and fifty to finish, and
# the fall needs no more than the thirty blows it takes to drop the
# hero. The vermin falls in one and carries a pebble, so there is
# something in the bag and something in the floor's own memory before
# the hero ever falls.
BRUTE = {"family": "brute", "weight": 3, "hp": 150, "atk": 10,
         "name": "a heavy brute"}
VERMIN = {"family": "vermin", "weight": 3, "drops": ["pebble"],
          "name": "a vermin"}

FIGHT = copy.deepcopy(DESCENT)
FIGHT["sections"][1]["families"] = [BRUTE, VERMIN]

PATCH = {"world.json": {"player": {"hp": HERO_HP}, "descent": FIGHT}}


def _play(tmp_path, case, pack="descent", patch=None):
    """One session of the real woven player, played by the death harness."""
    html = play_kit.weave(play_kit.pack(tmp_path, pack, patch=patch), tmp_path)
    run = subprocess.run(
        ["node", str(HARNESS), str(html), json.dumps(case)],
        capture_output=True, text=True, timeout=300,
    )
    if run.returncode != 0:
        raise RuntimeError(run.stderr)
    return json.loads(run.stdout)


def _plan(depth):
    return delve.floor_plan(FIGHT, depth)


def _walk(plan, start, goal, avoid=(), what=""):
    """The directions that walk `start` to `goal`, or a loud failure.

    The walk is planned against the floor the generator drew, so an
    unreachable goal is the test's own mistake and must not pass as a
    hero who stood still.
    """
    path = _path(plan, start, goal, avoid)
    assert path, f"no walk from {start} to {goal}" + (f" ({what})" if what else "")
    return path


def _descent_to(depth):
    """Walk out of the town and down to `depth`, one stair at a time."""
    actions = []
    here = list(TOWN_HERO)
    for d in range(1, depth + 1):
        if d == 1:
            path = _walk(TOWN, here, FIGHT["entry"]["at"], what="to the stair in")
        else:
            plan = _plan(d - 1)
            path = _walk(plan, here, plan["anchors"]["down"],
                         [m["at"] for m in plan["mobs"]], what=f"down floor {d - 1}")
        actions += [["dir", step] for step in path]
        actions += [["click", "#interact"], ["wait", 200]]
        here = list(_plan(d)["anchors"]["up"])
    return actions


def _tiles(start, path):
    """Every tile `path` walks over, `start` included."""
    out = [list(start)]
    here = list(start)
    for step in path:
        dx, dy = DIRS[step]
        here = [here[0] + dx, here[1] + dy]
        out.append(here)
    return out


def _staged(plan):
    """The vermin the hero stages on, the walk to it, and the brute after it.

    The pair whose staging walk keeps the brute furthest off that walk.
    The hero must reach the vermin and take its pebble BEFORE the brute
    ever gets a turn on it, and a brute is awake from ten tiles and
    closes from six, so a vermin with the brute three tiles off the walk
    to it is a hero that dies with an empty bag. The furthest one is
    past all of that: the walk is a walk past vermin worth one hit
    point, and the brute is only met on the way to it.
    """
    up = plan["anchors"]["up"]
    best = None
    for mob in plan["mobs"]:
        if mob["family"] != VERMIN["family"]:
            continue
        others = [m["at"] for m in plan["mobs"] if m["at"] != mob["at"]]
        walk = _path(plan, up, mob["at"], others)
        if not walk:
            continue
        # The two presses past the vermin are its death and the step
        # onto its tile, so the tiles they cover are part of the walk.
        walked = _tiles(up, walk + [walk[-1], walk[-1]])
        for brute in plan["mobs"]:
            if brute["family"] != BRUTE["family"]:
                continue
            spare = [m["at"] for m in plan["mobs"] if m["at"] != brute["at"]]
            fight = _path(plan, mob["at"], brute["at"], spare)
            if not fight:
                continue
            off = min(abs(brute["at"][0] - at[0]) + abs(brute["at"][1] - at[1])
                      for at in walked)
            if best is None or off > best[0]:
                best = (off, mob, walk, brute, fight)
    if best is None:
        raise AssertionError(
            f"no vermin and brute on {plan['name']} the hero can walk to")
    _off, mob, walk, brute, fight = best
    return mob, walk, brute, fight


@pytest.fixture(scope="module")
def fall(tmp_path_factory):
    """One death on the fifth floor, played once and read by the tests below.

    A real descent, walked: out of the town, down cellar 1-3 and into the
    hollow, one stair at a time. Every monster the walk bumps dies to that
    bump, so the vermin it passes are killed and their pebbles taken on
    the way. On the fifth floor the walk goes to a vermin first and then
    to the brute; the brute is what falls the hero, and the walk stops on
    the wake.
    """
    tmp_path = tmp_path_factory.mktemp("descent-death")
    plan = _plan(DEPTH)
    vermin, to_vermin, brute, to_brute = _staged(plan)
    walk = _descent_to(DEPTH)
    walk += [["dir", step] for step in to_vermin]
    # The last press of that walk is the bump that kills it; the two after
    # it are the step onto its tile, which is what takes the drop.
    walk += [["dir", to_vermin[-1]], ["dir", to_vermin[-1]]]
    walk += [["dir", step] for step in to_brute]
    case = {"floor": FLOOR, "wake": plan["anchors"]["up"], "walk": walk,
            "fight": {"dir": to_brute[-1], "presses": PRESSES}}
    return _play(tmp_path, case, patch=PATCH), plan, vermin, brute


def test_a_death_on_a_generated_floor_wakes_the_hero_on_that_floor(fall):
    result, plan, _vermin, _brute = fall
    assert result["errors"] == [], result["errors"]
    assert result["died"], f"the hero never fell on {FLOOR}"
    combat = result["reads"]["combat"]
    up = plan["anchors"]["up"]
    assert combat["region"] == FLOOR, \
        f"the hero woke in {combat['region']!r}: a death must not leave the descent"
    assert combat["hero"]["at"] == up, \
        f"the hero woke at {combat['hero']['at']}, not the floor's up stair {up}"
    assert combat["hero"]["hp"] == combat["hero"]["max"], "a wake is a whole hero"


def test_the_death_costs_the_floor_nothing(fall):
    result, plan, vermin, brute = fall
    # The bag: the pebble picked up before the fall is still in it.
    assert "pebble" in result["reads"]["combat"]["bag"]
    # The floor: its own memory of the kill, and where the hero walked.
    record = result["reads"]["doc"]["floors"][FLOOR]
    assert vermin["id"] in record["kills"], record["kills"]
    assert brute["id"] not in record["kills"], \
        "the brute is what fell the hero: it is still standing"
    assert record["fog"], "a death is not a new visit: the ground walked is kept"
    # And the stairs: the way down is still the way this floor drew it.
    doors = [t for t in result["reads"]["transitions"] if t["from"] == FLOOR]
    assert [t for t in doors
            if list(t["at"]) == plan["anchors"]["down"] and t["to"] == BELOW], \
        f"{FLOOR} has no stair down to {BELOW} after the death"


def test_the_why_log_names_the_floor_the_hero_resumed_on(fall):
    result, plan, _vermin, _brute = fall
    why = result["reads"]["why"] or []
    assert any(FLOOR in str((entry or {}).get("why")) for entry in why), why


def test_a_pack_with_no_descent_wakes_its_hero_in_the_town_as_before(tmp_path):
    """The behaviour-neutral half: a pack with no `descent` block.

    The descent part is in every woven file, so the one thing that must
    not move is what it does when it has nothing to do. The combat
    fixture carries no descent: the hero walks into its own fight, falls,
    and wakes at the baked wake point in the town - no descent document
    written, and nothing said about a floor.
    """
    result = _play(tmp_path, {"floor": "town", "wake": [1, 1], "walk": [],
                              "fight": {"dir": "right", "presses": 8}},
                   pack="combat")
    assert result["errors"] == [], result["errors"]
    assert result["died"], "the fixture's own fight never landed"
    combat = result["reads"]["combat"]
    assert combat["region"] == "town"
    assert combat["hero"]["at"] == [1, 1], "the baked wake point is the one that answers"
    assert combat["hero"]["hp"] == combat["hero"]["max"] == 3
    assert not [k for k in result["store"] if k.startswith("vefr-descent-")], \
        "a pack with no descent writes no descent document"
    assert not [e for e in (result["reads"]["why"] or [])
                if "descent" in str((e or {}).get("id"))], \
        "a death with no floor under it says nothing about a floor"