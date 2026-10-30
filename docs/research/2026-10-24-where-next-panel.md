# Does the pinned VEFR build ship a usable "Where next?" / "Why?" panel?

**2026-10-24.** Read-only research against the engine commit Lanternwake pins,
`72d366e731f5e4c286269928089cc35da96202f8` (the `VEFR_REF` in Lanternwake's
`.github/workflows/pack-check.yml`). Nothing was checked out; every claim below
is read from that commit with `git show 72d366e7:<path>` and
`git grep <pattern> 72d366e7 -- <path>`. The pinned commit **is** present in this
clone (`git cat-file -t 72d366e7` prints `commit`) and **is** an ancestor of
this branch's HEAD (`git merge-base --is-ancestor 72d366e7 HEAD` exits 0), so
every citation is a citation at the pin, not at HEAD.

## Answer

**Yes — both panels ship at the pin, and they are player-facing, not debug
tools.** The woven player has a pause-menu tab **Where next?** and a pause-menu
tab **Why did that happen?** (`web/player/parts/030-shell.html:205-206`), and
both render from real records the rules engine keeps: the *Where next?* panel
lists the `point-to` hints a rule produced (`web/player/parts/340-where-next-hints.js:70-94`),
and the *Why did that happen?* panel lists the last 20 fired rules with the
plain sentence that says which condition made each one fire
(`web/player/parts/340-where-next-hints.js:96-119`). The engine's own research note
records the `point-to` hint as ephemeral and the *Where next?* panel as the
merged remedy (`docs/research/2026-10-02-first-independent-pack.md:34`). The
panels are **in** the pinned build: its history contains merge commit
`28ee8f50` for PR #192, dated 2026-10-02, before the 2026-10-12 pin. The
honest limit on
the *Where next?* panel is that it is a **navigation pointer, not a
consequence panel**: a pack may only point at a region it declares, and the
sentence it shows is a template with the region id in it. A pack cannot put
free prose about a choice in that panel; the free prose belongs in a `say`
action and in the *Why did that happen?* panel.

## 1. Does the woven/standalone player render a "Where next?" panel, a "Why?" explanation, or any consequence/next-step hint UI?

Yes, on all three counts, and they are three different surfaces.

### 1a. The two evidence panels

The pause menu is the only place they live. The tab list is hard-coded in the
player shell:

- `web/player/parts/030-shell.html:205` — `<li><button type="button" data-panel="next">Where next?</button></li>`
- `web/player/parts/030-shell.html:206` — `<li><button type="button" data-panel="why">Why did that happen?</button></li>`

The panel bodies follow at `web/player/parts/030-shell.html:235-240` (the
*Where next?* body, with the fill point `#next-list` at
`web/player/parts/030-shell.html:238`) and
`web/player/parts/030-shell.html:241-246` (the *Why did that happen?* body,
with the fill point `#why-list` at `web/player/parts/030-shell.html:244`).

They render on open, from the records and nothing else:

- `web/player/parts/200-pause-menu.js:41` — `if (b.dataset.panel === 'next') renderNextPanel();`
- `web/player/parts/200-pause-menu.js:42` — `if (b.dataset.panel === 'why') renderWhyPanel();`

The two render functions:

- `renderNextPanel()` at `web/player/parts/340-where-next-hints.js:70-94`. It
  reads `window.VEFR_NEXT`, reverses it so the newest row is first
  (`web/player/parts/340-where-next-hints.js:76`), and writes one row per
  place: the place id in bold, then the line
  (`web/player/parts/340-where-next-hints.js:77-84`). When the list is empty
  it writes the fixed sentence *"Nothing has pointed the way yet."*
  (`web/player/parts/340-where-next-hints.js:86-89`).
- `renderWhyPanel()` at `web/player/parts/340-where-next-hints.js:96-119`. It
  reads `window.VEFR_WHY`, newest first
  (`web/player/parts/340-where-next-hints.js:102`), and writes the rule's id
  (dashes turned into spaces) followed by the engine's sentence
  (`web/player/parts/340-where-next-hints.js:103-110`). When the list is empty
  it writes *"Nothing has happened yet that needs explaining."*
  (`web/player/parts/340-where-next-hints.js:113-117`).

The two tabs are **always present**. `bindMenu()` removes the Album tab and the
Model-settings tab when the pack does not support them
(`web/player/parts/200-pause-menu.js:5-14`); it never removes *Where next?* or
*Why did that happen?*. A pack with no rules still gets both tabs, showing
their empty-state sentences.

### 1b. Where the two panels get their data

*Where next?* is fed by exactly one path. `window.VEFR_NEXT` is declared at
`web/player/parts/340-where-next-hints.js:42` and is only ever written by
`rulesNextRecord(place, line)` at
`web/player/parts/340-where-next-hints.js:55-64`, which keeps **one row per
place** (the newest word wins, `web/player/parts/340-where-next-hints.js:59`)
and mirrors the array to browser storage under
`vefr-next-<world>` (`web/player/parts/340-where-next-hints.js:64`).

`rulesNextRecord` has exactly two callers, and both are in the rules engine's
`point-to` handler:

- `web/player/parts/510-rules-closure-surfaces.js:41` — the "no way declared"
  case.
- `web/player/parts/510-rules-closure-surfaces.js:58` — the normal case.

`window.VEFR_RULES_POINT_TO` itself is at
`web/player/parts/510-rules-closure-surfaces.js:26-58`. It is reached only
through the rule action dispatch at
`web/player/parts/320-pack-rules.js:93-94`. So: **a rule action is the only
way to put a row in the Where next? panel.**

*Why did that happen?* is fed by `rulesWhyRecord(out.fired)` at
`web/player/parts/320-pack-rules.js:22`, called right after every rule run.
`rulesWhyRecord` is at `web/player/parts/320-pack-rules.js:136-143`: it pushes
`{id, why}` per fired rule, keeps **only the last 20**
(`web/player/parts/320-pack-rules.js:142`), and mirrors them to browser storage
under `vefr-rules-<world>` (`web/player/parts/320-pack-rules.js:143`).

The `why` sentence itself is the engine's, not the pack's. It is built at
`web/player/parts/445-rules-engine.js:369` by `buildWhy(rule, event, data, phrases)`,
where `phrases` are the plain phrases the rule's own `if` conditions produced
(`web/player/parts/445-rules-engine.js:355`); the entry is emitted at
`web/player/parts/445-rules-engine.js:407`. The shape is
`rule '<id>' fired: <phrase>` (`web/player/parts/445-rules-engine.js:333-335`).

**So the *Why?* panel explains why a RULE fired, not what a choice changed.**
It is a causality log, and its subject is the pack's condition ("the hero had
the brass key"), not the player's decision.

### 1c. The other consequence/next-step surfaces at the pin

- **Narrator line.** `combatSay(msg)` at
  `web/player/parts/240-verb-journal.js:37` writes one plain sentence to the
  screen-reader-live `#combat-live` element. A rule's `say` action reaches it
  (`web/player/parts/320-pack-rules.js:60-69`). This is the only place a
  pack's own free prose reaches the player in the moment.
- **Act end card.** `complete-act` opens one end card, "Keep exploring" or
  "Start over" (`web/player/parts/110-the-library.js:123-139`; the rule
  vocabulary lists it at `docs/guides/rules.md:97-100`). It records that a
  story beat is finished and does not advance to another act.
- **Journal panel.** The play journal holds whispers and arrivals
  (`web/player/parts/260-whisper.js:5`; arrival logging at
  `web/player/parts/240-verb-journal.js:18-24`). It is not a consequence log.
- **The ledger.** `window.VEFR_LEDGER`
  (`web/player/parts/050-inlined-world-pack.js:26`) is the pack's collected
  tavern-whisper ledger, fed into the Whisper prompt
  (`web/player/parts/260-whisper.js:18`). It has nothing to do with the two
  panels.

## 2. What the panel reads from a pack, and what a pack author must do

### 2a. What it reads

The *Where next?* panel itself reads **no pack data at all** at render time. It
reads `window.VEFR_NEXT` (`web/player/parts/340-where-next-hints.js:71-76`),
which is browser storage the engine wrote earlier. The pack data that reached
it got there through these bakes:

| Pack data | Baked as | Where |
|---|---|---|
| the pack's rules | `window.VEFR_RULES` | `web/player/parts/050-inlined-world-pack.js:65` |
| the pack's `world.json` (which carries `player_words`) | `window.VEFR_WORLD` | `web/player/parts/050-inlined-world-pack.js:2` |
| the act's regions | `window.VEFR_REGIONS` | `web/player/parts/050-inlined-world-pack.js:37` |
| the act's doors | `window.VEFR_TRANSITIONS` | `web/player/parts/050-inlined-world-pack.js:40` |

The doors are what turn a region id into a direction.
`transitions()` is `window.VEFR_TRANSITIONS`
(`web/player/parts/400-setup-town-open.js:21`), and
`VEFR_RULES_POINT_TO` walks it looking for the door that leaves the current
region for the target region, then reads that door's `at` / `to_at` tile
coordinates and turns the difference into north/south/east/west
(`web/player/parts/510-rules-closure-surfaces.js:28-47`). If no door is
declared, the pack gets the honest line *"No way to {place} is declared from
here."* (`web/player/parts/510-rules-closure-surfaces.js:38-43`).

The wording of each line lives in one table in the player,
`VEFR_PLAYER_WORDS` at `web/player/parts/340-where-next-hints.js:14-19`, with
the four keys `where_next.goal`, `where_next.reach`, `where_next.here`,
`where_next.no_way`. `playerWord(key, slots)` at
`web/player/parts/340-where-next-hints.js:27-36` prefers the pack's own word
from `window.VEFR_WORLD.player_words` and falls back to the engine's.

The same four keys are typed on the Python side as `shapes.PLAYER_WORDS` at
`src/vefr/shapes.py:1484-1493`, and `vefr check` refuses a wrong one through
`player_words_errors` at `src/vefr/maplab.py:1509-1530`. The pack's block is
optional: a pack that declares none plays the engine's wording byte for byte
(`docs/guides/rulesets.md:1563-1565`).

### 2b. What a pack author does to make a new fork's payoff appear in it

Write a rule whose `then` includes a `point-to` action naming a region the
pack declares. That is the whole recipe.

```json
{
  "id": "point-at-the-causeway",
  "when": {"enters": {"what": "the-causeway"}},
  "then": [{"point-to": "saltreach"}]
}
```

The steps and their ground truth:

- The value must be a **region id** the pack declares. `vefr check` refuses
  anything else: the rule's `point-to` is validated as a `place`
  (`src/vefr/maplab.py:1185`), a `place` must be in `known['places']`
  (`src/vefr/maplab.py:989-991`), and `known['places']` is the set of the
  pack's declared region names (`src/vefr/maplab.py:921-925`). A rule naming
  a place the pack does not declare is an error, not a silent skip.
- The action bakes as a plain string (`src/vefr/cli.py:2131-2132`).
- The player computes the direction from the pack's declared doors and writes
  one row per place into `window.VEFR_NEXT`
  (`web/player/parts/510-rules-closure-surfaces.js:44-58`).

Three hard limits a pack author has to design around:

1. **The panel shows a region id, not a display name.** The row's bold prefix
   is `e.place + ' - '` (`web/player/parts/340-where-next-hints.js:81`) and
   `e.place` is the region id the rule named. Region display names are
   explicitly out of scope for this table (`docs/guides/rulesets.md:1588-1590`).
   A pack whose regions are called `causeway-fork` and `salt-road` will show
   those ids to the player.
2. **The panel cannot hold free prose.** A pack may override the four
   *templates* through `player_words`, but each template must name its
   `{place}` slot (`src/vefr/shapes.py:1466-1483`,
   `docs/guides/rulesets.md:1566-1569`), and the `{place}` slot is always
   filled with the region id. There is no way to write "the left road closes
   behind you" into the *Where next?* panel.
3. **One row per place.** `rulesNextRecord` drops the previous row for the
   same place (`web/player/parts/340-where-next-hints.js:59`), so the panel
   holds the current intention for each place, not a history.

So for a fork with two routes, the *Where next?* panel can show the player
which region each route leads to and which way to step. It cannot show the
player what the fork *cost*. The fork's prose belongs in a `say` action (one
momentary narrator line) and its causality in the *Why did that happen?*
panel.

### 2c. Is it usable as-is by Lanternwake's pack?

**On the engine side, yes: the panels are in the pinned build, they need no
engine change, and they are the same panels VEFR's own research note asked
for.** Nothing in the pinned commit gates them behind a flag, a pack opt-in, or
a capability the pack must declare; they are unconditional parts of the
woven player.

**On the pack side, this is where the honest limit sits, and it is UNVERIFIED
from this clone.** The Lanternwake pack is not in this repository, so I cannot
read its `world.json`, its rules, or its region contracts. What the repo does
record is that the pack's playtest complaint was that `point-to` hints were
ephemeral (`docs/research/2026-10-02-first-independent-pack.md:34`, row 12:
"*`VEFR_RULES_POINT_TO` prints one `combatSay` line and forgets it*"), which
says the pack used `point-to` and that the panel was the agreed remedy
("**Where next?** panel: `point-to` results persist as inspectable
intentions"). If that holds, the panel populates for Lanternwake with no pack
change at all, because the pack's `point-to` actions already exist.

The command that would settle it, run in the Lanternwake checkout:

```
git grep -n '"point-to"' -- '*.json'
git grep -n '"regions"' -- '*/world.json'
```

## 3. What else exists at the pin for surfacing consequences

Since the answer to question 1 is yes, this is the honest inventory of the
other surfaces a pack can use for a consequence, and the smallest honest
statement a pack can make about each.

- **The narrator line (`say`).** One plain sentence, in the moment, in the
  screen-reader-live region (`web/player/parts/240-verb-journal.js:37`;
  dispatch at `web/player/parts/320-pack-rules.js:60-69`). This is the only
  surface that can carry a pack's own prose about what a choice changed. It
  is ephemeral: it is the current line, not a list.
- **The *Why did that happen?* panel.** A causality record of the last 20
  fired rules, each with the sentence naming the condition that let it fire
  (`web/player/parts/320-pack-rules.js:136-143`;
  `web/player/parts/445-rules-engine.js:369`). The smallest honest statement
  a pack can make is "this rule fired because this condition was true" — it
  is not a record of the player's decision, and it is capped at 20 entries.
- **The *Where next?* panel.** A navigation pointer to a declared region, one
  row per place, newest wins (`web/player/parts/340-where-next-hints.js:55-64`).
  The smallest honest statement a pack can make is "the world is aiming at
  this place, and here is the way" — nothing about consequences.
- **The act end card.** One card saying a story beat is complete, with "Keep
  exploring" and "Start over" (`web/player/parts/110-the-library.js:123-139`).
  The smallest honest statement is "this part of the story is over" — it does
  not advance to another act (`docs/guides/rules.md:97-100`).
- **Flags and beliefs.** A rule can `set` / `unset` a flag and
  `believes` / `stops-believing` / `tells` a claim
  (`docs/guides/rules.md:95-96`). These have **no player-facing surface at
  the pin**: `performRuleAction` applies them to the engine state and returns
  without writing anything to the page
  (the comment at `web/player/parts/320-pack-rules.js:53-56`: "they have no
  page surface and need none"; the apply at
  `web/player/parts/320-pack-rules.js:57-62`). They are readable only by
  other rules, and by a probe (`src/vefr/devtools.py:626-629`).

There is no pack-facing "consequences" or "what changed" screen at the pin.

## 4. Tests and docs at the pin that pin this behaviour

Tests:

- `tests/browser/test_menu_labels.py:68` — `CORE_TABS` includes
  `"Where next?"` and `"Why did that happen?"`, so the two tabs are asserted
  present in the woven menu at two widths.
- `tests/fixtures/events_play_harness.mjs:78-79` — after the `starts` rule
  fires, the harness asserts `window.VEFR_NEXT` holds the kept intention
  ("the point-to hint was kept as an intention").
- `tests/fixtures/events_play_harness.mjs:150-156` — the harness opens both
  panels and asserts `#next-list` has at least one row ("the Where next?
  panel shows the kept hint") and `#why-list` has at least eight rows ("the
  Why panel lists what actually fired").
- `tests/test_player_words.py:57-60` — the four `where_next.*` keys and their
  default wording; `tests/test_player_words.py:148-183` — the refusals for a
  blank, a non-string, a missing `{place}` slot, and an unknown key;
  `tests/test_player_words.py:80-90` — the drift guard between the Python
  and the player table.
- `tests/fixtures/player_words_harness.mjs:1-5,22-23,33-43` — the player-side
  table code slice runs in a Node `vm` with a stub `window` and no DOM;
  `:98-107` checks the `unknownKey` and `unfilledSlot` cases.
- `tests/test_rules_validator.py:141-146` — a `point-to` naming an unknown
  place is refused by the validator, two errors for one rule that also names
  an unknown `enters` place.

Docs:

- `docs/guides/rules.md:144-150` — the *Why did that happen?* section: every
  fired rule leaves one plain sentence, `point-to` hints are kept under
  *Where next?*, and "Both are real records of what ran - nothing is
  inferred."
- `docs/guides/rules.md:92-100` — the action vocabulary, with `point-to`
  described as "a direction that is kept in the **Where next?** panel" and
  `complete-act` as the end card.
- `docs/guides/glossary.md:53-54` — both panels in the glossary, each marked
  "in use (the woven player)".
- `docs/guides/rulesets.md:1532-1590` — the *Player words* section: the four
  keys and their defaults, the optional `world.json` block, the rules the
  checker enforces, and the out-of-scope list (region display names, POI
  labels in `point-to`).
- `ROADMAP.md:269-271` — the #192 entry, naming the two evidence panels and
  what they are made of.

The engine's own research note records both panels as merged in #192:
`docs/research/2026-10-02-first-independent-pack.md:34` (row 12, *Where next?*)
and the same file's row 11 at
`docs/research/2026-10-02-first-independent-pack.md:33` (the *Why did that
happen?* panel).

## What Lanternwake should do

Use the panel; do not build a second one. The pinned engine already ships
*Where next?* and *Why did that happen?* as unconditional parts of the woven
player, they were built for exactly this pack's complaint, and a Lanternwake
fork that writes its own "where next" UI would duplicate a surface the player
can already open, and would lose the engine's honest rule that the panel
shows only records and never infers. The fork's *payoff prose* does not
belong in that panel — the panel can only point at a declared region — so it
belongs in the rule's `say` action for the moment it lands and in the *Why
did that happen?* panel for the record, and the fork's two routes should be
two regions the pack declares, so that the panel can name them. Before
building the fork, the one thing to check is on the pack side, not the engine
side: that Lanternwake's regions and its `point-to` rules are named the way
the panel will show them, because the panel shows region ids, not display
names.

## UNRESOLVED

- **The Lanternwake pack itself is not in this clone.** Its `world.json`, its
  `regions`, its `player_words` and its `point-to` rules were not read. Check
  in the Lanternwake checkout with
  `git grep -n '"point-to"' -- '*.json'` and
  `git grep -n '"player_words"' -- '*/world.json'`.
- **Whether Lanternwake's pack actually declares `point-to` rules** is an
  inference from the engine's research note
  (`docs/research/2026-10-02-first-independent-pack.md:34`, row 12), not a
  reading of the pack.
- **Whether the pack's region ids read well to a player** cannot be judged
  from this clone, and the panel shows them verbatim
  (`web/player/parts/340-where-next-hints.js:81`).
- **The browser tests were not executed at the pinned commit.** The pinned
  commit was not checked out, and the browser tests need a woven pack built
  from it. `tests/browser/test_menu_labels.py` and
  `tests/fixtures/events_play_harness.mjs` are cited by reading them, not by
  running them at `72d366e7`. The command that would run them, in a checkout
  of the pin, is
  `uv run --group test pytest -q tests/browser/test_menu_labels.py tests/test_events_play.py`.
- **Whether the two panels survive the pack's own skin.** The menu body is
  skinned by the pack (`tests/browser/test_menu_labels.py:92-98` weaves the
  sample world with a skin), and no Lanternwake skin was inspected here.
