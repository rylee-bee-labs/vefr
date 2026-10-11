# Contributing to vefr

Thank you for wanting to help build vefr — a story engine for
playable worlds.

**Quick start:** clone, install, test, run:

```sh
git clone https://github.com/rylee-bee-labs/vefr.git
cd vefr
uv sync --group test
uv run --group test pytest -q       # should pass — count varies; check no new failures
uv run uvicorn vefr.main:app --app-dir src --port 8820
# open http://127.0.0.1:8820
```

From here, pick what you want to do:

| Want to... | Read this |
|---|---|
| Fix a bug | Reproduce → fix → test gate → PR |
| Add a feature | `ROADMAP.md` → find the Next item → discuss in an issue first |
| Build a world | [`GETTING_STARTED.md` §3](GETTING_STARTED.md#3-make-your-own-world) |
| Change the UI | `web/` — follow the [accessibility matrix](#accessibility-matrix) below |
| Change the pack contract | `src/vefr/world.py` docstring — **ask first** |

## Play-Nice Contracts

This project adopts [Play-Nice Contracts](https://github.com/rylee-bee-labs/play-nice-contracts)
as its shared cooperation constitution: truth and evidence before
generating content, explicit state, asking instead of guessing,
and accessibility floors. If your change touches a player-facing
surface, read the accessibility matrix first.

## Quick start (for agents)

1. Read `AGENTS.md` — it has every rule this repo enforces.
2. Read `AGENT_POLICY.md` — the decision kernel and definition of done.
3. Read `.project/CURRENT.md` — what's true right now.
4. Run the gate (must match CI exactly):
   ```sh
   uv sync --group test
   uv run --group test ruff check src tests scripts
   uv run --group test pytest -q
   python3 scripts/check_public_surface.py
   ```
   Or let one runner do the looking-up (see [Test gate](#test-gate-every-pr-must-pass)):
   ```sh
   scripts/check
   ```
   A step the runner has no tool for comes back `SKIP` and does not fail
   the run, so read the SKIP lines: a green `scripts/check` is not proof
   the gate passed.
5. Known pre-existing failures (do not treat as regressions):
   - `test_face_roll_is_honest_without_a_model`, `test_map_propose_is_honest_without_a_model` — model-dependent; fail when no LLM endpoint is reachable.

## What to work on

| Want to... | Read this |
|---|---|
| Fix a bug | `GETTING_STARTED.md` → reproduce → fix → test gate → PR |
| Add a feature | `ROADMAP.md` → find the Next item → discuss in an issue first |
| Build a world | `GETTING_STARTED.md` §3 ("Make your own world") |
| Change the pack contract | `src/vefr/world.py` docstring — **ask first** |
| Add a new API route | `src/vefr/main.py` — **ask first** |
| Change the UI | `web/` — follow the accessibility matrix below |
| Run the engine in a container | `docs/guides/bundled-brain.md` |

## Branch model

```
main ← PR ← feat/*
```

- One PR per concern. Keep them small.
- PR targets `main`. No direct pushes (branch protection enforced).
- Rebase before requesting review if your branch is behind.

## Test gate (every PR must pass)

```sh
scripts/check                 # the CI commands below, run as one table
```

`scripts/check` carries the CI commands as a step table and runs them
locally, so most of the gate is answered before the PR is sent:

```sh
scripts/check --list         # every CI step: what runs here, what is CI-only
scripts/check --json         # with --list, the same step table as JSON
scripts/check --fast         # the pre-push subset: lint, tests of the changed
                             # code, gitleaks on the branch diff
scripts/check --full         # the default, spelled out: every step that runs
                             # here, fast ones and slow ones
scripts/check --merge-ready  # merge origin/main into HEAD in a throwaway
                             # worktree and run the full check on the merged tree
```

Each step prints `PASS`, `FAIL`, or `SKIP` with the reason; a blocking
`FAIL` exits non-zero. A tool that is not installed is a `SKIP` with an
install hint, never a silent pass. With `uv` present the script runs the
command CI runs; without it, it falls back to the shared CI venv and
prints which one it used.

**It is a runner, not the gate.** A SKIP is not a pass: a step this
machine has no tool for is skipped, not checked, and the run still exits
0. So exit 0 means "no blocking step that could run here failed" — on a
machine with no toolchain that is every step SKIPped and nothing checked.
Read the `SKIP` lines and the summary's skip count, and let CI be the
gate that decides the PR.

| Step | Speed | Runs here? |
|---|---|---|
| `ruff check src tests scripts` | fast | yes |
| pytest on the tests this branch changed | fast | yes |
| public-surface guard | fast | yes |
| `norns validate --pack worlds/sample-world` | fast | yes, with the synced `uv` env |
| gitleaks over `origin/main..HEAD` | fast | yes, with the gitleaks binary |
| `npm ci` (jsdom, for the node-vm harnesses) | slow | yes, with npm |
| pytest, whole suite | slow | yes |
| `norns validate` on every shipped pack | slow | yes (matches the Gitea mirror) |
| actionlint, zizmor, vulture, deptry | fast / slow | when the tool is installed |
| axe-core a11y, browser tests, visual regression | — | **CI-only** (Playwright + Chromium) |
| lychee link check, Vale prose | — | **CI-only** (GitHub actions) |
| honest-claims policy, contract freshness | — | **CI-only** (ci-harness reusable workflows) |

**What it does not cover:** everything marked CI-only above; GitHub's own
mergeability, reviews and branch protection; and the image publish and
screenshot jobs, which only run on `main`. It is the commands, not the
decision to merge.

### What blocks a merge (required checks)

Branch protection on `main` requires these four checks, each bound to
GitHub Actions (app 15368):

| Check | Workflow |
| --- | --- |
| `ruff + pytest + sample-world + public-surface guard` | `ci.yml` |
| `claims / honest-claims policy` | `ci.yml` (ci-harness reusable workflow) |
| `gitleaks full-history scan` | `ci.yml` |
| `browser tests (studio as a person uses it)` | `dev-guards.yml`, with `VEFR_BROWSER_REQUIRED=1` |

**The browser check is required since 2026-10-09** (Rylee: *"Approved: make
VEFR's existing browser test job a required check."*). It runs
`pytest tests/browser` in Chromium on every pull request to `main`, with no
path filter, so a PR cannot avoid it. A required check that **fails**, is
**cancelled**, or never reports (**missing**) blocks the merge. Only success
lets it through. The `main` ruleset additionally requires the first and third
checks with its own strict up-to-date policy.

To see the list as GitHub holds it:

```sh
gh api repos/Rylee-Bee/vefr/branches/main/protection --jq '.required_status_checks.checks'
```

The same gate, one command at a time:

```sh
uv run --group test ruff check src tests scripts    # lint (scripts/ too — CI checks it)
uv run --group test pytest -q                       # tests (matches CI)
uv run norns validate --pack worlds/sample-world    # pack integrity
python3 scripts/check_public_surface.py            # no private IPs, hostnames, or creds
```

## Accessibility matrix (every UI change must answer)

- **Targets:** ≥44px minimum tap/click target
- **Colour:** rank by luminance, never hue alone; no colour-only meaning
- **Motion:** off by default; `prefers-reduced-motion` respected
- **Keyboard:** every interactive element reachable and operable
- **Screen reader:** semantic HTML, ARIA labels, live regions for dynamic content
- **Reading load:** short, plain English; Norse as flavour, not requirement

## Engine neutrality

The engine must stay story-agnostic — it works with any world pack,
including ones that don't exist yet. To keep that:

- No story content from private packs in tracked files
  (worlds under `worlds/` are gitignored unless shipped)
- No game-specific names in engine code, prompts, or API titles
- No runtime state (sessions, vault, journal)
- No model calls in deterministic surfaces
  (`export.py`, `weave.py`, `maplab.py`, `journal.py`, `blueprint.py`)

## Commit messages

Keep them short, imperative, prefixed:

```
fix: correct ollama URL in GETTING_STARTED
feat: add title screen to woven HTML export
docs: update README with bundled brain section
test: add gitignore tripwire for worlds tracking
```

For messages with quotes or newlines, use `git commit -F <file>`.

## Play-Nice Contracts

This project adopts [Play-Nice Contracts](https://github.com/rylee-bee-labs/play-nice-contracts) as its shared cooperation constitution. Every design, engineering, documentation, and release decision must point to the Play-Nice Contract it preserves or changes. See `.project/contracts/adoption.yaml` for the pinned revision.

## Getting help

- **[Issues](https://github.com/rylee-bee-labs/vefr/issues):** Bug reports
  and feature requests welcome
- **[Discussions](https://github.com/rylee-bee-labs/vefr/discussions):**
  For questions about building your own world
- **Security:** See [`SECURITY.md`](SECURITY.md) — never paste
  secrets in issues
- **Stuck?** Check [`GETTING_STARTED.md`](GETTING_STARTED.md) and
  the [API docs](http://127.0.0.1:8820/docs) (when the engine is
  running)
