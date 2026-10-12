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
  var price = itemValue(itemCatalog()[id]);
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
    Object.keys(cat).forEach(function (id) {
      var price = itemValue(cat[id]);
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

