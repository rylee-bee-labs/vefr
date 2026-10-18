
function setupTown() {
  var world = window.VEFR_WORLD;
  var canvas = document.getElementById('town-canvas');
  var ctx = canvas.getContext('2d');
  var phase = function () { return STATE.get().phase; };

  // The town data is the current region's, and it changes when the
  // hero steps through a door. `town`, `legend`, `pois`, `speakers`
  // and `hero` stay `var`s so draw() and move() read the current
  // values instead of a stale capture.
  var regions = window.VEFR_REGIONS || {};
  var start = window.VEFR_START || {};

  // The ways out of here, read at the moment they are asked for and never
  // captured. The descent rebinds `window.VEFR_TRANSITIONS` when a new run
  // clears the floors, so a `var` holding the list at boot went stale the
  // moment the player pressed New descent: the new floor's stairs were
  // wired into an array nobody read, and the hero was stranded. A captured
  // list and a rebound one cannot drift if nothing captures.
  function transitions() { return window.VEFR_TRANSITIONS || []; }

  // The current region's town data, from the baked regions (falling back
  // to the unified town when a pack baked no regions).
  function regionTown(name) {
    var r = regions[name];
    if (!r) return world.town;
    return {
      map: r.map || [],
      legend: r.legend || {},
      pois: r.pois || {},
      poi_text: r.poi_text || {},
      hero_start: r.hero_start || [1, 1],
      sanctuary_tiles: r.sanctuary_tiles || [],
      watch: r.watch || {},
      water_by_phase: r.water_by_phase || {},
      flood_tiles: r.flood_tiles || [],
      tile: r.tile || 32,
      fog: r.fog,
      bg: r.bg || '#131311',
      hero_color: r.hero_color || '#e8e5df',
      speaker_color: r.speaker_color || '#8b939c',
      speaker_head: r.speaker_head || '#d8d5df',
      props: r.props || [],
      decor: r.decor || [],   // a generated floor's decor (vefr#442)
    };
  }

  // Where the game begins: the act's `start`, else the first region's
  // own hero_start. So a pack can wake the player inside a room.
  var regionName = (start.region && regions[start.region]) ? start.region
    : (world._region || Object.keys(regions)[0] || 'town');
  var town = regionTown(regionName);
  var legend = town.legend;
  var pois = town.pois || {};
  var speakers = regionSpeakers(regionName);
  var hero = (Array.isArray(start.at) && start.at.length === 2
    ? start.at : town.hero_start).slice();
  // Published from the first tile, not only after the first arrival or step: a harness
  // (`vefr playthrough`) reads where the hero stands before its first key.
  window.VEFR_HERO_AT = { x: hero[0], y: hero[1], region: regionName };

  // The canvas's name, for a screen reader (vefr#461). The shell writes
  // one name into the markup and it never moved: a hero who stepped
  // through the door was still standing on a canvas called "the town".
  // The name is the place, so it is set on the way in and on every
  // region change (enterRegion), never on a click.
  //
  // A generated floor is the one place the ENGINE named, so the descent
  // answers first: a Section's label and the floor number - the words
  // the POI line and the hints already say (vefr#362) - else the floor
  // id, which is what every other surface falls back to. Every other
  // region is the pack's own: the author named it, and its region key
  // is that name, said in words.
  function placeInWords(name) {
    var D = window.VEFR_DESCENT;
    if (D && typeof D.isGenerated === 'function' && D.isGenerated(name)) {
      return String(typeof D.placeName === 'function' ? D.placeName(name) : name);
    }
    var words = String(name === undefined || name === null ? '' : name)
      .replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim();
    if (!words) return '';
    // A key that already reads as a name keeps its own article.
    return /^(the|a|an)\s/i.test(words) ? words : 'The ' + words;
  }

  function nameTheCanvas(name) {
    var el = document.getElementById('town-canvas');
    var place = el ? placeInWords(name) : '';
    if (!el || !place) return;
    el.setAttribute('aria-label', place + ', seen from above');
  }
  nameTheCanvas(regionName);

  // The current region's speakers. The baked group (window.VEFR_SPEAKERS)
  // says which keys belong here; a full spec from the world (with
  // `near`, etc.) wins when present, so single-region behavior is
  // exactly what it was.
  function regionSpeakers(name) {
    var grouped = (window.VEFR_SPEAKERS || {})[name];
    if (!grouped) return {};
    var all = (window.VEFR_WORLD && window.VEFR_WORLD.speakers) || {};
    var out = {};
    Object.keys(grouped).forEach(function (k) { out[k] = all[k] || grouped[k]; });
    return out;
  }

