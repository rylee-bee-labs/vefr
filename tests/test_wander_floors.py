"""The wander layout (ADR 0022): floors whose way from stair to stair winds.

A Section that names `"layout": "wander"` is laid out by
`delve_v3._wander_stage` instead of on a spine. Three things are held here:

1. **Opt-in.** A Section that names no layout and one that names `"spine"` draw
   the very same floors, so every pack that says nothing keeps its floors.
2. **Every property the v3 sweep promises**, on the wander layout, over the
   same 200 seeds x 4 sizes x 4 kinds and through the same derivation
   (`test_floor_v3_properties._region_graph`): one component, both stairs and
   every named tile reachable, the warden off the main path, two loops at 12
   rooms or more, 40% of rooms within one step of the path, 60% of chest value
   off it, and fewer than 0.5% of floors falling back to v2.
3. **What the layout is for.** On the spine, every walk from the up stair to
   the down stair is a straight line along one row; here no walk is, the walk
   turns, and the stairs are at least `WANDER_APART` apart.
"""

from __future__ import annotations

import copy
from collections import deque
from functools import lru_cache

import pytest

from vefr import delve, delve_v3, shapes

import test_floor_v3_properties as props

SIZES = props.SIZES
FLOOR_KINDS = props.FLOOR_KINDS
SEEDS = props.SEEDS


def _pack(kind: str, rooms: int, layout: str | None) -> dict:
    """The property sweep's own Section pack, with `layout` set or left out."""
    pack = copy.deepcopy(props._pack(kind, rooms))
    if layout is not None:
        pack["layout"] = layout
    return pack


@lru_cache(maxsize=None)
def _floor(seed: str, w: int, h: int, kind: str, rooms: int) -> dict:
    """One wander floor, drawn once per key and read by every test."""
    return delve_v3.generate_floor_v3(seed, (w, h), _pack(kind, rooms, "wander"), kind)


@lru_cache(maxsize=None)
def _geometry(seed: str, w: int, h: int, kind: str, rooms: int) -> props.Geometry:
    return props._region_graph(_floor(seed, w, h, kind, rooms))


def _walk(plan: dict) -> list[tuple[int, int]]:
    """The shortest tile walk from the up stair to the down stair."""
    rows = plan["rows"]
    start = tuple(plan["anchors"]["up"])
    goal = tuple(plan["anchors"]["down"])
    prev = {start: None}
    queue = deque([start])
    while queue:
        here = queue.popleft()
        if here == goal:
            break
        x, y = here
        for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            sx, sy = step
            if (0 <= sx < plan["w"] and 0 <= sy < plan["h"]
                    and rows[sy][sx] in props.WALKABLE and step not in prev):
                prev[step] = here
                queue.append(step)
    path = []
    tile = goal
    while tile is not None:
        path.append(tile)
        tile = prev.get(tile)
    return path[::-1]


def _turns(path: list[tuple[int, int]]) -> int:
    """How many times a tile walk changes direction."""
    turns = 0
    last = None
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        step = (x1 - x0, y1 - y0)
        if last is not None and step != last:
            turns += 1
        last = step
    return turns


def _swept():
    """Every wander floor of the sweep that kept v3 geometry, with its key."""
    for w, h, rooms in SIZES:
        for kind in FLOOR_KINDS:
            for seed in SEEDS:
                plan = _floor(seed, w, h, kind, rooms)
                if plan["gen"] == 3:
                    yield (seed, w, h, kind, rooms), plan


# --------------------------------------------------------------------- opt-in


@pytest.mark.parametrize("w, h, rooms", SIZES)
def test_a_section_that_names_no_layout_draws_the_spine(w, h, rooms):
    """No layout and `"spine"` are one floor; `"wander"` is another."""
    for kind in FLOOR_KINDS:
        for seed in SEEDS[:25]:
            plain = delve_v3.generate_floor_v3(seed, (w, h), _pack(kind, rooms, None), kind)
            spine = delve_v3.generate_floor_v3(seed, (w, h), _pack(kind, rooms, "spine"), kind)
            assert plain == spine, f"{props._where(seed, w, h, kind)}: naming the spine moved it"
            assert plain["rows"] != _floor(seed, w, h, kind, rooms)["rows"], (
                f"{props._where(seed, w, h, kind)}: the wander floor is the spine floor")


def test_layout_is_refused_unless_it_is_spine_or_wander():
    base = {"section": 1, "id": "cellar", "floors": 8, "rooms": [12, 18],
            "families": [{"family": "rat", "weight": 1}]}
    for layout in ("spine", "wander"):
        assert shapes.check_section({**base, "layout": layout}) == []
    for layout in ("maze", 3, True):
        problems = shapes.check_section({**base, "layout": layout})
        assert [p.sentence for p in problems] == [
            'section.layout must be "spine" or "wander", the way the floor\'s '
            'rooms are laid out']


def test_the_layout_is_part_of_the_floor_identity():
    """A save made before a Section switched layout redraws its floors."""
    pack = _pack("normal", 16, None)
    assert delve.section_hash(pack) != delve.section_hash({**pack, "layout": "wander"})


# ----------------------------------------------------------- the v3 properties


def test_fallback_rate_under_half_a_percent():
    total = 0
    fell_back = 0
    for w, h, rooms in SIZES:
        for kind in FLOOR_KINDS:
            for seed in SEEDS:
                total += 1
                if _floor(seed, w, h, kind, rooms)["gen"] != 3:
                    fell_back += 1
    assert total == props.SEED_COUNT * len(SIZES) * len(FLOOR_KINDS)
    assert fell_back / total < 0.005, f"{fell_back} of {total} wander floors fell back to v2"


@pytest.mark.parametrize("w, h, rooms, kind", props._cases())
def test_every_v3_property_holds(w, h, rooms, kind):
    pack = _pack(kind, rooms, "wander")
    measured = 0
    for seed in SEEDS:
        plan = _floor(seed, w, h, kind, rooms)
        if plan["gen"] != 3:
            continue
        measured += 1
        where = props._where(seed, w, h, kind)
        geom = _geometry(seed, w, h, kind, rooms)
        up = tuple(plan["anchors"]["up"])
        reach = props._flood(plan, up)
        assert reach == props._walkable_tiles(plan), f"{where}: more than one component"
        assert geom.covers_walkable, f"{where}: a carved tile is neither room nor corridor"
        for tile in props._point_tiles(plan):
            assert tile in reach, f"{where}: {tile} is not reachable"
        assert geom.main_path, f"{where}: no up -> down path"
        warden = tuple(plan["anchors"]["warden"])
        assert not geom.on_path[warden], f"{where}: the warden is on the main path"
        if geom.room_count >= 12:
            assert props._loop_count(geom) >= 2, f"{where}: fewer than two loops"
        near = len(props._within_one_step(geom)) / geom.room_count
        assert near >= 0.40, f"{where}: {near:.0%} of rooms within one step of the path"
        if plan["chests"]:
            total = sum(props._chest_value(pack, c["table"]) for c in plan["chests"])
            off = sum(props._chest_value(pack, c["table"]) for c in plan["chests"]
                      if not geom.on_path[tuple(c["at"])])
            assert off >= 0.60 * total, f"{where}: {off}/{total} chest value off the path"
    # A v2 floor is skipped above, so a case that kept almost nothing would
    # pass on nothing: the properties are only proved on floors that kept.
    assert measured >= 0.99 * len(SEEDS), (
        f"only {measured} of {len(SEEDS)} wander floors kept v3 geometry at "
        f"{w}x{h} {kind}")


@pytest.mark.parametrize("w, h, rooms, kind", props._cases()[:4])
def test_the_same_seed_draws_the_same_wander_floor(w, h, rooms, kind):
    for seed in SEEDS[:25]:
        again = delve_v3.generate_floor_v3(seed, (w, h), _pack(kind, rooms, "wander"), kind)
        assert again == _floor(seed, w, h, kind, rooms)


# ---------------------------------------------------------- what it is for


def test_no_walk_from_stair_to_stair_is_a_straight_line():
    """The spine's every walk is a straight line; no wander walk is one.

    The control is the spine itself, over a slice of the same sweep, so this
    test is known to be able to fail: on the spine it would.
    """
    straight = [key for key, plan in _swept() if _turns(_walk(plan)) == 0]
    assert not straight, f"{len(straight)} wander floors walk stair to stair in a line: {straight[:5]}"
    turns = sorted(_turns(_walk(plan)) for _key, plan in _swept())
    assert turns[len(turns) // 2] >= 6, f"the median wander walk turns {turns[len(turns) // 2]} times"

    spine_straight = 0
    for seed in SEEDS[:25]:
        plan = delve_v3.generate_floor_v3(seed, (64, 48), _pack("normal", 18, None), "normal")
        if plan["gen"] == 3 and _turns(_walk(plan)) == 0:
            spine_straight += 1
    assert spine_straight > 0, "the control: the spine is expected to walk in a line"


def test_the_stairs_stand_apart():
    for (seed, w, h, kind, _rooms), plan in _swept():
        up, down = plan["anchors"]["up"], plan["anchors"]["down"]
        apart = max(abs(up[0] - down[0]), abs(up[1] - down[1]))
        need = min(delve_v3.WANDER_APART, max(w, h) // 3)
        assert apart >= need, f"{props._where(seed, w, h, kind)}: the stairs are {apart} apart, {need} required"
