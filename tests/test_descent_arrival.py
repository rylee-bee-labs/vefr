"""vefr#362 and #363: a generated floor is announced by what it is.

A hero who goes down a stair arrives on the new floor's up-stair, which is
where the elevator rule wants them. The arrival used to greet them with
that stair - the POI line said "the stair up" and the big button "Go up the
stairs" - and a hint that named a floor named it by its region id,
`cellar-0-1`. A Section may now declare a `label` (#407), and the player
reads it:

- arriving on a floor of a labelled Section, the POI line and the button
  name the floor ("the Cellar, floor 1"), and reading it says which way
  the stair down lies, by the floor below's own title when it has one;
- the up-stair is still drawn and still walkable: once the floor is read,
  or the hero steps off and back, the same tile offers the way up again;
- a hint (`point-to`) names a labelled floor by its title, and the region
  id - the save's key, the rules' id - is the same id it always was;
- a Section with no label arrives exactly as before, and a pack with no
  label anywhere weaves byte for byte the file it wove before.

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

UP_WORDS = "Go up the stairs"


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


# ---- the arrival -----------------------------------------------------------

def test_arriving_on_a_labelled_floor_names_the_floor_not_the_stair(tmp_path):
    html = _weave(tmp_path, LABELLED)
    plan = delve.floor_plan(LABELLED, 1)
    up, down = plan["anchors"]["up"], plan["anchors"]["down"]
    steps = _arrive(1, LABELLED) + [
        "snap:arrived",
        "click:#interact", "snap:read",
        "click:#npc-close", "snap:closed",
        "click:#interact", "wait:150", "snap:climbed",
    ]
    snaps = _session(html, steps)

    arrived = snaps["arrived"]
    # The region id is the one the floor always had, and the hero is on
    # its up-stair - the arrival tile did not move.
    assert arrived["region"] == "cellar-0-1"
    assert arrived["hero"] == up
    assert arrived["poi"] == "the Cellar, floor 1"
    assert arrived["interact"] == "Look at the Cellar, floor 1"

    # Reading the floor says which way the stair down lies, and names the
    # floor below by its own title.
    read = snaps["read"]
    assert read["speechOpen"] is True
    assert read["speechName"] == "the Cellar, floor 1"
    assert read["speechLine"] == (
        f"To reach the Cellar, floor 2, go {_compass(up, down)}.")
    assert read["region"] == "cellar-0-1"

    # Once read, the tile is the stair again, and the stair still works.
    assert snaps["closed"]["interact"] == UP_WORDS
    assert snaps["climbed"]["region"] == "town"


def test_stepping_off_the_arrival_tile_and_back_finds_the_stair(tmp_path):
    html = _weave(tmp_path, LABELLED)
    plan = delve.floor_plan(LABELLED, 1)
    up = plan["anchors"]["up"]
    rows = plan["rows"]
    # One open neighbour of the up-stair, and the step back onto it.
    back = {"up": "down", "down": "up", "left": "right", "right": "left"}
    moves = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
    away = next(name for name, (dx, dy) in moves.items()
                if rows[up[1] + dy][up[0] + dx] != "#")
    steps = _arrive(1, LABELLED) + [
        f"walk:{away}", "snap:off", f"walk:{back[away]}", "snap:back",
    ]
    snaps = _session(html, steps)
    assert snaps["back"]["hero"] == up
    assert snaps["back"]["poi"] == "the stair up"
    assert snaps["back"]["interact"] == UP_WORDS


def test_the_last_labelled_floor_points_at_the_stair_down_when_the_next_has_no_title(tmp_path):
    # A one-floor labelled Section: the floor below its only floor is the
    # hollow's first, which declares no label, so the hint names the stair
    # rather than the hollow's region id.
    short = copy.deepcopy(LABELLED)
    short["sections"][0]["floors"] = 1
    short["sections"][0]["pattern"] = ["entry"]
    html = _weave(tmp_path, short)
    plan = delve.floor_plan(short, 1)
    up, down = plan["anchors"]["up"], plan["anchors"]["down"]
    assert delve.floor_plan(short, 2)["name"] == "hollow-0-1"
    snaps = _session(html, _arrive(1, short) + [
        "snap:arrived", "click:#interact", "snap:read"])
    assert snaps["arrived"]["region"] == "cellar-0-1"
    assert snaps["arrived"]["poi"] == "the Cellar, floor 1"
    assert snaps["read"]["speechLine"] == (
        f"To reach the stair down, go {_compass(up, down)}.")


def test_a_section_with_no_label_arrives_exactly_as_before(tmp_path):
    html = _weave(tmp_path, DESCENT)
    snaps = _session(html, _arrive(1, DESCENT) + ["snap:arrived"])
    arrived = snaps["arrived"]
    assert arrived["region"] == "cellar-0-1"
    assert arrived["poi"] == "the stair up"
    assert arrived["interact"] == UP_WORDS


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
