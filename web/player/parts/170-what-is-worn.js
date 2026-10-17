// ---- what is worn: the equipment state ----
// The five slots Rylee fixed. The panel shows them in this order, and
// the engine refuses any slot not in this list.
var EQUIP_SLOTS = ['hand', 'body', 'head', 'feet', 'charm'];
// Per-world saved state: `{slot: itemId}`. Lives alongside the bag and
// the purse, and is read and written through the store helper like
// them, because a sandboxed iframe can make browser storage throw.
var EQUIP_KEY = 'vefr-equipped-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
// Filled in by `loadEquipped` at boot; a worn id the catalog no longer
// has is dropped on load, never a crash.
var EQUIP_STATE = {};
function loadEquipped() {
  var raw = store.getJSON(EQUIP_KEY, null);
  var engine = window.VEFR_EQUIP_ENGINE;
  if (!engine) { EQUIP_STATE = {}; return; }
  // A stored value that is not a usable object reads as nothing worn.
  if (!(raw && typeof raw === 'object' && !Array.isArray(raw))) raw = null;
  EQUIP_STATE = engine.clean(raw, itemCatalog());
  saveEquipped(EQUIP_STATE);
  // A worn id cannot also sit in the bag: if a stale save has both,
  // the bag copy is dropped so the invariant holds.
  var worn = {};
  Object.keys(EQUIP_STATE).forEach(function (s) {
    if (typeof EQUIP_STATE[s] === 'string') worn[EQUIP_STATE[s]] = true;
  });
  if (Object.keys(worn).length) {
    var bag = bagItems().filter(function (id) { return !worn[id]; });
    store.setJSON(BAG_KEY, bag);
  }
  // A worn thing that grants a verb keeps granting it: the verb row is
  // drawn from what is carried AND what is worn, and this is the first
  // moment the worn map is the whole truth.
  renderVerbRow();
}
function saveEquipped(st) {
  store.setJSON(EQUIP_KEY, st || {});
}
// True when an id is currently worn in any slot. Used to keep a worn
// thing out of the bag list, the strip, and the Use button.
function isWorn(id) {
  for (var i = 0; i < EQUIP_SLOTS.length; i++) {
    if (EQUIP_STATE[EQUIP_SLOTS[i]] === id) return true;
  }
  return false;
}
// The stat contribution of what is worn. A missing engine reads as no
// contribution, so a pack without the engine still plays unchanged.
function equipStats() {
  var engine = window.VEFR_EQUIP_ENGINE;
  if (!engine) return { hp: 0, atk: 0 };
  return engine.statsFor({ hp: 0, atk: 0 }, itemCatalog(), EQUIP_STATE);
}

