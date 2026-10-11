"""A Section family's `drops` must be an item the pack really has.

On a generated floor a monster carries exactly what its Blueprint family
names: `vefr.delve.mobs_at` draws one id off that family's `drops`, and a
Section names a family by id and carries no record of its own (ADR 0014).
So a family naming an item the pack cannot describe is a monster the
player kills on floor 12 and takes nothing from - and every gate between
the pack and the bag (`cli._drop_ids` at the bake, `placeDrops` in the
player, `bagAdd` in the bag) drops it silently, so nothing anywhere said
so. `vefr check` said `ok:`.

Every fixture is a real pack built the shipped way - `make_mob_drop_pack`
and a real `vefr normalize` for the lock - with a catalog, a Blueprint
whose families carry `drops`, and one `sections/cellar.json` naming them.
Every assertion is on the sentence `vefr check` prints, the sentence AND
the pointer, and on the ids the bake itself keeps, so the check and the
weave agree by construction rather than by two copies of the rule.

Run with:

    bash tests/run.sh tests/test_mob_drops.py
"""

import json

from blueprint_helpers import vefr

import vefr.cli as cli
import vefr.maplab as maplab

import make_mob_drop_pack as mk


def with_drops(family, *drops):
    """The fixture families, with `family`'s defaults carrying `drops`.

    The whole table comes back, because the Section names every family in
    it and one this helper left out would be refused as unknown - a second
    sentence in a test about one bad drop.
    """
    out = {fid: dict(record) for fid, record in mk.FAMILIES.items()}
    base = dict(out[family]["defaults"])
    if drops:
        base["drops"] = list(drops)
    out[family] = {"defaults": base}
    return out


def check(built):
    """The problems `vefr check` reports for a pack, as a list of sentences."""
    return maplab.validate(maplab.load_pack(built), pack_dir=built)


def AT(family="rat", index=0):
    """The pointer and the where every one of these sentences carries."""
    return (f"sections/cellar.json: /families/{index}/family "
            f"section 'cellar' family '{family}'")


def PAYS_NOTHING(family="rat", index=0):
    """Every id dead: the rule's "holds nothing" sentence."""
    return (f"{AT(family, index)}: the family holds nothing - its drops name "
            "no item world.json declares")


def DEAD(item, family="rat", index=0):
    """One dead id beside a live one: named, on its own line."""
    return f"{AT(family, index)}: drop {item!r} is not an item world.json declares"


def NAMES_NO_ITEM(family="rat", index=0):
    """A `drops` line written and empty."""
    return (f"{AT(family, index)}: the family holds nothing - its 'drops' "
            "line names no item")


# ---- the gap, closed ----

def test_a_drop_whose_catalog_entry_has_no_name_is_reported(tmp_path):
    """`blank` is an `items` entry with no `name`, so nothing bakes it.

    `cli._player_items` - the bake's own read - drops an entry that cannot
    be described, and `cli._drop_ids` drops a drop naming a missing item.
    So the rat on every floor of this Section carried `blank`, the player
    killed it, and the bag gained nothing at all. Every tool said `ok:`.
    """
    built = mk.build(tmp_path, families=with_drops("rat", "blank"),
                     items=mk.ITEMS)
    assert check(built) == [PAYS_NOTHING()]


def test_a_drop_the_catalog_never_declared_is_reported(tmp_path):
    """The same refusal one step further out: no entry at all for the id."""
    built = mk.build(tmp_path, families=with_drops("rat", "pebble", "tarn"),
                     items=mk.ITEMS)
    assert check(built) == [DEAD("tarn")]


def test_a_drop_in_a_pack_with_no_catalog_at_all_is_reported(tmp_path):
    """No `items` key anywhere: a pack that promises an item it has none of.

    The catalog is read, not assumed - a pack that declares no catalog
    declares no items, and a drop is a promise the bag cannot keep.
    """
    built = mk.build(tmp_path, families=with_drops("rat", "pebble"),
                     items=None)
    assert check(built) == [PAYS_NOTHING()]


def test_one_bad_drop_in_a_list_that_otherwise_answers_is_reported(tmp_path):
    """The list is mostly real; the one that is not is still the sentence.

    Named at its own place in the order written, and it is the only one
    said: `pebble` is in the catalog and stays. This is the rule the chest
    check has always used, read here rather than written a second time.
    """
    built = mk.build(tmp_path, families=with_drops("rat", "pebble", "ghost"),
                     items=mk.ITEMS)
    assert check(built) == [DEAD("ghost")]


def test_the_second_familys_bad_drop_is_named_at_its_own_entry(tmp_path):
    """The pointer is the Section's family entry, in list order.

    `moth` is families/1, and it is `moth` the sentence names - so an
    author with three families and two wrong drops is told which one.
    """
    families = {"rat": mk.FAMILIES["rat"],
                "moth": {"defaults": dict(mk.FAMILIES["moth"]["defaults"],
                                          drops=["wisp"])}}
    built = mk.build(tmp_path, families=families, items=mk.ITEMS)
    assert check(built) == [PAYS_NOTHING("moth", 1)]


def test_the_front_door_refuses_the_pack(tmp_path):
    """The same pack through `vefr check` itself: exit 1 and the sentence.

    `maplab.validate` is the engine's read; this is the door, run as a
    subprocess so the exit code is the one a CI sees.
    """
    built = mk.build(tmp_path, families=with_drops("rat", "blank"),
                     items=mk.ITEMS)
    rc, out = vefr("check", "--pack", built)
    assert rc == 1
    assert PAYS_NOTHING() in out


# ---- what must stay legal ----

def test_a_drops_line_written_and_empty_is_still_a_refusal(tmp_path):
    """The one shape that is not the same as naming no drops at all.

    `drops: []` is a promise to pay with nothing to pay it with, so it is
    refused; a family that writes no `drops` key is a monster that carries
    nothing and is left alone (the test below). Both are read by the one
    rule the chest book is read by, where an empty `drops:` line is
    likewise refused and an absent one likewise left alone.
    """
    families = with_drops("rat", "pebble")
    families["rat"] = {"defaults": dict(families["rat"]["defaults"],
                                        drops=[])}
    built = mk.build(tmp_path, families=families, items=mk.ITEMS)
    assert check(built) == [NAMES_NO_ITEM()]


def test_a_family_that_names_no_drops_says_nothing(tmp_path):
    """A monster that carries nothing is a legitimate pack.

    The Section that must keep validating: most families on most floors
    are lootless, and a check that refused an absent `drops` would refuse
    every pack in the tree.
    """
    built = mk.build(tmp_path, items=mk.ITEMS)
    assert check(built) == []


def test_drops_the_catalog_answers_all_at_once_say_nothing(tmp_path):
    """Two real ids in one list: kept whole, in the order written."""
    built = mk.build(tmp_path,
                     families=with_drops("rat", "pebble", "blank2"),
                     items={**mk.ITEMS, "blank2": {"name": "a second pebble"}})
    assert check(built) == []


def test_a_drop_written_with_spaces_is_the_drop_the_bake_keeps(tmp_path):
    """`" pebble "` is a real id to the weave, so it is a real id here.

    `cli._drop_ids` strips each part before it asks the catalog, so this is
    the one place the check and the bake could drift; the check strips the
    same way and this pins that it does.
    """
    built = mk.build(tmp_path, families=with_drops("rat", " pebble "),
                     items=mk.ITEMS)
    assert check(built) == []


def test_a_section_with_no_drops_anywhere_is_untouched(tmp_path):
    """The door costs a legal pack nothing: no drops, no sentence."""
    built = mk.build(tmp_path)
    world = json.loads((built / "world.json").read_text(encoding="utf-8"))
    world["items"] = mk.ITEMS
    (built / "world.json").write_text(json.dumps(world), encoding="utf-8")
    assert check(built) == []


# ---- the check and the bake, one rule ----

def test_the_check_keeps_exactly_the_ids_the_bake_keeps(tmp_path):
    """Agreement by construction, on every case above at once.

    `cli._drop_ids` is what the weave runs over the same list; whatever it
    keeps, this check must have accepted, and whatever it throws away the
    check must have named. They are two readings of one catalog, not two
    rules, and this is what holds them to it.
    """
    catalog = cli._player_items({"items": mk.ITEMS})
    cases = [["pebble"], ["blank"], ["tarn"], [], [" pebble "], ["pebble", ""],
             ["pebble", "blank", "tarn"], [7]]
    for drops in cases:
        # a blank id is not an id: `cli._drop_ids` skips it before it
        # asks the catalog, so the check must skip it the same way.
        bad = [str(d).strip() for d in drops
               if str(d).strip() and str(d).strip() not in catalog]
        built = mk.build(tmp_path, families=with_drops("rat", *drops),
                         items=mk.ITEMS)
        said = check(built)
        # Refused exactly when the weave would throw an id away, and named
        # at the first one it throws away. `with_drops` writes no `drops`
        # key at all for an empty case, so `[]` here is the carve-out - a
        # family that carries nothing - and not a written empty line.
        assert bool(said) is bool(bad), drops
        if said:
            assert (f"drop {bad[0]!r} is not an item" in said[0]
                    or "holds nothing" in said[0]), drops


# ---- the shape of the refusal itself ----

def test_the_check_is_skipped_where_there_is_no_catalog_to_read(tmp_path):
    """`shapes.check_section` with no `drops` door skips this one check.

    A caller that has no catalog is not asked to guess at one: the family
    checks it does have (unknown family, missing stat) still run. `shapes`
    may not import `vefr`, so the reading arrives as the callable it takes
    its `resolve` through, and no callable means no drop check.
    """
    from vefr import shapes

    section = dict(mk.SECTION)

    def resolve(fid):
        return {"hp": 3, "atk": 1, "drops": ["tarn"]}

    def refused(sid, family, record):
        return "the family pays nothing"

    assert shapes.check_section(section, None, resolve) == []
    assert shapes.check_section(section, None, resolve, refused) != []


def test_a_family_whose_drops_are_not_a_list_is_not_this_check(tmp_path):
    """The shape of a family's `drops` is the Blueprint's own business.

    The one rule reads the comma-separated form exactly as the chest
    book's front matter is read - same helper, same split - so a family
    that writes a bare string naming a real item is not a new refusal.
    `vefr.delve.mob_drops` reads a list and nothing else, which is the
    Blueprint's business and not this check's.
    """
    built = mk.build(tmp_path,
                     families=with_drops("rat", "pebble") | {
                         "rat": {"defaults": {"hp": 3, "atk": 1,
                                              "drops": "pebble"}}},
                     items=mk.ITEMS)
    assert check(built) == []