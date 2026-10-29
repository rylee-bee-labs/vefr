"""The RPG core (ADR 0021), played in the real woven file in jsdom.

The engine half - validation, the bake, the Python twin - is pinned in
`test_rpg_core.py`. This file plays each rule the way a pack gets it when it
opts in, and the pack that opts in to none of it, which must play the old
fight with the old sentences and save no new key:

  * guard, on the hero and on a foe, and never below 1;
  * rolled blows - misses and critical hits - said in words, and the same
    every time the same moves are made;
  * traits on worn gear: stats, a reaction, a curse named once read, and a
    worn thing that keeps its rolled instance and gives it back;
  * mana and a spell that harms past guard, and a cast refused for want
    of mana; a thing that casts on charges, and a rest that wakes it again;
  * a drink that costs a turn when the pack says so;
  * a shop with its own stock, a markup and an entry that waits on a flag;
  * the fight row's own labels and a Cast button only while there is a
    harmful spell to cast;
  * the trip: the town stair that starts at the deepest landing, and a fall
    that wakes at home and leaves the bag's things where the hero fell.

Every read is what a player and a screen reader get, or the harness view the
player publishes. Needs node and jsdom; skips without them.
"""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "rpg_play_harness.mjs"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_descent_pack as descent_pack  # noqa: E402
import make_rpg_pack as mk  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def play(tmp_path, steps, pack=None, **build):
    pack = pack or mk.build(tmp_path, **build)
    out = tmp_path / "rpg-test.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    run = subprocess.run(["node", str(HARNESS), str(out), json.dumps({"steps": steps})],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr + run.stdout
    result = json.loads(run.stdout)
    assert result["errors"] == [], result["errors"]
    return result


LEFT = {"do": "press", "dir": "left"}


def foe(snapshot, fid="ember-hound"):
    return next(f for f in snapshot["foes"] if f["id"] == fid)


# ------------------------------------------------------------------ opt-out


def test_a_pack_with_none_of_it_fights_and_saves_as_before(tmp_path):
    out = play(tmp_path, [LEFT])["final"]
    assert foe(out)["hp"] == 3                     # 5 - the hero's 2
    assert out["hp"] == 5                          # 8 - the hound's 3
    assert "You hit an ember hound for 2." in out["said"]
    assert "an ember hound hits you for 3." in out["said"]
    assert out["mana"] == ""                       # no mana line at all
    assert out["rpg"]["fight"] is None and out["rpg"]["guard"] == 0
    assert not [k for k in out["saved"] if k.startswith(("vefr-mana-", "vefr-worn-"))]


# -------------------------------------------------------------------- guard


def test_guard_takes_from_every_blow_and_never_below_one(tmp_path):
    out = play(tmp_path, [LEFT], player={"guard": 2}, hound={"guard": 1})["final"]
    assert foe(out)["hp"] == 4                     # 2 - 1 guard
    assert out["hp"] == 7                          # 3 - 2 guard
    assert out["rpg"]["guard"] == 2
    floor = play(tmp_path, [LEFT], player={"guard": 9})["final"]
    assert floor["hp"] == 7                        # never below 1


def test_worn_guard_adds_to_the_hero(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "bagAdd('warded-coat'); equipItem('warded-coat');"
                             " bagSay('');"},
        LEFT,
    ], items=mk.ITEMS)["final"]
    assert out["rpg"]["guard"] == 1
    assert out["hp"] == 6                          # 3 - 1 guard


# -------------------------------------------------------------------- rolls


def test_rolled_blows_are_said_and_the_same_every_time(tmp_path):
    steps = [LEFT] * 6
    kw = {"fight": {"miss": 40, "crit": 40}, "hound": {"hp": 60, "atk": 1},
          "player": {"hp": 30}}
    first = play(tmp_path, steps + [{"do": "snap", "tag": "end"}], **kw)
    again = play(tmp_path, steps + [{"do": "snap", "tag": "end"}], **kw)
    assert first["snaps"]["end"]["hp"] == again["snaps"]["end"]["hp"]
    assert foe(first["snaps"]["end"])["hp"] == foe(again["snaps"]["end"])["hp"]
    assert first["final"]["said"] == again["final"]["said"]
    # Six exchanges at forty percent: the words for a roll are in what was said.
    said = " ".join(first["final"]["said"])
    assert any(w in said for w in ("You miss", "A clean hit!", "misses you", "A heavy blow!"))


# ------------------------------------------------------------------- traits


def test_worn_traits_change_the_numbers_and_react(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "bagAdd('keen-blade'); equipItem('keen-blade'); heroAtk()",
         "tag": "atk"},
        LEFT, LEFT,
    ], items=mk.ITEMS, traits=mk.TRAITS)
    assert out["evals"]["atk"] == 4                # 2 + 1 worn mod + 1 keen
    assert out["final"]["rpg"]["traits"]["atk"] == 1
    assert out["final"]["rpg"]["traits"]["reactions"] == ["kill_heal"]
    assert not foe(out["final"])["alive"]      # two blows of 4 fell it
    assert any("a keen blade warms you: you recover 2 health." in line
               for line in out["final"]["said"])


def test_a_worn_thing_keeps_its_instance_and_gives_it_back(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "bagAdd('plain-ring', {rarity: 'rare', traits: ['keen']});"
                             " equipItem('plain-ring', bagCarried()[0]); VEFR_RPG().worn",
         "tag": "worn"},
        {"do": "eval", "js": "Object.keys(localStorage).filter(k => k.startsWith('vefr-worn-'))",
         "tag": "keys-on"},
        {"do": "eval", "js": "takeOffSlot('charm'); bagCarried()", "tag": "bag"},
        {"do": "eval", "js": "Object.keys(localStorage).filter(k => k.startsWith('vefr-worn-'))",
         "tag": "keys-off"},
    ], items=mk.ITEMS, traits=mk.TRAITS)["evals"]
    assert out["worn"] == {"charm": {"rarity": "rare", "traits": ["keen"]}}
    assert out["keys-on"] == ["vefr-worn-rpg-test"]
    assert out["bag"][0]["rarity"] == "rare" and out["bag"][0]["traits"] == ["keen"]
    assert out["keys-off"] == []


def test_a_rarer_copy_of_a_worn_thing_can_be_swapped_in(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "bagAdd('plain-ring', {rarity: 'common', traits: []});"
                             " bagAdd('plain-ring', {rarity: 'rare', traits: ['keen']});"
                             " equipItem('plain-ring', bagCarried()[0]);"
                             " equipItem('plain-ring', bagCarried()[0]);"
                             " [VEFR_RPG().worn, bagCarried().map(c => c.rarity)]", "tag": "swap"},
    ], items=mk.ITEMS, traits=mk.TRAITS)["evals"]["swap"]
    assert out[0] == {"charm": {"rarity": "rare", "traits": ["keen"]}}
    assert out[1] == ["common"]


def test_a_curse_is_named_once_it_is_read(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "bagAdd('plain-ring', {rarity: 'fine', traits: ['reckless']});"
                             " carriedName(bagCarried()[0])", "tag": "unread"},
        {"do": "eval", "js": "localStorage.removeItem(BAG_KEY);"
                             " bagAdd('plain-ring', {rarity: 'fine', traits: ['reckless'],"
                             " identified: true}); carriedName(bagCarried()[0])", "tag": "read"},
    ], items=mk.ITEMS, traits=mk.TRAITS)["evals"]
    assert "reckless" not in out["unread"]
    assert out["read"] == "a plain ring (fine) - traits: reckless (cursed)"


# -------------------------------------------------------------------- magic

MAGIC = {"items": mk.ITEMS, "spells": mk.SPELLS, "growth": mk.GROWTH,
         "player": {"mana": 5}}


def test_a_spell_costs_mana_harms_past_guard_and_is_refused_when_short(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "castSpell('bolt')"}, {"do": "snap", "tag": "one"},
        {"do": "eval", "js": "castSpell('bolt')"}, {"do": "snap", "tag": "two"},
        {"do": "eval", "js": "castSpell('bolt')", "tag": "three"},
    ], hound={"hp": 10, "guard": 5}, **MAGIC)
    one, two = out["snaps"]["one"], out["snaps"]["two"]
    assert foe(one)["hp"] == 7 and one["mana"] == "Mana 3/5"
    assert foe(two)["hp"] == 4 and two["mana"] == "Mana 1/5"
    assert out["evals"]["three"] is False
    assert "Not enough mana" in out["final"]["bagLive"]
    assert foe(out["final"])["hp"] == 4


def test_a_ward_raises_guard_for_its_turns(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "castSpell('ward')"},
        {"do": "snap", "tag": "warded"},
        LEFT, LEFT, LEFT,
    ], hound={"hp": 40, "atk": 3}, **MAGIC)
    assert out["snaps"]["warded"]["rpg"]["ward"] == {"guard": 2, "turns": 2}
    assert out["final"]["rpg"]["ward"] == {"guard": 0, "turns": 0}


def test_a_thing_that_casts_spends_charges_and_rests_awake(tmp_path):
    items = dict(mk.ITEMS, wand={"name": "a birch wand", "casts": "bolt", "charges": 2})
    out = play(tmp_path, [
        {"do": "eval", "js": "bagAdd('wand'); useItem('wand'); useItem('wand');"
                             " carriedName(bagCarried()[0])", "tag": "spent"},
        {"do": "eval", "js": "useItem('wand')", "tag": "third"},
        {"do": "eval", "js": "HERO_HP = 2; saveHeroHp(); timeRest();"
                             " [carriedName(bagCarried()[0]), HERO_HP]", "tag": "rested"},
    ], hound={"hp": 6}, items=items, spells=mk.SPELLS, growth=mk.GROWTH,
        time={"rest": True, "rest_heals": True})
    ev = out["evals"]
    assert ev["spent"] == "a birch wand - 0 charges"
    assert ev["third"] is False
    assert not foe(out["final"])["alive"]       # 6 - 3 - 3: and the town is quiet
    assert ev["rested"] == ["a birch wand - 2 charges", 8]


def test_the_rest_button_survives_the_row_being_redrawn(tmp_path):
    rest = "!!document.querySelector('#verb-row [data-rest]')"
    out = play(tmp_path, [
        {"do": "eval", "js": rest, "tag": "before"},
        {"do": "eval", "js": "bagAdd('potion'); " + rest, "tag": "after"},
    ], items=mk.ITEMS, time={"rest": True})["evals"]
    assert out == {"before": True, "after": True}


def test_rest_does_not_heal_beside_a_living_foe(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "HERO_HP = 2; saveHeroHp(); timeRest(); HERO_HP", "tag": "hp"},
    ], time={"rest": True, "rest_heals": True})
    assert out["evals"]["hp"] == 2


# -------------------------------------------------------------------- turns


def test_a_drink_costs_a_turn_only_when_the_pack_says_so(tmp_path):
    drink = [{"do": "eval", "js": "bagAdd('potion'); HERO_HP = 4; saveHeroHp();"
                                  " useItem('potion'); HERO_HP", "tag": "hp"}]
    free = play(tmp_path, drink, items=mk.ITEMS)["evals"]["hp"]
    costs = play(tmp_path, drink, items=mk.ITEMS, fight={"turns": True})["evals"]["hp"]
    assert free == 6                               # 4 + 2, and the hound waits
    assert costs == 3                              # 4 + 2 - the hound's 3


# --------------------------------------------------------------------- shop


def test_a_shop_sells_its_stock_at_its_markup_and_waits_on_a_flag(tmp_path):
    rows = ("[...document.querySelectorAll('#trade-buy .trade-row')]"
            ".map(r => r.querySelector('.trade-name').textContent + ' '"
            " + r.querySelector('.trade-price').textContent)")
    out = play(tmp_path, [
        {"do": "eval", "js": "openTrade('keeper', 'The keeper'); " + rows, "tag": "before"},
        {"do": "eval", "js": "closeTrade(); window.rulesStateNow = function () {"
                             " return {flags: {opened: true}}; };"
                             " openTrade('keeper', 'The keeper'); " + rows, "tag": "after"},
    ], items=mk.ITEMS, keeper={"shop": "true", "markup": 150,
                               "stock": ["potion", {"item": "gem", "flag": "opened"}]})
    assert out["evals"]["before"] == ["a cloudy potion 8 gold"]       # ceil(5 * 1.5)
    assert out["evals"]["after"] == ["a cloudy potion 8 gold", "a cut gem 11 gold"]


def test_a_shop_with_no_stock_sells_everything_priced_as_before(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "openTrade('keeper', 'The keeper');"
                             " [...document.querySelectorAll('#trade-buy .trade-price')]"
                             ".map(p => p.textContent)", "tag": "prices"},
    ], items=mk.ITEMS, keeper={"shop": "true"})
    assert sorted(out["evals"]["prices"]) == sorted(["5 gold", "9 gold", "4 gold", "7 gold"])


# ---------------------------------------------------------------- the verbs


def test_the_row_names_its_own_labels_and_cast_only_with_a_harmful_spell(tmp_path):
    verbs = [{"verb": "attack", "label": "Strike"}, {"verb": "cast", "label": "Cast"}]
    labels = ("[...document.querySelectorAll('#verb-row button[data-verb]')]"
              ".map(b => b.dataset.label)")
    known = play(tmp_path, [{"do": "eval", "js": labels, "tag": "row"}],
                 verbs=verbs, **MAGIC)["evals"]["row"]
    assert known == ["Strike", "Cast"]
    later = copy.deepcopy(mk.SPELLS)
    later["spells"][0]["level"] = 2
    unknown = play(tmp_path, [{"do": "eval", "js": labels, "tag": "row"}], verbs=verbs,
                   items=mk.ITEMS, spells=later, growth=mk.GROWTH,
                   player={"mana": 5})["evals"]["row"]
    assert unknown == ["Strike"]


# ---------------------------------------------------------------- the pouch


def test_a_keepsake_in_the_pouch_takes_no_place_in_the_bag(tmp_path):
    pack = mk.build(tmp_path, items=dict(mk.ITEMS, button={"name": "a shoe button",
                                                            "pouch": True}))
    world = json.loads((pack / "world.json").read_text())
    world["bag"] = {"size": 2}
    (pack / "world.json").write_text(json.dumps(world))
    out = play(tmp_path, [
        {"do": "eval", "js": "[bagAdd('potion'), bagAdd('potion'), bagAdd('gem'),"
                             " bagAdd('button'), bagAdd('button'), bagHolds().length,"
                             " bagItems().length]", "tag": "adds"},
    ], pack=pack)["evals"]["adds"]
    assert out == [True, True, False, True, True, 2, 4]


# ---------------------------------------------------------------- the trips


def _trip_pack(tmp_path, **extra):
    descent = {"run_seed": "run-a", "entry": {"region": "town", "at": list(descent_pack.ENTRY_AT)},
               "sections": copy.deepcopy(descent_pack.SECTIONS)}
    descent.update(extra)
    return descent_pack.build(tmp_path, descent=descent)


ENTRY_TO = ("(window.VEFR_TRANSITIONS || []).filter(t => t.from === 'town'"
            " && String(t.at) === String(VEFR_DESCENT_DEF.entry.at)).map(t => t.to)")


def test_the_town_stair_starts_at_the_deepest_landing(tmp_path):
    pack = _trip_pack(tmp_path, resume="deepest-landing")
    out = play(tmp_path, [
        {"do": "eval", "js": ENTRY_TO, "tag": "fresh"},
        {"do": "eval", "js": "VEFR_DESCENT.ensureRegion(VEFR_DESCENT.floorPlan(2).name); "
                             + ENTRY_TO, "tag": "landed"},
    ], pack=pack)["evals"]
    assert out["fresh"] == ["cellar-0-1"]
    assert out["landed"] == ["cellar-0-2"]         # the pattern's landing is floor 2


def test_without_resume_every_trip_starts_at_the_first_floor(tmp_path):
    out = play(tmp_path, [
        {"do": "eval", "js": "VEFR_DESCENT.ensureRegion(VEFR_DESCENT.floorPlan(2).name); "
                             + ENTRY_TO, "tag": "landed"},
    ], pack=_trip_pack(tmp_path))["evals"]
    assert out["landed"] == ["cellar-0-1"]


FALL = """
(function () {
  var plan = VEFR_DESCENT.floorPlan(1);
  VEFR_ENTER_REGION(plan.name, null);
  var foe = VEFR_COMBAT.enemies.find(function (e) { return e.alive; });
  var spots = [[1, 0], [-1, 0], [0, 1], [0, -1]].map(function (d) {
    return [foe.at[0] + d[0], foe.at[1] + d[1]]; });
  VEFR_ENTER_REGION(plan.name, spots.find(function (s) {
    return plan.rows[s[1]] && plan.rows[s[1]][s[0]] === '.'; }));
  window.VEFR_ITEMS.keepsake = {name: 'a keepsake', keep: true};
  bagAdd('pebble'); bagAdd('pebble'); bagAdd('keepsake');
  HERO_HP = 1; saveHeroHp();
  VEFR_SPEND_TURN();
  return {name: plan.name, region: VEFR_COMBAT.region, bag: bagItems(),
          satchel: (VEFR_DESCENT.satchelIn(plan.name) || {}).items,
          line: document.getElementById('combat-live').textContent};
})()
"""


def test_a_fall_wakes_at_home_and_the_bag_waits_where_the_hero_fell(tmp_path):
    pack = _trip_pack(tmp_path, fall="home")
    world = json.loads((pack / "world.json").read_text())
    world["fight"] = {"turns": True}
    (pack / "world.json").write_text(json.dumps(world))
    out = play(tmp_path, [{"do": "eval", "js": FALL, "tag": "fell"}], pack=pack)
    fell = out["evals"]["fell"]
    assert fell["region"] == "town"
    assert fell["bag"] == ["keepsake"]            # a `keep` thing stays with the hero
    assert fell["satchel"] == ["pebble", "pebble"]
    assert "What you carried waits where you fell." in fell["line"]


def test_walking_onto_the_satchel_takes_it_all_back(tmp_path):
    js = """
(function () {
  window.VEFR_ITEMS.keepsake = {name: 'a keepsake', keep: true};
  var plan = VEFR_DESCENT.floorPlan(1);
  bagAdd('pebble');
  VEFR_DESCENT.dropSatchel(plan.name, plan.anchors.up);
  var gone = bagItems().length;
  VEFR_ENTER_REGION(plan.name, plan.anchors.up);
  VEFR_TAKE_HERE();
  return {gone: gone, back: bagItems(), left: VEFR_DESCENT.satchelIn(plan.name)};
})()
"""
    out = play(tmp_path, [{"do": "eval", "js": js, "tag": "took"}],
               pack=_trip_pack(tmp_path, fall="home"))["evals"]["took"]
    assert out == {"gone": 0, "back": ["pebble"], "left": None}
