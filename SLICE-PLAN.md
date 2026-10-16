# Slice E4 — sections (VEFR)

You are the single build worker for one slice of the VEFR game engine, working alone
in a throwaway clone: you read, write, edit, run shell commands and commit here. There is
no foreman and no sub-workers — do every step yourself, in order, committing each finished
step. Do not try to launch `offload` or any other agent; it does not exist here.

Your sandbox may not have `uv` or `node` on PATH and has no network. If you cannot run the
test suite, say so plainly in UNRESOLVED and still write the code and the tests; the
coordinator runs the gate outside your sandbox and reports what it sees.

## Repo and rules (they are not optional)

- Repo: VEFR (`Rylee-Bee/vefr`), a game ENGINE, MPL-2.0, Python 3.11+ under `src/vefr/`,
  the woven player under `web/`, tests under `tests/`. Read `AGENTS.md` in the repo root
  first; it is short and it is the boundary.
- `web/packaged.html` is GENERATED and never committed. Edit the parts under
  `web/player/parts/`; the file is rebuilt where it is read. Never hand-edit or commit it.
- The engine must never name a game. `tests/test_pack_neutrality.py` enforces it.
- No model calls in deterministic surfaces: `export.py`, `weave.py`, `maplab.py`, `journal.py`,
  `blueprint.py`, `generator.py`, `delve.py`.
- Tests first, frozen, and committed in their OWN commit before the implementation starts.
  A frozen test is not edited to make an implementation pass. If a frozen test is genuinely
  wrong, fix the test in a separate commit and say so in your report with the reason.
- Every commit ends with exactly this trailer line:

      Co-Authored-By: MiniMax-M3.1-Flash-Preview <noreply@minimax.io>

- Out of scope: E6, E8, E9, E10, the endless mode and omens, art, any content that is
  Rylee's to name (Section names, points of interest, affix and omen names, warden
  assignments, vault notes, town lines are all owner-gated — see PLAN.md §6 "Gated on
  Rylee"; use neutral placeholders in fixtures and never invent canon),
  anything under `worlds/` other than `worlds/sample-world` staying valid, deploys, any
  network push, sudo.
- One squash PR at the end. Do not merge anything. Do not push.

## What this slice is

PLAN.md §5 row **E4** in `docs/plans/endless-dungeon/PLAN.md`. Read §1 (the model), §2
(generator architecture and the determinism rule), §4 ("Fun at scale", especially the
elevator rule and the pacing table) before you start. Epic: vefr #273. This is the endgame's
structure: **Sections of 8 to 11 floors, each ending in a key warden and a vault.**

Already landed and yours to build on: E2 (`src/vefr/delve_v3.py`, the v3 generator),
E5a (stamps in v3), E7 (elites, groups, leash), S1 (`src/vefr/shapes.py`, the schema table),
B1/B2 (Blueprint format 2 things and 3 places), K2 (`store()`), F1 (fog as a bitset).

## Scope (PLAN.md §5, row E4)

- the **Section pack shape** on the S1 schema table — the shape is specified verbatim in
  PLAN.md §2 under "Section pack" (`sections/<id>.json`); copy it, do not invent one,
- the **depth curve** (`locate(depth, pack)` → `(cycle, section, k)`; `depth` is a global
  integer; the story is cycle 0),
- **weighted families**, with the families coming from Blueprint by id,
- the floor **pattern** (`["entry","n","n","special","landing","n","special","n","warden"]`),
- **landings**: each Section has two — its first floor and its 5th (Stardew's every-5). Reaching
  a landing records it permanently; a landing's up-stair goes straight to town; the town's
  dungeon stair offers every recorded landing of every opened Section; there is no lift down
  past a floor the hero has not reached.

Files likely touched: the `shapes.py` block, a `maplab.py` hook, `blueprint.py` (read-only
reference — it is a deterministic surface and must stay deterministic), `cli.py` (the bake),
`locks.py` (the sweep over sections).

## The rules that must hold (PLAN.md §2)

- Floor identity is `(gen version, section content hash, floor_key)`, so a Section's content
  hash is part of identity: changing a pack's Section data invalidates that Section's floors.
- `floor_key = run_seed/section.id/cycle/k`; each stream is
  `prng("v3|" + floor_key + "|layout")` and likewise for `|plan`, `|pop`, `|loot|<mob id>`,
  `|chest|<chest id>`.
- Forbidden: `Math.random`, the clock and globals; floats other than `floor(rng() * n)` with
  `0 <= n < 2^31`; iterating a map/dict/object's keys where draws are consumed (use arrays
  sorted by id); sorts whose comparator can tie (break ties by index).
- In a 9-floor Section the pacing table in §4 holds: elites 1 per floor (1-2 on floors 6-8,
  1 + warden on 9), groups 1-3, two special floors, a landing on floor 5, the key and the
  next-tier gear and the vault on floor 9.

## Acceptance (PLAN.md §5, row E4)

1. **Validator golden cases** in the S0 style (`tests/golden/validator/`): the Section block's
   error sentences are pinned, in order, so a later change to them is a deliberate act.
2. **`vefr check` sweeps every Section × 200 seeds**: for every Section in every fixture pack,
   every key is reachable and unsellable, and the floors hold. This is the §7 property proof
   from the E2 row, run over Sections rather than over one floor kind.
3. **A second fixture pack with different Section data and no code change** validates green —
   the proof that Sections are data and not hardcoded.
4. The full gate green, which is what the coordinator runs:

       bash tests/run.sh && uv run --group test ruff check src tests scripts && uv run --group test norns validate --pack worlds/sample-world && python3 scripts/check_public_surface.py

## How to build this slice (you do every step yourself)

1. Read PLAN.md §2's "Section pack" shape and S1's table, then list every touch point the new
   block needs, with file:line. Do not start editing until that list is written down.
2. Write the FROZEN tests for acceptance 1 to 3 and commit them alone.
3. Add the block to the schema table; add the `maplab.py` validation hook; wire `cli.py`'s bake;
   add the `locks.py` sweep.
4. Add the second fixture pack with different Section data.
5. Run what checks you can; update `ROADMAP.md` with exactly one entry for this landed change.

## Report (this exact shape, at the end)

    RESULT: <one sentence: is this slice done, and what is left>
    CHANGED: <files, with the commit sha of each logical step>
    CHECKS: <each command you ran and its result, verbatim output lines>
    EVIDENCE: <file:line for each of the three acceptance items>
    UNRESOLVED: <anything a reviewer must decide, or NONE>
    NEXT: <the one action the coordinator takes next>

Be honest. A slice that is not done is not a failure to report as done. Never weaken a sweep
or the golden to get green. If the Section block turns out to need a change to the pack
contract that `AGENTS.md` marks "Ask first", stop and say so in UNRESOLVED rather than
deciding it yourself.
---

## Decisions in force (quote these; do not paraphrase them)

- 2026-10-05 Rylee: "I want to have a fun project running alongside the infrastructure
  work." This is that project.
- 2026-10-05 Rylee: "Both, one after the other" — the dungeon lane first, then the rest of
  tighten-shapes (K3, S3, A0, A2, B4, A4, A5), which is a separate later mission.
- 2026-10-05 Rylee: "Run it alongside" — this lane has its own coordinator next to the
  infrastructure missions.
- 2026-10-04 Rylee, recorded in PLAN.md: map sizes up to 128x96 for phones; fog circle plus
  room reveal; the E7, E5, E8 order (E5a and E7 are merged).
- 2026-10-05 Rylee: ship only our own credited art, and nothing goes live without her yes
  after a gallery preview. So: no canon, no invented Section names, no publishing.
- Every slice: one worktree, one squash PR, rollback is `git revert`; after a VEFR merge,
  Cottage bumps `VEFR_REF`; `packaged.html` conflicts are rebuilt, never merged by hand.

## What is already landed, and this branch sits on top of two PRs

This worktree is based on `feat/vefr-s2-event-table`, which is **S2** (issue #267) and is
itself an open PR. S2 moved the event vocabulary into `shapes.EVENTS` and left
`maplab.py` with no event-name string literal at all, so the validator hook you add reads
that table rather than a list of its own. Two other slices are open at the same time and
also touch the generated player:

- **E1** (`vefr#308`) adds `web/player/parts/395-the-descent.js`.
- **E3** (`vefr#307`) adds `web/player/parts/395-engine-delve-v3.js`.

Neither touches a file you are building in, but all three regenerate
`web/packaged.html` and all three refresh `NO_SKIN_WEAVE_SHA256` in
`tests/test_skin_validator.py`. Expect that constant to need refreshing in your branch —
that is the designed behaviour, not a failure. See the next section for why it is easy to
get wrong.

## The one thing this slice's build will otherwise waste a day on

**`tests/run.sh` weaves the sample world over the GENERATED `web/packaged.html`, not over
`web/player/parts/`.** It does not read your parts. So:

- `web/packaged.html` is generated and, since vefr#523, never committed: the test session
  rebuilds it from the parts before the first test reads it, so an edited part is what gets
  measured. Anything you run outside pytest that reads the file - a weave by hand - wants
  `uv run python scripts/build_player.py` first.
- Never hand-edit `web/packaged.html`, and never commit it.
- `uv run python scripts/build_player.py --check` must be clean at the end: it asks whether
  the parts build (every listed part exists, none orphaned). `tests/test_player_build.py`
  enforces the same thing.

This is not a theoretical warning: slice E3 lost two full passes to exactly this, fixing the
part correctly and then measuring a stale `packaged.html`. The generated file was the only
difference between a failing suite and a green one.

## Your sandbox, honestly

You have no `uv`, no `node`, no `pytest` and no `ruff`, and no network. The coordinator
runs every gate outside your sandbox, on the same worktree, and reports what it sees. So:

- Do not claim a check you did not run. "NOT RUN (no uv in this sandbox)" is a complete,
  acceptable line in CHECKS. A check you argued for from reading the code is worth
  something; a check you claim you ran is worth nothing.
- Do not weaken, resize or skip a test to make something pass. You cannot run them anyway.
- You CAN run `python3` (the system one) for pure-Python reasoning, `git`, and `grep`/`sed`.
  Use it to check your own reasoning the way E3's second pass did: emulate the OLD behaviour
  and reproduce a reported failure exactly, which proves you are looking at the right bug.
