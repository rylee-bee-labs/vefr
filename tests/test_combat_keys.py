"""The fight, played with the keyboard only: the numbers on the combat
buttons, the focus that stays on the one you last used, and one plain
sentence per action in the result line (vefr #463).

Three things a player could not do before this:

  1. after a Strike / Console / Hurl the focus fell on the top of the
     page, so reaching the combat row again cost about eight Tabs, every
     turn;
  2. the combat row answered the mouse only - there was no number to
     press and none was printed;
  3. the result line named the action ("last action: console (dusk)"),
     which says nothing about what Console or an insult did.

The fixture is the interact pack, whose only hazard stands one tile
right of the hero's start with `sight: 0`, so `E` always opens the
enemy's verbs and the monster never steps anywhere on its own: the
hero's atk (2), the rat's hp (4) and its answer (1) are pinned numbers,
and every run below is one fight action from the same opening
position. The player is the REAL woven one in jsdom - nothing is
stubbed but the canvas.

Run with:

    bash tests/run.sh tests/test_combat_keys.py
"""

import json
import shutil

import pytest

from play_kit import pack, play, weave

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node not installed")

# The combat row's own state, the result line, the live line, and where
# the keyboard focus ended up.
READS = [
    "text:#combat-log",
    "text:#combat-live",
    "text:#verb-row button[data-verb='attack']",
    "text:#verb-row button[data-verb='console']",
    "text:#verb-row button[data-verb='hurl']",
    "focused:#verb-row button[data-verb='attack']",
    "focused:#verb-row button[data-verb='console']",
    "focused:#verb-row button[data-verb='hurl']",
    "VEFR_COMBAT.hero.hp",
    "VEFR_COMBAT.enemies.0.hp",
    "VEFR_COMBAT.enemies.0.alive",
    "store",
]

# The hero at [1, 1], the rat one tile right: `E` names it and opens the
# row. The wait afterwards is the button's own 400 ms disable window, so
# the next run presses a button that is usable again.
OPEN_FIGHT = ["begin", "key:e", "wait:100"]


def fight(tmp_path, steps):
    """Weave the fixture, play it with `steps`, hand back the reads."""
    html = weave(pack(tmp_path, "interact"), tmp_path)
    out = play(html, {"steps": OPEN_FIGHT + steps + ["wait:600"],
                      "read": READS})
    assert out["errors"] == [], out["errors"]
    return out["reads"]


def journalled(reads):
    """The last verb the player journalled, or None for no entry at all."""
    raw = reads["store"].get("vefr-packaged-combat")
    if not raw:
        return None
    return json.loads(raw)[-1]["verb"]


# ---- 1. the numbers are printed on the verbs ------------------------

def test_each_verb_prints_the_number_that_presses_it(tmp_path):
    """The three buttons read Strike 1, Console 2, Hurl an insult 3, so
    the shortcut is on the button instead of in a manual nobody opens.
    The label keeps its own word: the verb is the pack's, the digit is
    a shortcut, and the two are not one name."""
    reads = fight(tmp_path, [])
    assert reads["text:#verb-row button[data-verb='attack']"] == "Strike 1"
    assert reads["text:#verb-row button[data-verb='console']"] == "Console 2"
    assert (reads["text:#verb-row button[data-verb='hurl']"]
            == "Hurl an insult 3")


# ---- 2. the number keys press the verbs ----------------------------

def test_key_1_strikes_the_named_monster(tmp_path):
    """1 is Strike: the rat loses the hero's atk (4 -> 2), the verb is
    the last one journalled, and the turn still runs."""
    reads = fight(tmp_path, ["key:1"])
    assert reads["VEFR_COMBAT.enemies.0.hp"] == 2
    assert reads["VEFR_COMBAT.enemies.0.alive"] is True
    assert reads["VEFR_COMBAT.hero.hp"] == 2, "the rat still hits back"
    assert journalled(reads) == "attack"


def test_key_2_consoles_and_key_3_hurls(tmp_path):
    """2 is Console and 3 is Hurl: neither is a blow, so the rat's hp
    is untouched - but both spend the turn, and both are journalled."""
    reads = fight(tmp_path, ["key:2"])
    assert reads["VEFR_COMBAT.enemies.0.hp"] == 4, "words do no damage"
    assert reads["VEFR_COMBAT.hero.hp"] == 2, "the turn still runs"
    assert journalled(reads) == "console"

    reads = fight(tmp_path, ["key:3"])
    assert reads["VEFR_COMBAT.enemies.0.hp"] == 4, "words do no damage"
    assert reads["VEFR_COMBAT.hero.hp"] == 2, "the turn still runs"
    assert journalled(reads) == "hurl"


# ---- 3. focus stays on the verb that was used ----------------------

def test_focus_stays_on_the_last_verb_used_from_the_number_keys(tmp_path):
    """The keyboard does not have to be re-walked every turn: pressing
    2 leaves the focus on Console, so the next press - 1 or 3 - is the
    next key, not eight Tabs up the page."""
    reads = fight(tmp_path, ["key:2"])
    assert reads["focused:#verb-row button[data-verb='console']"] is True, (
        "the focus fell off the combat row after Console")
    assert reads["focused:#verb-row button[data-verb='hurl']"] is False


def test_focus_stays_on_the_verb_that_was_clicked(tmp_path):
    """The same from a click, because a click is the other way the row
    is used. (In jsdom a click never moves focus by itself, so this
    proves the player puts it back.)"""
    reads = fight(tmp_path, ["click:#verb-row button[data-verb='hurl']"])
    assert journalled(reads) == "hurl"
    assert reads["focused:#verb-row button[data-verb='hurl']"] is True, (
        "the focus fell off the combat row after a click")


def test_focus_stays_after_two_verbs_in_a_row(tmp_path):
    """Two turns in: press 1, then 2 once the button is usable again.
    The focus follows the last verb, not the first."""
    reads = fight(tmp_path, ["key:1", "key:e", "wait:600", "key:2"])
    assert reads["focused:#verb-row button[data-verb='console']"] is True
    assert reads["focused:#verb-row button[data-verb='attack']"] is False


# ---- 4. one plain sentence per action ------------------------------

def test_the_result_line_is_the_sentence_the_verb_said(tmp_path):
    """The line a player reads after each action is the sentence, not the
    name of the action: what Strike, Console and Hurl each did."""
    reads = fight(tmp_path, ["key:1"])
    assert reads["text:#combat-log"] == "You hit a storeroom rat for 2."

    reads = fight(tmp_path, ["key:2"])
    assert reads["text:#combat-log"] == "a storeroom rat quiets a little."

    reads = fight(tmp_path, ["key:3"])
    assert reads["text:#combat-log"] == "a storeroom rat does not care for that."


def test_the_result_line_never_names_the_action(tmp_path):
    """The old line was "last action: console (dusk)": the verb id and the
    phase, saying nothing. Whatever the action, the line now reads as a
    sentence and never as a log entry."""
    for key in ("1", "2", "3"):
        reads = fight(tmp_path, ["key:" + key])
        line = reads["text:#combat-log"]
        assert line, "no result line at all"
        assert "last action:" not in line, line
        assert line.endswith("."), line