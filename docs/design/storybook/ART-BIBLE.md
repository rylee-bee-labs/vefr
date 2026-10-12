# VEFR Storybook: art bible

**Status: draft for Rylee's review (2026-10-12).** Written from the art she liked in the Cottage of the Breeze
Section 1 beta: the round-20 cellar flagstones and walls, the redrawn residents, and the isolated doors and stairs.
Every kit drawn after this follows it. When a picture and this page disagree, the page is wrong or the picture is;
fix one of them on purpose.

## The feeling
Cozy and storybook: a place that is safe, generous and soft (Daniel Cook's cozy levers: safety, abundance,
softness). Warm light, rounded shapes, nothing sharp or alarming, nothing busy. A player should want to wander.

## One look
- **Hand-painted storybook.** Soft painted edges, gentle brush texture, no hard vector edges, no photographic
  texture, no pixel stair-steps.
- **Outlines:** characters, creatures and objects carry a gentle dark warm-brown outline (about #2b2118 at the
  edge, softened). Ground and wall tiles carry **no** outline.
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

## Scale (one rule for everything)
- **A ground or wall tile is 96 x 96 px of art**, drawn as one square of the world.
- **Characters and creatures are drawn on a 128 x 128 canvas**, standing on the bottom edge, and the game draws them
  at one tile times their `sprite_scale` (a person is about one tile tall; a rat 0.5; the Cellar King 1.7).
- **Objects (doors, stairs, trapdoors, props)** are drawn to fill about 80% of a 96 px tile, so one object reads as
  one square on the map.
- Check every kit **in the game at the phone zoom (52 px tiles)**, not only on a sheet.

## Layers (how the world stacks)
1. **Ground**: seamless repeating floors (flagstone, wood, grass, cobbles). Even light, no outline, no props.
2. **Walls and edges**: wall tiles, plus (next) the pieces where a wall meets a floor, corners and borders, so the
   engine can fit them automatically (autotiling). Today's walls are one repeating square.
3. **Objects and decals**: doors, stairs, trapdoors, barrels, rugs, cracks, as **transparent** pictures over the
   real ground or wall (Rylee: "a transparent layer or something so we can blend it in"). One object serves every
   material beneath it.
4. **Characters and creatures.**
5. **Light and fog**, drawn by the game.

## Perspective
Ground is straight top-down. Things that stand up (people, doors, door frames, furniture) are shown front-on, as
in classic top-down RPGs. A door on the bottom wall of a room is not drawn as a door face (it would sit upside
down); it is a threshold: a doormat with warm light spilling in.

## Making art (the recipe that worked)
- Codex image, **one bundled call per kit** (a grid of related subjects), with an approved in-game picture as the
  style reference; for one character's poses, one pose per call with the approved figure as the reference.
- Subjects that will be transparent are drawn **isolated on flat #00FF00**, nothing touching the cell edge; cut with
  `art/tools/slice_bundle.py`. Glows that bleed into the green (a lantern, light on a mat) need a soft key.
- Ground and walls are drawn **filling the cell**, made seamless with `art/tools/seamless_tile.py`.
- Every kit keeps its source sheet, prompt and credit under `art/source/`.

## Style block (paste into every prompt, word for word)
> Hand-painted storybook game art, warm muted palette (umber, rust, amber, cream, soft moss green), soft painted
> edges, gentle dark warm-brown outline on objects and characters only, warm light from the top left, cozy and
> calm, no text, no harsh contrast, no photographic texture.

## Review
A kit is done when Rylee has seen it in the game at phone size, and when nothing in it out-details the hero or
breaks the palette. A kit that fails is redrawn as a set, not patched one picture at a time.
