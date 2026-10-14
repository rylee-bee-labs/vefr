"""vefr#461: the game canvas names the place the hero is standing in.

The canvas is one picture with one name, and the name was written once
into the shell: "The town, seen from above". It never moved. A hero who
stepped through the door into the cellar, or down a stair into the
descent, was still standing on a canvas a screen reader called the town.

The label now follows the region: the pack's own name for the place,
said as the pack said it. A generated floor answers with its Section's
label (the same words the POI line and the hints already use, vefr#362);
an authored region answers with its own region key, said in words, so
`cottage-kitchen` is read "The cottage kitchen, seen from above".

Played through the REAL woven file in jsdom (tests/fixtures/play.mjs):
the two-region interact fixture walked through its own pinned door, and
the descent fixture walked down its own first stair.
"""

import copy
import re
import shutil
from pathlib import Path

import pytest

import play_kit

from test_descent_deltas import _descend
from test_descent_floors import DESCENT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

PARTS = Path(__file__).resolve().parents[1] / "web" / "player" / "parts"
CANVAS = "attr:#town-canvas|aria-label"
SEEN = ", seen from above"

# The interact fixture's own pinned walk (make_interact_pack.py): the hero
# start [1, 1] to the door's standing spot [9, 4], one step below the
# door tile at [9, 3]. Pressing E there goes through into the cellar.
TO_DOOR_SPOT = ["down", "down", "right", "right", "up", "right", "right",
                "right", "right", "down", "down", "right", "right"]


def _play(tmp_path, steps, pack="interact", patch=None):
    html = play_kit.weave(play_kit.pack(tmp_path, pack, patch=patch), tmp_path)
    reads = [CANVAS, "VEFR_COMBAT.region"]
    out = play_kit.play(html, {"steps": steps, "read": reads})
    assert out["errors"] == [], out["errors"]
    return out["reads"]


def test_the_canvas_names_the_region_the_game_began_in(tmp_path):
    """At the start the canvas names the region the hero wakes in."""
    reads = _play(tmp_path, ["begin"])
    assert reads["VEFR_COMBAT.region"] == "town"
    assert reads[CANVAS] == "The town" + SEEN


def test_the_canvas_follows_the_hero_through_a_door(tmp_path):
    """Through the fixture's door the canvas names the cellar, so a
    screen reader does not say the town while the hero stands in it."""
    reads = _play(tmp_path, ["begin", "walk:" + ",".join(TO_DOOR_SPOT), "key:e"])
    assert reads["VEFR_COMBAT.region"] == "cellar", \
        "the walk must really have changed region"
    assert reads[CANVAS] == "The cellar" + SEEN


def test_a_labelled_floor_is_named_by_its_own_label(tmp_path):
    """A descent floor answers with the words the player is already
    given: the Section's label and the floor number, not the region id
    (`cellar-0-1`, the save's key, said out loud)."""
    descent = copy.deepcopy(DESCENT)
    descent["sections"][0]["label"] = "the Cellar"
    patch = {"world.json": {"descent": copy.deepcopy(descent)}}
    reads = _play(tmp_path, _descend(1, descent=descent), pack="descent", patch=patch)
    assert reads["VEFR_COMBAT.region"] == "cellar-0-1"
    assert reads[CANVAS] == "the Cellar, floor 1" + SEEN


def test_the_shell_keeps_the_name_it_has_before_the_first_region():
    """The shell's own attribute is the one hard-coded name: what the
    canvas is called before the player has woken anywhere. Every name
    after that is built in the player from the region the hero is in, so
    no second copy can drift from the first."""
    shell = (PARTS / "030-shell.html").read_text(encoding="utf-8")
    assert 'aria-label="The town, seen from above"' in shell
    hard = [p.name for p in sorted(PARTS.iterdir())
            if p.suffix == ".html" and p.name != "030-shell.html"
            and re.search(r'aria-label="[^"]*seen from above"',
                          p.read_text(encoding="utf-8"))]
    assert hard == [], hard