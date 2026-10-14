# Agent Player Lab: the P4 spike of #317

A model plays a woven VEFR game the way a person does: it sees the screen and
the text a screen reader would read, picks one action from a closed list, and
that action is pressed as real keys. It writes a journal, and the run ends in
an evidence-first playtest report.

This is an **experiment**, not the Player Driver. It is slice P4 ("model
adapter") of [#317](https://github.com/rylee-bee-labs/vefr/issues/317) run
early, before P1 exists, to learn what an agent player actually needs. See ADR
0016 and `docs/plans/player-driver/PLAN.md`; the first proving game has its own pilot issue.
It changes nothing in `src/`, `web/` or any pack.

| File | What it is |
|---|---|
| `apl.py` | action vocabulary, player observation, the loop, policies, leak audit |
| `play.py` | one run: weave, open, play, write the evidence and `report.md` |
| `replay.py` | press a run's keys again with no model and report the first divergence |
| `profiles/curious-explorer.md` | the player's instructions (`{game}` is the pack's title) |
| `test_agent_player.py` | actions, limits, stop rules, leakage (36 tests) |

## What the agent may see

**Player** (the prompt): a 640x360 JPEG of the screen, the page's ARIA snapshot
(`locator.aria_snapshot()`: hidden and `display:none` content is left out,
screen-reader-only text is kept), which control has keyboard focus (a sighted
player sees the ring; the snapshot doesn't say), the result of its last action ("nothing
visible changed" and so on), its own journal and its last six actions.

**Never in a prompt:** `window.VEFR_*` globals, maps, flags, book text it hasn't
opened, the route. The player path makes no script calls into the page
(`test_player_observation_never_runs_page_script` checks the code with `ast`).
**QA** state (`VEFR_COMBAT` region, tile and HP) is read separately into `qa.jsonl`
for evidence and replay, and is never fed back.

`--canary` plants a window global, a `hidden` node and a `display:none` node.
After the run, the book pages from every place the hero never reached are
collected (QA side). If any of these turns up in `prompts.jsonl`, the run fails.

## Actions

`move` (dir, 1 to 5 steps), `interact` (F), `talk` (E), `whisper` (Q), `bag` (B),
`explore` (O), `confirm` (Enter), `back` (Escape), `next_control` (Tab), `wait`,
`finish` (reason). Anything else is refused and logged. Two refusals in a row
end the run.

These are the keys the woven player's own buttons advertise. When P1 lands,
this list should shrink into P1's logical vocabulary, not compete with it.

## Limits and stop rules

50 decisions, 150 key inputs (a move that would pass the cap is cut short and
marked `truncated`), 20 min, 400k input tokens. A page error stops the run.
Eight decisions in a row that change nothing visible stop it too. That stop is
recorded as player evidence (walking into a wall is a finding), not as a
harness failure. The agent may `finish` early with a reason.

After each action the harness waits until the on-screen text stops changing,
as a person would. Explore walks on a timer (`490-autoexplore.js`), so a fixed
wait would make results depend on model latency.

## Evidence (one run directory)

`run.json` (build identity: vefr and pack SHAs and dirty counts, woven sha256,
Chromium; model, provider, measured tokens and latency, stop reason, leak
audit, vision check), `trace.jsonl` (player: action, keys, result, new
on-screen text, digests, timing), `prompts.jsonl` (exactly what the model got,
minus the image bytes), `qa.jsonl` (QA only), `shots/`, `report.md`.

Run directories hold model output and screenshots. Keep them **outside this
checkout** and don't commit them.

## Run it

```bash
uv sync --group test
PACK=../<pack repo>/worlds/<pack>
# APL_CHROMIUM=/path/to/chromium   if Playwright's own browser is not installed

# A. tests (no model, no cost)
uv run --group test pytest experiments/agent-player -q
# B. plumbing dry run: seeded random policy, no model
uv run --group test python experiments/agent-player/play.py --pack "$PACK" \
  --policy random --seed apl-1 --canary --out /tmp/apl/dry
# C. a real session, with a provider already in ~/.config/opencode/opencode.json
#    (the same file bench/design/run.py reads). It checks that the browser draws text (no fonts = blank screenshots, exit 4), then the image check,
#    or use --text-only and say so.
#    Models that think inline (`<think>`) need --max-reply-tokens room (default 4000).
uv run --group test python experiments/agent-player/play.py --pack "$PACK" \
  --policy model --provider opencode:<name> --model <model id> \
  --profile curious-explorer --seed apl-1 --canary --out /tmp/apl/run-001
# D. replay the key tape (same timing as the run; --fast ignores timing)
uv run --group test python experiments/agent-player/replay.py /tmp/apl/run-001
# E. another game
uv run --group test python experiments/agent-player/play.py --pack worlds/sample-world \
  --policy random --max-actions 20 --canary --out /tmp/apl/sample
```

## Replay: what holds and what doesn't

Floors use `?vefr-seed=`. The harness also seeds `Math.random`, so line picks
repeat (`270-the-woven-pool.js`, `280-the-local-composer.js`). Keys go back in at
their recorded time offsets because some UI runs on real time.

What still varies: the message panel folds after 6 s on a timer
(`110-the-library.js`). A step that lands within a fraction of a second of that
fold can flip between runs. That's why exact pixels match less often than the
on-screen text, which in turn matches less often than the QA hero position.
`replay.py` reports all three and saves the first text divergence.

This is a key tape, not #317's Action Tape: it reproduces a run, it can't
continue a save.
