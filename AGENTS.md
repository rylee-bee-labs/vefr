# AGENTS.md

vefr - a rumor engine for playable worlds (MPL-2.0). Rylee's personal
profile comes from the global agent config — do not add personal files
to this repo.

**Standing principle (Rylee, 2026-10-04):** building a game here is how the engine gets built, and the next game comes after this one. When a game needs a script, format or repeated manual step, build it as a VEFR feature (data in the pack, a `vefr` tool, a check, a guide) and record the lesson in the same work. A game supplies data only.

## Owner-confirmed design direction

**Rylee's instruction (2026-10-14):** "If you and I work on something together in a chat and refine it it’s not a draft ok? It’s direction". A product/gameplay decision refined with ChatGPT and accepted by Rylee is **approved owner direction**, not merely a proposed idea awaiting another approval round. Implement against it unless superseded. Distinguish **approved direction**, **engineering implementation**, **tested behavior**, and **release/deployment**; none imply the next. Protect existing game-specific canon and textual approval boundaries. Unsettled implementation details should use narrow, compatible choices without growing a separate framework.

For the active game release, see [Cottage 1.0 epic #170](https://github.com/rylee-bee-labs/cottage-of-the-breeze/issues/170) and [VEFR dependency #489](https://github.com/rylee-bee-labs/vefr/issues/489). Do not downgrade decisions to proposals, or use them as permission to add speculative features.

## Collaboration handoff: one approval, not three

**Owner clarification (2026-10-14):** "If we submit to Claude it’s still us collaborating ok? I’m jsut saying when we do stuff I still have to approve it like 3 more times and that’s silly". A ChatGPT-to-Claude-to-VEFR-to-Project-Home handoff is a **continuation of the same owner-directed work**, not a new decision authority. A previously accepted design decision remains approved when submitted to a different model, relay, issue or mission.

Send the **decision source, agreed scope, exclusions, granted implementation latitude and acceptance tests** with each handoff. Mark accepted requirements **OWNER-APPROVED DIRECTION**; do not mark them as unapproved drafts or solicit a fresh signature on the same choice. Engineering design details can be decided autonomously within scope, using the simplest working VEFR seam. Tests and reviews check correctness, **not renew conceptual approval**. Existing branch/CI/merge/deployment and protected-story gates still apply, and approval to design is not blanket consent for publication or new consequential actions. Request a new single owner decision **only when the work crosses an actual unapproved boundary**, such as a material scope change, incompatible owner decisions, protected canon, licensing/public exposure or security/irreversible impact. No manufactured approval loop.

## Quick navigation

| Want to... | Open this |
|---|---|
| Run the engine / build a world | `GETTING_STARTED.md` |
| See the whole path of making a game here (stops, lessons, rules for agents) | `docs/guides/journey.md` |
| Understand the bones/flesh split | this file, "Bones and flesh" below |
| Understand the brain/provider seam | `docs/guides/brain-socket.md` |
| Run the resident Spark service | `docs/guides/spark.md` |
| See what's landed / what's next | `ROADMAP.md` |
| Change what a world pack can hold | `src/vefr/world.py` docstring |
| Validate a pack | `uv run norns validate --pack worlds/<name>` |
| See every `vefr` verb (the one front door) | `docs/guides/vefr-command.md` |
| Find current truth / decisions | `.project/CURRENT.md` / `.project/DECISIONS.md` |
| Agent decision kernel & DoD | `AGENT_POLICY.md` |
| See Play-Nice behavioral authority | `.project/contracts/adoption.yaml` |
| Deploy the bundled brain | `docs/guides/bundled-brain.md` |

<!-- NOTE: the vefr row sits after "Validate a pack" because it is the
     CLI map of the table; the two old-CLI mentions were rewritten in
     place (repo-is bullet + CLI references block) rather than deleted,
     since both names still work as aliases. -->

## What this repo is

- **The engine only** ("the bones"): FastAPI + any OpenAI-compatible LLM backend. MPL-2.0-licensed.
- One front door: `vefr` (its verbs in journey order, `--help` is canonical). The two old CLIs, `ratatoskr` (ops: skipa, test, weave, ferry, volumes, spark) and `norns` (craft: chat, validate, migrate, build-map, delve, verify, handbok, doctor, storyteller-test, storyteller-benchmark), keep working as aliases.
- `worlds/sample-world/` (Emberfield) ships with the engine — the demo pack.
- `worlds/lore/<flavor>/` packs are data-only mood-boards (CC BY-SA 4.0).

## What this repo isn't

- **The game.** The engine is the bones; the author's story is the flesh, kept in a separate private pack repo. Any non-shipped pack under `worlds/` is gitignored. The engine must never re-learn a game's name.
- Multi-backend tied: llama.cpp preferred, Ollama fallback. Structured output only.
- **Not a home for predecessor-engine identity.** Historical rewritten-engine lineage may exist in another repository, but that ancestry is provenance only. Current games stay separate from VEFR and use the pack contract. Never infer a game's lifecycle from engine consolidation. The engine tree remains game-name-neutral (`tests/test_pack_neutrality.py`); named provenance belongs in `.project/DECISIONS.md`.

## Directory map

| Path | Purpose |
|---|---|
| `src/vefr/` | The engine. `world.py` is the only seam between engine + story |
| `web/` | The studio workshop (`app.html`, `studio.css`, `app.js`; `state.js` is the one client state), the woven player (`packaged.html`, GENERATED from `web/player/parts/` and never committed: edit a part; the file is built where it is read - the weaver, `tests/conftest.py`, the hatch build hook for the wheel - or by `uv run python scripts/build_player.py`), art (`web/art/`), the studio shelf (`web/library/`) |
| `worlds/sample-world/` | Playable demo pack, acts shape, validates green |
| `worlds/lore/` | Three lore packs (norse, historical-event, norse-runes) |
| `tests/` | pytest suite, incl. node-vm harnesses for shipped JS |
| `.project/` | Current state, durable decisions, Play-Nice adoption pin, benchmark reports |
| `docs/guides/` | Operational guides (install, volumes, handoff, deploy, bundled-brain) |
| `scripts/` | CI helpers (public-surface guard, screenshot capture) |
| `deploy/` | Quadlet templates + startup script |
| `docs/screenshots/` | Committed screenshot gallery. CI (`screenshots.yml`) only uploads an artifact; refresh locally per `scripts/capture-screenshots.py` docstring |
| `bench/` | Model benchmarks (`bench/cli.py`); commit summaries to `bench/results/`, raw `bench/runs/*` output is gitignored. Rarely needed for engine work |
| `storyteller_packs/`, `templates/` | Tracked Storyteller packs and prompt templates (`docs/guides/storyteller-packs.md`) |
| `design/` | Design mockups, tokens, owner art (23 MB). Open for UI/art work, not for engine logic |
| `experiments/` | Scratch experiments; not shipped, excluded from the image |
| `data/` | Runtime state dir. A few tracked snapshot files predate the ignore rules (see Boundaries) — never add more |
| `.kilo/kilo.jsonc`, `.gitea/workflows/` | Kilo agent config (loads this file) and the legacy Gitea CI mirror |

## Bones and flesh

The engine and the story are kept apart. The engine ("the bones") owns
the common machinery; the pack ("the flesh") owns every character, place,
map, picture and rule that belongs to one story. Packs live in
`worlds/<name>/` and are loaded through the one seam, `world.py`.

```
src/vefr/           the engine (MPL-2.0)
  world.py          the pack loader - the only seam
  saga.py           the storytelling layer (prompts, voices, ledger)
  generator.py      rumor cards (speaker, whisper, is_true)
  main.py           the FastAPI surface the README's run command serves
  cli.py            one front door (`vefr`) plus the two aliases
                    (`ratatoskr`, `norns`)
  maplab.py         the one validator, shared by tests and both CLIs
  ...               forge, stefna, npc, combat, bonds, journey, runes, pool,
                    weave, trace, sessions, starred, chat, inspect, volumes,
                    lore, journal, export, delve, sections, shapes, stamps -
                    each module's docstring says what it is

worlds/<name>/     a world pack - a story
  world.json        phases, tones, voices, bonds, speakers, the town
  logbok.md         the world logbok - canon + style contract
  ledger.md         collected whispers - voice anchors, hand-curated
  map.md            the story's geometry, source of truth
  voices/*.md       how each character speaks (rules for the model)

worlds/sample-world/  Emberfield, the example world (CC0 1.0, so it can
                      be shared freely)
worlds/lore/<flavor>/ data-only mood boards: norse, historical-event,
                      norse-runes (CC BY-SA 4.0)

web/                the studio workshop (app.html + studio.css + app.js),
                    the woven player (packaged.html, GENERATED from
                    web/player/parts/ and never committed - built where it
                    is read by vefr.player_build), studio
                    art (web/art/), the studio's own Library shelf
                    (web/library/)
tests/              pytest - pack contract, schemas, fallbacks; browser
                    tests in tests/browser/; the player-build guard in
                    tests/test_player_build.py
```

The only world pack tracked in this repo is the sample. Real games keep
their packs in their own repositories and are placed in `worlds/<name>/`
locally. `VEFR_WORLD=<name>` selects the world; restart the engine after
adding one. Work on the engine here, and write the game there.

### What the engine may read

The engine never contains story. This is the whole contract:

| The engine reads | The engine never reads |
| --- | --- |
| `world.json` keys: title, phases, surface, voices, bonds, acts | the *names* of any specific pack's NPCs, places, or prose |
| `map.md` (geography only - the geometry, not the names) | sample text from any specific pack |
| `voices/*.md` (the rule shape, not the words) | a specific pack's characters or flavour text |
| pack-name only as an identifier for routes + filenames | anything about a game it was not handed |

If a specific game's names or text appear inside the engine source, that
is a bug: the engine should know nothing about any game until a pack is
loaded. `tests/test_pack_neutrality.py` enforces it.

### The three levels

One creator vocabulary at three levels:

- the **game** owns its characters, maps, art, story and one-off rules;
- a **gameplay feature** is a reusable way to play - turns, dialogue,
  detection, scoring (game developers also call this a gameplay system or
  a mechanic);
- the **VEFR core** owns the small common machinery those features need:
  things, places, state, rules, input, presentation, audio, saves.

A game-specific need stays in the game. A reusable gameplay feature is
promoted only after real games prove the same need. Core changes are
rarer still. These are logical boundaries, not a plugin framework or a
second language: games and features use the same public VEFR surface. See
`docs/guides/gameplay-features.md` and `docs/adr/0012-gameplay-features.md`.

### Pack design knobs

Each world decides how much the numbers matter. Every act declares a
`floor`:

- `costume` (the default): health is shown as a number but never drops to
  zero. Decoration.
- `story`: failing changes what happens in the story.
- `stakes`: the numbers really count; the act's ruleset says how.

Under the default, nothing blocks the player on health or dice: items
can't be lost, and characters always have something to say.

`world.json` can set a `surface`: `combat` (the default), `investigation`
or `plain`. It only changes what the player sees (health bars, encounter
prompts, investigation dice), not how the engine behaves. A pack that
wants no health or dice at all sets `surface: "plain"`, and the player
hides those panels.

The story structure follows the Hero's Journey through four phases:

| Phase | Journey stage | Rune |
|---|---|---|
| `whispers` | the call to adventure | **Fehu** (wealth, the seed-fire) |
| `doubts` | the refusal / the threshold | **Thurisaz** (the thorn) |
| `feared` | the tests, allies, enemies | **Kenaz** (the torch) |
| `awed` | the revelation / the return | **Sowilo** (the sun) |

Packs can rename the phases; the engine matches them by order. Each
phase's rune rides in the model's prompts to set the mood, but phases
never block the player.

**What's random.** Everything is predictable (packs, lore, journal,
export) except the rune cast. The same seed gives the same cast for about
a minute, and a cast is never repeated across sessions. Full
architecture: `docs/guides/brain-socket.md` (provider vs. brain) and
`docs/guides/bundled-brain.md` (the bundled model fleet).

Which kind of game each act plays (cooking, the newsroom desk) and the
fields that control it are in `docs/guides/rulesets.md`. Author grammars
(whispers, names, weather, expanded offline with no model) are in
`docs/guides/grammars.md`.

### Lore packs

`worlds/lore/<name>/` holds mood boards made of data:

| File | Engine reads? | Author reads? |
|---|---|---|
| `textures.md`, `names.md`, `questions.md` | yes | yes |
| `cards.md` (optional, e.g. norse-runes) | yes | yes |
| `prompt.md` | no | **yes** (copy-paste into any LLM) |
| `LICENSE.md` | no | yes (CC BY-SA 4.0 + attributions) |

`POST /api/builder/lore` takes a pack name and seed words and answers with
`textures`, `names` and `questions`. They are for mood, not canon;
`vefr chat` uses them in its interview. To add your own, make
`worlds/lore/<your-flavor>/` and write the files - the engine finds it
automatically. `docs/guides/lore.md` is the full guide.

### The studio

> *The loom is strung; the world provides the thread.*

**VEFR is also the game of making a game.** You start with an empty table
in a studio run by the old Norse, inside the World Tree, and a few words
about what you want to make. Each room is a department with a resident
who helps with that one piece: the Desk holds your pitch, the Map Room
draws the first place, the Folks introduce the people who live there, the
Library keeps your books, the Vault forges what you carry. They suggest;
you decide. At the end you have a game you made yourself, one file that
opens in any browser with no server and no model, and you understand it,
because you were there for every piece.

Every room is in `docs/screenshots/README.md` (one shot per room, and the
phone shots); `docs/guides/journey.md` is the same path written as stops
with the rules for agents; `docs/guides/residents.md` names the residents.

**The woven file.** `vefr weave` opens on a title screen with the world's
title picture, name and tagline, and a Begin button. The game fills the
screen, with speech, choices and health drawn over it and a pause menu
(`Esc`) for the journal. Everything the world needs is inside the file.
Walking into an enemy is the attack, and the first fight of a game says
so once ("Walk into an enemy to strike it."); a pack names its own words
for it in `player_words`.
In a region that declares fog, press `O` or tap **Explore** to walk to
the nearest unexplored ground; the walk stops on its own when a monster
comes into the light, the hero is wounded, or there is nothing left to
see. A carried torch widens that circle for a few turns; a chalked map
lays the whole place open. The dark is the pack's to set: press `V`, or
use Display in the pause menu, to see the whole map. In a fight, the
verbs answer `1`, `2` and `3` (each prints its own digit), the focus
stays on the verb you last used, and the result line says in one plain
sentence what the action did. Models help while
you make the game, in the studio; the finished file is complete on its own
(`docs/adr/0003-models-in-the-studio.md`). A game can still offer players
an optional model of their own for fresh lines.

**Accessibility.** The Boiler Room sets contrast (Warm & Easy, Bright &
Clear, Nothing Hides), the reading font (Atkinson Hyperlegible Next,
OpenDyslexic, a serif, or the system font), motion and sound. In the
studio nothing moves or makes a sound unless it is turned on. A woven
game that declares `sound` plays its soft cues by default and has a Sound
switch in Menu > Display. Fonts are SIL OFL and self-hosted in
`web/fonts/`. The pattern is credited to Fluid Infusion's UI Options.
`docs/guides/accessibility-contract.md` is the contract every screen
follows.

## Running it: container, compose, deploy

```sh
# from a checkout, build the image
mkdir -p ~/vefr-data
podman build -t localhost/vefr:latest .

# run it, with your own pack mounted in
podman run -d --name vefr -p 8820:8820 \
  -v ~/vefr-data:/app/data \
  -v /path/to/your-pack:/app/worlds/your-name:Z \
  -e VEFR_WORLD=your-name \
  -e VEFR_LLAMACPP_URL=http://host.docker.internal:8084 \
  localhost/vefr:latest

# compose: `compose.yml` is tracked, `compose.dev.yaml` is the dev override
podman compose up -d
```

`compose.yml` pulls `${VEFR_IMAGE:-ghcr.io/rylee-bee/vefr:latest}`. The
image is published to `ghcr.io/rylee-bee/vefr`; `:latest` moves with
every successful publish and `:sha-<full SHA>` never changes. The image
holds the engine, the studio, the sample world and a small model fleet
(`docs/guides/bundled-brain.md`). Whether a given tag exists right now is
a question for the registry, not for this tree.

Config comes from plain process env vars, never from a file the engine
reads: copy `example.env` to `.env`, fill it in, then
`set -a; source .env; set +a`. The full table is in `GETTING_STARTED.md`.

Deploying to a host is an **ask first** action
(`docs/guides/deploy.md`, `deploy/`):

```sh
uv run vefr ferry deploy --init     # writes deploy.toml.example
cp deploy.toml.example deploy.toml   # edit host + image
uv run vefr ferry deploy            # pre-flight, build, restart, verify
```

`deploy.toml` is gitignored; `deploy.toml.example` is the tracked template.

**Released demo files** (release-asset URLs as recorded in the README
before 2026-10-09; a checkout cannot prove a release exists, so check the
releases page before sharing either link): Emberfield, the sample world
woven with the storybook player, as a single asset in v2.1.0; and Burrito
Journalism, a journalism and taqueria game, as a single asset in v2.0.0
(built with `ratatoskr weave --pool 5`, CC BY 4.0 pack, MPL-2.0 engine).

## Project identity

This repository adopts [Play-Nice Contracts](https://github.com/rylee-bee-labs/play-nice-contracts)
as its shared working rules: evidence before generating content,
explicit state, asking instead of guessing, and minimum accessibility
standards. See `.project/contracts/adoption.yaml` for the adoption
record.

The engine/game boundary is fixed: VEFR is the engine/studio. Games stay
separate game projects and repositories that VEFR loads through the
world-pack contract. Historical predecessor-engine lineage does not make
a game a predecessor, and engine consolidation does not retire a game.
`.project/DECISIONS.md` (2026-10-04) is the ruling; the older
"folded in as a story pack" note that used to sit above the README is
superseded by it.

CI enforces the honest-claims policy: a strong claim ships the command
that checks it. Say `UNKNOWN` when a command cannot check it.

## Attribution and licensing

- Dependencies: fastapi, uvicorn, httpx, pydantic, sqlite-vec
  (MIT/BSD-3/Apache-2.0), declared in `pyproject.toml`; their notices
  ship in the wheels.
- Model: Qwen (Apache-2.0); outputs are shaped by this repo's prompts and
  reviewed by a human before they become canon.
- Code co-written with Kilo (AI) at the author's direction.
- Ideas borrowed, with thanks, from projects we did not build on:
  OpenPixel-RPG (MIT) for the whitebox pattern (a fixed blueprint a model
  must respect); RPG-JS (MIT) for the idea that any future renderer reads
  `/api/world`; ink and inkjs (MIT) for authored branching, saved for
  later.
- Engine license: MPL-2.0 (`LICENSE`) for `src/`, `web/` (except
  `web/art/`), `tests/`, `scripts/`, `docs/`, `deploy/` and
  `Containerfile`. `worlds/sample-world/` is CC0 1.0 (see its `LICENSE`).
  Lore mood boards under `worlds/lore/` are CC BY-SA 4.0 (each pack's
  `LICENSE.md`). The workshop's studio art in `web/art/` is CC BY-SA 4.0
  (`web/art/README.md`). Any other pack dropped into `worlds/<name>/`
  locally is its own author's property: the engine grants no license to
  story content and carries none here.
- `THIRD_PARTY_NOTICES.md` has the bundled web fonts (SIL OFL 1.1) and
  dependency notices. `TRADEMARKS.md` has fork-naming guidance -
  project-identity rules are descriptive, not a legal grant.
- `CODE_OF_CONDUCT.md` is the conduct code; `SECURITY.md` is the private
  reporting path.

```bash
# The gate — run before claiming anything is done (mirrors ci.yml)
uv sync --group test
scripts/check             # one runner for the gate below: --fast (pre-push), --full, --list, --merge-ready. A tool it has no binary for is SKIPped, not passed: read the SKIP lines, CI decides
npm ci                    # jsdom for the node-vm harnesses; without it pytest errors
uv run --group test ruff check src tests scripts
uv run --group test pytest -q
bash tests/run.sh tests/test_x.py   # same, built for a throwaway clone (offload worker/foreman): links node_modules, offline, no foreign venv
uv run --group test norns validate --pack worlds/sample-world
python3 scripts/check_public_surface.py   # public-surface guard: catches private data in tracked files

# PR-only extras (dev-guards.yml): browser tests need Playwright chromium
uv run playwright install chromium   # once
VEFR_BROWSER_REQUIRED=1 uv run pytest -q tests/browser

# Static guards, same job (config lives in pyproject.toml)
uv tool run vulture        # dead code
uv tool run deptry .       # dependency hygiene
# CI-only too: lychee (offline link check) and Vale (prose, advisory)

# Session-start health
uv run --group test norns doctor

# CLI references (--help prints the live, complete command list)
uv run vefr --help        # the front door: every verb, journey order
uv run ratatoskr --help   # the old ops CLI, still an alias
uv run norns --help       # the old craft CLI, still an alias

# The player: web/packaged.html is GENERATED from web/player/parts/ and never committed
# (vefr#523). Edit a part; the file is built where it is read - the weaver, tests/conftest.py,
# the wheel - and --check says whether the parts build. weave_digest.py proves byte-equality
uv run python scripts/build_player.py
uv run python scripts/build_player.py --check
uv run python scripts/weave_digest.py

# A PR labelled `refactor` claims its player changes moved no byte (vefr#529). CI passes that
# label down as VEFR_REFACTOR=1 and tests/weave_digest.py then weaves the merge base
# (`git merge-base HEAD origin/main`) in a temp worktree and compares. Nothing is committed for
# it, so two player PRs cannot collide on a digest line - that is the whole point. Run it
# locally the same way; without an origin/main to measure against it skips, with the reason
VEFR_REFACTOR=1 uv run --group test pytest -q tests/test_skin_validator.py

# Validate a world pack
uv run norns validate --pack worlds/<name>

# Run the engine locally
uv run uvicorn vefr.main:app --app-dir src --port 8820

# Package a single shareable HTML file
uv run ratatoskr weave --pool 5
```

## Boundaries

| Severity | Rule |
|---|---|
| **Always** | The gate above green before claiming done (matches CI). Paste the exact command + output. |
| **Always** | Every UI change answers the accessibility matrix: ≥44px targets, luminance over hue, motion off, keyboard + SR accessible. |
| **Always** | `norns validate` after any world-pack write. Never trust a hand edit. |
| **Always** | No model calls in deterministic surfaces: `export.py`, `weave.py`, `maplab.py`, `journal.py`, `blueprint.py`. |
| **Always** | One ROADMAP.md entry per landed change. Keep README/GETTING_STARTED in sync. |
| **Ask first** | Changing the pack contract, adding a tracked world pack, or a new public API route. |
| **Ask first** | Deploys (`ratatoskr ferry`, `deploy/`, `docs/guides/deploy.md`) and anything under CODEOWNERS (`scripts/`, `.github/workflows/`, licensing, `.gitleaks.toml`). |
| **Never** | Commit story content from a private pack, or name any specific game in engine code. |
| **Never** | Commit runtime state (sessions, vaults, journals, weave logs). Tracked runtime files already exist: `data/interface.jsonl`, `data/storyteller.jsonl`, `data/lore/` (snapshot commit `50a9fad`, now gitignored) and `data/vault.json` (committed with `7c74190`, not ignored). Untracking them is an owner call; don't refresh or stage them. |
| **Never** | Hand-edit `uv.lock` or drop `strict: true` on schema-constrained calls. |

## Style

- Python 3.11+, hatchling, `src/` layout. Deps: fastapi, uvicorn, httpx, pydantic, sqlite-vec (the Lorekeeper's vector index) — keep it short.
- Markdown: one idea per line, prose lines short.
- JS in `web/`: no framework; `state.js` is a plain object + subscribers. Shipped JS tested via node-vm harnesses.
- Engine voice: Norse-named, story-agnostic. Game-specific names belong in packs, never here.
- Branch model: `main` ← PR ← `feat/*`.
- CI runs on every PR: lint+test+validate+public-surface guard
  (`ci.yml`), secret scan (`secret-scan.yml`), and the tooling
  guards (`dev-guards.yml`).
- `security.yml` is **not** an intake path. It is a
  `workflow_dispatch`-only "public-surface guard" that re-runs
  `scripts/check_public_surface.py` on demand. Advisory intake is
  GitHub private vulnerability reporting — see `SECURITY.md`.
- Image publish (`publish-image.yml`) and screenshot capture
  (`screenshots.yml`) run on push to `main`.

## Cross-repo boundaries

- **Pack contract** (`src/vefr/world.py`) is consumed by private pack repos. Changing it is "Ask first"; record the companion change for the pack instead of editing another repo.
- Rylee's personal profile and estate rules come from the global agent config (`~/.agents/AGENTS.md`); don't restate them here.

## References

| Doc | What it is |
|---|---|
| `AGENT_POLICY.md` | Agent decision kernel: preflight, DoD, evidence requirements |
| `docs/guides/world-creation.md` | World authoring: norns chat -> validate -> build-map -> weave |
| `docs/guides/grammars.md` | Author grammars: offline whispers, weather, names |
| `docs/guides/rules.md` | Author rules: the thirteen events, ids, actions, kept items |
| `docs/guides/lore.md` | The Lorekeeper: facts, the derived index, `vefr-lore` |
| `docs/uat/` | UAT contracts: a journey + machine-checkable acceptance triples |
| `README.md` | The human front door: what this is, is it running, how to use it, where to read more. Deliberately short (owner-ruled shape, 2026-10-09): agent-only detail lives here, not there. Do not grow it back - a fact added to the README needs the command that checks it. |
| `CONTRIBUTING.md` | How to contribute (human + agent onboarding) |
| `docs/guides/brain-socket.md` | Architecture: VEFR owns reality; brains plug in |
| `docs/guides/bundled-brain.md` | Bundled model fleet, ports, swap guide |
| `docs/guides/spark.md` | Spark: the resident small brain |
| `ROADMAP.md` | Landed/Next ledger |
| `GETTING_STARTED.md` | Install + first-world walkthrough |
| `src/vefr/world.py` | The pack contract (docstring) |
