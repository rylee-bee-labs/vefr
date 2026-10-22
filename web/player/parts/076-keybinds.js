// ---- keybinds: the one table every named surface's keys come from ----
// Rylee's decision on vefr#508 (2026-10-16): the keys for gameplay,
// reading, the Journal, the menu and the keys that mean the same thing
// on every surface (the always-layer) are the player's to change. This
// part is the table, and the Controls panel that edits it; the one
// keydown handler the player already has (510-rules-closure-surfaces.js)
// asks the table, so there is no second input system - a key the player
// chooses travels the same road the default always did.
//
// The defaults are the keys the game shipped with, and they are the
// answer until the player changes one. A change replaces its action's
// keys, and Reset puts every default back. The save is the DELTA from
// the defaults - only the actions the player actually changed - so a
// save written before this part existed loads as itself (no row, so
// the defaults), and a row some other version wrote that this one does
// know nothing about is kept but never read.
//
// Three keys are not the table's to give, and the panel says so
// plainly when someone reaches for one: E keeps answering for Interact
// on every surface as the unadvertised alias (Rylee, 2026-10-14, the
// one decision tests/test_interact_key_name.py keeps); Space and Enter
// stay the browser's own button keys, which every focused control
// answers to first; and the digits stay on the fight verbs that print
// them (#463).
//
// One keybinds save, not one per world: the reading and sound keys
// carry each world's own answer, but the keys are the player's hands,
// and the hands play every world the same way.
var KEYBIND_KEY = 'vefr-keybinds';

// The contexts the player reads in the Controls panel, in the order
// their rows appear. `always` is the always-layer: the keys that mean
// the same thing on every surface.
var KEYBIND_CONTEXTS = [
  { id: 'always', name: 'Everywhere' },
  { id: 'gameplay', name: 'Gameplay' },
  { id: 'reading', name: 'Reading' },
  { id: 'journal', name: 'Journal' },
  { id: 'menu', name: 'Menu' }
];

// Which surfaces a context's keys are live on. Two actions collide when
// their contexts share a surface: the walking keys (gameplay, the
// Journal, the menu, and always) are all pressed on the same map, the
// reading keys and the menu key are pressed with a note open. Gameplay
// and reading share nothing, which is why A can move left on the map
// and turn the page back in a note, as it always has.
var KEYBIND_SURFACES = {
  always: ['walk', 'read'],
  gameplay: ['walk'],
  reading: ['read'],
  journal: ['walk'],
  menu: ['walk', 'read']
};

// The one list of actions. `keys` are the defaults, the keys the game
// shipped with; a player's choice replaces the whole row for that one
// action. The labels are the player's own words, the same words the
// How-to-play panel and the buttons use.
var KEYBIND_ACTIONS = [
  { id: 'interact', context: 'always', label: 'Use what is near you',
    keys: ['f'] },
  { id: 'up', context: 'gameplay', label: 'Move up',
    keys: ['ArrowUp', 'w'] },
  { id: 'down', context: 'gameplay', label: 'Move down',
    keys: ['ArrowDown', 's'] },
  { id: 'left', context: 'gameplay', label: 'Move left',
    keys: ['ArrowLeft', 'a'] },
  { id: 'right', context: 'gameplay', label: 'Move right',
    keys: ['ArrowRight', 'd'] },
  { id: 'whisper', context: 'gameplay', label: 'Listen for a rumor',
    keys: ['q'] },
  { id: 'bag', context: 'gameplay', label: 'Open the bag',
    keys: ['b'] },
  { id: 'explore', context: 'gameplay', label: 'Walk the unexplored dark',
    keys: ['o'] },
  { id: 'fog', context: 'gameplay', label: 'Turn the dark on and off',
    keys: ['v'] },
  { id: 'rest', context: 'gameplay', label: 'Rest until the watch turns',
    keys: ['r'] },
  { id: 'pageBack', context: 'reading', label: 'Turn the page back',
    keys: ['ArrowLeft', 'a'] },
  { id: 'pageForward', context: 'reading', label: 'Turn the page forward',
    keys: ['ArrowRight', 'd'] },
  { id: 'journal', context: 'journal', label: 'Open the Journal',
    keys: ['j'] },
  { id: 'menu', context: 'menu', label: 'Open the menu, and close what is open',
    keys: ['Escape'] }
];

function keybindAction(id) {
  for (var i = 0; i < KEYBIND_ACTIONS.length; i++) {
    if (KEYBIND_ACTIONS[i].id === id) return KEYBIND_ACTIONS[i];
  }
  return null;
}

// One action the panel does not list to a pack that has no use for it:
// Rest exists only for a pack that declared `"time": {"rest": true}`
// (255-time-rest.js). The row is in the table either way - so a key the
// player already chose for it is still kept and still read - but a pack
// with no Rest action is shown no Rest row, exactly as it was shown none
// before this part existed.
function keybindListed(a) {
  if (a.id === 'rest') return timeRestOn();
  return true;
}

function keybindSharesSurface(a, b) {
  var mine = KEYBIND_SURFACES[a] || [], theirs = KEYBIND_SURFACES[b] || [];
  for (var i = 0; i < mine.length; i++) {
    if (theirs.indexOf(mine[i]) !== -1) return true;
  }
  return false;
}

// A single letter answers to both its cases, exactly as the spelled-out
// checks always did ('f' and 'F', 'w' and 'W'); anything longer is the
// name the browser gives it ('ArrowUp', 'Escape') and matches exactly.
function keybindNormalize(key) {
  return (key && key.length === 1) ? key.toLowerCase() : key;
}

// The saved delta, read fresh every call and never cached, like the
// reading keys: a save that arrives late must still be found. A save
// that is not an object (blocked storage, a corrupted blob) reads as
// empty and every action keeps its defaults.
function keybindSaved() {
  var saved = store.getJSON(KEYBIND_KEY, {});
  if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {};
  return saved;
}

// This sitting's choices, kept beside the save so a change is felt at
// once and the save is only written when a change is made.
var keybindChosen = {};

// The keys one action answers to right now: the player's choice, else
// the saved row, else the defaults. A row that is not a list of strings
// is not a row, and the defaults answer.
function keybindKeys(id) {
  var a = keybindAction(id);
  if (!a) return [];
  var own = keybindChosen[id] || keybindSaved()[id];
  if (Array.isArray(own) && own.length) {
    var keys = own.filter(function (k) { return typeof k === 'string' && k; });
    if (keys.length) return keys;
  }
  return a.keys.slice();
}

// Does `key` answer for `action` right now? The question the one
// keydown handler asks; nothing else decides what a press does.
function keybindOn(action, key) {
  if (typeof key !== 'string' || !key) return false;
  var want = keybindNormalize(key);
  var keys = keybindKeys(action);
  for (var i = 0; i < keys.length; i++) {
    if (keybindNormalize(keys[i]) === want) return true;
  }
  return false;
}

// Write the delta: every action whose keys are not its defaults, and
// every row another version saved that this one does not know (kept as
// it came - not this version's place to erase it). Nothing changed
// means nothing saved, so a player who never opens the panel never
// writes a key.
function keybindApply() {
  var saved = keybindSaved();
  var delta = {};
  Object.keys(saved).forEach(function (id) {
    if (!keybindAction(id) && Array.isArray(saved[id])) delta[id] = saved[id];
  });
  KEYBIND_ACTIONS.forEach(function (a) {
    var now = keybindKeys(a.id);
    if (JSON.stringify(now) !== JSON.stringify(a.keys)) delta[a.id] = now;
  });
  if (Object.keys(delta).length) store.setJSON(KEYBIND_KEY, delta);
  else store.remove(KEYBIND_KEY);
}

// The words a key reads as, on the panel and on the buttons' own key
// letters. Single letters read uppercase, the way the shipped key
// letters always have.
function keybindKeyName(key) {
  if (key === ' ') return 'Space';
  if (key === 'ArrowUp') return 'Up arrow';
  if (key === 'ArrowDown') return 'Down arrow';
  if (key === 'ArrowLeft') return 'Left arrow';
  if (key === 'ArrowRight') return 'Right arrow';
  return key.length === 1 ? key.toUpperCase() : key;
}

// Why a key cannot be given to an action, in one plain sentence, or
// null when it can. The three reserved answers first (E, Space and
// Enter, the digits), then a key another action already answers to on
// a surface this one shares - the collision warning, with the way out
// in the same breath: choose a different key.
function keybindRefused(id, key) {
  var norm = keybindNormalize(key);
  if (norm === 'e') return 'That key is kept for Interact. Choose a different key.';
  if (norm === ' ' || norm === 'Enter')
    return 'Space and Enter always answer for Interact too. Choose a different key.';
  if (/^[1-9]$/.test(norm))
    return 'The number keys stay on the fight verbs printed on them. Choose a different key.';
  var mine = keybindAction(id);
  if (!mine) return 'That action is not one this game knows.';
  for (var i = 0; i < KEYBIND_ACTIONS.length; i++) {
    var other = KEYBIND_ACTIONS[i];
    if (other.id === id) continue;
    if (!keybindSharesSurface(mine.context, other.context)) continue;
    if (keybindOn(other.id, key)) {
      return keybindKeyName(key) + ' already answers for ' + other.label
        + '. Choose a different key.';
    }
  }
  return null;
}

// The buttons' key letters follow the table, so what a player chose is
// what the screen says (the shipped letters are the defaults, so
// nothing moves until something is changed).
function updateKeyLetters() {
  function letter(id) {
    var keys = keybindKeys(id);
    return keys.length ? keybindKeyName(keys[0]) : '';
  }
  function set(btnId, action, tip) {
    var btn = document.getElementById(btnId);
    if (!btn) return;
    var name = letter(action);
    if (!name) return;
    var kbd = btn.querySelector('kbd');
    if (kbd) kbd.textContent = name;
    if (tip) btn.title = tip + ' (' + name + ')';
  }
  set('interact', 'interact', null);
  set('talk', 'interact', 'Talk');
  set('whisper', 'whisper', 'Listen');
  set('bagbtn', 'bag', 'Bag');
  set('explore', 'explore', 'Explore');
  // The Rest verb's own letter follows the table too, but only a pack
  // that has a Rest verb has a button to set it on.
  if (timeRestOn()) set('rest', 'rest', 'Rest');
}

function keybindSay(msg) {
  var el = document.getElementById('keybind-live');
  if (el) el.textContent = msg;
}

function keybindRefreshRows() {
  var rows = document.querySelectorAll('[data-keybind-keys]');
  for (var i = 0; i < rows.length; i++) {
    var keys = keybindKeys(rows[i].getAttribute('data-keybind-keys'));
    rows[i].textContent = keys.map(keybindKeyName).join(' or ');
  }
}

// ---- the Controls panel ----
// The rows are built from the one table, so the panel can never list an
// action the keydown handler does not ask about. Changing a key is one
// press: the Change button listens for the next keydown itself, on the
// capture side of the document so the game's own handler never sees the
// key that is being offered. Esc stands the capture down and changes
// nothing; Tab stands it down too and keeps moving the focus.
var keybindCapturing = null;   // {id, btn, activationKey, armed}

// Which keys are down right now, and which one was last. A Change button
// can be pressed by mouse or by keyboard, and the keyboard roads arrive
// at different moments: Enter fires its click on keydown, Space on keyup.
// An Enter still held down keeps auto-repeating keydowns, which the
// capture would otherwise read as a refused binding and answer with the
// Space-and-Enter sentence - ending the capture the player just opened.
// So the capture keeps a note of what is held and waits for the
// activating key to come back up before it reads any key at all. A mouse
// press has no key to wait for and is armed at once, and so is a Space,
// whose click already arrives on the keyup.
var keybindHeld = {};
var keybindLastKey = null;

document.addEventListener('keydown', function (e) {
  keybindHeld[e.key] = true;
  keybindLastKey = e.key;
}, true);

document.addEventListener('keyup', function (e) {
  delete keybindHeld[e.key];
  var c = keybindCapturing;
  if (c && !c.armed && e.key === c.activationKey) c.armed = true;
}, true);

function keybindEndCapture() {
  if (!keybindCapturing) return;
  keybindCapturing.btn.textContent = 'Change';
  keybindCapturing = null;
}

function keybindBegin(id, btn, ev) {
  keybindEndCapture();
  // A click with no pointer behind it (detail 0) came from the keyboard.
  var activationKey = (ev && ev.detail === 0 && keybindLastKey) ? keybindLastKey : null;
  keybindCapturing = { id: id, btn: btn, activationKey: activationKey,
                       armed: !keybindHeld[activationKey] };
  btn.textContent = 'Press a new key';
  var a = keybindAction(id);
  keybindSay('Press a new key for ' + (a ? a.label : id) + '. Esc cancels.');
}

// Keys the browser and the system keep. Binding one of these would take
// reload (F5, Ctrl+R) or the system's own shortcuts away from the player
// for as long as the game is open, so the capture passes them by: it
// neither takes them nor blocks them, and it goes on waiting for a key
// that is the player's to give.
function keybindReservedWhy(e) {
  if (e.key === 'F5') return "F5 reloads the page, so it cannot be one of the game's keys.";
  if (e.key === 'Meta' || e.key === 'OS') return "That is the system's own key.";
  if (e.ctrlKey || e.metaKey || e.altKey) {
    return 'Ctrl, Alt and the system key stay with the browser and the system.';
  }
  return '';
}

document.addEventListener('keydown', function (e) {
  if (!keybindCapturing) return;
  // The press that opened the capture is still down: swallow it and its
  // auto-repeat, and the keyup above arms the capture for the next key.
  if (!keybindCapturing.armed) {
    e.preventDefault();
    e.stopPropagation();
    return;
  }
  if (e.key === 'Tab') { keybindEndCapture(); return; }
  if (e.repeat) return;
  var reserved = keybindReservedWhy(e);
  if (reserved) {
    keybindSay(reserved + ' Press another key, or Esc to stop.');
    return;
  }
  e.preventDefault();
  e.stopPropagation();
  var id = keybindCapturing.id;
  var a = keybindAction(id);
  if (e.key === 'Escape') {
    keybindEndCapture();
    keybindSay('Cancelled. Nothing was changed.');
    return;
  }
  // A modifier on its own is half a press; the capture keeps waiting.
  if (e.key === 'Shift' || e.key === 'Control' || e.key === 'Alt'
      || e.key === 'Meta' || e.key === 'Dead') return;
  var why = keybindRefused(id, e.key);
  if (why) {
    keybindEndCapture();
    keybindSay(why);
    return;
  }
  keybindChosen[id] = [keybindNormalize(e.key)];
  keybindApply();
  keybindEndCapture();
  keybindRefreshRows();
  updateKeyLetters();
  keybindSay((a ? a.label : id) + ' now answers to ' + keybindKeyName(e.key) + '.');
}, true);

function wireKeybinds() {
  var list = document.getElementById('keybind-list');
  if (!list) return;
  KEYBIND_CONTEXTS.forEach(function (ctx) {
    var head = document.createElement('h3');
    head.className = 'keybind-group';
    head.textContent = ctx.name;
    list.appendChild(head);
    KEYBIND_ACTIONS.forEach(function (a) {
      if (a.context !== ctx.id || !keybindListed(a)) return;
      var row = document.createElement('div');
      row.className = 'keybind-row';
      var label = document.createElement('span');
      label.className = 'keybind-label';
      label.textContent = a.label;
      var keys = document.createElement('span');
      keys.className = 'keybind-keys';
      keys.setAttribute('data-keybind-keys', a.id);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cta keybind-change';
      btn.setAttribute('data-keybind', a.id);
      btn.setAttribute('aria-label', 'Change the key for ' + a.label);
      btn.textContent = 'Change';
      btn.addEventListener('click', function (ev) { keybindBegin(a.id, btn, ev); });
      row.appendChild(label);
      row.appendChild(keys);
      row.appendChild(btn);
      list.appendChild(row);
    });
  });
  keybindRefreshRows();
  var reset = document.getElementById('keybind-reset');
  if (reset) reset.addEventListener('click', function () {
    keybindChosen = {};
    store.remove(KEYBIND_KEY);
    keybindRefreshRows();
    updateKeyLetters();
    keybindSay('Every key is back the way it came.');
    reset.focus();
  });
}

// A harness-readable snapshot of the table as it stands, read-only (the
// precedent of window.VEFR_COMBAT): what each action answers to right
// now, without pressing anything.
window.VEFR_KEYBINDS = function () {
  var out = {};
  KEYBIND_ACTIONS.forEach(function (a) { out[a.id] = keybindKeys(a.id).slice(); });
  return out;
};

wireKeybinds();
updateKeyLetters();
