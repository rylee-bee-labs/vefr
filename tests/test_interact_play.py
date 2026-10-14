"""The one-button Interact verb, played for real (interact play protocol).

The interact play harness EXECUTES the woven single-file player against
a stub DOM (jsdom) and plays the interact fixture pack
(tests/fixtures/make_interact_pack.py) end to end: every key the verb
answers to - E, Space, Enter and F - next to the resident, the door,
the chest and the trader; the nothing-in-reach case with full state
snapshots either side, so NOT ONE turn can slip through; the target
ring proved draw-only; and the regression half proving every action
that was reachable before the wiring still works (the Talk button, a
canvas click, the Interact button on chest/trade/door, a bump, and one
arrow press moving exactly one tile). Deterministic: the fixture's
coordinates and the save seed are pinned, so every string and snapshot
here is pinned too.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "interact_play_harness.mjs"
MAKE = ROOT / "tests" / "fixtures" / "make_interact_pack.py"

# The four keys that must all reach doInteract(), under the names the
# harness logs them by.
KEYS = ["e", "space", "enter", "f"]

NUDGE = "Nothing to use here. Walk up to something and try again."
NOTHING_HINT = "Nothing near you to use yet."
# The resident's spliced line, drawn from the pinned save seed (42 +
# the draw counter): E and Space draw the first pair, Enter and F the
# second.
LINE_A = ("Ask me again at dawn, when the lock is warm. "
          "The gate is heavy, but it opens for anyone who knocks.")
LINE_B = ("The gate is heavy, but it opens for anyone who knocks. "
          "Ask me again at dawn, when the lock is warm.")
RESIDENT_LINES = {"e": LINE_A, "space": LINE_A,
                  "enter": LINE_B, "f": LINE_B}


@pytest.fixture(scope="module")
def play(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    home = tmp_path_factory.mktemp("interact-home")
    made = subprocess.run(
        [sys.executable, str(MAKE), str(home)],
        capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    pack = Path(made.stdout.strip())
    out = home / "interact.html"
    rc = cli.cmd_build_web(_args(pack, out))
    assert rc == 0
    run = subprocess.run(
        ["node", str(HARNESS), str(out)],
        capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _args(pack: Path, out: Path):
    import argparse
    return argparse.Namespace(
        pack=str(pack), out=str(out), pool=0,
        with_bundle=False, from_live=None)


def _log(play):
    return {k: v for k, v in play["log"]}


def test_the_harness_played_every_scenario_without_throwing(play):
    """The harness's own tripwire: one thrown error anywhere in the
    walk, the keys, or the regressions lands in the log and fails."""
    assert "HARNESS-ERROR" not in _log(play)


def test_the_woven_player_has_no_timers(play):
    """The fixture's woven file carries no setInterval anywhere - the
    same pin tests/test_combat_loop.py keeps for its player."""
    assert play["setIntervalInTemplate"] is False


def test_the_fixture_wakes_on_the_pinned_tiles(play):
    """The pack wakes the hero at [1, 1] in the town with the fixture's
    numbers, and the rat sleeps one tile to the right - and with
    nothing else in reach, the first words are the fight label."""
    log = _log(play)
    assert log["start-region"] == "town"
    assert log["start-hero"] == {"hp": 3, "max": 3, "atk": 2, "at": [1, 1]}
    assert log["start-gold"] == 5
    assert log["start-rat"] == {"id": "storeroom-rat", "at": [2, 1],
                                "hp": 4, "atk": 1, "sight": 0, "alive": True,
                                "yields": False}
    assert log["start-hint"] == "Fight a storeroom rat"
    assert log["start-label"] == "Fight a storeroom rat"


def test_the_words_next_to_the_resident(play):
    """Standing on the resident's pinned spot [4, 2], all four keys see
    the same words: hint and button both say who you would talk to,
    and the button is neither hidden nor disabled."""
    log = _log(play)
    assert log["resident-spot"] == [4, 2]
    for k in KEYS:
        assert log[f"resident-{k}-hint"] == "Talk to the porter", k
        assert log[f"resident-{k}-label"] == "Talk to the porter", k
        assert log[f"resident-{k}-interact-hidden"] is False, k
        assert log[f"resident-{k}-interact-disabled"] is False, k


def test_e_space_enter_and_f_each_talk_to_the_resident(play):
    """Each of the four keys runs the talk path: the speech box opens
    (hidden False), the box names the porter, the note says where the
    line came from, #near stays clear, the words after the press still
    name the resident, and not one turn passed."""
    log = _log(play)
    for k in KEYS:
        assert log[f"resident-{k}-box-hidden"] is False, k
        assert log[f"resident-{k}-name"] == "the porter", k
        assert log[f"resident-{k}-line"] == RESIDENT_LINES[k], k
        assert log[f"resident-{k}-note"] == (
            "From this character's own lines."), k
        assert log[f"resident-{k}-near"] == "", k
        assert log[f"resident-{k}-hint-after"] == "Talk to the porter", k
        assert log[f"resident-{k}-label-after"] == "Talk to the porter", k
        # Talking is not a turn: the whole fight state is untouched.
        assert log[f"resident-{k}-snap"] == log[f"resident-{k}-snap-before"], k


def test_the_words_next_to_the_door(play):
    """Standing on the door's pinned spot [9, 4], all four keys see
    'Go through the door' on the hint and on the button, with the
    button always shown and enabled."""
    log = _log(play)
    for k in KEYS:
        assert log[f"door-{k}-spot"] == [9, 4], k
        assert log[f"door-{k}-hint"] == "Go through the door", k
        assert log[f"door-{k}-label"] == "Go through the door", k
        assert log[f"door-{k}-interact-hidden"] is False, k
        assert log[f"door-{k}-interact-disabled"] is False, k


def test_e_space_enter_and_f_each_go_through_the_door(play):
    """Each of the four keys walks through: the snapshot's region
    becomes the cellar, the hero arrives at its pinned [1, 1], and the
    words behind them fall back to the quiet idle state."""
    log = _log(play)
    for k in KEYS:
        assert log[f"door-{k}-region-after"] == "cellar", k
        assert log[f"door-{k}-hero-after"] == [1, 1], k
        assert log[f"door-{k}-hint-after"] == NOTHING_HINT, k
        assert log[f"door-{k}-label-after"] == "Interact", k


def test_the_words_next_to_the_chest(play):
    """Standing on [7, 2], one tile below the chest, all four keys see
    'Open the chest' on the hint and on the button - which stays shown
    and enabled."""
    log = _log(play)
    for k in KEYS:
        assert log[f"chest-{k}-spot"] == [7, 2], k
        assert log[f"chest-{k}-hint"] == "Open the chest", k
        assert log[f"chest-{k}-label"] == "Open the chest", k
        assert log[f"chest-{k}-interact-hidden"] is False, k
        assert log[f"chest-{k}-interact-disabled"] is False, k


def test_e_space_enter_and_f_each_open_the_chest(play):
    """Each of the four keys opens the reader on The Gate Ledger, both
    drops join the bag in order, #near stays clear, and the words after
    the (now empty) chest fall back to the idle state."""
    log = _log(play)
    for k in KEYS:
        assert log[f"chest-{k}-reader-hidden"] is False, k
        assert log[f"chest-{k}-reader-title"] == "The Gate Ledger", k
        assert log[f"chest-{k}-bag"] == ["cloudy-potion", "brass-ring"], k
        assert log[f"chest-{k}-near"] == "", k
        assert log[f"chest-{k}-hint-after"] == NOTHING_HINT, k
        assert log[f"chest-{k}-label-after"] == "Interact", k


def test_the_words_next_to_the_trader(play):
    """Standing on [6, 4], one tile above the trader, all four keys see
    'Trade with the peddler' on the hint and on the button, with the
    button always shown and enabled."""
    log = _log(play)
    assert log["trader-spot"] == [6, 4]
    for k in KEYS:
        assert log[f"trader-{k}-hint"] == "Trade with the peddler", k
        assert log[f"trader-{k}-label"] == "Trade with the peddler", k
        assert log[f"trader-{k}-interact-hidden"] is False, k
        assert log[f"trader-{k}-interact-disabled"] is False, k


def test_e_space_enter_and_f_each_open_the_trade_panel(play):
    """Each of the four keys opens the trade panel on the trader's own
    name, the words after the press still offer the trade, and opening
    a panel spends no turn."""
    log = _log(play)
    for k in KEYS:
        assert log[f"trader-{k}-trade-hidden"] is False, k
        assert log[f"trader-{k}-trade-title"] == "the peddler", k
        assert log[f"trader-{k}-hint-after"] == "Trade with the peddler", k
        assert log[f"trader-{k}-label-after"] == "Trade with the peddler", k
        assert log[f"trader-{k}-snap"] == log[f"trader-{k}-snap-before"], k


def test_the_interact_button_is_never_hidden_or_disabled(play):
    """With nothing in reach (the empty spot) and with a target in
    reach (every full case above), #interact is on screen and
    pressable: hidden False and disabled False every time."""
    log = _log(play)
    assert log["empty-interact-hidden"] is False
    assert log["empty-interact-disabled"] is False
    for target in ("resident", "door", "chest", "trader"):
        for k in KEYS:
            prefix = f"{target}-{k}"
            assert log[f"{prefix}-interact-hidden"] is False, prefix
            assert log[f"{prefix}-interact-disabled"] is False, prefix


def test_nothing_in_reach_says_so_in_plain_words(play):
    """On the empty spot [1, 5] - every pinned candidate far out of
    reach - the hint is the idle line, the button carries its dim
    class, and pressing any of the four keys writes the friendly
    nudge into #near instead of acting."""
    log = _log(play)
    assert log["empty-spot"] == [1, 5]
    assert log["empty-hint"] == NOTHING_HINT
    assert log["empty-label"] == "Interact"
    assert log["empty-dim"] is True
    assert log["empty-near-before"] == ""
    for k in KEYS:
        assert log[f"empty-{k}-near"] == NUDGE, k
        assert log[f"empty-{k}-hint"] == NOTHING_HINT, k
        assert log[f"empty-{k}-label"] == "Interact", k
        assert log[f"empty-{k}-dim"] is True, k


def test_nothing_in_reach_spends_not_one_turn(play):
    """The empty-case proof, per key: full VEFR_COMBAT snapshots after
    every press are byte-equal to the snapshot taken before any press -
    hero tile and hp, the rat's tile and hp, gold, bag and floor all
    unchanged."""
    log = _log(play)
    before = log["empty-e-snap-before"]
    for k in KEYS:
        assert log[f"empty-{k}-snap-before"] == before, k
        assert log[f"empty-{k}-snap"] == before, k
    # The fixture's numbers, while we are here: the rat still sleeps.
    assert before["hero"] == {"hp": 3, "max": 3, "atk": 2, "at": [1, 5]}
    assert before["enemies"][0]["at"] == [2, 1]
    assert before["enemies"][0]["hp"] == 4
    assert before["gold"] == 5
    assert before["bag"] == []
    assert before["floor"] == []


def test_the_target_ring_draws_with_a_target_and_moves_nothing(play):
    """Forced one draw() with a target in reach (a window resize makes
    the player redraw): the stub canvas saw strokes in the ring's own
    gold - the player did not throw - and the snapshots either side of
    the draw are equal, so drawing the ring changes no game state.
    jsdom has no real canvas, so the ring is proven DRAW-ONLY, not
    pixels: that is the ceiling of what this harness can prove."""
    log = _log(play)
    assert log["resident-ring-strokes"] >= 1
    assert log["resident-ring-before"] == log["resident-ring-after"]


def test_the_target_ring_stays_away_when_nothing_is_in_reach(play):
    """The same forced draw with nothing in reach strokes the ring's
    gold zero times (pickTarget is null, drawTargetRing returns early)
    and again changes nothing."""
    log = _log(play)
    assert log["empty-ring-strokes"] == 0
    assert log["empty-ring-before"] == log["empty-ring-after"]


# ---- the regression half: every action reachable BEFORE the wiring ----


def test_regression_the_talk_button_still_talks(play):
    """The old Talk button takes the same nearest-speaker road: pressed
    on the resident's spot, the speech box opens and names the porter,
    with nothing nagging in #near."""
    log = _log(play)
    assert log["talkbtn-box-hidden"] is False
    assert log["talkbtn-name"] == "the porter"
    assert log["talkbtn-near"] == ""


def test_regression_a_canvas_click_still_talks(play):
    """canvas.addEventListener('click', tryNPC) survived the wiring: a
    click on the town canvas still opens the speech box on the nearest
    resident."""
    log = _log(play)
    assert log["canvas-box-hidden"] is False
    assert log["canvas-name"] == "the porter"
    assert log["canvas-near"] == ""


def test_regression_the_interact_button_still_opens_a_chest(play):
    """Clicking #interact itself (not a key) on the chest spot opens
    the reader on The Gate Ledger and gives both drops."""
    log = _log(play)
    assert log["intchest-hint"] == "Open the chest"
    assert log["intchest-label"] == "Open the chest"
    assert log["intchest-reader-hidden"] is False
    assert log["intchest-reader-title"] == "The Gate Ledger"
    assert log["intchest-bag"] == ["cloudy-potion", "brass-ring"]


def test_regression_the_interact_button_still_opens_trade(play):
    """Clicking #interact itself on the trader spot still opens the
    trade panel on the trader's name."""
    log = _log(play)
    assert log["inttrade-hint"] == "Trade with the peddler"
    assert log["inttrade-label"] == "Trade with the peddler"
    assert log["inttrade-trade-hidden"] is False
    assert log["inttrade-trade-title"] == "the peddler"


def test_regression_the_interact_button_still_goes_through_a_door(play):
    """Clicking #interact itself on the door spot still swaps the
    region to the cellar at its pinned arrival tile."""
    log = _log(play)
    assert log["intdoor-hint"] == "Go through the door"
    assert log["intdoor-label"] == "Go through the door"
    assert log["intdoor-region-after"] == "cellar"
    assert log["intdoor-hero-after"] == [1, 1]


def test_regression_a_bump_still_strikes_and_the_enemy_answers(play):
    """One arrow key walked into the rat: the hero does not move, the
    rat loses the hero's atk (4 -> 2), and the enemy takes its turn and
    hits back (hero 3 -> 2), saying so in the live line."""
    log = _log(play)
    before, after = log["bump-before"], log["bump-after"]
    assert before["hero"]["at"] == [1, 1]
    assert after["hero"]["at"] == [1, 1]          # bumped, not moved
    assert after["hero"]["hp"] == before["hero"]["hp"] - 1
    rat_before = before["enemies"][0]
    rat_after = after["enemies"][0]
    assert rat_after["hp"] == rat_before["hp"] - before["hero"]["atk"]
    assert rat_after["alive"] is True
    # The first fight of this boot carries the one-time strike hint
    # (vefr #464) after the rat's own line.
    assert log["bump-said"] == (
        "a storeroom rat hits you for 1. Walk into an enemy to strike it.")


def test_regression_one_arrow_press_moves_exactly_one_tile(play):
    """One ArrowDown press, read from the player's own snapshot: the
    hero goes [1, 1] -> [1, 2] - exactly one tile, and the sleeping rat
    is untouched."""
    log = _log(play)
    before, after = log["arrow-before"], log["arrow-after"]
    assert before["hero"]["at"] == [1, 1]
    assert after["hero"]["at"] == [1, 2]
    assert after["enemies"][0] == before["enemies"][0]
    assert after["gold"] == before["gold"]
    assert after["bag"] == before["bag"]


# ---- Task 3: combat folds into the one verb ----


def test_interact_on_an_enemy_names_it_and_opens_the_verbs(play):
    """Facing the rat at the wake tile, the words already offer the
    fight; pressing E names the rat on the shared #verb-row and leaves
    the fight untouched until a verb is chosen - opening is not a turn."""
    log = _log(play)
    assert log["enemy-start-hint"] == "Fight a storeroom rat"
    assert log["enemy-start-label"] == "Fight a storeroom rat"
    assert log["enemy-start-row-label"] == "Combat actions"
    assert log["enemy-open-row-label"] == "What to do about a storeroom rat"
    assert log["enemy-verbs"] == ["Strike", "Console", "Hurl an insult"]
    # Each verb prints the digit that presses it (#463); the label is
    # read from its own word, so the shortcut is not part of the name.
    assert log["enemy-verb-keys"] == ["1", "2", "3"]
    assert log["enemy-open-snap"] == log["enemy-open-snap-before"]


def test_strike_from_the_enemy_menu_hurts_it_and_the_enemy_answers(play):
    """Clicking Strike in the menu is a bump by another road: the rat
    loses the hero's atk (4 -> 2), the menu clears back to its own
    label, and the rat still takes its turn (hero 3 -> 2)."""
    log = _log(play)
    before = log["enemy-open-snap-before"]
    after = log["enemy-strike-snap"]
    assert after["enemies"][0]["hp"] == (
        before["enemies"][0]["hp"] - before["hero"]["atk"])
    assert after["enemies"][0]["alive"] is True
    assert after["hero"]["hp"] == before["hero"]["hp"] - 1
    assert log["enemy-strike-row-label"] == "Combat actions"
    # This boot's first fight, so the strike hint rides the line here
    # too - a strike from the menu is the same strike as a bump.
    assert log["enemy-strike-said"] == (
        "a storeroom rat hits you for 1. Walk into an enemy to strike it.")


def test_console_does_no_damage_but_still_spends_a_turn(play):
    """Console is a non-attack verb: the rat's hp is unchanged, the
    verb is the last one journalled, the menu label clears, and the
    monsters take their turn anyway (hero 2 -> 1). #combat-live ends on
    the enemy's own hit line, because the turn resolves after the verb
    says its piece - so the sentence is proven by the journal, not the
    overwritten live line."""
    log = _log(play)
    struck = log["enemy-strike-snap"]
    after = log["enemy-console-snap"]
    assert after["enemies"][0]["hp"] == struck["enemies"][0]["hp"]
    assert after["hero"]["hp"] == struck["hero"]["hp"] - 1
    assert log["enemy-console-verb"] == "console"
    assert log["enemy-console-row-label"] == "Combat actions"
    assert log["enemy-console-said"] == "a storeroom rat hits you for 1."


def test_a_one_verb_surface_acts_at_once_with_no_menu(play):
    """An act whose verbs name exactly one verb: E applies it straight
    away - the shared row keeps its own label (no menu opened), the
    verb is journalled, and the turn still runs (the rat hits back)."""
    log = _log(play)
    assert log["oneverb-row-label"] == "Combat actions"
    assert log["oneverb-verb"] == "console"
    assert log["oneverb-snap"]["enemies"][0]["hp"] == log["oneverb-start-rat"]
    assert log["oneverb-snap"]["hero"]["hp"] == log["oneverb-start-hp"] - 1


def test_bumping_closes_an_open_enemy_menu_and_still_strikes(play):
    """With the enemy menu open, walking into the rat still bumps and
    clears the menu label in the same step; the rat loses the hero's
    atk (4 -> 2) and answers (hero 3 -> 2)."""
    log = _log(play)
    assert log["bumpclose-open-row-label"] == "What to do about a storeroom rat"
    assert log["bumpclose-row-label"] == "Combat actions"
    assert log["bumpclose-snap"]["enemies"][0]["hp"] == 2
    assert log["bumpclose-snap"]["hero"]["hp"] == 2
