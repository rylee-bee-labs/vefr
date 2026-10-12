# Endless dungeon: design record (Rylee's decisions)

Status: agreed 2026-10-04. The build plan is [PLAN.md](PLAN.md) (Opus, 2026-10-04), which supersedes the slice list below. Research: [big-generated-maps](../../research/big-generated-maps.md).


## The model
- The dungeon is one line of floors, cut into **Sections** of 8–11 floors. Floors past the hand-built ones are **generated while you play** from `seed + depth` (today `delve` only generates at build time: its docstring calls per-playthrough generation "a later slice").
- A **Section** is a data pack: enemy families, loot tier, tileset, scaling curve. A new Section needs no new code.
- Each Section ends with a **key warden**: a named boss carrying a key to a **vault** (a small treasure room with a lore note). Reading the note sets the flag that advances the act.
- **Acts change the town, never the dungeon generator.** After a vault, the hero walks back up; the town has changed (map pieces, residents, stock, lines). The next Section's stairs stay locked until that visit, with a **paid shortcut** to skip it on repeat runs (price to be tuned).
- The story end is the per-game flag `descent.story_end`, default `king-slain` (the **King**, the Diablo role, at the end of Act 3), per Amendment 1 (ADR 0015, approved by Rylee 2026-10-08). After the story end, "Keep exploring" opens the **endless mode**: Sections keep cycling at higher scaling, key wardens keep dropping.

## Floors
- Every floor holds randoms plus **one or two elites**: a normal family with a modifier (bigger, faster, fire-touched), a name and better drops.
- **Linked groups**: mobs placed as a pack, tied together so that waking one wakes the rest.
- Maps get **much bigger**. The camera and the stage work already scroll; size cost (generation time, sprite counts, save size, the map panel) must be measured first.
- **Hand-painted room sections** ("stamps"): an author paints a room or a few room shapes and the generator places them inside generated floors (anchored, rotated or not, with doors that must connect).

## What stays from the shipped Act 1 (Rylee's call)
Keep only the **first floor map**, the **King's throne room map**, and the **shape of a few hand-drawn rooms** (as stamps). Act 1 is rebuilt as **8–11 floors** with a key warden. The Cellar King moves to the end of Act 3. The three shipped Keybearers (Ashwing, Brother Sporeling, Sir Hollowhorn) were named on 2026-10-04 and are candidates for key wardens in the Sections.

## Engine slices (VEFR), in order
1. **E0 prototype**: port `delve` to play-time generation (`generateFloorV2` already ships in the player), `seed + depth`, saves store only changes. Measure big maps.
2. **E1 sections**: Section data shape, depth curve, family tables, Blueprint hook.
3. **E2 stamps**: hand-painted room sections placed by the generator.
4. **E3 elites and linked groups**.
5. **E4 key warden, vault and act gate**, including the paid shortcut.
6. **E5 endless mode**: cycling Sections after the final boss.

## Cottage work
Section packs, vault notes, warden names, town changes per act, a rebuilt Act 1, the King redrawn as the Act 3 boss. Existing Act 1 floors 2–6, their Keybearer placement and the floor-6 ending are replaced; the lock chain (`requires`) stays as the gate mechanism.

## Open
- Lengths (floors per Section, number of Sections): decide after E0.
- Shortcut price and whether it exists in the first run.
- Whether endless mode keeps story-free Sections or reuses the three.

## Principle (Rylee, 2026-10-04)
Everything is built in VEFR so the dungeon can be remade by any game: Cottage supplies only data (section packs, stamps, families, names, notes, art).
