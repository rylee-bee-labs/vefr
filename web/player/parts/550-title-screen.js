// ---- title screen ----
var titleScreen = document.getElementById('title-screen');
var tsEnter = document.getElementById('ts-enter');
// One way in, whichever key or the button got there. The flag matters
// because the key handler below and the button's own click can both
// fire for one press (Enter/Space on a focused button is the button's),
// and the world must start once.
var begun = false;
function beginGame() {
  if (begun) return;
  begun = true;
  titleScreen.setAttribute('aria-hidden', 'true');
  // After fade completes, remove from flow and show the game
  setTimeout(function () {
    // Now reveal config or play surface. configured:true (saved even
    // when both fields were left blank) means "setup decided - play",
    // so offline players don't get re-prompted on every load. The
    // llmUrl && llmModel check keeps pre-flag saves working.
    // Begin goes straight into the game; a model is only ever an
    // optional extra, offered from the pause menu.
    enterGame();
    // The one `starts` event: Begin has been pressed, the world is up
    // (setupTown has run, so the engine exists for any pack that has
    // rules - and fireRule is a no-op for every pack that does not).
    // In persist mode a reload skips it: the save already saw it.
    if (rulesStartsNow()) fireRule('starts', {});
  }, 0);
}
tsEnter.addEventListener('click', beginGame);
// The keys the title screen answers to (vefr#466). Begin holds the focus
// when the screen paints, so Enter and Space already reached it; F and E
// are the game's own Interact keys and did nothing here at all - a
// runner pressed F first on this screen in 7 of 16 runs - so they start
// the game here too. Tab is the other half: Begin is the only control on
// this screen, so Tab had nowhere to go but off the page, dropping focus
// onto the BODY, an invisible stop that swallowed the next Enter. It is
// held on Begin instead.
document.addEventListener('keydown', function (e) {
  if (begun) return;
  if (e.key === 'Tab') { e.preventDefault(); tsEnter.focus(); return; }
  if (e.key === 'f' || e.key === 'F' || e.key === 'e' || e.key === 'E'
    || e.key === ' ' || e.key === 'Enter') {
    if (e.repeat) return;
    // Space and Enter on a focused Begin are the button's own click; not
    // calling preventDefault keeps that path working, and `begun` stops
    // the second arrival from starting the world twice.
    beginGame();
  }
});
// Focus the enter button after paint
requestAnimationFrame(function () { tsEnter.focus(); });