// ---- the skin: the player paints the pack's pictures (design/ui-skin.md) ----
// A woven game may carry window.VEFR_SKIN: one baked object whose parts
// are data URIs. When it is there, a single <style id="vefr-skin-css">
// paints the real panels, buttons, bars and cursor and body gains the
// has-skin class. No skin (null) means no element, no class, no change.
// The whole sheet sits behind a media guard, so high contrast and forced
// colours keep the plain flat player (rules 3 and 4).
//
// Every part the contract names is drawn, not the four the loader happened
// to start with: slot, tab, toggle, tooltip, speech, divider, banner, corner
// and gold-plate are painted too, each only when the skin carries it
// (docs/plans/interface/PLAN.md, slice 4).
//
// Two more optional things a skin may name, both from
// docs/plans/interface/PLAN.md: `backdrop`, the seamless picture the ground
// outside the drawn map takes (painted on the canvas, in 480, once the
// picture has decoded), and `fonts`, the display and body families the
// engine bundles. A skin with neither plays exactly as it did.
// The parts the contract names beyond the four the loader always drew
// (docs/plans/interface/PLAN.md, slice 4). A skin carrying at least one of
// them has opted into the themed interface, and the HUD marks and the speech
// portrait (slice 5) belong to that opt-in: a skin that carries none of them
// has asked for the plain panels, so it keeps the plain HUD too.
var THEMED_PARTS = ['slot', 'tab', 'toggle', 'tooltip', 'speech',
  'divider', 'banner', 'corner', 'gold-plate'];

// How big a corner stud is, in px. The player draws 6 px accent dots; a stud
// is a thing you can read as a stud, and it is decoration, so it takes no
// pointer and it never sizes a control.
var CORNER_STUD = 18;

// WCAG relative luminance and contrast for two `r, g, b` triples (0..255), and the
// floor body text has to clear. The same maths, and the same 4.5, as
// tests/test_teal_contrast.py: a face a skin's words are drawn on is only a face if
// the words can be read on it.
var BODY_FLOOR = 4.5;
function faceLuma(r, g, b) {
  var lin = function (c) {
    c = c / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function faceContrast(one, two) {
  var a = faceLuma(one[0], one[1], one[2]);
  var b = faceLuma(two[0], two[1], two[2]);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

var SKIN_FONT_STACKS = {
  'Cinzel': "'Cinzel', Georgia, 'Times New Roman', serif",
  'Atkinson Hyperlegible Next': "'Atkinson Hyperlegible Next', system-ui, -apple-system, 'Segoe UI', sans-serif",
  'Crimson Pro': "'Crimson Pro', Georgia, 'Times New Roman', serif"
};

// Whether this person asked for the plain flat style instead of a skin's
// pictures (rule 4). Read when the ground is set, and again when the
// setting changes while the game is open.
function plainStyle() {
  if (!window.matchMedia) return false;
  return !!(window.matchMedia('(prefers-contrast: more)').matches
    || window.matchMedia('(forced-colors: active)').matches);
}
// The map repaints itself on the next step, but a picture that arrives late
// should not wait for one.
function redrawGround() {
  if (typeof window.VEFR_REDRAW === 'function') window.VEFR_REDRAW();
}
// The ground the skin asks for, or none: the picture only when the person
// has not asked for the plain flat style. The map is redrawn when it lands.
function loadBackdrop(skin) {
  var url = (skin && skin.backdrop && !plainStyle()) ? skin.backdrop : null;
  window.VEFR_BACKDROP_URL = url;
  if (!url) { window.VEFR_BACKDROP = null; return; }
  var probe = new Image();
  probe.onload = function () { window.VEFR_BACKDROP = probe; redrawGround(); };
  probe.onerror = function () { window.VEFR_BACKDROP = null; };   // the flat ground stays
  probe.src = url;
}
// The setting can change while the game is open; the ground follows it.
function watchPlainStyle(skin) {
  ['(prefers-contrast: more)', '(forced-colors: active)'].forEach(function (q) {
    var mq = window.matchMedia && window.matchMedia(q);
    if (mq && mq.addEventListener) {
      mq.addEventListener('change', function () { loadBackdrop(skin); redrawGround(); });
    }
  });
}
function skinFontStack(family) {
  return (typeof family === 'string'
    && Object.prototype.hasOwnProperty.call(SKIN_FONT_STACKS, family))
    ? SKIN_FONT_STACKS[family] : null;
}

// ---- the HUD marks and the speech portrait (interface slice 5) ----
// Five small inline SVGs, one per HUD line, in currentColor so each follows
// the words it sits beside. They are decoration: aria-hidden, no alt, no words
// of their own, and the words beside them are the words a screen reader reads.
// Each sits BESIDE its line in the same HUD block and never inside it, so a
// line the world does not use today still has its mark and the words do not
// move when the line appears. The mark is a sibling, so the player's own
// `[hidden] + .hud-icon` rule hides it exactly when its line is hidden.
// A pack with no skin draws none of them and plays exactly as it did.
var HUD_MARKS = {
  heart: { at: 'hud-hp', draw: '<path d="M12 20.5S4.5 15.6 4.5 11a4.2 4.2 0 0 1 7.5-2.6A4.2 4.2 0 0 1 19.5 11c0 4.6-7.5 9.5-7.5 9.5z"/>' },
  star: { at: 'hud-level', draw: '<path d="m12 3.8 2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.6-5 2.6.9-5.6-4-3.9 5.6-.8z"/>' },
  coin: { at: 'hud-gold', draw: '<circle cx="12" cy="12" r="8"/><path d="M12 7.5v9M9.6 10h4.8M9.6 14h4.8"/>' },
  bag: { at: 'bag-strip', draw: '<path d="M8 9.5V7.4a4 4 0 0 1 8 0v2.1"/><rect x="4" y="9.5" width="16" height="11" rx="2"/>' },
  door: { at: 'menu-open', draw: '<path d="M6.5 21V4.2a.7.7 0 0 1 .7-.7h7.3v17.5z"/><path d="M6.5 21H19"/><circle cx="12.4" cy="12" r=".9"/>' },
};

function addHudMarks() {
  Object.keys(HUD_MARKS).forEach(function (name) {
    var line = document.getElementById(HUD_MARKS[name].at);
    if (!line || !line.parentNode) return;
    if (line.parentNode.querySelector('svg[data-icon="' + name + '"]')) return;
    var span = document.createElement('span');
    span.className = 'hud-mark';
    span.innerHTML = '<svg viewBox="0 0 24 24" data-icon="' + name + '"'
      + ' fill="none" stroke="currentColor" stroke-width="1.8"'
      + ' stroke-linecap="round" stroke-linejoin="round" focusable="false"'
      + ' aria-hidden="true">'
      + HUD_MARKS[name].draw + '</svg>';
    line.parentNode.insertBefore(span, line.nextSibling);
  });
}

// The speech box shows a portrait when the speaker has a picture. It is
// decoration too: the speaker's name is already real text in .speaker, so the
// picture is aria-hidden with an empty alt. A speaker the pack gave no picture
// leaves the box exactly as it was - no empty slot, no broken image, and
// nothing left over from the speaker before.
function speakerPicture(speaker) {
  if (typeof speaker !== 'string' || !speaker) return '';
  var sprites = window.VEFR_SPRITES || {};
  if (typeof sprites[speaker] === 'string') return sprites[speaker];
  // A pack names its sprites by file stem, so "The Baker" looks for
  // "the-baker" and "the_baker" as well as for the words themselves.
  var slug = speaker.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  var keys = Object.keys(sprites);
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i].toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    if (k === slug) return sprites[keys[i]];
  }
  return '';
}

// The portrait hook the speech box calls is this function, named on the window
// when the skin loads (see 100-speech-box.js). The speech box reads it when it
// shows a speaker, so the order the two parts load in does not matter.
function dressSpeechBox(speaker) {
  var box = document.getElementById('npc-box');
  if (!box) return;
  var old = box.querySelector('img.npc-face');
  if (old) box.removeChild(old);
  var src = speakerPicture(speaker);
  if (!src) return;
  var im = document.createElement('img');
  im.className = 'npc-face';
  im.src = src;
  im.alt = '';
  im.setAttribute('aria-hidden', 'true');
  box.insertBefore(im, box.firstChild);
}

// ---- the look: the skin's pictures, or the plain dark player ----
// A pack with a skin offers the player a choice in Display: its painted look,
// or the plain dark one. Where a new player starts is the pack's call
// (world.json display.look: "plain" starts dark, anything else starts painted,
// as every skinned pack always has); after that the choice is the player's
// own and is remembered. Switching is live: the skin's sheet is built once and
// only switched on and off, so nothing about the game in progress changes.
var LOOK_KEY = 'vefr-look-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
// The player's store (065-store.js) holds the pick; a page without it (the
// skin part loaded on its own) keeps the pack's look and remembers nothing.
var lookStore = (typeof store !== 'undefined') ? store : { get: function () { return null; }, set: function () {} };
function lookPainted() {
  var mine = lookStore.get(LOOK_KEY);
  if (mine === 'plain') return false;
  if (mine === 'skin') return true;
  var display = (window.VEFR_WORLD && window.VEFR_WORLD.display) || {};
  return display.look !== 'plain';
}
// What the painted look is called in Display: the skin's own title, else its
// name with the dashes read as spaces.
function lookTitle(skin) {
  var t = (skin && (skin.title || skin.name)) || 'Painted';
  t = String(t).replace(/[-_]+/g, ' ');
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function setLook(painted) {
  var style = document.getElementById('vefr-skin-css');
  if (style) style.disabled = !painted;
  document.body.classList.toggle('has-skin', painted);
  document.body.classList.toggle('look-plain', !painted);
  window.VEFR_LOOK = painted ? 'skin' : 'plain';
  redrawGround();
}
function wireLookSetting(skin) {
  var box = document.getElementById('look-settings');
  if (!box) return;
  box.hidden = false;
  var painted = document.getElementById('look-skin-label');
  if (painted) painted.textContent = lookTitle(skin);
  var inputs = box.querySelectorAll('input[name="look"]');
  Array.prototype.forEach.call(inputs, function (input) {
    input.checked = (input.value === 'skin') === lookPainted();
    input.addEventListener('change', function () {
      if (!this.checked) return;
      lookStore.set(LOOK_KEY, this.value === 'skin' ? 'skin' : 'plain');
      setLook(this.value === 'skin');
    });
  });
}

function applySkin() {
  var skin = window.VEFR_SKIN;
  if (!skin || typeof skin !== 'object') return;
  wireLookSetting(skin);
  var parts = skin.parts || {};
  var ink = skin.ink || {};
  loadBackdrop(skin);
  watchPlainStyle(skin);

  // The flat ground behind a panel's own centre: dark ink wants a light
  // ground, so the words stay readable if the picture does not cover it.
  function ground() {
    var m = /^#([0-9a-fA-F]{6})$/.exec(ink.on_panel || '');
    if (!m) return '#F4EEDD';
    var n = parseInt(m[1], 16);
    var lum = (0.2126 * ((n >> 16) & 255)
      + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
    return lum > 0.55 ? '#15181D' : '#F4EEDD';
  }
  // One border-image rule from a part's picture and slice (nine-slice).
  function nine(file, slice, noFill) {
    var s = (typeof slice === 'number' && slice > 0) ? slice : 0;
    return ' border-image: url(' + file + ') ' + s + (noFill ? '' : ' fill') + ' / ' + s
      + 'px / 0 round;';
  }
  // A picture laid across the whole of a thing, stretched to fit it: the
  // picture may be smaller than what it paints, but never larger than the
  // panel it sits on. Written as the background longhands on purpose, so it
  // layers over the ground the player (or another part) already set underneath
  // instead of wiping it - that dark base is what keeps the words readable when
  // the picture is missing or a checker cannot see images.
  function plate(file) {
    return 'background-image: url(' + file + '); background-position: center;'
      + ' background-size: 100% 100%; background-repeat: no-repeat;';
  }
  // The middle of a panel picture is a small patch (often 32 px). border-image would TILE it
  // across a wide panel and show the seams as stripes behind the text, so a panel keeps only
  // its carved border from the picture and paints its middle one flat colour taken from the
  // picture's own centre (measured in the browser; ground() is the fallback).
  //
  // The picture's middle is a NICER version of that fallback face, never a licence to paint
  // words nobody can see. Every skinned surface - the panels, the menu tabs, the HUD boxes -
  // takes this one colour as its face and the skin's own `ink.on_panel` as its words, so a
  // picture whose middle does not carry that ink leaves the fallback standing, which does.
  // Measured on a soft-wood skin wearing dark ink: 1.14:1, and every tab label, the whole
  // content panel and every HUD value box went blank while the text stayed in the DOM,
  // visible and opaque - so the accessibility checks, which ask whether the words EXIST,
  // all passed.
  function sampleGround(file, slice) {
    var im = new Image();
    im.onload = function () {
      try {
        var c = document.createElement('canvas'); c.width = 1; c.height = 1;
        var w = im.naturalWidth, h = im.naturalHeight, sl = (slice | 0) || 0;
        var sw = Math.max(1, w - 2 * sl), sh = Math.max(1, h - 2 * sl);
        var x = c.getContext('2d'); x.drawImage(im, sl, sl, sw, sh, 0, 0, 1, 1);
        var d = x.getImageData(0, 0, 1, 1).data;
        var hex = /^#([0-9a-fA-F]{6})$/.exec(ink.on_panel || '');
        if (!hex) return;                       // no declared ink, nothing to read against
        var n = parseInt(hex[1], 16);
        if (faceContrast([(n >> 16) & 255, (n >> 8) & 255, n & 255],
                         [d[0], d[1], d[2]]) < BODY_FLOOR) return;   // keep the fallback
        document.documentElement.style.setProperty('--vefr-skin-ground',
          'rgb(' + d[0] + ',' + d[1] + ',' + d[2] + ')');
      } catch (e) { /* no canvas: the fallback colour stays */ }
    };
    im.src = file;
  }

  var css = '';
  // The type, when the skin chooses it: the player's own two variables, so
  // every rule already written reaches the new family. Only a family the
  // engine bundles has a stack here, and the same list is what the
  // validator accepts (maplab.SKIN_FONTS).
  var fonts = skin.fonts || {};
  var show = skinFontStack(fonts.display), read = skinFontStack(fonts.body);
  if (show) css += ':root { --display: ' + show + '; }\n';
  if (read) css += ':root { --read: ' + read + '; }\n';
  var panel = parts.panel;
  if (panel && panel.file) {
    css += '.glass, #npc-box, #reader .reader-card, #trade .reader-card, #menu .carved {'
      + nine(panel.file, panel.slice, true)
      + ' background: var(--vefr-skin-ground, ' + ground() + ');'
      + (ink.on_panel ? ' color: ' + ink.on_panel + ';' : '') + ' }\n';
  }
  // The plain player writes light-on-dark text colours on the HEADINGS, labels and lines
  // inside its panels; on a parchment panel those vanish (measured 1.2:1). So the ink the
  // skin declares reaches every piece of text inside a skinned panel, except buttons.
  if (panel && panel.file && /^#[0-9a-fA-F]{6}$/.test(ink.on_panel || '')) {
    var inPanel = ['.glass', '#npc-box', '#reader .reader-card', '#trade .reader-card', '#menu .carved'];
    css += inPanel.map(function (q) {
      return q + ' :not(button, button *, .cta, .cta *, .gbtn, .gbtn *, kbd)';
    }).join(',\n') + ' { color: ' + ink.on_panel + ' !important; }\n';
    // the menu's tab buttons sit on the panel too (the teal accent on parchment was 3.8:1)
    css += '#menu .pm button { color: ' + ink.on_panel + ' !important; }\n';
    sampleGround(panel.file, panel.slice);
  }
  var button = parts.button;
  if (button && button.file) {
    var b = '.gbtn, .cta, .verb-row button';
    // Light text with a dark shadow reads on the carved-wood face (>= 4.5:1 measured);
    // the plain player's gold and dark button labels did not.
    // A dark wood-brown base UNDER the picture: the plain player's gold Whisper button kept its
    // gold background-color beneath the wood, so with the picture missing (or to a checker that
    // cannot see images) the light text sat on gold at 3.2:1.
    css += b + ' { color: #F6F0E2 !important; background-color: #5F5043 !important;'
      + ' text-shadow: 0 1px 1px rgba(20, 12, 4, 0.7); }\n';
    css += b + ' {' + nine(button.file, button.slice) + ' min-height: 44px; }\n';
    if (button.hover) css += b + ':hover {' + nine(button.hover, button.slice) + ' }\n';
    if (button.pressed) css += b + ':active {' + nine(button.pressed, button.slice) + ' }\n';
    if (button.disabled) css += b + ':disabled {' + nine(button.disabled, button.slice) + ' }\n';
  }
  var bar = parts.bar;
  if (bar && bar.frame) {
    css += '.hud-hp-bar { background: url(' + bar.frame + ') center / 100% 100% no-repeat; }\n';
  }
  if (bar && bar.fill) {
    css += '.hud-hp-fill { background: url(' + bar.fill + ') center / 100% 100% no-repeat; }\n';
  }
  var cursor = parts.cursor;
  if (cursor && cursor.file) {
    var hs = (Array.isArray(cursor.hotspot) && cursor.hotspot.length >= 2)
      ? cursor.hotspot : [0, 0];
    css += 'body.has-skin { cursor: url(' + cursor.file + ') ' + hs[0]
      + ' ' + hs[1] + ', auto; }\n';
    if (cursor.hand) {
      css += 'body.has-skin a, body.has-skin button { cursor: url('
        + cursor.hand + ') ' + hs[0] + ' ' + hs[1] + ', auto; }\n';
    }
  }

  // ---- the parts a skin may carry and the player did not draw ----
  // design/ui-skin.md lists nine more parts than the four above: a skin ships
  // their pictures and, until now, nothing ever drew them. Each is written
  // only when the skin carries it, so a skin that leaves one out keeps the
  // plain player's own rule for that thing exactly. Three of them (panel,
  // speech, tab) are nine-slices and take the flat ground the panel does, so a
  // small picture never tiles into stripes behind the words; the rest are
  // pictures laid over a whole thing, stretched to it.
  //
  // Rules that never bend, and how each is kept:
  //   - all words stay real text: nothing here paints a word, and the speech
  //     box takes the skin's declared ink rather than a colour of its own;
  //   - the focus ring is never removed and no rule adds a transition or an
  //     animation, so the player's reduced-motion blanket still covers all of
  //     it;
  //   - no rule sets a width or a height on a control: the picture stretches,
  //     the 44 px hit area is the player's own and is left alone;
  //   - every rule is inside the one media guard below, so prefers-contrast:
  //     more and forced colours return the plain flat style.
  var slot = parts.slot;
  if (slot && slot.file) {
    css += '.equip-row {' + plate(slot.file) + ' border-radius: 6px; }\n';
    if (slot.hover) css += '.equip-row:hover {' + plate(slot.hover) + ' }\n';
    // The worn row is the one that carries the Take off control.
    if (slot.selected) {
      css += '.equip-row:has([data-action="takeoff"]) {' + plate(slot.selected) + ' }\n';
    }
  }
  var tab = parts.tab;
  if (tab && tab.file) {
    var t = '#menu .pm button';
    css += t + ' {' + nine(tab.file, tab.slice, true)
      + ' background: var(--vefr-skin-ground, ' + ground() + '); }\n';
    if (tab.selected) {
      css += t + '[aria-current="true"] {' + nine(tab.selected, tab.slice, true)
        + ' background: var(--vefr-skin-ground, ' + ground() + '); }\n';
    }
  }
  // A switch is its two states: off is how it rests, on is what it is pressed
  // into. Both switches the player already draws (the phase rail and the fog
  // one) take the same pair, and each picture is written against the state it
  // belongs to - the pressed control is never reached by the resting rule, so
  // neither picture can sit on a switch in the state it is not in.
  var toggle = parts.toggle;
  if (toggle && (toggle.off || toggle.on)) {
    ['.phase-rail button', '#fog-toggle'].forEach(function (sel) {
      if (toggle.off) {
        css += sel + '[aria-pressed="false"], ' + sel + ':not([aria-pressed]) {'
          + plate(toggle.off) + ' }\n';
      }
      if (toggle.on) {
        css += sel + '[aria-pressed="true"] {' + plate(toggle.on) + ' }\n';
      }
    });
  }
  // The small tool buttons' tooltip. It says what the button does: the words
  // come out of the shell's own `data-tip` (the same word the button's
  // screen-reader text carries, without the key letter the kbd chip already
  // shows), and the picture is the skin's plate behind them. Drawn for the
  // keyboard on focus exactly as it is for the pointer on hover. The dark
  // base and the light ink under the picture are the player's own button
  // face, so the words stay readable if the picture is missing.
  var tip = parts.tooltip;
  if (tip && tip.file) {
    css += '.gbtn--tool[title]:hover::after, .gbtn--tool[title]:focus-visible::after {'
      + ' content: attr(data-tip); position: absolute; left: 50%; bottom: -7px;'
      + ' transform: translateX(-50%); padding: 6px 10px; border-radius: 3px;'
      + ' white-space: nowrap; pointer-events: none;'
      + ' color: #F4EEDD; background-color: #15181D;'
      + plate(tip.file) + ' }\n';
  }
  var speech = parts.speech;
  if (speech && speech.file) {
    css += '.npc-box, #npc-box {' + nine(speech.file, speech.slice, true)
      + ' background: var(--vefr-skin-ground, ' + ground() + ');'
      + (ink.on_panel ? ' color: ' + ink.on_panel + ';' : '') + ' }\n';
  }
  var divider = parts.divider;
  if (divider && divider.file) {
    // The rule under the game head, drawn as the head's own bottom border.
    // The head is a wrapping flex box, so a pseudo-element there would be a
    // flex item: it would take a row of the head's own wrap instead of
    // drawing a line under it. A border-image never joins the flow, and the
    // player's own edge colour is under the picture in case it is missing.
    // The slice gives the whole picture to the bottom edge (top, right and
    // left slices 0, bottom 100%) and the width puts it in the 8 px border
    // only, with no `fill`, so the picture never paints the head's face.
    css += 'header.game-head { border-bottom: 8px solid var(--card-edge);'
      + ' border-image: url(' + divider.file + ') 0 0 100% 0'
      + ' / 0 0 8px 0 / 0 stretch; }\n';
  }
  var banner = parts.banner;
  if (banner && banner.file) {
    // The message panel. It is a picture behind the messages and nothing else:
    // the map canvas and the HUD frame sit on the map and are not touched.
    css += '.toasts {' + plate(banner.file) + ' padding: 6px 8px; border-radius: 4px; }\n';
  }
  var corner = parts.corner;
  if (corner && corner.file) {
    // The four corner studs. The player's own accents are two 6 px dots at the
    // top corners; a skin's corner picture is a stud with a size of its own,
    // and there are four of them, so the two pseudo-elements each paint a stud
    // at two opposite corners and the two together make the four. Each is
    // spread over the panel (which is what takes them out of the flow) and
    // takes no pointer, so it never sits between a person and a control.
    //
    // The player's own dot rule paints these with the background shorthand, so
    // the accent is still sitting in the background COLOUR underneath. A stud is
    // panel-sized now, so without clearing it the accent floods the whole panel.
    // The longhand, not the shorthand: the shorthand would take the picture too.
    function studs(one, two) {
      return 'content: ""; position: absolute; inset: 8px; width: auto; height: auto;'
        + ' border-radius: 0; opacity: 1; pointer-events: none;'
        + ' background-color: transparent;'
        + ' background-image: url(' + corner.file + '), url(' + corner.file + ');'
        + ' background-position: ' + one + ', ' + two + ';'
        + ' background-size: ' + CORNER_STUD + 'px ' + CORNER_STUD + 'px,'
        + ' ' + CORNER_STUD + 'px ' + CORNER_STUD + 'px;'
        + ' background-repeat: no-repeat;';
    }
    css += '.carved::before, #config::before {' + studs('left top', 'right bottom') + ' }\n';
    css += '.carved::after, #config::after {' + studs('right top', 'left bottom') + ' }\n';
  }
  var gold = parts['gold-plate'];
  if (gold && gold.file) {
    // A plate behind the words on a gold control. The words stay real text on
    // top of it, in the light button ink the button rule above already set.
    css += '.cta--gold, .gbtn--gold, .stage button.primary {' + plate(gold.file) + ' }\n';
  }

  if (css) {
    var style = document.createElement('style');
    style.id = 'vefr-skin-css';
    style.textContent = '@media (prefers-contrast: no-preference) and'
      + ' (not (forced-colors: active)) {\n' + css + '}\n';
    document.head.appendChild(style);
  }
  setLook(lookPainted());
  // A skin's marks belong to the skin, and to a skin that opted into the
  // themed interface: they are added here and not by the shell, and only when
  // the skin carries at least one of the parts above. A pack with no skin, and
  // a skin that carries none of them, gets no mark and no portrait and keeps
  // the HUD row the shell built.
  var themed = THEMED_PARTS.some(function (name) { return !!parts[name]; });
  if (themed) {
    addHudMarks();
    // The speech box asks for its portrait through this hook every time it
    // shows a speaker (100-speech-box.js), so the portrait does not depend on
    // which of the two parts the page happened to load first: a speech box
    // declared after this part calls the hook all the same, and one declared
    // before it did too. One hook, however many times a skin loads.
    window.VEFR_SPEECH_BOX = dressSpeechBox;
  }
}
applySkin();

