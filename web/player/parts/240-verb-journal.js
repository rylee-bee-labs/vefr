
// Verbs record to the packaged player's own journal - the same
// no-failure contract as the server route they mirror
// (/api/combat/action): the action only lives in the log.
//
// `result` is the sentence the verb spoke, which the result line shows
// instead of naming the action (#463). It is optional so an entry
// written before the sentence existed still reads.
const COMBAT_KEY = 'vefr-packaged-combat';
function recordVerb(verb, result) {
  var log = store.getJSON(COMBAT_KEY, []);
  log.push({ verb: verb, phase: STATE.get().phase, result: result || '',
             at: new Date().toISOString() });
  store.setJSON(COMBAT_KEY, log);
  renderCombatLog(log);
}

// Arrivals journal - the packaged twin of /api/journal/move: one
// entry per change of named place under the hero, browser storage
// only, same no-failure contract as the verbs above.
const MOVES_KEY = 'vefr-packaged-moves';
var lastPlace = null;
function journalVisit(poi, x, y) {
  if (poi === lastPlace) return;
  lastPlace = poi;
  var log = store.getJSON(MOVES_KEY, []);
  log.push({ kind: 'move', poi: poi, x: x, y: y, phase: STATE.get().phase, at: new Date().toISOString() });
  store.setJSON(MOVES_KEY, log);
}

// The result line: what the last action DID, in words (#463). It used
// to name the action ("last action: console (dusk)"), which told a
// reader nothing about what Console or an insult actually did - so the
// sentence the verb spoke is the line. An entry with no sentence of its
// own (written before this line existed) falls back to the old
// wording rather than going blank; the phase stays on the title for
// anyone who wants it.
function renderCombatLog(log) {
  var el = document.getElementById('combat-log');
  if (!el) return;
  if (!log || !log.length) { el.textContent = ''; return; }
  var last = log[log.length - 1];
  el.textContent = last.result
    || 'last action: ' + last.verb + (last.phase ? ' (' + last.phase + ')' : '');
  if (last.phase) el.title = last.phase;
}

// The combat line: one plain sentence for the eye and the screen
// reader. A hit is said, never shown by colour alone. It rides the
// same aria-live idiom as #library-live.
//
// Every sentence the world says lands on the Journal's quiet page
// (vefr#484) at the moment it is said; a caller that keeps its own
// line on the page itself passes true, so it is not kept twice.
function combatSay(msg, notOnPage) {
  var el = document.getElementById('combat-live');
  if (el) el.textContent = msg || '';
  if (msg && !notOnPage && typeof journalSay === 'function') journalSay(msg);
}

// The live line as it stands, so a caller can see what an action added
// to it before the monsters' turn writes over it.
function combatText() {
  var el = document.getElementById('combat-live');
  return el ? (el.textContent || '') : '';
}

