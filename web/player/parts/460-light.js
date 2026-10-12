  // ---- light: a torch, or a one-shot reveal ----
  // An item with `light` is used from the Bag. `radius`/`turns` widen the
  // lit area for a while, then it gutters out; `reveal` marks every
  // tile of the region explored at once. The pack's own base radius is
  // restored when the turns run out or a new region is entered.
  var lightTurns = 0;   // hero turns left on a burning torch
  var lightBonus = 0;   // extra tiles the torch adds to the lit circle
  // A torch widens the radius and nothing else. The lit area's shape is
  // the pack's (`fog.shape`, circle or square) and is read in one place
  // only - litNow(), in the fog part - so a torch widens whichever shape
  // the pack declared without this part having to know what it is, and
  // without a second reader the two could ever disagree about it.
  function lightBase() {
    return (town.fog && town.fog.radius) || 6;
  }
  function renderLightHud() {
    var el = document.getElementById('light-live');
    if (!el) return;
    if (lightTurns > 0) {
      el.hidden = false;
      el.textContent = 'Turns of light: ' + lightTurns;
    } else {
      el.hidden = true;
      el.textContent = '';
    }
  }
  // Put the dark back the way the pack declared it (a torch has died).
  function restoreLightRadius() {
    lightTurns = 0;
    lightBonus = 0;
    fogRadius = lightBase();
    renderLightHud();
  }
  // A new region is a fresh dark: a burning light does not travel.
  function resetLight() {
    lightTurns = 0;
    lightBonus = 0;
    renderLightHud();
  }
  // One hero turn passes: the torch burns one turn lower and gutters out
  // on the last. Announced once, on the turn it dies.
  function lightTick() {
    if (lightTurns <= 0) return;
    lightTurns -= 1;
    if (lightTurns <= 0) {
      restoreLightRadius();
      resize();
      draw();
      combatSay('The light gutters out.');
      return;
    }
    renderLightHud();
  }
  // The Bag's Use control for a `light` item. Returns true only when a
  // copy was actually spent; in a region with no dark (or the player's
  // fog turned off) it says so and keeps the thing.
  window.useLightItem = function (id, def) {
    var light = def && def.light;
    if (!light || typeof light !== 'object') return false;
    if (!fogOn || !town.fog) {
      bagSay('There is no dark here to light.');
      return false;
    }
    var reveal = light.reveal === true;
    var radius = light.radius, turns = light.turns;
    if (!reveal && (!(radius > 0) || !(turns > 0))) return false;
    // Spend only now that the item can actually be used - and never
    // spend a kept thing (a lantern is lit again, not used up).
    if (def.keep !== true && !bagRemoveOne(id)) return false;
    if (reveal) {
      for (var y = 0; y < town.map.length; y++) {
        for (var x = 0; x < town.map[0].length; x++) explored[x + ',' + y] = 1;
      }
      saveFog();
      draw();
      bagSay('The whole place is laid out.');
      return true;
    }
    lightBonus = radius;
    lightTurns = turns;
    fogRadius = lightBase() + lightBonus;
    renderLightHud();
    resize();
    draw();
    bagSay('The torch catches: ' + radius + ' wider for ' + turns + ' turns.');
    return true;
  };

  // The shopkeeper of this region, when the hero stands beside them.
  // window.VEFR_SHOPS names one speaker key per region; "next to" is
  // Manhattan distance one, the same reach as a bump.
  function shopkeeperNear() {
    var key = shopKeyHere(regionName);
    if (!key) return null;
    var spec = speakers[key];
    if (!spec || !Array.isArray(spec.at)) return null;
    var d = Math.abs(spec.at[0] - hero[0]) + Math.abs(spec.at[1] - hero[1]);
    return d <= 1 ? { key: key, spec: spec } : null;
  }

  // (The old `chestHere` - "the chest the hero is standing on" - is
  // gone with `useHere`; the Interact target list below enumerates
  // every chest in reach itself.)

  function spriteReady(key) {
    var im = spriteImgs[key];
    return im && im.complete && im.naturalWidth > 0;
  }
  // -- spriteScale start --
  // A character's size factor: the pack's own number when it is a sane one, else 1 (the standard).
  window.spriteScale = function (scales, key) {
    var v = scales && scales[key];
    return (typeof v === 'number' && isFinite(v) && v >= 0.2 && v <= 2) ? v : 1;
  };
  // -- spriteScale end --
  // The direction's frames, a missing side or `up` falling back as the
  // validator allows: a missing left or right is the other mirrored, and
  // anything else missing is `down`.
  var oneShots = {};
  function sheetPick(key, dir) {
    var dirs = ((spriteSheets[key] || {}).directions) || {};
    if (dirs[dir]) return { frames: dirs[dir], mirror: false };
    if (dir === 'left' && dirs.right) return { frames: dirs.right, mirror: true };
    if (dir === 'right' && dirs.left) return { frames: dirs.left, mirror: true };
    return { frames: dirs.down, mirror: false };
  }
  // The sheet cell a character shows now. A one-shot (act, attack, hurt)
  // plays its frames once, then the character is idle again; a looping
  // state (idle, talk) moves on at the sheet's fps, or holds frame 0 under
  // reduced motion. A walk frame follows the step counter, as it always did.
  function sheetCell(key, actor, dir, state, walkStep) {
    var pick = sheetPick(key, dir);
    if (!pick || !pick.frames) return null;
    var f = pick.frames, fps = spriteSheets[key].fps;
    var now = nowMs();
    var shot = oneShots[actor];
    if (shot && !reducedMotion()) {
      var list = f[shot.state] || [];
      var t = (now - shot.start) / 1000 * fps;
      if (t < list.length) {
        animWant = true;
        return { idx: list[Math.floor(t)], mirror: pick.mirror };
      }
    }
    delete oneShots[actor];
    if (state === 'walk' && f.walk && f.walk.length) {
      return { idx: f.walk[(walkStep - 1) % f.walk.length], mirror: pick.mirror };
    }
    var loop = (state === 'talk' && f.talk && f.talk.length) ? f.talk : f.idle;
    if (loop.length > 1 && !reducedMotion()) {
      animWant = true;
      return { idx: loop[Math.floor(now / 1000 * fps) % loop.length], mirror: pick.mirror };
    }
    return { idx: loop[0], mirror: pick.mirror };
  }
  // A one-shot starts now. Reduced motion shows none.
  function playOneShot(actor, state) {
    if (reducedMotion()) return;
    oneShots[actor] = { state: state, start: nowMs() };
  }
  // A character stands taller than its tile, feet on the tile's bottom.
  // `pose` names who it is (`actor`, the key one-shots are kept under), the
  // way it faces and the state it is in; a character with a ready walk
  // sheet draws the cell that pose picks, mirrored when its side is missing.
  function drawSprite(key, tx, ty, pose) {
    var im = spriteImgs[key];
    var h = T * 1.5 * spriteScale(window.VEFR_SPRITE_SCALE, key);
    var sheet = spriteSheets[key];
    var cell = (sheetUsable(sheet) && spriteSheetReady(key))
      ? sheetCell(key, pose.actor, pose.dir, pose.state, 0) : null;
    if (cell) {
      var sim = spriteSheetImgs[key];
      var fw = sheet.frame[0], fh = sheet.frame[1];
      var cols = Math.max(1, Math.floor(sim.naturalWidth / fw));
      var col = cell.idx % cols, row = Math.floor(cell.idx / cols);
      var sw = h * (fw / fh || 1);
      var dx = tx * T + (T - sw) / 2, dy = ty * T + T - h;
      if (cell.mirror) {
        ctx.drawImage(sim, col * fw, row * fh, fw, fh, dx + sw, dy, -sw, h);
      } else {
        ctx.drawImage(sim, col * fw, row * fh, fw, fh, dx, dy, sw, h);
      }
      return;
    }
    var w = h * (im.naturalWidth / im.naturalHeight || 1);
    ctx.drawImage(im, tx * T + (T - w) / 2, ty * T + T - h, w, h);
  }

  // An item marker on the floor: the item's sprite when the pack names a
  // ready one, else a small neutral dot. Small - a thing, not a body.
  function drawItemMarker(id, tx, ty) {
    var def = itemCatalog()[id];
    var sp = def && def.sprite;
    var size = T * 0.6;
    if (sp && spriteReady(sp)) {
      ctx.drawImage(spriteImgs[sp], tx * T + (T - size) / 2,
                    ty * T + (T - size) / 2, size, size);
      return;
    }
    ctx.fillStyle = '#CBC6B6';
    ctx.beginPath();
    ctx.arc(tx * T + T / 2, ty * T + T / 2, T * 0.16, 0, Math.PI * 2);
    ctx.fill();
  }

  // The hero alone is drawn with a little life: the hero faces the way
  // it walks, and a step is a short hop with a lean and a landing squash.
  // The motion is cosmetic - the game state changes at once in move(),
  // and only the drawing is tweened. Reduced motion turns the hop off.
  //
  // The pure maths lives in stepMotion(), which a node test can call
  // directly (progress in, pixel offset out); it has no game state.
