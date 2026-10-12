"""The bag's capacity: opt-in, unbounded unless a pack names a size.

A pack may name `bag.size` in world.json, and a carried thing with a `carry`
raises the cap by that many places. A pack that names no size keeps the
unbounded bag. A full bag refuses a floor pickup in one plain line and leaves
the thing on the floor, where it can be picked up once there is room; it
refuses a shop purchase in the same words and takes no gold; a warden's key
always fits.

The schema and the baked catalog are plain Python and run everywhere. The
behaviour runs the REAL woven player in a node jsdom harness
(`tests/fixtures/bag_capacity_harness.mjs`) and is skipped where node is absent.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli, maplab, shapes

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import make_equip_pack as mk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "bag_capacity_harness.mjs"

CAPPED = "bag-cap-test"
FREE = "bag-free-test"

# A satchel is an upgrade: carrying it adds two places. The vault key is the
# warden's key shape - an ordinary item the warden's `carries` names.
UPGRADE = {
    "satchel-1": {"name": "a leather satchel", "sprite": "cloak", "carry": 2},
    "vault-key": {"name": "a brass key", "sprite": "ring"},
}


# ---- the schema and the bake: no node needed ------------------------

def test_a_bag_size_is_a_whole_number_of_places():
    assert shapes.check(shapes.BLOCKS["bag"], {"size": 6}) == []
    assert [p.sentence for p in shapes.check(shapes.BLOCKS["bag"], {"size": 0})] == [
        "bag.size must be a whole number of at least 1"]
    assert [p.sentence for p in shapes.check(shapes.BLOCKS["bag"], {"size": "six"})] == [
        "bag.size must be a whole number, such as 6"]


def test_a_bag_block_must_hold_its_size():
    problems = shapes.check(shapes.BLOCKS["bag"], {})
    assert len(problems) == 1
    assert "size" in problems[0].sentence


def test_a_carry_is_a_positive_whole_number_on_an_item():
    assert shapes.check_item({"name": "a satchel", "carry": 2}) == []
    bad = shapes.check_item({"name": "a satchel", "carry": 0}, at="items.satchel")
    assert len(bad) == 1
    assert "items.satchel.carry" in bad[0].sentence


def test_a_pack_that_names_no_bag_has_no_bag_errors():
    assert maplab.bag_errors({}) == []
    assert maplab.bag_errors({"bag": {"size": 0}}) != []


def test_the_bake_carries_a_positive_carry_and_nothing_else():
    items = cli._player_items({"items": {
        "satchel": {"name": "a satchel", "carry": 2},
        "rock": {"name": "a rock", "carry": 0},
        "bead": {"name": "a bead", "carry": True},
    }})
    assert items["satchel"]["carry"] == 2
    assert "carry" not in items["rock"]
    assert "carry" not in items["bead"]


# ---- the behaviour: the woven player in jsdom -----------------------

def weave(dest, name, bag=None):
    pack = mk.build(dest, items=UPGRADE, name=name)
    if bag is not None:
        world_json = pack / "world.json"
        world = json.loads(world_json.read_text(encoding="utf-8"))
        world["bag"] = bag
        world_json.write_text(json.dumps(world), encoding="utf-8")
    out = dest / (name + ".html")
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    return out


def run(html, name, store=None, adds=None, take=None, drop=None,
        retake=False, buy=None, reload=None):
    spec = {"name": name, "store": store or {}}
    if adds is not None:
        spec["adds"] = adds
    if take is not None:
        spec["take"] = {"item": take}
    if drop is not None:
        spec["drop"] = drop
    if retake:
        spec["retake"] = True
    if buy is not None:
        spec["buy"] = {"item": buy}
    if reload is not None:
        spec["reload"] = {"adds": reload}
    result = subprocess.run(
        ["node", str(HARNESS), str(html), json.dumps(spec)],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def bag_store(name, entries, gold=None):
    store = {f"vefr-bag-{name}": json.dumps(entries)}
    if gold is not None:
        store[f"vefr-gold-{name}"] = str(gold)
    return store


@pytest.fixture(scope="module")
def capped(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    return weave(tmp_path_factory.mktemp("bag-cap"), CAPPED, bag={"size": 2})


@pytest.fixture(scope="module")
def free(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    return weave(tmp_path_factory.mktemp("bag-free"), FREE)


def test_an_unnamed_size_takes_an_unbounded_number_of_things(free):
    out = run(free, FREE, adds=[{"id": "potion-1"}] * 12)
    assert out["adds"] == [True] * 12
    assert len(out["bag"]) == 12
    assert out["count"] == "12 things carried."


def test_a_named_size_refuses_the_thing_past_the_cap(capped):
    out = run(capped, CAPPED, adds=[{"id": "potion-1"}] * 3)
    assert out["adds"] == [True, True, False]
    assert len(out["bag"]) == 2
    assert out["count"] == "2 of 2 carried."


def test_a_full_bag_leaves_the_pickup_on_the_floor_with_one_line(capped):
    out = run(capped, CAPPED,
              store=bag_store(CAPPED, ["potion-1", "potion-1"]),
              take="ring-1")
    assert out["combat"] == "Your bag is full. You leave a plain ring on the floor."
    assert out["bag"] == ["potion-1", "potion-1"]
    assert [d["item"] for d in out["floor"]] == ["ring-1"]


def test_a_pickup_with_room_is_taken_as_before(capped):
    out = run(capped, CAPPED, store=bag_store(CAPPED, []), take="ring-1")
    assert out["combat"] == "You pick up a plain ring."
    assert out["bag"] == ["ring-1"]
    assert out["floor"] == []


def test_a_warden_key_is_never_refused_at_the_cap(capped):
    out = run(capped, CAPPED,
              store=bag_store(CAPPED, ["potion-1", "potion-1"]),
              adds=[{"id": "potion-1"}, {"id": "vault-key", "alwaysFits": True}])
    assert out["adds"] == [False, True]
    assert out["bag"] == ["potion-1", "potion-1", "vault-key"]


def test_a_carried_upgrade_raises_the_cap_by_its_carry(capped):
    out = run(capped, CAPPED,
              store=bag_store(CAPPED, ["satchel-1"]),
              adds=[{"id": "potion-1"}] * 4)
    assert out["adds"] == [True, True, True, False]
    assert len(out["bag"]) == 4
    assert out["count"] == "4 of 4 carried."


def test_a_thing_left_by_a_full_bag_is_picked_up_once_there_is_room(capped):
    """The floor keeps what a full bag refused, across a reload: once a
    place is free, walking onto the tile again takes it."""
    out = run(capped, CAPPED,
              store=bag_store(CAPPED, ["potion-1", "potion-1"]),
              take="ring-1", drop=["potion-1"], retake=True)
    assert out["errors"] == [], out["errors"]
    assert out["combat"] == "Your bag is full. You leave a plain ring on the floor."
    assert out["recombat"] == "You pick up a plain ring."
    assert out["bag"] == ["potion-1", "ring-1"]
    assert out["floor"] == []


def test_an_upgrade_picked_up_in_play_raises_the_cap_across_a_reload(capped):
    """Not a pre-loaded saved bag: the satchel is picked up off the floor in
    play, the cap moves from 2 to 4 at once, and after a reload the bag, its
    cap and its count are the same and the cap still holds."""
    out = run(capped, CAPPED, store=bag_store(CAPPED, ["potion-1"]),
              take="satchel-1", adds=[{"id": "potion-1"}] * 3,
              reload=[{"id": "potion-1"}])
    assert out["errors"] == [], out["errors"]
    assert out["combat"] == "You pick up a leather satchel."
    assert out["adds"] == [True, True, False]
    assert out["count"] == "4 of 4 carried."
    after = out["reloaded"]
    assert after["bag"] == ["potion-1", "satchel-1", "potion-1", "potion-1"]
    assert after["room"] == 4
    assert after["count"] == "4 of 4 carried."
    assert after["adds"] == [False]
    assert len(out["bag"]) == 4


def test_a_full_bag_refuses_a_purchase_in_words_and_keeps_the_gold(capped):
    """A shop purchase into a full bag says the floor pickup's own words,
    adds nothing, and charges nothing."""
    out = run(capped, CAPPED,
              store=bag_store(CAPPED, ["potion-1", "potion-1"], gold=10),
              buy="ring-1")
    assert out["errors"] == [], out["errors"]
    assert out["trade"]["pressed"] is True
    assert out["trade"]["live"] == "Your bag is full."
    assert out["trade"]["gold"] == 10
    assert out["gold"] == "10"
    assert out["bag"] == ["potion-1", "potion-1"]


def test_a_purchase_with_room_is_bought_as_before(capped):
    out = run(capped, CAPPED, store=bag_store(CAPPED, ["potion-1"], gold=10),
              buy="ring-1")
    assert out["errors"] == [], out["errors"]
    assert out["trade"]["live"] == "You buy a plain ring for 3 gold."
    assert out["trade"]["gold"] == 7
    assert out["bag"] == ["potion-1", "ring-1"]
