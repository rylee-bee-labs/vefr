"""A descent entry and an authored door cannot share a tile (vefr#352).

The reported bug had two halves and each needed its own proof:

* `vefr check` said `ok:`. `descent_errors` never compared
  `descent.entry.at` against the act's transitions, so a pack whose entry
  stood on an authored door - the dungeon unreachable by walking - passed
  every gate. The check is refused here with one sentence naming the tile
  and both regions.
* At play time the authored door won the tile. The woven list holds the
  pack's doors first and a door is found by its region and tile, first
  match wins, so Interact on the entry tile went somewhere else. The
  descent entry now takes the tile (`claimTile`), proved by walking to it
  in the real woven player and reading the region it arrived in.

And the third acceptance bullet: a pack whose entry is not on a door
validates green, plays exactly as today, and keeps both its doors - the
authored one still opens, and the descent still opens.

The play half is the same jsdom harness the other descent play tests use,
so it is SKIPped without node, and the validator half needs no node at
all.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import play_kit
from vefr import delve, maplab

from test_descent_deltas import TOWN, TOWN_HERO, _go
from test_descent_floors import DESCENT

ROOT = Path(__file__).resolve().parents[1]
ENTRY_AT = list(DESCENT["entry"]["at"])          # the fixture's own [7, 5]
FLOOR_1 = delve.floor_plan(DESCENT, 1)["name"]    # what `locate(1)` names

# A plain second region the authored door opens onto. Engine-test canon
# only, like every other fixture here: a shed behind the town.
SHED_MAP = ["#####", "#...#", "#####"]
SHED_LEGEND = {".": {"base": ["#212a20"]},
               "#": {"base": ["#2a2e33"], "solid": True}}
# The door tile used by the pack that does NOT collide: the same town's
# [9, 5], two tiles east of the entry.
DOOR_ELSEWHERE = [9, 5]

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node not installed")

CLI_RUNNER = ("import sys; from vefr.cli import vefr_main; "
              "sys.argv = ['vefr'] + sys.argv[1:]; sys.exit(vefr_main())")


# ---- the two fixtures ----------------------------------------------------

def _story_can_end(pack: Path) -> Path:
    """The pack's story can end, the way the real town pack records it.

    The descent fixture is sample-world plus a descent, and neither
    carries a setter for the pack's own `story_end` flag - so `vefr
    check`'s progress walk (main's E8c, ADR 0015 check 5) would refuse
    this pack for a story that cannot end, and the collision tests
    below would be proving nothing about the collision. The setter is
    the town fixture's own shape: a rule sets the default `king-slain`
    flag, and the flag is declared in `world.json`'s `flags` block,
    because a rule that sets an undeclared flag is refused by the
    pack's own rules. It fires on opening the satchel chest the sample
    town already carries, which nothing in these tests opens.
    """
    path = pack / "world.json"
    world = json.loads(path.read_text(encoding="utf-8"))
    world["flags"] = {"king-slain": "the story is over"}
    world["rules"] = [{"id": "the-satchel-ends-the-story",
                       "when": {"opens": {"what": "a-travellers-satchel"}},
                       "then": [{"set": "king-slain"}], "once": True}]
    path.write_text(json.dumps(world), encoding="utf-8")
    return pack


def _with_shed(pack: Path, door_at) -> Path:
    """The descent fixture plus a `shed` region and one door from the town."""
    act_dir = pack / "acts" / "act-1"
    act = json.loads((act_dir / "world.json").read_text(encoding="utf-8"))
    act["regions"] = ["town", "shed"]
    act["transitions"] = [{"from": "town", "at": list(door_at),
                           "to": "shed", "to_at": [1, 1]}]
    (act_dir / "world.json").write_text(json.dumps(act), encoding="utf-8")
    shed = act_dir / "shed"
    shed.mkdir(exist_ok=True)
    (shed / "map.md").write_text("\n".join(SHED_MAP) + "\n", encoding="utf-8")
    (shed / "contract.json").write_text(json.dumps({
        "tile": 32, "bg": "#131311", "hero_start": [1, 1],
        "sanctuary_tiles": ["."], "water_by_phase": {}, "flood_tiles": [],
        "pois": {}, "legend": SHED_LEGEND}), encoding="utf-8")
    return _story_can_end(pack)


def _colliding(tmp_path) -> Path:
    """The fixture with a door standing on the descent's entry tile."""
    return _with_shed(play_kit.pack(tmp_path, "descent"), ENTRY_AT)


def _clean(tmp_path) -> Path:
    """The same pack, with its door two tiles away from the entry."""
    return _with_shed(play_kit.pack(tmp_path, "descent"), DOOR_ELSEWHERE)


def _errors(pack: Path) -> list[str]:
    return maplab.validate(maplab.load_pack(pack), pack_dir=pack)


def _collisions(pack: Path) -> list[str]:
    return [e for e in _errors(pack) if "descent.entry.at" in e]


def _vefr(*args) -> tuple:
    """The real `vefr` front door in a subprocess: (returncode, output)."""
    proc = subprocess.run([sys.executable, "-c", CLI_RUNNER, *map(str, args)],
                          capture_output=True, text=True, cwd=ROOT)
    return proc.returncode, proc.stdout + proc.stderr


# ---- the check ------------------------------------------------------------

def test_a_pack_with_no_collision_validates_green(tmp_path):
    assert _errors(_clean(tmp_path)) == []


def test_the_plain_descent_pack_still_validates_green(tmp_path):
    # The fixture with no authored door at all: the check adds nothing to
    # a pack that has no descent and nothing to one with no collision.
    assert _errors(play_kit.pack(tmp_path, "descent")) == []


def test_a_descent_entry_on_an_authored_door_is_refused(tmp_path):
    errors = _collisions(_colliding(tmp_path))
    assert len(errors) == 1, errors


def test_the_refusal_names_the_tile_and_both_regions(tmp_path):
    [sentence] = _collisions(_colliding(tmp_path))
    assert "[7, 5]" in sentence, sentence
    assert "'town'" in sentence and "'shed'" in sentence, sentence


def test_the_refusal_names_the_descent_entry(tmp_path):
    # The sentence says which of the two to move, so it has to name the
    # field: `descent.entry.at` is the half the check owns.
    [sentence] = _collisions(_colliding(tmp_path))
    assert "descent.entry.at" in sentence, sentence


def test_vefr_check_exits_non_zero_on_a_colliding_pack(tmp_path):
    pack = _colliding(tmp_path)
    code, out = _vefr("check", "--pack", pack)
    assert code != 0, out
    assert "descent.entry.at [7, 5]" in out, out


def test_vefr_check_is_ok_on_a_pack_with_no_collision(tmp_path):
    code, out = _vefr("check", "--pack", _clean(tmp_path))
    assert code == 0, out
    assert "ok:" in out, out


def test_the_shipped_sample_world_still_checks_ok():
    code, out = _vefr("check", "--pack", ROOT / "worlds" / "sample-world")
    assert code == 0, out
    assert "ok:" in out, out


def test_a_door_on_another_tile_of_the_same_region_is_not_a_collision(tmp_path):
    # The same region, the same door, one tile along: the check is about
    # the tile, not about the pack having an act door at all.
    assert _collisions(_clean(tmp_path)) == []


def test_a_door_from_another_region_is_not_a_collision(tmp_path):
    pack = _clean(tmp_path)
    act_dir = pack / "acts" / "act-1"
    act = json.loads((act_dir / "world.json").read_text(encoding="utf-8"))
    # Same tile, wrong side: the entry leaves `town`, so a door that
    # leaves `shed` cannot stand on it.
    act["transitions"].append({"from": "shed", "at": list(ENTRY_AT),
                               "to": "town", "to_at": [1, 1]})
    (act_dir / "world.json").write_text(json.dumps(act), encoding="utf-8")
    assert _collisions(pack) == []


def test_a_door_on_the_entry_tile_in_a_later_act_is_refused(tmp_path):
    # The entry is a pack-level fact, so a door on its tile in act 2 is
    # the same collision even though act 1 has none.
    pack = _clean(tmp_path)
    act2 = pack / "acts" / "act-2"
    act2.mkdir(exist_ok=True)
    (act2 / "world.json").write_text(json.dumps({
        "id": "act-2", "title": "The Return", "regions": ["town", "shed"],
        "transitions": [{"from": "town", "at": list(ENTRY_AT),
                         "to": "shed", "to_at": [1, 1]}]}), encoding="utf-8")
    assert len(_collisions(pack)) == 1, _errors(pack)


def test_the_collision_is_named_once_not_once_per_reading(tmp_path):
    # An acts-shape pack lists act 1's doors twice (as `transitions` and
    # as `acts[0]['transitions']`); the author gets one sentence.
    assert len(_collisions(_colliding(tmp_path))) == 1


def test_a_malformed_entry_is_left_to_the_shape_check(tmp_path):
    # `at` written as a string is already refused by `shapes`, in its own
    # words. The collision check must not raise on it, and must not add a
    # second sentence about a door it cannot place.
    pack = _clean(tmp_path)
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["descent"]["entry"]["at"] = "7,5"
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
    errors = _errors(pack)
    assert any("at" in e for e in errors), errors
    assert _collisions(pack) == []


def test_a_pack_with_no_descent_says_nothing_about_a_collision():
    assert maplab._entry_collision_sentences({"transitions": [
        {"from": "town", "at": [7, 5], "to": "shed", "to_at": [1, 1]}]},
        None) == []


# ---- play: the descent entry takes the tile -------------------------------

def _play(pack_dir, tmp_path, steps, reads=("VEFR_COMBAT.region",
                                           "VEFR_TRANSITIONS")):
    html = play_kit.weave(pack_dir, tmp_path)
    play = play_kit.play(html, {"steps": steps, "read": list(reads)})
    assert play["errors"] == [], play["errors"]
    return play


def _stand_on(tile) -> str:
    """The steps that walk the hero from the wake tile to `tile`."""
    return _go(TOWN, TOWN_HERO, tile)


@pytest.fixture(scope="module")
def collided(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    home = tmp_path_factory.mktemp("collision")
    return _colliding(home), home


def test_interact_on_the_entry_tile_enters_the_first_generated_floor(collided):
    # The bug, walked: stand on town [7, 5] - which now holds both the
    # authored door and the descent entry - press Interact, and the floor
    # `locate(1)` names is where the hero arrives.
    pack, home = collided
    play = _play(pack, home, ["begin", _stand_on(ENTRY_AT),
                              "click:#interact", "wait:250"])
    assert play["reads"]["VEFR_COMBAT.region"] == FLOOR_1, play["reads"]


def test_the_first_floor_is_the_one_locate_names():
    # Pinned so the assertion above cannot drift from the pack contract:
    # the floor the hero lands in is `locate(1)`'s floor, not "a floor".
    assert delve.locate(1, DESCENT)[1]["id"] == "cellar"
    assert FLOOR_1 == "cellar-0-1"


def test_the_authored_door_is_gone_from_the_entry_tile(collided):
    # Not "the entry is first in the list": the descent entry is the only
    # way out of that tile, so no stale door can answer Interact later.
    pack, home = collided
    play = _play(pack, home, ["begin", "wait:100"],
                 reads=("VEFR_TRANSITIONS",))
    ways_out = [t for t in play["reads"]["VEFR_TRANSITIONS"] or []
                if t.get("from") == "town"
                and [int(v) for v in t["at"]] == ENTRY_AT]
    assert len(ways_out) == 1, ways_out
    assert ways_out[0]["to"] == FLOOR_1, ways_out


# ---- play: a pack with no collision behaves exactly as today --------------

def test_the_authored_door_still_opens_on_a_pack_with_no_collision(tmp_path):
    pack = _clean(tmp_path)
    play = _play(pack, tmp_path, ["begin", _stand_on(DOOR_ELSEWHERE),
                                  "click:#interact", "wait:250"],
                 reads=("VEFR_COMBAT.region",))
    assert play["reads"]["VEFR_COMBAT.region"] == "shed", play["reads"]


def test_the_descent_still_opens_on_a_pack_with_no_collision(tmp_path):
    pack = _clean(tmp_path)
    play = _play(pack, tmp_path, ["begin", _stand_on(ENTRY_AT),
                                  "click:#interact", "wait:250"],
                 reads=("VEFR_COMBAT.region",))
    assert play["reads"]["VEFR_COMBAT.region"] == FLOOR_1, play["reads"]


def test_the_no_collision_pack_keeps_both_doors_in_the_woven_list(tmp_path):
    pack = _clean(tmp_path)
    play = _play(pack, tmp_path, ["begin", "wait:100"],
                 reads=("VEFR_TRANSITIONS",))
    ways = {(t["from"], tuple(t["at"])): t["to"]
            for t in play["reads"]["VEFR_TRANSITIONS"] or []}
    assert ways[("town", tuple(DOOR_ELSEWHERE))] == "shed"
    assert ways[("town", tuple(ENTRY_AT))] == FLOOR_1


# ---- the packaged player is the parts ------------------------------------

def test_the_packaged_player_carries_the_precedence_fix():
    # web/packaged.html is GENERATED; this is the half of the fix a player
    # actually gets. The build itself is proven by tests/test_player_build.py.
    built = (ROOT / "web" / "packaged.html").read_text(encoding="utf-8")
    assert "function claimTile(list, t)" in built
    assert "claimTile(list, { from: entry.region" in built