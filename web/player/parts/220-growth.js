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

function heroMax() {
  var h = window.VEFR_HERO || {};
  var base = (typeof h.hp === 'number' && h.hp > 0) ? h.hp : 6;
  return base + growthStats().hp + equipStats().hp;
}
function heroAtk() {
  var h = window.VEFR_HERO || {};
  var base = (typeof h.atk === 'number' && h.atk > 0) ? h.atk : 2;
  return base + growthStats().atk + equipStats().atk;
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
  try { r = engine.award(window.VEFR_GROWTH, GROWTH_STATE, xp); } catch (e) { return null; }
  if (!r) return null;
  GROWTH_STATE = r.state || GROWTH_STATE;
  saveGrowth();
  if (r.grew) healHeroBy(r.grew.hp);
  renderGrowth();
  // A level that has just been earned is the one moment a spell the hero
  // knew the name of becomes a spell the hero can cast (ADR 0018), so the
  // panel is redrawn here rather than only when the bag is opened.
  renderSpellList();
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

// Growth sentences are held until the turn's blows are all said, then
// added to the last line. A monster's counter-blow would otherwise wipe
// the good news off the screen before the player could read it.
var PENDING_GROWTH = null;
function sayGrowth(text) {
  if (!text) return;
  PENDING_GROWTH = (PENDING_GROWTH ? PENDING_GROWTH + ' ' : '') + text.replace(/^ /, '');
}
function flushGrowth() {
  if (!PENDING_GROWTH) return;
  var text = PENDING_GROWTH; PENDING_GROWTH = null;
  var el = document.getElementById('combat-live');
  if (!el) return;
  el.textContent = (el.textContent ? el.textContent + ' ' : '') + text;
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

// The act's verbs are the pack's own vocabulary; the baked defaults
// keep the old costume when the act declares none. One home for the
// list, so the verb row, Interact's enemy path and the tests cannot
// drift apart.
function surfaceVerbs() {
  var act = (window.VEFR_WORLD && window.VEFR_WORLD.acts
             && window.VEFR_WORLD.acts[0]) || {};
  if (Array.isArray(act.verbs) && act.verbs.length) {
    return act.verbs.map(function (v) {
      return [v, v.charAt(0).toUpperCase() + v.slice(1)];
    });
  }
  return [['attack', 'Strike'], ['console', 'Console'],
          ['hurl', 'Hurl an insult']];
}

// The enemy a #verb-row press is aimed at, or null. The row is always
// on screen, so naming a target is what "opens" the enemy menu;
// Escape, a resolved verb or a bump clears it again.
var VERB_TARGET = null;

