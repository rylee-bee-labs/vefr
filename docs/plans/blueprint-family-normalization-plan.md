# Plan 1 · Blueprint family normalization

> Status: held, not authorized (2026-11-02) · Owner: Rylee · Planner: Opus 5.5 · Date: 2026-10-02
> Held on 2026-11-02: normalization waits until the end-of-life date for hand-written Blueprint records is set. Rylee approved all four recommendations (Project Home decision 391).
> Inputs: `docs/research/language-architecture/` (00–13, SOURCES), `language-architecture-campaign.md`, `language-architecture-proof-pass.md`, the two private Cottage companions, and live code at VEFR `main` `45f5767`.
> Independent of [Plan 2, durable rule saves](durable-rule-saves-plan.md). Neither blocks the other.

**Gate.** Nothing here starts until Rylee has read the GO WITH CONSTRAINTS disposition (`11` item 6) and says go.
PR #219 (the research packet) should merge first, so the plan's links resolve on `main`.

## Decided by Rylee (2026-10-02) — these override anything below

| Item | Decision |
|---|---|
| D1 exit threshold | **At least 25% fewer authored values, or one real error caught.** Below that, stop and revert. |
| D2 generated records | **Committed in the pack and read-only.** |
| D3 hand-written records | **End of life to be set later.** Hand-written records stay fully supported for now; Rylee will set a date, if any, after the trial. Do not record "no end of life". |
| Names and shape | Blueprint, a JSON file inside the pack; stale output rejected; Cottage's CI pin bumped with the first normalizer. |

## Execution method (Rylee, 2026-10-02) — overrides any "Sonnet Foreman" wording below

Offloadable tasks run as an **offload foreman controlling offload workers**: `offload foreman -m foreman` (MiniMax M3.1 on the claude engine) launches `offload agent` workers on the `code` tier (`deepseek-flash`), under `--budget` and `--minutes`, on Bazzite. The foreman has no Edit or Write tools, so code comes only from workers. Sonnet is the integrator: it writes the keep tasks (ADR, frozen tests, security review, Cottage work), commits everything the workers need *before* launch (they see tracked files at HEAD), supplies each task's exact `--accept` command, then reviews and applies the foreman's result per `skills/offload/FOREMAN.md`. Nothing a foreman produces is merged without that review. Never use `alibaba:qwen3.8-max` as foreman. No Opus fan-out.

## 1 · Goal, in one paragraph

A pack may carry one optional file, `blueprint.json`, that declares creature **families** (defaults, at most one `extends`) and, per region, an ordered list of **instances**.
`vefr normalize` expands it into today's `enemies` records inside each owned region's `contract.json`, and writes a sidecar, `blueprint.lock.json`, with the source hash, the normalizer version and provenance.
`vefr check` (and so `norns validate`, and Cottage CI) checks the Blueprint, rejects stale or hand-edited generated output, then runs today's whole-pack validator unchanged.
The runtime, the bake and the player never learn the Blueprint exists.
Proven live by moving Cottage's creature records, and only those, to a Blueprint.

## 2 · Facts this plan relies on (reverified 2026-10-02)

| Fact | Evidence |
|---|---|
| `vefr check` is `cmd_map` → `maplab.main(['validate', ...])` → `cmd_validate` → `load_pack` + `validate(w, pack_dir)` | `src/vefr/cli.py:4314-4324`, `cli.py:583-586`, `maplab.py:1907-1931` |
| `norns validate` and Cottage CI reach the same `cmd_validate` | Cottage `.github/workflows/validate-pack.yml:26` pins `VEFR_REF`, runs `norns validate --pack ...` |
| So one hook in `maplab.validate` covers `vefr check`, `norns validate`, the builder's validate route and Cottage CI | `maplab.py:1381-1423` (optional catalogs checked there, e.g. growth at `:1420-1423`, library guarded by `pack_dir` at `:1755-1759`) |
| Enemy records live in `acts/<act>/<region>/contract.json` `enemies`; the validator checks id, name, `at` walkable, positive int `hp`/`atk`, `xp` only in levels mode | `maplab.py:1693-1752` |
| Validator does **not** check enemy `drops` ids; the bake silently filters unknown ones | no `drops` in `maplab.py`; `cli.py:1306-1318` `_drop_ids` |
| The bake reads exactly `id, name, at, hp, atk, sprite, drops` plus `sight` and `xp` when present | `cli.py:1732-1768` |
| Rule enemy ids resolve by reading every act's `contract.json` from disk, not from the in-memory world | `maplab.py:344-447` (`_rule_known_ids`) |
| `load_pack` reads only the **first** act's regions | `maplab.py:63-75` |
| VEFR already writes contracts as `json.dumps(obj, indent=2, ensure_ascii=False) + '\n'`; Cottage's contract files match that form byte for byte (checked on two of them) | `maplab.py:1839-1851`; local check |
| The weave never validates; Cottage's build script calls `cli.weave_html` directly | `cli.py:1606-1960`; Cottage `bin/publish-build.sh:12-14` |
| The CLI verb set is a tested contract | `tests/test_cli_help.py:54-58` (`REQUIRED_VERBS`, `VEFR_VERBS`), `:364-367` (`DISPATCH_ARGV`, `EXPECTED_BOUND`) |
| `features` detect values are a closed list | `src/vefr/features.py:24-25` |
| No existing use of "blueprint" in `src`, `web`, `docs/guides` | `grep -ri blueprint` empty |
| Proof code (probe A) is `experiments/language-proof/prototype.py` on `origin/experiment/language-proof-20261002` @ `649034f`, not on `main` | `git show` |

Cottage structure (counts only, from the private companion and a local read):
69 enemy records over 9 region contracts (6 of them hold enemies); 4 distinct sprites; 25 records carry `drops`, all naming real items; two key orders in use (64 and 5 records).
A rough model of 4 families keyed by sprite, no per-depth sub-families, gives about 508 authored values today versus about 350 in a Blueprint: **UNVERIFIED** estimate, not a promise.

## 3 · Design

### 3.1 Files in a pack

| File | Who edits | Purpose |
|---|---|---|
| `blueprint.json` (pack root) | the author | the edited truth for the regions it owns |
| `acts/<act>/<region>/contract.json` `enemies`, for owned regions | `vefr normalize` only | generated, read-only; everything else in the contract stays hand-authored |
| `blueprint.lock.json` (pack root) | `vefr normalize` only | source hash, versions, provenance |

The Blueprint is **not** a `world.json` key: the weave folds every `world.json` key into `VEFR_WORLD` (`cli.py:1624-1627`, `:1857`), and provenance must stay out of runtime globals (`09`).

Generated records are **committed** (my reading of decision 1, "generated contracts are read-only and carry a source hash"). Consequences, all wanted:

- every consumer that exists today (old pinned validators, the weave, the server, Studio) sees a fully materialized pack;
- "validate the whole normalized pack" is just today's validator on the pack on disk;
- the exit ramp is deleting two files.

### 3.2 Blueprint format 1

```json
{
  "blueprint": 1,
  "families": {
    "beetle":      { "defaults": { "name": "a beetle", "sprite": "beetle", "hp": 3, "atk": 1, "xp": 2 } },
    "deep-beetle": { "extends": "beetle", "defaults": { "hp": 4 } }
  },
  "regions": {
    "act-1/cave-2": {
      "enemies": [
        { "id": "b1", "family": "beetle", "at": [3, 4] },
        { "id": "b2", "family": "beetle", "at": [6, 4], "properties": { "drops": ["shell"] } }
      ]
    }
  }
}
```

(Synthetic example. No real pack content appears in VEFR.)

Closed sets, defined once as constants in `src/vefr/blueprint.py`:

| Where | Allowed keys |
|---|---|
| top level | `blueprint`, `families`, `regions` |
| family | `defaults`, `extends` |
| `defaults` / `properties` (family fields) | `name`, `sprite`, `hp`, `atk`, `xp`, `sight`, `drops` |
| region entry | `enemies` |
| instance | `id`, `family`, `at`, `properties` |

Rules:

- `"blueprint": 1` is required and is the **source version field**. It names the reader `read_v1`; `READERS = {1: read_v1}`. Missing, non-integer or unknown versions fail with one sentence naming the versions this VEFR reads.
- Expansion order: parent chain defaults (root first), then the family, then instance `properties`, then `id` and `at`. A later value **replaces** an earlier one whole; lists are never merged.
- One explicit parent. Unknown parent, unknown family, and cycles (self or longer) fail, naming the chain.
- Unknown keys at any level fail. There is no event or effect vocabulary in format 1, so a `when`, `then`, `effects` or any other word is an unknown-key error: declaring a word grants nothing (`09`, `12`).
- Region keys are `<act>/<region>`. Each must name an existing region directory, resolved through the existing path guard `cli._inside` (`cli.py:932`); no Blueprint string becomes a path any other way.
- A flat-shape pack with a `blueprint.json` fails: format 1 is acts-shape only.
- Instance ids are unique within their region (checked in the source, before the whole-pack check repeats it).
- Every `drops` id in Blueprint-owned records must name a pack item. This is new strictness for Blueprint-owned records only; hand-written packs are not newly failed.
- Emitted record key order is fixed: `id, name, sprite, at, hp, atk, xp, sight, drops` (absent keys skipped). This only matters for bytes, never for equality.
- Every error names its JSON pointer in the Blueprint (`/regions/act-1~1cave-2/enemies/1/properties/hp`).

### 3.3 The lock and the stale rule

`blueprint.lock.json`:

```json
{
  "blueprint": 1,
  "normalizer": 1,
  "source_sha256": "<sha256 of the canonical Blueprint>",
  "outputs": [
    { "file": "acts/act-1/cave-2/contract.json", "pointer": "/enemies",
      "records": [ { "source": "/regions/act-1~1cave-2/enemies/0",
                     "families": ["beetle"], "overrides": [] } ] }
  ]
}
```

- Canonical Blueprint hash: `sha256(json.dumps(parsed, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())`. Object key order and whitespace do not make a Blueprint stale; list order does.
- `NORMALIZER_VERSION` is an integer in `blueprint.py`, bumped whenever the same Blueprint could produce different output.
- **Stale** means: the lock's `source_sha256` differs from the current Blueprint, or any owned value on disk is not structurally equal (`07`: parsed-JSON `==`, key order ignored, list order significant) to what this VEFR expands now.
- A lock written by a **newer** normalizer or format than this VEFR knows fails clearly. An older normalizer whose output is still equal passes, with a one-line note to re-run `normalize`.
- `blueprint.json` without a lock, or a lock without `blueprint.json`, fails.

### 3.4 The pipeline, and where each step runs

```
read (versioned reader) -> validate source (closed keys, families, cycles, paths, drops)
  -> expand (ordered) -> provenance -> write owned values + lock
  -> validate the whole normalized pack (today's maplab.validate, which includes rules_errors)
```

| Entry point | Does |
|---|---|
| `vefr check --pack PACK` (and `norns validate`) | when `blueprint.json` or the lock exists: source checks + stale check, reported as `FAIL:` lines beside today's; then today's validation. No Blueprint, no lock: no new file read beyond two existence checks, output unchanged |
| `vefr normalize --pack PACK` | read-only: validate and expand, print a per-region summary, the provenance, and whether the committed output is fresh. Exit 0 fresh, 1 errors or stale |
| `vefr normalize --pack PACK --out PACK` | refresh in place: write only owned `enemies` values and the lock, in the canonical serializer, then run the whole-pack validator; on failure restore the previous bytes and exit 1 |
| `vefr normalize --pack PACK --out DIR` (DIR absent or empty) | copy the pack to DIR, refresh there, validate there; PACK is untouched |
| `cli.weave_html` (and so `vefr weave`, `publish`, the builder's shareable file) | refuses a pack whose Blueprint is stale or invalid, with the same sentence `check` prints. No Blueprint: unchanged |

No new server route, no Studio, no write route (`06`). Determinism: no clock, randomness or model call in `blueprint.py` (it joins the AGENTS.md deterministic-surface list).

## 4 · Acceptance tests (written first, frozen)

All VEFR fixtures are synthetic, in `tests/fixtures/blueprint/`. They land first as `pytest.mark.xfail(strict=True)`, so each implementation PR must flip them to passing and remove the mark; a Foreman that needs to change a frozen test stops and escalates.

| # | Test | Asserts |
|---|---|---|
| A1 | `test_blueprint_equivalence.py::legacy_equivalence` | a synthetic acts pack with hand-written enemies (uniform groups, one non-uniform record, `drops`, a per-depth `hp` via `extends`, a `sight`) and a Blueprint for it: expansion `==` the legacy `enemies` list of every owned region (structural equality per `07`) |
| A2 | `..::canonical_bytes` | `normalize --out PACK` run twice leaves identical bytes; untouched files and untouched keys of owned contracts are byte-identical to before |
| A3 | `test_blueprint_compat.py::no_blueprint_unchanged` | `worlds/sample-world`: `vefr check` stdout and exit code, `validate()` errors, and `weave_html` output are identical with the Blueprint hooks enabled and monkeypatched to no-ops |
| A4 | `..::lock_not_in_woven_file` | a Blueprint pack's woven HTML contains neither the source hash nor any provenance pointer |
| A5 | `test_blueprint_conformance.py` | walks `tests/fixtures/blueprint/v1/{valid,invalid}/<case>/`: each valid case's expansion equals its `expected.json`; each invalid case fails with the substring in `expected-error.txt`. Cases: unknown top/family/instance/field key; a `then` or `effects` key; unknown family; unknown parent; self cycle; two-step cycle; duplicate instance id; missing `at`; region that does not exist; region path escaping the pack; unknown `drops` item; version missing, `"1"`, `2`; invalid JSON; flat-shape pack |
| A6 | `test_blueprint_stale.py` | edit the Blueprint without normalizing: `check` fails "stale"; hand-edit one generated record: fails naming file and pointer; lock missing; lock without Blueprint; lock from normalizer `999`; older normalizer with equal output passes with a note |
| A7 | `..::weave_refuses_stale` | `weave_html` raises with the stale sentence; a fresh pack weaves |
| A8 | `..::whole_pack_validation` | a Blueprint that is valid on its own but places an enemy on a solid tile, or gives `xp` outside levels mode, is caught by the second validation and `--out PACK` restores the old bytes |
| A9 | `test_blueprint_cli.py` | `normalize` read-only writes nothing (directory hash before = after); `--out DIR` leaves PACK untouched; exit codes 0/1 |
| A10 | `tests/test_cli_help.py` | `normalize` added to `VEFR_VERBS`, `DISPATCH_ARGV`, `EXPECTED_BOUND` |
| A11 | `test_blueprint_docs.py` | the guide's field tables list exactly the closed-set constants; glossary has "Blueprint"; `vefr-command.md` names `normalize` |
| A12 | `test_blueprint_determinism.py` | same Blueprint → same lock and same records, run twice in one process and in two processes |

Gate per PR (AGENTS.md "Commands"): `uv run --group test ruff check src tests scripts`, `uv run --group test pytest -q`, `uv run --group test norns validate --pack worlds/sample-world`, `python3 scripts/check_public_surface.py`.

Cottage acceptance (private, in the Cottage PR body):

- C1 `norns validate --pack worlds/cottage-of-the-breeze` green at the new pin **before** adding the Blueprint (the real pack is an old pack and must be unchanged);
- C2 for every owned region, `json.loads(git show origin/main:<contract>)['enemies'] == json.loads(<contract>)['enemies']` after `normalize --out PACK` (the equivalence proof against today's records);
- C3 `vefr check` green; `vefr normalize --pack ...` reports fresh;
- C4 woven build plays: `vefr look` on the woven file reaches a creature floor; screenshot in the PR;
- C5 the exit-ramp measurement (section 9).

## 5 · Tasks

| # | Task | Mark | Foreman / model |
|---|---|---|---|
| T1 | ADR `docs/adr/0008-blueprint-format.md`: format 1, closed sets, version and deprecation policy (below), kernel budget, owner and change process | keep | none, Sonnet integrator |
| T2 | Write A1–A12 fixtures and tests, xfail strict; synthetic fixtures only | keep (frozen contract) | none, Sonnet integrator |
| T3 | `src/vefr/blueprint.py` (library half): `BlueprintError`, the closed-set constants, reader registry and `read_v1`, `read`, `expand` with source errors and pointers, canonical hash, path guard via `cli._inside`. Lock read/write, `check_errors` and the stale check move to PR 3 (T4/T5), where tests can reach them | offloadable (A1, A5, A12 prove it); the path guard is reviewed as **keep** | 1 offload foreman + `code` workers |
| T4 | Hook: `maplab.validate` calls `blueprint.check_errors(pack_dir)` when `pack_dir` is given; `weave_html` calls it first and raises | offloadable (A3, A6, A7, A8) | same Foreman as T5 |
| T5 | `vefr normalize` verb in `cli.py` (one module-level `cmd_normalize`), in-place restore on failure, `--out DIR` copy | offloadable (A8, A9, A10) | 1 offload foreman + `code` workers |
| T6 | Docs and discoverability: `docs/guides/blueprint.md` (one page, the three beginner questions), `docs/guides/vefr-command.md`, `docs/guides/glossary.md`, `src/vefr/world.py` docstring (pack contract), `docs/features.json` entry plus `"blueprint"` in `VALID_DETECTS` and its detector, `ROADMAP.md`, `.project/DECISIONS.md`, AGENTS.md deterministic-surface line | offloadable (A11, `vefr features --check`, `test_features.py`) | 1 offload foreman + `code` workers |
| T7 | Cottage: bump `VEFR_REF`, write `blueprint.json` for creature families only, run `normalize --out PACK`, prove C1–C5 | keep (private pack, canon-adjacent, owner merges) | none, Sonnet integrator; Rylee reviews |
| T8 | Exit-ramp verdict and evidence note in `.project/DECISIONS.md`; revert PR if it fails | keep | none, Sonnet integrator; Rylee decides |
| T9 | Security review of T3–T5: no Blueprint string reaches the filesystem except through `_inside`; `--out` refuses a non-empty DIR and never writes outside it | keep | none, Sonnet integrator |

**Launch budget:** at most 1 offload foreman at a time for this plan (2 total if Plan 2 runs in parallel), each via `offload foreman` with an exact file scope and the acceptance command. No Opus fan-out. Before launch the integrator runs `~/.agents/bin/route-plan` on this file and states the count again.

Versioning and deprecation policy (content of T1):

- the format is an integer in the file; each format has one reader and its own fixture directory;
- a reader is never removed without a migration tool, a release note, and an end date Rylee approves;
- the normalizer version bumps when output for the same input may change; the lock records it;
- an unknown newer format or normalizer fails with a sentence, never a guess;
- adding a field, family key or instance key is a format change and needs a written reason in the ADR (the kernel budget).

## 6 · PR sequence

| PR | Repo / branch | Contents | Files (verified to exist unless marked new) | Depends on |
|---|---|---|---|---|
| 1 | VEFR `feat/blueprint-contract` | T1, T2 | new `docs/adr/0008-blueprint-format.md`, new `tests/test_blueprint_*.py`, new `tests/fixtures/blueprint/`, `tests/test_cli_help.py` (A10 as xfail) | gate, #219 |
| 2 | VEFR `feat/blueprint-core` | T3; flips A1, A5, A12 (the library tests; the rest need the verb) | new `src/vefr/blueprint.py`, the tests' xfail marks, `ROADMAP.md` | 1 |
| 3 | VEFR `feat/blueprint-cli` | T4, T5, T9; flips A2, A3, A4, A6–A10 | `src/vefr/maplab.py`, `src/vefr/cli.py`, `tests/test_cli_help.py`, `ROADMAP.md` | 2 |
| 4 | VEFR `docs/blueprint-guide` | T6; flips A11 | new `docs/guides/blueprint.md`, `docs/guides/vefr-command.md`, `docs/guides/glossary.md`, `src/vefr/world.py`, `docs/features.json`, `src/vefr/features.py`, `ROADMAP.md`, `.project/DECISIONS.md`, `AGENTS.md` | 3 |
| 5 | Cottage `feat/blueprint-creatures` | T7 | `.github/workflows/validate-pack.yml` (pin), new `worlds/cottage-of-the-breeze/blueprint.json`, new `.../blueprint.lock.json`, the 6 region contracts that hold enemies | 4 merged to VEFR `main` |
| 6 | VEFR `docs/blueprint-verdict` (or a revert) | T8 | `.project/DECISIONS.md` | 5 |

Files prohibited for every Foreman: `web/packaged.html`, `src/vefr/delve.py`, `src/vefr/world.py` loader code (docstring only in PR 4), `.github/workflows/`, `scripts/`, `uv.lock`, any `worlds/` pack, the Cottage repo.

Cottage PR order inside one PR: commit 1 bumps the pin only (prove C1 locally), commit 2 adds the Blueprint and regenerated contracts. Verify both states locally and push once.

## 7 · Compatibility

| Case | Result |
|---|---|
| Pack without `blueprint.json` (every pack today) | unchanged: no new output, same bytes woven (A3) |
| Pack with a Blueprint, read by an **older** VEFR | still validates and weaves: the records are on disk; the older VEFR just does not check freshness (decision 8 accepts this) |
| Pack with a Blueprint, newer format than this VEFR | fails clearly, names the readers it has |
| Hand-written regions inside a Blueprint pack | untouched; only regions listed under `regions` are owned. Mixed ownership of one region is impossible by construction |
| Saves | not affected: ids and `at` are unchanged by normalization, so slain lists (`vefr-slain-<world>-<region>`) still match |
| Tools that rewrite contracts (`vefr delve`, Studio `write_pack`) | if they rewrite an owned region, the next `check` reports stale and `normalize --out PACK` restores it. **UNVERIFIED** whether Studio ever rewrites a floor contract's `enemies` |

## 8 · Durability checklist (campaign plan "Durability", items 1–9)

| Item | Where it is scheduled |
|---|---|
| 1 Conformance suite | A5 fixture walk, A1 equivalence, A12 determinism; runs in the normal `pytest` gate (no workflow change) |
| 2 Versioning and deprecation | T1, written before PR 2 ships the format |
| 3 Single source of truth | closed sets are constants in `blueprint.py`; the guide is checked against them (A11); `features.json` lists the feature (`vefr features --check`) |
| 4 Small enough for one head | format 1 is 3 top keys, 2 family keys, 4 instance keys, 7 fields; growth needs a written reason (T1) |
| 5 Owner and cadence | Rylee owns the format; changes go through an ADR amendment PR that Sonnet reviews and Rylee merges (T1) |
| 6 Teachability | `docs/guides/blueprint.md`; "what words does this game know" = `vefr normalize --pack P` lists families; "what can this thing do" and "why does it have this value" = the provenance lines (families chain, overridden keys) |
| 7 Dogfooding | Cottage CI runs `norns validate` at the pin, which now includes the stale check, on every Cottage PR |
| 8 Graceful degradation | hand-written records stay first class; no adapter is needed because nothing old changes. End of life is to be set later by Rylee (decided; see the top table) |
| 9 Honest exit ramps | every PR leaves `main` releasable; section 9 |

## 9 · Exit ramp and rollback

Measure in PR 5: authored enemy values (every scalar or list in `blueprint.json` versus every value in the replaced records), and whether source validation caught any real error.

- **Continue** if authored values fall by the agreed threshold (section 11, D1), or a real error is caught.
- **Stop and revert** otherwise:
  Cottage: delete `blueprint.json` and `blueprint.lock.json` and restore the pin. The contracts are already full records, so the pack is exactly a legacy pack again; nothing is half-migrated.
  VEFR: one bounded revert PR removes `blueprint.py`, the hook, the verb, the docs and the tests (PRs 2–4), with the verdict recorded in `.project/DECISIONS.md`.
- Rollback of any single VEFR PR is `git revert` of its merge commit; PRs 2–4 each keep `main` green on their own because unflipped tests stay xfail.

## 10 · Risks

| Risk | Response |
|---|---|
| Two truths drift (a hand edit to a generated record) | stale check in `validate` and in the weave (A6, A7) |
| Families need so many overrides that nothing shrinks (the rough estimate above has many per-depth overrides) | `extends` for depth variants; exit ramp measures it |
| A within-group difference in Cottage looks like a typo | it is expressed as an override, never "fixed"; Rylee decides (canon) |
| The weave refusal blocks a publish | intended; the sentence says the one command that fixes it |
| Key-order churn: 5 Cottage records change key order on first normalize | expected, structural equality holds (C2); called out in the PR body; no byte-equality claim |
| Path traversal through region keys | `_inside` guard, conformance case, T9 review |
| `load_pack` checks only the first act's regions | pre-existing limit; format 1 owns first-act regions in practice. A Blueprint region in a later act still gets source checks and rule-id resolution; its geometry check is as weak as today's. Noted in the guide |
| Private content leaks into VEFR | synthetic fixtures only; `check_public_surface.py`; `test_pack_neutrality.py` |
| Old pinned runtimes skip freshness | accepted by decision 8; Cottage's pin moves with PR 5 |

## 11 · Decisions for Rylee

D1–D3 are decided; see the table near the top. The engineering choices (file names `blueprint.json` / `blueprint.lock.json`, version key `"blueprint": 1`, `drops` checked only for owned records) stand unless vetoed.

## 12 · Out of scope

Rules lowering, floors and themes, generation recipes, guardians and the ending, events, traits, relations, kernel extraction, event sourcing, logic engines, natural language, YAML, Studio, any HTTP route, a provenance API, `vefr explain`/`diff`, changes to `web/packaged.html`, newly failing hand-written packs (for example on unknown `drops`), and Plan 2.
