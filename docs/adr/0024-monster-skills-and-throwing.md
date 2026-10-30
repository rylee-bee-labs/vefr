# 0024 - Monster skills and throwing

Date: 2026-10-30

## Status

**Accepted direction; implemented in one PR.** After her Gate 0 run of the
Cottage 1.0 build the owner said: "The mobs also need skills. And I guess we
need ranged attacks?" From the options offered she picked, in their words:
"Spider: web + spit", "Rat: festering bite", "Moth: dust", "Fat rat: squeal
for help" and "Throw things", after "Show it" (ADR 0023). That pick is the
ask-first answer for the two pack-contract keys below. The numbers (ranges,
waits, chances, defaults), the words each skill says, and that a thrown thing
lands where it struck are Claude's calls, named as such.

**Every key is opt-in.** A family with no `skills` and an item with no
`throw` bake and play exactly as before.

## Context

Every monster did one thing: walk up and bite for its `atk`. A spider and a
rat differed only in two numbers, and nothing reached the hero from more than
one tile away, in either direction.

Found on the way: a generated floor's enemy entry (`enemyEntry` in part 397)
dropped the `guard` and `gold` the plan had drawn for each monster (ADR
0021). On a generated floor, armour on a monster was never felt and its coins
were never paid. A real game's cellar showed it: every rat and moth planned
gold, and every enemy entry lacked it.

## Decision

**`skills`**, on a Blueprint family's `defaults` or a hand-placed enemy: a
list of up to two records, each one of a closed set, every number bounded and
defaulted (`rpg.SKILL_KINDS`, twinned as `RPG_SKILL_KINDS` in part 226):

- `web`: from up to `range` tiles on a clear line, once every `every` of its
  turns, instead of stepping: the hero is webbed for `turns` of their own
  turns. A webbed hero's step is a struggle that costs the turn, and a blow at
  a monster beside them is still a blow.
- `spit`: the same trigger: a hit for `harm`, rolled like a blow, which guard
  takes from.
- `fester`: on a melee blow that lands, `chance` in 100: a poison that bites
  `tick` a turn for `turns`.
- `dust`: on a melee blow that lands, `chance` in 100: the hero's blows miss
  `miss` in 100 more often for `turns` (through the fight roll, so it needs a
  `fight` block).
- `squeal`: once, the first time it is struck to half its health or below and
  still stands: every monster within `radius` tiles wakes. The default (16)
  reaches past a fight's own noise (12), which has already woken the nearer
  ones.

A clear line has no wall, prop or other monster on the tiles between. Each
chance is drawn from its own named stream (`skill|world|region|monster|skill|n`)
off the same seeded generator a blow uses, so the same moves give the same
bites. The three new states live with burning in part 425, are written on the
HUD's state line in words, and are cleared by a reload, as a burn is. A web or
dust laid in the monsters' turn is not counted down in that same turn, so
"stuck for 2 turns" is two of the hero's turns.

The descent's twins carry a family's skills onto its mobs, with defaults
filled the same way. `test_descent_parity.py` holds them to it.

**`throw`**, on an item: `{"harm": 1-20, "range": 2-8}` (range defaults to 5).
A thrown thing strikes the foe the fight row names, or the nearest one in
range on a clear line. It is rolled like a blow (a miss, a critical), guard
takes from it, and dust spoils it. It lands on the foe's tile, as the instance
it was, to be picked up again. A throw is a blow and costs the turn one costs.
A thing can be thrown:
- from the Bag;
- from the quick bar (ADR 0023: it is a quick-use thing);
- or from a `throw` verb on the fight row, which shows only while something
  that can be thrown is carried.

With nothing in reach the throw does not happen and costs nothing.

**And the fix.** `enemyEntry` carries the plan's `guard`, `gold` and `skills`.

## Consequences

- Two pack-contract keys:
  - `skills`: `blueprint.FIELD_KEYS`, a hand-placed enemy, and `rpg.skills_errors`.
  - `throw`: an item, and `rpg.item_errors`.
  - Both documented in `docs/guides/rpg-core.md`.
- Engine words. The lines each skill and a throw say ("an ember hound throws a web over you: you are stuck for 2 turns.") are engine defaults. A pack cannot yet name its own words for them.
- Not in this change:
  - skills on a warden's own record beyond what its family carries;
  - a skill a hero can learn;
  - a status that stacks;
  - any skill outside the five.

## Acceptance

`tests/test_monster_skills.py`, `tests/test_monster_skills_play.py`,
`tests/test_descent_parity.py` and the full gate.
