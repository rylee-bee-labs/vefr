# The RPG core

Eight small rules a pack can switch on, one key at a time.
Each turns a thin part of the fight, the loot or the trip home into a choice.
A pack that names none of them plays exactly as it did before.
The decision record is [ADR 0021](../adr/0021-the-rpg-core.md).

| You want | Name this | Where |
|---|---|---|
| Swings that can miss or land hard | `fight` | `world.json` |
| Drinking and casting to cost a turn | `fight.turns` | `world.json` |
| Armour | `player.guard`, `mods.guard`, a family's `guard` | `world.json`, `blueprint.json` |
| Deeper floors to be harder | a Section's `curve` | `sections/*.json` |
| Kills that sometimes drop nothing, and gold | a family's `drop_chance`, `gold` | `blueprint.json` |
| A shop that sells only its own things, at a profit | a shopkeeper's `stock`, `markup` | the act's `speakers` |
| Gear whose hidden words do something | `traits` | `world.json` |
| Spells that cost something, and wands | `player.mana`, a spell's `mana`/`harm`/`ward`, an item's `casts`/`charges` | `world.json` |
| A fight row with your own words, and a Cast button | the act's `verbs` | the act's `world.json` |
| Trips that go back to the deepest landing | `descent.resume` | `world.json` |
| A fall that sends you home and leaves your bag | `descent.fall` | `world.json` |
| A rest at home that heals | `time.rest_heals` | `world.json` |
| Keepsakes that never take a bag place | an item's `pouch` | `world.json` |

Every value is checked by `norns validate`, and every refusal is one plain sentence.

## Rolls and turns

```json
"fight": {"miss": 10, "crit": 8, "crit_times": 2, "turns": true}
```

- `miss` and `crit` are percents, 0 to 50, for the hero and the monsters alike.
- A critical blow is multiplied by `crit_times`, 2 or 3 (2 when left out).
- Every roll is said in words: "You miss the rat.", "A clean hit! ...", "A heavy blow!".
- Rolls come from a named, seeded stream. The same moves in the same state give the same rolls, so a reload never re-rolls a fight.
- `turns: true` makes drinking, using a thing and casting a spell cost a turn. The monsters answer it, as after a step.

## Guard

```json
"player": {"hp": 10, "atk": 2, "guard": 1}
```

- Guard is what every blow loses. A blow that lands is never reduced below 1.
- The hero's guard is `player.guard`, plus a worn thing's `mods.guard` (0 to 9), plus traits and a standing ward.
- A monster's guard is its family's `guard` in `blueprint.json`, or a region enemy's `guard`.
- Spell harm ignores guard. Magic is the build that walks past armour.

## Depth

A Section's `curve` was always accepted. It is now read at play:

```json
"curve": {"hp": [1.0, 1.4], "atk": [1.0, 1.3]}
```

- Floor `k` of an `n`-floor Section scales an ordinary monster's health and attack through `vefr.mob_stats` (ADR 0014).
- Floor 1 sits at the low end and the last floor at the high end.
- The warden keeps its own numbers. It is written for its floor.

## Spoils

On a family's `defaults` in `blueprint.json`:

```json
"cellar-rat": {"defaults": {"hp": 4, "atk": 1, "drops": ["candle"],
                            "drop_chance": 40, "gold": [1, 3]}}
```

- `drop_chance` (0 to 100) is the share of its kills on a generated floor that drop anything. Left out, every kill drops, as before.
- When a kill does drop, the item is the one it always would have been.
- `gold: [lo, hi]` pays coins on the kill, with one line: "You find 2 gold."

## Stock

On the speaker that keeps a shop:

```json
"trader": {"shop": "true", "markup": 200,
           "stock": ["potion", {"item": "satchel", "flag": "cellar-done"}]}
```

- `stock` lists what the shop sells, in order. An entry with a `flag` appears once that flag is set.
- `markup` (100 to 500) is the buy price as a percent of `value`, rounded up. The shop still buys at `value`.
- A shop with no `stock` sells every priced thing, as before.

## Traits

A trait is a word a rolled or fixed item carries (ADR 0017). A `traits` table gives the word something to do:

```json
"traits": {
  "keen":     {"atk": 1},
  "warded":   {"guard": 1},
  "lucky":    {"crit": 5},
  "warming":  {"kill_heal": 1},
  "eager":    {"opener": 2},
  "thorned":  {"thorns": 1},
  "reckless": {"atk": 3, "sting": 1, "curse": true}
}
```

- Stats: `hp`, `atk`, `guard`, `mana` (-9 to 9) and `crit` (-50 to 50).
- Reactions, each said in one line when it fires:
  - `kill_heal`: a kill restores N health.
  - `opener`: a blow on an unhurt foe is multiplied by N (2 or 3).
  - `thorns`: a monster that hits you takes N. It never fells a foe.
  - `sting`: each of your misses hurts you N. It never fells you.
- A reaction never fires another reaction, so a turn's chain is bounded.
- `curse: true` marks a curse. Once the item is read, it says "(cursed)". A cursed thing comes off like any other, so give every curse an upside.
- A trait works from a worn thing, and from a carried thing that has `carry` (a bag on the hero's back). It works whether or not the item has been read.
- A worn thing keeps its rarity and traits, and gives them back when it comes off.
- To make rarity matter, tie the number of traits to it in the item's `roll`:

```json
"roll": {"rarity": {"common": 60, "fine": 25, "rare": 10, "heroic": 4, "mythic": 1},
         "traits": ["keen", "warded", "lucky", "warming", "eager", "reckless"],
         "per_rarity": {"common": 0, "fine": 1, "rare": 2, "heroic": 2, "mythic": 3}}
```

  A rarity named in `per_rarity` bears exactly that many traits (0 to 4). A roll without it draws as before.

## Magic

```json
"player": {"mana": 6},
"spells": {"schools": ["ember"], "spells": [
  {"id": "ember-bolt", "name": "an ember bolt", "school": "ember", "level": 1,
   "mana": 2, "harm": 4, "range": 6},
  {"id": "warding-word", "name": "a warding word", "school": "ember", "level": 2,
   "mana": 1, "ward": {"guard": 2, "turns": 3}}
]},
"items": {
  "birch-wand": {"name": "a birch wand", "casts": "ember-bolt", "charges": 3, "value": 20}
}
```

- `player.mana` turns mana on. Gear (`mods.mana`) and traits add to it. The HUD shows "Mana 4/6".
- A spell's `mana` is its cost. A cast you cannot pay for is refused and costs nothing.
- A spell does one thing:
  - `heal` restores health (as before).
  - `harm` strikes the named foe, or the nearest living one within `range` tiles (6 when left out), past guard.
  - `ward` raises guard for a few turns.
- An item with `casts` and `charges` casts its spell for no mana, one charge a cast. Spent, it waits for a rest.

## The fight row

```json
"verbs": [{"verb": "attack", "label": "Strike"}, {"verb": "cast", "label": "Cast"}]
```

- A verb may name its own label. A bare word is labelled with itself, as before.
- `cast` casts the first harmful spell the hero knows and can pay for, at the foe the row names.
- The Cast button shows only while the hero knows a harmful spell.
- `throw` (ADR 0024) throws the first thing carried that can be thrown, at the foe the row names. It shows only while something can be thrown.

## Trips

On the `descent` block:

```json
"descent": {"run_seed": "ember", "entry": {...}, "sections": [...],
            "resume": "deepest-landing", "fall": "home"}
```

- `resume: "deepest-landing"`: the town stair goes to the deepest landing the hero has reached.
- `fall: "home"`: a fall on a generated floor wakes the hero at `player.wake`.
  - What was in the bag stays where they fell, as one satchel. Worn things and `keep` things stay with the hero.
  - The satchel is drawn on its floor even in the dark, and arriving there says so.
  - Walking onto it takes everything back. A second fall before fetching it replaces it.

On the `time` block:

```json
"time": {"rest": true, "rest_heals": true}
```

- Rest outside a generated floor, with nothing alive to fight, restores health, mana and every charge.
- Anywhere else, Rest turns the watch as it always did.

## The pouch

```json
"items": {"shoe-button": {"name": "a shoe button", "pouch": true}}
```

- A thing marked `pouch` is carried like any other, and takes none of the bag's places.
- A fall leaves it with the hero, as it does a `keep` thing.

## Monster skills

ADR 0024. A Blueprint family's `defaults` (or a hand-placed enemy) may carry up to two `skills`:

```json
"skills": [{"skill": "web", "range": 3, "turns": 2, "every": 5}, {"skill": "spit", "harm": 2}]
```

| Skill | When | What it does | Keys (default) |
| --- | --- | --- | --- |
| `web` | from up to `range` tiles, on a clear line, once every `every` of its turns | the hero cannot step for `turns` of their turns; a step is a struggle and costs the turn; a blow at a monster beside them is still a blow | `range` 2-6 (3), `turns` 1-5 (2), `every` 2-20 (5) |
| `spit` | the same | a hit for `harm`, rolled like a blow; guard takes from it | `range` 2-6 (4), `harm` 1-20 (2), `every` 2-20 (3) |
| `fester` | on a melee blow that lands, `chance` in 100 | the bite keeps biting: `tick` a turn for `turns` (poison) | `chance` 1-100 (30), `tick` 1-9 (1), `turns` 1-9 (3) |
| `dust` | the same | the hero's blows miss `miss` in 100 more often for `turns` (needs a `fight` block, which rolls misses) | `chance` 1-100 (40), `miss` 5-50 (25), `turns` 1-9 (3) |
| `squeal` | once, the first time it is struck to half its health or below | every monster within `radius` tiles wakes and comes | `radius` 2-24 (16) |

- A clear line has no wall, no prop and no other monster on the tiles between.
- Each chance is drawn from its own named stream, so the same moves give the same bites.
- The states (webbed, festering, dusted) are written on the HUD's state line in words, and a reload clears them, as it does a burn.

## Throwing

```json
"items": {"stone": {"name": "a stone", "throw": {"harm": 2, "range": 5}}}
```

- A thing with `throw` is thrown at the foe the fight row names, or the nearest one within `range` tiles (2-8, default 5) on a clear line.
- It is rolled like a blow (a miss, a critical), guard takes from its `harm` (1-20), and dust spoils it as it does a blow.
- It lands on the foe's tile, to be picked up again. A throw costs the turn a blow costs.
- Throw from the Bag, from the quick bar (it is a quick-use thing), or from a `throw` verb on the fight row, which shows only while something that can be thrown is carried.

## What this does not do yet

Named so nobody assumes it: elites and groups on generated floors, monster weaknesses, stock quantities and restock timing, permanent death, a map mark for the satchel, and interface icons for rarity.
