"""A monster on a generated floor is drawn with its family's sprite (MOBSPRITE).

A Section names Blueprint families and the family records carry a
`sprite` (`"sprite": "rat"`), but the descent's monsters and warden were
built without it, so the woven player drew every one of them as the
placeholder pawn. A monster now carries its family's sprite on the floor
plan and on the enemy entry the browser fights, and a family that names
none carries ''.
"""

import copy
import shutil

import pytest

import play_kit
from vefr import delve

from test_descent_deltas import _descend
from test_descent_floors import DESCENT

BLUEPRINT = {
    "blueprint": 1,
    "families": {
        "rat": {"defaults": {"name": "a grey rat", "sprite": "rat", "hp": 4,
                             "atk": 2, "sight": 5}},
        "moth": {"defaults": {"name": "a pale moth", "hp": 2, "atk": 1,
                              "sight": 3}},
    },
    "regions": {},
}

DESCENT_BP = copy.deepcopy(DESCENT)
DESCENT_BP["blueprint"] = BLUEPRINT

SPRITE_OF = {"rat": "rat", "moth": ""}


def test_a_generated_monster_carries_its_familys_sprite():
    seen = set()
    for depth in (1, 2, 3):
        for mob in delve.floor_plan(DESCENT_BP, depth)["mobs"]:
            seen.add(mob["family"])
            assert mob["sprite"] == SPRITE_OF[mob["family"]], mob
    assert seen == set(SPRITE_OF), seen


@pytest.mark.parametrize("family", sorted(SPRITE_OF))
def test_the_warden_carries_its_familys_sprite(family):
    descent = copy.deepcopy(DESCENT_BP)
    descent["sections"][0]["pattern"] = ["entry", "n", "warden"]
    descent["sections"][0]["warden"] = {"family": family, "id": f"{family}-king"}
    wardens = [mob for mob in delve.floor_plan(descent, 3)["mobs"]
               if mob.get("warden")]
    assert len(wardens) == 1, wardens
    assert wardens[0]["sprite"] == SPRITE_OF[family], wardens[0]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_enemy_the_player_fights_carries_its_familys_sprite(tmp_path):
    plan = delve.floor_plan(DESCENT_BP, 1)
    assert plan["mobs"], "the fixture descent's first floor drew no monsters"
    steps = [s for s in _descend(1, descent=DESCENT_BP) if s != "walk:"]
    pack = play_kit.pack(tmp_path, "descent",
                         patch={"world.json": {"descent": {"blueprint": BLUEPRINT}}})
    html = play_kit.weave(pack, tmp_path)
    play = play_kit.play(html, {"steps": steps,
                                "read": ["VEFR_ENEMIES"]})
    assert play["errors"] == [], play["errors"]
    entries = {e["id"]: e for e in play["reads"]["VEFR_ENEMIES"][plan["name"]]}
    for mob in plan["mobs"]:
        assert entries[mob["id"]]["sprite"] == SPRITE_OF[mob["family"]], mob
