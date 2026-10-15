// ---- first-run setup vs play ----
var play = document.getElementById('play');
var configBox = document.getElementById('config');
// Title screen shows first; config/play revealed after "enter" click.
// Wire up the config-save handler now so it's ready when needed.
var cfgError = document.getElementById('cfg-error');
document.getElementById('cfg-save').addEventListener('click', function () {
  llmUrl = document.getElementById('cfg-url').value.trim().replace(/\/+$/, '');
  llmModel = document.getElementById('cfg-model').value.trim();
  // Half-filled is the only mistake worth stopping: one without the
  // other can never reach an endpoint. Both blank is a real choice -
  // play offline, the woven pool carries the world.
  if (!!llmUrl !== !!llmModel) {
    cfgError.textContent = 'The address and the model name go together: fill in both, or leave both blank to play offline.';
    cfgError.hidden = false;
    return;
  }
  cfgError.hidden = true;
  saveConfig({ llmUrl: llmUrl, llmModel: llmModel, configured: true });
  enterGame();
});
document.getElementById('cfg-offline').addEventListener('click', function () {
  llmUrl = ''; llmModel = '';
  cfgError.hidden = true;
  saveConfig({ llmUrl: '', llmModel: '', configured: true });
  enterGame();
});
function enterGame() {
  configBox.hidden = true; play.hidden = false;
  startPlaySurface();
}

/* Which surface does the active act play on? A cooking act
   opens the kitchen; everything else keeps the town. */
var surfaceStarted = false;
function startPlaySurface() {
  // Coming back from Model settings keeps the game running.
  if (surfaceStarted) return;
  surfaceStarted = true;
  var act0 = (VEFR_WORLD.acts && VEFR_WORLD.acts[0]) || {};
  if (act0.ruleset === 'cooking' && act0.cooking && act0.cooking.tickets) {
    document.getElementById('stage').hidden = true;
    initKitchen();
  } else if (act0.ruleset === 'desk' && act0.desk && act0.desk.headlines) {
    document.getElementById('stage').hidden = true;
    initDesk();
  } else {
    document.body.classList.add('in-game');
    bootstrap();
  }
}

function bootstrap() {
  STATE.set({ world: window.VEFR_WORLD, phase: Object.keys(window.VEFR_WORLD.phases)[0] });
  loadEquipped();
  loadHeroHp();
  applySurface();
  buildPhaseRail();
  bindWhisper();
  setupTown();
  bindMenu();
  bindLibrary();
  renderBagPanel();
  renderBagStrip();
  renderGold();
  // Slice E1: the descent's own controls, once there is a town for them
  // to sit in. A pack with no descent binds nothing and shows nothing.
  if (window.VEFR_DESCENT) {
    window.VEFR_DESCENT.wireEntry();
    window.VEFR_DESCENT.bindDescent();
    window.VEFR_DESCENT.offerCard();
  }
  var touch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
  var statusEl0 = document.getElementById('status');
  if (!tutorialDone()) {
    statusEl0.textContent = touch
      ? 'Move on the left. Near someone, tap the round button.'
      : 'Move with the arrow keys or WASD. Press F to talk.';
    statusEl0.setAttribute('data-tutorial', '1');
  }
}

// The how-to-move line is a one-time lesson: it goes at the first step and stays
// gone (Rylee: the bottom text "basically never goes away").
function tutorialKey() {
  return 'vefr-tutorial-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
function tutorialDone() {
  return store.get(tutorialKey()) === '1';
}
function quietTutorial() {
  var el = document.getElementById('status');
  if (!el || el.getAttribute('data-tutorial') !== '1') return;
  el.textContent = '';
  el.removeAttribute('data-tutorial');
  store.set(tutorialKey(), '1');
}

