"""Spells: schools, learning by level, and books found as loot (ADR 0018).

The engine side of this slice, pinned here:

  * the shape - the two blocks on `shapes.BLOCKS`, and the one key a
    spellbook added to an item;
  * the four refusals, one test each, so a refusal that stops speaking
    takes its own test red with it;
  * level-gating - learning by level is a read of the growth block's own
    level, and its cap does not move;
  * the spellbook grant - deterministic, and a function of the drawn id;
  * the backward-compatibility proof - a pack that names no spells bakes
    the same catalog and drops the same things it always did.

The half a player meets - the Bag panel's Spells section, and casting one
in the real woven file - is `tests/test_spells_play.py`, which needs node.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

from vefr import cli, delve, maplab, shapes

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "web" / "player" / "parts"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_spell_pack as mk  # noqa: E402

# One good `spells` block: two schools, three spells, one of them with no
# `heal` and one above the level table's cap.
GOOD = {
    "schools": ["ember", "tide"],
    "spells": [
        {"id": "ember-bolt", "name": "an ember bolt", "school": "ember",
         "level": 1, "heal": 3},
        {"id": "tide-mend", "name": "a mending tide", "school": "tide",
         "level": 2, "heal": 5},
        {"id": "deep-call", "name": "a deep call", "school": "tide",
         "level": 9},
    ],
}


def _with(**patch):
    """`GOOD` with one top-level key replaced."""
    return {**GOOD, **patch}


def _code(part: Path) -> str:
    """A player part with its `//` comments stripped, so a claim about what
    the code *does* is not satisfied by a sentence about it."""
    lines = []
    for line in part.read_text(encoding='utf-8').splitlines():
        cut = line.find('//')
        lines.append(line if cut < 0 else line[:cut])
    return '\n'.join(lines)


def _one(**patch):
    """The first record of `GOOD` alone, patched - the rest untouched."""
    return [{**GOOD["spells"][0], **patch}] + GOOD["spells"][1:]


def _no_school(**patch):
    """The first record of `GOOD` with the `school` key taken away."""
    first = {k: v for k, v in GOOD["spells"][0].items() if k != 'school'}
    return [{**first, **patch}] + GOOD["spells"][1:]


# --- the shape --------------------------------------------------------------

def test_the_two_blocks_are_registered_and_named():
    assert shapes.BLOCKS["spells"] is shapes.SPELLS
    assert shapes.BLOCKS["spell"] is shapes.SPELL
    assert [k.name for k in shapes.SPELL.keys] == [
        "id", "name", "school", "level", "heal"]


def test_a_good_block_has_no_problems():
    assert shapes.check(shapes.SPELLS, GOOD, at="spells") == []
    assert maplab.spells_errors({"spells": GOOD}) == []
    assert maplab.item_spell_errors(
        "tide-tome", {"name": "a tide-bound tome", "spell": "tide-mend"},
        {"tide-mend"}) == []


def test_a_pack_with_no_spells_block_gets_no_output_at_all():
    """The additive half: no `spells` key is silence, not an empty block."""
    assert maplab.spells_errors({}) == []
    assert maplab.spells_errors({"name": "a pack"}) == []
    assert maplab.spells_learnable_at({}, 9) == []
    assert maplab.growth_level_cap({}) == 0
    # An item with no `spell` passes the new check exactly as it passed
    # the old ones.
    assert maplab.item_spell_errors("torch", {"name": "a pitch torch"}, set()) == []


def test_the_spell_key_is_an_items_key_and_a_later_slice_does_not_rewrite():
    """`ITEM_ADDED` is ADR 0017's record and stays exactly that; the spell
    key sits beside it, and `check_item` reads both."""
    assert shapes.ITEM_ADDED == ("rarity", "traits", "roll")
    assert shapes.ITEM_TAUGHT == ("spell",)
    assert shapes.check_item({"name": "a tide-bound tome",
                              "spell": "tide-mend"}) == []
    assert shapes.check_item({"name": "a tide-bound tome"}) == []
    # The nine keys ADR 0017 left alone are still left alone.
    assert shapes.check_item({"name": "a bit of junk", "value": 0,
                              "heal": "lots", "use": "  ", "luck": 3}) == []


# --- the four refusals ------------------------------------------------------

def test_a_spell_naming_a_school_the_pack_does_not_declare_is_named():
    """Refusal one: a school is a name the pack chose, so the block's own
    list is the only thing a spell can belong to."""
    assert maplab.spells_errors({"spells": _with(
        spells=_one(school="frost"))}) == [
        "spell 'ember-bolt' must name a school the pack declares, and "
        "'frost' is not one; the pack declares ember and tide"]
    # A school the pack did not declare is the whole refusal, whichever
    # spell named it.
    assert maplab.spells_errors({"spells": _with(
        schools=["ember"], spells=_one(school="tide"))}) == [
        "spell 'ember-bolt' must name a school the pack declares, and "
        "'tide' is not one; the pack declares ember",
        "spell 'tide-mend' must name a school the pack declares, and "
        "'tide' is not one; the pack declares ember",
        "spell 'deep-call' must name a school the pack declares, and "
        "'tide' is not one; the pack declares ember"]
    # A pack that declares no school at all says so in the same sentence.
    assert maplab.spells_errors({"spells": _with(schools=[])}) == [
        "spell 'ember-bolt' must name a school the pack declares, and "
        "'ember' is not one; the pack declares no schools at all",
        "spell 'tide-mend' must name a school the pack declares, and "
        "'tide' is not one; the pack declares no schools at all",
        "spell 'deep-call' must name a school the pack declares, and "
        "'tide' is not one; the pack declares no schools at all"]


def test_a_spell_learned_below_level_one_is_named():
    """Refusal two: `level` is a whole number of at least 1, and the table
    says so at the field rather than in a sentence about the spell."""
    assert maplab.spells_errors({"spells": _with(
        spells=_one(level=0))}) == [
            "spells.spells[0].level must be a whole number of at least 1"]
    assert maplab.spells_errors({"spells": _with(
        spells=_one(level=-3))}) == [
            "spells.spells[0].level must be a whole number of at least 1"]
    # A spell with no `level` at all is not a refusal: it waits for a book.
    assert maplab.spells_errors({"spells": _with(
        spells=_one(id="gutter-light"))}) == []


def test_a_spellbook_granting_a_spell_that_does_not_exist_is_named(tmp_path):
    """Refusal three: a book that teaches a spell the pack never wrote
    would teach nothing at all, so the item's own key is named.

    Asserted through `maplab.validate` on a real pack, not only against
    the helper: the refusal is worth nothing unless the sweep that runs
    in `vefr check` actually reaches the item catalog.
    """
    assert maplab.item_spell_errors(
        "tide-tome", {"name": "a tide-bound tome", "spell": "ash-call"},
        {"tide-mend"}) == [
            "item 'a tide-bound tome' (tide-tome) must teach a spell the "
            "pack declares, and 'ash-call' is not one of its spells"]
    # A pack with no spells at all has none the book could name.
    assert maplab.item_spell_errors(
        "tide-tome", {"name": "a tide-bound tome", "spell": "tide-mend"},
        set()) == [
            "item 'a tide-bound tome' (tide-tome) must teach a spell the "
            "pack declares, and 'tide-mend' is not one of its spells"]

    pack = mk.build(tmp_path, spells=mk.SPELLS, growth=mk.LEVELS, xp=3,
                    tome=False)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding='utf-8'))
    world["items"]["tide-tome"] = dict(mk.TOME, spell="ash-call")
    world_json.write_text(json.dumps(world), encoding="utf-8")
    loaded = {**json.loads(world_json.read_text(encoding='utf-8')),
              **maplab.load_pack(pack)}
    assert maplab.validate(loaded, pack) == [
        "item 'a tide-bound tome' (tide-tome) must teach a spell the pack "
        "declares, and 'ash-call' is not one of its spells"]
    # And the pack with the good book beside it is silent.
    good = mk.build(tmp_path, spells=mk.SPELLS, growth=mk.LEVELS, xp=3)
    assert maplab.validate(
        {**json.loads((good / 'world.json').read_text(encoding='utf-8')),
         **maplab.load_pack(good)}, good) == []


def test_a_spell_with_no_school_at_all_is_named():
    """Refusal four: the table's missing-key sentence, said again naming the
    spell and the file it is written in, so a pack with many spells is told
    which one is missing its school and where to look."""
    sentence = ('world.json: spell \'ember-bolt\' must hold a school, such as '
                '{"id": "ember-bolt", "name": "an ember bolt", "school": '
                '"ember", "level": 1, "heal": 3}')
    assert maplab.spells_errors({"spells": _with(
        spells=_no_school())}) == [sentence]
    # One broken record says one thing: the cross-record check leaves it to
    # the shape table rather than adding a second sentence about it.
    assert maplab.spells_errors({"spells": _with(
        schools=["ember"], spells=_no_school())}) == [
            sentence,
            "spell 'tide-mend' must name a school the pack declares, and "
            "'tide' is not one; the pack declares ember",
            "spell 'deep-call' must name a school the pack declares, and "
            "'tide' is not one; the pack declares ember"]
    # A record with no id either is named by its place in the list (the
    # missing id has its own sentence beside it).
    nameless = [{"name": "a nameless spark", "level": 1}]
    assert ("world.json: spell spells.spells[0] must hold a school, such as "
            '{"id": "ember-bolt", "name": "an ember bolt", "school": "ember", '
            '"level": 1, "heal": 3}') in maplab.spells_errors(
                {"spells": _with(spells=nameless)})


def test_a_refused_spell_teaches_nothing_rather_than_half_a_spell():
    """A refusal is a no-op, not a partial grant: a book naming a spell the
    pack does not have bakes the pack's own word, and the player is the
    only one who can decide what to do with it."""
    baked = cli._player_items({"items": {"tome": dict(mk.TOME,
                                                     spell="ash-call")}})
    assert baked["tome"]["spell"] == "ash-call"
    assert maplab.item_spell_errors("tome", {"name": "a tide-bound tome",
                                             "spell": "ash-call"},
                                    {"tide-mend"})


# --- level gating -----------------------------------------------------------

def _leveled_w(**patch):
    """The fixture's own pack shape: three spells, a three-step table."""
    return {"spells": mk.SPELLS, "growth": mk.LEVELS, **patch}


def test_learning_by_level_is_a_read_of_the_growth_blocks_own_level():
    """No second level counter: the cap is the length of the pack's own xp
    table, which is what `growthStats().level` is clamped to in play."""
    assert maplab.growth_level_cap(_leveled_w()) == 3
    assert maplab.growth_level_cap({}) == 0
    assert maplab.growth_level_cap(
        {"growth": {"mode": "practice",
                    "practice": {"atk": {"by": "strikes", "every": 1,
                                         "gain": 1, "cap": 1}}}}) == 0
    assert [r["id"] for r in maplab.spells_learnable_at(_leveled_w(), 1)] == \
        ["ember-bolt"]
    assert [r["id"] for r in maplab.spells_learnable_at(_leveled_w(), 2)] == \
        ["ember-bolt", "tide-mend"]


def test_no_level_reaches_a_spell_written_above_the_cap():
    """The hero's level cap does not move, and this is what that means: a
    spell above the table is simply never learned by level."""
    assert [r["id"] for r in maplab.spells_learnable_at(_leveled_w(), 3)] == \
        ["ember-bolt", "tide-mend"]
    assert [r["id"] for r in maplab.spells_learnable_at(_leveled_w(), 99)] == \
        ["ember-bolt", "tide-mend"]
    assert "deep-call" not in [r["id"] for r in
                               maplab.spells_learnable_at(_leveled_w(), 99)]


def test_a_pack_with_no_growth_block_learns_no_spell_by_level():
    """No growth block, no level, no level-learned spell - and a practice
    pack is the same answer, because practice keeps no level to read."""
    assert maplab.spells_learnable_at({"spells": mk.SPELLS}, 9) == []
    practice = {"growth": {"mode": "practice",
                           "practice": {"atk": {"by": "strikes", "every": 1,
                                                "gain": 1, "cap": 1}}}}
    assert maplab.spells_learnable_at(
        {"spells": mk.SPELLS, **practice}, 9) == []


# --- the spellbook grant ----------------------------------------------------

def _fixture_descent(tome_first=True):
    """The rolled fixture's descent block with its Blueprint beside it, and
    a rat that drops the one spellbook this pack has."""
    import make_rolled_pack as rolled
    block = json.loads(json.dumps({
        "descent": {"run_seed": "run-a",
                    "entry": {"region": "town", "at": list(rolled.ENTRY_AT)},
                    "sections": rolled.SECTIONS}}))
    block["descent"]["blueprint"] = json.loads(json.dumps(rolled.BLUEPRINT))
    drops = ["tide-tome", "torch"] if tome_first else ["torch", "tide-tome"]
    for family in block["descent"]["blueprint"]["families"].values():
        family["defaults"]["drops"] = drops
    return block


def test_a_spellbook_is_an_ordinary_item_and_bakes_the_spell_it_grants():
    """The grant rides the item. A spellbook is an entry in `items` like
    any other, and the spell it teaches rides on that entry - so a book
    found on a floor is a drop like every other drop."""
    items = cli._player_items({"items": {"tide-tome": mk.TOME}})
    assert items["tide-tome"] == {"name": "a tide-bound tome", "sprite": "",
                                 "value": 3, "use": "read",
                                 "spell": "tide-mend"}
    # The three id shapes a drop can be are still exactly three: a bare id,
    # and an instance record either way. A book is not a fourth one.
    drops = delve.mob_drops("k", "m0", ["tide-tome", "torch"],
                            {"tide-tome": mk.TOME,
                             "torch": {"name": "a pitch torch"}})
    assert all(isinstance(d, str) or set(d) == {"item", "rarity", "traits",
                                                "identified"} for d in drops)


def test_the_grant_is_deterministic_and_follows_the_drawn_id():
    """The spell a drop teaches is a function of the thing that dropped,
    and the thing that dropped is the draw every other drop already was -
    so there is no second draw and no second stream."""
    catalog = {"tide-tome": mk.TOME, "torch": {"name": "a pitch torch"}}
    descent = _fixture_descent()

    def teaches(item_id):
        taught = catalog.get(item_id, {}).get("spell")
        return taught if taught in {s["id"] for s in mk.SPELLS["spells"]} else ''

    runs = []
    for run in (0, 1, 2):
        for depth in range(1, 13):
            for mob in delve.floor_plan(descent, depth, run, catalog)['mobs']:
                for drop in mob['drops']:
                    runs.append(teaches(drop if isinstance(drop, str)
                                        else drop['item']))
    # The same descent drawn twice is the same sequence of lessons...
    again = []
    for run in (0, 1, 2):
        for depth in range(1, 13):
            for mob in delve.floor_plan(descent, depth, run, catalog)['mobs']:
                for drop in mob['drops']:
                    again.append(teaches(drop if isinstance(drop, str)
                                         else drop['item']))
    assert runs == again
    # ...and at least one floor really does hand over a book.
    assert 'tide-mend' in runs, runs
    # Adding the roll of a book to the catalog cannot move which item a
    # drop chose: the grant is read off the id, so a rolled book teaches
    # the same spell as the bare one.
    rolled = dict(catalog, **{"tide-tome": dict(
        mk.TOME, rarity="rare",
        roll={"rarity": {"rare": 1}, "traits": ["keen"]})})
    for depth in range(1, 13):
        for run in (0, 1, 2):
            for mob in delve.floor_plan(descent, depth, run, rolled)['mobs']:
                for drop in mob['drops']:
                    name = drop if isinstance(drop, str) else drop['item']
                    assert teaches(name) == ('tide-mend'
                                             if name == "tide-tome" else '')


# --- the bake ---------------------------------------------------------------

def test_the_woven_player_carries_the_pack_s_own_words(tmp_path):
    pack = mk.build(tmp_path, spells=mk.SPELLS, growth=mk.LEVELS, xp=3)
    world = {**json.loads((pack / 'world.json').read_text(encoding='utf-8')),
             **maplab.load_pack(pack)}
    assert maplab.validate(world, pack) == []
    html = cli.weave_html(pack)
    spells = json.loads(re.search(r'window\.VEFR_SPELLS = (.*?);\n',
                                  html, re.S).group(1))
    assert spells == mk.SPELLS
    items = json.loads(re.search(r'window\.VEFR_ITEMS = (\{.*?\});',
                                 html, re.S).group(1))
    assert items['tide-tome']['spell'] == 'tide-mend'


def test_a_pack_with_no_spells_bakes_no_line_and_keeps_its_catalog(tmp_path):
    """The backward-compatibility proof: a pack that names no spells
    carries no `VEFR_SPELLS` line at all - the additive rule, so nothing
    new is baked - and `VEFR_ITEMS` is byte for byte the catalog of `main`."""
    pack = tmp_path / "worlds" / "plain"
    plain = mk.build(pack, spells=None, tome=False)
    html = cli.weave_html(plain)
    assert 'window.VEFR_SPELLS =' not in html
    line = re.search(r'window\.VEFR_ITEMS = (\{.*?\});', html, re.S).group(0)
    assert hashlib.sha256(line.encode()).hexdigest() == \
        'e81e8873e4d5cb793ffae1b08f86861399e09eedbee15b9a2db8f52a9d270df5'
    assert 'spell' not in line


def test_the_shipped_sample_world_bakes_the_same_catalog_as_main():
    """The hash the acceptance asks for, on the pack the engine ships.

    `worlds/sample-world` declares no `spells`, so the catalog woven out
    of it is the one woven before ADR 0018. The digest below is the one
    a pristine `main` prints for the same pack.
    """
    html = cli.weave_html(ROOT / "worlds" / "sample-world")
    assert 'window.VEFR_SPELLS =' not in html
    baked = re.search(r'window\.VEFR_ITEMS = (\{.*?\});', html, re.S).group(0)
    assert hashlib.sha256(baked.encode('utf-8')).hexdigest() == \
        'e81e8873e4d5cb793ffae1b08f86861399e09eedbee15b9a2db8f52a9d270df5'


def test_a_pack_with_no_spells_drops_the_bare_ids_it_always_did():
    """And the other half of the proof: the draws are untouched, because a
    spellbook is an item and no draw in this slice is new."""
    descent = _fixture_descent(tome_first=False)
    catalog = {"tide-tome": mk.TOME, "torch": {"name": "a pitch torch"}}
    for run in (0, 1, 2):
        for depth in range(1, 13):
            with_book = delve.floor_plan(descent, depth, run, catalog)
            without = delve.floor_plan(descent, depth, run)
            assert [m['drops'] for m in with_book['mobs']] == \
                [m['drops'] for m in without['mobs']]


# --- the player's own copy --------------------------------------------------

def test_the_player_learns_by_level_from_the_growth_engine_and_by_book():
    """The two halves, read rather than run: the level half is a read of
    `growthStats().level` and the book half is a stored list. Nothing here
    counts levels."""
    code = _code(PARTS / '225-spells.js')
    # The level is read once, and it is read from the growth engine.
    assert code.count('growthStats().level') == 1
    # The learned-by-level half is derived on every read and never stored:
    # the only thing this part writes is the list of books read, under its
    # own key, and it never touches the growth part's storage.
    assert "vefr-spells-" in code
    assert code.count('store.setJSON(') == 1
    assert 'store.setJSON(SPELLS_KEY' in code
    assert 'vefr-growth-' not in code
    # And the growth block was not asked for a second counter.
    growth = _code(PARTS / '220-growth.js')
    assert 'var level' not in growth and 'level +=' not in growth


def test_the_spellbook_lesson_rides_the_use_verb_the_bag_already_had():
    """No second action system: reading a book is `useItem`, the verb a
    potion is already drunk with."""
    gold = (PARTS / '180-gold.js').read_text(encoding='utf-8')
    body = gold[gold.index('function useItem('):]
    body = body[:body.index('\nfunction ') if '\nfunction ' in body else len(body)]
    assert 'def.spell' in body
    assert 'learnSpellFromBook(def.spell)' in body
    # The button appears for a book that has nothing else usable.
    panel = gold[gold.index('function renderBagPanel('):]
    assert 'itemUsable(def)' in panel
    # The usable test is shared with the touch quick slots.
    usable = gold[gold.index('function itemUsable('):]
    usable = usable[:usable.index('\nfunction ')]
    assert "typeof def.spell === 'string'" in usable
