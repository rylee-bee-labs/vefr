"""A kill that pays nothing is refused: `vefr check` reads an enemy's `drops`.

The gap this closes, in the engine's own words: an enemy could write a
`drops` line naming items the pack does not declare, `vefr check` stayed
green, and the weave silently dropped every id (`cli._drop_ids`), so the
player killed something and walked away with nothing. The chest side of
this is already refused; an enemy `drops` is the same class one layer out.

Both surfaces are read by one rule, `library._drop_payout_errors`, against
one catalog - what the player will really get, so an `items` entry with no
`name` is no item and a pack with no `items` declares nothing. The three
sentences this file pins are that one rule's, unchanged by which surface
asked.
"""

import sys
from pathlib import Path

import pytest

from vefr import library, maplab

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures"))
from make_empty_drops_pack import build, build_no_catalog  # noqa: E402

DECLARED = {"cloudy-potion", "brass-ring"}
WHERE = "enemy 'a cellar rat' in region 'town'"


def _drop_sentence(enemy=None, declared=DECLARED):
    """`_enemy_drop_errors` for an enemy, absent `drops` line included."""
    if enemy is None:
        enemy = library.NO_DROPS
    return maplab._enemy_drop_errors(WHERE, enemy, declared)


# ---- the rule, one shape at a time ----

def test_a_drops_line_naming_no_id_is_refused():
    """"drops": [] is a claim to pay out that pays nothing."""
    assert _drop_sentence([]) == [
        f"{WHERE}: the kill holds nothing - its 'drops' line names no item"]


def test_blank_ids_are_nothing():
    """A blank id is not an id - the bake drops it and so does the check."""
    for blank in ([""], ["   "], [""], ",", ", ,"):
        assert _drop_sentence(blank), blank


def test_a_list_where_every_id_is_dead_is_the_holds_nothing_sentence():
    """That is the whole truth about it, so it is the whole sentence."""
    assert _drop_sentence(["chalked-map", "chalked-key"]) == [
        f"{WHERE}: the kill holds nothing - its drops name no item "
        "world.json declares"]


def test_a_dead_id_beside_a_live_one_is_named():
    """Not "holds nothing" - the kill pays one, and the other is a lie."""
    assert _drop_sentence(["cloudy-potion", "chalked-map", "brass-rung"]) == [
        f"{WHERE}: drop 'chalked-map' is not an item world.json declares",
        f"{WHERE}: drop 'brass-rung' is not an item world.json declares",
    ]


def test_the_sentence_names_the_enemy_and_the_reason():
    """"one sentence naming the enemy and why the kill pays nothing"."""
    (sentence,) = _drop_sentence(["chalked-map"])
    assert "a cellar rat" in sentence
    assert "region 'town'" in sentence
    assert "holds nothing" in sentence


def test_one_bad_id_beside_one_that_answers_is_still_refused():
    """The rule the chest check has always used, now the enemy's too.

    The list this came in with let a typo through whenever anything else
    in the list answered, which is the same silent no-payout the check
    exists to refuse - the kill still hands over an id the author wrote
    and the bake will drop.
    """
    assert _drop_sentence(["cloudy-potion", "chalked-map"])


def test_an_enemy_that_writes_no_drops_is_allowed():
    """A monster that carries nothing is a legitimate monster."""
    assert _drop_sentence() == []


def test_an_enemy_that_writes_only_real_ids_is_allowed():
    assert _drop_sentence(["cloudy-potion"]) == []


def test_the_pack_with_no_catalog_declares_nothing():
    """No `items` at all: every drop check runs and every drop fails."""
    (sentence,) = _drop_sentence(["cloudy-potion"], frozenset())
    assert sentence == (f"{WHERE}: the kill holds nothing - its drops name no "
                        "item world.json declares")
    assert _drop_sentence(["cloudy-potion"], frozenset())


def test_no_catalog_at_all_is_a_skipped_check_not_a_wrong_one():
    """None means "there was no catalog to read", which is not a refusal."""
    assert _drop_sentence(["cloudy-potion"], None) == []


def test_the_string_form_is_read_the_way_the_bake_reads_it():
    """An enemy may write the comma-separated form; the bake splits it too."""
    assert _drop_sentence("cloudy-potion") == []
    assert _drop_sentence("brass-ring, cloudy-potion") == []
    assert _drop_sentence("brass-ring, chalked-map") == [
        f"{WHERE}: drop 'chalked-map' is not an item world.json declares"]


def test_an_item_entry_with_no_name_is_not_declared():
    """`cli._player_items` drops a nameless entry, so its ids are not real.

    This is the subtle one: the pack does declare the id, and a check
    reading world.json's `items` keys would wave it through.
    """
    world = {"items": {"cloudy-potion": {"name": "a cloudy potion"},
                       "ghost-thread": {"sprite": "thread"}}}
    declared = library._declared_items(world["items"])
    assert "ghost-thread" not in declared
    assert _drop_sentence(["ghost-thread"], declared)


def test_the_enemy_and_the_chest_read_the_same_rule():
    """Two surfaces, one sentence: the chest says it and so does the rat."""
    book = {"extra": {"chest": "yes", "drops": "chalked-map"}}
    (chest,) = library._chest_drop_errors("library book 'a-note'", book, DECLARED)
    (enemy,) = _drop_sentence(["chalked-map"])
    # past the `where` each names, the two differ only in what holds
    # nothing, which is the surface's own word for the thing.
    assert chest.split(": ", 1)[1].replace("the chest", "@") == \
        enemy.split(": ", 1)[1].replace("the kill", "@")
    assert chest.endswith("its drops name no item world.json declares")


def test_the_chest_carve_out_is_the_whole_class_carve_out():
    """A chest with no `drops` line is left alone, and so is a rat."""
    assert library._chest_drop_errors(
        "library book 'a-note'", {"extra": {"chest": "yes"}}, DECLARED) == []
    assert _drop_sentence() == []


# ---- the same shapes on whole packs, through vefr check ----

@pytest.fixture
def packs(tmp_path):
    return build(tmp_path), build_no_catalog(tmp_path)


def _check(pack):
    return maplab.validate(maplab.load_pack(pack), pack)


def test_vefr_check_names_every_bad_hazard_on_a_pack(packs):
    bad, _ = packs
    sentences = " ".join(_check(bad))
    assert "a cellar rat" in sentences      # a drops line naming no id
    assert "a hollow moth" in sentences     # every id resolves to no item
    assert "a half-paid toll" in sentences  # one dead id beside a live one
    assert "a nameless one" in sentences    # an id under a nameless entry


def test_vefr_check_allows_the_enemy_that_answers(packs):
    bad, _ = packs
    assert "a brass golem" not in " ".join(_check(bad))


def test_vefr_check_refuses_every_drop_on_a_pack_with_no_catalog(packs):
    _, none = packs
    sentences = " ".join(_check(none))
    for who in ("a cellar rat", "a hollow moth", "a half-paid toll",
                "a brass golem", "a nameless one"):
        assert who in sentences, who


def test_the_fixture_pack_raises_nothing_but_its_drop_sentences(packs):
    """A fixture that also failed for another reason would prove nothing."""
    bad, _ = packs
    raised = _check(bad)
    assert raised and all("holds nothing" in e or "is not an item" in e
                          for e in raised), raised