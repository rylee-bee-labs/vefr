// ---- the descent: play-time floors (slice E1) ----
// The runtime half of `vefr.delve`'s descent, and the only place the
// player keeps a floor. A floor that was never baked at weave time is
// drawn here, at the stair, from the run seed - and what the save keeps
// about it is a handful of deltas (who was killed, what was dropped
// where, which secrets, and the explored bitset), never the grid.
//
// Four things live here, and they are the four questions a floor asks:
//   1. the pure twin: `locate`, the floor key, the five streams, the
//      plan, the layout, the mobs - all of it identical to Python's,
//      because the parity harness demands the same answers;
//   2. the virtual region: `ensureRegion` grows `window.VEFR_REGIONS`,
//      `window.VEFR_ENEMIES` and the transitions the moment a stair is
//      used, so a floor nobody baked loads and plays;
//   3. the save: one document per world through `store()`, with the
//      identity triple of every visited floor, the 40-floor cap and the
//      byte budgets of PLAN §3;
//   4. the two cards: the New-descent control, and the one-time
//      `gen_version` card a Release 1 save is offered.
//
// Nothing here names a game, reads a clock, or touches storage directly:
// the only randomness is `VEFR_DELVE.prng`, and every draw is
// `Math.floor(rng() * n)` off a stream named `v3|<floor key>|<stream>`.
window.VEFR_DESCENT = (function () {

  // The same numbers as `src/vefr/delve.py`; the parity harness is what
  // proves the two agree.
  var GEN_VERSION = 4;   // 4: play floors are v3 geometry (E8-0); 3 was v2
  var STREAM_VERSION = 'v3';
  var MOB_SPACING = 7;
  var FLOOR_CAP = 40;
  var FLOOR_BYTES = 1500;
  var SAVE_BYTES = 250000;
  var DEFAULT_FOG_RADIUS = 5;
  var DEFAULT_FAMILY = 'a stranger in the dark';
  var DOC_VERSION = 1;
  var LEGEND_FALLBACK = {
    '#': { base: ['#20242b'], solid: true, tile: 'dungeon-wall' },
    '.': { base: ['#1a1d22'], tile: 'dungeon-floor' },
    u: { base: ['#2b2f38'], tile: 'dungeon-stairs-up' },
    d: { base: ['#2b2f38'], tile: 'dungeon-stairs-down' },
    '+': { base: ['#3a2f24'], solid: true, tile: 'dungeon-door' }
  };

  // ---- the pack's block ------------------------------------------------
  // Read at call time, never captured: a woven file bakes the block in
  // before the first step, and a harness may plant its own.
  function def() { return window.VEFR_DESCENT_DEF || null; }

  function on() {
    var d = def();
    return !!(d && typeof d.run_seed === 'string' && d.run_seed &&
              Array.isArray(d.sections) && d.sections.length &&
              d.sections.every(function (s) { return s && typeof s.id === 'string'; }));
  }

  function sections() {
    var d = def();
    return on() ? d.sections : [];
  }

  function worldName() {
    return (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
  }

  // The URL parameter a caller uses to ask for a run seed of their own:
  // `player.html?vefr-seed=hello`. Read at call time, so a page opened
  // with it answers with it and a page opened without it changes not at
  // all - `vefr look --seed`, a share link and a headless reviewer all
  // name a seed without editing world.json. Length-capped because the
  // seed is part of every floor key (and of the save), and a URL is
  // untrusted input.
  var SEED_PARAM = 'vefr-seed';
  var SEED_MAX = 120;

  function seedParam() {
    try {
      if (!window.location || !window.location.search) return '';
      var asked = new URLSearchParams(window.location.search).get(SEED_PARAM);
      return (typeof asked === 'string') ? asked.trim().slice(0, SEED_MAX) : '';
    } catch (e) {
      // A browser without URLSearchParams gets the pack's own seed, the
      // same one it got before this parameter existed.
      return '';
    }
  }

  // The base seed every floor key is built on. The parameter wins over
  // the pack's `run_seed` when it is there; the pack's seed is what
  // every other caller already gets. A pack with no descent never asks
  // (see `on`), so the parameter is ignored there exactly as it was.
  function baseSeed() {
    var asked = seedParam();
    if (asked) return asked;
    var d = def();
    return (d && d.run_seed) || '';
  }

  // ---- the streams, in Python's order ---------------------------------
  function floorName(sectionId, cycle, k) {
    return sectionId + '-' + cycle + '-' + k;
  }

  function floorKey(seed, sectionId, cycle, k) {
    return seed + '/' + sectionId + '/' + cycle + '/' + k;
  }

  function streamSeed(key, stream) { return STREAM_VERSION + '|' + key + '|' + stream; }
  function lootSeed(key, mobId) { return streamSeed(key, 'loot|' + mobId); }
  function chestSeed(key, chestId) { return streamSeed(key, 'chest|' + chestId); }
  function runSeed(base, run) {
    run = (typeof run === 'number' && run > 0) ? Math.floor(run) : 0;
    return run === 0 ? base : base + '/run-' + run;
  }

  function randRange(rng, lo, hi) { return lo + Math.floor(rng() * (hi - lo + 1)); }

  function isWhole(n) { return typeof n === 'number' && isFinite(n) && Math.floor(n) === n; }

  function rangeOf(holder, key, fallback) {
    var value = holder ? holder[key] : null;
    if (Array.isArray(value) && value.length === 2 &&
        isWhole(value[0]) && isWhole(value[1]) && value[0] <= value[1]) {
      return [value[0], value[1]];
    }
    return fallback;
  }



  function floorsOf(section) {
    var value = section ? section.floors : null;
    if (isWhole(value) && value >= 1) return value;
    return null;
  }

  // ---- the families (the twin of `delve._families_of`) -----------------

  function has(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
  }

  // One Blueprint family's base record by id, or null: the twin of
  // `vefr.blueprint.resolve_family`. The `extends` chain is walked to its
  // root, then each family's own `defaults` are merged over them, a later
  // value replacing an earlier one whole. A family the Blueprint does not
  // have, one whose parent is missing and one caught in a cycle all come
  // back with no base - the validator says those out loud (`vefr check`,
  // `/families/0/family`), and a floor lays itself rather than refusing
  // to be walked.
  function familyBase(id) {
    var source = def();
    var families = (source && source.blueprint &&
                    typeof source.blueprint.families === 'object' &&
                    source.blueprint.families)
      ? source.blueprint.families : null;
    if (!families || typeof id !== 'string' || !has(families, id)) return null;
    var chain = [], seen = {}, current = id;
    while (true) {
      if (has(seen, current)) return null;          // a cycle has no root
      seen[current] = true;
      chain.push(current);
      var record = families[current];
      var parent = (record && typeof record === 'object') ? record.extends : null;
      if (parent === undefined || parent === null) break;
      if (!has(families, parent)) return null;     // an unknown parent
      current = parent;
    }
    var base = null;
    for (var i = chain.length - 1; i >= 0; i--) {   // the root first
      var defaults = families[chain[i]] ? families[chain[i]].defaults : null;
      if (!defaults || typeof defaults !== 'object') continue;
      if (!base) base = {};
      for (var key in defaults) {
        if (has(defaults, key)) base[key] = defaults[key];
      }
    }
    return base;
  }

  // A family's health as a range, for the one draw that spends it: a
  // Blueprint base is one whole number - `hp: 4` is four hit points,
  // every floor - and a pair is a Section's or a test's own range.
  function hpRange(family) {
    var value = family ? family.hp : null;
    if (isWhole(value)) return [value, value];
    return rangeOf(family, 'hp', [1, 1]);
  }

  // What one kill of this family is worth, on this floor (the twin of
  // `vefr.sections.xp_for`). A family's own `xp` is the number it
  // wrote; a family that writes none takes the documented default -
  // `XP_BASE` on the first floor, `XP_PER_DEPTH` more for every floor
  // below - so a descent that climbs pays more as it climbs. Pure, and
  // no draw is spent on it, so it moves no wall, no monster and no
  // drop.
  var XP_BASE = 1;
  var XP_PER_DEPTH = 2;
  function xpFor(family, depth) {
    var declared = family ? family.xp : null;
    if (isWhole(declared) && declared >= 0) return declared;
    var d = (isWhole(depth) && depth >= 1) ? depth : 1;
    return XP_BASE + XP_PER_DEPTH * (d - 1);
  }

  // ---- where a depth leads (the twin of `locate`) ----------------------
  function locate(depth) {
    var list = sections();
    var counts = list.map(floorsOf);
    var total = counts.reduce(function (a, b) { return a + (b || 0); }, 0);
    if (!isWhole(depth) || depth < 1 || !total) return null;
    var cycle = Math.floor((depth - 1) / total);
    var within = (depth - 1) % total;
    for (var i = 0; i < list.length; i++) {
      var count = counts[i] || 0;
      if (within < count) {
        return { cycle: cycle, section: list[i].id, sectionIndex: i,
                 k: within + 1, depth: depth };
      }
      within -= count;
    }
    return null;
  }

  // The name back into the depth it plays at, so a region that is only
  // known by its name still knows which floor it is.
  function depthOfName(name) {
    var at = parseName(name);
    if (!at) return 0;
    var list = sections();
    var total = 0;
    for (var i = 0; i < list.length; i++) total += floorsOf(list[i]) || 0;
    var before = 0;
    for (var j = 0; j < at.sectionIndex; j++) before += floorsOf(list[j]) || 0;
    return at.cycle * total + before + at.k;
  }

  // "<section id>-<cycle>-<k>": the id may itself carry dashes, so the
  // two numbers are read off the end and the id is the rest.
  function parseName(name) {
    if (!on()) return null;
    var m = /^(.*)-(\d+)-(\d+)$/.exec(String(name === undefined ? '' : name));
    if (!m) return null;
    var list = sections();
    for (var i = 0; i < list.length; i++) {
      if (list[i].id === m[1]) {
        return { section: list[i], sectionIndex: i,
                 cycle: Number(m[2]), k: Number(m[3]) };
      }
    }
    return null;
  }

  function isGenerated(name) { return parseName(name) !== null; }

  // ---- a floor, drawn (the twin of `floor_plan`) ----------------------
  function seedFor(run) { return runSeed(baseSeed(), run); }

  // ---- a floor's legend (the twin of `delve.section_legend`) -----------
  // The shared `LEGEND` with the Section's own `tiles` laid on top, which is
  // what makes two Sections in one descent draw different ground. Only a glyph
  // the generator already draws is overridden, and only its `tile`: the base
  // colours and the `solid` flag are the engine's. A Section with no `tiles`
  // gets exactly the legend every generated floor has always had.
  function sectionLegend(section) {
    var legend = {};
    Object.keys(LEGEND_FALLBACK).forEach(function (glyph) {
      var spec = LEGEND_FALLBACK[glyph], copy = {};
      Object.keys(spec).forEach(function (field) { copy[field] = spec[field]; });
      legend[glyph] = copy;
    });
    var tiles = (section && typeof section.tiles === 'object' &&
                 section.tiles && !Array.isArray(section.tiles)) ? section.tiles : null;
    if (!tiles) return legend;
    Object.keys(tiles).sort().forEach(function (glyph) {
      var name = tiles[glyph];
      if (typeof name === 'string' && name && isObj(legend[glyph])) {
        legend[glyph].tile = name;
      }
    });
    return legend;
  }

  // ---- the Section's own floor size and kind (twins of `vefr.sections`) --
  // Play draws exactly the floor `vefr check` sweeps (E8-0, 2026-10-09):
  // `floor_size` on the `v3|<key>|size` stream, `floor_kind` on the
  // `v3|<key>|special` stream, the same numbers in both languages.
  var SECTION_SIZE = [[64, 64], [48, 48]];
  var SIZE_BOUNDS = [[32, 128], [24, 96]];
  var SECTION_FLOORS = 9;
  var DEFAULT_PATTERN = ['entry', 'n', 'n', 'special', 'landing', 'n',
                         'special', 'n', 'warden'];
  var PATTERN_SLOTS = ['entry', 'n', 'special', 'landing', 'warden'];
  var DEFAULT_SPECIALS = ['treasure', 'infested', 'hub'];

  function wholePair(value, fallback) {
    if (Array.isArray(value) && value.length === 2 &&
        isWhole(value[0]) && isWhole(value[1])) {
      return [Math.min(value[0], value[1]), Math.max(value[0], value[1])];
    }
    return fallback;
  }
  function clampTo(value, bounds) { return Math.max(bounds[0], Math.min(bounds[1], value)); }
  function sectionFloors(section) {
    var v = section ? section.floors : null;
    return (isWhole(v) && v > 0) ? v : SECTION_FLOORS;
  }
  function sectionPattern(section) {
    var raw = section ? section.pattern : null;
    var slots = Array.isArray(raw)
      ? raw.filter(function (x) { return typeof x === 'string' && PATTERN_SLOTS.indexOf(x) >= 0; })
      : DEFAULT_PATTERN.slice();
    while (slots.length < sectionFloors(section)) slots.push('n');
    return slots;
  }
  function sectionSpecials(section) {
    var raw = section ? section.specials : null;
    if (Array.isArray(raw)) {
      var named = raw.filter(function (x) { return typeof x === 'string' && x; });
      if (named.length) return named;
    }
    return DEFAULT_SPECIALS;
  }
  function floorSize(section, key) {
    var raw = (section && section.size && typeof section.size === 'object' &&
               !Array.isArray(section.size)) ? section.size : null;
    var w = wholePair(raw ? raw.w : null, SECTION_SIZE[0]);
    var h = wholePair(raw ? raw.h : null, SECTION_SIZE[1]);
    var wl = clampTo(w[0], SIZE_BOUNDS[0]), wh = clampTo(w[1], SIZE_BOUNDS[0]);
    var hl = clampTo(h[0], SIZE_BOUNDS[1]), hh = clampTo(h[1], SIZE_BOUNDS[1]);
    var rng = window.VEFR_DELVE.prng('v3|' + key + '|size');
    var width = wl + Math.floor(rng() * (wh - wl + 1));
    var height = hl + Math.floor(rng() * (hh - hl + 1));
    return [width, height];
  }
  function floorKindOf(section, k, seed, cycle) {
    var slots = sectionPattern(section);
    var slot = (isWhole(k) && k >= 1 && k <= slots.length) ? slots[k - 1] : 'n';
    if (slot !== 'special') return 'normal';
    var kinds = sectionSpecials(section);
    var id = (section && typeof section.id === 'string') ? section.id : '';
    var rng = window.VEFR_DELVE.prng('v3|' + floorKey(seed, id, cycle, k) + '|special');
    return kinds[Math.floor(rng() * kinds.length)];
  }
  function tileOrNull(value) {
    return (Array.isArray(value) && value.length === 2) ? [value[0], value[1]] : null;
  }

  // The pack's stamps, as the weave carries them in the descent block (the
  // twin of delve.py `stamps_of`): the records `vefr check` sweeps with.
  function stampsOf() {
    var d = def();
    var found = d ? d.stamps : null;
    return Array.isArray(found)
      ? found.filter(function (r) { return r && typeof r === 'object' && !Array.isArray(r); })
      : [];
  }
  // Half of a floor's identity: the Section, and the pack's stamps when it
  // has any, so a stamp edit redraws floors too (twin of `section_hash`).
  function sectionHash(section) {
    var stamps = stampsOf();
    return hash12(canonical(stamps.length ? { section: section, stamps: stamps } : section));
  }

  // How many randoms this floor carries. Two answers, in this order: the
  // count the Section's own `mobs` table names for this floor (vefr#357 -
  // four on a floor the pack named four, zero on a floor it named zero, and
  // `from` for every floor it did not name), or, for a Section that names
  // none for it, the area budget (PLAN.md section 2, step 4 - "randoms by
  // area budget") the v3 pop stage also clamps. The budget is not a draw
  // either way.
  // The rule itself is `VEFR_DELVE.v3MobBudget`, part 396's own - the twin of
  // `vefr.delve_v3.mob_budget`, which `vefr.delve._mob_budget` calls the
  // same way. What lives here is the one thing this part knows that 396 does
  // not: how many walkable tiles this floor's rows carry.
  function mobBudget(rows, section, k) {
    var walkable = 0;
    for (var y = 0; y < rows.length; y++) {
      var row = rows[y], at = row.indexOf('.');
      while (at !== -1) { walkable++; at = row.indexOf('.', at + 1); }
    }
    return window.VEFR_DELVE.v3MobBudget(section, walkable, k);
  }

  // A Section names a Blueprint family by id and carries no record of
  // its own (ADR 0014), so the base - hp, atk, sight, drops, name - is
  // resolved out of the pack's Blueprint, which the bake writes into the
  // descent block beside the Sections, and the Section's own keys win
  // over it. That is `vefr.sections.families`, the merge the validator
  // and the generator already share, so a monster here cannot come out
  // with a family the check would not have accepted. An entry with no
  // base still draws; its stats come back at this function's own floor
  // of 1, which is the answer for a base that says nothing.
  function familiesOf(section) {
    var listed = (section && Array.isArray(section.families))
      ? section.families : [];
    var out = [];
    for (var i = 0; i < listed.length; i++) {
      var entry = listed[i];
      if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue;
      var name = entry.family;
      var base = (typeof name === 'string' && name) ? familyBase(name) : null;
      var merged = {};
      if (base) {
        for (var b in base) if (has(base, b)) merged[b] = base[b];
      }
      for (var e in entry) if (has(entry, e)) merged[e] = entry[e];
      out.push(merged);
    }
    return out.filter(function (f) {
      return typeof f.family === 'string' && f.family; })
      .sort(function (a, b) {
        return a.family < b.family ? -1 : (a.family > b.family ? 1 : 0); });
  }

  // A Section's family entry may name a `depth` range - `[7, 9]` for a family
  // meant for the last three floors of a nine-floor Section - and a range that
  // is not read is a family on every floor of the Section, which is what the
  // range was written to stop. `k` is the floor's own 1-based position inside
  // its Section, not the global depth: the range is the Section's, and each
  // Section counts from its own first floor. An entry with no range, or one
  // that is not a `[lo, hi]` pair of whole numbers, is on every floor -
  // `vefr check` says such a range out loud. The twin of `delve._family_on_floor`.
  var FLOOR_SPAN = 99;
  function familyOnFloor(family, k) {
    var range = rangeOf(family, 'depth', [1, FLOOR_SPAN]);
    return range[0] <= k && k <= range[1];
  }

  // `k` is the floor's 1-based position in its Section, which is what the
  // Section's own `mobs` table is read against. The twin of
  // `vefr.delve.mobs_at`.
  function mobsAt(key, section, rows, up, down, k, depth) {
    var rng = window.VEFR_DELVE.prng(streamSeed(key, 'pop'));
    var count = mobBudget(rows, section, k);
    var families = familiesOf(section).filter(function (f) {
      return familyOnFloor(f, k);
    });
    var pool = [];
    for (var f = 0; f < families.length; f++) {
      var weight = families[f].weight;
      weight = (isWhole(weight) && weight > 0 && weight <= 99) ? weight : 1;
      for (var w = 0; w < weight; w++) pool.push(families[f]);
    }
    var candidates = [];
    for (var y = 0; y < rows.length; y++) {
      for (var x = 0; x < rows[y].length; x++) {
        if (rows[y][x] !== '.') continue;
        if (Math.abs(x - up[0]) + Math.abs(y - up[1]) < MOB_SPACING) continue;
        if (Math.abs(x - down[0]) + Math.abs(y - down[1]) < MOB_SPACING) continue;
        candidates.push([x, y]);
      }
    }
    var mobs = [];
    for (var i = 0; i < count; i++) {
      if (!candidates.length || !pool.length) break;
      var pick = Math.floor(rng() * candidates.length);
      var at = candidates.splice(pick, 1)[0];
      var family = pool[Math.floor(rng() * pool.length)];
      var hr = hpRange(family);
      var hp = randRange(rng, Math.max(1, hr[0]), Math.max(1, hr[1]));
      var atk = isWhole(family.atk) ? family.atk : 1;
      var sight = isWhole(family.sight) ? family.sight : 6;
      mobs.push({
        id: 'm' + i, family: family.family,
        name: (typeof family.name === 'string' && family.name) ? family.name : DEFAULT_FAMILY,
        at: [at[0], at[1]], hp: Math.max(1, hp), atk: Math.max(1, atk),
        sight: Math.max(1, sight), xp: xpFor(family, depth),
        drops: mobDrops(key, 'm' + i, family.drops)
      });
    }
    return mobs;
  }

  // ---- the Section's warden (twin of delve.py, ADR 0015, E8a part 1) --
  // Monster `w` on the warden floor's v3 warden anchor, outside the area
  // budget; its defeat sets `warden:<id>:c<cycle>`, a permanent story flag,
  // and a warden whose flag is set is not spawned again. Amendment 1 §2
  // (E8d) adds how it is passed (`challenge`), whether a beaten one stays
  // (`yields`) and whether it can be struck at all (`fightable`).
  var WARDEN_MOB = 'w';
  // The two challenges Amendment 1 §2 gives a warden, in the ADR's order.
  // `defeat` is the default and is what every pack in the tree plays.
  var WARDEN_CHALLENGES = ['defeat', 'rule'];
  function wardenOf(section) {
    var raw = section ? section.warden : null;
    if (typeof raw === 'string' && raw) return { id: raw, family: raw };
    if (raw && typeof raw === 'object' && !Array.isArray(raw) &&
        typeof raw.family === 'string' && raw.family) {
      var out = { id: (typeof raw.id === 'string' && raw.id) ? raw.id : raw.family,
                  family: raw.family };
      if (typeof raw.carries === 'string' && raw.carries) out.carries = raw.carries;
      // Only what the pack wrote, exactly as `delve.warden_of`: a floor
      // plan for a pack that names none of the three holds the same bytes.
      if (WARDEN_CHALLENGES.indexOf(raw.challenge) >= 0) out.challenge = raw.challenge;
      if (raw.yields === true) out.yields = true;
      if (raw.fightable === false) out.fightable = false;
      return out;
    }
    return null;
  }
  function wardenFlag(id, cycle) { return 'warden:' + id + ':c' + cycle; }
  // The flag's two halves, read back: `warden:<id>:c<n>`. A flag that is
  // not one of this shape is some other pack's flag and not ours.
  function wardenFlagParts(flag) {
    var hit = /^warden:(.+):c(\d+)$/.exec(String(flag || ''));
    return hit ? { id: hit[1], cycle: Number(hit[2]) } : null;
  }

  // ---- the vault's story flag, the town gate and the story end (E8c) --
  // (twins of delve.py `vault_of`, `vault_flag`, `town_seen_flag`,
  // `story_end_of` and `act_number`.) A Section's `vault` is either a
  // stamp id, which names no story flag and therefore gates nothing, or a
  // record `{"stamp": ..., "sets": ...}`. `sets` is what the vault's note
  // records, and it is the guard ADR 0015 puts on the town gate: a visit
  // to town only counts once this Section's note has been read.
  var STORY_END_FLAG = 'king-slain';
  function vaultFlag(section) {
    var raw = section ? section.vault : null;
    if (typeof raw === 'string' && raw) return null;
    if (raw && typeof raw === 'object' && !Array.isArray(raw) &&
        typeof raw.stamp === 'string' && raw.stamp &&
        typeof raw.sets === 'string' && raw.sets) return raw.sets;
    return null;
  }
  function townSeenFlag(sectionId, cycle) { return 'town-seen:' + sectionId + ':c' + cycle; }
  function storyEnd() {
    var d = def();
    var value = (d && typeof d.story_end === 'string' && d.story_end) ? d.story_end : STORY_END_FLAG;
    return value;
  }
  // The act a set of story flags puts the story in: one plus the vault
  // notes actually read. Derived on every read, never stored (ADR 0015).
  function actNumber(truth) {
    var flags = isObj(truth) ? truth : {}, seen = [];
    sections().forEach(function (s) {
      var flag = vaultFlag(s);
      if (flag && flags[flag] === true && seen.indexOf(flag) < 0) seen.push(flag);
    });
    return 1 + seen.length;
  }
  function wardenRecord(section, k, cycle, at) {
    var warden = wardenOf(section);
    var slots = sectionPattern(section);
    var slot = (isWhole(k) && k >= 1 && k <= slots.length) ? slots[k - 1] : 'n';
    if (!warden || !at || slot !== 'warden') return null;
    var record = { id: warden.id, flag: wardenFlag(warden.id, cycle) };
    if (warden.carries) record.carries = warden.carries;
    if (warden.challenge) record.challenge = warden.challenge;
    if (warden.yields) record.yields = true;
    if (warden.fightable === false) record.fightable = false;
    return record;
  }
  // The warden floor's vault (ADR 0015; twin of delve.py `_vault_record`):
  // the placed vault stamp's door - the socket its corridor came in by -
  // its note, chest and home, the warden flag that opens the door, and
  // `sets`: the flag the vault's NOTE records, the guard the town gate is
  // behind (E8c). A Section whose `vault` is the bare stamp id E8b
  // shipped names no flag and gets `sets: null`, exactly as Python does.
  function vaultRecord(floor, section, k, cycle) {
    var slots = sectionPattern(section);
    var slot = (isWhole(k) && k >= 1 && k <= slots.length) ? slots[k - 1] : 'n';
    if (slot !== 'warden') return null;
    var placed = (floor.stamps || []).filter(function (p) { return p && p.role === 'vault'; })[0];
    if (!placed) return null;
    var anchors = placed.anchors || {};
    var warden = wardenOf(section);
    return { stamp: placed.id, door: tileOrNull(placed.socket),
             note: tileOrNull(anchors.note), chest: tileOrNull(anchors.chest),
             home: tileOrNull(anchors.home),
             flag: warden ? wardenFlag(warden.id, cycle) : null,
             sets: vaultFlag(section) };
  }
  function doorShut(plan) {
    return !!(plan && plan.vault && plan.vault.door && plan.vault.flag &&
              flags()[plan.vault.flag] !== true);
  }
  function withChar(row, x, ch) { return row.slice(0, x) + ch + row.slice(x + 1); }

  function withWarden(mobs, key, section, k, at, depth) {
    if (!wardenRecord(section, k, 0, at)) return mobs;
    var warden = wardenOf(section);
    var family = warden.family;
    var base = familyBase(family) || {};
    var rng = window.VEFR_DELVE.prng(streamSeed(key, 'warden'));
    var hr = hpRange(base);
    var hp = randRange(rng, Math.max(1, hr[0]), Math.max(1, hr[1]));
    var atk = isWhole(base.atk) ? base.atk : 1;
    var sight = isWhole(base.sight) ? base.sight : 6;
    var kept = mobs.filter(function (m) { return !(m.at[0] === at[0] && m.at[1] === at[1]); });
    var mob = {
      id: WARDEN_MOB, family: family,
      name: (typeof base.name === 'string' && base.name) ? base.name : DEFAULT_FAMILY,
      at: [at[0], at[1]], hp: Math.max(1, hp), atk: Math.max(1, atk),
      sight: Math.max(1, sight), xp: xpFor(base, depth),
      drops: mobDrops(key, WARDEN_MOB, base.drops), warden: true
    };
    // The two presentation keys ride the monster as well as the record,
    // because the player reads them off the monster.
    if (warden.fightable === false) mob.fightable = false;
    if (warden.yields === true) mob.yields = true;
    kept.push(mob);
    return kept;
  }

  // A monster's own loot stream: the order monsters are killed in cannot
  // change what they drop.
  function mobDrops(key, mobId, table) {
    var ids = Array.isArray(table)
      ? table.filter(function (i) { return typeof i === 'string' && i; }) : [];
    if (!ids.length) return [];
    var rng = window.VEFR_DELVE.prng(lootSeed(key, mobId));
    var chosen = ids[Math.floor(rng() * ids.length)];
    return [itemDraw(key, mobId, chosen, (window.VEFR_ITEMS || {})[chosen])];
  }

  // ---- rolled loot (ADR 0017): the twins of delve.py `roll_seed`,
  // `item_draw`, `_weighted` and `_trait_draw`. Read in this order and in
  // this many draws, or the two languages stop agreeing: the bake has
  // already resolved the roll's defaults, so what arrives here is
  // `{rarity: {name: weight}, traits: [...], chance, max}` with nothing
  // left to decide. The item's own fixed `rarity`/`traits` ride a drop
  // that is not drawn from, and an item with neither is the bare id it
  // has always been.

  // One drawn item's own roll stream, off the same floor key and the same
  // monster the base draw came from: the rarity and the hidden traits
  // cannot move when the base id moves, and two monsters never share one.
  function rollSeed(key, mobId, itemId) {
    return streamSeed(key, 'roll|' + mobId + '|' + itemId);
  }
  function itemRollOf(def) {
    if (!def || typeof def !== 'object') return null;
    var roll = def.roll;
    if (!roll || typeof roll !== 'object' || Array.isArray(roll)) return null;
    var table = roll.rarity;
    if (!table || typeof table !== 'object' || Array.isArray(table)) return null;
    var names = Object.keys(table).filter(function (n) {
      return isWhole(table[n]) && table[n] >= 1;
    });
    var pool = Array.isArray(roll.traits)
      ? roll.traits.filter(function (t) { return typeof t === 'string' && t; }) : [];
    // Both halves or nothing: a roll that cannot answer both questions
    // draws nothing, which is `maplab.item_roll_errors`' refusal, not a
    // half-rolled drop here.
    if (!names.length || !pool.length) return null;
    return {
      names: names,
      weights: names.map(function (n) { return table[n]; }),
      pool: pool,
      chance: isWhole(roll.chance) ? roll.chance : 100,
      max: isWhole(roll.max) ? roll.max : 1
    };
  }
  // One name off the table: `floor(rng() * total)` and a walk down the
  // weights - one floor of one stream, and no float compared with another.
  function weightedName(rng, names, weights) {
    var total = 0, i;
    for (i = 0; i < weights.length; i++) total += weights[i];
    var pick = Math.floor(rng() * total), upto = 0;
    for (i = 0; i < names.length; i++) {
      upto += weights[i];
      if (pick < upto) return names[i];
    }
    return names[names.length - 1];
  }
  // The hidden traits one rolled item carries, in draw order: whether it
  // bears any at all, then how many, then which - each drawn once, so two
  // traits never come back the same word and a seed always draws the same.
  function traitDraw(rng, roll) {
    var pool = roll.pool.slice(), out = [];
    if (roll.max < 1 || Math.floor(rng() * 100) >= roll.chance) return out;
    var want = Math.min(1 + Math.floor(rng() * roll.max), pool.length);
    for (var i = 0; i < want; i++) {
      out.push(pool.splice(Math.floor(rng() * pool.length), 1)[0]);
    }
    return out;
  }
  // The drop one drawn item is: the bare id it has always been, or the
  // instance record the bag keeps as it is. `identified` is false here
  // because nothing here decides a thing has been read, it only refuses
  // to pretend one has - reading is the town's identify service
  // (`195-the-identify-service.js`), and this draw is never redone.
  function itemDraw(key, mobId, itemId, def) {
    var entry = (def && typeof def === 'object') ? def : {};
    var roll = itemRollOf(entry);
    var rarity = (typeof entry.rarity === 'string' && entry.rarity) ? entry.rarity : '';
    var traits = Array.isArray(entry.traits)
      ? entry.traits.filter(function (t) { return typeof t === 'string' && t; }) : [];
    if (!roll) {
      if (!rarity && !traits.length) return itemId;
      return { item: itemId, rarity: rarity, traits: traits, identified: false };
    }
    var rng = window.VEFR_DELVE.prng(rollSeed(key, mobId, itemId));
    return {
      item: itemId, rarity: weightedName(rng, roll.names, roll.weights),
      traits: traitDraw(rng, roll), identified: false
    };
  }

  function floorPlan(depth, run) {
    var at = locate(depth);
    if (!at) return null;
    var section = sections()[at.sectionIndex];
    var run0 = isWhole(run) ? run : currentRun();
    var seed = seedFor(run0);
    var key = floorKey(seed, at.section, at.cycle, at.k);
    // the floor `vefr check` sweeps: the twin of delve.py `_v3_floor`
    var size = floorSize(section, key);
    var kind = floorKindOf(section, at.k, seed, at.cycle);
    var D = window.VEFR_DELVE;
    if (D.v3Constants.FLOOR_KINDS.indexOf(kind) < 0) kind = 'normal';
    var floor = D.generateFloorV3(seed, size, section, kind, stampsOf(), at.k, at.cycle);
    var rows = floor.rows.slice();
    var up = null, down = null;
    for (var y = 0; y < rows.length && (!up || !down); y++) {
      for (var x = 0; x < rows[y].length; x++) {
        if (rows[y][x] === 'u' && !up) up = [x, y];
        else if (rows[y][x] === 'd' && !down) down = [x, y];
      }
    }
    if (!up || !down) return null;
    var fog = (section && typeof section.fog === 'object') ? section.fog : null;
    var radius = (fog && isWhole(fog.radius)) ? fog.radius : DEFAULT_FOG_RADIUS;
    // The twin of delve.py's `block_fog`: the shape rides along only when
    // it is not the default, so a Section that names nothing and one that
    // names "circle" produce the same floor record on both sides of the
    // parity harness.
    var blockFog = { radius: Math.max(1, radius) };
    if (fog && fog.shape === 'square') blockFog.shape = 'square';
    return {
      name: floorName(at.section, at.cycle, at.k), key: key,
      identity: { gen: GEN_VERSION, hash: sectionHash(section), key: key },
      depth: depth, cycle: at.cycle, section: at.section, k: at.k,
      kind: kind, gen: floor.gen, w: floor.w, h: floor.h,
      rooms: floor.rooms.length, rows: rows,
      anchors: { up: up, down: down, warden: tileOrNull(floor.anchors.warden),
                 vault: tileOrNull(floor.anchors.vault) },
      mobs: withWarden(mobsAt(key, section, rows, up, down, at.k, depth), key, section,
                       at.k, tileOrNull(floor.anchors.warden), depth),
      warden: wardenRecord(section, at.k, at.cycle, tileOrNull(floor.anchors.warden)),
      vault: vaultRecord(floor, section, at.k, at.cycle),
      legend: sectionLegend(section),
      fog: blockFog
    };
  }

  // ---- canonical JSON and a short digest ------------------------------
  // The identity of a floor includes a hash of its Section, so the two
  // languages must agree on the bytes they hash: keys sorted, no spaces,
  // and numbers written the way both languages write a whole number.
  function canonical(value) {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    if (typeof value === 'number') return isFinite(value) ? String(value) : 'null';
    if (typeof value === 'string') return JSON.stringify(value);
    if (Array.isArray(value)) {
      var parts = [];
      for (var i = 0; i < value.length; i++) parts.push(canonical(value[i]));
      return '[' + parts.join(',') + ']';
    }
    if (typeof value === 'object') {
      var keys = Object.keys(value).sort();
      var out = [];
      for (var k = 0; k < keys.length; k++) {
        if (value[keys[k]] === undefined) continue;
        out.push(JSON.stringify(keys[k]) + ':' + canonical(value[keys[k]]));
      }
      return '{' + out.join(',') + '}';
    }
    return 'null';
  }

  function utf8Bytes(text) {
    var out = [], i, c;
    for (i = 0; i < text.length; i++) {
      c = text.charCodeAt(i);
      if (c < 0x80) { out.push(c); continue; }
      if (c < 0x800) {
        out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
        continue;
      }
      if (c >= 0xd800 && c <= 0xdbff && i + 1 < text.length) {
        var next = text.charCodeAt(i + 1);
        if (next >= 0xdc00 && next <= 0xdfff) {
          i++;
          var cp = 0x10000 + ((c - 0xd800) << 10) + (next - 0xdc00);
          out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 63),
                   0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
          continue;
        }
      }
      out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    return out;
  }

  function hash12(text) {
    var bytes = utf8Bytes(text);
    var h1 = 2166136261, h2 = 3335557771;
    for (var i = 0; i < bytes.length; i++) {
      h1 = Math.imul(h1 ^ bytes[i], 16777619) >>> 0;
      h2 = Math.imul(h2 ^ ((bytes[i] + i) & 255), 2246822519) >>> 0;
    }
    return hex8(h1) + hex8(h2).slice(0, 4);
  }

  function hex8(n) {
    var s = (n >>> 0).toString(16);
    while (s.length < 8) s = '0' + s;
    return s;
  }

  // ---- the save: one document, deltas only ----------------------------
  function docKey() { return 'vefr-descent-' + worldName(); }

  function freshDoc() {
    return { v: DOC_VERSION, gen: GEN_VERSION, run: 0, seed: baseSeed(),
             order: [], floors: {}, flags: {}, card: 0 };
  }

  function isObj(v) {
    return typeof v === 'object' && v !== null && !Array.isArray(v);
  }

  function loadDoc() {
    var saved = store.getJSON(docKey(), null);
    if (!isObj(saved) || saved.v !== DOC_VERSION) return freshDoc();
    if (!isObj(saved.floors)) saved.floors = {};
    if (!isObj(saved.flags)) saved.flags = {};
    if (!Array.isArray(saved.order)) saved.order = Object.keys(saved.floors);
    if (!isWhole(saved.run)) saved.run = 0;
    return saved;
  }

  function currentRun() {
    var run = loadDoc().run;
    return isWhole(run) && run >= 0 ? run : 0;
  }

  // PLAN §3's budgets are in BYTES, and the browser stores UTF-8, so
  // they are counted in UTF-8 bytes. `String.length` counts UTF-16 code
  // units, and one such unit is three bytes for most characters outside
  // ASCII - so a floor whose Section id, flags or deltas carry an accent,
  // an emoji or a skull weighed a third of what it weighs on disk and
  // sailed under a budget it did not fit.
  function bytesOf(value) { return utf8Length(JSON.stringify(value)); }

  function utf8Length(text) { return new TextEncoder().encode(text).length; }

  function floorBytes(record) { return bytesOf(record); }

  // PLAN §3's other half: a visited floor may not carry more than
  // FLOOR_BYTES, and nothing else in the save enforces that - forty floors
  // at 1.5 KB is 60 KB, comfortably inside SAVE_BYTES, so a save of
  // oversized records sails under the whole-save trim and the per-floor
  // number is a claim rather than a contract.
  //
  // What a floor gives up, in this order:
  //   1. the explored bitset. It is where the hero has walked, not what has
  //      been done, and on a big floor it is the whole weight of the record;
  //   2. the longest list of deltas, from its end, until it fits. Only a
  //      pack whose floors carry more deltas than the budget allows gets
  //      here, and it keeps as many as it can rather than being refused.
  // The identity triple is never given up: a floor that is over budget is
  // still the right floor, and its kills and chests stay true to it.
  var FLOOR_LISTS = ['kills', 'chests', 'drops', 'secrets'];

  function fitFloor(record) {
    var out = copyRecord(record);
    if (floorBytes(out) <= FLOOR_BYTES) return out;
    out.fog = '';
    while (floorBytes(out) > FLOOR_BYTES) {
      var longest = '';
      for (var i = 0; i < FLOOR_LISTS.length; i++) {
        if (!longest || out[FLOOR_LISTS[i]].length > out[longest].length) {
          longest = FLOOR_LISTS[i];
        }
      }
      if (!out[longest].length) break;
      out[longest].pop();
    }
    return out;
  }

  function fitFloors(doc) {
    var names = Object.keys(isObj(doc.floors) ? doc.floors : {});
    for (var i = 0; i < names.length; i++) {
      if (isObj(doc.floors[names[i]])) doc.floors[names[i]] = fitFloor(doc.floors[names[i]]);
    }
    return doc;
  }

  // The cap of PLAN §2: at most `FLOOR_CAP` floors, oldest first; and if
  // the save is still over its byte budget, the oldest bitsets go before
  // anything else, because a bitset is the whole weight of a floor.
  //
  // This is the whole-save half of the budget and nothing else: it is the
  // frozen order of sacrifice, and it deliberately does not shrink a
  // record to FLOOR_BYTES. The per-floor half is `fitFloors`, applied by
  // `saveDoc` to what is about to be written, so a document that arrives
  // oversized still reports exactly what the order of sacrifice leaves.
  function trimDoc(doc) {
    return fitDoc(doc).doc;
  }

  // The whole order a save gives things up in: the oldest bitsets first,
  // then the oldest floors whole, and nothing after that - the story
  // flags are the world's own memory and are never given up. So `fits`
  // says whether what is left is inside the budget or whether the save
  // can only be refused.
  function fitDoc(doc) {
    var names = Array.isArray(doc.order) ? doc.order.slice() : [];
    var known = Object.keys(isObj(doc.floors) ? doc.floors : {});
    for (var i = 0; i < known.length; i++) {
      if (names.indexOf(known[i]) === -1) names.push(known[i]);
    }
    while (names.length > FLOOR_CAP) names.shift();
    var out = { v: doc.v, gen: doc.gen, run: doc.run, seed: doc.seed,
                card: doc.card, flags: isObj(doc.flags) ? doc.flags : {},
                floors: {}, order: [] };
    for (var n = 0; n < names.length; n++) {
      var record = doc.floors[names[n]];
      if (!isObj(record)) continue;
      out.floors[names[n]] = copyRecord(record);
      out.order.push(names[n]);
    }
    var i2 = 0;
    while (bytesOf(out) > SAVE_BYTES && i2 < out.order.length) {
      var oldest = out.floors[out.order[i2]];
      if (oldest && oldest.fog) oldest.fog = '';
      i2++;
    }
    while (bytesOf(out) > SAVE_BYTES && out.order.length) {
      delete out.floors[out.order.shift()];
    }
    return { doc: out, fits: bytesOf(out) <= SAVE_BYTES };
  }

  function copyRecord(record) {
    return { g: record.g, h: record.h, k: record.k, n: record.n, s: record.s,
             kills: Array.isArray(record.kills) ? record.kills.slice() : [],
             chests: Array.isArray(record.chests) ? record.chests.slice() : [],
             drops: Array.isArray(record.drops) ? record.drops.slice() : [],
             secrets: Array.isArray(record.secrets) ? record.secrets.slice() : [],
             fog: typeof record.fog === 'string' ? record.fog : '' };
  }

  // A save that cannot be stored is never stored, and says so in words
  // the player can act on: the engine's own rule, not this part's
  // invention. The refusal is kept until a save goes through, and the
  // Descent panel shows it the next time it is opened.
  var lastRefusal = '';

  function saveRefusal() { return lastRefusal; }

  function refuse(text) {
    lastRefusal = text;
    var line = document.getElementById('descent-line');
    if (line) line.textContent = text;
  }

  function saveDoc(doc) {
    // The whole-save trim first (its order of sacrifice is the frozen
    // contract), then the per-floor budget on what survived it. Fitting a
    // floor only ever makes the save smaller, so `fits` still holds.
    var fit = fitDoc(doc);
    if (!fit.fits) {
      refuse('This descent has grown too large to save, so what happened on '
        + 'these floors is not being remembered. Start a new descent, or '
        + "clear this site's saved game in your browser, and try again.");
      return null;
    }
    lastRefusal = '';
    var out = fitFloors(fit.doc);
    store.setJSON(docKey(), out);
    return out;
  }

  // ---- the floors a descent remembers ---------------------------------
  // The identity triple is checked every time a floor is entered. A floor
  // that does not match is a floor the pack or the generator has moved
  // on from: it is drawn again and its deltas go, while the story flags
  // - which belong to the world, not to one floor - stay.
  var currentName = '';

  function recordFor(name, plan) {
    var doc = loadDoc();
    var record = doc.floors[name];
    if (isObj(record) && (record.h !== plan.identity.hash ||
                          record.g !== plan.identity.gen ||
                          record.k !== plan.identity.key)) {
      record = null;
    }
    if (!isObj(record)) {
      record = { g: plan.identity.gen, h: plan.identity.hash,
                 k: plan.identity.key, n: plan.depth, s: plan.section,
                 kills: [], chests: [], drops: [], secrets: [], fog: '' };
    }
    doc.floors[name] = record;
    if (doc.order.indexOf(name) === -1) doc.order.push(name);
    return { doc: doc, record: record, name: name };
  }

  function updateCurrent(mutator) {
    if (!currentName) return null;
    var doc = loadDoc();
    var record = doc.floors[currentName];
    if (!isObj(record)) return null;
    mutator(record);
    return saveDoc(doc);
  }

  function readCurrent(field, fallback) {
    var doc = loadDoc();
    var record = doc.floors[currentName];
    if (!isObj(record)) return fallback;
    var value = record[field];
    return value === undefined ? fallback : value;
  }

  // ---- the virtual region --------------------------------------------
  // The hook the plan calls the biggest structural unknown: the player's
  // region tables are plain objects and `enterRegion` only asks for
  // `regions[name]`, so a floor that was never baked is grown here, at
  // the moment the stair is used, before the player looks for it.
  var wired = {};

  function regionEntry(plan) {
    // The floor's own legend, which is its own Section's `tiles` over the
    // shared one: two Sections in one descent draw different ground. The
    // weave's shared legend is the floor for a plan that carries none.
    var legend = isObj(plan.legend) ? plan.legend
      : ((def() && isObj(def().legend)) ? def().legend : LEGEND_FALLBACK);
    var upKey = plan.anchors.up[0] + ',' + plan.anchors.up[1];
    var downKey = plan.anchors.down[0] + ',' + plan.anchors.down[1];
    var pois = {}, poiText = {};
    pois[upKey] = 'the stair up';
    poiText[upKey] = 'Steps climb back toward the day.';
    pois[downKey] = 'the stair down';
    poiText[downKey] = 'Steps drop into the dark.';
    var map = plan.rows.slice();
    // The vault door is shut until the warden falls (painted over the
    // plan's floor tile; `defeated` opens it in place).
    if (doorShut(plan)) {
      var door = plan.vault.door;
      map[door[1]] = withChar(map[door[1]], door[0], '+');
    }
    if (plan.vault && plan.vault.home) {
      var home = plan.vault.home, homeKey = home[0] + ',' + home[1];
      map[home[1]] = withChar(map[home[1]], home[0], 'u');
      pois[homeKey] = 'the stair home';
      poiText[homeKey] = 'Steps climb out of the vault, all the way home.';
    }
    return {
      map: map, legend: legend, pois: pois, poi_text: poiText,
      hero_start: plan.anchors.up.slice(), sanctuary_tiles: [],
      watch: {}, water_by_phase: {}, flood_tiles: [], tile: 32,
      fog: plan.fog, bg: '#0d0f12', hero_color: '#e8e5df',
      speaker_color: '#8b939c', speaker_head: '#d8d5df'
    };
  }

  // The region's own enemy record. It carries the `xp` the plan gave the
  // monster, which is what `loadEnemies` reads and `heroAttack` pays
  // through `growAward`: a generated monster that arrived here without
  // one is a kill worth nothing, and the floor it stood on is the only
  // place that number could have come from.
  // `fightable` rides it because the player reads it off the enemy and not
  // off the floor plan: it is what refuses a blow. `yields` is NOT copied
  // here. On the entry it means the
  // warden HAS yielded - a state, set below once it is beaten and again by
  // `heroAttack` when it falls - while the plan's `yields` only says it
  // WOULD stay. Copying the plan's key would put a fresh warden on the
  // roster already yielded and, by `loadEnemies`'s `alive`, unattackable
  // from the first turn, so its challenge could never be completed.
  function enemyEntry(mob) {
    var entry = { id: mob.id, name: mob.name, sprite: '', at: mob.at.slice(),
                  hp: mob.hp, atk: mob.atk, sight: mob.sight, xp: mob.xp,
                  drops: mob.drops.slice(), warden: mob.warden === true };
    if (mob.fightable === false) entry.fightable = false;
    return entry;
  }

  // The same door twice is one door - and the second time it is wired it
  // is the true one. The arrival tile is part of what a door says: a new
  // run redraws floor one, so the stair into the deep now ends on the new
  // floor's up-anchor, not on the tile the previous run drew. A dedupe
  // that kept the first `to_at` left the hero walking in mid-floor, and
  // on a run where that tile is a wall, inside one.
  function pushTransition(list, t) {
    for (var i = 0; i < list.length; i++) {
      var one = list[i];
      if (one && one.from === t.from && String(one.at) === String(t.at) &&
          one.to === t.to) {
        if (Array.isArray(t.to_at)) one.to_at = t.to_at.slice();
        return;
      }
    }
    list.push(t);
  }

  // The town gate (ADR 0015, "The town gate and the paid shortcut"): a
  // Section whose vault names the flag its note records is gated on
  // `town-seen:<section>:c<cycle>`, which a town visit sets once that
  // note has been read. The stair that carries a player on into the next
  // Section - the warden floor's down stair - carries the gate, and so
  // does any stair in the town that enters a Section: both are the one
  // mechanism, `requires` through `lockOpen`, and no pack writes either.
  // A Section whose `vault` is the bare stamp id E8b shipped names no
  // flag, gates nothing, and its stairs carry no `requires` at all. Inside
  // an endless cycle (cycle 1 or more) no Section is gated: endless mode
  // has no town gate, only the story end on the stair past the last Section.
  var GATE_LOCKED = 'The stair is shut. Go up to town first: town knows '
    + 'nothing of the way on until you have read what is kept down here.';

  function townGate(sectionId, cycle) {
    if (cycle >= 1) return null;
    var here = sections().filter(function (s) { return s && s.id === sectionId; })[0];
    return (here && vaultFlag(here)) ? townSeenFlag(sectionId, cycle) : null;
  }

  function gateFor(depth) {
    // The gate on a stair that enters the Section playing at `depth`. A
    // stair into the first Section has nothing behind it and is never
    // gated; any later one is gated on the town visit the Section before
    // it asked for.
    var at = locate(depth);
    if (!at || at.sectionIndex === 0) return null;
    return townGate(sections()[at.sectionIndex - 1].id, at.cycle);
  }

  // The descent's own way in takes its tile (vefr#352). A door is found
  // by its region and its tile, first match wins, and the pack's doors
  // are baked before this one - so an authored transition on the entry
  // tile used to answer Interact and the dungeon was unreachable by
  // walking. The entry is the pack's declared, checked way down, so it is
  // the door that survives on that tile: every other tile, and every
  // other door in the pack, is untouched. `vefr check` refuses a pack
  // that writes both on one tile, so this is the fallback for a pack
  // woven anyway, not a way to author a collision quietly.
  function claimTile(list, t) {
    for (var i = list.length - 1; i >= 0; i--) {
      var one = list[i];
      if (one && one.from === t.from && Array.isArray(one.at) &&
          String(one.at) === String(t.at)) list.splice(i, 1);
    }
    list.push(t);
  }

  // The stairs of a generated floor: down to the next depth, up to the
  // floor above - and the first floor's stair up is the way home.
  function wireFloor(name, plan) {
    if (wired[name]) return;
    wired[name] = true;
    var list = window.VEFR_TRANSITIONS || [];
    var down = locate(plan.depth + 1);
    if (down) {
      var below = floorPlan(plan.depth + 1);
      if (below) {
        var stair = { from: name, at: plan.anchors.down.slice(),
                      to: below.name, to_at: below.anchors.up.slice() };
        // The warden floor is the last floor of its Section, so its down
        // stair is the gate into the next one. The stair that leads past
        // the last Section into endless opens on the story end instead
        // (ADR 0015 Amendment 1 section 1): one stair carries one flag.
        var endless = down.cycle > plan.cycle;
        var gate = endless ? storyEnd() : townGate(plan.section, plan.cycle);
        if (gate) {
          stair.requires = { flag: gate };
          stair.locked_text = endless
            ? 'The stair is shut until the story ends: ' + gate + ' must be set.'
            : GATE_LOCKED;
        }
        pushTransition(list, stair);
      }
    }
    var up = locate(plan.depth - 1);
    if (up) {
      var above = floorPlan(plan.depth - 1);
      if (above) {
        pushTransition(list, { from: name, at: plan.anchors.up.slice(),
                               to: above.name, to_at: above.anchors.down.slice() });
      }
    } else {
      var entry = entryHere();
      if (entry) {
        pushTransition(list, { from: name, at: plan.anchors.up.slice(),
                               to: entry.region, to_at: entry.at.slice() });
      }
    }
    // The vault's stair home (ADR 0015): inside the vault, so it is only
    // reached through the door the warden's defeat opens.
    var home = plan.vault ? plan.vault.home : null;
    var way = entryHere();
    if (home && way) {
      pushTransition(list, { from: name, at: home.slice(), to: way.region, to_at: way.at.slice() });
    }
    window.VEFR_TRANSITIONS = list;
  }

  // The pack's own stair into the deep: the tile in a baked region the
  // descent starts from. It is a transition like any other, so the one
  // verb, the reach and the lock rules all work on it as they always did.
  function entryHere() {
    var d = def();
    if (!d || !isObj(d.entry)) return null;
    var region = d.entry.region;
    var at = d.entry.at;
    if (typeof region !== 'string' || !region ||
        !Array.isArray(at) || at.length !== 2 || !isWhole(at[0]) || !isWhole(at[1])) {
      return null;
    }
    return { region: region, at: at };
  }

  function wireEntry() {
    var entry = entryHere();
    if (!entry) return;
    var list = window.VEFR_TRANSITIONS || [];
    var first = locate(1);
    if (!first) return;
    var plan = floorPlan(1);
    if (!plan) return;
    // The town stair's entry for the next Section carries the same gate
    // the warden's down stair does (ADR 0015). The pack's own stair enters
    // the FIRST Section, which nothing lies behind and so is never gated;
    // the moment the elevator rule offers a town stair per Section, this
    // is what carries the gate on it.
    var gate = gateFor(1);
    claimTile(list, { from: entry.region, at: entry.at.slice(),
                      to: plan.name, to_at: plan.anchors.up.slice(),
                      requires: gate ? { flag: gate } : null,
                      locked_text: gate ? GATE_LOCKED : null });
    window.VEFR_TRANSITIONS = list;
  }

  // ---- books pinned to a generated floor (the twin of `place_books`) --
  // A library book on a generated floor names where on it to lie, not a
  // tile: the floor is redrawn every run, so the tile is chosen from the
  // floor itself - reachable ground, off the stairs and the monsters, one
  // book per tile - from the floor's own `book|<id>` stream. The same run
  // always shows a book in the same place; a new run moves it.
  var BOOK_NEAR = [2, 6];
  var VAULT_PLACES = { 'vault-note': 'note', 'vault-chest': 'chest' };   // twin of delve.VAULT_PLACES

  function floorDistances(rows, start) {
    var dist = {};
    dist[start[0] + ',' + start[1]] = 0;
    var queue = [[start[0], start[1]]];
    for (var i = 0; i < queue.length; i++) {
      var x = queue[i][0], y = queue[i][1], d = dist[x + ',' + y];
      var steps = [[x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]];
      for (var s = 0; s < 4; s++) {
        var nx = steps[s][0], ny = steps[s][1];
        if (ny < 0 || ny >= rows.length || nx < 0 || nx >= rows[0].length) continue;
        if (rows[ny].charAt(nx) === '#' || has(dist, nx + ',' + ny)) continue;
        dist[nx + ',' + ny] = d + 1;
        queue.push([nx, ny]);
      }
    }
    return dist;
  }

  function placeBooks(plan, books) {
    var rows = plan.rows, up = plan.anchors.up, down = plan.anchors.down;
    var fromUp = floorDistances(rows, up), fromDown = floorDistances(rows, down);
    var taken = {};
    taken[up[0] + ',' + up[1]] = true;
    taken[down[0] + ',' + down[1]] = true;
    (plan.mobs || []).forEach(function (m) { taken[m.at[0] + ',' + m.at[1]] = true; });
    // The vault's own tiles are never a drawn book's (twin of place_books).
    var vault = plan.vault || {}, reserved = {};
    ['door', 'note', 'chest', 'home'].forEach(function (k) {
      if (vault[k]) { reserved[vault[k][0] + ',' + vault[k][1]] = true; taken[vault[k][0] + ',' + vault[k][1]] = true; }
    });
    var out = {};
    function xy(k) { var p = k.split(','); return [Number(p[0]), Number(p[1])]; }
    function free(k) {
      var t = xy(k);
      return !taken[k] && has(fromUp, k) && rows[t[1]].charAt(t[0]) === '.';
    }
    function within(dist, lo, hi) {
      return Object.keys(dist).filter(function (k) {
        return dist[k] >= lo && (hi === null || dist[k] <= hi) && free(k);
      });
    }
    books.slice().sort(function (a, b) { return a.id < b.id ? -1 : (a.id > b.id ? 1 : 0); })
      .forEach(function (book) {
        // A vault book is pinned to the vault's note or chest, not drawn.
        if (has(VAULT_PLACES, book.place)) {
          var spot = vault[VAULT_PLACES[book.place]];
          if (spot && reserved[spot[0] + ',' + spot[1]]) {
            delete reserved[spot[0] + ',' + spot[1]];   // one book per vault tile
            out[book.id] = [spot[0], spot[1]];
          }
          return;
        }
        var tiles = book.place === 'near-up' ? within(fromUp, BOOK_NEAR[0], BOOK_NEAR[1])
          : (book.place === 'near-down' ? within(fromDown, BOOK_NEAR[0], BOOK_NEAR[1]) : []);
        if (!tiles.length) tiles = within(fromUp, BOOK_NEAR[0], null);
        if (!tiles.length) tiles = within(fromUp, 0, null);
        if (!tiles.length) return;
        tiles.sort(function (a, b) {
          var p = xy(a), q = xy(b);
          return p[1] - q[1] || p[0] - q[0];
        });
        var rng = window.VEFR_DELVE.prng(streamSeed(plan.key, 'book|' + book.id));
        var pick = tiles[Math.floor(rng() * tiles.length)];
        taken[pick] = true;
        out[book.id] = xy(pick);
      });
    return out;
  }

  // The library's books pinned to this floor get their tile for this run,
  // so finding, drawing and chests read `at` exactly as for any map book.
  function pinBooks(name, plan) {
    var pinned = (window.VEFR_LIBRARY || []).filter(function (b) {
      return b && b.found === 'map' && b.region === name && typeof b.place === 'string';
    });
    if (!pinned.length) return;
    var at = placeBooks(plan, pinned.map(function (b) { return { id: b.id, place: b.place }; }));
    pinned.forEach(function (b) { if (at[b.id]) b.at = at[b.id]; });
  }

  // The pictures a generated floor is drawn with, for this Section alone.
  // The weave resolves each Section's `tiles` into real pictures and bakes
  // them beside the Sections (`section_tiles`), so the two Sections of one
  // descent carry different ground rather than both falling back to the
  // pack's global tile set, which is the town's grass.
  //
  // A Section that names no `tiles` is given nothing here: its floors keep
  // drawing whatever `window.VEFR_TILES` holds, which is exactly what they
  // drew before any of this.
  function wireRegionTiles(name, sectionId) {
    var d = def();
    var perSection = (d && isObj(d.section_tiles)) ? d.section_tiles : null;
    var pictures = perSection && typeof sectionId === 'string'
      ? perSection[sectionId] : null;
    if (!isObj(pictures)) return false;
    var table = window.VEFR_REGION_TILES;
    if (!table) table = window.VEFR_REGION_TILES = {};
    table[name] = pictures;
    return true;
  }

  function ensureRegion(name) {
    if (!on() || wired[name]) return false;
    var depth = depthOfName(name);
    if (!depth) return false;
    var at = parseName(name);
    var plan = floorPlan(depth);
    if (!plan) return false;
    var regions = window.VEFR_REGIONS;
    if (!regions) return false;
    regions[name] = regionEntry(plan);
    // `at.section` is the section OBJECT (see parseName), so the id the
    // picture table is keyed by is `at.section.id` -- `sectionIdOf` is that,
    // and passing the object itself keys nothing and wires no pictures.
    wireRegionTiles(name, at ? at.section.id : '');
    pinBooks(name, plan);
    var enemies = window.VEFR_ENEMIES;
    if (!enemies) enemies = window.VEFR_ENEMIES = {};
    // A warden whose story flag is set stays beaten: not even a town
    // return, which clears the floor's kills, brings it back (ADR 0015).
    // A warden that `yields` is the one exception Amendment 1 §2 writes:
    // it is still standing after the flag is set, so it is still here -
    // and it comes back peaceful, which is what `yields` on the entry
    // says. Everything else about it is the ordinary warden's.
    var beaten = !!(plan.warden && flags()[plan.warden.flag] === true);
    var yields = !!(beaten && plan.warden && plan.warden.yields === true);
    enemies[name] = plan.mobs.filter(function (m) { return !(m.warden && beaten && !yields); })
                             .map(function (m) {
                               var e = enemyEntry(m);
                               if (yields && e.warden) e.yields = true;
                               return e;
                             });
    currentName = name;
    // The record is made before the player arrives, so an identity
    // mismatch is settled by the floor the player is about to see.
    var held = recordFor(name, plan);
    saveDoc(held.doc);
    wireFloor(name, plan);
    return true;
  }

  // Arriving somewhere: the stairs of the floor left behind, and the
  // Stardew reset when the way back is the surface.
  function onEnter(name) {
    if (!on()) return;
    var leaving = currentName;
    var entering = String(name === undefined ? '' : name);
    if (leaving && !isGenerated(entering)) {
      markTownSeen(entering, leaving);
      returnToTown(leaving);
    }
    if (isGenerated(entering)) {
      ensureRegion(entering);
    } else {
      currentName = '';
    }
  }

  // ---- the rule on `enters town` the Section expansion emits (ADR 0015)
  //
  // `town-seen:<section>:c<cycle>` is a story flag, so it is derived here
  // from the Section's own two facts - the flag its vault note records,
  // and the region the descent starts from - and a pack never writes it.
  // The guard is the vault's `sets` flag rather than the warden's, because
  // the ADR wants the visit to mean something: walking through town on the
  // way past is not the same as going home after reading what was kept.
  function ruleFlags() {
    var state = (typeof rulesStateNow === 'function') ? rulesStateNow() : null;
    return (state && isObj(state.flags)) ? state.flags : {};
  }

  function vaultRead(section) {
    var flag = vaultFlag(section);
    if (!flag) return false;
    return flags()[flag] === true || ruleFlags()[flag] === true;
  }

  function markTownSeen(region, leaving) {
    var entry = entryHere();
    if (!entry || entry.region !== String(region)) return [];
    // The cycle is the one the player is walking out of; arriving in town
    // from anywhere else (a landing's stair, a first run) is cycle 0.
    var at = parseName(leaving || '');
    var cycle = at ? at.cycle : 0;
    var set = [];
    sections().forEach(function (s) {
      if (!s || !vaultRead(s)) return;
      var flag = townSeenFlag(s.id, cycle);
      if (flags()[flag] !== true) { setFlag(flag, true); set.push(flag); }
    });
    return set;
  }

  // Returning to town clears what the Section's floors produced - what was
  // killed, taken and dropped there, the mines reset all together - and
  // keeps the memory of where the hero has walked and what they found.
  function returnToTown(name) {
    var doc = loadDoc();
    var changed = false;
    var floors = isObj(doc.floors) ? doc.floors : {};
    for (var i = 0; i < doc.order.length; i++) {
      var record = floors[doc.order[i]];
      if (!isObj(record)) continue;
      var at = parseName(doc.order[i]);
      if (!at || at.section.id !== sectionIdOf(name)) continue;
      if (record.kills.length || record.chests.length || record.drops.length) {
        record.kills = [];
        record.chests = [];
        record.drops = [];
        changed = true;
      }
    }
    if (changed) saveDoc(doc);
  }

  function sectionIdOf(name) {
    var at = parseName(name);
    return at ? at.section.id : '';
  }

  // ---- where a death on a floor leaves the hero ------------------------
  // A floor of the descent is not a place to wake up from. The hero
  // falls, wakes whole on that same floor at its up-stair, and the run
  // goes on - the shape the stair that carried them down already had. So
  // this answers `{region, at}`, and null for anything that is not a
  // floor of the descent: in town, or in a baked region, the pack's own
  // wake point answers exactly as it always has.
  //
  // Nothing is lost on the way: waking is a step back onto the floor,
  // not a redraw of it, so the kills, the drops and the walked ground
  // are the ones the hero left. And the why-log names the floor, so what
  // happened can be read back without watching the screen for it.
  function deathResume(name) {
    if (!on() || !isGenerated(name)) return null;
    var depth = depthOfName(name);
    var plan = depth ? floorPlan(depth) : null;
    if (!plan) return null;
    whySay('descent-death', 'You fell on ' + name + ' and woke at its up '
      + 'stair; the descent is unbroken.');
    return { region: name, at: plan.anchors.up.slice() };
  }

  // The player's why-log (`VEFR_WHY`, the Why panel), in the shape a
  // fired rule writes. Guarded because that part may not be in a file,
  // and a descent that cannot say what it did must still wake the hero
  // where it said it would.
  function whySay(id, text) {
    if (typeof rulesWhyRecord !== 'function') return;
    rulesWhyRecord([{ id: id, why: text }]);
  }

  // A monster fell on `name`. The warden's defeat is a permanent story
  // flag, kept through town returns, identity mismatches and evictions;
  // the record it returns names the key the warden carries, if any, and
  // whether a beaten warden stays on its anchor (Amendment 1 §2). A
  // warden whose challenge is `rule` is not passed by dying - its flag is
  // a pack rule's to set - so its death sets nothing, and the record is
  // still returned so a `yields` one still stands.
  function defeated(name, enemy) {
    if (!on() || !enemy || enemy.warden !== true) return false;
    var depth = depthOfName(name);
    var plan = depth ? floorPlan(depth) : null;
    if (!plan || !plan.warden) return false;
    if (plan.warden.challenge !== 'rule') finishChallenge(plan.warden.flag, name);
    return plan.warden;
  }

  // The one way a warden's flag is ever set, whichever challenge set it:
  // `defeat` when the warden dies, `rule` when a pack rule sets the flag.
  // So "the moment the flag is set, the key goes into the bag with a
  // line, the same as on death" is one piece of work and not two. The
  // vault door sees only the flag and does not change; it is opened in
  // place when the player is standing on the warden's floor, and on the
  // next wire of that floor otherwise, because `wireFloor` reads the
  // same flag.
  function finishChallenge(flag, here) {
    var already = flags()[flag] === true;
    setFlag(flag, true);
    var depth = here ? depthOfName(here) : 0;
    var plan = depth ? floorPlan(depth) : null;
    if (plan && plan.warden && plan.warden.flag === flag) {
      // The same array the player is walking, so no re-entry (which
      // would respawn the floor's monsters).
      var region = (window.VEFR_REGIONS || {})[here];
      if (plan.vault && plan.vault.door && plan.vault.flag === flag && region &&
          Array.isArray(region.map)) {
        var door = plan.vault.door;
        if ((region.map[door[1]] || '')[door[0]] === '+') {
          region.map[door[1]] = withChar(region.map[door[1]], door[0], '.');
        }
      }
    }
    return !already;
  }

  // A pack rule set a flag (`performRuleAction`'s one seam for `set`).
  // ADR 0015 Amendment 1 §2: for a `"challenge": "rule"` warden this is
  // the moment its challenge is complete, so the key it carries goes into
  // the bag with a line, exactly as on death. Every other flag is some
  // other pack's business and is left alone, and a rule that fires twice
  // delivers the key once: the flag being already set is what says so.
  function challengeSet(flag) {
    if (!on() || typeof flag !== 'string' || !flag) return '';
    var at = wardenFlagParts(flag);
    if (!at) return '';
    var warden = null;
    sections().forEach(function (s) {
      var here = wardenOf(s);
      if (here && here.id === at.id) warden = here;
    });
    if (!warden || warden.challenge !== 'rule') return '';
    if (!finishChallenge(flag, currentName)) return '';
    return warden.carries || '';
  }

  // What a bump into the shut vault door on `name` says, or '' for any
  // other tile: the door names who holds its key.
  function shutDoorLine(name, x, y) {
    var depth = on() ? depthOfName(name) : 0;
    var plan = depth ? floorPlan(depth) : null;
    if (!doorShut(plan) || plan.vault.door[0] !== x || plan.vault.door[1] !== y) return '';
    var warden = (plan.mobs || []).filter(function (m) { return m.warden; })[0];
    return 'The vault door is locked. ' + (warden ? warden.name : 'The warden') + ' holds the key.';
  }

  // ---- the story flags, which outlive every floor ---------------------
  function flags() { return loadDoc().flags; }

  function setFlag(flag, value) {
    var doc = loadDoc();
    doc.flags[flag] = (value === undefined) ? true : !!value;
    saveDoc(doc);
  }

  function landings() {
    var value = flags()['landing'];
    return Array.isArray(value) ? value : [];
  }

  function recordLanding(depth) {
    var doc = loadDoc();
    var seen = Array.isArray(doc.flags['landing']) ? doc.flags['landing'] : [];
    if (seen.indexOf(depth) === -1) {
      seen.push(depth);
      seen.sort(function (a, b) { return a - b; });
      doc.flags['landing'] = seen;
      saveDoc(doc);
    }
  }

  // ---- the deltas, read and written by the parts that own them -------
  function loadKills() { return readCurrent('kills', []); }
  function saveKills(ids) { return updateCurrent(function (r) { r.kills = ids; }); }
  function loadChests() { return readCurrent('chests', []); }
  function saveChests(ids) { return updateCurrent(function (r) { r.chests = ids; }); }
  function loadDrops() { return readCurrent('drops', []); }
  function saveDrops(list) { return updateCurrent(function (r) { r.drops = list; }); }
  function loadSecrets() { return readCurrent('secrets', []); }
  function saveSecrets(list) { return updateCurrent(function (r) { r.secrets = list; }); }

  // The explored bitset rides in the same record as everything else, so
  // the cap that keeps the save small keeps the memory too.
  function loadFog() { return readCurrent('fog', ''); }
  function saveFog(text) { return updateCurrent(function (r) { r.fog = text || ''; }); }

  // ---- a new descent --------------------------------------------------
  function resetRegions() {
    var regions = window.VEFR_REGIONS;
    var enemies = window.VEFR_ENEMIES;
    var regionTiles = window.VEFR_REGION_TILES;
    var names = Object.keys(isObj(regions) ? regions : {});
    for (var i = 0; i < names.length; i++) {
      if (!isGenerated(names[i])) continue;
      delete regions[names[i]];
      if (enemies) delete enemies[names[i]];
      if (regionTiles) delete regionTiles[names[i]];
    }
    var list = window.VEFR_TRANSITIONS || [];
    var kept = [];
    for (var j = 0; j < list.length; j++) {
      var t = list[j];
      if (t && isGenerated(t.from) && isGenerated(t.to)) continue;
      kept.push(t);
    }
    window.VEFR_TRANSITIONS = kept;
    wired = {};
  }

  // A new run is the same descent with a fresh seed: run one is the
  // pack's own, and every run after it is counted, so a player never
  // waits on a clock for a new world.
  function startRun(run) {
    var doc = loadDoc();
    var next = isWhole(run) && run >= 0 ? run : doc.run + 1;
    doc.run = next;
    doc.seed = runSeed(baseSeed(), next);
    doc.floors = {};
    doc.order = [];
    saveDoc(doc);
    resetRegions();
    currentName = '';
    wireEntry();
    return next;
  }

  // ---- the one-time gen_version card ----------------------------------
  // A Release 1 save cannot carry generated floors (PLAN §1, item 8), so
  // it is offered the choice once: keep this world as it was, or start
  // over with the floors the pack now carries.
  // The keys Release 1 wrote. `vefr-equipped-` and the fog bitset are
  // deliberately absent: the player writes both on a first run, and a
  // player who has never played is not an old save.
  var CARD_KEYS = ['vefr-bag-', 'vefr-gold-', 'vefr-hp-', 'vefr-library-',
                   'vefr-album-'];

  function oldSaveExists() {
    var name = worldName();
    for (var i = 0; i < CARD_KEYS.length; i++) {
      if (store.get(CARD_KEYS[i] + name) !== null) return true;
    }
    return false;
  }

  function needsCard() {
    if (!on()) return false;
    if (loadDoc().card === GEN_VERSION) return false;
    return oldSaveExists();
  }

  function cardShown() { return cardOpen; }

  var cardOpen = false;

  function showCard() {
    var box = document.getElementById('gen-card');
    if (!box) return false;
    var d = def();
    var line = document.getElementById('gen-card-line');
    if (line) {
      line.textContent = (d && d.card && d.card.note)
        ? d.card.note
        : 'The floors under this world are new. An old save cannot carry them: '
          + 'start over and play the new floors, or keep the world you have.';
    }
    box.hidden = false;
    cardOpen = true;
    var keep = document.getElementById('gen-card-keep');
    if (keep) keep.focus();
    return true;
  }

  function hideCard() {
    var box = document.getElementById('gen-card');
    if (box) box.hidden = true;
    cardOpen = false;
  }

  function keepOldSave() {
    var doc = loadDoc();
    doc.card = GEN_VERSION;
    saveDoc(doc);
    hideCard();
  }

  // Every save this site still holds, or null when the storage cannot be
  // asked at all. A storage that refused a remove leaves its key behind,
  // and a player told their save is gone when it is not is worse off
  // than one who is told the truth.
  function vefrKeysIn(storage) {
    if (!storage || typeof storage.length !== 'number' || typeof storage.key !== 'function') {
      return null;
    }
    var left = [];
    try {
      for (var i = 0; i < storage.length; i++) {
        var k = storage.key(i);
        if (typeof k === 'string' && k.indexOf('vefr-') === 0) left.push(k);
      }
    } catch (e) { return null; }
    return left;
  }

  function sayStartOverFailed(text) {
    var line = document.getElementById('gen-card-line');
    if (line) line.textContent = text;
    var box = document.getElementById('gen-card');
    if (box) box.hidden = false;
    cardOpen = true;
  }

  // A Start over clears every vefr- key on this site, and a clear cannot
  // be taken back - so the browser is asked to STORE a save first, and
  // the answer is read back rather than taken on trust. `store.setJSON`
  // gives up quietly when storage is full or blocked, so a write that
  // returned is not a write that happened; clearing on top of one of
  // those erases the only copy of the game and leaves nothing behind,
  // without a word to the player.
  //
  // The save written here is the new game's: this generation's mark, no
  // floors, the same seed. It is the save the reload would write anyway;
  // writing it first is what makes the clear safe.
  function freshSave() {
    var doc = freshDoc();
    doc.card = GEN_VERSION;
    return doc;
  }

  // Whether the new save is really in storage afterwards, not merely
  // handed over to a store that swallowed it.
  function storedSave(doc) {
    var written = null;
    try { written = saveDoc(doc); } catch (e) { return false; }
    if (!isObj(written)) return false;
    var back = store.getJSON(docKey(), null);
    if (!isObj(back)) return false;
    return JSON.stringify(back) === JSON.stringify(written);
  }

  function startOver() {
    var before = loadDoc();
    if (!storedSave(freshSave())) {
      sayStartOverFailed('Your saved game could not be cleared: this browser '
        + 'would not store a new save, so clearing the old one would leave '
        + 'you with nothing at all. Nothing has been cleared and nothing '
        + 'has been lost. Free some space, or allow this site to store '
        + 'data, then try Start over again.');
      return false;
    }
    var storage = store.raw();
    try { window.startoverKeys(storage); } catch (e) { /* read below says what is left */ }
    var left = vefrKeysIn(storage);
    if (left === null || left.length) {
      // The clear did not finish, so this was not a Start over: what was
      // about to be erased goes back where it was, and the refusal is
      // said. The message has always promised nothing was lost.
      putBack(before);
      if (left === null) {
        sayStartOverFailed('Your saved game could not be checked, so nothing has '
          + 'been cleared and nothing has been lost. Clear this site\'s saved '
          + 'game in your browser, then try Start over again.');
      } else {
        sayStartOverFailed('Your saved game could not be cleared: this browser '
          + 'would not let the game remove ' + left.length
          + (left.length === 1 ? ' save.' : ' saves.')
          + ' Nothing has been lost. Clear this site\'s saved game in your '
          + 'browser, then try Start over again.');
      }
      return false;
    }
    hideCard();
    window.location.reload();
    return true;
  }

  // The save that was there before a clear that did not finish. It goes
  // back through `saveDoc`, so the documented order of sacrifice still
  // decides what a too-large save keeps.
  function putBack(doc) {
    try { saveDoc(doc); } catch (e) { /* nothing left to say: the refusal above stands */ }
  }

  function offerCard() {
    if (!on()) return false;
    var doc = loadDoc();
    if (sweepIdentities(doc)) saveDoc(doc);
    if (needsCard()) return showCard();
    markGeneration();
    hideCard();
    return false;
  }

  // ---- the New-descent control ---------------------------------------
  function bindCard() {
    var keep = document.getElementById('gen-card-keep');
    var over = document.getElementById('gen-card-over');
    if (keep && !keep.dataset.bound) {
      keep.dataset.bound = '1';
      keep.addEventListener('click', keepOldSave);
    }
    if (over && !over.dataset.bound) {
      over.dataset.bound = '1';
      over.addEventListener('click', startOver);
    }
  }

  function bindDescent() {
    bindCard();
    var item = document.getElementById('menu-descent');
    var body = document.getElementById('descent-body');
    var line = document.getElementById('descent-line');
    var fresh = document.getElementById('descent-new');
    var row = document.getElementById('menu-descent-row');
    if (!on()) {
      // A pack that carries no descent has no descent to offer: the menu
      // item is not shown at all, rather than shown and refused.
      if (row) row.hidden = true;
      return false;
    }
    if (row) row.hidden = false;
    var render = function () {
      if (!line) return;
      var doc = loadDoc();
      var deepest = 0;
      for (var i = 0; i < doc.order.length; i++) {
        var record = doc.floors[doc.order[i]];
        if (isObj(record) && isWhole(record.n) && record.n > deepest) {
          deepest = record.n;
        }
      }
      line.textContent = 'Run ' + (doc.run + 1) + ' of the descent (' + doc.seed +
        '). Deepest floor reached: ' + deepest + '. A new descent starts the '
        + 'same Sections over with a fresh seed.';
      // A save that could not be stored is said first, while it is true.
      if (lastRefusal) line.textContent = lastRefusal;
    };
    render();
    if (item) {
      item.addEventListener('click', function () {
        render();
        if (fresh) fresh.focus();
      });
    }
    if (fresh) {
      fresh.addEventListener('click', function () {
        startRun();
        render();
        if (window.closeMenu) window.closeMenu();
        var first = locate(1);
        if (first) enterDescentFloor(1);
      });
    }
    return true;
  }

  // The one way into the deep that is not a stair on a floor: the
  // control itself, for a player who wants the next run now.
  function enterDescentFloor(depth) {
    var plan = floorPlan(depth);
    if (!plan) return false;
    ensureRegion(plan.name);
    if (typeof window.VEFR_ENTER_REGION === 'function') window.VEFR_ENTER_REGION(plan.name, null);
    return true;
  }

  function floor() {
    if (!currentName) return null;
    var depth = depthOfName(currentName);
    return depth ? floorPlan(depth) : null;
  }

  function markGeneration() {
    // The save declares which generation wrote it. A pack with no descent
    // never writes one, so a pack without a descent is exactly as it was.
    var doc = loadDoc();
    if (doc.card === GEN_VERSION) return false;
    doc.card = GEN_VERSION;
    saveDoc(doc);
    return true;
  }

  // Every remembered floor is checked against the floor this pack would
  // draw now, once, when the game starts. One that no longer matches is
  // dropped whole - it will be drawn again, and it is not the floor the
  // save was about. The story flags are never touched: a save that has
  // lost a floor has not lost the world.
  function sweepIdentities(doc) {
    var changed = false;
    var names = Array.isArray(doc.order) ? doc.order.slice() : [];
    for (var i = 0; i < names.length; i++) {
      var name = names[i];
      var at = parseName(name);
      var record = isObj(doc.floors) ? doc.floors[name] : null;
      if (!at || !isObj(record)) continue;
      var depth = depthOfName(name);
      if (!depth) continue;
      // `at.section` is the section OBJECT (see parseName); floorKey
      // concatenates its sectionId argument, so passing the object made
      // this key `run-a/[object Object]/0/1`, which never matched the
      // stored key and emptied every floor record on every load - the
      // kill list, the chests, the drops and the explored bitset with
      // it. The plan path takes `.id` (planFor, :251 area); so does
      // sectionIdOf, :704. Same accessor, same reason.
      var key = floorKey(seedFor(doc.run), at.section.id, at.cycle, at.k);
      if (record.h === sectionHash(at.section) && record.g === GEN_VERSION &&
          record.k === key) {
        continue;
      }
      // Not the floor the save was about: it is drawn again, so its
      // deltas are meaningless and go. What it *was* - how deep it was,
      // which Section - is kept, so the journal still reads true.
      doc.floors[name] = {
        g: GEN_VERSION, h: sectionHash(at.section), k: key,
        n: isWhole(record.n) ? record.n : depth, s: at.section,
        kills: [], chests: [], drops: [], secrets: [], fog: ''
      };
      changed = true;
    }
    return changed;
  }

  var api = {
    on: on, GEN_VERSION: GEN_VERSION, FLOOR_CAP: FLOOR_CAP,
    defeated: defeated, wardenFlag: wardenFlag, shutDoorLine: shutDoorLine,
    challengeSet: challengeSet,
    FLOOR_BYTES: FLOOR_BYTES, SAVE_BYTES: SAVE_BYTES,
    locate: locate, floorName: floorName, floorKey: floorKey,
    streamSeed: streamSeed, lootSeed: lootSeed, chestSeed: chestSeed,
    runSeed: runSeed, sectionHash: sectionHash, parseName: parseName,
    baseSeed: baseSeed, seedParam: seedParam, seedFor: seedFor,
    isGenerated: isGenerated, depthOfName: depthOfName, floorPlan: floorPlan,
    floorSize: floorSize, floorKindOf: floorKindOf, mobsAt: mobsAt, mobDrops: mobDrops, placeBooks: placeBooks,
    xpFor: xpFor,
    ensureRegion: ensureRegion, onEnter: onEnter, entryHere: entryHere,
    wireEntry: wireEntry, docKey: docKey, deathResume: deathResume,
    loadDoc: loadDoc, saveDoc: saveDoc, trimDoc: trimDoc, fitDoc: fitDoc,
    saveRefusal: saveRefusal,
    docBytes: bytesOf, floorBytes: floorBytes,
    loadKills: loadKills, saveKills: saveKills,
    loadChests: loadChests, saveChests: saveChests,
    loadDrops: loadDrops, saveDrops: saveDrops,
    loadSecrets: loadSecrets, saveSecrets: saveSecrets,
    loadFog: loadFog, saveFog: saveFog,
    flags: flags, setFlag: setFlag, landings: landings,
    recordLanding: recordLanding,
    // E8c: the story end, the town gate and the act, all derived reads.
    // `storyFlags` is how the ONE gate mechanism (`lockOpen`) sees a
    // story flag, which lives in the descent's own save beside the floors.
    storyEnd: storyEnd, townSeenFlag: townSeenFlag, vaultFlag: vaultFlag,
    townGate: townGate, markTownSeen: markTownSeen, actNumber: actNumber,
    storyFlags: function (flag) { return !!flag && flags()[flag] === true; },
    needsCard: needsCard, cardShown: cardShown, offerCard: offerCard,
    keepOldSave: keepOldSave, startOver: startOver,
    bindDescent: bindDescent, startRun: startRun,
    enterDescentFloor: enterDescentFloor,
    markGeneration: markGeneration, sweepIdentities: sweepIdentities
  };
  // `doc` and `floor` are values, not calls, read at the moment they are
  // asked for: a harness (and the debug console) can look at the save and
  // at the floor the hero is standing on without reaching for a function.
  Object.defineProperty(api, 'doc', { get: loadDoc });
  Object.defineProperty(api, 'floor', { get: floor });
  return api;
})();
