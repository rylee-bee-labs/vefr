"""vefr#350, the first half: a death on a generated floor is not a trip home.

Cozy death woke the hero wherever the pack's own `wake` said - and that
is a baked region, so a fall three floors into a descent threw the run
away and sent the hero back to the town to start again. The descent now
answers for its own floors: the hero wakes whole on the floor they fell
on, at its up-stair, with the kills, the drops, the bag and the stairs
they left behind.

Played through the REAL woven file in jsdom, against the floor the
generator drew: the fight is planned from `delve.floor_plan`, so the hero
walks to a monster it can reach and falls on it on purpose. The harness
stops pressing the moment the hero wakes, because a hero that wakes and
then keeps walking says nothing about where they woke.

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

from test_descent_deltas import TOWN, TOWN_HERO, _path
from test_descent_floors import DESCENT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "descent_death_harness.mjs"

# The floor of the acceptance criterion: `cellar-0-3`, the third floor of
# the fixture descent's first Section.
DEPTH = 3
FLOOR = "cellar-0-3"
BELOW = "hollow-0-1"

# The hero is given three hundred hit points and the monster it falls to
# has ten, so the fall takes thirty of its blows. The descent is walked
# before anything is staged, and every monster on the way walks toward
# the hero, so the numbers are chosen to survive that walk: a hero two
# meetings on the way down could finish would die on the wrong floor, and
# the test would be measuring the walk instead of the waking.
HERO_HP = 300
PRESSES = 60

# Two families, both on every floor of the Section. The brute is what
# kills the hero, and it outlives the fight: the hero's four points a
# bump take thirty of its hundred and fifty to finish, and the fall needs
# no more than the thirty blows it takes to drop the hero. The vermin
# falls in one and carries a pebble, so there is something in the bag and
# something in the floor's own memory before the hero ever falls.
BRUTE = {"family": "brute", "weight": 3, "hp": 150, "atk": 10,
         "name": "a heavy brute"}
VERMIN = {"family": "vermin", "weight": 3, "drops": ["pebble"],
          "name": "a vermin"}

FIGHT = copy.deepcopy(DESCENT)
FIGHT["sections"][0]["families"] = [BRUTE, VERMIN]

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
    assert path, f"no walk {what or f'{start} -> {goal}'}"
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


def _reachable(plan, family, start):
    """The first monster of `family` the hero can walk to from `start`, and the way.

    A v3 floor joins its rooms with corridors and its monsters wander
    while the walk is being planned, so this is the first one with a
    path that does not cross another monster's tile - the rule the
    deltas tests walk by.
    """
    for mob in plan["mobs"]:
        if mob["family"] != family:
            continue
        others = [m["at"] for m in plan["mobs"] if m["at"] != mob["at"]]
        path = _path(plan, start, mob["at"], others)
        if path:
            return mob, path
    raise AssertionError(f"no {family} on {plan['name']} the hero can reach")


@pytest.fixture(scope="module")
def fall(tmp_path_factory):
    """One death on the third floor, played once and read by the tests below.

    A real descent and a real fight: kill the vermin, take its pebble,
    then walk into the brute and keep bumping it until it finishes the
    job.
    """
    tmp_path = tmp_path_factory.mktemp("descent-death")
    plan = _plan(DEPTH)
    vermin, to_vermin = _reachable(plan, VERMIN["family"], plan["anchors"]["up"])
    brute, to_brute = _reachable(plan, BRUTE["family"], vermin["at"])
    walk = _descent_to(DEPTH)
    walk += [["dir", step] for step in to_vermin]
    # The last press of that walk is the bump that kills it; the two after
    # it are the step onto its tile, which is what takes the drop.
    walk += [["dir", to_vermin[-1]]] * 2
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
    assert result["reads"]["combat"]["bag"] == ["pebble"]
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