// ---- the engine's message table ----
// Every action-critical line a player reads in order to act lives
// here, once, with the engine's known-good wording as each entry's
// default. A pack may name its own word for a key (`player_words` in
// world.json, carried on window.VEFR_WORLD), and that word wins; a
// pack that names none plays exactly these bytes. vefr #259 is why
// the table exists: engine wording derived from structure reads "To
// reach floor-1, go north-west", a region id and a compass where the
// pack's name for the place and the action belong.
// The keys are typed once on the Python side (shapes.PLAYER_WORDS in
// src/vefr/shapes.py, which vefr check speaks refusals from);
// tests/test_player_words.py fails if the two drift.
// -- player words start --
var VEFR_PLAYER_WORDS = {
  'where_next.goal': 'To reach {place}.',
  'where_next.reach': 'To reach {place}, go {direction}.',
  'where_next.here': 'The way to {place} is right here.',
  'where_next.no_way': 'No way to {place} is declared from here.'
};
// The one reader: the pack's word when it supplies a usable one, the
// engine's own otherwise, with the slots filled from what the engine
// actually knows. A slot with nothing to fill it stays as written
// rather than printing "undefined" at a player. A pack word that is
// not usable - not a string, or only spaces - is not a word: `vefr
// check` refuses it, and if one ever reached play anyway it must not
// blank a line the player needs to act.
function playerWord(key, slots) {
  var pack = (window.VEFR_WORLD && window.VEFR_WORLD.player_words) || null;
  var mine = (pack && typeof pack[key] === 'string') ? pack[key].trim() : '';
  var text = mine || VEFR_PLAYER_WORDS[key] || key;
  var s = slots || {};
  return text.replace(/\{(\w+)\}/g, function (slot, name) {
    return typeof s[name] === 'string' ? s[name] : slot;
  });
}
// -- player words end --

// ---- where next: the point-to hints, kept as player-facing
// intentions ("Go toward Saltreach.") instead of thrown-away
// narration. Authored by rules; nothing is inferred. Same wrapped
// storage discipline as the why-log.
window.VEFR_NEXT = [];
var rulesNextLoaded = false;
function rulesNextKey() {
  return 'vefr-next-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
function rulesNextLoad() {
  if (rulesNextLoaded) return;
  rulesNextLoaded = true;
  var a = store.getJSON(rulesNextKey(), []);
  window.VEFR_NEXT = Array.isArray(a) ? a.filter(function (e) {
    return e && typeof e.place === 'string' && typeof e.line === 'string';
  }) : [];
}
// `shown` is the words the player reads for the place when they are not
// its id (a labelled Section's floor, vefr#363); the row is still keyed by
// the id, and a place shown by its own id stores exactly what it always did.
function rulesNextRecord(place, line, shown) {
  if (typeof place !== 'string' || !place) return;
  rulesNextLoad();
  var name = (typeof shown === 'string' && shown) ? shown : place;
  // one row per place: the newest word wins
  window.VEFR_NEXT = window.VEFR_NEXT.filter(function (e) { return e.place !== place; });
  var row = {
    place: place,
    line: line || playerWord('where_next.goal', { place: name })
  };
  if (name !== place) row.name = name;
  window.VEFR_NEXT.push(row);
  store.setJSON(rulesNextKey(), window.VEFR_NEXT);
}

// The two evidence panels the menu shows: where the world pointed,
// and why it did what it did. Both render only real records - the
// point-to hints and the fired rules - and invent nothing.
function renderNextPanel() {
  var list = document.getElementById('next-list');
  var count = document.getElementById('next-count');
  if (!list) return;
  rulesNextLoad();
  list.textContent = '';
  var rows = window.VEFR_NEXT.slice().reverse();   // newest word first
  rows.forEach(function (e) {
    var p = document.createElement('p');
    p.className = 'status';
    var b = document.createElement('b');
    b.textContent = (typeof e.name === 'string' && e.name ? e.name : e.place) + ' - ';
    p.appendChild(b);
    p.appendChild(document.createTextNode(e.line));
    list.appendChild(p);
  });
  if (!rows.length) {
    var empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'Nothing has pointed the way yet.';
    list.appendChild(empty);
  }
  if (count) count.textContent = rows.length
    ? rows.length + (rows.length === 1 ? ' place to aim at.' : ' places to aim at.')
    : '';
}
function renderWhyPanel() {
  var list = document.getElementById('why-list');
  var count = document.getElementById('why-count');
  if (!list) return;
  rulesWhyLoad();
  list.textContent = '';
  var rows = window.VEFR_WHY.slice().reverse();   // newest first
  rows.forEach(function (e) {
    var p = document.createElement('p');
    p.className = 'status';
    var b = document.createElement('b');
    // the rule's own id, as words: "light-the-causeway-lamp"
    b.textContent = (e.id || '').replace(/-/g, ' ') + ' - ';
    p.appendChild(b);
    p.appendChild(document.createTextNode(e.why || ''));
    list.appendChild(p);
  });
  if (!rows.length) {
    var empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'Nothing has happened yet that needs explaining.';
    list.appendChild(empty);
  }
  if (count) count.textContent = rows.length
    ? 'The last ' + rows.length + ' things the world did.'
    : '';
}

