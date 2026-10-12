/* Talk offline harness: EXECUTES the woven single-file player in a real
   DOM (jsdom, dev-only) and plays Talk on the interact fixture pack
   (make_interact_pack.py), with no brain (static) or with a brain
   configured whose every request fails (brain). Every scenario boots
   the player FRESH and logs one flat key/value list:

     - static: the cat (seeds only) answers each Talk with its seeded
       line for the time of day; the stranger (no line at all) is not
       offered Talk, the press opens nothing, and the Talk button says
       "They didn't answer.";
     - brain: the stranger's words stay 'Talk to', the Talk button says
       "They didn't answer." (the brain was expected and failed, and
       there is no seeded line), and the cat falls back to its seeded
       line when the brain fails.

   usage: node talk_offline_harness.mjs <woven.html> <static|brain> */
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const [htmlPath, mode] = process.argv.slice(2);
if (!htmlPath || (mode !== 'static' && mode !== 'brain')) {
  throw new Error('usage: talk_offline_harness.mjs <woven.html> <static|brain>');
}
const html = fs.readFileSync(htmlPath, 'utf8');
const noop = () => {};
const SAVE_SEED = '42';
const BRAIN = mode === 'brain';

function stubCanvas(window) {
  window.HTMLCanvasElement.prototype.getContext = function () {
    if (!this.__ctx) {
      this.__ctx = {
        canvas: this, save: noop, restore: noop, translate: noop,
        setTransform: noop, fillRect: noop, clearRect: noop, drawImage: noop,
        beginPath: noop, arc: noop, fill: noop, closePath: noop,
        moveTo: noop, lineTo: noop, fillText: noop, stroke: noop,
      };
    }
    return this.__ctx;
  };
}

/* The fixture's pinned walk: the hero starts at [1, 1]. [8, 2] is the
   only tile in reach of the cat at [9, 1]; [8, 4] is the only tile in
   reach of the stranger at [8, 5]. */
const TO_CAT = ['down', 'down', 'right', 'right', 'right', 'right',
                'right', 'right', 'right', 'up'];                 // [8, 2]
const TO_STRANGER = ['down', 'down'];                             // [8, 4]

const log = [];
const say = (k, v) => log.push([k, v]);

async function boot() {
  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'http://localhost/',
    beforeParse: (window) => {
      stubCanvas(window);
      window.matchMedia = () => ({
        matches: false, addListener: noop, removeListener: noop,
      });
      window.localStorage.setItem('vefr-save-seed', SAVE_SEED);
      if (BRAIN) {
        window.localStorage.setItem('vefr-packaged-config', JSON.stringify(
          { llmUrl: 'http://brain.invalid', llmModel: 'stub', configured: true }));
        window.fetch = () => Promise.reject(new Error('the brain is down'));
      }
    },
  });
  const { window } = dom;
  const document = window.document;
  const wait = (ms) => new Promise((r) => window.setTimeout(r, ms));
  for (let i = 0; i < 60 && !document.getElementById('ts-enter'); i++) await wait(50);
  document.getElementById('ts-enter').click();
  for (let i = 0; i < 60 && !window.VEFR_COMBAT; i++) await wait(50);
  if (!window.VEFR_COMBAT) throw new Error('boot never produced VEFR_COMBAT');

  const press = (dir) => {
    const b = [...document.querySelectorAll('#dpad button')]
      .find((x) => x.dataset.dir === dir);
    if (!b) throw new Error('no dpad button ' + dir);
    b.click();
  };
  const key = (k) => document.dispatchEvent(
    new window.KeyboardEvent('keydown', { key: k, bubbles: true }));
  const txt = (id) => document.getElementById(id).textContent;
  const snap = () => JSON.parse(JSON.stringify(window.VEFR_COMBAT));
  const closeNpc = () => { document.getElementById('npc-close').click(); };
  const box = () => document.getElementById('npc-box').hidden;
  const close = () => { try { window.close(); } catch (e) { /* already gone */ } };
  return { wait, walk: (dirs) => dirs.forEach(press), key, txt, snap,
           closeNpc, box, close, document };
}

try {
  if (!BRAIN) {
    {
      const g = await boot();
      g.walk(TO_CAT);
      say('cat-spot', g.snap().hero.at);
      say('cat-label', g.txt('interact-label'));
      for (let n = 1; n <= 3; n++) {
        g.closeNpc();
        g.key('e');
        await g.wait(150);
        say('cat-talk-' + n + '-box-hidden', g.box());
        say('cat-talk-' + n + '-name', g.txt('npc-name'));
        say('cat-talk-' + n + '-line', g.txt('npc-line'));
        say('cat-talk-' + n + '-near', g.txt('near'));
      }
      g.close();
    }
    {
      const g = await boot();
      g.walk(TO_CAT.concat(TO_STRANGER));
      say('stranger-spot', g.snap().hero.at);
      say('stranger-label', g.txt('interact-label'));
      say('stranger-hint', g.txt('use-hint'));
      g.closeNpc();
      g.key('e');
      await g.wait(150);
      say('stranger-key-box-hidden', g.box());
      say('stranger-key-name', g.txt('npc-name'));
      say('stranger-key-line', g.txt('npc-line'));
      say('stranger-key-near', g.txt('near'));
      g.closeNpc();
      g.document.getElementById('talk').click();
      await g.wait(150);
      say('stranger-talkbtn-box-hidden', g.box());
      say('stranger-talkbtn-name', g.txt('npc-name'));
      say('stranger-talkbtn-near', g.txt('near'));
      g.close();
    }
  } else {
    {
      const g = await boot();
      g.walk(TO_CAT.concat(TO_STRANGER));
      say('brain-stranger-label', g.txt('interact-label'));
      g.closeNpc();
      g.document.getElementById('talk').click();
      await g.wait(150);
      say('brain-stranger-talkbtn-box-hidden', g.box());
      say('brain-stranger-talkbtn-near', g.txt('near'));
      g.close();
    }
    {
      const g = await boot();
      g.walk(TO_CAT);
      say('brain-cat-label', g.txt('interact-label'));
      g.key('e');
      await g.wait(150);
      say('brain-cat-box-hidden', g.box());
      say('brain-cat-name', g.txt('npc-name'));
      say('brain-cat-line', g.txt('npc-line'));
      say('brain-cat-near', g.txt('near'));
      g.close();
    }
  }
} catch (e) {
  say('HARNESS-ERROR', String((e && e.message) || e));
}

process.stdout.write(JSON.stringify({ log }, null, 1));
