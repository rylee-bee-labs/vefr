// ---- growth (levels / practice) ----
// The growth engine is pure; this is the only place it meets storage
// and the world's own max. State is {xp, counts} and lives per world
// under `vefr-growth-<world>`; the level and the stat gains are derived
// from it on every read, never stored. Every storage access is wrapped
// so a hostile storage can never break a turn.
function growthKey() {
  var w = (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
  return 'vefr-growth-' + w;
}
function loadGrowth() {
  var raw = store.getJSON(growthKey(), null);
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return { xp: (typeof raw.xp === 'number' ? raw.xp : 0),
             counts: (raw.counts && typeof raw.counts === 'object' ? raw.counts : {}) };
  }
  return { xp: 0, counts: {} };
}
var GROWTH_STATE = loadGrowth();
var XP_WORD = 'experience';
function saveGrowth() {
  store.setJSON(growthKey(), GROWTH_STATE);
}
// The extra hp/atk the state has earned. No growth block (or a missing
// engine) reads as no growth, so a plain pack plays exactly as before.
function growthStats() {
  var engine = window.VEFR_GROWTH_ENGINE;
  if (!engine || !window.VEFR_GROWTH) return { level: null, hp: 0, atk: 0 };
  return engine.statsFor(window.VEFR_GROWTH, GROWTH_STATE);
}

// The traits a worn thing bears add to both (ADR 0021), and a curse may take
// away; neither number ever falls below 1. A pack with no `traits` adds 0.
function heroMax() {
  var h = window.VEFR_HERO || {};
  var base = (typeof h.hp === 'number' && h.hp > 0) ? h.hp : 6;
  return Math.max(1, base + growthStats().hp + equipStats().hp + rpgTraitTotals().hp);
}
function heroAtk() {
  var h = window.VEFR_HERO || {};
  var base = (typeof h.atk === 'number' && h.atk > 0) ? h.atk : 2;
  return Math.max(1, base + growthStats().atk + equipStats().atk + rpgTraitTotals().atk);
}
var HERO_HP = heroMax();
function heroHpKey() {
  var w = (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
  return 'vefr-hp-' + w;
}
function loadHeroHp() {
  var n = parseInt(store.get(heroHpKey()), 10);
  var max = heroMax();
  HERO_HP = (isFinite(n) && n > 0) ? Math.min(n, max) : max;
  return HERO_HP;
}
function saveHeroHp() {
  store.set(heroHpKey(), HERO_HP);
}
function renderHp() {
  var fill = document.getElementById('hud-hp-fill');
  var value = document.getElementById('hud-hp-value');
  if (!fill || !value) return;
  var max = heroMax();
  var pct = max > 0 ? Math.round((HERO_HP / max) * 100) : 0;
  fill.style.width = pct + '%';
  value.textContent = HERO_HP + '/' + max;
  renderGrowth();
  renderMana();
}

// The next xp step after the current one, for the level line. At the
// table's end the last step is shown, so the line stays honest.
function growthNextXp() {
  var g = window.VEFR_GROWTH;
  var table = (g && g.mode === 'levels' && g.levels && Array.isArray(g.levels.xp))
    ? g.levels.xp : [];
  var xp = (typeof GROWTH_STATE.xp === 'number') ? GROWTH_STATE.xp : 0;
  for (var i = 0; i < table.length; i++) {
    if (table[i] > xp) return table[i];
  }
  return table.length ? table[table.length - 1] : xp;
}
// A small words line near the health: only levels mode has a level to
// say. Practice keeps no counters, and no growth means no line at all
// (the text is cleared, not just hidden, so it stays out of the page).
function renderGrowth() {
  // The same words stand in the Bag panel too, where a phone, which keeps its
  // top bar to health and quickslots, reads them.
  var lines = [document.getElementById('hud-level'), document.getElementById('bag-level')]
    .filter(function (el) { return !!el; });
  if (!lines.length) return;
  var g = window.VEFR_GROWTH;
  if (!g || g.mode !== 'levels') {
    lines.forEach(function (el) { el.textContent = ''; el.hidden = true; });
    return;
  }
  var stats = growthStats();
  var xp = (typeof GROWTH_STATE.xp === 'number') ? GROWTH_STATE.xp : 0;
  var text = 'Level ' + stats.level + ' \u00b7 ' + xp + ' of '
    + growthNextXp() + ' ' + XP_WORD;
  lines.forEach(function (el) { el.textContent = text; el.hidden = false; });
}

// A growth of health heals the hero by the same amount, never above the
// new max (the max is derived first, so the cap is the grown one).
function healHeroBy(n) {
  if (typeof n !== 'number' || n <= 0) return;
  HERO_HP = Math.min(heroMax(), HERO_HP + n);
  saveHeroHp();
  renderHp();
}

// One landed blow: practice counts it and reports each stat that just
// crossed a step; levels ignores it. The state is saved on every change.
function growBump(kind) {
  var engine = window.VEFR_GROWTH_ENGINE;
  if (!engine || !window.VEFR_GROWTH) return [];
  var r = null;
  try { r = engine.bump(window.VEFR_GROWTH, GROWTH_STATE, kind); } catch (e) { return []; }
  if (!r) return [];
  GROWTH_STATE = r.state || GROWTH_STATE;
  saveGrowth();
  var heal = 0;
  (r.grown || []).forEach(function (g) { if (g && g.stat === 'hp') heal += g.gain; });
  healHeroBy(heal);
  renderGrowth();
  // Practice keeps no level, so no spell is learned here; the call is
  // cheap and it is the one place both modes pass through.
  renderSpellList();
  return r.grown || [];
}

// One defeated enemy in levels mode: award its xp, report the levels
// crossed. Returns the engine's result, or null when nothing grows.
function growAward(xp) {
  var engine = window.VEFR_GROWTH_ENGINE;
  if (!engine || !window.VEFR_GROWTH) return null;
  var r = null;
  var knew = spellIdsKnown();
  try { r = engine.award(window.VEFR_GROWTH, GROWTH_STATE, xp); } catch (e) { return null; }
  if (!r) return null;
  GROWTH_STATE = r.state || GROWTH_STATE;
  saveGrowth();
  if (r.grew) healHeroBy(r.grew.hp);
  renderGrowth();
  // A level that has just been earned is the one moment a spell the hero
  // knew the name of becomes a spell the hero can cast (ADR 0018), so the
  // panel is redrawn here rather than only when the bag is opened - and a
  // pack with `display.spell_card` (ADR 0023) gives each one its card.
  renderSpellList();
  spellCardsSince(knew);
  return r;
}

// The one practice sentence per growth, in the stat's own word. Levels
// never uses this and practice never names the xp word.
function practiceSuffix(grown) {
  if (!grown || !grown.length) return '';
  return grown.map(function (g) {
    var word = (g.stat === 'hp') ? 'Health' : 'Attack';
    return ' All that striking is paying off. ' + word + ' up by ' + g.gain + '.';
  }).join('');
}

// The one level-up sentence, listing only the stats that moved.
function levelSuffix(r) {
  if (!r || !r.grew || !r.levelsGained) return '';
  var parts = [];
  if (r.grew.hp > 0) parts.push('health up by ' + r.grew.hp);
  if (r.grew.atk > 0) parts.push('attack up by ' + r.grew.atk);
  if (!parts.length) return '';
  return ' You are stronger. Level ' + r.level + ': ' + parts.join(', ') + '.';
}

// Growth sentences - and the one-time strike hint (vefr #464, part 340)
// are held until the turn's blows are all said, then added to the last
// line, the hint after the growth because it is about the fight the
// player just walked into. A monster's counter-blow would otherwise
// wipe the good news off the screen before the player could read it.
var PENDING_GROWTH = null;
var PENDING_HINT = null;
function sayGrowth(text) {
  if (!text) return;
  PENDING_GROWTH = (PENDING_GROWTH ? PENDING_GROWTH + ' ' : '') + text.replace(/^ /, '');
}
function sayHint(text) {
  if (!text) return;
  PENDING_HINT = (PENDING_HINT ? PENDING_HINT + ' ' : '') + text.replace(/^ /, '');
}
function flushGrowth() {
  var held = [PENDING_GROWTH, PENDING_HINT].filter(function (t) {
    return !!t;
  }).join(' ');
  PENDING_GROWTH = null; PENDING_HINT = null;
  if (!held) return;
  var el = document.getElementById('combat-live');
  if (!el) return;
  el.textContent = (el.textContent ? el.textContent + ' ' : '') + held;
}

function renderEncounter() {
  var el = document.getElementById('encounter-prompt');
  if (!el) return;
  var world = window.VEFR_WORLD || {};
  var phases = Object.keys(world.phases || {});
  // The encounter appears in non-initial phases; the text stays
  // engine-neutral - the phase names belong to the pack, never to
  // this file.
  if (phases.indexOf(STATE.get().phase) <= 0) {
    el.hidden = true; el.textContent = ''; return;
  }
  el.hidden = false;
  el.textContent = 'Something stirs nearby.';
}

function applySurface() {
  var surface = (window.VEFR_WORLD && window.VEFR_WORLD.surface) || 'plain';
  document.body.setAttribute('data-surface', surface);
  renderHp();
  renderEncounter();
}

// ---- the verbs a carried thing grants (the item-grants slice) ----
//
// An item may hand the hero a verb of its own: `"grants": [{"verb":
// "mend", "label": "Mend the hull"}]` in the pack's catalog. While the
// thing is in the bag - or worn, when the item names a `slot` - its verbs
// sit in the row beside the act's, and when it leaves they go with it.
// Nothing here is stored: the bag and the equipped map already say what
// is carried, so a pack that grants nothing plays and saves as before.

// What the hero is carrying, worn things included: the bag's ids and the
// five slots'. A worn thing is out of the bag list, so the two are read
// together or a granted verb would blink off the moment it was worn.
function carryingItems() {
  var ids = bagItems();
  for (var i = 0; i < EQUIP_SLOTS.length; i++) {
    if (typeof EQUIP_STATE[EQUIP_SLOTS[i]] === 'string') {
      ids.push(EQUIP_STATE[EQUIP_SLOTS[i]]);
    }
  }
  return ids;
}

// What carrying things does to one verb: the extra damage that verb's
// blow carries, summed over every carried or worn thing whose `changes`
// name it. An effect the pack wrote in a broken shape adds nothing.
function verbAtkBonus(verb) {
  var cat = itemCatalog();
  var total = 0;
  carryingItems().forEach(function (id) {
    var def = cat[id];
    var changes = def && def.changes;
    if (!changes || typeof changes !== 'object') return;
    var effect = changes[verb];
    if (effect && typeof effect === 'object'
        && typeof effect.atk === 'number' && isFinite(effect.atk)) {
      total += effect.atk;
    }
  });
  return total;
}

// The verbs the hero carries that the act did not write, one entry per
// verb: `{verb, label, from, atk}`. Two copies of one thing grant one
// button, in the order the catalog and the pack listed them.
function grantedVerbs() {
  var cat = itemCatalog();
  var seen = {};
  var out = [];
  carryingItems().forEach(function (id) {
    var def = cat[id];
    if (!def || !Array.isArray(def.grants)) return;
    def.grants.forEach(function (g) {
      if (!g || typeof g.verb !== 'string' || !g.verb) return;
      if (typeof g.label !== 'string' || !g.label) return;
      if (seen[g.verb]) return;
      seen[g.verb] = true;
      out.push({ verb: g.verb, label: g.label, from: id,
                 atk: verbAtkBonus(g.verb) });
    });
  });
  return out;
}

// Is this verb one the hero is carrying? The granted verbs, by id. A verb
// the act already offers answers true as well when an item changes it -
// the change is what makes it worth noticing.
function isGrantedVerb(verb) {
  var granted = grantedVerbs();
  for (var i = 0; i < granted.length; i++) {
    if (granted[i].verb === verb) return true;
  }
  return verbAtkBonus(verb) > 0;
}

// The costume verbs of an act that declares none of its own. The act's own
// `verbs` replace this list entirely; the literals stay here so the default
// row is one table like any other.
var DEFAULT_VERB_ROW = [['attack', 'Strike'], ['console', 'Console'],
                        ['hurl', 'Hurl an insult']];

// The act's verbs are the pack's own vocabulary; the baked defaults
// keep the old costume when the act declares none. One home for the
// list, so the verb row, Interact's enemy path and the tests cannot
// drift apart. What the hero carries comes after the act's own, and a
// verb the act already has is never printed twice.
function surfaceVerbs() {
  var act = (window.VEFR_WORLD && window.VEFR_WORLD.acts
             && window.VEFR_WORLD.acts[0]) || {};
  var out = [];
  var seen = {};
  function add(verb, label) {
    if (typeof verb !== 'string' || !verb || seen[verb]) return;
    seen[verb] = true;
    out.push([verb, label]);
  }
  if (Array.isArray(act.verbs) && act.verbs.length) {
    act.verbs.forEach(function (v) {
      // A verb may name its own label (ADR 0021): {"verb": "attack",
      // "label": "Strike"}. A bare word is labelled with itself, as before.
      var verb = (v && typeof v === 'object') ? v.verb : v;
      if (typeof verb !== 'string') return;
      var label = (v && typeof v === 'object' && typeof v.label === 'string' && v.label)
        ? v.label : verb.charAt(0).toUpperCase() + verb.slice(1);
      // `cast` is on the row only while there is a harmful spell to cast.
      if (verb === 'cast' && !rpgCastReady()) return;
      add(verb, label);
    });
  } else {
    DEFAULT_VERB_ROW.forEach(function (pair) { add(pair[0], pair[1]); });
  }
  grantedVerbs().forEach(function (g) { add(g.verb, g.label); });
  return out;
}

// The row itself, rebuilt from the one list. Called at boot and again
// whenever the bag or the worn map changes, so a verb that arrives with
// a thing and leaves with it is painted and unpainted by the same line -
// and the digits printed on the buttons are re-numbered with them, so the
// number keys (#463) always answer through this row and nothing else.
//
// The granted verbs ride out on `window.VEFR_VERBS` for the tests: what
// is on the row because of what the hero is carrying, and what carrying
// it does to that verb. A pack that grants nothing publishes an empty
// list, which is the honest reading of an unchanged row.
function renderVerbRow() {
  var row = document.getElementById('verb-row');
  window.VEFR_VERBS = grantedVerbs();
  if (!row) return;
  row.textContent = '';
  surfaceVerbs().forEach(function (pair, i) {
    var b = document.createElement('button');
    b.type = 'button';
    b.dataset.verb = pair[0];
    // The label is kept beside its own word: the verb is the pack's
    // and the digit is a shortcut, and the two must not be read as
    // one name.
    var label = document.createElement('span');
    label.className = 'verb';
    label.textContent = pair[1];
    b.dataset.label = pair[1];
    b.appendChild(label);
    // With the quick bar on (ADR 0023) the digits past 4 are its keys, so a
    // fifth verb is pressed by tap or click and prints no digit.
    if (i < verbDigits()) {
      var key = document.createElement('kbd');
      key.textContent = String(i + 1);
      b.appendChild(document.createTextNode(' '));
      b.appendChild(key);
    }
    row.appendChild(b);
  });
  // The row was emptied above, and the pack's Rest button (part 255) with it:
  // put it back, after the verbs, as it was first drawn. A pack with no Rest
  // gets nothing here.
  if (typeof wireTimeRest === 'function') wireTimeRest();
}

// The nth button of the combat row, 1 being the first verb, or null.
// The number keys answer through this, so the key that presses a verb
// and the digit printed on that verb are one list and cannot drift
// (#463). Only a surface that shows the row answers: on `plain` and
// `investigation` the row is hidden and the keys do nothing.
function verbDigits() { return hotbarOn() ? 4 : 9; }
function combatVerbButton(n) {
  if (document.body.getAttribute('data-surface') !== 'combat') return null;
  if (n > verbDigits()) return null;
  var row = document.getElementById('verb-row');
  if (!row) return null;
  var buttons = row.querySelectorAll('button[data-verb]');
  return buttons[n - 1] || null;
}

// The enemy a #verb-row press is aimed at, or null. The row is always
// on screen, so naming a target is what "opens" the enemy menu;
// Escape, a resolved verb or a bump clears it again.
var VERB_TARGET = null;

