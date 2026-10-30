"""Monster skills and throwing (ADR 0024), played in the real woven file.

The RPG fixture's one hound beside (or a few steps from) the hero carries
each skill in turn; each test plays the presses a player would and reads
what a player and a screen reader get - the fight's lines, the HUD's state
line, the health - and the harness views the player publishes.

  * web: from a distance on a clear line, the hero is stuck for exactly the
    turns it said, struggling costs the turn, and a blow is still a blow;
  * spit: from a distance, a hit guard takes from, then it waits;
  * fester: a bite that keeps biting, said once;
  * dust: the hero's blows go wide, against the same seed without it;
  * squeal: once, at half health;
  * throw: at the foe, rolled like a blow, landing on its tile; from the
    fight row, the Bag and the quick bar; nothing in reach costs nothing;
  * the generated floor's monsters keep their guard, gold and skills (the
    ADR 0021 bug this change found).

Needs node and jsdom; skips without them.
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

STONE = {"stone": {"name": "a stone", "throw": {"harm": 3, "range": 5}}}


def play(tmp_path, steps, pack=None, **build):
    opts = {"fight": {"turns": True}}
    opts.update(build)
    pack = pack or mk.build(tmp_path, **opts)
    out = tmp_path / "skills.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    run = subprocess.run(["node", str(HARNESS), str(out),
                          json.dumps({"steps": steps, "matchMedia": False})],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr + run.stdout
    result = json.loads(run.stdout)
    assert result["errors"] == [], result["errors"]
    return result


def press(d):
    return {"do": "press", "dir": d}


def ev(js, tag):
    return {"do": "eval", "js": js, "tag": tag}


STATE = "document.getElementById('hud-state').textContent"
AT = "VEFR_COMBAT.hero.at"


# --------------------------------------------------------------------- web


def test_a_web_holds_the_hero_for_exactly_the_turns_it_said(tmp_path):
    hound = {"at": [6, 4], "hp": 9, "skills": [{"skill": "web", "range": 3, "turns": 2}]}
    out = play(tmp_path, [press("up"), ev(STATE, "held"), ev(AT, "at1"),
                          press("up"), ev(AT, "at2"), press("up"), ev(AT, "at3"),
                          press("up"), ev(AT, "at4")], hound=hound)
    e = out["evals"]
    said = out["final"]["said"]
    assert said[0] == "an ember hound throws a web over you: you are stuck for 2 turns."
    assert e["held"] == "Webbed (2 turns left)"
    assert e["at1"] == e["at2"] == e["at3"] == [3, 3]      # two struggles
    assert e["at4"] == [3, 2]                              # then free
    assert said.count("You struggle in the web.") >= 1
    assert any(line.endswith("You pull free of the web.") for line in said)


def test_a_webbed_hero_can_still_strike_what_stands_beside_them(tmp_path):
    hound = {"hp": 9, "skills": [{"skill": "web", "range": 2, "turns": 3}]}
    # Step away, get webbed from two tiles, then the hound walks up: a press
    # toward it is a blow, not a struggle.
    out = play(tmp_path, [press("right"), press("left"), press("left")], hound=hound)
    assert any(line.startswith("You hit an ember hound for") for line in out["final"]["said"])


def test_a_wall_between_stops_a_web(tmp_path):
    """The same web, the same presses, with a wall put between: no web."""
    hound = {"at": [6, 4], "hp": 9, "skills": [{"skill": "web", "range": 3, "turns": 2}]}
    open_ground = play(tmp_path / "a", [press("up")], hound=hound)
    pack = mk.build(tmp_path / "b", hound=hound, fight={"turns": True})
    map_md = pack / "acts" / "act-1" / "town" / "map.md"
    rows = map_md.read_text(encoding="utf-8").split("\n")
    for y in (3, 4, 5):
        rows[y] = rows[y][:5] + "#" + rows[y][6:]
    map_md.write_text("\n".join(rows), encoding="utf-8")
    walled = play(tmp_path / "b", [press("up")], pack=pack)
    assert any("web" in line for line in open_ground["final"]["said"])
    assert not any("web" in line for line in walled["final"]["said"])


# -------------------------------------------------------------------- spit


def test_a_spit_hits_from_a_distance_and_then_waits(tmp_path):
    hound = {"at": [7, 4], "hp": 9, "skills": [{"skill": "spit", "range": 4, "harm": 3, "every": 3}]}
    out = play(tmp_path, [press("up"), press("down")], hound=hound, player={"guard": 1})
    said = out["final"]["said"]
    assert said[0] == "an ember hound spits at you for 2."     # 3, less a guard of 1
    assert said.count("an ember hound spits at you for 2.") == 1
    assert out["final"]["hp"] == 6


# ------------------------------------------------------------ fester, dust


def test_a_festering_bite_keeps_biting_and_is_said_once(tmp_path):
    hound = {"hp": 30, "atk": 1, "skills": [{"skill": "fester", "chance": 100, "turns": 2, "tick": 1}]}
    out = play(tmp_path, [press("left"), ev(STATE, "st"), press("left")], hound=hound)
    said = " ".join(out["final"]["said"])
    assert out["evals"]["st"] == "Festering (poison, 1 turn left)"
    assert said.count("The bite festers: 1 a turn for 2 turns.") == 2   # a fresh one each time it closed
    assert "The poison takes 1 from you." in said


def test_dust_makes_the_heros_blows_go_wide(tmp_path):
    presses = [press("left")] * 8
    dusted = play(tmp_path / "a", presses, player={"hp": 40},
                  hound={"hp": 60, "atk": 1, "skills": [{"skill": "dust", "chance": 100, "turns": 9, "miss": 50}]})
    clear = play(tmp_path / "b", presses, player={"hp": 40}, hound={"hp": 60, "atk": 1})
    missed = [line for line in dusted["final"]["said"] if line == "You miss an ember hound."]
    assert missed, dusted["final"]["said"]
    assert "You miss an ember hound." not in clear["final"]["said"]
    assert dusted["final"]["said"][1].endswith("Dust gets in your eyes: your blows go wide for 9 turns.")


# ------------------------------------------------------------------ squeal


def test_a_squeal_comes_once_at_half_health(tmp_path):
    hound = {"hp": 6, "atk": 1, "skills": [{"skill": "squeal"}]}
    out = play(tmp_path, [press("left"), press("left")], hound=hound, player={"hp": 20, "atk": 2})
    said = " ".join(out["final"]["said"])
    # 6 -> 4: not yet half; 4 -> 2: half or below, and it squeals.
    assert said.count("squeals for help") == 1
    assert "You hit an ember hound for 2. an ember hound squeals for help, and nothing answers." in said


# ------------------------------------------------------------------- throw


def test_a_thrown_thing_strikes_the_foe_and_lands_on_its_tile(tmp_path):
    out = play(tmp_path, [ev("bagAdd('stone'); VEFR_THROW('stone', null)", "threw"),
                          ev("[bagItems(), VEFR_COMBAT.floor.map(d => [d.item, d.at])]", "where")],
               hound={"at": [6, 4], "hp": 9}, items=STONE)
    assert out["evals"]["threw"] is True
    assert out["final"]["said"][0] == "You throw a stone at an ember hound for 3."
    assert out["evals"]["where"] == [[], [["stone", [6, 4]]]]
    assert out["final"]["foes"][0]["hp"] == 6


def test_nothing_in_reach_costs_nothing(tmp_path):
    out = play(tmp_path, [ev("bagAdd('stone'); VEFR_THROW('stone', null)", "threw"),
                          ev("bagItems()", "bag")],
               hound={"at": [10, 8], "hp": 9}, items={"stone": {"name": "a stone", "throw": {"harm": 3, "range": 2}}})
    assert out["evals"]["threw"] is False and out["evals"]["bag"] == ["stone"]
    assert out["final"]["said"] == ["There is nothing in reach to throw a stone at."]
    assert out["final"]["hp"] == 8                           # no turn passed


def test_the_fight_row_throws_only_while_something_can_be_thrown(tmp_path):
    verbs = ["attack", "throw"]
    row = "Array.from(document.querySelectorAll('#verb-row button[data-verb]')).map(b => b.dataset.verb)"
    out = play(tmp_path, [ev("renderVerbRow(); " + row, "none"),
                          ev("bagAdd('stone'); renderVerbRow(); " + row, "some")],
               hound={"at": [6, 4], "hp": 9}, items=STONE, verbs=verbs)["evals"]
    assert out["none"] == ["attack"]
    assert out["some"] == ["attack", "throw"]


def test_the_bag_and_the_quick_bar_throw_too(tmp_path):
    out = play(tmp_path, [ev("bagAdd('stone'); bagAdd('stone'); renderBagPanel();"
                             " document.querySelector('#bag-list button[data-action=\"throw\"]').click(); bagItems()", "bag"),
                          {"do": "key", "key": "5"},
                          ev("[bagItems(), VEFR_COMBAT.enemies[0].hp]", "bar")],
               hound={"at": [6, 4], "hp": 20}, items=STONE, display={"hotbar": True})["evals"]
    assert out["bag"] == ["stone"]
    assert out["bar"][0] == []
    assert out["bar"][1] < 20 - 3                             # two throws struck (or one missed nothing)


# ------------------------------------------------- the generated floor's mobs


def test_a_generated_monster_keeps_its_guard_gold_and_skills(tmp_path):
    """Until ADR 0024 the floor's enemy entries dropped `guard` and `gold`."""
    descent = {"run_seed": "run-a", "entry": {"region": "town", "at": list(descent_pack.ENTRY_AT)},
               "sections": copy.deepcopy(descent_pack.SECTIONS)}
    pack = descent_pack.build(tmp_path, descent=descent)
    blueprint = {"blueprint": 1, "regions": {}, "families": {
        name: {"defaults": {"name": "a " + name, "hp": 4, "atk": 1, "guard": 1, "gold": [2, 2],
                            "skills": [{"skill": "squeal"}]}}
        for name in ("rat", "moth", "shade")}}
    js = ("(function () { VEFR_DESCENT_DEF.blueprint = " + json.dumps(blueprint) + ";"
          " var plan = VEFR_DESCENT.floorPlan(1); VEFR_DESCENT.ensureRegion(plan.name);"
          " return (VEFR_ENEMIES[plan.name] || []).filter(e => !e.warden)"
          ".map(e => [e.guard, e.gold, e.skills]); })()")
    entries = play(tmp_path, [ev(js, "entries")], pack=pack)["evals"]["entries"]
    assert entries, "the floor drew no monster"
    for guard, gold, skills in entries:
        assert guard == 1 and gold == 2 and skills == [{"skill": "squeal", "radius": 16}]
