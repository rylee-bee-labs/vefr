// ---- player settings: the look, larger text and reduced motion ----
// Three settings in the Display panel, stored and applied the way the panel's
// other settings are: a key in the store, read at the moment it matters, and
// put back on the page at once. The keys carry the world's name, so one game
// never borrows another's answer (the pattern the sound and the pictures use).
//
// The look is Dark or Parchment: the same interface in two faces, chosen by
// the player and remembered. Each pack may name the one it starts on
// (world.json display.palette) - Cottage starts Dark - and a pack that names
// nothing leaves the engine's own default alone, which is neutral: the device
// decides, exactly as before this setting existed. Nothing is imposed: the
// palette is one attribute on <body> and the tokens in 020-style.css do the
// rest, so the drawn world (the pack's art, with its own colours) is untouched
// whichever face is on.
//
// Larger text is a fifth more on the body and on every label that follows it:
// --text-scale goes on the root element and the type-scale tokens
// (--text-body, --text-title, --text-small) carry it themselves, so the
// approved 17/20/13 px scale and every rem size in the sheet move together
// (020-style.css). Reduced motion lays down the same blanket the OS's own
// media query does, and the drawn motion asks the same question through
// reducedMotion(), which is why a player whose phone says nothing can still
// turn the hopping and the fading off.
var TEXT_LARGE_SCALE = 1.2;

// The two faces a look may take. Spelled once, here, because the pack's block
// is checked against the same two words (world.json display.palette).
var LOOKS = ['dark', 'parchment'];

// Computed per call and never cached, like the rules keys: a world that
// arrives late must still find its own key, and a reader must see one place
// where the name is spelled.
function textLargeKey() {
  return 'vefr-textsize-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
function reducedMotionKey() {
  return 'vefr-reducedmotion-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
function lookKey() {
  return 'vefr-lookpalette-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
function textLarge() {
  return store.get(textLargeKey()) === '1';
}
function reducedMotionOn() {
  return store.get(reducedMotionKey()) === '1';
}
// The player's own pick, or nothing: null is a real answer, and it is how a
// player says "whatever the game starts on".
function playerLook() {
  var mine = store.get(lookKey());
  return LOOKS.indexOf(mine) >= 0 ? mine : null;
}
// What this pack starts a new player on, or null when it has said nothing.
function packLook() {
  var display = (window.VEFR_WORLD && window.VEFR_WORLD.display) || {};
  return LOOKS.indexOf(display.palette) >= 0 ? display.palette : null;
}
// The player's pick wins; then the pack's default; then the engine's neutral,
// which is no attribute at all and leaves the sheet's own default (and the
// device's light or dark setting) exactly as they were.
function effectiveLook() {
  var mine = playerLook();
  return mine || packLook() || null;
}

function applyPlayerSettings() {
  document.documentElement.style.setProperty('--text-scale',
                                           textLarge() ? String(TEXT_LARGE_SCALE) : '1');
  document.body.classList.toggle('reduced-motion', reducedMotionOn());
  var look = effectiveLook();
  if (look) document.body.setAttribute('data-look', look);
  else document.body.removeAttribute('data-look');
}

function wirePlayerSettings() {
  var large = document.getElementById('text-large');
  var motion = document.getElementById('reduced-motion');
  if (large && motion) {
    large.checked = textLarge();
    large.addEventListener('change', function () {
      store.set(textLargeKey(), large.checked ? '1' : '0');
      applyPlayerSettings();
    });
    motion.checked = reducedMotionOn();
    motion.addEventListener('change', function () {
      store.set(reducedMotionKey(), motion.checked ? '1' : '0');
      applyPlayerSettings();
    });
  }
  var looks = document.querySelectorAll('#look-palette input[name="look-palette"]');
  var showing = effectiveLook();
  Array.prototype.forEach.call(looks, function (input) {
    // With no pick and no pack default there is no face to show as chosen;
    // Dark is marked, because that is what the engine's neutral has always
    // been on a device that says nothing.
    input.checked = input.value === (showing || 'dark');
    input.addEventListener('change', function () {
      if (!this.checked) return;
      store.set(lookKey(), this.value);
      applyPlayerSettings();
    });
  });
}

applyPlayerSettings();
wirePlayerSettings();
