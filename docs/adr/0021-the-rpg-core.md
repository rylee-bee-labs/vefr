# 0021 - The RPG core: fight rolls, guard, depth, spoils, stock, traits, magic, trips

Date: 2026-10-29

## Status

**Accepted direction; implemented in one PR (Gate 1 of the Cottage 1.0
roadmap).** The owner chose "One big PR per gate" for this work
(cottage `NOTES.md`, 2026-10-29), which is the ask-first answer for the
pack-contract change below. Every gameplay rule here is owner-approved
direction from that day's sixteen answers (quoted in the game's `NOTES.md`
and `DESIGN.md`) or from the approved 1.0 direction (cottage#168, this
repo's #489). Implementation details nobody decided are chosen the
smallest compatible way and are named as such.

**Every key is opt-in.** A pack that declares none of them bakes the item,
spell, enemy and speaker records it baked before and plays the fight it
played before: `tests/test_rpg_core.py` pins the bake and
`tests/test_rpg_core_play.py` plays the opt-out fight and checks that no new
key is saved.

## Context

A code audit at `db3df92` (recorded in the game's
`docs/plans/release-1-0/LOOPS.md`) found the fight, the loot and the trip
home thin in ways no pack data could fix:

- damage is exactly Attack, every time; nothing reduces it;
- a generated kill always drops exactly one thing, and gold never drops;
- a Section's `curve` is validated and never read, so floor 36 fights like
  floor 1;
- the shop sells every priced item, unlimited, at the price it pays;
- rarity and traits are words in a name, and a worn thing forgets them;
- spells only heal, cost nothing and take no turn; drinking takes no turn;
- every trip from town starts again at floor 1; a fall on a floor wakes on
  that floor with nothing lost; resting does not heal.

Each is a small seam in an existing part. None needs a new subsystem, a
scripting language or a model call: everything below is deterministic.

## Decision

### 1. Fight rolls - world `fight` (owner: "Classic: misses and crits")

```json
"fight": {"miss": 10, "crit": 8, "crit_times": 2, "turns": true}
```

- `miss` (0..50) and `crit` (0..50) are percents, for the hero's blows and
  the monsters' alike. `crit_times` (2..3, default 2) multiplies a critical
  blow before anything reduces it.
- Every roll is drawn from its own named stream,
  `fight|<world>|<region>|<attacker>|<defender>|<n>`, where `n` counts the
  blows struck in this region since the hero entered it. The same moves in
  the same state give the same rolls, so reloading a save never re-rolls a
  fight, and no other stream (layout, spawns, loot) moves.
- `turns: true` makes using a carried thing and casting a spell cost a
  turn: the monsters act after it, as after a step. Absent, both stay free.
- Every roll is said in words in the fight line ("You miss the rat." /
  "A clean hit! ..."), never by colour or motion alone.

### 2. Guard (owner: "Guard stays as armour")

- `player.guard` (0..99), item `mods.guard` (0..9, worn), and a Blueprint
  family's or region enemy's `guard` (0..99).
- A blow that lands for more than 0 is reduced by the target's guard and
  never below 1. A resistance that turns a blow aside entirely still turns
  it aside (0 stays 0). Spell harm ignores guard.

### 3. Depth - a Section's `curve` is read (owner, 2026-10-08: danger "Rising")

`curve: {"hp": [lo, hi], "atk": [lo, hi]}`, multipliers in whole
hundredths. It was always validated and never read; the wiring was always
meant to be "slice E10 scales monster stats through `vefr.mob_stats` at
play", and that is what this does: an ordinary monster's drawn health and
attack on floor `k` of an `n`-floor Section go through ADR 0014's own
formula, `max(1, v * curve_pct // 100)` with `curve_pct = lo + (hi - lo) *
(k - 1) // (n - 1)`, with no affix and cycle 0 (elites and the endless ramp
stay unwired). Both twins (`delve.mobs_at`, `397-the-descent.js` `mobsAt`)
apply it after the last draw, so no stream moves, and a Section with no
`curve` is the neutral 100. The warden keeps its Blueprint numbers: a
warden is written for its floor.

### 4. Spoils - a family's `drop_chance` and `gold`

- `drop_chance` (0..100, default 100): the share of kills that drop
  anything. Drawn on `<loot stream>|chance`, so the item a drop names is
  still the one the old draw named.
- `gold: [lo, hi]` (0..9999): the coins a kill pays, drawn on
  `<floor key>|gold|<mob>` and added to the purse with one line ("You find
  3 gold."). Only a family that names it carries it.

### 5. Stock - a shopkeeper's `stock` and `markup`

On the speaker that keeps a shop: `stock` lists what it sells, each an
item id or `{"item": id, "flag": name}` that appears once the flag is
set; `markup` (100..500, default 100) is the buy price as a percent of the
item's `value`, rounded up. A shop with no `stock` sells every priced
item, as before.

### 6. Traits (owner: "Mostly stats, some tricks"; curses "Take it off at any time ... a deliberate upside")

A world `traits` table gives a trait word what it does:

```json
"traits": {
  "keen":   {"atk": 1},
  "warded": {"guard": 1},
  "hale":   {"hp": 2},
  "deep":   {"mana": 2},
  "lucky":  {"crit": 5},
  "warming": {"kill_heal": 1},
  "eager":  {"opener": 2},
  "thorned": {"thorns": 1},
  "reckless": {"atk": 3, "sting": 1, "curse": true}
}
```

- Stats: `hp`, `atk`, `guard`, `mana` (-9..9) and `crit` (-50..50 percent).
  The hero's numbers never fall below 1 health, 1 attack, 0 guard, 0 mana.
- Reactions, one closed set, each said in one line when it fires:
  `kill_heal` (a kill restores N), `opener` (a blow on an unhurt foe is
  multiplied by N, 2..3), `thorns` (a monster that hits you takes N),
  `sting` (each of your misses hurts you N, never below 1). A reaction
  never fires another reaction, so a turn's chain is bounded by
  construction.
- An item's `roll` may tie its trait count to its rarity: `per_rarity`
  (`{"common": 0, "rare": 2}`, 0..4 each) is drawn in both twins after the
  rarity, with no chance or count draw, so rarity finally matters. A roll
  without it draws exactly as ADR 0017 wrote.
- `curse: true` names a trait a curse: identified, it reads "(cursed)".
  A cursed thing comes off like any other.
- A trait works from a **worn** thing, and from a **carried** thing that
  has `carry` (a bag on your back), identified or not; identifying only
  tells you. A worn thing now keeps its rolled instance (rarity, traits,
  identified) and gives it back to the bag when it comes off, in a saved
  key that is only written when there is an instance to keep. A second copy
  of a worn id in the bag is a second thing: it is no longer hidden from the
  bag, nor dropped on reload (that reload also used to rewrite the bag as
  bare ids, wiping every rolled instance; it keeps the entries now).

- An item marked `pouch: true` (a keepsake) is carried and never takes one of
  the bag's places; a fall leaves it with the hero. **Claude's call** on the
  owner's bag answer: keepsakes go in the album pouch, never a slot.

### 7. Magic (owner: "a mana cost for learned books and charges for spells")

- `player.mana` (0..999): the hero's mana. Gear and traits add to it.
- A spell may cost `mana` (1..99) and may do one of: `heal` (as before),
  `harm` (1..99: damage to the named foe, or the nearest living one within
  `range` tiles, default 6; ignores guard), `ward` (`{"guard": N,
  "turns": T}`: guard for a few turns).
- An item with `casts: <spell id>` and `charges` (1..20) casts that spell
  for no mana; each use spends a charge, kept on the carried instance.
  Spent, it waits until the hero rests.
- Resting (below) refills mana and charges.
- The act's `verbs` may name a label: `{"verb": "attack", "label":
  "Strike"}`. A verb `cast` casts the first `harm` spell the hero knows and
  can pay for at the named foe; its button shows only while there is one.

### 8. Trips (owner: "Deepest landing only"; "Satchel contents")

On the `descent` block:

- `resume: "deepest-landing"`: the descent's entry from town goes to the
  deepest landing the hero has reached this run, at its arrival tile.
- `fall: "home"`: a fall on a generated floor wakes the hero at
  `player.wake`, not on the floor. What was in the bag (not what is worn,
  and not a `keep` thing) stays where the hero fell, as one satchel kept in
  the descent's own record - not with the floor's drops, which the trip
  home clears. Walking onto it takes it all back. One satchel: a second
  fall before the first is fetched replaces it.

On the `time` block:

- `rest_heals: true`: Rest outside a generated floor, with no living foe in
  the region, restores health, mana and every charge.

## Consequences

- One pack-contract change, recorded in `src/vefr/world.py`, the guide
  `docs/guides/rpg-core.md`, `docs/guides/rulesets.md` and
  `docs/features.json`.
- Two twins move together: `delve.mobs_at`/`mob_drops` and the player's
  `mobsAt`/`mobDrops` (curve, guard, chance, gold). `tests/test_descent_parity.py`
  holds them together.
- A worn thing's instance is a new saved key, written only for a pack that
  rolls or fixes traits, so `tests/test_store_keys.py`'s frozen contract
  holds for every other pack.
- Not in this change, named so it is not assumed: elites and groups on
  generated floors, monster weaknesses, status effects beyond burning,
  stock quantities and restock timing, classic (permanent) death, a map
  mark for the satchel beyond its arrival line, interface icons for rarity.

## Acceptance

`tests/test_rpg_core.py` (validation, bake, opt-out) and
`tests/test_rpg_core_play.py` (each rule played in the real woven player
in jsdom), the parity test, and the full gate.
