/* Player words harness: executes the REAL message table and its one
   reader (VEFR_PLAYER_WORDS / playerWord) extracted from
   web/packaged.html between their own marker comments, inside a node vm
   sandbox with no npm packages and no jsdom (the block reads one
   global, window.VEFR_WORLD, and nothing else).

   The pack under test arrives as JSON on argv and is put on
   window.VEFR_WORLD.player_words exactly as the weave would. Three
   cases, one run each, and every expected value pinned literally - the
   harness calls playerWord only to check what it returns, never to
   compute an expectation. It throws on a missing marker, on a block
   that never defines the reader, and on any disagreement.

     silent    - a pack that names none: the engine's own wording, byte
                 for byte what the player read before the table existed
                 (vefr #259's "To reach floor-1, go north-west")
     override  - a pack that names its own word for two of the four
                 where-next lines and for the strike hint
     unusable  - a pack whose words are not words (blank, not a
                 string): the engine's line stands in

   Usage: node player_words_harness.mjs <packaged.html> <case> '<pack words json>' */
import fs from 'node:fs';
import vm from 'node:vm';

const htmlPath = process.argv[2];
const which = process.argv[3];
const packWords = JSON.parse(process.argv[4] || '{}');
if (!htmlPath || !which) {
  throw new Error('usage: player_words_harness.mjs <packaged.html> <case> [json]');
}
const html = fs.readFileSync(htmlPath, 'utf8');

const start = html.indexOf('// -- player words start --');
const end = html.indexOf('// -- player words end --');
if (start === -1 || end === -1 || end < start) {
  throw new Error('player words markers not found in ' + htmlPath);
}
const code = html.slice(start, end);

const ctx = { window: { VEFR_WORLD: { name: 'a-pack', player_words: packWords } } };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(code, ctx, { timeout: 5000 });
if (typeof ctx.playerWord !== 'function') {
  throw new Error('the extracted block did not define playerWord');
}
const table = ctx.VEFR_PLAYER_WORDS;
const playerWord = ctx.playerWord;

/* ---- assertion plumbing ---- */
const report = { case: which };
function pin(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    throw new Error(name + ':\n  expected ' + e + '\n  actual   ' + a);
  }
  report[name] = actual;
}

/* The table is the action-critical lines, and only those: the four
   where-next hints and the strike hint (vefr #464). */
pin('tableKeys', Object.keys(table).sort(), [
  'combat.walk_to_strike', 'where_next.goal', 'where_next.here',
  'where_next.no_way', 'where_next.reach',
]);

if (which === 'silent') {
  pin('goal', playerWord('where_next.goal', { place: 'floor-1' }),
    'To reach floor-1.');
  pin('reach', playerWord('where_next.reach',
    { place: 'floor-1', direction: 'north-west' }),
    'To reach floor-1, go north-west.');
  pin('here', playerWord('where_next.here', { place: 'floor-1' }),
    'The way to floor-1 is right here.');
  pin('noWay', playerWord('where_next.no_way', { place: 'floor-1' }),
    'No way to floor-1 is declared from here.');
  /* The one row with no slot to fill: the engine's own sentence. */
  pin('strike', playerWord('combat.walk_to_strike'),
    'Walk into an enemy to strike it.');
} else if (which === 'override') {
  pin('reach', playerWord('where_next.reach',
    { place: 'the stair down', direction: 'north-west' }),
    'To get to the stair down, head north-west.');
  pin('goal', playerWord('where_next.goal', { place: 'the stair down' }),
    'The way on is the stair down.');
  pin('strike', playerWord('combat.walk_to_strike'),
    'Walk into a monster to hit it.');
  /* Only the keys the pack named change: its neighbours keep the
     engine's words. */
  pin('here', playerWord('where_next.here', { place: 'floor-1' }),
    'The way to floor-1 is right here.');
  pin('noWay', playerWord('where_next.no_way', { place: 'floor-1' }),
    'No way to floor-1 is declared from here.');
} else if (which === 'unusable') {
  pin('blank', playerWord('where_next.goal', { place: 'floor-1' }),
    'To reach floor-1.');
  pin('notAString', playerWord('where_next.reach',
    { place: 'floor-1', direction: 'north-west' }),
    'To reach floor-1, go north-west.');
  pin('blankHint', playerWord('combat.walk_to_strike'),
    'Walk into an enemy to strike it.');
} else {
  throw new Error('unknown case: ' + which);
}

/* Either way: a key the table does not have falls back to the key
   itself, never to undefined and never to a crash; and a slot with
   nothing to fill it stays as written rather than printing
   "undefined" at a player. */
pin('unknownKey', playerWord('where_next.nope', { place: 'floor-1' }),
  'where_next.nope');
pin('unfilledSlot', playerWord('where_next.reach', { place: 'floor-1' }),
  which === 'override'
    ? 'To get to floor-1, head {direction}.'
    : 'To reach floor-1, go {direction}.');

report.ok = true;
process.stdout.write(JSON.stringify(report));