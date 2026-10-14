/* Stair landing harness (vefr#465): what a hero can do on the tile a
   stair drops them on.

   Boots the REAL woven player in jsdom the way play.mjs does, runs the
   scripted steps, and takes a snapshot of what the player can read each
   time a `snap:NAME` step comes up - so one session can say what the
   button offered on arrival, after a second press, and after the hero
   has stepped off the landing and back onto it, without a second
   session redrawing anything.

   usage: node stair_landing_harness.mjs <woven.html> '<spec json>'
   spec  = {"steps": [...]}
   steps: "begin" | "wait:MS" | "walk:a,b" | "click:#sel" | "snap:NAME"
   prints one line: {"snaps": {NAME: {...}}, "errors": [...]} */
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
      return new Proxy({ canvas: this }, get: (t, k) => (k in t ? t[k] : noop) });
    };
    window.matchMedia = () => ({ matches: false, addListener: noop, removeEventListener: noop });
    window.addEventListener('error', (e) => errors.push(String(e.message || e)));
    window.localStorage.setItem('vefr-save-seed', '42');
  },
});
const { window } = dom;
const document = window.document;
const wait = (ms) => new Promise((r) => window.setTimeout(r, ms));
const text = (sel) => {
  const el = document.querySelector(sel);
  return el ? el.textContent : null;
};
const dirButton = (name) => [...document.querySelectorAll('#dpad button')]
  .find((b) => b.dataset.dir === name);

function snapshot() {
  const combat = window.VEFR_COMBAT || {};
  return {
    region: combat.region || null,
    hero: (combat.hero && Array.isArray(combat.hero.at)) ? combat.hero.at.slice() : null,
    poi: text('#poi'),
    interact: text('#interact-label'),
    near: text('#near'),
  };
}

const snaps = {};
async function run(step) {
  const colon = step.indexOf(':');
  const verb = colon === -1 ? step : step.slice(0, colon);
  const arg = colon === -1 ? '' : step.slice(colon + 1);
  if (verb === 'begin') {
    for (let i = 0; i < 60 && !document.getElementById('ts-enter'); i++) await wait(50);
    document.getElementById('ts-enter').click();
    for (let i = 0; i < 60 && !window.VEFR_COMBAT; i++) await wait(50);
    if (!window.VEFR_COMBAT) throw new Error('begin: VEFR_COMBAT never appeared');
    await wait(400);
  } else if (verb === 'wait') {
    await wait(Number(arg));
  } else if (verb === 'walk') {
    for (const d of arg.split(',').filter(Boolean)) {
      const b = dirButton(d);
      if (!b) throw new Error('walk: no pad button ' + d);
      b.click();
      await wait(10);
    }
  } else if (verb === 'click') {
    const el = document.querySelector(arg);
    if (!el) throw new Error('click: nothing at ' + arg);
    el.click();
    await wait(50);
  } else if (verb === 'snap') {
    snaps[arg] = snapshot();
  } else {
    throw new Error('unknown step: ' + step);
  }
}

for (const step of spec.steps || []) await run(step);
process.stdout.write(JSON.stringify({ snaps, errors }) + '\n');
window.close();
process.exit(0);