/* Dialog focus harness (vefr #462): plays the REAL woven player in jsdom and asks
   the two questions the issue asks. With a dialog open, does Tab stay inside it?
   And when it closes, is the focus back on the control that opened it?

   Two files, because the two answers live in different places: argv[2] is the
   events fixture (a resident, a shop), argv[3] is the descent fixture, which is
   the one box whose close path never moved focus anywhere (the floors-changed
   card, part 397's hideCard) - that is where "focus went back to the opener" is
   a real fix and not a restatement of what closeReader already did.

   usage: node dialog_focus_harness.mjs <events.html> <descent.html> */
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const noop = () => {};
function boot(path) {
  const dom = new JSDOM(fs.readFileSync(path, 'utf8'), {
    runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost/',
    beforeParse: (window) => {
      window.HTMLCanvasElement.prototype.getContext = function () {
        return new Proxy({ canvas: this }, { get: (t, k) => (k in t ? t[k] : noop) });
      };
      window.matchMedia = () => ({ matches: false, addListener: noop, removeListener: noop });
    },
  });
  return dom.window;
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const steps = [];
const note = (ok, what) => steps.push({ ok: !!ok, what });

async function begin(w) {
  for (let i = 0; i < 60 && !w.document.getElementById('ts-enter'); i++) await wait(50);
  w.document.getElementById('ts-enter').click();
  for (let i = 0; i < 60 && !w.VEFR_COMBAT; i++) await wait(50);
  await wait(200);
}
const key = (w, k, extra) => w.document.dispatchEvent(new w.KeyboardEvent(
  'keydown', Object.assign({ key: k, bubbles: true, cancelable: true }, extra || {})));
const $ = (w, id) => w.document.getElementById(id);
const here = (w) => w.document.activeElement;
const idOf = (w) => (here(w) && here(w).id) || (here(w) ? here(w).tagName.toLowerCase() : 'nothing');
// "Inside the box" means on one of its own controls, not on the box itself:
// a dialog with tabindex="-1" takes the focus first and Tab walks on from there.
const inBox = (w, id) => {
  const box = $(w, id);
  const el = here(w);
  return !!box && !!el && box.contains(el) && el !== box;
};
const lost = (w) => {
  const el = here(w);
  return !el || el === w.document.body || el === w.document.documentElement;
};
// The controls of the page behind every dialog: the ones run-004 named.
const PAGE = ['menu-open', 'talk', 'whisper', 'bagbtn', 'explore', 'interact', 'toasts-toggle'];
const onPage = (w) => PAGE.indexOf(idOf(w)) !== -1;

// Tab N times and say whether the focus stayed in the box every single time.
async function tabsStayInside(w, id, times, reverse) {
  let stayed = true, walked = 0;
  for (let i = 0; i < times; i++) {
    key(w, 'Tab', reverse ? { shiftKey: true } : null);
    if (!inBox(w, id) || onPage(w)) stayed = false;
    walked++;
  }
  return stayed && walked === times;
}

try {
  // ---------- the events fixture: Trade, a book, a line of speech ----------
  const w = boot(process.argv[2]);
  await begin(w);

  // Trade, opened the way the town opens it: the Interact button is the opener.
  $(w, 'interact').focus();
  w.openTrade('keeper', 'The Keeper', here(w));
  note(!$(w, 'trade').hidden, 'the Trade dialog opened');
  note(inBox(w, 'trade') === false, 'Trade takes the focus on the box itself first');
  key(w, 'Tab');
  note(inBox(w, 'trade'), 'one Tab lands on a control inside Trade');
  note(await tabsStayInside(w, 'trade', 8), 'eight more Tabs stay inside Trade');
  note(await tabsStayInside(w, 'trade', 3, true), 'Shift+Tab walks back inside Trade, never out');
  key(w, 'Escape');
  note($(w, 'trade').hidden, 'Escape closes Trade');
  note(idOf(w) === 'interact', 'and the focus goes back to the Interact button that opened it');

  // A book: the reader takes the focus on the box, and its own controls are
  // Back (disabled on the first page), Read on and Close.
  w.openReader({ id: 'a-test-note', title: 'A test note', pages: ['one', 'two', 'three'] });
  note(!$(w, 'reader').hidden, 'the reader opened');
  key(w, 'Tab');
  note(inBox(w, 'reader'), 'one Tab lands on a control inside the reader');
  note(await tabsStayInside(w, 'reader', 8), 'eight more Tabs stay inside the reader');
  note(idOf(w) !== 'reader-back', 'the disabled Back button is not a Tab stop');
  key(w, 'Escape');
  note($(w, 'reader').hidden, 'Escape closes the reader');
  note(!lost(w), 'and the focus is on a real control, not on nothing');

  // A line of speech: the smallest dialog there is.
  w.showSpeech('A rat', 'You look like trouble.', '');
  note(!$(w, 'npc-box').hidden, 'the speech box opened');
  key(w, 'Tab');
  note(await tabsStayInside(w, 'npc-box', 4), 'every Tab stays inside the speech box');
  key(w, 'e');   // E is the key that closes a speech box; Escape opens the menu
  note($(w, 'npc-box').hidden, 'E closes the speech box');
  note(!lost(w), 'and the focus is on a real control, not on nothing');
  w.close();

  // ---------- the descent fixture: the floors-changed card ----------
  // An old save and a new weave is the one path where closing a dialog leaves
  // the focus on nothing: hideCard() hides the card and moves the focus
  // nowhere. The save is planted before the game is entered, because that is
  // when the card is decided.
  const s = boot(process.argv[3]);
  const world = (s.VEFR_WORLD && s.VEFR_WORLD.name) || 'world';
  s.localStorage.setItem('vefr-bag-' + world, '[]');
  s.localStorage.setItem('vefr-descent-' + world, JSON.stringify(
    { v: 1, gen: 0, run: 0, seed: 'run-a', order: [], floors: {}, flags: {}, card: 0 }));
  await begin(s);
  const card = $(s, 'gen-card');
  note(!!s.VEFR_DESCENT && !!card && !card.hidden,
       'an old save meets the new floors and the card is offered');
  note(inBox(s, 'gen-card'), 'the card puts the focus on a control of its own');
  note(await tabsStayInside(s, 'gen-card', 4), 'Tab stays inside the card');
  $(s, 'gen-card-keep').click();
  await wait(50);
  note($(s, 'gen-card').hidden, 'Keep this world closes the card');
  note(!lost(s), 'and the focus is on a real control again, not on nothing');
  note(idOf(s) === 'menu-open', 'the control that opened it is where the focus went');
  s.close();
} catch (err) { note(false, 'threw: ' + err.message); }
console.log(JSON.stringify({ allOk: steps.every((x) => x.ok), steps }));
process.exit(0);