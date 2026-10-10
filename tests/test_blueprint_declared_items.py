"""Blueprint: a family `drops` only what the weave will really hand over.

The defect this file pins: `blueprint._declared_items` read the raw `items`
keys, while `cli._player_items` - the catalog `weave` bakes - drops any entry
with no `name`. A Blueprint naming such an id passed its own "unknown item in
drops" check and then paid nothing at play, because the enemy record was
written and the weave then filtered the drop out of it.

The catalog Blueprint compares against is the one `weave` bakes, so the two
cannot drift: `weave_html` calls `blueprint.check_errors(pack)` before it reads
a single byte of the world, and a pack that is not weavable at all is refused
there rather than baked.
"""

import copy
import inspect
import json
import re

import pytest

from blueprint_helpers import mk, vefr
from vefr import blueprint, cli

# The id used for the trap: declared in `items`, but with no `name`.
NAMELESS = "pebble"
ABSENT = "no-such-item"


def src():
    """A fresh copy of STD_BLUEPRINT for a test to edit."""
    return copy.deepcopy(mk.STD_BLUEPRINT)


def one_drop(source, item):
    """The standard pack reduced to a single instance dropping `item`."""
    source["regions"]["act-1/cave-2"]["enemies"] = [
        {"id": "b2", "family": "beetle", "at": [6, 4],
         "properties": {"drops": [item]}},
    ]
    source["regions"]["act-1/cave-3"]["enemies"] = []
    return source


def no_drops(source):
    """The standard pack with every drop taken away."""
    for enemies in source["regions"].values():
        for instance in enemies["enemies"]:
            (instance.get("properties") or {}).pop("drops", None)
            instance.pop("properties", None)
    return source


def build(tmp_path, source, extra_items=None, catalog=True):
    """A pack carrying `source`. `catalog=False` strips `items` from the
    pack world entirely; otherwise the sample catalog stands with
    `extra_items` written into it."""
    pack = mk.build(tmp_path, blueprint=source)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    if catalog:
        world["items"] = dict(world.get("items") or {}, **(extra_items or {}))
    else:
        world.pop("items", None)
    world_json.write_text(json.dumps(world), encoding="utf-8")
    return pack


def refusal(tmp_path, source, extra_items=None, **kw):
    """The BlueprintError one expansion raises, and the pack that raised it."""
    pack = build(tmp_path, source, extra_items, **kw)
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.expand(source, pack_dir=pack)
    return err.value, pack


# --------------------------------------------------------------------------
# The defect: an id the pack declares, in a form the weave drops.


def test_a_drop_naming_an_item_with_no_name_is_refused(tmp_path):
    err, _ = refusal(tmp_path, one_drop(src(), NAMELESS), {NAMELESS: {"sprite": "pebble"}})
    assert "is not one the player can be given" in str(err)
    assert NAMELESS in str(err)
    assert err.pointer == "/regions/act-1~1cave-2/enemies/0/properties/drops"


def test_the_nameless_case_is_the_one_that_used_to_pass(tmp_path):
    """The raw key is in `items`, so the old reader called it declared. Pinned
    as a fact about the fixture, so the trap cannot be quietly rebuilt."""
    pack = build(tmp_path, src(), {NAMELESS: {"sprite": "pebble"}})
    assert NAMELESS in json.loads((pack / "world.json").read_text())["items"]
    assert NAMELESS not in blueprint._declared_items(pack)


def test_a_refused_nameless_drop_leaves_the_pack_alone(tmp_path):
    """A refusal happens before anything is written: `plan` promises that an
    impossible sentence leaves the pack exactly as it was found."""
    source = one_drop(src(), NAMELESS)
    pack = build(tmp_path, source, {NAMELESS: {"sprite": "pebble"}})
    contract = pack / "acts" / "act-1" / "cave-2" / "contract.json"
    before = contract.read_bytes()
    with pytest.raises(blueprint.BlueprintError):
        blueprint.expand(source, pack_dir=pack)
    assert contract.read_bytes() == before
    assert not (pack / "blueprint.lock.json").exists()


def test_the_cli_refuses_it_with_the_sentence_and_exit_one(tmp_path):
    source = one_drop(src(), NAMELESS)
    pack = build(tmp_path, source, {NAMELESS: {"sprite": "pebble"}})
    rc, out = vefr("normalize", "--pack", pack, "--out", pack)
    assert rc == 1
    assert "is not one the player can be given" in out
    assert not (pack / "blueprint.lock.json").exists()


def test_the_nameless_case_is_caught_wherever_the_drop_was_written(tmp_path):
    """A family's own `defaults`, not only an instance's `properties`."""
    source = copy.deepcopy(mk.STD_BLUEPRINT)
    source["families"]["beetle"]["defaults"]["drops"] = [NAMELESS]
    source["regions"]["act-1/cave-2"]["enemies"] = [
        {"id": "b1", "family": "beetle", "at": [3, 4]},
    ]
    source["regions"]["act-1/cave-3"]["enemies"] = []
    err, _ = refusal(tmp_path, source, {NAMELESS: {"sprite": "pebble"}})
    assert "is not one the player can be given" in str(err)
    assert err.pointer == "/families/beetle/defaults/drops"


# --------------------------------------------------------------------------
# The case that was already caught stays caught, with its pinned sentence.


def test_a_wholly_absent_id_is_still_refused_with_the_same_sentence(tmp_path):
    err, _ = refusal(tmp_path, one_drop(src(), ABSENT))
    assert str(err).startswith(f"unknown item {ABSENT!r} in drops")
    assert err.pointer == "/regions/act-1~1cave-2/enemies/0/properties/drops"


def test_a_non_string_drop_is_still_refused_as_an_unknown_item(tmp_path):
    """`{"a": 1}` is unhashable, so it must not reach a set membership test."""
    err, _ = refusal(tmp_path, one_drop(src(), {"a": 1}))
    assert "unknown item" in str(err)


def test_a_door_needing_an_item_with_no_name_is_refused_too(tmp_path):
    """`needs` reads the same catalog through the same helper: a lock no
    player can pick open is the same silent nothing, at the source."""
    source = {"blueprint": 3, "regions": {"act-1/cave-2": {"places": [
        {"id": "d1", "kind": "door", "at": "3,6", "glyph": "+",
         "to": "cave-3", "to_at": "3,4", "needs": NAMELESS},
    ]}}}
    err, _ = refusal(tmp_path, source, {NAMELESS: {"sprite": "pebble"}})
    assert "is not one the player can be given" in str(err)
    assert err.pointer == "/regions/act-1~1cave-2/places/0/needs"


def test_a_door_needing_an_absent_item_still_says_unknown_item(tmp_path):
    source = {"blueprint": 3, "regions": {"act-1/cave-2": {"places": [
        {"id": "d1", "kind": "door", "at": "3,6", "glyph": "+",
         "to": "cave-3", "to_at": "3,4", "needs": ABSENT},
    ]}}}
    err, _ = refusal(tmp_path, source)
    assert str(err).startswith(f"unknown item {ABSENT!r} in needs")


def test_the_pinned_conformance_fixtures_still_say_unknown_item():
    """The four drop/needs `expected-error.txt` files under
    tests/fixtures/blueprint pin the sentence for an absent id. A fix that
    reworded them lands here."""
    root = mk.ROOT / "tests" / "fixtures" / "blueprint"
    names = {"ancestor-drops-item", "inherited-drops-item",
             "unknown-drops-item", "needs-unknown-item"}
    found = {p.parent.name: p.read_text(encoding="utf-8").splitlines()[0]
             for p in sorted(root.rglob("invalid/*/expected-error.txt"))
             if p.parent.name in names}
    assert set(found) == names, "a pinned drop/needs fixture moved"
    for name, first in found.items():
        assert first == "unknown item", (name, first)


# --------------------------------------------------------------------------
# A pack with no catalog at all, and a family that names no drops.


def test_a_pack_with_no_catalog_refuses_any_drop(tmp_path):
    source = one_drop(src(), "shell")
    pack = build(tmp_path, source, catalog=False)
    assert "items" not in json.loads((pack / "world.json").read_text())
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.expand(source, pack_dir=pack)
    assert str(err.value).startswith("unknown item 'shell' in drops")


def test_a_pack_with_no_catalog_expands_a_family_that_names_no_drops(tmp_path):
    source = no_drops(src())
    pack = build(tmp_path, source, catalog=False)
    regions, things = blueprint.plan(source, pack_dir=pack)
    records = regions["act-1/cave-2"]["enemies"]
    assert [r["id"] for r in records] == ["b1", "b2", "m1", "odd1"]
    assert things == []


def test_a_family_naming_no_drops_is_untouched(tmp_path):
    """The ordinary pack: every instance expands as before, and the standard
    pack's one drop (of `shell`, a named item) still stands."""
    pack = build(tmp_path, mk.STD_BLUEPRINT)
    regions, things = blueprint.plan(mk.STD_BLUEPRINT, pack_dir=pack)
    records = regions["act-1/cave-2"]["enemies"]
    assert [r["id"] for r in records] == ["b1", "b2", "m1", "odd1"]
    assert records[1]["drops"] == ["shell"]
    assert "drops" not in records[0]
    assert things == []


# --------------------------------------------------------------------------
# Which catalog, and why that is the right one.


def test_declared_items_is_exactly_the_catalog_weave_bakes(tmp_path):
    """The reader is `cli._player_items`, not a second reading of the file."""
    pack = build(tmp_path, mk.STD_BLUEPRINT,
                 {NAMELESS: {"sprite": "pebble"}, "bare": {},
                  "blank": {"name": "   "}, "good": {"name": "a good thing"}})
    world = {"items": json.loads((pack / "world.json").read_text())["items"]}
    assert blueprint._declared_items(pack) == set(cli._player_items(world))
    assert blueprint._declared_items(pack) == {"chalked-map", "shell", "torch", "good"}


def test_weave_asks_blueprint_first_before_it_reads_the_world():
    """Why Blueprint needs no reader of its own: the weave asks Blueprint
    first, so a pack whose world is not readable is refused there rather
    than baked with a drop nobody could receive."""
    text = inspect.getsource(cli.weave_html)
    assert text.index("blueprint.check_errors(pack)") < text.index("_player_items(world)")


def test_the_weave_really_pays_nothing_for_a_nameless_drop(tmp_path):
    """The other half of the defect, end to end. This pack carries no
    Blueprint at all, so nothing refuses it: hand the weave the enemy record
    the old check would have written and read what the player actually gets.
    """
    pack = mk.build(tmp_path, blueprint=None)
    # `cave-2` has to be on the act's own region list or the weave never
    # bakes it and the assertion below would pass for the wrong reason.
    act = pack / "acts" / "act-1" / "world.json"
    shape = json.loads(act.read_text(encoding="utf-8"))
    shape["regions"].append("cave-2")
    act.write_text(json.dumps(shape), encoding="utf-8")

    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["items"][NAMELESS] = {"sprite": "pebble"}
    world_json.write_text(json.dumps(world), encoding="utf-8")
    path = pack / "acts" / "act-1" / "cave-2" / "contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["enemies"] = [{"id": "b2", "name": "a beetle", "sprite": "beetle",
                            "at": [6, 4], "hp": 3, "atk": 1, "xp": 2,
                            "drops": [NAMELESS]}]
    path.write_text(json.dumps(contract), encoding="utf-8")

    def spawned():
        """The spawn record the woven file hands the player, drops and all."""
        found = re.search(r"window\.VEFR_ENEMIES = (\{.*?\});",
                          cli.weave_html(pack), re.S)
        assert found, "the weave baked no enemy table"
        return json.loads(found.group(1))["cave-2"]

    assert spawned()[0]["drops"] == []
    # The same record pays out the moment the entry is one the reader keeps.
    world["items"][NAMELESS]["name"] = "a pebble"
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert spawned()[0]["drops"] == [NAMELESS]