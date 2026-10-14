/* Play kit: one jsdom runner driven by a data spec, shared by the play
   harnesses. It boots the REAL woven player the way album_harness.mjs
   does, runs a list of scripted steps, then takes one synchronous read
   of each requested value.

   usage: node play.mjs <woven.html> '<spec json>'
   spec = {"store": {key: value}, "steps": [...], "read": [...]}
   steps: "begin" | "wait:MS" | "key:NAME" | "dir:NAME" | "walk:a,b" |
          "click:#sel" | "menu:PANEL"
   reads: "NAME" | "NAME.a.b" | "text:#sel" | "exists:#sel" |
          "visible:#sel" | "focused:#sel" | "store"
   A "NAME.a.b" path splits on '.', so a key that IS a dot - a map glyph -
   is not addressable: read the level above it and index in the test.
   prints one line: {"reads": {...}, "errors": [...], "store": {...}}
   The line is written whole however long it is (see `main`). */
import fs from 'node:fs';
import { JSDOM, VirtualConsole } from 'jsdom';

const html = fs.readFileSync(process.argv[2], 'utf8');
const spec = JSON.parse(process.argv[3] || '{}');
const noop = () => {};
const errors = [];
function stubCanvas(window) {
  window.HTMLCanvasElement.prototype.getContext = function () {
    return { canvas: this, save: noop, restore: noop, translate: noop, setTransform: noop,
             fillRect: noop, clearRect: noop, drawImage: noop, beginPath: noop, arc: noop,
             fill: noop, stroke: noop, closePath: noop, moveTo: noop, lineTo: noop, fillText: noop };
  };
}
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', (e) => errors.push(String((e && e.message) || e)));
const dom = new JSDOM(html, {
  runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/', virtualConsole,
  beforeParse: (window) => {
    stubCanvas(window);
    window.matchMedia = () => ({ matches: false, addListener: noop, removeListener: noop });
    window.addEventListener('error', (e) => errors.push(String(e.message || e)));
    window.localStorage.setItem('vefr-save-seed', '42');
    for (const [k, v] of Object.entries(spec.store || {})) window.localStorage.setItem(k, v);
  },
});
const { window } = dom;
const document = window.document;
const wait = (ms) => new Promise((r) => window.setTimeout(r, ms));

/* ---- steps ---------------------------------------------------------- */

/* The on-screen pad button for one direction, or undefined. Same lookup
   the harnesses' own press() uses. */
function dirButton(name) {
  return [...document.querySelectorAll('#dpad button')]
    .find((b) => b.dataset.dir === name);
}

/* Run one spec step. Returns false when the step is unknown, so the
   caller can name it and exit 2. */
async function runStep(step) {
  if (step === 'begin') {
    for (let i = 0; i < 60 && !document.getElementById('ts-enter'); i++) await wait(50);
    const enter = document.getElementById('ts-enter');
    if (!enter) throw new Error('begin: #ts-enter never appeared');
    enter.click();
    for (let i = 0; i < 60 && !window.VEFR_COMBAT; i++) await wait(50);
    if (!window.VEFR_COMBAT) throw new Error('begin: VEFR_COMBAT never appeared');
    await wait(400);
    return true;
  }
  const colon = step.indexOf(':');
  const verb = colon === -1 ? step : step.slice(0, colon);
  const arg = colon === -1 ? '' : step.slice(colon + 1);
  if (verb === 'wait') {
    const ms = Number(arg);
    if (arg.trim() === '' || !Number.isFinite(ms) || ms < 0) return false;
    await wait(ms);
    return true;
  }
  if (verb === 'key') {
    if (!arg) return false;
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: arg, bubbles: true }));
    return true;
  }
  if (verb === 'dir') {
    const b = dirButton(arg);
    if (!b) return false;
    b.click();
    return true;
  }
  if (verb === 'walk') {
    if (!arg) return false;
    const dirs = arg.split(',');
    for (const d of dirs) {
      if (!dirButton(d)) return false;
    }
    for (const d of dirs) {
      dirButton(d).click();
      await wait(10);
    }
    return true;
  }
  if (verb === 'click') {
    if (!arg) return false;
    let el = null;
    try { el = document.querySelector(arg); } catch (e) { el = null; }
    if (!el) return false;
    el.click();
    return true;
  }
  if (verb === 'menu') {
    if (!arg) return false;
    const opener = document.getElementById('menu-open');
    if (!opener) return false;
    opener.click();
    await wait(100);
    const btn = document.querySelector(`#menu [data-panel="${arg}"]`);
    if (!btn) return false;
    btn.click();
    return true;
  }
  return false;
}

/* ---- reads ---------------------------------------------------------- */

/* A JSON-safe copy: undefined and anything JSON cannot carry read as
   null rather than throwing. */
function clone(value) {
  if (value === undefined) return null;
  try { return JSON.parse(JSON.stringify(value)); } catch (e) { return null; }
}

/* window[NAME] or window[NAME.a.b], walking arrays by index; null at any
   missing hop and null when the global does not exist. */
function readGlobal(path) {
  let cur = window;
  for (const part of path.split('.')) {
    if (cur === null || cur === undefined) return null;
    cur = cur[part];
  }
  return clone(cur);
}

function readStore() {
  const store = {};
  for (let i = 0; i < window.localStorage.length; i++) {
    const k = window.localStorage.key(i);
    store[k] = window.localStorage.getItem(k);
  }
  return store;
}

/* Hidden on its own attributes only; visible() walks the ancestors. */
function hidden(el) {
  return el.hidden === true
    || (el.style && el.style.display === 'none')
    || el.getAttribute('aria-hidden') === 'true';
}

function visible(el) {
  for (let cur = el; cur; cur = cur.parentElement) {
    if (hidden(cur)) return false;
  }
  return true;
}

/* Resolve one read. Returns {ok, value}; ok false means unknown read. */
function doRead(read) {
  if (read === 'store') return { ok: true, value: readStore() };
  const colon = read.indexOf(':');
  if (colon === -1) return { ok: true, value: readGlobal(read) };
  const verb = read.slice(0, colon);
  const sel = read.slice(colon + 1);
  let el = null;
  try { el = sel ? document.querySelector(sel) : null; } catch (e) { el = null; }
  if (verb === 'text') return { ok: true, value: el ? el.textContent : null };
  if (verb === 'exists') return { ok: true, value: !!el };
  if (verb === 'visible') return { ok: true, value: !!el && visible(el) };
  /* Whether this element holds the keyboard focus right now - the read
     that proves a control kept focus instead of dropping it on the
     floor. False for an element that is not there at all. */
  if (verb === 'focused') return { ok: true, value: !!el && document.activeElement === el };
  return { ok: false, value: null };
}

/* ---- run ------------------------------------------------------------ */

async function main() {
  for (const step of Array.isArray(spec.steps) ? spec.steps : []) {
    if (!(await runStep(step))) {
      console.error('unknown step: ' + step);
      process.exit(2);
    }
  }
  const reads = {};
  for (const read of Array.isArray(spec.read) ? spec.read : []) {
    const r = doRead(read);
    if (!r.ok) {
      console.error('unknown read: ' + read);
      process.exit(2);
    }
    reads[read] = r.value;
  }
  const line = JSON.stringify({ reads, errors, store: readStore() });
  window.close();
  /* Written and WAITED FOR, not `console.log` followed by `process.exit`.
     Node flushes stdio on the way out of `process.exit` with a
     NON-BLOCKING try-write, which accepts what the 64 KB pipe buffer will
     take and throws the rest away - so a line longer than one pipe comes
     back cut off mid-string, and the harness reports it as a JSON decode
     error thousands of characters away from here. A descent walk that
     reads a Section's baked base64 tile table is exactly that long: the
     two Sections' ground plus the town's global set measure ~60 KB of the
     ~64 KB available, and the save doc is what pushes the rest over.
     Waiting for the drain makes the length of a read irrelevant, which is
     the only honest place for a harness to be indifferent to it. */
  process.stdout.write(line + '\n', () => process.exit(0));
}

try {
  await main();
} catch (err) {
  console.error(String((err && err.stack) || err));
  process.exit(1);
}
