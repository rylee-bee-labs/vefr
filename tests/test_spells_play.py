"""Spells, played in the real woven file (ADR 0018).

The engine side of this slice is pinned in `test_spells.py`: the shape,
the four refusals, level-gating and the backward-compatibility proof.
This file pins the half a player meets - the Bag panel's Spells section,
learning by level, learning from a book found as loot, and casting - in
the shipped player driven through a real DOM, the way
`test_growth_play.py` does, and with reduced motion on: this slice adds no
animation, so every word must be there on the first frame.

Needs node and jsdom; skips without them.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "spell_play_harness.mjs"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_spell_pack as mk  # noqa: E402

# The bag a floor drop of the one book leaves behind, and nothing else.
BAG = [{"id": "tide-tome", "rarity": "", "traits": [], "identified": False}]


def play(tmp_path, steps, bag=BAG, growth=None, **build):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    # The fixture's own defaults, and anything the spec names overrides
    # them - a pack with no spells at all is one call with `spells=None`.
    opts = {"growth": mk.LEVELS, "spells": mk.SPELLS, "xp": 3}
    opts.update(build)
    out = tmp_path / "spell-test.html"
    out.write_text(cli.weave_html(mk.build(tmp_path, **opts)), encoding="utf-8")
    spec = json.dumps({"steps": steps, "bag": bag, "growth": growth})
    run = subprocess.run(["node", str(HARNESS), str(out), spec],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr + run.stdout
    out_json = json.loads(run.stdout)
    assert out_json["errors"] == [], out_json["errors"]
    return out_json


def test_level_one_knows_exactly_the_spells_at_level_one(tmp_path):
    """The gate: level 1 has reached `ember-bolt` and nothing else.

    `tide-mend` is learned at level 2 and `deep-call` at level 9, which is
    above the three-step table the fixture grows by - so at level 1 the
    panel names one spell and holds the other two back.
    """
    out = play(tmp_path, [{"do": "openBag"}, {"do": "snap", "tag": "one"}])
    snap = out["snaps"]["one"]
    assert snap["spellNames"] == ["an ember bolt (ember)"], snap["spellNames"]
    assert snap["castLabels"] == ["Cast an ember bolt"], snap["castLabels"]
    assert snap["books"] is None, snap["books"]
    assert not snap["hidden"]
    assert "Spells" in snap["heading"]


def test_earning_a_level_teaches_the_next_spell(tmp_path):
    """Learning by level is a read of the growth block's own level: three
    xp is one level on this table, and the spell at level 2 is castable
    the moment it lands."""
    out = play(tmp_path, [{"do": "openBag"},
                          {"do": "grow", "xp": 3},
                          {"do": "snap", "tag": "two"}])
    snap = out["snaps"]["two"]
    assert snap["spellNames"] == ["an ember bolt (ember)", "a mending tide (tide)"], \
        snap["spellNames"]
    # Still derived, not stored: only a book is remembered.
    assert snap["books"] is None, snap["books"]


def test_a_book_found_as_loot_teaches_its_spell_and_is_spent(tmp_path):
    """The other way in. The tome is an ordinary item in the bag; using it
    reads it, teaches `tide-mend` at level 1, and spends the copy."""
    out = play(tmp_path, [{"do": "openBag"},
                          {"do": "snap", "tag": "before"},
                          {"do": "read", "item": "tide-tome"},
                          {"do": "snap", "tag": "after"}])
    before, after = out["snaps"]["before"], out["snaps"]["after"]
    assert before["spellNames"] == ["an ember bolt (ember)"], before["spellNames"]
    assert after["spellNames"] == ["an ember bolt (ember)", "a mending tide (tide)"], \
        after["spellNames"]
    # The book is gone from the bag and the lesson is remembered.
    assert "a tide-bound tome" in before["bagNames"]
    assert "a tide-bound tome" not in after["bagNames"]
    assert after["books"] == ["tide-mend"], after["books"]
    assert "You learn a mending tide." in after["live"], after["live"]


def test_casting_heals_and_never_spends_the_hero_on_nothing(tmp_path):
    """The cast is the item `heal` the bag already had, and it keeps the
    potion's rule: whole already means nothing is spent and the line says
    why. `ember-bolt` heals 3 and the hero's base max is 8."""
    out = play(tmp_path, [{"do": "openBag"},
                          {"do": "snap", "tag": "whole"},
                          {"do": "cast", "spell": "ember-bolt"},
                          {"do": "snap", "tag": "already"},
                          {"do": "hurt", "by": 4},
                          {"do": "cast", "spell": "ember-bolt"},
                          {"do": "snap", "tag": "hurt"}])
    whole, already, hurt = (out["snaps"]["whole"], out["snaps"]["already"],
                            out["snaps"]["hurt"])
    assert whole["max"] == 8 and whole["hp"] == 8, whole
    # Already whole: the spell is cast, nothing is gained and nothing is
    # spent - the hero's health is untouched.
    assert "You are already whole." in already["live"], already["live"]
    assert already["hp"] == 8, already
    # Hurt, then cast: the health the spell's own `heal` says it gives.
    assert hurt["hp"] == 7, hurt
    assert "You recover 3 health." in hurt["live"], hurt["live"]
    assert hurt["max"] == 8, hurt


def test_a_pack_with_no_spells_draws_no_spell_section_at_all(tmp_path):
    """The no-op half: the sample world bakes no spells line at all, so
    the Spells section is off the page and nothing is added to the panel."""
    out = play(tmp_path, [{"do": "openBag"}, {"do": "snap", "tag": "plain"}],
               spells=None, tome=False)
    snap = out["snaps"]["plain"]
    assert snap["spellNames"] == []
    assert snap["hidden"] is True
    assert snap["heading"] == ""
    assert "Spells" not in snap["panelText"]