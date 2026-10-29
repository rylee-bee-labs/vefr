// ---- the Trade panel: sell and buy at a shopkeeper ----
// A shop is one speaker per region, baked as window.VEFR_SHOPS =
// {region: key}. Walking beside that speaker and pressing Interact
// opens this dialog. Prices are the pack's own `value`s: selling takes
// one copy from the bag, buying adds one. Nothing is random, timed, or
// model-written - a trade is arithmetic on the pack's own numbers.
var TRADE_KEY = '';
var TRADE_OPENER = null;

// The shop key of a region, if any.
function shopKeyHere(region) {
  return (window.VEFR_SHOPS || {})[region || ''] || '';
}
// A thing's price, or 0 when the pack gives it none.
function itemValue(def) {
  return (def && typeof def.value === 'number' && def.value > 0)
    ? Math.floor(def.value) : 0;
}
// The shopkeeper's own spec (ADR 0021): its `stock` and `markup`, baked on
// the speaker only when the pack names them. Null for a shop that names none.
function tradeSpec() {
  var groups = window.VEFR_SPEAKERS || {};
  for (var region in groups) {
    if (groups[region] && groups[region][TRADE_KEY]) return groups[region][TRADE_KEY];
  }
  return null;
}
// What the hero pays: the value marked up by the shop's `markup` percent,
// rounded up so a sale never pays back what a purchase cost. A shop with no
// markup asks the value, as it always did.
function buyPrice(def) {
  var value = itemValue(def);
  var spec = tradeSpec();
  var markup = (spec && typeof spec.markup === 'number' && spec.markup >= 100) ? spec.markup : 100;
  return value ? Math.ceil(value * markup / 100) : 0;
}
// A story flag, from the rules or the descent: what a stock entry waits on.
function tradeFlagSet(flag) {
  var state = (typeof rulesStateNow === 'function') ? rulesStateNow() : null;
  if (state && state.flags && state.flags[flag] === true) return true;
  var D = window.VEFR_DESCENT;
  return !!(D && typeof D.storyFlags === 'function' && D.storyFlags(flag));
}
// What this shop sells: its `stock` - each entry that names no flag, or
// whose flag is set - in the pack's order; or, for a shop with no stock,
// every priced thing in the catalog, as before.
function tradeStock() {
  var cat = itemCatalog();
  var spec = tradeSpec();
  if (spec && Array.isArray(spec.stock)) {
    var out = [];
    spec.stock.forEach(function (entry) {
      if (!entry || !cat[entry.item] || !itemValue(cat[entry.item])) return;
      if (entry.flag && !tradeFlagSet(entry.flag)) return;
      if (out.indexOf(entry.item) < 0) out.push(entry.item);
    });
    return out;
  }
  return Object.keys(cat).filter(function (id) { return !!itemValue(cat[id]); });
}
function tradeSay(msg) {
  var el = document.getElementById('trade-live');
  if (el) el.textContent = msg || '';
}
// One trade row: art, name, price, then the verb button. Shared by the
// sell and buy lists so they read as one panel.
function tradeRow(id, price, action, label, disabled, onGo) {
  var row = document.createElement('div');
  row.className = 'trade-row';
  var src = itemSpriteSrc(id);
  if (src) {
    var im = document.createElement('img');
    im.src = src; im.alt = ''; im.className = 'bag-row-art';
    row.appendChild(im);
  }
  var name = document.createElement('span');
  name.className = 'trade-name';
  name.textContent = label || itemName(id);
  row.appendChild(name);
  var p = document.createElement('span');
  p.className = 'trade-price';
  p.textContent = price + ' gold';
  row.appendChild(p);
  var b = document.createElement('button');
  b.type = 'button';
  b.className = 'cta';
  b.textContent = action;
  b.dataset.item = id;
  b.dataset.action = action.toLowerCase();
  b.disabled = !!disabled;
  b.setAttribute('aria-label',
    action + ' ' + itemName(id) + ' for ' + price + ' gold');
  b.addEventListener('click', onGo);
  row.appendChild(b);
  return row;
}
// After a trade the clicked button is rebuilt, so put focus back on the
// same action (or on Close when it is gone or now disabled).
function settleTradeFocus(action, id) {
  var b = document.querySelector(
    '#trade [data-action="' + action + '"][data-item="' + id + '"]');
  if (!b || b.disabled) b = document.getElementById('trade-close');
  if (b) b.focus();
}
function sellItem(id) {
  var price = itemValue(itemCatalog()[id]);
  if (!price) return false;
  if (!bagRemoveOne(id)) return false;
  addGold(price);
  fireRule('sells', { what: id });
  tradeSay('You sell ' + itemName(id) + ' for ' + price + ' gold.');
  renderTrade();
  settleTradeFocus('sell', id);
  return true;
}
function buyItem(id) {
  if (tradeStock().indexOf(id) < 0) return false;
  var price = buyPrice(itemCatalog()[id]);
  if (!price || heroGold() < price) return false;
  // A full bag refuses the purchase before any gold changes hands, and
  // says so in the floor pickup's own words (bag capacity, ADR 0017).
  if (!bagAdd(id)) {
    tradeSay('Your bag is full.');
    return false;
  }
  addGold(-price);
  // Buying is acquiring: the same `picks-up` a floor drop fires,
  // plus the fact that it was bought.
  fireRule('picks-up', { what: id });
  fireRule('buys', { what: id });
  tradeSay('You buy ' + itemName(id) + ' for ' + price + ' gold.');
  renderTrade();
  settleTradeFocus('buy', id);
  return true;
}
// Draw both lists from the pack's numbers and the hero's purse.
function renderTrade() {
  var trade = document.getElementById('trade');
  if (!trade || trade.hidden) return;
  var goldEl = document.getElementById('trade-gold');
  if (goldEl) goldEl.textContent = 'You carry ' + heroGold() + ' gold.';
  var sell = document.getElementById('trade-sell');
  if (sell) {
    sell.textContent = '';
    var seen = {}, group = [];
    bagItems().forEach(function (id) {
      if (!itemValue(itemCatalog()[id])) return;
      if (seen[id]) { seen[id].n += 1; return; }
      seen[id] = { id: id, n: 1 };
      group.push(seen[id]);
    });
    if (!group.length) {
      var p = document.createElement('p');
      p.className = 'status';
      p.textContent = 'Nothing here they will buy.';
      sell.appendChild(p);
    } else {
      group.forEach(function (g) {
        var label = itemName(g.id) + (g.n > 1 ? ' x' + g.n : '');
        sell.appendChild(tradeRow(g.id, itemValue(itemCatalog()[g.id]),
          'Sell', label, false, function () { sellItem(g.id); }));
      });
    }
  }
  var buy = document.getElementById('trade-buy');
  if (buy) {
    buy.textContent = '';
    var cat = itemCatalog(), any = false, gold = heroGold();
    tradeStock().forEach(function (id) {
      var price = buyPrice(cat[id]);
      if (!price) return;
      any = true;
      buy.appendChild(tradeRow(id, price, 'Buy', '', gold < price,
        function () { buyItem(id); }));
    });
    if (!any) {
      var q = document.createElement('p');
      q.className = 'status';
      q.textContent = 'Nothing for sale.';
      buy.appendChild(q);
    }
  }
}
function openTrade(key, name, opener) {
  var trade = document.getElementById('trade');
  if (!trade) return;
  TRADE_KEY = key || '';
  TRADE_OPENER = opener || document.activeElement || null;
  var title = document.getElementById('trade-title');
  if (title) title.textContent = name || key || 'A trader';
  tradeSay('');
  trade.hidden = false;
  renderTrade();
  trade.focus();
}
function closeTrade() {
  var trade = document.getElementById('trade');
  if (!trade || trade.hidden) return;
  trade.hidden = true;
  TRADE_KEY = '';
  var back = TRADE_OPENER;
  TRADE_OPENER = null;
  if (back && back.focus) back.focus();
}

