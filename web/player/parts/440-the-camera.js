  // ---- the camera ----
  // A map smaller than the screen is scaled to fit and centred. A bigger
  // map scrolls with the hero at a readable size, so a large floor (or a
  // small room) never shrinks to a thumbnail. `cols`/`rows` are the current
  // region's size, recomputed on every resize so a door can swap the map.
  var cols = 0, rows = 0;
  var T = town.tile, viewW = 0, viewH = 0;
  var MIN_FIT_TILE = 16;   // below this, scroll at a readable size instead
  var HUD_BAND = 72;       // room the HUD frame needs above and below a whole dark map
  // The room a whole lit map leaves above and below itself, taken back as stage, so the HUD
  // pieces that hang off the stage's corners stand on spare room and not on its corner tiles
  // (issue #424). Its depth is the deepest of those pieces: the Messages button starts 64 px
  // down and is 44 px tall.
  var HUD_BAND_LIT = 112;
  // A whole lit map drawn smaller to leave those bands would also narrow its stage, and a
  // narrow stage wraps the HUD's top row onto the Messages button and the fight verbs onto
  // the action row. Such a stage keeps at least this width, centred on the map.
  var HUD_STAGE_MIN_W = 800;
  var MIN_STAGE_W = 420, MIN_STAGE_H = 360;  // enough for the HUD frame's corners
  // The phone camera needs the pack's display.phone_tile; see docs/guides/world-creation.md.
  var PHONE_TILE = (window.VEFR_WORLD.display || {}).phone_tile || 0;
  var PHONE_MIN_FIT = 36, PHONE_MARGIN = 3;
  var onPhone = false;
  var cameraAt = { x: 0, y: 0 };
  function phoneCamera() {
    if (!PHONE_TILE) return false;
    var q = window.location.search;
    if (/[?&]camera=desk\b/.test(q)) return false;
    if (/[?&]camera=phone\b/.test(q)) return true;
    return !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
  }
  // Pixel art (`display.pixel_art` in world.json): every picture is drawn at a whole-number
  // scale of the art's native tile, with no smoothing. A pack without it draws exactly as before.
  var pixelNative = (world.display && world.display.pixel_art
                     && world.display.pixel_art.native_tile) || 0;
  var pixelK = 1;   // one art pixel is pixelK / dpr CSS px
  if (pixelNative) document.body.classList.add('vefr-pixel');
  function pxRatio() { return window.devicePixelRatio || 1; }
  function snapPx(v) {
    if (!pixelNative) return v;
    var d = pxRatio();
    return Math.round(v * d) / d;
  }
  // The span an art picture covers along one axis, as [start, length] on whole device pixels.
  function snapSpan(at, size) {
    if (!pixelNative) return [at, size];
    var a = snapPx(at);
    return [a, snapPx(at + size) - a];
  }
  // A picture's drawn size in CSS px: its own art pixels at the snapped scale, else heightCss
  // tall at its own aspect.
  function artSize(natW, natH, heightCss) {
    if (pixelNative) return { w: natW * pixelK / pxRatio(), h: natH * pixelK / pxRatio() };
    return { w: heightCss * (natW / natH || 1), h: heightCss };
  }
  // The tile as k whole art pixels of device pixels. A whole map that fits rounds k down so it
  // still fits; any other map rounds to the nearest.
  function snapTile(wanted) {
    var d = pxRatio();
    var fits = cols * wanted <= viewW && rows * wanted <= viewH;
    var k = wanted * d / pixelNative;
    pixelK = Math.max(1, fits ? Math.floor(k) : Math.round(k));
    return pixelK * pixelNative / d;
  }
  function fitZoom() {
    if (onPhone) {
      var phoneFit = Math.min(viewW / (cols * town.tile), viewH / (rows * town.tile), 3);
      return phoneFit * town.tile >= PHONE_MIN_FIT ? phoneFit : PHONE_TILE / town.tile;
    }
    // The HUD sits in the stage's corners, so a whole map must leave a band
    // above and below for it; otherwise it reads whole and still reaches
    // under the buttons.
    var fitW = viewW / (cols * town.tile);
    var dock = window.innerWidth <= 600 && window.innerHeight > window.innerWidth;
    if (fogOn) {
      // A dark map is read up close. A map small enough to read whole at
      // 32 px shrinks into the HUD's band (and letterboxes on the dock),
      // exactly as before, so no HUD piece ever covers one of its tiles. A
      // bigger map scrolls, and there the tile is as big as the lit circle
      // lets fit the window's height, 32 to 48 px: the HUD sits in the dark
      // corners outside the circle. Sight 8 at 720 px is 42 px, where a
      // fixed 32 left the hero a speck (Cottage walk, 2026-10-12).
      var z = 32 / town.tile;
      var fitH = Math.max(viewH - 2 * HUD_BAND, 1) / (rows * town.tile);
      var whole = cols * town.tile * z <= viewW && rows * town.tile * z <= viewH;
      if (dock || whole) return Math.min(z, fitW, fitH);
      var lit = 2 * fogRadius + 1;
      var px = Math.floor(Math.max(viewH, 1) / lit);
      return Math.max(32, Math.min(48, px)) / town.tile;
    }
    // A lit map that reads whole leaves both bands clear: it takes a smaller tile until it
    // does, and a map that cannot do that at a readable tile scrolls instead (issue #424).
    // The dock letterboxes its map with its own spare room, so it keeps the fit that fills
    // the canvas.
    var fitH = dock ? viewH : Math.max(viewH - 2 * HUD_BAND_LIT, 1);
    var fit = Math.min(fitW, fitH / (rows * town.tile));
    if (fit * town.tile >= MIN_FIT_TILE) return Math.min(fit, 3);  // the whole map reads
    return 32 / town.tile;   // a big map: scroll at a comfortable tile
  }
  // The drawn map's rectangle, in viewport CSS pixels, published for the
  // in-world interface (docs/plans/interface/PLAN.md). `window.VEFR_STAGE`
  // is read by the browser contract; the `--stage-*` properties place
  // `.hud-frame`, a child of #stage, so they carry #stage's own offset
  // subtracted out. Published after every resize, which is where a window
  // resize, a door's region swap and the fog toggle's zoom change all meet.
  //
  // On a narrow portrait window (`stage--dock`) the map is letterboxed
  // with spare room above and below, so the stage grows to the whole
  // window and `VEFR_STAGE.map` keeps the drawn map inside it; the dock
  // CSS places the HUD, d-pad and action row in that spare room. A map
  // smaller than the stage's minimum would leave the HUD frame's corners
  // on map tiles, so the stage grows to the window there too and the map
  // is centred inside it, clear of every corner; a map big enough for
  // its frame keeps the map rectangle as the stage, except that a whole
  // lit map's stage also takes the HUD bands above and below it (and at
  // least HUD_STAGE_MIN_W of width), issue #424. The `--map-*`
  // properties are the map inside #stage, using the same #stage-relative
  // convention as the `--stage-*` ones.
  function publishStage() {
    var mapW = cols * T, mapH = rows * T;
    var rect = canvas.getBoundingClientRect();
    var mx, my, mw, mh;
    if (mapW <= viewW && mapH <= viewH) {
      // The whole map reads: it is centred on the canvas.
      mx = rect.left + (viewW - mapW) / 2;
      my = rect.top + (viewH - mapH) / 2;
      mw = mapW;
      mh = mapH;
    } else {
      // It scrolls past the window edges: the canvas, clipped to the window.
      mx = Math.max(0, rect.left);
      my = Math.max(0, rect.top);
      mw = Math.min(rect.right, window.innerWidth) - mx;
      mh = Math.min(rect.bottom, window.innerHeight) - my;
    }
    // A phone held upright: width <= 600 and taller than it is wide. The
    // stage is the window; the map stays the drawn rectangle inside it.
    var dock = window.innerWidth <= 600 && window.innerHeight > window.innerWidth && !onPhone;
    // A map too small for the HUD frame's corners gets the window as its
    // stage as well, so those corners fall on the spare room, not the map.
    var grow = dock || mw < MIN_STAGE_W || mh < MIN_STAGE_H;
    // A whole lit map left a band above and below itself (fitZoom); the stage takes it back,
    // so the HUD pieces that hang off its corners stand there and not on corner tiles
    // (issue #424). A dark map, a scrolling one and the phone camera keep the map rectangle.
    var band = (!fogOn && !onPhone && mapW <= viewW && mapH <= viewH)
      ? Math.max(0, Math.min(HUD_BAND_LIT, my - rect.top, rect.bottom - (my + mh))) : 0;
    var sw = band ? Math.min(Math.max(mw, HUD_STAGE_MIN_W), rect.width) : mw;
    var sx = band ? Math.max(rect.left, Math.min(mx - (sw - mw) / 2, rect.right - sw)) : mx;
    var x = grow ? 0 : sx, y = grow ? 0 : my - band;
    var w = grow ? window.innerWidth : sw, h = grow ? window.innerHeight : mh + 2 * band;
    window.VEFR_STAGE = {
      x: x, y: y, w: w, h: h,
      map: { x: mx, y: my, w: mw, h: mh },
      tile: T,   // the drawn tile, CSS px (read by tests/browser/test_camera_zoom.py)
      phone: onPhone   // the phone camera is on: the map fills the window, so a
                       // HUD corner panel has no room outside it (issue #430).
                       // Read by the messages panel, which folds itself here.
    };
    if (pixelNative) window.VEFR_STAGE.pixel = { native: pixelNative, k: pixelK };
    var stage = document.getElementById('stage');
    if (stage) {
      var box = stage.getBoundingClientRect();
      stage.style.setProperty('--stage-x', (x - box.left) + 'px');
      stage.style.setProperty('--stage-y', (y - box.top) + 'px');
      stage.style.setProperty('--stage-w', w + 'px');
      stage.style.setProperty('--stage-h', h + 'px');
      stage.style.setProperty('--map-x', (mx - box.left) + 'px');
      stage.style.setProperty('--map-y', (my - box.top) + 'px');
      stage.style.setProperty('--map-w', mw + 'px');
      stage.style.setProperty('--map-h', mh + 'px');
      if (dock) stage.classList.add('stage--dock');
      else stage.classList.remove('stage--dock');
    }
  }
  // The ground outside the drawn map (docs/plans/interface/PLAN.md, slice 2).
  // Today that ground is one flat colour, and a skin with a `backdrop` puts
  // its own seamless picture there instead. These are the rectangles the map
  // does NOT cover, clipped to the window, in view pixels: pure maths, with
  // `ready` saying whether the picture has decoded, and exposed read-only
  // (precedent: window.VEFR_STAGE) so a test can read them without a canvas.
  // A map that fills the window has no ground, so it returns no rectangles.
  window.VEFR_BACKDROP_BANDS = function (ready, viewW, viewH, camX, camY, mapW, mapH) {
    if (!ready) return [];
    // `camX`/`camY` are the camera's offsets, as draw() has them: the map's
    // own top-left on screen is -camX, -camY (it is negative when a map
    // smaller than the window is centred).
    var x0 = Math.max(0, -camX), y0 = Math.max(0, -camY);
    var x1 = Math.min(viewW, -camX + mapW), y1 = Math.min(viewH, -camY + mapH);
    if (x1 <= x0 || y1 <= y0) return [];
    var out = [];
    if (y0 > 0) out.push([0, 0, viewW, y0]);
    if (y1 < viewH) out.push([0, y1, viewW, viewH - y1]);
    if (x0 > 0) out.push([0, y0, x0, y1 - y0]);
    if (x1 < viewW) out.push([x1, y0, viewW - x1, y1 - y0]);
    return out;
  };
  var backdropBands = [], backdropDrawn = 0;
  // The skin's picture, or nothing. A pack with no skin never paints a table:
  // the picture only ever arrives through applySkin, and only for a skin that
  // named one.
  function skinBackdrop() {
    var skin = window.VEFR_SKIN;
    return (skin && typeof skin === 'object') ? (window.VEFR_BACKDROP || null) : null;
  }
  window.VEFR_BACKDROP_STATE = function () {
    return { url: window.VEFR_BACKDROP_URL || null, ready: !!skinBackdrop(),
             bands: backdropBands, drawn: backdropDrawn };
  };
  // Repaint the map on demand, for the parts outside this closure that have
  // something new to draw (the skin's backdrop, once its picture has decoded).
  // Precedent: window.refreshCombatSnapshot.
  window.VEFR_REDRAW = function () { draw(); };
  // The camera's offset as the last draw() placed it, read-only.
  window.VEFR_CAMERA = function () { return { x: cameraAt.x, y: cameraAt.y }; };
  function resize() {
    cols = town.map[0].length;
    rows = town.map.length;
    var dpr = window.devicePixelRatio || 1;
    viewW = canvas.clientWidth || window.innerWidth;
    viewH = canvas.clientHeight || window.innerHeight;
    canvas.width = Math.round(viewW * dpr);
    canvas.height = Math.round(viewH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    onPhone = phoneCamera();
    if (pixelNative) ctx.imageSmoothingEnabled = false;   // a canvas resize resets this
    T = town.tile * fitZoom();
    if (pixelNative) T = snapTile(T);
    publishStage();
  }
  window.addEventListener('resize', function () { resize(); draw(); });

  // The ground tiles, preloaded from data URIs (instant); the map is
  // redrawn once they decode. Tiles travel with the region: two regions
  // can use the same symbol for different ground. A symbol with no tile
  // falls back to its base colour.
  // -- pickVariant start --
  // The variant choice is a pure hash of the tile's own map coordinates:
  // the same cell always draws the same picture, so the woven world is
  // stable from visit to visit. A symbol with one picture always picks
  // index 0, exactly as it drew before variants existed. The multiply
  // and the final cast are unsigned 32-bit so JavaScript and the Python
  // mirror in tests/ agree on every cell.
  window.pickVariant = function (x, y, n) {
    var h = (Math.imul(x, 73856093) ^ Math.imul(y, 19349663)) >>> 0;
    return n > 0 ? h % n : 0;
  };
  // -- pickVariant end --
  // -- pickCell start --
  // A GRID tile is one picture drawn as cols x rows cells. The cell is chosen by position, not by
  // hash: cell (x mod cols, y mod rows), so a floor painted as one scene reads as one scene and
  // repeats only every cols tiles. The double modulo keeps a negative coordinate in range.
  window.pickCell = function (x, y, cols, rows) {
    return [((x % cols) + cols) % cols, ((y % rows) + rows) % rows];
  };
  // -- pickCell end --
