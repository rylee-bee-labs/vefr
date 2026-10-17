# vefr#502, first step: what VEFR already does with sound, and one music bed

**2026-10-16.** The owner's recorded decision (issue comment, rolling
interview, 2026-10-16) is **option A**: VEFR may expose a reusable, opt-in
ambient music capability in the always-layer; each game supplies and owns its
own musical identity; defaults stay quiet, with usable mute and volume; no
unexpected autoplay. This note is the inventory the decision asked for first,
and the record of the smallest thing that can honestly be called a
demonstration of it. It changes no pack's audio.

## The inventory: what sound already is

- `web/player/parts/120-sound.js`, in the always-layer, is the whole of the
  engine's audio. Nine synthesized cues (`hit`, `hurt`, `defeat`, `pickup`,
  `door`, `locked`, `level`, `sticker`, `end`), one `AudioContext` made
  lazily on the first cue, each cue a short oscillator ramp at a peak under
  0.08 with an exponential release. Every cue is a moment of play, never a
  timer and never music - the file says so in its own first comment.
- A pack opts in with `"sound": {"theme": "soft"}` in `world.json`
  (`maplab.sound_errors`, the frozen `SOUND` shape, `soft` being the only
  theme). It bakes as `window.VEFR_SOUND_DEF`, the literal `null` for a pack
  that names none.
- The published snapshot is `window.VEFR_SOUND = {theme, on, played: []}` and
  `window.VEFR_SOUND_VOLUME`. `played` records a cue whenever it *would* sound,
  so a harness can prove the cue path without an audio device (jsdom has no
  `AudioContext` at all).
- Menu > Display holds the **Sound** switch and the **Volume** slider, built
  only when the pack opted in, remembered under `vefr-sound-<world>` and
  `vefr-sound-<world>-volume`. Cues are on by default.
- Nothing else in the engine makes a sound. There is no music, no loop, no
  asset loading of any audio kind: `worlds/`, `storyteller_packs/` and
  `templates/` declare no `sound` at all, and no audio file ships in the repo.
  Cottage's soundtrack, if it has one, is that pack's own business and was not
  touched.

So the gap the decision names is real and small: there is a way for a pack to
own nine moments of sound, and no way at all for a pack to own an ambient bed.

## The demonstration in this slice

One optional top-level block, one synthesized bed, off by default:

```json
"music": {"track": "shore"}
```

- `MUSIC` in `src/vefr/shapes.py` holds exactly one required key, `track`,
  and `shore` is the only choice. `maplab.music_errors` names every other
  shape in one plain sentence. A pack with no `music` bakes the literal
  `null` and grows no music row.
- The player reads it as `window.VEFR_MUSIC_DEF` and publishes
  `window.VEFR_MUSIC = {track, on, playing, starts}` beside
  `window.VEFR_MUSIC_VOLUME`, so a test can see that a boot played nothing
  (`playing` false, `starts` 0) without reaching into a private variable.
- Three quiet defaults, each pinned by a test: **off at boot** (nothing
  sounds before a touch, and a remembered "on" waits for this boot's first
  touch, so there is no autoplay); the **volume slider starts at 40**, not at
  full; the **bed peaks at 0.025**, under any cue's 0.06.
- The bed is `shore`: five layered sine notes, six seconds, faded in over a
  second and out over the last 1.2 so the loop seam is a fade rather than a
  click. Synthesized, like the cues - no audio file, nothing to license, no
  third-party asset.
- Display gets a **Music** switch and a **Music volume** slider, built only
  when the pack opted in, beside the sound rows, remembered under
  `vefr-music-<world>` and `vefr-music-<world>-volume`. A mute takes effect
  at once (the loop is disarmed by a generation counter, so a bed already in
  flight cannot re-arm behind a switch that says off).

## What is deliberately not here

This is the first, smallest step. Still open, in the owner's hands or the
next slice:

- **One track.** `shore` demonstrates the capability; it is not a musical
  identity for any game. Pack-authored track data (a pack naming its own
  notes, or its own credited file) is the obvious next step, and the shape
  would have to hold to it before any pack is asked to use music.
- **No pack uses it.** Nothing in `worlds/`, `storyteller_packs/` or
  `templates/` declares `music`, so every shipped game is byte-for-byte as it
  was. Cottage's audio is untouched, as the decision requires.
- **Only the bed loop is gated.** The bed does not yet duck under a cue, fade
  out on the end card, or stop with the page; it runs until it is muted.
- **No ROADMAP move.** The LATER-board line "Music" stays where it is until
  this demonstration has been seen and heard, which is the owner's call.