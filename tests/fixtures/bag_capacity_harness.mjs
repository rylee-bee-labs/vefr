/* Bag capacity harness: drives the REAL woven player in jsdom.

   usage: node bag_capacity_harness.mjs <woven.html> '<spec json>'
   spec:
     name:   the world name the pack was woven under (keys the saved bag and floor)
     store:  {localStorage key: string} set before the page runs
     adds:   optional [{id, alwaysFits}] - each one is bagAdd(id, null, alwaysFits)
     take:   optional {item} - a floor drop of that item is seeded on the hero's
             own tile, and the walk-onto-it path (takeHere) runs once

   Prints one JSON object:
     adds:    [bool]              the result of each bagAdd, in order
     count:   string              the Bag panel's count line after the adds
     combat:  string              the live line after takeHere
     bag:     [entry]             the saved bag at the end
     floor:   [drop] | null       the saved floor at the end
     errors:  [string]            jsdom errors caught on the way
*/
import fs from 'node:fs';
import { JSDOM, VirtualConsole } from 'jsdom';

const html = fs.readFileSync(process.argv[2], 'utf8');
const spec = JSON.parse(process.argv[3] || '{}');
const noop = () => {};
const errors = [];

async function open(store) {
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (e) => errors.push(String((e && e.message) || e)));
  const dom = new JSDOM(html, {
    runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/', virtualConsole,
    beforeParse: (window) => {
      window.HTMLCanvasElement.prototype.getContext = function () {
        return new Proxy({ canvas: this }, { get: (t, k) => (k in t ? t[k] : noop) });
      };
      window.matchMedia = () => ({ matches: false, addListener: noop, removeListener: noop });
      window.addEventListener('error', (e) => errors.push(String(e.message || e)));
      for (const [k, v] of Object.entries(store)) window.localStorage.setItem(k, v);
    },
  });
  const w = dom.window;
  const d = w.document;
  const wait = (ms) => new Promise((r) => w.setTimeout(r, ms));
  for (let i = 0; i < 60 && !d.getElementById('ts-enter'); i++) await wait(50);
  d.getElementById('ts-enter').click();
  for (let i = 0; i < 60 && !w.VEFR_COMBAT; i++) await wait(50);
  await wait(300);
  return { w, d };
}

const bagKey = 'vefr-bag-' + spec.name;
const floorKey = 'vefr-floor-' + spec.name;
const base = spec.store || {};
const result = {};

let page = await open(base);
if (spec.adds) {
  result.adds = spec.adds.map((a) => page.w.bagAdd(a.id, null, !!a.alwaysFits));
  page.w.renderBagPanel();
  result.count = (page.d.getElementById('bag-count') || {}).textContent || '';
}
if (spec.take) {
  const spot = page.w.VEFR_HERO_SPOT();
  page.w.close();
  const floor = [{ region: spot.region, at: spot.at, item: spec.take.item }];
  page = await open({ ...base, [floorKey]: JSON.stringify(floor) });
  page.w.VEFR_TAKE_HERE();
  result.combat = (page.d.getElementById('combat-live') || {}).textContent || '';
}
const saved = (key) => JSON.parse(page.w.localStorage.getItem(key) || 'null');
result.bag = saved(bagKey);
result.floor = saved(floorKey);
result.errors = errors;

console.log(JSON.stringify(result));
page.w.close();
process.exit(0);
