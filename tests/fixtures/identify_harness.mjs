/* Identify harness (ADR 0017, T3 slice 2): drives the REAL woven player
   in jsdom, walks the hero up to the pack's reader, presses Interact,
   reads a carried thing, and reads the DOM back - synchronously, in the
   same tick as the click, so "the traits are there on the first frame"
   is proved by the page and not by reading the source.

   The bag is seeded the way a floor drop leaves it: a bare id for a
   plain thing, instance records for the rolled ones - one unread and one
   already read, so the page shows both states at once.

   usage: node identify_harness.mjs <woven.html> <spec json>
   spec: {"bag": <entries>, "motion": true|false, "steps": [...]}
     { "do": "walk", "dirs": ["right"] }   // press the dpad, one tile each
     { "do": "words", "tag": "" }           // capture the Interact's own words
     { "do": "interact", "key": "e" }       // press Interact
     { "do": "snap", "tag": "" }            // capture a named snapshot
     { "do": "readOne" }                    // click the first Read button
     { "do": "closeIdentify" }              // close the panel
     { "do": "openBag" }                    // open the Bag panel
     { "do": "reload" }                     // re-render from storage
   `motion: true` is a player who has asked for reduced motion; the same
   report with motion off is what the tests compare against.

   Prints {"final": <snapshot>, "snaps": {...}, "errors": [...]}.

   A snapshot:
     hint, label     // the Interact button's own words, as a player reads them
     title           // the identify panel's title
     rows            // each row's text and button word, in DOM order
     live            // the panel's own line of words
     panelText       // every word visible in the identify panel
     hidden          // whether the identify panel is open
     strip           // the HUD strip's aria-label (always in the DOM)
     bagNames        // each bag row's visible text, in DOM order
     bagPanel        // every word visible in the Bag panel
     bag             // the bag as it stands in localStorage
     hero            // the hero's tile
   */
import fs from 'node:fs';
import { JSDOM, VirtualConsole } from 'jsdom';

const html = fs.readFileSync(process.argv[2], 'utf8');
const spec = JSON.parse(process.argv[3] || '{}');
const noop = () => {};
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', (e) => errors.push(String((e && e.message) || e)));

const reduced = spec.motion !== false;

const dom = new JSDOM(html, {
  runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/', virtualConsole,
  beforeParse: (window) => {
    window.HTMLCanvasElement.prototype.getContext = function () {
      return new Proxy({ canvas: this }, { get: (t, k) => (k in t ? t[k] : noop) });
    };
    // Reduced motion is what a player who has asked for less of it gets.
    // This slice owes them the same reveal either way, and the tests run
    // both settings and compare the DOM word for word.
    window.matchMedia = () => ({ matches: reduced, addListener: noop, removeListener: noop });
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

const snap = () => {
  const rows = [...d.querySelectorAll('#identify-list .trade-row')];
  const panel = d.getElementById('identify');
  const strip = d.getElementById('bag-strip');
  const bagPanel = d.querySelector('[data-panel-body="bag"]');
  const worldName = (w.VEFR_WORLD && w.VEFR_WORLD.name) || 'world';
  let bag = null;
  try { bag = JSON.parse(w.localStorage.getItem('vefr-bag-' + worldName) || 'null'); } catch (e) { /* ignore */ }
  return {
    hero: JSON.parse(JSON.stringify(w.VEFR_COMBAT.hero.at || [])),
    hint: (d.getElementById('use-hint') || {}).textContent || '',
    label: (d.getElementById('interact-label') || {}).textContent || '',
    hidden: panel ? panel.hidden : null,
    title: (d.getElementById('identify-title') || {}).textContent || '',
    rows: rows.map((r) => ({
      text: (r.querySelector('.trade-name') || {}).textContent || '',
      button: (r.querySelector('button') || {}).textContent || '',
      aria: (r.querySelector('button') || { getAttribute: () => '' }).getAttribute('aria-label') || '',
    })),
    live: (d.getElementById('identify-live') || {}).textContent || '',
    panelText: panel ? (panel.textContent || '') : '',
    strip: strip ? (strip.getAttribute('aria-label') || '') : '',
    bagNames: [...d.querySelectorAll('#bag-list .bag-row')]
      .map((r) => (r.querySelector('.bag-row-name') || {}).textContent || ''),
    bagPanel: bagPanel ? (bagPanel.textContent || '') : '',
    bag,
  };
};

const press = (dir) => {
  const b = [...d.querySelectorAll('#dpad button')].find((x) => x.dataset.dir === dir);
  if (!b) throw new Error('no dpad button ' + dir);
  b.click();
};

const openBag = () => {
  const btn = d.getElementById('bagbtn');
  if (btn) btn.click();
  const tab = d.querySelector('[data-panel="bag"]');
  if (tab) tab.click();
};

const snaps = {};
let last = snap();
for (const step of spec.steps || []) {
  if (!step || !step.do) continue;
  if (step.do === 'walk') (step.dirs || []).forEach(press);
  else if (step.do === 'words') { /* nothing: snap() carries the words */ }
  else if (step.do === 'interact') {
    d.dispatchEvent(new w.KeyboardEvent('keydown', { key: step.key || 'e', bubbles: true }));
  } else if (step.do === 'snap') {
    snaps[step.tag || String(Object.keys(snaps).length)] = snap();
    continue;
  } else if (step.do === 'readOne') {
    const b = d.querySelector('#identify-list button[data-action="read"]');
    if (!b) throw new Error('no Read button in the identify panel');
    b.click();
    // The snapshot below is taken in this same tick, with no await in
    // between: whatever the player can see on the first frame after the
    // click is what this reads.
  } else if (step.do === 'closeIdentify') {
    d.getElementById('identify-close').click();
  } else if (step.do === 'openBag') {
    openBag();
  } else if (step.do === 'reload') {
    if (typeof w.renderBagPanel === 'function') w.renderBagPanel();
    if (typeof w.renderBagStrip === 'function') w.renderBagStrip();
  } else throw new Error('unknown step: ' + step.do);
  last = snap();
}

process.stdout.write(JSON.stringify({ reduced, steps: (spec.steps || []).length, final: last, snaps, errors }) + '\n');
w.close();
process.exit(0);