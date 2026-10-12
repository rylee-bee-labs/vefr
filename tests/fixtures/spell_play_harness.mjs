/* Spells harness (ADR 0018): drives the REAL woven player in jsdom and
   reads what the hero knows, what a book teaches and what a cast does.

   The bag is pre-seeded with the one spellbook the fixture pack has, the
   way a floor drop leaves it, and the growth state is seeded with the
   experience a level is worth, so both ways of learning are exercised
   without having to fight a monster first. Every read is what a player
   and a screen reader would get: the panel's visible text, the rows'
   own labels, and the storage behind them.

   usage: node spell_play_harness.mjs <woven.html> <spec json>
   spec: {"bag": [...], "growth": {...}, "steps": [...]}
     { "do": "openBag" }              // opens the Bag panel
     { "do": "hurt", "by": 4 }        // the hero loses that much health
     { "do": "cast", "spell": "id" }  // presses that spell's Cast button
     { "do": "castUnlisted", "spell": "id" } // castSpell(id) with no button,
                                      // the way a stale or forged press would
     { "do": "read", "item": "id" }   // presses that item's Use button
     { "do": "grow" }                 // awards 3 xp - one level
     { "do": "snap", "tag": "" }      // captures a named snapshot
   Prints {"steps": [...], "final": <snapshot>, "snaps": {...}, "errors": [...]}.

   A snapshot:
     spellNames: [string]  // each Spells row's visible text, in DOM order
     castLabels: [string]  // each Spells row's button label
     bagNames:   [string]  // each bag row's visible text, in DOM order
     panelText:  string    // every word visible in the Bag panel
     live:       string    // the panel's own live line
     hp:         number
     max:        number
     books:      [string]  // the learned-by-book list, as stored
     heading:    string    // the Spells heading's words
     hidden:     boolean   // whether the Spells section is off the page
     why:        [{id, why}] // the why-log (`VEFR_WHY`), oldest first
     whyText:    string    // every word the Why panel shows, newest first
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
    window.matchMedia = () => ({ matches: true, addListener: noop });
    window.addEventListener('error', (e) => errors.push(String(e.message || e)));
    const world = 'spell-test';
    if (spec.bag !== undefined) {
      window.localStorage.setItem('vefr-bag-' + world, JSON.stringify(spec.bag));
    }
    if (spec.growth !== undefined) {
      window.localStorage.setItem('vefr-growth-' + world, JSON.stringify(spec.growth));
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

const openBag = () => {
  const btn = d.getElementById('bagbtn');
  if (btn) btn.click();
  const tab = d.querySelector('[data-panel="bag"]');
  if (tab) tab.click();
};
const spellRow = (id) => [...d.querySelectorAll('#spell-list .bag-row')]
  .find((r) => (r.querySelector('button') || {}).dataset
    && r.querySelector('button').dataset.spell === id);
const bagButton = (id) => [...d.querySelectorAll('#bag-list button')]
  .find((b) => b.dataset.item === id);

const whyText = () => {
  if (typeof w.renderWhyPanel === 'function') w.renderWhyPanel();
  return (d.getElementById('why-list') || {}).textContent || '';
};

const snap = () => {
  const rows = [...d.querySelectorAll('#spell-list .bag-row')];
  const head = d.getElementById('spells-heading');
  const list = d.getElementById('spell-list');
  const panel = d.querySelector('[data-panel-body="bag"]');
  const worldName = (w.VEFR_WORLD && w.VEFR_WORLD.name) || 'world';
  let books = null;
  try { books = JSON.parse(w.localStorage.getItem('vefr-spells-' + worldName) || 'null'); } catch (e) { /* ignore */ }
  return {
    spellNames: rows.map((r) => (r.querySelector('.bag-row-name') || {}).textContent || ''),
    castLabels: rows.map((r) => (r.querySelector('button') || {}).getAttribute('aria-label') || ''),
    bagNames: [...d.querySelectorAll('#bag-list .bag-row .bag-row-name')]
      .map((r) => r.textContent || ''),
    panelText: panel ? (panel.textContent || '') : '',
    live: (d.getElementById('bag-live') || {}).textContent || '',
    hp: w.HERO_HP,
    max: w.heroMax ? w.heroMax() : null,
    books,
    heading: head ? (head.textContent || '') : '',
    hidden: list ? !!list.hidden : null,
    why: (w.VEFR_WHY || []).slice(),
    whyText: whyText(),
  };
};

const steps = [];
const snaps = {};
const note = (ok, what) => steps.push({ ok: !!ok, what });
let last = snap();
for (const step of (spec.steps || [])) {
  if (!step || !step.do) continue;
  if (step.do === 'openBag') openBag();
  else if (step.do === 'hurt') {
    w.HERO_HP = Math.max(1, w.HERO_HP - (step.by || 1));
    w.saveHeroHp();
    w.renderHp();
  } else if (step.do === 'cast') {
    const row = spellRow(step.spell);
    if (!row) note(false, 'no Cast row for ' + step.spell);
    else { row.querySelector('button').click(); note(true, 'cast ' + step.spell); }
  } else if (step.do === 'castUnlisted') {
    note(w.castSpell(step.spell), 'cast ' + step.spell);
  } else if (step.do === 'read') {
    const button = bagButton(step.item);
    if (!button) note(false, 'no Use button for ' + step.item);
    else { button.click(); note(true, 'read ' + step.item); }
  } else if (step.do === 'grow') {
    const r = w.growAward(step.xp || 3);
    note(!!r, 'awarded ' + (step.xp || 3) + ' xp');
  } else if (step.do === 'snap') {
    snaps[step.tag || String(Object.keys(snaps).length)] = snap();
    continue;
  } else throw new Error('unknown step: ' + step.do);
  await wait(30);
  last = snap();
}

process.stdout.write(JSON.stringify({ steps, final: last, snaps, errors }) + '\n');
w.close();
process.exit(0);