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
