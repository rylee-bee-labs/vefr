# VEFR Storybook

> Category: Game UI
> Surface: mobile-first web game (VEFR player); Cottage of the Breeze is its first theme

**Status: draft for Rylee's review (2026-10-12).** The cozy, storybook interface for VEFR games: the world fills the
screen, and everything else is one thumb away. Art direction lives in [ART-BIBLE.md](ART-BIBLE.md). Tokens live in
[tokens.css](tokens.css).

## North star
Rylee: "I should be able to wander around Cottage, discover something interesting, interact with it, manage my bag,
and keep exploring without fighting the interface."

## What is approved (only this gets built)
From Rylee's review on 2026-10-12 (her words in quotes; the full list is kept in the Cottage mission's
`artifacts/APPROVED-UI.md`):
- **Dark is the default; Parchment is the alternative**, chosen in Settings ("Dark as the default, with Parchment
  available in Settings").
- **The world fills the screen.** On a touch phone the camera follows the hero at **52 px tiles** instead of
  shrinking a map to fit ("52 px (Recommended)"). Portrait first; landscape works.
- **Floating joystick** in the lower-left thumb area ("Floating joystick instead of a permanently visible D-pad").
- **One smart action button** in the lower right that says what it will do: Read, Talk, Open, Fight, Go down.
- **Bag button above the smart button**; **B** (back) beside it; **quickslots beside health**, top left; the menu
  top right.
- **Game-contained panels** for the bag, dialogue, notes and settings: they open over the world, they read
  comfortably, and one big Close (or Back/Escape) shuts them. In landscape the bag is a roomy overlay, not a cramped
  side sheet.
- **Simple accessibility:** larger text, reduced motion, an alternative way to move.
- **Ways through drawn as what they are** (door, stairs up, stairs down, trapdoor), as transparent objects over the
  real ground.

Everything else on the OpenDesign boards (control-size slider, left-handed mirror, contrast toggle, sound sliders,
haptics, message-log page, target glow rings, combat feedback) is a **mockup** until Rylee approves it by name.
"Simplicity matters too."

## Layout (portrait 390 x 844, safe areas respected)
- **Top left:** health pill (label 13 px caps, number 16 px bold), then 1 or 2 quickslots (48 px) with count badges.
- **Top right:** menu button, 48 px.
- **Under the top bar, centred:** one message at a time as a small pill (16 px), fading after about 3 s; never over a
  control.
- **Lower left:** the joystick's touch area (the left part of the screen below the top bar); idle it shows only a
  faint 96 px ring; under the thumb a 120 px base and a 52 px knob.
- **Lower right:** smart button 72 px (verb 18 px bold, caption 13 px), B 56 px to its left, Bag 56 px above it.
- **Everything else is a panel**, opened on purpose and closed with one big target.
Landscape puts the same pieces at the two edges with the world in between.

## Controls (feel)
- The joystick snaps to four directions (dead zone 14 px; it changes axis only when the new one leads by 1.4x).
  The first step happens the moment the thumb lands; holding steps one tile every 200 ms; letting go stops at once;
  an open panel stops it.
- The smart button acts once per press, never repeats while held, and ignores a second press for 300 ms.
- Keyboard and gamepad keep working (arrows/WASD move, E/F act, B bag, Esc back).
- No page scrolling, zooming or text selection during play.

## Type (minimums, both looks)
| Piece | Size |
|---|---|
| Body text, descriptions | 17 px, line-height 1.45 (never below 16 px) |
| Item names, dialogue lines | 18-19 px |
| Toast | 16 px |
| Tabs | 15 px label + 18 px icon |
| Badges, captions | 13 px bold (nothing below 13 px) |
| Larger text setting | everything +20% |
Text contrast at least 4.5:1 against its surface in both looks.

## Motion
Panels and toasts ease in over 200-300 ms (ease-out), never snap; nothing flashes or shakes. Reduced motion swaps
every transition for an instant change.

## Looks
- **Dark (default):** warm charcoal surfaces, soft cream text, one amber accent. Calm; lets the painted world glow.
- **Parchment:** cream paper surfaces, dark ink, warm wood accents. The Cottage skin's old look, retuned for
  contrast and size.
