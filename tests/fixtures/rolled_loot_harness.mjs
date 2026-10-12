/* Rolled loot harness (ADR 0017): drives the REAL woven player in jsdom
   and reads what the bag says about a drawn drop.

   The bag is pre-seeded the way a floor drop leaves it - a bare id for a
   plain thing, an instance record for a rolled one - and the panel, the
   strip and the storage are read back the way a player and a screen
   reader would read them.

   usage: node rolled_loot_harness.mjs <woven.html> <spec json>
   spec: {"bag": <the entries>, "steps": [...]}
     { "do": "openBag" }        // opens the Bag panel
     { "do": "snap", "tag": "" } // captures a named snapshot
     { "do": "reload" }         // re-renders from storage
   Prints {"final": <snapshot>, "snaps": {...}, "errors": [...]}.

   A snapshot:
     bagNames:     [string]     // each bag row's visible text, in DOM order
     bagAria:      [string]     // each row's aria-label, where it has one
     strip:        string       // the HUD strip's aria-label
     stripKids:    [{cls, text}] // the HUD strip's own children, in order
     panelText:    string       // every word visible in the Bag panel
     bag:          <parsed>     // the bag as it stands in localStorage
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
  runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/', virtualConsole,
  beforeParse: (window) => {
    window.HTMLCanvasElement.prototype.getContext = function () {
      return new Proxy({ canvas: this }, { get: (t, k) => (k in t ? t[k] : noop) });
    };
    // Reduced motion is what a player who has asked for less of it gets,
    // and this slice owes them the same reveal either way.
    window.matchMedia = () => ({ matches: true, addListener: noop });
    window.addEventListener('error', (e) => errors.push(String(e.message || e)));
    const world = 'rolled-test';
    if (spec.bag !== undefined) {
      window.localStorage.setItem('vefr-bag-' + world, JSON.stringify(spec.bag));
    }
  },
});
const w = dom.window;
const d = w.document;
const wait = (ms) => new Promise((r) => w.setTimeout(r, ms));

for (let i = 0; i < 60 && !d.getElementById('ts-enter'); i++) await wait(50);
d.getElementById('ts-enter').click();
for (let i = 0; i < 60 && !w.VEFR_COMBAT; i++) await wait(50);
await wait(300);

const steps = spec.steps || [];

const snap = () => {
  const rows = [...d.querySelectorAll('#bag-list .bag-row')];
  const strip = d.getElementById('bag-strip');
  const panel = d.querySelector('[data-panel-body="bag"]');
  const worldName = (w.VEFR_WORLD && w.VEFR_WORLD.name) || 'world';
  let bag = null;
  try { bag = JSON.parse(w.localStorage.getItem('vefr-bag-' + worldName) || 'null'); } catch (e) { /* ignore */ }
  return {
    bagNames: rows.map((r) => (r.querySelector('.bag-row-name') || {}).textContent || ''),
    bagAria: rows.map((r) => r.getAttribute('aria-label') || ''),
    strip: strip ? (strip.getAttribute('aria-label') || '') : '',
    stripKids: strip ? [...strip.children].map((el) => ({ cls: el.className, text: el.textContent || '' })) : [],
    panelText: panel ? (panel.textContent || '') : '',
    bag,
  };
};

const openBag = () => {
  const btn = d.getElementById('bagbtn');
  if (btn) btn.click();
  const tab = d.querySelector('[data-panel="bag"]');
  if (tab) tab.click();
};

const snaps = {};
let last = snap();
for (const step of steps) {
  if (!step || !step.do) continue;
  if (step.do === 'openBag') openBag();
  else if (step.do === 'reload') {
    if (typeof w.renderBagPanel === 'function') w.renderBagPanel();
    if (typeof w.renderBagStrip === 'function') w.renderBagStrip();
  } else if (step.do === 'snap') {
    snaps[step.tag || String(Object.keys(snaps).length)] = snap();
    continue;
  } else throw new Error('unknown step: ' + step.do);
  last = snap();
}

process.stdout.write(JSON.stringify({ steps: steps.length, final: last, snaps, errors }) + '\n');
w.close();
process.exit(0);