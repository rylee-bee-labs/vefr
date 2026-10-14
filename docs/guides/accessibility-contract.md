# VEFR Accessibility Contract

**Every story deserves every audience.**

Weave your world tree. An AI works beside you, not above you, and you figure
things out together. Make a story, learn something about stories (and maybe
about yourself), then share it with anyone, anywhere.

---

## What VEFR is

VEFR is an engine *and* a game studio. Building is part of the fun: sketching
a map, drafting an item, or peeking at how the engine decided something are all
part of the experience. The Norse naming runs deep because the mythology matters
to the project.

Three things are built on it:

- **The VEFR studio.** A game studio under the World Tree, and a creative tool
  that feels like a game. Each room is a department with a resident who helps:
  the Desk for writing, the Map Room, the Folks, the Vault, the Library, the
  Chronicle for what has happened, and the Boiler Room for settings. Models
  help in the studio; the games it makes are finished artifacts (ADR 0003).
- **Burrito Journalism**, the engine demo and launch title. You sell breakfast
  burritos from a truck. You're good at it. You roll into a new town, people
  try your food, you get popular, you get trusted, and then they start asking
  for help. Soon you're delivering newspapers *and* burritos: "The Daily
  Hash(browns)". Different places play as different kinds of game (a
  Diablo-like dungeon, a food-truck sim, a journalism beat) with one voice and
  one story. There are also mutant water polo players who steal a printing
  press because they think it's neat. It's weird. It's an apocalypse. It's fun.
- **A personal RPG rooted in Norse myth.** It starts as a *Castle of the
  Winds* homage: monochrome, constrained, a UI like every RPG you've played.
  But nothing is what it seems. The health bar is really the journey's phase
  (whispers, doubts, feared, awed). Items have bonds instead of types:
  "given" (it fits badly), "cold" (a tool that doesn't care), "found" (rare,
  made for waiting hands). The quest log is your starred whispers, the moments
  you chose to remember. The runes in the corner are a live cast (what was,
  what is, what asks). As you play and the world learns your story, it turns
  from monochrome tradition into a colourful, living place that's yours; the
  interface blooms with it, because the transformation *is* the game. You
  start out thinking you're the hero saving the world from monsters, but the
  world thinks *you* are the monster. The real journey is learning that there
  is good, and that the old shell isn't the truth.

All three share the same accessible foundation, and all three feel completely
different. That's the point.

---

## Tone

### The AI is a collaborator

The model that helps you build is someone you think alongside, not a tool you
command. The conversation is casual and back-and-forth. Residents speak for it
in the studio, and nothing it drafts is kept until you choose it.

### Interface words: plain first

Buttons, labels, errors and loading messages say plainly what is happening.
Personality lives in the residents' greetings, the art and the ambience lines,
never in a riddle you have to decode to use the tool.

| Instead of | Write |
|---|---|
| `GENERATE WORLD` | `Begin a new world` |
| `EXECUTE` | `Try it` |
| `REVERT TO CHECKPOINT` | `Go back to…` |
| `COMMIT` | `Keep this` |
| `INSPECT PIPELINE STATE` | `See how this works` |
| `ERROR: INVALID INPUT` | `That didn't work. Check the name, then try again.` |

Buttons are invitations in sentence case. Errors say what went wrong and what
to do next.

### Every part can explain itself

Each panel and setting can show what it calls and what it does underneath.
That isn't hidden developer tooling; it's part of the game. You learn how AI
systems work by building a world, and you can look at the wiring whenever
you're curious.

### The journal is version control for your story

The Chronicle and the Hall work like git (go back, branch, bookmark), but the
words stay human. You're not managing branches and commits; you're exploring
paths your story could take and keeping the moments you want to remember.

---

## The Story Lifecycle

A story on VEFR doesn't end when you stop playing. It transforms.

1. **Play it.** You and the AI weave a story together — making choices,
   building the world, watching it grow.
2. **Export it.** When the story is done, export it as an accessible
   e-book. This is the Bilbo moment — closing the notebook, happy it
   happened, a little sad it's over. *"There and back again."* The e-book
   inherits the platform's accessibility: readable by anyone, on any
   device, with the same contrast/font/motion preferences baked in.
3. **Re-import it.** The exported story can be re-imported into the engine
   as a lore pack — the world you built becomes the foundation for someone
   else's story, or your own sequel. The circle closes.

Every story becomes the soil for the next.

---

## The Core Loop

Everything hangs off five beats:

**weave → play → understand → remember → grow**

Make something → play with it → understand it → remember it → grow it.

---

## Values

Before the rules, the why.

VEFR is a platform designed for anyone to tell a story. That means
the person playing — or building — could be anyone. Any background, any
identity, any body, any brain, any life situation. We don't know who's on
the other side of the screen, and we don't need to. The platform works for
them regardless.

**What this means in practice:**

- **Language is neutral and warm.** No gendered defaults. No assumptions
  about who the player is, what they look like, who they love, or what
  they've been through. When we address the player, we say "you" — and
  that "you" means whoever shows up.
- **Defaults are the inclusive floor.** The out-of-box experience isn't
  "normal mode" with accessibility bolted on. It *is* the accessible
  experience. Players opt *up* into more motion, more density, more
  complexity — never the reverse.
- **Fun is not optional.** If building with the engine doesn't feel like
  play, something is wrong. If playing a game on the engine doesn't make
  you want to keep going, something is wrong. Accessibility and joy are
  the same design goal — not competing priorities.
- **No one has to explain themselves.** The settings panel doesn't ask
  *why* you want high contrast or motion off. It just lets you set it.
  Preferences are personal — the platform respects them without
  requiring justification.

---

## Who This Is Really For

Not edge cases. Not special accommodations. Your players — and your
builders.

| Who shows up | What the platform does for them |
|---|---|
| **Someone who can't see the screen clearly** | Three contrast tiers. Luminance-only hierarchy. Screen reader structure. Nothing relies on color alone. |
| **Someone who navigates differently** | 44px targets everywhere. Full keyboard traversal. No precision requirements. Works with whatever input device they have. |
| **Someone whose brain works differently** | Motion off by default. No strobing. Short reading load. Migraine-safe palettes. Collapsed complexity with optional depth. |
| **Someone playing on the bus, in the sun, on mute** | Works on small screens. Readable in bright light. Fully playable without sound — captions and visual cues cover everything. |
| **Someone who just wants to play** | It works. Right away. Without configuration. The defaults are already good. |
| **Someone who just wants to build** | The creative tools feel like play. The AI is right there beside you. You learn by doing, not by reading docs. |

---

## The Seven Rules

Non-negotiable. Every game, every screen, every interactive element —
including the engine's own builder UI and the AI chat.

### 1. Targets ≥ 44px

Every button, tab, toggle, link, and input has a minimum hit target of
44×44px. Compact density mode makes things *look* tighter — it never shrinks
what your finger or keyboard can reach.

```css
button, [role="button"], .tab, .toggle, select, input { min-height: 44px; min-width: 44px; }
```

### 2. Luminance Carries Rank

Your hierarchy is built from light and dark, not color. Hue adds
personality — it never carries meaning. A player with any form of color
vision reads the same hierarchy you designed.

**A hue used for text carries a contrast floor; the same hue used for a
fill does not.** These are two different jobs and they need two tokens.
The engine's own builder UI is the worked example (#218): `--teal` is
the brand and AI-presence colour, tuned for dots, borders and fills,
where WCAG asks nothing of it. Small *labels* need 4.5:1, and the brand
step only reached 4.36 on a card. So text reads `--teal-text` (and
`--teal-text-hi` on hover), one step up the same ramp, which clears it
at 6.25. Repointing `--teal` itself would have fixed today's labels and
left the trap in place for the next person; the two jobs only stay
separate if they have two names.

`tests/test_teal_contrast.py` is the guard: it computes the ratio for
every theme, including the worst case (a 10px badge on a translucent
teal wash), and it fails if any stylesheet takes a text colour from a
fill token.

### 3. Motion OFF by Default

`prefs.motion` defaults to `'off'`. Nothing moves until the player says so.
Subtle mode (≤200ms, color/opacity only) is the first opt-in. Full motion is
never required for gameplay or building.

The OS `prefers-reduced-motion: reduce` is the final word — it overrides
everything, always.

### 4. Text ≥ 14px

Player-facing text never drops below 14px. Body default is 16px. Debug text
can go to 12px. The type scale responds to player preferences from `xs`
through `2xl`.

### 5. Focus Rings Always Visible

Keyboard navigation gets a clear, luminance-based focus ring on every
interactive element. 2px solid, 2px offset. Uses `--ink` by default so it
works regardless of your game's palette or the player's color vision.
Players can switch to accent-colored rings if they prefer.

```css
:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }
```

**And a dialog keeps it.** While a dialog is open - a book, a character's
line, a set of choices, the pause menu - Tab and Shift+Tab walk that
dialog's own controls and never step onto the page behind it. When the
dialog closes, the focus goes back to the control that opened it; if
that control is gone, it goes to the one control every screen has
(Menu). The woven player does this for every `role="dialog"` it opens
(`web/player/parts/045-dialog-focus.js`), so a new dialog gets it
without knowing the rule exists. Pinned by
`tests/test_dialog_focus.py` and `tests/browser/test_dialog_focus.py`.

### 6. Sound = Visual

Every audio event has a visual counterpart. Captions are ON by default.
The game is fully playable on mute. If a player turns off their speakers,
they miss atmosphere — never information.

### 7. Plain Language First

Labels, instructions, and feedback in clear, warm language. Flavor text —
Norse terms in the engine, journalism jargon in Burrito, whatever vocabulary
your game invents — adds character. It's never the only path to
understanding.

---

## The Preference Engine (`prefs.js`)

Every player controls their own experience. You build the settings panel;
the engine handles the plumbing.

### Keys and Defaults

```js
{
  textSize: 'm',           // xs | s | m | l | xl | 2xl
  spacing:  'm',           // tight | m | loose
  font:     'atkinson',    // system | atkinson | opendyslexic | serif
  contrast: 'm',           // m | high | ultra
  palette:  'standard',    // standard | cb-safe
  motion:   'off',         // off | subtle | full
  focus:    'luminance',   // luminance | accent
  density:  'comfortable', // comfortable | compact
  sound: {
    effects: 0.7,
    speech: 0.8,
    ambience: 0.5,
    pairWithVisual: true,
    captions: true
  }
}
```

### How It Works

1. `prefs.js` loads saved preferences from `localStorage` (key:
   `vefr-prefs`), merging with defaults so new keys land safely.
2. It writes a `data-prefs` attribute to `<html>` as a
   space-delimited token string (e.g.
   `text=m spacing=m font=atkinson contrast=m ...`).
3. CSS selectors key off this attribute (`html[data-prefs~="..."]`)
   — no JS needed in the stylesheet.
4. Call `VEFR_PREFS.set({ contrast: 'high' })` to persist,
   `VEFR_PREFS.preview({ contrast: 'high' })` for live preview
   without saving.

Your choices stick: they persist across sessions, can travel to another
browser in a link (`?prefs=`, handled by `prefs.js`), and always respect the
operating system's accessibility settings. Set them once and they follow you.

---

## The Contrast Ladder

Three tiers. Your game defines its own colors using the same CSS custom
property names. The engine applies the tier; your tokens decide what it
looks like.

### Required Tokens

```css
:root {
  --bg:        /* canvas background */;
  --card:      /* panel surfaces */;
  --card-edge: /* borders, dividers */;
  --ink:       /* primary text */;
  --ink-dim:   /* secondary text */;
  --accent:    /* primary accent color */;
}

html[data-prefs~="contrast=high"] {
  /* Higher contrast values — same token names */
}

html[data-prefs~="contrast=ultra"] {
  /* Maximum contrast: pure black/white, thicker borders, heavier weight */
}
```

### What Each Tier Looks Like

| Tier | Feels like | Guidance |
|---|---|---|
| **Standard** | Warm & easy. Comfortable, low-glare, readable. | ≥ WCAG AA (4.5:1 text, 3:1 UI) |
| **High** | Bright & clear. Sharper edges, stronger borders. | ≥ WCAG AAA (7:1 text) |
| **Ultra** | Nothing hides. Pure black, pure white, maximum separation. | Maximum achievable ratios |

### VEFR Engine Defaults

| Token | Standard | High | Ultra |
|---|---|---|---|
| `--bg` | `#131311` | `#0D0D0B` | `#000000` |
| `--card` | `#1D1B17` | `#161412` | `#000000` |
| `--card-edge` | `#3A352C` | `#5A5347` | `#FFFFFF` |
| `--ink` | `#E8E5DF` | `#F5F3EC` | `#FFFFFF` |
| `--ink-dim` | `#A39E92` | `#C2BDB0` | `#E8E8E8` |
| `--accent` | `#C9AD6B` | `#E1C282` | `#FFD56B` |

### Burrito Journalism

| Token | Standard | High | Ultra |
|---|---|---|---|
| `--bg` | `#1B1F22` | `#0D0D0B` | `#000000` |
| `--card` | `#252A2E` | `#161412` | `#000000` |
| `--card-edge` | `#3D4247` | `#5A5347` | `#FFFFFF` |
| `--ink` | `#EDE6D9` | `#F5F3EC` | `#FFFFFF` |
| `--ink-dim` | `#A8A29E` | `#C2BDB0` | `#E8E8E8` |
| `--accent` | `#D97706` | `#FFB833` | `#FFD56B` |

---

## Colorblind-Safe Palette

The `cb-safe` palette shifts hue-dependent distinctions to
luminance-equivalent alternatives. Your game adds its own overrides for
any game-specific hue use:

```css
html[data-prefs~="palette=cb-safe"] {
  /* Shift any color that relies on hue alone for meaning */
}
```

The engine handles phase colors (awed/feared) and bond colors. You handle
yours (e.g. Burrito's stamina bar and NPC indicators).

---

## Building a Settings Panel

The engine provides the preference contract. Your game builds its own
settings panel with its own personality. The panel must:

1. **Show every preference key** — don't hide options. Let the player
   decide what they need.
2. **Use `VEFR_PREFS.preview(patch)` on change** — live preview without
   saving.
3. **Use `VEFR_PREFS.set(patch)` on commit** — persist and notify.
4. **Respect 44px targets** — every control in the panel itself must meet
   the same rules it configures.
5. **Default to the inclusive floor** — the panel opens showing the current
   saved state, not the "normal" state.
6. **No justification required** — the panel doesn't ask *why* someone
   wants high contrast or motion off. It just lets them set it.

---

## Getting Started — Checklist for New Games

The foundation comes first. Your identity follows.

### Layer 1 — The Skeleton (inherited from VEFR)

Import `vefr-foundation.css` — it provides all of these out of the box:

- [ ] All interactive elements have `min-height: 44px; min-width: 44px`
- [ ] Motion defaults to `off` — verify nothing animates at default prefs
- [ ] Focus rings visible on every interactive element via `:focus-visible`
- [ ] Tab stays inside an open dialog, and comes back to the control that opened it
- [ ] Body font is Atkinson Hyperlegible Next with fallback stack
- [ ] All `data-prefs` CSS selectors from the engine are supported
- [ ] No player-facing text below 14px
- [ ] Captions and visual pairing on by default
- [ ] Language is neutral, warm, and assumes nothing about the player
- [ ] Interface words are plain first; residents and AI chat offer, never command

### Layer 2 — The Skin (owned by you)

- [ ] Define `--bg`, `--card`, `--card-edge`, `--ink`, `--ink-dim`,
      `--accent` in all three contrast tiers
- [ ] Define `cb-safe` palette overrides for any hue-dependent tokens
- [ ] Verify contrast ratios: standard ≥ AA, high ≥ AAA, ultra ≥ max
- [ ] Build a settings panel calling `VEFR_PREFS.set/preview`
- [ ] Make it feel like play — your identity references the foundation
      tokens, never overrides target sizes, motion defaults, or reading
      structure
- [ ] Audit all player-facing text for inclusive language — no gendered
      defaults, no assumptions about identity or ability
- [ ] Every panel has a "see how this works" path for the curious

---

*vefr — weave your world tree. every story becomes the soil for the next.*

*made with care for whoever you are, and the story only you can tell.*

---

## References

- Foundation CSS: `web/vefr-foundation.css` (shared accessible skeleton)
- Preferences: `web/prefs.js` (contract, defaults, CSS integration)
- Agent rules: `AGENTS.md` (boundary table, "Always" row)
- Burrito tokens: `Rylee-Bee/burrito-journalism/web/design-tokens.css`
  (skin only — imports vefr-foundation.css)
- Figma source: file `J0iRc8JElLGrJkvCz6L6fk`
  - Foundation: node `16:4`
  - Burrito gameplay: node `8:4`
  - Burrito UI kit: node `8:401`
  - AI chat concept: node `20:261`
  - Roadmap: node `20:4`
  - VEFR workshop concept: node `23:4`
  - VEFR workshop concept: node `25:244`

## Screen-reader testing (local, not in CI)

CI covers the automated half: axe-core on every woven player, plus the
contrast, target-size and motion rules above. It does not drive a real
screen reader, because the library that does - Guidepup
(`@guidepup/playwright`) - supports only VoiceOver on macOS and NVDA on
Windows, with no Linux runner. Running it in CI would mean paying
macOS/Windows minutes, so it stays a local check for now.

On a machine with a screen reader:

1. Install the dev tools once:
   `npm i -D @playwright/test @guidepup/guidepup @guidepup/playwright`.
2. Write a short Playwright script that starts the driver
   (`voiceOver.start()` or `nvda.start()`), opens a woven HTML file at a
   `file://` URL, and asserts the spoken output mentions the room
   description, the verb buttons, and the newest journal line.
3. Stop the driver (`voiceOver.stop()` / `nvda.stop()`).

Guidepup API: <https://www.guidepup.dev/docs/api/class-voiceover>

Revisit a scheduled (not per-PR) macOS job once the player has more
interaction worth speaking.
