"""vefr#366: a landing's up-stair is the way home, at play time too.

The bake (`vefr delve --section`, `cli.py`) has always wired a landing -
a floor whose pattern slot is `entry` or `landing` - to climb straight to
where the descent started (`tests/test_sections_e4.py`). The play-time
descent wired every up-stair below floor one to the floor above, so a hero
thirty floors down had thirty floors to climb. The player now reads the
same rule: `isLanding` is the twin of `sections.is_landing`, a landing's
up-stair arrives on `descent.entry.region` at `descent.entry.at`, and the
depth is kept in the save's `flags.landing`.

A Section whose pattern names neither slot keeps every floor-to-floor
stair exactly as it was, and floor one still climbs to the entry.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vefr import cli, delve, sections

from test_descent_floors import DESCENT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "descent_landing_harness.mjs"


def _with_patterns(*patterns):
    out = copy.deepcopy(DESCENT)
    for section, pattern in zip(out["sections"], patterns):
        if pattern is None:
            section.pop("pattern", None)
        else:
            section["pattern"] = pattern
    return out


# The fixture as it ships: cellar is entry, landing, warden; hollow names
# no pattern and takes the engine's, whose first slot is `entry`. Two cycles
# deep, so a landing in the endless cycle is wired the same way.
LANDED = _with_patterns(["entry", "landing", "warden"], None)
# No landing rule in play: neither Section names `entry` or `landing`.
FLAT = _with_patterns(["n", "n", "warden"], ["n", "n"])
DEPTHS = list(range(1, 11))


@pytest.fixture(scope="module")
def answers(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("landings")
    html = tmp / "p.html"
    html.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    cases = tmp / "cases.json"
    cases.write_text(json.dumps({"descents": [
        {"descent": LANDED, "depths": DEPTHS},
        {"descent": FLAT, "depths": DEPTHS}]}))
    run = subprocess.run(["node", str(HARNESS), str(html), str(cases)],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr + run.stdout
    landed, flat = json.loads(run.stdout)
    return {"landed": landed, "flat": flat}


def _python_landing(descent, depth):
    _cycle, section, k = sections.cycle_locate(depth, descent["sections"])
    return sections.is_landing(section, k)


def _expected_up(descent, depth):
    """Where the bake's rule sends this depth's up-stair."""
    plan = delve.floor_plan(descent, depth)
    if depth == 1 or _python_landing(descent, depth):
        return descent["entry"]["region"], descent["entry"]["at"]
    above = delve.floor_plan(descent, depth - 1)
    assert plan["name"] != above["name"]
    return above["name"], above["anchors"]["down"]


def test_the_twin_agrees_with_sections_is_landing(answers):
    for name, descent in (("landed", LANDED), ("flat", FLAT)):
        assert answers[name]["isLanding"] == [_python_landing(descent, d) for d in DEPTHS], name


def test_the_fixture_has_landings_below_floor_one():
    deep = [d for d in DEPTHS if d > 1 and _python_landing(LANDED, d)]
    assert deep and max(deep) >= 5, deep


def test_a_landing_climbs_to_the_entry_and_every_other_floor_to_the_one_above(answers):
    for up in answers["landed"]["ups"]:
        assert up["count"] == 1, up
        to, to_at = _expected_up(LANDED, up["depth"])
        assert (up["to"], up["to_at"]) == (to, list(to_at)), up


def test_floor_one_still_climbs_to_the_entry(answers):
    for name in ("landed", "flat"):
        first = answers[name]["ups"][0]
        assert (first["to"], first["to_at"]) == (DESCENT["entry"]["region"],
                                                 DESCENT["entry"]["at"])


def test_with_no_landing_rule_every_stair_climbs_one_floor(answers):
    for up in answers["flat"]["ups"][1:]:
        above = delve.floor_plan(FLAT, up["depth"] - 1)
        assert (up["to"], up["to_at"]) == (above["name"], above["anchors"]["down"]), up
    assert answers["flat"]["landings"] == []


def test_the_save_records_every_landing_reached(answers):
    assert answers["landed"]["landings"] == [d for d in DEPTHS if _python_landing(LANDED, d)]
