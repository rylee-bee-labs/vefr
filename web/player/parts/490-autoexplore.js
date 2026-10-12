  // ---- autoexplore ----
  // Step the hero toward the nearest unexplored tile, on a timer, and
  // stop the moment a person is needed: a lit monster, a wound, a dead
  // end, or the safety cap. Every step goes through move(), so turns,
  // monsters, fog and pickups stay honest. The status line speaks only
  // at start and stop - never each step - so a screen reader is not
  // drowned in a hundred tile names.
  var EXPLORE_PACE = 80;   // ms between steps: visible, still responsive
  var EXPLORE_CAP = 400;   // hard ceiling, so a strange map cannot loop
  var exploreTimer = null;
  var exploreSteps = 0;
  var exploreBtn = document.getElementById('explore');
  var exploreStatus = document.getElementById('explore-status');

  function exploring() { return exploreTimer !== null; }
  function exploreSay(msg) {
    if (exploreStatus) exploreStatus.textContent = msg || '';
  }
  function exploreStop(msg) {
    if (exploreTimer !== null) { window.clearTimeout(exploreTimer); exploreTimer = null; }
    exploreSteps = 0;
    if (exploreBtn) exploreBtn.setAttribute('aria-pressed', 'false');
    exploreSay(msg);
  }
  // A tile the hero may stand on: inside the map and not solid.
  function exploreOpen(x, y) {
    if (x < 0 || y < 0 || y >= town.map.length || x >= town.map[0].length) return false;
    return !((town.legend[town.map[y][x]] || {}).solid) && !propBlocked(x, y);
  }
  // Breadth-first over walkable tiles, from the hero. Enemies are walls
  // to the search: the fight belongs to the player, so route around it.
  // `order` is BFS order, so the first frontier tile found is nearest.
  function exploreBfs() {
    var dist = {}, parent = {}, order = [];
    var start = hero[0] + ',' + hero[1];
    dist[start] = 0;
    order.push(start);
    var queue = [[hero[0], hero[1]]];
    var dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
    for (var qi = 0; qi < queue.length; qi++) {
      var cx = queue[qi][0], cy = queue[qi][1];
      var ck = cx + ',' + cy;
      for (var i = 0; i < dirs.length; i++) {
        var nx = cx + dirs[i][0], ny = cy + dirs[i][1];
        var nk = nx + ',' + ny;
        if (dist[nk] !== undefined) continue;
        if (!exploreOpen(nx, ny) || enemyAt(nx, ny)) continue;
        dist[nk] = dist[ck] + 1;
        parent[nk] = ck;
        order.push(nk);
        queue.push([nx, ny]);
      }
    }
    return { dist: dist, parent: parent, order: order };
  }
  // Is this reachable tile itself dark, or beside a dark tile? If so,
  // reaching it (and the light the hero carries) reveals something new.
  function exploreFrontier(x, y) {
    if (!explored[x + ',' + y]) return true;
    var dirs = [[0, -1], [0, 1], [-1, 0], [1, 0]];
    for (var i = 0; i < dirs.length; i++) {
      if (!explored[(x + dirs[i][0]) + ',' + (y + dirs[i][1])]) return true;
    }
    return false;
  }
  // The nearest reachable tile that borders the dark; return only the
  // first step toward it. Null means there is nowhere left to walk.
  function exploreNextStep(bfs) {
    var start = hero[0] + ',' + hero[1];
    for (var i = 0; i < bfs.order.length; i++) {
      var key = bfs.order[i];
      if (bfs.dist[key] < 1) continue;   // never the hero's own tile
      var parts = key.split(',');
      if (!exploreFrontier(parseInt(parts[0], 10), parseInt(parts[1], 10))) continue;
      var cur = key;
      while (bfs.parent[cur] !== undefined && bfs.parent[cur] !== start) cur = bfs.parent[cur];
      if (bfs.parent[cur] === undefined) return null;
      var step = cur.split(',');
      return { dx: parseInt(step[0], 10) - hero[0], dy: parseInt(step[1], 10) - hero[1] };
    }
    return null;
  }
  // The nearest living enemy the light currently reaches, if any.
  function exploreSeenEnemy() {
    var lit = litNow();
    var best = null, bestDist = Infinity;
    enemies.forEach(function (e) {
      if (!e || !e.alive || !Array.isArray(e.at)) return;
      if (!lit[e.at[0] + ',' + e.at[1]]) return;
      var d = Math.abs(e.at[0] - hero[0]) + Math.abs(e.at[1] - hero[1]);
      if (d < bestDist) { bestDist = d; best = e; }
    });
    return best;
  }
  // "A rat comes into view.", "The Gaunt Wolf comes into view." - the
  // name's own article is kept rather than doubled.
  function enemyInView(name) {
    var n = String(name || 'something');
    var lower = n.toLowerCase();
    if (lower.indexOf('a ') === 0 || lower.indexOf('an ') === 0 || lower.indexOf('the ') === 0) {
      return n.charAt(0).toUpperCase() + n.slice(1) + ' comes into view.';
    }
    return 'A ' + n + ' comes into view.';
  }
  function exploreTick() {
    exploreTimer = null;
    var readerOpen = !document.getElementById('reader').hidden;
    var tradeOpen = !document.getElementById('trade').hidden;
    var menuOpen = !document.getElementById('menu').hidden;
    if (readerOpen || tradeOpen || menuOpen) { exploreStop('Stopped.'); return; }
    if (exploreSteps >= EXPLORE_CAP) { exploreStop('Stopped.'); return; }
    var seen = exploreSeenEnemy();
    if (seen) { exploreStop(enemyInView(seen.name)); return; }
    var step = exploreNextStep(exploreBfs());
    if (!step || (step.dx === 0 && step.dy === 0)) {
      exploreStop('Nothing left to explore here.');
      return;
    }
    var hpBefore = HERO_HP;
    var regionBefore = regionName;
    exploreSteps += 1;
    move(step.dx, step.dy);
    // A wound, a death-wake, or the enemy's own line stops the walk.
    var live = document.getElementById('combat-live');
    var said = live ? live.textContent : '';
    if (HERO_HP < hpBefore || regionName !== regionBefore
        || said === DEATH_LINE || said === STAIR_DEATH_LINE
        || said.indexOf(' hits you ') !== -1) {
      exploreStop('Stopped.');
      return;
    }
    exploreTimer = window.setTimeout(exploreTick, EXPLORE_PACE);
  }
  function startExplore() {
    if (exploring()) { exploreStop('Stopped.'); return; }
    if (!fogOn) { exploreSay("This place isn't dark enough to explore."); return; }
    exploreSteps = 0;
    exploreSay('Exploring...');
    if (exploreBtn) exploreBtn.setAttribute('aria-pressed', 'true');
    exploreTimer = window.setTimeout(exploreTick, EXPLORE_PACE);
  }
  if (exploreBtn) exploreBtn.addEventListener('click', startExplore);
  // A click anywhere else also stops the walk.
  document.addEventListener('click', function (e) {
    if (!exploring()) return;
    if (e.target && e.target.closest && e.target.closest('#explore')) return;
    exploreStop('Stopped.');
  });

