  // ---- things on the map (props) ----
  // A region may list `props`: a picture on the ground with a footprint
  // that blocks walking (`block` rows of '#' blocked and '.' open, every
  // cell blocked when it names none) and a strip of `frames` equal frames
  // played at `fps`. Props stand in the depth order with the characters.
  var PROP_FPS = 4;
  var propsFor = null;     // the town the cache below was read from
  var propList = [];
  var propCells = {};      // 'x,y' -> true for every blocked footprint cell
  function readProps() {
    if (propsFor === town) return;
    propsFor = town;
    propList = [];
    propCells = {};
    (Array.isArray(town.props) ? town.props : []).forEach(function (p) {
      if (!p || typeof p.pic !== 'string' || !Array.isArray(p.at)) return;
      var size = Array.isArray(p.size) ? p.size : [1, 1];
      var w = size[0] | 0, h = size[1] | 0;
      if (w < 1 || h < 1) return;
      var ax = p.at[0] | 0, ay = p.at[1] | 0;
      var block = Array.isArray(p.block) ? p.block : null;
      for (var dy = 0; dy < h; dy++) {
        for (var dx = 0; dx < w; dx++) {
          var blocked = block ? (block[dy] || '').charAt(dx) === '#' : true;
          if (blocked) propCells[(ax + dx) + ',' + (ay + dy)] = true;
        }
      }
      propList.push({ pic: p.pic, at: [ax, ay], w: w, h: h,
                      frames: (p.frames | 0) || 1, fps: (p.fps | 0) || PROP_FPS,
                      layer: p.layer === 'ground' ? 'ground' : 'stand' });
    });
  }
  function propBlocked(x, y) {
    readProps();
    return !!propCells[x + ',' + y];
  }

  // The pictures each region's props name, preloaded like the rest.
  var propPics = window.VEFR_PROP_PICS || {};
  var propImgs = {};
  Object.keys(propPics).forEach(function (region) {
    propImgs[region] = {};
    Object.keys(propPics[region]).forEach(function (pic) {
      var im = new Image();
      im.onload = function () { draw(); };
      im.src = propPics[region][pic];
      propImgs[region][pic] = im;
    });
  });
  function propImage(pic) {
    var im = (propImgs[regionName] || {})[pic];
    return (im && im.complete && im.naturalWidth > 0) ? im : null;
  }
  function propSeen(p) {
    for (var dy = 0; dy < p.h; dy++) {
      for (var dx = 0; dx < p.w; dx++) {
        if (!hideUnseen(p.at[0] + dx, p.at[1] + dy)) return true;
      }
    }
    return false;
  }
  function propFrame(p) {
    if (p.frames <= 1 || reducedMotion()) return 0;
    return Math.floor(nowMs() / 1000 * p.fps) % p.frames;
  }
  // The picture is as wide as the footprint and stands on its bottom edge.
  function drawProp(p) {
    var im = propImage(p.pic);
    if (!im) return;
    var fw = Math.floor(im.naturalWidth / p.frames), fh = im.naturalHeight;
    if (!fw) return;
    if (p.frames > 1 && !reducedMotion()) animWant = true;
    // Pixel art draws the picture at its own size (artSize); otherwise it is p.w tiles wide.
    var box = artSize(fw, fh, p.w * T * (fh / fw));
    var across = snapSpan((p.at[0] + p.w / 2) * T - box.w / 2, box.w);
    var up = snapSpan((p.at[1] + p.h) * T - box.h, box.h);
    ctx.drawImage(im, propFrame(p) * fw, 0, fw, fh, across[0], up[0], across[1], up[1]);
  }

  // ---- a generated floor's decor (vefr#442) ----
  // A Section may scatter small pictures over its floors: a puddle, a crack,
  // a torch on a wall face. They are drawn right after the ground, under
  // books, loot and everyone, and they never block. The descent wires each
  // floor's pictures into `VEFR_DECOR_PICS` by region name when the floor is
  // grown, so they are loaded the first time that floor is drawn.
  var decorImgs = {};      // src -> Image, shared by every floor
  function decorSrc(pic) {
    var pics = (window.VEFR_DECOR_PICS || {})[regionName];
    var src = pics ? pics[pic] : null;
    return (typeof src === 'string' && src) ? src : null;
  }
  function decorImage(src) {
    var im = decorImgs[src];
    if (!im) {
      im = decorImgs[src] = new Image();
      im.onload = function () { draw(); };
      im.src = src;
    }
    return (im.complete && im.naturalWidth > 0) ? im : null;
  }
  function drawDecor() {
    var list = Array.isArray(town.decor) ? town.decor : [];
    // `VEFR_DECOR_DRAWN` is how many seen decor this frame laid down that
    // have a picture to draw, loaded or not (a harness reads it).
    var drawn = 0;
    list.forEach(function (d) {
      if (!d || !Array.isArray(d.at) || hideUnseen(d.at[0], d.at[1])) return;
      var src = decorSrc(d.pic);
      if (!src) return;
      drawn++;
      var im = decorImage(src);
      if (!im) return;
      var fw = im.naturalWidth, fh = im.naturalHeight;
      // One tile wide, standing on the tile's bottom edge, as a 1x1 prop is.
      var box = artSize(fw, fh, T * (fh / fw));
      var across = snapSpan((d.at[0] + 0.5) * T - box.w / 2, box.w);
      var up = snapSpan((d.at[1] + 1) * T - box.h, box.h);
      ctx.drawImage(im, 0, 0, fw, fh, across[0], up[0], across[1], up[1]);
    });
    window.VEFR_DECOR_DRAWN = drawn;
  }

  // One ticker for everything that moves on its own. It redraws at most
  // twelve times a second, only while something animates and the page is
  // shown; reduced motion never starts it.
  var ANIM_STEP_MS = 1000 / 12;
  var animWant = false, animRaf = 0, animLast = 0;
  function scheduleAnim() {
    if (animRaf || !animWant || document.hidden) return;
    if (typeof requestAnimationFrame !== 'function') return;
    animRaf = requestAnimationFrame(animTick);
  }
  function animTick() {
    animRaf = 0;
    if (!animWant || document.hidden) return;
    var t = nowMs();
    if (t - animLast >= ANIM_STEP_MS) { animLast = t; draw(); return; }
    scheduleAnim();
  }
  document.addEventListener('visibilitychange', scheduleAnim);
  // A speech box opened or closed changes who is talking; the talk path itself never redraws.
  if (window.MutationObserver && document.getElementById('npc-box')) {
    new MutationObserver(function () { draw(); })
      .observe(document.getElementById('npc-box'), { attributes: true, attributeFilter: ['hidden'] });
  }

  // A harness-readable view of this region's props, read-only.
  window.VEFR_PROPS = function () {
    readProps();
    return {
      props: propList.map(function (p) {
        return { pic: p.pic, at: p.at.slice(), size: [p.w, p.h],
                 frames: p.frames, fps: p.fps };
      }),
      blocked: Object.keys(propCells).sort()
    };
  };
