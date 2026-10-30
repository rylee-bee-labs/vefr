// ---- touch controls: a floating joystick, one smart button, Bag, Listen, Explore, B and two quick slots ----
// On a coarse pointer this layer replaces the Acts row. Every action goes through
// the code the keys already use: move(), doInteract(), useItem(), openBag(), the
// Acts row's own Listen and Explore buttons (Q and O press the same), and the
// panel closers. The D-pad stays for those who choose it in Display.
// The button a player presses is Listen (#470); its element ids stay
// `whisper`, which is the engine's own game-name-neutral name for the feature.
//
// The move control is a stored preference, and one gallery origin serves every
// build of a game: they all share that origin's saved storage, so a value an
// older build wrote is still here when a newer build opens. A D-pad picked in
// an old build therefore used to pin the arrow pad on every later build, for a
// player who had only ever wanted the floating joystick (issue: the phone
// showed a busy arrow D-pad and several controls). So the value carries a
// marker beside it: the marker says the choice was made in this layer, and a
// stored value without it is a legacy leftover that falls back to the joystick.
window.__vefrTouch = { log: [] };

var TOUCH_MOVE_KEY = 'vefr-touch-move';
// The marker, and the version of this layer that writes it. A marker that is
// missing or older is not a choice made here.
var TOUCH_MOVE_SET_KEY = 'vefr-touch-move-set';
var TOUCH_MOVE_SET_VERSION = '2';
var TOUCH_SIZE_KEY = 'vefr-touch-size';
var TOUCH_LEFT_KEY = 'vefr-touch-left';
var TOUCH_DEAD_ZONE = 14;
var TOUCH_HYSTERESIS = 1.4;
var TOUCH_RING_RADIUS = 60;
var TOUCH_KNOB_SIZE = 52;
var TOUCH_STEP_MS = 200;
var TOUCH_MIN_GAP_MS = 120;
var TOUCH_ACTION_LOCKOUT_MS = 300;
var TOUCH_PANEL_IDS = ['menu', 'reader', 'trade', 'identify', 'act-end', 'npc-box', 'gen-card'];
var TOUCH_DIRS = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };

var touchApi = null;
var touchJoy = { id: null, ox: 0, oy: 0, scale: 1, dir: null, lastStepAt: -Infinity, timer: null, suppressed: false };
var touchLastAct = -Infinity;

function touchRecord(kind, key, dir, extra) {
  var entry = { t: performance.now(), kind: kind, key: key, dir: dir };
  if (extra) {
    for (var k in extra) entry[k] = extra[k];
  }
  window.__vefrTouch.log.push(entry);
}

function touchMoveMode() {
  if (store.get(TOUCH_MOVE_KEY) !== 'dpad') return 'joystick';
  if (store.get(TOUCH_MOVE_SET_KEY) !== TOUCH_MOVE_SET_VERSION) return 'joystick';
  return 'dpad';
}

// Boot: a D-pad value with no marker of this layer is a legacy leftover from
// another build on the same gallery origin. Put the joystick back and write
// the marker, so the stale state cannot come back.
function migrateTouchMovePref() {
  if (store.get(TOUCH_MOVE_KEY) !== 'dpad') return;
  if (store.get(TOUCH_MOVE_SET_KEY) === TOUCH_MOVE_SET_VERSION) return;
  store.set(TOUCH_MOVE_KEY, 'joystick');
  store.set(TOUCH_MOVE_SET_KEY, TOUCH_MOVE_SET_VERSION);
}

function touchSizePct() {
  var n = parseInt(store.get(TOUCH_SIZE_KEY), 10);
  return n >= 75 && n <= 150 ? n : 100;
}

function touchLeft() {
  return store.get(TOUCH_LEFT_KEY) === '1';
}

function applyTouchPrefs() {
  document.body.classList.toggle('touch-dpad', touchMoveMode() === 'dpad');
  document.body.classList.toggle('touch-left', touchLeft());
  document.body.style.setProperty('--touch-scale', (touchSizePct() / 100).toFixed(2));
}

function wireTouchSettings() {
  var moveInputs = document.querySelectorAll('input[name="touch-move"]');
  for (var i = 0; i < moveInputs.length; i++) {
    var input = moveInputs[i];
    input.checked = input.value === touchMoveMode();
    input.addEventListener('change', function () {
      store.set(TOUCH_MOVE_KEY, this.value);
      // The marker goes with it: this choice was made in this layer.
      store.set(TOUCH_MOVE_SET_KEY, TOUCH_MOVE_SET_VERSION);
      applyTouchPrefs();
    });
  }
  var size = document.getElementById('touch-size');
  var sizeOut = document.getElementById('touch-size-out');
  size.value = touchSizePct();
  sizeOut.textContent = size.value + '%';
  size.addEventListener('input', function () {
    store.set(TOUCH_SIZE_KEY, size.value);
    sizeOut.textContent = size.value + '%';
    applyTouchPrefs();
  });
  var left = document.getElementById('touch-left');
  left.checked = touchLeft();
  left.addEventListener('change', function () {
    store.set(TOUCH_LEFT_KEY, left.checked ? '1' : '0');
    applyTouchPrefs();
  });
}

function touchShown(id) {
  var el = document.getElementById(id);
  return !!el && !el.hidden;
}

function touchPanelOpen() {
  for (var i = 0; i < TOUCH_PANEL_IDS.length; i++) {
    if (touchShown(TOUCH_PANEL_IDS[i])) return true;
  }
  return false;
}

function touchStopExplore() {
  if (touchApi.exploring()) touchApi.exploreStop('Stopped.');
}

function touchPickDir(dx, dy, current) {
  if (Math.sqrt(dx * dx + dy * dy) < TOUCH_DEAD_ZONE) return null;
  var ax = Math.abs(dx);
  var ay = Math.abs(dy);
  var horizontal;
  if (current === 'left' || current === 'right') {
    horizontal = !(ay > ax * TOUCH_HYSTERESIS);
  } else if (current === 'up' || current === 'down') {
    horizontal = ax > ay * TOUCH_HYSTERESIS;
  } else {
    horizontal = ax >= ay;
  }
  if (horizontal) return dx < 0 ? 'left' : 'right';
  return dy < 0 ? 'up' : 'down';
}

var touchBase = document.getElementById('touch-base');
var touchKnob = document.getElementById('touch-knob');
var touchHint = document.getElementById('touch-hint');

function touchPlaceRing(x, y) {
  var r = TOUCH_RING_RADIUS * touchJoy.scale;
  touchBase.style.left = (x - r) + 'px';
  touchBase.style.top = (y - r) + 'px';
  touchBase.hidden = false;
  touchKnob.hidden = false;
  touchHint.hidden = true;
  touchMoveKnob(0, 0);
}

function touchHideRing() {
  touchBase.hidden = true;
  touchKnob.hidden = true;
  touchHint.hidden = false;
}

function touchMoveKnob(dx, dy) {
  var r = TOUCH_RING_RADIUS * touchJoy.scale;
  var d = Math.sqrt(dx * dx + dy * dy);
  var k = d > r ? r / d : 1;
  var half = (TOUCH_KNOB_SIZE / 2) * touchJoy.scale;
  touchKnob.style.left = (touchJoy.ox + dx * k - half) + 'px';
  touchKnob.style.top = (touchJoy.oy + dy * k - half) + 'px';
}

function touchArm(ms) {
  clearTimeout(touchJoy.timer);
  touchJoy.timer = setTimeout(touchTick, ms);
}

function touchDisarm() {
  clearTimeout(touchJoy.timer);
  touchJoy.timer = null;
}

function touchStep() {
  touchJoy.lastStepAt = performance.now();
  touchRecord('step', null, touchJoy.dir);
  touchStopExplore();
  var v = TOUCH_DIRS[touchJoy.dir];
  touchApi.move(v[0], v[1]);
}

function touchStopHold(reason) {
  touchDisarm();
  if (touchJoy.dir !== null) {
    touchRecord('stop', null, touchJoy.dir, { reason: reason });
    touchJoy.dir = null;
  }
}

function touchSuppress(reason) {
  if (touchJoy.suppressed) return;
  touchStopHold(reason);
  touchJoy.suppressed = true;
  touchHideRing();
  touchRecord('blocked', 'joystick', null, { reason: reason });
}

function touchTick() {
  touchJoy.timer = null;
  if (touchJoy.id === null || touchJoy.suppressed || touchJoy.dir === null) return;
  if (touchPanelOpen()) {
    touchSuppress('panel');
    return;
  }
  touchStep();
  touchArm(TOUCH_STEP_MS);
}

function touchSetDirection(next) {
  if (next === touchJoy.dir) return;
  if (next === null) {
    touchStopHold('center');
    return;
  }
  var acquired = touchJoy.dir === null;
  touchJoy.dir = next;
  if (acquired) {
    touchStep();
    touchArm(TOUCH_STEP_MS);
    return;
  }
  var wait = touchJoy.lastStepAt + TOUCH_MIN_GAP_MS - performance.now();
  if (wait > 0) {
    touchArm(wait);
  } else {
    touchStep();
    touchArm(TOUCH_STEP_MS);
  }
}

function touchDown(ev) {
  if (touchJoy.id !== null || touchPanelOpen()) return;
  ev.preventDefault();
  touchJoy.id = ev.pointerId;
  touchJoy.ox = ev.clientX;
  touchJoy.oy = ev.clientY;
  touchJoy.scale = touchSizePct() / 100;
  touchJoy.dir = null;
  touchJoy.suppressed = false;
  touchPlaceRing(ev.clientX, ev.clientY);
}

function touchMovePointer(ev) {
  if (ev.pointerId !== touchJoy.id || touchJoy.suppressed) return;
  if (touchPanelOpen()) {
    touchSuppress('panel');
    return;
  }
  var dx = ev.clientX - touchJoy.ox;
  var dy = ev.clientY - touchJoy.oy;
  touchMoveKnob(dx, dy);
  touchSetDirection(touchPickDir(dx, dy, touchJoy.dir));
}

function touchUpPointer(ev) {
  if (ev.pointerId !== touchJoy.id) return;
  touchStopHold(ev.type === 'pointerup' ? 'release' : 'cancel');
  touchJoy.id = null;
  touchJoy.suppressed = false;
  touchHideRing();
}

function touchSyncModal() {
  var open = touchPanelOpen();
  document.body.classList.toggle('touch-modal', open);
  if (open && touchJoy.id !== null) touchSuppress('panel');
}

function touchSyncSmart() {
  var src = document.getElementById('interact');
  var smart = document.getElementById('touch-smart');
  var text = ((document.getElementById('interact-label') || src).textContent || '').replace(/\s+/g, ' ').trim();
  var go = /^Go (down|up|through)\b/.exec(text);
  var cut = go ? go[0].length : text.indexOf(' ');
  var verb = (cut < 0 ? text : text.slice(0, cut)) || 'Interact';
  var caption = cut < 0 ? '' : text.slice(cut).trim();
  smart.querySelector('.verb').textContent = verb;
  smart.querySelector('.cap').textContent = caption;
  smart.classList.toggle('gbtn--dim', src.classList.contains('gbtn--dim'));
  smart.setAttribute('aria-label', text || 'Interact');
}

function touchSmartPress() {
  var now = performance.now();
  if (now - touchLastAct < TOUCH_ACTION_LOCKOUT_MS) {
    touchRecord('blocked', 'interact', null, { reason: 'lockout' });
    return;
  }
  touchLastAct = now;
  touchStopExplore();
  touchRecord('action', 'interact', null);
  touchApi.act();
}

function touchBagPress() {
  touchStopExplore();
  touchRecord('action', 'bag', null);
  if (window.openBag) window.openBag();
}

// Listen and Explore press the Acts row's own buttons, hidden on a phone but still
// wired, so a tap does exactly what Q and O do (issue #431).
function touchWhisperPress() {
  touchStopExplore();
  touchRecord('action', 'whisper', null);
  document.getElementById('whisper').click();
}

function touchExplorePress() {
  touchRecord('action', 'explore', null);
  document.getElementById('explore').click();
}

// Explore's pressed state and Listen's wait while it listens show on the touch twins.
function touchSyncTools() {
  var ex = document.getElementById('explore');
  var wh = document.getElementById('whisper');
  document.getElementById('touch-explore').setAttribute('aria-pressed', ex.getAttribute('aria-pressed') === 'true' ? 'true' : 'false');
  document.getElementById('touch-whisper').disabled = wh.disabled;
}

function touchClosePress() {
  touchRecord('action', 'b', null);
  if (touchShown('act-end')) closeActEnd();
  else if (touchShown('reader')) closeReader();
  else if (touchShown('trade')) closeTrade();
  else if (touchShown('identify')) closeIdentify();
  else if (touchShown('menu')) {
    if (touchShown('startover-body')) window.cancelStartover();
    else window.closeMenu();
  } else if (touchShown('npc-box')) document.getElementById('npc-close').click();
}

function quickItemIds() {
  var cat = itemCatalog();
  return bagCarried().filter(function (c) {
    return !isWorn(c.id) && itemUsable(cat[c.id]);
  }).slice(0, 2).map(function (c) { return c.id; });
}

function renderQuickslots() {
  var box = document.getElementById('touch-quick');
  if (!box) return;
  if (hotbarOn()) { renderHotbar(box); return; }
  var ids = quickItemIds();
  box.textContent = '';
  box.hidden = !ids.length;
  ids.forEach(function (id) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'touch-btn touch-quick-btn';
    b.dataset.item = id;
    b.setAttribute('aria-label', (itemCatalog()[id].use || 'Use') + ' ' + itemName(id));
    var src = itemSpriteSrc(id);
    if (src) {
      var im = document.createElement('img');
      im.src = src;
      im.alt = '';
      b.appendChild(im);
    } else {
      b.textContent = itemName(id).charAt(0).toUpperCase();
    }
    box.appendChild(b);
  });
}

// The quick bar (ADR 0023, `display.hotbar`): the same box, on every screen
// rather than a touch one alone, holding up to four things - each kind of a
// thing used in one tap, with how many are carried, then the spells known,
// with what each costs - and each button printing the key that presses it.
// A spell the hero cannot pay for is still a button (a press says why), and
// says so in its name; the eye gets the same answer, dimmed.
// A spell's face, drawn in a line so no art file is needed: a bolt for one
// that harms, a shield for a ward, a heart for a heal.
function hotbarIcon(spell) {
  var path = (rpgWhole(spell.harm) && spell.harm > 0) ? '<path d="M17 4l-7 12h6l-2 12 9-15h-6z"/>'
    : (spell.ward && typeof spell.ward === 'object') ? '<path d="M16 5l9 3v7c0 6-4 10-9 12-5-2-9-6-9-12V8z"/>'
    : (typeof spell.heal === 'number' && spell.heal > 0)
      ? '<path d="M16 26s-10-6-10-13a5 5 0 0 1 10-2 5 5 0 0 1 10 2c0 7-10 13-10 13z"/>'
      : '<circle cx="16" cy="16" r="8"/>';
  return '<svg class="hot-icon" viewBox="0 0 32 32" aria-hidden="true" focusable="false">' + path + '</svg>';
}
// The first letter of a name, past the article a pack writes ("a cloudy
// potion" is C): the face of a thing that has no picture.
function hotbarLetter(name) {
  var bare = String(name || '').replace(/^(a|an|the|some)\s+/i, '');
  return (bare.charAt(0) || '?').toUpperCase();
}
function renderHotbar(box) {
  var things = hotbarThings();
  box.textContent = '';
  box.classList.add('hotbar');
  box.setAttribute('aria-label', 'Quick bar');
  box.hidden = !things.length;
  things.forEach(function (t, i) {
    var keys = keybindKeys('quick' + (i + 1));
    var keyName = keys.length ? keybindKeyName(keys[0]) : '';
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'touch-btn touch-quick-btn hot-btn';
    b.dataset.slot = String(i);
    var words, badge = '';
    if (t.kind === 'item') {
      var def = itemCatalog()[t.id];
      b.dataset.item = t.id;
      words = (def.use || 'Use') + ' ' + itemName(t.id) + (t.count > 1 ? ', ' + t.count + ' carried' : '');
      badge = t.count > 1 ? String(t.count) : '';
      var src = itemSpriteSrc(t.id);
      if (src) {
        var im = document.createElement('img');
        im.src = src;
        im.alt = '';
        b.appendChild(im);
      } else {
        b.appendChild(document.createTextNode(hotbarLetter(itemName(t.id))));
      }
    } else {
      var spell = t.spell;
      var cost = (rpgManaOn() && rpgWhole(spell.mana)) ? spell.mana : 0;
      b.dataset.spell = t.id;
      words = 'Cast ' + (spell.name || t.id) + (cost ? ', ' + cost + ' mana' : '');
      if (cost > HERO_MP) {
        b.setAttribute('aria-disabled', 'true');
        words += ', not enough mana';
      }
      badge = cost ? String(cost) : '';
      b.insertAdjacentHTML('beforeend', hotbarIcon(spell));
      b.classList.add('hot-btn--spell');
    }
    if (badge) {
      var n = document.createElement('span');
      n.className = t.kind === 'item' ? 'bag-pip-count hot-count' : 'hot-cost';
      n.setAttribute('aria-hidden', 'true');
      n.textContent = badge;
      b.appendChild(n);
    }
    if (keyName) {
      var k = document.createElement('kbd');
      k.className = 'hot-key';
      k.setAttribute('aria-hidden', 'true');
      k.textContent = keyName;
      b.appendChild(k);
      b.setAttribute('aria-keyshortcuts', keys[0]);
    }
    b.setAttribute('aria-label', words + (keyName ? ' (key ' + keyName + ')' : ''));
    b.title = words + (keyName ? ' (' + keyName + ')' : '');
    box.appendChild(b);
  });
}

function touchQuickPress(e) {
  var slot = e.target.closest('button[data-slot]');
  if (slot && hotbarOn()) {
    touchStopExplore();
    touchRecord('action', 'quick', null, { slot: Number(slot.dataset.slot) });
    hotbarPress(Number(slot.dataset.slot));
    return;
  }
  var b = e.target.closest('button[data-item]');
  if (!b) return;
  touchStopExplore();
  touchRecord('action', 'quick', null, { item: b.dataset.item });
  useItem(b.dataset.item);
}

function setupTouchControls(api) {
  touchApi = api;
}

// A drag on the play area never moves the page (touch-action: none in the
// stylesheet is the first guard; some phone browsers still rubber-band or
// pull to refresh past it). A panel's own scrolling is left alone.
function touchHoldPage(e) {
  if (!document.body.classList.contains('in-game')) return;
  if (e.target.closest && e.target.closest('[role="dialog"], .reader-card')) return;
  if (e.cancelable) e.preventDefault();
}
document.getElementById('play').addEventListener('touchmove', touchHoldPage, { passive: false });

var touchZone = document.getElementById('touch-zone');
touchZone.addEventListener('pointerdown', touchDown);
window.addEventListener('pointermove', touchMovePointer);
window.addEventListener('pointerup', touchUpPointer);
window.addEventListener('pointercancel', touchUpPointer);

document.addEventListener('pointerdown', function (e) {
  var b = e.target.closest && e.target.closest('.touch-btn');
  if (b) b.classList.add('is-down');
});
function touchClearDown() {
  var down = document.querySelectorAll('.touch-btn.is-down');
  for (var i = 0; i < down.length; i++) down[i].classList.remove('is-down');
}
window.addEventListener('pointerup', touchClearDown);
window.addEventListener('pointercancel', touchClearDown);

document.getElementById('touch-smart').addEventListener('click', touchSmartPress);
document.getElementById('touch-bag').addEventListener('click', touchBagPress);
document.getElementById('touch-b').addEventListener('click', touchClosePress);
document.getElementById('touch-quick').addEventListener('click', touchQuickPress);
document.getElementById('touch-whisper').addEventListener('click', touchWhisperPress);
document.getElementById('touch-explore').addEventListener('click', touchExplorePress);

new MutationObserver(touchSyncSmart).observe(document.getElementById('interact'), {
  subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class']
});
var touchToolWatch = new MutationObserver(touchSyncTools);
touchToolWatch.observe(document.getElementById('explore'), { attributes: true, attributeFilter: ['aria-pressed'] });
touchToolWatch.observe(document.getElementById('whisper'), { attributes: true, attributeFilter: ['disabled'] });
var touchPanelWatch = new MutationObserver(touchSyncModal);
TOUCH_PANEL_IDS.forEach(function (id) {
  touchPanelWatch.observe(document.getElementById(id), { attributes: true, attributeFilter: ['hidden'] });
});

migrateTouchMovePref();
wireTouchSettings();
applyTouchPrefs();
touchSyncSmart();
touchSyncTools();
touchSyncModal();
renderQuickslots();
