"""Damage types, resistances and burning - the engine half (vefr#497).

Slice 1 of `design/elemental-and-status-effects.md`. Pinned here:

  * the resolver, which is the ONE place a number is changed by a
    resistance, on both damage paths - and the untyped path is the
    identity, because a pack that has not opted in must reach the same
    numbers it always did;
  * the pack contract: `player.resist`, `player.immune`, and a hazard's
    `dmg_type` and `burns`, each refused in one plain sentence;
  * the bake: every one of those four keys rides along ONLY when the
    pack declares it, so a pack that opts out weaves the exact bytes it
    always did;
  * the compatibility proof: the shipped sample pack still weaves to the
    digest `tests/test_skin_validator.py` pins.

The half a player meets - the sentence a blow speaks, the HUD line and
the burn's own turns - is `tests/test_elements_play.py`, which needs node.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from vefr import cli, elements, features, maplab

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_element_pack as mk  # noqa: E402
from test_skin_validator import NO_SKIN_WEAVE_SHA256  # noqa: E402


def errors(pack: Path) -> list[str]:
    return maplab.validate(maplab.load_pack(pack), pack)


def _hero_line(woven: str) -> dict:
    return json.loads(re.search(r"window\.VEFR_HERO = (.*);", woven).group(1))


def _enemies_line(woven: str) -> dict:
    return json.loads(re.search(r"window\.VEFR_ENEMIES = (.*);", woven).group(1))


# ---------------------------------------------------------------- the resolver

def test_an_untyped_blow_is_the_identity():
    """The whole compatibility promise in one line: no type, no change.

    Not clamped, not rounded, not copied - the very object that came in
    is what goes out, which is what every pack that has not opted in
    still depends on."""
    for amount in (0, 1, 2, 7, 100):
        out = elements.after_resist(amount)
        assert out == {"damage": amount, "how": "hit", "type": ""}
    # Even a number the resolver would not have produced itself.
    assert elements.after_resist("3")["damage"] == 3
    assert elements.after_resist(None)["damage"] is None


def test_a_resistance_divides_the_blow_and_says_so():
    """`resist` is a divisor, so the numbers stay whole in two languages."""
    out = elements.after_resist(3, "fire", {"fire": 2}, [])
    assert out == {"damage": 1, "how": "resisted", "type": "fire"}
    # Halving is rounding down, never up: a blow of 1 against a 2 takes 0.
    assert elements.after_resist(1, "fire", {"fire": 2}, [])["damage"] == 0
    # A resistance to another type is no resistance at all.
    assert elements.after_resist(3, "fire", {"cold": 2}, [])["how"] == "hit"


def test_immunity_beats_a_resistance_and_answers_in_words():
    out = elements.after_resist(4, "cold", {"cold": 2}, ["cold"])
    assert out == {"damage": 0, "how": "immune", "type": "cold"}
    # Nothing that is not a damage type is resisted, whatever is declared.
    assert elements.after_resist(4, "fiery", {}, ["fiery"])["how"] == "hit"


def test_the_type_words_are_closed_and_case_sloppy_keys_still_work():
    assert elements.normal_type("  FIRE ") == "fire"
    assert elements.normal_type("fiery") is None
    assert elements.normal_type(None) is None
    # A pack's own reader drops what it cannot use rather than raising:
    # the validator is what refuses, in a sentence an author can act on.
    assert elements.resist_of({"resist": {"fire": 2, "fiery": 2,
                                          "cold": 0, "acid": 99,
                                          "cold ": "x"}}) == {"fire": 2}
    assert elements.immune_of({"immune": ["fire", "fire", "fiery"]}) == ["fire"]
    assert elements.resist_of(None) == {} and elements.immune_of(None) == []


def test_burning_is_read_as_a_duration_and_a_tick():
    assert elements.burning_of({"burns": {"turns": 3, "tick": 1}}) == {
        "effect": "burning", "type": "fire", "turns": 3, "tick": 1}
    # Anything short of both numbers is not a burn at all.
    for bad in ({"turns": 3}, {"tick": 1}, {"turns": 0, "tick": 1},
                {"turns": 1.5, "tick": 1}, "burning", None):
        assert elements.burning_of({"burns": bad}) is None
    assert elements.burning_of({}) is None


# ------------------------------------------------------------------ the pack

def test_the_fixture_pack_is_clean(tmp_path):
    assert errors(mk.build(tmp_path, burns=mk.BURNING)) == []


def test_a_resistance_is_a_damage_type_and_a_whole_number(tmp_path):
    """Every way of writing it wrong, each refused in one sentence."""
    for resist, needle in [
        ({"fiery": 2}, "not a damage type"),
        ({"fire": 0}, "from 1 to 9"),
        ({"fire": 10}, "from 1 to 9"),
        ({"fire": 1.5}, "from 1 to 9"),
        ({"fire": True}, "from 1 to 9"),
        (["fire"], "must be an object"),
    ]:
        found = errors(mk.build(tmp_path, resist=resist, burns=mk.BURNING))
        assert any(needle in e for e in found), (resist, found)


def test_an_immunity_is_a_list_of_damage_types(tmp_path):
    for immune, needle in [
        (["fiery"], "not a damage type"),
        ("fire", "must be a list"),
    ]:
        found = errors(mk.build(tmp_path, immune=immune, burns=mk.BURNING))
        assert any(needle in e for e in found), (immune, found)


def test_a_hazard_names_a_real_damage_type_and_a_real_burn(tmp_path):
    for bad, needle in [
        ({"dmg_type": "fiery"}, "not a damage type"),
        ({"burns": {"turns": 0, "tick": 1}}, "whole turns"),
        ({"burns": {"turns": 2}}, "whole tick"),
        ({"burns": {"turns": 2, "tick": 1, "stack": True}},
         "may only hold turns and tick"),
        ({"burns": "burning"}, "must be an object"),
    ]:
        found = errors(mk.build(tmp_path, **bad))
        assert any(needle in e for e in found), (bad, found)


def test_the_sentence_names_the_hazard_and_its_region(tmp_path):
    """An author is sent to the entry they have to fix, not to the file."""
    found = errors(mk.build(tmp_path, dmg_type="fiery"))
    assert any("an ember hound" in e and "region 'town'" in e for e in found), found


# --------------------------------------------------------------------- the bake

def test_a_pack_that_opts_in_bakes_what_it_named(tmp_path):
    woven = cli.weave_html(mk.build(tmp_path, resist={"fire": 2},
                                    immune=["cold"], burns=mk.BURNING))
    hero = _hero_line(woven)
    assert hero["resist"] == {"fire": 2} and hero["immune"] == ["cold"]
    hound = _enemies_line(woven)["town"][0]
    assert hound["dmg_type"] == "fire"
    assert hound["burns"] == {"effect": "burning", "type": "fire",
                              "turns": 2, "tick": 2}


def test_a_pack_that_opts_out_bakes_none_of_it(tmp_path):
    """The opt-out proof: four keys, none of them on the page."""
    woven = cli.weave_html(mk.build(tmp_path, dmg_type=None, burns=None))
    assert "resist" not in _hero_line(woven) and "immune" not in _hero_line(woven)
    hound = _enemies_line(woven)["town"][0]
    assert "dmg_type" not in hound and "burns" not in hound


def test_the_shipped_sample_pack_still_weaves_to_its_pinned_digest():
    """Nothing here may change a pack that has not opted in.

    The constant is the one `tests/test_skin_validator.py` pins and
    keeps, with the readings that produced it in its own comment."""
    woven = cli.weave_html(SAMPLE)
    assert hashlib.sha256(woven.encode()).hexdigest() == NO_SKIN_WEAVE_SHA256
    hero = _hero_line(woven)
    assert "resist" not in hero and "immune" not in hero


# ------------------------------------------------------------------- detection

def test_the_feature_shelf_can_see_which_packs_opted_in(tmp_path):
    catalog = features.load_catalog()
    assert features.catalog_errors() == []

    def uses(**kw):
        opts = {"burns": mk.BURNING, "name": "element-detect"}
        opts.update(kw)
        pack = mk.build(tmp_path, **opts)
        return [r for r in features.scan_pack(pack, catalog=catalog)
                if r["id"] == "elements"][0]

    assert uses()["used"] is True and "typed hazards" in uses()["detail"]
    plain = uses(dmg_type=None, burns=None)
    assert plain == {"id": "elements", "used": False, "detail": "untyped damage"}
    resisted = mk.build(tmp_path, resist={"fire": 2}, dmg_type=None,
                        burns=None, name="element-detect-resist")
    row = [r for r in features.scan_pack(resisted, catalog=catalog)
           if r["id"] == "elements"][0]
    assert row == {"id": "elements", "used": True, "detail": "resistances"}


@pytest.mark.parametrize("value", ["fiery", "", None])
def test_the_type_table_is_the_design_notes(value):
    """The closed vocabulary is the design note's, spelled the same way."""
    assert elements.is_damage_type(value) is (value in elements.DAMAGE_TYPES)
    assert "burning" in elements.STATUS_EFFECTS