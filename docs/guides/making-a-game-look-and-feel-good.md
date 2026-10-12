# Making a VEFR game look and feel good

What we learned making Cottage of the Breeze comfortable on a phone (2026-10-11/12), written down so the next game
starts here instead of from scratch. Rylee, on reading the small-studio way of doing art: "Can we make sure to write
all of this into vefr as knowledge and a way to make game making better? I had no idea!"

The design system this produced is [`docs/design/storybook/`](../design/storybook/DESIGN.md) (with its
[art bible](../design/storybook/ART-BIBLE.md) and [tokens](../design/storybook/tokens.css)).

## 1. Start from a design system, not from screens
A design system is a short written look: colours, type sizes, control sizes, motion, how panels behave, and for a
game an **art bible**. Rylee's first interface was made screen by screen without one; the second was made against
one, and she said: "This new direction is much better than my first attempts without a design system." Write it
first (it can be rough), then draw against it, then correct it.

## 2. Keep three states apart: mockup, prototype, approved
- **Mockup**: an idea drawn to look at (OpenDesign boards).
- **Prototype**: an interaction you can try (a throwaway layer or an experiment branch, never merged as is).
- **Approved**: only what the owner decided to build.
A mockup is not a feature list. "Don't accidentally turn every interesting mockup into a feature requirement."
Keep one written approved list and build only from it. Simplicity matters too.

## 3. Make art the way a small studio does
1. **An art bible first**: palette, light direction, outline rule, detail level by layer, and one scale. Ours:
   [ART-BIBLE.md](../design/storybook/ART-BIBLE.md).
2. **The world is layers that stack**: ground (seamless), walls and their edges (autotiled), objects and decals
   (transparent), characters, then light and fog. Keep detail matched across layers: a painted barrel next to a
   flat floor breaks the illusion.
3. **One scale for everything**: here a tile is 96 px of art; characters are a 128 px canvas drawn at one tile
   times their `sprite_scale`; objects fill about 80% of a tile.
4. **Kits, not single pictures**: draw a place's set together (the cellar kit, the town kit), check it in the game at
   phone zoom, redraw the set if it fails.
5. **Ways through are objects**: a door or a stair is a transparent picture over the real floor or wall, so one
   picture serves every material (pack picture names `way-door`, `way-stairs-up`, `way-stairs-down`,
   `way-trapdoor`, drawn by the engine's way-picture support).

## 4. Recipes that worked
- **Bundle related subjects in ONE image call** (Codex image, `offload image`): a grid of a cast lineup, an icon set,
  four floors or four walls, on a flat #00FF00 background, with an approved in-game picture as the style reference.
  The subjects share one style pass, so they match. Ask for two variants and pick per cell.
- **One character's poses: one pose per call**, the approved figure as the reference, a word-for-word base prompt.
  Sheet-per-call drifts.
- **Cut** a bundle with [`tools/art/slice_bundle.py`](../../tools/art/slice_bundle.py) (keys every backdrop pixel,
  so green between curls or inside a net is removed). Glows that bleed into the green need a soft key.
- **Ground tiles** come out of a bundle's cells with [`tools/art/seamless_tile.py`](../../tools/art/seamless_tile.py)
  (blends each with a half-offset copy so its edges meet).
- **Transparent objects** cut from a filled cell with [`tools/art/way_tile.py`](../../tools/art/way_tile.py) fade
  their edges into whatever is beneath; drawing them isolated on green and slicing is cleaner still.
- **Compare a redraw with the old picture before shipping**: a "cuter" redraw came back more realistic and was
  rejected.
- **Paste the style block** from the art bible into every prompt, word for word.

## 5. A phone UI that gets out of the way
- **The world fills the screen.** On a touch phone the camera follows the hero at a readable tile (52 px for Cottage)
  instead of shrinking a map to fit; a town shrunk to fit a phone drew at 17.7 px and the hero was a speck.
- **Two thumbs**: movement lower left (a floating joystick that appears where the thumb lands), actions lower right
  (one smart button that says what it will do, B beside it, Bag above it). Health and quickslots top left, menu top
  right. Nothing else on screen while exploring.
- **Everything else is a panel**, opened on purpose, readable, closed with one big target or Back/Escape. Do not
  squeeze a menu into a strip to keep the world visible behind it.
- **Sizes**: touch targets 48 px or more (smart button 72, B and Bag 56); body text 16-17 px, nothing below 13 px,
  important labels 18 px or more; text contrast 4.5:1 or better.
- **Control feel** (from the prototype's video tests): a 14 px dead zone; change direction only when the new axis
  leads by 1.4x; first step the moment the thumb lands; one tile every 200 ms while held; stop at once on release; an
  open panel stops movement; the action button acts once per press.
- **No page scrolling, zooming or text selection during play** (`touch-action: none` and friends).

## 6. Accessibility and coziness, the cheap wins
From the Game Accessibility Guidelines' basic tier and the Xbox Accessibility Guidelines:
- large, well-spaced controls; a readable default text size and a larger option;
- no meaning carried by colour alone; text that never advances on a timer;
- reduced motion; an alternative way to move; settings remembered.
From Daniel Cook's cozy-games levers (safety, abundance, softness):
- no time pressure, no alarm-red, a gentle return after a fall;
- generous bags that never feel like a chore;
- warm light, rounded shapes, soft sounds, slow eased transitions (200-300 ms), no surprise pop-ups.

## 7. Test like the player, on video
- Record every build at **phone portrait (390 x 844), phone landscape (844 x 390) and desktop**, with touch emulation,
  and **look at the frames**: can I see her, read every word, reach every button with a thumb, does anything cover
  the world? A green bot said 38 of 39 while the player saw an 80-picture bag, a speck-sized hero and placeholder
  pawns.
- **Judge interactions in motion**, not stills: toasts over a moving hero, a sheet sliding over the world, the joystick
  under a thumb, controls against light and dark floors.
- **Script the interaction checks and log them** (`window.__proto.log`-style), so "looks wrong" and "works wrong" are
  told apart.
- **Trap: a browser with no fonts draws no text.** Playwright Chromium on a host without fonts measures every word at
  0 px and produced two false "bugs" here. Screenshot inside an environment with fonts (or check a test span's width
  first). CI's browser job is the layout authority.

## Sources
- [Game Accessibility Guidelines (basic)](https://gameaccessibilityguidelines.com/basic/)
- [Xbox Accessibility Guidelines](https://learn.microsoft.com/en-us/gaming/accessibility/guidelines)
- [Daniel Cook, "Cozy Games" (Lost Garden)](https://lostgarden.com/2018/01/24/cozy-games/)
- [Top Down Tile Set Design Guide for 2D Games](https://www.flooringclarity.com/tile-set-design-2d-games/)
