// ---- time that costs something (world.json "time") ----
// A pack that declares no `time` block has none of this: no Rest button,
// no Rest key, a free phase rail, and a phase that lives in memory only -
// exactly as before. Every key here answers to that one declaration.
//
//   "rest": true      a Rest verb in the action row (and R, from the one
//                     keybinds table) that turns the watch on by exactly
//                     one phase per press and fires the same
//                     `phase-changes` event the rail fires.
//   "rail": "locked"  the rail's free jump is hidden, so time moves only
//                     by resting and by rules that change the phase.
//   "persist": true   the standing phase is saved per world under its own
//                     key (`vefr-time-<world>`) and restored on reload.
//
// The save is written only when the pack asks for it, so a pack that does
// not opt in saves byte for byte what it saved before (tests/test_store_keys.py
// is the frozen contract on that).
function timeBlock() {
  var t = window.VEFR_WORLD && window.VEFR_WORLD.time;
  if (!t || typeof t !== 'object' || Array.isArray(t)) return null;
  return t;
}
function timeRestOn() {
  var t = timeBlock();
  return !!(t && t.rest === true);
}
function timeRailLocked() {
  var t = timeBlock();
  return !!(t && t.rail === 'locked');
}
function timePersistOn() {
  var t = timeBlock();
  return !!(t && t.persist === true);
}
function timePhases() {
  var p = window.VEFR_WORLD && window.VEFR_WORLD.phases;
  if (!p || typeof p !== 'object' || Array.isArray(p)) return [];
  return Object.keys(p);
}
function timePhaseNow() {
  return STATE.get().phase;
}
function timeSaveKey() {
  return 'vefr-time-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
// The phase a persist pack left off at, or null: no `persist`, no save, a
// save that is not an object, or a phase this bake does not declare (a
// phase the pack dropped since the save was written) are all "start as
// the first phase", which is what every pack did before this part.
function timePhaseLoad() {
  if (!timePersistOn()) return null;
  var saved = store.getJSON(timeSaveKey(), null);
  if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return null;
  var id = saved.phase;
  if (typeof id !== 'string' || timePhases().indexOf(id) === -1) return null;
  return id;
}
function timePhaseSave(id) {
  if (!timePersistOn() || typeof id !== 'string') return;
  store.setJSON(timeSaveKey(), { v: 1, phase: id });
}
// The phase a press of Rest turns to: the next one in the order the pack
// wrote them, and the first again after the last (a watch that comes
// round is a watch, not a dead end). One press moves time exactly one
// step; it never walks on to the next phase that wants something.
function timeNextPhase() {
  var ids = timePhases();
  if (!ids.length) return null;
  var at = ids.indexOf(timePhaseNow());
  if (at === -1) return ids[0];
  return ids[(at + 1) % ids.length];
}
// The one press of Rest. True when the watch turned, false when the pack
// has no Rest action or no phase to turn to - a pack that did not opt in
// is never moved, by key or by button.
function timeRest() {
  if (!timeRestOn()) return false;
  var next = timeNextPhase();
  if (!next) return false;
  gotoPhase(next);
  return true;
}
// The phase the game opens on: the one the save left off at when the
// pack persists it, else the first phase, which is what every pack has
// always done.
function firstPhaseForPlay() {
  return timePhaseLoad() || timePhases()[0] || null;
}
// The Rest verb in the action row, once, when the pack declares it. It
// carries no `data-verb`, so the fight verbs' own handler (which journals
// a press and runs a turn) never sees it: resting is not an attack. The
// key letter is read from the one keybinds table, the same road every
// other button's letters come from.
function wireTimeRest() {
  if (!timeRestOn()) return;
  var row = document.getElementById('verb-row');
  if (!row || row.querySelector('[data-rest]')) return;
  var b = document.createElement('button');
  b.type = 'button';
  b.id = 'rest';
  b.dataset.rest = '1';
  var label = document.createElement('span');
  label.className = 'verb';
  label.textContent = 'Rest';
  var key = document.createElement('kbd');
  key.textContent = keybindKeyName(keybindKeys('rest')[0] || 'r');
  b.appendChild(label);
  b.appendChild(document.createTextNode(' '));
  b.appendChild(key);
  // Held off for a moment so one press is one press: a held click, or a
  // click that lands twice, must not turn two phases.
  b.addEventListener('click', function () {
    if (b.getAttribute('aria-disabled') === 'true') return;
    b.setAttribute('aria-disabled', 'true');
    timeRest();
    window.setTimeout(function () { b.removeAttribute('aria-disabled'); }, 400);
  });
  row.appendChild(b);
  // The letter on it is the player's chosen key, read from the table
  // (the same place every other button's letter comes from).
  updateKeyLetters();
}
// A harness-readable snapshot of the standing time (precedent:
// window.VEFR_KEYBINDS, window.VEFR_COMBAT): what the watch stands at,
// what the pack declared about waiting, and whether the rail is a jump
// or a locked thing. Read-only, and present for every pack - a pack that
// declares no `time` reads the same shape with its three opt-ins false.
window.VEFR_TIME = function () {
  return {
    phase: timePhaseNow(),
    phases: timePhases(),
    rest: timeRestOn(),
    railLocked: timeRailLocked(),
    persist: timePersistOn()
  };
};