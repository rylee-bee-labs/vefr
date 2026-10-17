"""Mending recipes: two carried things become one (E2).

The authoring side of the slice, pinned here:

  * the shape - one `recipe` block on `shapes.BLOCKS`, four keys;
  * the refusals, one test each, each one plain sentence naming the
    recipe: a block that is not a list, a record that is not an object,
    a missing or unknown key, `inputs` that is not exactly two item
    ids, an input or an `output` the pack's `items` does not declare,
    and an id a second recipe already took;
  * the `mends` event - the fourteenth rules event, carrying the recipe
    id, refused when the recipe is not one the pack declares;
  * the backward-compatibility proof - a pack that declares no recipes
    validates exactly as it did, and the sweep that runs in
    `vefr check` reaches the block on a real pack.

The half a player meets - the Bag panel's Mend buttons, the preview and
the consuming mend - is `tests/browser/test_mending.py`, which needs
chromium.
"""

import json
import sys
from pathlib import Path

from vefr import maplab, shapes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_mending_pack as mk  # noqa: E402

# One good `recipes` block: two plain inputs, one output, the line the
# mend says - the same canon the browser test plays with.
GOOD = [
    {"id": "mend-the-net", "inputs": ["torn-net", "loose-peg"],
     "output": "whole-net", "say": "The net is whole again."},
]


def loaded(pack: Path) -> dict:
    """The pack as `vefr check` loads it: the unified shape over the file."""
    return {**json.loads((pack / "world.json").read_text(encoding="utf-8")),
            **maplab.load_pack(pack)}


# --- the shape --------------------------------------------------------------

def test_the_recipe_block_is_registered_and_named():
    assert shapes.BLOCKS["recipe"] is shapes.RECIPE
    assert [k.name for k in shapes.RECIPE.keys] == [
        "id", "inputs", "output", "say"]


def test_a_pack_with_no_recipes_validates_exactly_as_before(tmp_path):
    pack = mk.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world.pop("recipes")
    # The reaction rule names the recipe, so it goes with it: this is
    # the pack as it stood before the slice.
    world.pop("rules")
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert maplab.recipes_errors(loaded(pack)) == []
    assert maplab.validate(loaded(pack), pack) == []


def test_a_good_recipes_block_is_silent(tmp_path):
    pack = mk.build(tmp_path)
    assert maplab.recipes_errors(loaded(pack)) == []
    assert maplab.validate(loaded(pack), pack) == []


# --- the refusals, one test each ---------------------------------------------

def test_recipes_that_is_not_a_list_is_named(tmp_path):
    pack = mk.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["recipes"] = {"id": "mend-the-net"}
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert maplab.recipes_errors(loaded(pack)) == [
        "recipes must be a list, such as [" + shapes.RECIPE.example + "]"]


def test_a_recipe_that_is_not_an_object_is_named_with_its_place(tmp_path):
    pack = mk.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["recipes"] = ["mend-the-net"]
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert maplab.recipes_errors(loaded(pack)) == [
        "the recipe at position 0 must be an object, such as "
        + shapes.RECIPE.example]


def test_a_recipe_with_a_missing_or_unknown_key_is_named(tmp_path):
    pack = mk.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    record = dict(GOOD[0])
    output = record.pop("output")
    record["makes"] = output
    world["recipes"] = [record]
    world_json.write_text(json.dumps(world), encoding="utf-8")
    errors = maplab.recipes_errors(loaded(pack))
    assert errors == [
        "recipe 'mend-the-net' has an unknown key 'makes'; "
        "it may only hold id, inputs, output and say",
        "recipe 'mend-the-net' must hold its output, such as "
        + shapes.RECIPE.example], errors


def test_inputs_that_is_not_exactly_two_things_is_named(tmp_path):
    pack = mk.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    record = dict(GOOD[0], inputs=["torn-net"])
    world["recipes"] = [record]
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert maplab.recipes_errors(loaded(pack)) == [
        "recipe 'mend-the-net' inputs must name exactly two things to mend"]


def test_an_input_the_pack_does_not_declare_is_named(tmp_path):
    """The refusal the brief asks for by name: a recipe naming an item
    the pack's `items` does not declare is refused, through the sweep
    that runs in `vefr check` and not only against the helper."""
    pack = mk.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["recipes"] = [dict(GOOD[0], inputs=["torn-net", "unmade-thing"])]
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert maplab.recipes_errors(loaded(pack)) == [
        "recipe 'mend-the-net' inputs names unknown item 'unmade-thing'"]
    assert maplab.validate(loaded(pack), pack) == [
        "recipe 'mend-the-net' inputs names unknown item 'unmade-thing'"]


def test_an_output_the_pack_does_not_declare_is_named(tmp_path):
    pack = mk.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["recipes"] = [dict(GOOD[0], output="unmade-thing")]
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert maplab.recipes_errors(loaded(pack)) == [
        "recipe 'mend-the-net' output names unknown item 'unmade-thing'"]


def test_two_recipes_may_not_share_an_id(tmp_path):
    pack = mk.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["recipes"] = GOOD + [
        dict(GOOD[0], output="torn-net")]
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert maplab.recipes_errors(loaded(pack)) == [
        "two recipes share the id 'mend-the-net' - recipe ids must be unique"]


# --- the mends event ---------------------------------------------------------

def test_mends_is_the_fourteenth_event_and_carries_the_recipe_id():
    assert shapes.EVENTS["mends"] == (shapes.Key("recipe", "ref", ref="recipe"),)
    assert maplab.RULE_EVENT_KEYS["mends"] == ("recipe",)


def test_a_rule_may_fire_on_mends_and_only_name_a_declared_recipe(tmp_path):
    pack = mk.build(tmp_path)
    known = maplab._rule_known_ids(loaded(pack), pack)
    assert known["recipes"] == {"mend-the-net"}
    assert maplab._rule_event_errors(
        "r", {"mends": {"recipe": "mend-the-net"}}, known) == []
    assert maplab._rule_event_errors(
        "r", {"mends": {"recipe": "ghost"}}, known) == [
        "rule 'r' when 'mends' names unknown recipe 'ghost'"]


def test_the_fixture_pack_owns_a_rule_that_reacts_to_the_mend(tmp_path):
    """The reaction rule is part of the fixture pack, so the browser test
    plays a pack whose `mends` really is nameable - and the sweep that
    runs in `vefr check` accepts the whole pack as it stands."""
    pack = mk.build(tmp_path)
    world = loaded(pack)
    assert [r["id"] for r in world["rules"]] == ["the-yard-notices"]
    assert maplab.validate(world, pack) == []