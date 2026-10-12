  // ---- how a monster thinks ----
  // A monster walks the floor the way the hero does: over walkable
  // tiles, around corners and walls, never through them. Each turn the
  // walkable tiles are flooded once from wherever the thinking starts -
  // the hero, or a monster a lost one is drifting toward - and the
  // monster steps to the neighbour that is closest to (or furthest
  // from) that flood. Breadth-first, one cost per tile, so a tile four
  // paces the long way round is four, not zero. The neighbour order is
  // fixed - up, down, left, right - so a tie always breaks the same
  // way and a floor always plays out the same way. No randomness
  // anywhere in here.
  var DIRS = [[0, -1], [0, 1], [-1, 0], [1, 0]];
  // How near two tiles are the short way round, without the walls: the
  // strongest of the two axes, so eight tiles up and eight across is
  // eight and not sixteen. Sight, noise and the leash line are all
  // measured with it.
  function chebyshev(x1, y1, x2, y2) {
    return Math.max(Math.abs(x1 - x2), Math.abs(y1 - y2));
  }
  // A tile the flood may cross: on the map and not solid. Monsters and
  // the hero stand on walkable tiles too, so they are in the map - what
  // a single step may land on is `tileOpenForEnemy`'s business.
  function floorOpen(x, y) {
    if (x < 0 || y < 0 || y >= town.map.length || x >= town.map[0].length) return false;
    // The props part may be absent (a harness that loads only the monster parts).
    return !((town.legend[town.map[y][x]] || {}).solid)
      && !(typeof propBlocked === 'function' && propBlocked(x, y));
  }
  // Steps from (x, y) to every walkable tile. `dist` has the source at
  // 0 and no entry at all for a tile the flood never reached. The flood
  // stops `floodLimit` tiles (Manhattan) from its own source: the
  // monster turn sets that once, before any monster acts, to a little
  // past the farthest wake, so a turn never floods the far end of the
  // floor. It rides in a variable rather than an argument so the
  // signature stays `distMap(x, y)`; 0 (no monster turn has set it)
  // means unbounded. The turn's harness counter is fed from here too -
  // enemyTurn resets it per turn, so it always shows the last turn.
  var floodLimit = 0;
  function distMap(x, y) {
    var dist = {};
    var start = x + ',' + y;
    dist[start] = 0;
    var queue = [[x, y]];
    var stats = window.VEFR_FLOOD_STATS;
    if (stats) { stats.floods++; stats.tiles++; }
    for (var qi = 0; qi < queue.length; qi++) {
      var cx = queue[qi][0], cy = queue[qi][1];
      for (var i = 0; i < DIRS.length; i++) {
        var nx = cx + DIRS[i][0], ny = cy + DIRS[i][1];
        var away = manhattan(nx, ny, x, y);
        if (floodLimit && away > floodLimit) continue;
        var nk = nx + ',' + ny;
        if (dist[nk] !== undefined) continue;
        if (!floorOpen(nx, ny)) continue;
        dist[nk] = dist[cx + ',' + cy] + 1;
        queue.push([nx, ny]);
        if (stats) {
          stats.tiles++;
          if (away > stats.maxSpan) stats.maxSpan = away;
        }
      }
    }
    return dist;
  }
  // The turn's shared floods, one per source tile, each built the first
  // time something needs it and kept for the rest of the turn. The
  // floors are small and a flood is cheap, so a turn that never moves a
  // monster never pays for one.
  function turnMaps() { return { from: {} }; }
  function distances(maps, x, y) {
    var key = x + ',' + y;
    if (!maps.from[key]) maps.from[key] = distMap(x, y);
    return maps.from[key];
  }
  // One step along `dist`: the neighbour with the lowest count (dir 1),
  // or the highest (-1, for a monster running for its life). A tile
  // with no count is one the source cannot reach, and is never chosen.
  // A tie keeps the earlier neighbour in the fixed order, so the same
  // floor always plays out the same way. If the best tile is already
  // taken the monster holds rather than shuffling sideways, so two of
  // them nose to nose stay nose to nose. True means the step was onto
  // the hero, and the hero was hit.
  //
  // `leash` is the group's home map when this monster belongs to a
  // group (see below): a neighbour the home flood never reached, or
  // one further from home than the leash, is not a candidate at all,
  // so a member cannot step off the end of its line - in either
  // direction, chasing or running.
  function stepAlong(e, dist, dir, leash) {
    var best = null, bestVal = (dir > 0 ? Infinity : -Infinity);
    for (var i = 0; i < DIRS.length; i++) {
      var nx = e.at[0] + DIRS[i][0], ny = e.at[1] + DIRS[i][1];
      var d = dist[nx + ',' + ny];
      if (d === undefined) continue;
      if (leash && pastLeash(leash, nx, ny)) continue;
      if (dir > 0 ? (d >= bestVal) : (d <= bestVal)) continue;
      bestVal = d; best = [nx, ny];
    }
    if (!best) return false;
    if (best[0] === hero[0] && best[1] === hero[1]) return enemyAttack(e);
    if (!tileOpenForEnemy(best[0], best[1])) return false;
    e.face = faceOf(e.at, best);
    e.at = best;
    return false;
  }
  // The way a step from one tile to a neighbour points: the longer delta wins.
  function faceOf(from, to) {
    var dx = to[0] - from[0], dy = to[1] - from[1];
    if (Math.abs(dx) >= Math.abs(dy)) return dx < 0 ? 'left' : 'right';
    return dy < 0 ? 'up' : 'down';
  }
  // One step toward the group's home, on the home flood: the neighbour
  // with the LOWER count. A member stops within one tile of home and
  // then idles awake, so this is the whole of the walk back. Descending
  // by the same counts it came from, it can never step past the leash.
  function stepHome(e, leash) {
    var here = leash.map[e.at[0] + ',' + e.at[1]];
    if (here === undefined || here <= 1) return false;
    var best = null, bestVal = here;
    for (var i = 0; i < DIRS.length; i++) {
      var nx = e.at[0] + DIRS[i][0], ny = e.at[1] + DIRS[i][1];
      var d = leash.map[nx + ',' + ny];
      if (d === undefined || d >= bestVal) continue;
      bestVal = d; best = [nx, ny];
    }
    if (!best) return false;
    if (!tileOpenForEnemy(best[0], best[1])) return false;
    e.face = faceOf(e.at, best);
    e.at = best;
    return false;
  }
  // The nearest other living monster, by walking distance rather than
  // straight-line: a wall between two of them is a long way round. Ties
  // go to the first in the roster. Null when this one is alone.
  function nearestAlly(e, maps) {
    var from = distances(maps, e.at[0], e.at[1]);
    var best = null, bestDist = Infinity;
    for (var i = 0; i < enemies.length; i++) {
      var other = enemies[i];
      if (!other || !other.alive || other === e) continue;
      var d = from[other.at[0] + ',' + other.at[1]];
      if (d === undefined || d >= bestDist) continue;
      bestDist = d; best = other;
    }
    return best;
  }
  // Badly hurt: down to a third of the health it walked into the region
  // with. A monster that has never been touched is not.
  function badlyHurt(e) { return e.hp <= e.hp0 / 3; }

  // ---- groups, home and the leash ----
  // A group is the set of monsters that share a `group` id. Its home is
  // the tile its leader spawned on, and no member ever walks further
  // than `leash` steps from it - measured the long way round, over the
  // floor and around its walls, so a corridor between a member and its
  // home is the distance that counts.
  //
  // The ids, the leader mark and the leash ride on the baked spawn
  // records in `window.VEFR_ENEMIES`. `loadEnemies` (part 410) builds a
  // fresh live record for every spawn and copies across only the fields
  // the pack named a long time ago, so `prepareMinds` reads them here,
  // once per roster, and every question about a group is asked of the
  // fields it sets. A pack that names no group - every pack today -
  // leaves them empty and nothing below it runs.
  //
  // Nothing about a group is ever saved. `loadEnemies` builds a new
  // record per spawn, so a survivor is back on its spawn tile and
  // asleep the moment a region loads; the home maps below live in
  // memory for the length of the visit and are dropped with them.
  //
  // One map per group, and no ceiling on how many groups. There used to
  // be a cap of three here, on the reading that a fourth map cost more
  // than the turn budget allows. What the cap actually cost is a pack's
  // fourth group walking unheld: ADR 0014 says a member never steps
  // farther than `leash` from home, and it says it of every member, so a
  // home map that is refused is a member that chases the hero across the
  // floor and never walks home. The map is cut off at `leash + 1` steps
  // and the leash is at most 12, so one of them is thirteen rings of a
  // flood no wider than the group's own reach - a cost the three-group
  // case already pays, and the one a fourth group was asking for.
  var LEASH_DEFAULT = 6;       // what a group walks on if it names none
  var LEASH_MIN = 3;           // the closed range a pack may write
  var LEASH_MAX = 12;
  var mindHomes = {};          // group id -> {leash, map}, in memory only
  var mindRoster = null;       // the roster the fields below were set on
  var mindRegion = '';         // and the region it belongs to

  // The record this live monster was built from, by id. The live record
  // is a copy, so this is where the group keys still are.
  function rawSpawn(e) {
    var list = enemiesByRegion[regionName] || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i] && list[i].id === e.id) return list[i];
    }
    return null;
  }
  // Set the mind fields on a freshly loaded roster, once. Called at the
  // top of the monster turn and of the combat snapshot, both of which
  // see the same `enemies` array for as long as the region is loaded;
  // when `loadEnemies` builds the next one the identity changes and this
  // runs again, so a survivor starts asleep on every arrival. No awake
  // state is stored, and no save key is added for it.
  function prepareMinds() {
    if (enemies === mindRoster && regionName === mindRegion) return;
    mindRoster = enemies;
    mindRegion = regionName;
    mindHomes = {};
    for (var i = 0; i < enemies.length; i++) {
      var e = enemies[i];
      if (!e) continue;
      var raw = rawSpawn(e);
      // The tile it spawned on: home is a spawn tile, and a monster
      // that has walked away from it still knows the way back.
      e.spawn = Array.isArray(e.at) ? e.at.slice() : [0, 0];
      e.group = (raw && typeof raw.group === 'string') ? raw.group : '';
      e.leader = !!(raw && raw.leader === true);
      e.warden = !!(raw && raw.warden === true);
      e.awake = false;      // everyone is asleep until something wakes it
      e.grace = false;      // the free turn a group wake grants
      e.wakeSpread = true;  // nothing owed to a group yet
    }
  }
  // The living members of a group, lowest id first, so every question
  // about a group has the same answer on every run.
  function groupMembers(gid) {
    var out = [];
    for (var i = 0; i < enemies.length; i++) {
      var e = enemies[i];
      if (e && e.alive && e.group === gid) out.push(e);
    }
    out.sort(function (a, b) {
      return a.id < b.id ? -1 : (a.id > b.id ? 1 : 0);
    });
    return out;
  }
  // Its leader: the member marked `leader`, or - when the group names
  // none, which a pack may do - the living member with the lowest
  // sorted id. The leader is the only member a group's home hangs on.
  function groupLeader(gid) {
    var members = groupMembers(gid);
    for (var i = 0; i < members.length; i++) {
      if (members[i].leader) return members[i];
    }
    return members.length ? members[0] : null;
  }
  // How far the group may walk: the whole number the group itself
  // writes, inside the closed range, or the default. Read from the
  // leader's own record first, then from any member's, so a pack that
  // writes the leash once on the group is not asked to write it four
  // times.
  function groupLeash(gid) {
    var members = groupMembers(gid);
    for (var i = 0; i < members.length; i++) {
      var leash = rawSpawn(members[i]);
      leash = leash && leash.leash;
      if (typeof leash === 'number' && leash === Math.floor(leash)
          && leash >= LEASH_MIN && leash <= LEASH_MAX) return leash;
    }
    return LEASH_DEFAULT;
  }
  // The group's home: the tile its leader spawned on.
  function groupHome(gid) {
    var lead = groupLeader(gid);
    if (!lead) return null;
    return Array.isArray(lead.spawn) ? lead.spawn : lead.at;
  }
  // One flood from home, cut off at `limit` steps. Deliberately not
  // `distMap`: that one counts against the turn and publishes into
  // `window.VEFR_FLOOD_STATS`, and a home map is a floor-load map, not
  // a turn's work. The neighbour order is the same, so a tile two ways
  // round is two steps here as it is there.
  function homeReach(at, limit) {
    var dist = {};
    dist[at[0] + ',' + at[1]] = 0;
    var queue = [[at[0], at[1]]];
    for (var qi = 0; qi < queue.length; qi++) {
      var cx = queue[qi][0], cy = queue[qi][1];
      var d = dist[cx + ',' + cy];
      if (d >= limit) continue;
      for (var i = 0; i < DIRS.length; i++) {
        var nx = cx + DIRS[i][0], ny = cy + DIRS[i][1];
        var nk = nx + ',' + ny;
        if (dist[nk] !== undefined) continue;
        if (!floorOpen(nx, ny)) continue;
        dist[nk] = d + 1;
        queue.push([nx, ny]);
      }
    }
    return dist;
  }
  // The home map for this monster's group, built once and kept for the
  // visit. Every group gets one: a group whose map is missing is a group
  // that walks unheld, however many groups came before it.
  function homeMap(e) {
    if (!e || !e.group) return null;
    if (mindHomes[e.group]) return mindHomes[e.group];
    var home = groupHome(e.group);
    if (!home) return null;
    var leash = groupLeash(e.group);
    var entry = { leash: leash, map: homeReach(home, leash + 1) };
    mindHomes[e.group] = entry;
    return entry;
  }
  // The leash as `stepAlong` wants it, or nothing for a monster with no
  // group - which is how a lone monster and an elite keep behaving
  // exactly as they did before any of this.
  function leashOf(e) { return homeMap(e); }
  function pastLeash(leash, x, y) {
    var d = leash.map[x + ',' + y];
    // A tile the home flood never reached is past the end of the line
    // by definition, and so is one the map knows to be too far.
    return d === undefined || d > leash.leash;
  }
  // On the line: this member is as far from home as the leash allows,
  // so it fights from where it stands and does not walk. An adjacent
  // hero is still hit - the hero is not a step.
  function onLeashEdge(e, leash) {
    var d = leash.map[e.at[0] + ',' + e.at[1]];
    return d === undefined || d >= leash.leash;
  }
  // The warden: awake from the first turn of a floor, never asleep, and
  // it hunts. ADR 0015 owns where one stands and what its hall is; all
  // this needs is the mark on the spawn record, so the whole of the
  // behaviour hangs off this one predicate.
  function isWarden(e) { return !!(e && e.warden === true); }

