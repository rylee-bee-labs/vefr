# 0022 - Floors that wander: a Section's `layout`

Date: 2026-10-30

## Status

**Accepted direction; implemented in one PR.** The owner played the first
Section of the Cottage 1.0 build on 2026-10-30 (Gate 0) and said: "it feels
like the levels need some randomness. There are almost straight lines to every
staircase". Offered a layout where "rooms scatter over the whole map" and "the
way from stair to stair is a random walk that turns, climbs and can double
back", opt-in per Section, she chose it. That choice is the ask-first answer
for the pack-contract change below. The numbers in it (cell pitch, walk
length, how strongly the walk heads outward, how far apart the stairs stand)
are Claude's calls, measured and named as such.

## Context

The v3 layout stage lays every floor on a **spine**: one row of rooms across
the floor's long axis, the up stair in the first spine room and the down stair
in the last (`delve_v3._layout_stage`, step 3; PLAN.md section 2 took the idea
from the CotW spine). Rooms branch off one side, and the loops run alongside
it. Measured on a real pack's Section (64-80 x 48-56 floors, 12-18 rooms),
over 160 floors:

- every shortest walk from the up stair to the down stair was a straight line:
  0 turns, as long as the straight-line distance, both stairs on one row;
- about half of each floor stayed solid wall.

PLAN.md section 4's "measurably fun" checks (40% of rooms within one step of
the path, 60% of chest value off it) never asked whether the path bends, so
nothing caught it. No pack data could change it: `size` and `rooms` only
lengthen the same straight line.

## Decision

A Section may name `layout`:

```json
"layout": "wander"
```

`"spine"` is the default, and a Section that names nothing or names `"spine"`
draws exactly the floors it drew before. The layout is part of the floor's
identity (`section_hash` covers the whole Section), so a save made before a
Section switched layout redraws those floors rather than replaying deltas on a
map that no longer exists.

`"wander"` replaces stage 2's steps 3 to 6 with `delve_v3._wander_stage`.
Stages 1 and 3 to 5 are unchanged, and step 7 (the stamped rooms) is the
spine's own:

1. The floor is a grid of cells, `rand(8, 10)` x `rand(7, 8)` tiles each.
2. **The walk** starts in a random cell and steps to a free neighbour,
   never back onto a cell it has stood on, for two-thirds of the room
   quota. A step that takes it further from its first cell is three
   times as likely as one that does not, so it turns, climbs and doubles
   back but heads out across the floor. The stairs go at its two ends,
   exactly as they went at the spine's.
3. **A room in each cell**, sized and placed at random inside it, with
   the cell's last row and column left as wall. Each walk room is joined
   to the one before it by the spine's own L-shaped corridor.
4. **Branches**: every room, walk first, grows into the free cells beside
   it until the quota is met.
5. **Loops**: two or three corridors between side-by-side rooms not yet
   joined, only where the two rooms hang off walk rooms at most two
   apart, so no loop is a short cut past the walk.

Every corridor joins two rooms in side-by-side cells, so it never crosses a
third room. Stage 5 holds a wander floor to one more property: its stairs are
at least `min(16, max(w, h) // 3)` tiles apart (Chebyshev), so a walk that
doubled back to its start is drawn again by the retry ladder.

The JavaScript twin (`web/player/parts/396-engine-delve-v3.js`) carries the
same stage draw for draw (`wanderStage`, `layoutFor`), and the four new
constants are in the list both languages share.

## Measured

On the same pack's Section, 800 floors (100 runs x 8 floors): no walk from
stair to stair is a straight line; the median walk turns 14 times and is 1.5
times the straight-line distance; the stairs stand a median 35 tiles apart,
16 at least; the walkable area's bounding box covers 40% of the floor (30% on
the spine); no floor fell back to v2.

## Consequences

- One pack-contract key, recorded in `src/vefr/world.py`, `shapes.SECTION`
  and `docs/guides/rulesets.md`.
- The parity sweep runs twice: the spine, then the wander layout over the
  same 200 seeds x 4 sizes x 4 kinds, stamped half and nonzero cycles
  included, compared stage by stage.
- `tests/test_wander_floors.py` holds the wander layout to every property the
  v3 sweep promises, through the property file's own derivation, and to what
  it is for: no straight walk, a turning walk, stairs apart.
- Not in this change: a wander layout for the v2 fallback (it stays v2), and
  any change to the spine.

## Acceptance

`tests/test_wander_floors.py`, `tests/test_floor_v3_parity.py` (with its
wander half) and the full gate.
