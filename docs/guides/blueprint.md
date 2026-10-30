# Blueprints: a small source for repeated monsters

A pack often repeats the same creature: a beetle in one cave, a
slightly tougher beetle in the next. A **Blueprint** lets you write the
family once and let VEFR build the records.

## What is a Blueprint?

A Blueprint is one file at a pack root, `blueprint.json`. It holds a
few small families of enemy values and a list of regions. `vefr
normalize` expands it into the `enemies` list of every region it names.
The Blueprint is the edited truth for the regions it owns. The records
it writes are generated, not hand-written.

The word is "Blueprint". It is not `grammar.py`, which is text
expansion, and it has nothing to do with rules or events.

## When should I use one?

Use a Blueprint when the same monster repeats across regions and only a
few numbers change. Use it when you want one place to change a family
and have every region follow.

Do not use one for a single, hand-written enemy. A pack with no
`blueprint.json` is completely unchanged.

A Blueprint needs the acts shape. A flat pack (one `world.json`, no
`acts/`) cannot carry one.

## How do I run it?

First write `blueprint.json` at the pack root. Then run:

```sh
uv run vefr normalize --pack worlds/<name>
```

With no `--out` this is read-only: it prints one line per owned region
and says `fresh` when the committed output already matches. Add `--out`
to write the generated records and the lock:

```sh
uv run vefr normalize --pack worlds/<name> --out worlds/<name>
```

`--pack PACK --out PACK` refreshes the pack in place. `--out` may also
name a new or empty directory outside the pack; the pack is copied
there, refreshed and validated there, and the original is never
touched.

`normalize` exits `0` when the output is fresh or was written (or the pack has no Blueprint, which it says), and `1`
when there are errors or the committed output is stale.

Then check the whole pack:

```sh
uv run vefr check --pack worlds/<name>
```

`vefr check` validates the pack geometry and also refuses stale
Blueprint output.

## The file format

The version field `blueprint` is required. It must be the integer `1`,
the integer `2` or the integer `3`.

- `1` is enemies: `regions` carry `enemies` and nothing else.
- `2` is things: the same `regions` as `1`, and a `things` list at the
  top level. `places` is format 3's key and is refused on `2`.
- `3` is places: `regions` may also carry `places`. `things` is format
  2's key and is refused on `3`.

**Formats 2 and 3 cannot be combined.** One file declares one version,
and each format refuses the other format's key, with a pointer: a
`"blueprint": 2` file carrying `places` is refused, and a
`"blueprint": 3` file carrying `things` is refused. A format-2 file is
complete on its own and a format-3 file is complete on its own; there
is no version that takes both halves, and nothing in a file waits for
another format to arrive.

A pack on `1` expands exactly as it did before, byte for byte.

This is a full example on format 1 (a synthetic pack, not real
content):

```json
{
  "blueprint": 1,
  "families": {
    "beetle": {"defaults": {"name": "a beetle", "sprite": "beetle",
                            "hp": 3, "atk": 1, "xp": 2}},
    "deep-beetle": {"extends": "beetle", "defaults": {"hp": 4}},
    "moth": {"defaults": {"name": "a moth", "sprite": "moth",
                          "hp": 2, "atk": 1, "xp": 1, "sight": 3}}
  },
  "regions": {
    "act-1/cave-2": {"enemies": [
      {"id": "b1", "family": "beetle", "at": [3, 4]},
      {"id": "b2", "family": "beetle", "at": [6, 4],
       "properties": {"drops": ["shell"]}},
      {"id": "m1", "family": "moth", "at": [4, 2]},
      {"id": "odd1", "family": "beetle", "at": [5, 5],
       "properties": {"hp": 9}}
    ]},
    "act-1/cave-3": {"enemies": [
      {"id": "d1", "family": "deep-beetle", "at": [3, 4]},
      {"id": "d2", "family": "deep-beetle", "at": [6, 4]}
    ]}
  }
}
```

A region key is `<act>/<region>` and must name a real region directory
inside the pack. An instance needs an `id` and a `family`, and it needs
`at` (a `[x, y]` pair of whole numbers) unless a `properties` or family
value already provides one.

Values are merged in this order: parent family defaults first (root
first), then the family's own defaults, then the instance's
`properties`. A later value replaces an earlier one whole. Lists are
never merged. A family may extend at most one parent.

### The closed key sets

Every object may use only these keys. Anything else fails with a plain
sentence and a JSON pointer.

| Top level | |
|---|---|
| `blueprint` | the format version, `1`, `2` or `3` |
| `families` | the named families |
| `regions` | the regions this Blueprint owns |
| `things` | the things the pack carries, a list at the top level (format 2) |

<!-- TOP_KEYS: blueprint, families, regions, things -->

| A family | |
|---|---|
| `defaults` | the values this family contributes |
| `extends` | the one parent family, or absent |

<!-- FAMILY_KEYS: defaults, extends -->

| A field value (in `defaults` or `properties`) | |
|---|---|
| `name` | the monster's name |
| `sprite` | the picture key |
| `hp` | health |
| `atk` | attack |
| `xp` | experience |
| `sight` | how far it notices the hero |
| `drops` | a list of item ids the pack declares as items a player can be given (an `items` entry with no `name` never reaches the weave, so it is not one) |
| `guard` | what each blow at it loses, 0 to 99, never below 1 (ADR 0021) |
| `drop_chance` | the percent of its kills on a generated floor that drop anything, 0 to 100; 100 when left out (ADR 0021) |
| `gold` | the coins one kill pays, as `[lo, hi]`, 0 to 9999 (ADR 0021) |
| `skills` | up to two of `web`, `spit`, `fester`, `dust` and `squeal`, each with its own numbers (ADR 0024; `docs/guides/rpg-core.md`, "Monster skills") |

<!-- FIELD_KEYS: name, sprite, hp, atk, xp, sight, drops, guard, drop_chance, gold, skills -->

| A region entry | |
|---|---|
| `enemies` | the instances for this region |
| `places` | the doors, stairs and signs for this region (format 3) |

<!-- REGION_KEYS: enemies, places -->

| An instance | |
|---|---|
| `id` | a unique id within the region |
| `family` | the family to start from |
| `at` | the `[x, y]` position |
| `properties` | values that override the family for this one |

<!-- INSTANCE_KEYS: id, family, at, properties -->

Unknown keys, unknown families, unknown parents, cycles, duplicate
ids, a missing `at`, an absent region, a region path outside the pack,
and an unknown `drops` item all fail. A `drops` item the pack declares
but the weave cannot hand over - an `items` entry with no `name` - fails
too, in its own words, rather than passing here and paying nothing in
play. Generated records are written in
this key order: `id, name, sprite, at, hp, atk, xp, sight, drops`. A family nothing uses is checked too: a broken parent or a cycle there is rejected, so a typo cannot hide until the family is first used. An error about a `drops` list points at the declaration that supplied it (the family's `defaults`, an ancestor's, or the instance's `properties`).

## Places (format 3)

A **place** is one thing built into the floor: a door, a stair or a
sign. A door goes from six edits in four files to one. Written as a
place, it is one entry, and `vefr normalize` writes the rest.

```json
{
  "blueprint": 3,
  "families": {},
  "regions": {
    "act-1/cave-2": {"places": [
      {"id": "down", "kind": "stair", "at": "2,7", "glyph": ">",
       "tile": "stair-down", "to": "cave-3", "to_at": "3,1"},
      {"id": "keeper-door", "kind": "door", "at": "far:down off:down>up",
       "glyph": "D", "base": ["#332e26"], "to": "cave-3",
       "to_at": "3,1", "needs": "shell", "locked_text": "It will not open yet."},
      {"id": "warning", "kind": "sign", "at": "near:down", "glyph": "!",
       "label": "the cracked sign", "text": "The cave breathes here."}
    ]}
  }
}
```

| A place | |
|---|---|
| `id` | a unique id within the region (required) |
| `kind` | `door`, `stair` or `sign` (required) |
| `at` | where it stands (required): one placement sentence (a string) |
| `glyph` | the one character it paints on the map (required) |
| `tile` | the tile picture for that character |
| `base` | the legend colours; defaults to the region's `.` |
| `label` | the name of the poi, a sign only |
| `text` | what the sign says, a sign only |
| `to` | the region of the same act it leads to, with `to_at` |
| `to_at` | the tile it lands on, with `to` |
| `needs` | the item that opens it, a door only, with `to` |
| `locked_text` | what the door says while it is shut, a door only |

<!-- PLACE_KEYS: id, kind, at, glyph, tile, base, label, text, to, to_at, needs, locked_text -->

`id`, `kind`, `at` and `glyph` are always required. A `door` and a
`stair` must name `to` and `to_at`, and they come together: one
without the other fails. `needs` and `locked_text` are a door's alone,
and a door with either one must have `to`. `label` and `text` are a
sign's alone. `chest` is not a kind yet; the engine has no chest place
to point at.

### Where a place stands

`at` is a sentence read left to right, and its words are ANDed. The
whole language is five words:

- `x,y` is a coordinate, and the only form format 1 has.
- `far:ANCHOR` is the tile farthest from the anchor.
- `near:ANCHOR` is the tile nearest to the anchor.
- `off:A>B` is a tile that is not on any shortest route from anchor
  `A` to anchor `B`.
- `dead-end` is a tile that leads nowhere.

An **anchor** is a name the region already has: `up`, `down`, a place
id, a poi name, or `start`. One real sentence:

```json
{"id": "guardian", "kind": "sign", "at": "far:up off:up>down",
 "glyph": "!", "label": "the guardian", "text": "It watches the stair."}
```

Read it: the farthest tile from the arrival stair, on no route from
that stair to the stair down.

`room:N` is not in this version. It is held back for a later one.

### What one place writes

A place writes into the files a hand-written door would have touched:

- `contract.json` gets one legend entry for the `glyph`:
  `{base, solid: no, tile}`, with `base` defaulting to the region's
  `.` entry;
- `contract.json` gets a `pois` entry for the place's tile, holding
  `label`, and a `poi_text` entry, holding `text`;
- the act's `world.json` gets one `transitions` entry
  `{from, at, to, to_at, requires: {item: needs}, locked_text}`,
  appended after the hand-written ones so the hand transitions keep
  their `transition {i}` numbers;
- the character is written **into `map.md`**.

That last one is why deleting `blueprint.json` still leaves a working
pack. The glyph is a real character in the real file the bot and the
studio read, not an overlay drawn at weave time. Delete the
Blueprint, delete the lock, and the doors, stairs and signs are still
there, still walkable, in the ordinary hand-written shape.

## Things (format 2)

A **thing** is one item the player can pick up: gear, a potion, a
keepsake. A pack that spells out several items in `world.json` writes
them once here instead, and `vefr normalize` writes the entries and
puts them in the carriers' drops.

This is a full example on format 2 (a synthetic pack, not real
content):

```json
{
  "blueprint": 2,
  "families": {
    "beetle": {"defaults": {"name": "a beetle", "sprite": "beetle",
                            "hp": 3, "atk": 1, "xp": 2}}
  },
  "regions": {
    "act-1/cave-2": {"enemies": [
      {"id": "b1", "family": "beetle", "at": [3, 4]},
      {"id": "b2", "family": "beetle", "at": [6, 4]}
    ]}
  },
  "things": [
    {"id": "shell", "from": "b2", "name": "a cracked shell", "value": 4},
    {"id": "glow-cap", "from": "b1", "name": "a glow cap",
     "sprite": "cap", "light": {"radius": 2, "turns": 6}, "keep": true},
    {"id": "old-ring", "name": "an old ring", "slot": "charm",
     "mods": {"hp": 1}, "value": 20}
  ]
}
```

`things` is a list at the top level of the file, not a region key. It
sits beside `regions`, and a region on format 2 carries `enemies` only.

| A thing | |
|---|---|
| `id` | a unique id across the `things` (required) |
| `name` | the name the bag shows (required) |
| `from` | the enemy instance that drops it |
| `sprite` | the picture key (a non-empty string); defaults to the `id` |
| `value` | what a shop pays and asks, a positive whole number |
| `heal` | health restored on use, a positive whole number |
| `use` | the verb that uses it, a non-empty string, like `drink` |
| `keep` | `true`, or nothing, when a used thing stays in the bag |
| `slot` | where a worn thing sits: `hand`, `body`, `head`, `feet` or `charm` |
| `mods` | the stats a worn thing changes: `atk` and `hp` |
| `light` | a torch's `radius` and `turns`, or `{"reveal": true}` |

<!-- THING_KEYS: id, from, name, sprite, value, heal, use, keep, slot, mods, light -->

A `sprite`, `value`, `heal`, `use` or `keep` of the wrong type is
refused, one sentence and the record's own pointer, rather than dropped
at the weave: the item reader throws away a value it cannot use, and
the author would only find out in a woven file. A broken `light`,
`slot` or `mods` is caught by the pack validator instead, so those two
rules do not overlap.

`id` and `name` are always required. A thing with no name is refused
rather than written, because an item entry with no name never reaches
the player. An `id` holding `/` or `~` is refused too: the id is one
token of the `/items/<id>` pointer that owns the written entry, and
either character would make the entry a different key than the one the
stale check reads. `from` is optional: name it and the thing is a drop,
leave it out and the thing is written to `world.json` and nothing
carries it. The rest ride along only when the record gives them, so a
thing written with two keys bakes as exactly that.

A thing's own id counts as an item the Blueprint declares, so a carrier
may drop a thing the same file declares. It may not take over an entry
`world.json` already has by hand: a hand-written `items` entry with the
same id fails, one sentence, with a pointer. An entry that holds exactly
what the thing would write is not hand-declared, so deleting the `things`
list and putting the identical list back is ordinary work.

An instance id is unique within its region, not across the whole file,
so a `from` that reaches two owned regions is refused with both region
keys named rather than resolved to whichever came last.

A `from` may only reach an instance of a region this Blueprint owns,
and owning a region means it says `enemies`: a region the source names
but leaves without an `enemies` list keeps the hand's own records, so a
`from` into it is refused with that reason and that region named, not
with a sentence saying no region holds the instance.

### What one thing writes

- the pack root `world.json` gets one entry at `/items/<id>`, holding
  `name`, `sprite` (always written, defaulting to the `id`) and then
  only the reward keys the record gave: `value`, `heal`, `use`, `keep`,
  `light`, `slot`, `mods`;
- the carrier instance's `drops` gets the id appended at the **end** of
  the list, which is created when the instance has none. This is the
  one place a list is added to rather than replaced.

That second one is why deleting the `things` list still leaves a
working pack. The item entry and the appended drop are already the
ordinary hand-written shape, so nothing else changes.

## The stale rule

The output is **stale** when any of these is true:

- the lock's `source_sha256` differs from the current Blueprint's
  hash, or
- any owned `enemies` list on disk is not structurally equal to what
  this VEFR expands now, or
- an owned `map.md` cell does not hold the character its place names, or
- an owned `items` entry in `world.json` is not structurally equal to
  what this VEFR expands now, so a hand edit to a written item is
  stale.

Structural equality compares the parsed JSON: key order is ignored,
list order matters. It is not byte equality. The third clause is the
map cell: a cell a place owns is stale when someone drew a different
character there by hand.

One stale check compares the Blueprint to its lock. The other compares
the committed records to a fresh expansion. A newer normalizer or
format than this VEFR knows also fails, clearly, instead of guessing.

The one command that fixes stale output is:

```sh
uv run vefr normalize --pack PACK --out PACK
```

## The lock file

`vefr normalize --out` writes `blueprint.lock.json` beside the
Blueprint. It records:

- `source_sha256`, the hash of the canonical Blueprint,
- the `normalizer` and `blueprint` (format) versions, and
- `outputs`, the provenance of every generated record (source pointer,
  family chain, overridden keys).

The lock is how `check`, `normalize` and the weave know the output is
fresh. It is generated; do not hand-edit it.

## Generated records are read-only

The `enemies` lists of the regions a Blueprint owns are generated by
`vefr normalize`. Do not hand-edit them: the next stale check compares
them to a fresh expansion, and a hand edit reads as stale. Change the
Blueprint, then run `normalize` again. Regions the Blueprint does not
name are untouched.

The same holds for everything a place writes: the legend entry, the
poi and its text, the transition and the `map.md` cell. Do not hand
edit those either. And the same holds for everything a thing writes:
the `items` entry and the appended drop. Change the thing, then run
`normalize` again.

## Leaving a Blueprint behind

If the Blueprint does not earn its keep, use the exit ramp: delete
`blueprint.json` and `blueprint.lock.json`. The generated records are
already in the old `enemies` shape, so nothing else changes. The pack
is a normal hand-written pack again. A place is already written in the
hand-written shape too, glyph and all, so a pack with places leaves
the same way. A thing is already written in the hand-written shape too,
so a pack with things leaves the same way, and deleting only the
`things` list leaves every written item in place while the appended
drop goes back to what the source still says.

## What it will not do

- It adds no rules and no events. A Blueprint word grants no authority
  at play time.
- It adds no effect vocabulary.
- It does not inherit beyond one parent.
- It does not change a pack that opts out.
- Hand-written enemy records stay fully supported.

Format changes are an ADR amendment with a new reader and fixtures. See
[ADR 0008](../adr/0008-blueprint-format.md) and
[ADR 0010](../adr/0010-things-and-places.md) (formats 2 and 3, and the
one library return type B1 moved, with no shim).
