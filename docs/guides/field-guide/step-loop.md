# The step loop

One turn is one function: state + input -> new state + events.

## The idea

A game is a state machine with a face.
The state is what a reload must restore: hero tile, health, bag, explored tiles,
turn number.
The input is one action.
The events are the facts the turn produced, in the pack's own vocabulary -
`enters`, `defeats`, `picks-up`, `falls`, `wakes` and the other eleven in
`src/vefr/shapes.py:1883`.

Keep the function pure: the same state, action and random stream give the same
new state and events. No clock, no DOM, no network, no model.
Rendering and input sit outside it.
That is what lets a test call a turn without a browser, and what makes replay
mean "the same run".

VEFR has the loop but not this seam.
`move(dx, dy)` is the shipped turn
(`web/player/parts/480-town-input-and-turns.js:1477`): it faces the hero, checks
the edge, a living enemy, a web, a solid tile and a prop, moves, fires rules,
takes loot, then calls `enemyTurn()` and `statusTurn()` and draws.
The order is right; the shape is wrong for a test, because it mutates page
globals and paints.
The signature below is a card, not a landed API.

## Step API sketch

```python
from typing import Any

def step(state: dict[str, Any], action: str, rng) -> tuple[dict[str, Any], list[dict]]:
    """One turn: return a NEW state and the events it caused.

    `state` is JSON-able and belongs to the caller; the function copies it
    and never mutates it. `action` is one id from the act's verbs. `rng` is
    a seeded stream, never the global `random` module. A refused action
    returns the same state and no pack event.
    """
```

Events are data, not sentences. A rule may name only an event the pack
declares, and presentation turns it into one plain sentence.

## Knobs

- **Action vocabulary** - the act's `verbs` (`src/vefr/rpg.py:267`;
  `src/vefr/combat.py:70`) or a fixed move set.
- **What costs a turn** - `fight.turns` makes drinking, using a thing and
  casting cost a turn; the monsters answer (`docs/guides/rpg-core.md:36`).
- **Refusal** - a wall refuses, a living enemy is a bump attack, a solid person
  blocks, a shut door says its line
  (`web/player/parts/480-town-input-and-turns.js:1527-1539`).
- **What is state** - hero, health, bag, explored tiles, turn; floor rows come
  from the seed.
- **Event order** - a list, because replay compares it.
- **Batch or single** - one action per call; a batch is a fold.

## A 60-second example

The floor is [Ten-room delve](examples/ten-room-delve.md); the hero starts on
the up-stair at `(25, 13)`.

```python
state = {"hero": [25, 13], "turn": 0}
for action in ["right", "right", "right", "up", "up"]:
    state, events = step(state, action, rng)
# hero is [28, 11]; each call returned a new dict
```

The next `up` is a wall at `(28, 10)`: the state is unchanged and no pack event
is emitted. The shipped `move()` makes the same distinction, but returns
nothing and draws.

## A must-fail test idea

```python
before = copy.deepcopy(state)
after, events = step(state, "up", rng)
assert after["turn"] == before["turn"]
assert events == []
assert state == before          # the caller's state was not touched
assert after is not state
```

An implementation that advances the turn before checking the wall fails the
first assert. One that mutates `state["hero"]` in place fails the third: the
snapshot changes and the next call starts from a different state.
That is the common purity bug in a tile loop, caught without a browser.

## Accessibility

- **Keyboard** - every action has a key. The player uses arrows or WASD, and
  `1`, `2`, `3` for fight verbs; each verb prints its own digit
  (`AGENTS.md:250-252`).
- **Screen reader** - an event must have a plain sentence. "You miss the rat."
  is a result; a sprite that moved is not (`docs/guides/rpg-core.md:34`).
- **Low motion** - the step tween is decoration. The state is settled before
  the hop starts and the turn is never gated on animation
  (`web/player/parts/480-town-input-and-turns.js:1549`); reduced motion stops
  the tween (`:58`).
- **Meaning in words** - a refused step says why: the edge, the wall, the shut
  door, the person in the way.
- The wider contract is 44px targets, full keyboard traversal and nothing
  relying on colour alone (`docs/guides/accessibility-contract.md:160-161`).

## Provenance

- Shipped turn: `web/player/parts/480-town-input-and-turns.js` @
  `ec9a7f6c6370aeb3ed8767b5ee7619c2647f1b43` (`move` `:1477`, reduced motion
  `:58`, state settled before the tween `:1549`).
- Enemy turn: `web/player/parts/430-loot-on-the-floor.js` @
  `a0ad1068f185b156968c9d3ef7605a9a883e74e6` (`enemyTurn` `:751`).
- Status turn: `web/player/parts/425-the-elements.js` @
  `21573dc8abd74b7163e83e91fd2c291160d7ba2d` (`statusTurn` `:216`).
- Events: `src/vefr/shapes.py` @
  `ef1058511ffaeb32deba3f6121ff859e9fac588b` (`EVENTS` `:1883`).
- Verbs: `src/vefr/rpg.py` @
  `2c38a79c3751f824725a04e23c339ed1812d7b62` (`verb_ids` `:267`);
  `src/vefr/combat.py` @
  `5c227d7c3b3eb2e8e2d3c9ae2fd563432def01f4` (`verbs_for_pack` `:70`).
- The loop, end to end and pinned: `tests/test_combat_loop.py` @
  `2936e56f340ef05dce8e6c2e8e123bd4871c3bf9` (`:11-12`).
- OSS: rot.js, BSD-3-Clause, for turn scheduling
  (`docs/research/2026-09-30-enhancement-packet.md:56`); Ink and inkjs, MIT
  (`:51`).
- No pure `step(state, action)` exists in VEFR today. Two estate games have one:
  vibe-coder `src/logic/game.js` @
  `367bc5d9013e122e50a8970984eec60d2deb75c1` (`step(prev, a)` `:73`, a pure
  reducer over state and one verb), and haunted-card-table `src/rules/game.js`
  @ `ca89ed989c8829ae728b5764243a732864fd097b`, where `play(g, m)` at `:15`
  returns a new game and `replay(cfg, moves)` at `:10` rebuilds any position
  from its move list.
- Those two repositories are private estate projects, so the citation is the
  path and sha, not a URL.
