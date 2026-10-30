# The endless dungeon: build plan (2026-10-04)

Sources: `design-record.md` (agreed model), `research.md` (§1–§8 and the "what to steal" table), `delve.py`, `roadmap.md`, `tighten-shapes-plan.md` (lanes T and I), `cottage-notes.md`. `cottage-acts-2-3-plan.md` is **superseded** by this plan: it assumes new zones and act advance, but acts now change the town only. Claims about the player that I did not read in code are marked UNKNOWN.

## 1. The model, and where it will fail

Kept as agreed: Sections of 8–11 floors; a key warden at the end of each; vaults with a lore note that advances the act; acts change the town only; the King ends Act 3; endless mode after him; elites and linked groups; stamps; bigger maps; a paid shortcut past the town visit.

Challenges, stated plainly:

1. **"Much bigger maps" will make the game boring and slow if size is the goal.** The research's rule is *landmarks > size* (§5): Cogmind's 200×200 maps work only because they are dense with points of interest. Cottage is turn-based and meant to be "low bandwidth", and success is "I lost an evening to it". At 200×200, nine floors take several evenings per Section. **Size a floor by minutes to play it, not by tiles.** The target is 6–10 minutes per floor, so a Section is one evening. I expect 64×48 to 96×64, not research §4's 120×120. E0 decides.
2. **"Walk back up after the vault" is a chore at depth 27.** Every vault has a stair home, as the shipped King's room does. Section starts and mid-Section landings are reachable from town (§4 has the rule).
3. **"Endless at higher scaling" is the power-creep failure** (§7: "by depth 200 the numbers are unrecognisable"). Monster numbers stay bounded. Difficulty after the story comes from **omens** the player chooses (Hades heat, steal #9), and the reward is collection, not stats.
4. **Linked groups plus 1–2 elites per floor, turn-based, can spike.** If five monsters wake together, they all hit in the same turn. Groups are capped at 4. Section 1 uses groups of 2–3. Every group has a leash, and research §6's density cap applies: at most 1 elite group per ~8 rooms.
5. **Generating while you play means writing every generator feature twice** (Python and JS). That cost is accepted, because `vefr check` in Python must prove that every seed is winnable (§3, §8). The twin is kept small: only generation is twinned. Rendering, AI and UI stay JS-only.
6. **ADR 0006 "act advance" as written (move the hero to the next act's start region) no longer matches the model.** It is rescoped to **town states**: flag-selected changes to the town. Amend the ADR and the roadmap's NEXT entry in the same PR as E7.
7. **A paid shortcut on the first pass skips the story.** Recommendation: the shortcut for a Section's town visit exists only after that Section's vault note has been read once (in endless mode or after a New descent). Owner-gated.
8. **Release 1 saves will not carry over.** Floors 2–6 are replaced. The game shows a one-time "Start over" card, keyed on `gen_version`.

## 2. Generator architecture (delve v3)

**Steal:** room-and-corridor (ours, §1); the CotW **spine** (§1); Brogue **accretion** and its room-shape menu (§2); DCSS **vaults minus Lua** as stamps (§2); the Dormans lock/key **subgraph** only (§3); Brogue **key-holder** placement (§3); D2 **leader + minions** (§6); Stardew **special floors and elevator** (§5); **Hades modifiers** (§7); the §8 **sweep, goldens and perf budget**.

**Skip:** BSP, full WFC, herringbone, the full Dormans grammar, chunking, and cellular-automaton caves as a default (later, as one room shape).

**Pipeline.** The stages are pure and run in a fixed order. Each stage draws from its own seeded stream.

1. **Plan** (`plan` stream): from the Section pack and the floor's position, pick the floor kind, the size, and quotas (rooms, stamps by role, elites, groups, secrets, loops ≥2 when rooms ≥12).
2. **Layout** (`layout` stream): lay a spine across the long axis, with up and down near its ends. Place required stamps first as reserved rooms (landmark, warden hall, vault). Accrete rooms whose door sockets face existing space. Connect with v2's L-corridors. Add loops between room pairs at graph distance ≥4 and grid gap ≤6. Turn leaf rooms into secret rooms.
3. **Graph** (no draws): build the room graph, BFS from `up`, find the up→down path. The warden goes in the farthest room off it (the gates-and-guardians rule). Points of interest come from the Section's name list (steal #8).
4. **Populate** (`pop` stream): randoms by area budget, then elites, groups and chests on reachable tiles ≥7 from the stairs (the shipped spacing rule).
5. **Validate** in both languages. On failure, retry with `|try{n}` on the seed, up to 8 times, then fall back to v2. The fallback rate must stay below 0.5%.

**Output** is one JSON-able **FloorPlan**:

```json
{"gen":3,"w":80,"h":56,"rows":["####…"],"rooms":[[x,y,w,h,"shape"]],
 "anchors":{"up":[x,y],"down":[x,y],"warden":[x,y],"vault":[x,y]},
 "pois":[{"at":[x,y],"name":"…","stamp":"id"}],"secrets":[[x,y]],
 "spawns":[{"id":"m7","family":"moth","elite":"big","group":"g2","leader":true,"at":[x,y]}],
 "chests":[{"id":"c3","at":[x,y],"table":"t1"}],"waypoint":false}
```

### Data shapes

All are pack data, checked by the S1 schema table (`shapes.py`), not by new hand-written validators.

**Section pack** (`sections/<id>.json`):

```json
{"section":1,"id":"cellar","floors":9,"size":{"w":[64,80],"h":[44,56]},"rooms":[12,18],
 "tiles":{"#":"cellar-wall",".":"cellar-floor"},"fog":{"radius":4},
 "families":[{"family":"rat","weight":5,"depth":[1,6]}],
 "pattern":["entry","n","n","special","landing","n","special","n","warden"],
 "specials":["treasure","infested","hub"],
 "elites":{"per_floor":[1,2],"affixes":["big","quick","glowing"]},
 "groups":{"per_floor":[1,2],"minions":[2,3]},
 "curve":{"hp":[1.0,1.4],"atk":[1.0,1.3]},"loot":{"tier":1},
 "stamps":["cellar","any"],"pois":["…"],"warden":"ashwing","vault":"vault-cellar"}
```

**Stamp** (`stamps/<id>.json`, DCSS-style, §2):

```json
{"stamp":1,"id":"wine-alcove","role":"landmark","tags":["cellar"],"depth":[1,9],"weight":2,
 "max_per_floor":1,"rotate":true,"mirror":true,
 "rows":["##+##","#...#","+.A.+","#...#","#####"],
 "legend":{"A":{"anchor":"chest"}},"poi":"…"}
```

Glyphs: `#` wall, `.` floor, `+` door socket (at least one must connect; unused ones become wall), `?` secret door, space = generator decides, a letter = a named anchor (named by glyph, so rotation is safe, §2). Roles: `landmark | warden-hall | vault | secret | special | filler`.

**Elite affix:**

```json
{"id":"big","label":"Big {name}","hp":1.5,"atk":1.0,"scale":1.3,"extra_drops":1}
```

Only stat, scale and drop fields until status effects land (then `inflicts`, for "fire-touched"). "Quick" is an extra move every other turn if the AI loop allows it (UNKNOWN), else +1 aggro radius.

**Group:**

```json
{"leader":"elite|normal","minions":[2,3],"same_family":true,"wake":"all","leash":6}
```

**Warden:**

```json
{"id":"ashwing","family":"moth","hp":3.0,"atk":1.6,"scale":1.4,"carries":"ashwing-key",
 "hall":"warden-hall-moth","placement":"farthest-off-path","endless":{"affixes":1}}
```

- The key is `keep` and has no value (the shipped rule).

**Vault:**

```json
{"id":"vault-cellar","stamp":"vault-small","needs":"ashwing-key","note":"library/…md",
 "chest":["…"],"sets":"vault-1-read","home":"town"}
```

- The note fires a rule. The vault's stair goes home.

### The determinism rule

- **Depth.** `depth` is a global integer. `locate(depth, pack)` returns `(cycle, section, k)`; it is pure and derived only from the pack's Section list. The story is cycle 0.
- **Floor key.** `floor_key = run_seed/section.id/cycle/k`.
- **Streams.** Each stream is `prng("v3|" + floor_key + "|layout")`, and likewise for `|plan`, `|pop`, `|size`, `|special`, `|loot|<mob id>` and `|chest|<chest id>`. Separate streams mean that changing an affix table never moves a wall (§8 sub-seed rule). Loot is seeded per mob, so kill order never changes a drop. `|size` draws the floor's width and then its height, so a pack editing its own room quota moves no wall; `|special` draws which of the Section's `specials` a special slot is.
- **Floor identity.** A floor is identified by `(gen version, section content hash, floor_key)`.
- **Forbidden:**
  - `Math.random`, the clock, and globals;
  - floats other than `floor(rng() * n)` with `0 ≤ n < 2^31`;
  - iterating over the keys of a map, dict or object where draws are consumed. Use arrays sorted by id;
  - sorts whose comparator can tie. Break ties by index.

### The save-deltas rule

**The save never stores a grid.** All writes go through K2's `store()`.

- **Per floor:** the identity triple, killed mob ids, taken chest ids, items the hero dropped (with tile), secrets found, and an explored bitset (1 bit per tile, base64).
- **Permanent and story-level, kept in rule state:** warden killed, vault read, landings reached, act flags.

Lifecycle:
- **Returning to town** clears kills and chests for that Section, as Stardew's mines reset. The explored bitset and the secrets found are kept.
- **Identity mismatch** on a visited floor (the generator or the pack changed): regenerate the floor and drop its deltas. Story flags are untouched, so progress is never lost.
- **Cap:** keep deltas for at most 40 floors. Evict the oldest bitsets first.

### The Python/JS parity constraint

- `src/vefr/delve.py` v3 (or `delve_v3.py`) is the **spec**. It serves `vefr check` and the sweeps.
- The JS twin is the **runtime**, in the part that defines `window.VEFR_DELVE`.
- Each stage carries a numbered draw-order comment, as `generate_floor_v2` does.
- Parity is checked **per stage** (layout, then plan JSON), so a mismatch shows where it starts.
- `tests/test_floor_v3_parity.py` runs 200 seeds × every size × every floor kind through the real player in Chromium. It compares canonical FloorPlan JSON.
- v2 stays pinned by hash and stays the fallback.

## 3. Size and performance

**Sizes to try (E0):**

| Size | Rooms | Use |
|---|---|---|
| 48×32 | 16 | today's floors, baseline |
| 64×48 | 18 | candidate default |
| 96×64 | 24 | candidate for late floors |
| 128×96 | 32 | stress test only; expect to reject |

**Chunking:** none. A floor is the unit (§4: Cogmind, DCSS and Diablo all take this path). The camera already draws only the visible window. Only the current floor is held in memory. A revisit regenerates the floor and replays its deltas.

**Budgets.** A size is rejected if it misses any of these:

| Measure | Desktop | Phone proxy (Chromium, 4× CPU throttle) |
|---|---|---|
| Generate + validate, p95 over 200 seeds | ≤ 40 ms | ≤ 150 ms |
| Monster turn, all monsters awake | ≤ 8 ms | ≤ 30 ms |
| Frame while scrolling | ≤ 4 ms | ≤ 12 ms |
| Save per visited floor | ≤ 3 KB (1.5 KB until 2026-10-30: rolled loot left on a floor outgrew it, and the floor's map was given up first) | — |
| Whole save at 40 floors | ≤ 250 KB | — |
| `packaged.html` growth (engine code) | ≤ 30 KB | — |
| JS heap for the floor | ≤ 5 MB | — |

**Fog and auto-map:**
- Keep the shipped fog (lit radius, remembered tiles), but store it as a bitset.
- Auto-map panel:
  - drawn once to an offscreen canvas at 3 px per tile and updated incrementally;
  - shows stairs, points of interest, landings and the hero;
  - opens with M or from the Menu;
  - also offers a text list of the known places, for screen readers (the always-layer).
- Autoexplore already exists. It must stay under the turn budget.

**E0 measures these first, before anything else is built:**
1. Generation time in Python and in JS at each size: 200 seeds, p50 and p95, plus the fallback rate.
2. The time for the monster flood fills. The shipped AI floods "once per turn, shared". Measure with 10, 25 and 45 monsters at each size.
3. Frame time while the camera scrolls, desktop and phone proxy.
4. The **current storage format** of `vefr-floor-<world>` and of fog explored tiles, and their bytes at each size (UNKNOWN today; if the format is a list of "x,y" strings, a 96×64 floor costs ~35 KB).
5. Turns for the bot to clear a floor fully with autoexplore, and turns from stair to stair (a proxy for minutes per floor).
6. Whether the player can load a region that was **not baked at weave time**: a "virtual region" (UNKNOWN; this is the biggest structural unknown).
7. Whether a `requires` lock can test a flag, or only an item (UNKNOWN).

**The decision:** the largest size that passes every budget. Then Rylee plays two of the passing sizes, which is the real tie-break.

## 4. Fun at scale

**Landmarks.** Every floor has:
- one landmark stamp with a named point of interest, written into the auto-map and the journal;
- a different look at each Section boundary: tileset, family, map colour (§5).

**Loops.** At least 2 room-graph cycles per floor of 12 or more rooms (Jaquays, §5). Measured by the property sweep.

**Secrets.** Rylee loved CotW hidden rooms, and "walking into a wall" is her search verb.
- Secret doors open after 2 bumps.
- At least half the floors have one secret room.
- A secret room holds a chest or a sticker, never a key.

**"Measurably fun" (§3):**
- At least 40% of rooms lie within one step of the up→down path.
- At least 60% of chest value sits off that path, so exploring pays.
- Both are asserted by the sweep.

**Special floors** (Stardew pattern, §5). Each Section pattern places two:
- **treasure:** a locked room, with its key held by the floor's elite;
- **infested:** monsters only, no chests; the stair opens when the floor is clear;
- **hub:** a tiny safe room with one resident or trader stall (owner-gated content).

**The elevator rule.**
- Each Section has two **landings**: its first floor and its 5th floor (Stardew's every-5, §5).
- Reaching a landing records it permanently.
- The town's dungeon stair offers every recorded landing of every opened Section.
- A landing's up-stair goes straight to town.
- Vault stairs go home.
- There is no lift *down past* a floor you have not reached.

**Pacing in a 9-floor Section:**

| Floor | 1 | 2–3 | 4 | 5 | 6–8 | 9 |
|---|---|---|---|---|---|---|
| Elites | 1 | 1 | 1 | 1 | 1–2 | 1 + warden |
| Groups | 1 (2 minions) | 1–2 | special | 2 | 2–3 | 1 |
| Reward | landmark chest | chest + secret | special floor reward | landing | chests, special at 7 | key, gear of the next tier, vault |

- The monster curve rises inside a Section (`curve`). Loot tier steps up by one at each Section (§7).

**After the story: "the Deep Ledger"** (working name, owner-gated)

- **Unlock.** After the King, the tavern gets a board. Each **descent** is one cycle:
  - The 3 Sections are remixed with fresh seeds (`run_seed/endless/c`).
  - Story-free Sections are added once Cottage has art for them. The engine supports both, so this open question can be answered later.
- **Omens (the Hades lever).** At each Section stair, the player picks 0–3 omens, for example:
  - Darker: fog radius −1;
  - Crowded: +1 group per floor;
  - Restless: groups wake from farther away;
  - Lean: fewer potions;
  - Proud: wardens get +1 affix.

  Each omen adds a **star** when the Section is finished. Choosing an omen is the only way to make the dungeon harder.
- **Bounded numbers.** The monster multiplier is `min(1 + 0.2·c, 1.6)`. The loot tier caps at Section 3's tier + 1. The hero's level cap does not move. So there is no stat creep. That is enforced by the balance report in E10.
- **What stars and runs earn** (collection, not power):
  - album pages: one sticker per family × affix pair, plus each warden's endless variants;
  - new stamp sets that unlock into the generator, so floors get more variety;
  - cosmetic **cottage trinkets** for the shelf (a proposal; owner-gated, and it needs a small engine feature);
  - the depth and star record in the journal;
  - one seeded **town request** per cycle (e.g. "bring the Gardener three glowcaps"), rewarding gold, a sticker or a new line.
- **The rhythm.** One Section with its warden and small vault takes about one evening. That is the brief's "lost an evening".

## 5. Slices

| # | Scope | Files likely touched | Acceptance | Size | Who |
|---|---|---|---|---|---|
| **E0a** bench | Measurement only: items 1–5 in §3, at 4 sizes, v2 generator | new `scripts/bench_floors.py`, `tests/browser/bench_floor_play.py`, report `docs/research/endless-e0.md` | Report has p50/p95 for every cell in §3; reruns give identical counts (only times vary) | M (3 h) | **offload** (well-specified; no product code) |
| **E0b** read | Items 6–7 in §3, by reading the player and the lock code | none; notes in the same report | Each UNKNOWN answered with file:line | S (1 h) | **keep** |
| **E0c** decide | Pick sizes and budgets; Rylee playtests 2 sizes | `design/endless-dungeon.md` (new), ADR 0012 "play-time floors and save deltas" | Rylee's pick recorded | S | **keep** (owner gate) |
| **E1** play-time floors | `descent` block (run seed, New descent), `locate()`, v2 generated at stair time, virtual region, deltas through `store()`, `gen_version` card. Absorbs roadmap "random floors phase 2" | `delve.py`, `shapes.py`, `cli.py` (bake), the delve JS part, `065-store.js`, the region-load part | Property: same seed → same floor after reload in Chromium; deltas ≤ budget; a Release 1 save shows the card; bot plays 3 generated floors | L (6 h) | **offload** (foreman, frozen tests written by keep) |
| **E2** delve v3 (Python) | Pipeline §2, FloorPlan, retry and fallback, streams | `src/vefr/delve_v3.py`, `tests/test_floor_v3_properties.py`, `tests/golden/floors/v3/*.json`, `tests/test_floor_perf.py` | 200 seeds × sizes × kinds: one component, up↔down reachable, every anchor, spawn and chest reachable, warden off the path, loops ≥2, fun metrics in §4, fallback < 0.5%; 6 goldens; perf p95 within budget | L (8 h) | **offload** (property tests frozen first) |
| **E3** delve v3 (JS twin) | Line-by-line port | delve JS part, `tests/test_floor_v3_parity.py` | Per-stage parity over 200 seeds; perf budget in Chromium | M (4 h) | **offload** (ideal cheap work: the spec plus the parity harness) |
| **E4** sections | Section pack shape, depth curve, weighted families (Blueprint families by id), pattern, landings | `shapes.py` block, `maplab.py` hook, `blueprint.py` read-only reference, `cli.py`, `locks.py` (sweep over sections) | Validator golden cases (S0 style); `vefr check` sweeps every Section × 200 seeds; a second fixture pack with different Section data and no code change | M (5 h) | **offload** |
| **E5** stamps | Stamp format, rotate and mirror, sockets, `?` secret doors, placement in both languages, `vefr stamp check` | `stamps.py`, v3 layout stage (both languages), `shapes.py` | Every fixture stamp placed in ≥95% of eligible seeds; all 8 orientations parity-equal; a stamp with no connectable socket is rejected with a sentence | L (6 h) | **offload**, but **keep** owns the format ADR |
| **E6** auto-map and points of interest | Bitset fog, map panel, text list, landing marks | fog part, new map-panel part, `440-the-camera.js` (after K3) | Bitset ≤ budget; panel inside the stage at all sizes (stage-containment check); axe clean | M (4 h) | **offload** after the interface lane's panel slice |
| **E7** elites and groups | Affix shape (ADR amendment: closed enemy keys), group placement, wake-all + leash in AI, `extra_drops` | `shapes.py`, `blueprint.py` (closed sets), v3 pop stage (both languages), monster-AI part | Sweep: caps hold; a browser test wakes one member and all wake within 1 turn; leash returns members | M (5 h) | **keep** the ADR, **offload** the build |
| **E8** warden, vault, gate, town states | Warden placement and key, vault stamp, note → flag, town-visit gate, paid shortcut, **town states** (ADR 0006 rescope) | `locks.py`, rules engine (`445` after K3), region overlay in `cli.py`, B2 `places` for the vault door | `vefr check` proves every key is reachable and unsellable, for all Sections × 200 seeds; a scenario plays vault → town changes → next stair opens; the shortcut charges once | L (8 h) | **keep** (gate logic, ADR) |
| **E9** special floors and secrets | treasure, infested and hub kinds; bump-to-open secrets | v3 plan and pop stages, a player movement part | Sweep per kind; infested stair opens only when the floor is clear | M (4 h) | **offload** |
| **E10** endless and omens | `endless` block, cycle locate, omens as modifiers, bounded multiplier, board hook; **balance report** (roadmap NEXT item 8) | `sections.py`, `shapes.py`, `scripts/balance_report.py` | Depth 1–300 sweep: multiplier ≤ cap, loot tier ≤ cap; every omen changes only its stated field (golden diff) | M (5 h) | **offload**; **keep** reviews the numbers |

How these map to the design record: its E1 is E4 here, E2 is E5, E3 is E7, E4 is E8 and E5 is E10. The play-time port and the v3 twin were split out of its E0 because each one carries its own risk.

**Sequencing with the other lanes.** The 2-foreman cap and "one foreman per campaign" both apply.

- **Now, no collisions:** E0a runs as the single research worker. It touches only new files. E0b is coordinator work.
- **E1 needs K2.** `store()` and its lint must land first, because the save code must not add raw `localStorage` calls.
- **E2 is a new Python file only**, so it can run as soon as E0c is decided.
- **E4 needs S1** (the `shapes.py` table) and should follow S2.
- **E6 needs K3** (440 split, which waits for I1 to merge) and the interface lane's panel convention.
- **E8 needs B2** (places, for the vault door) and K3 (the 445 rules engine).
- **B3 (deferred placement sentences) is dropped.** Play-time placement in v3 replaces it.
- **Lane T reorder (recommended):** B0, K2, S1, S2, B2, **E1, E2→E3, E4, E5, E7, E8**, then A1, B1, B4 (their cut-lines still apply).

**Every slice:**
- one worktree under `~/worktrees/`;
- one squash PR, so rollback is `git revert`;
- after a VEFR merge, Cottage bumps `VEFR_REF`;
- `packaged.html` conflicts are rebuilt, never merged by hand.

## 6. Cottage content plan

**This is data only.** Every name, line, note and picture is **owner-gated**. Below are proposals.

| Act / Section | Floors | Families (existing art) | Warden (candidate) | Vault |
|---|---|---|---|---|
| 1, the cellar | authored floor 1 + 8 generated | rat, shade, moths, rustle; round 12 shallow cast (toad, crock mimic, wick sprite, spider) | **Ashwing** (pale moth) | Truth one: "the fire was meant to hold something down" (her pick; the note's words are hers) |
| 2, the root hollows | 9 | round 12 deep cast (cobweb wraith, cricket, barrel mimic, root tangle), mushroom folk | **Brother Sporeling** (mushroom elder) | Truth two: the one who came back is the Spell Keeper |
| 3, the undercroft below the burned tavern | 9 | beetles, hollow shade, ember creatures (needs fire status) | **Sir Hollowhorn** (stag beetle) carries the key to the **throne room**. The **King** carries the seal to the final vault | The realization: "what is held down is the town's own kindness" |

- Held back for endless wardens or a 4th Section: the Reeve mole and the Seneschal rat (round 11).
- **Kept from Act 1:** the floor 1 map, the King's throne-room map (reused as the Act 3 throne region), and 3–5 hand-drawn room shapes turned into stamps (Rylee picks which).
- **Replaced:** floors 2–6, the Keybearer placements, the floor-6 ending, the `cottage-deeper-zone` maps. The `requires` lock chain stays as the gate mechanism.

**Town changes per act** (drafts, hers to rewrite):
- After vault 1: the burned ruins are partly cleared, and the Trader's stock moves to tier 2.
- After vault 2: the Spell Keeper's reveal lines, and a new resident.
- After the King: the town is warm instead of wary. The old tavern is under rebuild, and the Deep Ledger board opens.

**Gated on Rylee:**
- names of Sections, points of interest, affixes and omens;
- warden assignments;
- vault notes;
- town lines;
- art: 2 new tilesets, 3 warden halls, the throne-room redraw, trinkets;
- lengths;
- the shortcut price.

## 7. Risks, unknowns, first three things

**Risks:**
- **Parity drift.** The per-stage parity CI gate catches it.
- **Monster flood fills at big sizes.** E0 measures them.
- **Save bloat.** Bitsets plus the 40-floor cap.
- **Generator changes breaking saves.** The identity triple and the regenerate rule.
- **Scope.** The campaign is about 60 hours on a small VM. E10 and E9 are cut first.
- **Overwhelming groups in Cozy mode.** Caps plus leash.
- **A 27-floor story may outlast "low bandwidth".** Lengths are decided after E0.
- **Collisions with lanes T and I.** See the sequencing above.

**UNKNOWN:**
- loading virtual regions;
- whether `requires` can test a flag;
- the current fog and floor storage format;
- phone performance on Rylee's real device;
- whether the AI can give a monster an extra move;
- how town states map onto baked regions;
- the real minutes per floor.

**Tomorrow:**
1. **E0b (keep, 1 hour).** Read the player's region-load path, the fog and floor store, and the `requires` check. Answer the four UNKNOWNs in §3 with file:line citations.
2. **Dispatch E0a** as the research worker, with this section's measurement table as its acceptance test.
3. **Write the frozen tests for E2** (`tests/test_floor_v3_properties.py` assertions and the FloorPlan schema). Also mark `cottage-acts-2-3-plan.md` as superseded and amend ADR 0006's roadmap entry to "town states".
