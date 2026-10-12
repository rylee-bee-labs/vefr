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
  // A character stands taller than its tile, feet on the tile's bottom.
  // A character with a ready walk sheet shows its down-facing idle frame.
  function drawSprite(key, tx, ty) {
    var im = spriteImgs[key];
    var height = T * 1.5 * spriteScale(window.VEFR_SPRITE_SCALE, key);
    var sheet = spriteSheets[key];
    if (sheetUsable(sheet) && spriteSheetReady(key)) {
      var sim = spriteSheetImgs[key];
      var fw = sheet.frame[0], fh = sheet.frame[1];
      var cols = Math.max(1, Math.floor(sim.naturalWidth / fw));
      var down = (sheet.directions && sheet.directions.down) || {};
      var idx = (down.idle && down.idle.length) ? down.idle[0] : 0;
      var col = idx % cols, row = Math.floor(idx / cols);
      var box = artSize(fw, fh, height);
      var across = snapSpan(tx * T + (T - box.w) / 2, box.w);
      var up = snapSpan(ty * T + T - box.h, box.h);
      ctx.drawImage(sim, col * fw, row * fh, fw, fh, across[0], up[0], across[1], up[1]);
      return;
    }
    var box = artSize(im.naturalWidth, im.naturalHeight, height);
    var across = snapSpan(tx * T + (T - box.w) / 2, box.w);
    var up = snapSpan(ty * T + T - box.h, box.h);
    ctx.drawImage(im, across[0], up[0], across[1], up[1]);
  }

  // An item marker on the floor: the item's sprite when the pack names a
  // ready one, else a small neutral dot. Small - a thing, not a body.
  function drawItemMarker(id, tx, ty) {
    var def = itemCatalog()[id];
    var sp = def && def.sprite;
    var size = T * 0.6;
    if (sp && spriteReady(sp)) {
      var im = spriteImgs[sp];
      var box = pixelNative ? artSize(im.naturalWidth, im.naturalHeight, size) : { w: size, h: size };
      var across = snapSpan(tx * T + (T - box.w) / 2, box.w);
      var up = snapSpan(ty * T + (T - box.h) / 2, box.h);
      ctx.drawImage(im, across[0], up[0], across[1], up[1]);
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
