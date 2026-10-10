// ---- gold: the hero's purse, persisted with the bag ----
// `vefr-gold-<world>` holds one number; the baked `VEFR_HERO.gold` is
// the starting purse (default 0). A world with no shop and no priced
// item shows no gold line, so an old world's HUD is untouched.
var GOLD_KEY = 'vefr-gold-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');

function itemHasValue(def) {
  return !!(def && typeof def.value === 'number' && def.value > 0);
}

// Does this world trade at all? A shop, or anything a shop would pay
// for. When false the game is exactly the game it was before gold.
var REWARD_ON = (function () {
  if (Object.keys(window.VEFR_SHOPS || {}).length) return true;
  var cat = window.VEFR_ITEMS || {};
  return Object.keys(cat).some(function (id) { return itemHasValue(cat[id]); });
})();

function heroGold() {
  var n = parseInt(store.get(GOLD_KEY), 10);
  if (isFinite(n) && n >= 0) return n;
  var baked = window.VEFR_HERO && window.VEFR_HERO.gold;
  return (typeof baked === 'number' && baked >= 0) ? baked : 0;
}
function saveGold(n) {
  n = Math.max(0, Math.floor(n));
  store.set(GOLD_KEY, n);
  return n;
}

function itemCatalog() {
  return (window.VEFR_ITEMS && typeof window.VEFR_ITEMS === 'object')
    ? window.VEFR_ITEMS : {};
}
function itemName(id) {
  var def = itemCatalog()[id];
  return (def && def.name) || id;
}
function itemSpriteSrc(id) {
  var def = itemCatalog()[id];
  var name = def && def.sprite;
  if (!name) return '';
  return (window.VEFR_SPRITES || {})[name] || '';
}
// ---- what is carried (ADR 0017) ----
// The bag is a list, and an entry in it is either a bare id - what every
// bag held before this slice, and what every pack that declares no `roll`
// still holds, byte for byte - or an instance record a rolled drop brought
// in: `{id, rarity, traits, identified}`. `bagCarried` reads both the same
// way, so every caller below can ask for what it needs and get it.
//
// The traits are read here and printed NOWHERE while `identified` is
// false - not covered up, absent from the page, so nothing is hidden
// from a screen reader that is not also hidden from the eye. Since ADR
// 0017's slice 2 something does turn it true: the identify service
// (`195-the-identify-service.js`) sets it on the instance in the saved
// bag, and `carriedName` below is the one line that changes - it is the
// only place the traits are allowed to become words.
function bagCarried() {
  var raw = store.getJSON(BAG_KEY, []);
  var cat = itemCatalog();
  if (!Array.isArray(raw)) return [];
  var out = [];
  for (var i = 0; i < raw.length; i++) {
    var entry = raw[i];
    var record = (entry && typeof entry === 'object' && !Array.isArray(entry)) ? entry : null;
    var id = record ? record.id : entry;
    if (typeof id !== 'string' || !cat[id]) continue;
    out.push({
      id: id,
      rarity: (record && typeof record.rarity === 'string') ? record.rarity : '',
      traits: (record && Array.isArray(record.traits))
        ? record.traits.filter(function (t) { return typeof t === 'string'; }) : [],
      identified: !!(record && record.identified === true)
    });
  }
  return out;
}
function bagItems() {
  return bagCarried().map(function (carried) { return carried.id; });
}
// What one carried thing is called: its own words, its rarity beside them
// the moment it is picked up (ADR 0017, slice 1), and - once the town has
// read it - its traits after that, in the same string. Nothing here
// animates, nothing waits on a timer and no trait is revealed by a
// picture: the whole reveal is this concatenation, so with motion off it
// is there on the first frame, and a screen reader reads the same
// sentence the eye reads. The traits are in it only while `identified`
// is true; before that they are in no part of the page.
function carriedName(carried) {
  var name = itemName(carried.id);
  var words = carried.rarity ? (name + ' (' + carried.rarity + ')') : name;
  if (carried.identified && carried.traits.length) {
    words += ' - traits: ' + carried.traits.join(', ');
  }
  return words;
}
// Rebuild the harness-readable fight snapshot after bag/gold changes.
// setupTown installs the real builder; before that (or in a pack with no
// game surface) this is a no-op.
function syncCombat() {
  if (typeof window.refreshCombatSnapshot === 'function') {
    try { window.refreshCombatSnapshot(); } catch (e) {}
  }
}
// Put one thing in the bag. `roll` is the drop's drawn
// `{rarity, traits}` when it has any: with it, the entry is saved as an
// instance record so the rarity is there on the next load and is never
// drawn twice; without it, the entry is the bare id this has always
// stored, which is what every caller but a floor drop passes.
function bagAdd(id, roll) {
  if (!itemCatalog()[id]) return false;
  var raw = store.getJSON(BAG_KEY, []);
  var cat = itemCatalog();
  // The bag has always dropped an id the catalog no longer has every time
  // it wrote, and it still does - an instance record is kept as itself,
  // because its id is the thing being carried.
  var ids = [];
  (Array.isArray(raw) ? raw : []).forEach(function (entry) {
    var named = (entry && typeof entry === 'object' && !Array.isArray(entry))
      ? entry.id : entry;
    if (typeof named === 'string' && cat[named]) ids.push(entry);
  });
  var rarity = (roll && typeof roll.rarity === 'string') ? roll.rarity : '';
  var traits = (roll && Array.isArray(roll.traits))
    ? roll.traits.filter(function (t) { return typeof t === 'string'; }) : [];
  if (rarity || traits.length) {
    ids.push({ id: id, rarity: rarity, traits: traits, identified: false });
  } else {
    ids.push(id);
  }
  store.setJSON(BAG_KEY, ids);
  renderBagPanel();
  renderBagStrip();
  syncCombat();
  return true;
}
// Take one copy of an id out of the bag - the first entry naming it, an
// instance record or a bare id alike. False when it was not carried.
function bagRemoveOne(id) {
  var ids = store.getJSON(BAG_KEY, []);
  if (!Array.isArray(ids)) return false;
  var at = -1;
  for (var i = 0; i < ids.length; i++) {
    var entry = ids[i];
    var named = (entry && typeof entry === 'object' && !Array.isArray(entry))
      ? entry.id : entry;
    if (named === id) { at = i; break; }
  }
  if (at === -1) return false;
  ids.splice(at, 1);
  store.setJSON(BAG_KEY, ids);
  renderBagPanel();
  renderBagStrip();
  syncCombat();
  return true;
}

// Use a carried thing. A thing the pack gave a `light` lights the dark
// (see setupTown); a thing with a `heal` raises health by `heal` (never
// above the max); a thing with a `spell` teaches it (ADR 0018). Either
// way it takes one copy out of the bag and says so in the panel's live
// line. With none of them, nothing happens.
function useItem(id) {
  var def = itemCatalog()[id];
  if (!def) return false;
  // A worn thing is not in the bag list, so its Use button does not
  // exist; if anything still reaches it, the line says take it off.
  if (isWorn(id)) {
    bagSay('Take it off first.');
    return false;
  }
  // The `use` verb fires with the item and the named place the hero is
  // standing on (the POI line's own text - the thing in reach); with
  // no named place it is '', which matches no rule and harms nothing.
  fireRule('uses-with', { item: id, with: (document.getElementById('poi') || {}).textContent || '' });
  // Usable is not the same as consumable: a `keep` thing is used and
  // stays; a bare `use` (no heal, no light) has nothing to spend and
  // is the natural shape of a quest tool.
  var keep = def.keep === true;
  if (def.light && typeof def.light === 'object'
      && typeof window.useLightItem === 'function') {
    return window.useLightItem(id, def);
  }
  var verb = def.use || 'use';
  // A spellbook is an ordinary item that teaches one spell when it is used
  // (ADR 0018), so the lesson rides the verb the bag has always had: the
  // book is read, one copy leaves the bag, and the spell is learned. The
  // `keep` rule is the item's own - a book the pack wants to stay in the
  // bag is used and stays.
  if (typeof def.spell === 'string' && def.spell) {
    if (!spellById(def.spell)) {
      // Only a pack `vefr check` refused gets here: the book names a
      // spell the pack never wrote. Say so in words rather than taking a
      // book away for a spell nobody can learn.
      bagSay('Nothing in ' + itemName(id) + ' is a spell this world teaches.');
      return false;
    }
    if (!keep && !bagRemoveOne(id)) return false;
    var fresh = learnSpellFromBook(def.spell);
    var learned = fresh ? (' You learn ' + spellName(def.spell) + '.')
      : ' You already know that one.';
    bagSay('You ' + verb + ' ' + itemName(id) + '.' + learned);
    renderSpellList();
    return true;
  }
  if (!(typeof def.heal === 'number' && def.heal > 0)) {
    bagSay('You ' + verb + ' ' + itemName(id) + '.');
    return true;
  }
  // Whole already: say so and keep the thing. A potion is not spent on
  // nothing, so the player never loses a heal by mis-tapping.
  if (HERO_HP >= heroMax()) {
    bagSay('You ' + verb + ' ' + itemName(id) + '. You are already whole.');
    return true;
  }
  if (!keep && !bagRemoveOne(id)) return false;
  var before = HERO_HP;
  HERO_HP = Math.min(heroMax(), HERO_HP + def.heal);
  saveHeroHp();
  renderHp();
  var gained = HERO_HP - before;
  bagSay('You ' + verb + ' ' + itemName(id) + '. '
    + 'You recover ' + gained + ' health.');
  syncCombat();
  return true;
}

// The Bag panel's live line (kept in the panel, not the game's toasts).
function bagSay(msg) {
  var el = document.getElementById('bag-live');
  if (el) el.textContent = msg || '';
}

// Gold writes redraw both the HUD line and the Bag panel's line.
function renderGold() {
  var g = heroGold();
  var hud = document.getElementById('hud-gold');
  if (hud) { hud.hidden = !REWARD_ON; hud.textContent = g + ' gold'; }
  var panel = document.getElementById('bag-gold');
  if (panel) panel.textContent = REWARD_ON ? ('You carry ' + g + ' gold.') : '';
  syncCombat();
}
function addGold(n) {
  var g = saveGold(heroGold() + n);
  renderGold();
  return g;
}

// The top-of-screen strip: a small sprite per carried thing, beside the
// health bar. A thing with no ready sprite is a neutral dot. A worn
// thing is not in the bag list and is not shown here - it sits in its
// slot in the Bag panel instead.
function renderBagStrip() {
  var strip = document.getElementById('bag-strip');
  if (!strip) return;
  strip.textContent = '';
  var carried = bagCarried().filter(function (c) { return !isWorn(c.id); });
  if (!carried.length) {
    strip.hidden = true;
    strip.setAttribute('aria-label', 'Nothing carried');
    return;
  }
  strip.hidden = false;
  carried.forEach(function (c) {
    var src = itemSpriteSrc(c.id);
    var node;
    if (src) {
      node = document.createElement('img');
      node.src = src;
      node.alt = '';
      node.className = 'bag-pip';
    } else {
      node = document.createElement('span');
      node.className = 'bag-pip bag-pip--dot';
      node.setAttribute('aria-hidden', 'true');
    }
    strip.appendChild(node);
  });
  // The strip's own words carry the rarity too, so a screen reader hears
  // what the eye sees and neither has to wait for anything.
  strip.setAttribute('aria-label',
    'Carrying: ' + carried.map(carriedName).join(', ') + '.');
}

// The Bag panel's "You" section: five slots in a fixed order, each
// row named by one sentence the eye and the screen reader share.
// An empty slot draws a plain inline-SVG outline so no new art file
// is needed. A worn slot gets a "Take off" button.
function emptySlotSvg(slot) {
  var head = '<svg class="equip-empty-svg" viewBox="0 0 32 32" aria-hidden="true" focusable="false">';
  switch (slot) {
    case 'hand':  return head + '<path d="M16 6v14M12 10l4-4 4 4M10 22h12"/></svg>';
    case 'body':  return head + '<path d="M10 8l6-2 6 2v10l-6 6-6-6z"/></svg>';
    case 'head':  return head + '<circle cx="16" cy="14" r="7"/><path d="M9 24h14"/></svg>';
    case 'feet':  return head + '<path d="M8 22h16l-2-6-6-2-6 2z"/></svg>';
    case 'charm': return head + '<circle cx="16" cy="16" r="6"/><circle cx="16" cy="16" r="2"/></svg>';
    default:      return head + '<rect x="6" y="6" width="20" height="20"/></svg>';
  }
}
function renderEquipSlots() {
  var host = document.getElementById('equip-slots');
  if (!host) return;
  host.textContent = '';
  var cat = itemCatalog();
  EQUIP_SLOTS.forEach(function (slot) {
    var row = document.createElement('div');
    row.className = 'equip-row';
    row.setAttribute('role', 'listitem');
    row.dataset.slot = slot;
    var id = (typeof EQUIP_STATE[slot] === 'string') ? EQUIP_STATE[slot] : null;
    var def = (id && cat[id]) ? cat[id] : null;
    var cap = slot.charAt(0).toUpperCase() + slot.slice(1);
    var sentence = def ? (cap + ': ' + (def.name || id)) : (cap + ': empty');
    // The art is decoration: the sentence carries the name. The empty
    // outline means "nothing worn here", so a worn slot must never draw
    // it - a worn thing with no ready sprite gets the same neutral dot
    // the bag list uses, so the two states never look alike.
    var art = document.createElement('span');
    art.className = 'equip-row-art';
    art.setAttribute('aria-hidden', 'true');
    if (def) {
      var src = itemSpriteSrc(id);
      if (src) {
        var im = document.createElement('img');
        im.src = src;
        im.alt = '';
        art.appendChild(im);
      } else {
        art.appendChild(document.createElement('span'));
        art.firstChild.className = 'bag-row-art--dot';
      }
    } else {
      art.innerHTML = emptySlotSvg(slot);
    }
    row.appendChild(art);
    var label = document.createElement('span');
    label.className = 'equip-row-name';
    label.textContent = sentence;
    row.appendChild(label);
    if (def) {
      var takeOff = document.createElement('button');
      takeOff.type = 'button';
      takeOff.className = 'cta';
      takeOff.textContent = 'Take off';
      takeOff.setAttribute('aria-label', 'Take off ' + (def.name || id));
      takeOff.dataset.slot = slot;
      takeOff.dataset.action = 'takeoff';
      takeOff.addEventListener('click', function () { takeOffSlot(slot); });
      row.appendChild(takeOff);
    }
    host.appendChild(row);
  });
}
// A one-line summary of what a worn item's mods do, for the live line.
// An item with no mods returns an empty string so the caller can skip.
function modsLine(def) {
  if (!def || !def.mods || typeof def.mods !== 'object') return '';
  var parts = [];
  if (typeof def.mods.hp === 'number' && def.mods.hp > 0) parts.push('Health up by ' + def.mods.hp);
  if (typeof def.mods.atk === 'number' && def.mods.atk > 0) parts.push('Attack up by ' + def.mods.atk);
  return parts.join('. ');
}
// The engine's refusal reasons in plain words the player can read.
function reasonToWords(reason) {
  switch (reason) {
    case 'not-an-item': return 'That is not something you can wear.';
    case 'no-slot':     return 'That cannot be worn.';
    case 'bad-slot':    return 'That does not fit there.';
    case 'wrong-slot':  return 'That does not fit there.';
    default:            return 'That did not work.';
  }
}
// Equip a carried thing into its own slot. The bag row is removed and
// the old wearer, if any, comes back to the bag.
function equipItem(id) {
  var def = itemCatalog()[id];
  if (!def) return;
  var engine = window.VEFR_EQUIP_ENGINE;
  if (!engine) {
    bagSay(reasonToWords('not-an-item'));
    return;
  }
  // An item with no slot cannot be worn. Say so in words rather than
  // asking the engine with a made-up slot.
  if (typeof def.slot !== 'string' || EQUIP_SLOTS.indexOf(def.slot) < 0) {
    bagSay(reasonToWords('no-slot'));
    return;
  }
  var result = engine.equip(EQUIP_STATE, itemCatalog(), def.slot, id);
  if (result.reason !== 'ok') {
    bagSay(reasonToWords(result.reason));
    return;
  }
  // Apply the change before the re-render so every read sees the new state.
  EQUIP_STATE = result.state;
  saveEquipped(EQUIP_STATE);
  bagRemoveOne(id);
  if (result.swapped) bagAdd(result.swapped);
  var line = 'You put on ' + (def.name || id) + '.';
  var ml = modsLine(def);
  if (ml) line += ' ' + ml + '.';
  // On a swap, name what came off so the player can see the change.
  if (result.swapped) {
    var oldDef = itemCatalog()[result.swapped];
    line += ' ' + (oldDef ? (oldDef.name || result.swapped) : result.swapped) + ' comes off.';
  }
  bagSay(line);
  renderHp();
  renderEquipSlots();
  syncCombat();
}
// Take a worn thing off: the slot empties, the thing returns to the
// bag, and current health is clamped to the new max if needed.
function takeOffSlot(slot) {
  var engine = window.VEFR_EQUIP_ENGINE;
  if (!engine) return;
  var id = (typeof EQUIP_STATE[slot] === 'string') ? EQUIP_STATE[slot] : null;
  var def = id ? itemCatalog()[id] : null;
  var result = engine.unequip(EQUIP_STATE, slot);
  if (!result.removed) {
    bagSay('Nothing to take off there.');
    return;
  }
  EQUIP_STATE = result.state;
  saveEquipped(EQUIP_STATE);
  bagAdd(result.removed);
  // If the new max is below current, clamp and save; never below 1.
  var newMax = heroMax();
  if (HERO_HP > newMax) {
    HERO_HP = engine.clampHealth(HERO_HP, newMax);
    saveHeroHp();
  }
  var line = 'You take off ' + (def ? (def.name || result.removed) : result.removed) + '.';
  bagSay(line);
  renderHp();
  renderEquipSlots();
  syncCombat();
}

// The pause-menu panel: a "You" section of five slots, then one row
// per carried (not worn) thing, sprite then name. A slotted thing in
// the bag gets an Equip button; anything with `use`, `heal`, `light` or
// `spell` keeps its Use button. A worn thing is never in this list. A row names
// the thing and its rarity together (ADR 0017), in one line of text with
// no timer behind it, so with motion off the rarity is there the moment
// the panel opens - and the traits it does not name (an unread thing)
// are not in the DOM at all, so nothing is only hidden from the eye. A
// thing the town's identify service has read names its traits here, in
// the same line and the same pass, with nothing behind a timer. The
// Spells section below the list is ADR 0018's, and it is nothing at all
// for a pack that declares no spells.
function renderBagPanel() {
  renderEquipSlots();
  renderSpellList();
  var list = document.getElementById('bag-list');
  var count = document.getElementById('bag-count');
  if (!list) return;
  list.textContent = '';
  var carried = bagCarried().filter(function (c) { return !isWorn(c.id); });
  var ids = carried.map(function (c) { return c.id; });
  if (!ids.length) {
    var p = document.createElement('p');
    p.className = 'empty';
    p.textContent = 'Nothing yet.';
    list.appendChild(p);
    if (count) count.textContent = '';
    renderGold();
    return;
  }
  carried.forEach(function (entry) {
    var id = entry.id;
    var row = document.createElement('div');
    row.className = 'bag-row';
    var src = itemSpriteSrc(id);
    if (src) {
      var im = document.createElement('img');
      im.src = src;
      im.alt = '';
      im.className = 'bag-row-art';
      row.appendChild(im);
    } else {
      var dot = document.createElement('span');
      dot.className = 'bag-row-art bag-row-art--dot';
      dot.setAttribute('aria-hidden', 'true');
      row.appendChild(dot);
    }
    var label = document.createElement('span');
    label.className = 'bag-row-name';
    label.textContent = carriedName(entry);
    row.appendChild(label);
    var def = itemCatalog()[id];
    // A slotted thing can be equipped from here. The engine refuses
    // anything that does not fit; the live line says so in words.
    if (def && typeof def.slot === 'string' && EQUIP_SLOTS.indexOf(def.slot) >= 0) {
      var eb = document.createElement('button');
      eb.type = 'button';
      eb.className = 'cta';
      eb.textContent = 'Equip';
      eb.dataset.item = id;
      eb.dataset.action = 'equip';
      eb.setAttribute('aria-label', 'Equip ' + itemName(id));
      eb.addEventListener('click', function () { equipItem(id); });
      row.appendChild(eb);
    }
    // Anything the pack gave a `use`, a `heal`, a `light` or a `spell`
    // can be used from here. The words are the pack's own verb, so a
    // potion is drunk, bread is eaten, a torch is lit and a book is
    // read. Usable is not the same as consumable: a `keep` thing is used
    // and stays.
    if (def && (def.use
        || (typeof def.heal === 'number' && def.heal > 0)
        || (def.light && typeof def.light === 'object')
        || (typeof def.spell === 'string' && def.spell))) {
      var use = document.createElement('button');
      use.type = 'button';
      use.className = 'cta';
      use.textContent = def.use || 'Use';
      use.dataset.item = id;
      use.dataset.action = 'use';
      use.setAttribute('aria-label',
        (def.use || 'Use') + ' ' + itemName(id));
      use.addEventListener('click', function () { useItem(id); });
      row.appendChild(use);
    }
    list.appendChild(row);
  });
  if (count) {
    count.textContent = ids.length
      + (ids.length === 1 ? ' thing carried.' : ' things carried.');
  }
  renderGold();
}

