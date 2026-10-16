# 484 mockups: the Journal message log and the calm fall card

**Status: mockups for review, awaiting Rylee's pick (vefr#484, owner ballot comment 6222138588,
2026-10-16). No layout is chosen and nothing here is built.** Open any file below in a browser;
each is one self-contained page — no network, no scripts, no images.

| File | The log | The fall card |
|---|---|---|
| [a-the-diary.html](a-the-diary.html) | **The Diary** — the lines are kept as a diary grouped under the place where they were said, newest place first, whispers and falls woven in | A centered reader-style card over a dimmed world: "You fell", the temple line, one gold **Keep exploring** and a quiet **Read the Journal** |
| [b-the-ledger.html](b-the-ledger.html) | **The Ledger** — the Journal grows Whispers/Messages tabs; every line is a row with its kind (said, fight, found, overheard) and its place, newest at the bottom, and the panel follows the newest row | A low card floating **above the fight row**, placed once so it can never sit on Strike |
| [c-the-quiet-page.html](c-the-quiet-page.html) | **The Quiet Page** — one plain page of every line in order, newest at the top, older lines a little quieter (never lighter than the contrast floor) | A **warm hush**: the world dims deep, one small quiet card near the bottom, any input continues |

Every page shows the same four states, as the ballot asks: a phone (390×844, the approved
storybook layout) with the Journal open on the log, the phone fall card, a desktop panel, and
an accessible state (Display > Larger text at +20%, the gold focus ring kept visible, 48px+
targets, 4.5:1 ink, reduced motion = instant change, the log readable as one ordered list and
the card a dialog that says itself aloud).

## What all three keep (not open for change here)

- **The world keeps its one fading line** exactly as approved (docs/design/storybook/DESIGN.md).
  These mockups only decide where the words can be read again.
- **The Journal is one panel, opened the way the Bag opens, with one big Close.** The earlier
  attempt (P4JFIX/P4JTEST) failed because the Journal log did not open behind the menu and the
  Strike button broke; every variant therefore has no second click to open the log, and a fall
  card that never covers the fight verbs.
- **The fall card says the words the game already says** (Death is Cozy, `cozyDeath`): the
  temple line, health whole again, nothing lost. No red, no shake, no timer; it waits for the
  player.
- **Accessibility contract** (docs/guides/accessibility-contract.md): larger text, reduced
  motion, 4.5:1 contrast, 48px targets, focus visible.

## What Rylee is asked to pick

1. **A, B or C** — prose that groups by place, a ledger that sorts by kind, or a plain quiet
   page. (Or a mix named in her words.)
2. **The fall card's shape** — centered reader card (A), low card clear of the verbs (B), or
   the warm hush (C).
3. Anything on this board she wants kept or cut before implementation.

## Left to do after her pick

- Implement the chosen variant in the woven player (`web/player/parts/`), with tests
  (the Journal opens and closes, the fall card shows and never blocks a fight verb).
- No player code changed in this step — these files are mockups only.