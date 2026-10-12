# Making art in the studio

How to make the pictures for a game, whether you are a person with an idea or an assistant helping one.
It is a loop, and every turn of it ends with something you can look at.

**Proof, pick, bulk, process, see it in the game, keep the record.**

## Why we do it this way

The point is not only the pictures. A big model spends tokens once, here, to build the things a small model
can then use cheaply: a **style kit** (the rules and anchors), a **prompt recipe**, a **command-line tool**
that runs it the same way every time, a **record** of every prompt and result, and a **way to search** that
record. Make a game this way and you learn how to make a game, and a little about how a model gets taught:
with templates, approved examples, plain tools and honest records.

That is why the record matters. A picture with its prompt, references, tool and an approved status is a
training example you are free to use. The studio's first experiment trained a small style add-on on 142 of
its own pictures and found it pulled a tiny model clearly toward the house look at half strength (see
`bench/results/pictures-2026-09-26.md`). The pictures you approve here are the next training set, and the
credits lines say where each one came from.

## The loop

1. **Brief one picture.** What it is, how big it is on screen (pick your tile and character sizes: they are
   pack data), and what has to read at that size.
2. **Proof in batches.** Ask a picture tool for several variations in one request, not one request per
   picture. The bake-off tool we use for proofs (Codex's built-in image generation) bills per call, so a
   batch is cheaper: on one run, two pictures in one call used about 40 percent fewer tokens each than two
   separate calls. Treat that as one measurement, not a promise.
3. **Look at it properly.** One tile on its own hides the problems. Put your proofs side by side, repeat a
   tile 2x2, and lay a mock room at the game's real tile size. Seams, stripes, grids and wrong scale show up
   there and nowhere else.
4. **The author picks.** Nothing is approved until the person whose game it is says so.
5. **Bulk with a tool that holds a style.** Once proofs are approved they become the style references. In
   our bake-off (2026-09-30) Alibaba's Wan 2.7 Image Pro followed layout instructions best and kept sprite
   frames the most consistent. One sample per cell: re-check it for your own game.
6. **Process, then see it in the real build.** Size it, cut it out, weave the game and screenshot it. A
   picture that is lovely alone and wrong in the room is caught here.
7. **Keep the record.** Save the original, the exact prompt, the references, the tool and the date beside
   every picture, with a status of draft or approved. It is how a picture stays explainable.

## Swap anything

The studio never assumes a look or a tool. A game has its own **style kit** (palette, rules, a ground and a
wall as anchors, the shared style words); two games never share one. The generator is just a script that
takes a folder, a name, a count, a brief and some reference pictures, and leaves numbered pictures plus
their credits lines. Any tool that fits that shape drops in. Sizes, tile sets, variants and character
sheets belong to the pack. A pack now brings its own tiles and variants; animated character sheets are
still proposed.

## A prompt recipe that worked

- One paragraph of **style words** shared by every picture in a kit (the painting style, how outlines look,
  the palette named with its colour values, "no text", "fills the frame").
- **Size the shapes for the tile**: "only 3 planks across the whole tile", "only 4 or 5 big stones". Without it
  you get many small shapes that turn to noise at tile size.
- Name the palette (hex values) and say "muted" if the tool leans saturated. Say "never pure black" for outlines.
- For a character: attach two pictures. The first is **who** (the existing character), the second is **style**
  (an approved tile). A reference is the strongest instruction.
- For frames: ask for a **turnaround** (front, back, left, right, same scale) and a **walk strip** (four frames,
  same baseline). Sheets stayed consistent where one call per frame would drift.

## What went wrong, so it does not go wrong for you

- Wood came out bright orange and every floor looked alike. Name a muted palette; give each surface its own
  anchor.
- Eight tiny planks per tile. Say how many shapes fit across it.
- A rug is an object, not a tile: repeated, it looks like a window.
- One tile per surface repeats in an obvious grid across a room. Plan 2 or 3 variants, or paint the surface as ONE
  picture and name it `<name>.grid3x3.webp`: the player draws one cell of it per tile, so the floor joins up and
  repeats only every 3 tiles. Draw the picture as one scene, then check the edges where cells meet.
- A request for "pixel art" returned a detailed painting with heavy outlines. If you want true pixel art,
  draw small and quantize; do not expect it from a painter.
- Image tools may draw a person when asked for an animal. Try your monsters early.
- **Pictures in a batch come back in any order.** The tool saves them in the order the files sort, not the order you asked.
  Identify each by looking, then rename. Never promise that picture 1 is the first thing you asked for.
- **"Transparent background" makes the painter draw the grey-and-white checkerboard as real pixels.** Ask for "a plain flat
  light grey background (not white, not a checkerboard)" and clear it when you cut the picture out. Then check: a figure that is
  more than about a tenth pale grey or white still has background in it.
- **Generated sheets are never the size you asked for** (a 4 by 4 sheet came back 1254 pixels wide, which does not divide by 4).
  Cut on rounded edges, leave a small margin so no figure touches the top or the sides, and stand the feet on the bottom edge.
- **A figure that looks realistic among painted ones needs style anchors.** Pass two or three accepted pictures from your own game as
  references and ask for "exactly the same style as the attached". The first cellar rat looked like a photograph; the redo, given the moth
  as an anchor, matched.
- **Seam checks are a heuristic.** A check that compares the pixels across the cell edges flags plank art with strong lines even when it
  looks fine. Look at the picture repeated 2 by 2 before you believe the flag.
- **Put every picture where the author can see it.** A visual learner cannot see files on a build machine. Publish each batch to the
  gallery as it lands (one set per group), and name the sets in plain words.

## For AI assistants

- **State the number of pictures before you start, batch them, and report what the run used.** Quota belongs
  to the owner.
- **Never approve a picture on the author's behalf.** Leave the status as draft.
- **Always save the prompt, references and tool.** No record, no picture.
- **Show, do not describe.** Send a contact sheet or a mock room. Many authors learn by looking.
- **Change one thing per round** so the author can see what each change did.
- **Run the checks on the real pictures, not only on test images.** Two tool bugs (a leftover checkerboard, figures touching the edge) passed their own tests and showed up only on real art.
- **Keep the art tools beside the art.** A game keeps its brief, batch, cut and check scripts in its own folder (Cottage of the Breeze: `art/tools`), so another game can swap in its own.
- **Keep the engine neutral.** Art lives in the pack. A game's names, places and looks never go in `src/`.

Next: [the journey](journey.md) puts this inside the whole path from an empty table to a game you can share.

## Kits, layers and an art bible (what Cottage taught us, 2026-10-12)

A small studio keeps a whole game looking like one game with three habits, and VEFR games should too:

- **An art bible before the art**: palette, light direction, outline rule, detail level by layer, and one scale for
  everything. Cottage's (the Storybook look) is
  [docs/design/storybook/ART-BIBLE.md](../design/storybook/ART-BIBLE.md); each game writes its own, the same
  shape, and may start from that one.
- **Layers that stack**: seamless ground, walls with their edges, transparent objects (doors, stairs, props),
  characters, then the game's light and fog. Match the detail across layers.
- **Kits, not single pictures**: draw a place's set in ONE bundled image call (a grid on flat #00FF00, an approved
  in-game picture as the style reference), cut it with `tools/art/slice_bundle.py`, make ground seamless with
  `tools/art/seamless_tile.py`, fade a filled object into the floor with `tools/art/way_tile.py`, then look at the
  kit in the game at phone zoom.

The whole story, with the phone UI and how to test like a player, is
[making-a-game-look-and-feel-good.md](making-a-game-look-and-feel-good.md).

## Pixel art, the Game Boy Advance way (what Cottage taught us, 2026-10-12)

Cottage of the Breeze chose true pixel art after a style test: the same six subjects painted two ways, then laid
out at the game's real phone size. Look at a style test where it will be played, never only on a sheet.

- **Tell the engine.** `"display": {"pixel_art": {"native_tile": 32}}` in `world.json` draws every picture at a
  whole-number scale with no smoothing, and characters, sheets and props at their own art size
  (`world-creation.md`, "Pixel art").
- **Pick the native size from the faces.** At 21 x 32 px a shrunk image-model figure loses its eyes; at 32 x 48 it
  keeps them. Cottage uses 32 px tiles and 48 px people.
- **One pixel density.** Shrink every subject to its planned native size, so a house's pixels are the size of the
  hero's.
- **Real pixels from painted ones.** An image model's "pixel art" is blocks that wander off a grid. Find the block
  size, take the middle of each block, key the backdrop, remove lone specks, and lock every picture to one master
  palette (`tools/art/pixelize.py`, below).
- **Front-on, not isometric.** Say "the front wall facing straight down the screen, NOT isometric", or buildings
  come out at an angle and will not sit on the grid.
- **Back views squash** unless a back view is the reference. Draw the front first, then use a good back view from an
  action strip as the reference for the back walk.
- **A character's poses come from one strip.** Six frames in one row on one ground line (idle, idle breathing, four
  walk steps; or pick up, hold, three swing frames, flinch). Cut the frames apart by shape, not evenly, or a swung
  stick that crosses into the next slot gets sliced.
- **Cut a grid sheet by cell.** Twelve props in a 4 x 3 grid merge into nine when found by shape.
- **Motion by recolouring.** Lamps and lit windows flicker, coals glow, water highlights slide a pixel: every frame
  is the same picture with a few colours changed, so nothing drifts. Keep the change to the light itself; a rust
  roof is close enough in colour to a lamp to shimmer with it.
- **Check what it added.** The image model put a cross on a village temple. Check every building for symbols nobody
  asked for.

### The pixel-art tools

Four tools in `tools/art/` do the steps above. Each needs Pillow and answers `--help`; run them as
`uv run --with pillow tools/art/<tool>.py ...`. Each writes hard pixels (alpha 0 or 255) and takes `--palette`, a
file of `{"colors": ["#rrggbb", ...]}`.

1. **A master palette** from pictures the author approved. It keeps only colours those pictures already use:

   ```sh
   uv run --with pillow tools/art/pixelize.py palette art/palette.json approved/*.png --colors 32
   ```

2. **Real pixels** from one painted picture. The tool finds the block size and offset on each axis, follows a grid
   that wanders, takes each block's middle pixel, keys a flat backdrop (`--key auto`, or `#00ff00`, or `none`),
   removes lone specks and locks colours to the palette. It prints the block size it found. If that is wrong,
   give `--block 16` (and `--offset X,Y`):

   ```sh
   uv run --with pillow tools/art/pixelize.py image painted/house.png art/house.png --palette art/palette.json --trim
   ```

3. **A walk sheet** from one-row strips of a character (pixelize each strip first). `PATH=SPEC` says where the
   strip's figures go, left to right: `[dir/]state[:N]`, with the direction `down` when it is left out. `-:N`
   skips figures. The tool cuts figures by shape, stands them on one baseline, scales them all by one factor
   (`--height`), and writes `hero-sheet.png`, `hero.sheet.json` (the engine's shape, see
   [rulesets.md](rulesets.md), "Walk sheets") and the still `hero.png`:

   ```sh
   uv run --with pillow tools/art/make_sheet.py --out sprites/hero --height 48 \
       idle.png=idle walk.png=walk action.png=act,attack:3,up/idle,hurt
   ```

   If the tool counts more or fewer figures than the spec names, it stops. Usually two figures touch, or a speck is
   left over.

4. **Motion by recolouring.** A role is `KIND:COLOURS`, and the colours are the exact colours in the picture. There
   are three kinds. `cycle` steps the colours along the list (water). `glow` makes them breathe (coals). `flicker`
   dims them now and then (lamps, lit windows). `--smoke X,Y` adds small smoke above a chimney top. Nothing else
   changes between frames. The output is one row of frames (`--split` also writes each frame):

   ```sh
   uv run --with pillow tools/art/animate.py art/house.png art/house-anim.png --frames 6 \
       --role flicker:#ffe08a,#f0b050,#b07830 --role cycle:#5aa0d8,#7cc0f0,#a8dcff
   ```

   The engine does not play prop animations yet. The strip is ready for when it does.

5. **A kit** of bundled sheets becomes props at their planned native sizes and seamless 3 x 3 ground grids
   (`NAME.grid3x3.png`, one picture the player draws a cell of per tile), all locked to one palette. The tool cuts
   each sheet by cell, never by shape. A plan file names every cell and its size:

   ```json
   {
     "palette": "palette.json",
     "tile": 32,
     "sheets": [
       {"image": "town-props.png", "grid": "3x1",
        "props": [{"name": "lamp", "size": [12, 32]}, {"name": "barrel", "height": 20}, null]},
       {"image": "town-ground.png", "grid": "2x2", "ground": ["grass", "cobbles", "dirt", null]}
     ]
   }
   ```

   ```sh
   uv run --with pillow tools/art/process_kit.py kits/town/plan.json --out staging/town
   ```

   `null` skips a cell. A prop with `size` fits inside that box and stands on its bottom edge. A prop with only
   `height` takes the width its shape needs. Props go to `staging/town/sprites/` and ground goes to
   `staging/town/tiles/`. Look at them in the game before you copy them into the pack.

The tests (`tests/art_cut/test_pixel_tools.py`) draw small pictures and check each promise:

```sh
uv run --group test --with pillow pytest -q tests/art_cut/test_pixel_tools.py
```
