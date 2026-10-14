"""One name for the interact key: F everywhere (vefr #467).

The player's own first-run hint, the key letter on the Talk button and the
How-to-play panel all advertised E while the big Interact button said F, so
explorers kept trying both to find out which was "right" (vefr#467; seen in
DeepSeek apl-2, runs 002 and 003).

The decision (Rylee, 2026-10-14) is F everywhere. E keeps working as Interact
everywhere, combat included, as an unadvertised alias: nothing on screen and
nothing in a doc names it.

Two halves, one promise:
  - the words: every hint, label and key letter in the player parts (and in
    the generated web/packaged.html) names F, and none names E;
  - the keys: played for real through the shared play kit, E reaches the
    one verb on the same road F does - beside a resident, and with a monster
    next to the hero, where it opens the same fight menu.
"""

import re
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "web" / "player" / "parts"
SHELL = PARTS / "030-shell.html"
TUTORIAL = PARTS / "090-first-run-setup-vs-play.js"
KEYS = PARTS / "510-rules-closure-surfaces.js"
GENERATED = ROOT / "web" / "packaged.html"
PLAYING = ROOT / "docs" / "guides" / "playing.md"
LIBRARY = ROOT / "web" / "library" / "29-one-button.md"

# Every way the player can spell "the interact key is E" on screen or in a
# doc. A new spelling is a new entry here, so the scan grows with the strings.
ADVERTISED = (
    r"<kbd>E</kbd>",
    r"Press E\b",
    r"\(E\)",
    r"`E`",
    r"\bE or F\b",
    r"\bE, F\b",
    r"\bE / F\b",
)


def _sources():
    """Every shipped player source: the parts, plus the generated file."""
    files = sorted(p for p in PARTS.iterdir() if p.is_file())
    return files + [GENERATED]


# ---- the words: F is the only name ----


def test_the_first_run_hint_names_f():
    """The one-time lesson at the foot of the screen says F."""
    assert "'Move with the arrow keys or WASD. Press F to talk.'" in TUTORIAL.read_text(encoding="utf-8")


def test_the_talk_button_carries_an_f():
    """The Talk tool button's key letter and its tooltip both say F."""
    talk = [line for line in SHELL.read_text(encoding="utf-8").splitlines()
            if 'id="talk"' in line]
    assert len(talk) == 1, "the Talk button is not one line any more"
    assert 'title="Talk (F)"' in talk[0]
    assert "<kbd>F</kbd>" in talk[0]


def test_how_to_play_names_f_space_and_enter():
    """Menu > How to play: the Interact keys are F, Space and Enter, and F
    closes a shop."""
    lines = [line for line in SHELL.read_text(encoding="utf-8").splitlines()
             if "<kbd>Space</kbd>" in line and "Interact button" in line]
    assert len(lines) == 1, "the How-to-play Interact line is gone or split"
    line = lines[0]
    for kbd in ("F", "Space", "Enter"):
        assert f"<kbd>{kbd}</kbd>" in line
    assert "close a shop" in line
    # Nothing in the sentence is left spelling the key E.
    assert not re.search(r"\bE\b", re.sub(r"</?(kbd|li|ul)>", "", line))


def test_no_part_and_no_built_player_advertises_e():
    """The whole ship - every part and the generated file - names no E key."""
    bad = []
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        for pattern in ADVERTISED:
            bad += [f"{path.relative_to(ROOT)}: {hit}" for hit in re.findall(pattern, text)]
    assert bad == [], bad


def test_the_keys_still_accept_e_and_f():
    """The keydown handler routes both letters to the one verb, so E is an
    alias on that same path, not a second older one."""
    handler = KEYS.read_text(encoding="utf-8")
    assert "else if (e.key === 'e' || e.key === 'E') doInteract();" in handler
    assert "else if (e.key === 'f' || e.key === 'F') doInteract();" in handler
    # The panels Interact opens are closed by the same two letters.
    both = "e.key === 'e' || e.key === 'E' || e.key === 'f' || e.key === 'F'"
    assert handler.count(both) >= 3


def test_the_docs_name_f():
    """The two docs that spell the key out: the playing guide and the
    library card."""
    playing = PLAYING.read_text(encoding="utf-8")
    assert "| `F`, `Space`, `Enter` | Interact." in playing
    assert "`E`" not in playing
    assert "Press F, Space or Enter" in LIBRARY.read_text(encoding="utf-8")


# ---- the keys: played for real ----

import play_kit  # noqa: E402  (tests/ is on sys.path beside this file)

node_only = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# The fixture's pinned walk to the resident's spot [4, 2] (see
# tests/fixtures/make_interact_pack.py). The hero wakes at [1, 1] with the
# storeroom rat one tile to the right, which is the combat case.
TO_RESIDENT = ["begin", "walk:down,down,right,right,up,right"]
ROW_LABEL = "attr:#verb-row|aria-label"
OPENED = "What to do about a storeroom rat"
FIGHT = "Fight a storeroom rat"


def _play(tmp_path, name, steps, read):
    """Boot the woven interact fixture, run `steps`, read `read` back."""
    home = tmp_path / name
    home.mkdir()
    html = play_kit.weave(play_kit.pack(home, "interact"), home)
    out = play_kit.play(html, {"steps": steps, "read": read})
    assert out["errors"] == [], out["errors"]
    return out["reads"]


def _both_keys(tmp_path, steps, read):
    """The same spec pressed with E and with F, from a fresh boot each."""
    return {k: _play(tmp_path, f"by-{k}", [*steps, f"key:{k}", "wait:300"], read)
            for k in ("e", "f")}


@node_only
def test_e_talks_to_the_resident_exactly_as_f(tmp_path):
    """Beside the porter, E and F open the same speech box: the same
    speaker, the same quiet #near, the same words behind them, and not one
    turn spent either way."""
    read = ["visible:#npc-box", "text:#npc-name", "text:#near",
            "text:#use-hint", "text:#interact-label", "VEFR_COMBAT"]
    reads = _both_keys(tmp_path, TO_RESIDENT, read)
    for k, r in reads.items():
        assert r["visible:#npc-box"] is True, k
        assert r["text:#npc-name"] == "the porter", k
        assert r["text:#near"] == "", k
        assert r["text:#use-hint"] == "Talk to the porter", k
        assert r["text:#interact-label"] == "Talk to the porter", k
        assert r["VEFR_COMBAT"]["hero"] == {"hp": 3, "max": 3, "atk": 2, "at": [4, 2]}, k
    assert reads["e"] == reads["f"]


@node_only
def test_e_opens_the_same_fight_as_f(tmp_path):
    """With the rat one tile away, E names it on the shared verb row exactly
    as F does - combat is not the place the alias stops working - and
    naming it spends no turn."""
    reads = _both_keys(tmp_path, ["begin"],
                       [ROW_LABEL, "text:#use-hint", "text:#interact-label", "VEFR_COMBAT"])
    for k, r in reads.items():
        assert r[ROW_LABEL] == OPENED, k
        assert r["text:#use-hint"] == FIGHT, k
        assert r["text:#interact-label"] == FIGHT, k
        # Naming the rat opens the menu and nothing else: no damage yet,
        # and the monster has not taken its turn.
        assert r["VEFR_COMBAT"]["enemies"][0]["hp"] == 4, k
        assert r["VEFR_COMBAT"]["hero"]["hp"] == 3, k
    assert reads["e"] == reads["f"]