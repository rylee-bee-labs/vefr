// ---- phase rail ----
// One way the watch turns, whatever turned it: the rail's own button, the
// Rest action (255-time-rest.js), or a rule that fires `phase-changes`
// elsewhere. They all come through gotoPhase, so a pack cannot end up
// with two different meanings of "the phase changed".
function gotoPhase(k) {
  if (!k) return;
  var rail = document.getElementById('phase');
  STATE.set({ phase: k });
  if (rail) {
    rail.querySelectorAll('button').forEach(function (x) {
      x.setAttribute('aria-pressed', x.dataset.phase === k ? 'true' : 'false');
    });
  }
  // A new tone moves the encounter prompt; the health line is
  // the hero's own and does not follow the phase.
  renderHp();
  renderEncounter();
  // Only a pack that asks for it keeps the standing phase (255).
  timePhaseSave(k);
  fireRule('phase-changes', { to: k });
  // The map draws by the phase too (the flood, lamplight's darkness): show the new one now, not at the next step.
  if (typeof window.VEFR_REDRAW === 'function') window.VEFR_REDRAW();
}
function buildPhaseRail() {
  var rail = document.getElementById('phase');
  rail.innerHTML = '';
  // "rail": "locked" takes the free jump away: no buttons to press, and
  // the row itself hidden, so time moves only by resting and by rules. A
  // pack that declares no `time` (or an open rail) builds exactly the
  // rail it always did.
  if (timeRailLocked()) {
    rail.style.display = 'none';
    return;
  }
  Object.keys(window.VEFR_WORLD.phases).forEach(function (k) {
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = k; b.dataset.phase = k;
    b.setAttribute('aria-pressed', 'false');
    b.addEventListener('click', function () { gotoPhase(k); });
    rail.appendChild(b);
  });
  rail.querySelectorAll('button').forEach(function (b) {
    b.setAttribute('aria-pressed', b.dataset.phase === STATE.get().phase ? 'true' : 'false');
  });
}

