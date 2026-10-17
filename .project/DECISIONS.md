# DECISIONS — vefr

## 2026-10-04 — Munr is a game built in VEFR, not a predecessor engine

**Decision (Rylee, 2026-10-04, in chat).** Munr is one active private game.
`Rylee-Bee/munr` is its canonical repository; VEFR is the engine/studio it is
made in. The former `munr-story` repository is a migration-history source,
not a second project identity.

The old norn implementation in Munr's Git ancestry is historical engine
lineage only. Moving reusable engine behavior into VEFR does **not** retire
Munr, and inactivity in that historical engine code must not be used as stale
or archive evidence for the game.

**Relationship.** Munr and VEFR are separate project identities connected by
the normal game/world-pack contract. Historical code ancestry is provenance,
not a synchronization contract.

**Supersedes/clarifies.** This closes the unresolved D5 question and clarifies
the 2026-09-25 "keep, separate" ruling. D5 ("Retire munr") is superseded.

**Status.** ACCEPTED.

## 2026-10-04 — the endless dungeon: sections, key wardens, acts change the town only (Rylee)

**Decisions (Rylee, in chat).** (1) The dungeon is one line of generated floors cut into sections of 8 to 11; each section ends in a key warden whose key opens a vault with a lore note that advances the act. (2) Acts change the town, never the dungeon generator; the King ends Act 3, then an endless mode. (3) Each floor has randoms plus one or two elites and linked groups; hand-painted room "stamps" can be placed in generated floors; maps get much bigger. (4) Everything is a VEFR feature; a game supplies data. (5) The stairs to the next section stay locked until the town visit, with a paid shortcut. (6) Target sizes up to 128x96, optimized for phones: monsters sleep until near, the flood fill is radius-bounded, fog becomes a bitset (E0a evidence, #278). (7) Fog style: a circle plus whole-room reveal. (8) The Keybearers are named Ashwing, Brother Sporeling and Sir Hollowhorn (Cottage), candidates for section wardens. (9) A playable generated prototype comes before the Cottage Act 1 rebuild.

**Why.** She wants a game she can play for hours after the story ends. The Opus plan and the research (`docs/research/big-generated-maps.md`) back the choices; lengths and the shortcut price stay open until a prototype. **Supersedes** the Cottage acts-2-3 plan and ADR 0006 as written (rescoped to town states).

## 2026-10-03 — four decisions: resistances live on both, "the Keybearer", one foreman, equipment first

**Decisions (Rylee, 2026-10-03, in chat).** Asked four focused questions; all four answered.

1. **The hero's resistances live in two places: the pack's `player` block as a base, and worn gear
   on top.** She chose "both" over the single authored set, knowing it widens slice one. So the
   pack contract carries `player.resist` / `player.immune` (a floor for the whole run) **and** an
   item-level grant that equipment adds. The gear half is cheaper than it looks and dodges the ADR
   entirely: Blueprint's closed `FIELD_KEYS` govern *enemy* records, not items, so an item field is
   validated by `item_slot_errors` and baked in `_player_items` with no format change. The enemy
   half still needs the ADR, because enemies must carry types.
2. **The guardian role word is "the Keybearer"** (from the Diablo III Keywarden precedent, verified
   the same day). Warm, storybook, and it tells the player exactly what the monster is for. Each
   floor's proper name and its key's name are still hers; the Cellar King, the seal, and the first
   lock (floor 3 to 4) are settled.
3. **Campaign work runs as one foreman per campaign, slices in sequence, MiniMax M3.1, budget 8,
   with the integrator reviewing every diff.** This answers `11-open-decisions.md` item 7, which
   had to be stated before a multi-slice campaign launches. The reasoning that decided it: the
   descent block splits into validator+bake and player generation, and those **share
   `maplab.py` and `web/packaged.html`**, so two foremen would conflict on the same files anyway.
   Four concurrent foremen was also rejected - the box has a documented history of an exit-137
   out-of-memory kill under load, and four diffs in one file at once is unreviewable anyway.
4. **Equipment is finished before anything new starts** (the glossary, the player guide, and the
   pack demo). The thread is live and two steps short; leaving it dangling to open a fourth work
   stream is how a repo accumulates half-landed slices.

**Status.** ACCEPTED (2026-10-03). Owner: Rylee.

## 2026-10-03 — wave 2: what the three stale issues actually cost

**Findings (2026-10-03, checked in the repo, not from the issue text).** #143, #144 and #145 sat
untouched from 2026-09-30. Their stated efforts do not survive contact with the code:

- **#144 (audio pairing) presumes a system that does not exist.** *(Historical, 2026-10-03. Superseded in part on 2026-10-04: a small synthesized sound set landed as #257. The pairing rule below still governs it.)* The engine had **no audio at
  all** - a search for `AudioContext`, `new Audio`, `playSound` and friends over `src/` and `web/`
  returns nothing but a line of prose in a Library chapter *about* art. So "pair every sound with a
  visual event" cannot be a pairing job; it is "build sound from nothing", and the stated `S-M` is
  wrong. Note the irony: the issue's *accessibility* promise, that silence stays fully playable, is
  **already true**, because there is no sound to silence. The valuable part is not a work item at
  all - it is a rule to honour *if* audio is ever added, which is far cheaper to write down now
  than to retrofit later.
- **#143 (Ink) is the most expensive per unit of value, and it breaks a real constraint.**
  `web/*.js` holds **six files, all first-party** - there is no vendored third-party JavaScript
  anywhere. `web/packaged.html` is a single file that must run from `file://`. Inlining `inkjs` is
  mechanically possible (the bake already inlines CSS, fonts and sprites), but it would be the
  first vendored library in the player. Worse, its acceptance asks `maplab` to validate that a
  pack's Ink *compiles*, which means running a JavaScript compiler from the Python validator - a
  new dependency in the validate path, and `norns validate` is a deterministic surface.
- **#145 (WFC) is largely superseded for the purpose it was filed under.** The approved weighted
  descent already delivers per-run variety with a far simpler mechanism, and a second generator
  shape is `M-L`. Its acceptance also depends on "#131 properties" (property tests), which is itself
  unbuilt wave-1 work. What remains genuinely distinct about WFC is *tile coherence* - tilesets
  that look hand-authored - which is an aesthetics question, not a variety one.

**Recommendation, for Rylee's call:** close #144 as a work item and keep its rule as a note; defer
#143 explicitly behind the descent block; narrow #145 to tile coherence so it stops carrying the
per-run-variety burden the descent block now owns.

**Status.** RECORDED (2026-10-03). No issue was closed or edited by this session.

## 2026-10-03 — two new campaigns approved: the weighted descent, and the full elemental triangle

**Decisions (Rylee, 2026-10-03, in chat).** Asked what she wanted next, she chose the **larger** of
both options offered, twice:

1. **Guardians are generated per run with a weighted table.** Randomness lives in a per-run seed
   (one per descent; each floor derived from `(run seed, floor number)`), **and** the tables gain
   weights, so some creatures are common and some rare. The design already proposed
   `per_floor: [min, max]` counts; weights are the one genuinely new concept, because they make
   the table answer "which one" as well as "how many".
2. **The full elemental triangle: damage types, status effects, and resistance/immunity.** Not the
   lore-only version, and not types-plus-one-status. This is the richest option and the one that
   turns every mob and the hero into a stat block.

**These are campaigns, not slices.** Each needs tests written first and merged, then an
implementation that flips exactly its own tests. #1 is close to one campaign. #2 is two or three
slices with an ADR first.

### What the code actually is today (surveyed 2026-10-03, evidence in the PR and `docs/guides/`)

The survey is worth keeping because it says the blast radius is **small but the seams are sharp**:

- **Damage is applied in exactly two functions.** `heroAttack` and `enemyAttack` in
  `web/packaged.html`, both a bare integer subtraction. No randomness anywhere in combat (the file
  says so in prose at three places). This is good news: the resolver has two seams, not twenty.
- **The two paths are asymmetric.** The hero's damage goes through `heroAtk()`; the enemy applies
  its **raw baked `atk`**. So a resistance or immunity rule cannot be a stat modifier - it needs a
  **resolver** applied on both sides, or fire damage will resist and necrotic will not.
- **The rules engine cannot own a status effect, by design.** `applyActions` in the pure engine
  changes only `{flags, beliefs, fired, items, where, meanings}` - it has no combatant, no hp and
  no timer. `validAction` is a closed if-chain that voids the whole rule for an unrecognised key,
  and the code states the law: *"One returned action onto a surface that ALREADY exists - never a
  new subsystem."* A status effect must therefore live in the **combat** layer. Extending the
  rules vocabulary would break that law, so it is not the route.
- **There are two timed-effect precedents and they are different shapes.** Item `light` is a real
  countdown (`lightTurns`, `lightTick()`) and is the pattern to imitate; its four turn boundaries
  (`lightTick(); enemyTurn();`) are the de-facto "the hero's turn is over" idiom a status effect
  must hook. Growth's `practice` mode is the opposite shape - a monotone accumulator with a cap and
  **no expiry** - so it is not a precedent for anything that ends.
- **A new enemy field is silently dropped unless threaded through four allow-lists**, one of which
  is the **closed** `FIELD_KEYS`/`FIELD_ORDER` in `src/vefr/blueprint.py`. So any enemy field is
  also a **Blueprint format change**, and therefore an ADR amendment. This is the coupling that
  makes campaign #2 bigger than it looks.
- **No per-depth or per-band stat scaling exists anywhere.** The ladder's "scaled by depth" is
  entirely unbuilt; growth is the only scaler and it is per-level or per-N-actions.

### Recommended order, and why

**The weighted descent first.** It is self-contained: it touches the generator, the bake and the
player's floor generation, and it needs **no new enemy field** as long as the guardian ladder stays
authored. It unblocks #215, whose only remaining blocker is the names. The elemental triangle
should follow, and should open with an **ADR**, because it changes the Blueprint's closed key sets
and adds a damage resolver - both of which are decisions to record before code, not after.

**Status.** ACCEPTED as scope (2026-10-03). Owner: Rylee. The ADRs and the frozen contracts are the
next step and are not yet written.

## 2026-10-03 — the language packet is approved; the gate is released

**Decision (Rylee, 2026-10-03, in chat: "Approved. Go").** This releases the gate in
`docs/research/language-architecture/11-open-decisions.md` item 6, which held that *nothing is
authorized until Rylee has read the disposition and says go*. She has now said go on the
disposition: **GO WITH CONSTRAINTS**.

**What the approval authorizes.** The earned scope only: an **optional, build-time source layer** —
authoring source -> validate -> normalize -> today's pack structures -> today's runtime. The first
slice of that is the **Blueprint**, and the Blueprint is already built, merged and trialled live on
the private pack (`docs/adr/0008-blueprint-format.md`, PRs #219-#233). So the approval confirms a
direction that is already partly spent; it does not by itself require new code.

**What the approval explicitly does NOT authorize** — the packet's own "What it does not earn"
list, unchanged by this ruling: a new runtime, event sourcing, a logic engine, natural-language
authoring, a plugin system, an estate-wide kernel, a resolver framework, broad pack migration, or a
new public pack contract. The kernel / dialect / pack horizon stays deferred until there is a
**second real consumer** (the 2026-10-02 second-consumer rule). "Go" means the gate is open, not
that the deferred list is now approved.

**Also still open inside the packet** (these need their own answers, not this one): the Foreman
count and model to state before any multi-slice campaign launches (`11-open-decisions.md` item 7),
and how guardians and the ending room are authored (item 5) — which is #215 and is separately
blocked on the guardian names.

**Status.** ACCEPTED (2026-10-03). Owner: Rylee.

## 2026-10-03 — Diablo's precedent for a key-guardian: a role, not a rank

**Reference, verified 2026-10-03.** Rylee asked, for the guardian naming in #215, "how does Diablo
do it?" The precedent is Diablo III's **Keywarden**, and it is the same problem: a tougher monster
that carries the key you need to go deeper.

- There are **four Keywardens**, one per act. Each is a **Super Unique** — a *variant of a stock
  monster*, not a new creature. Xah'Rith the Keywarden is a Morlu Incinerator.
- The name shape is **role label + proper name + epithet**: "Xah'Rith, the Keywarden of Terror,
  Tormentor of the Damned."
- The key is a **named artefact** in the same pattern: the Key of Terror.
- The role word is **functional**, not a rank. It is not a court hierarchy.

**What this settles for #215.** Three things, and they all reduce the naming burden rather than
adding to it:

1. **It confirms her 2026-10-02 decision.** "Variants of the monsters we already have, named from
   their art and abilities" is exactly what a Super Unique is. The precedent and her instinct agree.
2. **The recurring label is one word, and it is a function, not canon.** "Keywarden" tells the
   player what the monster is for without inventing a person. That is a much smaller thing for her
   to approve than six invented names.
3. **The king's-court rank scheme is the wrong read of the precedent.** Seneschal / chamberlain /
   marshal names the monsters for their rank, which is the opposite of naming them for their art
   and abilities. Recorded so the next session does not re-derive it.

**Still hers:** the role word itself, and the proper name for each floor's guardian and its key.
The boss's name is already settled (the Cellar King), as is the seal, the treasure room and the
fact that the first lock is the floor 3 to floor 4 stair.

**Status.** RECORDED (2026-10-03). Owner: Rylee (the naming itself).

## 2026-10-03 — a hue used for text carries a contrast floor; a fill does not

**Decision (Rylee asked which fix was best for engineering, 2026-10-03).** #218's own body suggested "a darker accent". That is backwards: on a dark surface, darkening *lowers* contrast. The fix is one step up the ramp, and the palette already had it (`teal-400`).

**The real defect, and the decision that follows from it.** One token, `--teal`, was doing two jobs. It is the brand/AI-presence colour, tuned for dots, borders and fills, where WCAG asks nothing of it — and four small labels (12px, 13px, 10px) took their *text* colour from it. The 12px menu heading sat at 4.36:1 on a card where body text needs 4.5.

1. **Two jobs, two names.** `--color-teal-text` and `--color-teal-text-hi`, declared **per theme**, one step up the ramp from the brand step. Not a redefinition of `--teal`: that would fix today's four labels and leave the trap for the next person who writes a small teal label, silently, because nothing would be measuring. Every dot, border and fill keeps `--teal` exactly as it was.
2. **Declared per theme, and this was load-bearing.** Inheriting the warm value would have given `max-contrast` a teal text *dimmer* than its own accent, walking back the entire purpose of that theme. The new test caught this before it shipped — which is the argument for writing the test before trusting the fix.
3. **A hue used for text has a contrast floor (4.5:1); the same hue used for a fill does not.** The two only stay separate if they have two names. Recorded as rule 2 in `docs/guides/accessibility-contract.md`.
4. **The guard is a test, not prose.** `tests/test_teal_contrast.py` computes the WCAG ratio for all three themes plus the worst case (a 10px badge on a 15% teal wash, 5.19), asserts the hover is never dimmer than the resting colour, **fails if any stylesheet sets `color:` from a fill token** (the original bug), and fails if `--teal-light` reappears.
5. **A second bug in the same block, found by looking:** `--teal-light` was used once, on `.context__evidence-link:hover`, and defined nowhere in the repo. The declaration was invalid at computed-value time, so the hover silently fell back to the inherited colour instead of getting brighter. Fixed and pinned.

**Honest limit.** This was measured against the shipped default theme. #218 was originally measured against the Cottage skin (#211), which this session cannot see. A skin that overrides `--teal` or paints its own surfaces needs the same treatment; the test only reads this repo's stylesheets. **UNVERIFIED for the private pack.**

**Status.** ACCEPTED (2026-10-03). Owner: Rylee (the direction: "what's the best fix for engineering?").

## 2026-10-03 — a worker that stops is worth more than one that passes

**Lesson (2026-10-03, the #217 A2 engine packet).** The offload worker was given a frozen 18-test contract and stopped instead of making them pass, naming two pins as unreachable. **Both faults were mine, in the tests:**

- `statsNoHp` asserted `hp: 6` while its own comment *and* my brief said a missing base `hp` starts at 0. Only `2` was reachable.
- `equipSwap` tried to swap a `charm` item into a `body` slot, which the `wrong-slot` rule correctly refuses — and no two catalog items shared a slot, so the swap was **untestable as written**. A real hole in the contract.

It also reported that my brief's predicted test count was wrong (71, not 39) and that strict `xfail` makes the literal acceptance command meaningless. All three were true.

**Rule.** When a worker escalates a frozen test, check the test before the worker. This is the second time the recorded process caught a bad test rather than a bad builder (`docs/guides/gates-and-guardians.md`'s locks, and the #219 campaign). **The xfail contract is a spec, and a spec written in one sitting has holes — a worker that stops on a hole is doing its job, not failing it.**

Corollary: pin a swap against two items that genuinely share a slot, or the swap is not testable. And keep the brief's acceptance command honest — a predicted count that is wrong trains the reader to distrust the brief.

**Status.** ACCEPTED (2026-10-03). Owner: the integrator (recorded from the session).

## 2026-10-03 — equipment's pack fields, and one function for two readers

**Decision.** Equipment step 1 (`design/equipment.md`, #217 track A slice A1, [PR #244](https://github.com/Rylee-Bee/vefr/issues/244)) is the pack fields and the bake, nothing else. The rules below are the frozen contract from #239, which Rylee merged as written; they are recorded here because they are pack contract, not implementation detail.

**The contract.**
1. Five slots: `hand`, `body`, `head`, `feet`, `charm`. `mods` holds only `atk` and `hp`, each a whole number 0 to 9, bools refused.
2. A slotted item may still carry `value` and `keep` (worth gold, or usable and not consumable) but **not** `heal`, `light` or `use`. A worn thing is not drunk, lit or spent.
3. An item named by a door's `requires.item` **may not have a slot**. The rationale is in the rule itself: a key stays in the bag so it can open its door more than once, so a worn key would be a key that can no longer be a key. (This also answers the design's still-open question — story items stay unequippable, because the frozen contract says so.)
4. An item with no `slot` is unchanged. The whole slice is additive; the sample world still validates and bakes as it did.

**The engineering rule, and this is the part worth keeping.** The five slots and the two mods are written **once**, in `maplab.item_slot_and_mods`, and read by both consumers: `item_slot_errors` (the validator, one plain sentence per problem) and `cli._player_items` (the bake, which carries only what comes back). Neither reader re-implements the rule, so they cannot drift. This is the 2026-10-02 second-consumer rule — *extract shared machinery only when two actual consumers independently need the same operation* — applied at the smallest scope that has two. It was not extended further: the bake and the validator were not merged, and the loading path was not touched.

**A small hardening beyond the tests.** Door keys are collected from **every act**, not just the first, because the locked-door code only ever read act 1. A key declared in act 2 would otherwise have been wearable and therefore unusable as a key. This is the same finding the post-Act-2 hardening handoff records as item 3 (validation parity across acts), met in the one place this slice needed it.

**Status.** ACCEPTED (2026-10-03). Owner: Rylee (the contract); integrator (the shared-function shape).

## 2026-10-02 (night) — lessons: workflow quirks and dead ends

Recorded so the next session does not repeat them (also in the homelab-memory debug journal and `~/.agents/skills/offload/FOREMAN.md`).

**Process that worked**
1. **Tests first, merged first, strict xfail, one mark set per PR.** Each slice starts as a PR that only adds tests (`xfail(strict=True)`), so a test that passes by accident turns the build red. A test that needs a later PR's code gets that PR's mark, so each implementation PR flips exactly its own tests. Run them once with `--runxfail` and confirm each fails for the reason meant.
2. **A cheap builder, a careful reviewer.** One `offload agent -m code` worker per slice, no foreman, for a slice with clear tests; a foreman only for 3+ independent tasks. Every success needed a review fix (a circular import, loose type checks, a symlink-following copy, a traceback, test-only code in the player, an unguarded path CodeQL flagged). The builder never edits tests.
3. **Re-check the shipped packs read-only after any validator or loader change:** `vefr check` on the sample world and on the private Cottage pack, and a re-`normalize` of a copy that must leave every file byte-identical.
4. **Strictness changes need a decision.** Rejecting broken unused Blueprint families was a tightening, so Rylee decided it. Say when a change can make a pack that loads today fail.
5. **Describe, don't forbid, in image prompts.** See `.project/CURRENT.md` and Cottage `art/STYLE.md`.

**Quirks and dead ends**
- **Stale bytecode:** restoring an edited file within the same second (same mtime to the second, same size) left the old `.pyc` running. Use `PYTHONPYCACHEPREFIX=$(mktemp -d)` for checks after any temporary edit, or delete the cache.
- **Deleting a stacked PR's base branch closes the PR** and it cannot be reopened or retargeted. Merge the lower PR without `--delete-branch`, retarget the upper PR to `main`, then delete. Otherwise open a replacement PR.
- **`gh pr update-branch` does not exist in this `gh`:** `gh api -X PUT repos/OWNER/REPO/pulls/N/update-branch`. Branch protection needs every PR up to date, so every merge makes the others behind.
- **Unquoted heredocs run backticks** (`<<EOF` is command substitution). Quote the delimiter (`<<'EOF'`) whenever the body has backticks or `$`, and read the file back.
- **`git add -A` sweeps other sessions' files** in a shared checkout. Stage named paths and run `git status` first.
- **A foreman must not wait on a background monitor:** its run ends when it stops calling tools. Clones need `~/worktrees/node_modules` for jsdom tests.
- **Private journals are walled off:** the Worlds Journal refuses every agent principal by design; VEFR's `journal.py` is player gameplay data. Lessons go in docs, the debug journal and Hive Library candidates, never in a journal.

**Status.** ACCEPTED (2026-10-02). Owner: Rylee.

## 2026-10-02 — Blueprint stays local; the second-consumer rule

**Decision.** From the refined PR #231 plan (`docs/plans/language-architecture-sonnet-implementation-update.md`).

1. **Implemented:** family resolution is one private operation in `src/vefr/blueprint.py` (`_resolve_family`), and a validation error names the declaration that supplied the value (a family's or an ancestor's `defaults`, or the instance's `properties`). Every family is checked for an unknown parent or a cycle, used or not (Rylee: reject broken unused families). Format 1, the key sets, the lock shape and valid output are unchanged.
2. **Rule:** extract shared machinery only when two actual consumers independently need the same operation and invariants. Two helpers inside one module justify local consolidation only. A local bug fix needs no second consumer.
3. **Subtraction test for a new abstraction:** name the duplicated fact or missing invariant; show what it deletes or makes enforceable; count the concepts, configuration and migration it adds; prefer the smallest change that pays. A change that only shortens syntax, or only serves hypothetical consumers, is deferred.
4. **Working boundaries, checked against VEFR's seams:** *Definition* is the Blueprint's families and defaults plus the pack's `world.json` items (exists). *Generator* is `src/vefr/delve.py` (`generate_floor`; note `src/vefr/generator.py` is the storyteller model client, not this) (exists). *Runtime* is the engine and player under host authority (exists). *Recipe* has no artifact or seam today: it is a hypothesis. "Theme owns vocabulary; generator owns arrangement" stands.
5. **Deferred:** the kernel / dialect / pack horizon. Blueprint gives no evidence for it; it waits for a second real consumer.
6. **Cottage:** the flat-families layout (277 to 257 authored values, no abstract parent families) is a separate private PR for Rylee's review. A parent family earns its place only when it expresses a real shared fact.

**Status.** ACCEPTED (2026-10-02). Owner: Rylee.

## 2026-10-02 — locked doors, and the first lock

**Decision (Rylee, in chat, 2026-10-02).**

1. **The first lock is the stair from floor 3 to floor 4** (Cottage), not the way out at the bottom.
2. **The key is an actual key**, not something of the story's.
3. **The guardians are stat variants of existing monsters**, named from their art and abilities (names are
   proposed by an agent and approved by her; nothing is canon until she says).
4. **Locked doors are built** (`requires` on a transition, exactly one of `item` or `flag`; `locked_text`
   optional, default "It will not open yet."; keys are never consumed in this slice). A flag lock needs
   `saves.rules: persist` to survive a reload. See `design/gates-and-guardians.md`, "Slice 1 contract".
5. **Cottage opted in to `saves.rules: persist`** (`legacy: from-log`) and to a Blueprint for its creatures.

**Status.** ACCEPTED (2026-10-02). Owner: Rylee. The guardian ladder, depth tables and the Cottage lock
placement are the next build.

## 2026-10-02 — Blueprint format 1

**Decision.** Recorded in full in
[`docs/adr/0008-blueprint-format.md`](../docs/adr/0008-blueprint-format.md):

1. **The Blueprint is the edited truth.** A pack may carry
   `blueprint.json` at its root; it owns the regions it names.
   `vefr normalize` expands it into those regions' `enemies` lists. A
   pack without one is unchanged.
2. **Generated JSON is committed and read-only.** The expanded records
   and `blueprint.lock.json` are written by `vefr normalize`, committed
   beside the Blueprint, and never hand-edited. The lock records the
   source hash, the normalizer and format versions, and provenance.
3. **The exit threshold is 25% / one real error.** Continue only if
   authored enemy values drop by at least 25% on the first real pack,
   or one real error is caught; otherwise delete `blueprint.json` and
   `blueprint.lock.json`.
4. **Hand-written records stay supported.** Their end of life, if any,
   is set later by Rylee after the trial.

**Status.** ACCEPTED (2026-10-02). Owner: Rylee.

## 2026-10-02 — the Cottage day: decisions that outlive it

- **We ship only art we made, and attribute all of it** (Rylee). Kenney is for prototyping
  only and is removed from the sample world; LimeZu was bought to support the artist and is
  used only in a project she names. Art enters `web/art/` through `tools/art/import_art.py`,
  which writes `web/art/MANIFEST.json`; a picture with no credit fails `tests/test_art_manifest.py`.
- **Accessibility is measured on the rendered game, not read off declared colours.** The skin
  looked fine on paper and failed at 1.2:1 in the player. Any change to panels, buttons or
  text colour is checked by rendering a real pack at desktop and phone size and measuring text
  against the pixels behind it (and with axe).
- **`docs/features.json` is the one source of truth for what VEFR can do.** A built feature
  needs a guide and a test or the suite fails. `GET /api/features` (approved by Rylee) is read-only,
  takes only a bare world name, and no model runs behind it. The Containerfile ships the file.
- **Growth has two modes in the engine, a game picks one** (Rylee): classic levels or learning by
  doing. Growth only adds; nothing is ever taken away.
- **Rule saves are a per-pack `saves` block, default reset** (Rylee, 2026-10-02): `saves.rules` is
  `persist` or `reset`; `saves.legacy` is `fresh` or `from-log`. The validator and docs landed
  first; the player work follows. See [`docs/adr/0009-rule-saves.md`](docs/adr/0009-rule-saves.md).
- **Foremen work from acceptance tests written first, and a foreman that stops on a test is
  right until proven otherwise.** Three escalations today were bugs in the tests. Fix the test,
  never the foreman; review every diff by hand; state the foreman count and model before launching.
- **The gallery tool adopts every live project before it renders and refuses to publish if it
  cannot see them.** A machine that knew only one project once replaced the front page (nothing
  was lost on the server; only the index was overwritten).
- **Designed, not built:** a lock on a transition and a ladder of guardians ending at the act's
  boss, whose seal opens a treasure room with a lore note and a way back to town (Rylee); the album.

## 2026-09-30 — the day's design calls, recorded

**Decision.** So the next agent does not re-litigate them:

1. **Dependency updates: Renovate, not Dependabot.** `renovate.json`
   (weekly, grouped, 7-day cooldown, Action digest pins, lockfile
   maintenance); `.github/dependabot.yml` removed. Installing the Mend app is
   the owner's step.
2. **`sqlite-vec` is a default dependency.** The Lorekeeper's `ask` uses a
   vec0 KNN index (`index/lore.db`); `facts.jsonl` stays authoritative, and a
   brute-force cosine fallback keeps every fact safe if the extension fails.
3. **Structured output has an opt-in grammar fallback.** A caller may set
   `payload["grammar"] = True`; `schema_grammar.py` turns the same JSON Schema
   into GBNF and the request carries `grammar` *instead of* `response_format`.
   The default path is unchanged.
4. **Two optional, additive pack blocks landed:** `grammars` (deterministic
   sentence recipes for offline whispers, weather on arrival, and generated
   floor names) and item `light` (`{radius, turns}` or `{reveal: true}`). A
   pack with neither behaves byte-for-byte as before.
5. **UAT contracts live in this repo.** `docs/uat/` holds a journey plus
   machine-checkable acceptance triples, in the estate harness's format, so
   "what good means" is public and versioned with the player.
6. **The gate grew, and so did its documentation.** `dev-guards.yml` adds
   vulture, deptry, lychee (offline) and Vale (advisory); AGENTS.md now lists
   them and the deps list names sqlite-vec.

**Status.** ACCEPTED.

---

## 2026-09-30 — runtime state untracked; the last of the first game's name swept

**Decision.** Two carry-overs from the 2026-09-30 audit:

1. **Runtime state leaves the tree.** `data/interface.jsonl`,
   `data/storyteller.jsonl`, `data/lore/facts.jsonl`,
   `data/lore/index/{meta,vectors}.jsonl`, and `data/vault.json` were
   tracked although the repo's own runtime-state rule and `.gitignore`
   say they never should be (`data/vault.json` was not even ignored).
   They are removed from the index, not from disk, and `/data/vault.json`
   joins the ignore list. **They remain in git history** (added by
   `50a9fad`); rewriting that history is a separate, owner-gated decision.
2. **The first game's name is gone from tracked files.** The 2026-09-29
   sweep (#123) fixed the glossary, tests, and ROADMAP; a second pass
   neutralized the remaining mentions in `docs/guides/studio-lessons.md`,
   `docs/guides/studio-modules.md`, and `bench/design/briefs.py`.

**Status.** ACCEPTED.

---

## 2026-09-25 — owner rulings: munr kept, test packs deleted, old art accepted

**Decision.** Three open items closed by the owner:

1. **munr: keep, separate.** Supersedes D5 ("Retire munr"). munr stays
   its own active repo, related but not synced (entry below). It may
   later ride on vefr as a costume-ruleset pack (VEFR-GAME-PLAN §2).
2. **`worlds/rylee-alpha-world/`: a test artifact, deleted.** It was
   the WP5 `norns chat` acceptance run (2026-09-22). Owner ruling the
   same day: test artifact, not a world. Deleted from disk together
   with the local `worlds/kitchen-playtest/` (both gitignored, on no
   remote). Its generated voice file had repeated itself, which is
   evidence about `norns chat` voice drafting.
3. **Commit `948df78` (non-CC0 art, 2026-09-06): accepted risk.** No
   branch contains it; GitHub still serves it only by exact SHA. No
   support request or history rewrite.

**Status.** ACCEPTED.

---

## 2026-09-25 — munr is a related repo, not a synced one; D5 unreconciled

**Decision.** `Rylee-Bee/munr` shares this codebase's rewritten-history
origin (identical "v0.1 - rumor engine skeleton" first commits) but
evolves independently. Never merge, rebase, or cherry-pick between the
two without an explicit owner decision.

**Rationale.** AGENTS.md carried this note by name (`78fa0f8`), which
broke `test_no_historical_package_names` and turned `main` red. The
engine tree must not name the sibling; this file is outside the audited
roots, so the name lives here and AGENTS.md points here.

**Resolved 2026-10-04.** The owner clarified that Munr is an active game
built in VEFR, not a predecessor engine. The old shared engine lineage is
historical provenance only; D5 is superseded.

**Status.** ACCEPTED; D5 CLOSED/SUPERSEDED.

---

## 2026-09-13 — Olympus restart: Vulkan campaign, harness evidence fixes, legacy backend labeled UNKNOWN

**Decision.** Complete the Small Model Olympics v0.4.1 qualifier campaign
on the intended Vulkan backend: rerun the 5 partials + hermes-1.5b +
phi-4-mini + the 9 never-started with the fixed harness; keep the 13 legacy
"complete" runs preserved with their backend labeled UNKNOWN; never mix
CPU/GPU numbers for the same participant.

**Rationale.**
- The recovery report's "CPU-bound" claim was unreliable: rootless podman
  shows empty `HostConfig.Devices` despite `--device /dev/dri:/dev/dri`
  working, and this llama.cpp build prints no verifiable backend line at
  boot, so I cannot prove the legacy 13's backend retroactively. UNKNOWN is
  the honest label (evidence = OBSERVED/INFERRED/UNKNOWN split).
- Live reproduction proved three harness bugs, not model faults, caused the
  partials: Gemma3 template 400 on consecutive assistant turns (and any
  mid-session system); Qwen3.5 template 500 on any non-first system
  message; the harness dropped `reasoning_content`, distorting every
  thinking-family participant (qwen3.5-0.8b/-2b/-4b, hermes-1.5b,
  granite-4.2-3b).
- The resident llama-qwen-agent (27B, 41k ctx) holds the GPU (16360/16368
  MiB). **Stop nothing:** keep it running for production stability and for
  methodological parity with the legacy 13; record vram/busy as contention
  context on every new run via `backend_probe`.

**Evidence.**
- `bench/reports/DIAGNOSIS-2026-09-13-stuck-runs.md` (three root causes,
  reproduced against live servers, verified fixed).
- `records.probe_backend` now samples the render node inside the container,
  so the recorded `backend` is OBSERVED, not assumed.

**Status.** ACCEPTED.

---

## 2026-09-12 — promote Qwen2.5-1.5B to DEFAULT; demote Granite 4.1 3B to FALLBACK

**Decision.** Promote **Qwen2.5-1.5B-Instruct** to Hermod DEFAULT Brain. Demote **Granite 4.1 3B** to FALLBACK role (retained, not deleted).

**Rationale.**
- Round 5 bounded benchmark: Qwen2.5-1.5B and Granite 4.1 3B are behaviorally equivalent on the current six-task Hermod benchmark (same pass/fail pattern, zero observed variance across 5 repetitions each).
- Qwen2.5-1.5B is approximately 45% smaller (1.08 GB vs 1.95 GB) and ~46% lower latency under benchmark conditions.
- Both models consistently fail Rune Classification — a domain-knowledge gap, not a capability gap.

**Evidence.**
- Round 5: 5 models similar to Granite tested; Qwen2.5-1.5B, Qwen2.5-3B, and Falcon3-3B tied at 83%.
- Round 5.5: 5x repeatability on Qwen2.5-1.5B and Granite 4.1 3B — all runs identical, zero variance.
- Careful language: "Qwen2.5-1.5B and Granite 4.1 3B are behaviorally equivalent on the current six-task Hermod benchmark" — NOT "the models are interchangeable" or equal general capability.

**Reservation.** Six tasks do not establish general model equivalence. The Receipt proves only the bounded benchmark result.

**Status.** ACCEPTED.

---

## 2026-09-21 — Engine-as-game direction: C+A synthesis, bundled brain, model fleet

**Decision.** The engine's next phase is "game-building engine that is
itself a game." Fourteen owner decisions shape the direction:

1. **DD1: Design direction = C+A synthesis.** The creation experience
   IS the game. Workshop rooms (Foyer, Desk, Vault) become alive and
   responsive to what the builder has done.

2. **DD2: Theme = Workshop.** Already complete. Iterate via OpenDesign.

3. **DD3: Export feel = game-quality.** Woven HTML gets a title card
   (world name, tagline, "play" button) so it feels like a game
   within 3 seconds of opening.

4. **D3′: Brain bundled inside the container.** `podman run vefr` =
   fully playable game, no external LLM setup. CPU-only, least
   hardware possible.

5. **D4′: BJ pack license = CC-BY-4.0.**

6. **D5: Retire munr.** Archive the predecessor engine repo.

7. **D6: Fixture placement = A (BJ-pack-supplied).** Rosa/Mateo
   fixtures move into the BJ pack.

8. **D7: BJ canonical home = `code/Rylee-Bee/burrito-journalism`.**

9. **Model fleet locked:** Qwen3-0.6B, Qwen3-1.7B, SmolVLM2-500M,
   bge-m3. Total: ~2.8GB. All Apache-2.0 or compatible.

**Evidence.** Full inventory, product direction, competitive landscape,
model verification, live demo on :8825.

**Status.** ACCEPTED.

---

## 2026-09-12 — adopt Play-Nice as canonical behavioral authority; preserve engine kernels

**Decision.** Pin `play-nice-contracts @ 0cee0652fb6f13c440b1fd9cc5d78fd87cdca8ad`
as the canonical behavioral constitution for this project. AGENTS.md and
AGENT_POLICY.md remain as the local engine-specific kernels — they
describe VEFR's architecture, world-pack shape, and how to work in this
repo; they do not duplicate Play-Nice's behavioral floors.

**Rationale.** VEFR is its own architecture: bring-your-own-brain, worlds
as data, maplab as the validator. Its behavioral floors (honesty,
truthfulness, inspect-before-claim, deterministic-first) come from
Play-Nice. Its architectural rules (pack loader contract, brain-socket
seam, world-vs-engine split) stay local. The adoption makes the upstream
pointer explicit without rewriting the local kernels.

**Evidence.** Library SHA `0cee065`. `contractctl adopt` reports VALID.
The existing AGENTS.md/AGENT_POLICY.md already reference "canonical
contract/index documentation" without naming one; this adoption names
Play-Nice.

**Conflicts.** None. VEFR's local rules and Play-Nice are layered
(architectural vs behavioral), not opposed.

**Status.** ACCEPTED.

---

## 2026-09-12 — select Granite 4.1 3B as Hermod Default Brain

**Decision.** After 3 rounds of benchmarking (11 models, 8 tested, 3 finalists),
select **Granite 4.1 3B** as the Hermod Default Brain.

**Rationale.**
- Highest combined semantic accuracy (92%) and protocol compliance (97%)
- Perfect rune classification (100% across 3 runs)
- Strong Hermod/Steward task performance (3/4 tasks stable)
- Only ~0.8s slower than Qwen3.5-2B
- Only ~670 MB larger than Qwen3.5-2B
- Better fit for an EA whose job is to reduce correction burden

**Evidence.**
- Round 1: 6 models tested, Qwen3.5-2B led with 8/8
- Round 2: 8 models tested, Granite emerged as challenger with 87.5%/100%
- Round 3: 3 finalists, 3 repetitions each — Granite won on semantic + protocol

**Alternatives considered.**
- Qwen3.5-2B: Lighter (1.28 GB) but lower semantic accuracy (89%)
- Qwen3.5-4B: Same accuracy as Granite but larger (2.74 GB) and slower (12.9s)

**Conflicts.** None. The data supports this choice.

**Status.** ACCEPTED.

---

## 2026-09-12 — retain Qwen3.5-2B as lightweight fallback

**Decision.** Retain Qwen3.5-2B as LIGHTWEIGHT FALLBACK, not as default.

**Rationale.** Smaller footprint (1.28 GB) and faster inference (6.3s) make it
useful for degraded-resource mode or emergency fallback. Its 89% semantic
accuracy is adequate for routine work.

**Evidence.** Round 3 testing showed stable performance across 3 repetitions.

**Status.** ACCEPTED.

---

## 2026-09-12 — Qwen3.5-4B optional, not in normal routing

**Decision.** Qwen3.5-4B is available for experimentation but not in normal routing.

**Rationale.** At 2.74 GB and 12.9s latency, its perfect Hermod task performance
does not justify the resource cost compared to Granite (1.95 GB, 7.1s, 92%).

**Evidence.** Round 3 showed perfect Hermod scores but at 2x the size/latency.

**Status.** ACCEPTED.

---

## 2026-09-12 — do not promote benchmark success to authority

**Decision.** Granite's 92% semantic score does NOT grant it world-state authority,
policy authority, mutation authority, or final acceptance authority.

**Rationale.** Benchmark success is evidence of capability, not a grant of power.
VEFR's architecture requires: model proposes → VEFR validates → policy decides.

**Evidence.** Play-Nice onboarding contract, VEFR architectural principles.

**Status.** ACCEPTED.

---

## 2026-09-12 — verification remains mandatory

**Decision.** All Granite/Hermod outputs remain subject to verification,
especially escalation judgment (33% unstable) and rune classification.

**Rationale.** 92% accuracy means 8% error rate. For consequential decisions,
verification is the safety net.

**Evidence.** Round 3 variance analysis showed instability on ambiguous cases.

**Status.** ACCEPTED.
## 2026-10-03 (night): `complete-act` is a rule action (Cottage release 1)

Approved with the act-2 plan (CURRENT, 2026-10-02) and recorded here now. `{"complete-act": "<act id>"}` names an act the pack declares; the player opens one end card on the overlay surface ("Keep exploring", "Start over"), once per save under `saves.rules: persist`. It records that a story beat is finished and does **not** advance acts (ADR 0006 is still unbuilt). Chosen over a new `ending` field or an `act-completes` event: the rule vocabulary already says when, so the one new thing is the action. Tests: `tests/test_complete_act.py`.

## 2026-10-04: lessons from the Cottage release-1 night

- **A bot that plays the pack finds what validators cannot.** The keyboard-only playthrough found a King that a level-8 hero could not beat (40 hp / 4 atk), guardians that woke and were killed before the lock could be tried, a wall tile that rendered as flat blocks (the 2x2 grid form; the 1x1 form works), and stairs labelled "down" on the way up. Run it before calling a pack done.
- **Foremen need their diffs read.** The lock check and the album passed their acceptance and needed no change; the playthrough-bot worker's own run passed but failed on the current pack until the bot learned to grind and to relax an over-strict check. "Worker says done" is a claim.
- **A tool-denied merge is not a reason to stop.** The classifier denied `gh pr merge` until Rylee said so in chat; branch-pinned CI let everything else proceed. Pin a pack's CI to a branch commit, then move it to main after the merge.
- **Codex beat MiniMax for item icons** in Rylee's storybook style and for consistency with the cast; MiniMax is fine for quick drafts (kept as alternates).
- **`gh pr update-branch` does not exist in this gh;** merge main into the branch yourself.
- **Never `rm` with shell variables;** the safety check refuses it. Use `git rm` with literal paths.

## 2026-10-04: Release 1 scope, and decisions the run made durable

- **Acts 2 and 3 were deferred by Rylee, deliberately.** Release 1 is a complete polished Act 1 that keeps the larger three-act direction. Do not read the absence of Acts 2 and 3 as an engine failure or an abandoned plan. Act advance (ADR 0006) and status effects (fire first) are the next engine capabilities because the future acts want them. Plan: `cottage-of-the-breeze/docs/plans/acts-2-3/PLAN.md`.
- **Order of work chosen by Rylee (2026-10-04):** refactor `web/packaged.html` into blocks before act advance and status effects (`docs/plans/player-split/PLAN.md`); build the in-world interface direction (`cottage-of-the-breeze/docs/plans/native-ui/PLAN.md`) with the frame work first. Her interface rule: everything inside the game is in the game's themed UI, no literal device frame, native to the world, "cute, minimal, warm".
- **Sound is opt-in per pack and on by default where a pack opts in.** Every cue already has its text in the live line, so silence is fully playable. This was an agent choice; the README's "nothing makes a sound unless you turn it on" describes the studio's Boiler Room settings. **Decided by Rylee (2026-10-04): on by default, with the visible switch.**
- **Story text is either an agent draft or approved by Rylee, and the pack should be able to say which** (finding 1 of `docs/research/cottage-release-1-learnings.md`). Until it can, drafts are flagged in the game's `NOTES.md`.
- **The discovery record is the source for the roadmap board.** Findings are classed engine / authoring / QA / player and ranked now / next / later; nothing in it is built.
- **Lessons from the night's workflow (also above):** the playthrough bot, not the validator, found the unwinnable King, the flat wall tile and the "down" stairs label; read every worker diff; parallel foremen collide on `docs/features.json` and `web/packaged.html`.

## 2026-10-04: journal — Cottage Release 1, the night VEFR was asked to finish a game

*(Engine and process history only. What happened to the hero, the town and the story is Cottage's own history: its `NOTES.md` and the in-game Chronicle. The two stay apart.)*

**What Cottage asked VEFR to learn.** An ending for a story beat; proof that a locked door can always be opened; a shelf of collectables; a few sounds; a character that walks. Each was reusable, so each went into VEFR first (tests written first, built by foremen or by hand, reviewed, merged): `complete-act` (#252), lock reachability in `vefr check` (#253), the album (#254), sound (#257), walk sheets (#258), plus a one-word fix (#255). Equipment, locks and the Blueprint were already there and were used for real.

**What surprised us.**
- The validator passed everything and the game was still unwinnable: the first King was too strong for a level-8 hero. Only a bot playing by keyboard found it. Guardians that woke up and followed the hero were killed before the lock could be tried.
- A wall picture made the same way as the floor rendered as flat grey blocks; it needed a different file form. Found by looking at a screenshot, not by any check.
- Every stair in the game said "Go down the stairs", including the way back up.
- The feature catalog (`vefr features --pack`) could not see five features Cottage used, and still listed finished features as partial.
- Rylee's complaint about the interface (HUD icons floating on the page) was not what the overflow measurement checked; the check measured the window, not the stage.

**What failed or needed correction.** A foreman's passing run failed on the current pack until the bot learned to grind and one check was relaxed; a change I made to hints (friendly names) failed the validator and was reverted within minutes; one art-source commit went straight to Cottage `main` instead of through a PR; Opus's plan mis-identified some art and the stakes mechanic, and was corrected by reading the code.

**What the playthrough exposed.** Balance, pacing, the wall tile, the stair label, reduced-motion settling of the walk frame, and that everything Cottage promises (gear, stickers) hangs on single enemy ids. See findings 3, 4, 7 and 8 in `docs/research/cottage-release-1-learnings.md`.

**The ten findings** (seven new, three deepened; ranked in the record): story draft/approved status; scenarios (start in any state); stage containment and panel accessibility checks; obtainability beyond keys; honest feature detection; a pack art-import verb with clean credits; a route and state API; a balance report; an overlay lane for hand edits to generated output; development questions VEFR can answer. The roadmap board puts the first four in NOW.

**Workflow lessons from the autonomous mission** (also in the 2026-10-04 lessons above): tests first and frozen, `--runxfail` acceptance, read every diff, merge main into a branch yourself, never `rm` with a shell variable, ask the owner in chat before a merge the classifier blocks, and keep two foremen from editing `docs/features.json` and `web/packaged.html` at once.

## 2026-10-04: a size-and-language pass was asked for

Rylee asked for a full optimization pass: smaller but more flexible, using language differently without costing human or agent readability. The measured result is `docs/research/size-and-language-pass.md`: 85% of the woven Cottage file is base64 pictures (about half is recoverable by baking WebP and storing identical pictures once), the pack's text is only 58 KB (the flexibility win is conventions and sentence forms that normalise to the canonical JSON, the Blueprint pattern), and the engine repeats its rule vocabulary in three files (one declarative vocabulary would end the lockstep). Nothing built; the order is in the document.

## 2026-10-04: the player is built from parts

`web/packaged.html` is now generated from `web/player/parts/` (56 files, order in `web/player/manifest.json`) by `scripts/build_player.py`; the generated file stays committed so every consumer, the wheel and the weaver are untouched. Chosen by Rylee ("split the packaged html ... in parallel" with the interface work). The proof of no behaviour change is byte-identical weave digests (`scripts/weave_digest.py`) plus `tests/test_player_build.py`. **Rule for agents and foremen: edit a part, run the build, commit both; never edit `web/packaged.html` by hand.** Parallel foremen can now work in different parts without colliding.

## 2026-10-04 (later): Rylee's decisions on the interface and the tightening work

- **Interface look:** parchment and soft wood, Ledger type (Crimson Pro), no literal device frame, everything on one stage; chosen in the interface lab after fifteen researched styles. Plan: `docs/plans/interface/PLAN.md`.
- **ADR 0010 (things and places):** glyphs are written into `map.md` (no weave-time overlay); places come before things; placement sentences are built in this mission, kept to six words (`far:`, `near:`, `off:`, `dead-end`, `room:`, `x,y`) with ties broken by a hash of the record id.
- **Order and limits:** one foreman at a time per lane (the interface lane and the tighten lane may run together); at most one extra research worker; every slice tests-first, with the weave digest or the golden file as its proof of no change.
- **Plan builder:** Opus wrote `docs/plans/tighten-shapes/PLAN.md` (the second of the two Opus calls allowed overnight, then re-approved by Rylee for this mission). Its corrections to the earlier estimates stand: `store()` saves 40 to 80 lines (its value is the lint), the schema table 150 to 250, and existing validator tests do not pin exact sentences, so a golden file comes first.

## 2026-10-04 (late afternoon): the endless dungeon's open questions answered; what the slices taught

**Rylee's decisions** (asked one at a time as pickers; recorded in ADRs 0013 to 0015, #293):
- **Wake rule:** sight plus noise. Loud events: fighting (12 tiles), opening doors and chests (6), breaking things and using stairs (8). Reloading puts sleepers back to sleep; no awake state is saved.
- **Key warden:** awake, and hunts the hero once the hero enters its hall.
- **Affixes:** cozy and cute names supplied by the pack; the engine ships neutral ids.
- **Stamps:** six to start: a 21x21 throne room (not 15x15), a random elite room, a room of 3 to 6 chests where one is quite likely a monster, a shrine, a treasure nook and a sleeping den. Only decorative stamps rotate or mirror. Required stamps always place; optional ones may be rare on purpose.
- **Town gate:** the paid shortcut that skips the town visit is a one-use item, one dropped by every section's vault, offered from the second cycle on. The final boss lives in its own region behind its door.
- **Order:** things follow places (B1 after B2); the endless slices go E7, then E5, then E8.

**What the slices taught** (each one is now a rule or a check, not just a note):
- **A foreman that runs out of time leaves real work scattered across its workers' clones.** B2 timed out at 100 minutes with no commit, yet its tests, docs and two implementation attempts sat in four clones; assembling them gave a passing slice (88 tests). The platform's worker contract now requires workers to commit as they go, and timeouts are sized to the slice.
- **The public-surface guard caught a machine path in a new test** (a hard-coded path to the game's pack). Trials against a real game pack are opt-in through `VEFR_TRIAL_PACK`, so no private path lives in this public repo.
- **A second-model review can read a stale branch.** The B2 reviewer flagged doc examples that a later commit had already fixed; check a finding against the current head before acting on it.
- **Draft ADRs go through the public-surface lens too:** an Opus draft named a game character; the engine ADR now says "the final boss".

## 2026-10-04 (evening): the worker machine lost its home folder; what changed

**What happened.** About 4 PM a process running as the owner's own account on the machine that hosts the AI workers deleted nearly everything in that account's home folder: checkouts, worker clones, service data and the keys kept there. The only survivors were files that account was not allowed to delete. The cause is not proven; several agents were running at the time and their logs went with the folder. Nothing on GitHub was lost, and no VEFR code was lost beyond two in-flight slices (E7, and the first slice of the worker sandbox), which were re-run the same evening.

**What changed, and why it is a VEFR lesson** (building Cottage is how VEFR gets built, and the tooling is part of that):
- **A container that shares the home folder is not isolation.** Workers now run as a separate account that cannot read the owner's files, inside a toolbox container, behind hourly read-only snapshots of every home folder. Until the per-worker sandbox lands, no high-value secret lives in the worker account.
- **Nothing important lives only on the worker machine.** Services and their data moved to the always-on servers, with nightly copies to network storage.
- **Commit every passing step.** Foreman plans now say so, after a timeout earlier the same day left a finished slice scattered across four uncommitted clones.
- **One harness.** Every worker tier now runs through Claude Code with the provider swapped in (cheaper models keep their reasoning across tool calls there); opencode remains a fallback.
- **The rule for slices that touch frozen tests still holds:** B1 stopped and asked before changing the four artifacts that said "format 2 does not exist", and the owner said yes.

## 2026-10-16: the generated player is built, never committed (vefr#523)

This reverses the "stays committed" half of the 2026-10-04 player-split decision above, on Rylee's
measurement: `web/packaged.html` was one generated 755 KB file that 43 of the last 74 commits touched,
so any two PRs editing player code collided on it and each had to merge `main`, rebuild and re-measure
before it could land. That, not the three-open-PR cap, was the estate's biggest blocker. The parts and
`web/player/manifest.json` are the only source.

- The join moved from `scripts/build_player.py` into `vefr.player_build`, so the weaver, the tests and
  the wheel all use one build; `scripts/build_player.py` is the command line over it.
- Built where it is read: `cli._template_candidates()` builds it in a source checkout, `tests/conftest.py`
  builds it once per session (and at conftest import, for tests that read the file as their module is
  imported), and `hatch_build.py` builds it before packaging, so the wheel still force-includes
  `vefr/web/packaged.html` for `pip install vefr @ git+...`.
- `scripts/build_player.py --check` changed meaning: it asks whether the parts build cleanly (every listed
  part exists, none orphaned, none listed twice), not whether a committed file is stale.
- The woven bytes did not change; `scripts/weave_digest.py` prints the same digests.
- **Rule for agents and foremen: edit a part, never `web/packaged.html`, and never commit it.**
  Rylee's order: this first, then raise the VEFR open-PR cap to 5.

## 2026-10-17: the player digest is measured at the merge base, not pinned (vefr#529)

Option 1 of the three in vefr#529, chosen by Claude under Rylee's 2026-10-17 overnight approval to
cut the estate's noise: keep the byte-for-byte guard for refactors only. The second half of vefr#523's problem survived it. `web/packaged.html` stopped
being committed, so player PRs no longer collide on 755 KB - and still collided on one line,
`NO_SKIN_WEAVE_SHA256` in `tests/test_skin_validator.py` (and on `SAMPLE_DATA_SHA` /
`ROLLED_DATA_SHA` in `tests/test_identify.py`). On 2026-10-16 three player PRs each re-pinned
it, and each merge forced the next one to merge `main`, re-measure twice and re-push before CI
could start.

- **The guard is the branch's claim, and the claim is a label.** A PR labelled `refactor` must
  reproduce the digests `git merge-base HEAD origin/main` prints; CI passes the label down as
  `VEFR_REFACTOR=1` and nothing else changes. The base is woven in a temp worktree at that merge
  base (`tests/weave_digest.py`), over this branch's fixture packs, with the base's own engine -
  so the comparison is main against the branch and nothing is written into either tree.
- **Nothing is committed for it.** That is the whole point: a pinned digest is a merge conflict
  on a line that measures a stack's own reading and does not compose.
- **Every other branch keeps what it can.** The weave is deterministic (twice, equal) and the
  digest is a well-formed sha256; the visual-regression job over the woven sample is untouched.
- **Skipped, never passed quietly.** With no `origin/main` - a plain local clone - the merge-base
  path skips with that reason.
- **Rule for agents and foremen: no PR refreshes a digest constant, because there are none left.**
  A player PR that is a genuine refactor labels itself `refactor` and must weave the same bytes;
  everything else changes bytes on purpose and says nothing about them.
- Measured at the merge base, the three retired constants come back byte for byte
  (`d42518a1…`, `1c2bef0a…`, `517fadef…`), which is the evidence that what is measured now is
  what was measured then.
