# Seeded RNG and replay

One seed and a recorded input list draw the same run every time.

## The idea

A run is a pure function of a seed plus an input list.
If every draw comes from a seeded stream, the same seed and inputs give the same
floor, drops, fight rolls and words.
Replay is then a test, a bug report and a shareable text, not a video.

VEFR already does this in the Python engine.
`delve.prng(seed)` is xmur3 (a string hashed to 32 bits) feeding mulberry32
(a 32-bit state to a float in `[0, 1)`), using only 32-bit integer maths so a
JavaScript twin gives the identical stream (`src/vefr/delve.py:109-137`).
`tests/test_delve_prng.py` pins six floats per seed against an independent
JavaScript reference, not this repo's own code (`:12-29`).

Seeds are named, not global.
A floor key is `run_seed/section/cycle/k` (`floor_key`, `:661`).
Each stage gets its own stream, `v3|<floor key>|<stream>`
(`stream_seed`, `:666`), so changing loot cannot move a wall.
Loot, chests and each drawn item get their own sub-stream
(`:676-696`).
`floor_plan` states the reason: "three streams that never share a draw"
(`:1535-1541`).
The public rule is the same: "Rolls come from a named, seeded stream"
(`docs/guides/rpg-core.md:35`).

Replay today is a driver, not a shared file format.
`vefr playthrough` reads a plan off the pack and plays it
(`src/vefr/devtools.py:850`, `:1155`); `tests/play_kit.play(html, spec)` runs a
spec of keypresses and returns JSON (`tests/play_kit.py:101`); `scenarios/*.json`
opens a named state (`src/vefr/scenarios.py`).
No replay document is shared across games yet.

## Step API sketch

```python
def replay(seed: str, inputs: list[str], step) -> dict:
    """Fold inputs over step from one seed and return a canonical log."""
    rng = prng(seed)
    state = new_run(seed)
    log = []
    for action in inputs:
        state, events = step(state, action, rng)
        log.append({"action": action, "state": state, "events": events})
    return {"seed": seed, "inputs": inputs, "final": state, "log": log}
```

A replay is `(seed, inputs)` plus the generator version.
VEFR carries that version in a floor's identity triple, `{'gen', 'hash', 'key'}`
(`src/vefr/delve.py:1579-1581`).
Without it, a generator change silently turns an old replay into a different
run.

## Knobs

- **Seed form** - a name (`"ten-room-delve"`) is easier to read and share than a
  number; the base run seed and run index are separate (`run_seed`, `:699`).
- **Draw order** - changing it redraws every floor. A real case is recorded in
  `tests/browser/test_turn_budget.py:80-87`: a floor-key change redrew every
  floor, and a seed that used to reach the monster cap no longer did.
- **What is saved** - seed plus deltas, or the whole state. VEFR keeps explored
  fog, drops and secrets per floor and regenerates the rows from the key
  (`tests/test_descent_deltas.py:213-224`).
- **Input vocabulary** - key names or action ids; one is stable across
  keyboards, the other across games.
- **A refusal** - log it as its own line with no state change, so the replay
  proves the refusal.
- **RNG family** - `random.Random` for a Python-only surface
  (`grammar.expand_seeded`, `src/vefr/grammar.py:111`), `prng` when a JS twin
  must match.

## A 60-second example

```python
from vefr import delve
rng = delve.prng("cottage")
print([rng() for _ in range(6)])
# [0.13393288478255272, 0.3199043916538358, 0.08566394122317433,
#  0.4837643166538328, 0.31890994450077415, 0.979176236083731]
```

Those are the pinned reference values in `tests/test_delve_prng.py:13-14`.

```python
delve.floor_key("ten-room-delve", "cellar", 0, 1)
# 'ten-room-delve/cellar/0/1'
delve.stream_seed("ten-room-delve/cellar/0/1", "layout")
# 'v3|ten-room-delve/cellar/0/1|layout'
```

Call `generate_floor_v2("ten-room-delve", 40, 16, 10)` twice: the rows are equal
(real output in [Ten-room delve](examples/ten-room-delve.md)).
Change one input, not the seed, and the walk ends elsewhere; the seed alone is
not the run.

## A must-fail test idea

```python
one = replay("ten-room-delve", ["right", "right", "up"], step)
two = replay("ten-room-delve", ["right", "right", "up"], step)
assert one == two
assert one["final"] != one["log"][0]["state"]   # the run actually moved
```

An implementation that calls `random.random()`, reads `time.time()`, or walks a
`set` whose order varies fails the first assert: the second log differs.
An implementation that refuses every input is trivially stable, so the second
assert makes it fail.
The narrower guard is the pinned float test: a wrong hash, such as Python's
`hash()` or `random.seed`, returns different floats on the first line.

## Accessibility

- **Text first** - a seed must be readable, copyable and typeable, not only a
  generated button. A replay is a list of named actions in words, which a
  screen reader can read and a keyboard can re-enter.
- **No timing** - replay must not depend on animation frames. VEFR settles the
  state before the hop and never gates the turn on animation
  (`web/player/parts/480-town-input-and-turns.js:1549`).
- **Low motion** - a replay viewer can step one action at a time with motion
  off; the log is the content.
- **Meaning in words** - the log says "moved to 28,12" or "the way is blocked",
  not only a digest. A digest proves equality; it does not explain the run.
- **Keyboard** - a replay is entered with the same keys as play and inherits the
  player's keyboard map and 44px targets
  (`docs/guides/accessibility-contract.md:160-161`).

## Provenance

- `src/vefr/delve.py` @ `b998b53168b18786bb0856e1c7d090af82a575da`
  (`prng` `:109`; `generate_floor_v2` `:393`; `floor_key` `:661`;
  `stream_seed` `:666`; `run_seed` `:699`; identity `:1579-1581`).
- `tests/test_delve_prng.py` @
  `c993716d334adb06d02a7a7bafaf292170b41fe5` (pinned floats `:12-23`, test
  `:26`).
- `src/vefr/grammar.py` @ `6ea17cf6a97622cdb75f0d586320ecefdea7e6c9`
  (`expand_seeded` `:111`).
- `src/vefr/devtools.py` @ `1d73d6d5abe46e31ab5f821f1c80cf5fbdfd87e5`
  (`playthrough_plan` `:850`; `playthrough` `:1155`).
- `tests/play_kit.py` @ `85a87719dca6af474c219b38a9a39285149c7154`
  (`play` `:101`).
- `src/vefr/scenarios.py` @ `647faf3d802e4ff6a73df84fc937698759e07f5a`.
- `tests/test_descent_deltas.py` @
  `d0a4737f7256462607c09c41fce9541f1f3f6d7a` (`:213-224`).
- OSS: xmur3 and mulberry32 are named "standard public-domain" in
  `tests/test_delve_prng.py:5-6`; rot.js is BSD-3-Clause
  (`docs/research/2026-09-30-enhancement-packet.md:56`); DeBroglie is MIT
  (`:94`).
- memomancer `src/core/rng.ts` @ `c9ed5ad1cc1596df1f86a45b0d78d8d5946c8729`
  (46 lines: `mulberry32` `:6`, `hashStr` `:16`, `intBetween` `:25`,
  `shuffled` `:31`, `weighted` `:41`) is the estate's smallest seeded stream:
  one function of a number, threaded through state instead of a global.
- haunted-card-table `src/rules/game.js` @
  `ca89ed989c8829ae728b5764243a732864fd097b` keeps a run as its move list and
  rebuilds it with `replay(cfg, moves)` at `:10` - replay as data, not as a
  recording.
- memomancer and haunted-card-table are private estate repositories, so the
  citation is the path and sha, not a URL.
