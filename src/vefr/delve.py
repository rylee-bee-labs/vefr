"""delve - the deterministic dungeon-floor generator.

The engine owns the *shape* of a generated floor; the story owns what
the floor means. `generate_floor` draws one floor from a seed using
rectangular rooms joined by L-corridors, marks the up-stair and the
down-stair, and guarantees a single connected cave with the two stairs
reachable from each other. `contract` writes the region contract.json a
generated floor needs, and `LEGEND` is the shared symbol -> tile table.

Everything here is rules-only and deterministic. The only randomness is
`random.Random(seed)` - never the global `random`, and never the clock -
so the same `(seed, width, height, rooms)` always draws the same rows.

Stair distance: `generate_floor` tries to place the down-stair at least
`MIN_STAIR_DISTANCE` (10) Manhattan tiles from the up-stair, so a floor
feels like a walk. If a layout cannot satisfy that after many tries it
relaxes to the widest pair it found rather than fail; the caller can
measure the pair it got.

Two ways in. `norns delve` still bakes floors once, at build time, from
a seed. The descent (E1) draws floors at play time instead: a pack's
`descent` block (`descent_of`) names its Sections, and `floor_plan` draws
the floor at a given depth from the run seed, keyed by
`floor_key(run_seed, section.id, cycle, k)` so each of its streams is
independent and the same run always meets the same floor. The player's
twin, web/player/parts/397-the-descent.js, draws the identical floor.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

# How far apart the two stairs should be, in Manhattan tiles. The
# generator keeps the widest pair it can find when a layout is too
# small to satisfy this.
MIN_STAIR_DISTANCE = 10

# The symbols a generated floor uses. `#` is solid; the rest are
# walkable. Every symbol points at a tile the studio's archive already
# ships (web/art/tiles/dungeon-*.webp), so a woven floor reads as stone
# instead of flat colour.
LEGEND = {
    "#": {"base": ["#20242b"], "solid": True, "tile": "dungeon-wall"},
    ".": {"base": ["#1a1d22"], "tile": "dungeon-floor"},
    "u": {"base": ["#2b2f38"], "tile": "dungeon-stairs-up"},
    "d": {"base": ["#2b2f38"], "tile": "dungeon-stairs-down"},
    # The vault door (ADR 0015) while it is shut; it opens to `.` when the
    # warden falls. Never in a plan's rows - play paints it over the door tile.
    "+": {"base": ["#3a2f24"], "solid": True, "tile": "dungeon-door"},
}

def section_legend(section) -> dict:
    """The legend of one Section's floors: the shared `LEGEND` with its `tiles` laid on top.

    A Section's `tiles` says which tileset each of the generator's own glyphs is
    drawn with (`{".": "ember-flagstone"}`), which is what makes two Sections in
    one descent draw different ground. Only a glyph the generator already draws
    is overridden, and only its `tile` is: the base colours and the `solid` flag
    are the engine's, because a floor that walked through its own wall would be
    a different generator.

    Pure, and a copy: `LEGEND` itself is never touched, so a Section with no
    `tiles` gets exactly the legend every generated floor has always had. The
    JavaScript twin is `sectionLegend` in web/player/parts/397-the-descent.js.
    """
    legend = {glyph: dict(spec) for glyph, spec in LEGEND.items()}
    tiles = section.get('tiles') if isinstance(section, dict) else None
    if not isinstance(tiles, dict):
        return legend
    for glyph in sorted(tiles, key=str):
        name = tiles[glyph]
        spec = legend.get(glyph)
        if isinstance(name, str) and name and isinstance(spec, dict):
            spec['tile'] = name
    return legend


# A generated floor is deep ground: near-black, lit only by the stairs.
BG = "#0d0f12"
HERO_COLOR = "#e8e5df"
SPEAKER_COLOR = "#8b939c"
SPEAKER_HEAD = "#d8d5df"

# How many times the stair picker samples before it relaxes the minimum.
_STAIR_ATTEMPTS = 500


def _to_int32(value: int) -> int:
    """The low 32 bits of `value`, read as JavaScript's signed 32-bit int."""
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    return value


def _imul(a: int, b: int) -> int:
    """JavaScript's `Math.imul`: a 32-bit signed multiply (low 32 bits)."""
    return _to_int32((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF))


def _ushr(value: int, bits: int) -> int:
    """JavaScript's unsigned right shift `>>>`, on a 32-bit word."""
    return (value & 0xFFFFFFFF) >> bits


def prng(seed: str):
    """A JavaScript-compatible random stream: floats in [0, 1).

    The string is hashed by its UTF-16 code units (exactly what
    JavaScript's `charCodeAt` reads, so an astral character is two
    units) with xmur3, and the resulting 32-bit state feeds mulberry32.
    Only 32-bit integer maths is used, so a JavaScript twin that runs
    the same code returns the identical stream. The returned closure is
    stateful: every call yields the next float and advances the state.
    """
    units = seed.encode("utf-16-le")
    codes = [units[i] | (units[i + 1] << 8) for i in range(0, len(units), 2)]
    h = _to_int32(1779033703 ^ len(codes))
    for code in codes:
        h = _imul(h ^ code, 3432918353)
        h = _to_int32((h << 13) | _ushr(h, 19))
    h = _imul(h ^ _ushr(h, 16), 2246822507)
    h = _imul(h ^ _ushr(h, 13), 3266489909)
    state = _to_int32(h ^ _ushr(h, 16))

    def next_float() -> float:
        nonlocal state
        state = _to_int32(state + 0x6D2B79F5)
        t = _imul(state ^ _ushr(state, 15), 1 | state)
        t = _to_int32((t + _imul(t ^ _ushr(t, 7), 61 | t)) ^ t)
        return _ushr(t ^ _ushr(t, 14), 0) / 4294967296

    return next_float


def _center(room: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, w, h = room
    return x + w // 2, y + h // 2


def _overlaps(a: tuple[int, int, int, int],
              b: tuple[int, int, int, int], pad: int) -> bool:
    """True when two room rectangles touch or sit closer than `pad`.

    Kept apart by at least one wall so rooms read as separate chambers
    instead of one merged blob.
    """
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ((ax - pad) < (bx + bw) and (bx - pad) < (ax + aw)
            and (ay - pad) < (by + bh) and (by - pad) < (ay + ah))


def _carve_room(grid: list[list[str]], room: tuple[int, int, int, int]) -> None:
    x, y, w, h = room
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            grid[yy][xx] = "."


def _carve_h(grid: list[list[str]], x0: int, x1: int, y: int) -> None:
    for x in range(min(x0, x1), max(x0, x1) + 1):
        grid[y][x] = "."


def _carve_v(grid: list[list[str]], x: int, y0: int, y1: int) -> None:
    for y in range(min(y0, y1), max(y0, y1) + 1):
        grid[y][x] = "."


def _carve_corridor(rng: random.Random, grid: list[list[str]],
                    a: tuple[int, int], b: tuple[int, int]) -> None:
    """An L-shaped corridor from `a` to `b` (order chosen at random)."""
    ax, ay = a
    bx, by = b
    if rng.random() < 0.5:
        _carve_h(grid, ax, bx, ay)
        _carve_v(grid, bx, ay, by)
    else:
        _carve_v(grid, ax, ay, by)
        _carve_h(grid, ax, bx, by)


def _place_rooms(rng: random.Random, grid: list[list[str]],
                 width: int, height: int,
                 count: int) -> list[tuple[int, int, int, int]]:
    """Carve up to `count` non-touching rooms; return the ones placed.

    A layout with little room may place fewer than `count`; the carved
    rooms are always internally connected by the caller's corridors.
    """
    placed: list[tuple[int, int, int, int]] = []
    max_w = max(3, min(9, width - 2))
    max_h = max(3, min(7, height - 2))
    for _ in range(count * 30):
        if len(placed) >= count:
            break
        w = rng.randint(3, max_w)
        h = rng.randint(3, max_h)
        x = rng.randint(1, width - 1 - w)
        y = rng.randint(1, height - 1 - h)
        room = (x, y, w, h)
        if any(_overlaps(room, other, 1) for other in placed):
            continue
        _carve_room(grid, room)
        placed.append(room)
    if not placed:
        # The interior is at least 3x3 (the caller enforces the sizes),
        # so this never fires in practice - kept so a floor always has
        # ground to stand on.
        _carve_room(grid, (1, 1, 3, 3))
        placed.append((1, 1, 3, 3))
    return placed


def _pick_stairs(rng: random.Random,
                 floors: list[tuple[int, int]]) -> tuple[tuple[int, int],
                                                         tuple[int, int]]:
    """Two distinct floor tiles for `u` and `d`.

    Samples pairs, keeping the widest; returns as soon as a pair meets
    `MIN_STAIR_DISTANCE`. A layout too small to satisfy it relaxes to
    the widest pair found.
    """
    if len(floors) < 2:
        raise ValueError("a floor needs at least two walkable tiles for stairs")
    best: tuple[tuple[int, int], tuple[int, int]] | None = None
    best_dist = -1
    for _ in range(_STAIR_ATTEMPTS):
        a, b = rng.sample(floors, 2)
        dist = abs(a[0] - b[0]) + abs(a[1] - b[1])
        if dist > best_dist:
            best, best_dist = (a, b), dist
        if dist >= MIN_STAIR_DISTANCE:
            return a, b
    assert best is not None
    return best


def _rand_range(rng, lo: int, hi: int) -> int:
    """A whole number in [lo, hi] (both inclusive) from one `prng` draw.

    Written as `lo + floor(rng() * (hi - lo + 1))` so a JavaScript twin
    using `Math.floor` gets the identical number.
    """
    return lo + int(rng() * (hi - lo + 1))


def _place_rooms_v2(rng, grid: list[list[str]], width: int, height: int,
                    count: int) -> list[tuple[int, int, int, int]]:
    """The `prng` twin of `_place_rooms`; see the v2 draw order below."""
    placed: list[tuple[int, int, int, int]] = []
    max_w = max(3, min(9, width - 2))
    max_h = max(3, min(7, height - 2))
    for _ in range(count * 30):
        if len(placed) >= count:
            break
        w = _rand_range(rng, 3, max_w)
        h = _rand_range(rng, 3, max_h)
        x = _rand_range(rng, 1, width - 1 - w)
        y = _rand_range(rng, 1, height - 1 - h)
        room = (x, y, w, h)
        if any(_overlaps(room, other, 1) for other in placed):
            continue
        _carve_room(grid, room)
        placed.append(room)
    if not placed:
        _carve_room(grid, (1, 1, 3, 3))
        placed.append((1, 1, 3, 3))
    return placed


def _carve_corridor_v2(rng, grid: list[list[str]],
                       a: tuple[int, int], b: tuple[int, int]) -> None:
    """The `prng` twin of `_carve_corridor` (one draw picks the bend)."""
    ax, ay = a
    bx, by = b
    if rng() < 0.5:
        _carve_h(grid, ax, bx, ay)
        _carve_v(grid, bx, ay, by)
    else:
        _carve_v(grid, ax, ay, by)
        _carve_h(grid, ax, bx, by)


def _pick_stairs_v2(rng,
                    floors: list[tuple[int, int]]) -> tuple[tuple[int, int],
                                                           tuple[int, int]]:
    """The `prng` twin of `_pick_stairs` (two draws pick two tiles)."""
    if len(floors) < 2:
        raise ValueError("a floor needs at least two walkable tiles for stairs")
    n = len(floors)
    best: tuple[tuple[int, int], tuple[int, int]] | None = None
    best_dist = -1
    for _ in range(_STAIR_ATTEMPTS):
        i = int(rng() * n)
        j = int(rng() * (n - 1))
        if j >= i:
            j += 1
        a, b = floors[i], floors[j]
        dist = abs(a[0] - b[0]) + abs(a[1] - b[1])
        if dist > best_dist:
            best, best_dist = (a, b), dist
        if dist >= MIN_STAIR_DISTANCE:
            return a, b
    assert best is not None
    return best


def generate_floor(seed: str, width: int = 30, height: int = 20,
                   rooms: int = 8) -> list[str]:
    """Draw one dungeon floor from `seed` as `height` rows of `width`.

    The rows use only `#` (wall), `.` (floor), `u` (up-stair) and `d`
    (down-stair). The border is solid wall; the interior is rooms joined
    by corridors, so every floor tile is reachable from every other and
    the two stairs are reachable from each other. The down-stair is
    placed at least `MIN_STAIR_DISTANCE` Manhattan tiles from the
    up-stair when the layout allows; otherwise the widest pair found is
    used (see the module docstring).

    Deterministic: `random.Random(seed)` is the only source of
    randomness, so identical inputs always return identical rows.
    Raises `ValueError` when `width` or `height` is smaller than 5 or
    `rooms` is smaller than 1.
    """
    if width < 5 or height < 5:
        raise ValueError("width and height must each be at least 5")
    if rooms < 1:
        raise ValueError("rooms must be at least 1")

    rng = random.Random(seed)
    grid = [["#"] * width for _ in range(height)]
    placed = _place_rooms(rng, grid, width, height, rooms)
    for a, b in zip(placed, placed[1:]):
        _carve_corridor(rng, grid, _center(a), _center(b))

    floors = [(x, y) for y in range(height) for x in range(width)
              if grid[y][x] == "."]
    up, down = _pick_stairs(rng, floors)
    grid[up[1]][up[0]] = "u"
    grid[down[1]][down[0]] = "d"
    return ["".join(row) for row in grid]


# generate_floor_v2 - the exact order of draws. A JavaScript twin must
# follow this line for line; `rng()` is one call of `prng(seed)`, and a
# whole number `rand(lo, hi)` is `lo + floor(rng() * (hi - lo + 1))`.
#
#  1. Validate: width and height must each be >= 5, and rooms >= 1;
#     otherwise raise ValueError (same messages as generate_floor).
#  2. rng = prng(seed). Build a `height` x `width` grid of "#".
#  3. max_w = max(3, min(9, width - 2));
#     max_h = max(3, min(7, height - 2)).
#  4. Rooms: repeat at most `rooms * 30` times, breaking early once
#     `rooms` rooms are placed. Each attempt draws, in this order:
#       w = rand(3, max_w);
#       h = rand(3, max_h);
#       x = rand(1, width - 1 - w);
#       y = rand(1, height - 1 - h).
#     The rectangle (x, y, w, h) is discarded if it overlaps any
#     already-placed room with pad 1 (no further draws that attempt);
#     otherwise carve it to "." and append it. If no room was placed,
#     carve (1, 1, 3, 3) and use that as the only room.
#  5. Corridors: for each consecutive pair of placed rooms (0->1, 1->2,
#     ..., n-2->n-1), take their centres cx = x + w // 2, cy = y + h // 2
#     (integer floor) and draw once:
#       if rng() < 0.5: carve horizontal from a.cx to b.cx at a.cy, then
#                       vertical from a.cy to b.cy at b.cx;
#       else:           carve vertical from a.cy to b.cy at a.cx, then
#                       horizontal from a.cx to b.cx at b.cy.
#     Every carve is inclusive of both endpoints and writes ".".
#  6. floors = every "." tile in row-major order: for y = 0..height-1,
#     then for x = 0..width-1.
#  7. Stairs: if len(floors) < 2 raise ValueError("a floor needs at
#     least two walkable tiles for stairs"). Otherwise repeat at most
#     _STAIR_ATTEMPTS (500) times:
#       n = len(floors);
#       i = floor(rng() * n);
#       j = floor(rng() * (n - 1));
#       if j >= i then j = j + 1            (so i != j);
#       a = floors[i]; b = floors[j];
#       dist = |a.x - b.x| + |a.y - b.y|.
#     Keep the pair with the largest dist seen so far (a strictly
#     greater dist replaces it; a tie keeps the earlier pair). Return
#     the first pair with dist >= MIN_STAIR_DISTANCE (10). If none
#     reaches it in 500 attempts, return the widest pair found.
#  8. Write "u" at the first stair and "d" at the second; return the
#     rows as strings.
def generate_floor_v2(seed: str, width: int = 30, height: int = 20,
                      rooms: int = 8) -> list[str]:
    """Draw one floor from `seed` using only the shared `prng`.

    Same shape as `generate_floor` (rooms joined by L-corridors, a solid
    wall border, one `u` and one `d` far apart when the layout allows,
    every walkable tile connected) but built entirely from `prng(seed)`,
    so a JavaScript twin draws identical rows. Raises `ValueError` for
    the same bad sizes as `generate_floor`. The draw order is the
    numbered comment above this function.
    """
    if width < 5 or height < 5:
        raise ValueError("width and height must each be at least 5")
    if rooms < 1:
        raise ValueError("rooms must be at least 1")

    rng = prng(seed)
    grid = [["#"] * width for _ in range(height)]
    placed = _place_rooms_v2(rng, grid, width, height, rooms)
    for a, b in zip(placed, placed[1:]):
        _carve_corridor_v2(rng, grid, _center(a), _center(b))

    floors = [(x, y) for y in range(height) for x in range(width)
              if grid[y][x] == "."]
    up, down = _pick_stairs_v2(rng, floors)
    grid[up[1]][up[0]] = "u"
    grid[down[1]][down[0]] = "d"
    return ["".join(row) for row in grid]


def _as_tile(value) -> tuple[int, int] | None:
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) for v in value)):
        return int(value[0]), int(value[1])
    return None


# ---- the descent: play-time floors (PLAN §2, rows E1) ----
#
# A descent is sized by minutes to play it, not by tiles. The pack's
# `descent` block names the run and the Sections; `locate` says which
# Section a depth is in; the floor for that depth is drawn here, from a
# run seed and nothing else. Everything below is pure: the same depth
# always draws the same floor, in Python and in the JavaScript twin
# beside it (web/player/parts/397-the-descent.js).

# The generation this descent draws. It rides in every floor's identity,
# in the save (so a save from a different generation is offered the
# start-over card once), and in the seed of every stream: `v3|<key>|...`.
GEN_VERSION = 4   # 4: play floors are v3 geometry (E8-0, 2026-10-09); 3 was v2 geometry
STREAM_VERSION = "v3"

# The flag a pack's story ends on unless it names another (ADR 0015
# Amendment 1, section 1). A final boss behind its own door sets this
# exactly as the ADR's own design describes; a pack that ends without one
# names `story_end` in its `descent` block and sets it with any rule.
STORY_END_FLAG = 'king-slain'

# The save budgets of PLAN §3, and the cap that keeps them.
FLOOR_CAP = 40
FLOOR_BYTES = 1_500
SAVE_BYTES = 250_000

# What a Section gets when it says nothing. Its floor size and kind come
# from `vefr.sections` (`_v3_floor`), the same numbers `vefr check` sweeps.
DEFAULT_FOG_RADIUS = 5
DEFAULT_FAMILY = "a stranger in the dark"

# A monster stands at least this far from both stairs, so arriving and
# leaving are never a fight the hero did not choose (the shipped spacing
# rule).
MOB_SPACING = 7

# The high end of "every floor", used where a family names no `depth` range.
# The Section contract caps `floors` at 11, so this covers any floor a Section
# may have; it is a default and never a bound, since a range the pack wrote is
# read exactly as written.
_FLOOR_SPAN = 99


def _range_of(section: dict, key: str, default: tuple[int, int]) -> tuple[int, int]:
    """A Section's `[lo, hi]` pair for `key`, or the engine's default."""
    value = section.get(key) if isinstance(section, dict) else None
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
            and value[0] <= value[1]):
        return int(value[0]), int(value[1])
    return default


def _floors_of(section: dict) -> int:
    value = section.get('floors') if isinstance(section, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    raise ValueError("every Section needs a whole number of floors, at least 1")


def _sections(pack) -> list[dict]:
    """The Section records a pack's descent carries, in pack order.

    Accepts the pack itself (a dict with a `descent` block), the block on
    its own, or the bare list of Sections, so a caller holding any of the
    three gets the same answer. A Section named by id rather than written
    out is refused: reading `sections/<id>.json` is the loader's job (the
    weave does it), not this function's.
    """
    block = pack
    if isinstance(pack, dict) and isinstance(pack.get('descent'), dict):
        block = pack['descent']
    listed = block.get('sections') if isinstance(block, dict) else block
    if not isinstance(listed, list) or not listed:
        raise ValueError("a descent needs a list of Sections")
    sections: list[dict] = []
    for entry in listed:
        if not isinstance(entry, dict):
            raise ValueError("every Section must be a record with an id and "
                             "its number of floors")
        if not isinstance(entry.get('id'), str) or not entry['id']:
            raise ValueError("every Section needs an id")
        sections.append(entry)
    return sections


def descent_of(pack, pack_dir=None) -> dict:
    """The pack's `descent` block, or `{}` when it declares none.

    A Section may be written out in the block or named by id and kept in
    `sections/<id>.json` beside the pack (`pack_dir`); the named ones are
    read here so every caller - the validator, the bake, the tests - sees
    the same resolved list of records.

    An id is pack data, so it goes through the same `_inside` guard
    (`cli._inside`) every other name out of a pack goes through before it
    touches the filesystem: an id like `../x` or `/etc/x` is refused in a
    sentence rather than read and baked.
    """
    block = pack.get('descent') if isinstance(pack, dict) else None
    if not isinstance(block, dict):
        return {}
    listed = block.get('sections')
    if not isinstance(listed, list):
        return block
    from .cli import _inside  # here, not at the top: cli imports this module

    base = os.path.realpath(str(pack_dir)) if pack_dir is not None else None
    sections = []
    for entry in listed:
        if not isinstance(entry, str):
            sections.append(entry)
            continue
        where = f'sections/{entry}.json'
        if base is None:
            raise ValueError(f"the Section {entry!r} is named but there is "
                             f"no pack to read {where} from")
        target = _inside(base, 'sections', f'{entry}.json')
        if target is None:
            raise ValueError(f"the Section {entry!r} is named but {where} "
                             f"would leave the pack")
        try:
            data = json.loads(Path(target).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise ValueError(f"the Section {entry!r} is named but "
                             f"{where} could not be read")
        if not isinstance(data, dict):
            raise ValueError(f"{where} must be a Section record")
        sections.append({'id': entry, **data})
    return {**block, 'sections': sections}


# ---- town states (ADR 0015 "Town states", Amendment 1 section 3) ---------
#
# A pack names the regions whose look follows a story flag: the town, an
# interior such as a tavern or a home. Each `use` is an ordinary authored
# region, baked as every other region is - there is no patch and no new
# runtime language here - and the state is DERIVED on each entry from the
# flags then true, never stored. A pack writes one block for one region
# (ADR 0015) or a list of them, one per region (Amendment 1); both are
# read here into the same list of `{region, states}` blocks.


def town_states_of(pack) -> list[dict]:
    """The pack's town-state blocks, one per region, in pack order.

    Both shapes are one list: the single block ADR 0015 writes is a list
    of one. A pack that names none gets `[]`, and every caller treats that
    as "no region changes" - the behaviour of every pack before E8c."""
    raw = pack.get('town_states') if isinstance(pack, dict) else None
    listed = raw if isinstance(raw, list) else [raw]
    return [entry for entry in listed
            if isinstance(entry, dict) and isinstance(entry.get('region'), str)
            and entry['region']]


def town_state_of(blocks, region: str, flags) -> str:
    """Which region a player actually loads on entering `region`.

    The LAST state whose `when` flag reads true wins, so a pack writes its
    states oldest first and the newest truth is the one that shows. With
    no true flag - or no block for this region at all - the region's own
    base loads, which is what a pack with no `town_states` always gets.

    Derived, never stored: the same flags always give the same answer, and
    a flag the player has never set can never have left a state behind."""
    truth = flags if isinstance(flags, dict) else {}
    for block in blocks if isinstance(blocks, (list, tuple)) else []:
        if not isinstance(block, dict) or block.get('region') != region:
            continue
        chosen = region
        for state in block.get('states') or []:
            if not isinstance(state, dict):
                continue
            when, use = state.get('when'), state.get('use')
            if isinstance(when, str) and when and truth.get(when) is True \
                    and isinstance(use, str) and use:
                chosen = use
        return chosen
    return region


def locate(depth: int, pack) -> tuple[int, dict, int]:
    """Where a depth leads: `(cycle, section, k)`, and nothing else.

    The story is cycle 0: depth 1 is the first floor of the first Section,
    and the Sections are walked in pack order. Past the last floor of the
    last Section the descent begins again in cycle 1, the Sections in the
    same order, so a descent is endless without any of it being special.

    Pure: the answer is read off the pack's Section list and the depth
    alone. A depth below 1, or a pack with no Sections, is refused rather
    than guessed at.
    """
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
        raise ValueError("depth must be a whole number of at least 1")
    sections = _sections(pack)
    counts = [_floors_of(s) for s in sections]
    cycle, within = divmod(depth - 1, sum(counts))
    for section, count in zip(sections, counts):
        if within < count:
            return cycle, section, within + 1
        within -= count
    raise ValueError("depth is outside this descent")   # unreachable


def floor_name(section_id: str, cycle: int, k: int) -> str:
    """The region name a floor plays under: stable across reloads.

    The name says where the floor is in the descent and nothing about
    which run drew it, so two runs reuse the names and the identity
    triple - not the name - is what tells their floors apart.
    """
    return f'{section_id}-{cycle}-{k}'


def floor_key(run_seed: str, section_id: str, cycle: int, k: int) -> str:
    """The key every one of a floor's streams is seeded from."""
    return f'{run_seed}/{section_id}/{cycle}/{k}'


def stream_seed(key: str, stream: str) -> str:
    """One named stream of one floor: `v3|<floor key>|<stream>`.

    A separate stream per stage, so changing what a floor carries - an
    affix table, a loot roll, a chest - can never move a wall (PLAN §8's
    sub-seed rule).
    """
    return f'{STREAM_VERSION}|{key}|{stream}'


def loot_seed(key: str, mob_id: str) -> str:
    """A monster's own loot stream: the kill order cannot change a drop."""
    return stream_seed(key, f'loot|{mob_id}')


def chest_seed(key: str, chest_id: str) -> str:
    """A chest's own stream, for the day the chest is opened."""
    return stream_seed(key, f'chest|{chest_id}')


def roll_seed(key: str, mob_id: str, item_id: str) -> str:
    """One drawn item's own roll stream (ADR 0017).

    A named stream off the same floor key and the same monster the base
    draw came from, so the rarity and the hidden traits cannot move when
    the base id moves, two monsters cannot share a roll, and the order
    monsters are killed in cannot change what any of them drop. The item
    id is in the name, so a monster that could carry two rolled things
    gives each its own stream rather than one shared draw.
    """
    return stream_seed(key, f'roll|{mob_id}|{item_id}')


def run_seed(base: str, run: int = 0) -> str:
    """The run seed of a run: the pack's own for the first, counted after."""
    run = 0 if not isinstance(run, int) or isinstance(run, bool) else max(0, run)
    return base if run == 0 else f'{base}/run-{run}'


def _canonical(value) -> str:
    """A Section's content as the bytes both languages hash.

    Keys in order, no spaces, and a number written the way both languages
    write one: a whole number as a whole number, anything else in its
    shortest round-trip form. Every key of a record is written, including
    one whose value is null - which is what makes two Sections that differ
    only in a null and an absent key hash differently, as they should.
    The JavaScript twin (web/player/parts/397-the-descent.js) has the same
    function, and the parity harness is what proves they agree.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonical(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value, key=str):
            parts.append(json.dumps(str(key), ensure_ascii=False) + ":"
                         + _canonical(value[key]))
        return "{" + ",".join(parts) + "}"
    return "null"


def _hash12(text: str) -> str:
    """Two 32-bit FNV-style lanes over the UTF-8 bytes, as twelve hex.

    Small, exact and identical in both languages, which is all a digest
    has to be: the only question asked of it is "is this the same Section
    as last time?".
    """
    h1 = 2166136261
    h2 = 3335557771
    for i, byte in enumerate(text.encode("utf-8")):
        h1 = ((h1 ^ byte) * 16777619) & 0xFFFFFFFF
        h2 = ((h2 ^ ((byte + i) & 255)) * 2246822519) & 0xFFFFFFFF
    return f"{h1:08x}{h2:08x}"[:12]


def section_hash(section: dict, stamps=None) -> str:
    """A short, stable digest of a Section's own content, and of the pack's stamps.

    Half of a floor's identity. Editing a Section changes the hash, which
    is how a save learns that the floor it remembers is no longer the
    floor it would draw. Since stamps reach play (2026-10-09) a stamp edit
    redraws floors too, so a pack that has stamps hashes them with the
    Section; a pack with none hashes exactly as it always did.
    """
    if stamps:
        return _hash12(_canonical({'section': section, 'stamps': stamps}))
    return _hash12(_canonical(section))


def stamps_of(descent) -> list:
    """The pack's stamp records the weave carries in the descent block, or []."""
    block = descent.get('descent') if isinstance(descent, dict) and isinstance(descent.get('descent'), dict) \
        else descent
    found = block.get('stamps') if isinstance(block, dict) else None
    return [r for r in found if isinstance(r, dict)] if isinstance(found, list) else []


def _run_seed_of(descent, run: int) -> str:
    block = descent
    if isinstance(descent, dict) and isinstance(descent.get('descent'), dict):
        block = descent['descent']
    base = block.get('run_seed') if isinstance(block, dict) else None
    if not isinstance(base, str) or not base:
        raise ValueError("a descent needs a run seed")
    return run_seed(base, run)


def floor_identity(descent, depth: int, run: int = 0) -> dict:
    """`(gen, section hash, floor key)`: what makes this floor this floor."""
    cycle, section, k = locate(depth, descent)
    key = floor_key(_run_seed_of(descent, run), section['id'], cycle, k)
    return {'gen': GEN_VERSION, 'hash': section_hash(section, stamps_of(descent)), 'key': key}


def item_draw(key: str, mob_id: str, item_id: str, entry) -> dict | str:
    """The drop one drawn item is (ADR 0017).

    A plain id when the pack fixed the thing and the pack said nothing
    else about it - which is what every pack before this slice gets, so
    every drop before this slice is the same string it was. Otherwise a
    record the bag keeps as it is:

        {'item': id, 'rarity': name, 'traits': [...], 'identified': False}

    A pack that declares only a `rarity` or `traits` beside an item gets
    those fixed - no draw, because there is no table to draw from - and
    still gets an instance that says they are not identified yet. A pack
    that declares a `roll` gets one draw on `v3|<key>|roll|<mob id>|<item
    id>`: the rarity first, by the table's own weights, then the traits -
    one question of whether it bears any at all (`chance` in 100), then
    how many (`max`), then which, each drawn once from what is left.
    Every one of those is `int(rng() * n)` with an `n` the pack's own
    whole numbers built, so the draw is the same in Python and in the
    JavaScript twin and holds in both directions.

    `identified` is False on every rolled instance because the reveal is
    the next slice: nothing here decides that a thing has been read, it
    only refuses to pretend one has.
    """
    from .maplab import item_rarity_of, item_roll_of, item_traits_of

    entry = entry if isinstance(entry, dict) else {}
    roll = item_roll_of(entry)
    fixed_rarity = item_rarity_of(entry)
    fixed_traits = item_traits_of(entry)
    if not roll:
        if not fixed_rarity and not fixed_traits:
            return item_id
        return {'item': item_id, 'rarity': fixed_rarity,
                'traits': list(fixed_traits), 'identified': False}
    rng = prng(roll_seed(key, mob_id, item_id))
    rarity = _weighted(rng, roll['rarity'])
    return {'item': item_id, 'rarity': rarity,
            'traits': _trait_draw(rng, roll), 'identified': False}


def _weighted(rng, table: list) -> str:
    """One name off a `[(name, weight)]` table: `int(rng() * total)` and a
    walk down the weights, so the draw is a single floor of a single
    stream and no float is compared with another."""
    total = sum(weight for _, weight in table)
    pick = int(rng() * total)
    upto = 0
    for name, weight in table:
        upto += weight
        if pick < upto:
            return name
    return table[-1][0]


def _trait_draw(rng, roll: dict) -> list:
    """The hidden traits one rolled item carries, in draw order.

    One question whether it bears any (`chance` in 100), then how many
    (1..`max`), then that many distinct words from the pool, each by
    `int(rng() * len(left))` over what is left - so two traits never come
    back the same word, and the same seed always draws the same two.
    """
    pool = list(roll['traits'])
    top = roll['max']
    if top < 1 or int(rng() * 100) >= roll['chance']:
        return []
    want = min(1 + int(rng() * top), len(pool))
    out: list[str] = []
    for _ in range(want):
        out.append(pool.pop(int(rng() * len(pool))))
    return out


def mob_drops(key: str, mob_id: str, table, catalog=None) -> list:
    """What one monster carries, drawn from that monster's own stream.

    `table` is the monster family's list of drop ids. One draw off
    `v3|<key>|loot|<mob id>`, so two monsters never share a roll and the
    order monsters are killed in cannot change what they drop.

    `catalog` is the pack's item catalog, which is where an item's `roll`
    is read from - the same map `VEFR_ITEMS` is in the woven player, and
    the same one the JavaScript twin reads. It is optional and defaults to
    None, so every caller written before ADR 0017 - and every pack that
    declares no `roll` - gets back the same list of bare ids it always
    did. With a catalog, an entry that has a `roll` (or a fixed rarity or
    traits) comes back as that item's instance record instead; see
    `item_draw` for the draw and for why the two shapes coexist.
    """
    ids = [i for i in table if isinstance(i, str) and i] if isinstance(table, list) else []
    if not ids:
        return []
    rng = prng(loot_seed(key, mob_id))
    chosen = ids[int(rng() * len(ids))]
    if not isinstance(catalog, dict):
        return [chosen]
    return [item_draw(key, mob_id, chosen, catalog.get(chosen))]


def _stairs_of(rows: list[str]) -> tuple[tuple[int, int], tuple[int, int]]:
    up = down = None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == 'u' and up is None:
                up = (x, y)
            elif ch == 'd' and down is None:
                down = (x, y)
    if up is None or down is None:
        raise ValueError("the generator drew no stairs")
    return up, down


def family_base(source, family_id) -> dict | None:
    """One Blueprint family's base record by id, or None.

    A Section names a Blueprint family by id and carries no record of its
    own (ADR 0014), so a play-time floor asks the Blueprint for the base
    rather than inventing one at the engine's floor of 1. The work is
    `vefr.blueprint.resolve_family`'s - the `extends` chain, the
    whole-value merge, the three refusals - and every refusal is None here:
    a family the Blueprint does not have is the validator's sentence
    (`/families/0/family`), so a floor that met one lays the floor anyway
    with no base rather than raising from inside a play-time sweep.
    """
    if not isinstance(source, dict) or not isinstance(family_id, str):
        return None
    from . import blueprint  # here, not at the top: blueprint imports cli

    try:
        return blueprint.resolve_family(source, family_id)
    except blueprint.BlueprintError:
        return None


def blueprint_of(pack_dir) -> dict:
    """The pack's Blueprint family declarations, or `{}`.

    The slice the descent reads and the bake writes into the descent
    block: the `families` object and nothing else, because a family's
    `extends` chain is the whole of what a floor resolves and a
    Blueprint's regions and things are none of its business. A pack with
    no `blueprint.json` has no families to resolve and its floors draw at
    the engine's own floor of 1, which is the same answer the validator's
    "this pack has no Blueprint" gives. The name is the module's own
    constant, not pack data, so there is nothing here to guard.
    """
    if pack_dir is None:
        return {}
    from . import blueprint

    path = Path(str(pack_dir)) / blueprint.BLUEPRINT_FILE
    if not path.is_file():
        return {}
    try:
        source = blueprint.read(path)
    except blueprint.BlueprintError:
        return {}
    families = source.get('families') if isinstance(source, dict) else None
    return {'families': families} if isinstance(families, dict) else {}


def _families_of(section: dict, source=None) -> list[dict]:
    """The Section's families with each family's base attached, sorted by
    family id: a draw may not depend on the order the pack wrote them in.

    A Section names a Blueprint family by id and carries no record of its
    own (ADR 0014), so the base - `hp`, `atk`, `sight`, `drops`, `name` -
    is resolved through `vefr.blueprint.resolve_family` and the Section's
    own keys win over it. That merge is `vefr.sections.families`'s, the
    one the validator and the generator already share, so a floor cannot
    come out with a family the check would not have accepted. An entry
    with no base still draws; its stats come back at `mobs_at`'s own floor
    of 1, which is the answer for a base that says nothing.
    """
    from . import sections  # here, not at the top: sections imports this module

    def resolve(family_id):
        return family_base(source, family_id) if source else None

    families = [f for f in sections.families(section, resolve)
                if isinstance(f.get('family'), str) and f['family']]
    return sorted(families, key=lambda f: f['family'])


def _hp_range(family: dict) -> tuple[int, int]:
    """A family's health as a range, for the one draw that spends it.

    A Blueprint base is one whole number - `hp: 4` is four hit points,
    every floor - while a Section or a hand-built descent may write a
    `[lo, hi]` pair. Either way the range is closed and the draw happens,
    because the stream's shape is the floor key's, not a family's.
    """
    value = family.get('hp')
    if isinstance(value, int) and not isinstance(value, bool):
        return value, value
    return _range_of(family, 'hp', (1, 1))


def _mob_budget(rows: list[str], section: dict | None = None,
                k: int = 1) -> int:
    """How many randoms this floor carries.

    Two answers and one place (`delve_v3.mob_budget`, the same function the
    v3 pop stage calls): the count the Section's own `mobs` table names for
    floor `k`, or - for a Section that names none for it, which is every
    Section written before vefr#357 - the area budget, one monster slot per
    `TILES_PER_MOB` walkable tiles clamped into `MOBS_MIN..MOBS_MAX` (PLAN.md
    section 2, step 4, "randoms by area budget"). The budget is not a draw
    either way.

    `rows` is counted here rather than handed over, because this floor's
    walkable tiles are counted off the rows it drew - `delve_v3` counts the
    canvas it carved - and each counts what it has always counted.
    """
    from . import delve_v3  # here, not at the top: delve_v3 imports this module

    walkable = sum(row.count('.') for row in rows)
    return delve_v3.mob_budget(section if isinstance(section, dict) else {},
                              walkable, k)


def _family_on_floor(family: dict, k: int) -> bool:
    """Whether a Section's family entry is drawn on floor `k` of its Section.

    A family may write a `depth` range - `[7, 9]` for a family meant for the
    last three floors of a nine-floor Section - and a range that is not read
    is a family on every floor of the Section, which is what the range was
    written to stop. `k` is the floor's own 1-based position inside the
    Section, not the global depth: the range is the Section's, and the two
    Sections of a descent each count from their own first floor.

    An entry with no `depth`, or one that is not a `[lo, hi]` pair of whole
    numbers, is on every floor: `vefr check` is what says such a range out
    loud. No draw is spent either way, so honouring it moves no other monster.
    """
    lo, hi = _range_of(family, 'depth', (1, _FLOOR_SPAN))
    return lo <= k <= hi


def mobs_at(key: str, section: dict, rows: list[str], up: tuple[int, int],
            down: tuple[int, int], source=None, catalog=None,
            k: int = 1, depth: int = 1) -> list[dict]:
    """Who lives on this floor, drawn from `v3|<key>|pop`.

    A floor's monsters are placed on floor tiles at least `MOB_SPACING`
    from both stairs, one per tile, in a fixed order: the count first,
    then for each monster its tile, its family, its health, its reach and
    its drops (the drops from that monster's own loot stream). The count
    is `_mob_budget` - the Section's own `mobs` for this floor where it
    names one, the area budget otherwise - and costs no draw, so a floor's
    size decides how full it is for every Section that names no count. A
    floor too small to hold them all carries as many as fit, never fewer
    than none. `k` is the floor's 1-based position in its Section, which
    is what the `mobs` table is read against and what a family's `depth`
    range is read against; `source` is the descent's Blueprint: the
    families are resolved through it, so a monster carries the stats its
    family id names rather than the floor of 1 a bare Section entry gives.
    `catalog` is the pack's item catalog, where an item's `roll` is read
    from (ADR 0017); with none, every drop is the bare id it was before
    this argument existed.

    Every monster carries an `xp`, so a kill pays: the family's own when
    it declares one, and `vefr.sections.xp_for`'s documented default off
    the floor's `depth` when it does not. It is read after the last draw
    and consumes none, so the floor's monsters, tiles and drops are
    exactly the ones a floor without this line drew.
    """
    from . import sections  # here, not at the top: sections imports this module

    rng = prng(stream_seed(key, 'pop'))
    count = _mob_budget(rows, section, k)
    families = [f for f in _families_of(section, source)
                if _family_on_floor(f, k)]
    pool: list[dict] = []
    for family in families:
        weight = family.get('weight')
        weight = weight if isinstance(weight, int) and not isinstance(weight, bool) \
            and 0 < weight <= 99 else 1
        pool.extend([family] * weight)
    candidates = [(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row)
                  if ch == '.' and abs(x - up[0]) + abs(y - up[1]) >= MOB_SPACING
                  and abs(x - down[0]) + abs(y - down[1]) >= MOB_SPACING]
    mobs: list[dict] = []
    for i in range(count):
        if not candidates or not pool:
            break
        at = candidates.pop(int(rng() * len(candidates)))
        family = pool[int(rng() * len(pool))]
        hp_lo, hp_hi = _hp_range(family)
        hp = _rand_range(rng, max(1, hp_lo), max(1, hp_hi))
        atk = family.get('atk')
        atk = atk if isinstance(atk, int) and not isinstance(atk, bool) else 1
        sight = family.get('sight')
        sight = sight if isinstance(sight, int) and not isinstance(sight, bool) else 6
        drops = family.get('drops')
        mobs.append({
            'id': f'm{i}', 'family': family['family'],
            'name': family.get('name') or DEFAULT_FAMILY,
            'at': [at[0], at[1]], 'hp': max(1, hp), 'atk': max(1, atk),
            'sight': max(1, sight),
            'xp': sections.xp_for(family, depth),
            'drops': mob_drops(key, f'm{i}', drops, catalog),
        })
    return mobs


# A library book pinned to a generated floor names WHERE on it to lie, not a
# tile: the floor is redrawn every run ("New descent") and whenever its
# Section changes, so a fixed tile can land in a wall. `place_books` chooses
# the tile from the floor itself - reachable ground, off the stairs and the
# monsters, one book per tile - from the floor's own `book|<id>` stream, so a
# run always shows a book in the same place and a new run moves it. The
# JavaScript twin is `placeBooks` in the descent part; the parity harness
# holds them equal.
# `vault-note` and `vault-chest` pin a book to the warden floor's vault (ADR 0015, E8b): the note and the
# chest the vault stamp names, a fixed tile rather than a draw, so they move no other book.
VAULT_PLACES = {"vault-note": "note", "vault-chest": "chest"}
BOOK_PLACES = ("near-up", "near-down", "anywhere", "vault-note", "vault-chest")
BOOK_NEAR = (2, 6)          # steps from the stair: near, but never on it


def _floor_distances(rows: list, start) -> dict:
    """Steps from `start` to every tile joined to it by floor (4-neighbour)."""
    h, w = len(rows), len(rows[0]) if rows else 0
    start = (start[0], start[1])
    dist = {start: 0}
    queue = [start]
    i = 0
    while i < len(queue):
        x, y = queue[i]
        i += 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= ny < h and 0 <= nx < w and rows[ny][nx] != "#" and (nx, ny) not in dist:
                dist[(nx, ny)] = dist[(x, y)] + 1
                queue.append((nx, ny))
    return dist


def place_books(plan: dict, books: list) -> dict:
    """`{book id: [x, y]}` for the books pinned to this floor, this run.

    `books` is `[{"id", "place"}]`. Books are placed in id order, each on a
    tile no earlier book, stair or monster holds. `near-up` and `near-down`
    want 2 to 6 steps from that stair; `anywhere` wants at least 2 from the
    up stair. A floor with no such tile falls back to anywhere reachable,
    and a book with no tile at all is left out (the validator says so).
    """
    rows = plan["rows"]
    up = tuple(plan["anchors"]["up"])
    down = tuple(plan["anchors"]["down"])
    from_up = _floor_distances(rows, up)
    from_down = _floor_distances(rows, down)
    taken = {up, down} | {tuple(m["at"]) for m in plan.get("mobs") or []}
    # The vault's own tiles are never a drawn book's, so a vault book (or none) moves no other book.
    vault = plan.get("vault") or {}
    reserved = {tuple(vault[k]) for k in ("door", "note", "chest", "home") if vault.get(k)}
    taken |= reserved
    lo, hi = BOOK_NEAR
    out = {}
    for book in sorted(books, key=lambda b: b["id"]):
        def free(t):
            return t not in taken and t in from_up and rows[t[1]][t[0]] == "."

        def within(dist, low, high):
            return [t for t, n in dist.items() if n >= low and (high is None or n <= high) and free(t)]

        place = book.get("place")
        if place in VAULT_PLACES:
            spot = vault.get(VAULT_PLACES[place])
            if spot and tuple(spot) in reserved:
                reserved.discard(tuple(spot))          # one book per vault tile
                out[book["id"]] = [spot[0], spot[1]]
            continue
        tiles = (within(from_up, lo, hi) if place == "near-up"
                 else within(from_down, lo, hi) if place == "near-down" else [])
        if not tiles:
            tiles = within(from_up, lo, None)
        if not tiles:
            tiles = within(from_up, 0, None)
        if not tiles:
            continue
        tiles.sort(key=lambda t: (t[1], t[0]))
        rng = prng(stream_seed(plan["key"], "book|" + book["id"]))
        pick = tiles[int(rng() * len(tiles))]
        taken.add(pick)
        out[book["id"]] = [pick[0], pick[1]]
    return out


# ---- the Section's warden (ADR 0015, E8a part 1) ---------------------------
# A Section names its warden's Blueprint family (`"warden": "cellar-king"`), and
# the warden floor (the pattern's `warden` slot) puts it on the v3 warden anchor
# as monster `w`, outside the area budget. Defeating it sets the permanent story
# flag `warden:<id>:c<cycle>`; a warden whose flag is set is not spawned again,
# so a town return cannot revive it. A record-form warden (ADR 0015) may name the
# key it `carries` into the bag when beaten; `yields` is E8d's.
WARDEN_MOB = 'w'


def warden_of(section: dict) -> dict | None:
    """The Section's warden as `{id, family}` (plus `carries`), or None when it names none.

    A Section writes its warden as the family id (`"cellar-king"`), or as a record (ADR 0015) naming the
    family, optionally its own `id` (the flag's middle, defaulting to the family) and the key it `carries`."""
    raw = section.get('warden') if isinstance(section, dict) else None
    if isinstance(raw, str) and raw:
        return {'id': raw, 'family': raw}
    if isinstance(raw, dict) and isinstance(raw.get('family'), str) and raw['family']:
        rid = raw.get('id')
        out = {'id': rid if isinstance(rid, str) and rid else raw['family'], 'family': raw['family']}
        if isinstance(raw.get('carries'), str) and raw['carries']:
            out['carries'] = raw['carries']
        return out
    return None


def warden_flag(warden_id: str, cycle: int) -> str:
    """The story flag a defeated warden sets: `warden:<id>:c<cycle>` (ADR 0015)."""
    return f'warden:{warden_id}:c{cycle}'


# ---- the vault's story flag, the town gate and the act (ADR 0015, E8c) ----
#
# A Section's vault may name the flag its note sets, as a record
# `{"stamp": ..., "sets": ...}`; the bare string E8b shipped is a stamp id
# and names no flag, and a Section with no flag has no gate. The flag is
# the guard ADR 0015 gives the town gate: a town visit only counts once
# the Section's note has been read, so a player cannot rush the gate by
# walking through town once on the way past.
TOWN_SEEN = 'town-seen:{section}:c{cycle}'


def vault_of(section: dict) -> dict | None:
    """The Section's vault as `{stamp, sets}`, or None when it names none.

    `sets` is the flag the vault's note records; it is `None` for the bare
    stamp id E8b shipped, which is the whole of that Section's vault as
    far as this engine is concerned."""
    raw = section.get('vault') if isinstance(section, dict) else None
    if isinstance(raw, str) and raw:
        return {'stamp': raw, 'sets': None}
    if isinstance(raw, dict) and isinstance(raw.get('stamp'), str) and raw['stamp']:
        sets = raw.get('sets')
        return {'stamp': raw['stamp'],
                'sets': sets if isinstance(sets, str) and sets else None}
    return None


def vault_flag(section: dict) -> str | None:
    """The flag a Section's vault note sets, or None when it names none."""
    vault = vault_of(section)
    return vault['sets'] if vault else None


def town_seen_flag(section_id: str, cycle: int) -> str:
    """The gate flag a town visit sets: `town-seen:<section>:c<cycle>` (ADR 0015)."""
    return TOWN_SEEN.format(section=section_id, cycle=cycle)


def story_end_of(descent) -> str:
    """The flag that ends this pack's story: its `story_end`, or the default.

    ADR 0015 Amendment 1 section 1 made the story end a per-game flag
    because a pack need not end on a final boss. `king-slain` is the
    default and is what a pack that names nothing gets, so a final boss
    behind its own door keeps working exactly as the ADR describes."""
    block = descent
    if isinstance(block, dict) and isinstance(block.get('descent'), dict):
        block = block['descent']
    value = block.get('story_end') if isinstance(block, dict) else None
    return value if isinstance(value, str) and value else STORY_END_FLAG


def board_open(descent, flags) -> bool:
    """Whether this game may go past its story: is `story_end` true?

    ADR 0015 Amendment 1 section 1: "Endless mode opens on `story_end`."
    E8c wrote the flag (`story_end_of`) and this is the one question that
    was left for the endless slice to ask: a depth past the story is
    `vefr.sections.cycle_locate`'s business and a floor that may be
    walked is this one's, so a hero who has not killed the King is still
    on the story's last cycle however deep a depth says they are.

    A flag set to anything but `True` is not set - the same reading
    `act_number` gives every other story flag, so one save is read the
    same way by every function that asks it a question.
    """
    truth = flags if isinstance(flags, dict) else {}
    return truth.get(story_end_of(descent)) is True


def act_number(sections, flags) -> int:
    """The act a set of story flags puts the story in: one plus its vaults.

    ADR 0015 rescopes ADR 0006's act advance to the town: the act is a
    derived read, never a stored pointer, and it is one plus the number of
    vault notes the player has actually read. `sections` is the descent's
    own list, because the vault flags are the Sections' to name."""
    truth = flags if isinstance(flags, dict) else {}
    return 1 + sum(1 for flag in vault_flags_of(sections)
                   if truth.get(flag) is True)


def vault_flags_of(sections) -> list[str]:
    """Every story vault flag a list of Sections names, in Section order.

    First-seen order kept, and never a set: `act_number` counts and the
    progress walk reads it, and a flag two Sections share is one flag."""
    out: list[str] = []
    for section in sections if isinstance(sections, (list, tuple)) else []:
        flag = vault_flag(section)
        if flag and flag not in out:
            out.append(flag)
    return out


def _warden_record(section: dict, k: int, cycle: int, at) -> dict | None:
    from . import sections  # here, not at the top: sections imports this module

    warden = warden_of(section)
    if warden is None or at is None or sections.slot(section, k) != 'warden':
        return None
    record = {'id': warden['id'], 'flag': warden_flag(warden['id'], cycle)}
    if 'carries' in warden:
        record['carries'] = warden['carries']
    return record


def _with_warden(mobs: list, key: str, section: dict, k: int, at, source,
                 catalog=None, depth: int = 1) -> list:
    """The floor's monsters, plus its warden on the warden anchor when this is the warden floor.

    The warden's stats are its family's, its health drawn on its own `warden` stream and its drops on
    its own loot stream, so adding it moves no other monster; a random monster that drew the anchor tile
    gives it up. Its `xp` is `vefr.sections.xp_for`'s, the same line every other
    monster on the floor takes: a warden that pays nothing is the deepest
    monster on the floor paying nothing."""
    from . import sections  # here, not at the top: sections imports this module

    if _warden_record(section, k, 0, at) is None:
        return mobs
    family = warden_of(section)['family']
    base = family_base(source, family) if source else None
    base = base if isinstance(base, dict) else {}
    rng = prng(stream_seed(key, 'warden'))
    hp_lo, hp_hi = _hp_range(base)
    hp = _rand_range(rng, max(1, hp_lo), max(1, hp_hi))
    atk = base.get('atk')
    atk = atk if isinstance(atk, int) and not isinstance(atk, bool) else 1
    sight = base.get('sight')
    sight = sight if isinstance(sight, int) and not isinstance(sight, bool) else 6
    tile = [int(at[0]), int(at[1])]
    kept = [m for m in mobs if m['at'] != tile]
    return kept + [{
        'id': WARDEN_MOB, 'family': family,
        'name': base.get('name') or DEFAULT_FAMILY,
        'at': tile, 'hp': max(1, hp), 'atk': max(1, atk), 'sight': max(1, sight),
        'xp': sections.xp_for(base, depth),
        'drops': mob_drops(key, WARDEN_MOB, base.get('drops'), catalog),
        'warden': True,
    }]


def _vault_record(floor: dict, section: dict, k: int, cycle: int) -> dict | None:
    """The warden floor's vault (ADR 0015), or None: the placed vault stamp's door - the socket its
    corridor came in through - and its note, chest and home anchors, with the flag that opens the door.

    The door is shut until the Section's warden is beaten (`flag`); a Section with no warden has an open
    vault (`flag` None). `sets` is the flag the vault's NOTE records - the guard ADR 0015 puts on the town
    gate, and None for the bare stamp id E8b shipped. Only the warden floor's vault is the vault; a vault
    stamp elsewhere is a room."""
    from . import sections  # here, not at the top: sections imports this module

    if sections.slot(section, k) != 'warden':
        return None
    placement = next((p for p in floor.get('stamps') or [] if p.get('role') == 'vault'), None)
    if placement is None:
        return None
    anchors = placement.get('anchors') or {}
    warden = warden_of(section)
    return {'stamp': placement['id'], 'door': _tile_or_none(placement.get('socket')),
            'note': _tile_or_none(anchors.get('note')), 'chest': _tile_or_none(anchors.get('chest')),
            'home': _tile_or_none(anchors.get('home')),
            'flag': warden_flag(warden['id'], cycle) if warden else None,
            'sets': vault_flag(section)}


def _tile_or_none(value):
    return [int(value[0]), int(value[1])] if isinstance(value, (list, tuple)) and len(value) == 2 else None


def _v3_floor(run_seed: str, section: dict, cycle: int, k: int, key: str, stamps=()) -> dict:
    """The v3 floor play draws: the same call `vefr check` sweeps (locks.py), so every floor a player
    can reach is one the check has walked. Size and kind come from the Section (`sections.floor_size`,
    `sections.floor_kind`); a kind outside the generator's four is drawn as `normal` rather than
    raising mid-descent (the check refuses such a pack). `stamps` are the pack's records, as the weave
    carries them in the descent block (`stamps_of`) and as `vefr check` loads them.
    Python and the descent part's twin must agree (tests/fixtures/descent_parity_harness.mjs)."""
    from vefr import delve_v3, sections   # both import this module
    size = sections.floor_size(section, key)
    kind = sections.floor_kind(section, k, run_seed, cycle)
    if kind not in delve_v3.FLOOR_KINDS:
        kind = 'normal'
    floor = delve_v3.generate_floor_v3(run_seed, size, section, kind, list(stamps), k, cycle=cycle)
    return {**floor, 'kind': kind}


def floor_plan(descent, depth: int, run: int = 0, catalog=None) -> dict:
    """The whole floor at `depth`, JSON-able and drawn from the run seed.

    The plan stream says how big the floor is, the layout stream carves
    it, and the pop stream fills it - three streams that never share a
    draw. The identity triple rides along so the save can tell this floor
    from the floor it drew last time. The descent's `blueprint` is the
    families' own records, so the monsters it fills the floor with carry
    the stats their ids name. The floor's `legend` is its own Section's
    (`section_legend`), so two Sections in one descent draw different ground.

    `catalog` is the pack's `items` map, which is where a drop's `roll`
    is read from (ADR 0017). It is optional and defaults to None, so every
    caller written before that argument - the validator, the guides, the
    parity harness - gets a floor whose drops are the bare ids they were.
    """
    cycle, section, k = locate(depth, descent)
    run_seed = _run_seed_of(descent, run)
    key = floor_key(run_seed, section['id'], cycle, k)
    stamps = stamps_of(descent)
    floor = _v3_floor(run_seed, section, cycle, k, key, stamps)
    rows = list(floor['rows'])
    up, down = _stairs_of(rows)
    fog = section.get('fog')
    radius = fog.get('radius') if isinstance(fog, dict) else None
    radius = radius if isinstance(radius, int) and not isinstance(radius, bool) \
        else DEFAULT_FOG_RADIUS
    block_fog = {'radius': max(1, radius)}
    # `shape` rides along only when it is not the default circle. The
    # block `shapes.FOG` is the door that lets a pack name `"square"`;
    # here the only value carried is that one, so a Section that says
    # nothing, and one that says `"circle"`, produce the very same floor
    # record - the same bytes in the save, in the floor digest and in the
    # parity harness. The player reads a missing shape as a circle
    # (`fogShape`, in `450-fog-of-war.js`).
    if isinstance(fog, dict) and fog.get('shape') == 'square':
        block_fog['shape'] = 'square'
    block = descent
    if isinstance(descent, dict) and isinstance(descent.get('descent'), dict):
        block = descent['descent']
    source = block.get('blueprint') if isinstance(block, dict) else None
    return {
        'name': floor_name(section['id'], cycle, k),
        'key': key,
        'identity': {'gen': GEN_VERSION, 'hash': section_hash(section, stamps),
                     'key': key},
        'depth': depth, 'cycle': cycle, 'section': section['id'], 'k': k,
        'kind': floor['kind'], 'gen': floor['gen'], 'w': floor['w'], 'h': floor['h'],
        'rooms': len(floor['rooms']), 'rows': rows,
        'anchors': {'up': [up[0], up[1]], 'down': [down[0], down[1]],
                    'warden': _tile_or_none(floor['anchors'].get('warden')),
                    'vault': _tile_or_none(floor['anchors'].get('vault'))},
        'mobs': _with_warden(mobs_at(key, section, rows, up, down, source,
                                     catalog, k, depth=depth),
                             key, section, k, floor['anchors'].get('warden'),
                             source, catalog, depth=depth),
        'warden': _warden_record(section, k, cycle, floor['anchors'].get('warden')),
        'vault': _vault_record(floor, section, k, cycle),
        'legend': section_legend(section),
        'fog': block_fog,
    }


def contract(width: int, height: int, hero_at,
             down_at=None) -> dict:
    """The region contract.json for one generated floor.

    `hero_at` is the up-stair tile `[x, y]` - the hero lands there when
    stepping down from the floor above - and `down_at` is the down-stair
    tile `[x, y]` (the way on). For convenience `hero_at` may instead be
    a mapping with `up`/`down` keys or a pair of tiles, in which case the
    down tile is read from it.

    Returns the same shape an authored region's contract.json uses:
    `legend`, `pois` + `poi_text` for the stairs, `hero_start`, `tile`,
    `bg` and the character colours. A generated floor marks no sanctuary
    (a floor is not a safe town) and no water.
    """
    up = down = None
    if isinstance(hero_at, dict):
        up = _as_tile(hero_at.get("up"))
        down = _as_tile(hero_at.get("down"))
    elif (isinstance(hero_at, (list, tuple)) and len(hero_at) == 2
            and all(_as_tile(v) is not None for v in hero_at)):
        up = _as_tile(hero_at[0])
        down = _as_tile(hero_at[1])
    else:
        up = _as_tile(hero_at)
    if down_at is not None:
        down = _as_tile(down_at)

    for tile in (up, down):
        if tile is None:
            continue
        x, y = tile
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"stair tile {tile} is outside the {width}x{height} floor")

    pois: dict[str, str] = {}
    poi_text: dict[str, str] = {}
    if up is not None:
        key = f"{up[0]},{up[1]}"
        pois[key] = "the stair up"
        poi_text[key] = "Steps climb back toward the day."
    if down is not None:
        key = f"{down[0]},{down[1]}"
        pois[key] = "the stair down"
        poi_text[key] = "Steps drop into the dark."

    return {
        "tile": 32,
        "bg": BG,
        "hero_start": list(up) if up is not None else [1, 1],
        "legend": {k: dict(v) for k, v in LEGEND.items()},
        "pois": pois,
        "poi_text": poi_text,
        "sanctuary_tiles": [],
        "water_by_phase": {},
        "flood_tiles": [],
        "watch": {},
        "hero_color": HERO_COLOR,
        "speaker_color": SPEAKER_COLOR,
        "speaker_head": SPEAKER_HEAD,
    }
