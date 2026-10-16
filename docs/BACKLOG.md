# vefr backlog

> **HISTORICAL SNAPSHOT, NOT AN ACTIVE WORK QUEUE** (captured 2026-10-07; rechecked 2026-10-16). These paragraphs preserve what was parked then, *not* present issue state, permission to begin work, or proof that features are missing. Some items were later reopened. As of the 2026-10-16 audit, historical entries #317 (Player Driver) and #295 (monster-turn benchmark) are **open again**. Follow those GitHub issues for current acceptance. Optional feature explorations now live in [the Feature Lab](research/2026-10-16-feature-lab.md), with exact [source briefs](research/2026-10-16-feature-lab-archive.md).
>
> **Current work source:** [open GitHub issues](https://github.com/rylee-bee-labs/vefr/issues), current PRs and mission/Project Home truth. Do **not** delete these archival entries when reopening or closing an issue; keep historic decisions and source links intact. No issue is automatically closed by this banner.
>
> **Reading note:** the original introduction below says to delete an old entry when reopening an issue. That was the 2026-10-07 practice being archived, **not current guidance**; preserve the dated narrative and use the live issue for active state.

This file is the tracking doc for work that was open in GitHub Issues and was closed as not planned on 2026-10-07, so the queue could reach zero.
The issue bodies are not edited; each summary below is ours, written from the body at close time.
To restart an item, reopen the linked issue or open a new one and delete its section here.
It was built by census: every issue open in this repository on 2026-10-07 appears below, newest first, and nothing else does.

### #317 — Epic: Player Driver, portable session capsules, and replayable play

- Issue: https://github.com/Rylee-Bee/vefr/issues/317
- Opened: 2026-10-06 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

Rylee and Sol worked this through on 2026-10-06 after noticing that one missing seam shows up as four different problems.
A player wants to pass the controller to another person.
A creator wants to hand an agent the exact run instead of describing how she played.
UAT and autoplay want to drive the game the same way a player does, and troubleshooting wants a compact artifact that reproduces a bug or an interesting route.
The epic generalizes #260 and the Release-1 findings about scenarios and one stable play-state API.
The proposed shape is one reusable player-driving seam plus two portable data shapes: a Player Driver, a deterministic observation/action contract that keyboard, touch, replay and agents all converge on, with VEFR remaining authoritative and the driver unable to invent world truth; and portable session capsules for the artifacts.
The hard constraint is that this must stay one system rather than becoming four.

Next step, when this is picked up: write down the single observation/action contract that keyboard, touch, replay and agents all sit on, before building any consumer of it.

### #295 — bench: rerun the 128x96 monster-turn numbers after E0d (sleeping monsters)

- Issue: https://github.com/Rylee-Bee/vefr/issues/295
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

E0a measured the monster turn at 10.8 ms at 64x48 and 33 ms at 128x96, against an 8 ms budget.
E0d (#288) made far monsters sleep and bounded the flood fill, which should bring those numbers down, but the bench was never rerun.
The bench is also stale in three concrete ways: it inlines the AI parts, it needed a `store` stub after K2, and its monster-turn assertion now fails because sleeping monsters do not take turns.
The ask is to rework `bench/` so it measures a turn with sleepers present, plus a worst case where a whole linked group is awake, since E7 adds groups.
Then rerun at 48x32, 64x48, 96x64 and 128x96 in the browser and write the numbers into `docs/research/endless-e0.md` and `bench/runs/`.
Acceptance is either the 128x96 awake-group case landing under the 8 ms budget, or a report that says plainly by how much it misses and what E7's caps should be.

Next step, when this is picked up: rework `bench/` to call the real AI parts (with a `store` stub) so it can measure a turn with sleeping monsters present.

### #273 — Epic: endless dungeon (sections, key wardens, play-time floors, stamps, elites)

- Issue: https://github.com/Rylee-Bee/vefr/issues/273
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

An epic for the endless dungeon mode.
The design record is `docs/plans/endless-dungeon/PLAN.md`, which holds Rylee's decisions from 2026-10-04.
It is sliced as E0 prototype (play-time generation, big maps), E1 sections, E2 hand-painted stamps, E3 elites and linked groups, E4 key warden, vault and act gate with a paid shortcut, and E5 endless mode.
Floor lengths are deliberately not fixed up front; they are tuned after E0 once real play-time numbers exist.

Next step, when this is picked up: read `docs/plans/endless-dungeon/PLAN.md` and take the first slice that has not landed.

### #269 — validator: the rule event list is typed three times and has drifted (maplab says six events, there are eleven)

- Issue: https://github.com/Rylee-Bee/vefr/issues/269
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

The tighten-shapes plan builder found that the rule validator, the album validator and the JS EVENTS table each list the rule events independently.
They have drifted apart: `maplab.py:694` says "the six events are ..." while there are eleven.
Slice S2 fixes it properly by collapsing the three lists into one event table and regenerating the golden exactly once, with the reason stated in the PR.
Until that lands, the sentence in `maplab` is simply wrong and will mislead the next reader.

Next step, when this is picked up: fix the wording at `maplab.py:694` so it names the eleven events rather than six.

### #268 — Epic: the in-world interface (parchment and soft wood, Ledger type, one stage)

- Issue: https://github.com/Rylee-Bee/vefr/issues/268
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

Rylee's direction of 2026-10-04 is that everything inside the game wears the game's own themed UI, with no literal device frame, native to the world, cute and minimal.
The chosen look is parchment and soft wood with Ledger type (Crimson Pro).
The plans are `docs/plans/interface/PLAN.md` and the Cottage `docs/plans/native-ui/PLAN.md`, and the lab artifact where she chose the look is saved there.
I1, the stage rectangle and HUD frame, is done and reads right on desktop; it sits on `feat/in-world-interface`, deliberately unmerged until the phone layout is right.
I2, the phone dock, is foreman-running, with tests already committed for containment, no-overlap, and controls sitting beside the map.
I3 through I6 follow: a themed backdrop as a skin `backdrop` part, skin-chosen bundled type, applying the skin parts the player currently ignores (slot, tab, toggle, tooltip, speech, divider, banner, corner, gold plate), and HUD icons plus a speech box.

Next step, when this is picked up: finish I2, the phone dock, so `feat/in-world-interface` can merge once the phone reads right.

### #267 — Epic: tighten the shapes (15 slices, two foreman lanes)

- Issue: https://github.com/Rylee-Bee/vefr/issues/267
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

The umbrella epic for the tighten-the-shapes campaign.
The plan is `docs/plans/tighten-shapes/PLAN.md` (Opus, 2026-10-04), with evidence in `docs/research/size-and-language-pass.md` passes 1 to 3 and `docs/research/tighten-shapes-web-research.md`.
ADR 0010 (things and places) records Rylee's decisions: glyphs are written into `map.md`, places come before things, and placement sentences are in scope under a six-word language.
The campaign runs as two lanes: an ordered lane of K1, B0, K2, S1, S2, A1, B2, B1, B4 with one foreman at a time, and a coordinator lane covering S0, the B0 gap tests, B0c, K3, S3 dispatch, A0 and A2.
Several slices are already checked off, including K1 (#272), B0 (#277), K2 (#276) and S1 (merged as #281), and S2 is the one-event-table fix that closes the "six events" drift in #269.

Next step, when this is picked up: land S2, the single event table, regenerating the golden once with the reason in the PR.

### #260 — vefr look cannot start in a given region (player.wake did not move the start)

- Issue: https://github.com/Rylee-Bee/vefr/issues/260
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

Found during the Cottage release-1 night.
`player.wake` in `world.json` does not change where `vefr look` starts.
That makes screenshotting a deeper floor cost a whole playthrough just to reach the floor you want to see.
The ask is a dev-only `vefr look --at REGION X,Y` flag so visual QA becomes cheap.
The workaround today is the Cottage bot, `tests/playthrough` driven by `COTTAGE_SHOTS`.

Next step, when this is picked up: add a dev-only `--at REGION X,Y` flag to `vefr look` so it can start in a given region.

### #259 — point-to shows raw region ids ("To reach floor-1"): regions need display names

- Issue: https://github.com/Rylee-Bee/vefr/issues/259
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

Found during the Cottage release-1 night.
`point-to` accepts only region ids, so the Where-next hint reads "To reach floor-1, go north-west." and leaks an internal name at the player.
The ask is a display name per region, and `point-to` also accepting POI labels such as "the stair down".
Cottage works around it for now by using plain ids everywhere.

Next step, when this is picked up: give regions a display name and let `point-to` accept POI labels like "the stair down".

### #217 — Equipment (design/equipment.md) and real act 2 (ADR 0006)

- Issue: https://github.com/Rylee-Bee/vefr/issues/217
- Opened: 2026-10-02 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

A backlog item for equipment, following `design/equipment.md` and ADR 0006, which together sketch what a real act 2 looks like.
Growth already adds a mods base.
Equipment's `mods.atk` and `mods.hp` are described as the next layer on top of that base.

Next step, when this is picked up: read `design/equipment.md` and settle which `mods.atk` and `mods.hp` values equipment grants.

### #216 — Album: reward progression and completeness while staying cozy

- Issue: https://github.com/Rylee-Bee/vefr/issues/216
- Opened: 2026-10-02 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

A backlog item for the album, tracked in `design/album.md`.
It asks for reward progression and a sense of completeness through the album.
The stated constraint is that it stays cozy rather than turning into a completionism treadmill.
Nothing has been started.

Next step, when this is picked up: read `design/album.md` and write down what the album tracks and what finishing it rewards.

### #215 — Random floors phase 2: locked stair (requires) + guardian ladder

- Issue: https://github.com/Rylee-Bee/vefr/issues/215
- Opened: 2026-10-02 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

A phase-2 backlog item for random floors, added 2026-10-02.
It asks for a locked stair gated by `requires` conditions.
It also asks for a guardian ladder, escalating the guardians between floors.
The design context lives in `design/random-floors.md` and `design/gates-and-guardians.md`.

Next step, when this is picked up: read `design/gates-and-guardians.md` and settle how `requires` is evaluated for the locked stair.

### #145 — feat(delve): richer floors (wave-function-collapse ideas)

- Issue: https://github.com/Rylee-Bee/vefr/issues/145
- Opened: 2026-09-30 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

This comes from Wave 2.5, section 2.2 of `docs/research/2026-09-30-enhancement-packet.md`.
Today the generator makes rooms joined by corridors.
Wave-function-collapse generation, using open work like mxgmn's WaveFunctionCollapse, DeBroglie and MarkovJunior, makes tilesets that feel hand-authored, which is the point for deeper floors and outdoor regions.
The seam is `src/vefr/delve.py`, a second generator shape sitting behind a flag or seed.
Acceptance is that generation is deterministic from a seed, stays reachable, passes the #131 properties, and is opted into by a pack rather than forced.
Effort is estimated at M-L.

Next step, when this is picked up: prototype one WFC generator in `src/vefr/delve.py` behind a flag and check it against the #131 properties.

### #143 — feat(narrative): optional Ink conversations per speaker

- Issue: https://github.com/Rylee-Bee/vefr/issues/143
- Opened: 2026-09-30 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

This comes from Wave 2.3, section 2.3 of `docs/research/2026-09-30-enhancement-packet.md`.
A speaker today has flat `seeds`, one line per phase.
Ink, under MIT, would add variables, once-only choices, conditional text and gather points, and it has an official JS runtime, `inkjs`, that runs inside the single-file player.
The seam is an optional `conversation.ink` per speaker, `inkjs` in `web/packaged.html`, and maplab validation that a pack's Ink compiles.
`seeds` has to keep working for packs that do not use Ink.
Acceptance is that a pack with an Ink conversation plays end to end offline, and a pack without one is unchanged.
Effort is estimated at M-L.

Next step, when this is picked up: get one Ink conversation playing end to end offline inside `web/packaged.html`.
