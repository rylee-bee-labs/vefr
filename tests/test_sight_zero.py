"""`sight: 0` survives a generated floor, in both languages (issue #437).

A pack writes `sight: 0` on a creature meant to sleep until it is woken -
a key-bearer, a cellar's king. A generated floor used to clamp every
monster's sight to at least 1 (`max(1, sight)` in `vefr.delve` and its
twin in `web/player/parts/397-the-descent.js`), so the floor turned the
family's 0 into 1. Now a family's whole `sight` is kept as written, and
only a negative one is lifted to 0:

- Python keeps 0 for a Section's family and for its warden;
- the JavaScript twin answers the same floor field for field, through
  the REAL woven player (the parity harness the descent tests share);
- in play, a sight-0 monster is not inert: it wakes like any other, it
  never walks at the hero, it hits back from the next tile, and a blow
  lands on it, so nothing about it can stall a floor.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vefr import delve
from vefr.cli import weave_html

from play_kit import play, weave
from test_descent_floors import DESCENT
from test_group_wake import open_room, walk_right

ROOT = Path(__file__).resolve().parents[1]
PARITY_HARNESS = ROOT / "tests" / "fixtures" / "descent_parity_harness.mjs"
DEPTHS = list(range(1, 11))


def _with_sight(sight):
    """The fixture descent with a Blueprint beside it whose every family
    has `sight` (left out when `sight` is None), and a warden (a rat) on
    the first Section's last floor. A Section names its families by id and
    the base, sight and all, is the Blueprint's (ADR 0014)."""
    descent = copy.deepcopy(DESCENT)
    names = {family["family"] for section in descent["sections"]
             for family in section["families"]}
    defaults = {"hp": 3, "atk": 1} if sight is None else {"hp": 3, "atk": 1, "sight": sight}
    descent["blueprint"] = {"blueprint": 1, "regions": {},
                            "families": {name: {"defaults": dict(defaults)} for name in names}}
    for section in descent["sections"]:
        for family in section["families"]:
            family.pop("sight", None)
    first = descent["sections"][0]
    first["pattern"] = ["entry", "n", "warden"]
    first["warden"] = {"family": "rat", "id": "rat-king"}
    return descent


def _mobs(descent):
    return [mob for depth in DEPTHS for mob in delve.floor_plan(descent, depth)["mobs"]]


def test_a_family_with_sight_zero_keeps_it_on_a_generated_floor():
    mobs = _mobs(_with_sight(0))
    assert any(not mob.get("warden") for mob in mobs), "no ordinary monster was drawn"
    assert any(mob.get("warden") for mob in mobs), "no warden was drawn"
    assert {mob["sight"] for mob in mobs} == {0}


def test_a_negative_sight_is_zero_and_an_absent_one_is_still_six():
    assert {mob["sight"] for mob in _mobs(_with_sight(-3))} == {0}
    assert {mob["sight"] for mob in _mobs(_with_sight(None))} == {6}
    assert {mob["sight"] for mob in _mobs(_with_sight(1))} == {1}


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_javascript_twin_keeps_sight_zero_too(tmp_path):
    """The same floors through the REAL woven player: the twin's record is
    Python's, field for field, and in it the sight is 0."""
    descent = _with_sight(0)
    html = tmp_path / "p.html"
    html.write_text(weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"descent": descent, "depths": DEPTHS, "runs": []}),
                     encoding="utf-8")
    run = subprocess.run(["node", str(PARITY_HARNESS), str(html), str(cases)],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr + run.stdout
    out = json.loads(run.stdout)
    assert out["hasApi"] is True
    assert len(out["plans"]) == len(DEPTHS)
    sights = set()
    for depth, plan in zip(DEPTHS, out["plans"]):
        want = delve.floor_plan(descent, depth)
        assert json.dumps(plan, sort_keys=True) == json.dumps(want, sort_keys=True), depth
        sights.update(mob["sight"] for mob in plan["mobs"])
    assert sights == {0}


READS = ["VEFR_COMBAT.hero.at", "VEFR_COMBAT.hero.hp",
         "VEFR_COMBAT.enemies.0.at", "VEFR_COMBAT.enemies.0.hp",
         "VEFR_COMBAT.enemies.0.sight", "VEFR_COMBAT.minds.0.awake"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_a_sight_zero_monster_wakes_holds_and_fights_back(tmp_path):
    """Played through the real woven player in the open room of
    tests/test_group_wake.py, the hero starting at [1, 1] with 3 hp."""
    sleeper = [{"id": "keybearer", "name": "a key-bearer", "at": [5, 1],
                "hp": 4, "atk": 1, "sight": 0, "sprite": "rat"}]
    html = weave(open_room(tmp_path, sleeper), tmp_path)

    # Two steps: the hero is two tiles off, inside the wake radius every
    # monster has (ten tiles), so it is awake - and with no sight it does
    # not walk at the hero. Nothing has struck the hero.
    reads = play(html, {"steps": walk_right(2), "read": READS})["reads"]
    assert reads["VEFR_COMBAT.enemies.0.sight"] == 0
    assert reads["VEFR_COMBAT.hero.at"] == [3, 1]
    assert reads["VEFR_COMBAT.minds.0.awake"] is True
    assert reads["VEFR_COMBAT.enemies.0.at"] == [5, 1], "a sight-0 monster never chases"
    assert reads["VEFR_COMBAT.hero.hp"] == 3

    # One more: the hero stands next to it, and it hits.
    reads = play(html, {"steps": walk_right(3), "read": READS})["reads"]
    assert reads["VEFR_COMBAT.hero.at"] == [4, 1]
    assert reads["VEFR_COMBAT.hero.hp"] == 2, "a sight-0 monster hits back from the next tile"

    # And the bump: the hero's blow lands, and it answers again.
    out = play(html, {"steps": walk_right(4), "read": READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.hero.at"] == [4, 1], "a bump strikes rather than moves"
    assert reads["VEFR_COMBAT.enemies.0.hp"] < 4, "the blow lands on a sight-0 monster"
    assert reads["VEFR_COMBAT.hero.hp"] == 1
