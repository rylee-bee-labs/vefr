# VEFR Storybook: art bible (Cottage of the Breeze)

**Whose look this is.** VEFR Storybook is **Cottage of the Breeze's** look, kept in VEFR as a worked example a
game may start from. VEFR does not impose it: every game chooses or writes its own design system and art bible
("two games never share one", [making-art.md](../../guides/making-art.md)), and nothing here takes a choice away
from a player. Look (Dark or Parchment), text size, reduced motion and how to move are the **player's**
settings; "Dark by default" is only where Cottage starts.

**Status: the look is decided; the kits are being redrawn (2026-10-12).** Rylee chose Game Boy Advance pixel art
in this storybook palette for the whole art set ("B: GBA pixel art (Recommended)", after a side-by-side style test at
phone size; "No art is sacred. Not even main npc"). The painted Section 1 art (round 20) is the old look, replaced
kit by kit. Every kit drawn from now on follows this page. When a picture and this page disagree, the page is wrong
or the picture is; fix one of them on purpose.

## The feeling
Cozy and storybook: a place that is safe, generous and soft (Daniel Cook's cozy levers: safety, abundance,
softness). Warm light, rounded shapes, nothing sharp or alarming, nothing busy. A player should want to wander.

## One look
- **Game Boy Advance pixel art, storybook-warm** (think *The Minish Cap*, *Mother 3*). Crisp square pixels at one
  density, hard edges, no anti-aliasing, no brush texture, no photographic texture. Chibi people about 2.5 heads
  tall.
- **Outlines:** characters, creatures and objects carry a 1-pixel dark warm-brown outline (about #2b2118). Ground
  and wall tiles carry **no** outline.
- **Light:** warm, from the top left, on everything that stands up (characters, objects, door frames, stair lips).
  Ground tiles are lit **evenly** (no vignette, no spot) so they repeat without seams. Darkness on a floor comes from
  the game's fog, never painted into a tile.
- **Detail by layer:** ground lowest (it repeats, so calm), walls a little more, objects medium, characters the
  most. A barrel never out-details the hero.

## Palette (measured from the approved art, 2026-10-12)
| Use | Colours |
|---|---|
| Cellar floor (warm umber stone) | #4a3d2a #3f321f #574732 #5f4f39 |
| Cellar wall (dark brick) | #2e2015 #402c20 #29170e #493528 |
| Ember floor (warm brick) | #533723 #5e3821 #643f26 |
| Skin and highlights | #f6d0a3 #e4b789 #d3ab7b |
| Warm accents (rust, amber) | #993f22 #be7d3a #e19747 #d8aa4e |
| Greens (cloth, moss) | #73623a #7f7944 |
Saturation stays moderate; the brightest things on a screen are skin, light and the item you are about to pick up.
Every picture is locked to one **master palette** (64 colours, kept with the game's art as `palette.json`), so a
house drawn this week and a barrel drawn next month share their colours.

## Scale (one rule for everything)
- **A tile is 32 x 32 art pixels.** The pack says so (`"display": {"pixel_art": {"native_tile": 32}}`) and the engine
  draws every picture at a whole-number scale with no smoothing (a phone shows 5 device pixels per art pixel).
- **A person is 48 art pixels tall** (1.5 tiles), drawn in 64 x 64 frames standing on the bottom row; a cat about
  22; a dwarf 42. Faces need it: at 32 px tall the eyes stop surviving the shrink from the image model.
- **Objects are drawn at their own size**: a cottage 3 tiles wide (96 px), the tavern and temple 5 (160 px), a tree
  2 tiles wide on a 1-tile trunk. A picture may rise above its footprint; the object layer sorts it by depth.
- **One pixel density everywhere.** A house's pixels are the same size as the hero's.
- Check every kit **in the game at the phone zoom**, not only on a sheet.

## Layers (how the world stacks)
1. **Ground**: seamless repeating floors (flagstone, wood, grass, cobbles). Even light, no outline, no props.
2. **Walls and edges**: wall tiles, plus the pieces where one ground meets another. A legend entry's `edges` names
   one 4 x 4 sheet of transparent pieces (in the region's `tiles/`); the engine lays the piece that matches which
   of the four neighbours share the symbol (`docs/guides/rulesets.md`, "A ground that blends"). Walls meeting a
   floor, and corners, are still one repeating square.
3. **Objects and decals**: houses, trees, the well, barrels, doors, stairs, as **transparent** pictures on the
   object layer (`props` in a region's contract), sorted by depth with the people (Rylee: "a transparent layer or
   something so we can blend it in"). Flat things (a pond, a rug, flowers) go on the ground layer
   (`"layer": "ground"`), under everyone.
4. **Characters and creatures.**
5. **Light and fog**, drawn by the game.

## Perspective
Ground is straight top-down. Things that stand up (people, buildings, doors, furniture) are shown front-on, as in
classic top-down RPGs: a building's front wall faces straight down the screen and its roof is seen from above-front.
Never isometric. A door on the bottom wall of a room is not drawn as a door face (it would sit upside
down); it is a threshold: a doormat with warm light spilling in.

## Making art (the recipe that worked)
- Codex image, **one bundled call per kit** (a grid of related subjects, or one row of six frames for one
  character's poses), with an approved in-game picture as the style reference.
- The image model paints "pixel art" as blocks that wander off a true grid. Each subject is turned into real pixel
  art at its native size: find the block size, take the middle of each block, key the green, despeckle, lock to the
  master palette (the pixel-art tools, vefr#426).
- Subjects are drawn **isolated on flat #00FF00**, nothing touching the cell edge. Cut a grid sheet by cell, not by
  shape: neighbours merge.
- Ground is drawn **filling the cell**, then made seamless at native size as a 3 x 3 grid (`name.grid3x3.webp`).
- **Motion the GBA way**: by recolouring, not repainting. Lamps and windows flicker, coals glow, water shimmers. A
  character's poses come from one strip, so nothing drifts between frames.
- Every kit keeps its source sheet, prompt and credit under `art/source/`.

## Style block (paste into every prompt, word for word)
> Game Boy Advance era pixel art in the same style as the reference image: crisp hard-edged square pixels, every
> pixel visible, a limited warm storybook palette (umber, rust, amber, cream, soft moss green), 1-pixel dark
> warm-brown outlines on objects and characters, light from the top left, no anti-aliasing, no text, no letters,
> no numbers.

Add for buildings and objects: "Classic top-down RPG view as in Game Boy Advance games like The Minish Cap: the
front wall facing straight down the screen, roof seen from above-front, NOT at an angle, NOT isometric." Check every
building for symbols the image model adds on its own (it put a cross on the temple).

## Review
A kit is done when Rylee has seen it in the game at phone size, and when nothing in it out-details the hero or
breaks the palette. A kit that fails is redrawn as a set, not patched one picture at a time.
