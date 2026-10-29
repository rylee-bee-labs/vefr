/* RPG core harness (ADR 0021): drives the REAL woven player in jsdom and
   plays a script of steps against it, reading back what a player and a
   screen reader get - the health and mana lines, the fight's live line,
   the Bag panel's live line - and the harness views the player publishes
   (window.VEFR_COMBAT, window.VEFR_RPG). Nothing here reads a colour.

   usage: node rpg_play_harness.mjs <woven.html> [spec json]
   spec: {"steps": [...]}
     { "do": "press", "dir": "left" }        // presses that dpad button
     { "do": "eval", "js": "...", "tag": "" } // runs JS in the page, keeps its JSON result
     { "do": "snap", "tag": "" }             // captures a named snapshot
   Prints {"final": <snapshot>, "snaps": {...}, "evals": {...}, "errors": [...]}.

   A snapshot:
     hp, max:   number    // the health the HUD reads
     mana:      string    // #hud-mana, '' when hidden
     live:      string    // #combat-live, the sentence the last turn spoke
     bagLive:   string    // #bag-live, the Bag panel's own line
     rpg:       object    // window.VEFR_RPG()
     foes:      [{id, hp, alive}]
     region:    string
     saved:     [string]  // every key the player's own storage now holds
     said:      [string]  // every line the fight has spoken, in order
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

// Every line the fight speaks, in order: the live line is one sentence that
// the next one replaces (a monster's answer writes over the blow it answers),
// so the harness keeps what the Messages page keeps - all of them.
const said = [];
const speak = w.combatSay;
w.combatSay = function (msg, notOnPage) { if (msg) said.push(String(msg)); return speak(msg, notOnPage); };

const press = (dir) => {
  const b = [...d.querySelectorAll('#dpad button')].find((x) => x.dataset.dir === dir);
  if (!b) throw new Error('no dpad button ' + dir);
  b.click();
};
const combat = () => (w.refreshCombatSnapshot ? w.refreshCombatSnapshot() : w.VEFR_COMBAT) || {};
const text = (id) => {
  const el = d.getElementById(id);
  return el && !el.hidden ? el.textContent || '' : '';
};
const snap = () => ({
  hp: w.HERO_HP,
  max: w.heroMax ? w.heroMax() : null,
  mana: text('hud-mana'),
  live: (d.getElementById('combat-live') || {}).textContent || '',
  bagLive: (d.getElementById('bag-live') || {}).textContent || '',
  rpg: w.VEFR_RPG ? JSON.parse(JSON.stringify(w.VEFR_RPG())) : null,
  foes: (combat().enemies || []).map((e) => ({ id: e.id, hp: e.hp, alive: e.alive })),
  region: combat().region || '',
  saved: Object.keys(w.localStorage).sort(),
  said: said.slice(),
});

const snaps = {};
const evals = {};
let last = snap();
for (const step of (spec.steps || [])) {
  if (!step || !step.do) continue;
  if (step.do === 'press') press(step.dir);
  else if (step.do === 'eval') {
    const value = w.eval(step.js);
    evals[step.tag || String(Object.keys(evals).length)] =
      value === undefined ? null : JSON.parse(JSON.stringify(value));
  } else if (step.do === 'snap') {
    snaps[step.tag || String(Object.keys(snaps).length)] = snap();
    continue;
  } else throw new Error('unknown step: ' + step.do);
  await wait(30);
  last = snap();
}

process.stdout.write(JSON.stringify({ final: last, snaps, evals, errors }) + '\n');
w.close();
process.exit(0);
