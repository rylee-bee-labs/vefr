"""vefr#363: a hint names a floor of a labelled Section by its title.

A hint (`point-to`) that named a generated floor named it by its region
id, `cellar-0-1`: the id is machine-made, and a Section's `id` cannot be
renamed to read better without renaming the region and every save key
with it. A Section may now declare a `label` (#407), and the player reads
it: a floor of a labelled Section is "the Cellar, floor 1" to the player
and `cellar-0-1` to everything the game keeps.

- a hint names a labelled floor by its title, and the Where next? row is
  still keyed by the region id;
- a Section with no label is named by its id, and its row is the row the
  player always stored;
- the label reaches the woven file inside the Section the weave already
  bakes, and it is the only byte that differs from the same pack woven
  without it.

Played through the REAL woven file in jsdom (`descent_arrival_harness.mjs`)
against the fixture descent; every walk is planned from `delve.floor_plan`,
so it is a walk a player could make. The Python twin of the floor's title
is `sections.floor_title`, and the last tests hold the two to each other.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import play_kit
from vefr import cli, delve, sections

from test_descent_deltas import _descend
from test_descent_floors import DESCENT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

HARNESS = Path(__file__).resolve().parent / "fixtures" / "descent_arrival_harness.mjs"

# The fixture descent with its first Section labelled and its second left
# as it was: the cellar's floors are announced, the hollow's are not.
LABEL = "the Cellar"
LABELLED = copy.deepcopy(DESCENT)
LABELLED["sections"][0]["label"] = LABEL


def _compass(start, goal):
    """The direction words `point-to` and the arrival speak, from Python."""
    dx, dy = goal[0] - start[0], goal[1] - start[1]
    vert = "north" if dy < 0 else ("south" if dy > 0 else "")
    horiz = "west" if dx < 0 else ("east" if dx > 0 else "")
    return f"{vert}-{horiz}" if vert and horiz else (vert or horiz)


def _weave(tmp_path, descent):
    patch = {"world.json": {"descent": copy.deepcopy(descent)}}
    return play_kit.weave(play_kit.pack(tmp_path, "descent", patch=patch), tmp_path)


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


def _arrive(depth, descent):
    """The steps that walk down to `depth` and stop on its up-stair."""
    return _descend(depth, descent=descent)


# ---- the hint ----------------------------------------------------------------

def test_a_hint_names_a_labelled_floor_by_its_title_and_keeps_the_id(tmp_path):
    html = _weave(tmp_path, LABELLED)
    snaps = _session(html, _arrive(1, LABELLED) + [
        "point:cellar-0-2", "snap:labelled",
        "point:hollow-0-1", "snap:plain",
    ])
    down = delve.floor_plan(LABELLED, 1)["anchors"]["down"]
    up = delve.floor_plan(LABELLED, 1)["anchors"]["up"]
    labelled = snaps["labelled"]
    line = f"To reach the Cellar, floor 2, go {_compass(up, down)}."
    assert labelled["said"] == line
    # The Where next? row is still keyed by the region id; the title rides
    # beside it for the panel to show.
    assert labelled["next"] == [
        {"place": "cellar-0-2", "line": line, "name": "the Cellar, floor 2"}]
    # A Section with no label is named by its id, and its row is the row
    # the player always stored.
    plain = snaps["plain"]["next"][-1]
    assert plain["place"] == "hollow-0-1"
    assert "name" not in plain
    assert plain["line"] == "No way to hollow-0-1 is declared from here."


# ---- the bake ----------------------------------------------------------------

def test_the_label_reaches_the_woven_player_and_no_label_bakes_nothing_new(tmp_path):
    plain = play_kit.pack(tmp_path, "descent",
                          patch={"world.json": {"descent": copy.deepcopy(DESCENT)}})
    named = play_kit.pack(tmp_path, "descent",
                          patch={"world.json": {"descent": copy.deepcopy(LABELLED)}})
    plain_html = cli.weave_html(plain)
    named_html = cli.weave_html(named)
    assert f'"label": "{LABEL}"' in named_html
    assert '"label"' not in plain_html.split("window.VEFR_DESCENT_DEF = ", 1)[1].split(";\n", 1)[0]
    # The label is the only difference between the two files: the region
    # ids, the floor keys and every other byte are the same.
    assert named_html.replace(f', "label": "{LABEL}"', "") == plain_html


# ---- the twins ---------------------------------------------------------------

@pytest.mark.parametrize("k", [1, 2, 3])
def test_the_python_title_is_the_label_and_the_floor_number(k):
    section = LABELLED["sections"][0]
    assert sections.floor_title(section, k) == f"{LABEL}, floor {k}"
    assert sections.floor_title(DESCENT["sections"][0], k) == ""
    # The region id is built from the id alone, label or not.
    assert sections.floor_region(section, k) == sections.floor_region(
        DESCENT["sections"][0], k)


def test_the_player_title_is_the_python_title(tmp_path):
    html = _weave(tmp_path, LABELLED)
    snaps = _session(html, _arrive(1, LABELLED) + [
        "point:cellar-0-2", "point:cellar-0-3", "snap:hinted"])
    names = {row["place"]: row.get("name") for row in snaps["hinted"]["next"]}
    section = LABELLED["sections"][0]
    assert names == {"cellar-0-2": sections.floor_title(section, 2),
                     "cellar-0-3": sections.floor_title(section, 3)}
