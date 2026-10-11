// ---- the identify service: a thing read once, in town ----
// A pack names the place a thing is read at the way it already names a
// shop: one speaker of a region carries `"identify": "true"` (also
// `yes`/`1`), read here off `window.VEFR_WORLD` - the world the weave
// already inlines, so a pack that names no service bakes no extra line
// and plays exactly the player it did. Standing beside that speaker and
// pressing Interact opens this dialog, which lists what the hero carries
// that has not been read yet; reading one sets `identified` on THAT
// instance in the saved bag and nothing else, and the traits are in the
// bag's own words from that moment on - in the strip, in the panel, and
// in the strip's aria-label a screen reader reads.
//
// Nothing here decides what a trait MEANS and nothing here writes a word
// about it: the rarity and the traits were drawn once, at the drop, from
// a named seeded stream (`delve.item_draw` and its JavaScript twin).
// This only reads them back. So there is no draw here, no model call,
// no clock and no animation - which is why with motion off the words are
// in the page the instant the button is pressed, in the same pass, in
// text rather than behind a picture.
var IDENTIFY_KEY = '';
var IDENTIFY_OPENER = null;

// The pack's own true words, the three a shopkeeper may also use. A
// blank or false flag is silence, and a pack that was refused for naming
// something else is silence here too - `vefr check` is what says so.
function identifies(spec) {
  if (!spec || typeof spec !== 'object') return false;
  if (spec.identify === true) return true;
  return /^(true|yes|1)$/i.test(String(spec.identify).trim());
}

// The identify speaker of a region, if the pack names one: the region's
// own speakers, out of the baked grouping, and the flag off the pack's
// own spec for that key. First one named wins, as the shopkeeper does.
function identifyKeyHere(region) {
  var grouped = (window.VEFR_SPEAKERS || {})[region || ''] || {};
  var all = (window.VEFR_WORLD && window.VEFR_WORLD.speakers) || {};
  var keys = Object.keys(grouped);
  for (var i = 0; i < keys.length; i++) {
    if (identifies(all[keys[i]] || grouped[keys[i]])) return keys[i];
  }
  return '';
}

// What is still unread: an instance record (ADR 0017) that has not been
// read and has something hidden in it. A bare id carries nothing hidden,
// so there is nothing to read and nothing is offered; a worn thing is not
// in the bag list either, so it is not offered here.
function bagUnread() {
  return bagCarried().filter(function (c) {
    return !c.identified && c.traits.length > 0 && !isWorn(c.id);
  });
}

// Read one carried thing: set `identified` on the first unread instance
// of that id in the saved bag and write the bag back. The rarity and the
// traits are NOT touched - they were drawn once, at the drop - so
// reading the same instance twice gives the same words twice, and the
// record that loads next run is this one, never a re-draw. Returns the
// instance as it now reads, or false when there was nothing to read.
function bagIdentifyOne(id) {
  var raw = store.getJSON(BAG_KEY, []);
  if (!Array.isArray(raw)) return false;
  var cat = itemCatalog();
  var at = -1;
  for (var i = 0; i < raw.length; i++) {
    var entry = raw[i];
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue;
    if (entry.id !== id || !cat[id] || entry.identified === true) continue;
    at = i;
    break;
  }
  if (at === -1) return false;
  raw[at].identified = true;
  store.setJSON(BAG_KEY, raw);
  // Both bag surfaces redraw in this same call, so the traits are in the
  // DOM on the first frame after the click - nothing waits a tick for it.
  renderBagPanel();
  renderBagStrip();
  syncCombat();
  // This instance and no other: two copies of one id can have been drawn
  // differently, and the line the panel says must name the one just read.
  return {
    id: id,
    rarity: typeof raw[at].rarity === 'string' ? raw[at].rarity : '',
    traits: Array.isArray(raw[at].traits)
      ? raw[at].traits.filter(function (t) { return typeof t === 'string'; })
      : [],
    identified: true,
  };
}

// The dialog's own line of words (kept in the panel, as the bag's is).
function identifySay(msg) {
  var el = document.getElementById('identify-live');
  if (el) el.textContent = msg || '';
}

// One row per unread thing: art, the thing and its rarity (what is known
// of it so far), and the verb. One read at a time, and the row is gone
// from this list the moment it is read.
function renderIdentify() {
  var panel = document.getElementById('identify');
  if (!panel || panel.hidden) return;
  var list = document.getElementById('identify-list');
  if (!list) return;
  list.textContent = '';
  var unread = bagUnread();
  if (!unread.length) {
    var p = document.createElement('p');
    p.className = 'empty';
    p.textContent = 'Nothing here is waiting to be read.';
    list.appendChild(p);
    return;
  }
  unread.forEach(function (carried) {
    var row = document.createElement('div');
    row.className = 'trade-row';
    var src = itemSpriteSrc(carried.id);
    if (src) {
      var im = document.createElement('img');
      im.src = src; im.alt = ''; im.className = 'bag-row-art';
      row.appendChild(im);
    }
    var name = document.createElement('span');
    name.className = 'trade-name';
    name.textContent = carriedName(carried);
    row.appendChild(name);
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'cta';
    b.textContent = 'Read';
    b.dataset.item = carried.id;
    b.dataset.action = 'read';
    b.setAttribute('aria-label', 'Read ' + carriedName(carried));
    b.addEventListener('click', function () { identifyThing(carried.id); });
    row.appendChild(b);
    list.appendChild(row);
  });
}

// Read a thing and say what it turned out to be, in the same words the
// bag now uses. A refused read (already read, or gone from the bag)
// changes nothing and says nothing.
function identifyThing(id) {
  var read = bagIdentifyOne(id);
  if (!read) return false;
  identifySay('You read ' + carriedName(read) + '.');
  renderIdentify();
  return true;
}

function openIdentify(key, name, opener) {
  var panel = document.getElementById('identify');
  if (!panel) return;
  IDENTIFY_KEY = key || '';
  IDENTIFY_OPENER = opener || document.activeElement || null;
  var title = document.getElementById('identify-title');
  if (title) title.textContent = name || key || 'Someone who reads things';
  identifySay('');
  panel.hidden = false;
  renderIdentify();
  panel.focus();
}
function closeIdentify() {
  var panel = document.getElementById('identify');
  if (!panel || panel.hidden) return;
  panel.hidden = true;
  IDENTIFY_KEY = '';
  var back = IDENTIFY_OPENER;
  IDENTIFY_OPENER = null;
  if (back && back.focus) back.focus();
}