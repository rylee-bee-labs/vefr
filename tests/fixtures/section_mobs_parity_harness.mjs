/* Section monster count (vefr#357): the two JavaScript twins must read a
   Section's own `mobs` table exactly the way the Python spec reads it.

     node section_mobs_parity_harness.mjs <woven html> <cases.json> <out>

   <cases.json> (written by pytest, from tests/test_section_monster_count.py):
     {"descent": <the pack's descent block>, "depths": [1, 2, ...],
      "runs": [0], "section": <the Section pack, `mobs` and all>,
      "floors": [{"seed", "w", "h", "kind", "depth", "cycle"}, ...]}

   Two twins, because there are two places the count is read in the player:

     1. part 396's pop stage - `VEFR_DELVE.generateFloorV3(seed, size,
        section, kind, records, depth, cycle)` - which fills a floor's
        `spawns` and `chests`. The public call, not `v3Attempt`, because the
        spec side is `vefr.delve_v3.generate_floor_v3` and the two must be
        asked the same question: the whole retry ladder and the `gen` with
        it. `depth` is per case, which is the whole point - a per-depth key
        cannot be shown at one depth.
     2. part 397's play-time floor - `VEFR_DESCENT.floorPlan(depth, run)` -
        which is the `mobs` list the player actually walks.

   The descent block is planted after the file has run, exactly as the bake
   writes it and the player reads it at call time, and nothing else is
   planted: no storage, so nothing here can be a saved value.

   Writes ONE JSON file at <out>: {"floors": [{"gen", "spawns", "chests"}],
   "plans": [...], "cases": {...}} - plain JSON, exactly as
   `descent_parity_harness.mjs` hands its answers back, so Python reads the
   file and canonicalises both sides itself and the comparison is the one
   every other parity test makes. */
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
w.VEFR_DESCENT_DEF = cases.descent;
await new Promise((r) => w.setTimeout(r, 300));

const D = w.VEFR_DELVE;
const G = w.VEFR_DESCENT;
const out = {
  hasApi: !!(D && typeof D.generateFloorV3 === 'function'
    && G && typeof G.floorPlan === 'function'),
  floors: [],
  plans: [],
};

if (out.hasApi) {
  for (const floor of cases.floors) {
    // The twin builds its own floor key out of the four parts it is given,
    // which is how the depth reaches the `mobs` table at all.
    const drawn = D.generateFloorV3(floor.seed, [floor.w, floor.h],
                                    cases.section, floor.kind, [],
                                    floor.depth, floor.cycle);
    out.floors.push({
      gen: drawn.gen,
      spawns: drawn.spawns,
      chests: drawn.chests,
    });
  }
  for (const depth of cases.depths) out.plans.push(G.floorPlan(depth));
  for (const run of cases.runs) out.plans.push(G.floorPlan(1, run));
}

fs.writeFileSync(process.argv[4], JSON.stringify({
  hasApi: out.hasApi,
  cases: { floors: cases.floors, runs: cases.runs },
  floors: out.floors,
  plans: out.plans,
}) + '\n');
w.close();
process.exit(out.hasApi ? 0 : 2);