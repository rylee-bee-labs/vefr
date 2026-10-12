# 0017 - Rolled loot: rarity at once, traits hidden

Date: 2026-10-10

## Status

**Proposed.** Three slices for phase 3. Becomes Accepted when all three land: rolled loot (slice 1), identify-as-a-town-service (slice 2), bag capacity (slice 3).

Slices 1 and 2 are landed and proven (see Acceptance). Slice 3, bag capacity, is written in the amendment at the end of this ADR (2026-10-12). What a thing's traits *do* is still undefined, and that stays an open question rather than a guess.

This section states slice 2; the rest of the ADR is slice 1 and still reads as written.

## Slice 2 - the identify service (ADR 0017, T3 slice 2)

Slice 1 left one flag nothing could turn: `identified` starts false and stays false. Slice 2 gives the town a place to read a thing, and the read itself.

### The pack contract: one flag on one speaker

A pack names the reader the way it already names a shop - a speaker carries `"identify": "true"` (also `yes`/`1`, or the boolean `true`) and is the service of its region:

```json
"speakers": {
  "reader": {"name": "The Reader", "at": [6, 4], "identify": "true"}
}
```

Nothing else. There is no `identify` block, no chance, no cost, no roll, no model: the thing being read was drawn once, at the drop, and reading it is a read. `maplab.identifies` is the one reader, and `web/player/parts/195-the-identify-service.js` mirrors it exactly, so a pack that passes `vefr check` is a pack that offers the service in play.

**Why the flag rides the speaker and bakes nothing new.** The shopkeeper's flag is read the same way, and `VEFR_WORLD` already carries every speaker of the pack in full. A new `window.VEFR_IDENTIFIES` line would have been a fourth thing to keep in step with nothing to gain, so this slice adds **no** baked block at all: a pack that names no reader weaves every `window.VEFR_*` data line exactly as `main` wove it. That is the compatibility proof below, and it is hash for hash.

### The read

Interacting with the reader (the same verb, the same reach, the same rank, that the Trade panel uses) opens a panel listing what the hero carries that has not been read. Reading one sets `identified: true` on **that instance** in `localStorage['vefr-bag-<world>']` and writes the bag back. That is the whole mechanism: no draw, no re-roll, no second record, no chance of naming the wrong copy when two copies of an id were drawn differently.

### The reveal

Once read, the traits are part of the thing's name in both bag surfaces - the panel row and the HUD strip's `aria-label` - as `a brass ring (rare) - traits: keen, cold`. In **text**, in the DOM, with nothing behind a timer, and in the same call as the click: `bagIdentifyOne` sets the flag, saves, and calls `renderBagPanel()` and `renderBagStrip()` itself. So with reduced motion on - and with it off - the words are on the first frame after the press. There is no animation in this slice to turn off, which is the strongest form the requirement can take; `tests/test_identify_play.py` reads the DOM in the same tick as the click and compares the two motion settings word for word.

The standard slice 1 set is kept, not lowered: while `identified` is false the traits are in **no** part of the page - not a row, not an attribute, not a title - so nothing is hidden from the eye that is not also hidden from a screen reader.

### The save

No version marker, and none needed: the bag entry is read as either shape already. A bag saved by slice 1 is a list of bare ids and instance records with `identified: false`, and this slice writes `identified: true` into the record that is already there - a bag saved by a build that predates slice 1 is still a list of strings. `bagCarried` reads all three, so a save written before any of this still loads, and a save written by it loads in an older build with the extra key simply unread. This answers open question 3 below: **no marker**.

### The refusals

Three, each one plain sentence naming the speaker and the field, in the voice of `item_roll_errors`:

1. `speaker 'The Reader' (reader) identify names 'alchemist', which is not a service this pack has: write true to make this speaker the one that reads things`
2. `speaker 'The Reader' (reader) identify must be the word true: a thing is read once, at the place the pack names, so identifying carries no chance, no roll and no model`
3. `speaker 'The Reader' (reader) offers identify in region 'hollow', which this pack does not have`

Refusal two is the standing rule (models never run on deterministic surfaces) made into a check: an `identify` object is where a pack would put a `chance`, a `roll` or a `model`, and each of those is either nondeterministic or model-written. A flag that says no (`false`, blank) is silence, exactly as a blank `shop` is.

### What is still missing

- **Bag capacity and bag upgrades - slice 3.** Written 2026-10-12, see the amendment below. The bag is unbounded unless a pack names a size, and it still has no weight and no slots beyond the five worn ones.
- **What a trait DOES.** Unchanged by this slice and still the open question below. The reveal makes the words visible; nothing in the engine reads them.
- **A cost for reading.** A pack cannot charge gold or time for it yet. That is a bag-economy question and belongs with a later slice, not with the capacity amendment.

### Acceptance for slice 2

- `tests/test_identify.py` - the flag and its one reader, the three refusals on the fixture's own act block, the no-re-roll rule (the draw is unchanged, and the read writes one field and no other), the two backward-compatibility hashes, and the static proof that nothing in the read path draws, waits or animates.
- `tests/test_identify_play.py` - the real woven player in jsdom: Interact beside the reader opens the panel; the Read button puts the traits into the HUD strip, the bag panel and the saved bag **on the first frame**; the same DOM with motion on and off; two copies of one draw read to the same words; the flag survives a reload.
- `tests/test_interact.py` - the reader's kind, label, reach and rank beside the trade panel's.
- `uv run --group test pytest -q` green, with the failures on `main` unchanged.

### The compatibility claim, precisely

The pack's own woven content is byte-identical for a pack that names no reader: every `window.VEFR_*` data line, hash for hash, on `worlds/sample-world` and on the rolled-loot fixture.

The **player around those lines is not** byte-identical, and could not be: this slice adds the read to the bag strip, the bag panel and the Interact verb, which is what the slice is. Every one of those additions is behind `identified` or behind the flag, so a pack that names no reader sees a player that behaves exactly as it did - which is the claim the fixture and the hashes carry, and what the pack-facing compatibility here means.

### Two sentences in the tree that said "not yet"

- `src/vefr/world.py` - was: "Nothing identifies a thing yet... nothing in this slice ever turns it true." Now: the flag, and the town reads a thing where a pack names a reader.
- `web/player/parts/160-the-bag.js` - was: "No weight, no dropping, no identifying yet." Now: no weight, no dropping, no bag size; the town reads what it reads, and slice 3 gives the bag its capacity.
- `web/player/parts/430-loot-on-the-floor.js` and `web/player/parts/397-the-descent.js` - the same, in one line each.

Rylee's picks this follows (2026-10-08): loot goes "Before E8 vaults"; the town gives "Rest, trade, identify"; danger rises. The brief for this slice is `docs/packets/`'s T3 packet.

## Context

There was no rarity and no identify machinery anywhere in the repo. An item was a `world.json` `items` entry - words, a sprite, and what it does - and `src/vefr/world.py` said so in one line: **"Nothing is identified yet."** The loot slice of `docs/guides/rulesets.md` said, of the same subject: **"Deterministic like the rest - fixed ids, no randomness, no model call."**

That last sentence is the tension this ADR has to settle honestly rather than paper over. The rule this engine actually holds is not "no randomness" but the determinism rule: **every draw comes from a named seeded stream off the run seed, no `Math.random`, no clock, no globals, no float arithmetic beyond `int(rng() * n)`** (`docs/packets/equip-engine-a2.md`; PLAN §8's sub-seed rule). A weighted draw off a named stream is deterministic in exactly the sense every other draw in this engine is - the same seed gives the same floor, the same monster, the same hit points, the same drop, the same rarity, the same traits. So the sentence in `rulesets.md` is not contradicted by this slice; it is *narrowed*, and the guide says so in place. What this slice adds is a second and third draw inside the one the engine already made, not an unseeded one.

Two sentences in the tree say "not yet" about identification, and both stay true after this slice rather than being rewritten to sound bigger:

- `src/vefr/world.py` - now: nothing identifies a thing yet; ADR 0017 gives a drop hidden traits and an `identified` flag that starts false, and nothing in this slice ever turns it true.
- `web/player/parts/160-the-bag.js:9` - now: no weight, no dropping, no identifying yet. Still true: this slice adds a word next to the thing's name and nothing else about identification.
- `web/player/parts/430-loot-on-the-floor.js` - now: a drop may carry the rarity it was drawn at and the traits it is hiding; identifying is the slice after this one.

## Decision

### The pack contract: three optional keys

An `items` entry may carry three new keys. Every one is optional, every one is additive, and an item that names none of them bakes and drops exactly what it did before.

```json
"items": {
  "cloudy-potion": {
    "name": "a cloudy potion", "sprite": "potion", "heal": 3, "use": "drink",
    "rarity": "common",
    "traits": ["keen"],
    "roll": {
      "rarity": {"common": 60, "uncommon": 30, "rare": 10},
      "traits": ["keen", "brave", "swift", "cold"],
      "chance": 60,
      "max": 2
    }
  }
}
```

- **`rarity`** - one plain word. On an item with no `roll`, the fixed rarity the thing is. On an item with a `roll`, it must be one of the names that item's own `roll.rarity` declares.
- **`traits`** - a list of plain words. Fixed, like `rarity`, when there is no `roll`.
- **`roll`** - `rarity` (required, a table of pack-chosen names and whole weights), `traits` (the pool), `chance` (int 0..100, how often a draw bears a trait at all; default 100 when a pool is named), `max` (int 0..4, how many at once; default 1).

The rarity names are the pack's. There is no closed vocabulary and no ordering the engine imposes: `common` and `odd` and `bramble` are all rarity names. A plain word is `[A-Za-z][A-Za-z0-9_-]{0,23}` (`shapes.WORD`) - one thing the bag can print, never a sentence that reads as two traits in a sentence.

`shapes.ITEM` is the block that states the whole item and `shapes.ROLL` the block inside it; both are registered in `shapes.BLOCKS`. `shapes.check_item`, not `check`, is the entry point, and it reads only `rarity`, `traits` and `roll`. The other nine keys are in the table so the table states the whole item, and are deliberately not re-checked there: every one of them accepts something today (a `value` of 0, a `heal` of "lots", a `use` of `"  "`, and any key the engine has never heard of), and a check that began refusing them would refuse packs that were never wrong about them.

### The draw

One drop draw yields a base item, and then, for that item, a rarity and some traits:

| stream | seed | spends |
|---|---|---|
| the base id | `v3\|<floor key>\|loot\|<mob id>` | one `int(rng() * len(ids))` - unchanged |
| the roll | `v3\|<floor key>\|roll\|<mob id>\|<item id>` | the rarity, then the traits |

The roll stream is named off the same floor key and the same monster the base draw came from, and the item id is in the name so a monster that could carry two rolled things gives each its own stream. Consequences, all pinned by tests: the base draw cannot move when a roll is added, two monsters never share a roll, and the order monsters are killed in cannot change what any of them drop (PLAN §8's sub-seed rule).

The order of the draws is fixed and is part of the contract, because the two languages must agree:

1. the rarity - `int(rng() * total)` over the pack's whole weights, then a walk down them;
2. whether the thing bears a trait at all - `int(rng() * 100) >= chance`;
3. how many - `1 + int(rng() * max)`, capped by the pool;
4. which - `int(rng() * len(left))` over what is left, so two traits never come back the same word.

Every one of those is `int(rng() * n)` with an `n` the pack's own whole numbers built. `maplab.RARITY_NAMES_MAX` (64), `RARITY_WEIGHT_MAX` (9999) and `TRAIT_POOL_MAX` (16) are the bounds that keep the product under 2**31, and they are the draw's bounds rather than an author's taste.

**Where a draw happens.** A draw needs a stream, so it happens where there is one: a monster's drop on a generated floor. A drop with no floor key to seed it - a town enemy, a chest, a rule that puts a thing on the floor - carries the item's **fixed** `rarity`/`traits` and draws nothing.

### What rides on the drop, and on the instance in the bag

A drawn drop is a record; an undrawn one is still the bare id it has always been:

```json
{"item": "cloudy-potion", "rarity": "uncommon", "traits": ["cold"], "identified": false}
```

`identified` is false on every instance and **nothing in this slice sets it true** - that is the next slice, and `web/player/parts/180-gold.js` is written so that turning it on is one line. The instance rides on the floor record and then into `localStorage['vefr-bag-<world>']`, which is now a list whose entries are either a bare id (every bag before this slice, and every bag of a pack that declares no roll) or an instance record. `bagCarried()` reads both the same way.

### The reveal

The bag strip, the bag panel and the pickup line name the thing **and its rarity together**, at once, from the moment of pickup: "a cloudy potion (uncommon)". The traits are in no part of the page - not in a row, not in a tooltip, not in an attribute - while `identified` is false. The strip's `aria-label` carries the same words, so a screen reader hears what the eye sees.

**Motion.** This slice adds no animation and no delay: the rarity is written into the same string as the name, in the same pass. So with reduced motion on - and with it off - the reveal is instant and identical. There is nothing to switch off, which is the strongest form the requirement can take; the reveal moment itself is slice 2's, and when that arrives the motion-off rule is one `prefers-reduced-motion` check away in the one place that animates.

### The refusals

Four, each one plain sentence naming the item and the field:

1. a `rarity` that is not one of the names the item's own `roll` declares;
2. a trait that is not one plain word (in the item's `traits` or in a roll's pool);
3. a `roll` with no rarity table, or a table with no whole weight in it;
4. a `roll` that asks for traits (`traits`, `chance` or `max`) and names no pool.

A refusal means the item draws nothing at all rather than half a roll: an unusable roll is a no-op in play, and the sentence is the pack author's.

## Compatibility

**Every new key is optional and additive, and no existing value changes meaning.** `maplab.item_roll_of` is the single reader the validator, the bake and the draw share, so the pack's words and the player's roll cannot drift apart.

The proof, on `worlds/sample-world` (a pack that declares no `rarity`, no `traits` and no `roll`), pristine `main` against this branch:

- the woven `VEFR_ITEMS` line, sha256 `3997a2ea7deea05adf61b9d51bcf6c54972dc489e85180b6f632caa4774d47a9` on both;
- every drop drawn on twelve floors and three runs, sha256 `7a3006b669db87c889c914841e75e70fbeae3f03ffe4b8d34d2abb671140f0fc` on both, and the same again with the catalog handed to `floor_plan`.

`mob_drops`, `mobs_at`, `_with_warden` and `floor_plan` all take the catalog as an **optional** argument defaulting to `None`, and the JavaScript twin reads `window.VEFR_ITEMS` where the weave already writes it. A caller written before this slice gets the same list of bare ids.

The saved bag is read as either shape and the saved floor record carries the extra fields only when a drop has them, so a save written by an older build reads identically and a save written by this one reads identically in an older build (the extra keys are simply not there).

## Acceptance

- `uv run --group test pytest -q` green, with the failures on `main` unchanged.
- `tests/test_rolled_loot.py` - the shape, the four refusals, the draw's determinism (same seed twice, different keys and monsters differ, the base id does not move, every stream named), the backward-compatibility hashes, the reveal's own words, and the static proof that nothing in the reveal path animates or waits.
- `tests/test_rolled_loot_play.py` - the real woven player in jsdom: the bag names the thing and its rarity, the traits are in no part of the page, the instance survives a reload, and a bag saved before this slice still reads.
- `tests/test_descent_parity.py` - the same cellar drawn in both languages with a rolled catalog planted: the whole drop, base id, rarity and traits, must match field for field.

**Every refusal goes red when it is removed.** Each of the four was mutated out of `src/vefr/maplab.py` (or, for the trait word, out of `shapes.py`'s `words` kind) in turn, and its own test failed with nothing else failing.

## What this slice does not do

Slice 1's own record, kept as it was written. Two of these have since landed and are marked; the rest are still out.

- **Identify as a service.** *Landed in slice 2* - the section above.
- **The reveal moment.** *Landed in slice 2* - the traits in text on the
  first frame, and still no animation of any kind.
- **What a trait does.** Read in, stored, hidden, never rendered. Whether a trait changes a number, changes a line, or is only ever flavour is an open question for slice 2 or 3 - it is a *pack data* question the moment the reveal exists, and guessing now would put a half-decided mechanic in the pack contract.
- **Bag capacity, weight, selling changes, grids, equipment.** Out of scope; slots and bag upgrades are slices 3 and later.
- **Rolled drops outside a generated floor.** A town enemy or a chest with no stream carries the item's fixed rarity and traits, unchanged.

## Open questions

1. Do traits change numbers, or are they words the player reads? (Owner.)
2. Does a fixed `rarity` on an unrolled item make it a "rare" thing for any future shop, sell or bag-capacity rule, or is it only ever a word in the bag?
3. Should the bag's save format grow a version marker when slice 2 starts writing `identified: true`?
4. Is a drop's rarity rolled from its own table every time, or can a Section bias it (an elite's drop being rarer than a rat's)?

## Amendment 1 (2026-10-12): bag capacity

Slice 3 is written. The owner's decisions in force: the bag is opt-in and unbounded unless a pack names a size (2026-10-12); capacity is "slots plus bag upgrades" (2026-10-08/09); the schema change is additive only, and any incompatible change goes to the owner as an ask (2026-10-11).

- **`bag.size`** - an optional block in `world.json`: `"bag": {"size": 6}`. A whole number of at least 1 and at most 99. A pack that names no `bag` keeps the unbounded bag it always had.
- **`carry`** - an optional whole number of at least 1 and at most 99 on an item. Carrying that item, in the bag or worn, raises the cap by its `carry`. An item with no `carry`, or a `carry` of 0, adds nothing. The carry is read from the baked catalog, so the player and the validator agree.
- **The refusal.** When the bag holds as many things as its cap, a floor pickup is refused and the thing stays on the floor, on the hero's tile. The player sees one line: "Your bag is full. You leave <names> on the floor."
- **Exemptions.** A warden's key always fits (ADR 0015, line 47: "so it cannot be lost"). The same goes for the other paths that move an item into the bag without a floor pickup: an equip swap, a take-off, a `give` from a rule, and a chest. Those call the bag with `alwaysFits`, because a refusal on those paths would lose the item rather than leave it on the floor.
- **The count line.** With a cap, the bag panel reads "2 of 2 carried."; without one it reads "12 things carried." as before.

Not in this amendment: a bag weight, slots beyond the five worn ones, a sixth worn slot, and any change to what "full slot" means in the equipment tests. The pack field names are `bag.size` and `carry`; the wording the player shows says "bag size" and "carry space" and never "slot", because a worn slot is a different thing.

Open, for the owner: a pack that names a `carry` item but no `bag.size` gets no cap, so the upgrade does nothing there. Whether that should be refused at validation or stay silent is not decided here.
## Owner decision (Rylee, 2026-10-12, closing vefr#342)

Rarity names stay pack-defined, as above, rather than a fixed engine set.
Unidentified traits are hidden in the rendered page only: a one-file
offline game rolls and saves its loot in the browser, so the trait pools
and a rolled bag entry are readable by anyone who opens the source, and
that is accepted.
