"""vefr#465: the tile a stair drops the hero on is a landing, not the stair back.

The arrival code path (`enterRegion`) put the hero on whatever tile the
transition's `to_at` names, which for a stair is the stair the other way.
The very next F or E press then offered "Go up the stairs" - the
prompt flipped between the way down and the way back up on successive
presses, with no step in between to say which was meant.

The landing tile is now set aside: the stair on it is not an Interact
target until the hero has stepped off and (stepping back) onto it, and a
door landing is untouched, because a door opens both ways and means the
same thing from either side.

Played through the REAL woven file in jsdom
(`stair_landing_harness.mjs`) against the fixture interact pack, with
its one door turned into a stair down to the cellar and a stair up out
of it. Every walk is planned from the fixture's own pinned coordinates,
so it is a walk a player could make. The descent's own arrival is in
tests/test_descent_arrival.py.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import play_kit
import make_interact_pack   # noqa: E402 - play_kit puts tests/fixtures on the path

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

HARNESS = Path(__file__).resolve().parent / "fixtures" / "stair_landing_harness.mjs"

# The fixture's pinned tiles (make_interact_pack's map):
#   hero start ....... [1, 1]   the town
#   the stair down .. [9, 3]   one tile above the stand-spot
#   the stand spot ... [9, 4]   facing up, the stair is the faced tile
#   cellar arrival ... [1, 1]   where the stair drops the hero
#   cellar beside .... [2, 1]   one step off the landing
DOWN = {"from": "town", "at": [9, 3], "to": "cellar", "to_at": [1, 1]}
UP = {"from": "cellar", "at": [1, 1], "to": "town", "to_at": [9, 3]}
STAIR_POIS = {"acts/act-1/town/contract.json": {"9, 3": "the stair down"},
              "acts/act-1/cellar/contract.json": {"1, 1": "the stair up"}}
# The same two transitions with no `stair` in either tile's name: both are
# doors, so both act the moment the hero stands on them.
DOOR_POIS = {"acts/act-1/town/contract.json": {"9, 3": "the way down"},
             "acts/act-1/cellar/contract.json": {"1, 1": "the way back"}}

# The town from the fixture's own start to the stand-spot, around the
# rat that sleeps at [2, 1]: down the west wall, across the south walk,
# then one step up so the stair is the tile the hero faces.
TO_THE_STAIR = ["walk:down,down,down,down",
                "walk:right,right,right,right,right,right,right,right",
                "walk:up"]

DOWN_WORDS = "Go down the stairs"
UP_WORDS = "Go up the stairs"
NOTHING = "Interact"       # the dim button: no target in reach


def _weave(tmp_path, pois):
    patch = {"acts/act-1/world.json": {"transitions": [DOWN, UP]}}
    patch.update(copy.deepcopy(pois))
    return play_kit.weave(play_kit.pack(tmp_path, "interact", patch=patch), tmp_path)


def test_the_fixture_gives_a_landing_somewhere_to_step():
    """A set-aside only happens where the hero can step (vefr#465).

    The landing tile is one the hero must be able to walk off; a tile
    with no open neighbour is never a landing, or the way back would be
    gone along with the flip.
    """
    rows = make_interact_pack.CELLAR_MAP
    assert rows[1][2] == ".", "the fixture's cellar landing must have a step off it"


def _session(html, steps):
    run = subprocess.run(
        ["node", str(HARNESS), str(html), json.dumps({"steps": steps})],
        capture_output=True, text=True, timeout=300,
    )
    if run.returncode != 0:
        raise RuntimeError(run.stderr)
    out = json.loads(run.stdout)
    assert out["errors"] == [], out["errors"]
    return out["snaps"]


def test_the_stair_prompt_does_not_flip_on_the_tile_the_stair_drops_the_hero_on(tmp_path):
    html = _weave(tmp_path, STAIR_POIS)
    snaps = _session(html, TO_THE_STAIR + [
        "snap:at_the_stair", "click:#interact", "snap:landed",
        "click:#interact", "wait:150", "snap:pressed",
    ])

    # The way down is offered from the stand-spot, as it always was.
    at_the_stair = snaps["at_the_stair"]
    assert at_the_stair["region"] == "town"
    assert at_the_stair["hero"] == [9, 4]
    assert at_the_stair["interact"] == DOWN_WORDS

    # Arrival is the arrival: the hero stands on the tile the transition
    # wrote, and the POI line names where they are.
    landed = snaps["landed"]
    assert landed["region"] == "cellar"
    assert landed["hero"] == [1, 1]
    assert landed["poi"] == "the stair up"

    # The landing is not the way back yet: the prompt does not flip, and
    # the press that would have gone up does not go up.
    assert landed["interact"] == NOTHING, \
        "the landing tile offered the stair back before the hero moved"
    assert snaps["pressed"]["region"] == "cellar", \
        "the second press climbed the stair the hero had just come down"
    assert snaps["pressed"]["hero"] == [1, 1]


def test_the_stair_comes_back_once_the_hero_has_stepped_off_and_returned(tmp_path):
    html = _weave(tmp_path, STAIR_POIS)
    snaps = _session(html, TO_THE_STAIR + [
        "click:#interact", "snap:landed",
        "walk:right", "snap:off", "walk:left", "snap:back",
        "click:#interact", "wait:150", "snap:up",
    ])

    assert snaps["landed"]["interact"] == NOTHING
    # One step off, the stair is in reach again - the hero chooses it now.
    assert snaps["off"]["hero"] == [2, 1]
    assert snaps["off"]["interact"] == UP_WORDS
    assert snaps["back"]["hero"] == [1, 1]
    assert snaps["back"]["interact"] == UP_WORDS

    # And the way home is the way it always was: back to the town, on
    # the tile the stair wrote - where the way down is set aside in its
    # turn, by the same rule.
    up = snaps["up"]
    assert up["region"] == "town"
    assert up["hero"] == [9, 3]
    assert up["interact"] != DOWN_WORDS, \
        "the stair down offered itself on the tile it had just dropped the hero on"


def test_a_door_landing_is_left_alone(tmp_path):
    """A door opens both ways: nothing about arriving through one changes."""
    html = _weave(tmp_path, DOOR_POIS)
    snaps = _session(html, TO_THE_STAIR + [
        "click:#interact", "snap:landed",
        "click:#interact", "wait:150", "snap:back",
    ])
    assert snaps["landed"]["region"] == "cellar"
    assert snaps["landed"]["interact"] == "Go through the door"
    assert snaps["back"]["region"] == "town"
    assert snaps["back"]["hero"] == [9, 3]