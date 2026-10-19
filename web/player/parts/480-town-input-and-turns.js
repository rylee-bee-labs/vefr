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
  // Where the hero stands, published for a harness to read back (the
  // precedent is window.VEFR_HERO_FRAME and window.VEFR_COMBAT, one
  // step further: the pose says how the hero looks, this says where it
  // is). Read-only, `{x, y, region}`, refreshed on every arrival and
  // after every step - `vefr playthrough` walks by it and re-reads it
  // after each press, so a refused step is a refusal it can see. A pack
  // whose player has no town at all never publishes it.
  function heroPublishAt() {
    window.VEFR_HERO_AT = { x: hero[0], y: hero[1], region: regionName };
    return window.VEFR_HERO_AT;
  }
  function nowMs() {
    return (window.performance && window.performance.now)
      ? window.performance.now() : Date.now();
  }
  // Read at move time, never cached, so a change of preference is felt.
  // The OS's own setting and the player's Display > Reduced motion switch are
  // the same question: either one asking for still motion gets still motion,
  // and the sheet lays down the matching blanket in CSS (020-style.css).
  function reducedMotion() {
    return !!(window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
      || reducedMotionOn();
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
  // A sheet hero keeps its walk frame a moment after a step lands, so a
  // held walk (a step every 200 ms) never flashes the standing frame
  // between steps: that flash read as a bounce on every tile.
  var WALK_LINGER_MS = 140;
  var heroLinger = 0;
  function heroRestSoon() {
    if (heroLinger) window.clearTimeout(heroLinger);
    heroLinger = window.setTimeout(function () {
      heroLinger = 0;
      if (heroAnim) return;
      heroSetPose('idle');
      draw();
    }, WALK_LINGER_MS);
  }
  function heroFrame() {
    if (!heroAnim) return;
    if (nowMs() - heroAnim.start >= STEP_MS) {
      heroAnim = null;
      if (heroHasSheet) { draw(); heroRestSoon(); return; }
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
    ctx.translate(snapPx(t[0] * T + T / 2), snapPx(t[1] * T + T));
    // The lean is a rotation. A real canvas has rotate(); the minimal
    // stub context used by the test harness may not, and in that case
    // the hero still draws, only without the tilt.
    // A sheet steps frame by frame, so it is drawn upright and unsquashed:
    // the lean and the landing squash on top of its own walk read as a bounce.
    if (off.lean && !heroHasSheet && typeof ctx.rotate === 'function') {
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
      var cell = sheetCell('hero', 'hero', heroFacing, (heroAnim || heroLinger) ? 'walk' : 'idle', heroWalkStep)
        || { idx: heroSheetIdx, mirror: heroSheetMirror };
      var col = cell.idx % cols, row = Math.floor(cell.idx / cols);
      if (window.VEFR_HERO_FRAME) window.VEFR_HERO_FRAME.frame = cell.idx;
      var base = artSize(fw, fh, T * 1.5 * spriteScale(window.VEFR_SPRITE_SCALE, 'hero'));
      var sh = base.h, sw = base.w;
      var across = snapSpan(-sw / 2, sw), up = snapSpan(-sh, sh);
      if (cell.mirror) {
        drawFlipped(sim, col * fw, row * fh, fw, fh, across[0], up[0], across[1], up[1]);
      } else {
        ctx.drawImage(sim, col * fw, row * fh, fw, fh, across[0], up[0], across[1], up[1]);
      }
    } else if (spriteReady('hero')) {
      var im = spriteImgs['hero'];
      var baseH = T * 1.5 * spriteScale(window.VEFR_SPRITE_SCALE, 'hero');
      var base = artSize(im.naturalWidth, im.naturalHeight, baseH);
      // The squash is drawn as a slightly wider, shorter body - no
      // context scale needed - with the feet still on the tile bottom.
      var h = base.h * (1 - off.squash);
      var w = base.w * (1 + off.squash);
      var across = snapSpan(-w / 2, w), up = snapSpan(-h, h);
      // Facing left is the same picture mirrored about the tile centre.
      if (heroFacing === 'left') drawFlipped(im, 0, 0, im.naturalWidth, im.naturalHeight, across[0], up[0], across[1], up[1]);
      else ctx.drawImage(im, across[0], up[0], across[1], up[1]);
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
    // A phone's camera may pass a map's edge by PHONE_MARGIN tiles.
    var margin = onPhone ? PHONE_MARGIN * T : 0;
    var camX = mapW <= viewW ? (mapW - viewW) / 2
      : Math.min(Math.max(camHero[0] * T + T / 2 - viewW / 2, -margin), mapW - viewW + margin);
    var camY = mapH <= viewH ? shortMapY(mapH)   // a room shorter than the window: clamped under the top bar (issue #448)
      : Math.min(Math.max(camHero[1] * T + T / 2 - viewH / 2, -margin), mapH - viewH + margin);
    camX = snapPx(camX); camY = snapPx(camY);
    cameraAt.x = camX;
    cameraAt.y = camY;

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
    edgesDrawn = 0;
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
        // A ground that blends: the piece of its edges sheet that matches which neighbours share
        // this symbol, laid over the tile. All four the same (15) draws nothing.
        var edgeImg = edgeImgs[ch];
        if (edgeImg && edgeImg.complete && edgeImg.naturalWidth > 0) {
          var mask = edgeMask(town.map, x, y);
          if (mask !== 15) {
            var ew = edgeImg.naturalWidth / 4, eh = edgeImg.naturalHeight / 4;
            ctx.drawImage(edgeImg, (mask % 4) * ew, Math.floor(mask / 4) * eh, ew, eh, x * T, y * T, T, T);
            edgesDrawn++;
          }
        }
        if (info.solid && !hasTile && !hasGrid) {   // the grey inset marks a wall with no picture
          ctx.fillStyle = '#444';
          ctx.fillRect(x * T + 4 * u, y * T + 4 * u, T - 8 * u, T - 8 * u);
        }
        if (info.deco && info.deco_color) {
          ctx.fillStyle = info.deco_color;
          ctx.fillRect(x * T + 8 * u, y * T + 8 * u, T - 16 * u, T - 16 * u);
        }
      }
    }
    // A generated floor's decor lies on the ground, under everything else.
    drawDecor();
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
    drawTargetCue();
    ctx.restore();
    if (animWant) scheduleAnim();
  }

  // ---- the cue on the smart action's target (vefr#486) --------------
  //
  // F, and the touch layer's smart button, act on ONE tile; before the
  // press, the player is told what that is with words alone. The cue
  // puts the same answer on the map itself, in two parts that are not
  // each other's backup:
  //
  //   the glow   - a soft halo over the tile and a little past its
  //               edge. It is what the eye notices first, and it is
  //               the part that is colour;
  //   the marks  - four corner brackets around the tile. A SHAPE: the
  //               cue still reads with the glow turned off, in a
  //               greyscale screenshot, to a player who cannot tell
  //               the gold from the ground. Nothing here relies on
  //               colour alone.
  //
  // The glow breathes only while motion is allowed; reduced motion -
  // the OS setting or Display > Reduced motion, the same question
  // reducedMotion() already answers for the step - draws it once, at
  // the middle of its range, and the brackets are identical either
  // way, so the cue is never motion-only information.
  //
  // Draw only: it reads the pick, changes no game state and never
  // calls draw(). It asks for the one shared ticker (455-the-props.js:
  // at most twelve times a second, only while the page is shown, and
  // never started without animation) for the breath, and nothing else.
  var TARGET_GLOW_MS = 2400;   // one breath, out and back
  var TARGET_GLOW_MIN = 0.08;  // the glow's own alpha, at its dimmest
  var TARGET_GLOW_MAX = 0.30;  // and at its brightest
  // The glow's alpha at a moment, as a pure function of a clock, so a
  // harness can ask what it should be without a canvas. Reduced
  // motion has no breath to read: it takes the middle and keeps it.
  window.VEFR_TARGET_GLOW = function (at) {
    var mid = (TARGET_GLOW_MIN + TARGET_GLOW_MAX) / 2;
    if (reducedMotion()) return mid;
    var t = typeof at === 'number' && isFinite(at) ? at : nowMs();
    var wave = (Math.cos(t / TARGET_GLOW_MS * Math.PI * 2) + 1) / 2;   // 0..1..0
    return TARGET_GLOW_MIN + (TARGET_GLOW_MAX - TARGET_GLOW_MIN) * wave;
  };
  function targetGlowColour(alpha) {
    return 'rgba(216, 170, 78, ' + alpha.toFixed(3) + ')';
  }
  function drawTargetCue() {
    var t = pickTarget(interactState());
    if (!t) return;
    if (!reducedMotion()) animWant = true;   // the shared ticker's breath
    var cx = t.at[0] * T + T / 2, cy = t.at[1] * T + T / 2;
    var reach = T * 1.05;      // how far the halo reaches past the centre
    var alpha = window.VEFR_TARGET_GLOW();
    ctx.save();
    // The glow. A context without gradients - the minimal stub a node
    // harness runs the player against - gets the flat disc at the
    // glow's centre value, so the cue still reads there.
    var grad = typeof ctx.createRadialGradient === 'function'
      ? ctx.createRadialGradient(cx, cy, T * 0.2, cx, cy, reach) : null;
    if (grad && typeof grad.addColorStop === 'function') {
      grad.addColorStop(0, targetGlowColour(alpha));
      grad.addColorStop(1, targetGlowColour(0));
      ctx.fillStyle = grad;
      ctx.fillRect(cx - reach, cy - reach, reach * 2, reach * 2);
    } else {
      ctx.fillStyle = targetGlowColour(alpha);
      ctx.beginPath();
      ctx.arc(cx, cy, T * 0.62, 0, Math.PI * 2);
      ctx.fill();
    }
    // The brackets: the tile's four corners, marked from just inside
    // each corner along its two edges, so they frame the tile instead of
    // covering what they point at. The HUD gold reads on both light and
    // dark ground; the marks are strokes only, never a fill, so the thing
    // being marked stays readable underneath.
    ctx.strokeStyle = '#D8AA4E';
    ctx.lineWidth = 2;
    var inset = T * 0.4, arm = T * 0.18;
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) {
      var mx = cx + s[0] * inset, my = cy + s[1] * inset;
      ctx.beginPath();
      ctx.moveTo(mx - s[0] * arm, my);
      ctx.lineTo(mx, my);
      ctx.lineTo(mx, my - s[1] * arm);
      ctx.stroke();
    });
    ctx.restore();
  }
  // What the cue is showing right now, read-only (precedent:
  // window.VEFR_MOTION), so a test can see the tile, the glow's alpha
  // and whether it is breathing without reading pixels. Null when
  // nothing is in reach, exactly as nothing is drawn.
  window.VEFR_TARGET_CUE = function () {
    var t = pickTarget(interactState());
    if (!t) return null;
    return { at: [t.at[0], t.at[1]], label: t.label, kind: t.kind,
             glow: window.VEFR_TARGET_GLOW(), breathing: !reducedMotion(),
             marks: 4 };
  };

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

  // Whether the hero can step off (x, y) at all - any open neighbour,
  // in a fixed order so the answer is the same everywhere. A stair
  // landing is only set aside when there is somewhere to step to
  // (vefr#465): a tile the hero can never leave is never a landing, or
  // the way back would be gone as well.
  function stepOffExists(x, y) {
    var steps = [[0, -1], [0, 1], [-1, 0], [1, 0]];
    for (var i = 0; i < steps.length; i++) {
      if (tileOpen(x + steps[i][0], y + steps[i][1])) return true;
    }
    return false;
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

  // Enter another region through a door or a stair: swap the current
  // map, speakers, and hero, then resize, draw, and refresh the POI
  // line. `via` is the kind of transition the hero came by ('door',
  // 'stairs', or nothing for a wake and for the New-descent control),
  // and it only decides one thing: whether the tile they land on is set
  // aside as a landing (below).
  function enterRegion(name, at, via) {
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
    nameTheCanvas(name);   // the canvas is named for where the hero is (vefr#461)
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
    heroPublishAt();
    fogOn = fogEnabled();
    fogRadius = (town.fog && town.fog.radius) || 6;
    resetLight();
    resetStatuses();   // a burn does not travel either (vefr#497)
    loadTiles();
    loadFog();
    seeNow();
    loadEnemies();
    combatSnapshot();
    // What this floor is, while the hero stands where they arrived
    // (vefr#362): only a floor of a labelled Section answers, so every
    // other region arrives exactly as it did.
    arrivalNote = (window.VEFR_DESCENT && typeof window.VEFR_DESCENT.arrival === 'function')
      ? window.VEFR_DESCENT.arrival(name, hero) : null;
    // The tile a stair drops the hero on is a landing, not the way back
    // (vefr#465). The hero stands exactly where the transition wrote -
    // the floor's up anchor, which the geometry and the elevator rule
    // are built on - but the stair on that tile stays set aside until
    // they have stepped off it, so the prompt cannot flip from "Go down
    // the stairs" to "Go up the stairs" on the very next press. Only a
    // stair arrival sets it aside: a door opens both ways and means the
    // same thing from either side, a wake is not an arrival at all, and
    // a tile the hero can never step off of is not a landing.
    // Any arrival by a transition (`via` is the kind used: a door into the
    // descent drops the hero on a floor's stair just as a stair does) sets
    // the tile aside; whether a stair is on it is asked when the button is
    // drawn, because a generated floor wires its stairs on arrival.
    landing = (via && stepOffExists(hero[0], hero[1])) ? [hero[0], hero[1]] : null;
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
      if (bagAdd(id, null, true)) {
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
  // `kind` is one of exactly: resident, trader, identifier, chest, book,
  // door, stairs, place, enemy. `id` is the caller's key (speaker key,
  // book id, transition id, enemy id, poi key); `name` is the display
  // name. A malformed candidate - missing or unknown kind, missing,
  // short or non-numeric `at` - is skipped, never an error.
  //
  // Reach is Manhattan from `state.hero`: one tile for the things you
  // touch (chest, book, door, stairs, place, enemy), two for people (the
  // talk reach today). `interactTargets` returns every candidate in
  // reach, in the caller's own order, each a fresh { kind, id, name,
  // at, dist, label } with `label` set from `labelFor`. `pickTarget`
  // returns one of them: a candidate on the tile the hero faces,
  // else one on the hero's own tile, else the nearest in reach.
  // Ties break by kind - door and stairs share the top rank and
  // candidate order decides between them, then chest, book, trader,
  // identifier, resident, place, enemy - and finally by candidate
  // order. The two service kinds sit where the trade panel's did, so a
  // shopkeeper or a reader opens their panel rather than their talk.
  // Nothing is mutated: every call returns fresh objects. No DOM, no
  // storage, no clock, no chance.
  globalThis.labelFor = function (target) {
    if (!target) return null;
    var name = target.name;
    if (target.kind === 'chest') return 'Open the chest';
    // A note lying on the ground is read, not opened.
    if (target.kind === 'book') return 'Read ' + name;
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
    var reach = { resident: 2, trader: 2, identifier: 2, chest: 1, book: 1,
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
    var rank = { door: 0, stairs: 0, chest: 1, book: 2, trader: 3,
                 identifier: 4, resident: 5, place: 6, enemy: 7 };
    var best = null, bestTier = -1, bestDist = -1, bestRank = -1;
    for (var i = 0; i < all.length; i++) {
      var t = all[i];
      // 0 the tile the hero faces, 1 the hero's own tile, 2 the rest.
      // A place under the hero's feet (tier 1) beats a resident merely
      // within talk reach (tier 2); a resident the hero faces (tier 0)
      // still wins, and on the own-tile tie `rank` puts the resident
      // before the place. A door facing the hero is tier 0 too, so an
      // adjacent resident never takes it.
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
  //   book     - every map book in this region that is not a chest, by
  //              its title: an unfound one from a tile away, and a found
  //              one only while the hero stands where it lay (it is no
  //              longer drawn, so from anywhere else it is gone);
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
      if (!b || b.found !== 'map' || !Array.isArray(b.at)) return;
      if ((b.region || 'town') !== regionName) return;
      if (b.chest) {
        if (bookIsFound(b.id)) return;
        candidates.push({ kind: 'chest', id: b.id, name: b.title || 'the chest',
                          at: [b.at[0], b.at[1]] });
        return;
      }
      // A found note is no longer drawn on the map, so it stays a target
      // only on the tile where it lay: the hero has just picked it up and
      // the button says what the hero holds. From a tile away it is gone.
      if (bookIsFound(b.id) && !(hero[0] === b.at[0] && hero[1] === b.at[1])) return;
      candidates.push({ kind: 'book', id: b.id, name: b.title || 'the note',
                        at: [b.at[0], b.at[1]] });
    });
    // Just arrived (vefr#362, #465): the tile the hero stands on is where
    // they arrived, not the stair under them. On a labelled floor it is
    // the floor itself, read as a note; on any other stair landing it is
    // nothing at all until they step off. The stair is set aside for
    // exactly that moment, and no longer.
    var arrived = arrivalHere();
    if (arrived) {
      candidates.push({ kind: 'place', id: ARRIVAL_ID, name: arrivalNote.name,
                        at: [hero[0], hero[1]] });
    }
    function onLanding(x, y) {
      return landingHere() && x === landing[0] && y === landing[1];
    }
    function onArrival(x, y) {
      // The tile the hero stands on when they arrive: the note above
      // where there is one, else the landing itself (vefr#465) - while
      // they are still on it.
      return (arrived && x === hero[0] && y === hero[1]) || onLanding(x, y);
    }
    transitions().forEach(function (tr) {
      if (!tr || tr.from !== regionName || !Array.isArray(tr.at)) return;
      if (typeof tr.at[0] !== 'number' || typeof tr.at[1] !== 'number') return;
      var c = transitionCandidate(tr);
      if (arrived && tr.at[0] === hero[0] && tr.at[1] === hero[1]) return;
      // A stair on the landing waits for the first step; a door on it
      // opens both ways and means the same from either side, so it stays.
      if (onLanding(tr.at[0], tr.at[1]) && c.kind === 'stairs') return;
      candidates.push(c);
    });
    var texts = town.poi_text || {};
    Object.keys(texts).forEach(function (key) {
      var xy = key.split(',');
      var x = Number(xy[0]), y = Number(xy[1]);
      if (!isFinite(x) || !isFinite(y)) return;
      if (onArrival(x, y)) return;
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

  // ---- one plain sentence per action (#463) ------------------------
  //
  // The result line used to name the action ("last action: console
  // (dusk)"), which says nothing about what the action did. Each verb
  // now speaks one sentence that reads as a sentence, and that
  // sentence is what the line shows.
  //
  // The wording is the engine's, so it stays neutral: nothing here
  // names a pack's creature, and `{what}` is filled from the pack's own
  // name for the thing acted on. A pack replaces any of these the way
  // it replaces every other player word - `player_words` in world.json,
  // key `combat.<verb>` - through the one reader, so the pack's own
  // sentence wins and this stays the default. The rows are joined onto
  // the one message table (part 340) rather than kept beside it, and
  // outside its markers, so the two tables keep their own key sets.
  var VEFR_COMBAT_WORDS = {
    attack: 'You hit {what} for {damage}.',
    console: '{what} quiets a little.',
    hurl: '{what} does not care for that.',
    other: 'You say it anyway. Nothing answers.',
    none: 'There is nothing here to answer that.'
  };
  Object.keys(VEFR_COMBAT_WORDS).forEach(function (verb) {
    VEFR_PLAYER_WORDS['combat.' + verb] = VEFR_COMBAT_WORDS[verb];
  });
  // One reader: the verb's own row when the verb - or the pack - has
  // one, else the catch-all for any verb a pack names, else the line
  // for a verb pressed with nothing to act on.
  function verbWord(verb, slots) {
    var words = (window.VEFR_WORLD && window.VEFR_WORLD.player_words) || {};
    var key = 'combat.' + verb;
    if (VEFR_PLAYER_WORDS[key] || typeof words[key] === 'string') {
      return playerWord(key, slots);
    }
    return playerWord('combat.other', slots);
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
    // A verb the hero carries may hit: the act's own `attack` always
    // does, and any verb something's `changes` give attack does too, for
    // that much more damage. A verb with no such change is still words.
    var bonus = verbAtkBonus(verb);
    if (verb === 'attack' || bonus > 0) return heroAttack(enemy, bonus);
    // The plain sentence, not "You use Console on it": what the verb
    // DID is the line a player reads (#463). `label` is kept in the
    // signature because the row's word is what the button says, but it
    // is no longer spelled into the sentence.
    var said = verbWord(verb, { what: (enemy && enemy.name) || 'it' });
    // The other verbs are words only, but a practice spec can learn from
    // them. The default verbs are `console`/`hurl`; any other name
    // counts toward nothing.
    var kind = (verb === 'console') ? 'consoles'
      : (verb === 'hurl') ? 'hurls' : null;
    if (kind) sayGrowth(practiceSuffix(growBump(kind)));
    combatSay(said);
    return true;
  }
  // One verb, acted on and journalled, in that order: the sentence the
  // verb spoke is the sentence the journal keeps, and it is read before
  // the monsters take their turn, so their answer cannot be what got
  // written down. Both call sites go through here, so a verb can never
  // be journalled without saying what it did.
  function takeVerb(verb, label, foe) {
    // Every verb pressed is a fact of the world: it fires `uses-verb` with
    // the verb's own id, the act's own verbs as well as the ones an item
    // grants, because the validator lets a rule name either (maplab.pack_verbs)
    // and a rule it accepts must be able to fire (#531 review). A pack with no
    // `uses-verb` rule notices nothing, so its play is unchanged.
    fireRule('uses-verb', { verb: verb });
    if (!foe) {
      // Pressed with nothing named to act on: nothing happens, and the
      // line says so in a sentence rather than naming the verb.
      recordVerb(verb, verbWord('none'));
      return false;
    }
    // The live line is emptied first so that what is on it afterwards is
    // exactly what this verb said - nothing to tell a quiet verb from a
    // loud one, and nothing left over from the last turn to be mistaken
    // for this one's sentence.
    combatSay('');
    var done = applyVerb(verb, label, foe);
    recordVerb(verb, combatText());
    return done;
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
        enterRegion(trans.to, trans.to_at, t.kind);
      } else if (t.kind === 'chest') {
        var books = libraryBooks(), book = null;
        for (var i = 0; i < books.length; i++) {
          if (books[i] && books[i].id === t.id) { book = books[i]; break; }
        }
        if (!book) throw new Error('chest gone');
        // A vault chest taken once stays taken (ADR 0015): its permanent
        // flag `vault-chest:<id>:c<cycle>` is consulted here, so a chest
        // whose flag is set opens empty even on a floor whose taken-chests
        // delta - or the library's found-list - is gone. A vault that names
        // no id keeps the found-list alone, exactly as E8b played.
        var D = window.VEFR_DESCENT;
        var vaultChest = book.place === 'vault-chest' && !!D;
        if (vaultChest && D.vaultChestTaken()) {
          makeNoise('chest');
          combatSay('The chest is empty.');
          return;
        }
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
        if (vaultChest) D.markVaultChestTaken();
        combatSnapshot();
      } else if (t.kind === 'book') {
        var lib = libraryBooks(), note = null;
        for (var n = 0; n < lib.length; n++) {
          if (lib[n] && lib[n].id === t.id) { note = lib[n]; break; }
        }
        if (!note) throw new Error('book gone');
        // An unfound note is found the way it is on any other map, and
        // that opens the reader. One already found - the hero stood on
        // it to get here - opens straight back up, with no second
        // "you found a book" toast. Reading is quiet: no noise.
        if (bookIsFound(note.id)) openReader(note);
        else foundBook(note, 'map');
      } else if (t.kind === 'trader') {
        openTrade(t.id, t.name, document.getElementById('interact'));
      } else if (t.kind === 'identifier') {
        openIdentify(t.id, t.name, document.getElementById('interact'));
      } else if (t.kind === 'resident') {
        if (!speakers[t.id]) throw new Error('speaker gone');
        // `comes-near` for the speaker talked to - the same event, with
        // the same distance, as the Talk button's nearest-speaker search
        // fires. This verb is the road an F press and the
        // `Talk to <name>` button both take, so a pack's rule over a
        // person has to be answered from here too.
        fireRule('comes-near', { who: t.id, distance: t.dist });
        talkToSpeaker({ key: t.id, spec: speakers[t.id], dist: t.dist });
      } else if (t.kind === 'place' && t.id === ARRIVAL_ID) {
        // The floor, read: its name and the way on. Reading it spends the
        // note; the landing stays set aside until the hero steps off the
        // tile, so the stair never answers the press that read (vefr#465).
        showSpeech(arrivalNote.name, arrivalNote.line, '');
        arrivalNote = null;
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
          if (takeVerb(verbs[0][0], verbs[0][1], foe)) {
            lightTick();
            // The monsters have their turn first, then the states their blows
            // left tick - the established order, and the one place the hero's own
            // damage resolves (vefr#497, review #528).
            enemyTurn();
            statusTurn();
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

  // The nearest resident the Talk control may name and take. It is the
  // same filtered set Interact uses (interactState leaves out a speaker
  // with no offline line when no brain is configured), so the words on
  // the button and the person it talks to can never disagree.
  function nearestResident() {
    return interactTargets(interactState()).filter(function (t) {
      return t.kind === 'resident';
    }).sort(function (a, b) { return a.dist - b.dist; })[0] || null;
  }

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
    var talk = document.getElementById('talk');
    if (talk) {
      var resident = nearestResident();
      var talkLabel = resident ? 'Talk to ' + resident.name : 'Talk';
      talk.setAttribute('aria-label', talkLabel);
      // The key letter is the player's own Interact binding, read from
      // the one keybinds table - never a hard-coded F. This runs after
      // `updateKeyLetters` on every step and every failed press, so a
      // rebinding must survive it.
      var talkKeys = keybindKeys('interact');
      var talkKey = talkKeys.length ? keybindKeyName(talkKeys[0]) : '';
      talk.title = talkKey ? talkLabel + ' (' + talkKey + ')' : talkLabel;
      var sr = talk.querySelector('.sr-only');
      if (sr) sr.textContent = talkLabel;
    }
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
    // A pack that opted into Rest (vefr E3) keeps its one always-available
    // verb on show: the row stays up with that button alone, so resting is
    // one press whenever the player wants it. Every other pack hides the
    // row exactly as before.
    vrow.hidden = !near && !timeRestOn();
  }

  // The floor the hero has just arrived on (vefr#362), from
  // VEFR_DESCENT.arrival: `{at, name, line}` while they still stand on the
  // tile they arrived at and have not read it, else null. `ARRIVAL_ID` is
  // its Interact id, which no `x,y` poi key can be.
  var ARRIVAL_ID = 'arrival';
  var arrivalNote = null;
  function arrivalHere() {
    return !!(arrivalNote && hero[0] === arrivalNote.at[0] && hero[1] === arrivalNote.at[1]);
  }
  // The stair tile an arrival dropped the hero on (vefr#465): `[x, y]`
  // while they are still standing on it, else null. The stair on that
  // tile is no Interact target until they step off - the first step
  // clears this, exactly as it clears the note above - so a stair never
  // answers the press that took it, in the other direction, at once.
  var landing = null;
  function landingHere() {
    return !!(landing && hero[0] === landing[0] && hero[1] === landing[1]);
  }

  // The named place the hero now stands on, written to the POI line.
  var POI_QUIET_MS = 4000;
  var poiTimer = null;
  function refreshPoi() {
    var here = '';
    if (arrivalHere()) here = arrivalNote.name;
    else for (var k in pois) {
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

  function peopleBlock() {
    var pl = (window.VEFR_WORLD || {}).player || {};
    return pl.people_block === true;
  }
  function speakerAt(x, y) {
    return Object.keys(speakers || {}).some(function (k) {
      var s = speakers[k];
      return s && Array.isArray(s.at) && s.at[0] === x && s.at[1] === y;
    });
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
        // The monsters have their turn first, then the states their blows
        // left tick - the established order, and the one place the hero's own
        // damage resolves (vefr#497, review #528).
        enemyTurn();
        statusTurn();
      }
      heroSettleSoon();
      return;
    }
    // A pack whose people are solid (player.people_block): pressing toward
    // one turns the hero to face them, and does not walk through them.
    if (peopleBlock() && speakerAt(nx, ny)) {
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
    heroPublishAt();
    arrivalNote = null;   // the arrival is over at the first step
    landing = null;       // and so is the set-aside: the stair is a stair
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
    // The monsters have their turn first, then the states their blows
    // left tick - the established order, and the one place the hero's own
    // damage resolves (vefr#497, review #528).
    enemyTurn();
    statusTurn();
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

  // The Talk button takes the resident its own words name (the same
  // filtered nearest resident `updateUse` reads), so the name and the
  // press resolve to one person. A canvas click keeps the older
  // nearest-speaker search above - it is a click on the map, not the
  // labelled control.
  function talkNearest() {
    var nearest = nearestResident();
    // `comes-near` for the resident found, with the ACTUAL Manhattan
    // distance - the same event and distance the Interact path fires.
    if (nearest) fireRule('comes-near', { who: nearest.id, distance: nearest.dist });
    if (!nearest) {
      document.getElementById('near').textContent = 'No one is close enough to talk to.';
      return;
    }
    talkToSpeaker({ key: nearest.id, spec: speakers[nearest.id], dist: nearest.dist });
  }

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
  // button, the canvas click, the F key (E is its unadvertised alias),
  // and Interact's resident pick. The line is the pack's own: straight
  // from the model when one answers, else from the woven pool, else
  // spliced from this character's fragments, else the speaker's seeded
  // line in turn.
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
  document.getElementById('interact').addEventListener('click', doInteract);
  document.getElementById('talk').addEventListener('click', talkNearest);
  document.getElementById('bagbtn').addEventListener('click', function () {
    if (window.openBag) window.openBag();
  });
