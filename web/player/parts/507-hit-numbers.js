  // ---- hit numbers (ADR 0023, `display.hit_numbers`) ----
  // Each blow's number over the one it struck: "3" over a foe, "CRIT 6", a
  // "miss", "-2" over the hero and "+3" for a heal. The fight's own line has
  // always said every one of these in words, so this is for the eye alone
  // (the layer is aria-hidden) and no colour carries a meaning the text
  // does not. A number rises and fades; with motion off - the OS's own
  // setting or the player's switch - it holds still and goes after a beat
  // longer, so it can still be read. It follows the map as the camera moves,
  // set again after every draw. A pack without the key draws none.
  var HIT_LIFE = 900;
  var hitFloats = [];
  function hitAt(tile, text, kind) {
    if (!displayOn('hit_numbers')) return;
    var host = document.getElementById('hits');
    var at = tile || hero;
    if (!host || !at || !text) return;
    var el = document.createElement('span');
    el.className = 'hit hit--' + kind;
    el.dataset.kind = kind;
    el.textContent = text;
    var stack = 0;
    hitFloats.forEach(function (f) { if (f.at[0] === at[0] && f.at[1] === at[1]) stack++; });
    var f = { el: el, at: [at[0], at[1]], stack: stack };
    hitFloats.push(f);
    host.appendChild(el);
    placeHit(f);
    window.setTimeout(function () {
      if (el.parentNode) el.parentNode.removeChild(el);
      var i = hitFloats.indexOf(f);
      if (i >= 0) hitFloats.splice(i, 1);
    }, reducedMotion() ? HIT_LIFE + 600 : HIT_LIFE);
  }
  // Over the middle of the tile, a line higher for each number already there.
  function placeHit(f) {
    f.el.style.left = (f.at[0] * T - cameraAt.x + T / 2) + 'px';
    f.el.style.top = (f.at[1] * T - cameraAt.y + T * 0.2 - f.stack * 16) + 'px';
  }
  afterDraw.push(function () { hitFloats.forEach(placeHit); });
  // The global half (a drink, a spell's heal) reaches it here; null is the hero.
  window.VEFR_HIT_AT = hitAt;
