# vefr - Roadmap

> The three Norns weave fate at the well beneath the world tree -
> not one fixed fate, whichever one is given them. This is the
> ladder from a tool built for one story, playable - to a tool
> anyone can point at their own.

## Where VEFR stands (2026-10-12)

> **Principle:** Cottage of the Breeze is how VEFR is built. Every lesson from it lands in the engine so the next game is easier to make.

> **Studio product vision (2026-10-12, proposed):** VEFR is also a game about **learning to make games**, designed first for people with imagination and no technical background. A resident-led visual workshop should guide a creator from their own idea through visible experiments to a tiny playable, explainable, shareable slice. The [twelve owner decisions, one-round research, built-vs-proposed inventory, and phased Studio plan](docs/plans/studio-creative-learning-vision.md) are a **product-direction proposal**, not permission to interrupt Cottage, current epics, or the evidence-led game -> gameplay feature -> core rule.

Cottage of the Breeze **Release 1** (a complete, polished Act 1, built through VEFR over one night) turned this roadmap from "make a game possible" into "make the next game easier". Acts 2 and 3 are part of the larger three-act direction and were left for later by Rylee's decision; that is a scoping choice, not an engine limit. This board is built from what the run proved and from the ranked discovery record, [`docs/research/cottage-release-1-learnings.md`](docs/research/cottage-release-1-learnings.md) (ten findings, each with evidence). The long list below stays as the history. Tags: **[engine]** capability, **[authoring]** developer experience, **[QA]** validation and checks, **[player]** what the player sees, **[Cottage]** content that lives in the game's repo.

### HOW VEFR GROWS

The architecture rule is deliberately small ([ADR 0012](docs/adr/0012-gameplay-features.md)):

```text
specific to one game          -> game
reused by two real games      -> gameplay feature
needed beneath several uses   -> VEFR core
```

A **gameplay feature** is the learner-facing name for a reusable gameplay system
or mechanic. Features use the same public VEFR vocabulary as games; this does
not add a plugin loader, package manager, second runtime or second authoring
language. Promotion is evidence-driven: the second real consumer earns the
abstraction, and the change must delete duplication or make an invariant
enforceable rather than merely shorten syntax.

The endless dungeon is the first real use of the rule: sections, key wardens, stamps, elites and play-time floors are built as VEFR features ([plan](docs/plans/endless-dungeon/PLAN.md)) so a second game can reuse them by writing data, and Cottage only supplies content. Cottage is the depth test. Independent overnight games are breadth tests.
Burrito Journalism is the later composition test: many short chapters may feel
like different kinds of games, but should prefer combinations of existing
gameplay features over new core machinery.

### SHIPPED (proven by Cottage Release 1)
- [engine] `complete-act`: a story beat can end with one accessible card, once per save (#252). It does not advance acts yet.
- [engine] Locks on doors and stairs, used for three stairs and a sealed door (#229); equipment in five slots (#244 to #251); Blueprint families (22 families, 73 creatures); durable rule saves; the skin loader.
- [QA] `vefr check` follows every lock and names a key that cannot be found, sits behind its own door, or could be sold (#253).
- [QA] `scripts/check` runs the CI commands locally, before the PR does: `--fast` before a push (lint, tests of the changed code, gitleaks on the diff), `--full` for the whole set, `--list` for the step table, `--merge-ready` to merge `main` into the branch in a throwaway worktree and check the merged tree. A step this machine has no tool for is a `SKIP` with a reason — a SKIP is not a pass, and CI is still what decides the PR. CI-only steps are listed as CI-only, never faked.
- [player] The sticker album, slice 1 (#254); a small set of soft synthesized sounds with a switch (#257); walk sheets, a character that walks in four directions (#258); stairs say "up" when they go up (#255).
- [player] Player words v0: one message table holds every action-critical line a player reads in order to act (the four where-next hints), a pack may name its own word for any of them in `world.json`'s `player_words`, and `vefr check` refuses a blank, non-string or place-less one — evidence for #259, whose "To reach floor-1, go north-west" is a region id where a place name belongs.
- [authoring] The player is built from parts: 56 files in `web/player/parts/` joined byte for byte into the committed `web/packaged.html` by `scripts/build_player.py` (#264); `scripts/weave_digest.py` proves a refactor changed nothing.
- [authoring] `vefr look`, `vefr probe`, `vefr publish`, `vefr features`; the Library chapters on locks and endings and on gear, albums, sound and walking (31 chapters on the shelf).
- [Cottage] Six floors, three Keybearers and the Cellar King, the King's room and an ending, eight unique monsters, eight wearable items, 25 stickers, a keyboard-only playthrough bot (desktop and phone) and an accessibility pass. All story text is agent draft until Rylee approves it.

### LANDED 2026-10-12 (Cottage Section 1 and the mobile UI rounds)
- [player] Descent creatures show their own art, the bag stacks by kind (id and rarity, up to eight then "+N"), and the
  camera comes closer on dark floors (#412). A way out is drawn as what it is: door, stairs up, stairs down,
  trapdoor, from the pack's own pictures when it has them (#416).
- [player] A game can choose a phone zoom (`display.phone_tile`), and on a phone the camera follows the hero up to
  three tiles past a map's edge, so she is never under the controls (#418).
- [player] Talk with no conversation brain says the resident's own seeded line for the time of day, and a resident
  with nothing to say is not offered Talk (#419).
- [player] A Section's `label` reaches play: a hint names a floor of it "the Cellar, floor 2" instead of the region id
  `cellar-0-2`, whose id, floor key and save keys are unchanged; a Section with no label reads as before (#363).
- [player] Arriving on a floor of a labelled Section names the floor, not the stair back up: the POI line and the
  button say "the Cellar, floor 2", and reading it points to the stair down. The up-stair is still drawn and
  walkable, and a Section with no label arrives exactly as before (#362).
- [authoring] The Storybook design system and its art bible (Cottage's look, kept as a worked example; every game
  chooses its own), and the guide to making a VEFR game look and feel good (#415).

- [player] An object layer: props with footprints, depth, a ground layer and animation; every character's idle,
  talk, act, attack and hurt; people who stand in the way (`player.people_block`) (#420). Pixel art drawn crisply
  (`display.pixel_art`, #427). Phone touch controls: a floating joystick, one smart button, Bag, size and a
  left-handed layout (#428; Whisper and Explore on a phone are #431). Cottage's Game Boy Advance town is built on
  all three (cottage-of-the-breeze#146).
- [player] Sweep fixes: the note's label, the wake line, and the phone Messages panel folds (#433).
- [engine] Bag capacity: an opt-in `bag.size` that leaves an item on the floor past the cap, with a warden's key
  always fitting (#434; follow-ups in #343). A vault's chest is keyed by the vault's own id and stays taken across a
  town return (#435).
- [authoring] "Make your first game", one page for a beginner (#429), and the Studio creative-learning vision
  (#421, proposed).

### LANDED 2026-10-13 (the storybook layout, built from Rylee's phone and desk playthroughs)
- [player] A mirrored walk frame really faces left on screen, and a drag on a phone never moves the page (#444).
- [player] The storybook phone layout (#445): a slim top bar (health, quickslots, a pill Menu; level and gold in
  the Bag), one message line that fades after 3 s, and only the smart button and Bag over the world (Whisper and
  Explore stay on Q and O; the Journal can "Listen for a whisper"). Phone text and panels are smaller, the Dark look
  stays dark on a light-mode phone, and a walk sheet hero walks without the lean and squash. A skinned pack can
  start on the plain look (`display.look`).
- [player] A desk follows the hero too (`display.desk_tile`, 32 to 96): the stage is the window, and messages are
  the phone's one fading line (#446).
- [engine] A Section can dress its generated floors with decor (#442, #443).
- [player] One name for the interact key: every hint, label and key letter says F, and E stays an
  unadvertised alias that still reaches the same verb, combat included (#467).

### LANDED 2026-10-14
- [player] **Whisper is now Listen** (#470): the button, its tooltip and the touch label say "Listen (Q)", and the
  rumor reads as overheard ("You overhear <the speaker>"), so it no longer looks like a whisper to whoever is
  standing next to you. How to play names it. The engine keeps its own name for the feature; the Journal's
  "Listen for a whisper" is unchanged.
### LANDED 2026-10-14 (the title screen takes the game's own keys)
- [player] `F`, `E` and `Space` start the game from the title screen, next to Begin and `Enter`, and `Tab` keeps the
  focus on Begin: it used to walk the focus onto the BODY, an invisible stop that swallowed the next `Enter` (#466).
  In run-001 that cost 29 of 50 decisions; 7 of 16 runs pressed `F` first on this screen. Tests:
  `tests/browser/test_title_screen_keys.py`.
### LANDED 2026-10-14
- [player] The game canvas is named for the place the hero is standing in (#461): the fixed "The town, seen from
  above" follows every region change, so a screen reader says "The cottage kitchen, seen from above" indoors and
  a descent floor answers with its Section's own label. Tests: `tests/test_canvas_place_label.py`.

### LANDED 2026-10-14 (the fight, from the keyboard)
- [player] The combat row keeps the focus on the verb you last used, so a fight no longer costs eight Tabs a turn back to the buttons; the verbs answer `1`, `2` and `3` and print their digit (#463).
- [player] The result line is one plain sentence per action - what Strike, Console and Hurl did - instead of naming the action (`last action: console (dusk)`). The wording is the engine's and stays game-name-neutral, and a pack replaces it through `player_words` (`combat.<verb>`; `vefr check` does not know those keys yet - see the known gap in [rulesets.md](docs/guides/rulesets.md)).

### IN PROGRESS (decided by Rylee on 2026-10-04; refreshed 2026-10-12)
- **The endless dungeon** (epic [#273](https://github.com/rylee-bee-labs/vefr/issues/273); design `docs/plans/endless-dungeon/DESIGN.md`, build plan `docs/plans/endless-dungeon/PLAN.md`, research `docs/research/big-generated-maps.md`): floors generated while you play from `seed + depth`, cut into sections of 8 to 11 floors; each ends in a key warden whose key opens a vault with a lore note; acts change the town only; elites, linked groups, hand-painted stamps and much bigger maps (up to 128x96, kept cheap for phones); an endless mode after the story.
  - **Merged:** E0a measurements (#278), F1 fog as a bitset (#287), E0d sleeping monsters and a radius-bounded flood (#288), E2 the v3 Python floor generator with property sweeps (#289).
  - **Decided (ADRs, #293; 0015 Accepted 2026-10-10 with E8d):** [0013 stamps](docs/adr/0013-stamp-format.md), [0014 elites and groups](docs/adr/0014-elites-and-groups.md), [0015 wardens, vaults and the town gate](docs/adr/0015-wardens-vaults-and-the-town-gate.md), with Rylee's answers recorded in each: sight plus noise wakes sleepers (fighting 12 tiles, doors and chests 6, stairs and breaking 8); the warden is awake and hunts once you enter its hall; reload resets sleepers; cozy affix names; six starting stamps (a 21x21 throne room, a random elite room, a room of 3 to 6 chests where one is likely a monster, a shrine, a treasure nook, a sleeping den); only decorative stamps rotate; required stamps always place; the paid town-skip shortcut is a one-use item, one per section vault, offered from the second cycle; the final boss has its own region.
    - **Landed (E4, sections):** the Section pack is one row on the [schema table](src/vefr/shapes.py) (`sections/<id>.json`, PLAN.md section 2 verbatim, `id` and `families` required and everything else defaulted) with 39 pinned golden sentences; `vefr.sections` reads a pack into the depth curve (`locate(depth, pack) -> (cycle, section, k)`, the story being cycle 0), the floor key `run_seed/section.id/cycle/k`, floor identity `(gen, section content hash, floor key)`, the floor pattern, the two landings a Section has and the flag each sets; `vefr check` sweeps every Section x 200 seeds and proves its floors hold; `vefr delve --section <id>` bakes a whole Section, its landings wired straight back to town. A second fixture pack with different Section data validates green with no code change.
    - **Landed (#364, how far a Section sees):** `fog.radius` may be 2..32, and 32 is a quarter of the widest floor `size` allows (128) - a Section now says how far it sees as a fraction of its own floor instead of against a bare 8 that no ADR, PLAN.md or pack records the reason for. The low end is unmoved, the radius a pack that says nothing gets is unmoved (`delve.DEFAULT_FOG_RADIUS`), and the lit area is still a disc: what to draw instead of a circle in a floor of rooms was Rylee's call on #364, and she answered it the next slice (below).
    - **Landed (#364, what a Section's fog is drawn as):** `fog.shape` names `"circle"` or `"square"`, circle first and circle the default - Rylee picked the square on 2026-10-09, and the option she turned down (sight that grows with what the hero has seen) is not here. A square lights every tile within the radius on each axis, so it holds every tile the disc holds and its corners reach further; the shape rides along in a floor's `fog` block only when it is the square, so a pack that names nothing and one that names `"circle"` weave to the same bytes. Nine floors of the fixture descent digest to the same bytes before and after, and the drawing is one branch in `litNow` - the circle keeps the expression it had. Tests: `tests/test_fog_shape.py`.
    - **Merged 2026-10-05:** E7 elites and groups (#299: affixes, linked groups, noise wake-ups, a leash on every member, ADR 0014's draw order stated as the order of the draws), E5 stamps (#301: hand-painted rooms in the v3 generator and `vefr stamp check`; required stamps place on 100% of eligible floors, optional ones have no minimum), E3 the v3 JavaScript twin (`web/player/parts/396-engine-delve-v3.js`, the runtime beside the Python spec, with `tests/test_floor_v3_parity.py` comparing 200 seeds x every size x every floor kind stage by stage in the woven player and `tests/browser/test_floor_v3_parity.py` measuring the PLAN.md section 3 budget in Chromium; E5b's stamp half landed with it) and **E1 play-time floors** (#314: the pack's `descent` block and `vefr check` on it, `locate()`, a v2 floor drawn at the stair from a run seed, the virtual region, the deltas kept through `store()` inside the budget of PLAN §3, the New-descent control, and the one-time `gen_version` card a Release 1 save is offered). **Next by the chosen order:** E8 wardens and vaults; E4 sections as the plan needs them.
    - **Landed 2026-10-09:** E8c town states and the gate - a pack's own `story_end` flag (ADR 0015 Amendment 1 §1, default `king-slain`), `town_states` as one block per region with the last true state winning on entry, the `town-seen:<section>:c<c>` gate the Section expansion emits on the warden's down stair, and the flag-only progress walk `vefr check` runs inside its 200-seed Section sweep (checks 4 and 5: every flag has a setter, and the walk reaches the story end).
    - **Landed 2026-10-10:** E8d the warden's challenge (ADR 0015 Amendment 1 §2 and §4), and with it the whole of E8 - **ADR 0015 is Accepted**. A warden record takes three optional keys, all defaulting to today's behaviour: `"challenge": "rule"` makes a pack rule the thing that sets `warden:<id>:c<c>` (and the key it carries goes into the bag the moment the flag is set, the same as on death), `"yields": true` leaves a beaten warden on its anchor, no longer hostile, instead of vanishing, and `"fightable": false` - which is only right beside `"challenge": "rule"` - takes the blow away and nothing else, so the hall stays as dangerous as it was. The progress walk's first step is the challenge rather than the killing, and a rule warden with no rule to set its flag is one plain sentence. The warden's own drops are read against the pack's catalog now, the last of the four drop surfaces D114 left unchecked. Compatibility is proved by digest: a pack naming none of the three keys contributes byte-identical descent bytes to its weave (`tests/test_warden_challenge.py`). **Next by the chosen order:** cycle 1 of the walk. (The paid town-skip shortcut was dropped 2026-10-12, vefr#438: with no town gate in endless mode it has nothing to skip.)
    - **Landed (#357, a Section's own monster count):** `mobs` is one optional key on a Section, a table of whole counts keyed by floor with a `from` entry for the floors it does not name (`{"1": 4, "from": 12}` = four on the first floor, twelve on the rest, `0` allowed). It replaces the area budget - one per 30 walkable tiles, clamped to 4..36 - which put 20 to 35 monsters on a floor 1 no pack could argue with, and it replaces it on the floors it names only: a Section that writes no `mobs` draws the floors it always drew, byte for byte. Read by `vefr.sections.mob_count` and applied in `vefr.delve_v3.mob_budget` - the v3 pop stage AND the play-time descent's own `mobs` list - with the JavaScript twins in parts 396 and 397 reading the same table through the same rule. It is read before the first draw and moves no other stage: the `size`, `plan` and `layout` streams do not see it, so a pack can add a count to a Section it has placed things on by coordinate without redrawing anything. `vefr check` refuses a count that is not a whole number, one outside 0..36 (ADR 0014's cap) and a key that names no floor, each at its own pointer with the Section named. Documented beside the Section contract in `docs/guides/rulesets.md`; tests: `tests/test_section_monster_count.py` (the issue's four bullets, incl. a layout compared byte for byte over 200 seeds and digests captured at `d5ce84c` for the two packs that name no count).
    - **Landed (#442, a Section's decor):** `decor` is one optional key on a Section, a list of `{"pic", "on": "floor" | "wall", "every"}` that scatters small `props/` pictures over its generated floors on their own `decor` stream. Decor never blocks, sits under everything else and is left out of the floor identity, so a dressed Section keeps every saved floor; a Section without it draws the same bytes. Python (`delve.decor_at`) and part 397 draw the same decor; tests: `tests/test_section_decor.py`.
    - **Landed 2026-10-11:** the stair past the last Section into endless cycle 1 is shut until the pack's `story_end` flag is set, with a sentence that names the flag (ADR 0015 Amendment 1 §1); the stair carries that flag instead of the town gate, since a stair carries one flag. Browser test: `tests/browser/test_endless_gate.py`, not yet run on the host.
    - **E8c's ground, vefr#359:** a monster the play-time descent spawns carries an `xp`, so a kill on a generated floor pays and shows the `level` cue exactly as an authored region's does. A Section's family row may declare its own `xp` (optional, additive); a family that declares none takes the engine's documented default, which rises with the floor's depth so the deepest Section pays most. Python (`vefr.sections.xp_for`) and the JavaScript twin answer identically, proved over 200 seeds.
  - **Merged 2026-10-09 (#350):** Cozy death on a generated floor wakes the hero on that floor at its up-stair, whole, with the descent intact and the why-log naming the floor - it no longer throws the run away to the pack's baked wake point; and a new run rewires the stair into the deep, so entering the descent lands on that run's floor-one up-stair instead of the tile the previous run drew.
  - **E8 is complete** (#369 to #373, #384, #404, #408, #435; vefr#341 closed 2026-10-12). Its follow-ups landed in the 2026-10-12 issue sweep: landings climb to town at play time (#366), a Section's `label` names its floors in play (#363), arrival announces the new floor (#362), and `sight: 0` stays 0 (#437). The paid town-skip shortcut is dropped (#438, Rylee 2026-10-12): with no town gate in endless mode it has nothing to skip.
  - **Known gap:** the 128x96 monster-turn numbers after E0d were not re-measured (the bench needs rework for sleeping monsters).
- **The in-world interface** (epic [#268](https://github.com/rylee-bee-labs/vefr/issues/268); `docs/plans/interface/PLAN.md`): the stage and the phone dock merged (#275), and backdrop/type skin slices merged (#300). The remaining soft-wood skin/HUD slice merged as #302 (speech box, slots, tabs, tooltip, divider, banner, HUD icons and the speech portrait).
- **Tighten the shapes** (epic [#267](https://github.com/rylee-bee-labs/vefr/issues/267); `docs/plans/tighten-shapes/PLAN.md`, ADR 0010): **merged** K1 shared test kit (#272), K2 one `store()` helper with a ban-lint (#276), B0 sprites by name (#277), S1 schema table core (#281), A1 art ledger and `vefr art` (#283), A3 skin kit manifest (#290), B2 places in Blueprint format 3 (#292), B1 things in Blueprint format 2 (#297, including its review-fix round), and S2 the one event table (#269: the eleven events and each event's payload now live once in `shapes.EVENTS`, read by both the rule and sticker validators; the JS twin follows in S3). **Next:** B4 packs and the Cottage trial, A4 `vefr art draw`, A5 `vefr art picker`, S3 the generated JS `EVENTS`.
- **The orchestration platform** (repo `Rylee-Bee/agent-platform`, which merged the old `agents` and `agent-config` repos on 2026-10-04; plan and decisions in `docs/plans/orchestration-v2/`): **merged** P0 fixes, P1 capacity meters, P1b classifier harness, mission wait-any and PR links, land/review, P3a capacity governor, dispatcher spec, the S1 bubblewrap worker sandbox (#18), author/reviewer model receipts (#27), the single-coordinator/review-gate hardening (#28), and on 2026-10-05 a Stop guard for sessions driving a mission (#30), a friction log (#31), the owner's decisions in every worker brief (#32), a cleanup that keeps a clone's work first (#33) and a live Now block for each repo (#34). The older P2 worker-contract draft (#8) explicitly remains **DO NOT MERGE**; its unsafe pre-sandbox shape is historical work, not the current platform path.
- **Housekeeping:** the three contradiction audits returned; four verified VEFR fixes merged (#291). Gallery sync (studio) merged.

### NOW (small, high leverage, straight from real use)
1. [authoring + QA] **Story status**: a pack can say which words are draft and which Rylee approved; `vefr check --release` lists drafts. (finding 1, new)
   - **Landed (2026-10-09, #339):** optional `status: draft | approved` (default `approved`) as a sibling key on books' front matter, voice files, `say` rules, album sticker names and item names; `vefr check --release` lists every draft with file and line and exits 0, `--strict` prints the same list and exits non-zero. No player-facing change: nothing under `web/` reads the key.
2. [authoring + QA] **Scenarios**: open the game, `vefr look` and the bot in any named state; generalises #260. (finding 2, new)
   - **Scenario half landed (2026-10-09):** `scenarios/<name>.json` in a pack, checked by `vefr check`; `vefr look|probe --pack P --scenario NAME` open the woven game in that state (ADR 0016 P2). Next: the capsule's capture and import, and the Cottage bot reading scenarios.
3. [QA] **Stage containment and panel accessibility**: every control inside the stage at many sizes, and every menu panel walked with axe. (finding 3, new; the containment and no-overlap tests are written and drive the interface slices; the panel walk is still to do)
   - **Sizing and seeding landed (2026-10-09):** `vefr look --sizes WxH[,WxH]` photographs a pack at each size, one file per size, and repeats its containment report at every one — so "the check measured the viewport, not the stage" stops being possible; `--at REGION X,Y` starts a run off the world's start region and `--seed` asks the descent for a run seed through the player's own `?vefr-seed=`. The fight verb row now stands inside the painted play panel rather than the page, and `#interact` keeps its whole label at phone widths (#353, #344).
4. [QA] **Obtainability**: widen the lock check to gear, books, stickers and creatures. (finding 4, deepened)
5. [authoring] Region display names for hints (#259). A Section's optional `label` landed (#407) and is validated; showing it in the hints and the floor announcement is #363.

### NEXT (what Act 2 and the next games need)
- [engine] ~~**Town states**~~ landed in E8c (#384; [ADR 0015](docs/adr/0015-wardens-vaults-and-the-town-gate.md)); **status effects** (fire first; `design/elemental-and-status-effects.md`, a campaign with an ADR amendment).
- [engine] ~~Random floors phase 2 (#215)~~ now slice E1 of the endless dungeon; **guardians** as pack data (placement sentences from ADR 0010 are the first step).
- [authoring] Honest feature detection and engine requirements per pack (finding 5); a route through a pack and one stable play-state API (finding 7); the overlay lane for hand edits on generated floors is superseded by Blueprint `places` (ADR 0010).
- [QA] A route through a pack plus one stable play-state API (7, new); a balance report from pack data (8, new).
- [player] Album logs (bestiary, items, map).

### LATER (worthwhile, no immediate evidence or dependency)
- [authoring] `vefr where|explain|map` development questions (finding 10, new).
- [authoring + QA] **Independent overnight game trials**: rotate capable models, give each the public creator surface and a blank game, forbid engine edits unless the game truly cannot be expressed, and record complete / gameplay-feature change / core change / workaround / docs gap. Repeated friction across unrelated games is evidence; one strange game is not.
- [QA] **1.0 readiness signal**: use ten consecutive independent overnight runs as a working window. Aim for at least eight complete playable games, at least seven with no core change, and no repeated unresolved creator-surface failure. This is a product signal, not a compatibility promise.
- [release] **Burrito Journalism composition pass**: the launch game may use many short chapters with different play styles; add or combine gameplay features before adding genre-specific core code.
- [player] Music; a second skin; per-run guardians and weighted tables; `stakes` as a real mechanic; optional Ink conversations (#143); richer floors (#145); save compatibility across content changes.

## Landed

- [x] **The game says that walking into an enemy is the attack, once** (2026-10-14, [#464](https://github.com/rylee-bee-labs/vefr/issues/464)): bump-to-attack was the one rule a player could only learn by accident - run-002 step 48 reads "You hit a nest of moths for 2. a nest of moths falls." and the explorer's note was "I only moved, yet the moths fell." The line gave the result away, never the rule. The first landed blow of a game now says one plain sentence, "Walk into an enemy to strike it.", held to the end of that turn beside the growth lines so a counter-blow cannot wipe it off the screen before the player has read it, and after the fight's own words so a phone - which draws one message line - draws it too. It is said once per world (`vefr-strike-hint-<world>` in the player's storage, so a reload does not bring it back and Start over clears it with the rest), and a pack names its own words for it in `player_words` as `combat.walk_to_strike`, the table's first row with no `{place}` to fill and so the first `sentence` kind on the schema table. No pack contract change beyond that one optional key, and a pack that names none plays the engine's line byte for byte. Guide: [`docs/guides/rulesets.md`](docs/guides/rulesets.md) (Bump to attack; Player words); tests: `tests/test_strike_hint.py`, `tests/test_player_words.py`.

- [x] **A deep landing's up-stair is the way home during play too** (2026-10-12, [#366](https://github.com/rylee-bee-labs/vefr/issues/366)): floors generated during play now follow the elevator rule that `delve --section` already bakes. A floor whose pattern slot is `entry` or `landing` climbs straight to `descent.entry.region` at `descent.entry.at`. It no longer climbs one floor at a time. Each landing the hero reaches is kept in the save's `flags.landing`, so it stays after a reload. Floor 1 is unchanged. If a Section's pattern has neither slot, its stairs climb floor by floor as before. No key was added. A new run also drops the previous run's stairs home from generated floors, so an old tile cannot be a hidden stair to town. Guide: `docs/guides/rulesets.md` (Landings). Tests: `tests/test_descent_landings.py`, `tests/browser/test_landing_home.py`.
- [x] **The touch controls are built for real: a floating joystick, one contextual action button, a Bag button, quickslots, and Settings** (2026-10-12, P3TOUCH): on a touch screen the player drags a floating joystick anywhere on the left of the map to walk, with the same step rhythm the prototype was accepted with, and the lower-right cluster holds the smart button (it says what it will do: Read, Talk, Open, Fight, Go down) with the Bag button above it. Health sits top left with two quickslots for usable bag items; the Menu button sits top right. The old D-pad and action row stay hidden on touch unless Display chooses the D-pad. Display gains the move-style choice (joystick or D-pad), Control size from 75% to 150%, and Left-handed, all kept across reloads. Keyboard and gamepad are unchanged. The layer's logic is in `515-touch-controls.js`, its styles in the coarse-pointer block of the style sheet, and its checks in `tests/browser/test_touch_controls.py`.
- [x] **The hero dying and waking are events a rule can name** (2026-10-09, [#365](https://github.com/Rylee-Bee/vefr/issues/365)): `falls` and `wakes` join the eleven in `shapes.EVENTS`, so both validators and the woven player read them on the same pass as everything else - `falls` carries what killed the hero and the region it happened in, `wakes` the region they woke in. Raised where death already happens (`cozyDeath`), before and after the hero moves, so the two are facts rather than places a pack has to infer from where the hero is standing. Death was not faked before this: `enters` fires on every arrival, so the faked line said "you wake up again" to a player who had merely walked home. Guide: `docs/guides/rules.md` (the thirteen events). Tests: `tests/test_death_events.py`.
- [x] **A drop that hands the player nothing is said out loud** (2026-10-09, D114): a chest book (`chest: yes`) whose `drops` no declared item answers for, and whose `drops` line names no id at all, opens on nothing and is refused by name - the bag takes an id only when the baked catalog holds it, so four keys that reached a 2026-10-08 game as empty chests validated green and made the floor unwinnable. ADR 0015's warden check gets the same rule for its `carries` key (an item declared with no `name` is not an item the bag can hold). A chest with no `drops` line holds its note and nothing else and is left alone. Guide: [`docs/guides/rulesets.md`](docs/guides/rulesets.md) (Items and loot); tests: `tests/test_empty_drops.py`.
- [x] **A Section's `tiles` reaches play, and the Section contract says which of its 18 keys are read** (2026-10-09, [#349](https://github.com/Rylee-Bee/vefr/issues/349), [#351](https://github.com/Rylee-Bee/vefr/issues/351)): the shape typed `tiles` and `vefr check` validated it, and the play-time descent never read it, so every Section in a descent drew the same ground - every floor's legend came from one table baked beside the Sections, and every floor's pictures from the pack's global `window.VEFR_TILES`, which is the town's grass. A floor's plan now carries its own Section's legend (`delve.section_legend`, twin `sectionLegend`), and the weave resolves each Section's `tiles` into real pictures keyed by Section id (`section_tiles`), so two Sections of one descent draw different ground. Only a glyph the generator already draws is overridden, and only its `tile`: the base colours and the solid flag stay the engine's, because a floor that walked through its own wall would be a different generator. A Section naming no `tiles` is left out entirely, so a pack with no `tiles` anywhere weaves byte-identically. `vefr check` now says a Section that names a tileset no picture exists for, by name - a floor that quietly falls back to a flat colour is the failure this slice exists to close. Alongside it, a family's `depth` range is read (#351): `[7, 9]` is three floors of that Section, not nine, counted from the Section's own first floor. And the shape's Section table now carries each key's own line of the contract (`doc`) plus `wired` and `wires`, so of the 18 keys `shapes.SECTION` validates, the 6 that the play-time descent does not read - `section`, `elites`, `groups`, `curve`, `loot`, `pois` - say plainly what would read them and which slice that is, rather than looking equally live. Tests: `tests/test_section_tiles.py`, `tests/test_section_family_depth.py`, `tests/test_descent_parity.py`. Docs: `docs/guides/rulesets.md` (Sections).

- [x] **A drop that hands the player nothing is refused - and there is one rule for it** (2026-10-10, D114 continued, cottage#114/#119/#120): D114 closed this on the chest book. The same shape then turned up on three more surfaces, and each fix arrived carrying its own idea of what a real item is, so all three are read by the one rule now - `library._drop_payout_errors`, over `library._declared_items` (the catalog the weave really bakes, so an `items` entry with no `name` is no item and a pack with no `items` declares none) and `cli._drop_ids`'s ids (what the bake really keeps). The four doors: `library._chest_drop_errors` (D114), `maplab._enemy_drop_errors` (a region enemy's `drops`, same class one layer out), `blueprint._declared_items` (a Blueprint family - it read the raw `items` keys, so a nameless entry passed Blueprint's own gate and the weave filtered the drop afterwards) and a Section family's `drops`, which `shapes.check_section` takes as a `drops` callable because that module may not import `vefr`. What is refused: a `drops` line that names no id, and any id no declared item answers for (named one by one; every id dead is the "holds nothing" sentence). What is NOT: a key that is not written at all - a chest holds its note and nothing else, a monster carrying nothing is legitimate, and most Section families name no drops. No catalog to read against is a skipped check, not a wrong one. This narrows one thing the enemy fix had allowed: a list where one id answers and one does not is now refused, which is what the chest check has always done and what the kill earns either way. `/warden/family` (`delve.mobs_at`) is named here and deliberately left alone - a fifth surface with its own question. Guides: [`docs/guides/rulesets.md`](docs/guides/rulesets.md) (Items and loot; Sections), [`docs/guides/blueprint.md`](docs/guides/blueprint.md); tests: `tests/test_empty_drops.py`, `tests/test_empty_enemy_drops.py`, `tests/test_blueprint_declared_items.py`, `tests/test_mob_drops.py`.

- [x] **The stamp sweep inside `vefr check` draws the gate's 200 seeds, so a room that places on 99 floors in 100 cannot be green** (2026-10-09, [#346](https://github.com/Rylee-Bee/vefr/issues/346) follow-up): the sweep #346 added to `vefr check` shipped at `cli.CHECK_STAMP_SEEDS = 8`, chosen to keep the fast half fast, and the gap that choice left was named rather than hidden - a required room placing on 99% of floors passes 8 seeds `0.99**8 = 92.3%` of the time and fails the 200-seed `vefr stamp check`. That is not a narrow gap, it is the common case, and the bar exists to be exact: 100% means every floor, because one floor in a hundred that loses its warden hall is a floor the hero walks into an empty hall. The constant is now **200**, the standalone gate's own default, so the two doors sweep at one confidence instead of one of them being the weak one - and `vefr check` was already paying for a 200-seed Section sweep (`locks.SECTION_SEEDS`) over the same `check-<n>` names, so this adds no new class of work. Catching a 99% room 99% of the time needs `ceil(log(0.01)/log(0.99)) = 459` seeds, which is what 200 is the same order as rather than a claim to be. Measured, not asserted (median of five runs each, same machine, same pack, source edited between the halves): a pack that ships stamped rooms goes **0.992s at 8 seeds to 3.906s at 200, a delta of 2.91s** (the sweep alone 0.12s to 3.03s), and `worlds/sample-world`, which ships no `stamps/` at all, is **0.065s to 0.061s** - unchanged, because the sweep is skipped before it costs anything. Every pack in the tree today is that second case. The coverage is demonstrated rather than argued on a fixture: a required landmark weighed 99 against one rival weighed 1 lands on 99 of 100 floors and misses first at `check-58`, so an 8-seed sweep says nothing at all and the 200-seed sweep refuses it (`placed on 1588 of 1600 cellar floors (99%); it needs 100%`). The seeds are still named, still `check-<n>`, still behind no flag - a pack must never be able to be green for free while carrying a room that never places, and a flag is exactly a way to be green for free. No change to `stamp_check` itself, to `locks.section_findings`'s sweep, or to any pack key. Guide: [`docs/guides/vefr-command.md`](docs/guides/vefr-command.md); tests: `tests/test_stamp_check_runs.py`.

- [x] **`vefr check` runs the stamp check, so a required room that never places cannot be green** (2026-10-09, [#346](https://github.com/Rylee-Bee/vefr/issues/346)): `vefr check` ran the shape checks and stopped, while the gate that catches a room which never places - `vefr stamp check` - was a separate command nobody had to run, so a pack printed `ok:` while carrying a required stamp that placed on almost no floor. The check now calls the same `stamp_check.report` that command calls (`cli._stamp_findings`), over the same `check-<n>` seeds, so there is one copy of the rule rather than two and the two doors cannot drift. **The seam was a smaller sweep, and the shape of it was chosen deliberately: no flag, no opt-in, a fixed small seed count (`cli.CHECK_STAMP_SEEDS = 8`) rather than the standalone gate's 200 - since raised to 200 by the entry above, which is where that reasoning is answered.** It is not behind a flag because a pack must never be able to be green for free while carrying a room that never places, and a flag is exactly a way to be green for free; it was small rather than 200 because the sweep is the slow half and `vefr check` runs on every pack write. Measured, not asserted: a pack with no `stamps/` is **0.007s before and 0.008s after** (the sweep is skipped before it costs anything, and it prints nothing), and a pack that does ship stamps goes **0.82s to 0.92s**. The trade was stated rather than hidden: a room crowded off its slot places on almost none of eight floors exactly as it does on none of sixteen hundred, so the reported bug is caught at any seed count - but a room that places on 99% of floors can pass the 8-seed sweep and still fail the 200-seed `vefr stamp check`, and that gap is what the entry above closed. The refusal is `stamp_check`'s own plain sentence (`stamp <id>: <what is wrong> <json pointer>`), named exactly as the other rules in this path already speak. No new pack key; no change to `stamp_check` itself. Guide: [`docs/guides/vefr-command.md`](docs/guides/vefr-command.md); tests: `tests/test_stamp_check_runs.py`.

- [x] **One tile, one way out: the descent's entry cannot stand on an authored door** (2026-10-09, [#352](https://github.com/Rylee-Bee/vefr/issues/352)): a pack whose `descent.entry.at` sat on a tile an act transition already used printed `ok:` and then, in play, went somewhere else - the woven list holds the pack's doors first and a door is found by its region and tile, so the authored one answered Interact and the generated floors were unreachable by walking. `vefr check` now refuses the pack in one sentence naming the tile and both regions (`maplab._entry_collision_sentences`, reading every act's doors, not only the first act's), and the descent entry takes its tile at play (`claimTile` in the descent part), so a pack woven anyway leads down rather than past. No new pack key; a pack with no collision validates and plays exactly as before. Guide: [`docs/guides/rulesets.md`](docs/guides/rulesets.md) (regions + transitions); tests: `tests/test_descent_entry_collision.py`.

- [x] **A skinned panel shows the skin's own face, not a sheet of the pack's accent** (2026-10-05, [#306](https://github.com/Rylee-Bee/vefr/issues/306), merged as `badc457`): the `corner` part's four studs rewrite `.carved::before` / `#config::before` into four corner pictures spread over the whole panel, and they set the picture longhands only. The player's own rule for those pseudo-elements paints them with the `background` SHORTHAND, so the accent stayed sitting in the background-COLOUR underneath - and a panel-sized pseudo-element with an accent background paints a full sheet of accent over the panel. Measured at the centre pixel of the open menu: parchment 230,199,146 before, teal 63,126,132 after. The studs now clear the background-COLOUR with the longhand (the shorthand would take the picture with it), so the four corner pictures stay and the panel's middle is the panel's own face again. Tests: `tests/browser/test_skin_panel_background.py`. Recorded here now; it merged without an entry.

- [x] **A skinned menu shows its words: a panel picture that cannot carry the skin's ink no longer takes its place** (2026-10-05): the player samples a panel picture's own middle into `--vefr-skin-ground` and lays every skinned surface on it - the panels, the menu tabs, the HUD value boxes - while the words on all three are the skin's `ink.on_panel`. Nothing checked that the two can be read together, so the sampled face quietly replaced the contrast-aware fallback the loader already had. Measured on a soft-wood skin wearing dark ink: `rgb(43, 33, 24)` on `rgb(58, 42, 24)` is **1.14:1**, and every tab label, the whole right-hand content panel and every HUD value box went blank while the text stayed in the DOM, `visible`, `opacity: 1` and 15.2px - which is why the eight existing Cottage browser checks and axe-core all passed: they ask whether the words exist, not whether anyone can see them. The sample is now only taken when it carries the declared ink at the 4.5:1 body-text floor `tests/test_teal_contrast.py` already holds this project to; a picture that does not leaves the fallback standing, which does. Nothing about a skin's own picture, ink or type changes, and no skin carries a colour for this bug. Tests: `tests/browser/test_menu_labels.py` (both the phone and the desktop width); the no-skin weave digest in `tests/test_skin_validator.py` moved with the player code, by the documented command.

- [x] **The in-world interface, slices 2 and 3: a themed backdrop and a themed type** (2026-10-04): `skin.json` may name an optional `backdrop` (one seamless picture, checked like any other), which the player tiles on the map canvas over the ground the drawn map does not cover, and an optional `fonts: {display, body}` naming one of the three families the engine bundles and ships (Cinzel, Atkinson Hyperlegible Next, and Crimson Pro, SIL OFL, added 2026-10-04). No skin, or a skin with neither, plays exactly as before: today's flat dark ground, today's type, and `window.VEFR_SKIN = null`. `prefers-contrast: more` and forced colours return the plain flat style, backdrop included. Plan: [`docs/plans/interface/PLAN.md`](docs/plans/interface/PLAN.md); guide: [`docs/guides/rulesets.md`](docs/guides/rulesets.md) (Skins); tests: `tests/test_skin_validator.py`, `tests/test_skin_apply.py`.

- [x] **The player is built from parts** (2026-10-04): `web/packaged.html` is generated from 56 parts in `web/player/parts/` by `scripts/build_player.py`; byte-identical weaves proven by `scripts/weave_digest.py`; `tests/test_player_build.py` guards it. Plan and rule: `docs/plans/player-split/PLAN.md`, `.project/DECISIONS.md`.

- [x] **Cottage Release 1 and the VEFR it taught** (2026-10-04, PRs #252 to #258, #261): `complete-act` (the end card), lock reachability in `vefr check`, the sticker album (slice 1), the up-stairs label fix, sound (nine synthesized cues, one switch, opt-in per pack), walk sheets (phase B of the pack art proposal), and the plan to split the player file. Guides: `docs/guides/rules.md`, `docs/guides/rulesets.md` (Album, Sound, Walk sheets). Library: chapters 30 and 31. The discovery record: [`docs/research/cottage-release-1-learnings.md`](docs/research/cottage-release-1-learnings.md).

- [x] **Blueprint, the optional family source for packs** (2026-10-02, PRs #219 to #227):
      a pack may carry `blueprint.json`, which `vefr normalize` expands into the
      region `enemies` lists (generated, committed, read-only), with a lock
      (`blueprint.lock.json`) and stale-output rejection in `check` and the weave
      ([ADR 0008](docs/adr/0008-blueprint-format.md),
      [guide](docs/guides/blueprint.md)). A pack without one is unchanged. The
      Cottage trial passed the exit threshold: 508 authored creature values became
      277 (45.5% fewer), all 69 records equal to the hand-written ones, and the
      woven player is identical. Plan:
      [`blueprint-family-normalization-plan.md`](docs/plans/blueprint-family-normalization-plan.md).
- [x] **Blueprint, one family resolution** (2026-10-02, PRs #232 and #233): `_resolve_family` replaces two
      traversals; a bad `drops` list points at the declaration that supplied it; broken unused families are
      rejected. Format 1 and output unchanged. Refined plan: PR #231.
- [x] **Equipment, the pack fields** (2026-10-03, #217 track A slice A1): an
      item may carry `slot` (`hand`, `body`, `head`, `feet`, `charm`) and,
      only beside it, `mods` (`atk` and `hp`, whole numbers 0 to 9, bools
      refused). A slotted item may still carry `value` and `keep` but not
      `heal`, `light` or `use`; an item a locked door names as its key may
      not be worn. The validator names each problem in one plain sentence,
      and the bake carries `slot`/`mods` only when valid, so a broken shape
      is a no-op rather than something unwearable. An item with no `slot`
      is unchanged, so every existing pack still loads
      ([design](design/equipment.md), [guide](docs/guides/rulesets.md)).
- [x] **Equipment, the pure engine** (2026-10-03, #217 track A slice A2):
      `window.VEFR_EQUIP_ENGINE` in the woven player - pure, no DOM, no
      clock, no randomness, no storage - answering `statsFor`, `equip`,
      `unequip`, `clean` and `clampHealth`. Attack is base plus worn
      `mods.atk`, max health base plus worn `mods.hp`, taking off clamps
      health down to the new max but never below 1, and equipping into a
      full slot hands the old wearer back for the bag. Four named
      refusals (no-slot, wrong-slot, not-an-item, bad-slot) make a
      duplicate impossible. Nothing is written into the caller's state,
      because that object is what gets saved. Pinned by a jsdom harness
      against the real woven file (`tests/test_equipment_engine.py`).
      Nothing wears anything yet: the Bag panel is the next slice.
- [x] **Equipment, the Bag panel** (2026-10-03, #217 track A slice A3): the "You"
      section above the bag - five slots in order, each row named by one sentence the eye and a
      screen reader share, empty slots drawn as inline-SVG outlines so no new art. **Equip** on a
      bag row, **Take off** on a worn slot, a swap puts the outgoing thing back in the bag, and
      one plain sentence names the change (and what came off). State at
      `localStorage['vefr-equipped-<world>']`, every access in `try {} catch {}`; a saved id the
      catalog no longer has is dropped on load; a worn thing is never in the bag list, so it
      cannot be traded or drunk. `heroMax()`/`heroAtk()` add the worn mods beside growth's, and
      taking off clamps health to the new max. `tests/test_equipment_ui.py` (14 pins, driven
      through the DOM and real `heroAtk()` numbers) plus
      `tests/fixtures/equip_ui_harness.mjs`. Review found and fixed a real defect: an occupied
      slot with no resolvable sprite drew the *empty* outline, so a worn thing could look like an
      empty one - the one signal that outline means. Equipment is playable end to end.
- [x] **Teal text has a contrast floor** (2026-10-03, #218): `--teal` is the
      brand/AI-presence colour, tuned for dots, borders and fills where WCAG
      asks nothing, and four small labels took their *text* colour from it. The
      12px menu heading sat at 4.36:1 on a card where body text needs 4.5, and
      the 10px world-card badge was worse on a translucent teal wash. The two
      jobs now have two names, `--teal-text` and `--teal-text-hi`, declared per
      theme and one step up the same ramp: 6.25 on a card, 5.19 on the badge
      wash, 8.68 on hover. Every dot, border and fill is untouched. Also fixed
      a second bug in the same block: `--teal-light` was used once on
      `.context__evidence-link:hover` and defined nowhere, so that hover
      silently fell back to the inherited colour.
      `tests/test_teal_contrast.py` is the guard - it computes the ratio for all
      three themes, fails if any stylesheet takes a text colour from a fill
      token, and fails if `--teal-light` reappears. Rule 2 of
      [`accessibility-contract.md`](docs/guides/accessibility-contract.md) now
      carries the general lesson.
- [x] **Durable rule saves** (2026-10-02, PRs #222 and #225): an optional `saves` block
      (`"rules": "persist" | "reset"`, `"legacy": "fresh" | "from-log"`); persist keeps a
      reload from forgetting fired rules, flags, beliefs and items, and fires `starts`
      once per save ([ADR 0009](docs/adr/0009-rule-saves.md),
      [plan](docs/plans/durable-rule-saves-plan.md)). Default is reset, today's behavior.
      Cottage opts in. The player also survives a `localStorage` that throws (a sandboxed
      iframe): [#224](https://github.com/Rylee-Bee/vefr/issues/224), fixed.
- [x] **Locked doors and stairs** (2026-10-02): a transition may carry
      `requires` (`{"item": ...}` or `{"flag": ...}`, exactly one) and a
      one-sentence `locked_text` (`design/gates-and-guardians.md`, build
      step 1). Interact on a locked door without the key says the line and
      the hero stays put; with the item in the bag or the flag set it opens
      as before, and the key is never consumed. The validator names a bad
      shape, an unknown key, an unknown item or flag, or a bad line.
      `tests/test_locked_stairs.py`.
- [x] **The declutter** (2026-10-02): Interact is the one big button, with Talk, Whisper,
      Bag and Explore as small icon buttons (inline SVG, words kept for screen readers);
      the Dusk/Dawn rail moved into Menu > Display; the top bar is just Menu. Fixes the
      phone HUD overlap the skin check found (the rail covered the level text), wraps the
      health/level/gold row before the Menu button, and starts the phone Messages panel
      below it. `tests/test_declutter.py`; no overlaps at 390/360/320 px and 1280/900;
      axe clean on the plain sample and the skinned Cottage.

- [x] **The quiet screen, WASD, Trade on E/F and a calmer step** (2026-10-02): the
      how-to-move line goes after the first step, the place name fades (its text stays for
      rules), fight buttons show only near a monster, messages sit in a collapsible corner
      panel, W/A/S/D walk (A/D turn note pages), E or F close Trade, and the hop is a third
      of what it was. `tests/test_quiet_ui.py`; the Messages toggle meets the 44 px floor.
- [x] **Three Library chapters** (2026-10-02): rules, getting stronger, one button and a
      quiet screen (`web/library/27-29`); the Whole Shelf sticker now wants all 20 books.
- [x] **Art in the repo, credited** (2026-10-02): `tools/art/import_art.py` and
      `web/art/MANIFEST.json`: 18 stickers, the delve set (gear, spell schools, shop signs,
      item badges, dungeon tiles), surface tiles and 13 theme kits at game size; every file
      has a credit and `tests/test_art_manifest.py` fails without one. Kenney sheets removed.
- [x] **The features catalog** (2026-10-02): `docs/features.json` (one source of truth for
      what VEFR can do) with a drift check in the test suite, `vefr features [--pack] [--json]
      [--check]`, one read-only `GET /api/features`, and two studio shelves ("What this game
      uses", "What VEFR can do"). The Containerfile ships the catalog (UNVERIFIED: no image
      built).
- [x] **Random floors, phase 1** (2026-10-02): `delve.prng` (xmur3 + mulberry32) and
      `generate_floor_v2` in Python, and the exact JavaScript twin `window.VEFR_DELVE`;
      `tests/test_floor_v2_parity.py` replays 10 streams and 50 floors through the real
      player and demands identical rows. `generate_floor` is untouched (pinned by hash).
- [x] **The skin loader** (2026-10-02): a pack's `skin` folder is validated, baked as data
      URIs and painted by the player (`design/ui-skin.md` steps 4-5). Measured on Cottage's
      real skin, which found and fixed four defects (#211): the ink never reached text inside
      panels, a tiled 32 px patch showed as stripes, the menu's left column was missed, and
      a gold button background sat under the wood. 0 text elements under 4.5:1, axe clean.
- [x] **Growth, dev verbs and the Interact fix** (2026-10-02): `design/growth.md`
      built (levels or practice, enemy `xp`, `VEFR_GROWTH_ENGINE`); Interact keys
      continue notes and speech boxes; `vefr publish|look|probe` and doctor tooling
      rows; `tests/run.sh` for throwaway clones; Kenney sheets removed from
      `worlds/sample-world`. Designs proposed: gates and guardians, the album.
      Built by two offload foremen to acceptance tests written first, reviewed by
      hand. 1272 passed, 3 skipped.

- [x] **The first independent pack's contract repairs** (2026-10-02):
      a substantial outside pack was built without engine changes and
      its recordings were verified against main (`docs/research/
      2026-10-02-first-independent-pack.md` holds the matrix). Fixed:
      **`opens` now fires** through the one Interact path (its only
      call site lived in the orphaned `useHere`, deleted with it -
      chests and doors emit `opens`, chests then emit `picks-up` per
      item); **`picks-up` on every player acquisition** (floor,
      chest, trade - a rule's `give` stays silent, the no-chains law);
      **one identity model** - POI labels, library book ids and enemy
      ids are declared things a rule may name, `comes-near` distance
      is 0..9 (0 = standing on it), so packs stop inventing fake items
      for landmarks; **five new events** - `defeats`, `buys`, `sells`,
      `reads`, `phase-changes` - all facts the player already performs;
      **`takes`** (the `give` pair) and item `keep: true` plus a bare
      `use`, so usable and consumable stop meaning the same thing;
      **two evidence panels** in the player's menu - *Why did that
      happen?* (the real `VEFR_WHY` records) and *Where next?*
      (`point-to` hints kept as intentions); **`handbok --pack` is
      pack-scoped** and fails closed on no history (it used to print
      another world's title and numbers), trace events now name their
      world; `refresh_living_tree` honors its own never-break contract
      (it let a PackError escape); and the door contract in the docs
      now matches the player (Interact, not stepping). The bake's
      `_rule_bakes`/`validAction` mirrors were pinned in lockstep with
      the validator - the drift they had is exactly the class of bug
      this pass exists to kill. Tests: `tests/test_rules_validator.py`
      (+6), `tests/test_events_play.py` + `tests/fixtures/
      events_play_harness.mjs` (the real woven file, every event
      through the player's own paths), `tests/test_handbok.py`
      (cross-pack isolation regression). 1180 passed, 1 skipped.

- [x] **The rules engine wired into the woven player** (2026-10-01): the
      pure engine block now RUNS. `cli.weave_html` bakes the pack's four
      catalogs through four new placeholders (`_player_rules`: `{}` and
      four literal `null`s when the pack declares none of flags/claims/
      people/rules - byte for byte the file it wove before; entries that
      cannot run are DROPPED, never half-baked). The player reads them as
      `window.VEFR_RULES/FLAGS/CLAIMS/PEOPLE` beside the engine, and one
      top-level `fireRule(eventName, data)` seam performs the returned
      actions on surfaces that already exist - `say` -> `showSpeech`
      (speaker key resolved to the pack's own name; unknown speaker
      skipped silently) or `combatSay` for the narrator, `give` ->
      `bagAdd`, `weather` -> the player's own darkness preference (the
      Display switch's path; label + aria-pressed stay honest, a pack's
      fog declaration never deleted), `point-to` -> one plain `combatSay`
      hint with the direction the transitions declare, `show/hide/reveal`
      -> the floor for item ids; `set/unset/believes/stops-believing/
      tells` stay engine-state only. Six one-line call sites: Begin
      (`starts`), `enterRegion` (`enters`), `tryNPC` + the POI the hero
      walks up to (`comes-near`, real Manhattan distances), the chest
      (`opens`), `takeHere` (`picks-up`, per item bagged), the use verb
      (`uses-with`). The player's rule log is `window.VEFR_WHY` (last 20
      `{id, why}`, persisted as `vefr-rules-<world>`, every access
      wrapped so a sandboxed iframe's throwing localStorage never takes
      the game down). `journal.KINDS` gains `rule_fired` with NO server
      call site yet (the woven player is static - gap on the commit).
      Pinned by `tests/test_rules_bake.py` (the null bake, the exact
      byte difference of the rules pieces, green validation, dropped
      entries) and `tests/test_rules_play.py` (the real woven file
      played in jsdom: Begin fires, one step fires, one plain sentence
      per rule naming its id).

- [x] **The rules catalog validator** (2026-10-01): world packs may now
      carry four OPTIONAL top-level keys - `flags`, `claims`, `people`
      and `rules` - and `maplab` checks them at authoring time, purely
      additive: a pack that declares none validates byte-for-byte as
      before (`load_pack` passes the four through only when declared;
      a test asserts they stay ABSENT for `worlds/sample-world`, which
      still validates green). New `maplab.rules_errors`, wired into
      `validate()` beside `grammar_errors`/`item_light_errors`, checks
      block shape, unique non-empty rule ids, the six events (`starts`,
      `enters`, `comes-near`, `opens`, `picks-up`, `uses-with`; `says`
      stays out - the woven player has nowhere to type words),
      conditions, actions, declared-flag reads/writes, unknown ids
      (flags/claims/people/items/places), the 40-rule limit, same-event
      conflicting actions (naming BOTH rule ids), and the 280-char say
      line (`RULE_SAY_LIMIT`) - plain sentences, each naming the rule
      id. New `maplab.rules_notes` is the two design warnings (a
      believed claim no rule can ever change; a belief nothing reads)
      and is deliberately NOT wired into `cmd_validate`. Path safety:
      rule/flag/person/claim ids never become filesystem paths - the
      only pack file read is `<pack_dir>/world.json`, guarded by a
      hostile-ids test. Pinned by `tests/test_rules_validator.py`
      (a good pack across all six events, fifteen bad packs, the
      compatibility checks, both notes, and the hostile pack).

- [x] **An Undo button on the Desk** (2026-10-01): the edit loop's way
      back now has a client. The existing `POST /api/builder/edits/undo`
      route (unchanged, plain sentences) is reachable from a real
      **Undo last edit** `<button type="button">` in the Desk's weave
      row beside **Play it here** (`web/js/rooms/workshop.js`, plus
      `API.editsUndo` in `web/js/api.js`). It posts `{"name": null}` so
      the route falls back to the active world - what the Folks room
      already sends - and writes the answer into its own polite live
      region (`#ws-undo-status`, `role="status"`, `aria-live="polite"`,
      the weave status pattern and CSS class). Success shows the
      route's sentence verbatim and reloads the Desk; a 404 says the
      route's own "nothing to undo" words kindly, not as an error, and
      changes nothing else; any other failure is one plain friendly
      sentence - never a raw status. Disabled while in flight,
      re-enabled after every answer, ≥44px via the cta classes.
      Pinned by a node-vm harness on the REAL workshop.js
      (`tests/fixtures/undo_harness.mjs` + `tests/test_web_undo_button.py`)
      and a browser test (`tests/browser/test_undo_button.py`);
      `docs/guides/studio-edits.md` and the glossary now say the button
      exists.

- [x] **One-button Interact, first slice** (2026-10-01): the woven player has one verb on `E`, `Space`, `Enter` and
      `F` plus the always-on Interact button: `interactTargets`, `pickTarget` and `labelFor` as a pure
      `-- interact start/end --` block with a node harness (facing tile, then the hero's own tile, then the
      nearest in reach; ties by kind: door or stairs, chest, trader, resident, place, enemy). The button and
      `#use-hint` say what the press will do ("Open the chest", "Talk to <name>", "Fight <name>"), a thin ring
      marks the target tile, and nothing in reach gets the gentle nudge with no turn spent. Interact on a
      monster opens its actions (`Strike`, `Console`, ...) in the shared verb row; bump-to-attack is unchanged.
      **Start over** in the pause menu asks once, clears every `vefr-` save on the site and returns to the
      title screen. Guides: `docs/guides/glossary.md` (verbs **interact**, **start over**) and the new
      `docs/guides/playing.md`.
- [x] **Close the loop, first slice** (2026-10-01): `POST /api/builder/character/place` (preview, force, plain 422s, backup, shared writer) and the Folks room's
      **Put in the game**; `GET /api/builder/weave/play/{name}` and the Desk's **Play it here** pane (strict sandbox, measured 0.115 s click to playing);
      the edit log (`data/edits.jsonl`) with `EDITS.md` in the game folder and one-level undo (`POST /api/builder/edits/undo`, route only); the events `play_here`
      and `character_placed` with the first-playable walk (its sticker is parked until Rylee picks a picture). Guide: `docs/guides/studio-edits.md`.
      Design: `design/close-the-loop.md`. Reviewed and gated by the orchestrator; CodeQL clean after containing the staged voice path.
- [x] **Grid tiles** (2026-10-01): `tiles/<name>.grid3x3.webp` is one picture drawn as cells, chosen by position; 2 to 8 a side; validator names bad grid names.
- [x] **The `vefr` front door** (2026-10-01): one command for find, doctor, check, chat, map, delve, weave, spark, test, ferry, handbok, with `vefr norns` and
      `vefr ratatoskr` as verbatim escape hatches; `vefr find` is a read-only local search that refuses files whose real path leaves the pack.

- [x] **A README that reaches a walking town** (2026-10-01): `README.md`'s
      "Open and play" now leads with the published image's one command
      (unchanged `podman run`, unchanged `ghcr.io/rylee-bee/vefr:latest` and
      env vars) and the sentence that there is no account, no key and no
      model to install - the image carries the small model fleet, so
      whispers and NPC lines work out of the box. Health, the town's URL and
      the existing walk paragraph follow; then one short step for fresh
      lines: `ratatoskr spark install` (pinned model, verified by size and
      sha256, `docs/guides/spark.md`) or your own OpenAI-compatible server
      via `VEFR_LLAMACPP_URL`, with `GETTING_STARTED.md` linked for the
      variable table instead of a pasted server command. The
      clone-and-build quickstart moved under "For developers" at the end of
      the section, keeping `uv sync --group test` and describing
      `VEFR_MODEL` as the studio/craft model rather than the storyteller
      (the default stays stated only in `GETTING_STARTED.md`). "Run the
      engine" keeps its local-build block and now points at "Open and play"
      for the published-image command, so the page carries one copy of it;
      its stale "an image with model weights" line now says the image ships
      the fleet, matching `Containerfile` and `publish-image.yml`. No link
      removed, no command changed.

- [x] **A friendly "no model answered" message** (2026-10-01): when no model
      answers, the person at the keyboard now reads one plain sentence
      instead of a raw endpoint URL and an httpx traceback string.
      `GeneratorUnavailable` and `GeneratorFailed` in `src/vefr/generator.py`
      build their message from `_no_model_message()` / `_unreadable_message()`:
      what was tried in words (the active storyteller pack and the model it
      asked for, from `resolve_active()`), that the game still plays without a
      model, and the next step (`ratatoskr spark install`, or start your own
      OpenAI-compatible server and set `VEFR_LLAMACPP_URL`). The two causes
      keep distinct sentences - an endpoint that never answered versus a model
      that answered unreadably (endpoint fine; try again or check the model) -
      and building the text can never raise: a BYOM pin falls back to the
      model name alone. The raw detail (endpoint URL, exception class and
      text) moves to a `detail` attribute and an ERROR log record via stdlib
      `logging`, so `storyteller_test._looks_like_missing_model` now reads the
      preserved detail and a 404 still classifies as SKIPPED while a refused
      connection stays an ERROR. `npc.py` / `chat.py` seed-line fallbacks and
      the provider/retry/chaining flow are untouched. New
      `tests/test_no_model_message.py` proves the sentence names the pack and
      model, leaks no URL or status code, keeps the skip heuristic honest, and
      still builds under a BYOM pin; the three provider tests now assert the
      new contract on message, `detail`, and the log record.

- [x] **A laptop-safe context default, told honestly** (2026-10-01): a pack's
      `context_window` is capability metadata and nothing else. It is read
      into `Storyteller.context_window` and stops there: no code path sizes
      memory, a KV cache, or a server from it, and `gemma4-e2b`'s 131072 on a
      ~2B model was a documentation hazard, not a live one. Rather than
      change what a pack declares or wire the number into a server command,
      the truth is now stated where people read it: a paragraph in
      `docs/guides/storyteller-packs.md` next to the manifest reference says
      the bundled brain's servers use fixed laptop-sized contexts (2048/4096/
      512 in `deploy/start-bundled.sh`, 8192 in the Spark quadlet), that a
      big number is a claim about the model rather than a memory bill, and
      that a player's own server picks the size their RAM can hold. `# NOTE:`
      lines at the field and the loader read in `src/vefr/storyteller.py` say
      the same in code. New contract test
      `tests/test_context_window_contract.py` fails if any engine code starts
      reading `context_window` off an object (the `min(recommended_ctx,
      context_window)` or `st.context_window` regression), checks every
      bundled pack still declares an int `context_window` that round-trips
      through the loader, and puts the doc's quoted server sizes under test.

- [x] **One documented truth for the default model** (2026-10-01): every
      doc and env file now says one true thing about how the engine picks
      the storyteller, and a test proves it. `GETTING_STARTED.md` states
      it once, in one anchor line: the storyteller uses the active
      Storyteller Pack's model, and with none set that is the first
      installed pack, else the first bundled pack (`gemma4-e2b` /
      `gemma-4-E2B-it`). The env table separates the roles that used to
      read as competing claims: `VEFR_STORYTELLER` picks the pack,
      `VEFR_MODEL` names the studio/craft model (and is the storyteller
      model only in an install with no packs, like the published image),
      while `VEFR_NARRATE_MODEL` and `VEFR_INTERFACE_MODEL` are separate
      fleet roles. `example.env`, the ADR (a dated 2026-10-01 amendment,
      not a rewrite), `README.md`, `docs/guides/install.md`,
      `docs/guides/bundled-brain.md`, and the image files (`compose.yml`,
      `Containerfile`, `deploy/vefr.container`, `src/vefr/volumes.py`)
      were corrected to match; the ADR's pack-id typo `ministral-3-3b` is
      fixed to `ministral3-3b`. No behaviour change: `resolve_active()`
      is untouched. New contract test `tests/test_default_model_contract.py`
      parses the anchor line and proves it against `resolve_active()`, and
      checks every documented `VEFR_STORYTELLER` value is a real pack id.

- [x] **Monsters that think with a map** (2026-09-30): a monster no longer
      walks in a straight line and stalls on a corner. Each turn the
      walkable tiles of the region are flooded once, breadth-first, from the
      hero, and every monster steps to the neighbour closest to that flood -
      so it walks round walls, corners and rooms instead of into them. A
      monster hurt to a third of the `hp` it walked into the region with
      (`hp0`, recorded in `loadEnemies`) steps the other way, to the
      furthest tile down the map, instead of closing; a monster that cannot
      see the hero drifts toward the nearest other living monster, by
      walking distance, so a pack stays a pack. Adjacent is still a hit,
      still for `atk`. The floods are built once per turn and shared,
      lazily, so a turn that never moves a monster never pays for one; a
      fixed neighbour order (up, down, left, right) breaks every tie, and
      there is no randomness or clock anywhere in the movement - the same
      floor always plays out the same way. Still no step onto a solid tile,
      another living monster, or the hero. The change is inside the
      movement functions only: combat, drops, the slain book, Cozy death,
      autoexplore, the fog toggle and the light item are untouched. Gap,
      on purpose: monsters still do not pick up loot. Guide:
      `docs/guides/rulesets.md` -> combat. Tests: a fixture floor with a
      wall in it, played in Chromium through the woven file
      (`tests/browser/test_monster_walking.py`, `tests/fixtures/make_wall_pack.py`).

- [x] **Pack grammars: the world's own words, expanded offline** (2026-09-30):
      an author can now ship a small grammar in `world.json` and a woven
      player keeps its voice with no model and no baked pool - the
      tracery-style deterministic text of enhancement wave 2 (#142), the
      first third of it. A grammar is `{rule: [strings]}` with an `origin`
      rule; `#rule#` inside a string draws one entry of that rule and every
      other character is kept. Three laws keep it safe: `origin` required,
      every reference resolves inside the same grammar, and one expansion
      draws at most 200 entries - a self-feeding grammar stops rather than
      loops. Two implementations of the same algorithm: `expand()` in the
      new `src/vefr/grammar.py` (standard library only, seeded through
      `random.Random`) and `grammarExpand()` in `web/packaged.html`, so the
      woven file needs no engine at all. The block is additive and every
      part optional: a pack with no `grammars` plays exactly as before.
      Wired: the `whisper` grammar speaks when a player has no endpoint,
      no pool and no fragment bank (speaker from `grammars.name`, else
      "someone"; truth from the seeded stream); the `weather` grammar says
      once in the status line on arriving in a region, journaled like any
      other arrival, never per step; the `name` grammar names a floor that
      `norns delve` generates, drawn from the delve seed and written into
      the region's `contract.json` (the `floor-N` directory name and every
      door are unchanged). `maplab.grammar_errors` checks the block with
      pack-level messages, so a typo is a line from `norns validate` rather
      than a silence at play time. Guide: `docs/guides/grammars.md`. Gate:
      843 passed, 4 skipped (`uv run --group test pytest -q`), 8 browser
      passed, ruff clean, `norns validate --pack worlds/sample-world` ok,
      public-surface guard clean. No model call anywhere in the path, and no
      new runtime dependency.

- [x] **Autoexplore for the woven player, and its UAT contract** (2026-09-30):
      a dark region can now be uncovered without tapping every step. The
      packaged player's action row gains an `Explore` control (`O`): it
      breadth-first searches the walkable tiles for the nearest unexplored
      ground and steps the hero there through `move()`, paced on a timer, so
      turns, monsters, fog and pickups stay honest. It stops the moment a
      living enemy is lit, the hero takes damage, no reachable dark tile
      remains, or a 400-step safety cap is hit; pressing `O` again, any other
      key, or a click elsewhere stops it. A `role="status"` line speaks only
      at start and stop. The sample world's town now declares
      `"fog": {"radius": 4}` so the demo lives in the dark, and the
      estate-format UAT contract lives at `docs/uat/autoexplore.md`. The dark
      is the player's to set: `V`, or the Display switch in the pause menu,
      turns it off for that world (remembered), which also seeds a future
      light mechanic (`fogRadius` is the lever).

- [x] **Renovate replaces Dependabot** (2026-09-30): `renovate.json` groups
      pip runtime, pip dev, npm and Actions updates, keeps a 7-day cooldown,
      and maintains Action digest pins; `lockFileMaintenance` keeps `uv.lock`
      fresh. The owner chose Renovate (the Mend app) after first choosing
      Dependabot; `dependabot.yml` is removed so the two do not open duplicate
      PRs. The app install is the one remaining step.

- [x] **Vale (prose) in CI, advisory** (2026-09-30): a `prose` job runs Vale
      3.23.0 over `docs/` and the Library with `fail_on_error: false`, using
      the built-in style (no network, no `vale sync`). It reports the house
      voice without blocking a PR; rules promote to errors once the existing
      docs pass.

- [x] **Static guards and link checks in CI** (2026-09-30): `dev-guards.yml`
      gains a `static` job (vulture dead code, deptry dependency hygiene, both
      configured in `pyproject.toml`) and a `links` job (lychee, offline, so no
      network flakiness). The 2026-09-30 audit found dangling files and stale
      references by hand; these make that class mechanical. Screen-reader
      automation (guidepup) is deferred - it needs a macOS/Windows runner
      (VoiceOver/NVDA only), which is an owner cost decision.

- [x] **The 2026-09-30 audit: runtime state untracked, and an enhancement
      packet** (2026-09-30): six runtime-state files that `.gitignore` (and
      the repo's own rule) already disowned were still tracked; they left
      the index (`#126`), and the last tracked mentions of the first game's
      name were swept. The open-source survey that will feed the next
      slices landed as `docs/research/2026-09-30-enhancement-packet.md`
      (`#127`), with its first wave filed as `#128`-`#133`.

- [x] **Reward, first slice — gold, a shop (sell + buy), and using a thing**
      (2026-09-30): loot left a thing carried but did nothing with it. Three
      optional, additive pack additions land the reward end. An item may now
      carry `value` (a positive int: what a shop pays and asks), `heal` (a
      positive int) and `use` (a verb such as `drink`); a speaker whose spec
      carries `"shop": "true"` (also `yes`/`1`) keeps its region's shop (at
      most one per region, the first named wins); and `world.player` may
      carry `gold` (a non-negative int; default 0), the starting purse. None
      are required, so an old pack bakes exactly the player it had before and
      its HUD does not move. The woven player bakes `VEFR_HERO.gold` and
      `VEFR_SHOPS` ({region: speaker key}) and the extra item fields. Gold is
      one number at `localStorage['vefr-gold-<world>']`, shown in the top-left
      HUD and as plain words in the Bag panel. Standing within one tile of
      the region's shopkeeper and using the world's interact verb opens a
      Trade dialog (44px targets, `aria-live` result, Escape/Close, focus
      returns): Sell lists carried things with a `value`, Buy lists every
      priced catalog thing, and an unaffordable Buy is disabled. A carried
      thing with a `heal` gets a Use button in the Bag panel: it raises health
      by `heal` (never above the max), spends one copy, and says so; at full
      health it says "You are already whole." and keeps the thing. Talking
      still gives the shopkeeper's own line; trading is a separate verb.
      Deterministic arithmetic on fixed pack numbers - no timers, no
      randomness, no model call, no new deps. Gaps: no haggling or variable
      prices, no stock beyond the catalog, no effects other than healing, no
      dropping or giving, and selling always pays exactly `value`. Guide:
      `docs/guides/rulesets.md` → reward. Tests:
      `tests/test_builder_weave.py`, `tests/test_combat_loop.py`.
- [x] **Loot, first slice — drops and a simple bag** (2026-09-30): killing
      something gave only survival. A world's `world.json` may now carry an
      optional `items` catalog (`{"<id>": {"name": "...", "sprite": "..."}}`;
      `sprite` names an entry in `player.sprites`, optional), a region's
      enemy may carry `drops` (a list of catalog ids), and a chest book
      (`chest: yes`) may carry `drops:` (a comma-separated id list in its
      front matter). The woven player bakes `VEFR_ITEMS` (an id with no name
      is dropped, and a drop naming a missing item is dropped too) and a
      `drops` list on each enemy and book. A killed enemy leaves its drops on
      the tile it died on as a small marker (sprite, else a dot); fog rules
      apply. Walking onto a drop takes it: it leaves the floor, one plain
      line says so, and a small sprite appears in the HUD. The floor persists
      per world (`vefr-floor-<world>`). The pause menu gains a Bag panel
      (next to Journal and Books) listing what is carried, one row per thing
      (`localStorage['vefr-bag-<world>']`, a list, so a duplicate id is a
      second copy); opening a chest still gives its note and also its items.
      Zero deps, deterministic, no model call. Gap: no weight, no using, no
      dropping, no selling, no identifying. Guide: `docs/guides/rulesets.md`
      → loot. Tests: `tests/test_builder_weave.py`,
      `tests/test_combat_loop.py`.
- [x] **Rolled loot, first slice — a rarity at once, traits hidden**
      (2026-10-10): a drop was a fixed id, so every cloudy potion in a run
      was the same cloudy potion. An `items` entry may now carry three
      optional keys - `rarity` (one plain word), `traits` (a list of plain
      words) and `roll` (`rarity`, a table of the pack's own names and
      whole weights; `traits`, the pool; `chance` 0..100; `max` 0..4) - and
      a monster's drop on a generated floor draws the rarity and the traits
      off a second named stream off the same floor key and monster
      (`v3|<key>|roll|<mob id>|<item id>`), so the same seed always drops
      the same potion at the same rarity, two monsters never share a roll,
      and the base id cannot move when a roll is added. The drawn instance
      (`{item, rarity, traits, identified: false}`) rides on the drop and
      then in the bag; the strip, the Bag panel and the pickup line name
      the thing and its rarity together from the moment of pickup, with no
      animation or delay anywhere in that path, and the traits are in no
      part of the page. Every key is optional and additive: `mob_drops`,
      `mobs_at`, `_with_warden` and `floor_plan` take the catalog as an
      optional argument, and a pack that names none of the three bakes the
      same `VEFR_ITEMS` and drops the same ids it did before (hashed both
      ways in `tests/test_rolled_loot.py`). `vefr check` refuses four
      things, one sentence each: a `rarity` outside the item's own table, a
      trait that is not one plain word, a `roll` with no rarity table, and
      a `roll` that asks for traits and names no pool. Gaps, deliberately:
      no identifying (nothing sets `identified` true), no reveal moment
      beyond the rarity being there, no answer yet to what a trait does,
      no bag size (since landed: see bag capacity below), and no rolled
      drops outside a generated floor's monsters. ADR: `docs/adr/0017-rolled-loot-with-rarity-and-hidden-traits.md`.
      Guide: `docs/guides/rulesets.md` → rolled loot. Tests:
      `tests/test_rolled_loot.py`, `tests/test_rolled_loot_play.py`,
      `tests/test_descent_parity.py`, `tests/fixtures/make_rolled_pack.py`.
- [x] **Identify, second slice — a town place that reads a thing**
      (2026-10-10): slice 1 hid the traits behind an `identified` flag
      nothing could turn. A speaker may now carry `"identify": "true"`
      (also `yes`/`1`/`true`) and is its region's reader, named exactly
      the way a pack already names a shopkeeper; standing beside that
      speaker and pressing Interact opens an Identify panel listing the
      carried things that have not been read, and reading one sets
      `identified: true` on THAT instance in the saved bag and nothing
      else. The rarity and the traits are the ones the drop drew - reading
      never re-rolls - and the flag survives a reload. Once read, the
      traits are named in the bag row and in the HUD strip's
      `aria-label`, in text, in the same call as the click, with no timer
      and no animation anywhere in the path: with motion off the words are
      on the first frame, which `tests/test_identify_play.py` reads out of
      the DOM in the same tick as the press and compares against the same
      run with motion on. Before a read the traits are still in no part of
      the page, so nothing is hidden from the eye that is not also hidden
      from a screen reader. No model call, no second draw, no clock. The
      flag rides the speaker the weave already inlines, so this slice adds
      no baked block: a pack that names no reader bakes every `VEFR_*`
      data line byte for byte (hashed both ways in
      `tests/test_identify.py`). `vefr check` refuses three, one sentence
      each: an `identify` naming some other service, an `identify` that is
      not the word true (an object could carry a chance, a roll or a
      model), and a speaker that offers identify in a region the pack does
      not have. Gaps, deliberately: no cost for a read (bag capacity has
      since landed, see below), and still no answer to what a trait *does*. ADR:
      `docs/adr/0017-rolled-loot-with-rarity-and-hidden-traits.md`. Tests:
      `tests/test_identify.py`, `tests/test_identify_play.py`,
      `tests/test_interact.py`, `tests/fixtures/make_identify_pack.py`,
      `tests/fixtures/identify_harness.mjs`.
- [x] **Bag capacity, third slice — a bag with a size, and carry**
      (2026-10-12): the bag was an unbounded list. A pack may now name
      `"bag": {"size": N}` in `world.json` (a whole number, 1 to 99); a pack
      that names no `bag` keeps the unbounded bag. An item may carry a
      `carry` (a whole number, 1 to 99), and each carried thing with one -
      in the bag or worn - raises the cap by that much. A full bag refuses a
      floor pickup in one plain line and leaves the thing on the floor. A
      warden's key, a `give`, a chest's contents, an equip swap and a
      take-off always fit, because refusing them would lose the thing. The
      bag panel reads "2 of 2 carried." when capped. `vefr check` refuses a
      `bag` block with no whole-number `size`, and a `carry` that is not a
      whole number from 1 to 99. Since then (#343 leftovers): a shop
      purchase into a full bag is refused in the Trade panel with "Your bag
      is full." and charges no gold, a thing a full bag left on the floor is
      picked up once there is room, and a satchel picked up in play keeps its
      places across a reload. Gaps, deliberately: a `carry` does nothing
      where the pack names no `bag.size`, and no weight. ADR:
      `docs/adr/0017-rolled-loot-with-rarity-and-hidden-traits.md`, amendment 1.
      Guide: `docs/guides/rulesets.md` → bag capacity. Tests:
      `tests/test_bag_capacity.py`, `tests/fixtures/bag_capacity_harness.mjs`.
- [x] **Spells, first slice — schools, levels, and the books found on the floor**
      (2026-10-10): the engine had levels and rolled loot and nothing to
      do with either. `world.json` may now carry an optional `spells` block
      (`schools`, a list of the pack's own plain words; `spells`, a list of
      `{id, name, school, level?, heal?}`), and an `items` entry one more
      optional key, `spell` - the id a book teaches when it is read. Learning
      by level is a **read of the level the `growth` block already derives**,
      not a second counter: no counter is added, and the level cap (the
      length of `levels.xp`) does not move, so a spell written above the
      table is never learned by level. A spellbook is an ordinary item, so a
      book found on a floor is a drop like every other drop and what it
      teaches follows from the id the draw already chose - no second draw,
      no second stream - and reading it rides the `use` verb a potion is
      already drunk with. Casting recovers the spell's `heal`, never above
      the max, and keeps the potion's already-whole rule; known spells are
      one section of the Bag panel, not a second action system. Every key is
      optional and additive: a pack that names none bakes no
      `window.VEFR_SPELLS` line at all, drops the same ids and bakes the
      same `VEFR_ITEMS` (hashed both ways in `tests/test_spells.py`), and
      its baked data is byte-identical to `main`'s. `vefr check` refuses four things, one
      sentence each: a school the block does not declare, a `level` under 1,
      a book teaching a spell the pack does not declare, and a spell with no
      school - and each goes red when its own refusal is removed. Gaps,
      deliberately: nothing says what a *school* does in play, `heal` is the
      whole of what a spell does, nothing sets `identified` true so the
      lesson rides `use`, and no event carries a spell. Since then (#345
      leftovers): every cast writes a `cast-<id>` why-log entry in the
      panel's own words, the no-school refusal names the spell and
      `world.json`, and `tests/test_spell_table.py` holds the shape, the
      bake and the player's reads to one another. ADR:
      `docs/adr/0018-spells-schools-and-spellbooks.md` (Proposed).
      Guide: `docs/guides/rulesets.md` → spells. Tests:
      `tests/test_spells.py`, `tests/test_spells_play.py`,
      `tests/test_spell_table.py`, `tests/fixtures/make_spell_pack.py`.
- [x] **Combat, first slice — bump to fight, and monsters that come for you**
      (2026-09-30): the dungeon had floors, fog, doors, stairs, books and a
      chest - and nothing to fight. A region's `contract.json` may now carry
      `enemies` (`{id, name, at, hp, atk, sprite, sight?}`; `sight` defaults
      to 6, Manhattan), and `world.json`'s `player` block gains optional
      `hp`/`atk` (default 6/2) and a `wake` point (default: the act's first
      region at its `hero_start`; a wake that names no real region is dropped,
      one on a missing or solid tile falls back to the region's start). The
      woven player bakes both (`VEFR_ENEMIES` per region, `VEFR_HERO`) and
      runs a turn-based, deterministic fight: walking into a living enemy
      bumps to attack for `hero.atk`; after every successful move each living
      enemy acts once - adjacent it strikes for its `atk`, else within
      `sight` it steps one tile toward the hero (larger axis first, never
      onto a solid tile, another enemy, or the hero), else it holds. A killed
      enemy is remembered per region, per world
      (`vefr-slain-<world>-<region>`) so a cleared room stays cleared. Zero
      hp is Cozy death: hp restored, one plain line, wake at `wake`; nothing
      is lost. The HUD health line now shows the hero's real `hp/max`
      (replacing the per-phase costume) and an `aria-live` line speaks each
      hit. Zero deps, no randomness, no clock, no model call. Gap: no
      items/loot, no fleeing, no rooms-and-corridors AI, classic death later.
      Guide: `docs/guides/rulesets.md` → combat. Tests:
      `tests/test_combat_loop.py`, `tests/test_transitions.py`,
      `tests/test_builder_weave.py`.
- [x] **Fog of war, for regions that ask for it** (2026-09-29): a region may
      declare `fog` (true, or `{"radius": N}`); the woven player then draws
      only what the hero has seen - a lit circle around them, walked ground
      remembered dimmed, everything else black. Explored tiles persist per
      region, per world. Opt-in, so a town stays bright; doors, books,
      chests and people stay hidden until seen. The Cottage floors carry
      `{"radius": 4}`. Baked per region
      (`cli._region_entry` -> `VEFR_REGIONS[<name>].fog`) and recomputed on
      entering a region. Test: `test_a_region_can_declare_fog`.
- [x] **The delve, first slice — generated dungeon floors** (2026-09-30): the
      game has an authored first floor and a stair down, but nowhere to
      fight or explore. `src/vefr/delve.py` is a rules-only floor generator:
      `generate_floor(seed, width, height, rooms)` draws rooms joined by
      L-corridors from `random.Random(seed)` alone (no global random, no
      clock), keeps a solid border, and guarantees one connected cave with
      `u`/`d` reachable from each other and at least `MIN_STAIR_DISTANCE`
      (10) Manhattan tiles apart when the layout allows (it relaxes to the
      widest pair otherwise). `LEGEND` maps `#`/`.`/`u`/`d` to the tile set's
      `dungeon-*` pictures; `contract()` writes the region `contract.json`.
      `norns delve` draws N floors, writes each as `acts/<id>/floor-N/`
      (`map.md` + `contract.json`), continues the `floor-*` numbering (or
      `--first-name`), and wires the stairs as transitions: the from-region's
      tile down to the first floor, each floor's `d` to the next, and every
      `u` back up; the last floor is the bottom for now. It refuses an
      existing region without `--force` and never writes outside the pack.
      The woven player is untouched — it already walks regions and uses
      stairs. Gap: generated once at build time from a seed; per-playthrough
      generation is a later slice, and only the first region's full geometry
      is validated (generated floors ride the door checks). Zero deps, no
      model call. Guide: `docs/guides/rulesets.md` → delve. Tests:
      `tests/test_delve.py`.

- [x] **Regions + door transitions in the woven player** (2026-09-29): an act
      can already declare several `regions`, but the woven player baked only
      the first and `transitions` was a reserved field. An act's `transitions`
      is now a list of doors (`{"from": "town", "at": [4, 5], "to":
      "cottage", "to_at": [4, 3]}`), and a speaker may name its `region`
      (default: the act's first). The loader keeps the act's speakers and
      attaches each region its own `speakers`; `weave_html` bakes
      `window.VEFR_REGIONS` (each region's map + contract), `VEFR_TRANSITIONS`
      (the doors, verbatim), and `VEFR_SPEAKERS` (grouped by region);
      `web/packaged.html` reassigns the current map, people and hero when the
      hero steps on a door, so a town and the entry room inside it are two
      maps joined by a door. A map with one region and no doors behaves exactly
      as before (the sample's visual baseline does not move). `maplab.validate`
      checks every door: `from`/`to` name declared regions, and `at`/`to_at`
      are on their maps and walkable. Known gap: only the first region's full
      geometry is validated today; the others are read for the door checks
      only (a follow-on). Tests:
      `test_builder_weave.py::test_woven_file_bakes_regions_transitions_and_grouped_speakers`,
      `test_transitions.py`. Deterministic: no model call anywhere.

- [x] **The manual names the camera and the sprites** (2026-09-29): "How Maps
      Work" now says a map can be bigger than the screen and is read through a
      *camera* that moves with the hero, and that the people on a map are
      *sprites* (a game can bring its own). The glossary gains `camera`;
      `sprites` already existed (with `sprite` as an alias). The studio-lessons
      note records the one class that bit us three times - the shipped player
      lagging the studio - and points at its fix: one renderer shared by the
      room and the file. Only what is true today is written; the *transition*
      entry waits for regions to land.
- [x] **The map scrolls with a camera** (2026-09-29): the woven player scaled
      the whole map to fit, so a floor bigger than the screen would shrink to a
      thumbnail. The canvas is now screen-sized and a camera follows the hero:
      a map that still reads whole is fitted and centred as before, a bigger
      one scrolls at a comfortable tile size, clamped at the edges. Only the
      visible window is drawn, at device-pixel resolution. Ground for bigger
      towns and dungeon floors. Visual baseline updated deliberately.
- [x] **Characters in the pack, drawn in play** (2026-09-29): the hero and
      every speaker were code-drawn figures (a dot, a lollipop). A pack may now
      name a sprite per character in a `sprites/` folder - `hero.png`, and one
      named for each speaker key. `weave_html` inlines them as data URIs
      (`cli._player_sprites` -> `window.VEFR_SPRITES`) and the woven player
      draws them where a character stands, taller than its tile with feet on
      the ground, falling back to the drawn figure when a name has no sprite.
      Cottage's first two: a town character (the owner's pick) and the hero.
      Test: `test_builder_weave.py::test_woven_file_bakes_pack_sprites`.
- [x] **The woven player draws the people** (2026-09-29): speakers were
      invisible in the shipped file - the studio's live player drew a
      body-and-head figure per speaker (`web/town.js`), the woven player drew
      only the map and the hero, so a player had no idea who was there to talk
      to (and tapping the map near an unseen speaker fired their line). The
      woven player now draws the same figure at each speaker's tile, scaled to
      the pack's tile size, using the pack's `speaker_color`/`speaker_head`,
      falling back to the engine's. Visual baseline updated deliberately.
- [x] **The Library, slice L2 — books found in play** (2026-09-29): the
      woven single-file player now carries a pack's books and lets a player
      find them. `weave_html` bakes `window.VEFR_LIBRARY` (fixed key order:
      id, title, kind, found, at, speaker, when, pages, found_words; `extra`
      dropped; no `library/` folder reads `[]`). `web/packaged.html` grants
      by `found`: shelf from the start, map when the hero lands on `at`,
      resident when the nearest speaker's key matches `speaker`, and earned
      for the two events a player can see (`first-visit` on the first load,
      `book:<id>` once that book is read) — `bell`, `act-complete` and
      `rumor-verified` stay unfound rather than invent an event. Found ids
      persist at `localStorage['vefr-library-<world>']`; a found book shows
      an aria-live toast and opens an accessible reader (real buttons, 44px,
      plain-text pages, arrow keys turn pages, Esc closes, movement guarded).
      The pause menu gains a Books panel listing what's found and counting
      what isn't. No model call, no timers. Guide: `docs/guides/rulesets.md`
      → library. Tests:
      `test_builder_weave.py::test_woven_file_bakes_the_packs_books` and
      `test_woven_file_without_a_library_bakes_an_empty_list`.
- [x] **The woven player draws the pack's ground tiles** (2026-09-29):
      a game looked plainer shipped than it did in the room that made it.
      The studio's Map Room draws picture tiles; the woven player drew flat
      colour rectangles, so a first playable build read as a dark, empty box.
      `weave_html` now resolves the same tile per legend symbol the room's own
      `tileFor` does (`cli._player_tiles` - explicit `"tile"`, else
      solid/sanctuary/deco pick stone-wall/rug/grass, else open ground picks
      grass or path by order), inlines each as a data URI (`window.VEFR_TILES`),
      and the player draws it, falling back to the symbol's base colour when a
      symbol has no tile. Tiles are ~2-4 KB each. Visual baseline updated
      deliberately (`tests/baselines/packaged-sample.png`, `VISUAL_UPDATE=1`).
      Test: `test_builder_weave.py::test_woven_file_inlines_the_legend_tiles`.
- [x] **The commission board, first slice** (2026-09-29): the studio-is-a-game
      loop starts. `src/vefr/commissions.py` is a rules-only module registry
      (one module, the Cartographer's map-sketches) plus a pack rule (`needs`):
      a commission is done when the town draws at least three kinds of ground
      and marks one as a place (a decorated or sanctuary square the Map Room
      can paint), and open otherwise with a plain reason - no model call
      anywhere. `GET /api/builder/commissions` serves the board; defer/resume
      persist to `data/commissions.json` (gitignored) so "not now" survives a
      restart, and a done job reads done regardless. The Hall gains a
      Commissions section: an open card offers the room (`Open the Map Room`)
      and a real "Not now" button, a finished one a quiet line; tap targets
      reuse the 44px `.cta`/`.btn` family, status is words not colour, no
      motion. Reply shapes declared in `replies.py` (`extra="forbid"`). Tests:
      `tests/test_commissions.py` (registry, the rule on bare vs satisfied temp
      packs, deferral persistence, all three routes incl. unknown-id 400 and an
      unreadable pack as an empty board). Guide:
      `docs/guides/studio-modules.md`. Next: the other modules, the ladder, the
      spare parts shelf.
- [x] **chat: a drafted voice can't loop; dedupe at the draft seam**
      (2026-09-26): the WP5 `norns chat` acceptance build left a voice file
      that said the same sentence over and over (`.project/DECISIONS.md`,
      2026-09-25). The artifact world was deleted as a test artifact, so the
      file can't be re-read; the mechanism was reproduced instead with a fake
      backend. **Cause:** nothing in the interview ever looked at what the
      model *said*. `draft()`'s `format` pins the JSON shape, never the
      content, so a small brain sampling at 0.85 that falls into a repetition
      loop answers with perfectly valid JSON full of one repeated sentence —
      and the interview wrote it to `voices/<name>.md` verbatim. The same hole
      fed the logbok, phase moods, bond prose and the per-phase seeds.
      **Fix:** `chat.dedupe_repeats()` — sentence-level, keeps the first
      occurrence in order, preserves line breaks and bullet lists, never
      invents text — applied at the one prose seam, `draft()`, which every
      interview draft and `/api/builder/chat` pass through. A draft that comes
      back empty now takes the retry → placeholder path instead of being
      written blank. Tests:
      `test_interview_voice_file_has_no_repeated_sentences` (a looping fake
      backend; the saved voice file is read off disk),
      `test_draft_returns_one_copy_of_a_looping_model`,
      `test_dedupe_repeats_keeps_the_first_copy_and_the_order`. No live model
      in any test; the engine stays game-neutral. **Found, not fixed here:**
      the interview writes the first speaker's draft to the pack root's
      `voices/<name>.md`, while an acts-shape pack's live voice file is the
      region one (`acts/<act>/<region>/voices/` — `resolve_voice_file()`
      prefers it). A separate path question, left alone under "smallest
      change".
- [x] **`ratatoskr spark status` tells the truth about a remote Spark**
      (2026-09-26): with Spark on another machine, the status command
      looked for the model file on this one and asked systemd over SSH
      for a `spark` unit (the appliance runs it under compose), so a
      healthy Spark always read "model FAIL / service unknown". Now a
      remote `VEFR_SPARK_URL` is checked by asking the server which GGUF it
      serves (`/props`) against the pinned file, and by health; local
      Spark keeps the file + service checks. `spark.is_remote`,
      `spark.served_model`; tests in `tests/test_spark.py`.
      `docs/guides/spark.md` no longer claims an engine-host fallback copy.
- [x] **Screenshots gallery + docs at current truth** (2026-09-26):
      `scripts/capture-screenshots.py` now photographs the studio as it is
      (every room at 1440px night, three rooms in daylight, three at 390px, a
      book open in the Library, a resident's chat, the woven player dark and
      light) as JPEG (2.5 MB, was ~12 MB as PNG) and writes
      `docs/screenshots/README.md`, the gallery page, from exactly the
      pictures it took. The old workshop screenshots are gone. The
      `screenshots` workflow runs on any `web/` or `src/vefr/` change
      (it only watched pre-redesign files), is read-only (its comment
      claimed it committed back; it never did), and uploads the gallery as an
      artifact; the committed gallery is refreshed by running the script.
      README, GETTING_STARTED, AGENTS and design/UI-REFERENCES describe the
      studio as it is. The sample world gains three demo books (CC0; "Writing
      a Book" teaches the format).
- [x] **The Library, slice L1** (2026-09-26): books a world keeps. A pack
      may carry `library/*.md` (front matter: title, found = shelf | map |
      resident | earned, at, speaker, when, kind; `* * *` breaks pages).
      `src/vefr/library.py` parses and validates (wired into
      `maplab.validate`, so `norns validate` checks every book); the
      loader carries `world["library"]`; `GET /api/library` (new, read-only,
      name-validated) serves the world's books + the studio shelf
      (`web/library/`: the game-making handbook as eight books); the
      workshop gains Urðr's Library room (shelves of spines, a parchment
      reader one page at a time, arrow keys turn pages, Library in the top
      nav and phone tab bar); the book export gains "The Library" chapter.
      No model call anywhere. Guide: `docs/guides/rulesets.md` → library.
      Tests: `tests/test_library.py` (20: format, every validator rule, the
      studio shelf, loader, API, export, reader harness
      `tests/fixtures/library_harness.mjs`). Next: L2, finding books in
      play (map pickup, resident gives, earned), then L3, writing books in
      the studio.
- [x] **The studio comes alive** (2026-09-26): residents change faces:
      the chat panel shows a resident thinking while they answer, happy when
      they reply, and sleepy when no model answers (`chat.py`'s
      "(draft failed" sentinel reply is now read as a failure, with an
      honest message and no "keep this note" offer); greeters look sleepy
      while the Storyteller is unreachable. Action poses sit beside what each
      resident tends (the brief, the drawing table, the invite bench, the
      forge, the cast card, the archive stairs, the boiler, the household).
      The Floor opens with a cutaway of the World Tree (Codex-generated,
      provenance in `web/art/README.md`) and carved room emblems; wood and
      iron textures on the creed band, shelves and top bar; the app icon as
      favicon; Ratatoskr waves goodbye in the footer. Words still carry every
      meaning; pictures are decorative (`alt=""`) except the cutaway, which
      is described. Gates: `pytest -q` 551 passed, 1 skipped; `ruff` clean;
      public-surface clean; axe-core over 11 rooms in night and day: zero
      serious/critical; 1440px + 390px screenshots: no errors, no sideways
      scroll.
- [x] **Commit a map to the world from the page** (2026-09-25): the
      drawing table could sketch and check but never write - "keep this
      sketch" saved a keepsake to the vault. New
      `POST /api/builder/map/build` validates the draft with maplab's own
      gate (422 with the validator's errors in words), refuses to clobber
      an existing map without `force` (409), then writes through the CLI's
      path (`maplab.write_pack`), copying the previous map file beside it
      as `<name>.bak-<timestamp>`. The pack name goes through
      `safe_pack_name` (400). The map room gains "use as this world's map"
      next to "keep this sketch" (≥44px, focus-visible, status in words;
      409 asks "Replace the current map? A backup is kept." with
      replace/cancel) and refreshes the world on success.
      Tests: `tests/test_map_build.py` (invalid → 422 + nothing written;
      valid → bytes match `norns build-map`; existing → 409; force →
      replaced + backup; acts shape → `map.md` + backup + fresh
      `/api/world`), plus the new route in the pack-name guard matrix.

- [x] **The studio's own art** (2026-09-26): owner-commissioned art,
      web-sized WebP in `web/art/` (1.2 MB): ten resident portraits replace
      the placeholder drawings; every room header carries its banner under a
      dark wash; the Studio home hero is the World Tree; Ratatoskr sleeps on
      a letter pile in empty rooms and searches with a lantern while loading;
      Bolt naps on the boiler when Spark is off; a new wax seal. License CC
      BY-SA 4.0 (owner decision), recorded in `web/art/README.md`,
      `THIRD_PARTY_NOTICES.md` and `README.md`. Gates: `pytest -q` 551
      passed, 1 skipped; `ruff` clean; public-surface clean; axe-core over
      all 11 rooms in night and day: zero serious/critical.
- [x] **Studio Hall: the workshop UI, completely replaced** (2026-09-25, owner: "complete replace", "never wanna see the old one
      again"). A game studio the old Norse run: iron top bar, room header
      with its resident, rune bands, engraved lettering (Cinzel, SIL OFL
      1.1, self-hosted), night by candle / day in the hall
      (`data-light`, separate from the contrast tiers, which keep
      working). New shell in `web/app.html`, all look in
      `web/studio.css`; `web/app.css` is deleted when the last room is
      rebuilt. Rebuilt so far: the Studio home (was the Foyer: hero from
      the world on the table, worlds as posters, news from the Chronicle,
      begin-a-world, the residents, the mantel), the Floor (new: every
      department), the Chronicle, the Desk, the Casting Table (all 24
      stones as carved tiles, plus "Cast the stones": a three-stone spread
      from `/api/runes/cast`; runes render via self-hosted Noto Sans Runic,
      SIL OFL 1.1, since most systems ship no Runic font), the Archives (a
      staircase that darkens with each step; raw truth is a keyboard-
      reachable disclosure, fixing the old `scrollable-region-focusable`),
      the Folks and the Vault (the forge and its drafting panel restyled;
      empty and loading states draw the squirrel instead of an emoji, which
      rendered as a missing-glyph box on systems without an emoji font), the
      Hall (creed plaque, the town window framed in wood, keepsake shelves,
      the household with portraits; its pressed-leaves shelf had the same
      blank-text bug as the Chronicle, now fixed) and Settings (Bolt, the
      face of Spark, gets a card that says in words whether Spark runs), and
      the Map Room (regions as pinned scraps with their survey, the drawing
      table with ink pots and a 44px tile grid in a wooden frame). Map fix:
      the pack check posted no JSON body, so `/api/builder/validate`
      answered 422 and the room always read "the pack won't answer";
      `web/js/api.js` now sends `{}` and the check reads "ok".
      Old `app.css` rules for rebuilt rooms are deleted as each room lands.
      Chronicle fix: actions, npc lines and
      letters no longer render as blank rows; runs of actions fold into
      one line (`web/js/chronicle.js`, pinned by
      `tests/test_web_chronicle.py`). The first walk, the resident folio and
      the house sheet are restyled too, and `web/app.css` is deleted.
      Accessibility fixes found on the way: `prefs.js` joined the
      `data-prefs` tokens with `;`, but every stylesheet reads them with
      `[data-prefs~=...]` (whitespace-separated), so no reading preference
      ever applied (font, text size, motion, spacing); tokens are now
      space-separated and `tests/fixtures/prefs_harness.mjs` pins it. The
      workshop never declared the OpenDyslexic face, so that choice fell
      back to Georgia; `web/studio.css` declares it, and with OpenDyslexic
      chosen the headings drop their engraved capitals. Text size now
      scales the root, so the whole page grows with it. Gates: `pytest -q`
      551 passed, 1 skipped; `ruff` clean; public-surface clean; axe-core
      over all 11 rooms in night and day: zero serious/critical; 1440px and
      390px screenshots of every room: no page errors, no sideways scroll.
- [x] **Weave from the web: a phone user with no terminal can make the
      shareable file** (2026-09-25): `ratatoskr weave` was terminal-only.
      The packaging core moved out of `cmd_build_web` into `weave_html` +
      `build_web` (the CLI keeps calling it, output byte-identical), and the
      served workshop's Desk grows a "Make shareable file" button:
      `POST /api/builder/weave` builds the current world (same `pack_dir`
      resolution as the other builder routes) into a server-owned dir
      (`VEFR_WEAVE_DIR` or `app_home()/dist`), one at a time (409 on a
      concurrent weave), returning `{name, size_bytes, built_at,
      download_url}`; `GET /api/builder/weave/file/{name}` serves that file
      as an attachment behind a strict filename regex + in-dir resolve
      (traversal refused). The page shows "Weaving…" then "Ready · N KB",
      then a Download link and — where `navigator.share` supports files — a
      Share button (>=44px targets, visible focus, status as words, 390px).
      Tests: `tests/test_builder_weave.py` (metadata + real download,
      traversal refusal, 409 lock, CLI/shared-core byte parity). Gates:
      ruff clean; pytest 488 passed / 3 skipped; sample-world validate ok;
      public-surface clean (401).

- [x] **Local test packs removed** (2026-09-25): owner ruling — the
      gitignored `worlds/rylee-alpha-world/` and `worlds/kitchen-playtest/`
      were test artifacts; deleted from disk (default pack now resolves to
      `sample-world`). DECISIONS and CURRENT corrected from "parked".

- [x] **Weave keeps acts for relative out-of-root packs; rumor canon pinned**
      (2026-09-25): `ratatoskr weave --pack ../<repo>/worlds/<pack>` silently
      dropped `VEFR_WORLD.acts` (the relative path was joined under
      `worlds/` and the load error swallowed), so the player's act router
      never saw `ruleset: cooking` and opened the town instead of the
      kitchen. `cmd_build_web` now resolves path-style packs to absolute.
      Regression: `test_weave_keeps_acts_for_relative_out_of_root_pack`
      (fails before, passes after). Also pinned: every rumor's system prompt
      carries the pack's `logbok.md` (`test_rumor_prompt_carries_pack_canon`;
      true since 2026-08-31, previously unpinned).

- [x] **Resolve the open-issue list** (2026-09-25): (1) the CI `--ignore`
      flags and the "informational" pytest step named two Storyteller test
      files that exist nowhere in the tree or history, and a tracker item
      (#50) that is no longer reachable; the informational step failed
      silently on every run. All removed: CI and the docs now run plain
      `pytest -q`. (2) D6 finished: engine tests and the rulesets guide
      example use neutral fixture fiction, no game-pack names. (3) The
      2026-09 model-benchmark reports and harnesses moved to
      `.project/archive/model-benchmarks-2026-09/` (only consumers were each
      other). (4) Owner rulings recorded in DECISIONS: the sibling engine repo kept separate (D5
      superseded), alpha pack parked, old art commit accepted. CURRENT.md
      updated; one open design call remains (rumor path reads no pack canon).

- [x] **Green main + orientation refresh** (2026-09-25): `78fa0f8`
      named the sibling engine in AGENTS.md and tripped
      `test_no_historical_package_names` (CI red on main). AGENTS.md now
      points to `.project/DECISIONS.md` (outside the audited roots), which
      records the not-synced rule and flags D5 as unreconciled.
      `.project/CURRENT.md` rewritten: the phase table (engine at Act 2, the game
      pack at Act 1 awaiting the owner's taste-pass), where the out-of-repo
      plan lives, open owner decisions, small safe debt, and a gate command
      that matches CI. Gate: ruff clean; pytest 0 failed; public-surface
      clean; validate ok.

- [x] **Act 2 increment 1: the Desk ruleset - is_true finally consumed, the
      world knows its own stories** (2026-09-22): Phase 2 of the game plan
      begins. Engine: `desk.py` (verify / print / facts / prompt_lines -
      deterministic, no model calls; knowledge DERIVED from the session
      journal on every read, no separate store to corrupt); rumors and NPC
      lines now thread the session id into their prompts, so
      `WHAT THE WORLD KNOWS NOW` (confirmed / debunked / printed) rides in
      every later generation; routes `POST /api/desk/verify`,
      `POST /api/desk/print`, `GET /api/desk/facts` (added under the
      approved plan; AGENTS ask-first noted in this entry); pack contract
      gains the per-act `desk` block (headlines validated >= 2 when
      `ruleset: desk`). Player: the packaged player grows a Desk screen
      (listen -> trust/doubt -> print -> what-the-world-knows), fully
      client-side like the rest of the single file, reusing the honest
      fallback chain (live schema -> woven pool -> composer -> fragments).
      Tests: test_desk.py (8 server pins incl. prompt injection both ways)
      + desk_harness.mjs + test_desk_loop.py (5 play pins; whole loop <= 6
      clicks). Weave now resolves out-of-root packs by path for pool builds
      (fixes tmp-pack weaves; BJ repo weaves unaffected). dev-guards: the
      desk pack joins the axe gate. Gates: a11y no serious/critical on
      sample+kitchen+desk weaves; visual drift 0.0000%; ruff clean; pytest
      2 failed (documented model-up env pair) / 474 passed / 1 skipped;
      public-surface clean (394); validate ok.

- [x] **Dev-guards: the tooling gate (owner directive: "implement them and
      continue development")** (2026-09-22): the MIT-tooling survey's top four
      land as one guard workflow + hardening. (1) `dev-guards.yml`:
      actionlint 1.7.12 (checksum-verified release binary) + zizmor 1.30.1
      (pinned `uv tool run`) over `.github/`; axe-core 4.13.0 gate (vendored
      MPL-2.0, `scripts/a11y_check.py`, real chromium via the existing
      playwright test dep) over BOTH woven players (sample + kitchen
      fixture); visual regression (`scripts/visual_regress.py`) — stdlib
      PNG decode (zlib + scanline unfilter, zero new deps; pixelmatch
      evaluated and set aside to honor keep-deps-short) against a committed
      baseline, `VISUAL_UPDATE=1` for deliberate redesigns. (2) zizmor's
      first run found seven live findings in OUR workflows; all fixed or
      justified: `persist-credentials: false` on ci/secret-scan/security
      checkouts, dependabot `cooldown: 7d`, screenshots.yml keeps its push
      token under a justified ignore, publish-image's `workflow_run`
      (main-branch-filtered, post-merge SHAs only) under a justified
      ignore. (3) the kitchen harness moved from my hand-rolled stub DOM to
      **jsdom** (MIT, dev-only `package.json`; happy-dom evaluated and
      rejected with evidence: it does not execute inline scripts via
      document.write). (4) `tests/fixtures/make_kitchen_pack.py` factors the
      neutral kitchen fixture out for CI gates. New: THIRD_PARTY.md
      (vendored/dev-only provenance). Local evidence: a11y gate no
      serious/critical on both woven players; visual drift 0.0000% vs fresh
      baseline; actionlint clean; zizmor "No findings" (2 ignored, 10
      suppressed); ruff clean; pytest 2 failed (documented model-up env
      pair) / 461 passed / 1 skipped; public-surface clean (384); validate ok.

- [x] **Act 1 increment 1: the kitchen ruleset v0, act-runner router, and the
      pleasant-loop harness** (2026-09-22): Phase 1 of VEFR-GAME-PLAN begins per
      the owner's Act-1 directive (a cooking act that wakes, serves, and prints
      its first page). Engine: per-act `cooking` contract block (pantry / tickets /
      morning_length / headlines / optional opening + byline) loaded by both
      loaders,
      shape-validated by maplab (orders must reference real pantry ids; every
      ticket needs the customer's voice; headlines must be a real choice),
      echoed by inspect. Player: `web/packaged.html` gains a per-act screen
      router (`startPlaySurface`) and the kitchen - tickets arrive as spoken
      notes (reading them is the game), assembly resolves by deterministic set
      equality, wrong burritos get kind beats never slaps, tickets set aside
      wait without penalty (no timers anywhere: `setInterval` absent from the
      template), and the morning closes with the player's first editorial
      choice printing page 1 of the paper (masthead, headline, pack byline,
      honest body, pack creed, "more mornings soon") plus a sleep/wake replay
      nudge. Tests: tests/test_cooking_contract.py (contract pins) and
      tests/test_kitchen_loop.py + tests/fixtures/kitchen_harness.mjs - a
      stub-DOM harness that EXECUTES the woven file and plays a whole morning,
      asserting journal order, kind beats, the printed page, a ≤4-clicks-per-
      ticket budget, and timer absence: the CI-enforceable half of the
      pleasant-loop protocol (VEFR-ACT1-SPEC §9). Playtest pass 1 (harness,
      offline): 8 clicks for a 3-ticket morning; fix-forward landed in the same
      increment (set-aside beat line was overwritten by the morning-over line;
      both now read). Weave bakes the acts contract (verbs/floor/tone/ruleset/
      cooking) so packaged packs carry their law; cli's default tagline lost its
      last private-canon string (the old private tagline, now the engine
      tagline; the canon list grew the string so the guard proves it stays
      gone - and caught this very entry quoting it, twice).
      Gates: ruff clean · pytest 2 failed (both documented model-up env) /
      461 passed / 1 skipped · public-surface clean (381) · norns validate ok.

- [x] **Phase 0 boundary: private canon out of the engine, pack-law contracts
      in, guards into code** (2026-09-22): owner-approved Phase 0 of
      VEFR-GAME-PLAN-2026-09-22 (vision interview Q1-Q8 is the authority).
      (1) Private-game assumptions removed WITHOUT touching the Norse
      identity: the engine tagline/PURPOSE (the old private tagline is gone;
      now "a rumor engine for playable worlds" + "the loom is strung; the
      world provides the thread"), gold-canon prose in journey.py/runes.py,
      the hardcoded 'awed'-phase sighting in town.js, starred stefna letters
      routed under a pack phase name (now their own `## letters` heading), and
      CSS/encounter lines keyed by phase/bond NAMES (now positional: the pack's
      culminating phase wears the accent via data-culm; encounter lines key by
      phase index). (2) Pack-law contract (world.py docstring): per-act `floor`
      (costume|story|stakes; default costume = today's behavior exactly),
      `tone` (the ridiculous-literal dial, carried in the storyteller prompt),
      `ruleset` (default ambient), `verbs` (the act's own action vocabulary -
      when declared it replaces the costume verbs in the HUD AND the
      /api/combat/action whitelist); `enemies/bosses/transitions` now
      shape-validated. All optional; every existing pack loads unchanged.
      (3) Guards extended into engine code: canon-strings list carries the
      removed strings (it caught this very entry's first draft quoting them -
      the teeth work); tests/test_phase0_boundary.py pins the boundary in CI
      (no pack phase names in engine behavior, no private taglines, verb/
      floor/tone/ruleset validation, tone-dial prompt carriage).
      (4) Function preserved: ruff + pytest + public-surface + norns validate
      green; sample-world untouched.

- [x] **web: setup is a choice, not a wall; the URL join can't double**
      (2026-09-22): two player-facing defects in `web/packaged.html`,
      both hit live during the WP5 playthrough. (1) Every POST joined
      `llmUrl + '/v1/chat/completions'`, so the config URL as the
      placeholder itself shows it (`...:11434/v1`) produced
      `/v1/v1/chat/completions` and a dead 404 — the join now lives
      once in `chatEndpoint()` (idempotent over base, `/v1`, trailing
      slashes, pasted full endpoint). (2) First-run setup hard-gated
      `alert('both URL and model are required.')`, with no way past it
      even though the woven pool exists precisely to carry offline
      play — both-blank now saves as a remembered offline choice
      (`configured: true`, older saves still pass), half-filled still
      warns (one without the other can never reach an endpoint), and
      `llmPost()` rejects straight into the pool/fragment fallbacks
      instead of fetching a relative URL. Pinned by
      `test_chat_endpoint_normalizes_the_config_url` and
      `test_setup_gate_allows_offline_play`.

- [x] **chat: a dead endpoint falls back, never crashes the interview**
      (2026-09-22): every model call in the interview retries twice
      before falling back to scaffold/placeholder — except transport
      failures never reached that loop: `generator._completion` wraps
      httpx timeouts in `GeneratorUnavailable`/`GeneratorFailed`, which
      none of the four retry loops caught, so a slow brain killed the
      interview mid-run (the `draft()` docstring's "never a crash
      mid-interview" was false for the one failure most likely to hit a
      first-time author). Found live during the WP5 owner walkthrough;
      both vefr transport exceptions now take the retry → fallback path
      in `draft`, `draft_theme`, `propose_map`, `propose_face`, pinned
      by `test_dead_endpoint_falls_back_instead_of_crashing`.

- [x] **weave: acts-shape packs bake the resolved world** (2026-09-22):
      `cmd_build_web` baked the raw `world.json` root, but acts-shape packs
      keep `town`/`speakers`/`creed` under `acts/<id>/` — so a woven file from
      such a pack drew a blank town (`setupTown` TypeError, bootstrap aborted
      before the verbs attached), exposed no `npc:` pools (`pool.py` read the
      long-dead root `speakers`), and fell back to the default tagline. Weave
      now merges `load_pack()` over the raw root (same shape the CLI's live
      path resolves), `pool.py` takes speakers from `current_act()`, and the
      pool fixtures were converted to acts shape — which is itself the
      regression test. Found by the first-ever browser stranger-test of a
      woven file (WP7).

- [x] **weave: template resolution works from a pip-installed engine**
      (2026-09-22): `cmd_build_web` resolved `web/packaged.html` only via
      the source-checkout or `VEFR_HOME` layouts, so a pack author running
      `ratatoskr weave` from their own repo (installed wheel) hit
      FileNotFoundError before any weaving began. The wheel now ships the
      template as package data (hatch force-include → `vefr/web/`),
      `_template_candidates()` covers checkout → package data → VEFR_HOME
      in that order, and regression tests pin both the candidate shape and
      the packaging config. Found while weaving the demo from the pack
      repo (WP7).

- [x] **WP6-wrap: templates + brain-socket example neutralized** (2026-09-22):
      owner chose "fix now" — the two copy-paste storyteller tests plus their
      sample fixture under `tests/templates/`, and the persistent-memory
      example in `docs/guides/brain-socket.md`, were the last tracked
      surfaces quoting private-pack names. All now use engine-neutral
      caretaker/forge and market-lane examples; self-contained tests stay
      green, guards clean (378 — the +1 is `sample-scene.json`, now tracked
      and scanned per D6, which was untracked during WP6's guard run).

- [x] **WP6 / D6: fixture content follows ownership - neutral sample
      in the engine, seam for pack scenes** (2026-09-22): the
      engine-owned audition fixture was a private pack's scene. D6:
      it moves to the BJ pack repo, and the engine now ships
      `tests/fixtures/storyteller/sample-scene.json` as the
      `norns storyteller-test` `--scene` default and the docs
      showcase (regenerated from real packet output). The loader
      gains `VEFR_STORYTELLER_FIXTURES` - a PATH-style dir list
      searched before the engine's own fixtures, so pack-supplied
      scenes win on id collision. The public-surface guard no
      longer skips `tests/fixtures/storyteller/` (that skip existed
      only for the moved fixture); engine tests repoint at
      `sample-scene`, and the BJ-content assertions move to the BJ
      pack's own test suite.

- [x] **example.env: interface port corrected, spark modes made explicit**
      (2026-09-22): the Interface Translator block still said "Port 8085
      is the unambiguous default" with `#VEFR_INTERFACE_URL=…:8085` —
      stale since WP2 moved the translator :8085 → :8087 (vision took
      :8085). Value and comment now say :8087, matching
      `interface.py:174` and `test_interface.py`. The Spark comment now
      names both documented modes (:8082 no-bundle default, :8083
      bundled image → `docs/guides/bundled-brain.md` carries both
      columns). Recon finding recorded: a suspected `spark.py`/:8082 vs
      `volumes.py`/:8083 contradiction is NOT one — the three writers
      are each self-consistent per mode, so no port code changed.

- [x] **Docs restructure: three-section README + canon guard on root
      docs** (2026-09-22): README grew to 484 lines mixing philosophy,
      world-authoring, and ops. Restructured to three pillars - "Open
      and play" (60-second start), "Build a world" (bones/flesh
      contract, pack layout, Design/Hero's-Journey + lore-pack tables,
      Surface), "Run the engine" (container, config, compose) - with
      the intro relinking to the new anchors, ~200 lines out. Moved the
      env-var table into GETTING_STARTED "What you need" with defaults
      corrected to code truth (`VEFR_MODEL=gpt-oss-20b`,
      `VEFR_LLAMACPP_URL=:8081`, `OLLAMA_URL=:11434`,
      `VEFR_KEEP_ALIVE=1m`), reordered GS to §1 get the code → §2 open
      and play → §3 make your own world → §4 sound check → §5 CLI →
      §6 shipping → §7 API (CONTRIBUTING anchor updated), relocated the
      phone-as-backend section to `docs/guides/install.md`, and cut
      count-free CLI prose from `cli.py --help`, `AGENTS.md`, and GS
      (`--help` is canonical). Scrubbed the one private-game canon line
      from README and extended `test_pack_neutrality` to audit root
      `*.md` + `LICENSE` with whitespace-normalized matching - RED
      captured pre-scrub (README:435), green after. Kept the
      worked-example lore tables (tight) and the pack file list;
      module tree compressed to pointers at `src/vefr/*.py` docstrings
      + `brain-socket.md`.

- [x] **screenshots workflow: first-ever green run** (2026-09-22): the
      auto-capture workflow had never passed — 7 straight failures
      since wiring. Every capture step actually succeeded (artifacts
      uploaded, ~1.5 MB of PNGs); the run was failed only by
      `setup-uv@v5`'s post-step, which prunes the uv cache before
      saving. The prune hung 5 minutes and exited 2, so the cache
      never once saved (every restore missed "No GitHub Actions
      cache found") — pure cost, sole failure. Aligned screenshots.yml
      to the exact pins `ci.yml`/`security.yml` already use and pass
      with: setup-uv v10.1.0 (prune-cache defaults false, node24),
      checkout v7.0.1, upload-artifact v7.0.1 — all SHA-pinned like
      the rest of the fleet.

- [x] **The creed: pack field rename + sample-value sanitize** (2026-09-22):
      the pack contract's `gold_rule` field carried one author's game
      term into the engine, and the sample-world value was that game's
      canon line. The field is now `creed` everywhere - contract
      (`world.py`), loader, inspect, maplab, spark prompt, API, weave
      tagline, web labels, CSS class, docs, fixtures - read through one
      owner (`creed_from`) so `gold_rule` survives as a read-fallback:
      packs written before the rename keep their line, and maplab
      writes them back as `creed` on the next save. Sample-world's
      value is now engine-neutral ("Walk gently; the town remembers.")
      across `world.json`, `logbok.md`, and `world-tree.md`. Added
      `test_creed_reads_the_legacy_field_name` pinning the alias, and
      the local canon-strings guard now bans the old line and term
      (list never ships - audit stays local-only by design). Gates:
      ruff clean; pytest 427 passed / 1 skipped (2 known
      model-dependent env failures); public-surface clean (377).

- [x] **World-creation guide: interview to playable HTML** (2026-09-22):
      drove `norns chat` end to end against the bundled Spark as a
      first-time author would - 15 prompts, exit 0, a valid pack in
      25 seconds. Both gated fallbacks captured verbatim (theme kept
      the scaffold's colors; the map proposal failed its hard
      validation gate twice and the proven layout held). Extended the
      map through `norns build-map` from a run-length segments file
      (+1 row, unforced - validation gated the write), re-validated
      ok, and wove a 10-line pool (`rumor:dusk`, `rumor:dawn`,
      `letter`, `forge`) into a 37.9 KB single-file HTML. Wrote
      `docs/guides/world-creation.md` from that capture: the full
      prompt sequence, what blank keeps, the fallback messages, the
      segments format, cleanup, troubleshooting - linked from
      `GETTING_STARTED.md` and the `AGENTS.md` references. Gates:
      ruff clean; pytest 425 passed / 2 skipped (2 known
      model-dependent env failures); public-surface clean (377).

- [x] **Bundled fleet complete: Vision tenant on :8085** (2026-09-22):
      docs promised a 4-model fleet; the image carried 3 — SmolVLM2 was
      never bundled (the docs-vs-reality gap). Added
      `ggml-org/SmolVLM2-500M-Video-Instruct` Q8_0 (417 MB) + its mmproj
      (104 MB) — SmolVLM2's only official 500M checkpoint, API-verified
      URLs + size guards, one image layer per model so editing one fetch
      can't re-fetch the fleet, and a build-time `--mmproj` assertion so
      a multimodal-less llama-server can never ship. `start-bundled.sh`
      launches vision on :8085 (health loop now 8083–8086);
      `VEFR_VISION_URL` baked into the image + compose/quadlet parity.
      The Interface Translator's default moved :8085 → :8087 — its own
      stated invariant is "never shares a default port with another
      conceptual service", and vision is now :8085's tenant (its docstring
      records the move). README/guide size claims corrected to the real
      546 MB. Verified local E2E: image in → description out on :8085,
      four brains + engine green; ruff clean; pytest 425 passed /
      2 skipped / 2 known model-dependent env failures; public-surface
      clean.

- [x] **NPC seed fallback survives the fail-closed translation** (2026-09-22):
      with the brain down, `POST /api/npc` returned a 404 leaking
      `[Errno111] Connection refused` instead of the canon seed line the
      contract promises (`npc.py`: "If the model is unreachable, a seed
      line speaks instead"). Cause: `_completion` translates httpx failures
      into `GeneratorUnavailable`/`GeneratorFailed`, but `generate_line`'s
      except tuple only caught raw `httpx` errors — the old test injected
      the error *below* that translation seam, so it stayed green while
      live runs broke. Surfaced by the WP2 Meera (brain-down) drill. Fix:
      catch both translated errors in `generate_line` + a regression test
      pinned at the production seam. Verified live: world/journal → 200
      with brains dead, npc → 200 `source:"seed"`; ruff clean; pytest
      425 passed / 2 skipped / 2 known model-dependent env failures.

- [x] **Container runs as root: bind mounts writable again** (2026-09-22):
      the non-root `USER vefr` (uid 999) could not write host-owned bind
      mounts under rootless engines — host uid 1000 maps to container uid 0,
      so the mount appears `root:root 755` and uid 999 gets EACCES. Observed
      live on the deployed quadlet: `POST /api/rumor` → 500
      `PermissionError: /app/data/journal.tmp`. Removed `USER`/`useradd`
      from the Containerfile; an in-file comment records why and forbids
      re-adding `USER` without solving bind-mount ownership. Under rootless
      engines container root *is* the unprivileged invoking user, so no real
      privilege is gained or lost; the named-volume compose flow was never
      affected. Verified: rootless docker + `:Z` bind write OK; ruff clean;
      public-surface clean; pytest 425 passed with the one known
      model-dependent env failure.
- [x] **Bundled-brain image build fixed + E2E verified** (2026-09-22,
      `a895898`): llama.cpp b5530 is now built from source inside the
      Containerfile (pre-built Linux release binaries are no longer
      published; static libs + `libgomp1` in the final image), and the three
      model URLs were corrected to API-verified paths with build-time size
      guards so an error page can never pass as a model — spark Qwen3-0.6B
      (`:8083`), storyteller Qwen3-1.7B (`:8084`), embeddings bge-m3
      (`:8086`), 2.0 GB baked. `docker compose up` now yields a playable
      game with no external LLM. Proven end-to-end: all three brain ports
      come up and `POST /api/rumor` returns a RumorCard generated by the
      bundled Qwen3-1.7B on CPU.
- [x] **Sample-world CC0 art swap** (2026-09-21): replaced the bundled
      non-redistributable tileset (1,131 PNGs) in `worlds/sample-world/assets/`
      with Kenney CC0 tiles under `assets/kenney/`; corrected `LICENSE` and
      `THIRD_PARTY_NOTICES.md`, which had mislabeled that art as CC0. The demo
      town renders its map in code, so gameplay is unaffected (`norns validate`
      green; `ruff` clean).
- [x] **Fleet Storyteller role + benchmark** (2026-09-14,
      `ab1695c`): the fleet storyteller capability — an anti-agentic
      narrator. `src/vefr/narrate.py` receives an authoritative
      action result plus bounded context and returns prose only (no
      tools, no mutation, no canon invention); fail-closed
      (`StorytellerUnavailable` / `StorytellerFailed`). Template
      as data in `templates/storyteller/narrate.json`
      (storyteller-narrate-v1: authority > template > lore >
      prose precedence, ambiguity preserved, player agency
      preserved). New CLI `vefr-story` (--json, --fixture, --model,
      --endpoint). Benchmark in `bench/storyteller/`: 25
      single-turn cases + 5 multi-turn sequences with hard
      must/must_all/must_not gates, non-contradiction continuity,
      and a replay mode. Winners (CPU llama.cpp):
      `smollm3-3b-q4` 25/25 gate, 5/5 sequences, 100%
      continuity, 11.4 tok/s (retained as storyteller head);
      `ministral-3-3b-q4` equivalent at 11.3 tok/s.
- [x] **Interface Translator + benchmark** (2026-09-13/14,
      `175d771` + `772677b`): `src/vefr/interface.py` — a tiny
      strict-intent brain mapping natural language to the engine's
      canonical action vocabulary (attack, console, hurl, strike,
      observe, speak, move) via strict json_schema + pydantic
      validation; deterministic clarification on missing args,
      fail-closed everywhere, no world mutation. Template as data
      in `templates/interface/intent.json`. Benchmark in
      `bench/interface/`: 29 deterministic cases; smaller models
      (qwen2.5-1.5b, qwen3.5-0.8b) fail the safety gate on unsafe
      false-positives; `qwen3.5-9b-mtp` wins (100% schema-valid,
      strongest safe-rate) as the reference head.
- [x] **Lorekeeper slice: `vefr-lore` add/ask** (2026-09-13,
      `f0d6612`): `src/vefr/lore_shell.py` — structured durable
      truth (`facts.jsonl` authoritative, `index/` derived),
      bge-m3 embed client via `VEFR_EMBED_URL`, pure-Python cosine
      retrieval, fail-soft on embed outage. No generative path.
- [x] **Small Model Finals + qualifier round, 2026-09 bench** (2026-09-13,
      bench/finals commits + local `bench/reports/` evidence): two
      skimmable rounds of the small-model bench campaign, plus the
      qualifier campaign that followed.
      (1) **Quick finals** (`bench/finals/DECISION-PACKET.md`,
      CPU-only, Q4_K_M): *Worlds* default = **Qwen3 1.7B**
      (6 PASS/8 PARTIAL vs LFM2.5-2.6B's 4/10), fallback LFM2.5;
      *VEFR* default = **Phi-4-mini** provisional (11/12 at 3x the
      speed of Ministral-3-3B's 12/12), fallback Ministral 3 3B.
      (2) **Qualifier campaign, suite 0.4.1** (`bench/reports/
      QUALIFIER-TLDR-2026-09-13.md`): 27 models x 53 tasks, every
      run now completes (the stuck runs were three harness bugs,
      zero model faults); backend is observed per run, not assumed;
      all latencies contended (resident 27B holds the VRAM) and
      never comparable to historical idle numbers. Standings
      (pass%): top = qwen3-1.7b 76, lfm2.5-2.6b 70,
      ministral-3-3b 68, falcon3-3b 66; weak = gemma3-1b 42,
      qwen3.5-0.8b/-2b 30/28. Honesty notes carried forward:
      phi-4-mini 64.2% here differs from its historical 100/100
      (different production-path set), and legacy backend
      provenance is UNKNOWN. Raw per-run evidence in
      `bench/runs/` (`index.json` is canonical).
- [x] **The Foyer sits in the house's own column** (2026-09-15): the
      launcher used to stretch full-bleed edge to edge while every
      other room sits in a centered ~680px readable column, and the
      first-walk rail (pinned top-right of the room) hovered over the
      foyer's right edge. The Foyer now keeps the same centered
      column as the Desk and the boiler room
      (`max-width: min(680px, calc(100vw - 32px))`, auto margins), so
      the walk rail clears the cards on desktop and the landing reads
      like the rest of the house.
- [x] **The Foyer — a launcher landing, the door you step through
      first** (2026-09-15): the studio now opens onto The Foyer, built
      like a game launcher: the project on the table (the real current
      world from `/api/world`, with act, phases, and an "enter the
      house" door into the Desk), the pantry (every real pack from
      `/api/builder/worlds`, honestly marked "in the pantry — ask the
      keeper to set VEFR_WORLD" since the engine is bound to one world
      per running house; no fake switching), what the house remembers
      (kept lately from the real vault, starred lately from the real
      journal, spoken lately from the folio threads and watch
      whispers), and quick options at the mantel that mirror the
      boiler room's contracts (hearth sound and motion via
      `VEFR_PREFS`, walk again + sheet via the first walk, boiler room
      door). Every panel fetches real endpoints with honest
      loading/empty states; nothing is invented. The Foyer is the
      first placard and the default landing route (a `#screen` hash
      still wins).
- [x] **The walk walks you — after each step, onwards to the next
      room** (2026-09-15): the housewarming used to stall at the
      first popup because the folio (bell and faces open it) covered
      the shelf and nothing guided you onward. Now each walk step
      knows its room; when a step truly completes, Ratatoskr tugs
      your sleeve and walks you to the next step's room — the folio
      steps wait until you close the folio, then set off, the rest
      move after a short beat, always with a ferry note. The shelf
      (and any room, including the Foyer) also shows a "walk me to
      {Room} →" button for the current step, hidden when you're
      already there. The step still only completes when the real
      action fires — the walk guides, never invents progress.
- [x] **The workshop becomes rooms: full scene frame, the
      household, and the keepsake Hall** (2026-09-15): the UI's
      chrome is gone - the shell is now a room scene with a hanging
      sign, a low shelf of ≥44px carved placards, a candle lantern
      for connection (lit when the storyteller is reachable, cold
      with a plain sentence when not), a world-phase candlelight
      tint, and the mood-note whisper. Nine screens: the seven rooms
      plus The Hall (real `/api/starred` + vault + journal stars) and
      plain Settings. The household lives here - one engine, many
      faces: The Storyteller (Desk), The Cartographer (Map),
      The Keeper of Faces (Folks), The Hoard-Keeper (Vault),
      Urðr (Chronicle), The Rune-Carver (Casting), Skuld (Archives),
      Ratatoskr (Hall). Every room has a "tended by" line and a
      speaking folio wired to `/api/builder/chat` with per-resident
      role templates (history owned by the page, `{message, history}
      → {reply}`), plus the Storyteller bell on the Desk. Squirrel
      ferry language for loading; motion off by default; all
      interactive targets back to ≥44px (the 40px/32px regressions
      are fixed). Engine stays story-agnostic; interiors carried
      forward from the warm pass. Reference provenance in
      `design/UI-REFERENCES.md` (RPGUI zlib, A Dark Room MPL-2.0,
      Twine/SugarCube per-theme, gameuidatabase.com taste).
- [x] **Rooms become benches: warmth, real builders, and rooms that
      use the screen** (2026-09-15): a second pass on the room scene -
      hearth glow, candle flicker (dead under `motion=off`), warmer
      wood, parchment folio, wax-seal mark, per-room ambience lines,
      and Ratatoskr's ferry note when the squirrel acts. The Map Room
      becomes a survey bench: per-region survey readouts (dimensions +
      ground census read off the real map), every mark a ≥44px door
      into the folio ("what is 'g' in town?"), a "deepen a landmark"
      tool wired to `/api/builder/enhance/map`, and a real pack-check
      (`/api/builder/validate`). The Vault becomes a forge bench:
      "ask the forge" (real model roll), shape the draft by hand on
      the anvil, keep it into the vault (`POST /api/vault`, new
      `VEFR_API.vaultKeep`), or deepen a kept thing
      (`/api/builder/enhance/item`); model-less failure is honest
      ("the forge is cold"), not a red error. Settings is no longer
      a plain hall: the boiler room has its own smith, Völundr, with
      the same folio chat as every room and role templates tuned to
      the studio itself (which reading mode, walking the motion
      setting, setting the room up for an easier day). Layout fixes: rooms span
      the full screen with centered readable columns (Chronicle,
      Archives, Hall, Map, Vault, Casting, Folks); Settings becomes a
      responsive grid (was a scrunched 580px column); deep Archives
      levels are readable (10-11px mono → 12-12.5px) with the raw
      truth contained; loading/empty states center everywhere (the
      Chronicle squirrel no longer veers left). Settings now drives
      `window.VEFR_PREFS.set(...)` - prefs.js is the one canonical
      owner of `data-prefs` tokens, so the motion-off a11y floor
      actually works in the workshop (the old `data-motion` attribute
      the foundation ignored is gone).
- [x] **The Map Room gains the drawing table - a map maker with no
      markdown** (2026-09-15): a storyteller doesn't need to know
      glyphs to make a map. The table reads the pack's real legend
      into labeled ink pots ("solid", "open ground", "marked",
      "sanctuary" - derived from the pack's own solid/deco/
      sanctuary_tiles data, never invented), a paintable 44px-cell
      grid with a proper roving-keyboard grid surface (arrows move,
      Enter inks), a live ink-line census, and three honest actions:
      "reset the ink" restores the pack's ground; "sketch new land"
      calls the new `/api/builder/map/propose` route (the same
      model-drafted, `maplab.validate`-gated run-length pipeline as
      the `norns chat` interview - proposal only, never writes to
      the pack, honest message without a model); "keep this sketch"
      posts the sketch as a real vault keepsake item (kind
      "sketch"). Drafts persist per world+region in localStorage so
      the table remembers your ink between visits, and "ask the
      Cartographer about it" prefills the folio. Two new tests
      (`tests/test_map_propose.py`) assert the route returns a
      validated grid and never mutates the pack, plus the honest
      no-model path. New public route `POST /api/builder/map/propose`
      (engine surface, flagged per Ask-first).
- [x] **The Housewarming — a first walk, taught by doing, and a
      broadsheet that stays** (2026-09-15): the first time the
      studio opens with no walk on record, Ratatoskr pins a short
      note under the sign. Five steps, one real action each, in five
      rooms: ring the bell, press the ground once, press a leaf,
      open a face, look out the window. Each step completes only
      when the real button truly fires (the same event hooks as the
      keeps and squeaks) — nothing is invented, no fake progress.
      Progress persists in `vefr.walk`; skipping is one press;
      "walk the house again" and "open the sheet" sit under
      Settings so both stay callable any time after setup. The
      tucked-in extra is a broadsheet — "How to read this house" —
      one line per room plus the three rules of the house, as a
      real dialog (focus-in, Escape closes, focus returns). The
      walk is model-agnostic on purpose: it works whether or not a
      brain is attached (the bell answers however the lantern
      honestly does). A11y held: real list/dialog semantics,
      ≥44px targets, aria-live step announcements, zero motion,
      plain English only. Verified 412 passed, 2 skipped.
- [x] **The household keeps, invites, listens, and sounds only when
      asked** (2026-09-15): the studio's ten wants, all landed.
      Keepsakes sit in the rooms: sketches kept from the table are
      pinned under it, every vault object shows its kind, the Folks
      grow by hand. "Invite a new face" (new public route
      `POST /api/builder/face/roll`, flagged per Ask-first): the
      model drafts name/role/seed through a schema-constrained
      pipeline, the engine places them with the interview's own
      deterministic rule (`_pick_tile` - reachable, unclaimed, dry),
      and keeping the editable card vaults a real `kind: "face"`
      item - the household grows, never invented. "Check the ground"
      (new public route `POST /api/builder/map/check`, deterministic
      - flagged): the draft grid is run through the real
      `maplab.validate` gate, surfaced honestly. The drawing table
      gains a fill (flood of one mark), an undo (40-step), and
      drag-to-paint. The studio listens: while visible it reads
      `/api/trace` every 10s and the Hall's fire keeps watch over
      true engine events as quiet whispers (each paired with a squeak
      when sound is on). Sound, off by default, lives in the prefs
      contract (`sound.effects/ambience/speech`, deep-merged by
      prefs.js) with one Settings row; every sound pairs with a
      visible event. The folio remembers per resident (localStorage)
      with a "forget this talk" control, and every reply can become
      a keepsake in one click ("keep this note" → vault
      `kind: "note"`) - the reply now renders live too. The Folks
      are living cards reading real `at/near/seeds` + wiki lines,
      each a door into the folio. The town sits behind glass in the
      Hall: a framed window rendering the real pack map at its real
      phase, hero lit gold, speakers lit teal, sanctuary rimmed.
      Five new tests (`tests/test_map_check.py`,
      `tests/test_face_roll.py`) cover the deterministic gate and
      the face pipeline incl. the honest no-model path; verified
      412 passed, 2 skipped. Full a11y contract held: ≥44px targets,
      luminance focus, motion off by default, plain English, sound
      paired + off.
- [x] **Container/registry: GHCR publication, .containerignore,
      compose split** (2026-09-13): VEFR images now publish to
      `ghcr.io/rylee-bee/vefr` automatically from `main` after CI
      passes. New `.github/workflows/publish-image.yml` follows the
      Worlds pattern: `workflow_run` gate on `ci` success, SHA +
      `latest` tags, OCI labels (title, description, source, license,
      revision, created), Docker Buildx, provenance disabled. New
      `.containerignore` excludes `.git`, venvs, `__pycache__`,
      `data/`, `bench/`, `experiments/`, `storyteller_packs/`,
      `.github/`, `.project/`, and env/deploy config from the build
      context. `compose.yml` restructured as portable base (pulls
      published GHCR image, `pull_policy: always`); new
      `compose.dev.yaml` for local source-tree builds
      (`podman compose -f compose.yaml -f compose.dev.yaml up --build`).
      `compose.yml` exposes `VEFR_IMAGE` env var for pinning to a
      known-good `:sha-...` tag for rollback. Health endpoint
      (`GET /api/health`) already existed; documented that it does not
      require a model — engine boots and serves UI without one.
      README updated: container quickstart references GHCR, new
      "Container images" / "Model configuration" / "Health and
      degraded state" / "Compose" sections. Public-surface guard
      updated to skip `bench/` (internal benchmark research, not
      public engine surface). Verified: `ruff check src tests scripts`
      clean; `pytest -q` 346 passed, 2 skipped; `norns validate
      --pack worlds/sample-world` ok; `check_public_surface.py` clean
      (1362 tracked files scanned).

- [x] **Public-release hardening pass** (2026-09-13,
      public-release epoch): tree sanitized of environment-specific
      references; `docs/guides/archive/` handoffs and host-specific
      `.project/` evidence deleted; `src/vefr/cli.py`'s last private
      defaults (`VEFR_DEFAULT_DEPLOY_HOST`, `VEFR_DEFAULT_BACKUP_LOCATION`)
      set to `''` with the deploy wrapper's silent-default guard
      rewritten to match; `web/packaged.html` real IP generalized;
      `--init` template host generalized to `deploy-host`. Storyteller
      WIP preserved byte-for-byte. New `scripts/check_public_surface.py`
      + `tests/test_public_surface.py` (17 tests) tripwire on
      RFC1918, homelab hostnames, private Gitea domains, the operator's
      SSH user, private paths, and obvious credential shapes. New
      GitHub Actions: `ci.yml` (ruff + blocking pytest with
      Storyteller WIP `--ignore`'d + informational WIP step +
      sample-world validate + public-surface guard), `secret-scan.yml`
      (gitleaks working-tree scan with `[allowlist]` for the test
      fixtures), `security.yml` (manual re-run). New `SECURITY.md`,
      `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/`
      (`bug_report.yml`, `feature_request.yml`), `.github/pull_request_template.md`.
      Branch protection on `main`: require PR, require `ci` +
      `secret-scan`, block force-push, block deletion, conversation
      resolution. Secret scanning + push protection + Dependabot
      alerts + Dependabot security updates enabled on the public
      repo. CodeQL default-setup enabled across actions / js / py.
      PR #2 merged at `37ef35e`. Repo flipped to public. Final gates:
      `uv run --group test ruff check src tests scripts` all checks
      passed; `python3 scripts/check_public_surface.py` clean (1345
      tracked files scanned); `uv run --group test pytest
      tests/test_public_surface.py -q` 17 passed; `uv run --group test
      norns validate --pack worlds/sample-world` ok; `uv run
      --group test pytest -q --ignore=tests/test_npc_action.py
      --ignore=tests/test_storyteller_benchmark.py` 315 passed, 0
      failed; gitleaks 230 commits scanned, no leaks found.

- [x] **License + project identity + Actions hardening** (2026-09-13,
      same public-release epoch): engine source/tooling relicensed
      from MIT to MPL-2.0 (file-level copyleft preserves improvements
      without forcing downstream applications to be MPL); worlds/
      sample-world/ (Emberfield) dedicated to the public domain under
      CC0 1.0; worlds/lore/<flavor>/ unchanged at CC BY-SA 4.0; web
      fonts retain SIL OFL 1.1 with attribution in
      `web/fonts/README.md`. New `TRADEMARKS.md` (descriptive, not a
      legal grant — "vefr" is not a registered trademark; forks
      welcome under the license, please use a distinct name for
      substantially modified versions); new `THIRD_PARTY_NOTICES.md`
      (FastAPI/Uvicorn/httpx BSD-3, Pydantic MIT, fonts SIL OFL 1.1).
      Actions hardening: third-party actions pinned to commit SHAs
      (`actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`
      = v4.2.2; `astral-sh/setup-uv@0c5e2b8115b80b4c7c5ddf6ffdd634974642d182`
      = v5.4.1) with version comment for human-readable reference.
      New `.github/CODEOWNERS` expressing "sensitive paths require
      maintainer review" (informational; branch protection enforces
      the rule). Verified gates: `uv run --group test ruff check src
      tests scripts` all checks passed; `python3
      scripts/check_public_surface.py` clean (1345 tracked files
      scanned); `uv run --group test pytest
      tests/test_public_surface.py -q` 17 passed; `uv run --group
      test pytest -q --ignore=tests/test_npc_action.py
      --ignore=tests/test_storyteller_benchmark.py` 315 passed, 0
      failed. The historical "license split: engine MIT" entry
      above remains in the ledger as the original decision;
      relicense landed via `LICENSE` file change, not by rewriting
      history.

- [x] **Truth-repair: canonical checkout documented, stale handoffs
      archived, CI added** (2026-09-07, truth-repair epoch): two
      checkouts on the dev box were documented in AGENTS.md with a
      do-not-commit-the-WIP rule for the kilo2 lane. Dated session
      snapshots (`session-handoff.md` 2026-08-31, two
      `handoff-snapshot-*` 2026-09-01 files) moved under
      `docs/guides/archive/` with a README marking them non-current;
      `deploy.md`'s reference repointed to the current `handoff.md`.
      The hard-coded pytest count in AGENTS.md was removed (it had
      drifted 200 → 307 → reality); the gate comment now says paste
      your own run's summary line and find verified counts in this
      ledger. New `.gitea/workflows/validate.yml` (first CI on this
      repo): ruff + pytest on PRs and main pushes, plus a
      pack-validation job that runs `norns validate` over every
      `worlds/*/world.json` pack. Verified: `uv run --group test
      pytest -q` → 296 passed, 2 skipped, 1 warning (0:03:35);
      `norns validate --pack worlds/sample-world` → ok. The
      machine-specific canonical-checkout path documented here was
      later corrected in the refinement pass below — the
      authoritative phrasing now lives in AGENTS.md "Active checkout
      and Storyteller WIP".
- [x] **Refinement pass: honest orientation, source-control truth,
      Trusted Translation pointer** (2026-09-12, refinement epoch):
      AGENTS.md "Canonical checkout" replaced with "Active checkout
      and Storyteller WIP" using portable language ("the checkout
      registered for VEFR in `agent-sync`") instead of the
      machine-specific path that no longer exists on the active
      checkout; the Gitea PR/tea claim corrected to GitHub
      `Rylee-Bee/vefr`; `.project/CURRENT.md` rewritten to lead with
      *phase* (refinement pass) and durable pointers, with SHA
      surfaced as `git log -1` rather than mirrored; `README.md`
      gains a concise pointer to Play-Nice's
      [Trusted Translation](https://github.com/Rylee-Bee/play-nice-contracts/blob/main/docs/principles/trusted-translation.md)
      philosophy (link, not copy); `GETTING_STARTED.md` Gitea-style
      `rylee/vefr` repo reference replaced with the public GitHub
      URL. CLI help subcommand counts (`norns` Four→Nine,
      `ratatoskr` Three→Six) are deferred — they live in
      `src/vefr/cli.py`, which is part of the protected Storyteller
      WIP; the Storyteller team should land them alongside their
      work. Play-Nice adoption pin remained
      `0cee0652fb6f13c440b1fd9cc5d78fd87cdca8ad` (no contract
      semantics changed in the new Play-Nice revision; only
      documentation did). Storyteller WIP (5 modified + 20 untracked
      files) untouched; nothing in the protected set was staged.
      Verified: `uv run --group test ruff check src tests` → All
      checks passed; `uv run --group test pytest -q
      --ignore=tests/test_npc_action.py
      --ignore=tests/test_storyteller_benchmark.py` → 298 passed
      in 266.61s; `norns validate --pack worlds/sample-world` → ok.
- [x] **Spark: a resident small brain, productionized**
      (2026-09-06, this session): the benchmark settled the model
      selection - Phi-4-mini-instruct Q4_K_M (spark-quality, 100/100
      VEFR functional score, ~1.9 GiB resident CPU-only) with
      Qwen3.5-0.8B Q8_0 (spark-tiny, 80.3/100, ~1.05 GiB) as the
      low-memory profile. `src/vefr/spark.py` builds Spark's context
      in layers from the spark contract, the loaded pack, the
      speaker's voice file, and supplied runtime state; strict
      json_schema responses validate before anything applies
      (`state_edit_check` fails closed). `ratatoskr spark
      install/status/smoke` acquires the pinned, hash-verified models,
      runs the quadlet service (loopback 8082, CPU-only, llama.cpp),
      wires VEFR_SPARK_URL, and proves the integrated path through the
      live /api/spark routes. Escalation to K2 is both a deterministic
      gate and a measured model capability (100/100). K2's
      configuration is untouched. See `docs/guides/spark.md`.

- [x] **the Figma design system integrated** (2026-09-06,
      feat/figma-theme-integration): the condensed design docs
      (design/) plus the full mockup export (design/mockups/, 36
      frames) are the reference; `web/vefr-theme.css` is the code
      home - every Figma primitive, the three semantic contrast
      themes (Warm & Easy / Bright & Clear / Nothing Hides) as
      `[data-theme]` blocks, spacing/radius/sizing scales, and the
      legacy `--bg`/`--card`/... aliases that point at them so every
      pre-existing rule themes itself. prefs.js derives `data-theme`
      from the contrast pref (one control, both vocabularies); the
      contrast option labels now carry the Figma theme names. Shell:
      the header is the 72px top bar (brand leaf, live world/act
      breadcrumbs from `/api/world`, engine StatusIndicator chip,
      zone pills) per design/HANDOFF.md; tabs/zones are ModeTab
      pills; primary actions are teal-fill `.btn-primary`; empty and
      error states got the vefr-states treatment; panel titles are
      the gold serif headers. Inter (variable woff2, SIL OFL) joined
      the self-hosted fonts for UI chrome; reading text stays on the
      prefs-driven fonts. packaged.html's inline palette realigned to
      the same primitives. Verified: ruff clean; pytest 307 passed
      with the only failures pre-existing on the base commit (a doc
      leak caught by test_pack_neutrality + untracked npc_action WIP);
      headless-browser pass at 1440/900px across all three themes,
      zones, prefs dialog, and a whisper round-trip with zero console
      errors and zero failed requests. Map: design/INTEGRATION.md.

- [x] **the engine's identity locked in** (2026-08-31, this session):
      Norse-coded + Hero's Journey as story structure + lore packs as
      data. The journey/rune anchors are in `src/vefr/journey.py`
      (whispers->Fehu, doubts->Thurisaz, feared->Kenaz, awed->Sowilo).
      Three lore packs ship: `worlds/lore/norse/` (wandering poets),
      `worlds/lore/historical-event/` (what the record couldn't hold),
      `worlds/lore/norse-runes/` (the rune-cast flavor with all 24
      Elder Futhark rune poems). Every lore pack is CC BY-SA 4.0 +
      per-pack LICENSE.md with sources. The engine reads the
      textures/names/questions; the author reads the prompt.md
      and copies it into any LLM.

- [x] **v0.1 - the skeleton**: FastAPI + ollama structured output,
      parchment UI, quadlet deploy on the deploy host
- [x] **v0.2 - the ledger**: collected whispers become the engine's
      voice anchors (Rylee curates; the cadence compounds)
- [x] **v0.3 - the forge & the vault**: items with three bonds -
      assigned (church-blue), attuned (gold, rare on purpose), cold
      (grey). Offer your hand. Kept items persist on the deploy host.
- [x] **v0.4 - the bell**: the bog at night, one ring per visit, the
      mother's chore-note in her voice - headed "For you."
- [x] **the canon**: the archive, the hero, the bell, the
      church, the dictionary, the laughing room, the labyrinth, the
      monsters, Bog & Bell style, the world's creed
- [x] **the founding myth**: the Keeper's empty throne, the Weaver's
      scorn, the Untongued - the Conserved Word vs the Fen Verse
- [x] **v1.0 - first tiles**: MAP.md became a walkable grid; the hero
      leaves the bookshop; the tower's sightlines became geometry you
      can feel
- [x] **v2.0 - the bones and the flesh**: engine/world split. All
      canon moved into the author's private story pack (logbok, ledger, map,
      voices, world.json); the engine reads everything through the
      pack loader. The town renderer is world-driven (/api/world).
      MIT on the bones; the flesh stays private. Someday: hand
      someone the bones, they grow their own story.
- [x] **the hearth**: the old soldier and the housekeeper come to the story -
      the soldier's house in the church's own shadow, one standing
      gold window, a sanctuary threshold the watch never crosses,
      plain speech and corn-bread. The the sea-folk join the canon: the
      Weaver's people, the name-keepers, seen once at the water's
      edge. And one law from the sealed layer: the game never holds
      her under.

- [x] **v1.2 - items in the world**: the vault became the game's
      inventory (carried item in the HUD); attunement on screen
      (gold ring, gold only when the world is kind); the reed
      crossing's water level became a choice (high in feared); the
      the sea-figure sighting at the water's edge (awed, gold, once).
      And the town grew 30x20 -> 40x28: the moot hall (its keeper
      keeps the roll), Katla's tavern (rumors are born there),
      Sigga's store (her ledger is not the parish ledger) - all
      with doors, verified reachable by flood-fill.
- [x] **the storytelling layer named**: style.py is saga.py -
      for the goddess who keeps stories at Sokkvabekk. Bragi
      composes the prompts; Idunn keeps the ledger that renews
      the voice.
- [x] **the rpg-js question**: answered 2026-08-30 - the custom
      renderer stays canonical. RPG-JS stays admired (MIT, a fine
      tool), and the door remains open through the pack contract:
      any future render target reads the same /api/world.
- [x] **`ratatoskr`/`norns` - the world-tree tooling**: two CLI
      entry points, story-agnostic. `ratatoskr` is the squirrel who
      ferries messages up and down Yggdrasil - skipa, test, weave
      (the file packager), and ferry (deploy / carry to NAS / fetch
      from Gitea). `norns` are the weavers - chat, validate,
      build-map, verify. `maplab.py` is the one geometry validator
      shared by both CLIs and the tests.
- [x] **the full rename, 2026-08-31**: this repo and package are
      `vefr` now (renamed several times before landing here) - the
      umbrella under which `ratatoskr` and `norns` both live as
      commands. Env vars
      (`VEFR_HOME`, `VEFR_WORLD`, `VEFR_MODEL`, `VEFR_VAULT`,
      `VEFR_KEEP_ALIVE`), and every hardcoded story reference in the
      engine (the API title, the health check's service name, the
      shared rumor system prompt, `world_name()`'s private-pack
      special-case) are gone.
      The story itself (the author's pack, `STYLE.md` included) moved
      to its own private repo, verified
      byte-identical before the move; the engine repo's history was
      then rewritten (`git filter-repo`) so no trace of it remains in
      any commit.
- [x] **the bones boot alone**: `worlds/sample-world/` (Emberfield) -
      a demonstration pack with zero story content, proven by
      physically removing the author's own pack and running the suite
      green. The engine works with any pack, or none beyond the
      sample.
- [x] **license split**: engine MIT (`src/`, `web/`, `tests/`,
      `deploy/`, `Containerfile`, `worlds/sample-world/`);
      the author's own story pack is all rights reserved, not
      covered by the engine's MIT - see that pack's own LICENSE.
- [x] **`norns chat`**: the conversational world-builder. Interviews
      canon, theme colors, phases, bonds, and one speaker's voice
      against the local ollama, starting from `worlds/sample-world/`
      so geometry can't break. The interview's flow is deterministic
      Python; the model only ever fills in prose or a hex color
      inside a schema it can't escape - `maplab.validate()` runs
      after every write. Fixed alongside it: every schema-constrained
      call in the engine (`generator`, `forge`, `bell`, `npc`, `chat`)
      now sends `"think": false` - the thinking model was dumping its
      chain-of-thought into the one string field a JSON schema left
      it, which would have shown up as narration inside rumors, item
      names, and the bell's letter.

- [x] **the session journal + story export** (2026-08-31): the
      vault was the only thing that persisted; now `journal.py` keeps
      a timestamped record of every rumor heard, line spoken, item
      kept, and the bell's letter - same atomic tmp+replace write as
      the vault, `VEFR_JOURNAL` to move it. `main.py`'s existing
      routes log after each generation, so the record is a byproduct
      of play, not a chore. `export.py` weaves the pack's title +
      logbok.md + the journal + the vault into one markdown document
      by deterministic templating (never a model call: it must work
      with ollama cold and must match what actually happened). New
      routes `GET /api/journal`, `POST /api/journal/clear`,
      `GET /api/export`; a Journal tab in `web/` reads the timeline
      back and downloads the story as a `.md`. A model-polish pass
      over the export stays available as a v2.

- [x] **shared story state** (2026-08-31): the two phase rails were
      two variables. `web/state.js` is now the one client-side state
      (a plain object, a patch function, a list of
      subscribers; no framework), and both script scopes - the town
      renderer and the tabs - read and write it. Set the world's tone
      in Rumors and the town's rail, watch radius, water level and
      canvas follow; set it in Town and the rumors rail follows.
      Keeping an item reaches the town's HUD and its gold ring without
      a tab click, because the vault list the Vault tab draws and the
      item the hero carries are the same list. `/api/world` is fetched
      once for the page instead of once per view. Two smaller things
      fell out of it: the rumors rail was hardcoded to the author's own
      four phase names (a story leak in engine HTML - any other pack's
      rumors silently fell back to its first phase), so it is built
      from the pack like the town's always was; and the Vault tab now
      loads the kept list when you open it rather than only after a
      forge. Validated by executing `state.js`, `town.js` and
      index.html's inline script under a stubbed DOM in node -
      including strict mode, to catch the undeclared-variable class of
      runtime bug that no syntax checker sees.

- [x] **inference backend: ollama -> llama.cpp on the 6900XT** (2026-08-31).
      Wall time on the live `vefr` went from ~27.6s per rumor/bell
      to ~2-5s end-to-end (curl + SSH overhead included). Root cause
      of the old slowness: the ollama container on the deploy host was the
      correct `ollama/ollama:rocm` image, but `podman inspect ollama`
      showed `Devices=[]` - no `/dev/kfd` or `/dev/dri` passed
      through, so a dense 27B Qwen was running on CPU the whole time.
      Switched to llama.cpp's OpenAI-compatible
      `/v1/chat/completions` endpoint with `gpt-oss-20b-UD-Q4_K_XL`
      (Apache-2.0, MoE 3.6B active). All five generation modules
      (`generator`, `forge`, `bell`, `npc`, `chat`) now go through
      one helper, `generator._completion(payload)`, which decides
      backend from `VEFR_LLAMACPP_URL` (preferred) or `OLLAMA_URL`
      (fallback). JSON constraint is now `response_format.json_schema`
      with `strict: true`; reasoning control is
      `chat_template_kwargs.reasoning_effort=low` (gpt-oss has no
      `off` - low/medium/high only, llama.cpp maintainers confirmed).
      The helper is monkeypatched instead
      of the wire layer, so backend swaps stay test-clean. Two btrfs-
      on-Fedora-Atomic gotchas hit along the way (documented in
      `~/llama-server/run-gptoss.sh`): podman bind sources MUST go
      through the operator's real `$HOME` and not a `/home`
      symlink (the `/home` -> `/var/home` symlink confuses
      rootless-podman statfs on the btrfs subvol);
      `HSA_OVERRIDE_GFX_VERSION=10.3.0` is required
      for the 6900XT (RDNA2/gfx1030) since llama.cpp's compiled
      runtime only recognizes gfx900/1030/1100/1200. The deploy
      quadlet was updated in place.

- [x] **the always-array world loader + the visible engine**
      (2026-08-31). `load_world()` now returns a single canonical
      shape: top-level keys (title, phases, surface, logbok,
      ledger, voices, bonds, acts) and `acts` is ALWAYS a list.
      Two on-disk shapes are supported. Flat: worlds/<name>/
      world.json + voices/ + map.md (legacy packs still work).
      Acts: worlds/<name>/world.json (pack-level contract) +
      acts/<id>/world.json (act contract) + acts/<id>/<region>/
      (map.md, voices/, sprites/). The loader walks the tree
      and discovers voices/sprites by convention. maplab.load_pack
      and maplab.write_pack round-trip both shapes; chat.py
      writes a new pack in whichever shape the scaffold uses.
      `current_act(world)` and `current_town(world)` are the
      accessors; every consumer reads through them. The canary
      pack `sample-world/` is migrated to the acts shape. The
      `surface` field is now in the always-array payload so the
      web UI can branch on it in a follow-on PR. Every loader
      step is recorded to `data/weave.jsonl` (the weave log) and
      surfaced at `/api/weave`. The Builder tab gets a "What the
      engine sees" panel that shows the resolved world and
      packages a markdown handoff bundle for an AI-buddy
      debugging session - see `docs/guides/handoff.md` for the
      format. The canary pack validates
      identically before and after the migration.

- [x] **the kilo init** (2026-08-31): `AGENTS.md` (the repo's
      operating rules - bones/flesh contract, the boundaries table,
      the gate command, the known drift) and `.kilo/kilo.jsonc`
      (project config: instructions = AGENTS.md only, uv/pytest/git
      allow-list, `data/**` + `uv.lock` edit-deny) are now tracked.
      Rylee's profile + shared agent rules load from the global
      kilo config, so this repo's instructions list stays one entry.

- [x] **the handoff guide caught up** (2026-08-31):
      `docs/guides/session-handoff.md` refreshed to the kilo-init
      HEAD + the 171-test gate; all three "honest gaps" closed out
      with evidence (real pool weave landed, mem0 live again,
      `tests/test_web_packaged.py`); the next-move table repointed
      at the surface-UI continuation.
- [x] **the LAN left the source** (2026-08-31): `VEFR_GITEA_URL`,
      `VEFR_LIVE_URL`, `VEFR_DEFAULT_DEPLOY_HOST`, and
      `VEFR_DEFAULT_BACKUP_LOCATION` (host:/path) replace the
      hardcoded Gitea IP, the live-stack IP, and the SSH host
      aliases - the engine source now carries neutral localhost
      defaults and takes its identity from the environment. The
      scaffold README derives its engine link from the checkout's
      own `origin` at runtime. Runtime data, not repo data.

- [x] **the reading row** (2026-08-31, this session): the
      Reading & sound panel, opened from a 44px trigger in the
      title bar, slides up as a bottom-sheet on mobile and a
      centered dialog on desktop. Three columns named for the
      three Norns: **Urd** (recalled settings, reset, share-link),
      **Verdandi** (live controls - text size, line spacing,
      font, contrast, colorblind-safe palette, motion, focus
      ring, density), **Skuld** (live preview of how the page
      reads right now). English labels lead; Norse names ride
      visibly as a secondary line. The full contract:
      `window.VEFR_PREFS.{get,set,preview,reset,on,shareLink,
      applyFromUrl}`; persistence is localStorage under
      `vefr-prefs`; cross-device sync is a base64-encoded URL
      (`?prefs=...`) you copy via the **Deila** button. The
      stylesheet keys off a single `<html data-prefs="...">`
      attribute set on every set/preview, so adding a new
      preference is one CSS rule and one `[data-pref-key]`
      select. The always-layer's reading row is part of the
      gate. Self-hosted Atkinson Hyperlegible Next + OpenDyslexic
      woff2 tracked under `web/fonts/` (SIL OFL); until the
      binaries are downloaded the @font-face rules 404 silently
      and the body falls through to its system serif. See
      `docs/guides/identity-terms-glossary.md` for the terms
      the panel uses.
- [x] **companion resources surveyed** (2026-08-31): a full
      CC0/MIT tool survey (engines, renderers, map authoring,
      narrative tools, art editors, audio, dev workflow) kept as a
      local research note - gitignored, since the repo may publish
      one day. Durable decisions: (Kenney CC0 art shipping as pack
      data was reversed 2026-10-02: Rylee removed the Kenney sheets; we
      ship only art we made, attributed) ; Tiled (then
      LDtk) importers parked after the surface-UI work; rot.js
      algorithms get borrowed for mapgen when `norns chat` v2
      opens; frameworks skip (the custom renderer stays
      canonical); the ebook export stays a stdlib writer; idea
      credits for incompatible-but-borrowed sources live in
      README's Attribution section.

- [x] **the bones stop talking** (2026-08-31, this session):
      A1+A2+A3+A4 - the strip. Every user-visible string in the
      engine that named a specific pack's voice, place, or
      speaker (the mill / the bell / the tower / the bookshop /
      the bog / the ferryman / the roll-keeper / the wanderer / the sea-figure) is gone or
      replaced with engine-neutral prose. The engine paints
      nothing where a pack would speak - tabs show empty
      status until `/api/world` returns, the whisper button
      says `listening...` / `whispered` / `nothing came back`
      instead of `the mill turns / the mill is warm / the
      mill is silent`, the Skuld preview shows em-dashes
      where the pack's phase + speaker would live. Comment
      drift (canon names in `state.js` / `town.js` /
      `world.py` / `volumes.py` / `cli.py` / `main.py`) replaced
      with engine-neutral identifiers; the one load-bearing
      private-pack-name rename
      in `norns build-map`'s scaffold helper gets an
      explanatory comment so the history isn't lost. The
      `norns chat` builder's system prompt no longer names
      example NPCs from the author's canon. README's
      "bones and the flesh" section now carries a worked
      example: develop on vefr, write the game in
      the private story repo, ferry fetch to play. The bones
      stay empty until a pack mounts.

- [x] **the dev board** (2026-08-31, this session): the Dev zone's
      github-projects-style board - the pack's four generators
      (whispers / voices / forge / bell) as draggable cards in a
      file-tree chrome. Cards are drawn from the loaded pack
      (/api/world, shared fetch - one request per page); a column
      the pack cannot fill is seeded from a deterministic
      engine-neutral pool (Norse-coded names, no canon strings -
      the strip holds here too), so the board is never empty and
      never storyful. A fresh seed per browser persists in
      localStorage (`vefr-board-seed`), so a run is reproducible
      but never identical to the pack. Dragging a card between
      columns re-homes it and persists (`vefr-board-cards`), with
      an honest "moved" timestamp; a fresh boot loads the store
      instead of regenerating. The right rail (hidden until a card
      is selected) shows the column's real endpoint, request and
      response shapes, a "try it" button that calls the endpoint
      like the game's own buttons do (and says plainly when the
      engine does not answer), and a draft box reserved for
      `norns chat` wiring. The board boots lazily on its own tab
      - the Play path never asks for it - and `web/board.js` is
      machine-tested two ways: the vm contract harness
      (tests/fixtures/board_harness.mjs) and the full-DOM
      harness's tab tour, which now proves the board adds no
      second /api/world fetch. Packaged play files are untouched
      (the board is a served-UI Dev feature). Editing cards
      belongs to `norns chat`, not a textarea - navigation-only
      chrome on purpose.

- [x] **the shadcn layer** (2026-08-31, this session): the UI
      adopts shadcn/ui's design language as a token vocabulary +
      component anatomy - CSS custom properties only. No React, no
      Tailwind, no build step: the packaged single-file stays
      self-contained. The shadcn names (--background, --foreground,
      --card, --border, --ring, --primary, --radius...) are DERIVED
      tokens referencing the engine's own luminance-first palette,
      so the reading row's contrast/palette overrides flow through
      the entire new vocabulary unchanged - the focus ring became a
      token (--ring), replacing two long per-selector pref lists
      with one rule pair. Buttons, cards, and inputs collapsed from
      ~8 near-duplicate blocks each into one :is() anatomy (outline
      default, solid primary variant, 44px minimums, motion off);
      radii follow shadcn's scale (one base, sm/md/lg/xl derived).
      The board stylesheet rides the same tokens. The town canvas
      renderer stays custom (the rpg-js decision stands - this
      layer dresses the document UI, not the game canvas).

- [x] **the drag layer** (2026-08-31, this session): the board's
      pointer drag moved to vendored SortableJS 1.15.7 (MIT, 45KB,
      classic script, provenance in web/vendor/README.md) - native
      HTML5 DnD has no touch support, so the board was desktop-only
      before. Drops now keep their dropped position (the store syncs
      to the DOM order instead of re-rendering), the ghost/chosen
      states use the token vocabulary, and native DnD remains as the
      honest fallback when the vendor file is absent (the test
      sandbox, a packaged file without it). Keyboard users re-home
      cards without a pointer at all: the rail carries one button
      per column (current column disabled), every move announces
      through an aria-live status line. @dnd-kit/dom was evaluated
      first and rejected on evidence: v0.5.0 ships ESM-only (verified
      against the jsDelivr entrypoint), which would force an import
      map or bundler onto a no-build repo. Two real bugs caught by
      the vm harness on the way in: syncColumns originally resolved
      cards only from the target column's store array (a card
      dragged in from another column would have been silently
      dropped) and the move() rewrite had lost its render() call.

- [x] **the draft wires to the smith** (2026-08-31, this session):
      the board rail's draft box is live - it was shipped inert with
      an IOU and now keeps its promise. One thread per card, held by
      the page (the /api/builder/chat endpoint is stateless; the
      last 6 turns replay for context). Every turn carries the
      card's context - name, kind, column, current text - so the
      smith knows what the author is pointing at; the wire format
      keeps the composed message while the rail's log renders the
      short draft. The thread dies with the page: drafts are
      conversation, not lore (nothing is persisted to the pack).
      Offline, the turn comes back out of the thread and the rail
      says so plainly - the draft stays yours. The vm harness drives
      the full contract: context in the composed message, both turns
      logged, textarea cleared, honest failure leaving the thread
      empty.

- [x] **one shell, every zone** (2026-08-31, this session): the
      layout instability Rylee flagged - the page swapped between a
      narrow reading column (Play/World) and a wide workbench (Dev),
      and the World zone was a third unrelated body of bare lists -
      is gone. The shell is one width everywhere (min(80rem,
      100% - 2rem)); reading surfaces cap their own line length
      (46rem) because the short-line reading win belongs to the
      text column, not the page. The World pane now wears the same
      skeleton as the board: Characters / Relics as two columns of
      selectable cards (role=button, Enter/Space, aria-pressed,
      luminance ring) with the full record in a shared right rail.
      The pane vocabulary (board-container / board-column /
      board-cards / board-rail) is the app's shared skeleton;
      Play keeps its inline cards for now - they already show their
      whole content, and hiding it behind a selection would add
      reading load, not remove it.

- [x] **the reachable UI** (2026-08-31): header earns its title,
      9 flat tabs become 3 static zones (Play / World / Dev) with
      plain-English labels leading and Norse secondary, 44px+ targets,
      luminance-only active states, prefers-reduced-motion honored,
      keyboard focus-visible tokens, and the reading row (text size,
      line spacing, contrast, fonts) built on VEFR_PREFS.

- [x] **ratatoskr weave --pool** (2026-08-31): pre-generation pass
      during packaging inlines `window.VEFR_POOL` for offline play
      with per-combo spending tracked in localStorage and fallback to
      honest silence when spent.

- [x] **surface UI for `surface: "combat"` packs** (2026-08-31,
      `06eed41`): the web UI renders the surface. `web/index.html`
      gains the HP bar (`.hud-hp`, combat surface only), the
      phase-dependent encounter prompt (hidden in the whispers
      phase), the combat verb row posting to `/api/combat/action`
      with the response landing in the journal, and the
      `<body data-surface="...">` attribute set from the
      `/api/world` payload at load. HP is synthesized per-phase by
      `combat.hp_for_pack()`, so packs need no hp data of their
      own; plain/investigation surfaces hide the whole costume
      via CSS. Verified live on the deploy host (2026-09-01): `/api/world`
      serves `surface: combat` + `hp: {current: 4, max: 4,
      per_phase: {dusk: 3, dawn: 4}}`. The packaged half landed
      the same day (see the packaged-costume entry).

- [x] **audit 2026-09-01** (2026-09-01): 10 PR sequence resolving
      live scaffold NameError, pack contract verification (stefna_voice,
      voices dual convention, strike prompt), final story prose and
      pronoun stripping, AST shape-based neutrality guard, vefr renaming
      sweep across web globals/events, and test harness execution for
      the reading row controller.

- [x] **dev overlay & aspect inspector + engine maintenance bundle** (2026-09-01, this session):
      In-game development overlay & aspect inspector drawer with
      accessible 44px trigger, dark-mode styling, and keyboard shortcuts
      (` and F12), wired to `GET /api/builder/aspects`. Surfaces loaded pack
      aspects, active act structure, region metadata, speaker seed matrices,
      living rune cast, and recent trace events. Full DOM harness coverage
      and FastAPI route verification. Plus mechanical cleanup bundle:
      deduplicated journey attachment in `world.py` (L2), extracted shared
      `UndoBuffer` helper in `sessions.py` preserving living tree touch
      semantics across vault and journal (L3), populated speaker source on
      `NpcLine` (L4), resilient FastAPI title & static mount handling (M5),
      and robust `app_home()` fallback guards for unbundled installs (M6).

- [x] **contextual AI enhance** (2026-09-01, this session):
      Scoped structured generation calls tailored to the active screen
      and resource in authoring and dev views. Implemented `src/vefr/enhance.py`
      with strict JSON schemas for map/POI descriptions, speaker voice prompts &
      dialogue rules, and relic forge flavor/curses. Wired into FastAPI at
      `POST /api/builder/enhance/{map,voice,item}` and integrated into the
      Builder tab with accessible triggers and status reporting. Tested with
      dedicated test suite (`tests/test_enhance.py`).

- [x] **`ferry deploy` hardened as the single ship button** (2026-09-01,
      this session). `ratatoskr ferry deploy` now owns the deploy
      path end-to-end: pre-flight gate (`pytest -q` +
      `norns validate --pack sample-world`, `--skip-tests` to bypass),
      rsync the checkout, skip `podman build` when the remote image's
      `vefr.engine_sha` label already matches the local HEAD
      (`--rebuild` to force), `systemctl --user restart vefr`,
      ensure the `vefr-{template,worlds}` named volumes exist,
      post-deploy `/api/health` + `maplab verify` (`--no-health` to
      bypass). `--init` writes `deploy.toml.example` + the README
      path; the wrapper refuses to run with any silent host
      default and points operators at `--init` (a fresh clone
      without a host should explode loudly, not `ssh` a hostname
      that resolves to nothing). `Containerfile` stamps
      `ENGINE_SHA=$(git rev-parse HEAD)` as a label so the
      no-op-skip works; `VEFR_DEPLOY_IMAGE` env override. New guide
      `docs/guides/deploy.md`; cross-link in `GETTING_STARTED.md`.
      Legacy `docs/guides/deploy-rsync-dance.md` kept for old
      bind-mount hosts. Tested in `tests/test_deploy.py` (4 new
      tests, full suite 200 passed).

- [x] **deploy-day fixes, atomic with the first wrapper deploy**
      (2026-09-01, `a11e532`). Two bugs the first ferry deploy
      exposed: `norns validate --pack sample-world` accepted only
      real paths and raised `FileNotFoundError` on a bare name, so
      the pre-flight gate could never pass - `maplab.cmd_validate`
      now resolves bare names through `pack_root()` the way
      `handbok`/`doctor`/`export` already did (3 tests in
      `tests/test_validate_pack_path.py`). And the post-deploy
      health probe hit `127.0.0.1` on the dev box (its SSH alias
      resolved to the wrong host) and gave up after one
      fixed 2-second sleep - it now probes through an SSH
      port-forward with a 20-attempt x 1.5s retry loop.

- [x] **dev zone polish: board, draft thread, inspector filter**
      (2026-09-01, PR #32, `526e06c`). Board drags within a column
      now announce `reordered in <col>.` in the board-status
      aria-live region (cross-column moves already did; intra-column
      was silent), and cards get a grabbing cursor while held. The
      draft-to-the-smith thread renders as labeled paragraphs
      (`board-chat-user` / `board-chat-smith`, luminance carries the
      role) instead of one flat text blob, auto-scrolls to the
      newest turn, gains a Clear thread button, and says under the
      log that the last 6 turns replay - the 7-turn harness run
      proves the cap. The aspect inspector gains a section filter
      (`dev-drawer-filter` + aria-live match count) that re-renders
      from the stored `/api/builder/aspects` payload - no refetch
      per keystroke; an empty query restores all six sections, and a
      no-match query says `no sections match.` plainly. Two real
      bugs the harnesses caught before any human did: the smith
      paragraph was classed `board-chat-assistant` (the CSS and the
      claim say smith), and the filter read `.html` off a string.
      Live on the deploy host after deploy (`526e06c`): served index.html
      carries the new ids, served board.css carries the grabbing
      cursor. Discovered and fixed along the way: the dev-box
      SSH alias resolves correctly and matches `VEFR_DEPLOY_HOST`,
      so a bare IP literal is not needed.

- [x] **reading row: Urd/Verdandi/Skuld live readbacks** (2026-09-01,
      PR #33, `a579d90`). The Skuld empty-state honesty check the
      matrix called for: the sample text was already engine-neutral
      (passes - no sample-world voice, the em-dash rule holds), but
      its meta line was dead placeholders - `phase: - speaker: -` for
      data the panel never had. Urd now carries a saved-state readout
      and Skuld a live `reading now:` readback, both fed by the same
      VEFR_PREFS values on every change, aria-live, layout pinned by
      min-height. The fake phase/speaker line is gone. Sound
      controls deliberately absent - no sound engine exists; sliders
      for silence would be dishonest UI. Harness checks cover change
      + reset on both readouts. Live on the deploy host after deploy
      (`a579d90`).

- [x] **api manner: honest 422/404s + the route guide tells the
      truth** (2026-09-01, PR #34, `2bfa064`). Found by driving the
      play loop live: `POST /api/vault` took a bare dict and answered
      a caller's typo (a missing `kind`) with a bare 500 - it now
      takes a typed `ItemCard` and answers 422 naming the missing
      fields. `POST /api/npc` answered an unknown speaker with a
      RuntimeError 500, and a voice-less pack would have died inside
      `next(iter({}))` - both are 404s in the engine's own words now
      (unreachable by the UI on sample-world; hand-rolled callers
      get the honesty too). And `one-source-of-routes.md` - the
      anti-drift doc itself - was drifted: it claimed a
      `POST /api/starred` that does not exist and listed 14 routes
      where 41 are served (missing `/api/world` itself, `/api/handoff`,
      the enhance trio, aspects, the journal/vault index routes).
      Regenerated from `app.routes`, dated. 4 new tests
      (`tests/test_api_manner.py`), suite 207 passed. Live-verified
      on the deploy host after deploy.

- [x] **block 5: sample-world polish - the pack stays neutral about
      bonds** (2026-09-01, PR #35, `041b77d`). Playing the pack live
      surfaced one defect: the board's forge response doc hardcoded
      `assigned | attuned | cold` - a bond list sample-world has
      never heard of (it draws given/found/cold). The doc now says
      `<the pack's bond keys>` with the reason in a comment, and
      `test_board_wired_into_chrome` refuses any hardcoded bond list
      in board.js (the canon-strings rule, applied to pack
      vocabulary). The pack itself validated and played green - and
      a handoff myth died on the record: `voices: 0` counts voice
      files, not speakers; sample-world ships one speaker (The
      Keeper) and the default-speaker npc flow works live.

- [x] **the packaged file wears the combat costume** (2026-09-01,
      PR #36, `bb4a665`). The web-UI half of the surface work landed
      in `06eed41`; this closes the packaged half. The weave
      artifact's template now carries the HP bar, the encounter
      prompt, and the verb row - data-surface comes from the pack at
      play time (a plain pack never sees the costume), HP is the
      same positional per-phase scale as combat.py inlined, the
      prompt text never names a pack's phase vocabulary, and the
      verbs record to a local localStorage journal - the same
      no-failure contract as /api/combat/action, minus the server.
      Test: builds a real packaged file through cmd_build_web and
      asserts the costume shipped, with a phase-name neutrality
      guard.

- [x] **chat v2: the interview grows the map and the town's
      people** (2026-09-01, PR #37, `59b3a25`). The interview is no
      longer frozen at the scaffold's proven-valid layout. The map:
      the model proposes run-length rows (build_map's own format) at
      the scaffold's exact dimensions using only the scaffold's
      legend characters; a proposal never touches the pack until
      maplab.validate() passes on a deep copy - two tries, then the
      proven layout stays and the author is told so. The gate is
      geometry-only; the interview's final validate is the full
      gate. Speakers: the town takes 1-3 voices (blank = 1) - extra
      voices get drafted seeds and a voice file, but their tile is
      deterministic code (reachable, unoccupied, unflooded,
      widest-spread band); no tile, no speaker, said plainly. The
      model call sits in chat.py's propose_map/_add_speaker;
      deterministic surfaces stay deterministic. 7 new tests, suite
      215 passed. Both changes live on the deploy host after deploy.

- [x] **the dev box plays** (2026-09-01, this session): five
      playability gaps closed as one bundle. (a) The model endpoint
      is a variable, never a host: `example.env` (tracked, neutral
      placeholders) copies to a gitignored `.env`, sourced before
      any entry point - GETTING_STARTED shows the shape. (b) The
      reading row's fonts ship: Atkinson Hyperlegible Next +
      OpenDyslexic woff2 (latin 400/700, vendored from Fontsource,
      SIL OFL) now tracked under `web/fonts/` with provenance - the
      font and contrast choices stop 404ing and the packaged file
      carries them from the first byte. (c) The road walked: journal
      kind `move`, `POST /api/journal/move` (42 routes), `town.js`
      posts one arrival per change of place (never per tile), the
      packaged file keeps the same journal in localStorage, and the
      export's "The Fen Walked" section witnesses the journey - the
      export.py TODO from earlier sessions closed. (d) The pool
      re-weaves: when the woven pool is spent, a small seeded
      composer re-splices its cloth - every word is real model
      output, whispers may cross combos (a rumor travels), npc lines
      stay locked to their speaker's own words, the status line says
      `woven anew from the pool's cloth.`, and with no pool at all
      the honest silence holds. Deterministic per save (mulberry32
      over a localStorage save-seed). The no-pool generator (pack-
      supplied whisper fragments) stays on Next - it is a pack-
      contract question. (e) The 76 runtime-state files under `data/`
      plus `worlds/poolworld/world-tree.md` left the index (`git rm
      -r --cached`); the gitignore rules hold alone and AGENTS.md's
      known-drift note reads none. Gate: 221 passed, 2 skipped
      (`uv run --group test pytest -q`), ruff clean.

- [x] **the no-pool world speaks** (2026-09-01, this session): the
      offline/no-server fallback's remaining half. Convention:
      `voices/<name>.fragments.md` beside a voice file carries that
      speaker's speakable lines - bullet lines speak, every other
      line is an author note. The loader strips the `.fragments`
      suffix, never registers a fragments file as a voice (the stem
      trap is test-pinned), and merges banks across act regions in
      file order - a region's bank travels with its own speakers.
      The packaged composer's ladder is now: live model -> woven
      pool -> the pool's own cloth -> the pack's own fragments ->
      honest silence, with the status line naming the rung (`from
      the pack's own fragments.` / `from their own fragments.`). An
      npc line only ever splices its own speaker's bank; fewer than
      two lines stays silent. sample-world ships the canary
      (`voices/keeper.fragments.md`), the package inlines the banks
      (`window.VEFR_FRAGMENTS`), and the pack-contract docstring
      documents the convention. `norns chat` v2 can later interview
      banks out of the author the way it drafts voice files. Gate:
      225 passed, 2 skipped (`uv run --group test pytest -q`), ruff
      clean.

- [x] **the ledger forgets no name** (2026-09-01, this session):
      the neutrality work's final three landed changes, recorded
      together. The tree scrub (PR #40): every tracked trace of the
      private pack and game names gone from tests, docs, LICENSE,
      and the guides - the two previously-skipped fixture suites
      now run against the tracked canary instead of skipping - and
      the two flagged follow-ups closed with it (`/api/builder/
      resolved` surfaces the fragment banks; the surface-UI entry
      no longer claims a half that the packaged-costume PR closed).
      The canon-name sweep (PR #41): the private-term list's
      character names swept from the synthetic fixtures and the
      ROADMAP story descriptions; the lore packs stay by design.
      The history scrub: a third filter-repo pass (backed up and
      verified, per the AGENTS.md boundary) rewrote every blob,
      commit message, and historical path name-free across all 200
      commits. The anti-regression guard's scope now covers src/,
      web/, tests/, docs/, and the root documents - it caught two
      stragglers on its first run. Gate: 240 passed, 0 skipped
      (`uv run --group test pytest -q`), ruff clean.

- [x] **the deploy button** (2026-09-01, this session):
      deploy.toml scaffolding landed (`--init` writes it; the
      per-host twin is gitignored like `.env`; the dev box's copy
      points at the deploy host and `.env` carries `VEFR_DEPLOY_HOST`) -
      and the deploy it drove surfaced a real wrinkle: the live
      quadlet's rw bind (`~/vefr-worlds/`) shadowed the engine's
      own sample-world with a pre-acts stale copy, so rebuilt
      templates never reached the running pack. The stale copy
      moved to `~/vefr-worlds-backup-20260901/` (starred-whispers
      preserved); engine-shipped packs now serve from the ro
      template and refresh on every image build, while author
      packs still land in the rw bind via ferry fetch. Verified
      live: health 200, the resolved view shows the keeper bank
      (6 lines), fonts 200.

- [x] **the wrapper reads its own config** (2026-09-01, this
      session): three wrapper additions for the recurring frictions
      the deploy-day work surfaced. `ferry deploy` consumes
      `deploy.toml` directly (stdlib tomllib; host and image
      resolve from it whenever --flags and env are silent - the
      export dance is gone, and a malformed toml reads as absent
      rather than taking the deploy path down). `skipa` grew two
      checks inside its existing seven questions: Q3 now runs the
      shadow check on the deploy host's rw bind and names any
      engine-shipped pack that would hide a freshly built template
      (the deploy-day find), and Q2 reports the reading-row fonts
      (0/4 would mean the woff2s never landed). `norns doctor`
      falls back to deploy.toml's url for the live check when
      `VEFR_LIVE_URL` is unset. And the deploy tunnel no longer
      leaks: `ssh -fN` forked past the Popen pid so `terminate()`
      could never reach it - one orphaned tunnel per deploy (three
      on the dev box as of today, killed; `-N` keeps the process
      where the finally can reach it). GETTING_STARTED's deploy
      section drops the export line. Gate: 247 passed
      (`uv run --group test pytest -q`), ruff clean.

- [x] **the Play workspace can be composed OR free-docked** (2026-09-03):
      the workspace is one responsive shell from 0 to 1179px (context left,
      game centre, journal right on wide screens; Town spans the width
      on medium; one panel at a time on narrow), and turns into a free
      dock of five windows (Town / Whispers / Bell / Vault / Journal)
      at >=1180px, matching the ChatGPT free-dock concept. Plain-English
      panel names with Norse `.sub` tags in the title bars (matches the
      existing tab-button convention), 44px drag/resize affordances,
      luminance-only focus, `prefers-reduced-motion` zeroes every
      transition, pointer drag throttled via rAF, localStorage
      persistence under `vefr:dock:v1` (versioned + merge-back-from-
      defaults on load). Keyboard parity: Enter/Space to grab, Arrow
      keys to move, Escape to cancel. "Reset dock layout" lives in the
      dev drawer so the player never sees it. Medium and narrow screens
      keep the composed shape (the inclusive-forward rule that says
      narrow gets a stable layout). Two commits:
      `wip: compose the play workspace` and
      `feat: free-dock Play workspace`. Gate: 248 passed
      (`uv run --group test pytest -q`), ruff clean; 30+ new checks
      in `tests/fixtures/dom_harness.mjs`.

- [x] **free-dock review fix-ups** (2026-09-03, this session): the
      landing had two reviewable defects caught in a headless-Chrome
      verification pass against the running engine. First: the
      `@media (min-width: var(--free-dock-breakpoint))` block is invalid
      CSS - browsers drop the whole rule when a `var()` appears in a
      media-query condition, so the entire free-dock structural
      enablement (window frames, drag handles, absolute positioning)
      silently never applied. Fix: literal `1180px` in the media query;
      the `--free-dock-breakpoint` custom property is kept on `:root`
      for JS-side reads via `getComputedStyle`, and the comment header
      on both declarations names the literal as the single source of
      truth. Second: the `density=compact` pref was setting
      `min-height: 36px` on tabs / zone buttons / phase-rail buttons,
      which violates the Always-target >= 44px rule (AGENTS.md).
      Fix: drop only `min-height`, keep the `padding: 0.35rem 0.7rem`
      trim (compact visually, contract intact). Adds
      `.gitattributes` stamping `text eol=lf` on `web/*.html`,
      `web/*.js`, `web/*.css`, `tests/**/*.mjs`, `tests/**/*.py`,
      `src/**/*.py`, `*.md` so Windows-checkout CRLF churn stops
      polluting future diffs - the actual normalization of existing
      mixed-ending files is deferred to a separate maintenance PR
      (mixing a 7000-line line-ending rewrite with a 20-line
      functional UI fix is exactly the diff-hygiene failure this
      guardrail exists to prevent). New regression file
      `tests/test_web_css_structure.py` (3 tests) catches: any
      `@media` condition using `var()`; drift between the CSS
      `--free-dock-breakpoint` value, the `@media` literal, and the
      JS `FREE_BREAKPOINT` fallback (all must stay 1180); any compact-
      density min-height below 44px. Browser-verified at 1280x800
      (free-dock frames visible, all five panels with DRAG/snap/min
      controls), 1100x900 (composed two-column, no free-dock leak),
      760x900 (composed still engaged at the breakpoint edge),
      700x900 (single active panel, no horizontal scroll, dock state
      from earlier wide-viewport usage doesn't break narrow layout).
      Live engine on the deploy host (`deploy-host:8820`) independently
      reproduced the pre-fix defect at 1280px. Gate: 251 passed
      (`uv run --group test pytest -q`), ruff clean.

- [x] **Storyteller Pack provider seam + audition harness** (2026-09-04,
      this session): the engine is now model-neutral. `Provider` enum
      is two values (OLLAMA + OPENAI_COMPATIBLE; llama.cpp / LM Studio /
      vLLM / LocalAI / TGI all hang off the latter as tested runtimes).
      The Tier ladder (0 minimum → 1 small → 2 creative → 3 smart
      control → 4 BYOM) is encoded in `[capabilities]` flags. New
      `src/vefr/storyteller.py` resolves the active storyteller from
      `VEFR_STORYTELLER` env, the `data/storytellers/active.toml`
      marker, installed packs, bundled packs, or the engine reference
      (gpt-oss-20b, kept for back-compat so existing tests still pass).
      Five audition packs ship under `storyteller_packs/`
      (gpt-oss-20b-reference, gryphe-style-gemma-12b creative ref,
      gemma4-e2b / gemma4-e4b / ministral3-3b); Qwen2.5-3B-Instruct
      sits under `data/storytellers/` as an evaluation-only candidate
      (research-only license, never a shippable default). `ScenePacket`
      + `norns storyteller-test --model/--matrix/--scene/--runs/--seed
      /--blind` give Rylei a side-by-side audition harness with
      artifacts saved to `artifacts/storyteller-tests/<ts>/{manifest.json,
      <pack>.txt, blind_map.txt}`. Missing models SKIP cleanly, no
      benchmark scores, no automatic judges. `/data/storytellers/`
      gitignored per the existing runtime-state convention. Gate: 278
      passed (`uv run --group test pytest -q`), ruff clean; the
      pack-neutrality test caught a private-story leak in a docstring
      and was fixed before merge.

- [x] **storyteller capability benchmark (blind A/B/C/D)** (2026-09-04,
      this session): the second-tier audition harness. Nine new
      fixtures (`hidden-fact-trap`, `immediate-interruption`,
      `old-promise`, `player-accusation`, `mythic-stranger`,
      `neutral-quiet-scene`, `gameplay-help`, `ambiguous-clue`,
      `player-surprising-action`) join the existing Rosa anchor for
      ten total. Each tests one or two specific capabilities; each
      carries an optional `forbidden_strings` list for deterministic
      hard-fail detection. New `src/vefr/storyteller_benchmark.py`
      assigns stable A/B/C/D labels (seeded, shuffled so position
      reveals nothing), runs every fixture against every configured
      pack N times, and writes a per-fixture blind review file plus
      a private `identity.json` mapping. `norns
      storyteller-benchmark {run,reveal,review}` exposes the three
      modes. Reveal step merges identity with hard-fail counts and
      pack metadata (license, quantization) so the reviewer can read
      prose, write A/B/C/D rankings, then compare against model cost.
      No automatic winner, no benchmark score, no LLM judge. Gate:
      293 passed (`uv run --group test pytest -q`), ruff clean; the
      pack-neutrality gate caught a gendered pronoun in a docstring
      and was fixed before claim. (A pre-existing doc leak in
      `docs/guides/accessibility-contract.md` flagged for separate
      review.)

## Next

*(Older detail. The board at the top of this file, "Where VEFR stands", is the current order.)*

- [ ] **Language architecture: the disposition read** (gate, owner). The proof
      pass ran and the research packet landed on 2026-10-03
      ([PR #242](https://github.com/Rylee-Bee/vefr/issues/242),
      `docs/research/language-architecture/`): **GO WITH CONSTRAINTS**. The
      packet authorizes nothing until Rylee has read it
      (`11-open-decisions.md` item 6) and says go. The Blueprint is the
      earned first slice and it is already built; the kernel, the dialect
      layer and pack migration are explicitly not earned and wait for a
      second real consumer. Floors phase 2, the album and equipment are
      informed by that disposition, not blocked by it.

- [ ] **Random floors, phase 2** (`design/random-floors.md`): the `descent` block, run seed,
      depth tables, **weights on table rows** (decided 2026-10-03, so the tables answer "which
      one" as well as "how many"; the guardian and the last room stay placed, not rolled, so the
      ending is reachable on every seed), the Journal line and the New descent button. **Next in
      order** — self-contained, and it unblocks #215.
- [ ] **Damage types, status effects and resistances**
      (`design/elemental-and-status-effects.md`, scope approved 2026-10-03): the full triangle.
      A **campaign, not a slice** — it needs a damage resolver (the two damage paths are
      asymmetric today), a status store on the `lightTick` turn pattern, a player resistance
      surface, and an ADR amendment because a new enemy field must also pass the **closed**
      Blueprint key sets. Four decisions are owed before any code.
- [ ] **Gates and guardians, the rest** (`design/gates-and-guardians.md`): the `requires`
      lock landed (see Landed). Still to build: the key-carrying guardians and the generated
      ladder ending in the act's boss, and the boss's seal opening a treasure room. Decided
      by Rylee (2026-10-02): the first lock is the stair from floor 3 to floor 4, the key is
      an actual key, and the guardians are stat variants of existing monsters, named from
      their art and abilities.
- [ ] **The album** (`design/album.md`): one record of what you have met, a sticker album
      first, bestiary, items and map as views later.
- [ ] **Equipment, the rest** (`design/equipment.md`): the pack fields
      and the pure engine landed (Landed above). Still to build: the Bag
      "You" section, the Equip/Take off buttons and the live line, the
      `localStorage` persistence (`vefr-equipped-<world>`), the hero
      wiring, the glossary, and the Cottage demo.
- [ ] **A real act 2** (ADR 0006): only the first act plays today.
- [ ] **Rules, remaining** (`design/rules-when-then.md`): `add_rule` edits and a `grows` event.
- [ ] **A second tiny skin** (`design/ui-skin.md` step 6), to prove skins swap.
- [ ] **A text-input surface** for the player (so a "when a word is said" event can exist): later.

### Enhancement wave 1 (2026-09-30 packet)

From `docs/research/2026-09-30-enhancement-packet.md`. Six small,
low-risk moves that compound; each has its own issue.

- [ ] **Grammar-constrained output** so any local model returns valid JSON
      (#128): a GBNF grammar for llama.cpp and/or Outlines /
      lm-format-enforcer for backends that ignore `response_format`.
- [ ] **An embedded vector index for the Lorekeeper** (#129): SQLite +
      `sqlite-vec`, with `facts.jsonl` still authoritative and `rebuild`
      still able to recreate the index from facts alone.
- [ ] **Gate hardening** (#130): vulture (dead code), deptry (deps),
      lychee (links), guidepup (screen readers).
- [ ] **Property tests** (#131) for delve determinism, reachability, and
      fog - same seed gives the same floor; no orphaned rooms; no seeing
      through a wall.
- [ ] **Dependency freshness** (#132): dependabot misses npm; evaluate
      Renovate and cover the workflow pins.
- [ ] **Vale** (#133) to enforce the house voice in docs.

### Enhancement wave 2 (2026-09-30 packet; owner-picked)

- [ ] **Autoexplore + Dijkstra-map AI** (#141): one key rolls toward the
      unexplored; monsters use desire-weighted maps. Movement, accessibility,
      and AI from one technique.
- [ ] **Tracery-style deterministic text** (#142): rumours, names, weather -
      seedable, offline, no model call.
- [ ] **Optional Ink conversations** (#143): richer per-speaker dialogue, with
      `inkjs` in the single-file player.
- [ ] **Audio pairing** (#144): every sound paired with a visual event; silence
      stays a fully playable mode.
- [ ] **Richer floors** (#145): wave-function-collapse ideas for deeper floors
      and outdoor regions.

- [ ] **Name a landmark in the Map Room** (from `studio-lessons.md`,
      2026-09-29): a square can be marked today, but a `pois` entry - a
      *named* place - still needs a route the Map Room does not have. The
      map commission's first rule wanted it and had to settle for a mark.
- [ ] **Interview template** (from `docs/guides/studio-lessons.md`): residents
      ask one question per turn, keep the author's words verbatim, recap before
      saving. First users: the Desk (the brief) and the Folks (a character).
- [ ] **Keep / Refine / Redo with pick-from-three** for every picture and draft;
      refine takes plain words; unpicked options go to a spare parts shelf.
- [ ] **Begin a new world starts blank**: placeholders marked "yours to write",
      not another world's tagline, map and keeper.
- [ ] **Say why when slow**: the status pill names a busy brain and offers the
      no-model path.
- (2026-09-16) `feat/dev-board` (123-commit orphan branch, dev-board UI
      chrome: repo header, file-tree, 4-col grid, drag-rank, right-rail
      stub) is **preserved on origin, unmerged** — assessment pending,
      do not discard without a bundle backup.
- [ ] **interactive chat helper**: inline conversational assistant in
      the builder UI answering world-building questions and adjusting pack data.
      Acceptance: persistent 6-turn chat in Builder tab successfully calls
      `/api/builder/chat` with pack context.
      (Existing machinery: `chat.py`, `/api/builder/chat`).
- [ ] **formatted ebook export**: single-document narrative exporter
      formatting playthroughs with chapter headings, character wiki, and
      collected relics. Acceptance: `/api/export` generates clean e-reader
      compatible EPUB/Markdown artifact with full metadata.
      (Existing machinery: `export.py`, deterministic preface templating).
- [ ] **engine + world full git scaffold**: standalone repository exporter
      packaging engine bones and author pack into an independent git project.
      Acceptance: `ratatoskr ferry scaffold --full` creates functional standalone
      repo with passing offline test suite.
      (Existing machinery: `cmd_scaffold`, pack contract loader).
- [ ] **Tiled map importer** (parked after the surface-UI work):
      `norns import-tiled map.json --pack X` reads Tiled's JSON
      export - visual map authoring, the storyteller-critical gap -
      and writes `map.md` + contract points through
      `maplab.build_map` + `maplab.validate()`. Thin and optional;
      text authoring stays canonical, no Tiled dependency. Tiled
      1.10's JS scripting API could later host a one-click "export
      as vefr pack" from inside the editor. See
      `docs/guides/companion-resources.md`.
- [ ] **more lore packs**: worlds/lore/<new-flavor>/ directories.
      Adding one is data-only (mkdir + four markdown files); the
      engine discovers it. Future flavors: homeric, east-asian-
      folklore, jewish-diaspora, contemporary-urban. Each one is
      a literary mood-board for fiction, licensed CC BY-SA 4.0.
- [ ] **the marketplace**: a community place to share, search, and
      rate engine add-ons - world packs, lore packs, sprites, map
      recipes, and model settings ("local LLM packs": someone's
      perfect llama.cpp + gpt-oss configuration for their exact
      hardware, shareable as data). The distribution path already
      exists (`ferry fetch --pull`, the Builder tab's import by
      owner/name), so v1 is an index over plain git repos, not new
      infrastructure - ratings live with the community, and
      discovery may grow a `norns market` command. The always-
      layer's "private until it isn't" made social.
- [ ] **accessible controls and audio-pairing**: the keybinds remap
      (GAG Basic, localStorage config) and audio-pairing hooks for
      visual event pairing when sound effects land.

## The always-layer

- the loop: whisper -> keep what's true -> the ledger -> the voice
  compounds
- the backups: Gitea, the durable clone, the NAS bundle
- inclusive-forward: every screen answers for different needs -
  reading load, target size, contrast over color, motion off by
  default, and when sound arrives, every sound paired with a
  visual event. It is part of the gate, not a follow-up.
- private until it isn't: one checkbox, whenever - or never. Both
  are complete endings.
