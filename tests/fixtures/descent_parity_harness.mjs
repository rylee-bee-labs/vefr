/* Descent parity harness: the woven player's JavaScript twin of `locate`
   and the play-time floor must answer exactly what Python answers.

   argv[2] = woven html, argv[3] = JSON cases made by pytest:
   {"descent": <the pack's descent block>, "depths": [1, 2, ...],
    "runs": [0, 1]}.
   Prints {"hasApi": bool, "located": [...], "plans": [...]}.

   A second descent may come with the cases as `blueprintDescent`, with
   `blueprintDepths`: the same block plus the pack's Blueprint, which is
   what a floor resolves its families through. It is planted exactly as
   the first one is - the player reads the block at call time - and its
   answers come back under `blueprint`.

   A third may come as `depthDescent` with `depthDepths`: a Section that
   names its own `tiles` and whose families carry `depth` ranges. Each
   answer is that floor's k, the families that drew on it and its legend,
   under `depth`.

   A fourth may come as `rolled`: `{descent, depths, items}`. The catalog
   is planted on `window.VEFR_ITEMS` for the duration of that block only -
   the same global the weave writes, read at call time - so the rolled
   draws (ADR 0017) are compared in both languages against a Python floor
   drawn from the same catalog. */
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
// The block is planted after the file has run, exactly as the bake writes
// it and the player reads it at call time. Nothing else is planted: no
// storage, so nothing here can be a saved value.
w.VEFR_DESCENT_DEF = cases.descent;
await new Promise((r) => w.setTimeout(r, 300));
const D = w.VEFR_DESCENT;
const out = { hasApi: !!(D && D.locate && D.floorPlan), located: [], plans: [] };
if (out.hasApi) {
  for (const depth of cases.depths) {
    const at = D.locate(depth);
    out.located.push([at.cycle, at.section, at.k]);
    out.plans.push(D.floorPlan(depth));
  }
  for (const run of cases.runs) {
    out.plans.push(D.floorPlan(1, run));
  }
}
if (cases.blueprintDescent) {
  w.VEFR_DESCENT_DEF = cases.blueprintDescent;
  out.blueprint = { located: [], plans: [] };
  for (const depth of cases.blueprintDepths) {
    const at = D.locate(depth);
    out.blueprint.located.push([at.cycle, at.section, at.k]);
    out.blueprint.plans.push(D.floorPlan(depth));
  }
}
// The two keys the shape has to say something about and the floor has to
// honour: a Section's `tiles` (its own ground) and a family's `depth` (which
// of the Section's floors it lives on). Planted exactly as above; the answers
// come back under `depth`.
if (cases.depthDescent) {
  w.VEFR_DESCENT_DEF = cases.depthDescent;
  out.depth = [];
  for (const depth of cases.depthDepths) {
    const plan = D.floorPlan(depth);
    const families = [...new Set((plan ? plan.mobs : []).map((m) => m.family))].sort();
    out.depth.push({ depth, k: plan ? plan.k : null, families,
                     legend: plan ? plan.legend : null });
  }
}
// Books pinned to a generated floor: `pins` is [{"depth", "run", "books"}], and
// each answer is the twin's `placeBooks` on that floor (descent block planted
// first, exactly as above).
if (cases.pins) {
  w.VEFR_DESCENT_DEF = cases.descent;
  out.pins = cases.pins.map((p) => D.placeBooks(D.floorPlan(p.depth, p.run), p.books));
}
// Rolled loot (ADR 0017): the same cellar, with a catalog beside it. The
// twin reads `window.VEFR_ITEMS` where the weave writes it, so the whole
// drop - base id, drawn rarity, hidden traits - is compared in both
// languages. The catalog is put back afterwards so no later case sees it.
if (cases.rolled) {
  const had = w.VEFR_ITEMS;
  w.VEFR_ITEMS = cases.rolled.items;
  w.VEFR_DESCENT_DEF = cases.rolled.descent;
  out.rolled = { located: [], plans: [] };
  for (const depth of cases.rolled.depths) {
    const at = D.locate(depth);
    out.rolled.located.push([at.cycle, at.section, at.k]);
    out.rolled.plans.push(D.floorPlan(depth));
  }
  w.VEFR_ITEMS = had;
}
// The RPG core (ADR 0021): the same shape as `rolled`, over a descent whose
// Section names a `curve` and whose families name `guard`, `gold` and a
// `drop_chance`, and a catalog whose roll ties traits to rarity.
if (cases.rpg) {
  const had = w.VEFR_ITEMS;
  w.VEFR_ITEMS = cases.rpg.items;
  w.VEFR_DESCENT_DEF = cases.rpg.descent;
  out.rpg = { plans: [] };
  for (const depth of cases.rpg.depths) out.rpg.plans.push(D.floorPlan(depth));
  w.VEFR_ITEMS = had;
}
fs.writeSync(1, JSON.stringify(out) + '\n');
w.close();
process.exit(0);