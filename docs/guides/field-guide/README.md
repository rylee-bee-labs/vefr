# The Gameplay Field Guide

A card is one small, testable system.
It says what the system is, the pure step it wants, the knobs a pack turns,
a 60-second example, one test that must fail on a wrong implementation,
what accessibility asks of it, and where it comes from.
A card is not a VEFR API and not a promise that the system is built.
It is the smallest shape a second real game would have to need.

Every card has the same seven parts, in this order:
**The idea** · **Step API sketch** · **Knobs** · **A 60-second example** ·
**A must-fail test idea** · **Accessibility** · **Provenance**.

## The cards

| Card | One line |
|---|---|
| [The step loop](step-loop.md) | state + input -> new state + events, pure enough for a test to call without a browser. |
| [Seeded RNG and replay](seeded-rng-and-replay.md) | one seed and a recorded input list draw the same run every time. |
| [Map generation with fog](mapgen-with-fov.md) | rooms and corridors first, then the part of the floor the hero has seen. |
| [Ten-room delve](examples/ten-room-delve.md) | one worked walk that ties the three together: generate, see, step, replay. |

## How a card is promoted

A card follows VEFR's own promotion rule, not a new one.
The rule is in [Gameplay features](../gameplay-features.md), "Promotion rule",
and the decision is [ADR 0012](../../adr/0012-gameplay-features.md).

> Keep a mechanic in the game until a **second real game** independently needs the
> same behavior and invariants.
>
> Then promote the smallest reusable shape only when all of these are true:
>
> 1. it uses VEFR's public creator/runtime surface instead of private engine hooks;
> 2. it contains no game names, canon or special cases;
> 3. a game that does not use it behaves exactly as before;
> 4. its public surface is smaller than the implementation it replaces;
> 5. validation, tests and a small example cover the contract;
> 6. the normal repo gate is clean and the change adds no warnings.
>
> — [Gameplay features](../gameplay-features.md), quoting the rule; the decision is [ADR 0012](../../adr/0012-gameplay-features.md).

Writing a card is not promotion.
A card may be written while the mechanic still lives in one game, because the
card is how the second game's need is compared.
A card that cannot cite an implementation is marked as a gap.
A card that can cite one quotes the file and its blob sha, so the claim can be
checked with `git rev-parse HEAD:<path>`.

## Not yet carded

The research found these gaps. Each line says what exists today, not what is promised.

- **Status effects** - the woven player runs `statusTurn()` for burns, webs and
  similar states, but there is no card and no pack-facing vocabulary yet
  (`web/player/parts/425-the-elements.js:216`).
- **An input-to-verbs layer** - an act can name its own `verbs` and
  `combat.verbs_for_pack` reads them, but there is no general layer that turns
  input into a verb (`src/vefr/combat.py:70`; `src/vefr/rpg.py:267`).
- **A menu and inventory pattern** - the bag, the trade panel and the equip
  panel exist in the player, but there is no card for their shared shape
  (`web/player/parts/160-the-bag.js`, `190-the-trade-panel.js`,
  `370-engine-equip.js`).
- **JS storylets** - no storylet system is implemented in the player.
  Ink and inkjs are research only (`docs/BACKLOG.md:188`;
  `docs/research/2026-09-30-enhancement-packet.md:51`).
- **A shared replay format** - `vefr playthrough` and `scenarios/` replay a walk
  for VEFR's own tools, but no replay document is shared across games
  (`src/vefr/devtools.py:1155`; `src/vefr/scenarios.py`).

## Honest about combat

VEFR's `combat.py` is a costume, not a combat system.
HP is a per-phase display, and a combat action is a journal entry; the engine
does not have a turn system (`src/vefr/combat.py:1-31`).
No card here claims a combat loop.

## Sources and what this run could verify

The three cards cite VEFR files at blob shas produced by
`git rev-parse HEAD:<path>` in this tree at the base commit `3ed48bb7`.
Those shas are real and reproducible.

The estate repositories named in the mission - memomancer,
haunted-card-table and vibe-coder - and the 2026-10-31 research notes were not
present in this run's filesystem, and the network was closed.
No sha or path is claimed for a file this run could not read.
No game repository URL is linked: none could be verified with the network closed.
Where VEFR has no implementation, the card says so plainly.

OSS references and their licences are quoted from the repository's own research
note, `docs/research/2026-09-30-enhancement-packet.md`:
rot.js, BSD-3-Clause (`:56`, `:71`); libtcod and python-tcod, BSD-3 / BSD-2
(`:67`); Ink and inkjs, MIT (`:51`); Tracery, Apache-2.0 (`:50`);
Hypothesis, MPL-2.0 (`:55`); DeBroglie, MIT (`:94`); mapgen4, Apache-2.0 (`:98`).
