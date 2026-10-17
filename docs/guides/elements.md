# Damage types, resistances and burning

A pack may opt in to typed damage. It is optional in the strict sense: a pack that declares none of
it deals the same untyped blows, keeps the same numbers and saves exactly what it saved before.
Nothing here changes another pack's balance.

This is slice 1 of `design/elemental-and-status-effects.md` (vefr#497): the resolver, the hero's
own resistances, and **burning** as the one status effect. What is *not* in it yet is listed at the
bottom.

## The words, kept apart

| Word | Means |
|---|---|
| **damage type** | what the damage is: `physical`, `fire`, `cold`, `lightning`, `poison`, `necrotic`, `acid`, `radiant`, `psychic`, `thunder` |
| **status effect** | the state left on a combatant: today only `burning` |
| **resistance / immunity** | what the target does about a type |

The list of types is closed, so "fiery" and "fire" cannot become two different mechanics.

## What the hero shrugs off

Both keys go on the pack's `player` block, and both are the floor for a whole run:

```json
"player": {
  "hp": 6, "atk": 2,
  "resist": {"fire": 2},
  "immune": ["cold"]
}
```

- `resist` is a damage type and a **whole number from 1 to 9**: the blow is divided by it, so `2`
  is half the damage. It is a divisor rather than a percentage so the numbers stay whole in both
  languages.
- `immune` is a list of damage types that cannot hurt the hero at all. Naming a type in both keys
  means immune wins.

## What a hazard deals

Two optional keys on an enemy in a region `contract.json`:

```json
{"id": "ember-hound", "name": "an ember hound", "at": [6, 3],
 "hp": 5, "atk": 2, "sight": 6,
 "dmg_type": "fire",
 "burns": {"turns": 3, "tick": 1}}
```

- `dmg_type` is the type of the blow it deals. Without it the blow is untyped, and no resistance
  can turn an untyped blow aside.
- `burns` leaves the hero **burning**: a `turns` count and a `tick` (how much, how often). Those two
  numbers are the whole of a status effect in this slice. The tick is fire damage, so the hero's
  `fire` resistance applies to it as well.

Burning is what the design note calls reversible: it is not stored. It lasts its turns, then it is
gone; a reload puts the hero back whole, and waking at the wake point or entering a new region ends
it, the way a burning light does not travel. No save changes shape, and no save written before this
slice is read wrong. A burn also never starts when the hero's resistance divides its every tick to
nothing: there is nothing left to burn with.

## What the player is told

Words, never colour alone:

- the blow itself: *an ember hound hits you with fire for 1; your resistance turns the rest aside*,
  or *... and it cannot touch you* when the type is immune, or *... and your resistance turns it
  aside* when the resistance divides the whole blow away, or the plain *a cellar rat hits you for
  2* when the pack has opted in to nothing;
- the state, on the line beside the health: **Burning (fire, 2 turns left)**, which is a
  `role="status"` region, so it is announced;
- each tick, on that same live line: *The fire takes 1 from you.* and, on the last turn, *The
  burning dies out of you.*

Nothing is a tint, an icon or a health-bar colour: the sentence and the line carry the whole of it,
which is the accessibility rule the design note names.

## Refusals

`vefr check` names each of these in one plain sentence:

- `player.resist` naming something that is not a damage type, or a divisor that is not a whole
  number from 1 to 9;
- `player.immune` that is not a list, or naming something that is not a damage type;
- an enemy `dmg_type` that is not a damage type;
- `burns` that is not an object, is missing `turns` or `tick`, holds something else, or gives a
  number under 1.

A refusal is a no-op, not a half-fire: the burn is not applied and the blow is dealt untyped.

## What is not here yet

- hazards authored in a Blueprint (`blueprint.json`): their fields are the closed `FIELD_KEYS` set,
  and widening that is a format change with its own review;
- resistances granted by worn gear (the second half of the decision Rylee made on 2026-10-03);
- a second status effect, stacking rules, and any damage type with no source yet.

The design note keeps the full campaign and the four choices it owed; this page is slice 1.