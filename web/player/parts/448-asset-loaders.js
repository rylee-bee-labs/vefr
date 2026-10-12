  var regionTiles = window.VEFR_REGION_TILES || {};
  // A symbol maps to either one data-URI string (one picture) or a list
  // of data-URI strings in variant order. The loader normalizes both to
  // a list of preloaded Images; the draw loop then asks for one image.
  var tileImgs = {};
  var tileGrids = {};   // symbol -> { img, cols, rows } for a grid picture
  // symbol -> the 4 x 4 edges sheet a legend entry's `edges` names, per region. Empty for a pack that
  // names none, so the ground draws exactly as it did before edges existed.
  var regionEdges = window.VEFR_TILE_EDGES || {};
  var edgeImgs = {};
  function loadTiles() {
    var set = regionTiles[regionName] || window.VEFR_TILES || {};
    tileImgs = {};
    tileGrids = {};
    edgeImgs = {};
    var edges = regionEdges[regionName] || {};
    Object.keys(edges).forEach(function (ch) {
      if (typeof edges[ch] !== 'string') return;
      var eim = new Image();
      eim.onload = function () { draw(); };
      eim.src = edges[ch];
      edgeImgs[ch] = eim;
    });
    Object.keys(set).forEach(function (ch) {
      var srcs = set[ch];
      if (srcs && typeof srcs === 'object' && !Array.isArray(srcs)) {
        // { src, cols, rows }: one picture drawn as a block of cells
        var cols = srcs.cols | 0, rows = srcs.rows | 0;
        if (typeof srcs.src !== 'string' || cols < 1 || rows < 1) return;
        var gim = new Image();
        gim.onload = function () { draw(); };
        gim.src = srcs.src;
        tileGrids[ch] = { img: gim, cols: cols, rows: rows };
        return;
      }
      if (typeof srcs === 'string') srcs = [srcs];
      if (!Array.isArray(srcs)) return;
      tileImgs[ch] = srcs.map(function (src) {
        var im = new Image();
        im.onload = function () { draw(); };
        im.src = src;
        return im;
      });
    });
  }
  loadTiles();

  // The character sprites, preloaded the same way. A character with no
  // sprite keeps the drawn figure (a body and a head, or the hero's dot).
  var sprites = window.VEFR_SPRITES || {};
  var spriteImgs = {};
  Object.keys(sprites).forEach(function (key) {
    var im = new Image();
    im.onload = function () { draw(); };
    im.src = sprites[key];
    spriteImgs[key] = im;
  });

  // The optional walk sheets, preloaded the same way: a sprite that has
  // one walks through its frames instead of sliding its single picture.
  // Empty for a pack with no sheets, so the drawing below is unchanged.
  var spriteSheets = window.VEFR_SPRITE_SHEETS || {};
  var spriteSheetImgs = {};
  Object.keys(spriteSheets).forEach(function (key) {
    var im = new Image();
    im.onload = function () { draw(); };
    im.src = spriteSheets[key].image;
    spriteSheetImgs[key] = im;
  });
  // A sheet is drawable only when its shape is complete: the validator
  // reports a bad one, this just keeps a stray bake from crashing play.
  function sheetUsable(sheet) {
    return !!(sheet && Array.isArray(sheet.frame) && sheet.frame.length === 2
      && sheet.frame[0] > 0 && sheet.frame[1] > 0 && sheet.directions);
  }
  var heroHasSheet = sheetUsable(spriteSheets.hero);
  function spriteSheetReady(key) {
    var im = spriteSheetImgs[key];
    return !!(im && im.complete && im.naturalWidth > 0);
  }

  // The door picture, preloaded like the rest. A door is a transition
  // tile; drawing it shows a way out instead of an invisible hole.
  var doorSrc = window.VEFR_DOOR || '';
  var doorImg = null;
  if (doorSrc) {
    doorImg = new Image();
    doorImg.onload = function () { draw(); };
    doorImg.src = doorSrc;
  }
  function doorReady() {
    return doorImg && doorImg.complete && doorImg.naturalWidth > 0;
  }

  // A pack's way pictures, preloaded the same way, keyed by their source.
  var wayImgs = {};
  function preloadWay(src) {
    if (!src || wayImgs[src]) return;
    var im = new Image();
    im.onload = function () { draw(); };
    im.src = src;
    wayImgs[src] = im;
  }
  Object.keys(window.VEFR_WAY_ICONS || {}).forEach(function (kind) {
    preloadWay(window.VEFR_WAY_ICONS[kind]);
  });
  Object.keys(window.VEFR_REGION_WAY_ICONS || {}).forEach(function (region) {
    var pics = window.VEFR_REGION_WAY_ICONS[region];
    Object.keys(pics).forEach(function (kind) { preloadWay(pics[kind]); });
  });
  function wayReady(src) {
    var im = wayImgs[src];
    return !!(im && im.complete && im.naturalWidth > 0);
  }

  // The book markers, preloaded like the rest. A book with no marker is
  // invisible: a map book is a tile you step on, a gifted one is a line
  // of text. Draw where one can still be found.
  var bookIconSrc = window.VEFR_BOOK_ICONS || {};
  var bookIconImgs = {};
  Object.keys(bookIconSrc).forEach(function (kind) {
    var im = new Image();
    im.onload = function () { draw(); };
    im.src = bookIconSrc[kind];
    bookIconImgs[kind] = im;
  });
  function bookIconReady(kind) {
    var im = bookIconImgs[kind];
    return im && im.complete && im.naturalWidth > 0;
  }

  // The chest picture, preloaded like the rest.
  var chestSrc = window.VEFR_CHEST_ICON || '';
  var chestImg = null;
  if (chestSrc) {
    chestImg = new Image();
    chestImg.onload = function () { draw(); };
    chestImg.src = chestSrc;
  }
  function chestReady() {
    return chestImg && chestImg.complete && chestImg.naturalWidth > 0;
  }

