// ---- the bag: what the hero is carrying (loot + reward, first slice) ----
// A kill leaves its drop on the floor (see setupTown); walking onto it
// takes it. The bag remembers what was taken, per playthrough, per
// world: `vefr-bag-<world>` is a plain list of item ids. A duplicate id
// is still added (two potions are two potions) - the bag is a list, not
// a set, and the panel shows one row per thing carried. A carried thing
// can be used (when the pack gives it a `heal` and a `use`); selling and
// buying happen at a shopkeeper's Trade panel (see below). Since ADR
// 0017 an entry may instead be the instance a rolled drop left behind
// (rarity and hidden traits); the bag logic and the strip live in the
// gold part below. No weight and no dropping. The bag is capped only when
// the pack names a `bag.size`, and a carried thing's `carry` raises the cap
// (see `bagRoom` in the gold part); the town reads what it reads (see
// `195-the-identify-service.js`).
var BAG_KEY = 'vefr-bag-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');

