# Rules — when this happens, do that

One rule is one sentence a person can read aloud:

> **When** the hero comes near the keeper, **if** the hero has the
> key, **then** take the key and say "You found it."

Rules live in `world.json` (top level, beside `flags`, `claims` and
`people`). They are data, not code: no loops, no numbers, no
priorities - rules run in the order written, and the world's answer
is always the same. The design note behind them is
`design/rules-when-then.md`; this page is the contract.

```json
{
  "id": "the-stone-hums",
  "when": {"comes-near": {"who": "the stone", "distance": 0}},
  "if":   [{"flag": "lit", "is": false}],
  "then": [{"set": "lit"}, {"say": "The stone hums."}],
  "once": true
}
```

## The fourteen events

Each fires from something the player already does. A pack may name
at most **40 rules** (see `docs/adr/0004-scoped-rules.md` for why).

| `when` | Means | Fires from |
|---|---|---|
| `{"starts": {}}` | the game begins | the Begin button |
| `{"enters": {"place": "X"}}` | the hero arrives in a region | crossing into it |
| `{"comes-near": {"who": "X", "distance": 0}}` | the hero is within N tiles of X (0 = standing on it) | Talk; walking onto a named place |
| `{"opens": {"what": "X"}}` | a chest or door is used | Interact on it |
| `{"picks-up": {"what": "X"}}` | the player takes an item | a floor drop, a chest's contents, a purchase |
| `{"uses-with": {"item": "X", "with": "Y"}}` | a carried item is used at a named place | Use in the bag |
| `{"defeats": {"what": "X"}}` | an enemy falls | the hit that ends it |
| `{"buys": {"what": "X"}}` | the player buys an item | the shop's Buy |
| `{"sells": {"what": "X"}}` | the player sells an item | the shop's Sell |
| `{"reads": {"what": "X"}}` | a book is closed having been read | the reader's Close |
| `{"phase-changes": {"to": "X"}}` | the watch turns to a phase | the Dusk/Dawn buttons (Menu > Display) |
| `{"falls": {"what": "X", "where": "Y"}}` | the hero's health reached zero; `what` is what did it, `where` the region it happened in | the blow that empties the health bar |
| `{"wakes": {"where": "X"}}` | the hero wakes after a fall, in region X | the Cozy wake, at the pack's wake point |
| `{"uses-verb": {"verb": "X"}}` | a verb on the verb row is pressed | pressing it - the act's own verb, or one an item granted |
| `{"mends": {"recipe": "X"}}` | two carried things are mended into one, by recipe X | Mend in the bag (see `recipes` in `docs/guides/rulesets.md`) |

`falls` and `wakes` are the hero's own two facts, and they are why a
death is not the same as an arrival. `enters` fires on every door the
hero walks through AND on the Cozy wake itself, so a pack faking a
death with it says "you wake up in the cottage again" to everyone who
merely popped home. `falls` is raised before the hero moves, so its
`where` is the region the hero fell in; `wakes` after, so its `where`
is where they woke. On a descent floor the region id IS the floor's
name (`<section>-<cycle>-<floor>`), so the place the event carries
says which floor of which cycle it happened on - the depth, in the one
id. A rule cannot *name* that id, though: `vefr check` resolves a
place against the regions the pack declares, and a generated floor is
redrawn every run, so a `falls`/`wakes` rule sticks to declared regions
and hears the floor through `say` instead. (Library books are the one
place a floor may be named; see `docs/guides/rulesets.md`.)

`uses-verb` is the one event that names the pack's own vocabulary rather
than a thing in it: `X` is a verb of the act's `verbs` list, or one an
item grants (see below). It fires when the verb is pressed, whatever the
press found - with a monster named or with nothing there - so a pack that
wants "the verb happened" writes it here and a pack that wants "the verb
landed" reads the flag the press set.

`what` is `""` when nothing in the pack did it - a rule naming a
specific enemy simply does not fire on that death. So a `falls` rule is
written per enemy the story has a line for (each one a better line than
a generic one would be), and the one line every death shares is the
`wakes` rule. Write one `say` on each and one `set` for a toast.

## One identity model

A rule may name only what the pack declares - and everything the
pack declares is nameable:

| Kind | Where it is declared | Used for |
|---|---|---|
| item ids | `world.json` `items` | `has`, `give`, `takes`, `picks-up`… |
| speaker keys | the act's `speakers` | `who`, `say`'s voice |
| region names | the act's `regions` | `enters`, `point-to`, a door's `opens`, `falls`/`wakes`' `where` |
| **POI labels** | the region contract's `pois` | `comes-near`, `uses-with` — the label *is* the id |
| **book ids** | `library/<id>.md` file names | `opens` (a chest), `reads` |
| **enemy ids** | the region contract's `enemies` | `defeats`, `falls`' `what` |
| phase names | `world.json` `phases` | `phase-changes`, the `phase` condition |
| **recipe ids** | `world.json` `recipes` | `mends` |
| flags / claims | `world.json` `flags` / `claims` | `set`, `believes`… |

The validator names anything else. There is no need to register a
fake item for a landmark: the place's own label is its id.

## Conditions (`if`) and actions (`then`)

Conditions (all must pass): `{"has": "<item>"}`,
`{"flag": "<f>", "is": true|false}`,
`{"believes"|"not-believes": {"who", "claim"}}`,
`{"is-in": {"who", "place"}}`, **`{"phase": "<phase>"}`** (the standing
phase, whatever the event was - see *Time that costs something* below),
`{"not": …}`, `{"all-of": [ … ]}`.

Actions: `say` (a narrator string, or `{"who", "line"}`),
`show` / `hide` / `reveal` (a thing on the floor),
`give` / **`takes`** (add / remove a carried item),
`set` / `unset` (a flag), `believes` / `stops-believing` / `tells`
(beliefs), `weather` (`"fog"` / `"clear"`), `point-to` (a direction
that is kept in the **Where next?** panel), **`complete-act`** (the
name of a declared act: opens one end card, "Keep exploring" or "Start
over", once per save with `saves.rules: persist`; it records that the
story beat is finished and does not advance to another act).

One rule fires at most once (`"once": true`, the default). In the
default `reset` mode that holds only until a reload: the fired markers
are forgotten, so a `once` rule may fire again. With `saves.rules` set
to `persist` the marker survives a reload and the rule fires at most
once per save. No rule ever triggers another: a `give` is not a
`picks-up`. That is the whole discipline - the world notices, remembers,
and changes in small understandable ways.

## Saves

A pack chooses how much of a run its rules remember, with an optional
top-level `saves` block in `world.json`:

```json
{ "saves": { "rules": "persist", "legacy": "from-log" } }
```

- `saves.rules` is `persist` or `reset`. The default is `reset`, today's
  behavior: each load starts the rules fresh, and no save key is read or
  written. `persist` keeps flags, fired markers, beliefs and the engine's
  items across a reload, and Start over clears them.
- `saves.legacy` chooses what a persist pack does with saves made before
  it opted in. `fresh` (the default) starts the rule state empty, so a
  `once` rule may repeat one time. `from-log` marks as fired the rules
  the **Why did that happen?** log proves fired; the log keeps only the
  last 20 entries, so older firings may still repeat once. It never marks
  a rule fired that did not fire.
- `starts` fires once per save in persist mode, and again after Start
  over. In reset mode it fires on every load, as today.

## Time that costs something

Until a pack asks for it, time is free: the phase rail in **Menu >
Display** jumps to any phase whenever the player likes, and the standing
phase lives in memory only. A pack declares an optional top-level `time`
block in `world.json` to change that:

```json
{ "time": { "rest": true, "rail": "locked", "persist": true } }
```

- `time.rest` puts a **Rest** verb in the action row (its key, `R` until
  the player changes it under **Menu > Controls**, is on the same keybind
  table as every other key). One press turns the watch on by exactly one
  phase - the next in the order the pack wrote `phases`, and the first
  again after the last - and fires the same `phase-changes` event the rail
  fires. A held key is one press, not many. On a `plain` or `investigation`
  surface the action row is not drawn at all (it is the fight row), so
  there Rest is its key and nothing else.
- `time.rail` is `"open"` or `"locked"`. `locked` hides the rail's free
  jump, so time moves only by resting and by rules that change the phase.
- `time.persist` keeps the standing phase across a reload, under its own
  save key `vefr-time-<world>`; Start over clears it. No `persist`, no
  key, no read and no write.

A rule can read the **standing** phase, so a rule can be about the hour
rather than about the thing that turned it:

```json
{ "id": "boats-may-come-in",
  "when": { "comes-near": { "who": "keeper", "distance": 2 } },
  "if": [{ "phase": "highwater" }],
  "then": [{ "say": "The boats can come in now." }] }
```

The condition is checked against the phase the watch stands at while the
event happens, whatever the event was, and it nests under `not` and
`all-of` like every other condition. The phase must be one the pack
declares in `phases`.

A pack that declares no `time` block plays and saves exactly as it did
before: no Rest verb, no Rest row in the Controls panel, a free rail, and
not one extra byte written to storage.

## Items: usable is not consumable

| Field | Means |
|---|---|
| `use` | a verb for the Bag's Use button ("drink", "turn") |
| `heal` | using restores health (and spends the copy) |
| `light` | using lights the dark (and spends the copy) |
| **`keep: true`** | using never spends it - a quest tool, a lantern |

A bare `use` with no `heal` and no `light` is a persistent tool: the
button appears, `uses-with` fires, nothing is spent.

### Items that grant a verb

An item may hand the hero a verb of its own. While the hero carries it -
or wears it, when the item names a `slot` - the verb sits in the verb row
beside the act's, with the words the pack wrote on the button:

```json
"items": {
  "caulking-mallet": {
    "name": "a caulking mallet",
    "grants": [{"verb": "mend", "label": "Mend the hull"}],
    "changes": {"mend": {"atk": 2}}
  }
}
```

| Field | Means |
|---|---|
| `grants` | a list of `{"verb": "<id>", "label": "<button words>"}`, in the order the row shows them |
| `changes` | what carrying the thing does to a verb it names, keyed by that verb's id |

- `verb` is one plain word, and it is the word the pack's `uses-verb`
  rules name. Two grants with the same verb are refused: the row would
  show two buttons and only one could be pressed.
- The verbs come and go with the thing. Spend it, sell it, hand it over -
  or just walk away from it - and the buttons leave the row; put it on and
  they stay. Two copies of one thing grant one button.
- `changes` is optional, and `atk` (0 to 9, the same bounds as a worn
  item's `mods`) is the only effect today: the extra damage that verb's
  blow carries while the thing is carried. A verb with a change lands a
  blow; a verb without one is still words. A `changes` key that names a
  verb the pack has not got is refused.
- Everything about this is opt-in. A pack with no `grants` anywhere plays
  and saves exactly as it did, and its verb row is the row it always had.

Pressing a granted verb fires `{"uses-verb": {"verb": "<id>"}}`, so what
the verb does is authored the way every other fact in the world is.

## Why did that happen?

Every fired rule leaves one plain sentence in the player's menu
(**Why did that happen?**), and `point-to` hints are kept under
**Where next?**. Both are real records of what ran - nothing is
inferred. They are the first place to look when a rule does not do
what the sentence says.
