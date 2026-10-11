"""The combat loop, mechanical half (pleasant-loop protocol).

The combat harness EXECUTES the woven single-file player against a stub
DOM and plays the first fight end to end: bump the adjacent enemy, watch
it hit back, kill it and see it stay dead, watch a distant enemy inside
its sight step toward the hero, then take a fatal blow and wake whole at
the baked wake point. It also plays the loot loop (the kill leaves its
drop on the floor, stepping onto it takes it into the bag, and a chest
gives its note and its items) and the reward loop (sell and buy at a
shopkeeper's fixed prices, then drink a potion that heals up to the
max and says so when there is nothing to heal). Deterministic: the
fixture is fixed, so every number here is pinned.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "combat_harness.mjs"
MAKE = ROOT / "tests" / "fixtures" / "make_combat_pack.py"

DEATH_LINE = "You wake in the temple. You lost nothing that mattered."


@pytest.fixture(scope="module")
def fight(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    home = tmp_path_factory.mktemp("combat-home")
    made = subprocess.run(
        [sys.executable, str(MAKE), str(home)],
        capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    pack = Path(made.stdout.strip())
    out = home / "combat.html"
    rc = cli.cmd_build_web(_args(pack, out))
    assert rc == 0
    run = subprocess.run(
        ["node", str(HARNESS), str(out)],
        capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _args(pack: Path, out: Path):
    import argparse
    return argparse.Namespace(
        pack=str(pack), out=str(out), pool=0,
        with_bundle=False, from_live=None)


def _log(fight):
    return {k: v for k, v in fight["log"]}


def _by_id(snapshot):
    return {e["id"]: e for e in snapshot["enemies"]}


def test_the_fight_starts_where_the_fixture_says(fight):
    log = _log(fight)
    start = log["start"]
    assert start["region"] == "town"
    assert start["hero"] == {"hp": 3, "max": 3, "atk": 2, "at": [1, 1]}
    assert start["gold"] == 5
    assert log["hp-line0"] == "3/3"
    # A world that trades shows the purse in words, beside the health bar.
    assert log["gold-line0"] == "5 gold"
    assert log["gold-line0-hidden"] is False
    rat = _by_id(start)["cellar-rat"]
    assert rat == {"id": "cellar-rat", "at": [2, 1], "hp": 4, "atk": 1,
                   "sight": 6, "alive": True, "yields": False}
    pale = _by_id(start)["pale-thing"]
    assert pale["at"] == [7, 1] and pale["atk"] == 2 and pale["sight"] == 6


def test_a_bump_attacks_and_the_answer_lands(fight):
    log = _log(fight)
    after = log["after-bump1"]
    # The hero did not move; the rat lost 2 hp and hit back for 1.
    assert after["hero"]["hp"] == 2
    assert after["hero"]["at"] == [1, 1]
    rat = _by_id(after)["cellar-rat"]
    assert rat["hp"] == 2 and rat["alive"] is True
    assert log["said-bump1"] == "a cellar rat hits you for 1."
    assert log["hp-line1"] == "2/3"


def test_a_killed_enemy_stays_dead(fight):
    log = _log(fight)
    after = log["after-bump2"]
    rat = _by_id(after)["cellar-rat"]
    assert rat["alive"] is False and rat["hp"] == 0
    assert "a cellar rat falls." in log["said-bump2"]
    slain = json.loads(log["slain-after-kill"])
    assert len(slain) == 1
    assert slain[0].startswith("cellar-rat#")  # id + the monster's signature


def test_an_enemy_in_sight_steps_toward_the_hero(fight):
    log = _log(fight)
    # Six tiles away at the start; one step per hero action, larger axis
    # first. Two hero actions bring it from x=7 to x=5.
    assert _by_id(log["after-bump1"])["pale-thing"]["at"] == [6, 1]
    assert _by_id(log["after-bump2"])["pale-thing"]["at"] == [5, 1]


def test_death_is_cozy_and_the_hero_wakes_whole(fight):
    log = _log(fight)
    after = log["after-death"]
    assert after["region"] == "town"
    assert after["hero"] == {"hp": 3, "max": 3, "atk": 2, "at": [1, 1]}
    assert log["hp-line-death"] == "3/3"
    assert log["said-death"] == DEATH_LINE
    # The fallen rat is still remembered; the other one is whole again.
    assert _by_id(after)["cellar-rat"]["alive"] is False
    assert _by_id(after)["pale-thing"] == {
        "id": "pale-thing", "at": [7, 1], "hp": 4, "atk": 2,
        "sight": 6, "alive": True, "yields": False}


def test_a_kill_leaves_its_drop_on_the_floor(fight):
    log = _log(fight)
    # The rat dies on [2, 1] and leaves its one drop there; the bag is
    # still empty until the hero walks onto it.
    assert log["floor-after-kill"] == [
        {"at": [2, 1], "item": "cloudy-potion", "name": "a cloudy potion"}]
    assert log["bag-after-kill"] == []


def test_walking_onto_a_drop_takes_it(fight):
    log = _log(fight)
    assert log["bag-after-take"] == ["cloudy-potion"]
    assert log["floor-after-take"] == []
    assert log["said-take"] == "You pick up a cloudy potion."
    # The HUD strip appears with one sprite for the one thing carried.
    assert log["strip-hidden-after-take"] is False
    assert log["strip-count-after-take"] == 1


def test_a_chest_gives_its_note_and_its_items(fight):
    log = _log(fight)
    # The chest's note opens in the reader and both items join the bag.
    # The potion is a second copy: the bag is a list, not a set.
    assert log["reader-title"] == "A Cellar Cache"
    assert log["bag-after-chest"] == [
        "cloudy-potion", "cloudy-potion", "brass-ring"]
    assert log["floor-after-chest"] == []
    assert log["said-chest"] == (
        "You take a cloudy potion, a plain brass ring from the chest.")
    # The Bag panel draws one row per carried thing.
    assert log["bag-panel-rows"] == 3
    assert log["bag-panel-count"] == "3 things carried."


def test_a_shopkeeper_sells_and_buys_at_his_prices(fight):
    log = _log(fight)
    assert log["trade-open"] is True
    assert log["trade-title"] == "a dusty merchant"
    assert log["trade-gold-open"] == "You carry 5 gold."
    # Sell one potion for its 8 gold: the purse rises, one copy leaves.
    assert log["gold-after-sell"] == 13
    assert log["after-sell"]["gold"] == 13
    assert log["after-sell"]["bag"] == ["cloudy-potion", "brass-ring"]
    assert log["said-sell"] == "You sell a cloudy potion for 8 gold."
    # Buy one back for the same 8: the purse falls, one copy returns.
    assert log["gold-after-buy"] == 5
    assert log["said-buy"] == "You buy a cloudy potion for 8 gold."
    assert log["bag-after-buy"] == [
        "cloudy-potion", "brass-ring", "cloudy-potion"]
    assert log["trade-closed"] is True


def test_a_potion_heals_but_never_past_the_max(fight):
    log = _log(fight)
    # One blow from the pale thing leaves the hero at 1 of 3.
    assert log["after-blow"]["hero"]["hp"] == 1
    assert log["after-blow"]["hero"]["at"] == [3, 1]
    assert _by_id(log["after-blow"])["pale-thing"]["hp"] == 2
    assert log["bag-gold-line"] == "You carry 5 gold."
    # A 3-heal drink at 1 hp recovers only 2 (the cap) and spends a copy.
    assert log["said-use"] == "You drink a cloudy potion. You recover 2 health."
    assert log["hp-after-use"] == 3
    assert log["after-use"]["hero"]["hp"] == 3
    assert log["after-use"]["bag"] == ["brass-ring", "cloudy-potion"]
    # A second drink at full health says so and keeps the potion.
    assert log["said-use-full"] == (
        "You drink a cloudy potion. You are already whole.")
    assert log["bag-after-use-full"] == ["brass-ring", "cloudy-potion"]
    assert log["after-use-full"]["hero"]["hp"] == 3


def test_no_timers_anywhere(fight):
    assert fight["setIntervalInTemplate"] is False
