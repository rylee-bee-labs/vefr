# Plan 2 · Durable rule saves

> Status: authorized (2026-11-02) · Owner: Rylee · Planner: Opus 5.5 · Date: 2026-10-02
> Authorized on 2026-11-02: Rylee approved all four recommendations (Project Home decision 391). The gate below is satisfied for this plan.
> Inputs: `docs/research/language-architecture/08` (save-state), `11` (decision 4), `13`, and live code at VEFR `main` `45f5767`.
> Independent of [Plan 1, Blueprint family normalization](blueprint-family-normalization-plan.md). It touches no Blueprint code and needs none.

**Gate.** Nothing here starts until Rylee has read the disposition (`11` item 6) and says go.

## Decided by Rylee (2026-10-02) — these override anything below

| Item | Decision |
|---|---|
| D4 field | A nested **`saves` block**, not a flat `rule_saves`. Shape: `"saves": {"rules": "persist" \| "reset", "legacy": "fresh" \| "from-log"}`. Absent block, or absent `rules`, means reset. Read every `rule_saves` below as `saves.rules`; rename the validator function and tests to match. Future save settings go in the same block. |
| D5 what persists | **All rule state**: flags, `once` markers, beliefs and the engine's items. |
| D6 `starts` | In persist mode it fires **once per save**, not once per load. Start over fires it again. |
| D7 old saves | **Per-pack choice** via `saves.legacy`. `fresh` (the default): no migration, a `once` rule may repeat one time. `from-log`: rules the WHY log proves fired are marked fired; the log is capped at 20 entries, so older firings may still repeat once. It never marks a rule fired that did not fire. |

Added acceptance tests (write first, with S1–S13): **S14** `saves.legacy` accepts `fresh` and `from-log` and rejects anything else with one plain sentence naming `saves.legacy`; **S15** `from-log` marks exactly the rule ids present in the WHY log and nothing else; **S16** `fresh` marks nothing; **S17** `starts` fires once per save in persist mode and again after Start over. `legacy` has no effect in reset mode (validator may warn).

## Execution method (Rylee, 2026-10-02) — overrides any "Sonnet Foreman" wording below

Offloadable tasks run as an **offload foreman controlling offload workers**: `offload foreman -m foreman` (MiniMax M3.1 on the claude engine) launches `offload agent` workers on the `code` tier (`deepseek-flash`), under `--budget` and `--minutes`, on Bazzite. The foreman has no Edit or Write tools, so code comes only from workers. Sonnet is the integrator: it writes the keep tasks (ADR, frozen tests, security review, Cottage work), commits everything the workers need *before* launch (they see tracked files at HEAD), supplies each task's exact `--accept` command, then reviews and applies the foreman's result per `skills/offload/FOREMAN.md`. Nothing a foreman produces is merged without that review. Never use `alibaba:qwen3.8-max` as foreman. No Opus fan-out.

## 1 · What the player holds today (reverified 2026-10-02)

| Fact | Evidence |
|---|---|
| Rules run only in the woven player; no other runtime has the engine | `grep VEFR_RULES_ENGINE web src` → `web/packaged.html` only |
| `fireRule` is the one seam: builds state lazily, runs, records why, performs actions | `web/packaged.html:2100-2111` |
| `RULES_STATE` is built from the bake by `engine.newState` on the first rule run, then `where` is filled from the baked speakers | `packaged.html:2118-2135` |
| `newState` returns `{flags, beliefs, fired, items, where, rules, meanings}` | `packaged.html:3138-3176` |
| Mutable play state the engine writes: `flags` (`set`/`unset`), `beliefs` (`believes`/`stops-believing`/`tells`, as `{value, source}`), `items` (`give`/`takes`, and every `picks-up` event), `fired` (rule id → `true`) | `packaged.html:3345-3366`, `:3468-3483` |
| Rebuilt from the bake every load, never play state: `rules`, `meanings`, `where` (people do not move) | `packaged.html:2124-2132`, `:3168-3175` |
| All four mutable parts are plain JSON (booleans, strings, nested objects); nothing holds functions, dates or cycles | same lines |
| Only the WHY log persists: `vefr-rules-<world>`, the last 20 `{id, why}` | `packaged.html:2191-2212` |
| So after a reload: a fired `once` rule can fire again, a set flag reads off, a told belief is gone, and `has` reads empty | consequence of the above; reproduced by probe B (`10`, private) |
| `starts` fires on every Begin, i.e. every page load | `packaged.html:5510-5513` |
| A rule may `set` only a declared flag; conditions name only declared flags; `tells`/`believes` name declared people (= speakers) | `src/vefr/maplab.py:608`, `:665`, `:472` |
| Start over removes every `vefr-` key, then reloads | `packaged.html:1420-1421`, `startoverKeys` at `:1670-1690` |
| Growth persistence, the pattern to copy: per-world key `vefr-growth-<world>`, every access wrapped in `try`, malformed data coerced to a fresh state, derived values never stored | `packaged.html:1454-1474` |
| The weave folds every `world.json` key into `VEFR_WORLD` | `src/vefr/cli.py:1624-1627`, `:1857` |
| Acts-shape `load_pack` carries optional keys to the validator only when declared (`growth`, `skin`, the rule catalogs) | `maplab.py:162-180` |

Not found: the brief says `rulesets.md` "now says rule state resets". It does not. `docs/guides/rulesets.md:281` is about wounded enemies.
The sentence that is false across reloads today is `docs/guides/rules.md:76` ("One rule fires at most once").

A pre-existing gap noticed, **not** fixed here: the engine's `items` is not kept in step with the bag (consumption and shop trades change the bag but not `state.items`; `packaged.html:3349-3366` only handles `give`/`takes`, `:3469-3471` only `picks-up`). This plan persists the engine's own record faithfully; it does not reconcile it with the bag.

## 2 · The decision

Decided by Rylee (`11` item 4): a **per-pack setting**, default **reset** so every existing pack plays as it does today; the engine supports both; Cottage opts in to **persist**.

Both modes, specified:

- **reset** (default, and when the field is absent): exactly today. No new storage key is read or written. Documented as intended in `rules.md`.
- **persist**: the four mutable parts survive a reload and are cleared by Start over.

Recommendation for Cottage, as decided: persist.

### Pack field

```json
{ "rule_saves": "persist" }
```

A top-level `world.json` string, one of `"persist"` or `"reset"`; absent means `"reset"`.

Why this shape, against the pack's own conventions:

- It mirrors `surface`: a top-level string enum with a back-compat default when absent (`src/vefr/world.py:77-82`, `:217`, `:597-606`). That is the convention for "pick one behavior".
- `growth` uses `{ "mode": ..., "<mode>": {...} }` because each mode carries its own block (`maplab.py:786-816`). Rule saves carry no block, so an object would be ceremony.
- It cannot live inside `rules`: `rules` is a list.
- The underscore spelling matches existing keys (`bond_draw`, `forge_texture`).
- It rides into the player through `VEFR_WORLD` with no new template placeholder, as `surface` does.

### Storage

Key: `vefr-rulestate-<world>` (same `<world>` as the WHY log, `VEFR_WORLD.name`).
It sits beside `vefr-rules-<world>` but cannot collide with it for any world name: the prefixes differ at their 11th character (`-` versus `t`).
The WHY log key and its shape stay exactly as they are.

Value:

```json
{ "v": 1,
  "flags":   { "<flag>": true },
  "fired":   { "<rule-id>": true },
  "beliefs": { "<person>": { "<claim>": { "value": true, "source": "told by <person>" } } },
  "items":   { "<item>": true } }
```

Why four parts, not only flags and `fired`: all four are written by the engine during play. Saving two would leave `believes` and `has` conditions resetting, the same bug in a smaller place. The test is simple to state: after a reload, the engine state equals the state before it, except for the parts rebuilt from the bake.

Load (persist mode only, inside `rulesStateNow`, after `newState` and the `where` fill):

- read, parse, check `v === 1`; anything else unreadable → keep the fresh state;
- a `v` greater than 1 → keep the fresh state **and do not write** this session, so a save from a newer woven file is not destroyed by an older one;
- overlay with recovery, dropping anything the current bake does not know: flags not in `VEFR_FLAGS`, rule ids not in `VEFR_RULES`, belief holders not in `VEFR_PEOPLE` or the baked speakers, claims not in `VEFR_CLAIMS`, items not in the baked items; non-boolean flag values and malformed belief entries are dropped. Never throw.

Save (persist mode only): after every `engine.run` in `fireRule` (a `picks-up` changes `items` even when no rule fires), write the four parts, wrapped in `try`. A failed write is silent; play continues in memory.

## 3 · Acceptance tests (written first, frozen)

New harness `tests/fixtures/rules_save_harness.mjs`, in the style of `rules_play_harness.mjs`, with the reload pattern of `pool_harness.mjs` (a second sandbox over the same store). Pack fixture: extend `tests/fixtures/make_rules_pack.py` with a `--rule-saves` option. New test file `tests/test_rules_saves.py`. Tests land first as `xfail(strict=True)`.

| # | Asserts |
|---|---|
| S1 persist | a `once` rule fired before reload does not fire after it; the WHY log is not appended twice |
| S2 persist | a set flag is still set after reload, so a rule gated on it fires on the next matching event |
| S3 persist | a `once: false` rule still fires again after reload |
| S4 persist | beliefs from `tells` and items from `picks-up`/`give` survive reload; after reload the state's four parts deep-equal the pre-reload parts |
| S5 reset, and field absent | after reload the `once` rule fires again (today's behavior pinned), and no `vefr-rulestate-` key is ever written |
| S6 changed pack | save under pack A, reweave as pack B with one rule, one flag, one claim and one item removed and one rule added: loads without error, removed ids are gone from state, the new rule can fire, kept ids keep their values |
| S7 bad data | stored value not JSON, `v: 0`, wrong types → fresh state, no error; `v: 2` → fresh state and the stored value is unchanged after play |
| S8 storage unavailable | `localStorage` getter throws, and separately `setItem` throws: the game begins, rules fire in memory, no uncaught error |
| S9 Start over | `startoverKeys` removes `vefr-rulestate-<world>` (add to `tests/test_startover.py`) |
| S10 per world | two worlds in one store keep separate state |
| S11 validator | `"persist"` and `"reset"` pass; `"always"`, `1`, `{}` fail with one plain sentence naming `rule_saves`; absent → no output (in `tests/test_rules_validator.py`) |
| S12 bake | `VEFR_WORLD.rule_saves` is present only when declared (in `tests/test_rules_bake.py`) |
| S13 docs | `rules.md` names `rule_saves`, both values and the default; glossary has the word (in the style of `tests/test_growth_docs.py`) |

Unchanged and must stay green: `tests/test_rules_engine.py`, `tests/test_rules_play.py`, `tests/test_rules_bake.py`, `tests/test_startover.py`, the browser suite.

Gate: `uv run --group test ruff check src tests scripts`, `uv run --group test pytest -q`, `uv run --group test norns validate --pack worlds/sample-world`, `python3 scripts/check_public_surface.py`; on the PR, `VEFR_BROWSER_REQUIRED=1 uv run pytest -q tests/browser`.

## 4 · Tasks

| # | Task | Mark | Foreman / model |
|---|---|---|---|
| R1 | ADR `docs/adr/0009-rule-saves.md`: the decision, field, key, value, recovery and version rules above | keep | none, Sonnet integrator |
| R2 | Write S1–S13, harness and fixture option, xfail strict | keep (frozen contract) | none, Sonnet integrator |
| R3 | Validator: `rule_saves_errors(w)` beside `growth_errors`, called from `validate`; carry `rule_saves` through acts-shape `load_pack` only when declared | offloadable (S11) | 1 offload foreman + `code` workers |
| R4 | Player: load and save in `packaged.html` around `rulesStateNow` and `fireRule`, outside the `-- rules start/end --` engine block, so the pure engine is unchanged | offloadable (S1–S10, S12) | same Foreman |
| R5 | Docs: `docs/guides/rules.md` (a "Saves" section; fix line 76's claim for reset mode), `design/rules-when-then.md`, `src/vefr/world.py` docstring (pack contract), `docs/guides/glossary.md`, `ROADMAP.md`, `.project/DECISIONS.md` | offloadable (S13) | same Foreman |
| R6 | Review: no new storage access outside `try`; reset path provably untouched (diff review plus S5) | keep | none, Sonnet integrator |
| R7 | Cottage: add `"rule_saves": "persist"` to `world.json`; bump `VEFR_REF` to a `main` that contains R3–R5; validate; play-check a reload in the woven build | keep (private pack, owner merges) | none, Sonnet integrator; Rylee reviews |

**Launch budget:** 1 offload foreman + `code` workers, via `offload foreman`, for R3–R5 as one bounded brief. If Plan 1 runs at the same time, 2 Foremen total. No Opus fan-out.

## 5 · PR sequence

| PR | Repo / branch | Contents | Files (verified to exist unless marked new) | Depends on |
|---|---|---|---|---|
| 1 | VEFR `feat/rule-saves-contract` | R1, R2 | new `docs/adr/0009-rule-saves.md`, new `tests/test_rules_saves.py`, new `tests/fixtures/rules_save_harness.mjs`, `tests/fixtures/make_rules_pack.py`, `tests/test_startover.py`, `tests/test_rules_validator.py`, `tests/test_rules_bake.py` | gate |
| 2 | VEFR `feat/rule-saves` | R3–R6; flips every xfail | `src/vefr/maplab.py`, `web/packaged.html`, `docs/guides/rules.md`, `design/rules-when-then.md`, `src/vefr/world.py`, `docs/guides/glossary.md`, `ROADMAP.md`, `.project/DECISIONS.md` | 1 |
| 3 | Cottage `feat/rule-saves-persist` | R7 | `worlds/cottage-of-the-breeze/world.json`, `.github/workflows/validate-pack.yml` | 2 merged |

Files prohibited for the Foreman: the engine block between `-- rules start --` and `-- rules end --` in `packaged.html`, `src/vefr/cli.py`, anything Blueprint, `.github/workflows/`, `scripts/`, `uv.lock`, any `worlds/` pack, the Cottage repo.

If Plan 1 lands first, Cottage PR 3 moves the pin past both; if not, it does not wait for Plan 1.

## 6 · Compatibility

| Case | Result |
|---|---|
| Every pack today (no `rule_saves`) | reset: byte-identical behavior; no new key read or written (S5) |
| Old woven files already shared | unchanged; they never had the code |
| A persist pack, player with a save from before opting in | no state key yet → fresh rule state on first load. A `once` rule that fired before may fire **one more time**. No migration: rebuilding `fired` from the WHY log without the matching flags could lock a flag-gated rule forever, which is worse than one repeat. Stated in `rules.md` |
| A persist pack that changes later (rule renamed, flag removed) | unknown ids dropped (S6); a renamed `once` rule counts as new and may fire again. Stated in `rules.md` |
| A pack switching persist → reset | the stored key is ignored, not deleted; Start over removes it |
| Older pinned validators reading a pack that declares the field | pass: `world.json` top-level keys are not closed today. **UNVERIFIED** against Cottage's current pin `160602e`; R7 bumps the pin anyway |

## 7 · Durability (campaign plan items that apply)

| Item | Here |
|---|---|
| 1 Conformance | S1–S13 run in the normal `pytest` gate |
| 2 Versioning | the save carries `v`; newer versions are left alone; the ADR states how `v` changes |
| 3 Single source | the two values are one constant in `maplab.py`; the docs test checks `rules.md` names them |
| 5 Owner | Rylee; changes through an amendment to ADR 0009 |
| 6 Teachability | `rules.md` "Saves": one paragraph, what persists, what Start over does, the two caveats |
| 7 Dogfooding | Cottage opts in and validates in CI |
| 8 Graceful degradation | default reset; storage failures degrade to in-memory play |
| 9 Exit ramp | below |

## 8 · Rollback and exit ramp

- Revert VEFR PR 2: the player stops reading and writing the key; stored values sit unused and Start over removes them. The validator then ignores `rule_saves`, so packs that declare it still load.
- Revert Cottage PR 3: the pack plays in reset mode again.
- Stop and revert if S5 cannot be kept green (reset mode would no longer be today's behavior), or if persisted state causes any crash in the browser suite.

## 9 · Risks

| Risk | Response |
|---|---|
| In persist mode, `starts` means "the first Begin of this save", not "every load" | intended reading of `once`; named in `rules.md`; Rylee confirms (D6) |
| A save blocks progress after a pack edit (a flag stays set that a new rule needs off) | recovery keeps only known ids; Start over is the documented reset; noted in `rules.md` |
| Two tabs of one world overwrite each other | last writer wins, as every other `vefr-` key does today |
| `items` diverges from the bag | pre-existing, unchanged in either mode; listed as a follow-up, not fixed here |
| A thrown storage call takes the game down | every access in `try`; S8 |

## 10 · Decisions for Rylee

D4–D7 are decided; see the table near the top. Nothing is open for this plan.

## 11 · Out of scope

Plan 1 and anything Blueprint, changing the engine block or rule semantics, the WHY log's key or shape, saving `where`, reconciling `items` with the bag, cross-device or server-side saves, export/import of saves, save slots, event sourcing or replay, guardians, gates and the album.
