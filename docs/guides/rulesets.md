# Rulesets — how an act declares the game it plays

The engine is a host; an act's `ruleset` says which game happens inside
it. Rulesets are **pack data plus a screen in the player**; the engine
supplies the shared core (journal, vault, canon, prompts, weave) and
never gates the player on numbers unless the act's `floor` says so.

## The per-act law fields

| Field | Values | Meaning |
|---|---|---|
| `ruleset` | `ambient` (default) · `cooking` · `desk` · future | which screen + loop the act plays |
| `floor` | `costume` (default) · `story` · `stakes` | how hard numbers bite. `costume` = the classic vefr way: HP tracks, the player never drops to zero, the bar is a costume. `story`/`stakes` get their mechanics from future rulesets; until then they validate and wait |
| `tone` | `literal` · `warm` · `deadpan` · `ridiculous` · `absurd` | the act's position on the ridiculous-literal dial; rides in every generation prompt for the act |
| `verbs` | list of strings | the act's own action vocabulary; when declared it replaces the engine's costume verbs in the HUD and the `/api/combat/action` whitelist |
| `transitions` | list of doors | the act's doors between `regions` (below) |
| `cooking` | object | the cooking loop's content (below) |
| `desk` | object | the desk loop's content (below) |

All optional. Absent means the engine's defaults, so every existing pack
loads unchanged. `maplab.validate` shape-checks whatever is declared
(orders must reference real pantry ids; headlines must be at least two
non-empty strings; verbs/enemies/bosses must be lists of strings;
`transitions` is a list of doors and is checked against the regions'
maps - see below).

## cooking (Act 1's loop)

```json
"cooking": {
  "opening": "Day one after the quiet. The grill remembers heat.",
  "byline": "by the morning truck",
  "pantry": [{"id": "egg", "label": "fried egg"}],
  "tickets": [{
    "id": "t1", "customer": "the regular", "order": ["egg", "salsa"],
    "note": "The usual. Egg, and the red one that bites.",
    "thanks": "The regular eats standing up, already turning toward the day.",
    "kind_line": "The regular eats it anyway, nodding at something only they can see."
  }],
  "morning_length": 3,
  "headlines": ["FIRST TRUCK ON THE ROAD SERVES BREAKFAST AGAIN"]
}
```

The loop: tickets arrive as **spoken notes** (reading them is the game —
the order ids stay hidden); the player wraps from the pantry and serves;
resolution is deterministic set equality; a wrong order gets its
`kind_line` (a kind beat, never a slap); after `morning_length` tickets
the player picks a headline and page 1 of the paper prints (masthead,
headline, `byline`, an honest body from the journal, the pack creed,
"more mornings soon"). `sleep · wake again` resets the rail for volume 2.

## desk (Act 2's loop)

```json
"desk": {
  "opening": "The desk opens after the quiet.",
  "headlines": ["FIRST LIGHT OVER THE EMPTY MARKET",
                 "TRAVELERS REPORT SONG AT THE FLOODED CROSSING"]
}
```

The loop: whispers arrive carrying a hidden truth (the engine owns
truth; the model only proposes the whisper). The player judges each
whisper — trust it / doubt it — and the engine compares the verdict
against what it actually sent (`src/vefr/desk.py`, deterministic, no
model calls). Correct verdicts and printed headlines become **world
knowledge**, derived from the session journal on every read, and ride
into every later rumor and NPC line as `WHAT THE WORLD KNOWS NOW`.
Wrong verdicts are journal entries, never failure states. Live app
routes: `POST /api/desk/verify`, `POST /api/desk/print`,
`GET /api/desk/facts`; the single-file player runs the same loop
client-side against the baked pool's truth.

## library (books a world keeps)

Not an act loop: a pack-level shelf every ruleset can use. A pack may
carry `library/*.md`, one authored book per file:

```markdown
---
title: A Miner's Note
found: map        # shelf (default) | map | resident | earned
at: [7, 4]        # map: the tile it lies on (walkable), on a region drawn by hand
region: town      # map: the region it lies in (default town)
speaker: keeper   # resident: the act voice that hands it over
when: bell        # earned: bell | first-visit | act-complete | rumor-verified | book:<id>
kind: note        # book (default) | note | terminal
status: draft     # draft | approved (default: approved) - see Story status below
---
The first page.

* * *

The second page.
```

A line holding only `* * *` starts a new page. The author writes every
word; no model call touches a book. `maplab.validate` (and so `norns
validate`) checks every book: a title, non-empty pages, a known `found`,
a walkable `at` for map books, a real speaker for given books, a known
`when` (or an existing `book:<id>`) for earned books, lowercase-dash
file names. The loader carries them as `world["library"]`;
`GET /api/library` serves the current world's books plus the studio's
own shelf (`web/library/`, the game-making handbook); the workshop's
Library room reads them a page at a time (`web/js/library.js`); the book
export adds a "The Library" chapter. Finding books in play has landed in
the woven player: a map book is picked up on its tile, a resident hands
one over when you talk, and earned books unlock on `first-visit` or after
reading the `book:<id>` they name (`bell`, `act-complete` and
`rumor-verified` wait for events the player can see). The pause menu's
Books panel reopens anything found. Code: `src/vefr/library.py` +
`src/vefr/cli.py` (bake) + `web/packaged.html` (reader); tests:
`tests/test_library.py` + `tests/test_builder_weave.py` +
`tests/fixtures/make_library_pack.py`.

**Every map book names a region the pack has** (`vefr check` refuses one
that does not, with the regions it does have). A book can also lie on a
floor of the generated descent, named `<section>-<cycle>-<floor>`
(`cellar-0-3` is the third floor of the `cellar` Section, first cycle).
A generated floor is redrawn every run ("New descent") and whenever its
Section changes, so such a book names **where** on the floor to lie
instead of a tile. Starting a new run redraws floor one from a fresh
seed, and the stair in the town is rewired with it: going into the deep
lands the hero on that run's floor-one up-stair, never mid-floor.

```markdown
---
title: A Letter, Folded Small
found: map
region: cellar-0-1
place: near-up    # near-up | near-down (2 to 6 steps from that stair) | anywhere
chest: yes
---
```

The floor chooses the tile each run: reachable ground, off the stairs and
the monsters, one book per tile, from the floor's own `book|<id>` stream,
so a run always shows the book in the same place and a new run moves it
(`delve.place_books`, and `placeBooks` in the descent part, held equal by
`tests/test_pinned_books.py`). A fixed `at` on a generated floor is
refused, and `vefr check` proves every pinned book finds a tile in each
of 200 runs.

## delve (generated floors)

Not an act loop yet: a build-time tool that generates dungeon floors the
engine owns. `norns delve` draws a floor from a seed - rules only, no
model call, deterministic - and writes it as a region of the act, wiring
the stairs as transitions.

A region - generated or authored - may also carry `fog` in its
`contract.json`: `true`, or `{"radius": N}`, draws it dark until explored
(a lit circle around the hero, walked ground remembered dimmed, the rest
black). The Cottage floors use `{"radius": 4}`; a town omits it.

```sh
uv run norns delve --pack worlds/<name> --seed <text> --floors N \
    --from-region town --from-at 4,5 \
    [--width W] [--height H] [--rooms R] \
    [--first-name floor-2] [--force]
```

`--from-region` is an existing region and `--from-at x,y` is the
walkable tile there that the author placed as the down-stair; the command
refuses (non-zero) if that tile is not walkable. Each generated floor is
a directory (`acts/<id>/floor-2/`, `floor-3/`, ...) carrying a `map.md`
and a `contract.json`. Numbering continues after the pack's existing
`floor-*` regions unless `--first-name` names the start. The last floor
generated is the bottom for now and keeps no down-stair; the output says
so. An existing generated region is refused unless `--force`; nothing
outside the pack is ever written.

The stairs wire as doors: the `from-region`'s stair goes down to the
first floor's `u`; each floor's `d` goes to the next floor's `u`; every
floor's `u` climbs back to the previous floor's `d` (or to
`from-region`/`from-at` for the first). The act's `regions` gains the new
names at the end - the first region stays first - and `start` and the
existing regions are untouched.

A generated map uses one shared legend (`src/vefr/delve.py`):

| char | meaning | tile |
|---|---|---|
| `#` | solid wall | `dungeon-wall` |
| `.` | floor | `dungeon-floor` |
| `u` | up-stair | `dungeon-stairs-up` |
| `d` | down-stair | `dungeon-stairs-down` |

`generate_floor(seed, width=30, height=20, rooms=8)` draws rectangular
rooms joined by L-corridors, keeps a solid border, and guarantees one
connected cave with the two stairs reachable from each other and far
apart (at least `MIN_STAIR_DISTANCE` Manhattan tiles when the layout
allows; it relaxes to the widest pair otherwise). `delve.contract(...)`
writes the region `contract.json`.

Known limits (this slice): floors are generated once, at build time,
from a seed and then baked into the pack - per-playthrough generation is
a later slice. Only the first region's full geometry is validated today;
the generated floors are checked by the door rules (see
"regions + transitions" below). Code: `src/vefr/delve.py` +
`src/vefr/cli.py` (`cmd_delve`); tests: `tests/test_delve.py`.

### delve --section (a whole Section)

`--section <id>` bakes a Section instead of N floors. Everything above it
still applies - the pack, the act, `--from-region`, `--from-at`,
`--seed`, `--force` - and the floors come out of the pack's
`sections/<id>.json` rather than out of `--width`/`--height`/`--rooms`:

```sh
uv run norns delve --pack worlds/<name> --seed <text> \
    --section cellar --from-region town --from-at 4,5
```

One region per floor, named `<section id>-<k>`, drawn by the v3 generator
(`src/vefr/delve_v3.py`) at the size and the floor kind the Section's own
pattern asks for. Each floor is drawn from the key
`run_seed/section.id/cycle/k`, which is what keeps two ordinary floors of
one Section from being the same map.

The wiring is the elevator rule. The `from-region`'s stair goes down
into floor 1; each floor's down-stair goes to the floor below; the last
floor is the bottom and keeps no down-stair. Every floor's up-stair
climbs back to the floor above it, except on a **landing** - a Section's
first floor and its fifth - where it goes straight back to `from-region`
instead.

Each written `contract.json` carries four keys a generated floor did not
have before, all additive: `section`, `k`, `floor_kind` and `landing`,
beside the `floor_key` the floor was drawn from. Otherwise it is the
shape `delve.contract` has always written.

A Section's own shape is checked by `vefr check` (`src/vefr/shapes.py`),
and every floor of every Section is swept over 200 seeds there too: one
component, and every anchor, point of interest, secret, monster and
chest reachable from the up-stair. Code: `src/vefr/sections.py`,
`src/vefr/locks.py` (`section_findings`), `src/vefr/cli.py`
(`_bake_section`); tests: `tests/test_sections_e4.py`.

A Section names its families by id and carries no record of one of its
own, so what a monster on a generated floor carries is exactly what
`drops` in its Blueprint family names (`delve.mobs_at`, one id off that
monster's own loot stream). `vefr check` reads those ids by the same
rule every other `drops` is read by (above): a family naming an id the
pack's `world.json` cannot describe with a `name` is one sentence at
`/families/<n>/family` naming the Section, the family and the empty kill,
because that monster would be killed for nothing on any floor. A family
that names no drops at all is fine - most of them do.

A Section's `fog` is how far it sees: `{"radius": N}`, a whole number
from 2 to 32, and the lit area around the arrival tile is a disc `N`
tiles in radius. The ceiling is a quarter of the widest floor `size`
allows (`size.w` tops out at 128), so a Section says its sight as a
fraction of the floor it declares rather than against a fixed number -
read it at the table as `shapes.FOG_RADIUS_MAX`, which is `SIZE`'s
largest `w` over four. A Section that leaves `fog` out gets the engine's
default (5) and plays exactly as before; this range bounds what a pack
may ask for, and changes nothing a pack left out.

The lit area is a disc unless the Section names what to draw:
`{"radius": 4, "shape": "square"}` lights every tile within `radius`
steps on each axis instead of by straight line, which holds every tile
the disc holds and reaches about 41% further at the corners - a floor of
rooms lit like a floor of rooms. `"circle"` is the default and is not a
second spelling of it: a Section that leaves `shape` out and one that
writes `"circle"` produce the same floor record, the same save and the
same digest, because the shape rides along in a floor's `fog` block only
when it is the square (Rylee picked the square on 2026-10-09, #364).
Anything else is refused by name: `section.fog.shape must be "circle" or
"square", not 'triangle'`. A hand-written region's `contract.json` may
say the same `shape` and the player draws it, though the validator pins
only the Section's block. Whether sight should grow with what the hero
has seen is still #364's open question, and is not this table's.

A Section's `tiles` is the ground its own floors are drawn with, and its
families' `depth` ranges are the floors of that Section they live on. Both
reach the player: a floor's plan carries its own Section's legend, the weave
resolves each Section's `tiles` into pictures keyed by Section id, and a
family written `"depth": [7, 9]` spawns on the last three floors of that
Section, counted from that Section's own first floor rather than the
descent's global depth. Only a glyph the generator already draws is
overridden, and only its `tile` - the base colours and the solid flag are the
engine's, because a floor that walked through its own wall would be a
different generator. A Section that names no `tiles` draws exactly what it
drew before, so a pack with no `tiles` anywhere is unchanged.

Of the keys `shapes.SECTION` validates, these reach the play-time descent:
`id`, `floors`, `size`, `rooms`, `tiles`, `fog`, `families`, `pattern`,
`specials`, `stamps`, `warden` and `vault`. The rest **are validated but
not read at play**, and the shape says so on each one rather than letting
them look live:

| key | what would read it |
| --- | --- |
| `section` | nothing yet - list Sections in the order you want the descent to walk them, and this number may disagree with that list without anything changing |
| `elites` | slice E7 (hands the pop stage's elites to the floor plan); until then `vefr check` sweeps every floor and measures elites the plan will never draw |
| `groups` | slice E7, the same way it hands over the elites |
| `curve` | slice E10 (scales monster stats at play); today only the balance report reads it, and a monster draws at its Blueprint's own numbers |
| `loot` | slice E10 (caps the loot tier by depth); nothing reads it today, and a monster draws one drop from its own family's `drops` |
| `pois` | slice E6 (puts a floor's points of interest in front of the player); today the v3 stage names them and the floor plan drops them |

`vefr check` also names a Section that asks for a tileset no picture exists
for - one in the pack's `tiles/` or the engine's - because such a floor
falls back to the glyph's own colour instead of failing.

### story_end: the flag a pack's story ends on

A pack's `descent` block may name `"story_end"`:

```json
{"run_seed": "ember", "entry": {"region": "town", "at": [7, 5]},
 "sections": ["cellar"], "story_end": "the-quiet-room-is-reached"}
```

It is the flag whose being true ends the story and opens the endless
board, and its default is `king-slain` - which is what a final boss
behind its own door sets. A pack that ends without a final boss names its
own flag and sets it with any rule (for example on `enters` a last region
reached through the final vault's door). Every place the descent asks
"has the story ended?" reads this name, and `vefr check`'s progress walk
asks it at the end.

### town_states: the regions that change with the story

A pack names the regions whose look follows a story flag - the town, an
interior such as a tavern or a home. One block per region, or a list of
them:

```json
"town_states": [
  {"region": "town", "states": [
    {"id": "act-2", "when": "vault-1-read", "use": "town-act-2"},
    {"id": "after-the-end", "when": "king-slain", "use": "town-after"}]},
  {"region": "tavern", "states": [
    {"id": "full", "when": "vault-1-read", "use": "tavern"}]}
]
```

The single block ADR 0015 wrote first is still valid and means exactly
what it says; the list is one block per region.

- **`use` is an ordinary authored region.** Bake it like any other region
  of the act - a `map.md` and a `contract.json` under `acts/<id>/`. There
  is no patch and no new runtime language: `vefr check` refuses a `use` or
  a `region` the pack does not declare.
- **The last true state wins.** On entering the region the engine loads
  the **last** state whose `when` flag reads true, else the region's own
  base. Write the states oldest first.
- **Derived on entry, never stored.** There is no pointer to go stale:
  the same flags always give the same answer, and a flag never set can
  never have left a state behind.
- **All of a region's states share that region's save.** `enters` fires
  for the region the author named (`town`), not for the face of it the
  player landed on, and the region's fog, dropped items and journal
  entry are the region's. A dropped item that is standing on a wall in
  the state being loaded moves to the nearest floor tile, scanning
  row-major - so it never becomes something the player cannot pick up.
- **The act** is one plus the number of vault notes read. It is a derived
  read like everything else here.

### the vault, the warden and the town gate

A Section's `warden` is a family id, or a record
`{"family", "id"?, "carries"?, "challenge"?, "yields"?, "fightable"?}`. Its
`vault` is a stamp id, or a record `{"stamp", "sets"}`:

```json
{"id": "cellar", "floors": 9,
 "warden": {"family": "cellar-king", "id": "ashwing", "carries": "ashwing-key"},
 "vault": {"stamp": "vault-small", "sets": "vault-1-read"}}
```

The warden stands on the warden floor - the pattern's `warden` slot - on
the floor's warden anchor, as monster `w`. Defeating it puts `carries`
**straight into the bag** and sets `warden:<id>:c<c>`, which keeps it
beaten through town returns, identity mismatches and evictions. Its
vault's single `+` is a door that is shut until that flag is set; the
`note`, `chest` and `home` anchors hold the note, the loot and the stair
home. `sets` is the flag the vault's **note** records - set it with a
rule on the note's `opens` - and it is what the town gate is guarded by:

```json
{"id": "the-first-note-is-read",
 "when": {"opens": {"what": "the-first-note"}},
 "then": [{"set": "vault-1-read"}], "once": true}
```

Three optional keys say how this particular warden is passed, and every
one of them defaults to what the two lines above already do - so a pack
that names none of them plays exactly as it did:

- **`"challenge": "rule"`** - a pack rule sets `warden:<id>:c<c>` instead
  (on `picks-up`, `uses-with`, `comes-near` or any other event), and the
  key it `carries` goes into the bag **the moment that flag is set**,
  with a line, the same as on death. Killing such a warden passes
  nothing: the flag is the rule's to set. The vault door, the town gate
  and the save rules read only the flag, so none of them change.
- **`"yields": true`** - a beaten warden stays on its anchor, no longer
  hostile, instead of vanishing. It is drawn in a muted colour and it
  comes back the same way when the floor is rebuilt.
- **`"fightable": false`** - only with `"challenge": "rule"`, and only
  beside it: a warden that cannot be struck is one no rule can complete,
  so `vefr check` refuses the pair in one sentence. Everything else
  about it is unchanged - it still sleeps, wakes and hunts by ADR 0014,
  so the hall stays dangerous and the Section's danger still rises.

```json
{"id": "cellar", "floors": 9,
 "warden": {"family": "cellar-king", "id": "ashwing",
            "carries": "ashwing-key", "challenge": "rule"},
 "vault": {"stamp": "vault-small", "sets": "vault-1-read"}}
```

The gate itself is never written by a pack. A Section whose vault names a
`sets` flag is gated on `town-seen:<section>:c<c>`: the Section expansion
puts `requires: {"flag": "town-seen:..."}` on the warden's down stair (and
on any town stair that enters a Section), and a rule on `enters <the
descent's entry region>` sets the flag once that Section's note has been
read. Both are ordinary `requires` locks - the one gate mechanism - and
`lockOpen` reads the story flag out of the descent's own save. A Section
whose `vault` is the bare stamp id names no flag and gates nothing.

The stair that leads past the last Section into endless cycle 1 is the one
stair that does not take the town gate: it requires the pack's `story_end`
flag (default `king-slain`) and says so while it is shut.

### the progress walk (`vefr check`)

`vefr check` walks every Section's story before it sweeps its floors: a
**flag-only simulation** that starts with no flags at all and repeats
three steps per Section - complete the warden's challenge (set its flag),
read the note, enter town - and asks at the end whether the pack's story
end is reached. No floor is drawn, no rule fires, and the answer is the
same sentence every time. It lives in `vefr.locks.progress_findings` and
runs inside `section_findings`, so it is part of the same 200-seed gate.

A Section ends its story on its vault's `sets` flag, so name the **last**
one the same flag the descent ends on. A pack that ends without a final
boss sets `story_end` with any rule instead.

A warden's first step is its **challenge**, not its killing: a `defeat`
warden is beaten by the walk, and a `rule` warden is completed by the
rule that sets its flag - so a `rule` warden with no such rule is one
sentence, the same missing setter a vault note's flag is.

Code: `src/vefr/delve.py` (`warden_of`, `warden_challenge`, `warden_yields`,
`warden_fightable`, `vault_of`, `town_seen_flag`, `story_end_of`,
`act_number`), `src/vefr/locks.py` (`progress_findings`),
`web/player/parts/397-the-descent.js` (the Section expansion that emits
the gate and the `enters town` rule, and `challengeSet`, the one seam a
rule's `set` asks);
tests: `tests/test_wardens.py`, `tests/test_warden_challenge.py`,
`tests/test_vault_door.py`, `tests/test_vault_contents.py`,
`tests/test_town_states.py`, `tests/test_progress_walk.py`,
`tests/test_descent_story_end.py`.

### the Section contract: what a Section may hold

The keys a Section pack (`sections/<id>.json`) may hold, in the order
`src/vefr/shapes.py` reads them. Only `id` and `families` are required;
everything else defaults, and a Section that names none of it is the
floor it always was. `vefr check` refuses a key that is not on this list,
and refuses every value below at the pointer that names it.

| key | what it is | default |
|---|---|---|
| `section` | the Section's number in the descent order | unordered |
| `id` | **required** - the floor key's middle | - |
| `label` | the name a player sees, 1 to 40 characters; the floor key, region and save keys never read it | the id |
| `floors` | how many floors it has | 9 |
| `size` | `{"w": [lo, hi], "h": [lo, hi]}` - every floor draws its own | w 64, h 48 |
| `rooms` | the `[lo, hi]` room quota a floor draws | 12 |
| `tiles` | the tile table: glyph to tileset | engine legend |
| `fog` | `{"radius": N}` | radius 5 |
| `families` | **required** - the families a floor draws from, with weights | - |
| `pattern` | one slot per floor: `entry`, `n`, `special`, `landing`, `warden` | the nine-floor pattern |
| `specials` | what a `special` slot may draw: `treasure`, `infested`, `hub` | all three |
| `elites` | `{"per_floor": [lo, hi], "affixes": [ids]}` | none |
| `groups` | `{"per_floor": [lo, hi], "minions": [lo, hi], "leader", "same_family", "wake", "leash"}` | none |
| `mobs` | **how many monsters a floor carries** - see below | the area budget |
| `curve` | `{"hp": [lo, hi], "atk": [lo, hi]}` - the depth multipliers | flat (1.0) |
| `loot` | `{"tier": N}` - checked, not yet read (E10) | - |
| `stamps` | the stamp ids this Section may use | none |
| `pois` | the point-of-interest names its floors carry | none |
| `warden` | a family id, or `{"family", "id", "carries"}` | no warden |
| `vault` | the vault stamp's id | no vault |
| `endless` | `{"omens": [{"id", "label", one of `fog_radius`/`groups_per_floor`/`warden_affixes`}], "picks": N}` - the omens an endless descent offers | no omens |

**`mobs` - how many monsters a floor carries.** Without it the count is
area policy: one monster per 30 walkable tiles, clamped into 4..36, which
put 20-35 monsters on a first floor no pack could argue with. With it the
pack decides, per depth:

```json
"mobs": {"1": 4, "from": 12}
```

A key is a floor of the Section (`"1"` is its first floor) or `"from"`,
which is the count every floor the table does not name carries. So the
example is four monsters on the floor a hero comes down to and twelve on
every floor after it - gentle at the top, rising from there, without
redrawing anything. `0` is a floor with nothing on it, which the area
budget could never say. A count is 0 to 36 (ADR 0014's hard cap), and
`vefr check` refuses anything else, naming the Section and the entry:

```
sections/cellar.json: /section/mobs/1 section.mobs['1'] must be between 0 and 36
```

It costs no draw, and it moves no tile: the `size`, `plan` and `layout`
streams do not read it, so a pack that sets a count on a Section it has
already placed things on by coordinate invalidates nothing it placed. Only
the **pop** stream moves - which is the one place the count is used, and
the reason a floor's monsters and chests are the only things about a floor
that differ once the key is set. Both the v3 generator
(`delve_v3.mob_budget`) and the play-time descent
(`delve.floor_plan`, the `mobs` list the player walks) read it, and the
JavaScript twins in `web/player/parts/396-` and `397-` read the same
table through the same rule. Code: `src/vefr/sections.py`
(`mob_count`), `src/vefr/delve_v3.py` (`mob_budget`); tests:
`tests/test_section_monster_count.py`.

A family row may carry an optional `xp`: the experience one kill of that
family pays, on every floor it stands on. A row that leaves it out is
not worth nothing - it takes the engine's default, which starts at 1 on
the first floor of the descent and rises 2 a floor below that, so a
deeper Section pays more (`vefr.sections.xp_for`, and its JavaScript
twin). A kill on a generated floor therefore pays exactly as an
authored region's kill does, and the `level` cue fires on the same
words. `vefr check` refuses a bad `xp` with a sentence naming the
Section and the family.

## regions + transitions (doors between maps)

An act may declare several `regions`, each its own directory under
`acts/<id>/`: a `map.md`, a `contract.json` (legend, pois, poi_text,
hero_start, sanctuary_tiles, watch, water_by_phase, flood_tiles, tile,
bg and the colours), and `voices/` + `sprites/`. The first region is
the act's home map.

A `transition` is a door from one region to another - an **entry
room** inside a building, or a floor below:

```json
"transitions": [
  {"from": "town", "at": [4, 5], "to": "cottage", "to_at": [4, 3]}
]
```

`at` is the tile the door stands on in `from`; `to_at` is where the hero
lands in `to`. A door is **used, not walked through**: the hero stands
on or faces the door tile and presses Interact (the button says "Go
through the door"), and passing a doorway never yanks the hero to
another map. Interact is the one canonical interaction path - the
same verb that opens a chest or a trade. A speaker
may carry `"region": "<region name>"`; a speaker with no `region`
belongs to the act's first region. Each loaded region carries its own
`speakers` dict (the act's speakers filtered to that region); the
act's `speakers` keeps all of them.

The woven player honours both: `weave_html` bakes `window.VEFR_REGIONS`
(one entry per region, from its `map_text` + contract),
`window.VEFR_TRANSITIONS` (the act's doors, verbatim), and
`window.VEFR_SPEAKERS` (the act's speakers grouped by region), and
`web/packaged.html` reassigns the current map, people and hero when a
door is crossed. A single-region pack with no transitions bakes one
region and behaves exactly as before. `maplab.validate` checks every
door: `from`/`to` name declared regions, and `at`/`to_at` are inside
their maps and walkable in their legends.

### A ground that blends: a legend's `edges`

Where one ground meets another (grass and a dirt lane, grass and cobbles)
the edge is a hard square, one tile at a time. A legend entry may ask for
a blend with `edges`, naming ONE picture in the region's own `tiles/`:

```json
"legend": {
  ".": {"tile": "grass"},
  "p": {"tile": "lane", "edges": "lane-edges"}
}
```

`tiles/lane-edges.webp` (or `.png`) is a 4 x 4 sheet of sixteen equal
pieces. The player draws one piece over every `p` tile, chosen by which of
its four neighbours are ALSO `p`: north 1, east 2, south 4, west 8, added
up. Piece `mask` sits at column `mask % 4`, row `mask // 4`, reading left
to right, top to bottom:

| row | pieces (same-symbol neighbours) |
|---|---|
| 0 | 0 none, 1 N, 2 E, 3 N+E |
| 1 | 4 S, 5 N+S, 6 E+S, 7 N+E+S |
| 2 | 8 W, 9 N+W, 10 E+W, 11 N+E+W |
| 3 | 12 S+W, 13 N+S+W, 14 E+S+W, 15 all four |

A piece is transparent except where the neighbouring ground creeps in, on
the sides whose bit is NOT set (piece 4 is a lane tile with grass on its
north, east and west). Piece 15 is never drawn, so leave it empty. A
neighbour past the map's edge counts as the same, so the map's border
draws no seam. Edges come from the pack only (the engine set has none),
and a symbol that names no `edges` draws exactly as before.

`vefr check` refuses an `edges` value that is not a plain picture name, a
name with no picture in the region's `tiles/`, and a name with variants
or a grid picture, each in a sentence naming the region and the symbol.
Code: `cli._edges_for_legend` (the bake, `window.VEFR_TILE_EDGES`),
`edgeMask` in `web/player/parts/440-the-camera.js`, `maplab._edge_errors`;
tests: `tests/test_tile_edges.py`, `tests/browser/test_tile_edges.py`.

### One tile, one way out: the descent's entry

A pack's optional `descent` block names the tile the generated floors
are entered from: `"entry": {"region": "town", "at": [7, 5]}`. That
entry is a door like any other, so **it cannot stand on a tile an act
transition already uses.** `vefr check` refuses the pack, in one
sentence that names the tile and both ends of the door:

```
FAIL: world.json: descent.entry.at [7, 5] is the door from 'town' to
'shed': the descent entry and an authored transition cannot share a
tile, so move one of them
```

The check reads every act's doors, not just the first act's: an entry
tile is a pack-level fact, so a door on it in any act is the same
collision. Move the authored door or the entry - either is the fix.

In play, the descent entry takes its tile: the entry is the pack's
declared, checked way down, so it is the door that answers Interact
there, and a pack that was woven anyway leads into the dungeon rather
than past it (`claimTile` in the descent part). Every other door in the
pack is untouched, and a pack with no collision plays exactly as it did
before. Tests: `tests/test_descent_entry_collision.py`.

### Landings: the way home from deep floors

Floors generated during play use the same elevator rule as
`delve --section` (above). A **landing** is a floor whose `pattern` slot
is `entry` or `landing`. Its up-stair goes straight to the descent's
entry, which is `descent.entry.region` at `descent.entry.at`. It does not
go to the floor above. With the default nine-floor pattern, a Section's
first and fifth floors are landings. This is also true in later cycles,
so a hero who is many floors down can get to town from the nearest
landing above them.

The player keeps each landing it reaches in the save as
`flags.landing`, a sorted list of depths. That list stays the same after
a reload. Floor 1 still climbs to the entry. If a Section's `pattern`
has no `entry` or `landing` slot, each of its floors climbs to the floor
above, as before. The rule has no new key, so `vefr check` and
`norns validate` read a pack the same way as before. The player's
`isLanding` is the twin of `sections.is_landing`. Tests:
`tests/test_descent_landings.py` and
`tests/browser/test_landing_home.py`.

### Locked doors

A door or stair may be locked behind a key. A transition may carry an
optional `requires` (a key item, or a flag) and an optional one-sentence
`locked_text`:

```json
"transitions": [
  {"from": "town", "at": [4, 5], "to": "cottage", "to_at": [4, 3],
   "requires": {"item": "brass-ring"},
   "locked_text": "The door is shut. The ring turns it."}
]
```

`requires` holds **exactly one** of `item` (an id in the pack's `items`
catalog) or `flag` (a declared flag name). Interact on the locked door
without it says `locked_text`, or "It will not open yet." when absent, and
the hero stays put - no `opens`, no arrival. With the item in the bag, or
the flag set, the door opens as it always did. **A key is never consumed:**
it stays in the bag whether or not the item is a kept thing.

A flag lock only survives a reload when the pack uses `saves.rules:
persist` (ADR 0009); otherwise the rule that sets the flag runs again on
the next load, as before. A transition with no `requires` behaves exactly
as today. `maplab.validate` names a `requires` that is not an object with
exactly one `item`/`flag`, points at an unknown item or flag, or carries
an unknown key, and a `locked_text` that is not one plain sentence of 1
to 200 characters (design/gates-and-guardians.md).

`vefr check` now follows the locks from the start region and names a
key that cannot be obtained before its door.

Known gap (this slice): only the **first** region's full geometry is
validated today (rectangular map, reachable tiles, pois, sanctuary,
water). Other regions' maps are read only for the door checks; their
own geometry validation is a follow-on.

## combat (first slice: bump to fight)

The dungeon has floors, fog, doors and stairs; this is the first thing
in them that moves on its own. Combat is **deterministic** - fixed
numbers, no randomness, no clock, no model calls - and **Cozy**: going
down never ends a story.

A pack's `world.json` may give the hero its own numbers and a wake
point:

```json
"player": {"hp": 6, "atk": 2,
           "wake": {"region": "town", "at": [11, 11]}}
```

`hp`/`atk` default to 6/2. `wake` is where Cozy death wakes the hero
(a floor of the descent answers for itself instead - see "Cozy death"
below); it defaults to the act's first region at its `hero_start`. A `wake`
that names no real region is dropped, and one on a missing or solid
tile falls back to that region's `hero_start` - the baked point is
always real.

A region's `contract.json` may carry `enemies`, one named hazard each:

```json
"enemies": [{"id": "cellar-rat", "name": "a cellar rat",
             "at": [12, 9], "hp": 4, "atk": 1, "sprite": "rat"}]
```

`id` is unique within the region; `at` is a walkable tile; `hp`/`atk`
are positive ints; `sprite` is optional and names an entry in the
pack's `player.sprites` (the same map the hero and speakers use). No
`sprite` draws the same body-and-head figure a speaker gets, in a
hostile colour. `sight` is optional (default 6) and is Manhattan
distance.

**The turn.** Every *successful* move (a step, or a bump attack) is
followed by one turn for each living enemy of the region. A monster
walks the floor, not a straight line: at the start of the turn the
walkable tiles are flooded once, breadth-first, from the hero (and, for
a monster that cannot see the hero, from the monster it is drifting
toward), and each monster steps to the neighbour closest to - or
furthest from - that flood. Walls, corners and rooms are therefore
walked round rather than into.

- adjacent (Manhattan distance 1) -> it attacks: hero hp drops by its
  `atk`, clamped at zero.
- else within `sight`, and hurt to a third of the `hp` it walked into
  the region with -> it steps one tile *away*: the neighbour furthest
  from the hero down the map.
- else within `sight` -> it steps one tile toward the hero, the short
  way round.
- else (out of sight) -> if another monster is alive it steps toward
  the nearest one, so a pack stays a pack; alone, it holds still.

A step never lands on a solid tile, another living monster, or the
hero - a step that would land on the hero attacks instead. Ties go to
a fixed neighbour order (up, down, left, right), so the same floor
always plays out the same way. There is no randomness and no clock
anywhere in the movement.

**Bump to attack.** Walking into a living enemy does not move the
hero; the hero strikes it instead for `hero.atk`. A killed enemy is
remembered per region, per world (`vefr-slain-<world>-<region>` in the
player's storage), so a cleared room stays cleared; a wounded one
resets when the page reloads.

**Cozy death.** At zero hp the hero is restored to `hp`, one plain
line is shown ("You wake in the temple. You lost nothing that
mattered."), and the hero wakes at `wake`. Nothing is lost.

A floor of the descent is the one place `wake` does not answer: a death
there wakes the hero on that same floor, at its up-stair and whole, with
the descent still around them - the kills, the drops, the bag and the
stairs are the ones they left. The why-log names the floor they resumed
on. Every other region, the town and a baked one included, wakes at
`wake` exactly as before.

The line names the place too, so it says the stair on a descent floor
("You wake at the foot of the stair, whole again. You lost nothing that
mattered.") and the temple everywhere else. Both lines are the player's
own; a pack can word either.

The HUD's health line shows the hero's real `hp/max`; a small
`aria-live` line speaks each hit. Baked per region (`VEFR_ENEMIES`)
and once for the hero (`VEFR_HERO`).

Known gaps (this slice): no fleeing, no
rooms-and-corridors AI (enemies only step and hit), no randomness, and
only a move is a turn - a hero can stand still safely. Classic death
is a later slice. Loot - what a kill leaves and a bag holds - is the
next slice (see "loot" below).

`maplab.validate` checks the region `enemies` shape: a unique id, a
name, a walkable `at`, and positive int `hp`/`atk`; a broken one is
named in plain words. Code: `src/vefr/maplab.py` (validation) +
`src/vefr/cli.py` (bake) + `web/packaged.html` (the turn); tests:
`tests/test_combat_loop.py` + `tests/test_transitions.py` +
`tests/test_builder_weave.py` + `tests/fixtures/make_combat_pack.py`.

## loot (first slice: drops and a simple bag)

Killing something used to give survival and nothing else. Now a kill can
leave a thing behind, the hero can carry it, and a Bag panel shows what
is held. It is deliberately small: no weight, no grids, no identifying,
and no using or selling. Deterministic like the rest - fixed ids, no
randomness, no model call.

(That sentence still governs the ids. Since ADR 0017 a drop may also draw
a **rarity** and some **hidden traits**, both off a named seeded stream
off the same floor key and monster - deterministic in exactly the way
every other draw here is, the same seed always dropping the same potion
at the same rarity. See "rolled loot" below.)

A pack's `world.json` may carry an `items` catalog (optional), keyed by
id:

```json
"items": {
  "cloudy-potion": {"name": "a cloudy potion", "sprite": "potion"},
  "brass-ring":    {"name": "a plain brass ring", "sprite": "ring"}
}
```

`name` is plain words, shown in the bag. `sprite` names an entry in the
pack's `player.sprites` (the same map the hero and speakers use) and is
optional; with none the marker falls back to a small neutral dot. An
entry with no name is dropped from what is baked, and a drop naming a
missing item is dropped too - the player never meets a thing the world
cannot describe.

A region's enemy may carry `drops`, a list of catalog ids:

```json
{"id": "cellar-rat", "name": "a cellar rat", "at": [2, 1],
 "hp": 4, "atk": 1, "sprite": "rat", "drops": ["cloudy-potion"]}
```

A chest book (`chest: yes` in its front matter) may also hold items:
`drops: cloudy-potion, brass-ring` - a comma-separated list of catalog
ids, read from `extra` like `chest` already is.

**A `drops` line that pays nothing is refused.** `vefr check` reads a
chest's `drops` - and an enemy's, and a Blueprint family's - against the
catalog, because the bag refuses an id the catalog does not hold. An
`items` entry with no `name` is no item: `weave` drops it from the catalog
it bakes (`cli._player_items`), and a pack with no `items` at all declares
none, so every drop check runs and every drop fails.

One rule reads all of them, `library._drop_payout_errors`. A `drops` line
that names no id at all is refused, and so is any id the catalog does not
answer for, named one by one. A thing that writes **no `drops` line at
all** is left alone: a chest holds its note and nothing else, a monster
carrying nothing is a legitimate monster, and most Section families name
no drops. Only a line that is written and pays nothing is refused.

An enemy's `drops` is refused by `maplab._enemy_drop_errors`, beside it,
and says the same thing in the same words.

**The drop.** A killed enemy's drops are left on the tile it died on, as
a small item marker (the item's sprite, or a dot). Fog rules apply: a
drop is drawn only where the light reaches. **Walking onto a drop takes
it**: it leaves the floor, one plain line says so ("You pick up a cloudy
potion."), and a small sprite appears in the HUD where the health bar is.
The floor is remembered per world (`vefr-floor-<world>`), so leaving and
coming back is honest about what is still lying there. **The bag** is a
list of item ids at `localStorage['vefr-bag-<world>']`; a duplicate id is
still added - two potions are two potions. The pause menu's Bag panel
(next to Journal and Books) lists what is carried, one row per thing,
sprite and name; empty it says "Nothing yet.". Opening a chest still
gives its note, and also gives any items its `drops` names, with one
line.

Baked as `VEFR_ITEMS` (the catalog), a `drops` list on each enemy and
each book. Code: `src/vefr/cli.py` (`_player_items`, `_drop_ids`) +
`web/packaged.html` (floor, take, bag panel, HUD strip); tests:
`tests/test_builder_weave.py` + `tests/test_combat_loop.py` +
`tests/fixtures/combat_harness.mjs` + `tests/fixtures/make_combat_pack.py`;
the refused-drop check is `tests/test_empty_enemy_drops.py` +
`tests/fixtures/make_empty_drops_pack.py`.

Known gaps (this slice): no weight, no using, no dropping, no selling,
and no identifying - a carried thing is only a name and a picture for
now. `maplab.validate` does not yet pin the `items` shape; the bake drops
an unknown id instead, and a `drops` line that resolves to nothing is
refused rather than dropped quietly (above). The bag has no size limit
unless a pack names one (see bag capacity, below).

## rolled loot (first slice: rarity at once, traits hidden)

ADR 0017. A drop on a generated floor now yields a base item **and** a
rarity, and the bag says both together the moment it is picked up
("a cloudy potion (uncommon)"). An item may also carry traits, which
stay hidden until the thing has been read at a reader (see identify,
below): nothing renders them, and nothing identifies them.

Three optional keys on an `items` entry, all additive - a catalog that
names none of them bakes and drops exactly what it always did:

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

- `rarity` is one plain word - one of the names **this item's own
  `roll.rarity` declares** when it has a roll, or its fixed rarity when
  it does not. The names are the pack's: there is no closed list and no
  order the engine imposes.
- `traits` is a list of plain words, fixed when there is no `roll`.
- `roll.rarity` is the table and the weights (whole numbers);
  `roll.traits` is the pool; `chance` (0..100, default 100) is how often
  a draw bears a trait at all; `max` (0..4, default 1) is how many at
  once.

**The draw.** On a generated floor the base id is drawn from the
monster's own loot stream exactly as before, and the rarity and traits
from a second named stream off the same floor key and monster:
`v3|<floor key>|roll|<mob id>|<item id>`. Same seed, same potion at the
same rarity, every time; two monsters never share a roll; the base id
cannot move when a roll is added. A drop with no stream to seed it - a
town enemy, a chest, a rule - carries the item's fixed rarity and traits
and draws nothing.

**What the bag holds.** An entry is either a bare id (every bag before
this slice, and every bag of a pack that declares no `roll`) or the
instance a rolled drop left behind: `{"id": …, "rarity": …, "traits":
[…], "identified": false}`. The traits are read and printed nowhere
until the thing has been read at a reader (see identify, below).

**`vefr check` refuses four things,** one plain sentence each: a
`rarity` outside the item's own table, a trait that is not one plain
word, a `roll` with no rarity table, and a `roll` that asks for traits
and names no pool. A refused roll draws nothing at all rather than half
a roll.

Code: `src/vefr/shapes.py` (`ITEM`, `ROLL`, `check_item`) +
`src/vefr/maplab.py` (`item_roll_of`, `item_roll_errors`) +
`src/vefr/delve.py` (`roll_seed`, `item_draw`, `mob_drops`) +
`src/vefr/cli.py` (`_player_items`) + `web/player/parts/` (the bag, the
strip, the drop). Tests: `tests/test_rolled_loot.py` (shape, refusals,
determinism, compatibility) + `tests/test_rolled_loot_play.py` (the bag
in the real player) + `tests/test_descent_parity.py` (the same floor in
both languages) + `tests/fixtures/make_rolled_pack.py`.

Known gaps of this slice, since narrowed by identify and bag capacity
(below): no identifying (nothing set `identified` true), no reveal moment
beyond the rarity simply being there, no idea yet what a trait *does*,
and no rolled drops anywhere but a generated floor's monsters.

## identify (second slice: the town reads a thing)

ADR 0017, slice 2. One optional flag on one speaker:

```json
"speakers": {
  "reader": {"name": "The Reader", "at": [6, 4], "identify": "true"}
}
```

`true` (also `yes`/`1`, or the boolean) makes that speaker the reader of
its region - the same kind of flag `shop` is, read the same way. Stand
beside them, press Interact, and an Identify panel lists what the hero
carries that has not been read; reading one sets `identified: true` on
that instance in `localStorage['vefr-bag-<world>']` and writes the bag
back. Nothing else is written: the rarity and the traits are the ones
the drop drew, so reading the same thing twice gives the same words
twice, and a save written before this slice still reads.

Once read, the traits are named in the bag row and in the HUD strip's
`aria-label` - in text, in the same call as the click, with no timer and
no animation anywhere in the path, so with reduced motion the words are
there on the first frame. Before a read they are in no part of the page.

No model call, no second draw, no clock, and no way to charge for a read.
The flag rides the speaker the weave already inlines, so a pack that
names no reader bakes every `VEFR_*` data line exactly as before.

**`vefr check` refuses three things,** one plain sentence each: an
`identify` naming some other service, an `identify` that is not the word
true (an object could carry a chance, a roll or a model), and a speaker
that offers identify in a region the pack does not have.

Code: `src/vefr/maplab.py` (`identifies`, `identify_errors`) +
`web/player/parts/195-the-identify-service.js` and the one line of
`180-gold.js` that names a read thing's traits. Tests:
`tests/test_identify.py` + `tests/test_identify_play.py` +
`tests/fixtures/make_identify_pack.py`.

Known gaps of this slice, since narrowed by bag capacity (below): no cost
for a read, and still no answer to what a trait *does*.

## bag capacity (third slice: a bag with a size)

ADR 0017, amendment 1. The bag is unbounded unless a pack names a size.
Two optional fields:

```json
"bag": {"size": 6},
"items": {
  "satchel-1": {"name": "a leather satchel", "sprite": "cloak", "carry": 2}
}
```

- `bag.size` is a whole number from 1 to 99 in `world.json`. A pack
  with no `bag` block keeps the unbounded bag it always had.
- `carry` is a whole number from 1 to 99 on an item. Each carried thing
  with a `carry` raises the cap by that much. "Carried" means in the bag
  or worn, so wearing a satchel keeps its places. A `carry` of 0, or no
  `carry`, adds nothing.

When the bag is full, a floor pickup is refused. The thing stays on the
floor under the hero, and the player reads one line, for example "Your
bag is full. You leave a plain ring on the floor." The thing waits there:
once a place is free, walking onto the tile again picks it up. A shop
purchase into a full bag is refused too: the Trade panel says "Your bag
is full.", and no gold is taken. The bag panel counts
against the cap: "2 of 2 carried." When the pack names no size it reads
"12 things carried." as before.

Some things always fit, because refusing them would lose them rather than
leave them on the floor: a warden's key, an item a rule gives, a chest's
contents, an equip swap, and a take-off.

**`vefr check` refuses two things,** one plain sentence each: a `bag`
block with no whole-number `size` from 1 to 99, and a `carry` that is not
a whole number from 1 to 99.

Known gaps: a `carry` does nothing where the pack names no `bag.size`,
and there is no weight and no slot beyond the five worn ones.

Code: `src/vefr/shapes.py` (`BAG`, `ITEM_CARRIES`) + `src/vefr/maplab.py`
(`bag_errors`) + `src/vefr/cli.py` (`_player_items`) +
`web/player/parts/180-gold.js` (`bagRoom`, `bagAdd`) and
`430-loot-on-the-floor.js` (the refusal) and `190-the-trade-panel.js`
(`buyItem`, the shop's refusal). Tests:
`tests/test_bag_capacity.py` + `tests/fixtures/bag_capacity_harness.mjs`.

## reward (first slice: gold, trade, and using a thing)

The loot slice left a thing carried but did nothing with it. This slice
adds the reward end: a purse of gold, a shopkeeper who buys and sells,
and using a carried thing. It is still deliberately small - no haggling,
no stock limits, no equipping (equipment came later: see Equipment), no weight - and still deterministic:
prices and heals are fixed pack numbers, no randomness, no model call,
no clock.

Three optional additions to the pack shape, all additive:

An item may carry `value` (a positive int: what a shop pays and asks),
`heal` (a positive int), and `use` (a verb such as `drink`):

```json
"items": {
  "cloudy-potion": {"name": "a cloudy potion", "sprite": "potion",
                    "value": 8, "heal": 3, "use": "drink"},
  "brass-ring":    {"name": "a plain brass ring", "sprite": "ring",
                    "value": 3}
}
```

A speaker may carry `"shop": "true"` (also `yes` or `1`). At most one
shopkeeper per region; the first one named wins. A speaker with no
`shop` is exactly the speaker it always was:

```json
"speakers": {
  "merchant": {"name": "a dusty merchant", "at": [2, 2],
               "near": "the stall", "shop": "true",
               "seeds": {"dusk": "...", "dawn": "..."}}
}
```

And `world.player` may carry `gold`, the starting purse (a non-negative
int, default 0):

```json
"player": {"hp": 3, "atk": 2, "gold": 5, "wake": {"region": "town", "at": [1, 1]}}
```

None of the three is required. A pack that names none of them bakes
exactly the player it had before, and its HUD does not move: the gold
line appears only when the world trades at all (a shopkeeper exists, or
some catalog item has a `value`).

**The purse.** Gold is one number at `localStorage['vefr-gold-<world>']`,
seeded from the baked `VEFR_HERO.gold`. It shows as a short line in the
top-left HUD ("5 gold") and as plain words in the Bag panel ("You carry
5 gold.").

**The trade.** A shopkeeper's Trade panel opens when the hero stands
within one tile of them (the same reach as a bump) and presses Interact
(or `F`), the same verb that opens a door or a chest. Sell lists each
carried thing with a `value` and its price, with a Sell button; Buy lists
every catalog entry with a `value` and its price, with a Buy button. A
Buy the purse cannot afford is disabled. Each trade updates both lists,
the purse, and an `aria-live` line ("You sell a cloudy potion for 8
gold."). The panel is a dialog: 44px targets, close with the Close button
or `Escape`, and focus returns to the Interact button. Talking (Talk /
`E`) still gives the shopkeeper's own line; trading is a separate verb.

**Using a thing.** The Bag panel gives a Use button to any carried thing
the pack gave a `heal`. Using it raises health by `heal`, never above the
max, spends one copy, and says so ("You drink a cloudy potion. You
recover 2 health."). At full health it says "You are already whole." and
keeps the thing - a potion is never spent on nothing.

Baked as `VEFR_HERO.gold`, `VEFR_SHOPS` (a `{region: speaker key}` map),
and the extra `value`/`heal`/`use` fields on each `VEFR_ITEMS` entry.
Code: `src/vefr/cli.py` (`_player_items`, the hero block, the shops map)
+ `web/packaged.html` (gold, bag, use, trade); tests:
`tests/test_builder_weave.py` + `tests/test_combat_loop.py` +
`tests/fixtures/combat_harness.mjs` + `tests/fixtures/make_combat_pack.py`.

Known gaps (this slice): no haggling or variable prices, no stock or
shop inventories beyond the catalog, no equipping (added later: see Equipment) or effects other than
healing, no dropping or giving, no currency other than gold, and selling
always pays exactly `value`. `maplab.validate` does not yet pin the
reward fields; the bake ignores a `value`/`heal` that is not a positive
int and a `use` that is blank.

## light (first slice: a torch and a one-shot reveal)

Some regions are dark (their `contract.json` declares `fog`). A pack can
give a carried thing a `light` so the player can widen that circle or
lay the whole map open. It is additive: an item without a `light` bakes
exactly as before, and a pack with no `light` anywhere plays as it always
did. Still deterministic - fixed numbers, no randomness, no model call.

An item's `light` takes one of two forms:

```json
"items": {
  "torch":       {"name": "a pitch torch",
                  "light": {"radius": 2, "turns": 6}},
  "chalked-map": {"name": "a chalked map",
                  "light": {"reveal": true}}
}
```

`radius` (an int 1..20) widens the lit circle by that many tiles for
`turns` (an int 1..999) hero turns; when the turns run out the region's
own base radius returns and the light gutters out (announced once).
`reveal: true` marks every tile of the current region explored in a
single use. A `light` must name at least one form.

**Use.** A `light` item gets a Use control in the Bag panel, like a
`heal`. Using a torch from the Bag widens the light, spends one copy, and
says so ("The torch catches: 2 wider for 6 turns."); using a reveal map
spends one copy and says "The whole place is laid out.". In a region with
no dark (or after the player turns the dark off with `V` / Display) it
says "There is no dark here to light." and **keeps the thing**. While a
light burns, the top-left HUD shows a small "Turns of light: N"; the
counter is for glancing, and the news rides the ordinary announcements.
Entering another region ends the light (a fresh region is a fresh dark).

Baked as the extra `light` field on each `VEFR_ITEMS` entry (only a
usable form is baked). Code: `src/vefr/cli.py` (`_player_items`) +
`src/vefr/maplab.py` (`item_light_errors`) + `web/packaged.html` (the
Bag use, the HUD, the turn); tests: `tests/test_light.py`. The sample
world carries a torch and a chalked map in a chest for a live look.

Known gaps (this slice): one burning light at a time (a second torch
replaces the first), no light on the floor (drops are not lamps), and no
colour or animation - the lit circle simply grows.

## growth (levels or learning by doing)

Growth is optional and additive. **Both ways are off by default:** a pack
with no `growth` key plays as before. A pack that declares one picks a
single `mode` and carries only that mode's block.

In `levels` mode a defeated enemy gives experience, and enough experience
is a new level. `levels.xp` is a strictly rising list of whole numbers
that starts at 0, with at most 20 entries; entry N is the experience that
reaches level N+1, and the hero starts at level 1. `levels.gain` gives the
health and attack added by each level (whole numbers 0 to 9):

```json
"growth": {
  "mode": "levels",
  "levels": {"xp": [0, 10, 25, 50], "gain": {"hp": 2, "atk": 1}}
}
```

An enemy carries its own `xp` (a whole number of at least 0; absent means
0), and only in `levels` mode:

```json
{"id": "rat", "hp": 4, "atk": 1, "sprite": "rat", "xp": 3}
```

In `practice` mode there are no levels and no experience. Each stat grows
as the hero keeps doing a thing. `practice` names only `hp` and `atk`;
each carries `by` (one of `strikes`, `hits-taken`, `consoles`, `hurls`),
`every` (a whole number 1 to 99), `gain` (a whole number 0 to 9) and `cap`
(the most that stat can grow in total, at least 1):

```json
"growth": {
  "mode": "practice",
  "practice": {
    "atk": {"by": "strikes", "every": 12, "gain": 1, "cap": 4},
    "hp":  {"by": "hits-taken", "every": 8, "gain": 1, "cap": 6}
  }
}
```

A level-up (or a practice growth) of health also heals the hero by the
same amount, never above the new max. The extra health and attack are
derived from the saved state every time, never stored, so a re-woven game
cannot leave a stale level. `maplab.validate` checks the shape above and
names a bad field in plain words. The status line ("Level 2 · 14 of 25
experience") shows in `levels` mode only. All of it is deterministic: no
randomness, no model call, no clock.

Code: `src/vefr/maplab.py` (validation) + `src/vefr/cli.py` (bake) +
`web/packaged.html` (the engine and its seams); tests:
`tests/test_growth_validator.py` + `tests/test_growth_engine.py` +
`tests/test_growth_play.py` + `tests/fixtures/make_growth_pack.py`.

## spells (schools, levels, and the books found on the floor)

Spells are optional and additive: **a pack with no `spells` key plays
exactly as it did**, and one that declares none bakes no
`window.VEFR_SPELLS` line at all, so its woven bytes are the ones it wove
before this feature. A pack may declare the schools it teaches and
the spells in them:

```json
"spells": {
  "schools": ["ember", "tide"],
  "spells": [
    {"id": "ember-bolt", "name": "an ember bolt", "school": "ember",
     "level": 1, "heal": 3},
    {"id": "tide-mend", "name": "a mending tide", "school": "tide",
     "level": 2, "heal": 5},
    {"id": "gutter-light", "name": "a gutter light", "school": "ember"}
  ]
}
```

`id`, `name` and `school` are required; `level` and `heal` are not. The
school names are the pack's own plain words, and there is no closed list
and no order the engine imposes.

**Learning by level.** A spell with a `level` is learned the moment the
hero's level reaches it. That level is the one the `growth` block above
already derives and already caps at the length of `levels.xp` - spells
add no counter of their own and **the cap does not move**, so a spell
written above the table's last entry is never learned by level. A pack
with no `growth` block, and a `practice` pack (which keeps no level),
learn nothing by level at all.

**Learning from a book.** A spellbook is an ordinary item with one extra
optional key, `spell`:

```json
"items": {
  "tide-tome": {"name": "a tide-bound tome", "use": "read",
                "spell": "tide-mend"}
}
```

It is a drop like any other drop, so which spell a book teaches follows
from which book the draw already chose - there is no second draw and no
second stream. Reading it is the `use` verb a potion is already drunk
with: the book is spent (unless it carries `keep`), the spell is learned,
and the panel's live line says which. A spell with no `level` is only
ever taught this way.

**Casting.** A known spell appears in the Bag panel, under the bag, with
a `Cast` button. Casting recovers its `heal` and never above the hero's
max, and keeps the potion's rule: already whole means nothing is gained
and nothing is spent, and the line says so. A spell with no `heal` casts,
says so and changes no number. Every cast also goes in the Why panel as
`cast <spell id>` with the same line, so it can be read back later; a
refused cast writes nothing there.

`vefr check` refuses four things, one plain sentence each: a spell
naming a school the block does not declare, a `level` under 1, a book
teaching a spell the pack does not declare, and a spell with no school
at all (named by its id and the file: "world.json: spell 'ember-bolt'
must hold a school, such as ..."). What a school does in play, and what a spell does beyond
healing, are open questions this slice does not answer - see ADR 0018.

Code: `src/vefr/shapes.py` (the two blocks) + `src/vefr/maplab.py` (the
sweep) + `src/vefr/cli.py` (the bake) + `web/player/parts/225-spells.js`
(the player); tests: `tests/test_spells.py` +
`tests/test_spells_play.py` + `tests/test_spell_table.py` (the shape,
the bake and the player's reads held to one another) +
`tests/fixtures/make_spell_pack.py`.

## equipment (the pack fields and the engine; the wearing is a later slice)

Equipment is optional and additive: a pack whose items carry no `slot`
plays exactly as it did, and a pack with no `items` is untouched. **This
slice is the pack fields and the pure engine.** Nothing wears anything
yet: the Bag panel, the buttons and the live line are the next slice.

An item may carry `slot`, exactly one of `hand`, `body`, `head`, `feet` or
`charm`, and `mods`, which is only allowed beside a slot:

```json
"items": {
  "green-cloak": {"name": "a green hooded cloak", "sprite": "cloak",
                  "slot": "body", "mods": {"hp": 2}},
  "short-bow":   {"name": "a short bow", "sprite": "bow",
                  "slot": "hand", "mods": {"atk": 1}},
  "brass-ring":  {"name": "a plain brass ring", "sprite": "ring",
                  "slot": "charm"},
  "cloudy-potion": {"name": "a cloudy potion", "heal": 3, "use": "drink"}
}
```

- `mods` holds only `atk` and `hp` (max health), each a whole number from
  0 to 9; a bool is refused. No `mods` means a keepsake that only looks
  nice.
- A slotted item may still carry `value` and `keep`, but not `heal`,
  `light` or `use`: a worn thing is not drunk or lit.
- An item named by a door's `requires.item` may not have a slot. A key
  stays in the bag so it can open its door more than once.
- An item with no `slot` cannot be worn (a potion, a key) and behaves
  exactly as before.

`maplab.validate` checks the shape above and names a bad field in plain
words, once per item. The bake carries `slot`, and `mods` beside it, only
when the shape is valid, so a broken one is a silent no-op rather than
something the player cannot wear. This slice is the **pack fields and the
bake** only (`design/equipment.md`, build step 1 of 5): the equip state,
the stat sums, the Bag's "You" section and the buttons come with their
own slices. Deterministic throughout: no randomness, no model call, no
clock.

The engine (`window.VEFR_EQUIP_ENGINE`, pure, in the woven player) answers
the numbers and moves the worn state: `statsFor(base, items, equipped)`,
`equip`, `unequip`, `clean`, `clampHealth`. Attack is base `atk` plus the
worn `mods.atk`; max health is base `hp` plus worn `mods.hp`; taking off
something that lowered the max clamps current health down to it, never
below 1. `equip` refuses an item with no slot, a slot it does not fit, an
id the catalog lacks, and an id already worn, so a duplicate is
impossible, and equipping into a full slot returns the old wearer so the
bag can take it back. Nothing is written into the caller's state, because
that object is what gets saved. Deterministic like the rest: no
randomness, no model call, no clock.

Code: `src/vefr/maplab.py` (`SLOTS`, `MOD_STATS`,
`item_slot_and_mods`, `item_slot_errors`, `_door_key_items`) +
`src/vefr/cli.py` (the `_player_items` bake) + `web/packaged.html`
(`VEFR_EQUIP_ENGINE`); tests: `tests/test_equipment_validator.py` +
`tests/test_equipment_engine.py` + `tests/fixtures/make_equip_pack.py` +
`tests/fixtures/equip_engine_harness.mjs`.

## Album (stickers a world keeps)

A `world.json` may carry `album`, an optional list of stickers
`{id, name, kind, when, riddle?, shine?}`. `id` is unique and `name` is
1–60 characters; `kind` is `open`, `riddle` or `secret`; `shine` is
`paper` (default), `foil` or `holo`. `when` is exactly one rules event,
the same vocabulary and identity model a rule uses. An `open` sticker
shows its name from the start, a `riddle` shows only its riddle until
earned, and a `secret` appears only in a count. Rewards only add.
Code: `src/vefr/maplab.py` (`album_errors`) + `src/vefr/cli.py`
(`_player_album`) + `web/packaged.html`; tests: `tests/test_album.py`.

## Sound

A `world.json` may carry `sound`, an optional object: `{"theme": "soft"}`.
No audio files: every cue is synthesized in the browser; `soft` is the only theme.
The nine cues are `hit`, `hurt`, `defeat`, `pickup`, `door`, `locked`, `level`, `sticker` and `end`.
Each fires at one moment of play, never on a timer, and the live line already says it in words.
Menu > Display > Sound turns them off for this browser, on by default; a pack with no `sound` has no switch.
Code: `src/vefr/maplab.py` (`sound_errors`) + `src/vefr/cli.py` + `web/packaged.html`; tests: `tests/test_sound.py`.

## Skins (a picture pack for the interface)

A skin is a folder of pictures that repaints the player's interface. It is
optional and additive: a pack that names none bakes exactly as before.

A pack's `world.json` may carry a `skin` field naming a folder inside the
pack:

```json
"skin": "skins/parchment-and-wood"
```

The folder holds one `skin.json` and its pictures. `skin.json` has a
`name`, a `credit`, a `parts` object and an optional `ink` object, plus
two more optional keys — a `backdrop` and a `fonts` pair:

```json
{
  "name": "parchment-and-wood",
  "credit": "Rylee and Claude",
  "parts": {
    "panel":  {"file": "panel.webp", "slice": 32},
    "button": {"file": "button.webp", "slice": 20, "hover": "button-hover.webp",
               "pressed": "button-pressed.webp", "disabled": "button-disabled.webp"},
    "bar":    {"frame": "bar-frame.webp", "fill": "bar-fill.webp"},
    "cursor": {"file": "cursor.webp", "hand": "cursor-hand.webp", "hotspot": [4, 4]}
  },
  "ink": {"on_panel": "#2B2118", "on_panel_dim": "#5A4A38"},
  "backdrop": "table.webp",
  "fonts": {"display": "Cinzel", "body": "Crimson Pro"}
}
```

The known parts are `panel`, `button`, `tab`, `toggle`, `bar`, `slot`,
`speech`, `tooltip`, `gold-plate`, `divider`, `banner`, `corner` and
`cursor`; each names its pictures under the keys that part uses.

**The backdrop** is one seamless picture for the ground the drawn map
does not cover inside the window — the table the game sits on. It is
painted on the map canvas, not with CSS, and only where the map does not
reach: a map that fills the window shows none of it. A skin without a
`backdrop` gets today's flat dark ground, exactly as before.

**The fonts** choose the type: `display` for titles and buttons, `body`
for reading. The names come from the families the engine bundles and
ships inside the woven file — `Cinzel`, `Atkinson Hyperlegible Next` and
`Crimson Pro` — so there is no download at play time. Any other name is
refused by the validator rather than left to fall back. Choosing a
typeface does not change any colour, so the ink rules below still decide
whether the words are readable.

**The validator's rules.** `maplab.validate` (and so `norns validate`)
reads the folder and refuses a bad skin with one plain sentence. The
folder must stay inside the pack. `skin.json` must be a JSON object with
a non-empty `name` and `credit`, and only known parts; an unknown part is
a typo to fix, not something the player quietly ignores. Every named
picture must exist, be a `.png` or `.webp`, and be under 300 KB. A
`slice` must be a whole number of at least 1 and at most half the smaller
side of its picture. `ink` colours must be `#RRGGBB`. A `backdrop` is
checked like any other picture, and `fonts` may only name a bundled
family for `display` or `body`.

**How it is drawn.** The loader inlines every picture as a data URI, so
the woven file stays one offline file. Panels and buttons use CSS
`border-image` with the slice width (a nine-slice), so one small picture
stretches to any size. Bars are a frame picture with a clipped fill
picture. The cursor is a CSS `cursor: url(...)` with a hotspot, and a
hand for things you can use. The backdrop is tiled on the map canvas
under the whole stylesheet, and the fonts are the player's own `--display`
and `--read` variables, so every rule already written reaches them.

**Safety.** Text is never inside a picture: every word is real HTML, and
pictures are only backgrounds, borders and icons. Focus is never removed.
Targets stay at least 44 px. `prefers-contrast: more` and forced colours
fall back to the plain flat look, so a skin never wins over a person's
contrast setting — the backdrop goes with it, and the type returns to the
player's own. **No skin means no change**: a pack with no `skin`
field bakes byte-for-byte as before, and the baked value is `null`.

Code: `src/vefr/maplab.py` (`skin_errors`) + `src/vefr/cli.py`
(`_baked_skin`) + `web/player/parts/540-the-skin.js` (`applySkin`),
`440-the-camera.js`, `448-asset-loaders.js` (the ground's pictures) and
`480-town-input-and-turns.js` (the ground);
tests: `tests/test_skin_validator.py` + `tests/test_skin_apply.py`.

## Walk sheets (a character that walks)

A sprite may carry a walk cycle: three files side by side in `sprites/`.

    sprites/hero.png            the single picture (still the fallback)
    sprites/hero-sheet.png      the frames, left to right, top to bottom
    sprites/hero.sheet.json     which frame is which

```json
{
  "image": "hero-sheet.png",
  "frame": [32, 32],
  "fps": 8,
  "directions": {
    "down":  {"idle": [0],  "walk": [1, 2, 3, 4]},
    "right": {"idle": [10], "walk": [11, 12, 13, 14]},
    "up":    {"idle": [15], "walk": [16, 17, 18, 19]}
  }
}
```

Frames number left to right, top to bottom.
`frame` is one cell's size and `fps` its pace.
A direction may be missing: a missing `left` or `right` is the other
side mirrored, and a missing `up` falls back to `down`. `down` is
required. The player draws the `idle` frame standing, a `walk` frame
per step, and settles back to `idle`. The validator checks every
sheet: the image exists beside it, `frame` and `fps` are in range, the
directions are known, and every frame index is inside the sheet's grid.

Each direction may also name more states, each a list of frame indexes:

- `idle` - 1 to 16 frames. A list longer than one loops at the sheet's
  `fps`; a single frame stands still.
- `walk` - 2 to 16 frames, one per step, as above. Optional: a character
  that never walks (a resident at their stall) may leave it out, and
  stands on its `idle`.
- `talk` - 1 to 16 frames, looped while the speech box is open and the
  character is beside the hero.
- `act`, `attack`, `hurt` - 1 to 16 frames each, played once at the
  sheet's `fps` and then back to `idle`. `act` is the hero taking
  something; `attack` and `hurt` are the blow struck and the blow taken,
  for the hero and for a monster alike.

A speaker turns to face the hero when the hero stands beside it, and
looks down otherwise. A monster faces the way it last stepped. A pack
that names none of the new states plays as before: a one-frame `idle`
stands still, and nothing loops or plays once. Under reduced motion
nothing loops and no one-shot plays: an idle or talk list shows its
first frame.

## Story status (draft words and the release gate)

An agent may draft a whole story; nothing ships as canon until the
owner has read and edited it. So a pack may say which of its words are
still drafts, with an optional `status` key: **`draft`** or
**`approved`** (the default when the key is absent, so every pack that
predates it validates and reads exactly as before). A `status` written
as anything else is a validation error naming the file, like every
other typed key.

`status` is a **sibling key on the object that already owns the words** -
no wrapper object, no second format:

| words | where the key goes |
|---|---|
| a book | its front matter, beside `title`/`found`/`kind` (above) |
| a voice file | `world.json`'s `voices.<id>`, beside `file` and `strike` |
| a speaker's voice file | `world.json`'s `speakers.<id>`, beside `voice_file` and `seeds` |
| a `say` rule | the rule, beside `when`/`if`/`then` |
| an album sticker name | the sticker, beside `name`/`kind`/`when` (Album, above) |
| an item name | the item, beside `name` (`items.<id>`) |

A voice file is the one surface with no front matter of its own - the
whole `.md` is the prompt the weaver sends, so a `---` block would
become words - which is why its status rides on the record that names
the file. A rule's status is on the rule rather than on the `say`
action because an action names exactly one thing to do, and the woven
player's rule engine reads that object key by key.

`vefr check --release` lists every draft word with its file and line:

```console
$ uv run vefr check --pack worlds/<name> --release
6 draft word(s):
  acts/act-1/world.json:20  speaker 'keeper' - voices/keeper.md is a draft
  library/a-draft-book.md:3  book 'a-draft-book' - A Draft Book is a draft
  world.json:85  voice 'draft-keeper' - voices/keeper.md is a draft
  ...
```

It lists and exits 0. Add `--strict` to make the gate fail on a draft -
it prints the whole list **first**, so a human sees what is in the way
before the non-zero exit. A pack with no drafts prints one line
(`no drafts - every word in this pack is approved`) and exits 0 under
both spellings.

The `file:line` is the line the `status` is written on. A rule or
sticker with no `id` has nothing to name itself by, so it is listed as
`the rule at position N` - the same words `vefr check` uses when it
refuses that rule for having no id.

This is a release gate, not a mode: **a draft word plays exactly as an
approved one does.** Nothing in `web/` reads the key, and no surface
reads it outside the gate. Code: `src/vefr/story_status.py`
(`drafts`, `errors`, `report`) + `src/vefr/library.py` (the book's front
matter) + `src/vefr/maplab.py` (the unknown-value refusal) +
`src/vefr/cli.py` (`vefr check --release --strict`); tests:
`tests/test_story_status.py` + `tests/fixtures/make_story_status_pack.py`.

## Adding a ruleset (the checklist later acts follow)

1. Loader passthrough in `src/vefr/world.py` (acts + flat shapes).
2. `maplab.validate` pins for the block's shape.
3. A screen branch in `startPlaySurface()` in `web/packaged.html`
   (and, when the live app needs it, routes in `src/vefr/main.py` —
   AGENTS.md lists new public routes as ask-first).
4. A neutral fixture builder in `tests/fixtures/make_<name>_pack.py`
   (engine-test canon only; real canon lives in pack repos).
5. A harness in `tests/fixtures/<name>_harness.mjs` (jsdom, dev-only)
   that PLAYS the loop, plus a `tests/test_<name>_loop.py` pinning
   journal order, feedback lines, and the click budget — the
   pleasant-loop protocol (VEFR-ACT1-SPEC §9): two playtest passes per
   increment, nine-point checklist, dud kill-switch.
6. **Every overlay the ruleset adds (a panel, a note, a speech box) must be continued by the Interact keys** (E, F, Space, Enter) or deliberately be a choice that keeps its own controls, and a test must say which. A player that needs a click mid-loop breaks the loop (Rylee, 2026-10-02; `tests/test_overlay_interact.py`).
7. ROADMAP entry with pasted gates; dev-guards green; merge without
   `--admin`.

## What a ruleset must never do

- Call a model from a deterministic surface (`export.py`, `weave.py`,
  `maplab.py`, `journal.py`, `desk.py` — the export law).
- Introduce timers or pressure (the truck-arrives law).
- Punish: failure bends the story or waits; it never ends it.
- Name private canon in engine code or fixtures (the neutrality guard
  reads engine surfaces on every CI run).

## Player words (the pack's own wording, v0)

The engine speaks a few action-critical lines — the ones a player has
to read in order to act — and it writes each of them in ONE table, not
at the call site. v0 of that table is the four where-next lines:

| key | the engine's wording | what it tells the player |
|---|---|---|
| `where_next.goal` | `To reach {place}.` | which place the world is aiming at |
| `where_next.reach` | `To reach {place}, go {direction}.` | which way to step to get there |
| `where_next.here` | `The way to {place} is right here.` | it is already where the hero stands |
| `where_next.no_way` | `No way to {place} is declared from here.` | the action is not available |

Those defaults are the strings the player already read (vefr #259:
"To reach floor-1, go north-west" — a region id and a compass where a
place name and an action belong). This slice moves them into one home
and gives the pack a say; it does not build a localization framework.

A pack MAY name its own word for any of them, and MAY name none. The
block is `world.json`'s `player_words`, one key per row, each the
pack's own sentence:

```json
"player_words": {
  "where_next.reach": "To get to {place}, head {direction}."
}
```

Rules, all of them `vefr check`'s to enforce (and none of them said
about a pack that names no word):

- the block is optional and additive; a pack that declares none plays
  the engine's own wording byte for byte, and nothing about it is ever
  reported;
- every value must be a string, must say something (not empty, not only
  spaces), and must name its `{place}` slot — the engine hands it the
  place being pointed at. `{direction}` is available too and stays as
  written when there is no direction to fill it;
- a key the table does not have is refused: a word nothing can ever
  read is a word the author thought they had said;
- each refusal is one plain sentence naming `world.json` and the key.
  The engine never quietly falls back to its own default for a word a
  pack meant to supply.

The key set is typed once in Python (`shapes.PLAYER_WORDS` in
`src/vefr/shapes.py`, which the refusals are spoken from) and once in
the player (`VEFR_PLAYER_WORDS` in
`web/player/parts/340-where-next-hints.js`, which holds the wording);
`tests/test_player_words.py` fails if they drift. The pack's words ride
the world object the weave already bakes, so there is no new
placeholder and no new bake step.

Code: `src/vefr/shapes.py` (`PLAYER_WORDS`, the `place-label` kind) +
`src/vefr/maplab.py` (`player_words_errors`) + `web/player/parts/340-where-next-hints.js`
(`VEFR_PLAYER_WORDS`, `playerWord`); tests: `tests/test_player_words.py`.

Out of scope for v0: every other string in the player, region display
names (vefr #363), POI labels in `point-to`, and any pluralization or
translation framework.
