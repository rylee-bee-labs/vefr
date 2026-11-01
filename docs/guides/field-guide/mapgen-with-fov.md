# Map generation with fog

Rooms and corridors first, then the part of the floor the hero has seen.

## The idea

Generate the floor first, then decide what the hero can see.
The generator is a pure function of a seed; the view is a pure function of the
hero's tile and the explored memory.
A test can then check the floor without a renderer.

VEFR's generator is room-and-corridor: up to `rooms` non-touching rectangles,
L-corridors, a solid border, one `u` and one `d` at least `MIN_STAIR_DISTANCE`
(10) apart when the layout allows, and every walkable tile reachable
(`generate_floor`, `src/vefr/delve.py:313-338`; `tests/test_delve.py:129-170`).
`generate_floor_v2` is the same shape on the shared `prng`, with the draw order
written out for a JavaScript twin (`:341-420`); `generate_floor_v3` adds stamps,
monsters and vaults (`src/vefr/delve_v3.py:2714`).

VEFR's view is fog of war, not line-of-sight field of view.
`450-fog-of-war.js` lights a radius - a circle by default, a square when the
floor asks (`litNow`, `:115-137`) - remembers every lit tile in a bitset
(`seeNow`, `:138-146`) and hides the rest (`hideUnseen`, `:147-149`).
Walls do not block the light: a tile behind a wall inside the radius is lit.
True shadowcasting FOV is not implemented; rot.js, BSD-3-Clause, is the named
prior art (`docs/research/2026-09-30-enhancement-packet.md:56`).

The pack sets `fog: {radius, shape}` in a region contract
(`src/vefr/shapes.py:1040`); `vefr.sections.fog_radius` bounds it at 2 and lets
a Darker omen shrink it, never grow it (`src/vefr/sections.py:851-866`).
A floor's plan carries the radius (`src/vefr/delve.py:1558-1572`); no fog draws
the region whole.

## Step API sketch

```python
def generate(seed: str, width: int, height: int, rooms: int) -> list[str]:
    """A pure floor: rows of '#', '.', 'u' and 'd'."""

def lit(rows: list[str], at: tuple[int, int], radius: int,
        shape: str = "circle") -> set[tuple[int, int]]:
    """The tiles lit now. Pure; no memory."""

def see(explored: frozenset[tuple[int, int]],
        lit: set[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    """The remembered tiles after this look: explored | lit."""
```

`lit` is the view, `see` is the memory, `generate` is the floor; none draws.

## Knobs

- **Size and rooms** - `width`, `height`, `rooms`; a cramped area places fewer
  rooms. 30x12 with `rooms=10` placed four; 40x16 placed ten (real output in
  [Ten-room delve](examples/ten-room-delve.md)).
- **Stair distance** - `MIN_STAIR_DISTANCE` (10), relaxed to the widest pair
  when the layout cannot satisfy it (`src/vefr/delve.py:39`, `:219-241`).
- **Fog** - on or off per region; radius and shape; omens that only shrink it.
- **Memory** - the explored bitset is per region and per world; a generated
  floor keeps it in the descent document, and a cap bounds remembered floors
  (`web/player/parts/450-fog-of-war.js:59-64`).
- **Player escape hatch** - fog can be turned off per world
  (`fogPrefOn`, `:16-21`); `V` or Display shows the whole map
  (`AGENTS.md:248-249`).
- **Reveals** - a torch widens the circle for a few turns; a chalked map opens
  the whole place (`AGENTS.md:247-249`).

## A 60-second example

```python
from vefr import delve
rows = delve.generate_floor_v2("ten-room-delve", 40, 16, 10)
assert rows == delve.generate_floor_v2("ten-room-delve", 40, 16, 10)
```

The floor is 40 by 16, with 306 walkable tiles; `u` is at `(25, 13)` and `d` at
`(30, 6)`, 12 tiles apart. The rows are in
[Ten-room delve](examples/ten-room-delve.md).
Standing on `u` with radius 6 lights 85 tiles; the down-stair is outside the
light. The lit window around the hero - `@` hero, `*` lit, `.` unlit floor,
`#` wall - is:

```text
......*......
#..*******...
..*********..
#***********#
#***********.
#***********.
******@******
#***********.
#***********#
```

The light crosses the walls in those rows. That is radius fog; a line-of-sight
implementation would darken the far side.

## A must-fail test idea

```python
rows = delve.generate_floor_v2("connected", 30, 20, 8)
up, down = stairs(rows)
seen = flood(rows, up)
floor_tiles = {(x, y) for y, row in enumerate(rows)
               for x, c in enumerate(row) if c != "#"}
assert seen == floor_tiles
assert down in seen
```

A generator that places rooms but forgets the corridors fails: part of the floor
is unreachable from the up-stair, so `seen` is smaller than `floor_tiles`. A
generator that seals a stair into a pocket fails the second assert.
That is the test VEFR already runs (`tests/test_delve.py:153-162`).

The visibility half has a different missing test: put a floor tile one step
behind a wall from the hero and assert it is not in `lit()`. A disc of light
fails; a shadowcaster passes. VEFR's `litNow` fails that test, so it is the gap
the next FOV implementation must close, not a claim about today.

## Accessibility

- **Fog is never the only signal** - the hero's tile, the exits and nearby
  things need words; a dimmed tile tells a screen-reader player nothing.
- **An escape hatch** - `V` or Display shows the whole map, and fog can be
  turned off per world (`web/player/parts/450-fog-of-war.js:16-21`;
  `AGENTS.md:248-249`). That
  is an accessibility setting, not a cheat.
- **Autoexplore** - `O` or Explore walks to the nearest unexplored ground and
  stops on a monster, a wound or nothing left to see
  (`AGENTS.md:244-247`; `web/player/parts/490-autoexplore.js`).
- **Low motion and words** - revealing tiles should not flash; the step tween
  obeys reduced motion (`web/player/parts/480-town-input-and-turns.js:58`). Say
  "the passage is
  dark", not only a dimmed rectangle.
- The wider contract is 44px targets and full keyboard traversal
  (`docs/guides/accessibility-contract.md:160-161`).

## Provenance

- `src/vefr/delve.py` @ `b998b53168b18786bb0856e1c7d090af82a575da`
  (`generate_floor` `:313`; v2 draw order `:341-392`; `generate_floor_v2`
  `:393`; `DEFAULT_FOG_RADIUS` `:462`; plan fog `:1558-1572`).
- `src/vefr/delve_v3.py` @
  `e9968fc81335ec9cf92980a225aad9d19a77c021` (`generate_floor_v3` `:2714`).
- `src/vefr/sections.py` @ `b063861aa9183711db7fcb3baa344760ac230316`
  (`fog_radius` `:851`).
- `src/vefr/shapes.py` @ `ef1058511ffaeb32deba3f6121ff859e9fac588b`
  (`FOG` `:1040`; `FOG_RADIUS_MAX` `:1008`; `FOG_RADIUS_MIN` `:1061`).
- `web/player/parts/450-fog-of-war.js` @
  `7886c68b20dfaa454b5a8ed62e423606264ff491` (`fogPrefOn` `:16`; `litNow`
  `:115`; `seeNow` `:138`; `hideUnseen` `:147`).
- `web/player/parts/490-autoexplore.js` @
  `9e8b49ff3a31bf32f62d1613720e42a8f767db9e`.
- `tests/test_delve.py` @ `560f50d05f1be51bb58f5af20406abba04537fda`
  (same seed `:129`; reachability `:153`).
- OSS: rot.js, BSD-3-Clause
  (`docs/research/2026-09-30-enhancement-packet.md:56`, `:71`); libtcod and
  python-tcod, BSD-3 / BSD-2 (`:67`); DeBroglie, MIT (`:94`); mapgen4,
  Apache-2.0 (`:98`).
- memomancer `src/core/fov.ts` and `mapgen.ts` were named in the mission but
  were not present in this run, so no sha is claimed.
