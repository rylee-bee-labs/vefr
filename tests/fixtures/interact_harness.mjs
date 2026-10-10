/* Interact harness: executes the REAL window.interactTargets /
   window.pickTarget / window.labelFor helpers extracted from
   web/packaged.html between their own marker comments, inside a node
   vm sandbox with no npm packages and no jsdom (the block is pure,
   so the sandbox needs nothing but Math). It then drives every case
   from the Task 1 brief and prints one JSON report to stdout.

   Every expected value in here is pinned literally - the harness
   calls the helpers only to check them, never to compute an
   expectation, so the test file has nothing to guess at. It throws on
   a missing marker, on a block that never defines the three
   functions, on any disagreement with a pinned value, and on any
   mutation of a state object (a JSON snapshot is taken before and
   after every call).

   Usage: node interact_harness.mjs <path/to/packaged.html> */
import fs from 'node:fs';
import vm from 'node:vm';

const htmlPath = process.argv[2];
if (!htmlPath) throw new Error('usage: interact_harness.mjs <packaged.html>');
const html = fs.readFileSync(htmlPath, 'utf8');

const start = html.indexOf('// -- interact start --');
const end = html.indexOf('// -- interact end --');
if (start === -1 || end === -1 || end < start) {
  throw new Error('interact markers not found in ' + htmlPath);
}
const code = html.slice(start, end);

const ctx = { Math };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(code, ctx, { timeout: 5000 });
for (const fn of ['interactTargets', 'pickTarget', 'labelFor']) {
  if (typeof ctx[fn] !== 'function') {
    throw new Error('the extracted block did not define ' + fn);
  }
}

/* ---- assertion plumbing ---- */
const report = {};
function pin(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    throw new Error(name + ':\n  expected ' + e + '\n  actual   ' + a);
  }
  report[name] = actual;
}

/* Every call runs between JSON snapshots of the state it was handed:
   the block must never mutate what it reads. */
function call(fn, state) {
  const before = JSON.stringify(state);
  const out = fn(state);
  if (JSON.stringify(state) !== before) {
    throw new Error('mutated state: ' + JSON.stringify(state));
  }
  return out;
}

const { interactTargets, pickTarget, labelFor } = ctx;
const run = (state) => ({
  targets: call(interactTargets, state),
  pick: call(pickTarget, state),
});

/* Builders: candidates and states written out short so every id and
   name below stays a literal in the expectations. */
const c = (kind, id, name, x, y) => ({ kind, id, name, at: [x, y] });
const st = (hero, facing, candidates) => ({ hero, facing, candidates });

/* ---- 1. facing-first ---- */
/* A chest on the facing tile beats a nearer chest on the hero's own
   tile and beats a resident standing beside the hero. */
const facingFirst = run(st([5, 5], 'up', [
  c('chest', 'bk-face', 'the oak chest', 5, 4),
  c('chest', 'bk-here', 'the brass chest', 5, 5),
  c('resident', 'sp-ada', 'Ada', 4, 5),
]));
pin('facingFirstTargets', facingFirst.targets, [
  { kind: 'chest', id: 'bk-face', name: 'the oak chest', at: [5, 4], dist: 1,
    label: 'Open the chest' },
  { kind: 'chest', id: 'bk-here', name: 'the brass chest', at: [5, 5], dist: 0,
    label: 'Open the chest' },
  { kind: 'resident', id: 'sp-ada', name: 'Ada', at: [4, 5], dist: 1,
    label: 'Talk to Ada' },
]);
pin('facingFirstPick', facingFirst.pick,
  { kind: 'chest', id: 'bk-face', name: 'the oak chest', at: [5, 4], dist: 1,
    label: 'Open the chest' });

/* ---- 2. own tile ---- */
/* Nothing on the facing tile: the chest under the hero beats the
   resident one tile away. */
const ownTile = run(st([5, 5], 'up', [
  c('resident', 'sp-ada', 'Ada', 6, 5),
  c('chest', 'bk-here', 'the brass chest', 5, 5),
]));
pin('ownTileTargets', ownTile.targets, [
  { kind: 'resident', id: 'sp-ada', name: 'Ada', at: [6, 5], dist: 1,
    label: 'Talk to Ada' },
  { kind: 'chest', id: 'bk-here', name: 'the brass chest', at: [5, 5], dist: 0,
    label: 'Open the chest' },
]);
pin('ownTilePick', ownTile.pick,
  { kind: 'chest', id: 'bk-here', name: 'the brass chest', at: [5, 5], dist: 0,
    label: 'Open the chest' });

/* ---- 3. nearest fallback ---- */
/* Facing tile and own tile are empty: the enemy one tile away beats
   the trader two tiles away. */
const nearest = run(st([5, 5], 'up', [
  c('trader', 'tr-bram', 'Bram', 5, 7),
  c('enemy', 'e-rat', 'the cellar rat', 5, 6),
]));
pin('nearestTargets', nearest.targets, [
  { kind: 'trader', id: 'tr-bram', name: 'Bram', at: [5, 7], dist: 2,
    label: 'Trade with Bram' },
  { kind: 'enemy', id: 'e-rat', name: 'the cellar rat', at: [5, 6], dist: 1,
    label: 'Fight the cellar rat' },
]);
pin('nearestPick', nearest.pick,
  { kind: 'enemy', id: 'e-rat', name: 'the cellar rat', at: [5, 6], dist: 1,
    label: 'Fight the cellar rat' });

/* ---- 4. tie order ---- */
/* Every adjacent pair of the kind list, staged as two candidates one
   tile either side of the hero (both in reach, both off the facing
   and own tiles, so only the kind rank can decide). Each pair runs
   in both list orders: door/ stairs share a rank so the candidate
   LIST decides; every other pair is decided by the kind rank
   whichever way it is listed. All expectations literal. */
function tieAdj(a, b) {
  return run(st([5, 5], 'up', [
    { kind: a.kind, id: a.id, name: a.name, at: [4, 5] },
    { kind: b.kind, id: b.id, name: b.name, at: [6, 5] },
  ]));
}
const DOOR = { kind: 'door', id: 't-cellar', name: 'the cellar door' };
const STAIRS = { kind: 'stairs', id: 't-down', name: 'the way down' };
const CHEST = { kind: 'chest', id: 'bk-oak', name: 'the oak chest' };
const TRADER = { kind: 'trader', id: 'tr-bram', name: 'Bram' };
const IDENTIFIER = { kind: 'identifier', id: 'id-wren', name: 'Wren' };
const RESIDENT = { kind: 'resident', id: 'sp-ada', name: 'Ada' };
const PLACE = { kind: 'place', id: 'poi-well', name: 'the old well' };
const ENEMY = { kind: 'enemy', id: 'e-rat', name: 'the cellar rat' };

/* The winner's target, fully literal: caller lists the winner first
   at [4, 5], so the winner sits there. */
const win4 = (k, label) => ({ kind: k.kind, id: k.id, name: k.name,
  at: [4, 5], dist: 1, label });
const win6 = (k, label) => ({ kind: k.kind, id: k.id, name: k.name,
  at: [6, 5], dist: 1, label });

/* door vs stairs: equal rank, list order decides. */
pin('tieDoorFirst', tieAdj(DOOR, STAIRS).pick,
  win4(DOOR, 'Go through the door'));
pin('tieStairsFirst', tieAdj(STAIRS, DOOR).pick,
  win4(STAIRS, 'Go down the stairs'));
/* stairs vs chest */
pin('tieStairsThenChest', tieAdj(STAIRS, CHEST).pick,
  win4(STAIRS, 'Go down the stairs'));
pin('tieChestThenStairs', tieAdj(CHEST, STAIRS).pick,
  win6(STAIRS, 'Go down the stairs'));
/* chest vs trader */
pin('tieChestThenTrader', tieAdj(CHEST, TRADER).pick,
  win4(CHEST, 'Open the chest'));
pin('tieTraderThenChest', tieAdj(TRADER, CHEST).pick,
  win6(CHEST, 'Open the chest'));
/* trader vs resident */
pin('tieTraderThenResident', tieAdj(TRADER, RESIDENT).pick,
  win4(TRADER, 'Trade with Bram'));
pin('tieResidentThenTrader', tieAdj(RESIDENT, TRADER).pick,
  win6(TRADER, 'Trade with Bram'));
/* trader vs identifier: the two town services rank as one pair, the
   shopkeeper first because he was first. */
pin('tieTraderThenIdentifier', tieAdj(TRADER, IDENTIFIER).pick,
  win4(TRADER, 'Trade with Bram'));
pin('tieIdentifierThenTrader', tieAdj(IDENTIFIER, TRADER).pick,
  win6(TRADER, 'Trade with Bram'));
/* identifier vs resident: a reader opens their panel, not their talk,
   exactly as a shopkeeper does. */
pin('tieIdentifierThenResident', tieAdj(IDENTIFIER, RESIDENT).pick,
  win4(IDENTIFIER, 'Ask Wren to read things'));
pin('tieResidentThenIdentifier', tieAdj(RESIDENT, IDENTIFIER).pick,
  win6(IDENTIFIER, 'Ask Wren to read things'));
/* resident vs place */
pin('tieResidentThenPlace', tieAdj(RESIDENT, PLACE).pick,
  win4(RESIDENT, 'Talk to Ada'));
pin('tiePlaceThenResident', tieAdj(PLACE, RESIDENT).pick,
  win6(RESIDENT, 'Talk to Ada'));
/* place vs enemy */
pin('tiePlaceThenEnemy', tieAdj(PLACE, ENEMY).pick,
  win4(PLACE, 'Look at the old well'));
pin('tieEnemyThenPlace', tieAdj(ENEMY, PLACE).pick,
  win6(PLACE, 'Look at the old well'));

/* ---- 5. reach ---- */
/* A chest 2 tiles away is out; a resident 2 tiles away is in; a
   resident 3 tiles away is out. People reach 2, things reach 1. */
const reachChest = run(st([5, 5], 'up', [c('chest', 'bk-far', 'far chest', 7, 5)]));
pin('reachChestTargets', reachChest.targets, []);
pin('reachChestPick', reachChest.pick, null);

const reachRes2 = run(st([5, 5], 'up', [c('resident', 'sp-two', 'Toki', 7, 5)]));
pin('reachResident2Targets', reachRes2.targets, [
  { kind: 'resident', id: 'sp-two', name: 'Toki', at: [7, 5], dist: 2,
    label: 'Talk to Toki' },
]);
pin('reachResident2Pick', reachRes2.pick,
  { kind: 'resident', id: 'sp-two', name: 'Toki', at: [7, 5], dist: 2,
    label: 'Talk to Toki' });

const reachRes3 = run(st([5, 5], 'up', [c('resident', 'sp-three', 'Ulf', 8, 5)]));
pin('reachResident3Targets', reachRes3.targets, []);
pin('reachResident3Pick', reachRes3.pick, null);

/* A reader is a person: the same reach a shopkeeper and a resident
   have, two tiles. */
const reachId2 = run(st([5, 5], 'up', [c('identifier', 'id-two', 'Wren', 7, 5)]));
pin('reachIdentifier2Targets', reachId2.targets, [
  { kind: 'identifier', id: 'id-two', name: 'Wren', at: [7, 5], dist: 2,
    label: 'Ask Wren to read things' },
]);
pin('reachIdentifier2Pick', reachId2.pick,
  { kind: 'identifier', id: 'id-two', name: 'Wren', at: [7, 5], dist: 2,
    label: 'Ask Wren to read things' });

const reachId3 = run(st([5, 5], 'up', [c('identifier', 'id-three', 'Wren', 8, 5)]));
pin('reachIdentifier3Targets', reachId3.targets, []);
pin('reachIdentifier3Pick', reachId3.pick, null);

/* ---- 6. nothing in reach ---- */
const nothing = run(st([5, 5], 'up', []));
pin('nothingTargets', nothing.targets, []);
pin('nothingPick', nothing.pick, null);
pin('nothingLabel', labelFor(nothing.pick), null);

/* ---- 7. all eight labels, plus null and absent ---- */
pin('labelChest', labelFor({ kind: 'chest', name: 'x' }), 'Open the chest');
pin('labelResident', labelFor({ kind: 'resident', name: 'Ada' }), 'Talk to Ada');
pin('labelTrader', labelFor({ kind: 'trader', name: 'Bram' }), 'Trade with Bram');
pin('labelIdentifier', labelFor({ kind: 'identifier', name: 'Wren' }), 'Ask Wren to read things');
pin('labelDoor', labelFor({ kind: 'door', name: 'x' }), 'Go through the door');
pin('labelStairs', labelFor({ kind: 'stairs', name: 'x' }), 'Go down the stairs');
pin('labelStairsUp', labelFor({ kind: 'stairs', name: 'the stair up' }), 'Go up the stairs');
pin('labelStairsDown', labelFor({ kind: 'stairs', name: 'the stair down' }), 'Go down the stairs');
pin('labelPlace', labelFor({ kind: 'place', name: 'the old well' }),
  'Look at the old well');
pin('labelEnemy', labelFor({ kind: 'enemy', name: 'the cellar rat' }),
  'Fight the cellar rat');
pin('labelNull', labelFor(null), null);
pin('labelAbsent', labelFor(undefined), null);

/* ---- 8. malformed candidates are skipped, never an error ---- */
const malformed = run(st([5, 5], 'up', [
  null,
  7,
  { id: 'no-kind', name: 'Ghost', at: [5, 5] },
  { kind: 'goblin', id: 'bad-kind', name: 'Goblin', at: [5, 5] },
  { kind: 'chest', id: 'no-at', name: 'No At' },
  { kind: 'chest', id: 'short-at', name: 'Short At', at: [5] },
  { kind: 'chest', id: 'string-at', name: 'String At', at: '5,5' },
  { kind: 'chest', id: 'nan-at', name: 'NaN At', at: ['5', 5] },
  c('chest', 'bk-good', 'the good chest', 5, 5),
]));
pin('malformedTargets', malformed.targets, [
  { kind: 'chest', id: 'bk-good', name: 'the good chest', at: [5, 5], dist: 0,
    label: 'Open the chest' },
]);
pin('malformedPick', malformed.pick,
  { kind: 'chest', id: 'bk-good', name: 'the good chest', at: [5, 5], dist: 0,
    label: 'Open the chest' });

/* ---- 9. no mutation, fresh objects ---- */
/* `call` snapshot-checked every invocation above. Now prove the
   targets are fresh: clobbering a returned target must not change
   what the next call returns, and must not change the state. */
const pureState = st([5, 5], 'up', [
  c('chest', 'bk-pure', 'the chest', 5, 4),
  c('resident', 'sp-ada', 'Ada', 4, 5),
]);
const first = call(interactTargets, pureState);
const firstCopy = JSON.parse(JSON.stringify(first));
first[0].label = 'CLOBBERED';
first[0].at[0] = 99;
delete first[1];
const second = call(interactTargets, pureState);
pin('targetsStayFresh', second, firstCopy);
pin('stateUntouched', JSON.parse(JSON.stringify(pureState)),
  st([5, 5], 'up', [
    c('chest', 'bk-pure', 'the chest', 5, 4),
    c('resident', 'sp-ada', 'Ada', 4, 5),
  ]));
const pickA = call(pickTarget, pureState);
const pickB = call(pickTarget, pureState);
pin('picksStayFresh', pickA, pickB);
if (pickA === pickB) throw new Error('pickTarget returned a shared object');

report.ok = true;
process.stdout.write(JSON.stringify(report));
