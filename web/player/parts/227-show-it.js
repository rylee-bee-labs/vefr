// ---- show it (ADR 0023): what the fight already does, where the player looks ----
// Four things the rules already did, each only in a sentence that the next
// one replaced: a spell learned on a level, gear better than what is worn,
// the number a blow struck for, and the potions and spells kept in the Bag.
// Each one is opt-in on its own `display` key, so a pack that names none of
// them plays and looks exactly as it did:
//
//   * `spell_card`  - a card says what a spell just learned does, what it
//     costs and how to cast it;
//   * `wear_prompt` - picking up gear that would raise a stat asks "Wear
//     it?" and shows the change (Attack 3 to 5), the way a stake asks;
//   * `hit_numbers` - each blow's number over the one it struck (part 507);
//   * `hotbar`      - up to four quick-use buttons for the things used in
//     one tap and the spells the hero knows, keys 5 to 8 (part 515 draws
//     it, part 510 answers its keys).
function displayOn(name) {
  var d = window.VEFR_WORLD && window.VEFR_WORLD.display;
  return !!(d && typeof d === 'object' && d[name] === true);
}

// A number over the hero from outside the fight's closure (a drink, a
// spell's heal): part 507 draws it, and with `hit_numbers` off it draws none.
function heroHitNumber(text, kind) {
  if (typeof window.VEFR_HIT_AT === 'function') window.VEFR_HIT_AT(null, text, kind);
}

// ---- the spell card ---------------------------------------------------
// A card like the fall's: one quiet box near the foot of the screen, the
// focus on its one button, and back where it was when it closes. It waits
// for Interact, the menu key or a tap: a walking key does nothing while it
// is up, so a player pressing on through a fight does not wave it away
// unread. Two spells learned on one level are two cards, one after the
// other, in the pack's order.
var LEARN_QUEUE = [];
var learnOpener = null;
function spellCardOn() { return displayOn('spell_card'); }
// What the spell does, in the words the cast itself will say.
function spellCardNotes(spell) {
  var notes = [];
  var harm = rpgWhole(spell.harm) && spell.harm > 0 ? spell.harm : 0;
  var ward = spell.ward && typeof spell.ward === 'object' ? spell.ward : null;
  var heal = typeof spell.heal === 'number' && spell.heal > 0 ? spell.heal : 0;
  if (harm) {
    var reach = (rpgWhole(spell.range) && spell.range > 0) ? spell.range : 6;
    notes.push('It strikes the nearest foe within ' + reach + ' tiles for ' + harm
      + '. Guard does not stop it.');
  } else if (ward && rpgWhole(ward.guard) && rpgWhole(ward.turns)) {
    notes.push('It raises your guard by ' + ward.guard + ' for ' + ward.turns
      + (ward.turns === 1 ? ' turn.' : ' turns.'));
  } else if (heal) {
    notes.push('It heals you by ' + heal + '.');
  }
  if (rpgManaOn() && rpgWhole(spell.mana) && spell.mana > 0) {
    notes.push('It costs ' + spell.mana + ' mana.');
  }
  notes.push(spellCardHow(spell));
  return notes;
}
// How to cast it, from what this pack actually puts on screen: the quick
// bar's key when it is there, the fight row's Cast when that is the spell
// the row casts, and the Bag always.
function spellCardHow(spell) {
  var slot = -1;
  if (hotbarOn()) {
    var things = hotbarThings();
    for (var i = 0; i < things.length; i++) {
      if (things[i].kind === 'spell' && things[i].id === spell.id) slot = i;
    }
  }
  if (slot >= 0) {
    var keys = keybindKeys('quick' + (slot + 1));
    return 'Press ' + (keys.length ? keybindKeyName(keys[0]) : 'its key')
      + ' or tap it on the quick bar. It is in the Bag too.';
  }
  var row = rpgReadySpell();
  if (rpgWhole(spell.harm) && spell.harm > 0 && (!row || row.id === spell.id)) {
    return 'In a fight, Cast on the fight row casts it. It is in the Bag too.';
  }
  return 'Cast it from the Bag.';
}
function showSpellCard(id) {
  var spell = spellById(id);
  var card = document.getElementById('learn');
  if (!spell || !card || !spellCardOn()) return;
  if (!card.hidden) { LEARN_QUEUE.push(id); return; }
  var line = 'You learn ' + (spell.name || id) + '.';
  document.getElementById('learn-line').textContent = line;
  var list = document.getElementById('learn-notes');
  list.textContent = '';
  spellCardNotes(spell).forEach(function (text) {
    var li = document.createElement('li');
    li.textContent = text;
    list.appendChild(li);
  });
  card.dataset.spell = id;
  journalSay(line);
  if (!learnOpener) learnOpener = document.activeElement;
  card.hidden = false;
  var ok = document.getElementById('learn-ok');
  if (ok) ok.focus();
}
function closeSpellCard() {
  var card = document.getElementById('learn');
  if (!card || card.hidden) return;
  card.hidden = true;
  delete card.dataset.spell;
  if (LEARN_QUEUE.length) { showSpellCard(LEARN_QUEUE.shift()); return; }
  var back = learnOpener;
  learnOpener = null;
  try {
    if (back && back !== document.body && back !== document.documentElement
        && back.isConnected && back.focus) back.focus();
    else document.getElementById('menu-open').focus();
  } catch (e) { /* gone */ }
}
// The spells a level has just taught: the ones known now that were not
// known before, in the pack's order. Read by the growth part around an
// award, so a level-learned spell gets its card the moment it is earned.
function spellIdsKnown() {
  return spellsKnown().map(function (s) { return s.id; });
}
function spellCardsSince(before) {
  if (!spellCardOn()) return;
  spellIdsKnown().forEach(function (id) {
    if (before.indexOf(id) < 0) showSpellCard(id);
  });
}
(function () {
  var card = document.getElementById('learn');
  if (!card) return;
  document.getElementById('learn-ok').addEventListener('click', function (e) {
    e.stopPropagation();
    closeSpellCard();
  });
  // A tap on the dim around the card closes it too, as the fall's does.
  card.addEventListener('click', function (e) {
    if (e.target === card) closeSpellCard();
  });
})();

// ---- Wear it? -----------------------------------------------------------
// Picking up a thing that would raise one of the hero's numbers asks, the
// way a stake asks: a line and two buttons under the messages, Y and N on
// a keyboard, and the game going on while it waits. The change is what the
// player can know: the thing's own `mods` and the traits of an instance the
// town has read. An unread trait is in no number here, as it is in no word
// anywhere else (ADR 0017), so the question never gives a curse away.
var WEAR_PENDING = null;
var wearOpener = null;
function wearPromptOn() { return displayOn('wear_prompt'); }
var WEAR_STATS = [['hp', 'Health'], ['atk', 'Attack'], ['guard', 'Guard'], ['mana', 'Mana']];
function wearKnown(id, inst) {
  var def = itemCatalog()[id];
  var out = { hp: 0, atk: 0, guard: 0, mana: 0 };
  if (!def) return out;
  var mods = def.mods && typeof def.mods === 'object' ? def.mods : {};
  WEAR_STATS.forEach(function (pair) {
    if (rpgWhole(mods[pair[0]]) && mods[pair[0]] > 0) out[pair[0]] += mods[pair[0]];
  });
  if (inst && inst.identified === true && Array.isArray(inst.traits)) {
    var table = rpgTraitTable();
    inst.traits.forEach(function (word) {
      var spec = table[word];
      if (!spec || typeof spec !== 'object') return;
      WEAR_STATS.forEach(function (pair) {
        if (rpgWhole(spec[pair[0]])) out[pair[0]] += spec[pair[0]];
      });
    });
  }
  return out;
}
// The hero's numbers now, as the HUD and the Bag read them (a ward's
// passing guard is not counted: wearing a thing does not raise it).
function wearNow() {
  var ward = (RPG_WARD && RPG_WARD.turns > 0) ? RPG_WARD.guard : 0;
  return { hp: heroMax(), atk: heroAtk(), guard: heroGuard() - ward, mana: heroManaMax() };
}
// What wearing `carried` would change, stat by stat, or [] when it would
// raise nothing. Mana is counted only for a pack that has it.
function wearChange(carried) {
  var def = itemCatalog()[carried.id];
  if (!def || typeof def.slot !== 'string' || EQUIP_SLOTS.indexOf(def.slot) < 0) return [];
  var wornId = (typeof EQUIP_STATE[def.slot] === 'string') ? EQUIP_STATE[def.slot] : null;
  var on = wearKnown(carried.id, carried);
  var off = wornId ? wearKnown(wornId, WORN_INST[def.slot]) : wearKnown('', null);
  var now = wearNow();
  var out = [];
  var raises = false;
  WEAR_STATS.forEach(function (pair) {
    if (pair[0] === 'mana' && !rpgManaOn()) return;
    var delta = on[pair[0]] - off[pair[0]];
    if (!delta) return;
    if (delta > 0) raises = true;
    out.push({ stat: pair[0], word: pair[1], from: now[pair[0]],
               to: Math.max(pair[0] === 'hp' || pair[0] === 'atk' ? 1 : 0, now[pair[0]] + delta) });
  });
  return raises ? out : [];
}
function wearHost() { return document.getElementById('wear-ask'); }
function wearClose() {
  var host = wearHost();
  WEAR_PENDING = null;
  if (!host) return;
  var hadFocus = host.contains(document.activeElement);
  while (host.firstChild) host.removeChild(host.firstChild);
  host.hidden = true;
  var back = wearOpener;
  wearOpener = null;
  if (!hadFocus) return;
  try {
    if (back && back !== document.body && back.isConnected && back.focus) back.focus();
  } catch (e) { /* gone */ }
}
// Ask about one carried thing, just picked up. Nothing is asked when the
// pack has not opted in, when the thing raises nothing, or when another
// question (a stake) is already waiting for the same two keys.
function offerToWear(carried) {
  if (!wearPromptOn() || !carried || (typeof STAKE_PENDING !== 'undefined' && STAKE_PENDING)) return false;
  var change = wearChange(carried);
  var host = wearHost();
  if (!change.length || !host) return false;
  var def = itemCatalog()[carried.id];
  var keepFocus = WEAR_PENDING ? wearOpener : document.activeElement;
  wearClose();
  WEAR_PENDING = { carried: carried };
  wearOpener = keepFocus;
  // Lines in a div, not a <p>: on a phone the messages fold every <p> but
  // the newest, and the question must stay whole while it waits.
  var line = document.createElement('div');
  line.className = 'glass wear-line';
  line.id = 'wear-line';
  line.textContent = 'Wear ' + carriedName(carried) + '?';
  host.appendChild(line);
  var worn = (typeof EQUIP_STATE[def.slot] === 'string') ? EQUIP_STATE[def.slot] : null;
  var said = [];
  change.forEach(function (c) {
    var p = document.createElement('div');
    p.className = 'glass wear-change';
    p.dataset.stat = c.stat;
    // The arrow is for the eye; a screen reader hears "from 3 to 5".
    p.appendChild(document.createTextNode(c.word + ' '));
    var sr = document.createElement('span');
    sr.className = 'sr-only';
    sr.textContent = 'from ';
    p.appendChild(sr);
    p.appendChild(document.createTextNode(c.from + ' '));
    var arrow = document.createElement('span');
    arrow.setAttribute('aria-hidden', 'true');
    arrow.textContent = '→ ';
    p.appendChild(arrow);
    var to = document.createElement('span');
    to.className = 'sr-only';
    to.textContent = 'to ';
    p.appendChild(to);
    p.appendChild(document.createTextNode(String(c.to)));
    host.appendChild(p);
    said.push(c.word + ' from ' + c.from + ' to ' + c.to);
  });
  if (worn) {
    var off = document.createElement('div');
    off.className = 'glass wear-change';
    off.textContent = itemName(worn) + ' comes off.';
    host.appendChild(off);
  }
  var wear = stakeButton('wear-yes', 'stake-btn stake-btn--take', 'Wear it',
    said.join(', '), wearYes);
  var skip = stakeButton('wear-no', 'stake-btn', 'Not now',
    'keep it in the bag', wearNo);
  wear.setAttribute('aria-keyshortcuts', 'y');
  skip.setAttribute('aria-keyshortcuts', 'n');
  [[wear, 'Y'], [skip, 'N']].forEach(function (pair) {
    var k = document.createElement('kbd');
    k.textContent = pair[1];
    pair[0].appendChild(document.createTextNode(' '));
    pair[0].appendChild(k);
  });
  host.appendChild(wear);
  host.appendChild(skip);
  host.hidden = false;
  // Focus opens on the answer that changes nothing, as the stake's does:
  // a player who pressed Enter to walk on has not been asked yet.
  skip.focus();
  return true;
}
// The thing asked about must still be in the bag: the question may have
// waited while it was dropped, sold or left in a satchel.
function wearCarriedNow(carried) {
  var all = bagCarried();
  for (var i = 0; i < all.length; i++) {
    var c = all[i];
    if (c.id === carried.id && c.rarity === carried.rarity
        && c.traits.join(',') === carried.traits.join(',')) return c;
  }
  return null;
}
function wearYes() {
  var asked = WEAR_PENDING;
  wearClose();
  if (!asked) return;
  var held = wearCarriedNow(asked.carried);
  if (!held) {
    combatSay('You no longer carry ' + itemName(asked.carried.id) + '.');
    return;
  }
  equipItem(held.id, held);
  var said = (document.getElementById('bag-live') || {}).textContent || '';
  if (said) combatSay(said);
}
function wearNo() {
  wearClose();
}
// Y and N answer the question and nothing else; with none waiting, both
// keys mean what they always meant.
function wearKey(e) {
  if (!WEAR_PENDING || e.repeat) return false;
  var k = (e.key && e.key.length === 1) ? e.key.toLowerCase() : '';
  if (k === 'y') { wearYes(); return true; }
  if (k === 'n') { wearNo(); return true; }
  return false;
}

// ---- the quick bar ------------------------------------------------------
// The things a player reaches for in a fight, one tap each: a carried thing
// used in one go (a heal, a light, a thing that casts), one button per kind
// in the pack's own item order, then the spells the hero knows in the
// pack's own order - at most four. Keys 5 to 8 by default, in the player's
// Controls like every other key; with the bar on, the fight row's number
// keys stop at 4, so a digit always means one button.
// Four slots. A function, not a `var`: the bag strip draws the bar while
// earlier parts are still loading, before a `var` here would be set.
function hotbarSlots() { return 4; }
function hotbarOn() { return displayOn('hotbar'); }
function quickUse(def) {
  return !!def && ((typeof def.heal === 'number' && def.heal > 0)
    || (typeof def.casts === 'string' && !!def.casts)
    || (!!def.light && typeof def.light === 'object'));
}
function hotbarThings() {
  if (!hotbarOn()) return [];
  var cat = itemCatalog();
  var counts = {};
  bagCarried().forEach(function (c) { counts[c.id] = (counts[c.id] || 0) + 1; });
  var out = [];
  Object.keys(cat).forEach(function (id) {
    if (counts[id] && quickUse(cat[id])) out.push({ kind: 'item', id: id, count: counts[id] });
  });
  spellsKnown().forEach(function (s) { out.push({ kind: 'spell', id: s.id, spell: s }); });
  return out.slice(0, hotbarSlots());
}
// The slot a key answers for (0 to 3), or -1.
function hotbarSlotFor(key) {
  if (!hotbarOn()) return -1;
  for (var i = 0; i < hotbarSlots(); i++) {
    if (keybindOn('quick' + (i + 1), key)) return i;
  }
  return -1;
}
// One press of one slot: the Bag's own Use, or the Bag's own Cast aimed at
// the foe the fight row names. An empty slot does nothing. The Bag says
// what happened in its own line, which is not on screen in play, so the
// same words go to the fight's line - ahead of whatever a monster answered
// with in the turn the press cost, so both are read in the order they
// happened.
function hotbarPress(i) {
  var t = hotbarThings()[i];
  if (!t) return false;
  var live = document.getElementById('bag-live');
  if (live) live.textContent = '';
  var before = combatText();
  if (t.kind === 'item') useItem(t.id);
  else castSpell(t.id, { target: (typeof VERB_TARGET !== 'undefined') ? VERB_TARGET : null });
  var said = live ? live.textContent : '';
  if (said) {
    var now = combatText();
    combatSay((now && now !== before && said.indexOf(now) < 0) ? said + ' ' + now : said, true);
  }
  return true;
}
