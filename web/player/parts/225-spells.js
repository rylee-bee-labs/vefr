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
// `spells` block bakes no `window.VEFR_SPELLS` line at all, so every
// function here answers "no spells" and the Bag panel draws nothing it did
// not draw before.
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
  var byLevel = {};
  spellsByLevel().forEach(function (r) { byLevel[r.id] = true; });
  // The pack's own order is the order the hero learns in: a spell is
  // learned when the level reaches it or when its book is read, and the
  // list must not reorder one way of learning ahead of the other.
  spellRecords().forEach(function (r) {
    if (seen[r.id]) return;
    if (!byLevel[r.id] && books.indexOf(r.id) < 0) return;
    seen[r.id] = true;
    out.push(r);
  });
  return out;
}
// Cast one the hero knows. The whole effect is the item `heal` the bag has
// always had, and the "already whole" rule is the potion's: a spell is not
// spent on nothing, so a mis-tap costs nothing and says why. A spell the
// pack gave no `heal` casts and changes no number, which is the honest
// answer for a pack that has not written the numbers yet.
//
// Every cast - healing or not - also goes in the why-log (`VEFR_WHY`, the
// Why panel) as `cast-<id>` with the same words the panel said, the way
// the descent writes a death there, so what a cast did can be read back
// after the panel's live line has moved on. A refused cast is not a cast
// and writes nothing.
// ADR 0021 adds three things, each opt-in. A spell may cost `mana` (paid
// from the hero's own when the pack declares `player.mana`; a refused cast
// pays nothing), may `harm` the named foe - or the nearest living one within
// `range` tiles - for a number guard does not reduce, or may `ward` the hero
// with guard for a few turns. `opts.free` is a thing that casts on a charge
// (the bag spent it), and `opts.target` is the foe the fight row named. A
// cast that happened costs the turn a cast costs when the pack's `fight`
// says so; one that did not happen costs nothing.
function castSpell(id, opts) {
  opts = opts || {};
  if (!opts.free && !spellKnown(id)) {
    bagSay('You have not learned that spell.');
    return false;
  }
  var spell = spellById(id);
  if (!spell) return false;
  var line = 'You cast ' + (spell.name || id) + '.';
  var cost = (!opts.free && rpgManaOn() && rpgWhole(spell.mana)) ? spell.mana : 0;
  if (cost > HERO_MP) {
    castSay(id, 'Not enough mana for ' + (spell.name || id) + ': it needs '
      + cost + ' and you have ' + HERO_MP + '.');
    return false;
  }
  var harm = rpgWhole(spell.harm) && spell.harm > 0 ? spell.harm : 0;
  if (harm) {
    // How far it reaches: the spell's own `range`, else six tiles.
    var reach = (rpgWhole(spell.range) && spell.range > 0) ? spell.range : 6;
    var hit = (typeof window.VEFR_SPELL_HARM === 'function')
      ? window.VEFR_SPELL_HARM(spell, opts.target || null, reach) : null;
    if (!hit) {
      castSay(id, 'There is nothing in reach for ' + (spell.name || id) + '.');
      return false;
    }
    rpgPayMana(cost);
    castSay(id, line + ' ' + hit);
    if (!opts.free && !opts.noTurn) rpgSpendTurn();
    return true;
  }
  var ward = spell.ward && typeof spell.ward === 'object' ? spell.ward : null;
  if (ward && rpgWhole(ward.guard) && rpgWhole(ward.turns)) {
    rpgPayMana(cost);
    RPG_WARD.guard = ward.guard;
    RPG_WARD.turns = ward.turns;
    castSay(id, line + ' Guard up by ' + ward.guard + ' for ' + ward.turns
      + (ward.turns === 1 ? ' turn.' : ' turns.'));
    syncCombat();
    if (!opts.free && !opts.noTurn) rpgSpendTurn();
    return true;
  }
  var heal = spell && typeof spell.heal === 'number' && spell.heal > 0
    ? spell.heal : 0;
  if (!heal) {
    rpgPayMana(cost);
    castSay(id, line);
    return true;
  }
  if (HERO_HP >= heroMax()) {
    castSay(id, line + ' You are already whole.');
    return true;
  }
  rpgPayMana(cost);
  var before = HERO_HP;
  healHeroBy(heal);
  castSay(id, line + ' You recover ' + (HERO_HP - before) + ' health.');
  syncCombat();
  if (!opts.free && !opts.noTurn) rpgSpendTurn();
  return true;
}
function rpgPayMana(cost) {
  if (!cost) return;
  HERO_MP = Math.max(0, HERO_MP - cost);
  saveHeroMana();
  renderMana();
}
// The harmful spell the fight row's Cast button casts (ADR 0021): the first
// one in the pack's order the hero knows and can pay for. Null when none.
function rpgReadySpell() {
  var known = spellsKnown();
  for (var i = 0; i < known.length; i++) {
    var s = known[i];
    if (!(rpgWhole(s.harm) && s.harm > 0)) continue;
    var cost = (rpgManaOn() && rpgWhole(s.mana)) ? s.mana : 0;
    if (cost <= HERO_MP) return s;
  }
  return null;
}
function rpgCastReady() {
  var known = spellsKnown();
  for (var i = 0; i < known.length; i++) {
    if (rpgWhole(known[i].harm) && known[i].harm > 0) return true;
  }
  return false;
}
// One cast's words: the panel's live line, and the same words in the
// why-log. Guarded because the rules part may not be in a file, and a
// cast that cannot be logged must still be cast.
function castSay(id, text) {
  bagSay(text);
  if (typeof rulesWhyRecord !== 'function') return;
  rulesWhyRecord([{ id: 'cast-' + id, why: text }]);
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
    name.textContent = (spell.school ? (spell.name + ' (' + spell.school + ')')
      : spell.name) + ((rpgManaOn() && rpgWhole(spell.mana)) ? ' - ' + spell.mana + ' mana' : '');
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
  // A spell just learned may be the first harmful one: the fight row's Cast
  // button (ADR 0021) follows what the hero knows.
  renderVerbRow();
}