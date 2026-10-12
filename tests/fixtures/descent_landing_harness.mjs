/* Descent landing harness (vefr#366): where every generated floor's
   up-stair goes, and which landings the save records.

   argv[2] = woven html, argv[3] = JSON cases made by pytest:
   {"descents": [{"descent": <block>, "depths": [1, 2, ...]}, ...]}.
   For each descent the block is planted, every depth's floor is entered
   through `ensureRegion` (what a stair does), and the answer is
   {"ups": [{depth, to, to_at}], "landings": [...], "isLanding": [...]}:
   the transition out of each floor's up anchor, the save's
   `flags.landing`, and the twin's `isLanding` for each depth's Section
   and k. Storage is a plain in-memory map, emptied between descents. */
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const noop = () => {};
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const dom = new JSDOM(fs.readFileSync(process.argv[2], 'utf8'), {
  runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/',
  beforeParse: (window) => {
    window.HTMLCanvasElement.prototype.getContext = function () {
      return new Proxy({ canvas: this }, { get: (t, k) => (k in t ? t[k] : noop) });
    };
    window.matchMedia = () => ({ matches: false, addListener: noop, removeListener: noop });
  },
});
const w = dom.window;
await new Promise((r) => w.setTimeout(r, 300));
const D = w.VEFR_DESCENT;
const out = [];
for (const one of cases.descents) {
  w.localStorage.clear();
  w.VEFR_DESCENT_DEF = one.descent;
  D.startRun(0);
  const ups = [];
  const isLanding = [];
  for (const depth of one.depths) {
    const plan = D.floorPlan(depth);
    D.ensureRegion(plan.name);
    const up = (w.VEFR_TRANSITIONS || []).filter((t) => t && t.from === plan.name &&
      String(t.at) === String(plan.anchors.up));
    ups.push({ depth, count: up.length, to: up.length ? up[0].to : null,
               to_at: up.length ? up[0].to_at : null });
    isLanding.push(D.isLanding(D.parseName(plan.name).section, plan.k));
  }
  out.push({ ups, isLanding, landings: D.landings() });
}
fs.writeSync(1, JSON.stringify(out) + '\n');
w.close();
process.exit(0);
