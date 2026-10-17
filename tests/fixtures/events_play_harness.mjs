/* Events play harness: EXECUTES the woven single-file player in a
   real DOM (jsdom, dev-only) and performs every player action the
   rules engine can now notice - through the paths a player uses:
   Interact on a chest, walking onto a drop, bumping a rat, using a
   kept quest tool, trading at a shopkeeper, closing a book, turning
   the watch. It reports the fired rules, the bag, the gold and the
   two new evidence panels.

   usage: node events_play_harness.mjs <woven.html> */
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(process.argv[2], 'utf8');
const noop = () => {};

/* jsdom has no canvas; the player only needs a 2D context to exist so
   setupTown runs. Every drawing call is a no-op. */
function stubCanvas(window) {
  window.HTMLCanvasElement.prototype.getContext = function () {
    return {
      canvas: this, save: noop, restore: noop, translate: noop,
      setTransform: noop, fillRect: noop, clearRect: noop, drawImage: noop,
      beginPath: noop, arc: noop, fill: noop, stroke: noop,
      closePath: noop, moveTo: noop, lineTo: noop, fillText: noop,
      rotate: noop,
    };
  };
}

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  url: 'http://localhost/',
  beforeParse: (window) => {
    stubCanvas(window);
    window.matchMedia = () => ({
      matches: false, addListener: noop, removeListener: noop,
    });
  },
});
const { window } = dom;
const document = window.document;
const wait = (ms) => new Promise((r) => window.setTimeout(r, ms));
const whyLog = () => (window.VEFR_WHY || []).slice();
const flags = () => ((window.VEFR_RULES_STATE || {}).flags) || {};
const bag = () => JSON.parse(
  window.localStorage.getItem('vefr-bag-events-test') || '[]');
const hero = () => window.VEFR_COMBAT.hero.at.slice();
const until = async (cond, label) => {
  for (let i = 0; i < 80 && !cond(); i++) await wait(25);
  if (!cond()) throw new Error('timed out waiting for ' + label);
};
const press = (dir) => {
  const b = [...document.querySelectorAll('#dpad button')]
    .find((x) => x.dataset.dir === dir);
  if (!b) throw new Error('no dpad button ' + dir);
  b.click();
};
const walkTo = async (tx, ty) => {
  for (let i = 0; i < 40; i++) {
    const [x, y] = hero();
    if (x === tx && y === ty) return;
    if (x !== tx) press(x < tx ? 'right' : 'left');
    else press(y < ty ? 'down' : 'up');
    await wait(10);
  }
};

const steps = [];
const note = (ok, what) => steps.push({ ok: !!ok, what: what });

try {
  // ---- Begin: `starts` fires (the give + the point-to hint) ----
  for (let i = 0; i < 60 && !document.getElementById('ts-enter'); i++) await wait(50);
  document.getElementById('ts-enter').click();
  await until(() => flags()['lit'] === true, 'the starts rule');
  note(bag().includes('brass-key'), 'Begin gave the brass key');
  note((window.VEFR_NEXT || []).some((e) => e.place === 'town'),
       'the point-to hint was kept as an intention');

  // ---- Interact on the chest under the hero: `opens` + `picks-up` ----
  document.getElementById('interact').click();
  await until(() => flags()['opened'] === true, 'the opens rule');
  await until(() => flags()['got-it'] === true, 'the chest picks-up rule');
  note(true, 'Interact on the chest fired opens and picks-up');

  // ---- use the kept quest tool on the named place: `uses-with` ----
  press('right');               // onto the POI whose label is "keeper"
  await wait(20);
  window.useItem('brass-key');
  await until(() => flags()['used-key'] === true, 'the uses-with rule');
  note(bag().includes('brass-key'),
       'a kept tool is used and stays in the bag');

  // ---- bump the rat to death: `defeats`, and `takes` its toll ----
  for (let i = 0; i < 20 && flags()['won'] !== true; i++) {
    const snap = window.refreshCombatSnapshot();
    const foe = snap.enemies.filter((e) => e.alive)[0];
    if (!foe) break;
    const [hx, hy] = snap.hero.at;
    const [fx, fy] = foe.at;
    if (fx !== hx) press(fx < hx ? 'left' : 'right');
    else press(fy < hy ? 'up' : 'down');
    await wait(15);
  }
  await until(() => flags()['won'] === true, 'the defeats rule');
  note(!bag().includes('brass-key'), 'the takes action removed the key');

  // ---- walk onto the fallen drop: `picks-up` on the floor path ----
  const drop = window.refreshCombatSnapshot().floor[0];
  if (drop) await walkTo(drop.at[0], drop.at[1]);
  await until(() => flags()['got-drop'] === true, 'the floor picks-up rule');
  note(true, 'the fallen drop fired picks-up');

  // ---- trade at the shopkeeper: `buys` and `sells` ----
  await walkTo(6, 4);           // beside the keeper, the shopkeeper
  document.getElementById('interact').click();
  await until(() => !document.getElementById('trade').hidden, 'the trade panel');
  const buyBtn = document.querySelector(
    '#trade-buy button[data-item="cloudy-potion"]');
  if (!buyBtn) throw new Error('nothing to buy');
  buyBtn.click();
  await until(() => flags()['bought'] === true, 'the buys rule');
  const sellBtn = document.querySelector(
    '#trade-sell button[data-item="cloudy-potion"]');
  if (!sellBtn) throw new Error('nothing to sell');
  sellBtn.click();
  await until(() => flags()['sold'] === true, 'the sells rule');
  note(true, 'buying and selling fired their own events');
  window.closeTrade();

  // ---- read and close the chest's book: `reads` ----
  window.openMenu();
  document.querySelector('[data-panel="books"]').click();
  const bookBtn = document.querySelector('[data-panel-body="books"] button');
  if (!bookBtn) throw new Error('no book in the Books panel');
  bookBtn.click();
  await until(() => !document.getElementById('reader').hidden, 'the reader');
  document.getElementById('reader-close').click();
  await until(() => flags()['read-it'] === true, 'the reads rule');
  note(true, 'closing the book fired reads');

  // ---- turn the watch: `phase-changes` ----
  const dawn = document.querySelector('#phase button[data-phase="dawn"]');
  if (!dawn) throw new Error('no dawn button on the rail');
  dawn.click();
  await until(() => flags()['turned'] === true, 'the phase-changes rule');
  note(true, 'turning the watch fired phase-changes');

  // ---- the two evidence panels render from real records ----
  document.querySelector('[data-panel="next"]').click();
  const nextRows = document.querySelectorAll('#next-list p').length;
  note(nextRows >= 1, 'the Where next? panel shows the kept hint');
  document.querySelector('[data-panel="why"]').click();
  const whyRows = document.querySelectorAll('#why-list p').length;
  note(whyRows >= 8, 'the Why panel lists what actually fired');

  console.log(JSON.stringify({
    steps: steps,
    flags: flags(),
    bag: bag(),
    gold: window.VEFR_COMBAT.gold,
    fired: whyLog().map((e) => e.id),
    next: window.VEFR_NEXT,
    whyRows: whyRows,
    nextRows: nextRows,
    allOk: steps.every((s) => s.ok),
  }));
  // Exit on purpose: with pretendToBeVisual, requestAnimationFrame is live, and an animation the page legitimately
  // keeps running (the target cue's breathing glow, a prop's frames) would otherwise keep node alive forever.
  process.exit(0);
} catch (err) {
  console.error(String((err && err.stack) || err));
  console.log(JSON.stringify({ steps: steps, flags: flags(), bag: bag(),
                               failed: true }));
  process.exit(1);
}
