"""Issue #470: the Whisper button is called Listen.

The button read like "whisper to whoever is standing next to you", and every
explorer who pressed it beside the cat believed the cat had summoned the
speaker. It overhears a rumor from anywhere in town, so the player-facing text
says so: the button, its tooltip and the touch label are "Listen (Q)", the
speech box says "You overhear <speaker>", and How to play names it.

The engine keeps its own name for the feature (the `whisper` element ids, the
`bindWhisper`/`composeWhisper` functions, the pool key `rumor:<phase>`): that
name is game-name-neutral and is not the player's.

The labels are read out of the shipped file, `web/packaged.html` (GENERATED
from `web/player/parts/`, see tests/test_player_build.py). The dialog is
played for real in jsdom, which is why that one test skips without node.
"""

import re
import shutil
from pathlib import Path

import pytest

import play_kit

ROOT = Path(__file__).resolve().parents[1]
PLAYER = (ROOT / "web" / "packaged.html").read_text(encoding="utf-8")


def _element(html: str, elem_id: str) -> str:
    """The one button with this id, opening tag and words, as written."""
    m = re.search(r"<button\b[^>]*\bid=\"" + re.escape(elem_id) + r"\"[^>]*>.*?</button>",
                  html, re.DOTALL)
    assert m, f"no <button> with id={elem_id} in the woven player"
    return m.group(0)


def test_the_acts_button_and_its_tooltip_say_listen():
    tag = _element(PLAYER, "whisper")
    assert 'title="Listen (Q)"' in tag, tag
    assert 'data-tip="Listen"' in tag, tag
    assert "<kbd>Q</kbd>" in tag, tag
    # The screen reader reads the word, the key rides beside it.
    assert "<span class=\"sr-only\">Listen</span>" in tag, tag


def test_the_touch_label_says_listen():
    tag = _element(PLAYER, "touch-whisper")
    assert 'aria-label="Listen (Q)"' in tag, tag
    assert "<span>Listen</span>" in tag, tag


def test_how_to_play_names_the_listen_button():
    assert "Hear a rumor with <kbd>Q</kbd> or the Listen button." in PLAYER
    assert "or the Whisper button" not in PLAYER


def test_the_journal_line_stays():
    """The decision keeps this one: the Journal collects whispers, and says so."""
    assert '<button type="button" id="journal-whisper">Listen for a whisper</button>' in PLAYER


def test_the_engine_keeps_its_own_name_for_the_feature():
    """The rename is player-facing text only. The engine's name is neutral and stays."""
    for name in ("function bindWhisper()", "composeWhisper(", "whisperFromFragments()"):
        assert name in PLAYER, name
    assert _element(PLAYER, "whisper").startswith("<button type=\"button\" id=\"whisper\"")


def test_both_rumor_paths_frame_the_dialog_as_overheard():
    """The wiring the played test above drives: the rumor box prints the
    overheard name, and both paths that can produce a rumor pass it - the live
    model and the offline pool/fragments/grammar. The portrait hook still gets
    the speaker itself, or a skin's face would go missing."""
    assert "function overheardName(speaker)" in PLAYER
    assert "'You overhear ' + (speaker || 'someone in town')" in PLAYER
    assert PLAYER.count("overheardName(card.speaker)") == 2
    assert "textContent = shownAs || speaker || ''" in PLAYER


def test_the_dialog_says_the_rumor_was_overheard(tmp_path):
    """Played for real: the button draws a rumor offline, and the speech box
    frames it as something overheard rather than a reply from the cat."""
    if shutil.which("node") is None:
        pytest.skip("node not installed - the jsdom harnesses need it")
    pack = play_kit.pack(tmp_path, "lock")
    woven = play_kit.weave(pack, tmp_path)
    out = play_kit.play(woven, {
        "steps": ["begin", "click:#whisper", "wait:800"],
        "read": ["text:#npc-name", "text:#npc-line", "text:#status"],
    })
    reads = out["reads"]
    name = reads["text:#npc-name"]
    assert name, f"no rumor came back: {reads}"
    assert name.startswith("You overhear "), name
    assert reads["text:#npc-line"].strip('“”" ').strip(), f"an empty line: {reads}"
    assert not out["errors"], out["errors"]