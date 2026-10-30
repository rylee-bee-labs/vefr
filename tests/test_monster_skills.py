"""Monster skills and throwing (ADR 0024): the engine half.

The play half - each skill and a throw in the woven player - is pinned in
`test_monster_skills_play.py`. This file pins what Python owns:

  * the reader: `rpg.skills_of` fills each skill's defaults, keeps the pack's
    order, drops a skill it cannot play and keeps at most two;
  * the validator: one plain sentence per problem, on a Blueprint family and
    on a hand-placed enemy;
  * `rpg.throw_of` and the item check;
  * the bake: `skills` on a hand-placed enemy and `throw` on an item ride
    along only when the pack names them, so a pack without them bakes the
    bytes it always did;
  * the descent's Python twin carries a family's skills onto its mobs (the
    JavaScript twin is held to it by `test_descent_parity.py`).
"""

import copy
import sys
from pathlib import Path

import pytest

from vefr import cli, delve, maplab, rpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_rpg_pack as mk  # noqa: E402

import test_descent_parity as parity  # noqa: E402


# ------------------------------------------------------------------ reader


def test_each_skill_takes_its_defaults_in_the_order_written():
    got = rpg.skills_of({"skills": [{"skill": "squeal"}, {"skill": "web", "range": 4}]})
    assert got == [{"skill": "squeal", "radius": 16},
                   {"skill": "web", "range": 4, "turns": 2, "every": 5}]


def test_every_kind_has_defaults_inside_its_own_bounds():
    for kind, spec in rpg.SKILL_KINDS.items():
        for key, (bounds, default) in spec.items():
            assert bounds[0] <= default <= bounds[1], (kind, key)
        assert rpg.skills_of({"skills": [{"skill": kind}]})[0]["skill"] == kind


@pytest.mark.parametrize("bad", [
    {"skill": "fly"},
    {"skill": "web", "range": 9},
    {"skill": "spit", "colour": "green"},
    {"skill": "dust", "miss": True},
    "web",
])
def test_a_skill_it_cannot_play_is_left_out(bad):
    assert rpg.skills_of({"skills": [bad, {"skill": "squeal"}]}) == [
        {"skill": "squeal", "radius": 16}]


def test_a_monster_keeps_at_most_two():
    three = [{"skill": "web"}, {"skill": "spit"}, {"skill": "squeal"}]
    assert [s["skill"] for s in rpg.skills_of({"skills": three})] == ["web", "spit"]


def test_a_record_without_skills_has_none():
    for record in ({}, {"skills": None}, {"skills": "web"}, None):
        assert rpg.skills_of(record) == []


# --------------------------------------------------------------- validator

WHERE = "blueprint.json: family 'spider'"


@pytest.mark.parametrize("skills, sentence", [
    ("web", f'{WHERE} skills must be a list of up to 2 skills, such as [{{"skill": "web"}}]'),
    ([{"skill": "web"}, {"skill": "spit"}, {"skill": "dust"}], f"{WHERE} skills may hold at most 2 skills"),
    ([{"skill": "fly"}], f"{WHERE} skill 1 must name its skill, one of web, spit, fester, dust, squeal"),
    ([{"skill": "web"}, {"skill": "web"}], f"{WHERE} skill 2 is a second web: a monster has each skill once"),
    ([{"skill": "spit", "colour": "green"}], f"{WHERE} skill 1 (spit) may only hold range, harm, every, not 'colour'"),
    ([{"skill": "web", "range": 1}], f"{WHERE} skill 1 (web) range must be a whole number from 2 to 6"),
    ([{"skill": "squeal", "radius": 30}], f"{WHERE} skill 1 (squeal) radius must be a whole number from 2 to 24"),
])
def test_each_problem_is_one_plain_sentence(skills, sentence):
    assert rpg.family_errors("spider", {"skills": skills}) == [sentence]


def test_good_skills_say_nothing():
    good = [{"skill": "web", "range": 3, "turns": 2, "every": 5}, {"skill": "spit"}]
    assert rpg.family_errors("spider", {"skills": good}) == []


def test_a_hand_placed_enemy_is_checked_the_same_way(tmp_path):
    pack = mk.build(tmp_path, hound={"skills": [{"skill": "web", "turns": 9}]})
    errors = maplab.validate(maplab.load_pack(pack), pack)
    hits = [e for e in errors if "skill" in e]
    assert hits == ["enemy 'an ember hound' in region 'town' skill 1 (web) turns must be a "
                    "whole number from 1 to 5"], errors


# ------------------------------------------------------------------- throw


def test_throw_takes_its_range_default_and_refuses_anything_else():
    assert rpg.throw_of({"throw": {"harm": 2}}) == {"harm": 2, "range": 5}
    assert rpg.throw_of({"throw": {"harm": 3, "range": 8}}) == {"harm": 3, "range": 8}
    for bad in ({"harm": 0}, {"harm": 2, "range": 1}, {"harm": 2, "spin": True}, 2):
        assert rpg.throw_of({"throw": bad}) is None
    assert rpg.item_errors("stone", {"name": "a stone", "throw": {"harm": 30}}, []) == [
        "item 'a stone' (stone) throw must be {\"harm\": 1 to 20, \"range\": 2 to 8}, "
        "such as {\"harm\": 2, \"range\": 5}"]


# -------------------------------------------------------------------- bake


def _baked(tmp_path, **build):
    html = cli.weave_html(mk.build(tmp_path, **build))
    return html


def test_skills_and_throw_ride_the_bake_only_when_named(tmp_path):
    plain = _baked(tmp_path / "plain")
    skilled = _baked(tmp_path / "skilled",
                     hound={"skills": [{"skill": "spit"}]},
                     items={"stone": {"name": "a stone", "throw": {"harm": 2}}})
    assert '"skills"' not in plain and '"throw"' not in plain
    baked = skilled.replace(" ", "")
    assert '"skills":[{"skill":"spit","range":4,"harm":2,"every":3}]' in baked
    assert '"throw":{"harm":2,"range":5}' in baked
    items = cli._player_items({"items": {"stone": {"name": "a stone", "throw": {"harm": 2}}}})
    assert items["stone"]["throw"] == {"harm": 2, "range": 5}


# ------------------------------------------------------------- the descent


def test_the_python_twin_carries_a_familys_skills_onto_its_mobs():
    descent = copy.deepcopy(parity.RPG_DESCENT)
    seen = 0
    for depth in parity.RPG_DEPTHS:
        for mob in delve.floor_plan(descent, depth, catalog=parity.RPG_ITEMS)["mobs"]:
            if "skills" in mob:
                seen += 1
                assert all(s["skill"] in rpg.SKILL_KINDS for s in mob["skills"])
    assert seen, "no mob of a skilled family was drawn"
    # And a descent whose families name no skills plans the dicts it planned.
    plain = copy.deepcopy(parity.RPG_DESCENT)
    for family in plain["blueprint"]["families"].values():
        family.get("defaults", {}).pop("skills", None)
    for depth in parity.RPG_DEPTHS:
        assert not any("skills" in m for m in delve.floor_plan(plain, depth, catalog=parity.RPG_ITEMS)["mobs"])
