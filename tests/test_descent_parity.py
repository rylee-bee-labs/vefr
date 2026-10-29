"""Play-time floors, R: the JavaScript twin answers exactly what Python answers.

The player is one static HTML file, so the descent is walked in the
browser and Python is only the reference. This replays `locate` and the
whole floor plan (size, rooms, rows, stairs, mobs, identity) for a dozen
depths and two runs through the REAL woven player in jsdom
(`window.VEFR_DESCENT`) and demands identical answers, in both
directions: nothing may be in one language and not the other.

The last two cases are the vefr#315 review finding: a Section names a
Blueprint family by id and carries no record of its own (ADR 0014), so a
floor that read the Section's entry and stopped drew every monster at the
engine's own floor of 1 HP, 1 atk and no drops. The descent carries the
pack's Blueprint (`blueprint`), both twins resolve each family through it,
and the same floor is compared in both languages.
"""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli, delve, maplab
from vefr import stamps as stamps_mod
from test_descent_floors import DESCENT

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "descent_parity_harness.mjs"
DEPTHS = list(range(1, 13))
RUNS = [0, 1, 2]

# ADR 0014: a Section's `families` entry names a Blueprint family by id
# and carries no record of its own, so `hp`, `atk`, `sight`, `name` and
# `drops` come from the pack's Blueprint - here the one the descent
# carries, which is what the weave writes beside the Sections.
# `gutter-rat` extends `rat` and overrides only its `hp`, which is the
# whole-value replacement over the root chain; `ghost` is named by a
# Section and defined by no Blueprint, and that is the validator's
# sentence rather than a floor's.
BLUEPRINT = {
    "blueprint": 1,
    "families": {
        "rat": {"defaults": {"name": "a grey rat", "sprite": "rat", "hp": 4,
                             "atk": 2, "sight": 5, "drops": ["pebble"]}},
        "gutter-rat": {"extends": "rat", "defaults": {"hp": 9}},
        "moth": {"defaults": {"name": "a pale moth", "sprite": "moth", "hp": 2,
                              "atk": 1, "sight": 3}},
        "shade": {"extends": "moth", "defaults": {"name": "a cold shade"}},
    },
    "regions": {},
}

# The same descent with the Blueprint beside it and the cellar's families
# naming ids that exercise it: one through an `extends` chain, one at the
# root, and one the Blueprint does not have.
BLUEPRINT_DESCENT = copy.deepcopy(DESCENT)
BLUEPRINT_DESCENT["blueprint"] = BLUEPRINT
BLUEPRINT_DESCENT["sections"][0]["families"] = [
    {"family": "gutter-rat", "weight": 2, "depth": [1, 3]},
    {"family": "moth", "weight": 1, "depth": [1, 3]},
    {"family": "ghost", "weight": 1, "depth": [1, 3]},
]
# E8a: the cellar ends on a warden floor, so the third floor carries monster
# `w` on the v3 warden anchor and the plan's warden record in both languages.
BLUEPRINT_DESCENT["sections"][0]["pattern"] = ["entry", "n", "warden"]
# The record form (ADR 0015): its own id and the key it carries reach the plan in both languages.
BLUEPRINT_DESCENT["sections"][0]["warden"] = {"family": "gutter-rat", "id": "rat-king", "carries": "rat-key"}
# vefr#349: the cellar names its own ground, so the plan carries that legend and both
# languages read it off the floor rather than off one shared table baked beside the Sections.
BLUEPRINT_DESCENT["sections"][0]["tiles"] = {".": "wood-floor", "#": "stone-wall"}
# Stamps in play (2026-10-09): the fixture stamps ride in the descent block as the weave carries
# them, and the cellar uses them, so both languages draw the same stamped rooms and the same vault.
BLUEPRINT_DESCENT["stamps"] = json.loads(json.dumps(
    stamps_mod.load(Path(__file__).resolve().parent / "fixtures" / "stamps")))
BLUEPRINT_DESCENT["sections"][0]["stamps"] = ["cellar"]
BLUEPRINT_DESCENT["sections"][0]["vault"] = "vault-cellar"

# ADR 0017: the same cellar, with drops that roll. The catalog is the
# pack's own `items`, handed to `floor_plan` on the Python side and planted
# on `window.VEFR_ITEMS` for the JavaScript one, so the whole drop - base
# id, drawn rarity, hidden traits - is compared in both languages.
# `brass-ring` is the other half of the slice: a fixed `rarity` and fixed
# `traits` with no `roll` under them, so there is no table and nothing is
# drawn - the two kinds of instance a drop can carry are both here.
ITEMS = {
    "pebble": {"name": "a grey pebble", "sprite": "", "value": 1},
    "brass-ring": {"name": "a brass ring", "sprite": "", "rarity": "common",
                   "traits": ["keen"]},
    "cloudy-potion": {
        "name": "a cloudy potion", "sprite": "potion", "heal": 3, "use": "drink",
        "roll": {"rarity": {"common": 60, "uncommon": 30, "rare": 10},
                 "traits": ["keen", "brave", "swift", "cold"],
                 "chance": 60, "max": 2},
    },
}

ROLLED_DESCENT = copy.deepcopy(BLUEPRINT_DESCENT)
ROLLED_DESCENT["blueprint"]["families"]["rat"]["defaults"]["drops"] = ["pebble"]
ROLLED_DESCENT["blueprint"]["families"]["moth"]["defaults"]["drops"] = [
    "brass-ring", "cloudy-potion"]
# E8d: this descent's warden carries Amendment 1's three keys, so the
# whole-plan comparison below holds the plan record AND the mob they ride
# equal in both languages - `challenge`, `yields` and `fightable` are
# exactly the keys a JS twin that forgot them would drop.
ROLLED_DESCENT["sections"][0]["warden"] = {
    "family": "gutter-rat", "id": "rat-king", "carries": "rat-key",
    "challenge": "rule", "yields": True, "fightable": False}
ROLLED_DEPTHS = [1, 2, 3]

# ADR 0021: every field the RPG core added to a monster, in both twins. The
# cellar's curve scales every floor differently, the rat carries guard, gold
# and a drop chance, and the moth drops a charm whose roll ties its traits to
# its rarity - so a twin that read one of them differently, or spent a draw
# the other did not, gives a different plan.
RPG_ITEMS = dict(copy.deepcopy(ITEMS), **{"charm": {
    "name": "a charm", "sprite": "",
    "roll": {"rarity": {"common": 50, "rare": 30, "mythic": 20},
             "traits": ["keen", "brave", "swift", "cold"],
             "per_rarity": {"common": 0, "rare": 2, "mythic": 3}}}})
RPG_DESCENT = copy.deepcopy(ROLLED_DESCENT)
RPG_DESCENT["sections"][0]["curve"] = {"hp": [1.0, 2.5], "atk": [1.0, 3.0]}
RPG_DESCENT["blueprint"]["families"]["rat"]["defaults"].update(
    {"guard": 1, "gold": [1, 9], "drop_chance": 50})
RPG_DESCENT["blueprint"]["families"]["moth"]["defaults"]["drops"] = ["charm"]
RPG_DEPTHS = [1, 2, 3]


# One Section, nine floors, and the two keys the shape has to be honest about.
# `rat` is everywhere; `moth` stops at floor 3 and `beetle` starts at floor 7,
# which is the regression vefr#351 names - a `depth` range that is not read is
# a family on every floor of the Section. The Section also names its own
# ground, so the two languages are compared on a legend that is not the shared
# one either of them would answer from memory.
DEPTH_DESCENT = copy.deepcopy(DESCENT)
DEPTH_DESCENT["sections"] = [{
    "id": "deep",
    "floors": 9,
    "size": {"w": [32, 36], "h": [24, 26]},
    "rooms": [6, 8],
    "fog": {"radius": 5},
    "tiles": {".": "wood-floor"},
    "families": [
        {"family": "rat", "weight": 3, "depth": [1, 9]},
        {"family": "moth", "weight": 2, "depth": [1, 3]},
        {"family": "beetle", "weight": 2, "depth": [7, 9]},
    ],
}]
DEPTH_DEPTHS = list(range(1, 10))


@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    home = tmp_path_factory.mktemp("descent-parity")
    html = home / "p.html"
    html.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    cases = home / "cases.json"
    cases.write_text(json.dumps({"descent": DESCENT, "depths": DEPTHS,
                                 "runs": RUNS,
                                 "blueprintDescent": BLUEPRINT_DESCENT,
                                 "blueprintDepths": [1, 2, 3],
                                 "rolled": {"descent": ROLLED_DESCENT,
                                            "depths": ROLLED_DEPTHS,
                                            "items": ITEMS},
                                 "rpg": {"descent": RPG_DESCENT,
                                         "depths": RPG_DEPTHS,
                                         "items": RPG_ITEMS},
                                 "depthDescent": DEPTH_DESCENT,
                                 "depthDepths": DEPTH_DEPTHS}),
                     encoding="utf-8")
    run = subprocess.run(["node", str(HARNESS), str(html), str(cases)],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr + run.stdout
    return json.loads(run.stdout)


def _canonical(value):
    return json.dumps(value, sort_keys=True)


def test_the_twin_exists(replay):
    assert replay["hasApi"] is True


def test_locate_matches_for_every_depth(replay):
    got = replay["located"]
    assert len(got) == len(DEPTHS)
    for depth, answer in zip(DEPTHS, got):
        cycle, section, k = delve.locate(depth, DESCENT)
        assert answer == [cycle, section["id"], k], depth


def test_the_whole_floor_matches_field_for_field(replay):
    got = replay["plans"]
    assert len(got) == len(DEPTHS) + len(RUNS)
    for depth, plan in zip(DEPTHS, got):
        want = delve.floor_plan(DESCENT, depth)
        assert _canonical(plan) == _canonical(want), depth


def test_a_second_run_is_another_floor_on_both_sides(replay):
    got = replay["plans"][len(DEPTHS):]
    for run, plan in zip(RUNS, got):
        descent = copy.deepcopy(DESCENT)
        want = delve.floor_plan(descent, 1, run=run)
        assert _canonical(plan) == _canonical(want), run


def test_the_plan_carries_no_grid_in_its_identity(replay):
    for plan in replay["plans"]:
        assert set(plan["identity"]) == {"gen", "hash", "key"}
        assert plan["name"] == plan["name"].lower()


def test_a_rolled_floor_is_the_same_floor_in_both_languages(replay):
    """ADR 0017: the rarity and the hidden traits are drawn in both.

    The base id was already a twin draw; the rarity and the traits are a
    second one, off a second named stream, and a twin that read the
    catalog in a different order or spent the draws in a different order
    would give a player a different potion from the one Python drew.

    Two kinds of instance ride a drop, and the fixture makes both. A pack
    that declares a `roll` gets its rarity drawn off that table, so the
    rarity must be one of the names the table itself carries. A pack that
    declares only a `rarity` or `traits` gets no draw at all - there is
    no table to draw from - and gets exactly those words back, which is
    what `item_draw` says it does and the only thing a twin could get
    wrong here while still agreeing with itself. Both have to appear, or
    one of the two branches is not being read off a real floor.
    """
    got = replay["rolled"]["plans"]
    assert len(got) == len(ROLLED_DEPTHS)
    rolled_any = drawn_any = fixed_any = False
    for depth, plan in zip(ROLLED_DEPTHS, got):
        want = delve.floor_plan(ROLLED_DESCENT, depth, catalog=ITEMS)
        assert _canonical(plan) == _canonical(want), depth
        for mob in want["mobs"]:
            for drop in mob["drops"]:
                if not isinstance(drop, dict):
                    continue
                rolled_any = True
                assert drop["identified"] is False, drop
                entry = ITEMS[drop["item"]]
                roll = maplab.item_roll_of(entry)
                if roll:
                    # drawn: a name this roll's own table carries, and
                    # traits off its own pool - never the pack's fixed words.
                    drawn_any = True
                    names = {name for name, _ in roll["rarity"]}
                    assert names, drop
                    assert drop["rarity"] in names, drop
                    assert set(drop["traits"]) <= set(roll["traits"]), drop
                else:
                    # fixed: no table, so no draw, so the pack's own words
                    # come back verbatim - the same rarity, the same traits
                    # in the pack's order, and not one thing invented.
                    fixed_any = True
                    assert "rarity" in entry or "traits" in entry, entry
                    assert drop == {"item": drop["item"],
                                    "rarity": entry.get("rarity", ""),
                                    "traits": list(entry.get("traits", [])),
                                    "identified": False}, drop
    assert rolled_any, "the fixture rolled nothing, so this proved nothing"
    assert drawn_any, "the fixture drew nothing, so no rarity was read off a table"
    assert fixed_any, "the fixture fixed nothing, so no no-draw drop was read"


def test_the_rpg_core_floor_is_the_same_floor_in_both_languages(replay):
    """ADR 0021: curve, guard, gold, drop chance and rarity-tied traits.

    Each is read after the draws it does not own, on a stream of its own, so
    the plan is compared whole - and the fixture is checked to have made each
    of them, or the comparison proved nothing about it.
    """
    got = replay["rpg"]["plans"]
    assert len(got) == len(RPG_DEPTHS)
    seen = {"guard": False, "gold": False, "dropped": False, "kept": False,
            "tied": False}
    for depth, plan in zip(RPG_DEPTHS, got):
        want = delve.floor_plan(RPG_DESCENT, depth, catalog=RPG_ITEMS)
        assert _canonical(plan) == _canonical(want), depth
        for mob in want["mobs"]:
            seen["guard"] |= mob.get("guard") == 1
            seen["gold"] |= isinstance(mob.get("gold"), int)
            if mob.get("guard") == 1:      # a rat, or a family extending one
                seen["dropped" if mob["drops"] else "kept"] = True
            for drop in mob["drops"]:
                if isinstance(drop, dict) and drop["item"] == "charm":
                    per = RPG_ITEMS["charm"]["roll"]["per_rarity"]
                    assert len(drop["traits"]) == per[drop["rarity"]], drop
                    seen["tied"] = True
    assert all(seen.values()), seen


def test_the_rolled_floor_is_the_same_floor_twice_on_each_side(replay):
    """And the twin is not accidentally deterministic in one language
    only: Python draws the same plan twice, and so does the browser."""
    for depth in ROLLED_DEPTHS:
        first = delve.floor_plan(ROLLED_DESCENT, depth, catalog=ITEMS)
        second = delve.floor_plan(ROLLED_DESCENT, depth, catalog=ITEMS)
        assert _canonical(first) == _canonical(second), depth


def test_a_family_is_resolved_from_the_blueprint_rather_than_the_sections_entry():
    """The Python half of the vefr#315 finding, read off the floor itself.

    A Section names a Blueprint family by id and carries no record of its
    own (ADR 0014), so `hp`, `atk`, `sight`, `name` and `drops` are the
    Blueprint's answer to that id. A floor that read the Section's entry
    and stopped drew every monster at 1 HP, 1 atk and no drops, which is
    the same floor twice and a game where nothing can be fought.
    """
    plan = delve.floor_plan(BLUEPRINT_DESCENT, 1)
    assert plan["mobs"], "the cellar's first floor drew no monsters"
    for mob in plan["mobs"]:
        if mob["family"] == "gutter-rat":
            # The chain: `gutter-rat` overrides `hp` over `rat`, and takes
            # everything else from the root.
            assert (mob["hp"], mob["atk"], mob["sight"]) == (9, 2, 5), mob
            assert mob["name"] == "a grey rat", mob
            assert mob["drops"] == ["pebble"], mob
        elif mob["family"] == "moth":
            assert (mob["hp"], mob["atk"], mob["sight"]) == (2, 1, 3), mob
            assert mob["name"] == "a pale moth", mob
        else:
            # A family no Blueprint has: no base, so the engine's own
            # floor of 1 and the id the Section wrote. `vefr check` refuses
            # that Section with `/families/0/family`; a floor lays anyway.
            assert mob["family"] == "ghost", mob
            assert (mob["hp"], mob["atk"], mob["drops"]) == (1, 1, []), mob


def test_a_family_the_blueprint_cannot_resolve_lays_the_floor_at_one():
    """Every refusal `resolve_family` makes is the validator's, not a floor's.

    An unknown family, one that extends itself, one whose parent is
    missing and one caught in a cycle all come back with no base, and a
    floor with no base draws the monster anyway - at the engine's own
    floor of 1, with the id the Section wrote.
    """
    broken = {"families": {
        "loop": {"extends": "loop", "defaults": {"hp": 6}},
        "orphan": {"extends": "ghost", "defaults": {"hp": 6}},
        "spare": {"extends": "loop", "defaults": {"hp": 6}},
    }}
    for family in ("ghost", "loop", "orphan", "spare"):
        assert delve.family_base(broken, family) is None, family
    assert delve.family_base(None, "rat") is None

    descent = copy.deepcopy(BLUEPRINT_DESCENT)
    descent["blueprint"] = broken
    descent["sections"][0]["families"] = [{"family": "orphan", "weight": 1}]
    plan = delve.floor_plan(descent, 1)
    assert plan["mobs"]
    for mob in plan["mobs"]:
        assert (mob["family"], mob["hp"], mob["atk"], mob["drops"]) \
            == ("orphan", 1, 1, []), mob


def test_the_blueprint_floor_is_the_same_floor_in_both_languages(replay):
    """The same floor with a Blueprint beside it, in both languages.

    Both twins resolve the same ids through the same chain and agree on
    every field, so the mobs a browser draws are the mobs Python drew -
    including the stats, which are the whole of the finding.
    """
    got = replay["blueprint"]["plans"]
    assert len(got) == 3
    for depth, plan in zip([1, 2, 3], got):
        want = delve.floor_plan(BLUEPRINT_DESCENT, depth)
        assert _canonical(plan) == _canonical(want), depth
    assert {mob["hp"] for mob in got[0]["mobs"]} != {1}, \
        "every monster drew at 1 HP: the Blueprint was never read"


def test_a_section_names_the_ground_its_own_floors_are_drawn_with(replay):
    """vefr#349: `tiles` reaches the floor, in both languages.

    Before this the legend came from one table baked beside the Sections, so
    every Section in a descent drew the same ground however reasonable a
    `tiles` was. The floor now carries its own Section's legend, and the
    field-for-field comparison above is what proves the two languages agree
    on it; this says what that legend has to be, so the parity can only pass
    by being right rather than by both sides reading nothing.
    """
    got = replay["blueprint"]["plans"]
    assert got, "the blueprint descent drew no floors"
    for plan in got:
        want = delve.floor_plan(BLUEPRINT_DESCENT, plan["depth"])
        assert _canonical(plan["legend"]) == _canonical(want["legend"]), plan["depth"]
    first = got[0]["legend"]
    assert first["."]["tile"] == "wood-floor", first
    assert first["#"]["tile"] == "stone-wall", first
    # A glyph the Section did not name is still the engine's, and the base
    # colours are never a pack's to change: a floor that walked through its
    # own wall would be a different generator.
    assert first["u"] == delve.LEGEND["u"], first
    assert first["#"]["solid"] is True and first["#"]["base"] == ["#20242b"], first


def test_a_section_that_names_no_tiles_draws_exactly_the_legend_it_always_did(replay):
    """The no-breaking-change half: a Section with no `tiles` is the shared one.

    `LEGEND` itself is never touched, so the floor a pack that never wrote
    `tiles` gets is the floor it got before - which is also the floor the
    JavaScript twin's own fallback is.
    """
    plain = copy.deepcopy(DESCENT)
    for depth in DEPTHS:
        want = delve.floor_plan(plain, depth)
        assert want["legend"] == delve.LEGEND, depth
    assert delve.section_legend({"id": "no-tiles"}) == delve.LEGEND
    assert delve.LEGEND["."]["tile"] == "dungeon-floor", \
        "section_legend wrote into the shared legend"


def test_a_familys_depth_range_is_the_floors_it_is_drawn_on(replay):
    """vefr#351: `depth: [7, 9]` means the last three floors, in both languages.

    A range that is not read is a family on every floor of the Section, and
    the Cottage worker found that by counting spawns rather than by reading
    the code - so the check here is the same counting, on both sides.
    """
    assert replay["depth"], "the depth descent drew no floors"
    drawn = {}
    for answer, depth in zip(replay["depth"], DEPTH_DEPTHS):
        want = delve.floor_plan(DEPTH_DESCENT, depth)
        assert answer["k"] == want["k"], depth
        assert answer["families"] == sorted({m["family"] for m in want["mobs"]}), depth
        assert _canonical(answer["legend"]) == _canonical(want["legend"]), depth
        drawn[depth] = set(answer["families"])
    for depth, families in drawn.items():
        assert ("beetle" in families) == (7 <= depth <= 9), \
            f"floor {depth} drew the wrong families: {sorted(families)}"
        assert ("moth" in families) == (1 <= depth <= 3), \
            f"floor {depth} drew the wrong families: {sorted(families)}"
        assert "rat" in families, f"floor {depth} lost the every-floor family"


def test_the_weave_hands_the_player_the_families_it_resolves(tmp_path):
    """The other end of the same fix: where the twin's Blueprint comes from.

    A floor can only resolve a family id if the pack's Blueprint travels
    with the descent, so `weave_html` bakes its `families` in beside the
    Sections. A pack with no Blueprint bakes none, which is the same
    answer the validator gives such a pack: nothing to resolve, and the
    engine's own floor of 1.
    """
    sys.path.insert(0, str(ROOT / "tests"))
    sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
    from blueprint_helpers import normalized_pack  # noqa: E402
    import make_descent_pack  # noqa: E402

    withblueprint = normalized_pack(tmp_path / "a", blueprint=BLUEPRINT)
    _with_descent(withblueprint, copy.deepcopy(DESCENT))
    baked = _baked_descent(cli.weave_html(withblueprint))
    assert baked["blueprint"]["families"] == BLUEPRINT["families"]
    assert baked["legend"], "the legend beside it is still baked"

    without = make_descent_pack.build(tmp_path / "b")
    assert _baked_descent(cli.weave_html(without))["blueprint"] == {}


def _with_descent(pack: Path, descent) -> None:
    """The pack's `world.json` carrying this descent block."""
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["descent"] = descent
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")


def _baked_descent(html: str) -> dict:
    """The descent block as `weave_html` wrote it into the player."""
    line = next(row for row in html.splitlines()
                if row.startswith("window.VEFR_DESCENT_DEF = "))
    return json.loads(line.split(" = ", 1)[1].rstrip().rstrip(";"))