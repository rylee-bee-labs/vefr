"""The player's words: one message table, and a pack may speak.

v0 of the player-words contract (vefr #259): every action-critical line
a player has to read in order to act is written once, in the woven
player's message table (`VEFR_PLAYER_WORDS`, part 340), with the
engine's known-good wording as each entry's default. A pack may name
its own word for a key (`world.json`'s `player_words`), and `vefr check`
refuses one that is not a usable word.

Four claims, and what each is pinned by:

1. the two tables agree - the key set is typed once in Python
   (`shapes.PLAYER_WORDS`, which `vefr check` speaks refusals from)
   and once in the player (which holds the wording), and
   `test_the_two_tables_agree` fails if they drift;
2. the wording has one home - `test_the_wording_lives_in_one_place`
   finds every one of the four lines exactly once across
   `web/player/parts/`, inside the table;
3. a pack's own word wins and a bad one is refused -
   `test_a_pack_word_wins` and `test_a_bad_override_is_refused_*`;
4. a pack that names none is never answered about - it validates
   unchanged, bakes no words at all, and reads the engine's own lines.

The JS half runs the REAL table out of web/packaged.html in a node vm
(`tests/fixtures/player_words_harness.mjs`), pinned to literals, and is
skipped where node is absent - this repo's engine tests never require
it. Everything else is plain Python over the shipped source and a
fixture pack woven for real.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from vefr import cli, maplab, shapes

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"
PARTS = ROOT / "web" / "player" / "parts"
PACKAGED = ROOT / "web" / "packaged.html"
HARNESS = Path(__file__).resolve().parent / "fixtures" / "player_words_harness.mjs"

TABLE_START = "// -- player words start --"
TABLE_END = "// -- player words end --"

# The engine's known-good wording, pinned here as literals: these are
# the exact bytes a player read before the table existed (vefr #259's
# "To reach floor-1, go north-west"), and a pack that names no word
# must still read these.
KNOWN_GOOD = {
    "where_next.goal": "To reach {place}.",
    "where_next.reach": "To reach {place}, go {direction}.",
    "where_next.here": "The way to {place} is right here.",
    "where_next.no_way": "No way to {place} is declared from here.",
}


# ---- the tables -----------------------------------------------------

def _js_table() -> dict:
    """The shipped message table, parsed out of the woven player.

    Read from web/packaged.html, not from the part, so the file the
    player actually runs is what is checked. The same hand-extraction
    `tests/test_event_table.py` uses for the `EVENTS` twin.
    """
    src = PACKAGED.read_text(encoding="utf-8")
    start = src.find(TABLE_START)
    end = src.find(TABLE_END)
    assert start != -1 and end != -1 and start < end, "player words markers"
    return dict(re.findall(r"'([\w.]+)':\s*'([^']*)'", src[start:end]))


def test_the_two_tables_agree():
    """The key set is typed once in Python and once in the player.

    Remove either row from `shapes.PLAYER_WORDS` or from the player's
    message table and this fails: the validator would refuse a word for
    a key that can never be read, or the player would speak a word
    nothing can replace. The same drift gate `tests/test_event_table.py`
    keeps for `shapes.EVENTS`.
    """
    assert sorted(k.name for k in shapes.PLAYER_WORDS.keys) == sorted(_js_table())


def test_the_table_holds_the_engine_known_good_wording():
    """Each entry's default is the wording a player already reads."""
    assert _js_table() == KNOWN_GOOD


def test_the_wording_lives_in_one_place():
    """Each of the four lines is written exactly once, in the table.

    This is the evidence half of vefr #259: the strings were built out
    of structure at two call sites, which is how a region id and a
    compass ended up where a place name and an action belong. A call
    site that spelled one out again would put a second home back.
    """
    sources = sorted(PARTS.glob("*.js"))
    for key, text in KNOWN_GOOD.items():
        found = [p.name for p in sources
                 if p.read_text(encoding="utf-8").count(text) == 1]
        assert found == ["340-where-next-hints.js"], (key, found)
        # and it is the table entry, not a stray sentence beside it
        table = _js_table()
        assert table[key] == text


def test_no_part_still_builds_a_hint_out_of_structure():
    """No player part assembles "To reach " + something any more.

    The structural derivation is the bug; reading the hint from the
    table is the fix. This fails if either call site is reverted to
    string concatenation even though the table still exists.
    """
    for part in sorted(PARTS.glob("*.js")):
        text = part.read_text(encoding="utf-8")
        assert "'To reach ' +" not in text, part.name
        assert "'No way to ' +" not in text, part.name
        assert "'The way to ' +" not in text, part.name


# ---- what vefr check says -------------------------------------------

def _errors(words) -> list[str]:
    return maplab.player_words_errors({'player_words': words})


def test_a_pack_that_names_nothing_is_never_answered_about():
    """Silence is not a problem to report, and never a sentence.

    The block is optional and additive, so a pack that declares none
    gets the empty list - not a warning, not a nudge, not a default
    echoed back at it.
    """
    assert maplab.player_words_errors({}) == []
    assert _errors({}) == []


def test_a_pack_word_is_accepted():
    """A usable word - one that names its `{place}` - is good."""
    assert _errors({'where_next.reach': 'To get to {place}, head {direction}.'}) == []
    # Every key on its own, and several at once.
    assert _errors({k: t for k, t in KNOWN_GOOD.items()}) == []


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n", " \t\n "])
def test_an_empty_override_is_refused_with_the_key_named(blank):
    """An empty or whitespace-only word says nothing, and is refused.

    The sentence names the file and the key, so the author knows which
    line of which file to go and write - and never sees a default
    substituted for the word they meant to supply.
    """
    (line,) = _errors({'where_next.reach': blank})
    assert line.startswith('world.json: /player_words/where_next.reach ')
    assert 'must be words a player can read, not blanks' in line


@pytest.mark.parametrize("wrong", [5, None, True, ["To {place}."], {"to": "To {place}."}])
def test_an_override_that_is_not_a_string_is_refused(wrong):
    """A word that is not a word at all is refused, key named."""
    (line,) = _errors({'where_next.reach': wrong})
    assert line.startswith('world.json: /player_words/where_next.reach ')


def test_an_override_naming_no_place_is_refused():
    """A sentence with no `{place}` slot cannot name where to go."""
    (line,) = _errors({'where_next.goal': 'Go that way.'})
    assert line.startswith('world.json: /player_words/where_next.goal ')
    assert 'must name the place as {place}' in line


def test_an_unknown_key_is_refused():
    """A key the message table does not have could never be read."""
    (line,) = _errors({'where_next.sideways': 'To {place}.'})
    assert line.startswith('world.json: /player_words/where_next.sideways ')
    assert 'unknown key' in line


def test_a_block_that_is_not_an_object_is_refused():
    """`player_words` is a table of words, not a word."""
    (line,) = _errors('To reach {place}.')
    assert line.startswith('world.json: /player_words ')
    assert 'must be an object' in line


# ---- a pack that names none -----------------------------------------

def test_the_sample_pack_validates_and_is_never_asked_about():
    """`vefr check` on the shipped pack: clean, and silent about words.

    The pack declares no `player_words`, so the new rule contributes
    nothing to its output - the whole point of an additive block.
    """
    assert 'player_words' not in maplab.load_pack(SAMPLE)
    assert maplab.validate(maplab.load_pack(SAMPLE), pack_dir=SAMPLE) == []


def _pack(tmp_path, words=None) -> Path:
    """A copy of the shipped sample, with the given `player_words`."""
    pack = tmp_path / "a-pack"
    shutil.copytree(SAMPLE, pack)
    if words is not None:
        cfg = json.loads((pack / "world.json").read_text(encoding="utf-8"))
        cfg["player_words"] = words
        (pack / "world.json").write_text(json.dumps(cfg), encoding="utf-8")
    return pack


def _baked_world(html: str) -> dict:
    """The world object the woven file carries on window.VEFR_WORLD."""
    body = re.search(r"window\.VEFR_WORLD = (\{.*\});", html).group(1)
    return json.loads(body)


def test_a_pack_with_no_words_bakes_no_words(tmp_path):
    """The silent pack's woven file holds no words of its own.

    Proof one half: no pack data of this kind is baked anywhere in the
    woven file, so the player can only ever read the engine's own lines.
    The other half - that those lines are the known-good bytes - is
    `test_the_engine_lines_reach_a_player` below.
    """
    pack = _pack(tmp_path)
    assert 'player_words' not in maplab.load_pack(pack)
    html = cli.weave_html(pack)
    assert '"player_words":' not in html
    assert 'player_words' not in _baked_world(html)


def test_a_pack_word_reaches_the_woven_player(tmp_path):
    """A pack that names a word bakes exactly that word, and validates.

    The override rides the world object the weave already bakes, so
    there is no new placeholder and no new bake step to drift.
    """
    words = {'where_next.reach': 'To get to {place}, head {direction}.'}
    pack = _pack(tmp_path, words)
    assert maplab.validate(maplab.load_pack(pack), pack_dir=pack) == []
    html = cli.weave_html(pack)
    assert _baked_world(html)["player_words"] == words
    assert '"player_words":' in html


def test_a_bad_word_is_refused_end_to_end(tmp_path):
    """The refusal `vefr check` prints for a word that is not a word."""
    pack = _pack(tmp_path, {'where_next.reach': ''})
    (line,) = maplab.validate(maplab.load_pack(pack), pack_dir=pack)
    assert line == ('world.json: /player_words/where_next.reach '
                    'player_words.where_next.reach must be words a player '
                    'can read, not blanks')


# ---- the player's own half (node) -----------------------------------

@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node not installed - this repo's engine tests "
                           "never require it")
@pytest.mark.parametrize(
    "case,words",
    [
        # A pack that names none: the exact lines a player read before
        # the table existed, place and direction filled in.
        ('silent', {}),
        # A pack that names its own word for two of the four: those two
        # change, the other two keep the engine's.
        ('override', {
            'where_next.reach': 'To get to {place}, head {direction}.',
            'where_next.goal': 'The way on is {place}.',
        }),
        # Words that are not words: the engine's line stands in rather
        # than a blank one reaching a player who has to act.
        ('unusable', {'where_next.goal': '   ', 'where_next.reach': 5}),
    ],
)
def test_the_engine_lines_reach_a_player(case, words):
    """Run the REAL table out of web/packaged.html and check every line.

    `tests/fixtures/player_words_harness.mjs` pins each expectation
    literally; this only says the block ran and agreed.
    """
    run = subprocess.run(
        ["node", str(HARNESS), str(PACKAGED), case, json.dumps(words)],
        capture_output=True, text=True, timeout=30,
    )
    assert run.returncode == 0, (
        f"player words harness failed:\n{run.stdout}\n{run.stderr}")
    assert json.loads(run.stdout)["ok"] is True