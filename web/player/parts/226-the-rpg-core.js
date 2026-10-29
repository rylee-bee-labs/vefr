// ---- the RPG core (ADR 0021): rolls, guard, traits, mana, charges ----
// Every rule here answers to a key the pack names, and a pack that names
// none of them gets the old answer from every function: no roll (a blow
// always lands for its number), no guard (0), no trait, no mana, no
// charge. The fight itself still lives in the closure (parts 430 and 480);
// this part is the global half the bag, the stats and the spells read.
// Everything is deterministic: a roll is drawn from a named stream of the
// same seeded generator the descent uses, so the same moves in the same
// state give the same rolls and a reload never re-rolls a fight.

function rpgWorldName() {
  return (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
}
function rpgWhole(n) {
  return typeof n === 'number' && isFinite(n) && Math.floor(n) === n;
}

// The pack's `fight` block with its defaults, or null when it names none.
function rpgFight() {
  var f = window.VEFR_WORLD && window.VEFR_WORLD.fight;
  if (!f || typeof f !== 'object' || Array.isArray(f)) return null;
  function pctOf(v) { return (rpgWhole(v) && v >= 0 && v <= 50) ? v : 0; }
  return {
    miss: pctOf(f.miss),
    crit: pctOf(f.crit),
    critTimes: (f.crit_times === 3) ? 3 : 2,
    turns: f.turns === true
  };
}
function rpgPlayer() {
  var p = window.VEFR_WORLD && window.VEFR_WORLD.player;
  return (p && typeof p === 'object') ? p : {};
}

// ---- rolls ---------------------------------------------------------
// One blow's roll: `{miss, crit}` from the stream
// `fight|<world>|<region>|<attacker>|<defender>|<n>`, where `n` counts the
// blows struck in this region since the hero came into it. A pack with no
// `fight` block never rolls: the answer is null and the blow lands.
var RPG_BLOWS = { region: null, n: 0 };
function rpgRoll(region, attacker, defender, critBonus) {
  var f = rpgFight();
  if (!f || !(window.VEFR_DELVE && window.VEFR_DELVE.prng)) return null;
  if (RPG_BLOWS.region !== region) { RPG_BLOWS.region = region; RPG_BLOWS.n = 0; }
  RPG_BLOWS.n++;
  var rng = window.VEFR_DELVE.prng(['fight', rpgWorldName(), region, attacker,
                                    defender, RPG_BLOWS.n].join('|'));
  var miss = Math.floor(rng() * 100) < f.miss;
  var crit = !miss && Math.floor(rng() * 100)
    < Math.max(0, Math.min(100, f.crit + (critBonus || 0)));
  return { miss: miss, crit: crit, times: f.critTimes };
}

// A landed blow, reduced by the target's guard and never below 1. A blow
// a resistance turned aside entirely (0) stays turned aside.
function rpgGuarded(damage, guard) {
  if (!(damage > 0)) return damage;
  var g = (rpgWhole(guard) && guard > 0) ? guard : 0;
  return Math.max(1, damage - g);
}

// ---- what is worn, as instances -------------------------------------
// `EQUIP_STATE` keeps the bare id per slot, as it always has. The rolled
// instance a worn thing came from - its rarity, its traits, whether the
// town has read it, its charges - is kept beside it under its own key, and
// that key is written only while there is an instance to keep, so a pack
// that never rolls saves the keys it always saved.
var WORN_KEY = 'vefr-worn-' + rpgWorldName();
var WORN_INST = {};
function rpgInstanceOf(entry) {
  if (!entry || typeof entry !== 'object') return null;
  var out = {};
  if (typeof entry.rarity === 'string' && entry.rarity) out.rarity = entry.rarity;
  if (Array.isArray(entry.traits) && entry.traits.length) out.traits = entry.traits.slice();
  if (entry.identified === true) out.identified = true;
  if (rpgWhole(entry.charges)) out.charges = entry.charges;
  return Object.keys(out).length ? out : null;
}
function loadWornInstances() {
  var raw = store.getJSON(WORN_KEY, null);
  WORN_INST = {};
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return;
  Object.keys(raw).forEach(function (slot) {
    if (typeof EQUIP_STATE[slot] === 'string' && raw[slot] && typeof raw[slot] === 'object') {
      var inst = rpgInstanceOf(raw[slot]);
      if (inst) WORN_INST[slot] = inst;
    }
  });
  saveWornInstances();
}
function saveWornInstances() {
  if (Object.keys(WORN_INST).length) store.setJSON(WORN_KEY, WORN_INST);
  else store.remove(WORN_KEY);
}

// ---- traits ---------------------------------------------------------
// What a trait word does, from the pack's `traits` table: a few stats and
// a closed set of reactions. A trait the table does not name does nothing,
// which is how every trait worked before this part.
function rpgTraitTable() {
  var t = window.VEFR_WORLD && window.VEFR_WORLD.traits;
  return (t && typeof t === 'object' && !Array.isArray(t)) ? t : {};
}
// Every trait the hero is bearing, with the thing that bears it: a worn
// thing's, and a carried bag's (a thing with `carry` is worn on the back).
// Identified or not - reading a thing tells you, it does not switch it on.
function rpgTraitSources() {
  var out = [];
  var cat = itemCatalog();
  // Read before this part's own `var`s are set when an earlier part asks at
  // load time (`var HERO_HP = heroMax()`), so every table is read guarded.
  var worn = WORN_INST || {};
  EQUIP_SLOTS.forEach(function (slot) {
    var id = EQUIP_STATE[slot];
    var inst = worn[slot];
    var traits = (inst && inst.traits) || ((cat[id] && Array.isArray(cat[id].traits)) ? cat[id].traits : []);
    if (typeof id === 'string') traits.forEach(function (w) { out.push({ word: w, from: id }); });
  });
  bagCarried().forEach(function (c) {
    var def = cat[c.id];
    if (!def || !rpgWhole(def.carry)) return;
    c.traits.forEach(function (w) { out.push({ word: w, from: c.id }); });
  });
  return out;
}
var RPG_STATS = ['hp', 'atk', 'guard', 'mana', 'crit'];
var RPG_REACTIONS = ['kill_heal', 'opener', 'thorns', 'sting'];
// The sum of every borne trait's stats, and each reaction with the thing
// that carries it (the strongest one wins, so two of a kind never chain).
function rpgTraitTotals() {
  var table = rpgTraitTable();
  var out = { hp: 0, atk: 0, guard: 0, mana: 0, crit: 0, reactions: {} };
  rpgTraitSources().forEach(function (src) {
    var spec = table[src.word];
    if (!spec || typeof spec !== 'object') return;
    RPG_STATS.forEach(function (k) { if (rpgWhole(spec[k])) out[k] += spec[k]; });
    RPG_REACTIONS.forEach(function (k) {
      if (!rpgWhole(spec[k]) || spec[k] <= 0) return;
      var held = out.reactions[k];
      if (!held || spec[k] > held.n) out.reactions[k] = { n: spec[k], from: src.from, word: src.word };
    });
  });
  return out;
}
function rpgTraitIsCurse(word) {
  var spec = rpgTraitTable()[word];
  return !!(spec && spec.curse === true);
}

// ---- gear and trait stats -------------------------------------------
// The worn `mods` the equip engine does not add (it adds hp and atk, as it
// always has): guard and mana, the two ADR 0021 gave a worn thing.
function rpgWornMods(stat) {
  var cat = itemCatalog();
  var total = 0;
  EQUIP_SLOTS.forEach(function (slot) {
    var def = cat[EQUIP_STATE[slot]];
    if (def && def.mods && rpgWhole(def.mods[stat]) && def.mods[stat] > 0) total += def.mods[stat];
  });
  return total;
}
// The hero's guard: the pack's base, worn mods, traits and a standing ward.
var RPG_WARD = { guard: 0, turns: 0 };
function heroGuard() {
  var base = rpgPlayer().guard;
  base = (rpgWhole(base) && base >= 0) ? base : 0;
  var ward = RPG_WARD || { guard: 0, turns: 0 };
  return Math.max(0, base + rpgWornMods('guard') + rpgTraitTotals().guard
                  + (ward.turns > 0 ? ward.guard : 0));
}
// A turn has passed: a standing ward counts down by one.
function rpgWardTick() {
  if (RPG_WARD.turns > 0) {
    RPG_WARD.turns--;
    if (!RPG_WARD.turns) RPG_WARD.guard = 0;
  }
}

// ---- mana -----------------------------------------------------------
// A pack opts in with `player.mana`; with none there is no mana at all, no
// line on the HUD and no saved key - a spell with a `mana` cost is then
// free, which is the answer for a pack that has not written the numbers.
function rpgManaOn() {
  var m = rpgPlayer().mana;
  return rpgWhole(m) && m >= 0;
}
function heroManaMax() {
  if (!rpgManaOn()) return 0;
  return Math.max(0, rpgPlayer().mana + rpgWornMods('mana') + rpgTraitTotals().mana);
}
var MANA_KEY = 'vefr-mana-' + rpgWorldName();
var HERO_MP = 0;
function loadHeroMana() {
  if (!rpgManaOn()) { HERO_MP = 0; return 0; }
  var n = parseInt(store.get(MANA_KEY), 10);
  var max = heroManaMax();
  HERO_MP = (isFinite(n) && n >= 0) ? Math.min(n, max) : max;
  return HERO_MP;
}
function saveHeroMana() {
  if (rpgManaOn()) store.set(MANA_KEY, HERO_MP);
}
// The mana line beside the health: words and a number, never a colour alone.
function renderMana() {
  var el = document.getElementById('hud-mana');
  if (!el) return;
  if (!rpgManaOn()) { el.hidden = true; el.textContent = ''; return; }
  HERO_MP = Math.min(HERO_MP, heroManaMax());
  el.hidden = false;
  el.textContent = 'Mana ' + HERO_MP + '/' + heroManaMax();
}

// ---- charges ----------------------------------------------------------
// A thing with `casts` holds `charges`; what is left rides on the carried
// instance. A bare id has all of them.
function rpgChargesLeft(entry, def) {
  if (!def || !rpgWhole(def.charges)) return 0;
  return (entry && rpgWhole(entry.charges)) ? entry.charges : def.charges;
}

// ---- spending a turn --------------------------------------------------
// With `fight.turns`, drinking, using a thing and casting cost a turn: the
// monsters act after it, as after a step. The closure installs the hook
// (part 510); before it does, or with no fight block, nothing happens.
function rpgSpendTurn() {
  var f = rpgFight();
  if (!f || !f.turns) return;
  if (typeof window.VEFR_SPEND_TURN === 'function') window.VEFR_SPEND_TURN();
}

// ---- rest ------------------------------------------------------------
// `time.rest_heals`: a rest away from the descent's floors, with nothing
// alive to fight in the region, restores health, mana and every charge.
// The closure says whether the hero is somewhere quiet (part 510).
function rpgRestHeals() {
  var t = window.VEFR_WORLD && window.VEFR_WORLD.time;
  if (!(t && t.rest_heals === true)) return false;
  var quiet = (typeof window.VEFR_QUIET_HERE === 'function') ? window.VEFR_QUIET_HERE() : false;
  if (!quiet) return false;
  HERO_HP = heroMax();
  saveHeroHp();
  renderHp();
  if (rpgManaOn()) { HERO_MP = heroManaMax(); saveHeroMana(); renderMana(); }
  rpgRechargeAll();
  return true;
}
function rpgRechargeAll() {
  var raw = store.getJSON(BAG_KEY, []);
  if (!Array.isArray(raw)) return;
  var changed = false;
  var out = raw.map(function (entry) {
    if (entry && typeof entry === 'object' && rpgWhole(entry.charges)) {
      changed = true;
      var copy = {};
      Object.keys(entry).forEach(function (k) { if (k !== 'charges') copy[k] = entry[k]; });
      return (copy.rarity || (copy.traits && copy.traits.length)) ? copy : copy.id;
    }
    return entry;
  });
  if (changed) store.setJSON(BAG_KEY, out);
  Object.keys(WORN_INST).forEach(function (slot) {
    if (WORN_INST[slot] && rpgWhole(WORN_INST[slot].charges)) {
      delete WORN_INST[slot].charges;
      if (!rpgInstanceOf(WORN_INST[slot])) delete WORN_INST[slot];
      changed = true;
    }
  });
  if (changed) { saveWornInstances(); renderBagPanel(); }
}

// A harness-readable view of the core (precedent: window.VEFR_TIME): every
// number the rules above derive, for a pack that opts in and one that does not.
window.VEFR_RPG = function () {
  var t = rpgTraitTotals();
  return {
    fight: rpgFight(), guard: heroGuard(), mana: HERO_MP, manaMax: heroManaMax(),
    traits: { hp: t.hp, atk: t.atk, guard: t.guard, mana: t.mana, crit: t.crit,
              reactions: Object.keys(t.reactions).sort() },
    ward: { guard: RPG_WARD.guard, turns: RPG_WARD.turns },
    worn: JSON.parse(JSON.stringify(WORN_INST))
  };
};
