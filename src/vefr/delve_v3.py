"""delve_v3 - the v3 floor generator: five pure stages, one stream each.

PLAN.md section 2 is the spec. `generate_floor_v3` takes a seed, a floor
size, a Section pack and a floor kind, and returns a FloorPlan dict: the
grid, the rooms, the anchors, the points of interest, the secrets, the
monsters and the chests.

The five stages run in a fixed order, each drawing from its own stream
keyed off the floor key:

  1. plan    `v3|<floor_key>|plan`    quotas and flavour, never a wall
  2. layout  `v3|<floor_key>|layout`  spine, stamp rooms, accretion, loops
  3. graph   no draws at all           the room graph, the path, the warden
  4. pop     `v3|<floor_key>|pop`     monsters, elites, groups, chests
  5. validate, and on a failure retry the whole floor with `|try{n}`

The layout stream is the only stream that carves, so a rewritten affix,
group or family table cannot move a wall. That is the sub-seed rule of
PLAN.md section 2. After `MAX_TRIES` retries the caller gets v2 geometry
with `gen: 2`.

PLAN.md section 2 also names a `loot` stream per mob and a `chest`
stream per chest. Neither is drawn here: a FloorPlan carries a chest's
table id, and a mob's family and affix and nothing else - ADR 0014
closes the spawn keys at eight and a stat is not one of them. A mob's
whole-number stats come out of `vefr.mob_stats`, which the balance
report (E10) calls, rather than out of this stage. What is inside a
chest or a corpse is the loot stream's business, not the pop stage's.

Determinism: `delve.prng` and its 32-bit integer maths are the only
source of randomness. No `random`, no clock, no global, no dictionary is
ever iterated while draws are consumed - every list here is a list.
"""

from __future__ import annotations

import json
from collections import deque

from vefr import stamps
from vefr.delve import generate_floor_v2, prng

# The alphabet of a generated floor: `#` is wall, the rest stand on.
WALL = "#"
FLOOR = "."
UP = "u"
DOWN = "d"

# The floor kinds the endless dungeon knows. A v3 floor is one of these.
FLOOR_KINDS = ("normal", "treasure", "infested", "hub")

# How many times stage 5 may retry a floor before the caller gets v2
# geometry. PLAN.md section 2 caps the fallback rate at 0.5%; the layout
# is built to satisfy the properties by construction, so a retry is rare.
MAX_TRIES = 8

# How many spine chords a floor may close. PLAN.md section 4 wants two
# room-graph cycles and one chord makes three, so this is the plan
# stage's range for a number no floor needs the top of.
LOOPS_MIN = 2
LOOPS_MAX = 3

# Rooms a v3 floor keeps. The loop property of PLAN.md section 4 bites
# at 12 rooms, and a floor that cannot hold a dozen of them is a narrow
# one the pack asked for anyway; below this the retry ladder tries
# again and v2 geometry is the last answer.
ROOMS_FLOOR = 6

# The pop stage's own spacing rule: a monster, a chest or a secret stands
# at least this many tiles (Chebyshev) from both stairs.
STAIR_CLEAR = 7

# One floor tile this many times is one monster slot, before the clamps.
# `MOBS_MAX` is twice a number: the top of the budget clamp, and ADR
# 0014's hard cap of 36 monsters a floor. They are the same ceiling, so
# they are the same constant - and it is a third thing, the top of the
# range `shapes.SECTION`'s `mobs` key is held to, so a count past it is
# refused by `vefr check` rather than clamped in silence.
TILES_PER_MOB = 30
MOBS_MIN = 4
MOBS_MAX = 36

# ADR 0014's hard caps, applied AFTER the omens would be, so the
# "Crowded" omen of PLAN.md section 4 cannot break one. Every one of
# them is a ceiling the pack may ask past: a cap that is hit stops
# further draws of that kind, and it neither raises nor fails the
# floor. THE OMEN HOOK GOES HERE - omens change the budget above and
# these four numbers below, and the clamp is applied after they are
# read, never before.
#
# Lone elites: the ones that lead no group. An elite that leads a group
# is that group's leader and is counted by the two caps under this one.
LONE_ELITES_MAX = 2
# Groups on a floor.
GROUPS_MAX = 3
# Members of one group, its leader and its minions together.
GROUP_MEMBERS_MAX = 4
# One elite-led group per this many rooms, and never below one while the
# Section's `groups.per_floor` still asks for a group at all.
ROOMS_PER_ELITE_GROUP = 8

# The two room shapes the graph stage names a stamp room by, in
# `rooms[i][4]`: the warden's hall and the vault. ADR 0014 keeps a group
# leader out of both, and out of any secret room. `landmark` is not on
# the list - the ADR names a vault, a hall and a secret room, and the
# landmark is none of the three.
STAMP_ROOMS = ("hall", "vault")

# How far a minion stands from its leader, Chebyshev. ADR 0014
# "Placement" says 2, and the stage used to search 4: a group that wakes
# as one is a fight the hero can see coming, and 2 is the radius that
# keeps every member inside the room its leader holds. A wider search
# also put minions through walls, which is the half of the rule the
# straight line alone does not check.
MINION_REACH = 2

# The closed range a Section's `groups.leash` may write, and what a group
# walks on when the Section names none. ADR 0014's "Section `groups`" line
# says the same three numbers, and the player's own `LEASH_MIN`,
# `LEASH_MAX` and `LEASH_DEFAULT` (part 420) are these three: the leash is
# the player's to enforce, and it is the pack's to write, so the two ends
# of it are named once per language and have to agree.
LEASH_MIN = 3
LEASH_MAX = 12
LEASH_DEFAULT = 6

# Chest tables. The value of a chest is `section["chest_values"][table]`,
# or 1 when the table is unmapped, so these are ids and never amounts.
CHEST_TABLES = ("t1", "t2")

# The room shape menu a room draws from. Brogue's menu, trimmed: PLAN.md
# section 2 steals a shape menu, and a shape is a short lowercase word.
# The three stamp shapes - hall, landmark and vault - are NOT in here:
# the graph stage names the rooms that hold them, and a shape that two
# rooms can hold for two different reasons says nothing.
SHAPES = ("cell", "closet", "den", "nook")

# The names a point of interest falls back on when the Section pack names
# none. A real pack carries its own list in `section["pois"]`.
FALLBACK_POIS = ("the drowned well", "the ash alcove", "the rusted grate")

# The packs of a floor that are not a Section pack are defaulted here, so
# a missing key never raises. PLAN.md section 2's data shapes.
DEFAULT_ROOMS = (12, 12)
DEFAULT_FAMILIES = ({"family": "rat", "weight": 1},)
DEFAULT_ELITES = {"per_floor": (0, 0), "affixes": ()}
DEFAULT_GROUPS = {"per_floor": (0, 0), "minions": (2, 3),
                  "leader": "normal", "same_family": True}


def _rand(rng, lo: int, hi: int) -> int:
    """A whole number in [lo, hi], both inclusive, from one draw.

    `lo + floor(rng() * (hi - lo + 1))`, so a JavaScript twin using
    `Math.floor` gets the identical number. `delve._rand_range` is the
    same line; it is written out here so the twin has one place to read.
    """
    return lo + int(rng() * (hi - lo + 1))


def _pick(rng, count: int) -> int:
    """An index in [0, count) from one draw, the list-position twin."""
    return int(rng() * count)


# ------------------------------------------------------------- pack reading
# Every accessor here defaults, because PLAN.md section 2 says only `id`,
# `rooms`, `families`, `elites`, `groups` and `pois` are required and a
# missing key must never raise.


def _pair(value, fallback: tuple[int, int]) -> tuple[int, int]:
    """A `[lo, hi]` pair of whole numbers, sorted, or `fallback`."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            lo, hi = int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return fallback
        return (lo, hi) if lo <= hi else (hi, lo)
    return fallback


def _demand(value, fallback: tuple[int, int]) -> tuple[int, int]:
    """A `[lo, hi]` count whose low bound is a DEMAND, not a suggestion.

    `_pair` orders a reversed pair by swapping its halves, which is the
    right thing for a range whose two ends are interchangeable - a room
    quota, a minion count. It is the wrong thing for a count, because a
    count's low bound is what the Section ASKS for: ADR 0014 says so out
    loud in the cap list ("1 elite-led group per 8 rooms, but at least 1
    when the Section's `per_floor` range asks for one"), and the low bound
    of a reversed pair is the only half of it the author wrote twice.

    So a reversed count is resolved to its low bound. `per_floor: [1, 0]`
    - "at least one group a floor, and none" - is a pack that contradicts
    itself, and the number both halves of it agree on is the one it
    states most firmly. Read as `rand(1, 1)` the floor carries the group
    the pack asked for and the cap above it is reachable; read as
    `rand(0, 1)` the same pack loses half its groups, and the cap that
    was written to protect them is never even consulted. The pack can
    still ask for no groups at all, by writing `[0, 0]`.
    """
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            lo, hi = int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return fallback
        return (lo, hi) if lo <= hi else (lo, lo)
    return fallback


def _names(value, fallback) -> list[str]:
    """A list of non-empty strings, or `fallback` when it is not one."""
    if isinstance(value, (list, tuple)):
        names = [str(item) for item in value if str(item)]
        if names:
            return names
    return list(fallback)


def _read_rooms(section: dict) -> tuple[int, int]:
    """The room quota range of a Section pack."""
    return _pair(section.get("rooms"), DEFAULT_ROOMS)


def _read_families(section: dict) -> list[dict]:
    """The family table, each entry `{family, weight}`, weights positive.

    The entry is kept WHOLE and only its weight is normalised. A Section
    names a Blueprint family by id and carries no record of its own
    (ADR 0014), so a pack that resolved one through
    `vefr.blueprint.resolve_family` hands the pop stage the resolved base
    on the entry - `hp`, `atk`, `xp`, `sight` - and this reader passes it
    on untouched. An entry with no base stats still draws; its stats
    come back at mob_stats' own floor of 1, which is the answer for a
    base that says nothing.
    """
    raw = section.get("families")
    if not isinstance(raw, (list, tuple)):
        return [dict(family) for family in DEFAULT_FAMILIES]
    families: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("family", ""))
        if not name:
            continue
        entry = dict(item)
        try:
            weight = int(item.get("weight", 1))
        except (TypeError, ValueError):
            weight = 1
        entry["weight"] = max(0, weight)
        families.append(entry)
    if not any(family["weight"] for family in families):
        for family in families:
            family["weight"] = 1
    return families or [dict(family) for family in DEFAULT_FAMILIES]


def _read_elites(section: dict) -> tuple[int, int, list[str]]:
    """How many elites a floor carries, and their affix ids.

    `per_floor` is read by `_demand` and not by `_pair`: a count's low
    bound is what the Section asks for, so a reversed one is a count, not
    a range to be re-ordered.
    """
    raw = section.get("elites")
    if not isinstance(raw, dict):
        lo, hi = DEFAULT_ELITES["per_floor"]
        return lo, hi, list(DEFAULT_ELITES["affixes"])
    lo, hi = _demand(raw.get("per_floor"), (0, 0))
    return lo, hi, _names(raw.get("affixes"), ())


def _read_groups(section: dict) -> tuple[int, int, int, int, str, bool, int | None]:
    """How many groups a floor carries, their size, their two flags, and
    the leash their spawns carry.

    `leader` is "elite" or "normal" and defaults to "normal". A Section
    that leads its groups with an elite says so, and the neutral default
    is the one a pack can be valid without: `vefr.shapes` refuses a pack
    that asks for an elite-led group and names no affix at all.

    `same_family` defaults to True, the value ADR 0014's own group record
    shows. A linked group that wakes as one thing is one kind of thing,
    and a pack that wants a mixed mob says `false` and pays a family
    draw for every minion.

    `per_floor` is read by `_demand` and not by `_pair`, for the reason
    the cap below gives: ADR 0014's elite-led-group cap is phrased off
    this range's LOW bound, so a low bound the draw does not honour is a
    cap that is never reached. `minions` stays a range - two ends the
    author can mean in either order, with no cap of its own reading
    either end.

    `leash` is `None` and not a number when the Section names none, and
    the spawns then carry no `leash` key at all: the player's own
    `LEASH_DEFAULT` is what a group walks on, so a pack that wrote
    nothing gets exactly the same floor it always did. A leash the
    Section does name is a whole number inside the closed range ADR 0014
    writes - `vefr.shapes` refuses one outside it, and a Section that
    somehow says 2 or 13 or True is treated as having said nothing here
    rather than as a group that walks two tiles or thirteen.
    """
    raw = section.get("groups")
    if not isinstance(raw, dict):
        return (DEFAULT_GROUPS["per_floor"] + DEFAULT_GROUPS["minions"]
                + (DEFAULT_GROUPS["leader"], DEFAULT_GROUPS["same_family"])
                + (None,))
    leader = str(raw.get("leader", DEFAULT_GROUPS["leader"]))
    if leader not in ("elite", "normal"):
        leader = DEFAULT_GROUPS["leader"]
    leash = raw.get("leash")
    if type(leash) is not int or not LEASH_MIN <= leash <= LEASH_MAX:
        leash = None
    return (_demand(raw.get("per_floor"), (0, 0))
            + _pair(raw.get("minions"), (2, 3))
            + (leader, bool(raw.get("same_family", DEFAULT_GROUPS["same_family"])),
               leash))


def _draw_family(rng, families: list[dict]) -> str:
    """One family id, drawn by weight over the list in pack order."""
    total = sum(family["weight"] for family in families)
    if total <= 0:
        return families[0]["family"]
    roll = _pick(rng, total)
    walked = 0
    for family in families:
        walked += family["weight"]
        if roll < walked:
            return family["family"]
    return families[-1]["family"]


def mob_budget(section: dict, walkable: int, k: int) -> int:
    """How many monsters this floor carries, and the one place that says so.

    Two answers, in this order, and the first one the pack wrote wins:

    - the count `section["mobs"]` names for floor `k` (vefr#357) - four on
      a floor the pack named four, zero on a floor it named zero, and the
      same number for `k` in every language because it is pack data;
    - otherwise the area budget, one monster per `TILES_PER_MOB` walkable
      tiles, clamped into `MOBS_MIN..MOBS_MAX`.

    `walkable` is the caller's own count of the floor's walkable tiles and
    is not re-measured here: the v3 pop stage counts the canvas and
    `vefr.delve` counts the rows, and each counts what it always counted.

    A named count is clamped to `0..MOBS_MAX` rather than to
    `MOBS_MIN..MOBS_MAX`, because a pack that wrote zero meant zero and one
    that wrote four meant four on a floor small enough to hold four. The
    clamp is still here for a Section read off disk without its check, the
    same reason `sections.size_range` clamps into `SIZE_BOUNDS`. It is not
    a draw: `k` and the count are read before the pop stream's first draw,
    so a Section that sets `mobs` opens the same three streams as one that
    does not.

    The JavaScript twin is `mobBudget` in part 396, published as
    `VEFR_DELVE.v3MobBudget` and called from part 397's own `mobBudget` as
    well as from the pop stage - one implementation on both sides of the
    player, beside this one on this side.
    """
    from . import sections  # here, not at the top: sections imports this module

    named = sections.mob_count(section, k)
    if named is not None:
        return min(MOBS_MAX, max(0, named))
    return min(MOBS_MAX, max(MOBS_MIN, walkable // TILES_PER_MOB))


def _read_size(size_range) -> tuple[int, int]:
    """The floor size, and only the `(w, h)` form of it.

    A pair of whole numbers and nothing else: a lone width, a triple, a
    string or a fractional width is a caller's mistake and raises rather
    than being rounded into a floor of some other shape.
    """
    if not isinstance(size_range, (list, tuple)) or len(size_range) != 2:
        raise ValueError("size_range must be a (w, h) pair of whole numbers")
    if any(not isinstance(value, int) or isinstance(value, bool)
           for value in size_range):
        raise ValueError("size_range must be a (w, h) pair of whole numbers")
    width, height = size_range
    if width < 8 or height < 8:
        raise ValueError("a v3 floor needs a size of at least 8 by 8")
    return width, height


# ------------------------------------------------------------------ canvas


class Canvas:
    """The grid under construction, with the bookkeeping v3 needs.

    Three tile sets, kept disjoint on purpose. `owner` names the room a
    tile belongs to (-1 for none), `corr` holds the corridor tiles, and
    `walk` holds both. The frozen tests read the room graph back off
    `rows` and `rooms` alone, so every carved tile has to belong to a
    room or to a corridor region that touches one. Carving a corridor
    that runs through a room therefore moves those tiles from `corr` into
    `owner`, which is what keeps the two sets disjoint.
    """

    def __init__(self, width: int, height: int):
        self.w = width
        self.h = height
        self.grid = [[WALL] * width for _ in range(height)]
        self.owner = [-1] * (width * height)
        self.corr: set[int] = set()
        self.walk: set[int] = set()
        self.rooms: list[list] = []
        # The tiles a stamped room painted, which no corridor may cross, and
        # the number of walkable tiles the rooms claim between them. A
        # stamped room is not a filled rectangle, so `owned` is counted as
        # the stamps are laid rather than as `w * h` per room.
        self.locked: set[int] = set()
        self.owned = 0
        # What the stamp stage placed, in placement order, one record per
        # stamped room (ADR 0013, Placement). The graph stage reads it: a
        # stamped room is the room its role names, and its letters are the
        # anchors the floor plan carries.
        self.stamps: list[dict] = []

    def carve_room(self, rect: tuple[int, int, int, int], index: int) -> None:
        """Fill a room rectangle with floor and claim every one of its tiles."""
        x, y, width, height = rect
        for yy in range(y, y + height):
            row = self.grid[yy]
            for xx in range(x, x + width):
                here = yy * self.w + xx
                row[xx] = FLOOR
                self.owner[here] = index
                self.corr.discard(here)
                self.walk.add(here)
        self.owned += width * height

    def carve_stamp(self, rows: list[str], rect: tuple[int, int, int, int],
                    index: int, used: tuple[int, int]) -> None:
        """Paint a stamped room and claim only the tiles it can stand on.

        The room is a drawing, not a rectangle: `#` and a space stay wall, a
        used socket becomes floor and every other socket becomes wall (ADR
        0013, Placement 3), and a letter is a floor tile that also carries a
        name. So a stamped room's walkable area is smaller than its
        rectangle, which is why `owned` is counted tile by tile.
        """
        x, y = rect[0], rect[1]
        for yy, row in enumerate(rows):
            for xx, glyph in enumerate(row):
                here = (y + yy) * self.w + (x + xx)
                # The whole rectangle is locked, walls and all: a corridor
                # may not run through a painted room, and the wall tiles are
                # the ones it would otherwise cross for free.
                self.locked.add(here)
                if glyph in (WALL, " "):
                    self.grid[y + yy][x + xx] = WALL
                    continue
                if glyph in ("+", "?") and (xx, yy) != used:
                    self.grid[y + yy][x + xx] = WALL
                    continue
                self.grid[y + yy][x + xx] = FLOOR
                self.owner[here] = index
                self.corr.discard(here)
                self.walk.add(here)
                self.owned += 1

    def carve_h(self, x0: int, x1: int, y: int) -> None:
        """Carve a horizontal run, inclusive of both ends."""
        for x in range(min(x0, x1), max(x0, x1) + 1):
            self._carve(x, y)

    def carve_v(self, y0: int, y1: int, x: int) -> None:
        """Carve a vertical run, inclusive of both ends."""
        for y in range(min(y0, y1), max(y0, y1) + 1):
            self._carve(x, y)

    def _carve(self, x: int, y: int) -> None:
        here = y * self.w + x
        if self.grid[y][x] == WALL:
            self.grid[y][x] = FLOOR
            self.walk.add(here)
        if self.owner[here] < 0:
            self.corr.add(here)

    def stamp_corridor(self, tiles: list[tuple[int, int]], index: int,
                       rect: tuple[int, int, int, int]) -> None:
        """Carve one corridor into a stamped room, from the outside in.

        A stamped room's corridor is routed rather than linked, so it is
        handed over as the tiles it runs through instead of as two rooms.
        The route runs from the socket's mouth to the socket tile, and a
        mouth may be a space inside the room's own rectangle. That tile
        belongs to the room: it is inside the room's rectangle, so every
        reader of `rooms` counts it as the room's, and the corridor region
        starts at the next tile out. One tile, one owner - that is what
        keeps the grid readable as rooms plus corridors, and what stops a
        stamped room reading as a cut vertex with a corridor through it.
        """
        x, y, width, height = rect
        for tile_x, tile_y in tiles:
            here = tile_y * self.w + tile_x
            if not (x <= tile_x < x + width and y <= tile_y < y + height):
                self._carve(tile_x, tile_y)
                continue
            if self.grid[tile_y][tile_x] == WALL:
                self.grid[tile_y][tile_x] = FLOOR
                self.walk.add(here)
                self.owned += 1
            self.owner[here] = index
            self.corr.discard(here)

    def rows(self) -> list[str]:
        """The grid as the FloorPlan's `rows`: one string per row."""
        return ["".join(row) for row in self.grid]


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int], pad: int) -> bool:
    """True when two room rectangles touch or sit closer than `pad`.

    One idea per line, and the pad is what keeps a wall between two
    rooms: two rooms that touch would be neighbours in the room graph
    with no corridor between them, and v3 lays its corridors through the
    gap it drew.
    """
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ((ax - pad) < (bx + bw) and (bx - pad) < (ax + aw)
            and (ay - pad) < (by + bh) and (by - pad) < (ay + ah))


def _center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    """The middle tile of a room, floors as `generate_floor_v2` does."""
    x, y, width, height = rect
    return x + width // 2, y + height // 2


def _fits(canvas: Canvas, rect: tuple[int, int, int, int]) -> bool:
    """True when a rectangle is inside the grid and clear of every room."""
    x, y, width, height = rect
    if x < 1 or y < 1 or x + width > canvas.w - 1 or y + height > canvas.h - 1:
        return False
    return not any(_overlaps(rect, tuple(room[:4]), 1) for room in canvas.rooms)


def _fits_stamp(canvas: Canvas, rect: tuple[int, int, int, int]) -> bool:
    """`_fits`, and clear of every carved tile as well.

    A stamped room lands after the galleries and the chords, so the wall a
    plain room is placed against may already carry a corridor. Overwriting
    one would eat the corridor and strand whatever it served, so a stamp
    that lands on carved ground is not placed at all.
    """
    if not _fits(canvas, rect):
        return False
    x, y, width, height = rect
    return all(
        (yy * canvas.w + xx) not in canvas.walk
        for yy in range(y, y + height)
        for xx in range(x, x + width)
    )


# --------------------------------------------------------------- corridors


def _link(rng, canvas: Canvas,
          first: tuple[int, int, int, int],
          second: tuple[int, int, int, int]) -> None:
    """An L-shaped corridor between two room rectangles, `delve`'s shape.

    The door sockets are the tile of each room's facing side that faces
    the other room: the last column and the middle row of the left room
    against the first column of the right one, and the same on the
    vertical. The axis is the one the two rooms are further apart on, so
    the long leg of the L runs along the gap and the short leg steps
    into the second room.
    """
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    gap_x = max(ax - (bx + bw), bx - (ax + aw))
    gap_y = max(ay - (by + bh), by - (ay + ah))
    if rng() < 0.5:
        # The first leg runs from `first` to the bend.
        if gap_x >= gap_y:
            start = (ax + aw - 1, ay + ah // 2)
            end = (bx, by + bh // 2)
            canvas.carve_h(start[0], end[0], start[1])
            canvas.carve_v(start[1], end[1], end[0])
        else:
            start = (ax + aw // 2, ay + ah - 1)
            end = (bx + bw // 2, by)
            canvas.carve_v(start[1], end[1], start[0])
            canvas.carve_h(start[0], end[0], end[1])
    else:
        # The same two legs, the other way round the bend.
        if gap_x >= gap_y:
            start = (ax + aw // 2, ay + ah // 2)
            end = (bx + bw // 2, by + bh // 2)
            canvas.carve_v(start[1], end[1], start[0])
            canvas.carve_h(start[0], end[0], end[1])
        else:
            start = (ax + aw // 2, ay + ah // 2)
            end = (bx + bw // 2, by + bh // 2)
            canvas.carve_h(start[0], end[0], start[1])
            canvas.carve_v(start[1], end[1], end[0])


def _gallery_loop(canvas: Canvas, horizontal: bool,
                  first: tuple[int, int, int, int],
                  second: tuple[int, int, int, int],
                  row: int) -> None:
    """A corridor that runs along one gallery row to close a cycle.

    The run is carved on a row that is a wall, one tile clear of the
    rooms it serves, and it is entered from each end. So the run passes
    over the wall between every pair of rooms it spans and reads as one
    corridor region that touches all of them, which is exactly the edge
    the loop needs: two rooms that were only joined by the chain.
    """
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    if horizontal:
        near, far = ax + aw - 1, bx
        if near > far:
            near, far = far, near
        canvas.carve_h(near, far, row)
        canvas.carve_v(row, ay + ah // 2, ax + aw - 1)
        canvas.carve_v(row, by + bh // 2, bx)
    else:
        near, far = ay + ah - 1, by
        if near > far:
            near, far = far, near
        canvas.carve_v(near, far, row)
        canvas.carve_h(row, ax + aw // 2, ay + ah - 1)
        canvas.carve_h(row, bx + bw // 2, by)


# ----------------------------------------------------------------- stage 1
# the plan stream - the exact order of draws. A JavaScript twin must
# follow this line for line; `rng()` is one call of
# `prng("v3|" + floor_key + "|plan")`, and a whole number `rand(lo, hi)`
# is `lo + floor(rng() * (hi - lo + 1))`.
#
#  1. quota  = rand(rooms_lo, rooms_hi)   from `section["rooms"]`,
#     defaulted to (12, 12). The room quota of the floor.
##  2. loops  = rand(LOOPS_MIN, LOOPS_MAX)  how many spine chords to
#     close. Stage 2 draws at most this many; one chord is already
#     three cycles, and validate wants at least two.
#  3. secrets = rand(0, 2)                 how many leaf rooms to turn
#     into secret rooms. PLAN.md section 4 wants at least half the
#     floors to hold one.
##  4. flavour = floor(rng() * FLAVOURS)     which of the pack's named
#     points of interest becomes this floor's landmark. The name it
#     picks is a name, not a tile: it cannot move a wall.
#  5. waypoint = floor(rng() * 2)           a floor kind of "hub" is a
#     waypoint when this lands on 0, and nothing else ever is.
#
# Nothing above moves a wall. The quota reaches stage 2 as a number to
# lay out, not as a decision this stage makes about the grid, so the
# plan stream stays the reason a rewritten affix table cannot move a
# stone.
FLAVOURS = 4


def _plan_stage(rng, section: dict, floor_kind: str) -> dict:
    """The plan stage: quotas and flavour, drawn from the plan stream."""
    lo, hi = _read_rooms(section)
    plan = {
        "quota": _rand(rng, lo, hi),
        "loops": _rand(rng, LOOPS_MIN, LOOPS_MAX),
        "secrets": _rand(rng, 0, 2),
        "flavour": _pick(rng, FLAVOURS),
        "waypoint": floor_kind == "hub" and _pick(rng, 2) == 0,
    }
    # The layout a Section asks for (ADR 0022). A name, not a draw, and only
    # carried when it is not the spine, so a Section that names none plans
    # exactly the dict it always planned.
    if section.get("layout") == "wander":
        plan["layout"] = "wander"
    return plan


# ----------------------------------------------------------------- stage 2
# the layout stream - the exact order of draws. `rng()` is one call of
# `prng("v3|" + floor_key + "|layout")`, `rand(lo, hi)` is
# `lo + floor(rng() * (hi - lo + 1))` and `pick(n)` is
# `floor(rng() * n)`. This is the only stage that carves.
#
#  1. row_h = rand(5, 7)          the pitch of a slot row across the
#     short axis, so a room of up to `row_h - 1` tiles and a wall.
#     band = row_h - 1.
#  2. n_slots = (short - 2) // row_h;
#     band_slot = n_slots // 2;   the spine's slot row, the middle one.
#     band_lo = 1 + band_slot * row_h.
#  3. spine: the up-stair end first. Repeat while the plan's quota is
#     not half spent and the cursor is inside the long axis:
#       da = rand(4, 6)            the room's size along the long axis;
#       shape = pick(len(SHAPES));
#       place (cursor, band_lo, da, band); cursor = cursor + da + 1.
#     A draw that will not fit ends the spine, and no further draw is
#     taken. Each room is joined to the one before it with one L-shaped
#     corridor, which takes one draw for the bend.
#  4. accretion: children go on ONE side of the band first, and the
#     side with the most free slot rows wins, the lower one on a tie.
#     The free rows of that side, nearest the spine first, are the rows
#     the children may use. Walk the spine in order and, for each spine
#     room, try those rows in turn. Stop for a room once `cap` children
#     are placed or the quota is met. If the quota is still short when
#     the spine is done, do the whole thing again over the free rows of
#     the other side, in the same order and the same draws; a floor the
#     first pass filled - every floor of the sizes in PLAN.md section 3
#     - takes no draw at all here. Each attempt, in this order and
#     whether or not it is placed:
#       da = rand(3, 5)            the child's size along the long axis;
#       db = rand(3, band)         its size across the short axis.
#     A child is centred on its parent, clamped inside the long axis,
#     skipped when it does not fit its slot row or touches another
#     room, and otherwise placed and joined to its parent by one
#     L-shaped corridor, which takes one draw for the bend.
#  5. the child gallery: on the child side, on the wall row just past
#     the outermost child row - the one row no child's corridor can
#     reach, because every corridor stops at its own room - a run from
#     the first child of that row to the last. It serves every child it
#     runs past, so those rooms gain a second way in and the room graph
#     stops being a tree of dead ends.
#  6. the spine chords, which are the loops. Take the pairs
#       (0, 3), (4, 7), (8, 11), ... clipped to the last spine room,
#     one per four rooms, and the first `plan["loops"]` of them - the
#     one number the plan stage drew that the layout stage reads. Each is
#     closed with a gallery corridor on the wall row just off the band
#     on the side NO child was placed on, so a chord is a region of its
#     own and two chords do not run into one another. A run over four
#     rooms joins all six pairs of those four, and the chain already
#     has three of them, so one chord is three cycles: more than the
#     two PLAN.md section 4 asks for, out of one corridor.
#  7. the stamped rooms (ADR 0013, Placement), last, because a stamp may
#     not land on carved ground. The slots are, in order, warden-hall,
#     vault (only when the pack names one), landmark, then `special`,
#     `secret` and `filler` up to the quotas below. A slot with no
#     eligible stamp of its role takes no draw at all. Per slot:
#       role = pick(total weight of that role's stamps)
#     then, per attempt, up to ATTEMPTS (24) of them, in this order:
#       o = pick(len(allowed))     the orientation, from the allowed set
#       x = rand(1, w - width - 1)  and then
#       y = rand(1, h - height - 1)
#     An attempt that does not fit, or that cannot be reached from one
#     of its own sockets, is spent like any other: the three draws
#     happen, nothing is carved, and the next attempt is taken. A stamp
#     too big for the floor at any orientation gives its slot up at
#     once and takes no draw at all, so a 21x21 room cannot burn a
#     floor's attempt budget on a 48x32 grid. The connection draws
#     nothing: a corridor is routed from the socket mouth to the nearest
#     carved tile, both L-bends tried in a fixed order, and the first
#     route crossing no locked tile wins. A used `+` becomes floor and a
#     used `?` becomes a `secrets` entry; an unused socket becomes wall.
#     A required role still missing fails the floor, which the retry
#     ladder redraws with `|try{n}`; on the LAST try the required roles
#     are pinned to named spots instead, and a role that still fails
#     falls back to v2 with the role reported as a defect.
#
# A chord's own pair is three rooms apart, not four, and its grid gap
# is however wide the spine is. The plan's rule is kept in the order it
# was written and could not be met as written: two rooms four steps
# apart along a chain of this pitch are a dozen tiles from each other,
# so "at least 4 apart in the graph" and "a grid gap of 6 or less" are
# two conditions no pair meets at once. What the sweep measures is the
# cycle, and a chord makes three of them.


def _child_rows(band_slot: int, n_slots: int) -> tuple[list[int], int]:
    """The free slot rows children may use, and the side they are on.

    1 is the side past the band, where `across` grows, and -1 the side
    before it. The side with the most free rows wins and the lower one
    on a tie, so the choice follows from the floor's shape and is not a
    draw.
    """
    below = list(range(band_slot + 1, n_slots))
    above = list(range(band_slot - 1, -1, -1))
    if len(below) >= len(above):
        return below, 1
    return list(reversed(above)), -1


def _far_rows(band_slot: int, n_slots: int, side: int) -> list[int]:
    """The free slot rows on the other side of the band, nearest first.

    The second accretion pass, for a floor the first one could not fill.
    """
    if side == 1:
        return list(reversed(range(band_slot - 1, -1, -1)))
    return list(range(band_slot + 1, n_slots))


def _layout_stage(rng, canvas: Canvas, plan: dict, pool: list[dict],
                  pinned: bool = False) -> tuple[list[int], list[str]]:
    """The layout stage: the spine, accretion, the galleries, the stamps.

    Rooms are laid out along the long axis and across the short one, in
    "along, across" order, so a tall floor lays its spine down rather
    than across. A floor is square-free either way: the grid is always
    carved as rooms joined by corridors.

    `pool` is the stamp set this floor may use - empty for a Section that
    names no stamp tags, which is every floor of a pack without stamps,
    and those floors are laid out exactly as they were before ADR 0013.
    `pinned` is the last try's flag, and it only means anything when the
    pool is not empty.

    Returns the spine, the rooms in chain order, so the graph stage can
    put the two stairs at its ends, and the required roles that wanted a
    stamped room and did not get one. An empty second list is a floor
    that keeps.
    """
    width, height = canvas.w, canvas.h
    horizontal = width >= height
    long_len, short_len = (width, height) if horizontal else (height, width)

    def rect(along: int, across: int, along_size: int, across_size: int):
        if horizontal:
            return (along, across, along_size, across_size)
        return (across, along, across_size, along_size)

    def place(along: int, across: int, along_size: int, across_size: int) -> int:
        index = len(canvas.rooms)
        box = rect(along, across, along_size, across_size)
        canvas.carve_room(box, index)
        canvas.rooms.append([box[0], box[1], box[2], box[3], SHAPES[_pick(rng, len(SHAPES))]])
        return index

    row_h = _rand(rng, 5, 7)
    band = row_h - 1
    n_slots = (short_len - 2) // row_h
    band_slot = n_slots // 2
    band_lo = 1 + band_slot * row_h
    if n_slots < 1:
        return [], []

    # 3. the spine, one room after another down the long axis.
    spine: list[int] = []
    cursor = 1
    spine_target = max(3, (plan["quota"] + 1) // 2)
    while len(spine) < spine_target:
        along_size = _rand(rng, 4, 6)
        if cursor + along_size > long_len - 1:
            break
        index = place(cursor, band_lo, along_size, band)
        if spine:
            _link(rng, canvas, tuple(canvas.rooms[spine[-1]][:4]), tuple(canvas.rooms[index][:4]))
        spine.append(index)
        cursor += along_size + 1
    if len(spine) < 2:
        return [], []

    # 4. accretion, every spine room grown into the free rows of one
    #    side, then into the free rows of the other if that was not
    #    enough to reach the quota. A second pass draws nothing at all
    #    on a floor the first pass filled, which is every floor of the
    #    sizes in PLAN.md section 3.
    near_rows, side = _child_rows(band_slot, n_slots)
    far_rows = _far_rows(band_slot, n_slots, side)
    cap = max(2, -(-(plan["quota"] - len(spine)) // len(spine)))
    spine_set = set(spine)
    for row_set in (near_rows, far_rows):
        if len(canvas.rooms) >= plan["quota"]:
            break
        for parent in spine:
            if len(canvas.rooms) >= plan["quota"]:
                break
            grown = 0
            for slot in row_set:
                if grown >= cap or len(canvas.rooms) >= plan["quota"]:
                    break
                along_size = _rand(rng, 3, 5)
                across_size = _rand(rng, 3, band)
                across = 1 + slot * row_h
                if across + across_size > short_len - 1:
                    continue
                along = canvas.rooms[parent][0] + (canvas.rooms[parent][2] - along_size) // 2
                along = max(1, min(along, long_len - 1 - along_size))
                if not _fits(canvas, rect(along, across, along_size, across_size)):
                    continue
                index = place(along, across, along_size, across_size)
                _link(rng, canvas, tuple(canvas.rooms[parent][:4]),
                      tuple(canvas.rooms[index][:4]))
                grown += 1
    children = [room for room in range(len(canvas.rooms)) if room not in spine_set]

    # 5. the child gallery, in front of the outermost child row.
    if children and near_rows:
        _child_gallery(canvas, horizontal, children, near_rows[-1] + side, row_h,
                       short_len, side)

    # 6. the spine chords, on the side of the band no child was placed on.
    edge = canvas.h if horizontal else canvas.w
    gallery = band_lo - 1 if side == 1 else band_lo + band
    if 1 <= gallery <= edge - 2:
        for nth, i in enumerate(range(0, len(spine) - 1, 4)):
            if nth >= plan["loops"] or i + 3 >= len(spine):
                break
            _gallery_loop(canvas, horizontal, tuple(canvas.rooms[spine[i]][:4]),
                          tuple(canvas.rooms[spine[i + 3]][:4]), gallery)

    # 7. the stamped rooms, once everything else has stopped carving.
    missing: list[str] = []
    if pool:
        up = _center(tuple(canvas.rooms[spine[0]][:4]))
        _placed, missing = _stamp_stage(rng, canvas, plan, pool, spine, up, pinned)
    return spine, missing


def _child_gallery(canvas: Canvas, horizontal: bool, children: list[int],
                   slot: int, row_h: int, short_len: int, side: int) -> None:
    """A corridor in front of the outermost row of child rooms.

    The run is carved on the wall row just past that row, which no
    child's corridor reaches, so it is a region of its own that serves
    exactly the rooms of that row. Two of those rooms were only joined
    by the whole length of the spine; now the region joins them to each
    other, and that is a cycle.
    """
    if slot < 0 or slot + 1 > (short_len - 2) // row_h:
        return
    across = 1 + slot * row_h
    row = across if side == 1 else across - 1
    if not 1 <= row <= (canvas.h if horizontal else canvas.w) - 2:
        return
    same = [room for room in children
            if (canvas.rooms[room][1] if horizontal else canvas.rooms[room][0]) == across]
    if len(same) < 2:
        return
    _gallery_loop(canvas, horizontal, tuple(canvas.rooms[same[0]][:4]),
                  tuple(canvas.rooms[same[-1]][:4]), row)


# ----------------------------------------------------------- stage 2, wander
# The `wander` layout (ADR 0022), the layout stream's other order of draws.
# A Section that names `"layout": "wander"` is laid out here instead of on a
# spine; stages 3 to 5 are the same. `rng()`, `rand` and `pick` are the
# spine layout's own.
#
#  1. cell_w = rand(8, 10); cell_h = rand(7, 8)   the pitch of the cell grid.
#     cols = (w - 1) // cell_w; rows = (h - 1) // cell_h. A grid of fewer
#     than two cells lays nothing, and the retry ladder takes over.
#  2. start = (rand(0, cols - 1), rand(0, rows - 1))   the walk's first cell.
#  3. the walk: while it is shorter than max(3, (2 * quota + 2) // 3)
#     cells, the free cells beside its last cell, east, south, west, north
#     in that order; none ends the walk. Each option that is further from
#     the first cell (Manhattan, in cells) than the last cell is listed
#     WANDER_AWAY times, any other once, and
#       next = listed[pick(len(listed))].
#     A cell is free while no room stands in it. The walk never crosses
#     itself, so it turns, climbs and doubles back but heads outward.
#  4. a room in each walk cell, in walk order, and a room in a cell is
#       rw = rand(4, cell_w - 2); rh = rand(3, cell_h - 2);
#       x = cell_x + rand(0, cell_w - 1 - rw); y = cell_y + rand(0, cell_h - 1 - rh);
#       shape = pick(len(SHAPES)),
#     with `cell_x = 1 + c * cell_w` and `cell_y = 1 + r * cell_h`. The
#     last column and row of every cell stay wall, so two rooms never
#     touch. Each walk room after the first is joined to the one before
#     it with one L-shaped corridor, which takes one draw for the bend.
#  5. branches: every room in index order - the walk first, then each
#     room as it is placed - grows into the free cells beside it, east,
#     south, west, north, until it has `cap` children or the quota is met:
#       cell = options[pick(len(options))]; a room there (4); a link (1).
#     `cap = max(1, ceil((quota - walk) / walk))`.
#  6. loops: every pair of rooms in side-by-side cells, row-major and east
#     before south, that no corridor joins yet and whose roots - the walk
#     room each one hangs off - are at most WANDER_REACH apart along the
#     walk. Then, `plan["loops"]` times while any are left:
#       pair = pairs.pop(pick(len(pairs))); a link (1).
#     A loop stays local, so no loop is a short cut past the walk.
#  7. the stamped rooms, exactly as the spine layout's step 7.
#
# Every corridor joins two rooms in side-by-side cells, so it stays inside
# those two cells and never crosses a third room. Stage 5 holds a wander
# floor to one more property: its stairs are at least
# min(WANDER_APART, max(w, h) // 3) tiles apart (Chebyshev), so a walk that
# doubled back to its start is drawn again rather than kept.

WANDER_DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
# How far apart along the walk a loop's two roots may be.
WANDER_REACH = 2
# How many times a step away from the walk's first cell is listed.
WANDER_AWAY = 3
# The least Chebyshev distance between a wander floor's two stairs, capped
# at a third of the floor's long side so a small floor can still keep one.
WANDER_APART = 16


def _wander_stage(rng, canvas: Canvas, plan: dict, pool: list[dict],
                  pinned: bool = False) -> tuple[list[int], list[str]]:
    """The wander layout: a walk over a grid of cells, branches, local loops.

    Returns what `_layout_stage` returns: the walk's rooms in walk order,
    which the graph stage puts the two stairs at the ends of, and the
    required roles that wanted a stamped room and did not get one.
    """
    cell_w = _rand(rng, 8, 10)
    cell_h = _rand(rng, 7, 8)
    cols = (canvas.w - 1) // cell_w
    rows = (canvas.h - 1) // cell_h
    if cols * rows < 2:
        return [], []

    cells: dict[tuple[int, int], int] = {}
    root: list[int] = []
    linked: set[tuple[int, int]] = set()

    def place(cell: tuple[int, int], walk_at: int) -> int:
        index = len(canvas.rooms)
        room_w = _rand(rng, 4, cell_w - 2)
        room_h = _rand(rng, 3, cell_h - 2)
        x = 1 + cell[0] * cell_w + _rand(rng, 0, cell_w - 1 - room_w)
        y = 1 + cell[1] * cell_h + _rand(rng, 0, cell_h - 1 - room_h)
        canvas.carve_room((x, y, room_w, room_h), index)
        canvas.rooms.append([x, y, room_w, room_h, SHAPES[_pick(rng, len(SHAPES))]])
        cells[cell] = index
        root.append(walk_at)
        return index

    def join(a: int, b: int) -> None:
        _link(rng, canvas, tuple(canvas.rooms[a][:4]), tuple(canvas.rooms[b][:4]))
        linked.add((min(a, b), max(a, b)))

    def free_beside(cell: tuple[int, int]) -> list[tuple[int, int]]:
        out = []
        for dc, dr in WANDER_DIRS:
            near = (cell[0] + dc, cell[1] + dr)
            if 0 <= near[0] < cols and 0 <= near[1] < rows and near not in cells:
                out.append(near)
        return out

    # 2-3. the walk, a cell at a time, never onto a cell it has stood on.
    walk_target = max(3, (2 * plan["quota"] + 2) // 3)
    walk_cells = [(_rand(rng, 0, cols - 1), _rand(rng, 0, rows - 1))]
    seen = {walk_cells[0]}
    while len(walk_cells) < walk_target:
        c, r = walk_cells[-1]
        options = [
            (c + dc, r + dr) for dc, dr in WANDER_DIRS
            if 0 <= c + dc < cols and 0 <= r + dr < rows and (c + dc, r + dr) not in seen
        ]
        if not options:
            break
        # A step that takes the walk further from its first cell is listed
        # WANDER_AWAY times, any other step once, so the walk still turns and
        # doubles back but heads out across the floor rather than curling up.
        here = abs(c - walk_cells[0][0]) + abs(r - walk_cells[0][1])
        weighted = []
        for option in options:
            there = abs(option[0] - walk_cells[0][0]) + abs(option[1] - walk_cells[0][1])
            weighted.extend([option] * (WANDER_AWAY if there > here else 1))
        step = weighted[_pick(rng, len(weighted))]
        walk_cells.append(step)
        seen.add(step)
    if len(walk_cells) < 2:
        return [], []

    # 4. a room in every walk cell, each joined to the one before it.
    spine: list[int] = []
    for at, cell in enumerate(walk_cells):
        index = place(cell, at)
        if spine:
            join(spine[-1], index)
        spine.append(index)

    # 5. branches into the free cells, the walk first, then every room grown.
    cap = max(1, -(-(plan["quota"] - len(spine)) // len(spine)))
    cell_of = {index: cell for cell, index in cells.items()}
    parent = 0
    while parent < len(canvas.rooms) and len(canvas.rooms) < plan["quota"]:
        options = free_beside(cell_of[parent])
        grown = 0
        while options and grown < cap and len(canvas.rooms) < plan["quota"]:
            cell = options.pop(_pick(rng, len(options)))
            child = place(cell, root[parent])
            cell_of[child] = cell
            join(parent, child)
            grown += 1
        parent += 1

    # 6. local loops between side-by-side rooms no corridor joins yet.
    pairs = []
    for r in range(rows):
        for c in range(cols):
            a = cells.get((c, r))
            if a is None:
                continue
            for dc, dr in ((1, 0), (0, 1)):
                b = cells.get((c + dc, r + dr))
                if b is None or (min(a, b), max(a, b)) in linked:
                    continue
                if abs(root[a] - root[b]) > WANDER_REACH:
                    continue
                pairs.append((a, b))
    for _ in range(plan["loops"]):
        if not pairs:
            break
        a, b = pairs.pop(_pick(rng, len(pairs)))
        join(a, b)

    # 7. the stamped rooms, once everything else has stopped carving.
    missing: list[str] = []
    if pool:
        up = _center(tuple(canvas.rooms[spine[0]][:4]))
        _placed, missing = _stamp_stage(rng, canvas, plan, pool, spine, up, pinned)
    return spine, missing


def _layout_for(plan: dict):
    """The layout stage a plan asks for: the wander layout or the spine.

    One place, read by the door and by the parity reference alike, so a floor
    is never laid out by one layout in the spec and by the other in a test.
    """
    return _wander_stage if plan.get("layout") == "wander" else _layout_stage


# How many carved tiles a socket's corridor may end on, tried nearest
# first. ADR 0013 says a corridor starts at a socket mouth and takes the
# first bend that crosses no locked tile; it does not name the corridor's
# far end, because a corridor's far end is a room this one has not been
# placed next to yet. So the far end is the nearest carved tile, and the
# next few nearest ones after that, in a fixed order and with no draw.
STAMP_ROUTE_ENDS = 4


# --------------------------------------------------------- the stamped rooms
# ADR 0013's Placement section, in the layout stream. A stamped room is a
# hand-drawn grid pasted onto the floor: it is not a rectangle, it is
# locked once painted, and it is reached by one corridor out of one of
# its own sockets. Everything here is a function of the layout stream and
# of the pack, so `vefr stamp check` and a JavaScript twin see the same
# room in the same place.
#
# Nothing in this section draws a number that the plan stage did not
# already draw. The slot list is arithmetic on `quota` and `secrets`, and
# a Section that names no tags places no stamps, so a floor without
# stamps is laid out exactly as it was before this section existed.


def _stamp_pool(section: dict, pack: list[dict], depth: int) -> list[dict]:
    """The stamps this Section may use on a floor `depth` steps into it.

    ADR 0013's eligibility rule: the Section's `stamps` tags have to
    overlap the stamp's own tags - or name `any`, which every stamp
    matches - and `depth` has to be inside the stamp's own depth range,
    which is `k`, the floor's 1-based position in its Section.

    The pack arrives in sorted id order from `stamps.load` and is walked in
    that order, so a weighted draw over a role is the same in every
    language.
    """
    tags = {str(tag) for tag in _names(section.get("stamps"), ())}
    if not tags or not pack:
        return []
    pool = []
    for record in pack:
        if stamps.ANY_TAG not in tags and not tags & set(record["tags"]):
            continue
        # A Section that names no vault has no vault to open, and a vault
        # room is a locked door and a note rather than a place to walk
        # into, so its stamp never enters the pool. The slot is still
        # there and takes no draw, which is the rule the layout stage
        # comment writes.
        if record["role"] == "vault" and not section.get("vault"):
            continue
        low, high = record["depth"]
        if low <= depth <= high:
            pool.append(record)
    return pool


def stamp_pool(section: dict, pack: list[dict], depth: int) -> list[dict]:
    """The public face of `_stamp_pool`, for `vefr stamp check`.

    The check has to ask the same eligibility question a floor asks, or
    a rate it reports is a rate against a second copy of the rule. It
    draws nothing and places nothing, so it is safe to call from a
    sweep; the twin writes its own, from this docstring.
    """
    return _stamp_pool(section, pack, depth)


def _stamp_slots(plan: dict) -> list[str]:
    """The roles wanted on this floor, in the order ADR 0013 places them.

    The three required roles first, one each, then `special`, `secret` and
    `filler` up to quotas the plan stage has already drawn - one special
    per eight rooms, as many secrets as the plan asked for, one filler per
    four rooms. A slot with no eligible stamp of its role takes no draw at
    all, so a pack that ships only landmarks still lays out the floor the
    other six slots would have left alone.
    """
    return (
        list(stamps.REQUIRED_ROLES)
        + ["special"] * (plan["quota"] // 8)
        + ["secret"] * plan["secrets"]
        + ["filler"] * (plan["quota"] // 4)
    )


def _weighted_stamp(rng, pool: list[dict]) -> dict:
    """One stamp of a role, by weight, walking the ids in sorted order.

    The same walk and the same cumulative sum as `_draw_family`, so a twin
    written from either one draws the same stamp.
    """
    total = sum(record["weight"] for record in pool)
    if total <= 0:
        return pool[0]
    roll = _pick(rng, total)
    walked = 0
    for record in pool:
        walked += record["weight"]
        if roll < walked:
            return record
    return pool[-1]


def _nearest_walkable(canvas: Canvas, tile: tuple[int, int], limit: int,
                      count: int) -> list[tuple[int, int]]:
    """The `count` carved tiles nearest `tile`, nearest first.

    Rings outward rather than scanning every carved tile, because a stamp
    lands against open wall and the answer is usually a tile or two away,
    and a tile is found in the same order in every language: by Manhattan
    steps first, then row-major. `limit` is the floor's long axis, so the
    search cannot run away on a floor where a room really is the far side.
    """
    tx, ty = tile
    found: list[tuple[int, int]] = []
    for radius in range(1, limit):
        ring = []
        for dy in range(-radius, radius + 1):
            across = radius - abs(dy)
            for dx in ((-across, across) if across else (0,)):
                x, y = tx + dx, ty + dy
                if 0 <= x < canvas.w and 0 <= y < canvas.h:
                    if (y * canvas.w + x) in canvas.walk:
                        ring.append((y * canvas.w + x, x, y))
        if ring:
            found.extend(entry[1:] for entry in sorted(ring))
            if len(found) >= count:
                return found[:count]
    return found


def _span(lo: int, hi: int) -> list[int]:
    """Every whole number from `lo` to `hi`, both ends, either direction."""
    step = 1 if hi >= lo else -1
    return list(range(lo, hi + step, step))


def _bends(start: tuple[int, int], end: tuple[int, int]) -> list[list[tuple[int, int]]]:
    """The two L-shaped routes between two tiles, the long way round first.

    The first runs along `start`'s row and then up `end`'s column; the
    second runs along `start`'s column and then along `end`'s row. Both
    are written out tile by tile, and both start and end where they are
    asked to.

    No draw, unlike `_link`: ADR 0013 says the first bend that crosses no
    locked tile wins, and "first" has to mean the same thing in every
    language, so the order is written down here instead of rolled.
    """
    (x0, y0), (x1, y1) = start, end
    return [
        [(x, y0) for x in _span(x0, x1)] + [(x1, y) for y in _span(y0, y1)[1:]],
        [(x0, y) for y in _span(y0, y1)] + [(x, y1) for x in _span(x0, x1)[1:]],
    ]


def _stamp_route(canvas: Canvas, rows: list[str], rect: tuple[int, int, int, int]):
    """The corridor that reaches a stamped room, or None when none does.

    Sockets are tried nearest the floor first - the mouth's Manhattan
    distance to the nearest carved tile - and a tie goes to the socket that
    comes first in row-major order, which is the order `stamps.sockets`
    already hands them over in. Each socket is tried as both L bends, and
    the first route that crosses no locked tile and no other carved tile
    wins. The route ends on the socket tile, because that is the tile the
    corridor has to claim for the room to be reached at all.

    None means the room cannot be connected from here, so the caller
    spends another attempt on a different spot.
    """
    x, y = rect[0], rect[1]
    choices = []
    for socket in stamps.sockets(rows):
        at = (socket["at"][0] + x, socket["at"][1] + y)
        mouth = (socket["mouth"][0] + x, socket["mouth"][1] + y)
        ends = _nearest_walkable(canvas, mouth, max(canvas.w, canvas.h),
                                 STAMP_ROUTE_ENDS)
        if not ends:
            continue
        # `socket["at"]` is the row-major tie-break; the record's own
        # order is never sorted, so a twin walking the same list lands on
        # the same socket.
        walk = abs(mouth[0] - ends[0][0]) + abs(mouth[1] - ends[0][1])
        choices.append((walk, socket["at"], socket, at, mouth, ends))
    for _nearest, _row_major, socket, at, mouth, ends in sorted(choices, key=lambda c: c[:2]):
        for target in ends:
            for bend in _bends(mouth, target):
                tiles = bend + [at]
                if _route_clear(canvas, tiles, rect, at, target):
                    return socket, tiles
    return None


def _route_clear(canvas: Canvas, tiles: list[tuple[int, int]],
                 rect: tuple[int, int, int, int], at: tuple[int, int],
                 target: tuple[int, int]) -> bool:
    """True when a route stays inside the grid and out of everything carved.

    Three rules, all of them the same rule seen from a different side: a
    corridor does not cut through a room. It may not cross a tile a
    stamped room locked (ADR 0013, Placement 3), it may not cross any
    tile of the room it is being routed to except the socket it comes in
    through - walls included, or a corridor would run through a hand-drawn
    wall - and it may not cross a carved tile at all except the one carved
    tile it ends on, which is the room it is joining.
    """
    x, y, width, height = rect
    for x0, y0 in tiles:
        if not (0 <= x0 < canvas.w and 0 <= y0 < canvas.h):
            return False
        if (x0, y0) == at or (x0, y0) == target:
            continue
        if x <= x0 < x + width and y <= y0 < y + height:
            return False
        if (y0 * canvas.w + x0) in canvas.locked:
            return False
        if (y0 * canvas.w + x0) in canvas.walk:
            return False
    return True


def _lay_stamp(canvas: Canvas, rows: list[str], rect: tuple[int, int, int, int],
               record: dict, o: int) -> dict | None:
    """Check the spot, route one corridor to it, then paint it.

    Nothing is carved until both checks pass, so a rejected attempt costs
    four draws and leaves the floor exactly as it was.
    """
    if not _fits_stamp(canvas, rect):
        return None
    found = _stamp_route(canvas, rows, rect)
    if found is None:
        return None
    socket, tiles = found
    width, height = len(rows[0]), len(rows)
    index = len(canvas.rooms)
    canvas.rooms.append([rect[0], rect[1], width, height, record["role"]])
    canvas.carve_stamp(rows, rect, index, socket["at"])
    canvas.stamp_corridor(tiles, index, rect)
    named = stamps.anchors(rows, record["legend"])
    placement = {
        "id": record["id"],
        "role": record["role"],
        "orientation": o,
        "room": index,
        "at": [rect[0], rect[1]],
        "size": [width, height],
        "anchors": {
            entry["anchor"]: [entry["at"][0] + rect[0], entry["at"][1] + rect[1]]
            for entry in named.values()
        },
    }
    # The socket the corridor came in through, in floor coordinates. A
    # room with no used socket is a room nothing can reach, so the record
    # names the one that was used; the others became wall when the room
    # was painted.
    placement["socket"] = [socket["at"][0] + rect[0], socket["at"][1] + rect[1]]
    if socket["kind"] == "secret":
        placement["secret"] = placement["socket"]
    if record["poi"]:
        placement["poi"] = record["poi"]
    canvas.stamps.append(placement)
    return placement


def _try_stamp(rng, canvas: Canvas, record: dict) -> dict | None:
    """Up to 24 attempts at one stamp, three draws each, in this order:

    the orientation, then `x`, then `y`. The first attempt that fits and
    can be reached is taken; all 24 failing gives up the slot. A stamp too
    big for the floor at any orientation takes no draw at all and gives up
    at once, which is what keeps a 21x21 landmark from burning a floor's
    attempt budget on a 48x32 grid.
    """
    allowed = stamps.orientations(record)
    for _ in range(stamps.ATTEMPTS):
        o = allowed[_pick(rng, len(allowed))]
        rows = stamps.orient(record["rows"], o)
        width, height = len(rows[0]), len(rows)
        if width + 2 > canvas.w or height + 2 > canvas.h:
            return None
        rect = (_rand(rng, 1, canvas.w - width - 1),
                _rand(rng, 1, canvas.h - height - 1), width, height)
        placed = _lay_stamp(canvas, rows, rect, record, o)
        if placed is not None:
            return placed
    return None


# The two required roles ADR 0013 names a position for, in the order it
# names them: the warden-hall at the far end of the spine, the vault in
# the corner farthest from `up`. The landmark is a required role and is
# not in here, because the ADR gives it no position.
_PINNED_ROLES = ("warden-hall", "vault")


# The pinned try's two named positions, in the order ADR 0013 gives them.
# The last try draws nothing at all, so these have to be named rather than
# sampled: the warden-hall goes at the far end of the spine, the vault in
# the corner farthest from `up`.
def _ordered_spots(canvas: Canvas, around: tuple[int, int]) -> list[tuple[int, int]]:
    """Every spot a stamp may be pinned to, `around` first.

    Nearest by Manhattan steps, ties row-major, so the list is a fixed
    order and not a draw: the same floor pins to the same spot in every
    language. The border is left out because `_fits` needs a wall row
    round every room.
    """
    return sorted(
        ((x, y) for y in range(1, canvas.h - 1) for x in range(1, canvas.w - 1)),
        key=lambda spot: (abs(spot[0] - around[0]) + abs(spot[1] - around[1]),
                          spot[1], spot[0]),
    )


def _pin_spots(canvas: Canvas, role: str, spine: list[int], up: tuple[int, int]):
    """The spots a required stamp is pinned to on the last try, in order."""
    if spine and role == "warden-hall":
        # The far end of the spine: the last spine room, and outward
        # from it, so the hall is at the end of the walk rather than in
        # the first free corner the sweep reaches.
        x, y, width, height = canvas.rooms[spine[-1]][:4]
        yield from _ordered_spots(canvas, (x + width - 1, y + height // 2))
        return
    corners = [(1, 1), (canvas.w - 2, 1), (1, canvas.h - 2), (canvas.w - 2, canvas.h - 2)]
    for corner in sorted(corners,
                         key=lambda c: (-(abs(c[0] - up[0]) + abs(c[1] - up[1])), c)):
        yield from _ordered_spots(canvas, corner)


def _faces_centre(rows: list[str], rect: tuple[int, int, int, int],
                  centre: tuple[int, int]) -> bool:
    """True when one of the room's sockets opens towards the floor's centre.

    "Towards" is the axis the mouth points along, plus the other axis
    staying inside the room's own span, so a corridor leaving a west wall
    mid-height counts as facing a centre that is east of it and level.
    """
    x, y, width, height = rect
    for socket in stamps.sockets(rows):
        mx = socket["mouth"][0] + x
        my = socket["mouth"][1] + y
        dx, dy = socket["step"]
        if dx and (centre[0] - mx) * dx > 0 and abs(centre[1] - my) <= height:
            return True
        if dy and (centre[1] - my) * dy > 0 and abs(centre[0] - mx) <= width:
            return True
    return False


def _pin_stamp(canvas: Canvas, record: dict, spine: list[int],
               up: tuple[int, int]) -> dict | None:
    """The last try's placement for one required stamp: no draws at all.

    The first id of the role in sorted order, the first allowed
    orientation whose mouth faces the floor's centre, and the first spot
    the role is pinned to that fits and can be reached. ADR 0013 names a
    pinned position for the warden-hall and for the vault; the landmark
    keeps the ordinary 24 attempts, because a named position for it was
    never written down and inventing one here would be a second rule the
    twin does not have.
    """
    allowed = stamps.orientations(record)
    centre = (canvas.w // 2, canvas.h // 2)
    for along, across in _pin_spots(canvas, record["role"], spine, up):
        for o in allowed:
            rows = stamps.orient(record["rows"], o)
            rect = (along, across, len(rows[0]), len(rows))
            if rect[0] + rect[2] > canvas.w - 1 or rect[1] + rect[3] > canvas.h - 1:
                continue
            if not _faces_centre(rows, rect, centre):
                continue
            placed = _lay_stamp(canvas, rows, rect, record, o)
            if placed is not None:
                return placed
    return None


def _stamp_stage(rng, canvas: Canvas, plan: dict, pool: list[dict],
                 spine: list[int], up: tuple[int, int],
                 pinned: bool) -> tuple[list[dict], list[str]]:
    """Place this floor's stamped rooms, in ADR 0013's order.

    The three required roles first, then the optional slots, each one
    drawing its stamp by weight and then spending up to 24 attempts on a
    spot. A stamp that reaches `max_per_floor` drops out of its role's
    choices, so neither the draw nor the pinned try picks one that is
    already on the floor.

    Returns the placements and the required roles that wanted a stamped
    room and did not get one: the caller fails the floor over that, and
    the retry ladder draws the same floor key again with `|try{n}`.

    On the last try `pinned` is true and the warden-hall and the vault -
    the two roles ADR 0013 names spots for - skip the attempts and the
    draw and take their named positions instead, before any other room.
    The landmark keeps the ordinary 24 attempts: ADR 0013 gives no named
    position for it, and inventing one here would be a rule the twin does
    not have. The pinned roles take no weighted draw either, so the last
    try's stream is its own.
    """
    groups: dict[str, list[dict]] = {}
    for record in pool:
        groups.setdefault(record["role"], []).append(record)
    used: dict[str, int] = {}
    placed: list[dict] = []
    missing: list[str] = []
    for role in _stamp_slots(plan):
        # `max_per_floor` is the limit a stamp declares for itself and it
        # holds on the pinned path too: the pinned try takes the first id
        # of the role in sorted order, and a stamp already on the floor
        # has spent its place on this floor whichever try placed it.
        choices = [record for record in groups.get(role, [])
                   if used.get(record["id"], 0) < record["max_per_floor"]]
        if pinned and role in _PINNED_ROLES:
            got = _pin_stamp(canvas, choices[0], spine, up) if choices else None
        else:
            got = _try_stamp(rng, canvas, _weighted_stamp(rng, choices)) if choices else None
        if got is None:
            if role in stamps.REQUIRED_ROLES:
                missing.append(role)
            continue
        used[got["id"]] = used.get(got["id"], 0) + 1
        placed.append(got)
    return placed, missing


# ----------------------------------------------------------------- stage 3
# the graph stage - no draws at all. It reads the layout back out of the
# grid, exactly the way `tests/test_floor_v3_properties.py` does, so the
# main path the warden and the chests are placed against is the same
# main path the sweep measures.
#
#  1. A node per room, in `rooms` order, then a node per maximal
#     4-connected run of corridor tiles. Corridor nodes are numbered in
#     the row-major order of their first tile, so the numbering matches
#     the sweep's to the node.
#  2. An edge when a corridor tile is 4-adjacent to a room tile, and
#     when two room tiles are 4-adjacent across no corridor.
#  3. The main path is a breadth-first walk of that region graph from
#     the room holding the up-stair to the room holding the down-stair,
#     neighbours visited in ascending node order, so the lower index
#     wins a tie. Its room nodes, in order, are the main path.
#  4. Distances are counted from the up room over the room graph.
#  5. The warden goes in the farthest room off the main path, ties
#     broken by the lower room index: the gates-and-guardians rule.
#  6. The landmark goes in the next room off the path after that, and
#     the vault in the one after it when the pack names a vault.
#     A room a stamp was painted into is already the room its role
#     names, so it is used instead of being chosen: the warden hall is
#     the hall the author drew, the landmark is the one with the `poi`
#     letter, and the anchors are those letters rather than the middle
#     of the rectangle. A stamped room is left out of the off-path walk
#     below, so no room is two things at once.


def _bfs_path(adj: list[set[int]], start: int, goal: int) -> list[int] | None:
    """The shortest node path start -> goal, ties broken by node index.

    Neighbours are visited in ascending node order, so the first route
    found is the canonical one. This is the sweep's own routine, kept
    line for line: a path that differs here is a path that differs
    there, and the warden would be placed against the wrong one.
    """
    if start == goal:
        return [start]
    prev: dict[int, int | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in sorted(adj[node]):
            if nxt in prev:
                continue
            prev[nxt] = node
            if nxt == goal:
                path = [nxt]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                return path[::-1]
            queue.append(nxt)
    return None


def _bfs_depth(adj: list[set[int]], start: int, count: int) -> list[int]:
    """The hop count from `start` to every node, -1 where there is none."""
    depth = [-1] * count
    depth[start] = 0
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in sorted(adj[node]):
            if depth[nxt] < 0:
                depth[nxt] = depth[node] + 1
                queue.append(nxt)
    return depth


def _region_graph(canvas: Canvas) -> list[set[int]]:
    """The region graph: rooms first, corridor regions after.

    Read back out of the carved grid rather than kept alongside it, so
    the graph the generator reasons about is the graph a reader can
    derive from `rows` and `rooms`.
    """
    width, height = canvas.w, canvas.h
    rooms = canvas.rooms
    room_count = len(rooms)
    adj: list[set[int]] = [set() for _ in range(room_count)]
    seen: set[int] = set()
    for index in sorted(canvas.corr):
        if index in seen:
            continue
        node = len(adj)
        adj.append(set())
        seen.add(index)
        stack = [index]
        while stack:
            here = stack.pop()
            x, y = here % width, here // width
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                other = ny * width + nx
                room = canvas.owner[other]
                if room >= 0:
                    adj[node].add(room)
                elif other in canvas.corr and other not in seen:
                    seen.add(other)
                    stack.append(other)
    # Two rooms sharing a tile edge are neighbours with no corridor.
    for index, room in enumerate(rooms):
        x, y, w, h = room[0], room[1], room[2], room[3]
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                for nx, ny in ((xx + 1, yy), (xx - 1, yy), (xx, yy + 1), (xx, yy - 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    other = canvas.owner[ny * width + nx]
                    if 0 <= other != index:
                        adj[index].add(other)
                        adj[other].add(index)
    # The flood above only ever writes a corridor node's edge, so the
    # region graph is made undirected here, the way the sweep does.
    for node, neighbours in enumerate(adj):
        for other in sorted(neighbours):
            adj[other].add(node)
    return adj


def _room_graph(adj: list[set[int]], room_count: int) -> list[set[int]]:
    """The room graph: two rooms joined directly or through one corridor.

    A corridor that serves three rooms joins all three pairs, which is
    the sweep's rule and the reason a gallery corridor reads as an edge
    between every pair of rooms it runs past.
    """
    room_adj: list[set[int]] = [set() for _ in range(room_count)]
    for node, neighbours in enumerate(adj):
        low = sorted(other for other in neighbours if other < room_count)
        if node < room_count:
            for other in low:
                if other != node:
                    room_adj[node].add(other)
                    room_adj[other].add(node)
        for i, first in enumerate(low):
            for second in low[i + 1:]:
                room_adj[first].add(second)
                room_adj[second].add(first)
    return room_adj


class Graph:
    """What stage 3 reads back out of a carved floor."""

    def __init__(self, adj: list[set[int]], room_adj: list[set[int]]):
        self.adj = adj
        self.room_adj = room_adj
        self.room_count = len(room_adj)
        self.main: list[int] = []
        self.main_rooms: list[int] = []
        self.depth: list[int] = []


def _stand_in(canvas: Canvas, room: int, prefer: tuple[int, int] | None = None):
    """A tile of `room` a thing can stand on.

    The middle tile, as everywhere else in the file, unless the room is
    a stamped one: a hand-drawn room is not a filled rectangle, so its
    middle may be a drawn wall, and an anchor on a wall is an anchor
    nothing can walk to. `prefer` is the room's own named anchor - the
    warden letter of a stamped hall, the `poi` letter of a stamped
    landmark - and it wins whenever it is walkable, which is what a
    stamp is for.
    """
    x, y, width, height = canvas.rooms[room][:4]
    middle = _center((x, y, width, height))
    if prefer is not None and prefer[1] * canvas.w + prefer[0] in canvas.walk:
        return prefer
    if middle[1] * canvas.w + middle[0] in canvas.walk:
        return middle
    for yy in range(y, y + height):
        for xx in range(x, x + width):
            if (yy * canvas.w + xx) in canvas.walk:
                return (xx, yy)
    return middle


def _stamped(canvas: Canvas, role: str) -> dict | None:
    """The stamped room of a role, the first one placed, or None.

    One per role is the rule the layout stage places by, so a floor with
    two of a role takes the first and the rest are ordinary rooms with a
    story-room shape.
    """
    for placement in canvas.stamps:
        if placement["role"] == role:
            return placement
    return None


def _graph_stage(canvas: Canvas, spine: list[int], plan: dict,
                 section: dict) -> tuple[Graph, dict, list[dict], list[list]]:
    """The graph stage: the stairs, the main path, the warden, the pois.

    Nothing is drawn here. Everything below is read out of the grid the
    layout stage left, so the two stages cannot disagree about where a
    room is or which rooms the path runs through.

    A stamped room is already the room its role names, so it is used
    where a plain room would be chosen: the warden hall that was drawn
    is the warden hall, and the warden anchor is the letter the author
    drew. A stamped room is never also chosen out of `off_path`, or one
    room would be two things at once.
    """
    up_room, down_room = spine[0], spine[-1]
    up = _center(tuple(canvas.rooms[up_room][:4]))
    down = _center(tuple(canvas.rooms[down_room][:4]))
    canvas.grid[up[1]][up[0]] = UP
    canvas.grid[down[1]][down[0]] = DOWN

    adj = _region_graph(canvas)
    room_adj = _room_graph(adj, len(canvas.rooms))
    graph = Graph(adj, room_adj)
    path = _bfs_path(adj, up_room, down_room)
    if path is not None:
        graph.main = path
        graph.main_rooms = [node for node in path if node < graph.room_count]
    graph.depth = _bfs_depth(room_adj, up_room, graph.room_count)

    on_path = set(graph.main_rooms)
    drawn = {placement["room"] for placement in canvas.stamps}
    # The farthest room off the path, then the next, then the next. The
    # warden takes the first, the landmark the second, the vault the
    # third, each sorted by hop count from the up-stair and then by room
    # index so a tie never depends on a draw.
    off_path = sorted(
        (room for room in range(graph.room_count)
         if room not in on_path and room not in drawn),
        key=lambda room: (-graph.depth[room], room),
    )
    hall = _stamped(canvas, "warden-hall")
    landmark = _stamped(canvas, "landmark")
    vault = _stamped(canvas, "vault")
    warden_room = hall["room"] if hall else (off_path[0] if off_path else up_room)
    landmark_room = landmark["room"] if landmark else (
        off_path[1] if len(off_path) > 1 else warden_room)
    vault_room = None
    if section.get("vault"):
        # A Section that names no vault has no vault to open, so the floor
        # gets no vault anchor and no vault point of interest out of the
        # off-path walk. The pool keeps a vault stamp off such a Section's
        # floors already, and this is the same rule read at the other end
        # of the floor: an anchor is the Section's promise, not the
        # placer's to make, and one that points at nothing is worse than
        # no anchor at all.
        vault_room = vault["room"] if vault else (
            off_path[2] if len(off_path) > 2 else None)

    # A stamp reads as the room it sits in, so the room that holds the
    # warden hall, the landmark or the vault is named in `rooms`.
    if hall is None:
        canvas.rooms[warden_room][4] = "hall"
    if landmark is None:
        canvas.rooms[landmark_room][4] = "landmark"
    if vault_room is not None and vault is None:
        canvas.rooms[vault_room][4] = "vault"

    names = _names(section.get("pois"), FALLBACK_POIS)
    poi_at = _stand_in(canvas, landmark_room, _at_of(landmark, "poi"))
    pois = [{
        "at": [poi_at[0], poi_at[1]],
        "name": (landmark["poi"] if landmark and landmark.get("poi")
                 else names[plan["flavour"] % len(names)]),
        "stamp": landmark["id"] if landmark else "landmark",
    }]
    if vault_room is not None and vault is None:
        vault_at = _stand_in(canvas, vault_room)
        pois.append({
            "at": [vault_at[0], vault_at[1]],
            "name": names[(plan["flavour"] + 1) % len(names)],
            "stamp": "vault",
        })

    # A leaf room is a room with one way in, and PLAN.md section 2 turns
    # leaves into secret rooms. The stamp rooms are spoken for already.
    taken = {warden_room, landmark_room}
    if vault_room is not None:
        taken.add(vault_room)
    leaves = [
        room for room in range(graph.room_count)
        if room not in taken and room not in on_path
        and len(room_adj[room]) == 1
    ]
    secrets = []
    for room in leaves[:plan["secrets"]]:
        x, y = _center(tuple(canvas.rooms[room][:4]))
        secrets.append([x, y])
    # A used `?` is the secret, wherever the room sits (ADR 0013,
    # Placement 3). The stamped rooms are not leaves in this list - a
    # secret room has no door at all - so nothing is counted twice.
    for placement in canvas.stamps:
        if "secret" in placement:
            secrets.append(list(placement["secret"]))

    anchors = {
        "up": [up[0], up[1]],
        "down": [down[0], down[1]],
        "warden": None,
        "vault": None,
        "landmark": [poi_at[0], poi_at[1]],
    }
    warden_at = _stand_in(canvas, warden_room, _at_of(hall, "warden"))
    anchors["warden"] = [warden_at[0], warden_at[1]]
    if vault_room is not None:
        x, y = _stand_in(canvas, vault_room)
        anchors["vault"] = [x, y]
    return graph, anchors, pois, secrets


def _at_of(placement: dict | None, name: str) -> tuple[int, int] | None:
    """One named anchor of a placement as a tile, or None when it has none."""
    if not placement:
        return None
    at = placement["anchors"].get(name)
    return (at[0], at[1]) if at else None


# ----------------------------------------------------------------- stage 4
# the pop stream - the exact order of draws. `rng()` is one call of
# `prng("v3|" + floor_key + "|pop")`, `rand(lo, hi)` is
# `lo + floor(rng() * (hi - lo + 1))` and `pick(n)` is `floor(rng() * n)`.
# ADR 0014's "Draw order" is normative and this is the same list.
#
# The candidates are read off the grid, in row-major order, BEFORE the
# first draw, and cost no draw: every walkable tile at least STAIR_CLEAR
# (7) tiles (Chebyshev) from both stairs. A tile is taken at most once.
# Two more lists come off the same read, likewise for free: the tiles a
# group leader may stand on (`clear` less every vault, hall and secret
# room, which the graph stage has already named) and, per leader, the
# small box of tiles a minion of that group may stand on.
#
# The budget is not a draw:
#       budget = the count section["mobs"] names for this floor, else
#                clamp(walkable // TILES_PER_MOB, MOBS_MIN, MOBS_MAX).
# A Section that names a count names it for its own floors (`"1": 4`) and
# for the rest (`"from": 12`); a Section that names none is the area
# budget above, exactly as it was before the key existed. Either way it is
# read before the first draw and moves no other stage. `mob_budget` is
# where both answers live, with the JavaScript twin's beside them.
#
# The hard caps are applied where the stage says and not before: 36
# monsters a floor, 2 lone elites, 3 groups, 4 members to a group, and
# one elite-led group per 8 rooms (never below 1 while the pack's
# `groups.per_floor` still asks for a group). A cap that is hit stops
# further DRAWS of that kind; it does not raise and it does not fail the
# floor. The warden is outside the budget and outside every cap here -
# ADR 0015 owns it, and no spawn carries a `warden` key until one does.
#
#  1. Elites, first. `elite_count = rand(elite_lo, elite_hi)` from
#     `section["elites"]["per_floor"]`, drawn ONCE and before the loop.
#     A pack that names a count and no affix table still draws that
#     count and then places nothing, so the stream does not move when
#     only the table changes. Then, per elite, in this order: a family
#     by weight, an affix by index from `["affixes"]`, then a tile.
#  2. Groups, next. `group_count = rand(group_lo, group_hi)` from
#     `section["groups"]["per_floor"]`, drawn once before its loop, for
#     the same reason. Then, per group, in this order: the minion count
#     `rand(minion_lo, minion_hi)` capped to GROUP_MEMBERS_MAX - 1, the
#     leader's family, the leader's affix (only when `groups.leader` is
#     `elite` and the pack names affixes), the leader's tile, and then
#     per minion a family - only when `same_family` is false - and a
#     tile within MINION_REACH (2, Chebyshev) of the leader and in the
#     leader's own room or corridor region. The leash is neither a draw
#     nor a placement: `groups.leash` is a number the pack wrote, so it
#     rides on every member's spawn the moment a group exists, and on
#     none of them when the Section named none.
#  3. Randoms, last, filling the budget the elites and the groups left.
#     For each, in order: a family by weight, then a tile. A pack that
#     names no elite and no group therefore carries exactly the budget.
#  4. Chests: count = min(rand(2, 2 + quota // 8), the number of rooms
#     off the main path no mob holds). Rooms off the main path first,
#     farthest from the up-stair first; a room whose centre a monster,
#     an elite, a minion or a leader already holds is dropped, and a
#     table by index from CHEST_TABLES per chest. Every chest lands off
#     the main path, so the whole of the floor's chest value is off it
#     and exploring pays.
#
# The lists above are the ORDER THE DRAWS HAPPEN IN, and a placement is
# not a draw: the tile is settled first, and a monster with nowhere to
# stand spends NOTHING - no family, no affix. So a leader on a floor
# whose stamp rooms leave no free tile, or a random on a floor whose
# clear tiles run out, costs the stream no draw at all, and the chest
# count and every chest table after it stay where the floor key says
# they are. One rule, four places: elite, group leader, minion, random.
# The count draws - the elite count, the group count and each group's
# minion count - are the exception and stay where ADR 0014 lists them,
# ahead of the tile: a count is a statement of its own, drawn whether or
# not the loop it opens goes on to place anything. A draw that never
# happens cannot be out of order.
#
# The ids follow the draws: a monster is `m<n>` in draw order, so the
# first draw of the stage is `m0` and the counter never runs ahead of
# the stream. A group is `g<n>` in group order.
#
# A spawn carries the closed keys of ADR 0014 and no others: `id`,
# `family`, `at`, then `elite`, `group`, `leader` and `leash` where they
# apply (`leader` as `true` and as nothing else, `leash` on every member
# of a group and only when the Section named one). The eight are the
# whole set, so a spawn carries no `hp`, `atk` or `xp`: those are not in
# the ADR's list, and a monster's stats are the balance report's to
# compute off the same closed Section data rather than a FloorPlan field.
#
# The chest value of a table is `section["chest_values"][table]`, or 1
# when the pack does not name it. No chest is placed by its value, so
# no table can move a chest onto the path.


def _eligible(canvas: Canvas, stairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Every walkable tile clear of both stairs, in row-major order."""
    width = canvas.w
    clear: list[tuple[int, int]] = []
    for index in sorted(canvas.walk):
        x, y = index % width, index // width
        if all(max(abs(x - sx), abs(y - sy)) >= STAIR_CLEAR for sx, sy in stairs):
            clear.append((x, y))
    return clear


# ---- the spread: which of those tiles a monster stands on ----
#
# The pool is walked in row-major order and the first free tile wins, so
# without this every floor packed its monsters into its top rows: the
# first spawn took (0, 0)-ish, the next the tile after it, and a floor
# 96 rows deep never put a monster below row 2. Six goldens said the
# same thing - spawn y 1..2 on four of them, a single row on the other
# two - which is a floor where the whole population stands shoulder to
# shoulder by the north wall and the rest of the map is empty.
#
# The fix costs no draw. The tiles are REORDERED, not chosen from: the
# same pool of every walkable tile clear of the stairs, walked in an
# order that scatters instead of packing, and the first free tile is
# still the one that wins. A draw-free rule keeps the pop stream
# reading the same in both languages, which is PLAN.md section 2's
# sub-seed rule: a pack with an elite count and no affix table has to
# consume exactly the same draw either way.
#
# The order is a rank per tile, lowest first, ties broken row-major. The
# rank is a 32-bit mix of the floor key and the tile's own coordinates,
# and both halves are plain integer arithmetic so a JavaScript twin can
# write the same five lines and get the same floor. Python's `hash` is
# not used and cannot be: it is salted per process, so two runs of the
# same seed would stop being the same floor.


def _key_salt(floor_key: str) -> int:
    """The floor key as a 32-bit number: FNV-1a over its UTF-8 bytes.

    FNV-1a, the same hash the v2 twin and the benches checksum with.
    Every step is a mask or a shift, so `Math.imul` and `>>> 0` in
    JavaScript are the same function.
    """
    h = 0x811C9DC5
    for byte in floor_key.encode("utf-8"):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return h


def _tile_rank(salt: int, x: int, y: int) -> int:
    """Where one tile falls in its floor's spread order, 0 to 2**32-1.

    Two multiplies, two shifts, no table: the coordinates go in
    through a multiply-shift of their own so that neighbouring tiles do
    not land on neighbouring ranks, and the high bits are folded back
    down so a rank is not read mostly out of the low half of the
    multiply.
    """
    h = (salt ^ ((x + 1) * 0x9E3779B1)) & 0xFFFFFFFF
    h = (h * 0x85EBCA6B + (y + 1) * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 0x2545F491) & 0xFFFFFFFF
    return h ^ (h >> 13)


def _spread(tiles: list[tuple[int, int]], salt: int) -> list[tuple[int, int]]:
    """`tiles`, in the order this floor's seed scatters them.

    The same list, permuted: no tile is added and none is dropped, so
    the pool a floor can place on is exactly the pool it could place on
    before. The `(y, x)` tail of the key makes the order total, so two
    tiles that rank the same - a pair in a thousand, a million tiles
    down - are still placed in a fixed order rather than in whatever
    order the sort happened to find them.
    """
    return sorted(tiles, key=lambda tile: (_tile_rank(salt, tile[0], tile[1]),
                                           tile[1], tile[0]))


def _stamp_free(canvas: Canvas, clear: list[tuple[int, int]],
                secrets: list[list[int]]) -> list[tuple[int, int]]:
    """`clear` less every room a group leader may not stand in.

    The graph stage has already named what is spoken for: the warden's
    room and the vault are the two stamp shapes in `rooms[i][4]`, and a
    secret room is a leaf room whose centre is in `secrets`. Both are
    read off what stage 3 wrote, so the two stages cannot disagree about
    which rooms a leader has to keep out of. The result is a filter of
    `clear` and keeps whatever order `clear` is in, so a leader pool is
    the same spread walk with fewer tiles in it - no second sort, and no
    chance of the two pools disagreeing about which tile comes first.
    """
    spoken_for = {index for index, room in enumerate(canvas.rooms)
                  if room[4] in STAMP_ROOMS}
    for tile in secrets:
        for index, room in enumerate(canvas.rooms):
            if (room[0] <= tile[0] < room[0] + room[2]
                    and room[1] <= tile[1] < room[1] + room[3]):
                spoken_for.add(index)
    blocked: set[tuple[int, int]] = set()
    for index in sorted(spoken_for):
        x, y, width, height = canvas.rooms[index][:4]
        for yy in range(y, y + height):
            for xx in range(x, x + width):
                blocked.add((xx, yy))
    return [tile for tile in clear if tile not in blocked]


def _neighbourhood(tile: tuple[int, int], width: int, height: int,
                   reach: int) -> list[tuple[int, int]]:
    """The tiles within `reach` of `tile`, in row-major order.

    Row-major, and NOT the spread order the pop stage walks its pools
    in, and that difference is the point. A minion is placed within
    `MINION_REACH` of its own leader: the box is twenty-five tiles at a
    reach of 2, against a pool of thousands, and scattering those
    twenty-five would scatter a group across the floor and break ADR
    0014's "within 2 tiles of its leader" before it ever got measured.
    Inside the box the order is a tie-break between tiles that are all
    next to the same leader anyway, and row-major is the tie-break
    every language can write without a hash.

    Membership is the pop stage's business, not this box's: the caller
    filters the box by the set of tiles the pop stage could place on, so
    a minion can only stand where a random could have stood.
    """
    return [(xx, yy)
            for yy in range(max(0, tile[1] - reach), min(height, tile[1] + reach + 1))
            for xx in range(max(0, tile[0] - reach), min(width, tile[0] + reach + 1))]


def _corridor_regions(canvas: Canvas) -> dict[int, int]:
    """Each corridor tile's region, numbered in row-major first-tile order.

    Built only when a group leader stands on a corridor, and kept for the
    rest of the floor. `Canvas.owner` already answers the room half of
    ADR 0014's "same room or corridor region"; this answers the corridor
    half, and it numbers the regions by the row-major order of their
    first tile so a number never depends on a hash seed.
    """
    width = canvas.w
    regions: dict[int, int] = {}
    number = 0
    for start in sorted(canvas.corr):
        if start in regions:
            continue
        regions[start] = number
        stack = [start]
        while stack:
            here = stack.pop()
            x, y = here % width, here // width
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not (0 <= nx < width and 0 <= ny < canvas.h):
                    continue
                other = ny * width + nx
                if other in canvas.corr and other not in regions:
                    regions[other] = number
                    stack.append(other)
        number += 1
    return regions


def _pop_stage(rng, canvas: Canvas, graph: Graph, plan: dict, section: dict,
               up: tuple[int, int], down: tuple[int, int],
               secrets: list[list[int]], floor_key: str, k: int = 1):
    """The pop stage: elites, groups, randoms and chests.

    `k` is `depth`, the floor's 1-based position in its Section, and it is
    what the Section's own `mobs` table is read against (`mob_budget`). It
    is read, never drawn, and no other stage of the floor is given it.
    """
    # The pool, in the order this floor's seed scatters it (see
    # `_spread`). One sort, before the first draw, and no draw spent on
    # it: the pool is the same set of tiles either way, only the order
    # it is walked in changes, and a floor that packed its monsters into
    # the top two rows is the thing being fixed.
    clear = _spread(_eligible(canvas, [up, down]), _key_salt(floor_key))
    # A leader's pool and a minion's box, both read off the grid before
    # the first draw, so neither costs one. `_stamp_free` filters `clear`,
    # so the leader pool is already in the spread order.
    leaders_clear = _stamp_free(canvas, clear, secrets)
    clear_set = set(clear)
    # Two different questions, so two different sets. `taken` holds the
    # TILES `take()` has handed out, and `occupied` holds every tile a
    # monster, an elite, a minion or a chest holds. One set cannot answer
    # both: a chest's tile is only ever added to `occupied`, so a chest
    # filter reading `taken` would drop nothing.
    taken: set[tuple[int, int]] = set()
    occupied: set[tuple[int, int]] = set()
    # The index of the first candidate not yet taken. Tiles only ever
    # leave the list, so this walks forward and never looks back unless
    # a leader or a minion takes a tile out of order.
    cursor = 0
    # The corridor regions, built the first time a leader stands on one.
    corr_regions: dict[int, int] | None = None

    def take(pool: list[tuple[int, int]],
             near: tuple[int, int] | None = None) -> tuple[int, int] | None:
        """The first free tile of `pool`, in the order `pool` is in.

        One routine, three pools. `clear` is every walkable tile clear of
        the stairs, in this floor's spread order, and its cursor walks
        forward because a tile only ever leaves the list; a leader's
        pool is `clear` less the rooms that are spoken for, which is the
        same order with fewer tiles; a minion's pool is the small box
        around its leader, already filtered to `clear`, and the leader's
        own region is applied on top of it.

        Two orders, and both are fixed. `clear` and the leader's pool
        are walked in the seed's spread order, so the monsters of a
        floor are scattered over it instead of packed into its top
        rows; the minion box is walked row-major, because a minion has
        to stay within `MINION_REACH` of its own leader and there is no
        room in a twenty-five tile box to spread anything. Neither order
        is a draw, so the pop stream is the same either way and a
        JavaScript twin can replay it from the floor key.
        """
        nonlocal cursor
        if near is None and pool is clear:
            while cursor < len(clear) and clear[cursor] in taken:
                cursor += 1
            if cursor >= len(clear):
                return None
            tile = clear[cursor]
            cursor += 1
        else:
            tile = None
            for candidate in pool:
                if candidate in taken:
                    continue
                if near is not None and not _same_region(canvas, near, candidate,
                                                         corr_regions):
                    continue
                tile = candidate
                break
            if tile is None:
                return None
        taken.add(tile)
        occupied.add(tile)
        return tile

    families = _read_families(section)
    spawns: list[dict] = []

    def place(tile: tuple[int, int], family: str, elite: str | None = None,
              group: str | None = None, leader: bool = False,
              leash: int | None = None) -> None:
        """One spawn, in the closed FloorPlan shape of ADR 0014.

        The keys are the ADR's and the ADR's only: `id`, `family`, `at`,
        then `elite`, `group`, `leader` and `leash` where they apply.
        `leader` is written as `true` and as nothing else, and `warden` is
        never written - ADR 0015 owns it and no warden exists yet.

        `leash` rides along only when the Section named one, and on EVERY
        member of the group rather than on the leader alone, because the
        player reads it off a spawn record and asks any member for it
        (part 420's `groupLeash`). A pack that wrote `groups.leash: 9` and
        got spawns with no `leash` on them had a floor where every group
        walked on the player's own default of 6, and nothing said so.

        No stat is written. ADR 0014 closes the FloorPlan spawn keys at
        those eight, so a spawn carries no `hp`, `atk` or `xp`, and the
        `vefr.mob_stats` call is not made here at all: the numbers are
        the balance report's to compute (E10), off the same closed
        Section data, and a spawn that carried them would carry a key
        the ADR does not list.
        """
        spawn = {
            "id": f"m{len(spawns)}",
            "family": family,
            "at": [tile[0], tile[1]],
        }
        if elite is not None:
            spawn["elite"] = elite
        if group is not None:
            spawn["group"] = group
        if leader:
            spawn["leader"] = True
        if leash is not None:
            spawn["leash"] = leash
        spawns.append(spawn)

    # The budget. `MOBS_MAX` is this clamp's ceiling and is also ADR
    # 0014's cap of 36 monsters, so nothing below can pass it. The
    # elites and the group members below are reserved out of it FIRST;
    # the randoms fill whatever is left over. A Section that names its
    # own count for this floor (`mobs`) replaces the area budget whole -
    # see `mob_budget`, which is also where `delve.mobs_at` and the
    # player's twin get theirs.
    budget = mob_budget(section, len(canvas.walk), k)

    # 1. Elites, in the ADR's order and before anything else.
    #
    # The count draw is a statement of its own, made BEFORE the loop, and
    # the stage above says why: a pack with an elite count and no affix
    # table has to consume exactly the same draw a pack with one does. A
    # count written inside the `range()` call would read as "the count is
    # only drawn when there are affixes", and the two streams would part
    # the first time a pack gained a table. So the count is drawn, the
    # loop runs, and a pack with no table places nothing.
    #
    # Per elite, in the ADR's order: a family, an affix by index, then a
    # tile. The tile is placed rather than drawn, so it costs no draw -
    # and it is placed FIRST, so an elite whose floor has no clear tile
    # left spends no family and no affix either. LONE_ELITES_MAX stops
    # the loop: a cap that is hit stops further draws of that kind, it
    # does not raise and it does not fail the floor.
    elite_lo, elite_hi, affix_ids = _read_elites(section)
    elite_count = _rand(rng, elite_lo, elite_hi)
    lone = 0
    for _ in range(elite_count):
        if not affix_ids:
            continue
        if lone >= LONE_ELITES_MAX or len(spawns) >= budget:
            break
        tile = take(clear)
        if tile is None:
            break
        family = _draw_family(rng, families)
        affix = affix_ids[_pick(rng, len(affix_ids))]
        place(tile, family, elite=affix)
        lone += 1

    # 2. Groups. The count draw is a statement of its own here too, for
    # the same reason. Per group, in the ADR's order: the minion count,
    # the leader's family, the leader's affix when the group is led by
    # an elite, the leader's tile, and then per minion a family (only
    # when `same_family` is false) and a tile within MINION_REACH of the
    # leader and in the leader's own room or corridor region. The
    # leader's tile is placed before its two draws, for the elites' own
    # reason: `leaders_clear` is `clear` less the vault, hall and secret
    # rooms, so it is the pool most likely to run out, and a group that
    # never got a leader must not spend a family and an affix on it.
    #
    # Two caps stop the loop, and both stop DRAWS rather than only
    # placement: GROUPS_MAX groups a floor, and one elite-led group per
    # ROOMS_PER_ELITE_GROUP rooms - never below one, while the Section's
    # own `groups.per_floor` still asks for a group at all.
    group_lo, group_hi, minion_lo, minion_hi, led_by, same_family, leash = \
        _read_groups(section)
    # ADR 0014's own phrasing of the cap: "1 elite-led group per 8 rooms,
    # but at least 1 when the Section's `per_floor` range asks for one",
    # and the range asks for one whenever either of its ends says so. The
    # question is asked of BOTH ends rather than of the high one alone,
    # because the high bound is the end a pack writes to cap itself and
    # the low bound is the end it writes to ask - and a Section that
    # writes `per_floor: [1, 0]` is asking. `_demand` above is what makes
    # that true of the draw as well as of the cap; before it, the same
    # pack was read as `rand(0, 1)` and half its floors carried no group
    # at all, with a cap of one waiting behind a count of zero.
    asks_for_a_group = group_lo > 0 or group_hi > 0
    elite_led_cap = (max(1, graph.room_count // ROOMS_PER_ELITE_GROUP)
                     if asks_for_a_group else 0)
    group_count = _rand(rng, group_lo, group_hi)
    elite_led = 0
    for number in range(group_count):
        if number >= GROUPS_MAX or len(spawns) >= budget:
            break
        if led_by == "elite" and elite_led >= elite_led_cap:
            break
        minion_count = min(_rand(rng, minion_lo, minion_hi), GROUP_MEMBERS_MAX - 1)
        leader = take(leaders_clear)
        if leader is None:
            break
        leader_family = _draw_family(rng, families)
        leader_affix = None
        if led_by == "elite" and affix_ids:
            leader_affix = affix_ids[_pick(rng, len(affix_ids))]
        if canvas.owner[leader[1] * canvas.w + leader[0]] < 0 and corr_regions is None:
            corr_regions = _corridor_regions(canvas)
        group = f"g{number}"
        place(leader, leader_family, elite=leader_affix, group=group,
              leader=True, leash=leash)
        if led_by == "elite":
            elite_led += 1
        # The box is a property of the leader, not of the minion, so it
        # is built once per group. `take` drops the tiles it hands out,
        # so the second minion reads the same box and gets the next free
        # tile in it.
        box = [tile for tile
               in _neighbourhood(leader, canvas.w, canvas.h, MINION_REACH)
               if tile in clear_set]
        # The tile is placed before the family is drawn, and that is the
        # whole point of the order: a placement costs no draw, so a box
        # with nowhere left to put a minion spends NOTHING on it. Draw
        # the family first, as the ADR's draw order lists the two, and a
        # minion that is never placed still takes a draw with it - one
        # draw out of step, and then the next group's family, the next
        # random's family and both chest tables are all one draw away
        # from where the floor key says they are. The ADR's order is the
        # order the DRAWS happen in, and a draw that never happens cannot
        # be out of order. Same rule as the elite's tile above and the
        # random's below: the tile first, and only then what the monster
        # standing on it is.
        for _ in range(minion_count):
            if len(spawns) >= budget:
                break
            tile = take(box, near=leader)
            if tile is None:
                break
            family = leader_family if same_family else _draw_family(rng, families)
            place(tile, family, group=group, leash=leash)

    # 3. Randoms, filling the budget the elites and the groups left. Per
    # random: a family, then a tile - and the tile is placed first, for
    # the same reason as the three above. A cramped floor is the case
    # that reaches it: `budget` clamps to four even where the walkable
    # tiles are counted in dozens, and the seven-tile exclusion around
    # each stair can take that many tiles away, so the last random can
    # find nothing to stand on. It then costs the floor no family, and
    # the chest count after it is where the floor key says it is.
    # A pack that names no elite and no group therefore carries exactly
    # the budget and nothing else.
    for _ in range(budget - len(spawns)):
        tile = take(clear)
        if tile is None:
            break
        family = _draw_family(rng, families)
        place(tile, family)

    chests: list[dict] = []
    off_path = sorted(
        (room for room in range(graph.room_count) if room not in set(graph.main_rooms)),
        key=lambda room: (-graph.depth[room], room),
    )
    spots = [(_center(tuple(canvas.rooms[room][:4])), room) for room in off_path]
    spots = [spot for spot in spots if spot[0] not in occupied]
    for number in range(min(_rand(rng, 2, 2 + plan["quota"] // 8), len(spots))):
        tile, _room = spots[number]
        occupied.add(tile)
        chests.append({
            "id": f"c{number}",
            "at": [tile[0], tile[1]],
            "table": CHEST_TABLES[_pick(rng, len(CHEST_TABLES))],
        })
    return spawns, chests


def _same_region(canvas: Canvas, leader: tuple[int, int], tile: tuple[int, int],
                 regions: dict[int, int] | None) -> bool:
    """Is `tile` in the leader's own room, or its own corridor region?

    ADR 0014 puts a minion "within Chebyshev 2 of the leader, in the same
    room or corridor region". The straight line is half of that and the
    region is the other half: two rooms are never laid closer than one
    wall, so a radius of 2 can reach out of the leader's room and a
    search on distance alone would put a minion through the wall into a
    room the group does not belong to.
    """
    width = canvas.w
    here = leader[1] * width + leader[0]
    there = tile[1] * width + tile[0]
    room = canvas.owner[here]
    if room >= 0:
        return canvas.owner[there] == room
    return regions is not None and regions.get(there) == regions.get(here)


# ----------------------------------------------------------------- stage 5
# the validate stage - the checks `tests/test_floor_v3_properties.py`
# runs, run again here before the caller ever sees the floor. A failure
# is not a bug in the floor, it is a bad draw: the retry ladder draws
# the same floor key with `|try{n}` appended and does it again.
#
# Nothing is drawn here either. The stage reads the plan it was handed
# and answers one question: is this floor good enough to ship?


def _flood(canvas: Canvas, start: tuple[int, int]) -> set[int]:
    """Every walkable tile 4-connected to `start`."""
    width = canvas.w
    seen = {start[1] * width + start[0]}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < width and 0 <= ny < canvas.h):
                continue
            other = ny * width + nx
            if other in canvas.walk and other not in seen:
                seen.add(other)
                stack.append((nx, ny))
    return seen


def _chest_value(section: dict, table: str) -> int:
    """What one chest is worth: the pack's table, else 1 when unmapped."""
    values = section.get("chest_values")
    if not isinstance(values, dict):
        return 1
    worth = values.get(table, 1)
    return worth if isinstance(worth, int) and not isinstance(worth, bool) else 1


def _loops(graph: Graph) -> int:
    """The cyclomatic number of the room graph: edges - nodes + 1."""
    edges = sum(len(neighbours) for neighbours in graph.room_adj) // 2
    return edges - graph.room_count + 1


def _within_one_step(graph: Graph) -> set[int]:
    """The rooms at room-graph distance 0 or 1 from the main path."""
    near = set(graph.main_rooms)
    for room in graph.main_rooms:
        near |= graph.room_adj[room]
    return near


def _validate(plan: dict, canvas: Canvas, graph: Graph, section: dict) -> bool:
    """Every property the sweep asserts, answered on the plan itself."""
    rooms = plan["rooms"]
    anchors = plan["anchors"]
    if len(rooms) < 2 or not plan["pois"]:
        return False
    if anchors["up"] is None or anchors["down"] is None or anchors["warden"] is None:
        return False
    up = (anchors["up"][0], anchors["up"][1])
    down = (anchors["down"][0], anchors["down"][1])
    if up == down:
        return False
    if section.get("layout") == "wander":
        apart = min(WANDER_APART, max(canvas.w, canvas.h) // 3)
        if max(abs(up[0] - down[0]), abs(up[1] - down[1])) < apart:
            return False

    # One connected component, and nothing carved that belongs to no room
    # and no corridor: the rooms and the corridors tile the walkable set.
    reach = _flood(canvas, up)
    if len(reach) != len(canvas.walk):
        return False
    # `canvas.owned` and not the rectangles: a stamped room is a drawing,
    # so its walkable tiles are counted as they are laid rather than as
    # `w * h`. For a floor of plain rooms the two are the same number.
    if canvas.owned + len(canvas.corr) != len(canvas.walk):
        return False

    def room_of(tile: list[int]) -> int:
        """Which room a named tile is in, by the room's rectangle."""
        for index, room in enumerate(rooms):
            if (room[0] <= tile[0] < room[0] + room[2]
                    and room[1] <= tile[1] < room[1] + room[3]):
                return index
        return -1

    for tile in anchors.values():
        if tile is not None and tile[0] + tile[1] * canvas.w not in reach:
            return False
    for poi in plan["pois"]:
        if poi["at"][0] + poi["at"][1] * canvas.w not in reach:
            return False
    for tile in plan["secrets"]:
        if tile[0] + tile[1] * canvas.w not in reach:
            return False
    for spawn in plan["spawns"]:
        if spawn["at"][0] + spawn["at"][1] * canvas.w not in reach:
            return False
    for chest in plan["chests"]:
        if chest["at"][0] + chest["at"][1] * canvas.w not in reach:
            return False

    # The main path, the warden off it, and the stairs in one component.
    if not graph.main_rooms:
        return False
    room_count = graph.room_count
    up_room = room_of(anchors["up"])
    down_room = room_of(anchors["down"])
    warden_room = room_of(anchors["warden"])
    if min(up_room, down_room, warden_room) < 0:
        return False
    if _bfs_path(graph.room_adj, up_room, down_room) is None:
        return False
    if warden_room in set(graph.main_rooms):
        return False

    if room_count >= 12 and _loops(graph) < LOOPS_MIN:
        return False
    if len(_within_one_step(graph)) < 0.40 * room_count:
        return False
    if plan["chests"]:
        total = 0
        off = 0
        for chest in plan["chests"]:
            worth = _chest_value(section, chest["table"])
            total += worth
            if room_of(chest["at"]) not in set(graph.main_rooms):
                off += worth
        if total and off < 0.60 * total:
            return False
    try:
        json.dumps(plan, sort_keys=True)
    except (TypeError, ValueError):
        return False
    return True


# ----------------------------------------------------------------- the door


def _attempt(floor_key: str, width: int, height: int, section: dict,
             floor_kind: str, stamp_pack: list[dict], depth: int,
             pinned: bool, trace: dict | None = None) -> tuple[dict | None, str]:
    """One draw of one floor: the five stages, or None when it fails.

    Three streams are opened, one for each stage that draws, and the
    graph and validate stages open none. Every stream name is the floor
    key and the stage name, exactly as PLAN.md section 2 writes them, so
    a JavaScript twin can replay a stage on its own.

    The second half of the answer is the defect, or "" for a good floor
    and for a floor that failed for an ordinary reason. A required stamp
    that would not place is a defect and not a bad draw: the retry
    ladder is meant to fix a bad draw, and a floor that fell back to v2
    over a stamp is a floor the author has to hear about (ADR 0013,
    Placement 4).

    `trace`, when given, is filled in with the floor key and the roles
    this floor wanted a stamped room for. The slot list is arithmetic on
    the plan and takes no draw, so a caller that reports the list changes
    nothing about the floor; `vefr stamp check` needs it because ADR
    0013 calls a stamp eligible only where "its role is wanted on the
    floor", and a secret room is wanted on a floor that drew no secret.
    """
    plan_rng = prng(f"v3|{floor_key}|plan")
    layout_rng = prng(f"v3|{floor_key}|layout")
    pop_rng = prng(f"v3|{floor_key}|pop")

    plan = _plan_stage(plan_rng, section, floor_kind)
    if trace is not None:
        trace["floor_key"] = floor_key
        trace["slots"] = set(_stamp_slots(plan))
    canvas = Canvas(width, height)
    pool = _stamp_pool(section, stamp_pack, depth)
    spine, missing = _layout_for(plan)(layout_rng, canvas, plan, pool, pinned)
    if len(spine) < 2 or missing:
        return None, f"stamp:{missing[0]}" if missing else ""
    graph, anchors, pois, secrets = _graph_stage(canvas, spine, plan, section)
    if graph.room_count < ROOMS_FLOOR:
        return None, ""
    up = (anchors["up"][0], anchors["up"][1])
    down = (anchors["down"][0], anchors["down"][1])
    spawns, chests = _pop_stage(pop_rng, canvas, graph, plan, section, up, down,
                                secrets, floor_key, depth)

    floor = {
        "gen": 3,
        "w": width,
        "h": height,
        "rows": canvas.rows(),
        "rooms": [list(room) for room in canvas.rooms],
        "anchors": anchors,
        "pois": pois,
        "secrets": secrets,
        "spawns": spawns,
        "chests": chests,
        "waypoint": plan["waypoint"],
    }
    if canvas.stamps:
        # The placements ride along on the floor: which stamp, which way
        # up it is, and where each of its letters stands. `vefr stamp
        # check` reads them, and a caller that wants to name the room
        # the player is standing in has the id without a second lookup.
        floor["stamps"] = canvas.stamps
    if not _validate(floor, canvas, graph, section):
        return None, ""
    return floor, ""


def _fallback(seed: str, width: int, height: int, section: dict,
              defect: str = "") -> dict:
    """The v2 floor of PLAN.md section 2's last resort, as a FloorPlan.

    v2 stays pinned by hash and stays the fallback, so a caller that
    cannot have a v3 floor still gets the shape it always had: the rows,
    the stairs, and the room rectangles v2 geometry can be read back
    into. No point of interest, no secret, no monster, no chest.

    `defect` is the reason the v3 floor was not good enough, when the
    reason is a stamp that would not place - `stamp:<role>` - and "" for
    every other reason. ADR 0013's Placement 4 wants that floorback
    reported rather than hidden, and the key on the floor is where
    `vefr stamp check` reads it from; a v2 floor with no defect is the
    ordinary kind and carries no key at all.
    """
    quota = _read_rooms(section)[0]
    rows = generate_floor_v2(f"{seed}/fallback", width, height, max(2, quota))
    rooms = _read_rectangles(rows, width, height)
    floor = {
        "gen": 2,
        "w": width,
        "h": height,
        "rows": rows,
        "rooms": rooms,
        "anchors": {
            "up": _find(rows, UP, width, height),
            "down": _find(rows, DOWN, width, height),
            "warden": None,
            "vault": None,
            "landmark": None,
        },
        "pois": [],
        "secrets": [],
        "spawns": [],
        "chests": [],
        "waypoint": False,
    }
    if defect:
        floor["stamp_defect"] = defect
    return floor


def _read_rectangles(rows: list[str], width: int, height: int) -> list[list]:
    """The rectangles v2 geometry can be read back into, one per region.

    v2 draws no room list, so the fallback reads the regions out of its
    own rows: every 4-connected run of walkable tiles is one region, and
    its bounding box is the rectangle. A v2 corridor and the room it
    runs to are one region, so the boxes are generous by design; a
    caller that wants a room list for a v2 floor is reading a floor that
    never promised one.
    """
    seen = [[False] * width for _ in range(height)]
    rooms: list[list] = []
    for y in range(height):
        for x in range(width):
            if seen[y][x] or rows[y][x] == WALL:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            lo_x = hi_x = x
            lo_y = hi_y = y
            while stack:
                cx, cy = stack.pop()
                lo_x, hi_x = min(lo_x, cx), max(hi_x, cx)
                lo_y, hi_y = min(lo_y, cy), max(hi_y, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and not seen[ny][nx]:
                        if rows[ny][nx] in (FLOOR, UP, DOWN):
                            seen[ny][nx] = True
                            stack.append((nx, ny))
            rooms.append([lo_x, lo_y, hi_x - lo_x + 1, hi_y - lo_y + 1, "open"])
    return rooms


def _find(rows: list[str], glyph: str, width: int, height: int) -> list[int] | None:
    """The first tile carrying `glyph`, in row-major order."""
    for y in range(height):
        row = rows[y]
        for x in range(width):
            if row[x] == glyph:
                return [x, y]
    return None


def generate_floor_v3(seed: str, size_range, section: dict, floor_kind: str,
                      stamp_pack=None, depth: int = 1,
                      trace: dict | None = None, *, cycle: int = 0) -> dict:
    """Draw one v3 floor from `seed` and return its FloorPlan.

    `size_range` is the chosen `(w, h)` of the floor and nothing else.
    `section` is a Section pack; only `id`, `rooms`, `families`, `elites`,
    `groups`, `mobs`, `pois`, `stamps` and `vault` are read, every other key
    is defaulted, and a missing key never raises. `floor_kind` is one of
    `normal`, `treasure`, `infested` or `hub`.

    `stamp_pack` is the pack's stamp set as `stamps.load` hands it over:
    a list of read records, already sorted by id. It is the stamped
    rooms ADR 0013 places, and it is empty by default, so a call that
    knows nothing about stamps is byte-for-byte the floor it always was.
    The Section's own `stamps` tags say which of them this Section may
    use, and `depth` is `k`, the floor's 1-based position in its
    Section, which is what a stamp's own `depth` range is measured
    against. `cycle` is the descent cycle the floor belongs to and
    defaults to 0, the story.

    The floor key is `f"{seed}/{section_id}/{cycle}/{depth}"` - the shape
    PLAN.md section 2 writes, `run_seed/section.id/cycle/k` - so the same
    seed, section, cycle and floor number is the same floor, and two
    ordinary floors of one Section are two floors. A floor that fails
    stage 5 is drawn again from the same key with `|try{n}` appended, up
    to `MAX_TRIES` times; after that the caller gets v2 geometry with
    `gen: 2` and the same keys. The fallback rate is the fraction of calls
    that come back with a `gen` other than 3. The LAST try pins the
    required stamps (ADR 0013, Placement 4), and a floor that falls back
    to v2 over a stamp carries `stamp_defect` naming the role that would
    not place.

    `trace`, when given, is a dict the floor writes its key and its
    wanted stamp roles into - what `vefr stamp check` measures a rate
    against. Passing one changes nothing about the floor.

    Deterministic: `delve.prng` is the only source of randomness, so the
    same arguments always return the same plan. Raises `ValueError` for
    a `size_range` that is not a pair of whole numbers of 8 or more, and
    for a `floor_kind` outside `FLOOR_KINDS`.
    """
    width, height = _read_size(size_range)
    if floor_kind not in FLOOR_KINDS:
        raise ValueError(f"floor_kind must be one of {', '.join(FLOOR_KINDS)}")
    pack = section if isinstance(section, dict) else {}
    raw_id = pack.get("id", "")
    section_id = raw_id if isinstance(raw_id, str) else str(raw_id or "")
    base_key = f"{seed}/{section_id}/{cycle}/{depth}"
    records = [record for record in (stamp_pack or ()) if isinstance(record, dict)]
    defect = ""
    for attempt in range(MAX_TRIES + 1):
        floor_key = base_key if attempt == 0 else f"{base_key}|try{attempt}"
        floor, failed = _attempt(floor_key, width, height, pack, floor_kind,
                                 records, depth, pinned=attempt == MAX_TRIES,
                                 trace=trace)
        if floor is not None:
            return floor
        if failed:
            defect = failed
    return _fallback(str(seed), width, height, pack, defect)
