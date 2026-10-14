/* Interact harness: EXECUTES the woven single-file player in a real
   DOM (jsdom, dev-only) and plays the one-button Interact verb on the
   interact fixture pack. Every scenario boots the player FRESH (the
   chest's found-list, the door's region and the save's fragment draw
   counter all live in storage, so a shared boot would leak one
   scenario into the next), walks the pinned tiles from
   make_interact_pack.py, and logs one flat key/value list:

     - E, Space, Enter and F next to the resident, the door, the
       chest and the trader: the words on #use-hint / #interact-label
       before the press and the action each key produced;
     - nothing in reach: the friendly nudge, the dimmed button, and
       full VEFR_COMBAT snapshots before/after every press, so the
       tests can prove NOT ONE turn passed;
     - the target ring: jsdom has no real canvas, so the ring is only
       proven DRAW-ONLY - the stub counts strokes in the ring's own
       gold (#D8AA4E, set nowhere else in the player) and the
       snapshots around a forced draw() prove no state moved;
     - the regression half: the Talk button, a canvas click, the
       Interact button itself on chest/trade/door, a bump, and one
       arrow press moving exactly one tile.

   The talk path is async: with no endpoint configured llmPost
   rejects immediately and the offline fallback runs - the woven pool
   is empty (pool=0), so the resident's own fragment bank splices a
   line into the speech box. The save seed is pinned in storage so
   that splice is deterministic.

   usage: node interact_play_harness.mjs <woven.html> */
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(process.argv[2], 'utf8');
const noop = () => {};
/* Pinned save seed: composeFromFragments draws from
   saveSeed() + nextDraw(), so pinning the seed pins the line. */
const SAVE_SEED = '42';

/* jsdom has no canvas; the player only needs a 2D context to exist so
   setupTown runs. Every drawing call is a no-op - except stroke, which
   counts the ring's own gold so the tests can see drawTargetRing ran.
   #D8AA4E is set as a canvas strokeStyle nowhere else in the player
   (the CSS uses of that gold are DOM, not canvas). */
const ring = { strokes: 0 };
function stubCanvas(window) {
  window.HTMLCanvasElement.prototype.getContext = function () {
    if (!this.__ctx) {
      this.__ctx = {
        canvas: this, save: noop, restore: noop, translate: noop,
        setTransform: noop, fillRect: noop, clearRect: noop, drawImage: noop,
        beginPath: noop, arc: noop, fill: noop, closePath: noop,
        moveTo: noop, lineTo: noop, fillText: noop,
        stroke: function () {
          if (this.strokeStyle === '#D8AA4E') ring.strokes += 1;
        },
      };
    }
    return this.__ctx;
  };
}

/* Walk routes over the pinned town of make_interact_pack.py; each
   ends on that target's standing spot (see the coordinate comment
   there). Never a tile beside the rat except the bump test, so the
   enemy and every pin stay put. */
const TO_RESIDENT = ['down', 'down', 'right', 'right', 'up', 'right'];   // [4, 2]
const TO_CHEST = TO_RESIDENT.concat(['right', 'right', 'right']);         // [7, 2]
const TO_DOOR = TO_CHEST.concat(['down', 'down', 'right', 'right']);      // [9, 4]
const TO_TRADER = TO_DOOR.concat(['left', 'left', 'left']);               // [6, 4]
const TO_EMPTY = TO_TRADER.concat(['left', 'left', 'left', 'left', 'left',
                                   'down']);                              // [1, 5]

const KEYS = [['e', 'e'], [' ', 'space'], ['Enter', 'enter'], ['f', 'f']];

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
    },
  });
  const { window } = dom;
  const document = window.document;
  const wait = (ms) => new Promise((r) => window.setTimeout(r, ms));
  window.localStorage.setItem('vefr-save-seed', SAVE_SEED);
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
  const walk = (dirs) => dirs.forEach(press);
  const key = (k) => document.dispatchEvent(
    new window.KeyboardEvent('keydown', { key: k, bubbles: true }));
  const txt = (id) => document.getElementById(id).textContent;
  const snap = () => JSON.parse(JSON.stringify(window.VEFR_COMBAT));
  const closeNpc = () => { document.getElementById('npc-close').click(); };
  const closeTrade = () => { document.getElementById('trade-close').click(); };
  const words = (prefix) => {
    say(prefix + '-hint', txt('use-hint'));
    say(prefix + '-label', txt('interact-label'));
    say(prefix + '-interact-hidden', document.getElementById('interact').hidden);
    say(prefix + '-interact-disabled', document.getElementById('interact').disabled);
  };
  /* The ring, proved draw-only: force one draw() (the player redraws
     on window resize) with the stroke counter zeroed, then compare
     full snapshots either side. jsdom's stub canvas cannot show pixels,
     so a stroke in the ring's own gold is the proof it drew. */
  const measureRing = async (prefix) => {
    ring.strokes = 0;
    const before = snap();
    window.dispatchEvent(new window.Event('resize'));
    await wait(50);
    say(prefix + '-ring-strokes', ring.strokes);
    say(prefix + '-ring-before', before);
    say(prefix + '-ring-after', snap());
  };
  const close = () => { try { window.close(); } catch (e) { /* already gone */ } };
  const journal = () => JSON.parse(
    window.localStorage.getItem('vefr-packaged-combat') || '[]');
  return { window, document, wait, walk, key, txt, snap,
           closeNpc, closeTrade, words, measureRing, close, journal };
}

try {
  // ---- the boot pin: where the fixture wakes and what it says ----
  {
    const g = await boot();
    say('start-region', g.snap().region);
    say('start-hero', g.snap().hero);
    say('start-gold', g.snap().gold);
    say('start-rat', g.snap().enemies[0]);
    say('start-hint', g.txt('use-hint'));
    say('start-label', g.txt('interact-label'));
    g.close();
  }

  // ---- the resident: four keys talk, then the Talk button and a
  //      canvas click take the same road (regression) ----
  {
    const g = await boot();
    g.walk(TO_RESIDENT);
    say('resident-spot', g.snap().hero.at);
    await g.measureRing('resident');
    for (const [k, name] of KEYS) {
      g.closeNpc();                       // an open box would eat Space
      const before = g.snap();
      g.words('resident-' + name);
      g.key(k);
      await g.wait(150);                  // the offline talk fallback is async
      say('resident-' + name + '-box-hidden',
          g.document.getElementById('npc-box').hidden);
      say('resident-' + name + '-name', g.txt('npc-name'));
      say('resident-' + name + '-line', g.txt('npc-line'));
      say('resident-' + name + '-note', g.txt('npc-note'));
      say('resident-' + name + '-near', g.txt('near'));
      say('resident-' + name + '-hint-after', g.txt('use-hint'));
      say('resident-' + name + '-label-after', g.txt('interact-label'));
      say('resident-' + name + '-snap', g.snap());
      say('resident-' + name + '-snap-before', before);
    }
    // Regression: the Talk button still talks to the same resident.
    g.closeNpc();
    g.document.getElementById('talk').click();
    await g.wait(150);
    say('talkbtn-box-hidden', g.document.getElementById('npc-box').hidden);
    say('talkbtn-name', g.txt('npc-name'));
    say('talkbtn-near', g.txt('near'));
    g.closeNpc();
    // Regression: a canvas click still tries the nearest speaker.
    g.document.getElementById('town-canvas').click();
    await g.wait(150);
    say('canvas-box-hidden', g.document.getElementById('npc-box').hidden);
    say('canvas-name', g.txt('npc-name'));
    say('canvas-near', g.txt('near'));
    g.close();
  }

  // ---- the door: each key walks through to the cellar ----
  for (const [k, name] of KEYS) {
    const g = await boot();
    g.walk(TO_DOOR);
    say('door-' + name + '-spot', g.snap().hero.at);
    g.words('door-' + name);
    g.key(k);
    await g.wait(50);
    say('door-' + name + '-region-after', g.snap().region);
    say('door-' + name + '-hero-after', g.snap().hero.at);
    say('door-' + name + '-hint-after', g.txt('use-hint'));
    say('door-' + name + '-label-after', g.txt('interact-label'));
    g.close();
  }

  // ---- the chest: each key opens the reader and gives the drops ----
  for (const [k, name] of KEYS) {
    const g = await boot();
    g.walk(TO_CHEST);
    say('chest-' + name + '-spot', g.snap().hero.at);
    g.words('chest-' + name);
    g.key(k);
    await g.wait(50);
    say('chest-' + name + '-reader-hidden',
        g.document.getElementById('reader').hidden);
    say('chest-' + name + '-reader-title', g.txt('reader-title'));
    say('chest-' + name + '-bag', g.snap().bag);
    say('chest-' + name + '-near', g.txt('near'));
    say('chest-' + name + '-hint-after', g.txt('use-hint'));
    say('chest-' + name + '-label-after', g.txt('interact-label'));
    g.close();
  }

  // ---- the trader: four keys open the trade panel (closed between
  //      presses), then the Interact button itself (regression) ----
  {
    const g = await boot();
    g.walk(TO_TRADER);
    say('trader-spot', g.snap().hero.at);
    for (const [k, name] of KEYS) {
      g.closeTrade();                     // an open panel would eat the keys
      const before = g.snap();
      g.words('trader-' + name);
      g.key(k);
      await g.wait(50);
      say('trader-' + name + '-trade-hidden',
        g.document.getElementById('trade').hidden);
      say('trader-' + name + '-trade-title', g.txt('trade-title'));
      say('trader-' + name + '-hint-after', g.txt('use-hint'));
      say('trader-' + name + '-label-after', g.txt('interact-label'));
      say('trader-' + name + '-snap', g.snap());
      say('trader-' + name + '-snap-before', before);
    }
    // Regression: the #interact button still opens the trade panel.
    g.closeTrade();
    g.words('inttrade');                    // hint/label before the click
    g.document.getElementById('interact').click();
    await g.wait(50);
    say('inttrade-trade-hidden', g.document.getElementById('trade').hidden);
    say('inttrade-trade-title', g.txt('trade-title'));
    g.close();
  }

  // ---- nothing in reach: the nudge, the dim, and NOT ONE turn ----
  {
    const g = await boot();
    g.walk(TO_EMPTY);
    say('empty-spot', g.snap().hero.at);
    say('empty-hint', g.txt('use-hint'));
    say('empty-label', g.txt('interact-label'));
    say('empty-interact-hidden', g.document.getElementById('interact').hidden);
    say('empty-interact-disabled',
        g.document.getElementById('interact').disabled);
    say('empty-dim',
        g.document.getElementById('interact').classList.contains('gbtn--dim'));
    say('empty-near-before', g.txt('near'));
    const before = g.snap();
    await g.measureRing('empty');
    for (const [k, name] of KEYS) {
      g.key(k);
      await g.wait(50);
      say('empty-' + name + '-near', g.txt('near'));
      say('empty-' + name + '-hint', g.txt('use-hint'));
      say('empty-' + name + '-label', g.txt('interact-label'));
      say('empty-' + name + '-dim',
          g.document.getElementById('interact').classList.contains('gbtn--dim'));
      say('empty-' + name + '-snap', g.snap());
      say('empty-' + name + '-snap-before', before);
    }
    g.close();
  }

  // ---- regression: #interact still goes through a door ----
  {
    const g = await boot();
    g.walk(TO_DOOR);
    g.words('intdoor');
    g.document.getElementById('interact').click();
    await g.wait(50);
    say('intdoor-region-after', g.snap().region);
    say('intdoor-hero-after', g.snap().hero.at);
    g.close();
  }

  // ---- regression: #interact still opens a chest ----
  {
    const g = await boot();
    g.walk(TO_CHEST);
    g.words('intchest');
    g.document.getElementById('interact').click();
    await g.wait(50);
    say('intchest-reader-hidden', g.document.getElementById('reader').hidden);
    say('intchest-reader-title', g.txt('reader-title'));
    say('intchest-bag', g.snap().bag);
    g.close();
  }

  // ---- regression: a bump still strikes, and the rat answers ----
  {
    const g = await boot();
    say('bump-before', g.snap());
    g.key('ArrowRight');                 // arrow-key bump, not the dpad
    await g.wait(50);
    say('bump-after', g.snap());
    say('bump-said', g.txt('combat-live'));
    g.close();
  }

  // ---- regression: one arrow press moves exactly one tile ----
  {
    const g = await boot();
    say('arrow-before', g.snap());
    g.key('ArrowDown');
    await g.wait(50);
    say('arrow-after', g.snap());
    g.close();
  }

  // ---- combat folds into Interact: the enemy menu, a strike, a
  //      console verb, a one-verb surface, and a bump that closes it ----
  {
    const g = await boot();
    say('enemy-start-hint', g.txt('use-hint'));
    say('enemy-start-label', g.txt('interact-label'));
    say('enemy-start-row-label',
        g.document.getElementById('verb-row').getAttribute('aria-label'));
    say('enemy-verbs',
        [...g.document.querySelectorAll('#verb-row button')]
          .map((b) => b.querySelector('.verb').textContent));
    say('enemy-verb-keys',
        [...g.document.querySelectorAll('#verb-row button kbd')]
          .map((k) => k.textContent));
    const before = g.snap();
    g.key('e');                                   // open the enemy menu
    await g.wait(50);
    say('enemy-open-row-label',
        g.document.getElementById('verb-row').getAttribute('aria-label'));
    say('enemy-open-snap', g.snap());
    say('enemy-open-snap-before', before);
    const strike = [...g.document.querySelectorAll('#verb-row button')]
      .find((b) => b.dataset.verb === 'attack');
    strike.click();                               // strike resolves, turn runs
    await g.wait(50);
    say('enemy-strike-snap', g.snap());
    say('enemy-strike-said', g.txt('combat-live'));
    say('enemy-strike-row-label',
        g.document.getElementById('verb-row').getAttribute('aria-label'));
    // Console: words only, no damage - but still a turn. Wait out the
    // button's own 400 ms disable window before opening again.
    await g.wait(450);
    g.key('e');
    await g.wait(50);
    const consoleBtn = [...g.document.querySelectorAll('#verb-row button')]
      .find((b) => b.dataset.verb === 'console');
    consoleBtn.click();
    await g.wait(50);
    say('enemy-console-snap', g.snap());
    say('enemy-console-said', g.txt('combat-live'));
    say('enemy-console-verb', g.journal().slice(-1)[0].verb);
    say('enemy-console-row-label',
        g.document.getElementById('verb-row').getAttribute('aria-label'));
    g.close();
  }

  // ---- a one-verb surface acts at once, with no menu opened ----
  {
    const g = await boot();
    g.window.VEFR_WORLD.acts[0].verbs = ['console'];   // exactly one verb
    say('oneverb-start-hp', g.snap().hero.hp);
    say('oneverb-start-rat', g.snap().enemies[0].hp);
    g.key('e');
    await g.wait(50);
    say('oneverb-row-label',
        g.document.getElementById('verb-row').getAttribute('aria-label'));
    say('oneverb-verb', g.journal().slice(-1)[0].verb);
    say('oneverb-snap', g.snap());
    say('oneverb-said', g.txt('combat-live'));
    g.close();
  }

  // ---- a bump closes an open enemy menu (and still strikes) ----
  {
    const g = await boot();
    g.key('e');                                   // open the enemy menu
    await g.wait(50);
    say('bumpclose-open-row-label',
        g.document.getElementById('verb-row').getAttribute('aria-label'));
    g.key('ArrowRight');                          // bump the sleeping rat
    await g.wait(50);
    say('bumpclose-row-label',
        g.document.getElementById('verb-row').getAttribute('aria-label'));
    say('bumpclose-snap', g.snap());
    g.close();
  }
} catch (e) {
  say('HARNESS-ERROR', String((e && e.message) || e));
}

process.stdout.write(JSON.stringify({
  log,
  setIntervalInTemplate: html.includes('setInterval'),
}, null, 1));
