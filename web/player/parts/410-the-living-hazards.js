  // ---- the living hazards ----
  // Each region's enemies ride in baked (`window.VEFR_ENEMIES`, one
  // list per region). A slain enemy is remembered per region, per
  // world, so a cleared room stays cleared; a wounded one resets on
  // reload. Combat is deterministic: fixed numbers, no randomness, no
  // clock. Enemy sight is Manhattan distance.
  var enemiesByRegion = window.VEFR_ENEMIES || {};
  var enemies = [];

  function slainKey() {
    var w = (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
    return 'vefr-slain-' + w + '-' + regionName;
  }
  // A generated floor remembers its kills in the descent's own save,
  // beside its explored bitset, because a floor that was never baked is
  // not a region name anyone kept a key for.
  function descentOn() {
    return !!(window.VEFR_DESCENT && window.VEFR_DESCENT.isGenerated(regionName));
  }
  function loadSlain() {
    if (descentOn()) return window.VEFR_DESCENT.loadKills();
    var a = store.getJSON(slainKey(), []);
    return Array.isArray(a) ? a : [];
  }
  function saveSlain() {
    if (descentOn()) {
      var names = [];
      for (var i = 0; i < enemies.length; i++) {
        if (enemies[i] && !enemies[i].alive) names.push(enemies[i].id);
      }
      window.VEFR_DESCENT.saveKills(names);
      return;
    }
    var dead = enemies.filter(function (e) { return !e.alive; })
      .map(function (e) { return e.id + '#' + (e.sig || ''); });
    store.setJSON(slainKey(), dead);
  }
  // A monster is remembered by what it *is*, not only by its name: move it,
  // restat it, or regenerate the floor, and it is a new monster again. So a
  // rebuild never leaves a floor mysteriously empty.
  //
  // That is what a BAKED region needs, because its kill list is a flat
  // storage key with nothing else in it: the signature is the only thing
  // there that can tell a rebuilt floor from the floor that was played.
  //
  // A generated floor already carries that answer, and carries it better:
  // the descent's own record is keyed by the floor's identity triple - gen
  // version, section content hash, floor key - and PLAN §2's per-floor save
  // is "killed mob ids", nothing else. So on a generated floor the id IS
  // the whole of the memory, and matching it against a signature compares
  // "m0" with "m0#a pale moth|13,15|1|1|" and never matches: every kill on
  // every floor that was never baked was forgotten the moment the page was
  // reloaded, which is the one thing a kill list exists to stop.
  function slainKeyFor(id, sig, generated) {
    return generated ? id : id + '#' + sig;
  }
  function enemySig(raw) {
    // A drop is the bare id it always was, or the instance a generated
    // floor drew (ADR 0017) - which the signature names by its id and its
    // rarity, so two rolls of the same thing are still two signatures.
    var drops = (Array.isArray(raw.drops) ? raw.drops : []).map(function (d) {
      return (typeof d === 'string') ? d
        : ((d && d.item ? d.item : '') + ':' + (d && d.rarity ? d.rarity : ''));
    }).join(',');
    return [raw.name, (Array.isArray(raw.at) ? raw.at.join(',') : ''),
            raw.hp, raw.atk, drops].join('|');
  }
  // A baked foe's `gold`: a drawn number on a generated floor, a `[lo, hi]`
  // on a hand-placed one (paid as its low end - no draw is spent outside the
  // descent's own streams), and 0 when it names none.
  function goldOfFoe(g) {
    if (typeof g === 'number' && g > 0) return Math.floor(g);
    if (Array.isArray(g) && typeof g[0] === 'number' && g[0] > 0) return Math.floor(g[0]);
    return 0;
  }
  function loadEnemies() {
    var dead = loadSlain();
    var generated = descentOn();
    var list = enemiesByRegion[regionName] || [];
    enemies = list.map(function (e) {
      var sig = enemySig(e);
      return {
        id: e.id, name: e.name, sprite: e.sprite || '',
        sig: sig,
        at: Array.isArray(e.at) ? e.at.slice() : [0, 0],
        hp: (typeof e.hp === 'number') ? e.hp : 1,
        // The health it walked in with, kept so "badly hurt" means a
        // third of that and not a number someone typed into a pack.
        hp0: (typeof e.hp === 'number') ? e.hp : 1,
        atk: (typeof e.atk === 'number') ? e.atk : 1,
        sight: (typeof e.sight === 'number') ? e.sight : 6,
        // The xp this foe is worth, in levels mode (design/growth.md).
        // A pack without it reads as zero: defeat still plays as before.
        xp: (typeof e.xp === 'number') ? e.xp : 0,
        drops: Array.isArray(e.drops) ? e.drops.slice() : [],
        // What a blow at it loses, and the coins it pays (ADR 0021): 0 and
        // none for a record that names neither, which is the old fight.
        guard: (typeof e.guard === 'number' && e.guard > 0) ? e.guard : 0,
        gold: goldOfFoe(e.gold),
        // ADR 0015 Amendment 1 §2, read here rather than at the fight:
        // `fightable` is what refuses a blow and `yields` is what leaves
        // a beaten warden standing, and both have to be on the record
        // before the player can touch anything.
        fightable: e.fightable !== false,
        yields: e.yields === true,
        // What this blow IS, and what it leaves behind (vefr#497): the
        // damage type the hero's resistances may turn aside, and the
        // burning it inflicts. A contract that named neither reads as
        // '' and null here, and the fight is then the untyped one it
        // always was.
        dmgType: normalDamageType(e.dmg_type),
        burns: (e.burns && typeof e.burns === 'object'
                && typeof e.burns.turns === 'number' && e.burns.turns >= 1
                && typeof e.burns.tick === 'number' && e.burns.tick >= 1)
               ? { effect: 'burning', type: 'fire', turns: e.burns.turns,
                   tick: e.burns.tick }
               : null,
        // What it can do besides walk up and bite (ADR 0024), and the turns
        // each ranged skill still waits; a record with none has [] here
        // and fights the fight it always fought.
        // (Guarded: a harness may load the monster parts without the RPG core.)
        skills: (typeof rpgSkillsOf === 'function') ? rpgSkillsOf(e) : [],
        skillWait: {},
        squealed: false,
        // A yielding warden that is on the roster at all has already
        // yielded: the descent puts one here only once its challenge
        // flag is set, and it is not a living hazard from then on - it
        // is a thing still standing where it stood.
        alive: e.yields !== true
               && dead.indexOf(slainKeyFor(e.id, sig, generated)) === -1
      };
    });
  }
  function enemyAt(x, y) {
    for (var i = 0; i < enemies.length; i++) {
      var e = enemies[i];
      if (e && e.alive && e.at[0] === x && e.at[1] === y) return e;
    }
    return null;
  }
  function tileOpenForEnemy(x, y) {
    if (y < 0 || x < 0 || y >= town.map.length || x >= town.map[0].length) return false;
    if ((town.legend[town.map[y][x]] || {}).solid) return false;
    // The props part may be absent (a harness that loads only the monster parts).
    if (typeof propBlocked === 'function' && propBlocked(x, y)) return false;
    if (x === hero[0] && y === hero[1]) return false;
    return !enemyAt(x, y);
  }
  function manhattan(x1, y1, x2, y2) {
    return Math.abs(x1 - x2) + Math.abs(y1 - y2);
  }

