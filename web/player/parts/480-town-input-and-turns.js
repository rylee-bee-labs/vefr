  // ---- end the hero's step motion ----

  // The in-flight step, if any. Kept tiny: where it started, the tile
  // delta to travel, the way the hero faces, when it began, its rAF id.
  var heroAnim = null;
  var heroFacing = 'down';
  // The walk-sheet pose: which frame index to draw, whether it is
  // mirrored, and the one-step walk counter that advances per step.
  var heroSheetIdx = 0;
  var heroSheetMirror = false;
  var heroWalkStep = 0;
  // Which direction's frames to draw for the current facing, and whether
  // the picture flips: a missing side uses the other side's frames
  // mirrored, a missing up falls back to down.
  function heroSheetFrames() {
    var pick = sheetPick('hero', heroFacing);
    return pick.frames ? pick : null;
  }
  // Advance and publish the hero's pose. Only a hero with a sheet gets
  // window.VEFR_HERO_FRAME; a pack without one never gets the global at
  // all, so a harness reads null rather than a stale pose.
  function heroSetPose(state) {
    if (!heroHasSheet) return;
    var pick = heroSheetFrames();
    var frames = pick && pick.frames;
    var idx = heroSheetIdx;
    if (frames) {
      if (state === 'walk' && Array.isArray(frames.walk) && frames.walk.length) {
        idx = frames.walk[(heroWalkStep - 1) % frames.walk.length];
      } else if (Array.isArray(frames.idle) && frames.idle.length) {
        idx = frames.idle[0];
      }
    }
    heroSheetIdx = idx;
    heroSheetMirror = pick ? pick.mirror : false;
    window.VEFR_HERO_FRAME = { dir: heroFacing, state: state, frame: idx,
                               mirrored: heroSheetMirror };
  }
  function nowMs() {
    return (window.performance && window.performance.now)
      ? window.performance.now() : Date.now();
  }
  // Read at move time, never cached, so a change of preference is felt.
  function reducedMotion() {
    return !!(window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }
  // Where the hero is DRAWN right now: the settled tile when no step is
  // running, else the tweened tile plus its offset. Never moves the
  // game's hero.
  function heroPose() {
    var settled = { tile: [hero[0], hero[1]],
                    off: { dx: 0, dy: 0, lean: 0, squash: 0 } };
    if (!heroAnim) return settled;
    var p = (nowMs() - heroAnim.start) / STEP_MS;
    if (p >= 1) return settled;
    var off = stepMotion(p, heroAnim.fx, heroAnim.fy, T, heroAnim.dir, false,
                         heroAnim.hop);
    return { tile: [heroAnim.ox + off.dx / T, heroAnim.oy + off.dy / T], off: off };
  }
  // Begin the drawn tween for a step that has already happened in the
  // game. An interrupted step starts from where the hero is drawn, and
  // moves are never queued: the new one simply replaces the old.
  function heroStartStep(tx, ty, dx, dy) {
    if (reducedMotion()) { heroAnim = null; heroSettleSoon(); return; }
    var raf = heroAnim ? heroAnim.raf : 0;
    var from = heroAnim ? heroPose().tile : [tx - dx, ty - dy];
    // A sheet already moves frame by frame, so the bob rides at 0.
    heroAnim = { ox: from[0], oy: from[1], fx: tx - from[0], fy: ty - from[1],
                 dir: heroFacing, hop: heroHasSheet ? 0 : STEP_HOP,
                 start: nowMs(), raf: raf };
    if (!heroAnim.raf) heroAnim.raf = requestAnimationFrame(heroFrame);
  }
  // Back to idle when no tween will do it: a bump, a wall, or reduced
  // motion still shows the walk frame, then settles on the same clock.
  function heroSettleSoon() {
    if (!heroHasSheet || heroAnim) return;
    window.setTimeout(function () { heroSetPose('idle'); draw(); }, STEP_MS);
  }
  // Draw only while a step is running; on the last frame, stop, return
  // the pose to idle, and paint the settled tile. No idle loop.
  function heroFrame() {
    if (!heroAnim) return;
    if (nowMs() - heroAnim.start >= STEP_MS) {
      heroAnim = null;
      heroSetPose('idle');
      draw();
      return;
    }
    draw();
    if (heroAnim) heroAnim.raf = requestAnimationFrame(heroFrame);
  }
  // The hero's own draw path: mirror left, hop with the offset, the dot
  // fallback unchanged (facing never mirrors it).
  function drawHero() {
    var pose = heroPose();
    var t = pose.tile, off = pose.off;
    ctx.save();
    ctx.translate(t[0] * T + T / 2, t[1] * T + T);
    // The lean is a rotation. A real canvas has rotate(); the minimal
    // stub context used by the test harness may not, and in that case
    // the hero still draws, only without the tilt.
    if (off.lean && typeof ctx.rotate === 'function') {
      ctx.rotate(off.lean * Math.PI / 180);
    }
    if (heroHasSheet && spriteSheetReady('hero')) {
      // One cell of the sheet, drawn 1.5 tiles tall with the same squash
      // and mirror as the single picture. A missing side's frames are
      // drawn flipped.
      var sheet = spriteSheets.hero;
      var sim = spriteSheetImgs.hero;
      var fw = sheet.frame[0], fh = sheet.frame[1];
      var cols = Math.max(1, Math.floor(sim.naturalWidth / fw));
      var cell = sheetCell('hero', 'hero', heroFacing, heroAnim ? 'walk' : 'idle', heroWalkStep)
        || { idx: heroSheetIdx, mirror: heroSheetMirror };
      var col = cell.idx % cols, row = Math.floor(cell.idx / cols);
      if (window.VEFR_HERO_FRAME) window.VEFR_HERO_FRAME.frame = cell.idx;
      var sheetH = T * 1.5 * spriteScale(window.VEFR_SPRITE_SCALE, 'hero');
      var sheetW = sheetH * (fw / fh || 1);
      var sh = sheetH * (1 - off.squash);
      var sw = sheetW * (1 + off.squash);
      if (cell.mirror) {
        ctx.drawImage(sim, col * fw, row * fh, fw, fh, sw / 2, -sh, -sw, sh);
      } else {
        ctx.drawImage(sim, col * fw, row * fh, fw, fh, -sw / 2, -sh, sw, sh);
      }
    } else if (spriteReady('hero')) {
      var im = spriteImgs['hero'];
      var baseH = T * 1.5 * spriteScale(window.VEFR_SPRITE_SCALE, 'hero');
      var baseW = baseH * (im.naturalWidth / im.naturalHeight || 1);
      // The squash is drawn as a slightly wider, shorter body - no
      // context scale needed - with the feet still on the tile bottom.
      var h = baseH * (1 - off.squash);
      var w = baseW * (1 + off.squash);
      // Facing left is the same picture mirrored about the tile centre.
      if (heroFacing === 'left') ctx.drawImage(im, w / 2, -h, -w, h);
      else ctx.drawImage(im, -w / 2, -h, w, h);
    } else {
      ctx.fillStyle = town.hero_color || '#e8e5df';
      ctx.beginPath();
      ctx.arc(0, -T / 2, T / 3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  // A harness-readable snapshot of the hero's motion, read-only
  // (precedent: window.VEFR_COMBAT). It never changes the game; it
  // exists so a test can see the facing and the drawn tile.
  window.VEFR_MOTION = function () {
    var pose = heroPose();
    return { facing: heroFacing, drawn: [pose.tile[0], pose.tile[1]],
             animating: !!heroAnim };
  };
  // The pure step maths, exposed the same read-only way so a node test
  // can call it directly (reduced motion in -> the identity out).
  window.VEFR_STEP_MOTION = stepMotion;

  function draw() {
    animWant = false;
    var ph = phase();
    var water = (town.water_by_phase || {})[ph];
    var flood = town.flood_tiles || [];
    var mapW = cols * T, mapH = rows * T;
    // The camera: follow the hero once the map is bigger than the screen,
    // clamp to the edges, and centre it when it fits.
    // The camera follows where the hero is DRAWN (the tween), not the settled tile, so a big
    // scrolling map glides during the hop instead of snapping a tile and sliding the hero back.
    // At rest the drawn tile is the settled one, so nothing changes when no step is running.
    var camHero = heroPose().tile;
    var camX = mapW <= viewW ? (mapW - viewW) / 2
      : Math.min(Math.max(camHero[0] * T + T / 2 - viewW / 2, 0), mapW - viewW);
    var camY = mapH <= viewH ? (mapH - viewH) / 2
      : Math.min(Math.max(camHero[1] * T + T / 2 - viewH / 2, 0), mapH - viewH);

    ctx.fillStyle = town.bg; ctx.fillRect(0, 0, viewW, viewH);
    // The ground the map does not cover takes the skin's table, when the skin
    // has one and its picture has decoded (the bands come from the camera).
    // Tiles are laid from the window's own origin, so the wood does not crawl
    // when the map scrolls. No backdrop: the flat ground above stands.
    var backdrop = skinBackdrop();
    backdropBands = window.VEFR_BACKDROP_BANDS(!!backdrop, viewW, viewH, camX, camY, mapW, mapH);
    backdropDrawn = 0;
    if (backdropBands.length) {
      var tableW = backdrop.naturalWidth || backdrop.width;
      var tableH = backdrop.naturalHeight || backdrop.height;
      if (tableW && tableH) {
        backdropBands.forEach(function (band) {
          for (var top = band[1]; top < band[1] + band[3]; top += tableH) {
            for (var left = band[0]; left < band[0] + band[2]; left += tableW) {
              ctx.drawImage(backdrop, left, top,
                Math.min(tableW, band[0] + band[2] - left),
                Math.min(tableH, band[1] + band[3] - top));
              backdropDrawn++;
            }
          }
        });
      } else {
        backdropBands = [];      // a picture with no size paints nothing
      }
    }
    ctx.save();
    ctx.translate(-camX, -camY);
    var litSet = fogOn ? litNow() : null;   // what is lit right now

    var u = T / 32;   // the pack's mark sizes are authored for a 32px tile
    var x0 = Math.max(0, Math.floor(camX / T));
    var x1 = Math.min(cols - 1, Math.ceil((camX + viewW) / T));
    var y0 = Math.max(0, Math.floor(camY / T));
    var y1 = Math.min(rows - 1, Math.ceil((camY + viewH) / T));
    for (var y = y0; y <= y1; y++) {
      for (var x = x0; x <= x1; x++) {
        if (hideUnseen(x, y)) continue;
        var ch = town.map[y][x];
        var info = legend[ch] || {};
        var color = (info.base && info.base[0]) || '#222';
        var imgs = tileImgs[ch];
        var grid = tileGrids[ch];
        var tile = imgs && imgs.length
          ? imgs[pickVariant(x, y, imgs.length)] : null;
        var hasTile = tile && tile.complete && tile.naturalWidth > 0;
        var hasGrid = grid && grid.img.complete && grid.img.naturalWidth > 0;
        if (hasGrid) {
          var cell = pickCell(x, y, grid.cols, grid.rows);
          var cw = grid.img.naturalWidth / grid.cols, chh = grid.img.naturalHeight / grid.rows;
          ctx.drawImage(grid.img, cell[0] * cw, cell[1] * chh, cw, chh, x * T, y * T, T, T);
        } else if (hasTile) {
          ctx.drawImage(tile, x * T, y * T, T, T);
        } else {
          ctx.fillStyle = color;
          ctx.fillRect(x * T, y * T, T, T);
        }
        if (info.solid && !hasTile) {
          ctx.fillStyle = '#444';
          ctx.fillRect(x * T + 4 * u, y * T + 4 * u, T - 8 * u, T - 8 * u);
        }
        if (info.deco && info.deco_color) {
          ctx.fillStyle = info.deco_color;
          ctx.fillRect(x * T + 8 * u, y * T + 8 * u, T - 16 * u, T - 16 * u);
        }
      }
    }
    if (water === 'high') {
      ctx.fillStyle = 'rgba(80,80,140,0.35)';
      flood.forEach(function (t) {
        ctx.fillRect(t[0] * T, t[1] * T, T, T);
      });
    }
    // Doors: every transition that leaves this region is drawn, so the
    // way to another map is visible underfoot.
    transitions().forEach(function (t) {
      if (!t || t.from !== regionName || !Array.isArray(t.at)) return;
      if (hideUnseen(t.at[0], t.at[1])) return;
      var src = wayPictureSrc(wayKindOf(t));
      if (src) {
        if (wayReady(src)) ctx.drawImage(wayImgs[src], t.at[0] * T, t.at[1] * T, T, T);
      } else if (doorReady()) {
        ctx.drawImage(doorImg, t.at[0] * T + T * 0.08, t.at[1] * T + T * 0.08,
                      T * 0.84, T * 0.84);
      }
    });
    // Books you have not found yet: a marker where one can still be found
    // (a map book on its tile, a gifted one on the person who gives it).
    (window.VEFR_LIBRARY || []).forEach(function (b) {
      if (!b || bookIsFound(b.id)) return;
      var at = null;
      if (b.found === 'map') {
        if ((b.region || 'town') !== regionName) return;  // lies on another map
        if (Array.isArray(b.at)) at = b.at;
      } else if (b.found === 'resident') {
        if (!b.speaker || !speakers[b.speaker]) return;   // giver not in this room
        at = speakers[b.speaker].at;
      }
      if (!at) return;
      if (hideUnseen(at[0], at[1])) return;
      if (b.chest) {
        if (!chestReady()) return;
        ctx.drawImage(chestImg, at[0] * T + T * 0.08, at[1] * T + T * 0.08, T * 0.84, T * 0.84);
        return;
      }
      if (!bookIconReady(b.found)) return;
      ctx.drawImage(bookIconImgs[b.found], at[0] * T + T * 0.12, at[1] * T + T * 0.12,
                    T * 0.76, T * 0.76);
    });
    // Everything that stands on the ground, drawn in one list. A region
    // with props sorts it by base row (a prop's bottom row, a character's
    // own row) so what stands further back is covered by what stands in
    // front; a region without props keeps the order it always had.
    readProps();
    var stands = [];
    var seq = 0;
    function stand(row, label, paint) {
      stands.push({ row: row, label: label, seq: seq++, paint: paint });
    }
    // A ground prop (a pond, a rug, flowers) lies flat: drawn now, under
    // everyone, whatever its row.
    var grounds = [];
    propList.forEach(function (p) {
      if (!propSeen(p)) return;
      if (p.layer === 'ground') { grounds.push('ground:' + p.pic); drawProp(p); return; }
      stand(p.at[1] + p.h - 1, 'prop:' + p.pic, function () { drawProp(p); });
    });
    // The people: their own sprite when the pack names one, else the
    // drawn figure (a body and a head), so you can see who is here.
    var npcBox = document.getElementById('npc-box');
    var speechOpen = !!npcBox && !npcBox.hidden;
    Object.keys(speakers || {}).forEach(function (key) {
      var s = speakers[key];
      if (!s || !Array.isArray(s.at)) return;
      if (hideUnseen(s.at[0], s.at[1])) return;
      stand(s.at[1], 'speaker:' + key, function () {
        if (spriteReady(key)) {
          var beside = Math.abs(s.at[0] - hero[0]) + Math.abs(s.at[1] - hero[1]) === 1;
          drawSprite(key, s.at[0], s.at[1], {
            actor: 'speaker:' + key,
            dir: beside ? faceOf(s.at, hero) : 'down',
            state: beside && speechOpen ? 'talk' : 'idle' });
          return;
        }
        var px = s.at[0] * T, py = s.at[1] * T;
        ctx.fillStyle = town.speaker_color || '#8b939c';
        ctx.beginPath();
        ctx.arc(px + 16 * u, py + 21 * u, 6 * u, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = town.speaker_head || '#d8d5df';
        ctx.beginPath();
        ctx.arc(px + 16 * u, py + 11 * u, 4 * u, 0, Math.PI * 2);
        ctx.fill();
      });
    });

    // The living hazards: their own sprite when the pack names one,
    // else the same body-and-head figure as a speaker, in a hostile
    // colour. A slain enemy is never drawn - except a warden that
    // `yields` (ADR 0015 Amendment 1 §2), which stays on its anchor and
    // is drawn in a muted colour to say it is no longer hostile. Fog
    // hides the unseen either way.
    enemies.forEach(function (e) {
      if (!e || !Array.isArray(e.at)) return;
      if (!e.alive && !e.yields) return;
      // A monster is only drawn where the light reaches: you cannot
      // remember something that moves, and seeing through the dark
      // would give the floor away.
      if (fogOn && !(litSet && litSet[e.at[0] + ',' + e.at[1]])) return;
      stand(e.at[1], 'enemy:' + e.id, function () {
        if (e.sprite && spriteReady(e.sprite)) {
          if (!e.alive) ctx.globalAlpha = 0.45;
          drawSprite(e.sprite, e.at[0], e.at[1], {
            actor: 'enemy:' + e.id, dir: e.face || 'down', state: 'idle' });
          ctx.globalAlpha = 1;
          return;
        }
        var ex = e.at[0] * T, ey = e.at[1] * T;
        ctx.fillStyle = e.alive ? '#8a3b34' : '#4d4a48';
        ctx.beginPath();
        ctx.arc(ex + 16 * u, ey + 21 * u, 6 * u, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = e.alive ? '#d9c3bd' : '#8e8a84';
        ctx.beginPath();
        ctx.arc(ex + 16 * u, ey + 11 * u, 4 * u, 0, Math.PI * 2);
        ctx.fill();
      });
    });

    // Loot lying on the floor: a killed enemy's drop, at the tile it
    // died on. Drawn only where the light reaches, like a living hazard.
    floor.forEach(function (d) {
      if (!d || d.region !== regionName || !Array.isArray(d.at)) return;
      if (fogOn && !(litSet && litSet[d.at[0] + ',' + d.at[1]])) return;
      stand(d.at[1], 'loot:' + d.item, function () {
        drawItemMarker(d.item, d.at[0], d.at[1]);
      });
    });

    // The hero: their own sprite when the pack names one, else the dot.
    // The one character drawn with facing and step motion.
    stand(camHero[1], 'hero', drawHero);
    if (propList.length) {
      stands.sort(function (a, b) { return (a.row - b.row) || (a.seq - b.seq); });
    }
    window.VEFR_DRAW_ORDER = grounds.concat(stands.map(function (s) { return s.label; }));
    stands.forEach(function (s) { s.paint(); });
    // Fog of war: explored but not currently lit is dimmed; never-seen
    // tiles were skipped above and stay dark.
    if (fogOn) {
      var lit = litSet || litNow();
      ctx.fillStyle = 'rgba(5, 6, 8, 0.62)';
      for (var fy = y0; fy <= y1; fy++) {
        for (var fx = x0; fx <= x1; fx++) {
          var fk = fx + ',' + fy;
          if (explored[fk] && !lit[fk]) ctx.fillRect(fx * T, fy * T, T, T);
        }
      }
    }
    drawTargetRing();
    ctx.restore();
    if (animWant) scheduleAnim();
  }

  // A thin ring on the tile Interact would act on, so the picture and
  // the hint words agree. Draw only: it reads the pick, changes no
  // game state, and never calls draw(). The HUD gold reads on both
  // light and dark ground; an outline only, never a fill.
  function drawTargetRing() {
    var t = pickTarget(interactState());
    if (!t) return;
    ctx.save();
    ctx.strokeStyle = '#D8AA4E';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(t.at[0] * T + T / 2, t.at[1] * T + T / 2, T * 0.42,
            0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  // A door on the current region's tile (nx,ny), if any.
  function transitionAt(nx, ny) {
    var list = transitions();
    for (var i = 0; i < list.length; i++) {
      var t = list[i];
      if (t && t.from === regionName && Array.isArray(t.at)
          && t.at[0] === nx && t.at[1] === ny) return t;
    }
    return null;
  }

  // The weather the pack's own grammar speaks on arrival: said once
  // in the status line and journaled like any other arrival, so it
  // is an arrival, not a per-step line. A pack with no `weather`
  // grammar says nothing and the arrival is the same one it always was.
  function sayArrivalWeather(name) {
    var line = grammarFromPack('weather');
    if (!line) return;
    var statusEl = document.getElementById('status');
    if (statusEl) statusEl.textContent = line;
    journalVisit(name, hero[0], hero[1]);
  }

  // ---- town states (ADR 0015) --------------------------------------------
  // Which face of a region a player walks into: the LAST state whose
  // `when` flag reads true, else the region's own base. Derived on every
  // entry from the flags true at that moment and never stored, so a pack
  // adds no save key and no runtime language - each `use` is an ordinary
  // authored region, baked as it always was.
  //
  // The region KEEPS its own identity. `regionName` below is still the
  // region the player entered, so all of a region's states share one
  // save: its fog, its dropped items and its journal entry are the
  // region's, not the state's. That is also why an arrival still fires
  // `enters` for the region the author named rather than for the face of
  // it the player landed on - a rule on `enters town` is a rule about
  // arriving in town at all.
  function storyFlagsNow() {
    var truth = {};
    var D = window.VEFR_DESCENT;
    if (D && typeof D.flags === 'function') {
      var own = D.flags() || {};
      for (var k in own) {
        if (Object.prototype.hasOwnProperty.call(own, k)) truth[k] = own[k];
      }
    }
    var state = rulesStateNow();
    var ruled = (state && state.flags) ? state.flags : {};
    for (var j in ruled) {
      if (Object.prototype.hasOwnProperty.call(ruled, j)) truth[j] = ruled[j];
    }
    return truth;
  }

  function townStateFor(name) {
    var blocks = window.VEFR_TOWN_STATES;
    if (!blocks) return name;
    var listed = Array.isArray(blocks) ? blocks : [blocks];
    var truth = null;
    for (var i = 0; i < listed.length; i++) {
      var block = listed[i];
      if (!block || block.region !== name) continue;
      var states = Array.isArray(block.states) ? block.states : [];
      var chosen = name;
      if (truth === null) truth = storyFlagsNow();
      for (var j = 0; j < states.length; j++) {
        var one = states[j];
        if (!one || typeof one.when !== 'string' || !one.when) continue;
        if (truth[one.when] === true && typeof one.use === 'string' && one.use) {
          chosen = one.use;
        }
      }
      // A `use` the pack never authored is refused by `vefr check`; if one
      // slips through anyway the base loads rather than an empty map.
      return (chosen === name || regions[chosen]) ? chosen : name;
    }
    return name;
  }

  function tileOpen(x, y) {
    var rows = (town && town.map) || [];
    if (!(y >= 0) || y >= rows.length) return false;
    var row = rows[y] || '';
    if (!(x >= 0) || x >= row.length) return false;
    return !((town.legend[row.charAt(x)] || {}).solid) && !propBlocked(x, y);
  }

  // The floor tile nearest `[x, y]` by Manhattan distance, scanning
  // row-major so a tie keeps the first tile found: the answer is the same
  // on every machine and in both languages.
  function nearestFloorTile(at) {
    var rows = (town && town.map) || [], best = null, bestD = Infinity;
    for (var y = 0; y < rows.length; y++) {
      for (var x = 0; x < rows[y].length; x++) {
        if (!tileOpen(x, y)) continue;
        var d = Math.abs(x - at[0]) + Math.abs(y - at[1]);
        if (d < bestD) { bestD = d; best = [x, y]; }
      }
    }
    return best;
  }

  // A dropped item left in one face of a region can be standing against a
  // wall in the next. All of a region's states share its save, so the
  // item moves to the nearest floor tile rather than becoming something
  // the player can never walk onto and so never pick up.
  function settleDrops(name) {
    var moved = false;
    floor.forEach(function (d) {
      if (!d || d.region !== name || !Array.isArray(d.at)) return;
      if (tileOpen(d.at[0], d.at[1])) return;
      var spot = nearestFloorTile(d.at);
      if (!spot) return;
      d.at = spot;
      moved = true;
    });
    if (moved) saveFloor();
  }

  // Enter another region through a door: swap the current map,
  // speakers, and hero, then resize, draw, and refresh the POI line.
  function enterRegion(name, at) {
    // The virtual region (slice E1): a floor that was never baked at
    // weave time is drawn and inserted here, before the player is asked
    // for it, so every path below - the map, the monsters, the stairs,
    // the memory of what was killed - finds it waiting.
    if (window.VEFR_DESCENT) {
      window.VEFR_DESCENT.onEnter(name);
      window.VEFR_DESCENT.ensureRegion(name);
    }
    if (!regions[name]) return;
    // Which face of this region the story has earned (ADR 0015).
    var where = townStateFor(name);
    var changed = where !== name;
    fireRule('enters', { place: name });   // one `enters` per arrival
    regionName = name;
    town = regionTown(where);
    legend = town.legend;
    pois = town.pois;
    speakers = regionSpeakers(where);
    // `at` is a tile of the region the door was written for. A state is
    // another region entirely, so the hero stands on its own `hero_start`
    // unless that tile happens to be open ground here too.
    hero = (!changed || tileOpen(at && at[0], at && at[1]))
      ? (at || town.hero_start).slice() : town.hero_start.slice();
    if (changed) settleDrops(name);
    heroAnim = null;   // a new region's hero appears settled, not mid-hop
    heroSetPose('idle');
    fogOn = fogEnabled();
    fogRadius = (town.fog && town.fog.radius) || 6;
    resetLight();
    loadTiles();
    loadFog();
    seeNow();
    loadEnemies();
    combatSnapshot();
    resize();
    draw();
    refreshPoi();
    updateUse();
    renderFogToggle();
    sayArrivalWeather(name);
  }

  // The one way into another region, for the parts outside this closure
  // (the New-descent control walks straight into floor one).
  window.VEFR_ENTER_REGION = enterRegion;

  // A chest gives the note it holds (the book reader) and anything its
  // `drops` names, added to the bag with one line. A chest is found
  // after it opens, so its things are taken once.
  function giveChestDrops(book) {
    var ids = (book && Array.isArray(book.drops)) ? book.drops : [];
    var names = [];
    ids.forEach(function (id) {
      // Taking it out of the chest is the player acquiring it, so it
      // fires the same `picks-up` a floor drop fires. (A rule's own
      // `give` stays silent: a give is not a picks-up - the
      // no-chains law.)
      if (bagAdd(id)) {
        names.push(itemName(id));
        fireRule('picks-up', { what: id });
      }
    });
    if (names.length) combatSay('You take ' + names.join(', ') + ' from the chest.');
  }

  // -- interact start --
  // One verb, three pure helpers (the logic only; the wiring is a
  // later pass). The caller builds `state` from the live game; this
  // block only reads it, so a node vm sandbox whose only global is
  // Math can run it. Shape of `state`:
  //
  //   {
  //     hero: [x, y],                 // the hero's tile
  //     facing: 'up'|'down'|'left'|'right',
  //     candidates: [ { kind, id, name, at: [x, y] } ]
  //   }
  //
  // `kind` is one of exactly: resident, trader, identifier, chest,
  // door, stairs, place, enemy. `id` is the caller's key (speaker key,
  // book id, transition id, enemy id, poi key); `name` is the display
  // name. A malformed candidate - missing or unknown kind, missing,
  // short or non-numeric `at` - is skipped, never an error.
  //
  // Reach is Manhattan from `state.hero`: one tile for the things you
  // touch (chest, door, stairs, place, enemy), two for people (the
  // talk reach today). `interactTargets` returns every candidate in
  // reach, in the caller's own order, each a fresh { kind, id, name,
  // at, dist, label } with `label` set from `labelFor`. `pickTarget`
  // returns one of them: a candidate on the tile the hero faces,
  // else one on the hero's own tile, else the nearest in reach.
  // Ties break by kind - door and stairs share the top rank and
  // candidate order decides between them, then chest, trader,
  // identifier, resident, place, enemy - and finally by candidate
  // order. The two service kinds sit where the trade panel's did, so a
  // shopkeeper or a reader opens their panel rather than their talk.
  // Nothing is mutated: every call returns fresh objects. No DOM, no
  // storage, no clock, no chance.
  globalThis.labelFor = function (target) {
    if (!target) return null;
    var name = target.name;
    if (target.kind === 'chest') return 'Open the chest';
    if (target.kind === 'resident') return 'Talk to ' + name;
    if (target.kind === 'trader') return 'Trade with ' + name;
    if (target.kind === 'identifier') return 'Ask ' + name + ' to read things';
    if (target.kind === 'door') return 'Go through the door';
    // A stair the pack names as going up ("the stair up") climbs; any other
    // stair keeps the original words.
    if (target.kind === 'stairs') {
      return /\bup\b/i.test(String(name || '')) ? 'Go up the stairs' : 'Go down the stairs';
    }
    if (target.kind === 'place') return 'Look at ' + name;
    if (target.kind === 'enemy') return 'Fight ' + name;
    return null;
  };

  globalThis.interactTargets = function (state) {
    var out = [];
    if (!state || typeof state !== 'object') return out;
    var hero = state.hero;
    if (!Array.isArray(hero) || hero.length < 2) return out;
    if (typeof hero[0] !== 'number' || !isFinite(hero[0])) return out;
    if (typeof hero[1] !== 'number' || !isFinite(hero[1])) return out;
    var reach = { resident: 2, trader: 2, identifier: 2, chest: 1,
                  door: 1, stairs: 1, place: 1, enemy: 1 };
    var list = Array.isArray(state.candidates) ? state.candidates : [];
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      if (!c || typeof c !== 'object') continue;
      var max = reach[c.kind];
      if (typeof max !== 'number') continue;   // missing or unknown kind
      var at = c.at;
      if (!Array.isArray(at) || at.length < 2) continue;
      if (typeof at[0] !== 'number' || !isFinite(at[0])) continue;
      if (typeof at[1] !== 'number' || !isFinite(at[1])) continue;
      var dist = Math.abs(at[0] - hero[0]) + Math.abs(at[1] - hero[1]);
      if (dist > max) continue;                // out of reach
      var target = { kind: c.kind, id: c.id, name: c.name,
                     at: [at[0], at[1]], dist: dist };
      target.label = labelFor(target);
      out.push(target);
    }
    return out;
  };

  globalThis.pickTarget = function (state) {
    var all = interactTargets(state);
    if (!all.length) return null;
    var hero = state.hero;
    var step = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
    var face = step[state.facing];
    var fx = null, fy = null;
    if (face) { fx = hero[0] + face[0]; fy = hero[1] + face[1]; }
    var rank = { door: 0, stairs: 0, chest: 1, trader: 2,
                 identifier: 3, resident: 4, place: 5, enemy: 6 };
    var best = null, bestTier = -1, bestDist = -1, bestRank = -1;
    for (var i = 0; i < all.length; i++) {
      var t = all[i];
      // 0 the tile the hero faces, 1 the hero's own tile, 2 the rest
      var tier = 2;
      if (fx !== null && t.at[0] === fx && t.at[1] === fy) tier = 0;
      else if (t.at[0] === hero[0] && t.at[1] === hero[1]) tier = 1;
      var r = rank[t.kind];
      if (best === null
          || tier < bestTier
          || (tier === bestTier && t.dist < bestDist)
          || (tier === bestTier && t.dist === bestDist && r < bestRank)) {
        best = t; bestTier = tier; bestDist = t.dist; bestRank = r;
      }
    }
    return best;
  };
  // -- interact end --

  // One transition on this map as an Interact candidate: a stair or a door.
  function transitionCandidate(tr) {
    var key = tr.at[0] + ',' + tr.at[1];
    var sym = (town.map[tr.at[1]] || '')[tr.at[0]] || '';
    var stair = /stair/i.test((pois || {})[key] || '')
      || sym === 'u' || sym === 'd';
    return { kind: stair ? 'stairs' : 'door', id: key,
             name: (pois || {})[key] || 'the way through',
             at: [tr.at[0], tr.at[1]] };
  }

  // The picture kind of one transition: a stair the label says goes up or
  // down, a trapdoor when its name or tile says so, else a door.
  function wayKindOf(tr) {
    var c = transitionCandidate(tr);
    if (c.kind === 'stairs') {
      return labelFor(c) === 'Go up the stairs' ? 'stairs-up' : 'stairs-down';
    }
    var sym = (town.map[tr.at[1]] || '')[tr.at[0]] || '';
    var tile = ((town.legend || {})[sym] || {}).tile || '';
    return (/trap ?door/i.test(c.name) || /trap ?door/i.test(tile)) ? 'trapdoor' : 'door';
  }

  // The region's own picture for a kind, else the pack's, else '' (the door).
  function wayPictureSrc(kind) {
    var own = (window.VEFR_REGION_WAY_ICONS || {})[regionName] || {};
    return own[kind] || (window.VEFR_WAY_ICONS || {})[kind] || '';
  }

  // The caller half of the one verb: build the state the pure block
  // above wants from the LIVE game - the hero, the way it faces, and
  // every candidate in this region, gathered in this order:
  //
  //   resident - every speaker here with a real `at` (the people
  //              talkToSpeaker talks to); with no brain configured, a
  //              speaker with no offline line is not a target at all;
  //   trader   - the region's shopkeeper, found the way
  //              shopkeeperNear finds it (shopKeyHere) but with NO
  //              distance cut, so the pure block's own reach rules
  //              decide; the reach cut lives only in shopkeeperNear;
  //   identifier - the region's reader (ADR 0017, T3 slice 2), the
  //                speaker that carries `"identify": "true"`, found
  //                the same way: identifyKeyHere names it and the
  //                pure block's own reach rules decide.
  //   chest    - every unfound chest book in this region: a chest
  //              book (`chest: yes`, `found: map`) whose region is
  //              this one and which is not already found;
  //   door     - every transition out of this region, except stairs:
  //              a tile is stairs when the region's `pois` for that
  //              tile mentions a stair (/stair/i on pois[key]) OR the
  //              map symbol there is a delve stair symbol (`u` up /
  //              `d` down - the floor alphabet src/vefr/delve.py
  //              generates), else it is a door. Simple and
  //              deterministic; a mislabel still acts as the same
  //              transition;
  //   place    - every `poi_text` tile in this region, named by
  //              pois[key] or the poi_text value itself;
  //   enemy    - every living enemy, by name.
  //
  // Each candidate carries a stable id: speaker key, book id, `x,y`
  // for a transition or poi, enemy id.
  function interactState() {
    var candidates = [];
    Object.keys(speakers || {}).forEach(function (key) {
      var s = speakers[key];
      if (!s || !Array.isArray(s.at)) return;
      if (!brainConfigured() && !hasOfflineLine(key, s)) return;
      candidates.push({ kind: 'resident', id: key, name: s.name,
                        at: [s.at[0], s.at[1]] });
    });
    var shopKey = shopKeyHere(regionName);
    var shop = shopKey ? speakers[shopKey] : null;
    if (shop && Array.isArray(shop.at)) {
      candidates.push({ kind: 'trader', id: shopKey, name: shop.name,
                        at: [shop.at[0], shop.at[1]] });
    }
    // The region's reader, the same two lines as the shopkeeper above: a
    // pack that names no identify service adds no candidate at all, and
    // the region plays exactly as it did.
    var readerKey = identifyKeyHere(regionName);
    var reader = readerKey ? speakers[readerKey] : null;
    if (reader && Array.isArray(reader.at)) {
      candidates.push({ kind: 'identifier', id: readerKey,
                        name: reader.name,
                        at: [reader.at[0], reader.at[1]] });
    }
    libraryBooks().forEach(function (b) {
      if (!b || !b.chest || b.found !== 'map' || !Array.isArray(b.at)) return;
      if ((b.region || 'town') !== regionName) return;
      if (bookIsFound(b.id)) return;
      candidates.push({ kind: 'chest', id: b.id, name: b.title || 'the chest',
                        at: [b.at[0], b.at[1]] });
    });
    transitions().forEach(function (tr) {
      if (!tr || tr.from !== regionName || !Array.isArray(tr.at)) return;
      if (typeof tr.at[0] !== 'number' || typeof tr.at[1] !== 'number') return;
      candidates.push(transitionCandidate(tr));
    });
    var texts = town.poi_text || {};
    Object.keys(texts).forEach(function (key) {
      var xy = key.split(',');
      var x = Number(xy[0]), y = Number(xy[1]);
      if (!isFinite(x) || !isFinite(y)) return;
      candidates.push({ kind: 'place', id: key,
                        name: (pois || {})[key] || texts[key],
                        at: [x, y] });
    });
    enemies.forEach(function (e) {
      if (!e || !e.alive || !Array.isArray(e.at)) return;
      candidates.push({ kind: 'enemy', id: e.id, name: e.name,
                        at: [e.at[0], e.at[1]] });
    });
    return { hero: [hero[0], hero[1]], facing: heroFacing,
             candidates: candidates };
  }

  // Task 3: fight through the one verb. The row is the same #verb-row
  // the surface always shows; naming a target is what "opens" it, and
  // nothing here re-implements the damage maths.
  function openEnemyVerbs(enemy) {
    VERB_TARGET = enemy;
    var row = document.getElementById('verb-row');
    if (row) row.setAttribute('aria-label',
      'What to do about ' + (enemy.name || 'this monster'));
  }
  // Clearing the target returns the row's own label; called on Escape,
  // on a bump, and after a verb resolves.
  function closeEnemyVerbs() {
    VERB_TARGET = null;
    var row = document.getElementById('verb-row');
    if (row) row.setAttribute('aria-label', 'Combat actions');
  }
  // One verb, one enemy. `attack` is the existing heroAttack (so the
  // damage is exactly a bump's); any other verb the pack names is
  // words only - deterministic, no model, no clock, no chance. It
  // answers whether the verb happened at all, because a blow at an
  // unattackable warden (ADR 0015 Amendment 1 §2) does not, and a verb
  // that did not happen spends no turn.
  function applyVerb(verb, label, enemy) {
    if (!enemy) return false;
    if (verb === 'attack') return heroAttack(enemy);
    var said = 'You use ' + label + ' on ' + (enemy.name || 'it') + '.';
    // The other verbs are words only, but a practice spec can learn from
    // them. The default verbs are `console`/`hurl`; any other name
    // counts toward nothing.
    var kind = (verb === 'console') ? 'consoles'
      : (verb === 'hurl') ? 'hurls' : null;
    if (kind) sayGrowth(practiceSuffix(growBump(kind)));
    combatSay(said);
    return true;
  }

  // A locked door or stair (design/gates-and-guardians.md, step 1).
  // A transition without `requires` is always open. With one, it opens
  // when the named item is in the bag, or the named flag reads true in
  // the rules state (a missing state leaves a flag lock shut). The key
  // is never consumed.
  //
  // A story flag the descent owns - the warden beats, and the town gate
  // of ADR 0015 - lives in the descent's own save beside the floors, not
  // in the rules state, so this asks both. It is still the one gate
  // mechanism: `requires` through this function, whatever set the flag.
  function lockOpen(trans) {
    var req = trans && trans.requires;
    if (!req || typeof req !== 'object') return true;
    if (typeof req.item === 'string' && req.item
        && bagItems().indexOf(req.item) !== -1) return true;
    if (typeof req.flag === 'string' && req.flag) {
      var state = rulesStateNow();
      if (state && state.flags && state.flags[req.flag] === true) return true;
      var D = window.VEFR_DESCENT;
      if (D && typeof D.storyFlags === 'function' && D.storyFlags(req.flag)) return true;
    }
    return false;
  }

  // The one verb: act on whatever pickTarget chose, through the code
  // that already does it - nothing here is re-implemented. With
  // nothing in reach (or anything unexpected) write ONE friendly line
  // into #near, spend NO turn, and never throw: the whole dispatch is
  // wrapped, so an error lands on the same gentle nudge.
  function doInteract() {
    var near = document.getElementById('near');
    var nudge = 'Nothing to use here. Walk up to something and try again.';
    function nope() { if (near) near.textContent = nudge; }
    try {
      var t = pickTarget(interactState());
      if (!t) { nope(); return; }
      if (t.kind === 'door' || t.kind === 'stairs') {
        var trans = transitionAt(t.at[0], t.at[1]);
        if (!trans) throw new Error('transition gone');
        // A lock says its one line and stays put: no `opens`, no
        // arrival, the hero unmoved.
        if (!lockOpen(trans)) {
          combatSay(trans.locked_text || 'It will not open yet.');
          soundCue('locked');
          return;
        }
        // A door used is a door opened: `opens` carries the place it
        // opens into (a declared region), then the arrival fires
        // `enters` as it always has.
        soundCue('door');
        // A loud thing the hero just did, at their own tile and before
        // the arrival has moved them off it (ADR 0014's noise table): a
        // door opened carries 6 tiles, and a stair used - the same
        // transition, told from a door by the region's own naming of the
        // tile - carries 8.
        if (t.kind === 'stairs') {
          makeNoise('stair');
        } else {
          makeNoise('door');
        }
        fireRule('opens', { what: trans.to });
        enterRegion(trans.to, trans.to_at);
      } else if (t.kind === 'chest') {
        var books = libraryBooks(), book = null;
        for (var i = 0; i < books.length; i++) {
          if (books[i] && books[i].id === t.id) { book = books[i]; break; }
        }
        if (!book) throw new Error('chest gone');
        // One `opens` per opening, through the one interaction path
        // the player has. The chest's own identity is its book id;
        // its contents follow with their own `picks-up`.
        fireRule('opens', { what: book.id });
        // A chest opened is 6 tiles of noise (ADR 0014's table), and it
        // is a chest being opened whether the note inside it is a
        // library book or only a cache.
        makeNoise('chest');
        foundBook(book, 'map');
        giveChestDrops(book);
        combatSnapshot();
      } else if (t.kind === 'trader') {
        openTrade(t.id, t.name, document.getElementById('interact'));
      } else if (t.kind === 'identifier') {
        openIdentify(t.id, t.name, document.getElementById('interact'));
      } else if (t.kind === 'resident') {
        if (!speakers[t.id]) throw new Error('speaker gone');
        talkToSpeaker({ key: t.id, spec: speakers[t.id], dist: t.dist });
      } else if (t.kind === 'place') {
        showSpeech((pois || {})[t.id] || '', (town.poi_text || {})[t.id] || '',
                   '');
      } else if (t.kind === 'enemy') {
        var foe = null;
        for (var j = 0; j < enemies.length; j++) {
          if (enemies[j] && enemies[j].id === t.id) { foe = enemies[j]; break; }
        }
        if (!foe || !foe.alive) throw new Error('enemy gone');
        var verbs = surfaceVerbs();
        if (verbs.length === 1) {
          // One verb: act at once, no menu - but the turn still runs,
          // unless the verb was refused (a warden that cannot be
          // struck), which changes nothing and therefore costs nothing.
          recordVerb(verbs[0][0]);
          if (applyVerb(verbs[0][0], verbs[0][1], foe)) {
            lightTick();
            enemyTurn();
          }
        } else {
          openEnemyVerbs(foe);
        }
      } else {
        throw new Error('unknown target');
      }
      updateUse();   // the words follow whatever just happened
    } catch (err) {
      nope();
    }
  }

  // (The old `useHere` - "use what you are standing on" - lived here
  // and was the only caller of fireRule('opens'). It lost its callers
  // when one-button Interact landed and is gone: the Interact path
  // above is the one canonical interaction, and it fires `opens`.)

  // The Interact control: ALWAYS on screen - never hidden, never
  // disabled, so it stays focusable and pressable. Its own words say
  // what the next press will do; with nothing in reach it dims
  // (`.gbtn--dim`) and the hint says so plainly. #use-hint keeps its
  // aria-live="polite" and never gets the hidden attribute back.
  function updateUse() {
    var btn = document.getElementById('interact');
    var hint = document.getElementById('use-hint');
    if (!btn) return;
    var label = labelFor(pickTarget(interactState()));
    var labelEl = document.getElementById('interact-label');
    if (labelEl) labelEl.textContent = label || 'Interact';
    btn.classList.toggle('gbtn--dim', !label);
    if (hint) hint.textContent = label || 'Nothing near you to use yet.';
    updateVerbRow();
  }

  // The fight buttons are for fights: shown with a living monster within a few
  // tiles (or while its menu is open), hidden otherwise. Interact still opens
  // the same menu on a faced monster.
  function updateVerbRow() {
    var vrow = document.getElementById('verb-row');
    if (!vrow) return;
    var near = !!VERB_TARGET;
    for (var i = 0; !near && i < enemies.length; i++) {
      var en = enemies[i];
      if (en.alive && Math.abs(en.at[0] - hero[0]) + Math.abs(en.at[1] - hero[1]) <= 4) near = true;
    }
    vrow.hidden = !near;
  }

  // The named place the hero now stands on, written to the POI line.
  var POI_QUIET_MS = 4000;
  var poiTimer = null;
  function refreshPoi() {
    var here = '';
    for (var k in pois) {
      if (k === hero[0] + ',' + hero[1]) { here = pois[k]; break; }
    }
    var poiEl = document.getElementById('poi');
    poiEl.textContent = here || '';
    poiEl.classList.remove('quiet');
    if (poiTimer) { clearTimeout(poiTimer); poiTimer = null; }
    // A named place is a short arrival line, not a permanent label; hide it
    // visually after a moment but keep the text (a `uses-with` rule reads it).
    if (here) poiTimer = setTimeout(function () { poiEl.classList.add('quiet'); }, POI_QUIET_MS);
    return here;
  }

  function move(dx, dy) {
    // The hero faces the way the move is trying to go, even when it is
    // refused: a bump, a wall or the map's edge still turns the hero.
    if (dx > 0) heroFacing = 'right';
    else if (dx < 0) heroFacing = 'left';
    else if (dy > 0) heroFacing = 'down';
    else if (dy < 0) heroFacing = 'up';
    // A sheet shows the walk frame the moment a direction is pressed (a
    // step, a bump or a wall - the facing turns either way); the step's
    // tween, or heroSettleSoon for the rest, returns it to idle. The
    // cycle advances once per press and publishes NOW, not in the rAF,
    // so a synchronous reader sees the walk itself.
    heroWalkStep++;
    heroSetPose('walk');
    updateUse();   // the words follow the turn, even when the step is refused
    var nx = hero[0] + dx, ny = hero[1] + dy;
    if (nx < 0 || ny < 0 || ny >= town.map.length || nx >= town.map[0].length) {
      heroSettleSoon();
      return;
    }
    // Bump to attack: a living enemy on the destination tile is struck
    // instead of walked into. Either way the enemies take their turn -
    // except a blow at a warden that cannot be struck, which is no
    // fight and so is no turn (ADR 0015 Amendment 1 §2).
    var target = enemyAt(nx, ny);
    if (target) {
      var struck = heroAttack(target);
      closeEnemyVerbs();   // a bump closes any open enemy menu
      if (struck !== false) {
        lightTick();
        enemyTurn();
      }
      heroSettleSoon();
      return;
    }
    if ((town.legend[town.map[ny][nx]] || {}).solid) {
      var shut = (window.VEFR_DESCENT && window.VEFR_DESCENT.shutDoorLine)
        ? window.VEFR_DESCENT.shutDoorLine(regionName, nx, ny) : '';
      if (shut) combatSay(shut);
      heroSettleSoon();
      return;
    }
    if (propBlocked(nx, ny)) {
      heroSettleSoon();
      return;
    }
    hero = [nx, ny];
    quietTutorial();
    // Draw-only: start the hop now, but the game state above is already
    // settled and the turn below is never gated on the animation.
    heroStartStep(nx, ny, dx, dy);
    heroSettleSoon();
    var here = refreshPoi();
    if (here) journalVisit(here, nx, ny);
    // `comes-near` for a named place the hero walks up to: the tile is
    // the contact, so the distance is 0.
    if (here) fireRule('comes-near', { who: here, distance: 0 });
    libraryOnTile(nx, ny, regionName);
    takeHere();
    seeNow();
    updateUse();
    lightTick();
    enemyTurn();
    updateVerbRow();   // the monsters moved: the fight buttons follow
  }

  // The nearest-speaker search (the canvas click, the Talk button):
  // talk to whoever is within two tiles, or say so plainly.
  function tryNPC() {
    var nearest = null, dmin = 999;
    for (var key in speakers) {
      var s = speakers[key];
      var d = Math.abs(s.at[0] - hero[0]) + Math.abs(s.at[1] - hero[1]);
      if (d < dmin) { dmin = d; nearest = { key: key, spec: s, dist: d }; }
    }
    // `comes-near` for the speaker found, with the ACTUAL Manhattan
    // distance the loop just computed - a rule's declared reach does
    // the rest of the judging.
    if (nearest) fireRule('comes-near', { who: nearest.key, distance: nearest.dist });
    if (!nearest || nearest.dist > 2) {
      document.getElementById('near').textContent = 'No one is close enough to talk to.';
      return;
    }
    talkToSpeaker(nearest);
  }

  // The Talk button's handler: the same nearest-speaker path, under
  // its own name so Interact and Talk share one road.
  function talkNearest() { tryNPC(); }

  function brainConfigured() { return Boolean(llmUrl && llmModel); }

  // The speaker's seeded lines in the pack's own order.
  function seededLines(spec) {
    var seeds = (spec && spec.seeds) || {};
    return Object.keys(seeds).map(function (k) { return seeds[k]; })
      .filter(function (l) { return typeof l === 'string' && l.trim(); });
  }

  // The seeded line for the time of day, else the first one: seeds are
  // keyed by phase, so a dawn line is never said at dusk. Every Talk says
  // it again, the way a resident repeats themselves.
  function seededLine(spec, ph) {
    var own = spec && spec.seeds && spec.seeds[ph];
    if (typeof own === 'string' && own.trim()) return own;
    return seededLines(spec)[0] || null;
  }

  // Whether the offline talk path can produce any line for this speaker.
  function hasOfflineLine(key, spec) {
    if (seededLines(spec).length) return true;
    if (fragmentSpeakers().indexOf(key) !== -1) return true;
    var pool = window.VEFR_POOL || {};
    return Object.keys(pool).some(function (k) { return (pool[k] || []).length > 0; });
  }

  // One speaker's line - the talk path itself, shared by the Talk
  // button, the canvas click, the old E key, and Interact's resident
  // pick. The line is the pack's own: straight from the model when
  // one answers, else from the woven pool, else spliced from this
  // character's fragments, else the speaker's seeded line in turn.
  function talkToSpeaker(nearest) {
    var ph = phase();
    libraryFromSpeaker(nearest.key);
    var seed = (nearest.spec.seeds || {})[ph] || '';
    var voice = window.VEFR_VOICES[nearest.key] || '';
    var tone = world.phases[ph] || '';
    var system = voice + '\n\nCURRENT PHASE: ' + tone;
    var userPrompt = nearest.spec.name + ' speaks one line at ' + nearest.spec.near
      + ' in the current phase tone. The seed line for this phase: "' + seed
      + '" Match its plainness and shape, do not copy it word for word. Reply with only the JSON object.';
    var schema = { type: 'object', properties: {
      speaker: { type: 'string' }, line: { type: 'string' },
    }, required: ['speaker', 'line'], additionalProperties: false };
    llmPost({
      model: llmModel,
      messages: [{ role: 'system', content: system }, { role: 'user', content: userPrompt }],
      response_format: { type: 'json_schema', json_schema: { schema: schema, strict: true } },
      max_tokens: 120, temperature: 0.85, stream: false,
      chat_template_kwargs: { reasoning_effort: 'low' },
    }).then(function (r) { return r.json(); }).then(function (j) {
      var line = JSON.parse(j.choices[0].message.content);
      document.getElementById('near').textContent = '';
      showSpeech(nearest.spec.name, line.line, '');
    }).catch(function () {
      var key = 'npc:' + (STATE.get().phase || '?') + ':' + (nearest.key || '?');
      var pooled = poolDraw(key);
      var respliced = pooled ? null : composeLine(key);
      var card = pooled || respliced || composeFromFragments(nearest.key, 'line');
      if (card) {
        document.getElementById('near').textContent = '';
        showSpeech(card.speaker, card.line, pooled
          ? ''
          : respliced ? "Mixed from the game's saved lines."
          : "From this character's own lines.");
        return;
      }
      var seeded = seededLine(nearest.spec, ph);
      if (seeded) {
        document.getElementById('near').textContent = '';
        showSpeech(nearest.spec.name, seeded, '');
      } else {
        document.getElementById('near').textContent = "They didn't answer.";
      }
    });
  }

  document.getElementById('npc-close').addEventListener('click', function () {
    document.getElementById('npc-box').hidden = true;
    document.getElementById('talk').focus();
  });
  document.getElementById('talk').addEventListener('click', talkNearest);
  document.getElementById('interact').addEventListener('click', doInteract);
  document.getElementById('bagbtn').addEventListener('click', function () {
    if (window.openBag) window.openBag();
  });

