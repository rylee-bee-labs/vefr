  // ---- lamplight: per-pixel light over the drawn map ----
  // The pack's optional `light` block (src/vefr/world.py, LIGHT; docs/guides/world-creation.md, "Lamplight"), drawn
  // by the light rig (035-lightrig.html) on a WebGL2 canvas laid over the town canvas, after every draw() (the afterDraw
  // hook in 480). The drawn map is the ground plane's paint, with the tiles' normal maps for relief; the tiles that
  // stand up are planes one height up, cut from the same drawn pixels, and they cast shadows. With no `light` block,
  // no WebGL2, a lost context, the Display switch off, or a phase the pack does not darken, the light canvas is hidden
  // or gone and the map shows exactly as it does without it.
  (function () {
    var spec = window.VEFR_WORLD && window.VEFR_WORLD.light;
    if (!spec || typeof spec !== 'object' || Array.isArray(spec)) return;
    if (/[?&]lamplight=off\b/.test(window.location.search)) return;
    if (typeof createLightRig !== 'function') return;   // its own script (035) did not load in this browser
    var KEY = 'vefr-lamplight-' + (window.VEFR_WORLD.name || 'world');
    var FLAT = 'rgb(128,128,255)';   // a normal map's "facing straight up": no relief
    var HERO = { reach: 1.5, height: 1.3, intensity: 2, color: '#ffd694' };
    var LAMP = { reach: 2.4, height: 2.2, intensity: 2.4, color: '#ffdb99' };
    var SCALE_MAX = 1.5;   // the light's pixels per CSS pixel, at most: the phone test held 60 fps at 1.5
    var glc = document.createElement('canvas');
    glc.id = 'lamp-canvas';
    glc.setAttribute('aria-hidden', 'true');
    glc.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:none;pointer-events:none';
    canvas.parentNode.insertBefore(glc, canvas.nextSibling);
    var rig = null, lost = false, row = null;
    // The light is gone for this page (the context was lost, or lighting failed): its canvas and its switch go, and
    // the map draws as it does without lamplight.
    function stop() {
      lost = true;
      rig = null;
      glc.remove();
      if (row) row.remove();
    }
    try {
      rig = createLightRig(glc, { maxLights: 4, maxCasters: 3, onLost: stop });
    } catch (e) {   // no WebGL2, or a context that cannot run the rig: the map stays as it is
      glc.remove();
      return;
    }
    var on = store.get(KEY) !== 'off';
    var heights = [];   // the distinct standing heights, low to high: one caster plane each
    Object.keys(spec.stand || {}).forEach(function (name) {
      var h = spec.stand[name];
      if (typeof h === 'number' && heights.indexOf(h) < 0) heights.push(h);
    });
    heights.sort(function (a, b) { return a - b; }).splice(3);

    function hexRgb(h, fallback) {
      var m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(h || '');
      return m ? [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255] : fallback;
    }
    // The darkness now: one colour for every phase, or the phase's own; null when this phase is not darkened.
    function ambient() {
      var a = spec.ambient;
      if (typeof a === 'string') return hexRgb(a, null);
      return a && typeof a === 'object' && a[phase()] ? hexRgb(a[phase()], null) : null;
    }
    function layer() { var c = document.createElement('canvas'); return { c: c, x: c.getContext('2d') }; }
    function size(L, w, h) {
      if (L.c.width !== w || L.c.height !== h) { L.c.width = w; L.c.height = h; }
      L.x.setTransform(1, 0, 0, 1, 0, 0);
      L.x.clearRect(0, 0, w, h);
      L.x.imageSmoothingEnabled = !pixelNative;
    }
    var relief = layer();                                     // the ground's normals, the whole view
    var stands = heights.map(function () { return { paint: layer(), relief: layer() }; });

    // The region's normal maps, as the weave baked them by symbol (the tile's own shape).
    var normals = {}, normalsFor = null;
    function picture(src) {
      var im = new Image();
      im.onload = function () { draw(); };
      im.src = src;
      return im;
    }
    function loadNormals() {
      normalsFor = regionName;
      normals = {};
      var table = (window.VEFR_TILE_NORMALS || {})[regionName] || {};
      Object.keys(table).forEach(function (ch) {
        var v = table[ch];
        if (typeof v === 'string') normals[ch] = { imgs: [picture(v)] };
        else if (Array.isArray(v)) normals[ch] = { imgs: v.map(picture) };
        else if (v && v.src) normals[ch] = { grid: { img: picture(v.src), cols: v.cols, rows: v.rows } };
      });
    }
    function ready(im) { return !!(im && im.complete && im.naturalWidth > 0); }
    // One tile's normal map onto a layer, at device pixels: the same variant or grid cell draw() chose for the tile.
    function paintNormal(L, ch, x, y, px, py, s) {
      var n = normals[ch];
      if (!n) return;
      if (n.grid) {
        if (!ready(n.grid.img)) return;
        var cell = pickCell(x, y, n.grid.cols, n.grid.rows);
        var cw = n.grid.img.naturalWidth / n.grid.cols, chh = n.grid.img.naturalHeight / n.grid.rows;
        L.x.drawImage(n.grid.img, cell[0] * cw, cell[1] * chh, cw, chh, px, py, s, s);
        return;
      }
      var count = (tileImgs[ch] && tileImgs[ch].length) || n.imgs.length;
      var im = n.imgs[pickVariant(x, y, count)];
      if (ready(im)) L.x.drawImage(im, px, py, s, s);
    }

    var planesFor = '', found = [];
    function world(bb, dpr) {   // a device-pixel box back to map pixels, for a plane's rect
      return [cameraAt.x + bb[0] / dpr, cameraAt.y + bb[1] / dpr,
              Math.max(1, bb[2] - bb[0]) / dpr, Math.max(1, bb[3] - bb[1]) / dpr];
    }
    // After each draw(): repaint the planes from what draw() just put on the canvas, then light them. Anything that
    // fails in here (a canvas too big for this GPU, a picture the browser will not hand to WebGL) stops lamplight for
    // the page rather than draw(), whose callers still have work to do after it.
    function sync() {
      if (!rig) return;
      try {
        light();
      } catch (e) {
        stop();
        if (window.console) console.warn('lamplight stopped: ' + (e && e.message));
      }
    }
    function light() {
      var dark = on ? ambient() : null;
      glc.style.display = dark ? 'block' : 'none';
      if (!dark) return;
      if (normalsFor !== regionName) loadNormals();
      var dpr = window.devicePixelRatio || 1, W = canvas.width, H = canvas.height, s = T * dpr;
      var gw = Math.round(viewW * scale()), gh = Math.round(viewH * scale());
      if (glc.width !== gw || glc.height !== gh) { glc.width = gw; glc.height = gh; }
      size(relief, W, H);
      relief.x.fillStyle = FLAT;
      relief.x.fillRect(0, 0, W, H);
      var standAt = (window.VEFR_LIGHT_STAND || {})[regionName] || {};
      found = heights.map(function () { return { tiles: [], bb: [W, H, 0, 0] }; });
      var x0 = Math.max(0, Math.floor(cameraAt.x / T)), x1 = Math.min(cols - 1, Math.ceil((cameraAt.x + viewW) / T));
      var y0 = Math.max(0, Math.floor(cameraAt.y / T)), y1 = Math.min(rows - 1, Math.ceil((cameraAt.y + viewH) / T));
      for (var y = y0; y <= y1; y++) {
        for (var x = x0; x <= x1; x++) {
          if (hideUnseen(x, y)) continue;
          var ch = town.map[y][x];
          var px = Math.round((x * T - cameraAt.x) * dpr), py = Math.round((y * T - cameraAt.y) * dpr);
          paintNormal(relief, ch, x, y, px, py, s);
          var k = heights.indexOf(standAt[ch]);
          if (k < 0) continue;
          var f = found[k];
          f.tiles.push([px, py]);
          f.bb = [Math.min(f.bb[0], px), Math.min(f.bb[1], py), Math.max(f.bb[2], px + s), Math.max(f.bb[3], py + s)];
        }
      }
      // Each height's standing tiles: the drawn map's own pixels where they stand, and their normals.
      found.forEach(function (f, k) {
        var st = stands[k], bb = f.bb, w = Math.max(1, bb[2] - bb[0]), h = Math.max(1, bb[3] - bb[1]);
        size(st.paint, w, h);
        size(st.relief, w, h);
        if (!f.tiles.length) return;
        st.paint.x.drawImage(canvas, -bb[0], -bb[1]);
        // Keep the drawn pixels only where these tiles stand: ONE fill of every tile's square, because each fill in
        // destination-in also clears everything outside its own shape.
        st.paint.x.globalCompositeOperation = 'destination-in';
        st.paint.x.fillStyle = '#000';
        st.paint.x.beginPath();
        f.tiles.forEach(function (t) { st.paint.x.rect(t[0] - bb[0], t[1] - bb[1], s, s); });
        st.paint.x.fill();
        st.paint.x.globalCompositeOperation = 'source-over';
        st.relief.x.drawImage(relief.c, -bb[0], -bb[1]);
      });
      var view = [cameraAt.x, cameraAt.y, viewW, viewH];
      var key = regionName + ' ' + W + 'x' + H + ' ' + T;
      if (planesFor !== key) {
        rig.setPlanes([{ albedo: canvas, normal: relief.c, rect: view, z: 0, mips: false, nearest: !!pixelNative }]
          .concat(heights.map(function (h, k) {
            return { albedo: stands[k].paint.c, normal: stands[k].relief.c, rect: world(found[k].bb, dpr), z: h * T,
                     casts: 0.9, thickness: h * T, mips: false, nearest: !!pixelNative };
          })));
        planesFor = key;
      }
      rig.updatePlane(0, { albedo: canvas, normal: relief.c, rect: view });
      found.forEach(function (f, k) {   // a height with nothing standing on screen sends no pictures at all
        rig.updatePlane(k + 1, f.tiles.length ? { albedo: stands[k].paint.c, normal: stands[k].relief.c,
                                                  rect: world(f.bb, dpr), hidden: false } : { hidden: true });
      });
      frame();
      schedule();
    }

    // The lights: the hero's own, then the region's lamps that shine now (no flag, or its flag set) and are not
    // hidden in the dark, nearest the hero first; four at most, the light rig's limit.
    function lights(t) {
      var still = reducedMotion(), out = [];
      var flick = function (seed) {
        return still ? 1 : 1 + 0.07 * Math.sin(t * 0.0071 + seed) * Math.sin(t * 0.0113 + seed * 2)
          + 0.03 * Math.sin(t * 0.031 + seed);
      };
      // glow: the soft disc around the flame itself, [strength, radius in tiles].
      function light(d, at, seed, glow) {
        var c = hexRgb(d.color, [1, 0.85, 0.6]);
        return { x: at[0] * T, y: at[1] * T, z: d.height * T, intensity: d.intensity * flick(seed),
                 reach: d.reach * T, size: T * 0.3, color: c, edge: [c[0], c[1] * 0.65, c[2] * 0.45],
                 glow: glow[0], glowRadius: T * glow[1] };
      }
      var me = heroPose().tile;
      if (spec.hero && typeof spec.hero === 'object') {
        // Held beside the hero, as a lantern in hand, with a small glow: a light on the hero's own tile washes their
        // picture out to white.
        out.push(light(Object.assign({}, HERO, spec.hero), [me[0] + 0.62, me[1] + 0.55], 1, [0.5, 0.8]));
      }
      var lamps = ((spec.lamps || {})[regionName] || []).filter(function (l) {
        return Array.isArray(l.at) && !hideUnseen(l.at[0], l.at[1]) && (!l.flag || ruleFlagOn(l.flag));
      });
      lamps.sort(function (a, b) {
        return (Math.abs(a.at[0] - me[0]) + Math.abs(a.at[1] - me[1]))
          - (Math.abs(b.at[0] - me[0]) + Math.abs(b.at[1] - me[1]));
      });
      lamps.slice(0, 4 - out.length).forEach(function (l) {
        out.push(light(Object.assign({}, LAMP, l), [l.at[0] + 0.5, l.at[1] + 0.5], l.at[0] * 7 + l.at[1], [0.9, 1.4]));
      });
      return out;
    }
    function scale() { return Math.min(window.devicePixelRatio || 1, SCALE_MAX); }
    var lastLights = [];
    function frame() {
      var dark = rig && on ? ambient() : null;
      if (!dark) return;
      lastLights = lights(performance.now());
      rig.render({ camera: { x: cameraAt.x + viewW / 2, y: cameraAt.y + viewH / 2, zoom: scale() },
                   lights: lastLights, ambient: dark, clear: hexRgb(town.bg, [0.02, 0.03, 0.04]) });
    }
    // The flame's flicker redraws the light alone, 30 times a second, while motion is allowed and the page is seen.
    // With reduced motion nothing moves: the light is drawn once per draw().
    var raf = 0, lastTick = 0;
    function schedule() {
      if (!raf && rig && on && !document.hidden && !reducedMotion()) raf = requestAnimationFrame(tick);
    }
    function tick(t) {
      raf = 0;
      if (!rig || !on || document.hidden || reducedMotion() || !ambient()) return;
      if (t - lastTick >= 32) {
        lastTick = t;
        try { frame(); } catch (e) { stop(); return; }
      }
      raf = requestAnimationFrame(tick);
    }
    document.addEventListener('visibilitychange', schedule);

    // Display > Lamplight: built only when the light can run, so a pack without it, or a browser without WebGL2,
    // has no switch to find. A real checkbox on a 44px row, like Sound's.
    var panel = document.querySelector('[data-panel-body="display"]');
    if (panel) {
      row = document.createElement('p');
      row.className = 'sound-row';
      var label = document.createElement('label');
      var box = document.createElement('input');
      box.type = 'checkbox';
      box.id = 'lamplight-toggle';
      box.checked = on;
      box.addEventListener('change', function () {
        on = box.checked;
        store.set(KEY, on ? 'on' : 'off');
        draw();
      });
      label.appendChild(box);
      label.appendChild(document.createTextNode(' Lamplight'));
      row.appendChild(label);
      var subhead = null;
      for (var i = 0; i < panel.children.length; i++) {
        if (panel.children[i].matches('h2.menu-sub')) { subhead = panel.children[i]; break; }
      }
      panel.insertBefore(row, subhead);
    }

    // For tests and the curious, read-only: whether the light shows, the lights of the last frame, the plane count,
    // whether the context was lost, whether the flicker runs, and a tile's middle in the canvas's own pixels.
    window.VEFR_LAMPLIGHT = {
      on: function () { return !!rig && on && !!ambient(); },
      lights: function () { frame(); return lastLights.slice(); },
      planes: function () { return 1 + heights.length; },
      lost: function () { return lost; },
      standing: function () {
        return found.map(function (f, k) {
          var c = stands[k].paint.c, d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data, n = 0;
          for (var i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
          return { tiles: f.tiles.length, opaque: n, size: T * (window.devicePixelRatio || 1) };
        });
      },
      looping: function () { return !!raf; },
      px: function (x, y) {
        var dpr = window.devicePixelRatio || 1;
        return [Math.floor(((x + 0.5) * T - cameraAt.x) * dpr), Math.floor(((y + 0.5) * T - cameraAt.y) * dpr)];
      }
    };
    afterDraw.push(sync);
  })();
