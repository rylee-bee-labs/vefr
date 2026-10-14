// ---- player settings: larger text and reduced motion ----
// Two switches in the Display panel, stored and applied the way the panel's
// other settings are: a key in the store, read at the moment it matters, and
// put back on the page at once. The keys carry the world's name, so one game
// never borrows another's answer (the pattern the sound and the look use).
//
// Larger text is a fifth more on the body and on every label that follows it:
// --text-scale goes on the root element and every size in the sheet is in rem,
// so they all move together (020-style.css). Reduced motion lays down the same
// blanket the OS's own media query does, and the drawn motion asks the same
// question through reducedMotion(), which is why a player whose phone says
// nothing can still turn the hopping and the fading off.
var TEXT_LARGE_SCALE = 1.2;

// Computed per call and never cached, like the rules keys: a world that
// arrives late must still find its own key, and a reader must see one place
// where the name is spelled.
function textLargeKey() {
  return 'vefr-textsize-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
function reducedMotionKey() {
  return 'vefr-reducedmotion-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
function textLarge() {
  return store.get(textLargeKey()) === '1';
}
function reducedMotionOn() {
  return store.get(reducedMotionKey()) === '1';
}

function applyPlayerSettings() {
  document.documentElement.style.setProperty('--text-scale',
                                           textLarge() ? String(TEXT_LARGE_SCALE) : '1');
  document.body.classList.toggle('reduced-motion', reducedMotionOn());
}

function wirePlayerSettings() {
  var large = document.getElementById('text-large');
  var motion = document.getElementById('reduced-motion');
  if (!large || !motion) return;
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

applyPlayerSettings();
wirePlayerSettings();
