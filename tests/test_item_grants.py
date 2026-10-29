"""Item-granted verbs: what a carried thing hands the hero (E1).

An item may declare `"grants": [{"verb": "mend", "label": "Mend the hull"}]`
and optionally `"changes": {"mend": {"atk": 2}}`. While the thing is carried
(or worn, when it names a `slot`) those verbs sit in the verb row beside the
act's own; when it leaves, they go. Pressing one fires `uses-verb`, the
fourteenth event, so a pack writes what it does the way it writes everything
else it notices.

The play-time half is `tests/browser/test_item_grants.py` (Chromium, and the
published `window.VEFR_VERBS` snapshot). This file is the authoring half:

  * the SHAPE - `shapes.GRANT`, the two keys on `shapes.ITEM`, and that
    `check_item` reads them and nothing else the catalog already accepted;
  * the REFUSALS `vefr check` speaks, one test each, in plain words;
  * the READERS - `item_grants_of` / `item_changes_of` - and that the bake
    carries exactly what they resolved;
  * the BACKWARD COMPATIBILITY PROOF - a catalog written before this slice
    bakes the same bytes, and a pack with no `grants` is a pack whose verb
    row is the act's own.

No story text: every item here is neutral engine-test canon.
"""

from pathlib import Path

from vefr import cli, maplab, shapes

ROOT = Path(__file__).resolve().parents[1]

# The shape of the slice, exactly as a pack writes it.
GOOD = {
    "name": "a caulking mallet",
    "sprite": "mallet",
    "grants": [{"verb": "mend", "label": "Mend the hull"},
               {"verb": "caulk", "label": "Caulk the seam"}],
    "changes": {"mend": {"atk": 2}},
}

# A wearable thing that grants a verb: worn, it is out of the bag, and the
# verb has to stay in the row all the same.
WORN = {
    "name": "a sailor's glove",
    "sprite": "glove",
    "slot": "hand",
    "mods": {"atk": 1},
    "grants": [{"verb": "reef", "label": "Reef the sail"}],
}

# A catalog written before this slice, key for key what `VEFR_ITEMS` must
# still be for it.
PLAIN = {
    "torch": {"name": "a pitch torch", "sprite": "",
              "light": {"radius": 2, "turns": 6}},
    "potion-1": {"name": "a cloudy potion", "sprite": "potion",
                 "value": 4, "heal": 3, "use": "drink"},
    "cloak-1": {"name": "a hooded cloak", "sprite": "cloak",
                "slot": "body", "mods": {"hp": 2}},
    # The silent no-ops an older catalog may carry: a value of 0, a heal
    # that is not a number. Neither is new and neither is refused.
    "junk": {"name": "a bit of junk", "value": 0, "heal": "lots"},
}


# --- the shape ---------------------------------------------------------------

def test_the_grant_block_is_held_and_its_keys_are_registered():
    """The button needs two things: a word to fire under and words to show."""
    assert shapes.BLOCKS["item"] is shapes.ITEM
    keys = [k.name for k in shapes.GRANT.keys]
    assert keys == ["verb", "label"]
    assert all(k.required for k in shapes.GRANT.keys)
    assert shapes.ITEM_GRANTS == ("grants", "changes")
    # The two sit together, right before the keys ADR 0021 added after them.
    names = [k.name for k in shapes.ITEM.keys]
    at = names.index("grants")
    assert names[at:at + 2] == ["grants", "changes"]
    assert names[at + 2:] == list(shapes.ITEM_CASTS)


def test_a_good_item_has_no_problems():
    assert shapes.check_item(GOOD) == []
    assert maplab.item_grants_errors("mallet-1", GOOD,
                                     maplab.pack_verbs({"items": {"mallet-1": GOOD}})) == []


def test_the_shape_reads_only_the_keys_this_slice_added():
    """A catalog written before this slice keeps its silence."""
    for spec in PLAIN.values():
        assert shapes.check_item(spec) == []
        assert maplab.item_grants_errors(spec.get("name", "x"), spec, set()) == []
    # A key the table has never heard of is still the pack's own business.
    assert shapes.check_item({"name": "an odd thing", "luck": 3}) == []


def test_a_grant_of_the_wrong_type_is_named_where_it_was_written():
    """The table speaks about shapes; `check_item` moves the sentence onto
    the entry it belongs to, so a pack author reads one line with its own
    item id in it."""
    problems = shapes.check_item(
        {"name": "a caulking mallet", "grants": [{"verb": "mend"}]},
        at="items.mallet-1")
    assert [p.sentence for p in problems] == [
        'a grant must hold its label, such as {"verb": "mend", '
        '"label": "Mend the hull"}']
    assert [p.pointer for p in problems] == ["/item/grants/0/label"]


def test_grants_that_is_not_a_list_is_named():
    assert [p.sentence for p in shapes.check_item(
        {"name": "a caulking mallet", "grants": {"verb": "mend"}},
        at="items.mallet-1")] == [
        'items.mallet-1.grants must be a list of the verbs this grants, such '
        'as [{"verb": "mend", "label": "Mend the hull"}]']


def test_changes_that_is_not_an_object_is_named():
    assert [p.sentence for p in shapes.check_item(
        {"name": "a caulking mallet", "changes": []},
        at="items.mallet-1")] == [
        'items.mallet-1.changes must be an object naming the verb each '
        'effect is for, such as {"mend": {"atk": 2}}']


# --- the refusals ------------------------------------------------------------

def test_a_verb_granted_twice_is_named():
    """One verb is one button: a second grant of the same word would put two
    buttons on the row that only one of them could ever be pressed."""
    spec = {"name": "a caulking mallet",
            "grants": [{"verb": "mend", "label": "Mend the hull"},
                       {"verb": "mend", "label": "Mend it again"}]}
    assert maplab.item_grants_errors("mallet-1", spec, {"mend"}) == [
        "item 'a caulking mallet' (mallet-1) grants the verb 'mend' more "
        "than once: the verb row would show two buttons with the same word"]


def test_a_change_for_a_verb_this_pack_has_not_is_named():
    """A verb is the act's own or one an item grants - never a word only
    this item made up, which nothing could ever fire."""
    spec = {"name": "a caulking mallet", "changes": {"polish": {"atk": 1}}}
    assert maplab.item_grants_errors("mallet-1", spec, {"mend"}) == [
        "item 'a caulking mallet' (mallet-1) changes the verb 'polish', "
        "which is not a verb this pack uses: a verb is one of the act's "
        "own, or one this item grants"]


def test_a_change_that_is_not_an_object_is_named():
    spec = {"name": "a caulking mallet", "changes": {"mend": 2}}
    assert maplab.item_grants_errors("mallet-1", spec, {"mend"}) == [
        "item 'a caulking mallet' (mallet-1) change for the verb 'mend' "
        "must be an object holding atk"]


def test_an_effect_this_slice_does_not_play_is_named():
    assert maplab.item_grants_errors(
        "mallet-1", {"name": "a caulking mallet",
                     "changes": {"mend": {"hp": 2}}}, {"mend"}) == [
        "item 'a caulking mallet' (mallet-1) change for the verb 'mend' "
        "may only hold atk, not 'hp'"]


def test_an_effect_outside_its_own_bounds_is_named():
    assert maplab.item_grants_errors(
        "mallet-1", {"name": "a caulking mallet",
                     "changes": {"mend": {"atk": 12}}}, {"mend"}) == [
        "item 'a caulking mallet' (mallet-1) change atk for the verb "
        "'mend' must be a whole number 0 to 9"]
    # A bool is not a whole number here, and true is not one atk.
    assert maplab.item_grants_errors(
        "mallet-1", {"name": "a caulking mallet",
                     "changes": {"mend": {"atk": True}}}, {"mend"})


def test_one_item_says_every_problem_it_has():
    """One sentence each, in the order the pack wrote them."""
    spec = {"name": "a caulking mallet",
            "changes": {"polish": {"atk": 1}, "mend": {"atk": 99}}}
    assert maplab.item_grants_errors("mallet-1", spec, {"mend"}) == [
        "item 'a caulking mallet' (mallet-1) changes the verb 'polish', "
        "which is not a verb this pack uses: a verb is one of the act's "
        "own, or one this item grants",
        "item 'a caulking mallet' (mallet-1) change atk for the verb "
        "'mend' must be a whole number 0 to 9"]


# --- the readers and the bake ------------------------------------------------

def test_the_bake_carries_exactly_what_the_readers_resolved():
    """One reader each, so the pack's words and the player's row cannot
    become two different verbs."""
    assert maplab.item_grants_of(GOOD) == [
        {"verb": "mend", "label": "Mend the hull"},
        {"verb": "caulk", "label": "Caulk the seam"}]
    assert maplab.item_changes_of(GOOD) == {"mend": {"atk": 2}}
    baked = cli._player_items({"items": {"mallet-1": GOOD}})["mallet-1"]
    assert baked["grants"] == maplab.item_grants_of(GOOD)
    assert baked["changes"] == maplab.item_changes_of(GOOD)


def test_a_pack_whose_items_grant_nothing_bakes_no_grants():
    """Nothing broken rides along: a grant with no words, a change with no
    number, and a `changes` that is not an object are all dropped rather
    than baked as a button or an effect nothing can use."""
    spec = {"name": "an odd thing",
            "grants": ["mend", {"verb": "mend"}, {"label": "Mend"},
                       {"verb": "", "label": "Mend"},
                       {"verb": "two words", "label": "Mend"}],
            "changes": {"mend": {"atk": "two"}, "caulk": 2, "reef": {"hp": 1}}}
    assert maplab.item_grants_of(spec) == []
    assert maplab.item_changes_of(spec) == {}
    baked = cli._player_items({"items": {"odd": spec}})["odd"]
    assert "grants" not in baked and "changes" not in baked


def test_a_pack_with_no_grants_bakes_its_catalog_byte_for_byte():
    """The backward-compatibility proof: a catalog written before this slice
    is the catalog this slice bakes, key for key and value for value."""
    assert cli._player_items({"items": PLAIN}) == {
        "torch": {"name": "a pitch torch", "sprite": "",
                  "light": {"radius": 2, "turns": 6}},
        "potion-1": {"name": "a cloudy potion", "sprite": "potion",
                     "value": 4, "heal": 3, "use": "drink"},
        "cloak-1": {"name": "a hooded cloak", "sprite": "cloak",
                    "slot": "body", "mods": {"hp": 2}},
        "junk": {"name": "a bit of junk", "sprite": ""},
    }


def test_a_worn_thing_keeps_its_grant_and_its_slot():
    """Both ride on one record: the slot makes it wearable, the grants make
    it a verb, and neither is a reason to refuse the other."""
    baked = cli._player_items({"items": {"glove-1": WORN}})["glove-1"]
    assert baked["slot"] == "hand" and baked["mods"] == {"atk": 1}
    assert baked["grants"] == [{"verb": "reef", "label": "Reef the sail"}]
    assert shapes.check_item(WORN) == []


# --- the verbs of the pack ---------------------------------------------------

def test_pack_verbs_is_the_acts_own_and_every_granted_one():
    """What a `uses-verb` rule may name: the row the act already had, and
    the row an item adds. Nothing else, so a rule can never wait on a verb
    the player cannot press."""
    world = {"acts": [{"verbs": ["plate", "flip", "serve"]}],
             "items": {"mallet-1": GOOD, "ring-1": {"name": "a brass ring"}}}
    assert maplab.pack_verbs(world) == {"plate", "flip", "serve", "mend", "caulk"}
    # A pack with no acts and no grants has no verb at all - which is what
    # makes a `uses-verb` rule on it a refusal rather than a rule that
    # silently never fires.
    assert maplab.pack_verbs({"items": {"ring-1": {"name": "a brass ring"}}}) == set()
    assert maplab.pack_verbs({}) == set()
    assert maplab.pack_verbs("not a world") == set()


def test_a_use_verb_rule_may_name_an_acts_verb_or_a_granted_one():
    world = {"acts": [{"verbs": ["plate"]}],
             "items": {"mallet-1": GOOD},
             "flags": {"mended": "the hull was mended", "plated": "a plate landed"},
             "rules": [{"id": "the-mallet-spoke", "when": {"uses-verb": {"verb": "mend"}},
                        "then": [{"set": "mended"}]},
                       {"id": "the-plate-landed", "when": {"uses-verb": {"verb": "plate"}},
                        "then": [{"set": "plated"}]}]}
    assert maplab.rules_errors(world) == []
    # A verb nobody has is refused by name, in the rule author's own words.
    world["rules"].append({"id": "the-ghost-spoke",
                           "when": {"uses-verb": {"verb": "polish"}},
                           "then": [{"set": "polished"}]})
    assert maplab.rules_errors(world) == [
        "rule 'the-ghost-spoke' when 'uses-verb' names unknown verb 'polish'",
        "rule 'the-ghost-spoke' sets flag 'polished', which is not declared "
        "in flags"]


def test_the_player_rules_engine_knows_the_event_too():
    """The JavaScript twin of the table (tests/test_event_table.py is the
    guard; this is the sentence it cannot see - the why-line a fired rule
    leaves behind)."""
    part = (ROOT / "web" / "player" / "parts" / "445-rules-engine.js").read_text(
        encoding="utf-8")
    assert "'uses-verb': { keys: ['verb'], target: 'verb' }" in part
    assert "'the hero used ' + data.verb" in part