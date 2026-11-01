# Ten-room delve

One worked walk through the three cards on one floor: generate, see, step,
replay.
Every number below is output from this VEFR tree, not an illustration.
The commands and blob shas are at the end.

## 1. Generate

```python
from vefr import delve
SEED = "ten-room-delve"
rows = delve.generate_floor_v2(SEED, 40, 16, 10)
```

The call asks for ten rooms; the placer placed ten at this size (checked with
`delve._place_rooms_v2` on the same seed and size).
The floor is 40 by 16, with a solid border, 306 walkable `.` tiles and one `u`
and one `d`:

```text
########################################
####################.........####....###
###....#############.................###
###.......##########..........###....###
###....##.###......#####.####.#####.####
#####.###.###......#####.##.........####
##....#.....#......#......#...d.....####
##....#.....#.......................####
##....#.....#......#......#.........####
##........................#.........####
##...##.....#......#......###.#####.####
##...##.....########......#.....###.####
#######.....##.....#......#.....###.####
##############...........u..........####
##############.....########.....########
########################################
```

The up-stair is at `(25, 13)`, the down-stair at `(30, 6)`: 12 Manhattan tiles
apart, over the generator's minimum of 10 (`MIN_STAIR_DISTANCE`,
`src/vefr/delve.py:39`).
Call `generate_floor_v2` twice and the rows are equal.
`generate_floor` (v1) has the same shape but uses `random.Random`; v2 is the one
built on the shared `prng`, with its draw order written out at
`src/vefr/delve.py:341-392` so a JavaScript twin draws the same rows.

## 2. See

The player's fog lights a radius around the hero, remembers what was lit and
hides the rest (`web/player/parts/450-fog-of-war.js:115-149`).
With the hero on the up-stair and radius 6, 85 tiles are lit.
Here is the lit window around `(25, 13)`, cropped to columns 19-31 and rows
7-15, with `@` for the hero, `*` for a lit tile, `.` for an unlit floor tile
and `#` for a wall:

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

The light crosses the walls in those rows.
VEFR's fog is radius fog, not line-of-sight: a tile behind a wall inside the
radius is lit.
The explored set is saved as a base64 bitset, one bit per tile, row-major
(`encodeFog`, `:37-50`); the memory is per region and per world, and a generated
floor keeps it in the descent document (`:62-64`).
The down-stair at `(30, 6)` is outside the lit radius from the start.

## 3. Step

The shipped turn is `move(dx, dy)`
(`web/player/parts/480-town-input-and-turns.js:1477`).
Its wall check is small and exact:

```javascript
if ((town.legend[town.map[ny][nx]] || {}).solid) {
  var shut = (window.VEFR_DESCENT && window.VEFR_DESCENT.shutDoorLine)
    ? window.VEFR_DESCENT.shutDoorLine(regionName, nx, ny) : '';
  if (shut) combatSay(shut);
  heroSettleSoon();
  return;
}
```

That is a refusal: the hero stays put.
The game state is already settled before the hop starts, and the turn is never
gated on the animation (`:1549`).

The [step card](../step-loop.md) asks for the same turn as a pure function.
Folding nine inputs over a small `step` on this floor gives this real log:

```text
right  moved    (26, 13)
right  moved    (27, 13)
right  moved    (28, 13)
up     moved    (28, 12)
up     moved    (28, 11)
up     blocked  (28, 11)
up     blocked  (28, 11)
right  moved    (29, 11)
right  moved    (30, 11)
```

Seven moves, two refusals, and the hero ends at `(30, 11)`.
The step's state would be the hero tile, the explored set, the turn number and
the floor key; the floor rows are regenerated from the seed, not saved.

## 4. Replay

```python
assert delve.generate_floor_v2(SEED, 40, 16, 10) == rows
assert walk(rows, (25, 13), INPUTS) == ((30, 11), EVENTS)
```

Run that twice and both assertions hold.
The seed and the input list are enough to reproduce the run; the generator
version rides in the floor's identity triple, `{'gen', 'hash', 'key'}`
(`src/vefr/delve.py:1579-1581`), so a change to the generator cannot quietly
pass an old replay off as the same floor.
Change one input, not the seed, and the end changes.
That is the [seeded RNG and replay](../seeded-rng-and-replay.md) card in one
sentence.

## What ties the three together

| Card | Pure shape | This floor |
|---|---|---|
| Generate | seed -> rows | `"ten-room-delve"` -> 40x16, 306 walkable tiles |
| See | rows + hero + radius -> lit, then remembered | 85 lit tiles at `(25, 13)`, radius 6 |
| Step | state + input -> new state + events | nine inputs, seven moves, two refusals |
| Replay | seed + inputs -> the same log | same rows, same end `(30, 11)` |

The seam is the seed plus the input list.
Everything else is either derived (the rows, the lit set) or saved as a delta
(the explored bits, the drops, the secrets).

## Provenance

The floor and the walk were produced in this tree at the base commit `3ed48bb7`
with Python 3.14.7:

```sh
PYTHONPATH=src python3 -c 'from vefr import delve; print("\n".join(delve.generate_floor_v2("ten-room-delve", 40, 16, 10)))'
```

The blob shas were produced with `git rev-parse HEAD:<path>`:

```text
src/vefr/delve.py                              b998b53168b18786bb0856e1c7d090af82a575da
src/vefr/delve_v3.py                           e9968fc81335ec9cf92980a225aad9d19a77c021
src/vefr/sections.py                           b063861aa9183711db7fcb3baa344760ac230316
src/vefr/shapes.py                             ef1058511ffaeb32deba3f6121ff859e9fac588b
web/player/parts/450-fog-of-war.js             7886c68b20dfaa454b5a8ed62e423606264ff491
web/player/parts/480-town-input-and-turns.js   ec9a7f6c6370aeb3ed8767b5ee7619c2647f1b43
tests/test_delve.py                            560f50d05f1be51bb58f5af20406abba04537fda
tests/test_delve_prng.py                       c993716d334adb06d02a7a7bafaf292170b41fe5
```

The generator is cited at `src/vefr/delve.py:313-420`; the fog at
`web/player/parts/450-fog-of-war.js:115-149`; the shipped turn at
`web/player/parts/480-town-input-and-turns.js:1477-1560`.
The estate files behind the three cards were checked from a clone of each private repository, and the
blob shas above were produced the same way:

```text
memomancer src/core/rng.ts               c9ed5ad1cc1596df1f86a45b0d78d8d5946c8729
memomancer src/core/fov.ts               8b48021e4718474814e209e6a3773f3298e14b14
memomancer src/core/mapgen.ts            fba040200b2c82f739705027ccf85c3306e8b8cb
haunted-card-table src/rules/game.js     ca89ed989c8829ae728b5764243a732864fd097b
haunted-card-table src/rules/solver.js   d4d50e7697d0d5cac8387c74ae6a5be9572800cf
vibe-coder src/logic/game.js             367bc5d9013e122e50a8970984eec60d2deb75c1
```
