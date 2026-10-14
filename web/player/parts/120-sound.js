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

