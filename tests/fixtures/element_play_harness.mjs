/* Elements harness (vefr#497): drives the REAL woven player in jsdom and
   plays the one fire/burning encounter - a hazard standing beside the
   hero's start, so a single press of a direction is the whole fight.

   Every read is what a player and a screen reader would get: the health
   the HUD shows, the live region's sentence (#combat-live is role="status"),
   and the words on the state line beside the health (#hud-state, also a
   live region). Nothing here reads a colour.

   usage: node element_play_harness.mjs <woven.html> [spec json]
   spec: {"steps": [...]}
     { "do": "press", "dir": "left" }   // presses that dpad button
     { "do": "snap", "tag": "" }         // captures a named snapshot
   Prints {"final": <snapshot>, "snaps": {...}, "errors": [...]}.

   A snapshot:
     hp, max:   number    // the health the HUD reads
     live:      string    // #combat-live, the sentence the last blow spoke
     state:     string    // #hud-state, the line beside the health
     stateOn:   boolean   // whether that line is on the page at all
     statuses:  [{effect, type, turns, tick}]   // the store itself
     saved:     [string]  // every key the player's own storage now holds
     foe:       number    // the hazard's remaining health
*/
import fs from 'node:fs';
import { JSDOM, VirtualConsole } from 'jsdom';

const html = fs.readFileSync(process.argv[2], 'utf8');
const spec = JSON.parse(process.argv[3] || '{}');
const noop = () => {};
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', (e) => errors.push(String((e && e.message) || e)));

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  url: 'http://localhost/',
  virtualConsole,
  beforeParse: (window) => {
    window.HTMLCanvasElement.prototype.getContext = function () {
      return new Proxy({ canvas: this }, { get: (t, k) => (k in t ? t[k] : noop) });
    };
    window.matchMedia = () => ({ matches: true, addListener: noop });
    window.addEventListener('error', (e) => errors.push(String(e.message || e)));
  },
});
const w = dom.window;
const d = w.document;
const wait = (ms) => new Promise((r) => w.setTimeout(r, ms));

for (let i = 0; i < 60 && !d.getElementById('ts-enter'); i++) await wait(50);
d.getElementById('ts-enter').click();
for (let i = 0; i < 60 && !w.VEFR_COMBAT; i++) await wait(50);
await wait(300);

const press = (dir) => {
  const b = [...d.querySelectorAll('#dpad button')].find((x) => x.dataset.dir === dir);
  if (!b) throw new Error('no dpad button ' + dir);
  b.click();
};
// The published fight snapshot (window.VEFR_COMBAT), refreshed every turn: the player's own
// variables live inside setupTown and are not on window.
const combat = () => (w.refreshCombatSnapshot ? w.refreshCombatSnapshot() : w.VEFR_COMBAT) || {};
const hero = () => (combat().enemies || []).find((e) => e && e.id === 'ember-hound');

const snap = () => {
  const line = d.getElementById('hud-state');
  const foe = hero();
  return {
    hp: w.HERO_HP,
    max: w.heroMax ? w.heroMax() : null,
    live: (d.getElementById('combat-live') || {}).textContent || '',
    state: line ? line.textContent || '' : null,
    stateOn: line ? !line.hidden : null,
    statuses: JSON.parse(JSON.stringify(combat().statuses || [])),
    saved: Object.keys(w.localStorage).sort(),
    foe: foe ? foe.hp : null,
  };
};

const snaps = {};
let last = snap();
for (const step of (spec.steps || [])) {
  if (!step || !step.do) continue;
  if (step.do === 'press') press(step.dir);
  else if (step.do === 'snap') {
    snaps[step.tag || String(Object.keys(snaps).length)] = snap();
    continue;
  } else throw new Error('unknown step: ' + step.do);
  await wait(30);
  last = snap();
}

process.stdout.write(JSON.stringify({ final: last, snaps, errors }) + '\n');
w.close();
process.exit(0);