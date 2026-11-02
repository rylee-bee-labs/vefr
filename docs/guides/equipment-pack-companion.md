# Companion change: the equipment demo in a private pack

The engine side of equipment is done and verified (#244 pack fields, #247 the pure engine, #249 the
Bag panel). What is left for step 5 of `design/equipment.md` is **pack data**, and pack data lives
in your private pack repo — so this is the change to make there, not here. The engine records the
companion change rather than editing across the repo boundary
(`docs/agent-reference.md`, "Cross-repo boundaries").

## The change

Give an item a `slot`, and optionally `mods`. That is the whole contract. Both are optional and
additive: an item with neither plays exactly as it always did.

```json
"items": {
  "brass-ring": {"name": "a plain brass ring", "sprite": "ring",
                 "slot": "charm", "value": 12}
}
```

Verified against the engine tonight: this exact entry validates clean, and bakes as
`{"name": "a plain brass ring", "sprite": "ring", "value": 12, "slot": "charm"}` — the slot rides
along, and the ring becomes wearable in the charm slot with no stat change.

With stats, add `mods` (only `atk` and `hp`, each a whole number 0 to 9):

```json
"green-cloak": {"name": "a green hooded cloak", "sprite": "cloak",
                "slot": "body", "mods": {"hp": 2}},
"short-bow":   {"name": "a short bow", "sprite": "bow",
                "slot": "hand", "mods": {"atk": 1}}
```

## The rules, so a surprising validator error is never a surprise

- `slot` is exactly one of `hand`, `body`, `head`, `feet`, `charm`.
- `mods` holds only `atk` and `hp`, whole numbers 0 to 9. A bool is refused.
- A slotted item may still carry `value` and `keep`, but **not** `heal`, `light` or `use` — a worn
  thing is not drunk, lit or spent.
- An item a locked door names as its key (`requires.item`) **may not have a slot**. A key stays in
  the bag so it can open its door more than once, and a worn key could not.
- No `slot` means not wearable, and it behaves exactly as before.

Every one of those is a plain-sentence error from `vefr validate`, naming the item and the problem.

## What the demo needs from you

`design/equipment.md` step 5 says "Cottage's cloak, bow and ring wired to the round 8 icons". Today
the pack carries two items: `cloudy-potion` and `brass-ring`. The ring is ready to become a charm
slot today — it already has a sprite. **A cloak and a bow do not exist yet**, and their names are
yours, so I have not invented them.

So the demo is one of:

1. **The ring only.** Smallest true demo: one wearable thing, worn into the charm slot, taken off
   again. Everything is already in place and needs no new art.
2. **The ring plus a cloak and a bow**, once you have named them. This is the design's demo and it
   shows the swap (two body things, one charm) and the stat change.

Either way the art question is separate: the pack's `player.sprites` already has `ring` and
`potion`. A cloak and a bow would need new icons, which is a `offload image` draft for you to
review, not something to slip in unreviewed.

## Not done, and why it is not in this repo

- **The guardian ladder and the floor 3 lock** (build steps 2-3) need a new `guardians` pack block,
  which is a pack-contract change and therefore ask-first. It also waits on your naming — the role
  word is now **the Keybearer** (Rylee, 2026-10-03, from the Diablo III precedent), with the
  Cellar King at the bottom and each floor's name still yours.
- **The elemental campaign** (damage types, status effects, resistance) would touch enemy records,
  and enemy records are the Blueprint's *closed* key sets — so it needs an ADR amendment before
  code. Its companion change is recorded in `design/elemental-and-status-effects.md`.

## Verify a pack after any of this

```bash
uv run norns validate --pack worlds/<name>       # from the VEFR checkout
```

The engine pin matters: the pack's CI validates against a pinned engine commit
(`ci: validate the VEFR pack on every PR`), so bump that pin when you want the new fields to pass.
