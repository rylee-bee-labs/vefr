# 0015 - Wardens, vaults and the town gate

Date: 2026-10-04

## Status

Accepted. E8 merged in five parts (E8-0, E8a, E8b, E8c, E8d), 2026-10-05 to 2026-10-10. Plan: `docs/plans/endless-dungeon/PLAN.md` sections 1, 2, 4 and 5.

**Progress (2026-10-09).** E8a has landed the warden, in two parts:
- **Spawn and flag:** the Section's warden stands on the v3 warden anchor as `w`, and its defeat sets `warden:<id>:c<c>`, which keeps it beaten.
- **The key:** a Section's `warden` is either a name (spawned as that family; Cottage writes family ids such as `"cellar-king"`) or a record `{"family", "id"?, "carries"?}`. `carries` goes straight into the bag on defeat, and `vefr check` holds it to check 3: declared, `keep`, no `value`, dropped by no family.

E8b landed the vault: the stamp's socket is a door shut until the warden's flag is set, and its `note`, `chest` and `home` anchors hold the note, the loot and the stair home.

**E8c has landed the town half, in three parts:**
- **The story end is a per-game flag.** A `descent` block may name `"story_end"`, default `king-slain`, and the progress walk reads it wherever this ADR says `king-slain` ends the story.
- **Town states.** `town_states` is one block per region (the single block below is still valid), each `use` an ordinary authored region, the last true `when` winning on entry, derived and never stored, all of a region's states sharing that region's save identity. The act is 1 plus the number of true vault flags, which is what ADR 0006 is rescoped to.
- **The gate and the walk.** A Section's `vault` may be a record `{"stamp", "sets"}`; `sets` is the flag its note records, and it guards `town-seen:<section>:c<c>`, which the Section expansion's rule on `enters town` sets. The gate rides `requires` on the warden's down stair (and on any town stair entering a Section, which is the elevator rule's to grow). `vefr check` runs the flag-only progress walk inside its 200-seed Section sweep: checks 4 and 5, one clear sentence for a flag nobody can set.

The vault record's `note`, `chest`, `needs` and `home`, the warden record's other keys (`hp`, `atk`, `scale`, `hall`, `placement`) and Amendment 1's `challenge`, `yields` and `fightable` are refused as unknown until their slices (E8d for the amendment) add them. E10 has since added the warden record's `endless` (the `affixes` bound this ADR names) and the Section's own `endless` block. The paid shortcut is E10, and so is cycle 1 of the walk.

**E8d has landed Amendment 1's `challenge`, `yields` and `fightable** (2026-10-10), and with it the last of E8:
- **The challenge.** `challenge` is `defeat` (the default, and exactly what E8a shipped) or `rule`. A `rule` warden is completed by a pack rule setting `warden:<id>:c<c>`, and the moment that flag is set the key it `carries` goes into the bag with a line, the same as on death. The vault door, the town gate and the save rules read only the flag and did not change.
- **The two presentation keys.** `yields: true` leaves a beaten warden on its anchor, no longer hostile, instead of vanishing - including when the floor is rebuilt, which is the one exception to "a warden whose flag is set is not spawned". The flag is what makes it stay, so a `rule` warden killed in passing leaves its anchor and comes back hostile when the floor is rebuilt: its challenge is not complete, and nothing else may say that it is. `fightable: false` takes the blow away and nothing else: the warden still sleeps, wakes and hunts by ADR 0014, and it is refused beside any challenge but `"rule"`, because a warden nobody can fight and no rule can pass is a Section that cannot be finished.
- **Check 5's first step** is now the challenge rather than the killing, and a `rule` warden with no rule to set its flag fails the walk with one sentence, the same missing setter a vault note's flag is.

**What is still not here, and is not this ADR's slices.** The paid shortcut and cycle 1 of the walk are E10 (see below). The vault record's `note`, `chest`, `needs` and `home` and the warden record's `hp`, `atk`, `scale`, `hall`, `placement` and `endless` are still refused as unknown keys: `needs` is already covered by `carries` (check 3), the note and the chest are library books pinned to the vault's anchors, and no E8 slice reads the rest. `endless.affixes` is with endless mode. Note that `docs/plans/endless-dungeon/PLAN.md` line 260 lists the paid shortcut inside its E8 row, which is the one place this ADR's own numbering (the shortcut is E10, here and in the Progress paragraph above) and the plan's slice table disagree.

This ADR amends **ADR 0006**: "act advance" becomes **town states**. The edit to 0006 landed with E8c, in which ADR 0006's Status changed to **Superseded in part**.

Rylee's calls:
- a key warden ends each Section;
- the vault note advances the act;
- acts change only the town;
- the next Section waits for a visit to town, and a paid shortcut can skip that visit;
- the story end is the per-game flag `descent.story_end` (default `king-slain`), per Amendment 1 (ADR 0015, approved by Rylee 2026-10-08); endless mode comes after it.

## Context

E0b found that `lockOpen` opens a transition when `requires.item` is in the bag *or* `requires.flag` is `true`, never consuming the key, and that generated regions can be inserted before `enterRegion`. ADR 0006 moved the hero to a new act region; here only the town changes. Returning to town clears a Section's kills and chests, which would revive wardens and vault chests unless they are story state.

## Decision

### Warden

```json
{"id":"ashwing","family":"moth","hp":3.0,"atk":1.6,"scale":1.4,"carries":"ashwing-key",
 "hall":"warden-hall-moth","placement":"farthest-off-path","endless":{"affixes":1}}
```

- Closed keys; `placement` has one value; `hp`, `atk` in [1.0, 4.0], whole hundredths, combined as in ADR 0014.
- It stands on its hall stamp's `warden` anchor. The hall has exactly one used socket, so it is a leaf off the up→down path (asserted).
- Spawn `{"id":"w","family":…,"warden":"ashwing","at":…}`, outside the monster budget.
- On death the key goes **straight into the bag** with a line, so it cannot be lost, and `warden:<id>:c<c>` is set.
- In cycles `c >= 1` it draws `endless.affixes` affixes on the `loot|w` stream; "Proud" adds one.

### Vault

```json
{"id":"vault-cellar","stamp":"vault-small","needs":"ashwing-key","note":"library/truth-one.md",
 "chest":["…"],"sets":"vault-1-read","home":"town"}
```

- **The record as it stands (E8c).** A Section's `vault` is a stamp id, or a record holding `stamp` and `sets` - the two the engine reads today. `id`, `needs`, `note` and `chest` are refused as unknown until the slice that reads them lands; `needs` is already covered by the warden's `carries` (check 3), and the note and chest are library books pinned to the vault's anchors.

- **Where it is.** The vault stamp sits on the warden floor. Its single `+` is the **vault door**.
- **The door.** A transition with `requires: {"flag": "warden:<id>:c<c>"}`; its `locked_text` names the key. A flag, not the item, because keys are never consumed and a cycle-0 key would open every later vault. `needs` stays so `vefr check` can trace the key.
- **UNKNOWN: how the door opens.** Its `to` is the same region and `to_at` the tile just inside. Whether `enterRegion` into the current region keeps floor state is UNKNOWN; E8's first test checks it. If not, E8 adds a B2 `door` place that opens in place; nothing else changes.
- **The note.** The `note` anchor is a library book. Opening it fires the shipped `opens {what: <book id>}`, and a rule `opens → set <sets>` records that it was read.
- **The chest and the way home.** The `chest` anchor holds the loot. The `home` anchor is a stair to `home`.

### The town gate and the paid shortcut

- The warden floor's down stair and the town stair's entry for the next Section carry `requires: {"flag": "town-seen:<section>:c<c>"}`.
- A rule on `enters town`, guarded by the vault's `sets` flag, sets `town-seen`. The Section expansion emits it; packs never hand-write it.
- **Shortcut:** offered only when `c >= 1`, so a first pass never skips the story (plan challenge 7). Paying spends the one-use item the Section's vault drops (not gold) and sets `town-seen:<s>:c<c>` and `shortcut-paid:<s>:c<c>`; a second press finds the flag set and charges nothing.

### Town states (ADR 0006 rescoped)

```json
"town_states": {"region":"town","states":[
  {"id":"act-2","when":"vault-1-read","use":"town-act-2"},
  {"id":"act-3","when":"vault-2-read","use":"town-act-3"},
  {"id":"after-king","when":"king-slain","use":"town-after-king"}]}
```

- Each `use` is an ordinary authored region, baked as usual: no patches, no new runtime language.
- Entering `region` loads the **last** state whose `when` is true, else `region`. Derived on each entry, never stored.
- The act is 1 plus the number of true story vault flags; `king-slain` opens the endless board. ADR 0006's `act-completes` event and per-act surfaces are withdrawn.
- All states share `region`'s save identity. A dropped item now on a wall moves to the nearest floor tile, scanning row-major.

### Save state

- **Permanent story flags.** These are never evicted or reset:
  - `warden:<id>:c<c>` and `vault-chest:<id>:c<c>`;
  - each vault's `sets` flag;
  - `town-seen:*` and `shortcut-paid:*`;
  - landings;
  - `king-slain`.
- A warden whose flag is set is not spawned; a vault chest whose flag is set opens empty. A town return cannot revive either.
- Floor deltas are the plan's: identity triple, killed ids (including `w`), taken chests, dropped items, found secrets, explored bitset.
- **The bitset encoding** belongs to slice F1; beyond "1 bit per tile, base64" it is UNKNOWN. At 128x96 the raw bitset is 1,536 bytes, about 2 KB in base64, over the 1.5 KB per-floor budget: F1 must run-length encode it, or the owner raises the budget.
- An identity mismatch drops deltas and keeps every flag. The 40-floor cap evicts only deltas.

### What `vefr check` must prove

These hold for every Section, for seeds `check-0..199`, in cycles 0 and 1:

1. The hall and the vault are placed (ADR 0013). The `warden` anchor and the vault door can be reached from `up` without using secret doors.
2. `note`, `chest` and `home` can be reached from the vault door.
3. `carries` names a declared item that is `keep` and has no value. That item is in no shop, in no chest table, and in no secret room.
4. Every `sets`, `when` and gate flag has a setter.
5. **Progress walk.** A flag-only simulation starts with no flags and repeats three steps over the Sections: kill the warden, read the note, enter town. It must open every Section and reach `king-slain`. In cycle 1 it must also succeed when it uses the shortcut, and the shortcut must never be offered in cycle 0.
6. Every `use` region exists and validates.

## Consequences

- One gate mechanism: `requires` flags through `lockOpen`; the Keybearer chain becomes flag locks.
- Each town state is one more baked region (ADR 0006's bake cost; town maps are small).
- About five flags per Section per cycle: negligible.

## Acceptance

- `tests/test_wardens_vaults.py`: the shapes, golden rejection sentences, and checks 1–4.
- `tests/test_progress_walk.py`: check 5, plus a fixture with a missing setter that fails with a sentence.
- `tests/test_town_states.py`: the last true state wins, no true flags gives the base region, and an item moves off a new wall.
- `tests/browser/test_vault_to_town.py`: the warden dies and the key is in the bag; the door opens; the note is read; the home stair leads to a changed town; the next stair is open.
- `tests/browser/test_shortcut.py`: there is no shortcut in cycle 0; in cycle 1 it charges once, and pressing again is free.
- `tests/test_story_flags_survive.py`: after a town return, an identity mismatch and an eviction, the warden stays dead and the chest stays empty.

## Owner decisions (2026-10-04) and open questions

1. **Decided: offered from the second cycle on, and paid with a one-use item found in a vault** (not gold). **Every section's vault drops one** (owner, 2026-10-04).
2. **Decided: no town gate in endless mode** (owner, ELDEC 2026-10-11/12).
3. **Decided: New descent counts as a later cycle** (owner, ELDEC 2026-10-11/12).
4. **Decided: endless vaults hold loot only, no notes** (owner, ELDEC 2026-10-11/12).
5. **Decided: its own region behind the final boss's door.** *(Per game since Amendment 1: a pack may end its story without a final boss.)*
6. **Decided: town lines, residents and shop stock use the pack drafts verbatim** (owner, ELDEC 2026-10-11/12).

## Amendment 1 (approved by Rylee, 2026-10-08)

Rylee, 2026-10-08: *"I approve the proposed amendment to ADR 0015."* Her boundary: *"Do not treat this approval as permission for a broader engine redesign."*

Cottage of the Breeze, Rylee's decisions of 2026-10-08: **"No final boss"** (the story ends in a quiet room you reach and return from) and **"Different kinds of guardian encounters"** (a fight, a way past, an interaction). Her guidance: *"The engine should retain the ability to support final bosses in other games"* and *"I do not want a Cottage-specific workaround or three separate engine systems if an existing encounter contract can support these differences."* E8 is not built yet, so this amends design text only. Everything above stands except where this section says otherwise.

1. **The story end is a per-game flag.** A pack's `descent` names it: `"story_end": "<flag>"`, default `king-slain`. A final boss behind its own door, as decided above, stays fully supported. A pack may instead set the flag with any rule, for example on entering a final authored region reached through the last Section's vault door. Endless mode opens on `story_end`. Wherever this ADR says `king-slain` opens the endless board or ends the progress walk, read `story_end`.
2. **A warden's challenge.** A warden takes an optional `"challenge"`:
   - `"defeat"` (the default): exactly the current text. On death the key goes straight into the bag and `warden:<id>:c<c>` is set.
   - `"rule"`: a pack rule sets `warden:<id>:c<c>` (for example on `picks-up`, `uses-with` or `comes-near`). The moment the flag is set, the key goes into the bag with a line, the same as on death.

   The vault door, the town gate and the save rules see only the flag, so they do not change. Two optional presentation keys:
   - `"yields": true`: a defeated warden stays on its anchor, no longer hostile, instead of vanishing.
   - `"fightable": false`: only with `"rule"`. The warden cannot be attacked. It still sleeps, wakes and hunts by ADR 0014's sight and noise rules, so the hall stays dangerous and the Section's danger still rises.
3. **Town states for more than one region.** `town_states` may be a list of `{"region", "states"}` blocks, one per region (the town, an interior such as a tavern or a home). The single-block form above stays valid. Each region still loads its last true state, derived on entry and never stored.
4. **The checks.** Check 5's "kill the warden" becomes "complete the warden's challenge" (set its flag), and "reach `king-slain`" becomes "reach the pack's `story_end`". Check 4 (every flag has a setter) already requires a setter for a `"rule"` warden's flag, so a rule warden with no rule fails `vefr check` with a sentence.
5. **Acceptance additions** (in E8's tests):
   - a fixture whose warden has `"challenge": "rule"` passes the progress walk with a rule as its setter, and fails with a sentence without one;
   - a `"yields"` warden stays on its anchor after defeat;
   - a `"fightable": false` warden cannot be attacked;
   - a list-form `town_states` loads per region;
   - a pack whose `story_end` is set by entering a region opens endless mode with no boss.

**Compatibility.** Every key this amendment adds is optional, and its default is today's behaviour: `story_end` defaults to `king-slain`, `challenge` to `defeat`, and the single-block `town_states` stays valid. Existing saves and content keep working, and rising danger is unchanged.

**Order.** A `"rule"` warden needs rules that can name things on a generated floor. That comes from VEFR's pinned-placement work (books, chests and named things at a depth), which E8's vault notes also use. E8 may therefore ship `"defeat"` first and add `"rule"` once that work lands. Nothing here changes ADR 0010, 0013, 0014 or 0016.
