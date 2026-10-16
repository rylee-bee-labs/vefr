# The game-neutral launcher around the woven Player (vefr#454)

**Status: step 1 built** (2026-10-16). This note records the scoped
design direction the owner chose, the smallest first step that was
built under it, and - plainly - everything that is deliberately not
built yet.

Rylee's decision, from the owner ballot (issue #454 comment 6222137761,
2026-10-16):

> Rylee chooses a SMALL shared, game-neutral launcher around the
> existing woven Player. Games retain their own identity and skins.
> Reuse existing title/pause/settings/input rather than duplicate
> controls or create a new framework. Treat as scoped design
> direction, not approval to merge/deploy.

That direction is not re-opened here. It is recorded as an ADR-shaped
note rather than an ADR because the full shell is not decided yet -
only its direction and its first step.

## Why

`vefr weave` writes one complete game per file: the pack's own title
screen, skin, accent, sounds, saves and rules ride inside the woven
HTML. What does not exist yet is a neutral front door - a page where
the games a server holds are listed and any one of them can be
played. The studio (`web/app.html`, `web/js/rooms/launcher.js`) has a
play pane, but it is the authoring house's pane: it belongs to the
workshop flow, and it is not a place to hand a player.

The issue asks for a shell with pause, resume, display/accessibility
options, input affordances, fullscreen and game metadata. The decision
bounds it: SMALL, shared, game-neutral, and **reusing** the existing
title/pause/settings/input - the launcher must not grow a second title
screen, a second pause menu, or a competing input path (revived #317
keeps input to one logical player action path). No new framework, no
new engine, and no game-specific references in the shell.

## Design

The launcher is a shell with almost nothing in it. In one sentence:
**it lists the woven games the server holds, and it opens each one
whole, inside one sandboxed frame.**

- **A game is a woven file.** The playable unit the launcher lists is
  the thing the engine already produces: a self-contained woven HTML
  in the server's weave output dir (`dist/`, the same tree
  `ratatoskr weave` and the served builder write to). A pack that was
  never woven is not listed - the launcher opens games, it does not
  make them. Weave-on-demand from the launcher is a later step.
- **The identity is the game's.** The listing reads each woven file's
  own baked `<title>` (`_woven_title`): the launcher contributes no
  name of its own, and no game's strings reach the shell's DOM as
  markup - only as text, because packs may be imported.
- **Opening hands over the whole player.** The game runs in the
  launcher's one frame, `sandbox="allow-scripts"` and nothing more -
  the exact regime the studio play pane already ships, so a woven page
  (opaque origin, no storage of the surrounding page) can never reach
  the shell. The response behind the frame carries the same
  `Content-Security-Policy: sandbox allow-scripts`, and both doors
  (studio pane, launcher) serve through one builder
  (`_serve_woven_playback`), so they cannot drift apart. The game's
  own title screen is the game's Begin button; the shell's chrome is
  one bar (the way back, and the game's own name as text) and the
  frame. Leaving a game empties the frame - the game stops, and its
  own durable saves are its own affair.
- **Separate from the studio, sharing its guards.** The launcher page
  (`GET /launcher`, `web/launcher.html` + `web/launcher.js`) is not
  `app.html` and loads no studio code. Its two routes live in their
  own `/api/launcher/` namespace but delegate to the same strict
  helpers the builder routes use (`_woven_file`'s match-then-lookup,
  never a request string joined onto a path), so the route guard
  (`tests/test_web_routes.py`) covers the shell exactly as it covers
  the studio.

## Proof it changed nothing about how a game plays

No player part (`web/player/parts/`) and no weave byte is touched; the
woven sample's digest is unchanged. The shell adds routes and a page
and nothing else. `tests/test_launcher.py` (written first, failing
first) pins the three behaviours that exist so far:

- **listing** - the games route returns every woven file, newest
  first, each under its own baked title, ignoring what is not a woven
  `.html`, and an empty house is an empty list;
- **opening** - the play route serves the actual woven player whole
  (a real weave through the served builder, its own `ts-title` in the
  body), inline, behind the same sandbox CSP as the studio pane, and
  refuses any name the server did not write;
- **neutrality** - the page bakes no pack's name and carries no second
  title screen, and the shell's JS places game strings as text only.

## Later steps (explicitly deferred, in the issue's own order)

- Pause/resume, display and accessibility options, gamepad/keyboard/
  touch affordance detection, fullscreen, game metadata in the shell
  - each reused from the existing player parts, never duplicated.
- `.vefr` archives in the listing and opening flow (ADR 0019's format
  landed; the launcher still lists woven HTML only, as the issue's
  "support existing woven HTML immediately" step says).
- Weave-on-demand, so an un-woven pack can be listed too.
- Embeddability constraints, sandbox origin/storage and frame sizing
  written down as a contract; viewport, orientation, focus,
  reduced-motion and failure testing on desktop and phone.
- Desktop native and PWA packaging - optional targets, not MVP.

## Risks

- Two doors to one file (studio pane, launcher) invite divergence; the
  shared `_serve_woven_playback` builder and the same-way test are the
  guard, and any third door must go through it too.
- The listing reads each file's head on every request; fine for a
  shelf of games, and it re-reads nothing else.