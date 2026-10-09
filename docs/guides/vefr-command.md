# The vefr command

One front door.
Every verb that used to live in `ratatoskr` (running things) or
`norns` (making things) is a `vefr` verb now, and the old names keep
working as aliases. Nothing you have written down goes stale.

```sh
uv run vefr --help    # every verb, in the order you use them
```

## The verbs

In journey order: the order an author walks the path, from a session
that starts sound to a file you can send to a friend. This is the
order `vefr --help` prints them in, too.

| Verb | What it is | Old spelling |
|---|---|---|
| `vefr doctor` | session-start health: git, tree, tests, pack, live, backups, vault; one answer | `norns doctor` + `ratatoskr skipa` |
| `vefr chat` | interview a new world into existence | `norns chat` |
| `vefr map` | rebuild the map from run-length rows | `norns build-map` |
| `vefr delve` | generate dungeon floors from a seed, or a whole Section, and wire the stairs | `norns delve` |
| `vefr check` | validate the pack geometry; `--release` lists every draft word (`--strict` to fail on one); `--live URL` validates a running deployment | `norns validate` / `norns verify` |
| `vefr weave` | package a world into one self-contained HTML file | `ratatoskr weave` |
| `vefr handbok` | write the mechanics manual from real play | `norns handbok` |
| `vefr spark` | the resident small brain: `install`, `status`, `smoke`, `task` | `ratatoskr spark` |
| `vefr test` | the pytest suite; extra args pass through, e.g. `-k chat` | `ratatoskr test` |
| `vefr ferry` | deploy, carry, fetch, scaffold | `ratatoskr ferry` |
| `vefr skipa` | kept for now; prints one line saying it is part of `vefr doctor` | `ratatoskr skipa` |
| `vefr find` | local read-only search of the pack's markdown and the journal | new |
| `vefr features` | the feature catalog: what VEFR can do, and what a pack uses | new |
| `vefr normalize` | expand a Blueprint into its owned regions and refresh the lock | new |

Two habits carry over unchanged: validate after every pack write
(`uv run vefr check --pack worlds/<name>`), and read `--help` for the
live list straight from the code.

## Developer verbs

Three verbs help when you work on the game itself. They live in
`src/vefr/devtools.py`, and `vefr doctor` now lists the tooling they
need under a short `tooling:` block.

`vefr publish` weaves the pack and hands the single HTML file to the
gallery CLI, which carries it to the site. It prints the command
instead of running it with `--dry-run`.

```sh
uv run vefr publish --pack worlds/sample-world
```

`vefr look` opens the woven player in headless Chromium, screenshots it,
and lists the text standing over the map. It catches text that has
drifted onto the map.

```sh
uv run vefr look --pack worlds/sample-world
```

Four flags make it a photographer rather than one snapshot.

`--sizes WxH[,WxH]` photographs the pack at each size it names, one
file per size with the size in the name (`look-390x844.png`), and
reports the containment of every HUD piece once per size. One size (or
none) writes `--out` exactly as before, at 1280x800.

```sh
uv run vefr look --pack worlds/sample-world --sizes 390x844,1440x900
```

The containment report measures `window.VEFR_STAGE`, the rectangle the
game itself paints on, and never the viewport. That is the difference
between "the control is on screen" and "the control is inside the
play panel": a piece that has fallen out of the frame is inside one and
not the other, and a piece that sits inside the stage at 1280x800 can
be outside it at 390x844. `--json` prints one report per size.

`--at REGION X,Y` starts the run somewhere other than the world's start
region. It needs `--pack`, because the region and the tile are checked
against the pack before a browser opens - a region the pack does not
have, or a tile the hero cannot stand on, is refused by name.

```sh
uv run vefr look --pack worlds/sample-world --at town 4,6
```

`--at` is a start position and nothing more: the typed half of a
scenario. For a state worth checking in, write
`scenarios/<name>.json` instead (below), and `vefr check` will keep it
honest against the pack.

`--seed SEED` asks the game for a run seed of its own. It rides the
player's `?vefr-seed=` parameter - open a woven player with
`?vefr-seed=hello` and the descent begins with the base seed `hello`,
drawing the same floors a pack baked with `run_seed: "hello"` draws. A
pack with no descent ignores it exactly as it ignores the parameter
today.

```sh
uv run vefr look --pack path/to/your-pack --seed hello --steps ArrowDown,ArrowRight
```

`vefr probe` fires rule events at the woven player and reads the why-log
and flags back. Each event is written `event:key=value`.

```sh
uv run vefr probe --pack worlds/sample-world --fire "enters:place=town"
```

All three return `0` when they do the
work, and `2` when the arguments are wrong or a tool they need
(Chromium, the gallery CLI) is missing. A missing tool is a report, not
a failed check, and never changes `vefr doctor`'s exit code.

### Scenarios: open the game in a named state

A scenario is a pack file, `scenarios/<name>.json`, that names a game
state: where the hero stands and what they carry. `vefr look` and
`vefr probe` open the woven game in it, so a deep floor can be seen and
tested without playing the way down to it.

```json
{
  "note": "the second floor down, with a purse and a staff",
  "start": {"depth": 2},
  "gold": 120,
  "bag": ["potion", "potion"],
  "equipped": {"hand": "oak-staff"},
  "xp": 40,
  "hp": 12
}
```

`start` is required and names either an authored region,
`{"region": "town", "at": [4, 6]}` (`at` is optional; the region's own
start is used without it), or a floor of the generated descent,
`{"depth": 5}`, entered at its stairs the way the hero arrives. The rest
is optional. `vefr check` checks every scenario against the pack: the
region and the tile, that a depth has a descent, and that every item is
one the pack defines and fits the slot it is worn in.

```sh
uv run vefr look --pack path/to/your-pack --scenario floor-two
uv run vefr probe --pack path/to/your-pack --scenario floor-two --fire "enters:place=town"
```

A scenario is the Player Driver's session capsule written by hand
(ADR 0016): the values go into the player's own save keys before the
page loads, so the woven game is unchanged, and the hero is walked in
through the same paths a player takes. The command then checks the hero
arrived where the scenario says, and exits `1` with a sentence if not.

## `vefr features`

`vefr features` prints the engine's feature catalog from
`docs/features.json`: every feature's id and status (`built`, `partial`
or `proposed`), and, when you pass `--pack`, whether that pack uses it.

```sh
uv run vefr features --pack worlds/sample-world
```

`--json` prints the whole report as one JSON object. `--check` is the
drift gate: it prints every catalog error and exits `1` if the catalog
has drifted from the repo, otherwise it prints `catalog ok` and exits
`0`.

## `vefr normalize`

`vefr normalize --pack PACK [--out DIR]` expands a pack's Blueprint
into the `enemies` lists of the regions it owns.

Without `--out` it is read-only: it prints one line per owned region
and whether the committed output is fresh. With `--out` equal to the
pack it refreshes the pack in place; any other `--out` must be a new or
empty directory outside the pack, and the pack is copied there,
refreshed and validated there. A failure leaves the previous bytes in
place.

```sh
uv run vefr normalize --pack worlds/sample-world
uv run vefr normalize --pack worlds/sample-world --out worlds/sample-world
```

Exit codes for this verb: `0` when the output is fresh or was written;
`1` on errors or when the committed output is stale. `vefr check` runs
the same stale check and refuses stale output too. The guide is
[Blueprints](blueprint.md).

## Escape hatches

Old muscle memory still runs. Both of these run the old CLIs exactly
as they were, unchanged:

```sh
uv run vefr norns validate --pack worlds/sample-world
uv run vefr ratatoskr test
```

The bare old names (`norns ...`, `ratatoskr ...`) also still work as
aliases. Every verb that had `--json` still has it.

## Exit codes

The same across every command, so a script can branch without a table
of exceptions:

| Code | Meaning |
|---|---|
| `0` | did what it says |
| `1` | refused, invalid, or failed |
| `2` | bad arguments |
| `3` | a backend (Spark, the live stack) could not be reached |
| `4` | gated: nothing changed, a person must approve |

## `--json` for agents

The envelope is the same every time, whichever verb you call:

```json
{"ok": true, "status": "ok", "changed": false, "warnings": [], "actions": [], "data": {}}
```

- `ok` - did it work
- `status` - a short machine-readable state
- `changed` - did anything change on disk or on the host
- `warnings` - what it noticed but did not stop for
- `actions` - what it did
- `data` - the verb's own payload

```sh
uv run vefr check --pack worlds/sample-world --json
```

## Where to go next

- [The Journey](journey.md) - the whole path, stop by stop.
- [Blueprints](blueprint.md) - a small source for repeated monsters.
- [World creation](world-creation.md) - the interview, the map, the file.
- [Spark](spark.md) - the resident small brain.
- [The Lorekeeper](lore.md) - facts and the derived index.
- [Volumes](volumes.md) - export and carry a session's state.
- [Bundled brain](bundled-brain.md) - the models that ship with the image.
