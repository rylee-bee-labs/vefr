  // ---- fog of war ----
  // A region may declare `fog`: only what the hero has seen is drawn, a
  // radius around them is lit, and the rest of the memory is dimmed.
  // Explored tiles are remembered per region, per world, as a bitset:
  // one bit per tile of the region map, row-major, most significant bit
  // first in each byte, base64 text under `vefr-fog2-...`. An old JSON
  // array of "x,y" strings under `vefr-fog-...` converts on load - the
  // bitset written, the old key dropped - so no tile is lost in the move.
  // A player preference on top of the pack's choice: a region may declare
  // fog, and the player may still turn the dark off for themselves. Kept
  // per world, beside the explored tiles.
  function fogPrefKey() {
    var w = (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
    return 'vefr-fogpref-' + w;
  }
  function fogPrefOn() {
    return store.get(fogPrefKey()) !== 'off';
  }
  function setFogPref(on) {
    store.set(fogPrefKey(), on ? 'on' : 'off');
  }
  function fogEnabled() { return !!town.fog && fogPrefOn(); }
  var fogOn = fogEnabled();
  var fogRadius = (town.fog && town.fog.radius) || 6;
  var explored = {};
  function fogKey() {
    var w = (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
    return 'vefr-fog-' + w + '-' + regionName;
  }
  function fog2Key() {
    var w = (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
    return 'vefr-fog2-' + w + '-' + regionName;
  }
  // One bit per tile: index = y*width + x over the region map, most
  // significant bit first in each byte, then base64. In-memory stays
  // keyed "x,y" - only the saved form is packed.
  function encodeFog() {
    var w = town.map[0].length, h = town.map.length;
    var bits = new Uint8Array((w * h + 7) >> 3);
    for (var y = 0; y < h; y++) {
      for (var x = 0; x < w; x++) {
        if (!explored[x + ',' + y]) continue;
        var i = y * w + x;
        bits[i >> 3] |= 1 << (7 - (i & 7));
      }
    }
    var s = '';
    for (var b = 0; b < bits.length; b++) s += String.fromCharCode(bits[b]);
    return btoa(s);
  }
  function decodeFog(value) {
    var w = town.map[0].length, h = town.map.length;
    var raw = atob(value);
    for (var i = 0; i < w * h; i++) {
      if (!(raw.charCodeAt(i >> 3) & (1 << (7 - (i & 7))))) continue;
      explored[(i % w) + ',' + ((i / w) | 0)] = 1;
    }
  }
  // A generated floor has no baked region and no fog key of its own: its
  // explored tiles are one field of the floor's delta record, so the cap
  // on remembered floors bounds the memory as well as the map.
  function descentFog() {
    return !!(window.VEFR_DESCENT && window.VEFR_DESCENT.isGenerated(regionName));
  }
  function loadFog() {
    explored = {};
    if (descentFog()) {
      var packedFloor = window.VEFR_DESCENT.loadFog();
      if (packedFloor) {
        try { decodeFog(packedFloor); } catch (e) { /* unreadable: start dark */ }
      }
      return;
    }
    var packed = store.get(fog2Key());
    if (packed) {
      try { decodeFog(packed); } catch (e) { /* unreadable memory: start dark */ }
      return;
    }
    // The old era's JSON array: read it either way, because fog off may
    // not write but must not forget. The move to the bitset happens on
    // the first save, which also drops the old key.
    var old = store.getJSON(fogKey(), null);
    if (!Array.isArray(old)) return;
    old.forEach(function (k) { explored[k] = 1; });
    if (fogOn) saveFog();
  }
  function saveFog() {
    if (!fogOn) return false;   // fog off, or no fog here: write nothing
    if (descentFog()) {
      try { window.VEFR_DESCENT.saveFog(encodeFog()); }
      catch (e) { return false; }
      return true;
    }
    var value;
    // Encode first: a failure must leave the store untouched.
    try { value = encodeFog(); } catch (e) { return false; }
    store.set(fog2Key(), value);
    // Drop the old array only once the bitset is really there: store.set
    // swallows a failed write (quota, sandbox), and then the old key is
    // all the memory there is.
    if (store.get(fog2Key()) === value) store.remove(fogKey());
    return true;
  }
  // What the lit area is drawn as, and the shape a floor whose `fog`
  // block names no shape is drawn as: the circle every floor has always
  // drawn, so a pack written before the key plays exactly as it did.
  var DEFAULT_FOG_SHAPE = 'circle';
  // Read at call time rather than held beside `fogRadius`: the radius is
  // reset on entering a region, and a second value to remember to reset
  // is a second way to leave one behind.
  function fogShape() {
    return (town.fog && town.fog.shape === 'square') ? 'square'
                                                      : DEFAULT_FOG_SHAPE;
  }
  function litNow() {
    var out = {};
    if (!fogOn) return out;
    // Both shapes are written over the same square of tiles: `fogRadius`
    // steps out on each axis is the whole of either one, so the loop is
    // the shape's bounding box and the test below decides the corners.
    var square = fogShape() === 'square';
    for (var y = hero[1] - fogRadius; y <= hero[1] + fogRadius; y++) {
      for (var x = hero[0] - fogRadius; x <= hero[0] + fogRadius; x++) {
        if (x < 0 || y < 0 || y >= town.map.length || x >= town.map[0].length) continue;
        var dx = x - hero[0], dy = y - hero[1];
        // A circle counts the tiles within `fogRadius` steps by straight
        // line; a square counts the tiles within `fogRadius` steps on
        // each axis, so it holds every tile the circle holds and its
        // corners reach sqrt(2) further out.
        var lit = square
          ? Math.max(Math.abs(dx), Math.abs(dy)) <= fogRadius
          : dx * dx + dy * dy <= fogRadius * fogRadius;
        if (lit) out[x + ',' + y] = 1;
      }
    }
    return out;
  }
  function seeNow() {
    var lit = litNow();
    var changed = false;
    Object.keys(lit).forEach(function (k) {
      if (!explored[k]) { explored[k] = 1; changed = true; }
    });
    if (changed) saveFog();
    return lit;
  }
  function hideUnseen(x, y) {
    return fogOn && !explored[x + ',' + y];
  }

