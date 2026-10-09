// -- delve v3 start --
// delve v3: the JavaScript twin of Python's `src/vefr/delve_v3.py`.
//
// PLAN.md section 2 is the contract. `delve_v3.py` is the SPEC - it serves
// `vefr check` and the property sweeps - and this part is the RUNTIME: the
// same five stages, in the same order, drawing the same numbers from the same
// seeds, so a floor is the same floor in either language. The parity harness
// (tests/fixtures/floor_v3_parity_harness.mjs, and the Chromium path in
// tests/browser/test_floor_v3_parity.py) runs this exact text inside the real
// woven player and demands the same canonical JSON Python produces, stage by
// stage, over 200 seeds x every size x every floor kind.
//
// Pure logic only: no DOM, no clock, no global random, no storage, no
// network, no globals. The only randomness is `VEFR_DELVE.prng` from part 390, and the
// only float consumed from it is `Math.floor(rng() * n)` with `0 <= n < 2^31`
// (or the one `rng() < 0.5` comparison `_link` makes). Every set is walked
// through a sorted array, every sort breaks its ties, and every list is an
// array - PLAN.md section 2's determinism rule, obeyed in the shape of the
// code rather than in a comment about it. A draw is spelled with its call
// parentheses in the code and without them in the comments, because the parity
// test reads every line of this part - comments included - and holds each one
// to one of the three draw shapes.
//
// THE PORTING TABLE. Stage by stage, the spec's function beside this part's.
//
//   stage    the spec (delve_v3.py)             this part            state
//   -------- ----------------------------------- ------------------- --------
//   read     _rand, _pick                        rand, pick          done
//            _pair, _demand, _names              pairOf, demandOf,   done
//                                                namesOf
//            _read_rooms                         readRooms           done
//            _read_families                      readFamilies        done
//            _read_elites                        readElites          done
//            _read_groups                        readGroups          done
//            _draw_family                        drawFamily          done
//            _read_size                          readSize            done
//   1 plan   _plan_stage (draws 1-5)             planStage           done
//   2 layout Canvas                              makeCanvas          done
//            _overlaps, _center                  overlaps, center    done
//            _fits, _fits_stamp                  fits, fitsStamp     done
//            _link                               link                done
//            _gallery_loop                       galleryLoop         done
//            _child_rows, _far_rows              childRows,          done
//                                                farRowsFor
//            _layout_stage (draws 1-7)           layoutStage         done
//            _child_gallery                      childGallery        done
//            stamps.orient                       stampOrient         done
//            stamps.orientations                 stampOrientations   done
//            stamps.sockets                      stampSockets        done
//            stamps.anchors                      stampAnchors        done
//            _stamp_pool                         stampPool           done
//            _stamp_slots                        stampSlots          done
//            _weighted_stamp                     weightedStamp       done
//            _nearest_walkable                   nearestWalkable     done
//            _span, _bends                       span, bends         done
//            _stamp_route, _route_clear          stampRoute,         done
//                                                routeClear
//            _lay_stamp                          layStamp            done
//            _try_stamp                          tryStamp            done
//            _ordered_spots                      orderedSpots        done
//            _pin_spots                          pinSpots            done
//            _faces_centre                       facesCentre         done
//            _pin_stamp                          pinStamp            done
//            _stamp_stage                        stampStage          done
//   3 graph  _bfs_path                           bfsPath             done
//            _bfs_depth                          bfsDepth            done
//            _region_graph                       regionGraph         done
//            _room_graph                         roomGraphOf         done
//            _stand_in                           standIn             done
//            _stamped                            stamped             done
//            _graph_stage (no draws)             graphStage          done
//            _at_of                              atOf                done
//   4 pop    _eligible                           eligible            done
//            _key_salt, _tile_rank, _spread      keySalt, tileRank,  done
//                                                spread
//            _stamp_free                         stampFree           done
//            _neighbourhood                      neighbourhood       done
//            _corridor_regions                   corridorRegions     done
//            _same_region                        sameRegion          done
//            _pop_stage (draws 1-4)              popStage            done
//   5 door   _flood                              flood               done
//            _chest_value                        chestValue          done
//            _loops, _within_one_step            loopCount,          done
//                                                withinOneStep
//            _validate                           validateFloor       done
//            _attempt                            v3Attempt           done
//            _fallback                           fallback            done
//            _read_rectangles, _find             readRectangles,     done
//                                                findGlyph
//            generate_floor_v3                   generateFloorV3     done
//
// E5b's JS half landed here: `vefr.stamps` places stamped rooms in the spec
// and the runtime has to place the same one, so the reader's orient,
// orientations, sockets and anchors are in this part too. They draw nothing -
// a stamp is placed by the layout stream, and these are its geometry.
//
// STAGE ORDER IS FIXED: plan, layout, graph (no draws), pop, validate. Each
// stage that draws takes every one of its numbers from its own stream, named
// `v3|<floor key>|<stage>`, so a rewritten affix table can never move a wall
// (PLAN.md section 2's sub-seed rule).
(function () {
  var D = window.VEFR_DELVE;   // prng and generateFloorV2 from part 390

  // ---------------------------------------------------------- the constants
  // Every number the spec names, one list, read by the parity test out of
  // `VEFR_DELVE.v3Constants` and compared with the spec's. Two languages, one
  // set of constants: a twin that quietly agreed on 39 ms and 41 ms is not a
  // twin.
  var WALL = '#';
  var FLOOR = '.';
  var UP = 'u';
  var DOWN = 'd';

  // The floor kinds the endless dungeon knows. A v3 floor is one of these.
  var FLOOR_KINDS = ['normal', 'treasure', 'infested', 'hub'];

  // How many times stage 5 may retry a floor before the caller gets v2
  // geometry. PLAN.md section 2 caps the fallback rate at 0.5%.
  var MAX_TRIES = 8;

  // How many spine chords a floor may close; one chord is already three
  // cycles and validate wants at least two.
  var LOOPS_MIN = 2;
  var LOOPS_MAX = 3;

  // Rooms a v3 floor keeps. Below this the retry ladder tries again and v2
  // geometry is the last answer.
  var ROOMS_FLOOR = 6;

  // The pop stage's own spacing rule: a monster, a chest or a secret stands at
  // least this many tiles (Chebyshev) from both stairs.
  var STAIR_CLEAR = 7;

  // One floor tile this many times is one monster slot, before the clamps.
  // MOBS_MAX is both the top of the budget clamp and ADR 0014's hard cap,
  // and it is a third thing: the top of the range `shapes.SECTION`'s `mobs`
  // key is held to, so a count past it is refused by `vefr check` rather
  // than clamped in silence.
  var TILES_PER_MOB = 30;
  var MOBS_MIN = 4;
  var MOBS_MAX = 36;

  // The floors a `mobs` count may name, the range `floors` itself is held to.
  // The twin of `vefr.sections.MOB_FLOOR_MAX`.
  var MOB_FLOOR_MAX = 99;

  // ADR 0014's hard caps, applied AFTER the omens would be. A cap that is hit
  // stops further draws of that kind; it neither raises nor fails the floor.
  var LONE_ELITES_MAX = 2;
  var GROUPS_MAX = 3;
  var GROUP_MEMBERS_MAX = 4;
  var ROOMS_PER_ELITE_GROUP = 8;

  // The two room shapes the graph stage names a stamp room by, in
  // rooms[i][4]: the warden's hall and the vault.
  var STAMP_ROOMS = ['hall', 'vault'];

  // How far a minion stands from its leader, Chebyshev (ADR 0014).
  var MINION_REACH = 2;

  // The closed range a Section's `groups.leash` may write, and what a group
  // walks on when the Section names none. Part 420 names these three too.
  var LEASH_MIN = 3;
  var LEASH_MAX = 12;
  var LEASH_DEFAULT = 6;

  // Chest tables: ids, never amounts. The value is `section.chest_values[t]`.
  var CHEST_TABLES = ['t1', 't2'];

  // The room shape menu a room draws from: Brogue's, trimmed.
  var SHAPES = ['cell', 'closet', 'den', 'nook'];

  // The names a point of interest falls back on when the pack names none.
  var FALLBACK_POIS = ['the drowned well', 'the ash alcove', 'the rusted grate'];

  // The packs of a floor that are not a Section pack, defaulted here, so a
  // missing key never raises.
  var DEFAULT_ROOMS = [12, 12];
  var DEFAULT_FAMILIES = [{ family: 'rat', weight: 1 }];
  var DEFAULT_ELITES = { perFloor: [0, 0], affixes: [] };
  var DEFAULT_GROUPS = { perFloor: [0, 0], minions: [2, 3], leader: 'normal',
                         sameFamily: true };

  // The plan stage's fifth draw: which quarter of the pack's names becomes this
  // floor's landmark.
  var FLAVOURS = 4;

  // How many carved tiles a socket's corridor may end on, tried nearest first.
  var STAMP_ROUTE_ENDS = 4;

  // ADR 0013's reader, in the part of it placement needs.
  var STAMP_ATTEMPTS = 24;
  var STAMP_ANY_TAG = 'any';
  var STAMP_REQUIRED_ROLES = ['warden-hall', 'vault', 'landmark'];
  var STAMP_STEPS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  var STAMP_STANDING = '.ABCDEFGHIJKLMNOPQRSTUVWXYZ';

  // The two required roles ADR 0013 names a position for, in the order it
  // names them. Only the last try uses them.
  var PINNED_ROLES = ['warden-hall', 'vault'];

  // ----------------------------------------------------------------- drawing
  // `rand(lo, hi)` is `lo + floor(rng * (hi - lo + 1))` and `pick(n)` is
  // `floor(rng * n)`, which is `delve_v3._rand` and `delve_v3._pick` written
  // out so this part has one place to read them.

  function rand(rng, lo, hi) {
    return lo + Math.floor(rng() * (hi - lo + 1));
  }

  function pick(rng, count) {
    return Math.floor(rng() * count);
  }

  // Python's `int()` on a JSON value: a whole number truncates, a numeric
  // string parses, anything else is the caller's fallback. The spec's readers
  // lean on this - `int(item.get("weight", 1))` inside a `try` is how a
  // malformed affix table becomes a weight of 1 rather than a crash.
  function toInt(value, fallback) {
    if (typeof value === 'number') {
      return isFinite(value) ? Math.trunc(value) : fallback;
    }
    if (typeof value === 'string' && /^[+-]?[0-9]+$/.test(value.trim())) {
      return parseInt(value.trim(), 10);
    }
    return fallback;
  }

  // A `[lo, hi]` pair of whole numbers, sorted, or `fallback`. The low bound
  // is interchangeable with the high one here: a room quota, a minion count.
  function pairOf(value, fallback) {
    if (!Array.isArray(value) || value.length !== 2) return fallback;
    var lo = toInt(value[0], null);
    var hi = toInt(value[1], null);
    if (lo === null || hi === null) return fallback;
    return lo <= hi ? [lo, hi] : [hi, lo];
  }

  // The same read for a COUNT, and a different rule: a reversed count resolves
  // to its low bound, because a count's low bound is what the Section ASKS
  // for. ADR 0014's elite-led-group cap is phrased off that low bound, so a
  // draw that did not honour it is a cap that is never reached.
  function demandOf(value, fallback) {
    if (!Array.isArray(value) || value.length !== 2) return fallback;
    var lo = toInt(value[0], null);
    var hi = toInt(value[1], null);
    if (lo === null || hi === null) return fallback;
    return lo <= hi ? [lo, hi] : [lo, lo];
  }

  // A list of non-empty strings, or `fallback` when it is not one.
  function namesOf(value, fallback) {
    if (Array.isArray(value)) {
      var names = [];
      for (var i = 0; i < value.length; i++) {
        var name = String(value[i]);
        if (name) names.push(name);
      }
      if (names.length) return names;
    }
    return fallback.slice();
  }

  // ---------------------------------------------------------- pack reading
  // Every accessor defaults, because PLAN.md section 2 says only `id`,
  // `rooms`, `families`, `elites`, `groups` and `pois` are required and a
  // missing key must never raise.

  // The room quota range of a Section pack.
  function readRooms(section) {
    return pairOf(section.rooms, DEFAULT_ROOMS);
  }

  function isPlainObject(value) {
    return !!value && typeof value === 'object' && !Array.isArray(value);
  }

  // The family table, each entry `{family, weight}`, weights positive. The
  // entry is kept WHOLE and only its weight is normalised, so a pack that
  // resolved a Blueprint family hands the pop stage its resolved base on the
  // entry and this reader passes it on untouched.
  function readFamilies(section) {
    var raw = section.families;
    if (!Array.isArray(raw)) return DEFAULT_FAMILIES.map(copyEntry);
    var families = [];
    for (var i = 0; i < raw.length; i++) {
      var item = raw[i];
      if (!isPlainObject(item)) continue;
      var name = item.family === undefined ? '' : String(item.family);
      if (!name) continue;
      var entry = copyEntry(item);
      var weight = item.weight === undefined ? 1 : item.weight;
      entry.weight = Math.max(0, toInt(weight, 1));
      families.push(entry);
    }
    var any = false;
    for (var j = 0; j < families.length; j++) {
      if (families[j].weight) any = true;
    }
    if (!any) {
      for (var k = 0; k < families.length; k++) families[k].weight = 1;
    }
    if (!families.length) return DEFAULT_FAMILIES.map(copyEntry);
    return families;
  }

  function copyEntry(entry) {
    var out = {};
    for (var key in entry) {
      if (Object.prototype.hasOwnProperty.call(entry, key)) out[key] = entry[key];
    }
    return out;
  }

  // How many elites a floor carries, and their affix ids. `per_floor` is read
  // by `demandOf`, so the low bound is what the pack asked for.
  function readElites(section) {
    var raw = section.elites;
    if (!isPlainObject(raw)) {
      return { lo: DEFAULT_ELITES.perFloor[0], hi: DEFAULT_ELITES.perFloor[1],
               affixes: namesOf(DEFAULT_ELITES.affixes, []) };
    }
    var range = demandOf(raw.per_floor, [0, 0]);
    return { lo: range[0], hi: range[1], affixes: namesOf(raw.affixes, []) };
  }

  // How many groups a floor carries, their size, their two flags, and the
  // leash their spawns carry. `leader` is "elite" or "normal" and defaults to
  // "normal"; `same_family` defaults to true; a leash outside the closed range
  // is treated as if the Section had said nothing.
  function readGroups(section) {
    var raw = section.groups;
    if (!isPlainObject(raw)) {
      return { lo: DEFAULT_GROUPS.perFloor[0], hi: DEFAULT_GROUPS.perFloor[1],
               minionLo: DEFAULT_GROUPS.minions[0], minionHi: DEFAULT_GROUPS.minions[1],
               leader: DEFAULT_GROUPS.leader, sameFamily: DEFAULT_GROUPS.sameFamily,
               leash: null };
    }
    var leader = raw.leader === undefined ? DEFAULT_GROUPS.leader : String(raw.leader);
    if (leader !== 'elite' && leader !== 'normal') leader = DEFAULT_GROUPS.leader;
    var leash = raw.leash;
    if (typeof leash !== 'number' || !Number.isInteger(leash)
        || leash < LEASH_MIN || leash > LEASH_MAX) {
      leash = null;
    }
    var count = demandOf(raw.per_floor, [0, 0]);
    var minions = pairOf(raw.minions, [2, 3]);
    return {
      lo: count[0],
      hi: count[1],
      minionLo: minions[0],
      minionHi: minions[1],
      leader: leader,
      sameFamily: raw.same_family === undefined ? DEFAULT_GROUPS.sameFamily
                                                 : !!raw.same_family,
      leash: leash,
    };
  }

  // One family id, drawn by weight over the list in pack order.
  function drawFamily(rng, families) {
    var total = 0;
    for (var i = 0; i < families.length; i++) total += families[i].weight;
    if (total <= 0) return families[0].family;
    var roll = pick(rng, total);
    var walked = 0;
    for (var j = 0; j < families.length; j++) {
      walked += families[j].weight;
      if (roll < walked) return families[j].family;
    }
    return families[families.length - 1].family;
  }

  // A `mobs` table's key as a floor number, or 0 when it names no floor. The
  // twin of `vefr.sections._floor_number`: a key is a floor only if it is the
  // decimal spelling of that floor, so "03", "+3" and "three" name nothing.
  function floorOfKey(key) {
    if (typeof key !== 'string' || !/^[0-9]+$/.test(key)) return 0;
    var number = parseInt(key, 10);
    if (number < 1 || number > MOB_FLOOR_MAX) return 0;
    return String(number) === key ? number : 0;
  }

  // The Section's own monster count, as `floors` (a table of floor -> count)
  // and `every` (the `from` entry). `{floors: {}, every: null}` is a Section
  // that names no count at all, which is every Section written before
  // vefr#357. An entry that is not a whole number is left out rather than
  // raised: `vefr check` is what says a bad count out loud. The twin of
  // `vefr.sections.mobs_of`.
  function readMobs(section) {
    var raw = section ? section.mobs : null;
    var out = { floors: {}, every: null };
    if (!isPlainObject(raw)) return out;
    for (var key in raw) {
      if (!Object.prototype.hasOwnProperty.call(raw, key)) continue;
      var value = raw[key];
      if (typeof value !== 'number' || !Number.isInteger(value)) continue;
      if (key === 'from') { out.every = value; continue; }
      var floor = floorOfKey(key);
      if (floor) out.floors[floor] = value;
    }
    return out;
  }

  // The count floor `k` carries because the pack said so, or null when the
  // Section names nothing for it and the area budget stands. A floor the pack
  // named wins over `from`; `from` wins over the area budget; neither is a
  // draw. The twin of `vefr.sections.mob_count`.
  function mobCount(section, k) {
    var table = readMobs(section);
    var named = false;
    for (var floor in table.floors) {
      if (Object.prototype.hasOwnProperty.call(table.floors, floor)) {
        named = true;
        break;
      }
    }
    if (!named && table.every === null) return null;
    if (Number.isInteger(k) && Object.prototype.hasOwnProperty.call(
        table.floors, k)) return table.floors[k];
    return table.every;
  }

  // How many monsters this floor carries. The Section's own count for floor `k`
  // when it names one - clamped to 0..MOBS_MAX, because a pack that wrote zero
  // meant zero and one that wrote four meant four - and otherwise the area
  // budget: one slot per TILES_PER_MOB walkable tiles, clamped into
  // MOBS_MIN..MOBS_MAX. `walkable` is the caller's own count and is not
  // re-measured. Read before the first draw, never drawn, and the `size`,
  // `plan` and `layout` streams do not see it. The twin of
  // `vefr.delve_v3.mob_budget`.
  function mobBudget(section, walkable, k) {
    var named = mobCount(section, k);
    if (named !== null) return Math.min(MOBS_MAX, Math.max(0, named));
    return Math.min(MOBS_MAX, Math.max(MOBS_MIN, Math.floor(walkable / TILES_PER_MOB)));
  }

  // The floor size, and only the `(w, h)` form of it: a pair of whole numbers
  // and nothing else. A lone width, a triple or a fractional width is a
  // caller's mistake and raises rather than being rounded into another shape.
  function readSize(sizeRange) {
    if (!Array.isArray(sizeRange) || sizeRange.length !== 2) {
      throw new Error('size_range must be a (w, h) pair of whole numbers');
    }
    for (var i = 0; i < 2; i++) {
      if (typeof sizeRange[i] !== 'number' || !Number.isInteger(sizeRange[i])) {
        throw new Error('size_range must be a (w, h) pair of whole numbers');
      }
    }
    var width = sizeRange[0];
    var height = sizeRange[1];
    if (width < 8 || height < 8) {
      throw new Error('a v3 floor needs a size of at least 8 by 8');
    }
    return [width, height];
  }

  // ----------------------------------------------------------------- stage 1
  // the plan stream - the exact order of draws, and the spec's comment above
  // `_plan_stage` line for line. One `rng` is one call of
  // prng("v3|" + floor_key + "|plan"), and `rand(lo, hi)` is
  // `lo + floor(rng * (hi - lo + 1))`.
  //
  //  1. quota  = rand(rooms_lo, rooms_hi)   from `section["rooms"]`,
  //     defaulted to (12, 12). The room quota of the floor.
  //  2. loops  = rand(LOOPS_MIN, LOOPS_MAX)  how many spine chords to
  //     close. Stage 2 draws at most this many; one chord is already
  //     three cycles, and validate wants at least two.
  //  3. secrets = rand(0, 2)                 how many leaf rooms to turn
  //     into secret rooms.
  //  4. flavour = floor(rng * FLAVOURS)       which of the pack's named
  //     points of interest becomes this floor's landmark. The name it
  //     picks is a name, not a tile: it cannot move a wall.
  //  5. waypoint = floor(rng * 2)             a floor kind of "hub" is a
  //     waypoint when this lands on 0, and nothing else ever is.
  //
  // Nothing above moves a wall. The quota reaches stage 2 as a number to lay
  // out, not as a decision this stage makes about the grid, so the plan stream
  // stays the reason a rewritten affix table cannot move a stone.

  function planStage(rng, section, floorKind) {
    var quota = readRooms(section);
    return {
      quota: rand(rng, quota[0], quota[1]),
      loops: rand(rng, LOOPS_MIN, LOOPS_MAX),
      secrets: rand(rng, 0, 2),
      flavour: pick(rng, FLAVOURS),
      waypoint: floorKind === 'hub' && pick(rng, 2) === 0,
    };
  }

  // ----------------------------------------------------------------- canvas
  // The grid under construction, with the bookkeeping v3 needs. Three tile
  // sets, kept disjoint on purpose: `owner` names the room a tile belongs to
  // (-1 for none), `corr` holds the corridor tiles, and `walk` holds both. So
  // every carved tile belongs to a room or to a corridor region that touches
  // one, which is what keeps the floor readable as rooms plus corridors: a
  // corridor running through a room moves those tiles from `corr` into `owner`.

  function makeCanvas(width, height) {
    var grid = [];
    for (var y = 0; y < height; y++) {
      var row = [];
      for (var x = 0; x < width; x++) row.push(WALL);
      grid.push(row);
    }
    var owner = new Int32Array(width * height);
    owner.fill(-1);
    return {
      w: width,
      h: height,
      grid: grid,
      owner: owner,
      corr: new Set(),
      walk: new Set(),
      rooms: [],
      locked: new Set(),
      owned: 0,
      stamps: [],
    };
  }

  // Fill a room rectangle with floor and claim every one of its tiles.
  function carveRoom(canvas, rect, index) {
    var x = rect[0], y = rect[1], width = rect[2], height = rect[3];
    for (var yy = y; yy < y + height; yy++) {
      var row = canvas.grid[yy];
      for (var xx = x; xx < x + width; xx++) {
        var here = yy * canvas.w + xx;
        row[xx] = FLOOR;
        canvas.owner[here] = index;
        canvas.corr.delete(here);
        canvas.walk.add(here);
      }
    }
    canvas.owned += width * height;
  }

  // Paint a stamped room and claim only the tiles it can stand on. The room is
  // a drawing, not a rectangle: `#` and a space stay wall, a used socket
  // becomes floor and every other socket becomes wall (ADR 0013, Placement 3),
  // and a letter is a floor tile that also carries a name. So a stamped room's
  // walkable area is smaller than its rectangle, which is why `owned` is
  // counted tile by tile.
  function carveStamp(canvas, rows, rect, index, used) {
    var x = rect[0], y = rect[1];
    for (var yy = 0; yy < rows.length; yy++) {
      for (var xx = 0; xx < rows[yy].length; xx++) {
        var glyph = rows[yy][xx];
        var here = (y + yy) * canvas.w + (x + xx);
        // The whole rectangle is locked, walls and all: a corridor may not
        // run through a painted room, and the wall tiles are the ones it
        // would otherwise cross for free.
        canvas.locked.add(here);
        if (glyph === WALL || glyph === ' ') {
          canvas.grid[y + yy][x + xx] = WALL;
          continue;
        }
        if ((glyph === '+' || glyph === '?') && !(xx === used[0] && yy === used[1])) {
          canvas.grid[y + yy][x + xx] = WALL;
          continue;
        }
        canvas.grid[y + yy][x + xx] = FLOOR;
        canvas.owner[here] = index;
        canvas.corr.delete(here);
        canvas.walk.add(here);
        canvas.owned += 1;
      }
    }
  }

  // Carve a horizontal run, inclusive of both ends.
  function carveH(canvas, x0, x1, y) {
    for (var x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) carveTile(canvas, x, y);
  }

  // Carve a vertical run, inclusive of both ends.
  function carveV(canvas, y0, y1, x) {
    for (var y = Math.min(y0, y1); y <= Math.max(y0, y1); y++) carveTile(canvas, x, y);
  }

  function carveTile(canvas, x, y) {
    var here = y * canvas.w + x;
    if (canvas.grid[y][x] === WALL) {
      canvas.grid[y][x] = FLOOR;
      canvas.walk.add(here);
    }
    if (canvas.owner[here] < 0) canvas.corr.add(here);
  }

  // Carve one corridor into a stamped room, from the outside in. A stamped
  // room's corridor is routed rather than linked, so it is handed over as the
  // tiles it runs through instead of as two rooms. A mouth may be a space
  // inside the room's own rectangle; that tile belongs to the room, so the
  // corridor region starts at the next tile out. One tile, one owner.
  function stampCorridor(canvas, tiles, index, rect) {
    var x = rect[0], y = rect[1], width = rect[2], height = rect[3];
    for (var i = 0; i < tiles.length; i++) {
      var tileX = tiles[i][0], tileY = tiles[i][1];
      var here = tileY * canvas.w + tileX;
      if (!(x <= tileX && tileX < x + width && y <= tileY && tileY < y + height)) {
        carveTile(canvas, tileX, tileY);
        continue;
      }
      if (canvas.grid[tileY][tileX] === WALL) {
        canvas.grid[tileY][tileX] = FLOOR;
        canvas.walk.add(here);
        canvas.owned += 1;
      }
      canvas.owner[here] = index;
      canvas.corr.delete(here);
    }
  }

  // The grid as the FloorPlan's `rows`: one string per row.
  function canvasRows(canvas) {
    var rows = [];
    for (var y = 0; y < canvas.h; y++) rows.push(canvas.grid[y].join(''));
    return rows;
  }

  // True when two room rectangles touch or sit closer than `pad`. The pad is
  // what keeps a wall between two rooms: two rooms that touch would be
  // neighbours in the room graph with no corridor between them, and v3 lays
  // its corridors through the gap it drew.
  function overlaps(a, b, pad) {
    return ((a[0] - pad) < (b[0] + b[2]) && (b[0] - pad) < (a[0] + a[2])
      && (a[1] - pad) < (b[1] + b[3]) && (b[1] - pad) < (a[1] + a[3]));
  }

  // The middle tile of a room, floors as `generate_floor_v2` does.
  function center(rect) {
    return [rect[0] + Math.floor(rect[2] / 2), rect[1] + Math.floor(rect[3] / 2)];
  }

  // True when a rectangle is inside the grid and clear of every room.
  function fits(canvas, rect) {
    var x = rect[0], y = rect[1], width = rect[2], height = rect[3];
    if (x < 1 || y < 1 || x + width > canvas.w - 1 || y + height > canvas.h - 1) {
      return false;
    }
    for (var i = 0; i < canvas.rooms.length; i++) {
      if (overlaps(rect, canvas.rooms[i], 1)) return false;
    }
    return true;
  }

  // `fits`, and clear of every carved tile as well. A stamped room lands after
  // the galleries and the chords, so the wall a plain room was placed against
  // may already carry a corridor; overwriting one would eat the corridor and
  // strand whatever it served, so a stamp that lands on carved ground is not
  // placed at all.
  function fitsStamp(canvas, rect) {
    if (!fits(canvas, rect)) return false;
    var x = rect[0], y = rect[1], width = rect[2], height = rect[3];
    for (var yy = y; yy < y + height; yy++) {
      for (var xx = x; xx < x + width; xx++) {
        if (canvas.walk.has(yy * canvas.w + xx)) return false;
      }
    }
    return true;
  }

  // -------------------------------------------------------------- corridors

  // An L-shaped corridor between two room rectangles, `delve`'s shape. The door
  // sockets are the tile of each room's facing side that faces the other room;
  // the axis is the one the two rooms are further apart on, so the long leg of
  // the L runs along the gap and the short leg steps into the second room.
  // The one draw here picks which way round the bend the L goes.
  function link(rng, canvas, first, second) {
    var ax = first[0], ay = first[1], aw = first[2], ah = first[3];
    var bx = second[0], by = second[1], bw = second[2], bh = second[3];
    var gapX = Math.max(ax - (bx + bw), bx - (ax + aw));
    var gapY = Math.max(ay - (by + bh), by - (ay + ah));
    if (rng() < 0.5) {
      // The first leg runs from `first` to the bend.
      if (gapX >= gapY) {
        carveH(canvas, ax + aw - 1, bx, ay + Math.floor(ah / 2));
        carveV(canvas, ay + Math.floor(ah / 2), by + Math.floor(bh / 2), bx);
      } else {
        carveV(canvas, ay + ah - 1, by, ax + Math.floor(aw / 2));
        carveH(canvas, ax + Math.floor(aw / 2), bx + Math.floor(bw / 2), by);
      }
    } else {
      // The same two legs, the other way round the bend.
      if (gapX >= gapY) {
        carveV(canvas, ay + Math.floor(ah / 2), by + Math.floor(bh / 2),
          ax + Math.floor(aw / 2));
        carveH(canvas, ax + Math.floor(aw / 2), bx + Math.floor(bw / 2),
          by + Math.floor(bh / 2));
      } else {
        carveH(canvas, ax + Math.floor(aw / 2), bx + Math.floor(bw / 2),
          ay + Math.floor(ah / 2));
        carveV(canvas, ay + Math.floor(ah / 2), by + Math.floor(bh / 2),
          bx + Math.floor(bw / 2));
      }
    }
  }

  // A corridor that runs along one gallery row to close a cycle. The run is
  // carved on a row that is a wall, one tile clear of the rooms it serves, and
  // it is entered from each end - so it passes over the wall between every
  // pair of rooms it spans and reads as one corridor region touching all of
  // them, which is exactly the edge the loop needs.
  function galleryLoop(canvas, horizontal, first, second, row) {
    var ax = first[0], ay = first[1], aw = first[2], ah = first[3];
    var bx = second[0], by = second[1], bw = second[2], bh = second[3];
    if (horizontal) {
      var near = ax + aw - 1;
      var far = bx;
      if (near > far) {
        var swap = near;
        near = far;
        far = swap;
      }
      carveH(canvas, near, far, row);
      carveV(canvas, row, ay + Math.floor(ah / 2), ax + aw - 1);
      carveV(canvas, row, by + Math.floor(bh / 2), bx);
    } else {
      var lowNear = ay + ah - 1;
      var lowFar = by;
      if (lowNear > lowFar) {
        var swap2 = lowNear;
        lowNear = lowFar;
        lowFar = swap2;
      }
      carveV(canvas, lowNear, lowFar, row);
      carveH(canvas, row, ax + Math.floor(aw / 2), ay + ah - 1);
      carveH(canvas, row, bx + Math.floor(bw / 2), by);
    }
  }

  // ----------------------------------------------------------------- stage 2
  // the layout stream - the exact order of draws, and the spec's comment above
  // `_layout_stage` line for line. `rand(lo, hi)` is
  // `lo + floor(rng * (hi - lo + 1))` and `pick(n)` is `floor(rng * n)`. This
  // is the only stage that carves.
  //
  //  1. row_h = rand(5, 7)          the pitch of a slot row across the
  //     short axis, so a room of up to `row_h - 1` tiles and a wall.
  //     band = row_h - 1.
  //  2. n_slots = (short - 2) // row_h;
  //     band_slot = n_slots // 2;   the spine's slot row, the middle one.
  //     band_lo = 1 + band_slot * row_h.
  //  3. spine: the up-stair end first. Repeat while the plan's quota is
  //     not half spent and the cursor is inside the long axis:
  //       da = rand(4, 6)            the room's size along the long axis;
  //       shape = pick(len(SHAPES));
  //       place (cursor, band_lo, da, band); cursor = cursor + da + 1.
  //     A draw that will not fit ends the spine, and no further draw is
  //     taken. Each room is joined to the one before it with one L-shaped
  //     corridor, which takes one draw for the bend.
  //  4. accretion: children go on ONE side of the band first, and the
  //     side with the most free slot rows wins, the lower one on a tie. The
  //     free rows of that side, nearest the spine first, are the rows the
  //     children may use. Walk the spine in order and, for each spine room,
  //     try those rows in turn. Stop for a room once `cap` children are
  //     placed or the quota is met. If the quota is still short when the
  //     spine is done, do the whole thing again over the free rows of the
  //     other side, in the same order and the same draws. Each attempt, in
  //     this order and whether or not it is placed:
  //       da = rand(3, 5)            the child's size along the long axis;
  //       db = rand(3, band)         its size across the short axis.
  //     A child is centred on its parent, clamped inside the long axis,
  //     skipped when it does not fit its slot row or touches another
  //     room, and otherwise placed and joined to its parent by one
  //     L-shaped corridor, which takes one draw for the bend.
  //  5. the child gallery: on the child side, on the wall row just past
  //     the outermost child row, a run from the first child of that row to
  //     the last. It serves every child it runs past, so those rooms gain a
  //     second way in and the room graph stops being a tree of dead ends.
  //  6. the spine chords, which are the loops. Take the pairs
  //       (0, 3), (4, 7), (8, 11), ... clipped to the last spine room,
  //     one per four rooms, and the first `plan.loops` of them. Each is
  //     closed with a gallery corridor on the wall row just off the band
  //     on the side NO child was placed on. A run over four rooms joins all
  //     six pairs of those four, and the chain already has three of them, so
  //     one chord is three cycles.
  //  7. the stamped rooms (ADR 0013, Placement), last, because a stamp may
  //     not land on carved ground. The slots are, in order, warden-hall,
  //     vault (only when the pack names one), landmark, then `special`,
  //     `secret` and `filler` up to the quotas below. A slot with no
  //     eligible stamp of its role takes no draw at all. Per slot:
  //       role = pick(total weight of that role's stamps)
  //     then, per attempt, up to 24 of them, in this order:
  //       o = pick(len(allowed))     the orientation, from the allowed set
  //       x = rand(1, w - width - 1)  and then
  //       y = rand(1, h - height - 1)
  //     An attempt that does not fit, or that cannot be reached from one of
  //     its own sockets, is spent like any other: the three draws happen,
  //     nothing is carved, and the next attempt is taken. A stamp too big
  //     for the floor at any orientation gives its slot up at once and takes
  //     no draw at all. The connection draws nothing: a corridor is routed
  //     from the socket mouth to the nearest carved tile, both L-bends tried
  //     in a fixed order, and the first route crossing no locked tile wins. A
  //     used `+` becomes floor and a used `?` becomes a `secrets` entry; an
  //     unused socket becomes wall. A required role still missing fails the
  //     floor, which the retry ladder redraws with `|try{n}`; on the LAST try
  //     the required roles are pinned to named spots instead, and a role that
  //     still fails falls back to v2 with the role reported as a defect.

  function childRows(bandSlot, nSlots) {
    // The free slot rows children may use, and the side they are on. 1 is the
    // side past the band and -1 the side before it. The side with the most
    // free rows wins and the lower one on a tie, so the choice follows from
    // the floor's shape and is not a draw.
    var below = [];
    var above = [];
    var i;
    for (i = bandSlot + 1; i < nSlots; i++) below.push(i);
    for (i = bandSlot - 1; i >= 0; i--) above.push(i);
    if (below.length >= above.length) return { near: below, side: 1 };
    return { near: above.slice().reverse(), side: -1 };
  }

  // The free slot rows on the other side of the band, nearest first: the second
  // accretion pass, for a floor the first one could not fill.
  function farRowsFor(bandSlot, nSlots, side) {
    var out = [];
    var i;
    if (side === 1) {
      for (i = bandSlot - 1; i >= 0; i--) out.push(i);
    } else {
      for (i = bandSlot + 1; i < nSlots; i++) out.push(i);
    }
    return out;
  }

  // The layout stage: the spine, accretion, the galleries, the stamps.
  //
  // Rooms are laid out along the long axis and across the short one, in
  // "along, across" order, so a tall floor lays its spine down rather than
  // across. `pool` is the stamp set this floor may use - empty for a Section
  // that names no stamp tags, which is every floor of a pack without stamps,
  // and those floors are laid out exactly as they were before ADR 0013.
  // `pinned` is the last try's flag, and it only means anything when the pool
  // is not empty.
  //
  // Returns the spine (the rooms in chain order, so the graph stage can put
  // the two stairs at its ends) and the required roles that wanted a stamped
  // room and did not get one.
  function layoutStage(rng, canvas, plan, pool, pinned) {
    var width = canvas.w;
    var height = canvas.h;
    var horizontal = width >= height;
    var longLen = horizontal ? width : height;
    var shortLen = horizontal ? height : width;

    function rectOf(along, across, alongSize, acrossSize) {
      return horizontal ? [along, across, alongSize, acrossSize]
                        : [across, along, acrossSize, alongSize];
    }

    function place(along, across, alongSize, acrossSize) {
      var index = canvas.rooms.length;
      var box = rectOf(along, across, alongSize, acrossSize);
      carveRoom(canvas, box, index);
      canvas.rooms.push([box[0], box[1], box[2], box[3],
                         SHAPES[pick(rng, SHAPES.length)]]);
      return index;
    }

    var rowH = rand(rng, 5, 7);
    var band = rowH - 1;
    var nSlots = Math.floor((shortLen - 2) / rowH);
    var bandSlot = Math.floor(nSlots / 2);
    var bandLo = 1 + bandSlot * rowH;
    if (nSlots < 1) return { spine: [], missing: [] };

    // 3. the spine, one room after another down the long axis.
    var spine = [];
    var cursor = 1;
    var spineTarget = Math.max(3, Math.floor((plan.quota + 1) / 2));
    while (spine.length < spineTarget) {
      var alongSize = rand(rng, 4, 6);
      if (cursor + alongSize > longLen - 1) break;
      var index = place(cursor, bandLo, alongSize, band);
      if (spine.length) link(rng, canvas, head(canvas.rooms[spine[spine.length - 1]]),
                              head(canvas.rooms[index]));
      spine.push(index);
      cursor += alongSize + 1;
    }
    if (spine.length < 2) return { spine: [], missing: [] };

    // 4. accretion, every spine room grown into the free rows of one side,
    //    then into the free rows of the other if that was not enough.
    var near = childRows(bandSlot, nSlots);
    var nearRows = near.near;
    var side = near.side;
    var farRows = farRowsFor(bandSlot, nSlots, side);
    var cap = Math.max(2, Math.ceil((plan.quota - spine.length) / spine.length));
    var rowSets = [nearRows, farRows];
    for (var pass = 0; pass < rowSets.length; pass++) {
      if (canvas.rooms.length >= plan.quota) break;
      var slots = rowSets[pass];
      for (var p = 0; p < spine.length; p++) {
        if (canvas.rooms.length >= plan.quota) break;
        var grown = 0;
        for (var s = 0; s < slots.length; s++) {
          if (grown >= cap || canvas.rooms.length >= plan.quota) break;
          var slot = slots[s];
          var childAlong = rand(rng, 3, 5);
          var childAcross = rand(rng, 3, band);
          var across = 1 + slot * rowH;
          if (across + childAcross > shortLen - 1) continue;
          var parent = canvas.rooms[spine[p]];
          var along = parent[0] + Math.floor((parent[2] - childAlong) / 2);
          along = Math.max(1, Math.min(along, longLen - 1 - childAlong));
          if (!fits(canvas, rectOf(along, across, childAlong, childAcross))) continue;
          var child = place(along, across, childAlong, childAcross);
          link(rng, canvas, head(parent), head(canvas.rooms[child]));
          grown += 1;
        }
      }
    }
    var spineSet = new Set(spine);
    var children = [];
    for (var room = 0; room < canvas.rooms.length; room++) {
      if (!spineSet.has(room)) children.push(room);
    }

    // 5. the child gallery, in front of the outermost child row.
    if (children.length && nearRows.length) {
      childGallery(canvas, horizontal, children, nearRows[nearRows.length - 1] + side,
                   rowH, shortLen, side);
    }

    // 6. the spine chords, on the side of the band no child was placed on.
    var edge = horizontal ? canvas.h : canvas.w;
    var gallery = side === 1 ? bandLo - 1 : bandLo + band;
    if (gallery >= 1 && gallery <= edge - 2) {
      var nth = 0;
      for (var i = 0; i < spine.length - 1; i += 4) {
        if (nth >= plan.loops || i + 3 >= spine.length) break;
        galleryLoop(canvas, horizontal, head(canvas.rooms[spine[i]]),
                    head(canvas.rooms[spine[i + 3]]), gallery);
        nth += 1;
      }
    }

    // 7. the stamped rooms, once everything else has stopped carving.
    var missing = [];
    if (pool.length) {
      var up = center(head(canvas.rooms[spine[0]]));
      missing = stampStage(rng, canvas, plan, pool, spine, up, pinned);
    }
    return { spine: spine, missing: missing };
  }

  // The first four numbers of a room rectangle, which is what every corridor
  // function wants. A copy, because the shape at index 4 is the graph stage's
  // to write.
  function head(room) {
    return [room[0], room[1], room[2], room[3]];
  }

  // A corridor in front of the outermost row of child rooms. The run is carved
  // on the wall row just past that row, which no child's corridor reaches, so
  // it is a region of its own that serves exactly the rooms of that row. Two
  // of those rooms were only joined by the whole length of the spine; now the
  // region joins them to each other, and that is a cycle.
  function childGallery(canvas, horizontal, children, slot, rowH, shortLen, side) {
    if (slot < 0 || slot + 1 > Math.floor((shortLen - 2) / rowH)) return;
    var across = 1 + slot * rowH;
    var row = side === 1 ? across : across - 1;
    if (!(row >= 1 && row <= (horizontal ? canvas.h : canvas.w) - 2)) return;
    var same = [];
    for (var i = 0; i < children.length; i++) {
      var room = canvas.rooms[children[i]];
      if ((horizontal ? room[1] : room[0]) === across) same.push(children[i]);
    }
    if (same.length < 2) return;
    galleryLoop(canvas, horizontal, head(canvas.rooms[same[0]]),
                head(canvas.rooms[same[same.length - 1]]), row);
  }

  // ------------------------------------------------------- the stamped rooms
  // ADR 0013's Placement section, in the layout stream. A stamped room is a
  // hand-drawn grid pasted onto the floor: it is not a rectangle, it is locked
  // once painted, and it is reached by one corridor out of one of its own
  // sockets. Everything here is a function of the layout stream and of the
  // pack, so a stamp check and this twin see the same room in the same place.
  //
  // Nothing in this section draws a number the plan stage did not already draw.
  // The slot list is arithmetic on `quota` and `secrets`, and a Section that
  // names no tags places no stamps.

  // One turn clockwise: a w x h grid comes back as an h x w grid. The top row
  // of the old grid becomes the right-hand column of the new one.
  function turnClockwise(rows) {
    var height = rows.length;
    var out = [];
    for (var y = 0; y < rows[0].length; y++) {
      var line = '';
      for (var x = 0; x < height; x++) line += rows[height - 1 - x][y];
      out.push(line);
    }
    return out;
  }

  // The grid as it looks at orientation `o`, `o` in `0..7`: mirror first when
  // `o >= 4`, then turn clockwise `o % 4` times. Read-only, and a fresh list of
  // fresh strings every call.
  function stampOrient(rows, o) {
    if (!(o >= 0 && o <= 7)) throw new Error('orientation ' + o + ' is not one of 0..7');
    var drawn = [];
    for (var i = 0; i < rows.length; i++) {
      drawn.push(o >= 4 ? rows[i].split('').reverse().join('') : rows[i]);
    }
    for (var turn = 0; turn < o % 4; turn++) drawn = turnClockwise(drawn);
    return drawn;
  }

  // Which orientations this stamp's two flags allow, in draw order - the order
  // a random draw indexes, so `allowed[pick(allowed.length)]` is the whole
  // rule. A story room comes back as `[0]`, because the reader has already
  // refused it a `rotate` or a `mirror`.
  function stampOrientations(record) {
    if (record.rotate && record.mirror) return [0, 1, 2, 3, 4, 5, 6, 7];
    if (record.rotate) return [0, 1, 2, 3];
    if (record.mirror) return [0, 4];
    return [0];
  }

  // Every socket of a drawn grid, in row-major order, ready to route to: the
  // socket tile, its kind, the single tile a corridor steps onto, the mouth on
  // the far side of it, and the direction out of that mouth. Ties between two
  // sockets are the placer's to break: nearest mouth first, row-major after.
  function stampSockets(rows) {
    var height = rows.length;
    var width = rows[0].length;
    var found = [];
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        var glyph = rows[y][x];
        if (glyph !== '+' && glyph !== '?') continue;
        var into = null;
        for (var i = 0; i < STAMP_STEPS.length; i++) {
          var nx = x + STAMP_STEPS[i][0];
          var ny = y + STAMP_STEPS[i][1];
          if (nx >= 0 && nx < width && ny >= 0 && ny < height
              && STAMP_STANDING.indexOf(rows[ny][nx]) >= 0) {
            into = [nx, ny];
            break;
          }
        }
        // The reader promises every socket exactly one way in; a stamp that
        // breaks the promise never reaches a floor.
        if (into === null) continue;
        var mouth = [2 * x - into[0], 2 * y - into[1]];
        found.push({
          at: [x, y],
          kind: glyph === '+' ? 'door' : 'secret',
          into: into,
          mouth: mouth,
          step: [mouth[0] - x, mouth[1] - y],
        });
      }
    }
    return found;
  }

  // Where each letter of the legend stands in a drawn grid. A glyph is a glyph
  // in all eight orientations, so the turn never renames anything.
  function stampAnchors(rows, legend) {
    var found = {};
    for (var y = 0; y < rows.length; y++) {
      for (var x = 0; x < rows[y].length; x++) {
        var glyph = rows[y][x];
        if (isPlainObject(legend) && isPlainObject(legend[glyph])) {
          found[glyph] = { at: [x, y], anchor: legend[glyph].anchor };
        }
      }
    }
    return found;
  }

  // The stamps this Section may use on a floor `depth` steps into it: the
  // Section's `stamps` tags have to overlap the stamp's own tags - or name
  // `any`, which every stamp matches - and `depth` has to be inside the
  // stamp's own depth range, which is `k`, the floor's 1-based position in its
  // Section. The pack arrives in sorted id order from `stamps.load` and is
  // walked in that order, so a weighted draw over a role is the same in every
  // language.
  function stampPool(section, pack, depth) {
    var tags = namesOf(section.stamps, []);
    if (!tags.length || !pack.length) return [];
    var wanted = new Set(tags);
    var pool = [];
    for (var i = 0; i < pack.length; i++) {
      var record = pack[i];
      var overlap = false;
      var own = Array.isArray(record.tags) ? record.tags : [];
      for (var j = 0; j < own.length; j++) {
        if (wanted.has(String(own[j]))) {
          overlap = true;
          break;
        }
      }
      if (!wanted.has(STAMP_ANY_TAG) && !overlap) continue;
      // A Section that names no vault has no vault to open, and a vault room
      // is a locked door and a note rather than a place to walk into, so its
      // stamp never enters the pool. The slot is still there and takes no
      // draw, which is the rule the layout comment writes.
      if (record.role === 'vault' && !section.vault) continue;
      if (record.depth[0] <= depth && depth <= record.depth[1]) pool.push(record);
    }
    return pool;
  }

  // The roles wanted on this floor, in the order ADR 0013 places them: the
  // three required roles first, one each, then `special`, `secret` and
  // `filler` up to quotas the plan stage has already drawn. A slot with no
  // eligible stamp of its role takes no draw at all.
  function stampSlots(plan) {
    var slots = STAMP_REQUIRED_ROLES.slice();
    var i;
    for (i = 0; i < Math.floor(plan.quota / 8); i++) slots.push('special');
    for (i = 0; i < plan.secrets; i++) slots.push('secret');
    for (i = 0; i < Math.floor(plan.quota / 4); i++) slots.push('filler');
    return slots;
  }

  // One stamp of a role, by weight, walking the ids in sorted order. The same
  // walk and the same cumulative sum as `drawFamily`, so a twin written from
  // either one draws the same stamp.
  function weightedStamp(rng, pool) {
    var total = 0;
    for (var i = 0; i < pool.length; i++) total += pool[i].weight;
    if (total <= 0) return pool[0];
    var roll = pick(rng, total);
    var walked = 0;
    for (var j = 0; j < pool.length; j++) {
      walked += pool[j].weight;
      if (roll < walked) return pool[j];
    }
    return pool[pool.length - 1];
  }

  // The `count` carved tiles nearest `tile`, nearest first. Rings outward
  // rather than scanning every carved tile, because a stamp lands against open
  // wall and the answer is usually a tile or two away - and a tile is found in
  // the same order in every language: by Manhattan steps first, then
  // row-major. `limit` is the floor's long axis, so the search cannot run away.
  function nearestWalkable(canvas, tile, limit, count) {
    var tx = tile[0];
    var ty = tile[1];
    var found = [];
    for (var radius = 1; radius < limit; radius++) {
      var ring = [];
      for (var dy = -radius; dy <= radius; dy++) {
        var across = radius - Math.abs(dy);
        if (across) {
          ring = pushTile(ring, canvas, tx - across, ty + dy);
          ring = pushTile(ring, canvas, tx + across, ty + dy);
        } else {
          ring = pushTile(ring, canvas, tx, ty + dy);
        }
      }
      if (ring.length) {
        ring.sort(byRowMajor);
        for (var i = 0; i < ring.length; i++) found.push([ring[i][1], ring[i][2]]);
        if (found.length >= count) return found.slice(0, count);
      }
    }
    return found;
  }

  // One carved tile into a search ring, as `[index, x, y]` so the ring sorts
  // row-major on the index alone.
  function pushTile(ring, canvas, x, y) {
    if (x < 0 || x >= canvas.w || y < 0 || y >= canvas.h) return ring;
    var here = y * canvas.w + x;
    if (!canvas.walk.has(here)) return ring;
    ring.push([here, x, y]);
    return ring;
  }

  function byRowMajor(a, b) {
    return a[0] - b[0];
  }

  // Every whole number from `lo` to `hi`, both ends, either direction.
  function span(lo, hi) {
    var step = hi >= lo ? 1 : -1;
    var out = [];
    for (var value = lo; step > 0 ? value <= hi : value >= hi; value += step) {
      out.push(value);
    }
    return out;
  }

  // The two L-shaped routes between two tiles, the long way round first: the
  // first runs along `start`'s row and then up `end`'s column, the second runs
  // along `start`'s column and then along `end`'s row. No draw, unlike `link`:
  // ADR 0013 says the first bend that crosses no locked tile wins, and "first"
  // has to mean the same thing in every language.
  function bends(start, end) {
    var x0 = start[0], y0 = start[1], x1 = end[0], y1 = end[1];
    var first = [];
    var second = [];
    var across = span(x0, x1);
    var down = span(y0, y1);
    var i;
    for (i = 0; i < across.length; i++) first.push([across[i], y0]);
    for (i = 1; i < down.length; i++) first.push([x1, down[i]]);
    for (i = 0; i < down.length; i++) second.push([x0, down[i]]);
    for (i = 1; i < across.length; i++) second.push([across[i], y1]);
    return [first, second];
  }

  // The corridor that reaches a stamped room, or null when none does. Sockets
  // are tried nearest the floor first - the mouth's Manhattan distance to the
  // nearest carved tile - and a tie goes to the socket that comes first in
  // row-major order. Each socket is tried as both L bends, and the first route
  // that crosses no locked tile and no other carved tile wins. The route ends
  // on the socket tile, because that is the tile the corridor has to claim for
  // the room to be reached at all.
  function stampRoute(canvas, rows, rect) {
    var x = rect[0];
    var y = rect[1];
    var choices = [];
    var sockets = stampSockets(rows);
    for (var i = 0; i < sockets.length; i++) {
      var socket = sockets[i];
      var at = [socket.at[0] + x, socket.at[1] + y];
      var mouth = [socket.mouth[0] + x, socket.mouth[1] + y];
      var ends = nearestWalkable(canvas, mouth, Math.max(canvas.w, canvas.h),
                                 STAMP_ROUTE_ENDS);
      if (!ends.length) continue;
      var walk = Math.abs(mouth[0] - ends[0][0]) + Math.abs(mouth[1] - ends[0][1]);
      choices.push({ walk: walk, socket: socket, at: at, mouth: mouth, ends: ends });
    }
    // `socket.at` is the row-major tie-break, so "nearest, then row-major" is
    // a total order and no stability is borrowed from the sort.
    choices.sort(function (a, b) {
      if (a.walk !== b.walk) return a.walk - b.walk;
      if (a.socket.at[0] !== b.socket.at[0]) return a.socket.at[0] - b.socket.at[0];
      return a.socket.at[1] - b.socket.at[1];
    });
    for (var c = 0; c < choices.length; c++) {
      var choice = choices[c];
      for (var t = 0; t < choice.ends.length; t++) {
        var target = choice.ends[t];
        var routes = bends(choice.mouth, target);
        for (var r = 0; r < routes.length; r++) {
          var tiles = routes[r].concat([choice.at]);
          if (routeClear(canvas, tiles, rect, choice.at, target)) {
            return { socket: choice.socket, tiles: tiles };
          }
        }
      }
    }
    return null;
  }

  // True when a route stays inside the grid and out of everything carved.
  // Three rules, all the same rule from a different side: a corridor does not
  // cut through a room. It may not cross a tile a stamped room locked, it may
  // not cross any tile of the room it is being routed to except the socket it
  // comes in through - walls included - and it may not cross a carved tile at
  // all except the one it ends on.
  function routeClear(canvas, tiles, rect, at, target) {
    var x = rect[0], y = rect[1], width = rect[2], height = rect[3];
    for (var i = 0; i < tiles.length; i++) {
      var x0 = tiles[i][0], y0 = tiles[i][1];
      if (!(x0 >= 0 && x0 < canvas.w && y0 >= 0 && y0 < canvas.h)) return false;
      if ((x0 === at[0] && y0 === at[1]) || (x0 === target[0] && y0 === target[1])) {
        continue;
      }
      if (x <= x0 && x0 < x + width && y <= y0 && y0 < y + height) return false;
      var here = y0 * canvas.w + x0;
      if (canvas.locked.has(here)) return false;
      if (canvas.walk.has(here)) return false;
    }
    return true;
  }

  // Check the spot, route one corridor to it, then paint it. Nothing is carved
  // until both checks pass, so a rejected attempt costs four draws and leaves
  // the floor exactly as it was.
  function layStamp(canvas, rows, rect, record, o) {
    if (!fitsStamp(canvas, rect)) return null;
    var found = stampRoute(canvas, rows, rect);
    if (found === null) return null;
    var socket = found.socket;
    var tiles = found.tiles;
    var width = rows[0].length;
    var height = rows.length;
    var index = canvas.rooms.length;
    canvas.rooms.push([rect[0], rect[1], width, height, record.role]);
    carveStamp(canvas, rows, rect, index, socket.at);
    stampCorridor(canvas, tiles, index, rect);
    var named = stampAnchors(rows, record.legend);
    var anchors = {};
    for (var glyph in named) {
      if (!Object.prototype.hasOwnProperty.call(named, glyph)) continue;
      var entry = named[glyph];
      anchors[entry.anchor] = [entry.at[0] + rect[0], entry.at[1] + rect[1]];
    }
    var placement = {
      id: record.id,
      role: record.role,
      orientation: o,
      room: index,
      at: [rect[0], rect[1]],
      size: [width, height],
      anchors: anchors,
      // The socket the corridor came in through, in floor coordinates. A room
      // with no used socket is a room nothing can reach, so the record names
      // the one that was used; the others became wall when the room was
      // painted.
      socket: [socket.at[0] + rect[0], socket.at[1] + rect[1]],
    };
    if (socket.kind === 'secret') placement.secret = placement.socket;
    if (record.poi) placement.poi = record.poi;
    canvas.stamps.push(placement);
    return placement;
  }

  // Up to 24 attempts at one stamp, three draws each, in this order: the
  // orientation, then `x`, then `y`. The first attempt that fits and can be
  // reached is taken; all 24 failing gives up the slot. A stamp too big for
  // the floor at any orientation takes no draw at all and gives up at once.
  function tryStamp(rng, canvas, record) {
    var allowed = stampOrientations(record);
    for (var attempt = 0; attempt < STAMP_ATTEMPTS; attempt++) {
      var o = allowed[pick(rng, allowed.length)];
      var rows = stampOrient(record.rows, o);
      var width = rows[0].length;
      var height = rows.length;
      if (width + 2 > canvas.w || height + 2 > canvas.h) return null;
      var rect = [rand(rng, 1, canvas.w - width - 1),
                  rand(rng, 1, canvas.h - height - 1), width, height];
      var placed = layStamp(canvas, rows, rect, record, o);
      if (placed !== null) return placed;
    }
    return null;
  }

  // Every spot a stamp may be pinned to, `around` first: nearest by Manhattan
  // steps, ties row-major, so the list is a fixed order and not a draw. The
  // border is left out because `fits` needs a wall row round every room.
  function orderedSpots(canvas, around) {
    var out = [];
    for (var y = 1; y < canvas.h - 1; y++) {
      for (var x = 1; x < canvas.w - 1; x++) out.push([x, y]);
    }
    out.sort(function (a, b) {
      var da = Math.abs(a[0] - around[0]) + Math.abs(a[1] - around[1]);
      var db = Math.abs(b[0] - around[0]) + Math.abs(b[1] - around[1]);
      if (da !== db) return da - db;
      if (a[1] !== b[1]) return a[1] - b[1];
      return a[0] - b[0];
    });
    return out;
  }

  // The spots a required stamp is pinned to on the last try, in order: the
  // warden hall at the far end of the spine, and the vault in the corners
  // farthest from `up`.
  function pinSpots(canvas, role, spine, up) {
    if (spine.length && role === 'warden-hall') {
      var room = canvas.rooms[spine[spine.length - 1]];
      return orderedSpots(canvas, [room[0] + room[2] - 1,
                                   room[1] + Math.floor(room[3] / 2)]);
    }
    var corners = [[1, 1], [canvas.w - 2, 1], [1, canvas.h - 2],
                   [canvas.w - 2, canvas.h - 2]];
    corners.sort(function (a, b) {
      var da = -(Math.abs(a[0] - up[0]) + Math.abs(a[1] - up[1]));
      var db = -(Math.abs(b[0] - up[0]) + Math.abs(b[1] - up[1]));
      if (da !== db) return da - db;
      if (a[0] !== b[0]) return a[0] - b[0];
      return a[1] - b[1];
    });
    var out = [];
    for (var i = 0; i < corners.length; i++) {
      out = out.concat(orderedSpots(canvas, corners[i]));
    }
    return out;
  }

  // True when one of the room's sockets opens towards the floor's centre.
  // "Towards" is the axis the mouth points along, plus the other axis staying
  // inside the room's own span, so a corridor leaving a west wall mid-height
  // counts as facing a centre that is east of it and level.
  function facesCentre(rows, rect, centre) {
    var x = rect[0], y = rect[1], width = rect[2], height = rect[3];
    var sockets = stampSockets(rows);
    for (var i = 0; i < sockets.length; i++) {
      var socket = sockets[i];
      var mx = socket.mouth[0] + x;
      var my = socket.mouth[1] + y;
      var dx = socket.step[0];
      var dy = socket.step[1];
      if (dx && (centre[0] - mx) * dx > 0 && Math.abs(centre[1] - my) <= height) {
        return true;
      }
      if (dy && (centre[1] - my) * dy > 0 && Math.abs(centre[0] - mx) <= width) {
        return true;
      }
    }
    return false;
  }

  // The last try's placement for one required stamp: no draws at all. The
  // first id of the role in sorted order, the first allowed orientation whose
  // mouth faces the floor's centre, and the first spot the role is pinned to
  // that fits and can be reached. ADR 0013 names a pinned position for the
  // warden hall and for the vault; the landmark keeps the ordinary 24
  // attempts, because a named position for it was never written down and
  // inventing one here would be a second rule the twin does not have.
  function pinStamp(canvas, record, spine, up) {
    var allowed = stampOrientations(record);
    var centre = [Math.floor(canvas.w / 2), Math.floor(canvas.h / 2)];
    var spots = pinSpots(canvas, record.role, spine, up);
    for (var s = 0; s < spots.length; s++) {
      for (var a = 0; a < allowed.length; a++) {
        var rows = stampOrient(record.rows, allowed[a]);
        var rect = [spots[s][0], spots[s][1], rows[0].length, rows.length];
        if (rect[0] + rect[2] > canvas.w - 1 || rect[1] + rect[3] > canvas.h - 1) {
          continue;
        }
        if (!facesCentre(rows, rect, centre)) continue;
        var placed = layStamp(canvas, rows, rect, record, allowed[a]);
        if (placed !== null) return placed;
      }
    }
    return null;
  }

  // Place this floor's stamped rooms, in ADR 0013's order. The three required
  // roles first, then the optional slots, each one drawing its stamp by weight
  // and then spending up to 24 attempts on a spot. A stamp that reaches
  // `max_per_floor` drops out of its role's choices, so neither the draw nor
  // the pinned try picks one that is already on the floor.
  //
  // Returns the required roles that wanted a stamped room and did not get one:
  // the caller fails the floor over that, and the retry ladder draws the same
  // floor key again with `|try{n}`. On the last try `pinned` is true and the
  // warden hall and the vault - the two roles ADR 0013 names spots for - skip
  // the attempts, the draw and the weighted choice, and take their named
  // positions instead, before any other room.
  function stampStage(rng, canvas, plan, pool, spine, up, pinned) {
    var groups = {};
    for (var i = 0; i < pool.length; i++) {
      var role = pool[i].role;
      if (!Object.prototype.hasOwnProperty.call(groups, role)) groups[role] = [];
      groups[role].push(pool[i]);
    }
    var used = {};
    var missing = [];
    var slots = stampSlots(plan);
    for (var s = 0; s < slots.length; s++) {
      var wanted = slots[s];
      // `max_per_floor` is the limit a stamp declares for itself and it holds
      // on the pinned path too: a stamp already on the floor has spent its
      // place on this floor whichever try placed it.
      var all = Object.prototype.hasOwnProperty.call(groups, wanted) ? groups[wanted] : [];
      var choices = [];
      for (var c = 0; c < all.length; c++) {
        var spent = used[all[c].id] || 0;
        if (spent < all[c].max_per_floor) choices.push(all[c]);
      }
      var got = null;
      if (choices.length) {
        if (pinned && PINNED_ROLES.indexOf(wanted) >= 0) {
          got = pinStamp(canvas, choices[0], spine, up);
        } else {
          got = tryStamp(rng, canvas, weightedStamp(rng, choices));
        }
      }
      if (got === null) {
        if (STAMP_REQUIRED_ROLES.indexOf(wanted) >= 0) missing.push(wanted);
        continue;
      }
      used[got.id] = (used[got.id] || 0) + 1;
    }
    return missing;
  }

  // ----------------------------------------------------------------- stage 3
  // the graph stage - no draws at all. It reads the layout back out of the
  // grid, exactly the way the property sweep does, so the main path the warden
  // and the chests are placed against is the same main path the sweep
  // measures.
  //
  //  1. A node per room, in `rooms` order, then a node per maximal
  //     4-connected run of corridor tiles. Corridor nodes are numbered in
  //     the row-major order of their first tile, so the numbering matches
  //     the sweep's to the node.
  //  2. An edge when a corridor tile is 4-adjacent to a room tile, and
  //     when two room tiles are 4-adjacent across no corridor.
  //  3. The main path is a breadth-first walk of that region graph from
  //     the room holding the up-stair to the room holding the down-stair,
  //     neighbours visited in ascending node order, so the lower index
  //     wins a tie. Its room nodes, in order, are the main path.
  //  4. Distances are counted from the up room over the room graph.
  //  5. The warden goes in the farthest room off the main path, ties
  //     broken by the lower room index: the gates-and-guardians rule.
  //  6. The landmark goes in the next room off the path after that, and
  //     the vault in the one after it when the pack names a vault.
  //     A room a stamp was painted into is already the room its role
  //     names, so it is used instead of being chosen: the warden hall is
  //     the hall the author drew, the landmark is the one with the `poi`
  //     letter, and the anchors are those letters rather than the middle
  //     of the rectangle. A stamped room is left out of the off-path walk
  //     below, so no room is two things at once.

  function pushUnique(list, value) {
    if (list.indexOf(value) < 0) list.push(value);
  }

  function byNumber(a, b) {
    return a - b;
  }

  // A set of whole numbers as a sorted array. The determinism rule forbids
  // walking a map's keys where draws are consumed, so every set here is read
  // through this, and every sort breaks its ties by index.
  function sortedSet(set) {
    var out = Array.from(set);
    out.sort(byNumber);
    return out;
  }

  // The shortest node path start -> goal, ties broken by node index.
  // Neighbours are visited in ascending node order, so the first route found
  // is the canonical one. This is the sweep's own routine, kept line for line:
  // a path that differs here is a path that differs there, and the warden
  // would be placed against the wrong one.
  function bfsPath(adj, start, goal) {
    if (start === goal) return [start];
    var prev = {};
    prev[start] = start;
    var queue = [start];
    for (var head = 0; head < queue.length; head++) {
      var node = queue[head];
      var neighbours = adj[node].slice().sort(byNumber);
      for (var i = 0; i < neighbours.length; i++) {
        var nxt = neighbours[i];
        if (prev[nxt] !== undefined) continue;
        prev[nxt] = node;
        if (nxt === goal) {
          var path = [nxt];
          while (prev[path[path.length - 1]] !== path[path.length - 1]) {
            path.push(prev[path[path.length - 1]]);
          }
          return path.reverse();
        }
        queue.push(nxt);
      }
    }
    return null;
  }

  // The hop count from `start` to every node, -1 where there is none.
  function bfsDepth(adj, start, count) {
    var depth = [];
    var i;
    for (i = 0; i < count; i++) depth[i] = -1;
    depth[start] = 0;
    var queue = [start];
    for (var head = 0; head < queue.length; head++) {
      var node = queue[head];
      var neighbours = adj[node].slice().sort(byNumber);
      for (var j = 0; j < neighbours.length; j++) {
        var nxt = neighbours[j];
        if (depth[nxt] < 0) {
          depth[nxt] = depth[node] + 1;
          queue.push(nxt);
        }
      }
    }
    return depth;
  }

  // The region graph: rooms first, corridor regions after. Read back out of
  // the carved grid rather than kept alongside it, so the graph the generator
  // reasons about is the graph a reader can derive from `rows` and `rooms`.
  function regionGraph(canvas) {
    var width = canvas.w;
    var height = canvas.h;
    var rooms = canvas.rooms;
    var roomCount = rooms.length;
    var adj = [];
    var i;
    for (i = 0; i < roomCount; i++) adj.push([]);
    var seen = new Set();
    var corridors = sortedSet(canvas.corr);
    for (var c = 0; c < corridors.length; c++) {
      var index = corridors[c];
      if (seen.has(index)) continue;
      var node = adj.length;
      adj.push([]);
      seen.add(index);
      var stack = [index];
      while (stack.length) {
        var here = stack.pop();
        var x = here % width;
        var y = Math.floor(here / width);
        var around = [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]];
        for (var s = 0; s < 4; s++) {
          var nx = around[s][0];
          var ny = around[s][1];
          if (!(nx >= 0 && nx < width && ny >= 0 && ny < height)) continue;
          var other = ny * width + nx;
          var room = canvas.owner[other];
          if (room >= 0) {
            pushUnique(adj[node], room);
          } else if (canvas.corr.has(other) && !seen.has(other)) {
            seen.add(other);
            stack.push(other);
          }
        }
      }
    }
    // Two rooms sharing a tile edge are neighbours with no corridor.
    for (var r = 0; r < rooms.length; r++) {
      var x0 = rooms[r][0], y0 = rooms[r][1], w0 = rooms[r][2], h0 = rooms[r][3];
      for (var yy = y0; yy < y0 + h0; yy++) {
        for (var xx = x0; xx < x0 + w0; xx++) {
          var sides = [[xx + 1, yy], [xx - 1, yy], [xx, yy + 1], [xx, yy - 1]];
          for (var k = 0; k < 4; k++) {
            var nx2 = sides[k][0];
            var ny2 = sides[k][1];
            if (!(nx2 >= 0 && nx2 < width && ny2 >= 0 && ny2 < height)) continue;
            var neighbour = canvas.owner[ny2 * width + nx2];
            if (neighbour >= 0 && neighbour !== r) {
              pushUnique(adj[r], neighbour);
              pushUnique(adj[neighbour], r);
            }
          }
        }
      }
    }
    // The flood above only ever writes a corridor node's edge, so the region
    // graph is made undirected here, the way the sweep does.
    for (var n = 0; n < adj.length; n++) {
      var neighbours = adj[n].slice().sort(byNumber);
      for (var q = 0; q < neighbours.length; q++) pushUnique(adj[neighbours[q]], n);
    }
    return adj;
  }

  // The room graph: two rooms joined directly or through one corridor. A
  // corridor that serves three rooms joins all three pairs, which is the
  // sweep's rule and the reason a gallery corridor reads as an edge between
  // every pair of rooms it runs past.
  function roomGraphOf(adj, roomCount) {
    var roomAdj = [];
    var i;
    for (i = 0; i < roomCount; i++) roomAdj.push([]);
    for (var node = 0; node < adj.length; node++) {
      var low = adj[node].filter(function (other) { return other < roomCount; })
                          .sort(byNumber);
      if (node < roomCount) {
        for (var a = 0; a < low.length; a++) {
          if (low[a] !== node) {
            pushUnique(roomAdj[node], low[a]);
            pushUnique(roomAdj[low[a]], node);
          }
        }
      }
      for (var b = 0; b < low.length; b++) {
        for (var c = b + 1; c < low.length; c++) {
          pushUnique(roomAdj[low[b]], low[c]);
          pushUnique(roomAdj[low[c]], low[b]);
        }
      }
    }
    return roomAdj;
  }

  // A tile of `room` a thing can stand on. The middle tile, as everywhere else
  // in the generator, unless the room is a stamped one: a hand-drawn room is
  // not a filled rectangle, so its middle may be a drawn wall, and an anchor
  // on a wall is an anchor nothing can walk to. `prefer` is the room's own
  // named anchor - the warden letter of a stamped hall, the `poi` letter of a
  // stamped landmark - and it wins whenever it is walkable, which is what a
  // stamp is for.
  function standIn(canvas, room, prefer) {
    var box = canvas.rooms[room];
    var middle = center([box[0], box[1], box[2], box[3]]);
    if (prefer !== null && prefer !== undefined
        && canvas.walk.has(prefer[1] * canvas.w + prefer[0])) {
      return prefer;
    }
    if (canvas.walk.has(middle[1] * canvas.w + middle[0])) return middle;
    for (var yy = box[1]; yy < box[1] + box[3]; yy++) {
      for (var xx = box[0]; xx < box[0] + box[2]; xx++) {
        if (canvas.walk.has(yy * canvas.w + xx)) return [xx, yy];
      }
    }
    return middle;
  }

  // The stamped room of a role, the first one placed, or null. One per role is
  // the rule the layout stage places by, so a floor with two of a role takes
  // the first and the rest are ordinary rooms with a story-room shape.
  function stamped(canvas, role) {
    for (var i = 0; i < canvas.stamps.length; i++) {
      if (canvas.stamps[i].role === role) return canvas.stamps[i];
    }
    return null;
  }

  // One named anchor of a placement as a tile, or null when it has none.
  function atOf(placement, name) {
    if (!placement) return null;
    var at = placement.anchors[name];
    return at ? [at[0], at[1]] : null;
  }

  // The graph stage: the stairs, the main path, the warden, the pois.
  //
  // Nothing is drawn here. Everything below is read out of the grid the layout
  // stage left, so the two stages cannot disagree about where a room is or
  // which rooms the path runs through. A stamped room is already the room its
  // role names, so it is used where a plain room would be chosen, and it is
  // never also chosen out of `offPath`, or one room would be two things at
  // once.
  function graphStage(canvas, spine, plan, section) {
    var upRoom = spine[0];
    var downRoom = spine[spine.length - 1];
    var up = center(head(canvas.rooms[upRoom]));
    var down = center(head(canvas.rooms[downRoom]));
    canvas.grid[up[1]][up[0]] = UP;
    canvas.grid[down[1]][down[0]] = DOWN;

    var adj = regionGraph(canvas);
    var roomAdj = roomGraphOf(adj, canvas.rooms.length);
    var graph = {
      adj: adj,
      roomAdj: roomAdj,
      roomCount: canvas.rooms.length,
      main: [],
      mainRooms: [],
      depth: [],
    };
    var path = bfsPath(adj, upRoom, downRoom);
    if (path !== null) {
      graph.main = path;
      graph.mainRooms = path.filter(function (node) { return node < graph.roomCount; });
    }
    graph.depth = bfsDepth(roomAdj, upRoom, graph.roomCount);

    var onPath = new Set(graph.mainRooms);
    var drawn = new Set();
    for (var s = 0; s < canvas.stamps.length; s++) drawn.add(canvas.stamps[s].room);
    // The farthest room off the path, then the next, then the next. The warden
    // takes the first, the landmark the second, the vault the third, each
    // sorted by hop count from the up-stair and then by room index so a tie
    // never depends on a draw.
    var offPath = [];
    for (var room = 0; room < graph.roomCount; room++) {
      if (!onPath.has(room) && !drawn.has(room)) offPath.push(room);
    }
    offPath.sort(function (a, b) {
      if (graph.depth[a] !== graph.depth[b]) return graph.depth[b] - graph.depth[a];
      return a - b;
    });
    var hall = stamped(canvas, 'warden-hall');
    var landmark = stamped(canvas, 'landmark');
    var vault = stamped(canvas, 'vault');
    var wardenRoom = hall ? hall.room : (offPath.length ? offPath[0] : upRoom);
    var landmarkRoom = landmark ? landmark.room
      : (offPath.length > 1 ? offPath[1] : wardenRoom);
    var vaultRoom = null;
    if (section.vault) {
      // A Section that names no vault has no vault to open, so the floor gets
      // no vault anchor and no vault point of interest out of the off-path
      // walk. The pool keeps a vault stamp off such a Section's floors
      // already, and this is the same rule read at the other end of the
      // floor: an anchor is the Section's promise, not the placer's to make.
      vaultRoom = vault ? vault.room : (offPath.length > 2 ? offPath[2] : null);
    }

    // A stamp reads as the room it sits in, so the room that holds the warden
    // hall, the landmark or the vault is named in `rooms`.
    if (!hall) canvas.rooms[wardenRoom][4] = 'hall';
    if (!landmark) canvas.rooms[landmarkRoom][4] = 'landmark';
    if (vaultRoom !== null && !vault) canvas.rooms[vaultRoom][4] = 'vault';

    var names = namesOf(section.pois, FALLBACK_POIS);
    var poiAt = standIn(canvas, landmarkRoom, atOf(landmark, 'poi'));
    var pois = [{
      at: [poiAt[0], poiAt[1]],
      name: (landmark && landmark.poi) ? landmark.poi
        : names[plan.flavour % names.length],
      stamp: landmark ? landmark.id : 'landmark',
    }];
    if (vaultRoom !== null && !vault) {
      var vaultAt = standIn(canvas, vaultRoom, null);
      pois.push({
        at: [vaultAt[0], vaultAt[1]],
        name: names[(plan.flavour + 1) % names.length],
        stamp: 'vault',
      });
    }

    // A leaf room is a room with one way in, and PLAN.md section 2 turns leaves
    // into secret rooms. The stamp rooms are spoken for already.
    var taken = new Set([wardenRoom, landmarkRoom]);
    if (vaultRoom !== null) taken.add(vaultRoom);
    var leaves = [];
    for (var leaf = 0; leaf < graph.roomCount; leaf++) {
      if (!taken.has(leaf) && !onPath.has(leaf) && roomAdj[leaf].length === 1) {
        leaves.push(leaf);
      }
    }
    var secrets = [];
    for (var i = 0; i < leaves.length && i < plan.secrets; i++) {
      var at = center(head(canvas.rooms[leaves[i]]));
      secrets.push([at[0], at[1]]);
    }
    // A used `?` is the secret, wherever the room sits (ADR 0013, Placement
    // 3). The stamped rooms are not leaves in this list - a secret room has no
    // door at all - so nothing is counted twice.
    for (var t = 0; t < canvas.stamps.length; t++) {
      if (canvas.stamps[t].secret) secrets.push(canvas.stamps[t].secret.slice());
    }

    var anchors = {
      up: [up[0], up[1]],
      down: [down[0], down[1]],
      warden: null,
      vault: null,
      landmark: [poiAt[0], poiAt[1]],
    };
    var wardenAt = standIn(canvas, wardenRoom, atOf(hall, 'warden'));
    anchors.warden = [wardenAt[0], wardenAt[1]];
    if (vaultRoom !== null) {
      var home = standIn(canvas, vaultRoom, null);
      anchors.vault = [home[0], home[1]];
    }
    return { graph: graph, anchors: anchors, pois: pois, secrets: secrets };
  }

  // ----------------------------------------------------------------- stage 4
  // the pop stream - the exact order of draws, and the spec's comment above
  // `_pop_stage` line for line. `rand(lo, hi)` is
  // `lo + floor(rng * (hi - lo + 1))` and `pick(n)` is `floor(rng * n)`.
  // ADR 0014's "Draw order" is normative and this is the same list.
  //
  // The candidates are read off the grid, in row-major order, BEFORE the
  // first draw, and cost no draw: every walkable tile at least STAIR_CLEAR
  // (7) tiles (Chebyshev) from both stairs. A tile is taken at most once.
  // Two more lists come off the same read, likewise for free: the tiles a
  // group leader may stand on (`clear` less every vault, hall and secret
  // room, which the graph stage has already named) and, per leader, the
  // small box of tiles a minion of that group may stand on.
  //
  // The budget is not a draw:
  //       budget = the count section["mobs"] names for this floor, else
  //                clamp(walkable // TILES_PER_MOB, MOBS_MIN, MOBS_MAX).
  // A Section that names a count names it for its own floors ("1": 4) and for
  // the rest ("from": 12); a Section that names none is the area budget above,
  // exactly as it was before the key existed. Either way it is read before the
  // first draw and moves no other stage. `mobBudget` is where both answers live.
  //
  // The hard caps are applied where the stage says and not before: 36
  // monsters a floor, 2 lone elites, 3 groups, 4 members to a group, and one
  // elite-led group per 8 rooms (never below 1 while the pack's
  // `groups.per_floor` still asks for a group). A cap that is hit stops
  // further DRAWS of that kind; it does not raise and it does not fail the
  // floor. The warden is outside the budget and outside every cap here.
  //
  //  1. Elites, first. `elite_count = rand(elite_lo, elite_hi)` from
  //     `section["elites"]["per_floor"]`, drawn ONCE and before the loop. A
  //     pack that names a count and no affix table still draws that count and
  //     then places nothing, so the stream does not move when only the table
  //     changes. Then, per elite, in this order: a family by weight, an affix
  //     by index from `["affixes"]`, then a tile.
  //  2. Groups, next. `group_count = rand(group_lo, group_hi)` from
  //     `section["groups"]["per_floor"]`, drawn once before its loop, for the
  //     same reason. Then, per group, in this order: the minion count
  //     `rand(minion_lo, minion_hi)` capped to GROUP_MEMBERS_MAX - 1, the
  //     leader's family, the leader's affix (only when `groups.leader` is
  //     `elite` and the pack names affixes), the leader's tile, and then per
  //     minion a family - only when `same_family` is false - and a tile within
  //     MINION_REACH (2, Chebyshev) of the leader and in the leader's own room
  //     or corridor region. The leash is neither a draw nor a placement: it is
  //     a number the pack wrote, so it rides on every member's spawn the moment
  //     a group exists, and on none of them when the Section named none.
  //  3. Randoms, last, filling the budget the elites and the groups left. For
  //     each, in order: a family by weight, then a tile. A pack that names no
  //     elite and no group therefore carries exactly the budget.
  //  4. Chests: count = min(rand(2, 2 + quota // 8), the number of rooms off
  //     the main path no mob holds). Rooms off the main path first, farthest
  //     from the up-stair first; a room whose centre a monster, an elite, a
  //     minion or a leader already holds is dropped, and a table by index from
  //     CHEST_TABLES per chest. Every chest lands off the main path, so the
  //     whole of the floor's chest value is off it and exploring pays.
  //
  // The lists above are the ORDER THE DRAWS HAPPEN IN, and a placement is not
  // a draw: the tile is settled first, and a monster with nowhere to stand
  // spends NOTHING - no family, no affix. So a leader on a floor whose stamp
  // rooms leave no free tile, or a random on a floor whose clear tiles run
  // out, costs the stream no draw at all, and the chest count and every chest
  // table after it stay where the floor key says they are. One rule, four
  // places: elite, group leader, minion, random. The count draws - the elite
  // count, the group count and each group's minion count - are the exception
  // and stay where ADR 0014 lists them, ahead of the tile: a count is a
  // statement of its own, drawn whether or not the loop it opens goes on to
  // place anything.
  //
  // The ids follow the draws: a monster is `m<n>` in draw order, so the first
  // draw of the stage is `m0` and the counter never runs ahead of the stream.
  // A group is `g<n>` in group order.
  //
  // A spawn carries the closed keys of ADR 0014 and no others: `id`, `family`,
  // `at`, then `elite`, `group`, `leader` and `leash` where they apply
  // (`leader` as `true` and as nothing else, `leash` on every member of a
  // group and only when the Section named one). The eight are the whole set,
  // so a spawn carries no `hp`, `atk` or `xp`: a monster's stats are the
  // balance report's to compute off the same closed Section data.

  // Every walkable tile clear of both stairs, in row-major order.
  function eligible(canvas, stairs) {
    var width = canvas.w;
    var clear = [];
    var tiles = sortedSet(canvas.walk);
    for (var i = 0; i < tiles.length; i++) {
      var index = tiles[i];
      var x = index % width;
      var y = Math.floor(index / width);
      var far = true;
      for (var s = 0; s < stairs.length; s++) {
        var gap = Math.max(Math.abs(x - stairs[s][0]), Math.abs(y - stairs[s][1]));
        if (gap < STAIR_CLEAR) {
          far = false;
          break;
        }
      }
      if (far) clear.push([x, y]);
    }
    return clear;
  }

  // ---- the spread: which of those tiles a monster stands on ----
  //
  // The pool is walked in the seed's order and the first free tile wins, so
  // without this every floor packed its monsters into its top rows. The fix
  // costs no draw: the tiles are REORDERED, not chosen from, and the first
  // free tile is still the one that wins. A draw-free rule keeps the pop
  // stream reading the same in both languages, which is PLAN.md section 2's
  // sub-seed rule.
  //
  // The order is a rank per tile, lowest first, ties broken row-major. The
  // rank is a 32-bit mix of the floor key and the tile's own coordinates, and
  // both halves are plain integer arithmetic so a twin can write the same five
  // lines and get the same floor.

  // The string as UTF-8 bytes, which is what the spec hashes. A lone surrogate
  // is refused rather than replaced: the spec raises on one, and a floor key
  // never carries one.
  function utf8Bytes(text) {
    var out = [];
    for (var i = 0; i < text.length; i++) {
      var code = text.charCodeAt(i);
      if (code < 0x80) {
        out.push(code);
      } else if (code < 0x800) {
        out.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
      } else if (code >= 0xd800 && code <= 0xdbff) {
        if (i + 1 >= text.length) throw new Error('a floor key carries a lone surrogate');
        var low = text.charCodeAt(i + 1);
        if (low < 0xdc00 || low > 0xdfff) {
          throw new Error('a floor key carries a lone surrogate');
        }
        var point = 0x10000 + ((code - 0xd800) << 10) + (low - 0xdc00);
        out.push(0xf0 | (point >> 18), 0x80 | ((point >> 12) & 0x3f),
                 0x80 | ((point >> 6) & 0x3f), 0x80 | (point & 0x3f));
        i += 1;
      } else if (code >= 0xdc00 && code <= 0xdfff) {
        throw new Error('a floor key carries a lone surrogate');
      } else {
        out.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f),
                 0x80 | (code & 0x3f));
      }
    }
    return out;
  }

  // The floor key as a 32-bit number: FNV-1a over its UTF-8 bytes. FNV-1a is
  // the same hash the v2 twin and the benches checksum with. Every step is a
  // mask or a shift, so `Math.imul` and `>>> 0` are the same function.
  function keySalt(floorKey) {
    var bytes = utf8Bytes(String(floorKey));
    var h = 0x811C9DC5;
    for (var i = 0; i < bytes.length; i++) {
      h = Math.imul(h ^ bytes[i], 0x01000193) >>> 0;
    }
    return h;
  }

  // Where one tile falls in its floor's spread order, 0 to 2**32-1. Two
  // multiplies, two shifts, no table: the coordinates go in through a
  // multiply-shift of their own so that neighbouring tiles do not land on
  // neighbouring ranks, and the high bits are folded back down so a rank is
  // not read mostly out of the low half of the multiply.
  function tileRank(salt, x, y) {
    var h = (salt ^ Math.imul(x + 1, 0x9E3779B1)) >>> 0;
    h = (Math.imul(h, 0x85EBCA6B) + Math.imul(y + 1, 0xC2B2AE35)) >>> 0;
    h = (h ^ (h >>> 15)) >>> 0;
    h = Math.imul(h, 0x2545F491) >>> 0;
    return (h ^ (h >>> 13)) >>> 0;
  }

  // `tiles`, in the order this floor's seed scatters them: the same list,
  // permuted, so the pool a floor can place on is exactly the pool it could
  // place on before. The `(y, x)` tail of the key makes the order total, so
  // two tiles that rank the same are still placed in a fixed order.
  function spread(tiles, salt) {
    var out = tiles.slice();
    out.sort(function (p, q) {
      var rp = tileRank(salt, p[0], p[1]);
      var rq = tileRank(salt, q[0], q[1]);
      if (rp !== rq) return rp - rq;
      if (p[1] !== q[1]) return p[1] - q[1];
      return p[0] - q[0];
    });
    return out;
  }

  // `clear` less every room a group leader may not stand in. The graph stage
  // has already named what is spoken for: the warden's room and the vault are
  // the two stamp shapes in `rooms[i][4]`, and a secret room is a leaf room
  // whose centre is in `secrets`. The result is a filter of `clear` and keeps
  // whatever order `clear` is in, so a leader pool is the same spread walk
  // with fewer tiles in it.
  function stampFree(canvas, clear, secrets) {
    var spokenFor = new Set();
    for (var i = 0; i < canvas.rooms.length; i++) {
      if (STAMP_ROOMS.indexOf(canvas.rooms[i][4]) >= 0) spokenFor.add(i);
    }
    for (var t = 0; t < secrets.length; t++) {
      var tile = secrets[t];
      for (var j = 0; j < canvas.rooms.length; j++) {
        var room = canvas.rooms[j];
        if (room[0] <= tile[0] && tile[0] < room[0] + room[2]
            && room[1] <= tile[1] && tile[1] < room[1] + room[3]) {
          spokenFor.add(j);
        }
      }
    }
    var blocked = new Set();
    var rooms = sortedSet(spokenFor);
    for (var k = 0; k < rooms.length; k++) {
      var box = canvas.rooms[rooms[k]];
      for (var yy = box[1]; yy < box[1] + box[3]; yy++) {
        for (var xx = box[0]; xx < box[0] + box[2]; xx++) {
          blocked.add(yy * canvas.w + xx);
        }
      }
    }
    var out = [];
    for (var c = 0; c < clear.length; c++) {
      if (!blocked.has(clear[c][1] * canvas.w + clear[c][0])) out.push(clear[c]);
    }
    return out;
  }

  // The tiles within `reach` of `tile`, in row-major order. Row-major, and NOT
  // the spread order the pop stage walks its pools in, and that difference is
  // the point: a minion is placed within MINION_REACH of its own leader, and
  // scattering a twenty-five tile box would scatter a group across the floor.
  function neighbourhood(tile, width, height, reach) {
    var out = [];
    for (var yy = Math.max(0, tile[1] - reach); yy < Math.min(height, tile[1] + reach + 1); yy++) {
      for (var xx = Math.max(0, tile[0] - reach); xx < Math.min(width, tile[0] + reach + 1); xx++) {
        out.push([xx, yy]);
      }
    }
    return out;
  }

  // Each corridor tile's region, numbered in row-major first-tile order. Built
  // only when a group leader stands on a corridor, and kept for the rest of
  // the floor. `owner` already answers the room half of ADR 0014's "same room
  // or corridor region"; this answers the corridor half, and numbers the
  // regions by the row-major order of their first tile so a number never
  // depends on a hash seed.
  function corridorRegions(canvas) {
    var width = canvas.w;
    var regions = new Map();
    var number = 0;
    var corridors = sortedSet(canvas.corr);
    for (var i = 0; i < corridors.length; i++) {
      var start = corridors[i];
      if (regions.has(start)) continue;
      regions.set(start, number);
      var stack = [start];
      while (stack.length) {
        var here = stack.pop();
        var x = here % width;
        var y = Math.floor(here / width);
        var around = [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]];
        for (var s = 0; s < 4; s++) {
          var nx = around[s][0];
          var ny = around[s][1];
          if (!(nx >= 0 && nx < width && ny >= 0 && ny < canvas.h)) continue;
          var other = ny * width + nx;
          if (canvas.corr.has(other) && !regions.has(other)) {
            regions.set(other, number);
            stack.push(other);
          }
        }
      }
      number += 1;
    }
    return regions;
  }

  // Is `tile` in the leader's own room, or its own corridor region? ADR 0014
  // puts a minion "within Chebyshev 2 of the leader, in the same room or
  // corridor region". The straight line is half of that and the region is the
  // other half: two rooms are never laid closer than one wall, so a radius of
  // 2 can reach out of the leader's room and a search on distance alone would
  // put a minion through the wall.
  function sameRegion(canvas, leader, tile, regions) {
    var width = canvas.w;
    var here = leader[1] * width + leader[0];
    var there = tile[1] * width + tile[0];
    var room = canvas.owner[here];
    if (room >= 0) return canvas.owner[there] === room;
    return regions !== null && regions.has(there) && regions.get(there) === regions.get(here);
  }

  // The pop stage: elites, groups, randoms and chests.
  // `k` is `depth`, the floor's 1-based position in its Section, and it is
  // what the Section's own `mobs` table is read against (`mobBudget`). It is
  // read, never drawn, and no other stage of the floor is given it.
  function popStage(rng, canvas, graph, plan, section, up, down, secrets, floorKey, k) {
    // The pool, in the order this floor's seed scatters it. One sort, before
    // the first draw, and no draw spent on it: the pool is the same set of
    // tiles either way, only the order it is walked in changes.
    var clear = spread(eligible(canvas, [up, down]), keySalt(floorKey));
    // A leader's pool and a minion's box, both read off the grid before the
    // first draw, so neither costs one.
    var leadersClear = stampFree(canvas, clear, secrets);
    var clearSet = new Set();
    for (var c = 0; c < clear.length; c++) clearSet.add(clear[c][1] * canvas.w + clear[c][0]);
    // Two different questions, so two different sets. `taken` holds the TILES
    // take() has handed out, and `occupied` holds every tile a monster, an
    // elite, a minion or a chest holds. One set cannot answer both: a chest's
    // tile is only ever added to `occupied`.
    var taken = new Set();
    var occupied = new Set();
    // The index of the first candidate not yet taken. Tiles only ever leave the
    // list, so this walks forward and never looks back unless a leader or a
    // minion takes a tile out of order.
    var cursor = 0;
    // The corridor regions, built the first time a leader stands on one.
    var corrRegions = null;
    var families = readFamilies(section);
    var spawns = [];

    // The first free tile of `pool`, in the order `pool` is in. One routine,
    // three pools: `clear` is every walkable tile clear of the stairs, in this
    // floor's spread order, and its cursor walks forward because a tile only
    // ever leaves the list; a leader's pool is `clear` less the rooms that are
    // spoken for, which is the same order with fewer tiles; a minion's pool is
    // the small box around its leader, already filtered to `clear`, and the
    // leader's own region is applied on top of it.
    //
    // Two orders, and both are fixed: the spread order for the floor's own
    // tiles, row-major for the minion box, because a minion has to stay
    // within MINION_REACH of its own leader. Neither order is a draw, so the
    // pop stream is the same either way and this part can replay it from the
    // floor key.
    function take(pool, near) {
      var tile = null;
      if (near === undefined && pool === clear) {
        while (cursor < clear.length && taken.has(clear[cursor][1] * canvas.w + clear[cursor][0])) {
          cursor += 1;
        }
        if (cursor >= clear.length) return null;
        tile = clear[cursor];
        cursor += 1;
      } else {
        for (var p = 0; p < pool.length; p++) {
          var candidate = pool[p];
          if (taken.has(candidate[1] * canvas.w + candidate[0])) continue;
          if (near !== undefined && !sameRegion(canvas, near, candidate, corrRegions)) {
            continue;
          }
          tile = candidate;
          break;
        }
        if (tile === null) return null;
      }
      taken.add(tile[1] * canvas.w + tile[0]);
      occupied.add(tile[1] * canvas.w + tile[0]);
      return tile;
    }

    // One spawn, in the closed FloorPlan shape of ADR 0014. The keys are the
    // ADR's and the ADR's only: `id`, `family`, `at`, then `elite`, `group`,
    // `leader` and `leash` where they apply. `leader` is written as `true`
    // and as nothing else. `leash` rides along only when the Section named
    // one, and on EVERY member of the group rather than on the leader alone,
    // because the player reads it off a spawn record and asks any member for
    // it (part 420's `groupLeash`).
    function place(tile, family, elite, group, leader, leash) {
      var spawn = { id: 'm' + spawns.length, family: family, at: [tile[0], tile[1]] };
      if (elite !== null && elite !== undefined) spawn.elite = elite;
      if (group !== null && group !== undefined) spawn.group = group;
      if (leader) spawn.leader = true;
      if (leash !== null && leash !== undefined) spawn.leash = leash;
      spawns.push(spawn);
    }

    // The budget. MOBS_MAX is this clamp's ceiling and is also ADR 0014's cap
    // of 36 monsters, so nothing below can pass it. The elites and the group
    // members below are reserved out of it FIRST; the randoms fill whatever is
    // left over. A Section that names its own count for this floor (`mobs`)
    // replaces the area budget whole - see `mobBudget`.
    var budget = mobBudget(section, canvas.walk.size, k);

    // 1. Elites, in the ADR's order and before anything else. The count draw
    // is a statement of its own, made BEFORE the loop: a pack with an elite
    // count and no affix table has to consume exactly the same draw a pack
    // with one does. Per elite: a family, an affix by index, then a tile - and
    // the tile is placed FIRST, so an elite whose floor has no clear tile left
    // spends no family and no affix either. LONE_ELITES_MAX stops the loop: a
    // cap that is hit stops further draws of that kind, it does not raise and
    // it does not fail the floor.
    var elites = readElites(section);
    var eliteCount = rand(rng, elites.lo, elites.hi);
    var lone = 0;
    for (var e = 0; e < eliteCount; e++) {
      if (!elites.affixes.length) continue;
      if (lone >= LONE_ELITES_MAX || spawns.length >= budget) break;
      var eliteTile = take(clear);
      if (eliteTile === null) break;
      place(eliteTile, drawFamily(rng, families),
            elites.affixes[pick(rng, elites.affixes.length)], null, false, null);
      lone += 1;
    }

    // 2. Groups. The count draw is a statement of its own here too. Per group,
    // in the ADR's order: the minion count, the leader's family, the leader's
    // affix when the group is led by an elite, the leader's tile, and then per
    // minion a family (only when `same_family` is false) and a tile within
    // MINION_REACH of the leader and in the leader's own room or corridor
    // region. The leader's tile is placed before its two draws, for the
    // elites' own reason.
    //
    // Two caps stop the loop, and both stop DRAWS rather than only placement:
    // GROUPS_MAX groups a floor, and one elite-led group per
    // ROOMS_PER_ELITE_GROUP rooms - never below one, while the Section's own
    // `groups.per_floor` still asks for a group at all.
    var groups = readGroups(section);
    var asksForGroup = groups.lo > 0 || groups.hi > 0;
    var eliteLedCap = asksForGroup
      ? Math.max(1, Math.floor(graph.roomCount / ROOMS_PER_ELITE_GROUP))
      : 0;
    var groupCount = rand(rng, groups.lo, groups.hi);
    var eliteLed = 0;
    for (var number = 0; number < groupCount; number++) {
      if (number >= GROUPS_MAX || spawns.length >= budget) break;
      if (groups.leader === 'elite' && eliteLed >= eliteLedCap) break;
      var minionCount = Math.min(rand(rng, groups.minionLo, groups.minionHi),
                                 GROUP_MEMBERS_MAX - 1);
      var leaderTile = take(leadersClear);
      if (leaderTile === null) break;
      var leaderFamily = drawFamily(rng, families);
      var leaderAffix = null;
      if (groups.leader === 'elite' && elites.affixes.length) {
        leaderAffix = elites.affixes[pick(rng, elites.affixes.length)];
      }
      if (canvas.owner[leaderTile[1] * canvas.w + leaderTile[0]] < 0 && corrRegions === null) {
        corrRegions = corridorRegions(canvas);
      }
      var groupId = 'g' + number;
      place(leaderTile, leaderFamily, leaderAffix, groupId, true, groups.leash);
      if (groups.leader === 'elite') eliteLed += 1;
      // The box is a property of the leader, not of the minion, so it is built
      // once per group. take() drops the tiles it hands out, so the second
      // minion reads the same box and gets the next free tile in it.
      var hood = neighbourhood(leaderTile, canvas.w, canvas.h, MINION_REACH);
      var box = [];
      for (var h = 0; h < hood.length; h++) {
        if (clearSet.has(hood[h][1] * canvas.w + hood[h][0])) box.push(hood[h]);
      }
      for (var m = 0; m < minionCount; m++) {
        if (spawns.length >= budget) break;
        var minionTile = take(box, leaderTile);
        if (minionTile === null) break;
        place(minionTile, groups.sameFamily ? leaderFamily : drawFamily(rng, families),
              null, groupId, false, groups.leash);
      }
    }

    // 3. Randoms, filling the budget the elites and the groups left. Per
    // random: a family, then a tile - and the tile is placed first, for the
    // same reason as the three above. A pack that names no elite and no group
    // therefore carries exactly the budget and nothing else.
    // The count is read ONCE, as `range(budget - len(spawns))` reads it: a
    // `for (r = 0; r < budget - spawns.length; r++)` re-reads a bound that
    // falls as fast as the counter rises, and halves the budget's monsters.
    var randoms = budget - spawns.length;
    for (var r = 0; r < randoms; r++) {
      var randomTile = take(clear);
      if (randomTile === null) break;
      place(randomTile, drawFamily(rng, families), null, null, false, null);
    }

    // 4. Chests, off the main path, farthest from the up-stair first.
    var mainRooms = new Set(graph.mainRooms);
    var offPath = [];
    for (var room = 0; room < graph.roomCount; room++) {
      if (!mainRooms.has(room)) offPath.push(room);
    }
    offPath.sort(function (a, b) {
      if (graph.depth[a] !== graph.depth[b]) return graph.depth[b] - graph.depth[a];
      return a - b;
    });
    var spots = [];
    for (var s2 = 0; s2 < offPath.length; s2++) {
      spots.push([center(head(canvas.rooms[offPath[s2]])), offPath[s2]]);
    }
    var free = [];
    for (var f = 0; f < spots.length; f++) {
      if (!occupied.has(spots[f][0][1] * canvas.w + spots[f][0][0])) free.push(spots[f]);
    }
    var chests = [];
    var chestCount = Math.min(rand(rng, 2, 2 + Math.floor(plan.quota / 8)), free.length);
    for (var n = 0; n < chestCount; n++) {
      var chestTile = free[n][0];
      occupied.add(chestTile[1] * canvas.w + chestTile[0]);
      chests.push({
        id: 'c' + n,
        at: [chestTile[0], chestTile[1]],
        table: CHEST_TABLES[pick(rng, CHEST_TABLES.length)],
      });
    }
    return { spawns: spawns, chests: chests };
  }

  // ----------------------------------------------------------------- stage 5
  // the validate stage - the checks the property sweep runs, run again here
  // before the caller ever sees the floor. A failure is not a bug in the floor,
  // it is a bad draw: the retry ladder draws the same floor key with `|try{n}`
  // appended and does it again.
  //
  // Nothing is drawn here either. The stage reads the plan it was handed and
  // answers one question: is this floor good enough to ship?

  // Every walkable tile 4-connected to `start`.
  function flood(canvas, start) {
    var width = canvas.w;
    var seen = new Set();
    seen.add(start[1] * width + start[0]);
    var stack = [start];
    while (stack.length) {
      var at = stack.pop();
      var x = at[0];
      var y = at[1];
      var around = [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]];
      for (var s = 0; s < 4; s++) {
        var nx = around[s][0];
        var ny = around[s][1];
        if (!(nx >= 0 && nx < width && ny >= 0 && ny < canvas.h)) continue;
        var other = ny * width + nx;
        if (canvas.walk.has(other) && !seen.has(other)) {
          seen.add(other);
          stack.push([nx, ny]);
        }
      }
    }
    return seen;
  }

  // What one chest is worth: the pack's table, else 1 when unmapped.
  function chestValue(section, table) {
    var values = section.chest_values;
    if (!isPlainObject(values)) return 1;
    var worth = values[table];
    if (worth === undefined) worth = 1;
    return (typeof worth === 'number' && Number.isInteger(worth)) ? worth : 1;
  }

  // The cyclomatic number of the room graph: edges - nodes + 1.
  function loopCount(graph) {
    var edges = 0;
    for (var i = 0; i < graph.roomAdj.length; i++) edges += graph.roomAdj[i].length;
    return edges / 2 - graph.roomCount + 1;
  }

  // The rooms at room-graph distance 0 or 1 from the main path.
  function withinOneStep(graph) {
    var near = new Set(graph.mainRooms);
    for (var i = 0; i < graph.mainRooms.length; i++) {
      var around = graph.roomAdj[graph.mainRooms[i]];
      for (var j = 0; j < around.length; j++) near.add(around[j]);
    }
    return near;
  }

  // Every property the sweep asserts, answered on the plan itself. The sweep
  // checks the same list from the outside; here it is the generator refusing to
  // ship a floor that would fail.
  function validateFloor(floor, canvas, graph, section) {
    var rooms = floor.rooms;
    var anchors = floor.anchors;
    if (rooms.length < 2 || !floor.pois.length) return false;
    if (anchors.up === null || anchors.down === null || anchors.warden === null) {
      return false;
    }
    var up = anchors.up;
    var down = anchors.down;
    if (up[0] === down[0] && up[1] === down[1]) return false;

    // One connected component, and nothing carved that belongs to no room and
    // no corridor: the rooms and the corridors tile the walkable set.
    var reach = flood(canvas, up);
    if (reach.size !== canvas.walk.size) return false;
    // `owned` and not the rectangles: a stamped room is a drawing, so its
    // walkable tiles are counted as they are laid rather than as `w * h`. For a
    // floor of plain rooms the two are the same number.
    if (canvas.owned + canvas.corr.size !== canvas.walk.size) return false;

    // Which room a named tile is in, by the room's rectangle.
    function roomOf(tile) {
      for (var index = 0; index < rooms.length; index++) {
        if (rooms[index][0] <= tile[0] && tile[0] < rooms[index][0] + rooms[index][2]
            && rooms[index][1] <= tile[1] && tile[1] < rooms[index][1] + rooms[index][3]) {
          return index;
        }
      }
      return -1;
    }

    function reachable(tile) {
      return reach.has(tile[0] + tile[1] * canvas.w);
    }

    var names = Object.keys(anchors);
    for (var i = 0; i < names.length; i++) {
      if (anchors[names[i]] !== null && !reachable(anchors[names[i]])) return false;
    }
    for (var p = 0; p < floor.pois.length; p++) {
      if (!reachable(floor.pois[p].at)) return false;
    }
    for (var s = 0; s < floor.secrets.length; s++) {
      if (!reachable(floor.secrets[s])) return false;
    }
    for (var m = 0; m < floor.spawns.length; m++) {
      if (!reachable(floor.spawns[m].at)) return false;
    }
    for (var c = 0; c < floor.chests.length; c++) {
      if (!reachable(floor.chests[c].at)) return false;
    }

    // The main path, the warden off it, and the stairs in one component.
    if (!graph.mainRooms.length) return false;
    var upRoom = roomOf(anchors.up);
    var downRoom = roomOf(anchors.down);
    var wardenRoom = roomOf(anchors.warden);
    if (upRoom < 0 || downRoom < 0 || wardenRoom < 0) return false;
    if (bfsPath(graph.roomAdj, upRoom, downRoom) === null) return false;
    if (graph.mainRooms.indexOf(wardenRoom) >= 0) return false;

    if (graph.roomCount >= 12 && loopCount(graph) < LOOPS_MIN) return false;
    if (withinOneStep(graph).size < 0.40 * graph.roomCount) return false;
    if (floor.chests.length) {
      var total = 0;
      var off = 0;
      for (var x = 0; x < floor.chests.length; x++) {
        var worth = chestValue(section, floor.chests[x].table);
        total += worth;
        if (graph.mainRooms.indexOf(roomOf(floor.chests[x].at)) < 0) off += worth;
      }
      if (total && off < 0.60 * total) return false;
    }
    // The spec's last check is that the plan serialises to JSON. Everything in
    // a FloorPlan here is a whole number, a boolean, null or a string, so that
    // holds by construction - and the parity harness canonicalises every floor
    // it compares, which is the same check run for real.
    return true;
  }

  // ----------------------------------------------------------------- the door

  // The layout stage's output, in the shape the parity harness compares.
  function layoutOf(canvas, spine, missing) {
    return {
      rows: canvasRows(canvas),
      rooms: canvas.rooms.map(function (room) {
        return [room[0], room[1], room[2], room[3], room[4]];
      }),
      stamps: canvas.stamps,
      spine: spine,
      missing: missing,
    };
  }

  // One draw of one floor: the five stages, kept open at their boundaries so a
  // parity failure can name the stage it starts in.
  //
  // Three streams are opened, one for each stage that draws, and the graph and
  // validate stages open none. Every stream name is the floor key and the stage
  // name, exactly as PLAN.md section 2 writes them, so a stage can be replayed
  // on its own.
  //
  // `failed` is "" for a floor that came through and for one that gave up for
  // an ordinary reason, and `stamp:<role>` for a required stamp that would not
  // place - which is a defect and not a bad draw: the retry ladder is meant to
  // fix a bad draw, and a floor that fell back to v2 over a stamp is a floor
  // the author has to hear about (ADR 0013, Placement 4).
  function v3Attempt(floorKey, width, height, section, floorKind, stampPack,
                     depth, pinned) {
    var planRng = D.prng('v3|' + floorKey + '|plan');
    var layoutRng = D.prng('v3|' + floorKey + '|layout');
    var popRng = D.prng('v3|' + floorKey + '|pop');

    var plan = planStage(planRng, section, floorKind);
    var canvas = makeCanvas(width, height);
    var pool = stampPool(section, stampPack || [], depth);
    var laid = layoutStage(layoutRng, canvas, plan, pool, !!pinned);
    var spine = laid.spine;
    var missing = laid.missing;
    var out = {
      plan: plan,
      layout: layoutOf(canvas, spine, missing),
      graph: null,
      pop: null,
      floor: null,
      failed: '',
    };
    if (spine.length < 2 || missing.length) {
      out.failed = missing.length ? 'stamp:' + missing[0] : '';
      return out;
    }

    var graphed = graphStage(canvas, spine, plan, section);
    var graph = graphed.graph;
    out.graph = {
      anchors: graphed.anchors,
      pois: graphed.pois,
      secrets: graphed.secrets,
      main: graph.main,
      mainRooms: graph.mainRooms,
      depth: graph.depth,
      roomAdj: graph.roomAdj.map(function (row) { return row.slice().sort(byNumber); }),
      adj: graph.adj.map(function (row) { return row.slice().sort(byNumber); }),
    };
    if (graph.roomCount < ROOMS_FLOOR) return out;

    var anchors = graphed.anchors;
    var up = [anchors.up[0], anchors.up[1]];
    var down = [anchors.down[0], anchors.down[1]];
    var popped = popStage(popRng, canvas, graph, plan, section, up, down,
                          graphed.secrets, floorKey, depth);

    var floor = {
      gen: 3,
      w: width,
      h: height,
      rows: canvasRows(canvas),
      rooms: canvas.rooms.map(function (room) {
        return [room[0], room[1], room[2], room[3], room[4]];
      }),
      anchors: anchors,
      pois: graphed.pois,
      secrets: graphed.secrets,
      spawns: popped.spawns,
      chests: popped.chests,
      waypoint: plan.waypoint,
    };
    // The placements ride along on the floor: which stamp, which way up it is,
    // and where each of its letters stands.
    if (canvas.stamps.length) floor.stamps = canvas.stamps;
    out.pop = { spawns: popped.spawns, chests: popped.chests };
    out.floor = floor;
    // The spec refuses a floor its own checks reject and the ladder draws that
    // floor key again under `|try{n}`; the twin refuses the same one, or the
    // player would be handed a floor `vefr check` says is bad.
    if (!validateFloor(floor, canvas, graph, section)) out.floor = null;
    return out;
  }

  // The v2 floor of PLAN.md section 2's last resort, as a FloorPlan. v2 stays
  // pinned by hash and stays the fallback, so a caller that cannot have a v3
  // floor still gets the shape it always had: the rows, the stairs, and the
  // room rectangles v2 geometry can be read back into. No point of interest,
  // no secret, no monster, no chest.
  //
  // `defect` is the reason the v3 floor was not good enough, when the reason is
  // a stamp that would not place - `stamp:<role>` - and "" for every other
  // reason. ADR 0013's Placement 4 wants that fallback reported rather than
  // hidden.
  function fallback(seed, width, height, section, defect) {
    var quota = readRooms(section)[0];
    var rows = D.generateFloorV2(seed + '/fallback', width, height,
                                 Math.max(2, quota));
    var floor = {
      gen: 2,
      w: width,
      h: height,
      rows: rows,
      rooms: readRectangles(rows, width, height),
      anchors: {
        up: findGlyph(rows, UP, width, height),
        down: findGlyph(rows, DOWN, width, height),
        warden: null,
        vault: null,
        landmark: null,
      },
      pois: [],
      secrets: [],
      spawns: [],
      chests: [],
      waypoint: false,
    };
    if (defect) floor.stamp_defect = defect;
    return floor;
  }

  // The rectangles v2 geometry can be read back into, one per region. v2 draws
  // no room list, so the fallback reads the regions out of its own rows: every
  // 4-connected run of walkable tiles is one region, and its bounding box is
  // the rectangle. A v2 corridor and the room it runs to are one region, so the
  // boxes are generous by design.
  function readRectangles(rows, width, height) {
    var seen = [];
    for (var y = 0; y < height; y++) seen.push(new Array(width).fill(false));
    var rooms = [];
    for (var yy = 0; yy < height; yy++) {
      for (var xx = 0; xx < width; xx++) {
        if (seen[yy][xx] || rows[yy][xx] === WALL) continue;
        var stack = [[xx, yy]];
        seen[yy][xx] = true;
        var loX = xx, hiX = xx, loY = yy, hiY = yy;
        while (stack.length) {
          var at = stack.pop();
          var cx = at[0], cy = at[1];
          loX = Math.min(loX, cx);
          hiX = Math.max(hiX, cx);
          loY = Math.min(loY, cy);
          hiY = Math.max(hiY, cy);
          var around = [[cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]];
          for (var k = 0; k < 4; k++) {
            var nx = around[k][0];
            var ny = around[k][1];
            if (!(nx >= 0 && nx < width && ny >= 0 && ny < height) || seen[ny][nx]) {
              continue;
            }
            var glyph = rows[ny][nx];
            if (glyph !== FLOOR && glyph !== UP && glyph !== DOWN) continue;
            seen[ny][nx] = true;
            stack.push([nx, ny]);
          }
        }
        rooms.push([loX, loY, hiX - loX + 1, hiY - loY + 1, 'open']);
      }
    }
    return rooms;
  }

  // The first tile carrying `glyph`, in row-major order.
  function findGlyph(rows, glyph, width, height) {
    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        if (rows[y][x] === glyph) return [x, y];
      }
    }
    return null;
  }

  // Draw one v3 floor from `seed` and return its FloorPlan.
  //
  // `size` is the chosen `(w, h)` of the floor and nothing else. `section` is
  // a Section pack; only `id`, `rooms`, `families`, `elites`, `groups`,
  // `pois`, `stamps` and `vault` are read, every other key is defaulted, and a
  // missing key never raises. `floorKind` is one of `normal`, `treasure`,
  // `infested` or `hub`.
  //
  // `stampPack` is the pack's stamp set as `vefr.stamps.load` hands it over: a
  // list of read records, already sorted by id. The Section's own `stamps`
  // tags say which of them this Section may use, and `depth` is `k`, the
  // floor's 1-based position in its Section. `cycle` is the descent cycle the
  // floor belongs to and defaults to 0, the story.
  //
  // The floor key is `seed/section.id/cycle/depth` - the shape PLAN.md
  // section 2 writes, `run_seed/section.id/cycle/k` - so the same seed,
  // section, cycle and floor number is the same floor, and two ordinary floors
  // of one Section are two floors. A floor that fails stage 5 is drawn again
  // from the same key with `|try{n}` appended, up to MAX_TRIES times; after
  // that the caller gets v2 geometry with `gen: 2` and the same keys. The
  // fallback rate is the fraction of calls that come back with a `gen` other
  // than 3. The LAST try pins the required stamps (ADR 0013, Placement 4), and
  // a floor that falls back to v2 over a stamp carries `stamp_defect` naming
  // the role that would not place.
  //
  // Deterministic: `prng` is the only source of randomness, so the same
  // arguments always return the same plan. Throws for a `size` that is not a
  // pair of whole numbers of 8 or more, and for a `floorKind` outside
  // FLOOR_KINDS.
  function generateFloorV3(seed, size, section, floorKind, stampPack, depth, cycle) {
    var sizeRange = readSize(size);
    if (FLOOR_KINDS.indexOf(floorKind) < 0) {
      throw new Error('floor_kind must be one of ' + FLOOR_KINDS.join(', '));
    }
    var pack = isPlainObject(section) ? section : {};
    var rawId = pack.id;
    var sectionId = typeof rawId === 'string' ? rawId : (rawId ? String(rawId) : '');
    if (depth === undefined || depth === null) depth = 1;
    if (cycle === undefined || cycle === null) cycle = 0;
    var baseKey = seed + '/' + sectionId + '/' + cycle + '/' + depth;
    var records = Array.isArray(stampPack)
      ? stampPack.filter(function (record) { return isPlainObject(record); })
      : [];
    var defect = '';
    for (var attempt = 0; attempt <= MAX_TRIES; attempt++) {
      var floorKey = attempt === 0 ? baseKey : baseKey + '|try' + attempt;
      var got = v3Attempt(floorKey, sizeRange[0], sizeRange[1], pack, floorKind,
                          records, depth, attempt === MAX_TRIES);
      if (got.floor !== null) return got.floor;
      if (got.failed) defect = got.failed;
    }
    return fallback(String(seed), sizeRange[0], sizeRange[1], pack, defect);
  }

  // The constants the determinism rule names in both languages, in one place
  // the parity test reads and compares with the spec's. Two languages, one set
  // of constants: a twin that quietly agreed on 39 tiles and 41 is not a twin.
  D.v3Constants = {
    WALL: WALL,
    FLOOR: FLOOR,
    UP: UP,
    DOWN: DOWN,
    FLOOR_KINDS: FLOOR_KINDS,
    MAX_TRIES: MAX_TRIES,
    LOOPS_MIN: LOOPS_MIN,
    LOOPS_MAX: LOOPS_MAX,
    ROOMS_FLOOR: ROOMS_FLOOR,
    STAIR_CLEAR: STAIR_CLEAR,
    TILES_PER_MOB: TILES_PER_MOB,
    MOBS_MIN: MOBS_MIN,
    MOBS_MAX: MOBS_MAX,
    MOB_FLOOR_MAX: MOB_FLOOR_MAX,
    LONE_ELITES_MAX: LONE_ELITES_MAX,
    GROUPS_MAX: GROUPS_MAX,
    GROUP_MEMBERS_MAX: GROUP_MEMBERS_MAX,
    ROOMS_PER_ELITE_GROUP: ROOMS_PER_ELITE_GROUP,
    STAMP_ROOMS: STAMP_ROOMS,
    MINION_REACH: MINION_REACH,
    LEASH_MIN: LEASH_MIN,
    LEASH_MAX: LEASH_MAX,
    LEASH_DEFAULT: LEASH_DEFAULT,
    CHEST_TABLES: CHEST_TABLES,
    SHAPES: SHAPES,
    FALLBACK_POIS: FALLBACK_POIS,
    DEFAULT_ROOMS: DEFAULT_ROOMS,
    FLAVOURS: FLAVOURS,
    STAMP_ROUTE_ENDS: STAMP_ROUTE_ENDS,
    STAMP_ATTEMPTS: STAMP_ATTEMPTS,
    STAMP_REQUIRED_ROLES: STAMP_REQUIRED_ROLES,
    STAMP_ANY_TAG: STAMP_ANY_TAG,
  };

  // The stream names PLAN.md section 2 writes, for one floor key: each stage
  // that draws takes every one of its numbers from its own stream, so a
  // rewritten affix table can never move a wall.
  D.v3Streams = function (floorKey) {
    return {
      plan: 'v3|' + floorKey + '|plan',
      layout: 'v3|' + floorKey + '|layout',
      pop: 'v3|' + floorKey + '|pop',
    };
  };

  D.v3Attempt = v3Attempt;
  D.generateFloorV3 = generateFloorV3;
  // The monster count of one floor, for part 397's play-time descent: the
  // Section's own `mobs` for floor `k` where it names one, the area budget
  // otherwise. One implementation for both call sites in the player, beside
  // one in Python (`vefr.delve_v3.mob_budget`, which `vefr.delve._mob_budget`
  // calls the same way). `walkable` is the caller's own count of the floor's
  // walkable tiles and is never re-measured here.
  D.v3MobBudget = mobBudget;
})();
// -- delve v3 end --