# 0018 - Spells: schools, levels, and the books found on the floor

Date: 2026-10-10

## Status

**Proposed.** Slice 1 of 1 for the spells phase (after loot, before
endless mode). This slice is landed and proven (see Acceptance below),
but it stays Proposed until it has been played in Cottage: the whole of
what a spell *does* is one effect, and what a school *means* is the
owner's question, not this ADR's.

Rylee's picks this follows (2026-10-08): spells go **after loot** and
before endless mode. The phase's brief is `docs/packets/`'s spells
packet.

## Context

Three seams already existed, and this slice hooks them rather than
building beside them.

**Levels.** `growth` is an optional pack block, checked by
`maplab.growth_errors`, baked to `window.VEFR_GROWTH`, and read by
`web/player/parts/220-growth.js`. That part derives the level from
stored experience on every read and never stores it, and
`growthStats().level` is already clamped to the length of `levels.xp` -
that length is the cap. **Learning a spell by level is therefore a read,
not a counter**, and the brief's rule that the hero's level cap does not
move binds here as it does everywhere else.

**Loot.** ADR 0017 landed rolled loot as `vefr#381`: `delve.item_draw`
returns a bare id or an instance record, and the bag stores both shapes
in one list. A spellbook found as loot had nowhere to be; it is an
ordinary item, so it needed one key and no new drop type.

**Identify.** ADR 0017's slice 2 - identify as a town service - **has not
landed.** Nothing in the tree turns `identified` true, and
`tests/test_rolled_loot.py` pins that nothing ever will until that slice.
This slice therefore does **not** gate the lesson on `identified`: the
spell is taught when the book is *used*, through the verb the bag already
has. A book that identify later marks does not stop teaching, so the two
slices compose in any order.

There was no `spells` key anywhere, no school, and nothing in the engine
that a spell could hook onto.

## Decision

### The pack contract: one optional block, one optional item key

`world.json` may carry a `spells` block:

```json
"spells": {
  "schools": ["ember", "tide"],
  "spells": [
    {"id": "ember-bolt", "name": "an ember bolt", "school": "ember",
     "level": 1, "heal": 3},
    {"id": "tide-mend", "name": "a mending tide", "school": "tide",
     "level": 2, "heal": 5}
  ]
}
```

- **`schools`** - the pack's own school names, each one plain word
  (`shapes.WORD`). There is no closed vocabulary and no ordering the
  engine imposes: `ember` and `tide` and `bramble` are all school names.
- **`spells`** - a list of records. `id` and `name` are required;
  `school` is required; `level` and `heal` are optional.
- **`level`** - a whole number of at least 1: the level at which the hero
  has learned this spell. **A spell with no `level` is not a refusal** -
  it is a spell only a book can teach, which is the second way in.
- **`heal`** - a whole number of at least 1, and the whole of what
  casting does in this slice.

A spell is a record in a list rather than a key it is filed under, so its
id is written beside its name. That is the same choice `families` makes
in a Section, and for the same reason: one pack may want two schools with
the same display name and still tell them apart.

`shapes.SPELL` and `shapes.SPELLS` are two rows on the one schema table
and are registered in `shapes.BLOCKS`. The spellbook's key is one more
optional key on `shapes.ITEM`, in `shapes.ITEM_TAUGHT` rather than in
`shapes.ITEM_ADDED` - `ITEM_ADDED` is ADR 0017's own record of what it
added and `tests/test_rolled_loot.py` pins it by value, so a later slice
does not write into an earlier slice's record. `check_item` reads both
tuples.

### Learning by level

`spellsByLevel()` in `web/player/parts/225-spells.js` asks the growth
engine for its own level and returns every spell whose `level` is at or
below it. That is the whole of the rule, and it has three consequences
worth writing down:

- **No second counter.** The level is read, never stored by this slice.
- **The cap does not move.** The growth engine clamps the level to the
  length of `levels.xp`, so a spell written above the table's last entry
  is simply never learned by level - which is the answer, not a refusal.
  `maplab.growth_level_cap` states the cap on the pack side and
  `maplab.spells_learnable_at` states the gate, and both read the same
  two things the player reads.
- **No level, no spells by level.** A pack with no `growth` block, and a
  `practice` pack (which keeps no level to read), learn nothing by level.
  Every spell waits for a book.

`web/player/parts/220-growth.js` redraws the panel when a level is
earned and when practice ticks; it does not compute anything about
spells.

### The spellbook

A spellbook is an entry in the pack's `items` catalog carrying `spell`:

```json
"items": {
  "tide-tome": {"name": "a tide-bound tome", "use": "read",
                "spell": "tide-mend"}
}
```

It is a drop like any other drop, so **there is no new draw and no new
stream**: the spell it teaches is a function of the id the draw already
chose, and a rolled book teaches exactly what the bare one does. It is
read through `useItem` - the verb a potion is already drunk with - which
takes one copy out of the bag (unless the pack gave it `keep`), calls
`learnSpellFromBook` and says what was learned in the panel's own live
line.

Only the books are stored, under `vefr-spells-<world>` as a list of ids.
The level-learned half is derived on every read, exactly as the growth
part derives its own level. A save written before this slice reads as no
books.

### Casting

`castSpell(id)` reuses the item `heal` verbatim - the hero recovers that
much health, never above the max - and the potion's already-whole rule:
a spell is not spent on nothing, so a mis-tap costs nothing and the line
says why. A spell with no `heal` casts, says so and changes no number,
which is the honest answer for a pack that has not written the numbers
yet, and not a refusal.

**There is no second action system.** The known spells are one section of
the Bag panel below the bag list, drawn as rows with a `Cast` button by
`renderSpellList()` and called from `renderBagPanel()`. Each row names
the spell and its school in one line of text and the button carries an
`aria-label` naming the same two words, so the eye and a screen reader
are told the same thing in the same sentence. The panel's existing live
line (`role="status"`) says what a cast or a lesson did. For a pack that
declares no spells the section is hidden and empty: the heading's words
are cleared, not just the rows.

**Motion.** This slice adds no animation, no delay and no timer, so with
reduced motion on - and with it off - every word is there on the first
frame.

### The refusals

Four, each one plain sentence naming the field:

1. a spell naming a school the block does not declare -
   `spell 'ember-bolt' must name a school the pack declares, and 'frost'
   is not one; the pack declares ember and tide`;
2. a `level` under 1 - the table's own sentence at the field,
   `spells.spells[0].level must be a whole number of at least 1`;
3. an item teaching a spell the pack does not declare -
   `item 'a tide-bound tome' (tide-tome) must teach a spell the pack
   declares, and 'ash-call' is not one of its spells`;
4. a spell with no `school` at all - the table's own missing-key
   sentence, `spell must hold a school, such as {...}`.

A refusal is a no-op, not a half-spell: a book naming a spell the pack
does not have bakes the pack's own word and the player says the words
are in no school the hero knows, rather than the book being taken away.

## Compatibility

**Every new key is optional and additive, and no existing value changes
meaning.** `maplab.spells_of`, `spell_ids_of` and `spell_schools_of` are
the single readers the validator, the bake and the tests share, so the
pack's words and the player's spells cannot drift apart.

The proof, on `worlds/sample-world` (a pack that declares no `spells`),
pristine `main` against this branch:

- the woven `VEFR_ITEMS` line, sha256
  `e81e8873e4d5cb793ffae1b08f86861399e09eedbee15b9a2db8f52a9d270df5` on
  both;
- every drop drawn on twelve floors and three runs, sha256
  `e97feb4abd76e2d4728ec2b5100adde0b305323fd74c89bd22e32b6a030e870f` on
  both;
- the new `window.VEFR_SPELLS` line bakes the literal `null`, exactly as
  `window.VEFR_SKIN` does;
- **and the whole weave is byte-identical**: woven with `main`'s
  `web/packaged.html` in place of this branch's, this branch's `cli.py`
  produces `7ef6d4411e8a6f2661346fe6701d4a741173f33aaa94ec4085925c2649258dfe`
  for this pack, byte for byte what `main` produced. The only thing that
  moved the whole-file digest is the shared player template, which is
  woven into every pack by design - which is why
  `tests/test_skin_validator.py`'s `NO_SKIN_WEAVE_SHA256` was recomputed
  rather than carried over.

The saved bag is read as either shape and is untouched by this slice; a
book is an ordinary entry in it. `vefr-spells-<world>` is a new key, so a
save written before this slice reads as no books.

## Acceptance

- `tests/test_spells.py` - the shape, the four refusals, level-gating and
  the cap, the spellbook grant and its determinism, the
  backward-compatibility hashes, and the player's own copy read rather
  than run.
- `tests/test_spells_play.py` - the real woven player in jsdom: level 1
  knows exactly one spell, earning a level teaches the next, reading a
  book found as loot teaches its spell and spends the copy, casting heals
  and the already-whole rule holds, and a pack with no spells draws no
  section at all.
- `tests/fixtures/make_spell_pack.py` - the fixture: a three-step level
  table, three spells (one at level 1, one at level 2, one at level 9,
  above the cap) and one book.
- `vefr check --pack worlds/sample-world` → `ok`, exit 0.

**Every refusal goes red when it is removed.** Each of the four was
mutated out of `src/vefr/shapes.py` or `src/vefr/maplab.py` in turn, and
its own test failed with nothing else failing.

## What this slice does not do

- **What a school does.** A school is a name the pack chose and a label
  the panel prints. Nothing yet restricts which spells a hero may learn by
  which school, because nothing here decides what a school *is*.
- **What a spell does beyond healing.** `heal` is the whole effect. A
  spell that burns, freezes or speaks has no key yet, and guessing one
  would put a half-decided mechanic in the pack contract.
- **Identify.** Nothing sets `identified` true; the lesson rides `use`.
- **Mana, cooldowns, spell slots, a casting animation.** None of it.
- **Spells for rules.** No event carries a spell, so no rule fires on one.
- **The hero's level cap.** Unmoved, by this slice and by the next.

## Open questions

1. What is a school *for* in play - a gate on what a hero may learn, a
   line of words in the panel, or only ever a label? (Owner.)
2. Should a spell learned by level announce itself when the level is
   earned, or only appear in the panel? This slice shows it in the panel
   and says nothing in the moment.
3. Is `heal` the right first effect, or should the first effect be the
   one that fires a rule?
4. Should a school be a record with its own name rather than a plain
   word, the moment a school has more to say than one word?