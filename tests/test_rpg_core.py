"""The RPG core (ADR 0021): validation, the bake, and the Python twin.

The play half is `test_rpg_core_play.py`. This file pins the engine half:

  * every ADR 0021 key is refused in one plain sentence when it is wrong,
    and a pack that names none of them is told nothing;
  * the bake carries a key only when the pack named it, so a pack that
    names none of them bakes the item, spell, enemy and speaker records it
    always baked;
  * the descent's Python twin reads a Section's `curve` through
    `vefr.mob_stats` and a family's `guard`, `drop_chance` and `gold`, each
    on a stream of its own - so a Section and a family that name none of
    them draw the floors they always drew.
"""

import copy
import json
import sys
from pathlib import Path

from vefr import cli, delve, maplab, rpg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_rpg_pack as mk  # noqa: E402


def errors(world, pack_dir=None):
    return maplab.rpg_errors(world, pack_dir)


# --------------------------------------------------------------- validation


def test_a_pack_that_names_none_of_it_is_told_nothing():
    assert errors({"player": {"hp": 6}, "items": {}}) == []
    sample = json.loads((ROOT / "worlds" / "sample-world" / "world.json").read_text())
    assert errors(sample) == []


def test_the_fight_block_is_bounded_and_closed():
    assert errors({"fight": {"miss": 10, "crit": 8, "crit_times": 3, "turns": True}}) == []
    said = errors({"fight": {"miss": 60, "crit": -1, "crit_times": 5, "turns": "yes",
                             "luck": 1}})
    assert "world.json: fight may only hold miss, crit, crit_times, turns, not 'luck'" in said
    assert any("fight.miss must be a whole number from 0 to 50" in s for s in said)
    assert any("fight.crit must be a whole number from 0 to 50" in s for s in said)
    assert any("fight.crit_times must be 2 or 3" in s for s in said)
    assert "world.json: fight.turns must be true or false" in said


def test_the_heros_guard_and_mana_are_bounded():
    assert errors({"player": {"guard": 2, "mana": 6}}) == []
    said = errors({"player": {"guard": 100, "mana": -1}})
    assert any("player.guard must be a whole number from 0 to 99" in s for s in said)
    assert any("player.mana must be a whole number from 0 to 999" in s for s in said)


def test_the_traits_table_names_only_what_a_trait_can_do():
    assert errors({"traits": mk.TRAITS}) == []
    said = errors({"traits": {"keen": {"atk": 12, "luck": 1}, "odd": {"opener": 5},
                              "dull": "slow", "cursed": {"curse": False}}})
    assert any("trait 'keen' may only hold" in s and "'luck'" in s for s in said)
    assert any("trait 'keen' atk must be a whole number from -9 to 9" in s for s in said)
    assert any("trait 'odd' opener must be a whole number from 2 to 3" in s for s in said)
    assert any("trait 'dull' must be an object" in s for s in said)
    assert any("trait 'cursed' curse must be true" in s for s in said)


def test_a_spell_does_one_thing_and_costs_what_it_says():
    good = {"spells": mk.SPELLS}
    assert errors(good) == []
    bad = copy.deepcopy(mk.SPELLS)
    bad["spells"][0].update({"heal": 2, "range": 30})
    bad["spells"][1]["ward"] = {"guard": 2}
    said = errors({"spells": bad})
    assert any("spell 'bolt' does one thing: heal and harm cannot sit together" in s
               for s in said)
    assert any("spell 'bolt' range must be a whole number of tiles from 1 to 20" in s
               for s in said)
    assert any("spell 'ward' ward must be" in s for s in said)


def test_a_thing_that_casts_names_a_real_spell_and_its_charges():
    world = {"spells": mk.SPELLS, "items": {
        "wand": {"name": "a wand", "casts": "bolt", "charges": 3}}}
    pack_errors = maplab._rpg_item_errors("wand", world["items"]["wand"], {"bolt", "ward"})
    assert pack_errors == []
    said = maplab._rpg_item_errors(
        "stick", {"name": "a stick", "casts": "fireball", "charges": 30}, {"bolt"})
    assert any("casts 'fireball', which is not a spell this pack declares" in s for s in said)
    assert any("charges must be a whole number from 1 to 20" in s for s in said)
    lonely = maplab._rpg_item_errors("stick", {"name": "a stick", "charges": 2}, {"bolt"})
    assert any("charges need a casts" in s for s in lonely)


def test_a_shops_stock_names_its_own_items_and_a_markup():
    world = {"items": {"potion": {"name": "a potion", "value": 5}},
             "acts": [{"speakers": {"keeper": {"shop": "true", "markup": 200,
                                               "stock": ["potion",
                                                         {"item": "potion", "flag": "f"}]}}}]}
    assert errors(world) == []
    world["acts"][0]["speakers"]["keeper"].update({"markup": 50, "stock": ["anvil"]})
    said = errors(world)
    assert any("speaker 'keeper' stock names 'anvil'" in s for s in said)
    assert any("speaker 'keeper' markup must be a whole number from 100 to 500" in s
               for s in said)


def test_a_familys_guard_drop_chance_and_gold_are_bounded(tmp_path):
    (tmp_path / "blueprint.json").write_text(json.dumps({"blueprint": 2, "families": {
        "rat": {"defaults": {"guard": 1, "drop_chance": 40, "gold": [1, 4]}},
        "bad": {"defaults": {"guard": 500, "drop_chance": 101, "gold": [5, 1]}}},
        "regions": {}}))
    said = errors({}, tmp_path)
    assert not any("'rat'" in s for s in said)
    assert any("family 'bad' guard must be" in s for s in said)
    assert any("family 'bad' drop_chance must be" in s for s in said)
    assert any("family 'bad' gold must be [lo, hi]" in s for s in said)


def test_the_validator_runs_it_on_a_whole_pack(tmp_path):
    good = mk.build(tmp_path, fight={"miss": 10}, items=mk.ITEMS, spells=mk.SPELLS,
                    growth=mk.GROWTH, traits=mk.TRAITS, player={"guard": 1, "mana": 4})
    assert maplab.validate(maplab.load_pack(good), pack_dir=good) == []
    bad = mk.build(tmp_path, fight={"miss": 99})
    said = maplab.validate(maplab.load_pack(bad), pack_dir=bad)
    assert any("fight.miss must be a whole number from 0 to 50" in s for s in said)


# --------------------------------------------------------------------- bake


def test_the_bake_carries_a_key_only_when_the_pack_named_it():
    plain = cli._player_items({"items": {"potion": {"name": "a potion", "heal": 2}}})
    assert plain == {"potion": {"name": "a potion", "sprite": "", "heal": 2}}
    items = cli._player_items({"items": {
        "wand": {"name": "a wand", "casts": "bolt", "charges": 3},
        "coat": {"name": "a coat", "slot": "body", "mods": {"guard": 1, "mana": 2}}}})
    assert items["wand"]["casts"] == "bolt" and items["wand"]["charges"] == 3
    assert items["coat"]["mods"] == {"guard": 1, "mana": 2}
    pouch = cli._player_items({"items": {"button": {"name": "a button", "pouch": True},
                                         "pebble": {"name": "a pebble", "pouch": False}}})
    assert pouch["button"]["pouch"] is True and "pouch" not in pouch["pebble"]


def test_the_spell_bake_carries_cost_and_effects():
    baked = cli._player_spells({"spells": mk.SPELLS})["spells"]
    assert baked[0] == {"id": "bolt", "name": "an ember bolt", "school": "ember",
                        "level": 1, "mana": 2, "harm": 3}
    assert baked[1]["ward"] == {"guard": 2, "turns": 2}


def test_a_woven_pack_bakes_enemy_guard_and_gold_and_a_shops_stock(tmp_path):
    pack = mk.build(tmp_path, hound={"guard": 2, "gold": [3, 5]}, items=mk.ITEMS,
                    keeper={"shop": "true", "markup": 150, "stock": ["potion"]})
    html = cli.weave_html(pack)
    assert '"guard": 2' in html and '"gold": [3, 5]' in html
    assert '"stock": [{"item": "potion"}], "markup": 150' in html


def test_a_woven_pack_with_none_of_it_bakes_none_of_it(tmp_path):
    html = cli.weave_html(mk.build(tmp_path))
    for key in ('"guard":', '"gold": [', '"stock":', '"markup":', '"casts":'):
        assert key not in html


# ----------------------------------------------------------- the Python twin

SECTION = {"id": "cellar", "floors": 5, "families": [{"family": "rat"}],
           "curve": {"hp": [1.0, 2.0], "atk": [1.0, 3.0]}}


def test_the_curve_scales_through_mob_stats():
    assert rpg.curved(10, SECTION, 1, "hp") == 10
    assert rpg.curved(10, SECTION, 3, "hp") == 15     # 150 hundredths at floor 3 of 5
    assert rpg.curved(10, SECTION, 5, "hp") == 20
    assert rpg.curved(2, SECTION, 5, "atk") == 6
    assert rpg.curved(7, {"id": "flat", "floors": 5}, 5, "hp") == 7


def _floor(section, families, k=1):
    source = {"blueprint": 2, "families": families}
    rows = ["#" * 30] + ["#" + "." * 28 + "#" for _ in range(18)] + ["#" * 30]
    return delve.mobs_at("seed/cellar/0/%d" % k, section, rows, (1, 1), (28, 18),
                         source=source, k=k, depth=k)


def test_a_section_and_family_that_name_none_of_it_draw_what_they_always_drew():
    plain = {"id": "cellar", "floors": 5, "families": [{"family": "rat"}], "mobs": {"from": 6}}
    fam = {"rat": {"defaults": {"name": "a rat", "hp": 4, "atk": 1, "drops": ["pebble"]}}}
    mobs = _floor(plain, fam)
    assert mobs and all(set(m) == {"id", "family", "name", "sprite", "at", "hp", "atk",
                                   "sight", "xp", "drops"} for m in mobs)
    assert all(m["drops"] == ["pebble"] for m in mobs)


def test_guard_gold_and_drop_chance_ride_on_their_own_streams():
    section = {"id": "cellar", "floors": 5, "families": [{"family": "rat"}], "mobs": {"from": 8}}
    plain = {"rat": {"defaults": {"name": "a rat", "hp": 4, "atk": 1, "drops": ["pebble"]}}}
    rich = copy.deepcopy(plain)
    rich["rat"]["defaults"].update({"guard": 1, "gold": [2, 6], "drop_chance": 50})
    before, after = _floor(section, plain), _floor(section, rich)
    # The same monsters on the same tiles with the same numbers.
    assert [(m["at"], m["hp"], m["atk"]) for m in before] == \
        [(m["at"], m["hp"], m["atk"]) for m in after]
    assert all(m["guard"] == 1 and 2 <= m["gold"] <= 6 for m in after)
    dropped = [m["drops"] for m in after]
    assert ["pebble"] in dropped and [] in dropped     # half of eight, near enough
    for m in after:
        if m["drops"]:
            assert m["drops"] == ["pebble"]             # the item the old draw named


def test_the_curve_moves_numbers_and_nothing_else():
    flat = {"id": "cellar", "floors": 5, "families": [{"family": "rat"}], "mobs": {"from": 6}}
    steep = dict(flat, curve={"hp": [1.0, 2.0], "atk": [1.0, 2.0]})
    fam = {"rat": {"defaults": {"name": "a rat", "hp": 4, "atk": 2}}}
    a, b = _floor(flat, fam, k=5), _floor(steep, fam, k=5)
    assert [m["at"] for m in a] == [m["at"] for m in b]
    assert [m["hp"] * 2 for m in a] == [m["hp"] for m in b]
    assert [m["atk"] * 2 for m in a] == [m["atk"] for m in b]
