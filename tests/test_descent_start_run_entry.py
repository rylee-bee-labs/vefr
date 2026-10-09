"""vefr#350, the second half: a new run rewires the stair into the deep.

`startRun` redraws floor one from a new seed, so the stair out of the town
now ends on a different tile. The door between them was deduplicated on
(from, at, to) alone, and the town is not a generated floor - so the
arrival tile of the run that came before survived every cycle, and the
hero walked into the middle of a floor that had been drawn again. On a
run where that tile is a wall, the hero walked in inside one.

Each test here plays a real session: the New-descent control is pressed
as many times as the run under test, the hero walks home over the
floor's own up stair, and then comes back in through the door in the
town. That is a second cycle in full - and it is the transition, not the
control's own walk-in, that is being measured.
"""

import shutil

import pytest

import play_kit
from vefr import delve

from test_descent_deltas import TOWN, TOWN_HERO, _go
from test_descent_floors import DESCENT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# Six runs, so the arrival tile is proved against five redraws and not
# against one coincidence.
RUNS = 6
ENTRY = DESCENT["entry"]["at"]

READS = ["VEFR_COMBAT.region", "VEFR_COMBAT.hero", "VEFR_TRANSITIONS", "store"]


def _play(tmp_path, steps):
    html = play_kit.weave(play_kit.pack(tmp_path, "descent"), tmp_path)
    return play_kit.play(html, {"steps": steps, "read": list(READS)})


def _first_floor(run):
    return delve.floor_plan(DESCENT, 1, run=run)


def _enter(run):
    """The steps that start `run` and then walk the hero into it from the town."""
    steps = ["begin", "wait:200"]
    for _ in range(run):                   # New descent: one run, walked straight in
        steps += ["menu:descent", "wait:150", "click:#descent-new", "wait:300"]
    if not run:
        steps.append(_go(TOWN, TOWN_HERO, ENTRY))
    else:
        # The control has already put the hero on floor one. Walk home
        # over that floor's own up stair first, so what is measured next
        # is the way back in - the door in the town, not the control.
        steps += ["click:#interact", "wait:300"]
    steps += ["click:#interact", "wait:300"]
    return [s for s in steps if s != "walk:"]


def _entry_doors(play):
    return [t for t in play["reads"]["VEFR_TRANSITIONS"]
            if t["from"] == DESCENT["entry"]["region"]
            and list(t["at"]) == ENTRY and t["to"] == _first_floor(0)["name"]]


@pytest.mark.parametrize("run", range(RUNS))
def test_entering_the_descent_lands_on_this_runs_up_stair(tmp_path, run):
    play = _play(tmp_path, _enter(run))
    assert play["errors"] == [], play["errors"]
    plan = _first_floor(run)
    combat = play["reads"]["VEFR_COMBAT"]
    got = combat["hero"]["at"]
    assert combat["region"] == plan["name"], \
        f"run {run} should open on {plan['name']}, not {combat['region']}"
    assert got == plan["anchors"]["up"], \
        f"run {run} drew its up stair at {plan['anchors']['up']}; the hero came in at {got}"
    assert plan["rows"][got[1]][got[0]] != "#", \
        f"run {run} put the hero inside a wall at {got}"


@pytest.mark.parametrize("run", range(1, RUNS))
def test_the_door_into_the_deep_carries_this_runs_arrival_and_only_one(tmp_path, run):
    """The dedupe may not keep an arrival from a run that has been left.

    Starting runs one after another is what the endless control does, and
    the door in the town is the one transition whose other end is not a
    generated floor - so it is the one `resetRegions` cannot drop, and the
    one a dedupe on the door's identity alone would freeze.
    """
    play = _play(tmp_path, _enter(run))
    assert play["errors"] == [], play["errors"]
    doors = _entry_doors(play)
    assert len(doors) == 1, \
        f"{len(doors)} doors from the town into the deep after {run + 1} runs: {doors}"
    assert doors[0]["to_at"] == _first_floor(run)["anchors"]["up"], \
        f"the door still ends at {doors[0]['to_at']}, the tile run {run} drew over"