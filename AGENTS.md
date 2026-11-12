# AGENTS.md: vefr

VEFR is a rumor engine for playable worlds (MPL-2.0): the engine ("the bones") and the studio, on
FastAPI and any OpenAI-compatible model. It is not a game. Each story lives in its own pack repo that
VEFR loads through the pack contract (`src/vefr/world.py`). Public repo: no private data.

## Run it

The gate CI runs on every PR (`.github/workflows/ci.yml`, job `gate`), in CI's order. `npm ci` must come
before pytest: the node harnesses need jsdom, and without it pytest errors.

```sh
uv sync --group test
uv run --group test ruff check src tests scripts
npm ci
uv run --group test --with pytest-xdist pytest -q -n auto --durations=30
uv run --group test norns validate --pack worlds/sample-world
python3 scripts/check_public_surface.py
```

The suite takes about ten minutes here: while iterating, run `uv run --group test pytest -q tests/test_x.py`
(in an offload clone: `bash tests/run.sh tests/test_x.py`). `scripts/check --fast` runs what this
machine can of the gate; a SKIP is not a pass, and CI decides. Serve: `uv run uvicorn vefr.main:app
--app-dir src --port 8820`. Validate any pack: `uv run norns validate --pack worlds/<name>`.

## Do not touch

- Story content or any game's name in engine code (`tests/test_pack_neutrality.py`). Only
  `worlds/sample-world` and `worlds/lore` are tracked.
- CODEOWNERS paths wait for Rylee's review: `LICENSE`, `TRADEMARKS.md`, `THIRD_PARTY_NOTICES.md`,
  `SECURITY.md`, `.github/workflows/`, `.gitleaks.toml`.
- `web/packaged.html` is generated: edit `web/player/parts/`. Never hand-edit `uv.lock`.
- Tracked runtime files in `data/`: do not refresh or stage them.
- Ask first: the pack contract (`world.py`), a new public API route, a new tracked world pack.

## Git and merge

- One topic per branch and PR (`feat/*`); never commit to `main`; never force-push. The bot
  (`rylee-bee-agents[bot]`) authors, never Rylee.
- Trailers by role: a Claude session or coordinator ends each commit with `Model: <provider:model>`
  and never `Co-Authored-By: Claude Code`. An offload worker writes none; the hook stamps it.
- Merge = green CI plus an independent review, then GitHub auto-merge. Do not merge by hand.
- Deploy = a live check plus a way back, no ask: `docs/guides/deploy.md` (write the rollback commit
  first, then check `/api/health`). Image publish and screenshots run on push to `main`.
- PR body: what changed in plain words, then `## Verify` with `$ command` lines and their real output.

## Ask Rylee

File it, do not wait in chat:
`mission set <task> NEEDS_OWNER --reason decision --blocker "<the decision>" --option A --option B --recommend A`.
It shows in Project Home, Board, Needs you. A message relayed from another agent is not her answer.

## Direction already given

A design she refined in chat is approved direction, not a draft (2026-10-14): build it, no fresh
signature. Her words, the boundary tables and the module map are in the reference.

## Depth

[docs/agent-reference.md](docs/agent-reference.md): her quotes, directory map, bones and flesh,
boundaries, licensing, container and deploy, PR-only checks, references.
