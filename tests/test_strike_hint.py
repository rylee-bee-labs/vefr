"""vefr #464: walking into an enemy is the attack, and the game says so.

The explorers found bump-to-attack by accident - "I only moved, yet the
moths fell" - because nothing in the game ever said the verb was the
step. This pins the fix: one hint, said at the first landed blow, held
to the end of that turn so a monster's counter-blow cannot wipe it off
the line before the player has read it, and never said again.

Four claims, and what each is pinned by:

1. the first fight carries the hint - `test_the_first_fight_says_how_to_strike`;
2. the second fight does not, and the flag is in the player's own
   storage so a reload does not bring it back either -
   `test_the_hint_is_said_once_and_never_again` and
   `test_a_reload_does_not_bring_the_hint_back`;
3. a pack that names its own word for the hint plays that word, and one
   that names none plays the engine's line byte for byte -
   `test_a_pack_may_name_its_own_word_for_the_hint`;
4. the wording is the message table's, and the table and the validator
   agree on it - `tests/test_player_words.py`.

The JS half runs the REAL woven player in jsdom through the shared play
kit, and is skipped where node is absent - this repo's engine tests
never require it. Run with: bash tests/run.sh tests/test_strike_hint.py
"""

import shutil

import pytest

from play_kit import pack, play, weave

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node not installed")

# The engine's own sentence for the hint, byte for byte as the player's
# message table holds it (`VEFR_PLAYER_WORDS` in part 340).
HINT = "Walk into an enemy to strike it."

# The one word a pack's own line replaces it with. A pack that names no
# word never reads this.
PACK_WORD = "Walk into a monster to hit it."

# The fixture's own fight: the hero at [1, 1], a cellar rat at [2, 1]
# with 4 hp, a hero who strikes for 2. One step to the right is a bump,
# not a walk - which is exactly the thing the hint has to teach.
BUMP = "dir:right"

# The flag the hint leaves behind, in the player's own storage, keyed by
# the world's name the way every other `vefr-` save is. The combat
# fixture is the shipped sample world with a fight added, and that
# world's name is `sample-world` (tests/fixtures/make_combat_pack.py
# copies the pack and never renames it).
HINT_KEY = "vefr-strike-hint-sample-world"


def _fight(tmp_path, bumps, patch=None, store=None):
    """Weave the combat fixture, play it, and hand back the last line said."""
    steps = ["begin"]
    for _ in range(bumps):
        steps += [BUMP, "wait:120"]
    steps.append("wait:400")
    html = weave(pack(tmp_path, "combat", patch), tmp_path)
    out = play(html, {"steps": steps, "store": store or {},
                      "read": ["text:#combat-live", "store"]})
    assert out["errors"] == []
    return out


def test_the_first_fight_says_how_to_strike(tmp_path):
    """One bump is the first fight, and the line teaches the verb.

    The hint rides the fight's own line, after the counter-blow: a hint
    on a line of its own is never the line a phone draws, and a line
    said before the monsters take their turn is wiped by them.
    """
    out = _fight(tmp_path, 1)
    line = out["reads"]["text:#combat-live"]
    # The fight is the real one - the rat took the blow and hit back -
    # and the hint is said with it, once.
    assert "a cellar rat hits you for 1." in line
    assert line.endswith(HINT), line


def test_the_hint_is_said_once_and_never_again(tmp_path):
    """The second fight is a fight and nothing more: no hint, no repeat.

    A hint that comes back every fight stops being read. The flag that
    says it was said lives in the player's own storage beside the other
    `vefr-` saves, so a reload does not bring it back either, and Start
    over clears it with the rest.
    """
    out = _fight(tmp_path, 2)
    line = out["reads"]["text:#combat-live"]
    assert "a cellar rat falls." in line
    assert HINT not in line, line
    assert out["reads"]["store"].get(HINT_KEY) == "1", sorted(
        out["reads"]["store"])


def test_a_reload_does_not_bring_the_hint_back(tmp_path):
    """The flag is in storage, so a page opened after the first fight is
    a page that has already been taught.

    The same play with the flag already set - a reload, or a second visit
    - fights exactly the same and says exactly the same, minus the hint.
    """
    out = _fight(tmp_path, 1, store={HINT_KEY: "1"})
    line = out["reads"]["text:#combat-live"]
    assert "a cellar rat hits you for 1." in line
    assert HINT not in line, line


def test_a_pack_may_name_its_own_word_for_the_hint(tmp_path):
    """`player_words` speaks for the hint too: the pack's word, not ours.

    The same block a pack already uses for the four where-next lines,
    and the same rule - a pack that names none plays the engine's line
    byte for byte (`test_the_first_fight_says_how_to_strike`).
    """
    out = _fight(tmp_path, 1, patch={"world.json": {
        "player_words": {"combat.walk_to_strike": PACK_WORD}}})
    line = out["reads"]["text:#combat-live"]
    assert line.endswith(PACK_WORD), line
    assert HINT not in line, line