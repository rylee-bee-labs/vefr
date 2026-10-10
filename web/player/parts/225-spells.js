// ---- spells: the schools a pack teaches, and what the hero has learned ----
// Two ways in, one list out. A spell with a `level` is learned the moment
// `growthStats().level` reaches it - a read of the level that already
// exists, never a second level counter, and never a cap that moves: the
// growth block's own table is still the only thing that says how high the
// hero gets. A spell with no `level` is learned by reading a book found as
// loot, and that one is stored, because nothing else remembers it.
//
// Only the books are stored, under `vefr-spells-<world>`: the level-learned
// half is derived on every read from the growth state, exactly as the
// growth part derives its own level rather than keeping it. A pack with no
// `spells` block bakes the literal `null`, so every function here answers
// "no spells" and the Bag panel draws nothing it did not draw before.
var SPELLS_KEY = 'vefr-spells-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');

// The pack's spell records, or an empty list when it declared none.
function spellRecords() {
  var block = window.VEFR_SPELLS;
  if (!block || typeof block !== 'object' || !Array.isArray(block.spells)) return [];
  return block.spells.filter(function (r) {
    return r && typeof r === 'object' && typeof r.id === 'string' && r.id;
  });
}
function spellById(id) {
  var found = null;
  spellRecords().forEach(function (r) { if (r.id === id) found = r; });
  return found;
}
// What a spell is called in a sentence: its own name, or the id the pack
// filed it under when the name is not one there is.
function spellName(id) {
  var spell = spellById(id);
  return (spell && spell.name) ? spell.name : id;
}
// The spell ids a book taught, stored per playthrough. A malformed or
// hostile save reads as no books rather than as a broken turn.
function loadSpellBooks() {
  var raw = store.getJSON(SPELLS_KEY, []);
  if (!Array.isArray(raw)) return [];
  return raw.filter(function (id) { return typeof id === 'string' && id; });
}
function saveSpellBooks(ids) {
  store.setJSON(SPELLS_KEY, ids);
}
// Every spell the hero has learned by reading a book: what the drop named,
// once each, in the order it was read. Adding one that is already known
// changes nothing and says so rather than pretending a second lesson.
function learnSpellFromBook(id) {
  var spell = spellById(id);
  if (!spell) return false;
  var books = loadSpellBooks();
  if (books.indexOf(id) >= 0) return false;
  books.push(id);
  saveSpellBooks(books);
  return true;
}
// The spells the hero's level has already taught. The level is the growth
// engine's own derived number, and it is already clamped to the pack's
// xp table - so this reads the cap and never has to hold one. A null
// level (no growth block, or a practice pack, which keeps no level) and
// a pack with no spells both teach nothing.
function spellsByLevel() {
  var level = growthStats().level;
  if (typeof level !== 'number' || level < 1) return [];
  var out = [];
  spellRecords().forEach(function (r) {
    if (typeof r.level === 'number' && r.level >= 1 && r.level <= level) out.push(r);
  });
  return out;
}
function spellKnown(id) {
  var records = spellsByLevel();
  for (var i = 0; i < records.length; i++) if (records[i].id === id) return true;
  return loadSpellBooks().indexOf(id) >= 0;
}
// Everything the hero knows, in the pack's own order, each spell once:
// this is the list the panel draws and the only list anything else should
// ask for. The level-learned half comes from the growth engine and the
// book half from storage, and neither is written back here - reading what
// the hero knows must never change what it is.
function spellsKnown() {
  var out = [];
  var seen = {};
  var books = loadSpellBooks();
  var add = function (r) {
    if (!seen[r.id]) { seen[r.id] = true; out.push(r); }
  };
  spellRecords().forEach(function (r) {
    if (books.indexOf(r.id) >= 0) add(r);
  });
  spellsByLevel().forEach(add);
  return out;
}
// Cast one the hero knows. The whole effect is the item `heal` the bag has
// always had, and the "already whole" rule is the potion's: a spell is not
// spent on nothing, so a mis-tap costs nothing and says why. A spell the
// pack gave no `heal` casts and changes no number, which is the honest
// answer for a pack that has not written the numbers yet.
function castSpell(id) {
  if (!spellKnown(id)) {
    bagSay('You have not learned that spell.');
    return false;
  }
  var spell = spellById(id);
  var line = 'You cast ' + (spell.name || id) + '.';
  var heal = spell && typeof spell.heal === 'number' && spell.heal > 0
    ? spell.heal : 0;
  if (!heal) {
    bagSay(line);
    return true;
  }
  if (HERO_HP >= heroMax()) {
    bagSay(line + ' You are already whole.');
    return true;
  }
  var before = HERO_HP;
  healHeroBy(heal);
  bagSay(line + ' You recover ' + (HERO_HP - before) + ' health.');
  syncCombat();
  return true;
}
// The Bag panel's "Spells" section. Nothing at all for a pack that
// declares no spells: the heading is hidden and the list is empty, so a
// pack with no `spells` block draws the panel it always drew. Each row
// names the spell and its school in one line of text and the button names
// the same two words in its own label, so the eye and a screen reader are
// told the same thing in the same sentence.
//
// The schools list is not read here on purpose. A school is a name the
// pack chose, a spell outside the list is a pack `vefr check` refuses,
// and nothing in this slice decides what a school is FOR - so the player
// prints the name the pack wrote and asks nothing of it.
function renderSpellList() {
  var list = document.getElementById('spell-list');
  var head = document.getElementById('spells-heading');
  var known = spellsKnown();
  if (!list) return;
  if (head) {
    head.hidden = !known.length;
    head.textContent = known.length
      ? 'Spells (' + known.length + ')' : '';
  }
  list.textContent = '';
  if (!known.length) {
    // A pack with no spells block has no section at all, so the words are
    // cleared rather than left behind for a later pack to read.
    list.hidden = true;
    list.setAttribute('aria-label', '');
    return;
  }
  list.hidden = false;
  known.forEach(function (spell) {
    var row = document.createElement('div');
    row.className = 'bag-row';
    row.setAttribute('role', 'listitem');
    var name = document.createElement('span');
    name.className = 'bag-row-name';
    name.textContent = spell.school ? (spell.name + ' (' + spell.school + ')')
      : spell.name;
    row.appendChild(name);
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'cta';
    button.textContent = 'Cast';
    button.dataset.spell = spell.id;
    button.dataset.action = 'cast';
    button.setAttribute('aria-label', 'Cast ' + (spell.name || spell.id));
    button.addEventListener('click', function () { castSpell(spell.id); });
    row.appendChild(button);
    list.appendChild(row);
  });
  list.setAttribute('aria-label', 'Spells you know: '
    + known.map(function (s) { return s.name; }).join(', ') + '.');
}