/* Descent death harness: walk the REAL woven player down to a floor and
   then fight until the hero falls - pressing nothing else the moment
   they wake.

   The press kit (play.mjs) takes one reading at the end of a fixed list
   of steps, and a hero that wakes on the floor's up stair and then keeps
   walking is no measurement of where they woke. So the fight is a loop
   that stops on the wake itself, which is the one thing being measured.

   usage: node descent_death_harness.mjs <woven.html> <case json>
   case = {"floor": "cellar-0-3", "wake": [x, y],
           "walk": [["dir", "up"], ["click", "#interact"], ["wait", 150]],
           "fight": {"dir": "left", "presses": 60}}
   prints {"reads": {...}, "died": bool, "presses": N, "store": {...},
           "errors": [...]} */
import fs from 'node:fs';
import { JSDOM, VirtualConsole } from 'jsdom';

const html = fs.readFileSync(process.argv[2], 'utf8');
const plan = JSON.parse(process.argv[3] || '{}');
const noop = () => {};
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', (e) => errors.push(String((e && e.message) || e)));
const dom = new JSDOM(html, {
  runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/', virtualConsole,
  beforeParse: (window) => {
    window.HTMLCanvasElement.prototype.getContext = function () {
      return { canvas: this, save: noop, restore: noop, translate: noop,
               setTransform: noop, fillRect: noop, clearRect: noop, drawImage: noop,
               beginPath: noop, arc: noop, fillText: noop, stroke: noop, closePath: noop,
               moveTo: noop, lineTo: noop, fill: noop };
    };
    window.matchMedia = () => ({ matches: false, addListener: noop, removeListener: noop });
    window.addEventListener('error', (e) => errors.push(String(e.message || e)));
    window.localStorage.setItem('vefr-save-seed', '42');
  },
});
const { window } = dom;
const document = window.document;
const wait = (ms) => new Promise((r) => window.setTimeout(r, ms));

const dirButton = (name) =>
  [...document.querySelectorAll('#dpad button')].find((b) => b.dataset.dir === name);
const press = (name) => {
  const b = dirButton(name);
  if (!b) throw new Error('no dpad button ' + name);
  b.click();
};
const same = (a, b) => Array.isArray(a) && Array.isArray(b)
  && a.length === b.length && a.every((v, i) => v === b[i]);
// The dpad's own order, and the tile each way moves: a fight turns
// through these when a press is refused.
const DIRS = ['up', 'down', 'left', 'right'];
const VEC = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };

async function main() {
  for (let i = 0; i < 60 && !document.getElementById('ts-enter'); i++) await wait(50);
  document.getElementById('ts-enter').click();
  for (let i = 0; i < 60 && !window.VEFR_COMBAT; i++) await wait(50);
  if (!window.VEFR_COMBAT) throw new Error('VEFR_COMBAT never appeared');
  await wait(400);

  // A wake is the hero's health going UP: nothing in this pack heals
  // them, so a rise is the one thing `cozyDeath` does that no other
  // press can. Standing on the wake tile with full health is not a
  // wake - a hero that woke two tiles away can stroll onto it without
  // being hit - so the old "hurt at some point, and whole, and on the
  // tile" test read a stroll as a fall and every later reading was of
  // the wrong floor. A wake it is.
  let died = false;
  let presses = 0;
  let hp = (window.VEFR_COMBAT.hero || {}).hp;
  const woke = () => {
    const hero = (window.VEFR_COMBAT || {}).hero || {};
    const rose = typeof hero.hp === 'number' && typeof hp === 'number' && hero.hp > hp;
    hp = hero.hp;
    return rose && same(hero.at, plan.wake) && hero.hp === hero.max;
  };

  // The staging walk stops on the wake too, for the reason the fight
  // does: a hero that fell halfway down and then kept walking has not
  // staged anything, and every press after the fall is a press on a
  // floor the test never meant to measure.
  for (const [verb, arg] of plan.walk || []) {
    if (verb === 'wait') { await wait(Number(arg) || 0); continue; }
    if (verb === 'dir') press(arg);
    else if (verb === 'click') document.querySelector(arg).click();
    await wait(verb === 'click' ? 150 : 20);
    if (woke()) { died = true; break; }
  }

  // The fight: one way in, over and over, until the hero is found whole
  // again on the floor's own up stair.
  //
  // A press the engine refuses (a wall, the edge of the floor) is not
  // even a turn, so a fight that began facing one would never have
  // happened at all. When a press neither moves the hero nor bumps
  // something, the next one turns instead.
  //
  // `!died` is a boolean, and `<` binds tighter than `&&`: written
  // `i < !died && presses`, the test is `i < !died`, which is `i < 1`
  // while the hero is standing, and the fight is over after one press.
  // The count is the loop's bound and the wake is what stops it.
  let stuck = false;
  const fight = plan.fight || {};
  let dir = fight.dir || 'down';
  for (let i = 0; i < (fight.presses || 0) && !died; i++) {
    const before = (window.VEFR_COMBAT.hero || {}).at || [];
    if (stuck) dir = DIRS[(DIRS.indexOf(dir) + 1) % DIRS.length];
    const [dx, dy] = VEC[dir] || VEC.down;
    const bumping = (window.VEFR_COMBAT.enemies || []).some((e) =>
      e.alive && e.at[0] === before[0] + dx && e.at[1] === before[1] + dy);
    press(dir);
    presses++;
    await wait(20);
    const hero = (window.VEFR_COMBAT || {}).hero || {};
    const after = hero.at || [];
    stuck = !bumping && after[0] === before[0] && after[1] === before[1];
    if (woke()) { died = true; break; }
  }

  const store = {};
  for (let i = 0; i < window.localStorage.length; i++) {
    const k = window.localStorage.key(i);
    store[k] = window.localStorage.getItem(k);
  }
  return {
    died,
    presses,
    reads: {
      combat: window.VEFR_COMBAT,
      why: window.VEFR_WHY,
      transitions: window.VEFR_TRANSITIONS,
      doc: window.VEFR_DESCENT ? window.VEFR_DESCENT.doc : null,
    },
    store,
    errors,
  };
}

let out;
try {
  out = await main();
} catch (err) {
  out = { died: false, presses: 0, reads: {}, store: {}, errors: errors.concat([String(err)]) };
}
process.stdout.write(JSON.stringify(out) + '\n');
window.close();
process.exit(0);