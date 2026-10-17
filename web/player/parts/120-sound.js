// ---- sound: a few soft synthesized cues for the moments of play ----
// A pack may opt in (window.VEFR_SOUND_DEF = {"theme": "soft"}); a pack
// that does not leaves window.VEFR_SOUND undefined, and Display gets no
// switch at all. A cue records its name FIRST and only then tries to
// sound, because jsdom has no AudioContext at all: a missing, suspended
// or throwing context must never throw out of a cue. The preference is
// read once, here at boot, from the same per-world key pattern the fog
// and the rule log use, and every storage access is wrapped (a
// sandboxed iframe's browser storage throws).
var SOUND_KEY = 'vefr-sound-'
  + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
// The volume slider sits beside the switch in the same block and is stored
// the same way, one key further on. 0-100, 100 (full) unless the player says
// otherwise; read at every cue, so a slider moved mid-play is heard at once.
var SOUND_VOLUME_KEY = SOUND_KEY + '-volume';
function soundVolume() {
  var n = parseInt(store.get(SOUND_VOLUME_KEY), 10);
  if (!(n >= 0 && n <= 100)) n = 100;
  return n / 100;
}
if (window.VEFR_SOUND_DEF && window.VEFR_SOUND_DEF.theme) {
  var soundOn = true;
  soundOn = store.get(SOUND_KEY) !== 'off';
  window.VEFR_SOUND = { theme: window.VEFR_SOUND_DEF.theme,
                        on: soundOn, played: [] };
  // The player's own volume, as a number 0..1, beside the snapshot above
  // rather than inside it: VEFR_SOUND's three keys are a contract other code
  // reads whole, and a fourth would change what they see.
  window.VEFR_SOUND_VOLUME = soundVolume();
}

// One table for the nine cues the engine names. Each note is
// [start Hz, end Hz, start ms, length ms], so a fall, a rise or a
// sweep is a real ramp on the oscillator's frequency, never two flat
// notes. Sine or triangle, 80-300 ms, one quiet peak under 0.08, an
// exponential release: a nudge at a moment of play - never on a
// timer, never looping, never music.
var SOUND_PEAK = 0.06;
var SOUND_CUES = {
  hit:     { wave: 'triangle', notes: [[220, 150, 0, 90]] },
  hurt:    { wave: 'triangle', notes: [[165, 110, 0, 110]] },
  defeat:  { wave: 'sine', notes: [[240, 170, 0, 140], [175, 110, 130, 150]] },
  pickup:  { wave: 'sine', notes: [[250, 330, 0, 90], [340, 430, 85, 110]] },
  door:    { wave: 'sine', notes: [[180, 95, 0, 260]] },
  locked:  { wave: 'triangle', notes: [[140, 140, 0, 130], [140, 140, 140, 130]] },
  level:   { wave: 'sine', notes: [[220, 275, 0, 90], [275, 350, 90, 100],
                                   [350, 440, 190, 110]] },
  sticker: { wave: 'triangle', notes: [[520, 560, 0, 90], [660, 700, 100, 120]] },
  end:     { wave: 'sine', notes: [[196, 196, 0, 300], [247, 247, 0, 300],
                                   [294, 294, 0, 300]] }
};

var SOUND_CTX = null;
function soundContext() {
  // Made lazily on the FIRST cue, never at boot: by then a user
  // gesture has happened. No AudioContext (jsdom, an old browser)
  // means null and a record with no sound. Everything in try/catch.
  try {
    if (SOUND_CTX) return SOUND_CTX;
    var Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    SOUND_CTX = new Ctor();
    return SOUND_CTX;
  } catch (e) { return null; }
}

// One cue, sounded: a start frequency ramping to an end frequency on
// the oscillator, and a peak gain of at most 0.08 (times the player's
// own volume) falling exponentially toward silence - never a linear
// ramp, never a bare stop. A suspended context resumes on a wrapped
// promise; if any of it throws, the cue stays the record it already
// made. A slider at zero is silence without being a fault: the cue is
// still recorded, because the sound is on and only quiet.
function soundPlay(cue) {
  var ctx = soundContext();
  if (!ctx) return;
  var vol = soundVolume();
  if (vol <= 0) return;
  try {
    if (ctx.state === 'suspended' && ctx.resume) {
      var resuming = ctx.resume();
      if (resuming && resuming.catch) resuming.catch(function () {});
    }
    var at = ctx.currentTime;
    cue.notes.forEach(function (n) {
      var t0 = at + n[2] / 1000, dur = n[3] / 1000;
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = cue.wave;
      osc.frequency.setValueAtTime(n[0], t0);
      osc.frequency.exponentialRampToValueAtTime(n[1], t0 + dur);
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.exponentialRampToValueAtTime(SOUND_PEAK * vol, t0 + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t0);
      osc.stop(t0 + dur + 0.02);
      osc.onended = function () {
        try { osc.disconnect(); gain.disconnect(); } catch (e) {}
      };
    });
  } catch (e) {}
}

// The one entry point, called only at the nine seams of play. It
// records the cue when sound is on (even with no audio device), keeps
// the last 50, and returns with nothing at all when the pack opted out
// or the player turned the switch off.
function soundCue(name) {
  try {
    if (!window.VEFR_SOUND || !window.VEFR_SOUND.on) return;
    var played = window.VEFR_SOUND.played;
    played.push(name);
    if (played.length > 50) played.splice(0, played.length - 50);
    var cue = SOUND_CUES[name];
    if (cue) soundPlay(cue);
  } catch (e) {}
}

// Display > Sound: built at boot, ONLY when the pack opted in, so a
// pack without sound has no switch to find (the ids stay null). A real
// checkbox on a 44px row: keyboard-reachable, the global focus ring
// left alone, and no colour the menu does not already use. Beside it,
// one slider for how loud the cues are - the switch says whether, the
// slider says how much, and there is only ever this one of each.
if (window.VEFR_SOUND) {
  (function () {
    var panel = document.querySelector('[data-panel-body="display"]');
    if (!panel) return;
    var row = document.createElement('p');
    row.className = 'sound-row';
    var label = document.createElement('label');
    var box = document.createElement('input');
    box.type = 'checkbox';
    box.id = 'sound-toggle';
    box.checked = window.VEFR_SOUND.on;
    box.addEventListener('change', function () {
      window.VEFR_SOUND.on = box.checked;
      store.set(SOUND_KEY, box.checked ? 'on' : 'off');
    });
    label.appendChild(box);
    label.appendChild(document.createTextNode(' Sound'));
    row.appendChild(label);

    var volRow = document.createElement('p');
    volRow.className = 'sound-row';
    var volLabel = document.createElement('label');
    volLabel.htmlFor = 'sound-volume';
    volLabel.appendChild(document.createTextNode(' Volume'));
    var vol = document.createElement('input');
    vol.type = 'range';
    vol.id = 'sound-volume';
    vol.min = '0';
    vol.max = '100';
    vol.step = '5';
    vol.value = String(Math.round(soundVolume() * 100));
    var volOut = document.createElement('output');
    volOut.id = 'sound-volume-out';
    volOut.setAttribute('for', 'sound-volume');
    volOut.textContent = vol.value + '%';
    vol.addEventListener('input', function () {
      store.set(SOUND_VOLUME_KEY, vol.value);
      volOut.textContent = vol.value + '%';
      window.VEFR_SOUND_VOLUME = soundVolume();
    });
    volRow.appendChild(volLabel);
    volRow.appendChild(vol);
    volRow.appendChild(volOut);

    // After the fog status line, before "Time of day".
    // The panel's own first sub-heading (a direct child): the touch settings carry a nested one, and
    // insertBefore with a grandchild as the reference throws.
    var subhead = null;
    for (var i = 0; i < panel.children.length; i++) {
      if (panel.children[i].matches('h2.menu-sub')) { subhead = panel.children[i]; break; }
    }
    panel.insertBefore(row, subhead);
    panel.insertBefore(volRow, subhead);
  })();
}

// ---- music: one optional ambient bed the pack asked for (vefr #502) ----
// The recorded owner decision: VEFR may offer a reusable, opt-in ambient
// music capability; each pack owns its own musical identity and may take
// it or leave it. A pack opts in with `"music": {"track": "shore"}` in
// world.json (window.VEFR_MUSIC_DEF); a pack that does not leaves
// window.VEFR_MUSIC undefined and Display gets no music row at all, and
// its audio is byte for byte what it was.
//
// Three things are quiet on purpose. Music is OFF at boot: nothing
// sounds until the player ticks the box, so there is never an
// unexpected autoplay, and the first sound is always a gesture of the
// player's own. The volume starts at MUSIC_DEFAULT (not at full). The
// bed itself peaks lower than any cue (MUSIC_PEAK), so at full volume
// music is still the quietest thing in the game. Like the cues, an
// AudioContext is made lazily on the toggle and every step is wrapped:
// jsdom has none, and a missing, suspended or throwing context must
// never throw out of the toggle.
var MUSIC_KEY = 'vefr-music-'
  + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
var MUSIC_VOLUME_KEY = MUSIC_KEY + '-volume';
var MUSIC_DEFAULT = 40;
// The player's own volume, 0-100, in the same shape as the sound
// slider's key and read at every loop, so a slider moved mid-play is
// heard at the next fade. Absent means the quiet default.
function musicVolume() {
  var n = parseInt(store.get(MUSIC_VOLUME_KEY), 10);
  if (!(n >= 0 && n <= 100)) n = MUSIC_DEFAULT;
  return n / 100;
}
if (window.VEFR_MUSIC_DEF && window.VEFR_MUSIC_DEF.track) {
  // `on` is the player's remembered choice, read the same way the
  // sound switch reads its own. It is NOT a promise to play: a boot
  // that carried a choice over from last time still plays nothing
  // until the player touches the page (see the one-shot listener in
  // the Display block), so `playing` is false and `starts` is 0 in
  // every case at boot.
  window.VEFR_MUSIC = { track: window.VEFR_MUSIC_DEF.track,
                        on: store.get(MUSIC_KEY) === 'on',
                        playing: false, starts: 0 };
  window.VEFR_MUSIC_VOLUME = musicVolume();
}

// One synthesized bed: [Hz, ms] pairs layered from the loop's start, so
// a bed is a chord held long enough to sit under play rather than a
// tune that asks for attention. `shore` is a low open fifth with the
// fifth on top, its notes together, layered as one soft chord fading in over a second and out
// over the last stretch of the loop, so the seam between loops is a
// fade rather than a click. No audio files ship: nothing to license.
var MUSIC_PEAK = 0.025;
var MUSIC_BEDS = {
  shore: { notes: [[110, 6000], [164.81, 6000], [220, 6000],
                   [164.81, 6000], [110, 6000]] }
};

var MUSIC_CTX = null;
// Bumped on every stop. A loop that is already in flight checks it
// before arming the next one, so a mute mid-loop cannot leave the bed
// quietly playing on after the switch says off.
var MUSIC_GEN = 0;
function musicContext() {
  try {
    if (MUSIC_CTX) return MUSIC_CTX;
    var Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    MUSIC_CTX = new Ctor();
    return MUSIC_CTX;
  } catch (e) { return null; }
}

// One pass of the bed, scheduled from the context's clock. Each note is
// an oscillator into its own gain, the whole pass peaking at
// MUSIC_PEAK * the player's volume; `starts` counts the passes asked
// for, so a harness can see that a boot played nothing.
function musicPass(ctx, gen) {
  var bed = MUSIC_BEDS[window.VEFR_MUSIC.track];
  if (!bed) return;
  var vol = musicVolume();
  if (vol <= 0) {
    // Silent at volume 0, but still listening: check again in a second, so raising the slider brings the
    // bed back without turning Music off and on (#530 review).
    try {
      setTimeout(function () {
        if (gen !== MUSIC_GEN) return;
        if (!window.VEFR_MUSIC.on || !window.VEFR_MUSIC.playing) return;
        musicPass(ctx, gen);
      }, 1000);
    } catch (e) {}
    return;
  }
  var at = ctx.currentTime + 0.05;
  var loopMs = 0;
  bed.notes.forEach(function (n) {
    var dur = n[1] / 1000;
    if (n[1] > loopMs) loopMs = n[1];
    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(n[0], at);
    var fadeIn = Math.min(1, dur / 2), fadeOut = Math.max(0, dur - 1.2);
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.linearRampToValueAtTime(MUSIC_PEAK * vol, at + fadeIn);
    gain.gain.setValueAtTime(MUSIC_PEAK * vol, at + fadeOut);
    gain.gain.linearRampToValueAtTime(0.0001, at + dur);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(at);
    osc.stop(at + dur + 0.05);
    osc.onended = function () {
      try { osc.disconnect(); gain.disconnect(); } catch (e) {}
    };
  });
  // The pass is over when the longest note is; arm the next one then,
  // so no timer runs behind a closed page.
  var wait = Math.max(0, (loopMs / 1000) - ctx.currentTime + at);
  try {
    setTimeout(function () {
      if (gen !== MUSIC_GEN) return;
      if (!window.VEFR_MUSIC.on || !window.VEFR_MUSIC.playing) return;
      musicPass(ctx, gen);
    }, wait * 1000);
  } catch (e) {}
  window.VEFR_MUSIC.starts++;
}

// Start: called only from the toggle's own change event, so the
// AudioContext is made inside a gesture and the first note is the
// player asking for it. Everything wrapped; a failure leaves the
// switch where the player put it and the bed silent.
function musicStart() {
  var ctx = musicContext();
  if (!ctx) return;
  try {
    if (ctx.state === 'suspended' && ctx.resume) {
      var resuming = ctx.resume();
      if (resuming && resuming.catch) resuming.catch(function () {});
    }
    var gen = ++MUSIC_GEN;
    window.VEFR_MUSIC.playing = true;
    musicPass(ctx, gen);
  } catch (e) {}
}

// Stop: the switch's word. The generation bump disarms the loop, and
// the nodes already scheduled are stopped where they are (their gains
// are already fading out, so stopping early is a cut at the volume
// slider's level and never a bang).
function musicStop() {
  MUSIC_GEN++;
  try {
    if (MUSIC_CTX) {
      MUSIC_CTX.close().then(function () {}, function () {});
      MUSIC_CTX = null;
    }
  } catch (e) {}
  window.VEFR_MUSIC.playing = false;
}

// Display > Music, built at boot ONLY when the pack opted in, exactly
// like the Sound rows: a real checkbox on a 44px row and one slider
// for how loud the bed is. Off until it is ticked, and remembered in
// this browser under the world's own name.
if (window.VEFR_MUSIC) {
  (function () {
    var panel = document.querySelector('[data-panel-body="display"]');
    if (!panel) return;
    var row = document.createElement('p');
    row.className = 'sound-row';
    var label = document.createElement('label');
    var box = document.createElement('input');
    box.type = 'checkbox';
    box.id = 'music-toggle';
    box.checked = window.VEFR_MUSIC.on;
    label.appendChild(box);
    label.appendChild(document.createTextNode(' Music'));
    row.appendChild(label);

    var volRow = document.createElement('p');
    volRow.className = 'sound-row';
    var volLabel = document.createElement('label');
    volLabel.htmlFor = 'music-volume';
    volLabel.appendChild(document.createTextNode(' Music volume'));
    var vol = document.createElement('input');
    vol.type = 'range';
    vol.id = 'music-volume';
    vol.min = '0';
    vol.max = '100';
    vol.step = '5';
    vol.value = String(Math.round(musicVolume() * 100));
    var volOut = document.createElement('output');
    volOut.id = 'music-volume-out';
    volOut.setAttribute('for', 'music-volume');
    volOut.textContent = vol.value + '%';
    volLabel.appendChild(vol);
    volLabel.appendChild(volOut);
    volRow.appendChild(volLabel);

    function setOn(on) {
      window.VEFR_MUSIC.on = on;
      store.set(MUSIC_KEY, on ? 'on' : 'off');
      box.checked = on;
      if (on) musicStart(); else musicStop();
    }
    box.addEventListener('change', function () { setOn(box.checked); });
    vol.addEventListener('input', function () {
      store.set(MUSIC_VOLUME_KEY, vol.value);
      volOut.textContent = vol.value + '%';
      window.VEFR_MUSIC_VOLUME = musicVolume();
    });

    // A choice carried over from last time waits for this boot's first
    // touch - one listener, removed the moment it runs - so a reload
    // resumes the bed the player asked for without a page that makes
    // sound before anyone has touched it.
    if (window.VEFR_MUSIC.on) {
      var wake = function () {
        document.removeEventListener('pointerdown', wake, true);
        document.removeEventListener('keydown', wake, true);
        try { musicStart(); } catch (e) {}
      };
      document.addEventListener('pointerdown', wake, true);
      document.addEventListener('keydown', wake, true);
    }

    var subhead = null;
    for (var i = 0; i < panel.children.length; i++) {
      if (panel.children[i].matches('h2.menu-sub')) { subhead = panel.children[i]; break; }
    }
    panel.insertBefore(row, subhead);
    panel.insertBefore(volRow, subhead);
  })();
}

