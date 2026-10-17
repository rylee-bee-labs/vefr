# Damage types, status effects and resistances

Status: **proposed, scope approved 2026-10-03.** Rylee chose the full triangle — types, status
effects, and resistance/immunity — over the lore-only and types-plus-one-status options. No code,
no pack contract, no ADR yet. This note records the shape the survey supports and the three
decisions still owed before any of it can be built.

Spec source: Rylee, 2026-10-03, in chat ("electrified or fiery or necromancer or whatever for the
mobs and the players"). The vocabulary below is the correction, because the request mixed four
different axes under one adjective.

## Slice 1 landed (vefr#497, 2026-10-16)

Rylee's decision in vefr#497 (issue comment 6221698162) chose Option B and named this slice: optional
damage types, resistances and status effects, begun as one small reversible fire/burning encounter
with accessible feedback, preserving existing balance and saves. What that decision has bought, in
the build order below:

1. **The resolver.** `elements.after_resist()` (engine) and `resolveDamage()` (player part 425) are
   the one place a number is changed by a resistance, and both damage paths call it. Resistance is a
   **divisor** (`{"fire": 2}` is half), so the numbers stay whole in both languages.
2. **`player.resist` / `player.immune`.** Settled above on 2026-10-03; built, validated, and baked
   only when a pack declares them.
3. **`burning`, one status effect,** authored on a hazard as `burns: {"turns", "tick"}`, on the
   `lightTick` pattern. It is **not stored**: a reload, a new region and a cozy death all end it, so
   no save changes shape. That answers open question 2 with the answer that changes nothing else.
4. **The encounter and its feedback.** Words on the live region and a words-only HUD line beside the
   health (`#hud-state`, kept on a phone), never a colour.

The pack contract is documented in [`docs/guides/elements.md`](../docs/guides/elements.md), the
pinned behaviour in `tests/test_elements.py` and `tests/test_elements_play.py`.

**Still owed, deliberately not in this slice:** a hazard authored in a Blueprint (its fields are the
closed `FIELD_KEYS` set, which is a format change and wants its own review rather than a side door),
resistances granted by worn gear (open question 3's second half), a second status effect, stacking,
and any damage type with no source yet.

## The vocabulary, because "fiery" and "necromancer" are three things each

| Axis | The term | Values |
|---|---|---|
| what the damage **is** | **damage type** | physical, fire, cold, **lightning**, poison, **necrotic**, acid, radiant, psychic, thunder |
| the **state** on a combatant | **status effect** (tabletop: *condition*) | **burning**, poisoned, bleeding, chilled, frozen, **stunned**, rooted, slowed, **silenced**, feared, charmed, blinded |
| the combatant's **relationship** to a type | **resistance / immunity / vulnerability** | the precise tabletop triple; this is what stops elemental combat becoming a damage race |
| where the magic comes from | **school of magic** | necromancy, pyromancy, storm-calling, conjuration, divination |

Corrections to the three examples Rylee gave:

- **"necromancer" is a character, not an effect.** It is the *source*. What it does is inflict
  **necrotic** damage, **raise** the dead, or leave a **hex**.
- **"fiery" hides three mechanics.** A mob that *burns* is **incendiary** and leaves **burning**
  (damage over time). A mob that *is* fire is **immune** or **resistant** to it. A mob that
  *erupts* deals **fire** damage. One adjective, three mechanics.
- **"electrified" is the state, not the type.** The type is **lightning**; the state is
  **electrified**, which in practice is a short **stun** plus small recurring damage.

Every status effect needs exactly two properties to be checkable: a **duration** (in turns) and a
**tick** (how much, how often). That is the entire data shape.

## What the engine has today (surveyed 2026-10-03; evidence in `.project/DECISIONS.md`)

- **Damage is two functions.** `heroAttack` and `enemyAttack` in `web/packaged.html`, both a bare
  integer subtraction. No randomness in combat anywhere.
- **The two paths are asymmetric.** The hero goes through `heroAtk()`; the enemy applies its raw
  baked `atk`. **So this needs a resolver applied on both sides** — otherwise fire will resist and
  necrotic will not, which is the kind of asymmetry nobody notices until a fight feels wrong.
- **No damage type, no resistance, no status effect exists.** Not in the rules vocabulary, not in
  the pack contract, not in the player.
- **The rules engine cannot own a status effect.** `applyActions` changes only
  `{flags, beliefs, fired, items, where, meanings}` — no combatant, no hp, no timer — and
  `validAction` is a closed chain that voids a whole rule for an unrecognised key. The code states
  the law: *"One returned action onto a surface that ALREADY exists - never a new subsystem."*
  A status effect therefore belongs in the **combat** layer, and extending the rules vocabulary
  would break a deliberate rule.
- **The pattern to imitate is item `light`,** not growth. `light` is a real countdown
  (`lightTurns`, `lightTick()`), and its four turn boundaries — `lightTick(); enemyTurn();` — are
  the de-facto "the hero's turn is over" idiom. Growth's `practice` mode is a monotone accumulator
  with a cap and **no expiry**, so it is the wrong shape for anything that ends.
- **A new enemy field is silently dropped unless threaded through four allow-lists**, and one of
  them is the **closed** `FIELD_KEYS`/`FIELD_ORDER` in `src/vefr/blueprint.py`. So every enemy field
  is also a **Blueprint format change** and therefore an ADR amendment.

## House constraints that bind

- **Colour is never the only signal** (accessibility rule 2). A burning mob cannot be *only*
  orange; it needs the word or the silhouette. The same applies to a resistance — never tint the
  health bar alone.
- Deterministic like the rest: no randomness, no model call, no clock.
- Every mechanic lands **tests first**, merged with strict xfail, then flipped by its own PR.
- Any new pack field is **ask-first** and needs a plain-sentence validator error.

## Open, and owed before code

1. **The resolver.** One function both damage paths call, taking (amount, type, attacker, target)
   and returning the number after resistance/immunity. Without it the asymmetry above is a bug.
2. **The status store and its tick.** A list of `{effect, turns, ...}` per combatant, decremented
   at the four `lightTick()` boundaries. Does it persist across a reload, and does it save? That
   interacts with ADR 0009 (rule saves) and needs an answer.
3. ~~**What the player can carry.**~~ **Settled 2026-10-03 (Rylee): resistances live in *two*
   places — the pack's `player` block as a base, and worn gear on top.** So the contract carries
   `player.resist` / `player.immune` as the floor for a whole run, and an item-level grant that
   equipment adds. **The gear half is cheaper than it looks and needs no ADR:** Blueprint's closed
   `FIELD_KEYS` govern *enemy* records, not items, so an item field is validated beside
   `item_slot_errors` and baked in `_player_items` with no format change. The enemy half still does
   need the ADR, because enemies must carry types.
4. **Is a status effect a Blueprint field, a pack block, or both?** It touches the closed key
   sets either way, so it needs an ADR amendment before code.
5. **Does gear-granted resistance stack, and does it show?** Rylee chose gear on top, which opens
   two small questions the pack contract must answer: does a second resistant item stack or does the
   strongest win, and does the hero's resistance get a visible readout. The accessibility rule
   says it cannot be a tint on the health bar alone, so a readout is implied.

## Build order, once the above are answered

1. Types only, as pure maths plus the resolver, with a node harness. No status effects yet: this
   is the slice that makes the resolver honest.
2. `player.resist` / `player.immune` as the base surface, read by the resolver on both paths.
3. Gear-granted resistance, on top of the base — the item field, `item_slot_errors`, `_player_items`.
   No ADR needed for this step, which is why it can come before the enemy work.
4. One status effect end to end (`burning`), on the `lightTick` pattern, with persistence decided.
   **This is the step that needs the ADR**, because the effect is authored on an enemy.
5. The accessibility pass (every signal has a word; resistance is never a tint alone).

**Deliberately not in this campaign:** a school-of-magic vocabulary (it is lore text and a sprite,
zero mechanics, and it can ride along with any of the above), duration extensions, stacking,
immunities that change mid-fight, and anything a model would have to decide.
