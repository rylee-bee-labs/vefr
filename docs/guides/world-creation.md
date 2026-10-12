# World creation - from interview to a playable file

> One interview writes you a validated pack; one more command weaves
> it into a single HTML file you can open and play. Proven end to end
> 2026-09-22 against the bundled Spark (`:8083`): 15 prompts, exit 0,
> a valid pack in 25 seconds, a map extension through `build-map`,
> and a 37.9 KB single-file HTML with 10 woven pool lines.

## What you need

- A brain: the bundled fleet (`docs/guides/bundled-brain.md`) or any
  OpenAI-compatible backend pointed at with `VEFR_LLAMACPP_URL`.
- This repo, with `uv sync` done (`GETTING_STARTED.md`, step 1).

## The whole flow

```sh
uv run norns chat --name your-world                  # 1. the interview
uv run norns validate --pack worlds/your-world       # 2. the gate
uv run norns build-map --segments segs.json \
    --pack worlds/your-world                         # 3. optional: reshape the map
uv run ratatoskr weave --pool 2 --pack your-world    # 4. -> dist/your-world-<date>.html
```

Open the HTML in a browser, set your LLM URL + model in it, play — or
leave both blank to play offline from the woven pool.
`worlds/*` is gitignored - a throwaway world never touches git.

## 1. The interview

`norns chat` asks, in order (scaffold defaults in brackets):

| # | The question | Blank keeps | Behind it |
|---|---|---|---|
| 1 | What's your world called? [scaffold title] | scaffold title | becomes the pack's `world.json` title |
| 2 | In one or two sentences, what's the story? | - | the premise |
| 3 | Who is your protagonist, in a few words? | - | premise + protagonist -> the model drafts `logbok.md`, printed for you |
| 4 | the color mood (e.g. 'candlelit church', 'cold moonlit fen') | scaffold colors | theme draft, schema-constrained |
| 5 | Rename the phases? comma-separated, same count (2) | dusk, dawn | rewrites the phase keys |
| 6-7 | In a few words, what's the mood of 'dusk'? 'dawn'? | scaffold mood | one prose draft per phase |
| 8 | Rename the bonds? same count (3) | given, found, cold | renames how items connect to your protagonist |
| 9-11 | what does a '<bond>' bond feel like? | scaffold cards | a prose draft: card + prompt per bond |
| 12 | how should the town feel to walk? (e.g. 'tight lanes around a well') | scaffold layout | the map proposal - the hardest call |
| 13 | How many people stand in your town? (1-3, blank = 1) | one | each extra gets a "who else stands there?" + personality prompt |
| 14 | Your first townsperson is '<name>'. What should they be called? | scaffold name | |
| 15 | In a few words, who is <name>? | skips their drafts | a seed line per phase + a `voices/<file>.md` voice file |

Then: `checking your world...` runs the full validator - either
`ok - ... is valid and ready`, or a FAIL list naming what to fix by
hand, plus the next-steps commands.

Every question has a default. Blank keeps the scaffold's proven
piece, so even a fast, half-answered interview ends in a pack that
validates - the scaffold exists so the interview cannot strand you.

## 2. When a draft falls back

Every model call in the interview is schema-constrained and tries
twice before falling back. What the fallbacks look like, verbatim
from the dry run:

```text
  theme draft failed twice - keeping the scaffold's colors
  the map draft never validated twice - keeping the scaffold's
  proven layout (always try: norns validate --pack worlds/<name>)
```

The map proposal is the hardest ask in the whole flow: the model
must emit run-length rows at the scaffold's exact dimensions, using
only the scaffold's legend characters, that pass `maplab.validate()`
in place - geometry, reachability from the hero's start, every
speaker still on walkable ground. In the dry run every prose draft
(canon, phase moods, bond cards, voice, seeds) landed on the 0.6B
Spark while both gated structured drafts fell back. A bigger brain
narrows that gap:

```sh
VEFR_LLAMACPP_URL=http://127.0.0.1:8084 uv run norns chat --name your-world
```

A prose draft that fails twice becomes a plain placeholder instead -
you always get something to edit, never a crash mid-interview.

A small brain can also fall into a repetition loop and answer with the
same sentence over and over. The schema pins the JSON shape, not the
words, so `draft()` collapses repeated sentences before the interview
writes anything: your logbok, bonds, seeds and `voices/<name>.md` carry
each sentence once.

## 3. Reshaping the map later

`norns build-map` rebuilds the town map from a run-length segments
file - `{"rows": [[["H", 4], ["#", 12], ...], ...]}`, one
`[character, count]` pair run per row, every row the same width:

```sh
uv run norns build-map --segments segs.json --pack worlds/your-world
uv run norns validate --pack worlds/your-world
```

Dry run: a one-row extension (10 -> 11 rows, width 12), run
unforced. `build-map` validates before writing - bad geometry never
lands unless you pass `--force` (then fix it and validate anyway).
The validator after any map write is not optional; hand edits
included.

## 4. Weave it into one file

```sh
VEFR_LLAMACPP_URL=http://127.0.0.1:8083 \
    uv run ratatoskr weave --pool 2 --pack your-world
```

`--pool N` needs a live model: it pre-generates N real lines per
combination (dry run: 10 lines across `rumor:dusk`, `rumor:dawn`,
`letter`, `forge`), then writes `dist/your-world-<date>.html`. Open
it in any browser: the file carries the whole pack, and it plays
completely without a model (see `docs/adr/0003`). By default the game
never mentions models. To offer players an optional model of their own
for fresh lines, add `"model": "optional"` to the `player` block below;
it then appears under Model settings in the pause menu.

### The title screen

The shared file opens on a title picture. By default it's the World
Tree's front door; give your game its own, and an accent colour for
its buttons, in `world.json`:

```json
"player": {
  "title_art": "assets/title.webp",
  "accent": "#C98049",
  "model": "optional"
}
```

`title_art` is a path inside your pack (WebP, PNG or JPEG; around
1400px wide keeps the file small). `accent` is a six-digit hex colour;
the button text turns dark or light to stay readable on it. `model` is
optional too; leave it out and the game offers no model at all.

### The phone's zoom

A touch phone draws a map whole only when that keeps its tile at 36 px or
more; a bigger map scrolls with the hero at a size you choose. Set that
size in `world.json`:

```json
"display": {
  "phone_tile": 52
}
```

`phone_tile` is a whole number from 32 to 72, in CSS pixels. Left out,
a phone plays exactly as it always has. The camera may scroll up to three
tiles past the map's edge, so the hero is never under the corner buttons;
the ground past the edge takes the region's backdrop, or the dark.

### Your own tiles and variants

A region may bring its own ground pictures in a `tiles/` directory beside
`sprites/` (a flat pack keeps `tiles/` at the pack root). A legend entry
with `"tile": "stone-wall"` looks in the region's `tiles/` first and then
in the engine's own art, so one region can repaint any ground:

```text
worlds/your-world/acts/act-1/town/
├── map.md
├── contract.json      # legend: { ".": { "tile": "grass" } }
├── sprites/
└── tiles/
    ├── grass.webp      # variant 1 - optional
    ├── grass.2.webp    # variant 2
    └── grass.3.webp    # variant 3
```

The unnumbered file is variant 1 and is optional; `name.2.webp`,
`name.3.webp`, ... are the other variants, in numeric order. The player
picks a variant from the cell's own map coordinates, so the same world
always looks the same and a save and a screenshot agree. One picture
behaves exactly as before.

Bake at 2x the on-screen tile size (192px for a 96px tile). The engine
bakes the file as it is and never resizes, so the resizing is your pack's
own processing step. A tile the region and the engine both lack is a
validation error in a region that has a `tiles/`, while a region without
one still falls back to the engine set silently.

### Doors, stairs and trapdoors

A way out is drawn with the engine's door picture unless the pack brings
its own for that kind. Name the picture in `tiles/`:

- `way-door` - a door
- `way-stairs-up` - a stair that goes up
- `way-stairs-down` - a stair that goes down
- `way-trapdoor` - a trapdoor

A stair is a transition whose point of interest names "stair" or whose
map symbol is `u` or `d`; it goes up when its name has the word "up". A
trapdoor is one whose point of interest or legend tile says "trapdoor" or
"trap door". The region's own `tiles/` is tried first, then the pack's
root `tiles/`; a kind neither names keeps the door picture. A way picture
is drawn over the whole tile, so bake it at the same size as ground tiles.

### Pixel art

A world drawn in pixel art says so in `world.json`:

```json
"display": { "pixel_art": { "native_tile": 32 } }
```

`native_tile` is one tile's size in art pixels: a whole number from 8 to 64. With it set, the
engine draws the world at a whole-number scale of that size and never smooths a picture, so every
art pixel is a crisp square. The tile is rounded to a whole number of screen pixels, and the
engine publishes the scale it chose as `VEFR_STAGE.pixel` (`{ "native": 32, "k": 3 }` means three
screen pixels per art pixel). A pack without the block is drawn exactly as before.

With `native_tile` set, the rule for the art is:

- Author tiles at `native_tile`: a 32 x 32 tile for `32`. This replaces the "bake at 2x" rule
  above for a pixel-art pack.
- Author characters and objects at their own native size. A 48 px tall hero is drawn 1.5 tiles
  tall, because 48 = 1.5 x 32. Their size comes from the art, not from `sprite_scale`.
- Never resize pixel art in the pack. The engine scales it.

### Things on the map (props)

A prop is a picture drawn over the ground: a rock, a bush, a well. Its
footprint can block walking. Declare props in a region's `contract.json`
under `props`, one object per prop:

```json
"props": [
  { "pic": "well", "at": [5, 2], "size": [1, 2], "block": ["#", "#"] },
  { "pic": "flowers", "at": [7, 6], "block": ["."], "frames": 2, "fps": 4 }
]
```

- `pic` - the picture's file name without its extension. It is looked up as
  `.webp` then `.png` in the region's `props/` folder, then the pack's root
  `props/` folder. Use a transparent picture.
- `at` - `[x, y]`, the tile of the picture's top-left corner.
- `size` - `[width, height]` in tiles; the default is `[1, 1]`. The picture is
  drawn across the whole footprint, bottom edge on the footprint's last row.
- `block` - one string per footprint row, each the width of `size`: `#` is a
  blocked tile, `.` an open one. Leave it out and every tile of the footprint
  blocks walking.
- `frames` - how many frames the picture holds, side by side in one strip
  (1 to 12; the default is 1). The picture's width must divide evenly by it.
- `fps` - how fast the frames change (1 to 12; the default is 4). Reduced
  motion shows frame 0.
- `layer` - `"stand"` (the default) for something that stands up: it is
  drawn in front of or behind people by its bottom row. `"ground"` for
  something flat (a pond, a rug, a patch of flowers): it is drawn under
  everyone, so a person on a dock or a rug is never hidden by it.

A prop is drawn only where the player can see the ground, and it is drawn
in front of or behind people by its bottom row. A blocked prop stops the
hero, monsters and autoexplore the way a wall does.

The validator refuses a prop whose picture is missing, whose footprint leaves
the map, whose `block` does not match its `size`, or whose footprint covers
a speaker, the hero's start, a wake point, a door or a map book. Each message
names the region, the prop's number and its picture.

### People you cannot walk through

In most RPGs a person stands in the way. Set `"people_block": true` in
the `player` block of `world.json` and the hero cannot walk onto a
speaker's tile: pressing toward them turns her to face them. Left out,
the hero can pass through people as before; keep it off if a speaker
stands in a corridor the hero must get through.

## Where your world lives

```text
worlds/your-world/
├── world.json         # pack root: title, phases, bonds, voices
├── logbok.md          # the canon the interview drafted
├── map.md             # the town map
├── ledger.md          # generation log
├── world-tree.md      # act/POI overview
├── voices/            # speaker voice files (+ fragments)
└── acts/act-1/        # act shape: world.json, town/ (contract,
                       # map.md, sprites/, voices/)
```

The contract for every field lives in `src/vefr/world.py`. The
interview writes it; `norns validate` checks it; you can hand-edit
any of it - then validate again, because the tool never trusts your
edit, including the engine's own.

## Cleaning up

```sh
rm -rf worlds/your-world    # gitignored - git status stays clean
```

## Troubleshooting

| Symptom | Truth |
|---|---|
| drafts keep falling back | the smallest brain strains on gated structured drafts - point the interview at `:8084` or any bigger backend |
| `validate` FAIL after a hand edit | the validator names the file and reason; fix, re-run `norns validate --pack worlds/<name>` |
| `build-map` refused to write | validation failed before the write - fix the segments (`--force` writes anyway, then validate) |
| brain unreachable during play | engine-time generation fails closed (an error, never invented lore); the interview itself degrades to scaffold + placeholders |

## See also

- `GETTING_STARTED.md` - install, run, first checks
- `docs/guides/bundled-brain.md` - the model fleet and how to swap brains
- `docs/guides/brain-socket.md` - the provider seam behind `VEFR_LLAMACPP_URL`
- `docs/guides/making-art.md` - style kits, tiles and character art
