  // ---- loot on the floor ----
  // A killed enemy leaves what it carried on the tile it died on; the
  // floor is remembered per world (`vefr-floor-<world>`, one list of
  // {region, at, item}) so leaving and coming back is honest about what
  // is still lying there. A drop a generated floor drew also carries the
  // rarity it was drawn at and the traits it is hiding (ADR 0017), and
  // the bag keeps that instance rather than drawing it again. Taking a
  // drop removes it. No weight, no use, no drop, no sell; a trait stays
  // hidden on the floor and in the bag until the town's identify service
  // reads it (`195-the-identify-service.js`).
  var floor = [];

  function floorKey() {
    var w = (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world';
    return 'vefr-floor-' + w;
  }
  // What one drop record is, wherever it is being written: the three
  // fields every drop has always had, plus the drawn instance a rolled
  // drop carries (ADR 0017). A drop that carries no rarity and no traits
  // is written as the three fields alone, so a pack that declares no
  // `roll` saves and reloads exactly the bytes it always did.
  function dropRecord(d) {
    var out = { region: regionName, at: d.at.slice(), item: d.item };
    var traits = (d.traits && d.traits.length) ? d.traits : null;
    if (d.rarity || traits) {
      out.rarity = d.rarity || '';
      out.traits = traits ? traits.slice() : [];
      out.identified = d.identified === true;
    }
    return out;
  }
  // The instance a drop is, read one way: a rolled record as itself, and
  // a bare id (a town enemy, a chest, a rule) with whatever the catalog
  // fixed on it - a fixed `rarity`/`traits` ride along unchanged, because
  // a drop with no floor to seed it is never drawn from.
  function dropInstance(d) {
    if (d && typeof d === 'object' && !Array.isArray(d)) {
      return { id: d.item, rarity: d.rarity || '',
               traits: Array.isArray(d.traits) ? d.traits : [] };
    }
    var def = itemCatalog()[d];
    return { id: d, rarity: (def && typeof def.rarity === 'string') ? def.rarity : '',
             traits: (def && Array.isArray(def.traits)) ? def.traits : [] };
  }
  function loadFloor() {
    // A generated floor keeps its drops in its own delta record: with the
    // tile they lie on, and never the floor they lie on.
    if (window.VEFR_DESCENT && window.VEFR_DESCENT.isGenerated(regionName)) {
      floor = window.VEFR_DESCENT.loadDrops();
      floor = Array.isArray(floor) ? floor.filter(function (d) {
        return d && typeof d.item === 'string' && Array.isArray(d.at)
          && d.at.length === 2 && itemCatalog()[d.item];
      }) : [];
      return;
    }
    var a = store.getJSON(floorKey(), []);
    floor = Array.isArray(a) ? a.filter(function (d) {
      return d && typeof d.item === 'string' && typeof d.region === 'string'
        && Array.isArray(d.at) && d.at.length === 2 && itemCatalog()[d.item];
    }) : [];
  }
  function saveFloor() {
    if (window.VEFR_DESCENT && window.VEFR_DESCENT.isGenerated(regionName)) {
      window.VEFR_DESCENT.saveDrops(floor.map(dropRecord));
      return;
    }
    store.setJSON(floorKey(), floor);
  }
  function dropsAt(x, y) {
    return floor.filter(function (d) {
      return d.region === regionName && d.at[0] === x && d.at[1] === y;
    });
  }
  // Leave a killed enemy's drops where it died. A drop is either the
  // record a generated floor drew (with its rarity and its hidden traits,
  // ADR 0017) or a bare id, which takes whatever the catalog fixed on it.
  // Only a catalog item is placed; the bake already dropped an unknown id.
  function placeDrops(at, ids) {
    var added = false;
    (ids || []).forEach(function (entry) {
      var inst = (entry && typeof entry === 'object' && !Array.isArray(entry))
        ? { id: entry.item, rarity: entry.rarity || '',
            traits: Array.isArray(entry.traits) ? entry.traits : [] }
        : dropInstance(entry);
      if (!inst.id || !itemCatalog()[inst.id]) return;
      floor.push(dropRecord({
        region: regionName, at: [at[0], at[1]], item: inst.id,
        rarity: inst.rarity, traits: inst.traits, identified: false }));
      added = true;
    });
    if (added) saveFloor();
  }
  // Walking onto a drop takes every item lying on that tile. One plain
  // line says what was taken - the thing and its rarity, at once, with
  // nothing to wait for - and the bag panel and the strip redraw. A drop
  // a full bag refuses stays on the floor, and the same line says so; a
  // drop whose id the catalog lost is dropped as it always was.
  function takeHere() {
    takeSatchelHere();
    var here = dropsAt(hero[0], hero[1]);
    if (!here.length) return;
    var names = [];
    var left = [];
    var picked = [];
    // One `picks-up` per item actually bagged.
    here.forEach(function (d) {
      var inst = dropInstance(d);
      if (bagAdd(inst.id, inst)) {
        picked.push(inst);
        names.push(carriedName(inst));
        fireRule('picks-up', { what: inst.id });
      } else if (itemCatalog()[inst.id]) {
        left.push(d);
      }
    });
    floor = floor.filter(function (d) {
      var onTile = d.region === regionName
        && d.at[0] === hero[0] && d.at[1] === hero[1];
      return !onTile || left.indexOf(d) !== -1;
    });
    saveFloor();
    var said = [];
    if (names.length) {
      playOneShot('hero', 'act');
      soundCue('pickup');
      said.push('You pick up ' + names.join(', ') + '.');
    }
    if (left.length) {
      said.push('Your bag is full. You leave ' + left.map(function (d) {
        return itemName(dropInstance(d).id);
      }).join(', ') + ' on the floor.');
    }
    if (said.length) combatSay(said.join(' '));
    // ADR 0023 (`display.wear_prompt`): the first thing just picked up that
    // would raise one of the hero's numbers asks to be worn.
    for (var i = 0; i < picked.length; i++) {
      if (offerToWear({ id: picked[i].id, rarity: picked[i].rarity || '',
                        traits: picked[i].traits.slice(), identified: false })) break;
    }
  }
  window.VEFR_TAKE_HERE = takeHere;
  // The satchel a fall left (ADR 0021): walking onto it takes every thing
  // in it back, whatever the bag's room - it was the hero's already.
  function takeSatchelHere() {
    var D = window.VEFR_DESCENT;
    var sat = (D && typeof D.satchelIn === 'function') ? D.satchelIn(regionName) : null;
    if (!sat || sat.at[0] !== hero[0] || sat.at[1] !== hero[1]) return;
    var items = D.takeSatchel();
    var raw = store.getJSON(BAG_KEY, []);
    store.setJSON(BAG_KEY, (Array.isArray(raw) ? raw : []).concat(items));
    renderBagPanel();
    renderBagStrip();
    renderVerbRow();
    syncCombat();
    playOneShot('hero', 'act');
    soundCue('pickup');
    combatSay('You find your satchel. Everything you carried is back.');
  }
  window.VEFR_HERO_SPOT = function () {
    return { region: regionName, at: [hero[0], hero[1]] };
  };

  // A hero bump: strike the enemy on the tile you tried to walk into.
  // `bonus` is what the hero is carrying adds to this one blow (the
  // item-grants slice): the verb the blow came through decides it, and
  // a plain bump carries none.
  //
  // ADR 0021, each part opt-in: a pack with a `fight` block rolls the blow
  // (a miss, or a critical multiplied by `crit_times`) from its own named
  // stream; the foe's `guard` takes from the blow, never below 1; and the
  // traits the hero bears may react - `opener` on an unhurt foe, `sting` on
  // a miss, `kill_heal` and the foe's `gold` on a kill. Every one of them is
  // said in the same sentence the blow speaks. A pack with none of it rolls
  // nothing and the blow is the one that always landed.
  function heroAttack(e, bonus) {
    // ADR 0015 Amendment 1 §2: a warden with `"fightable": false` cannot
    // be attacked. The blow never lands, makes no noise and spends no
    // turn - there is no fight to have with it - and one plain line says
    // so. Everything else about such a warden is unchanged: it still
    // sleeps, wakes and hunts, so the hall stays dangerous.
    if (!e || e.fightable === false) {
      combatSay('You cannot strike ' + ((e && e.name) || 'it') + '.');
      return false;
    }
    // The blow lands, so this is a fight: say once, here, that walking
    // into an enemy is the attack (vefr #464). A warden that cannot be
    // struck returns above, because there was no fight to teach.
    hintStrikeOnce();
    var totals = rpgTraitTotals();
    var roll = rpgRoll(regionName, 'hero', e.id, totals.crit, heroMissBonus());
    playOneShot('hero', 'attack');
    wakeOne(e);
    makeNoise('fight');
    if (roll && roll.miss) {
      // A miss is still a swing: it spends the turn and wakes the floor.
      var missed = verbWord('miss', { what: e.name });
      var sting = totals.reactions.sting;
      if (sting && HERO_HP > 1) {
        var stung = Math.min(sting.n, HERO_HP - 1);
        HERO_HP -= stung;
        saveHeroHp();
        renderHp();
        missed += ' ' + itemName(sting.from) + ' stings you for ' + stung + '.';
        hitAt(null, '-' + stung, 'hurt');
      }
      hitAt(e.at, 'miss', 'miss');
      combatSay(missed);
      combatSnapshot();
      return true;
    }
    // Through the one resolver (vefr#497), on the hero's side as well as
    // the hazard's - a resolver on one side only is how fire turns aside
    // and poison does not. The hero's own blow is untyped for now: a
    // hazard's `dmg_type` is what it DEALS, not what it takes, and the
    // pack contract has no key for the second yet. A hazard that
    // declares no resistance answers with its own number, so this is the
    // blow that always landed.
    // An item-granted verb's bonus (Mending Shift E1) is added before the resolver, so a resistance
    // answers the whole blow.
    var amount = heroAtk()
      + ((typeof bonus === 'number' && isFinite(bonus) && bonus > 0) ? Math.round(bonus) : 0);
    var crit = !!(roll && roll.crit);
    if (crit) amount *= roll.times;
    var opener = totals.reactions.opener;
    var opened = !!(opener && e.hp >= (e.hp0 || e.hp));
    if (opened) amount *= opener.n;
    var dmg = rpgGuarded(resolveDamage(amount, '', e.resist, e.immune).damage, e.guard);
    e.hp = Math.max(0, e.hp - dmg);
    playOneShot('enemy:' + e.id, 'hurt');
    soundCue('hit');
    hitAt(e.at, crit ? 'CRIT ' + dmg : String(dmg), crit ? 'crit' : 'hit');
    // The blow says itself in one sentence, from the same message
    // table every other player line comes from (#463) - the bytes are
    // the ones this always read.
    var said = verbWord(crit ? 'crit' : 'attack', { what: e.name, damage: String(dmg) });
    if (opened) said += ' ' + itemName(opener.from) + ' makes the first blow count.';
    // A landed blow is one practice count; levels mode ignores it.
    sayGrowth(practiceSuffix(growBump('strikes')));
    if (e.hp <= 0) said += foeFalls(e, totals);
    else said += squealIfHurt(e);
    combatSay(said);
    combatSnapshot();
    return true;
  }
  // Everything a foe's death does, whatever felled it - a blow or a spell:
  // the slain record, a warden's yield and key, the drops, the `defeats`
  // event, the coins and a trait that warms the hero (ADR 0021), then the
  // xp. Returns the words to add to the line that felled it.
  function foeFalls(e, totals) {
    totals = totals || rpgTraitTotals();
    e.alive = false;
    saveSlain();
    var beaten = (window.VEFR_DESCENT && window.VEFR_DESCENT.defeated)
      ? window.VEFR_DESCENT.defeated(regionName, e) : false;
    // A warden that `yields` (ADR 0015 Amendment 1 §2) stays on its
    // anchor, no longer hostile, instead of vanishing: it is not alive
    // any more - nothing attacks it and it attacks nothing - but it is
    // still drawn, still where it stood, and it comes back the same way
    // when the floor is rebuilt.
    if (beaten && beaten.yields === true) {
      e.yields = true;
      if (Array.isArray(e.spawn)) e.at = e.spawn.slice();
    }
    // A warden's key goes straight into the bag, so it cannot be lost
    // on the floor (ADR 0015). The key follows the FLAG, not the death:
    // a `"challenge": "rule"` warden (Amendment 1 §2) is not passed by
    // dying, so nothing is handed over until its rule sets the flag.
    var passed = !!(beaten && window.VEFR_DESCENT
                    && window.VEFR_DESCENT.storyFlags
                    && window.VEFR_DESCENT.storyFlags(beaten.flag));
    var keyLine = (passed && beaten.carries && bagAdd(beaten.carries, null, true))
      ? ' You take ' + itemName(beaten.carries) + '; it is in your bag.' : '';
    soundCue('defeat');
    placeDrops(e.at, e.drops);
    fireRule('defeats', { what: e.id });
    var said = ' ' + e.name + ' falls.' + keyLine;
    if (e.gold > 0) {
      addGold(e.gold);
      said += ' ' + verbWord('gold', { amount: String(e.gold) });
    }
    var warm = totals.reactions.kill_heal;
    if (warm && HERO_HP < heroMax()) {
      var before = HERO_HP;
      HERO_HP = Math.min(heroMax(), HERO_HP + warm.n);
      saveHeroHp();
      renderHp();
      said += ' ' + itemName(warm.from) + ' warms you: you recover '
        + (HERO_HP - before) + ' health.';
    }
    // The defeat line first, then the xp it was worth, then any level.
    var r = growAward(e.xp);
    if (typeof e.xp === 'number' && e.xp > 0) {
      sayGrowth('You earn ' + e.xp + ' ' + XP_WORD + '.');
    }
    if (r && r.grew && r.levelsGained) soundCue('level');
    sayGrowth(levelSuffix(r));
    return said;
  }
  // A spell's harm (ADR 0021): at the foe the fight row named, else the
  // nearest living one within `range` tiles (the spells part reads it),
  // nearest first and then the roster's own order. Guard does not answer
  // it - magic is the build that walks past armour. A spell with nothing in
  // reach returns null and the cast does not happen. Returns its words.
  function spellHarm(spell, target, range) {
    var foe = (target && target.alive && target.fightable !== false) ? target : null;
    if (!foe) {
      var best = -1;
      for (var i = 0; i < enemies.length; i++) {
        var e = enemies[i];
        if (!e || !e.alive || e.fightable === false) continue;
        var d = chebyshev(e.at[0], e.at[1], hero[0], hero[1]);
        if (d > range) continue;
        if (best === -1 || d < best) { best = d; foe = e; }
      }
    }
    if (!foe) return null;
    var dmg = resolveDamage(spell.harm, '', foe.resist, foe.immune).damage;
    foe.hp = Math.max(0, foe.hp - dmg);
    hitAt(foe.at, String(dmg), 'spell');
    wakeOne(foe);
    makeNoise('fight');
    playOneShot('enemy:' + foe.id, 'hurt');
    soundCue('hit');
    var said = 'It strikes ' + foe.name + ' for ' + dmg + '.';
    if (foe.hp <= 0) said += foeFalls(foe);
    else said += squealIfHurt(foe);
    combatSay(said);
    combatSnapshot();
    flushGrowth();
    return said;
  }
  window.VEFR_SPELL_HARM = spellHarm;

  // ---- monster skills and throwing (ADR 0024) ----
  // A clear line from one tile to another: every tile between them (not
  // the two ends) is open ground with no monster on it, walked the way a
  // straight line is drawn on a grid. A web, a spit and a thrown thing all
  // need one, so a wall or another monster stands in the way of each.
  function clearLine(x0, y0, x1, y1) {
    var dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
    var sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    var err = dx - dy, x = x0, y = y0;
    while (true) {
      var e2 = 2 * err;
      if (e2 > -dy) { err -= dy; x += sx; }
      if (e2 < dx) { err += dx; y += sy; }
      if (x === x1 && y === y1) return true;
      if ((town.legend[town.map[y][x]] || {}).solid) return false;
      if (typeof propBlocked === 'function' && propBlocked(x, y)) return false;
      if (enemyAt(x, y)) return false;
    }
  }
  function skillOf(e, kind) {
    var list = (e && e.skills) || [];
    for (var i = 0; i < list.length; i++) if (list[i].skill === kind) return list[i];
    return null;
  }
  // Each of the monster's own turns brings a waiting skill one turn nearer.
  function skillsTick(e) {
    var wait = e.skillWait || {};
    for (var k in wait) if (wait.hasOwnProperty(k) && wait[k] > 0) wait[k]--;
  }
  // A web or a spit at a hero within its range on a clear line, when the
  // skill is not still waiting. Answers whether the hero fell, or null when
  // no skill was used (the monster then walks as it always did).
  function rangedSkill(e) {
    var reach = chebyshev(e.at[0], e.at[1], hero[0], hero[1]);
    e.skillWait = e.skillWait || {};
    var kinds = ['web', 'spit'];
    for (var i = 0; i < kinds.length; i++) {
      var sk = skillOf(e, kinds[i]);
      if (!sk || reach > sk.range || e.skillWait[sk.skill] > 0) continue;
      if (!clearLine(e.at[0], e.at[1], hero[0], hero[1])) continue;
      e.skillWait[sk.skill] = sk.every;
      playOneShot('enemy:' + e.id, 'attack');
      if (sk.skill === 'web') {
        var held = applyHeroStatus({ effect: 'webbed', turns: sk.turns });
        combatSay(e.name + ' throws a web over you: you are stuck for ' + sk.turns
          + (sk.turns === 1 ? ' turn.' : ' turns.'));
        if (held) hitAt(null, 'webbed', 'miss');
        return false;
      }
      var roll = rpgRoll(regionName, e.id, 'hero', 0);
      if (roll && roll.miss) {
        hitAt(null, 'miss', 'miss');
        combatSay(e.name + ' spits at you and misses.');
        return false;
      }
      var hurt = rpgGuarded(sk.harm, heroGuard());
      HERO_HP = Math.max(0, HERO_HP - hurt);
      saveHeroHp();
      renderHp();
      hitAt(null, '-' + hurt, 'hurt');
      soundCue('hurt');
      combatSay(e.name + ' spits at you for ' + hurt + '.');
      if (HERO_HP <= 0) { cozyDeath(e); return true; }
      return false;
    }
    return null;
  }
  // A festering bite, dust in the eyes: each with its own chance, drawn
  // from its own stream. Answers the words to add to the blow's line.
  function onHitSkills(e) {
    var said = '';
    var fester = skillOf(e, 'fester');
    if (fester && rpgSkillRoll(regionName, e.id, 'fester') < fester.chance) {
      var f = applyHeroStatus({ effect: 'festering', type: 'poison', turns: fester.turns,
                                tick: fester.tick });
      if (f && f.fresh) said += ' The bite festers: ' + fester.tick + ' a turn for ' + fester.turns
        + (fester.turns === 1 ? ' turn.' : ' turns.');
    }
    var dust = skillOf(e, 'dust');
    if (dust && rpgSkillRoll(regionName, e.id, 'dust') < dust.chance) {
      var d = applyHeroStatus({ effect: 'dusted', turns: dust.turns, miss: dust.miss });
      if (d && d.fresh) said += ' Dust gets in your eyes: your blows go wide for ' + dust.turns
        + (dust.turns === 1 ? ' turn.' : ' turns.');
    }
    return said;
  }
  // The first time a monster with `squeal` is struck to half its health or
  // below and still stands, it squeals: every monster within the radius
  // wakes and comes. Once a life. Answers the words to add to the line.
  function squealIfHurt(e) {
    var sk = skillOf(e, 'squeal');
    if (!sk || e.squealed || !e.alive || e.hp > (e.hp0 || e.hp) / 2) return '';
    e.squealed = true;
    var woke = 0;
    for (var i = 0; i < enemies.length; i++) {
      var o = enemies[i];
      if (!o || o === e || !o.alive) continue;
      if (chebyshev(o.at[0], o.at[1], e.at[0], e.at[1]) > sk.radius) continue;
      if (!o.awake) woke++;
      wakeOne(o);
    }
    soundCue('hurt');
    return ' ' + e.name + ' squeals for help' + (woke ? '!' : ', and nothing answers.');
  }
  // The first carried thing that can be thrown, in the pack's own order.
  function throwableId() {
    var cat = itemCatalog();
    var carried = bagItems();
    var ids = Object.keys(cat);
    for (var i = 0; i < ids.length; i++) {
      if (carried.indexOf(ids[i]) >= 0 && rpgThrowOf(cat[ids[i]])) return ids[i];
    }
    return null;
  }
  // Throw one carried thing (ADR 0024) at the foe the fight row names, or
  // the nearest living one in range on a clear line. It is rolled like a
  // blow (a miss, a critical), guard takes from it, and it lands on the
  // foe's tile, to be picked up again. A throw is a blow: it costs the
  // turn one costs, unless the caller runs that turn itself (`noTurn`).
  // Answers whether a throw happened.
  function heroThrow(id, target, opts) {
    opts = opts || {};
    var def = itemCatalog()[id];
    var spec = rpgThrowOf(def);
    if (!spec || bagItems().indexOf(id) < 0) return false;
    function inReach(f) {
      return f && f.alive && f.fightable !== false
        && chebyshev(f.at[0], f.at[1], hero[0], hero[1]) <= spec.range
        && clearLine(hero[0], hero[1], f.at[0], f.at[1]);
    }
    var foe = inReach(target) ? target : null;
    if (!foe) {
      var best = -1;
      for (var i = 0; i < enemies.length; i++) {
        var e = enemies[i];
        if (!inReach(e)) continue;
        var dist = chebyshev(e.at[0], e.at[1], hero[0], hero[1]);
        if (best === -1 || dist < best) { best = dist; foe = e; }
      }
    }
    if (!foe) {
      combatSay('There is nothing in reach to throw ' + itemName(id) + ' at.');
      return false;
    }
    var carried = null;
    bagCarried().forEach(function (c) { if (!carried && c.id === id) carried = c; });
    if (!carried || !bagRemoveEntry(carried)) return false;
    var totals = rpgTraitTotals();
    var roll = rpgRoll(regionName, 'hero', foe.id, totals.crit, heroMissBonus());
    playOneShot('hero', 'attack');
    wakeOne(foe);
    makeNoise('fight');
    var said;
    if (roll && roll.miss) {
      hitAt(foe.at, 'miss', 'miss');
      said = 'You throw ' + itemName(id) + ' at ' + foe.name + ' and miss.';
    } else {
      var crit = !!(roll && roll.crit);
      var amount = spec.harm * (crit ? roll.times : 1);
      var dmg = rpgGuarded(resolveDamage(amount, '', foe.resist, foe.immune).damage, foe.guard);
      foe.hp = Math.max(0, foe.hp - dmg);
      playOneShot('enemy:' + foe.id, 'hurt');
      soundCue('hit');
      hitAt(foe.at, crit ? 'CRIT ' + dmg : String(dmg), crit ? 'crit' : 'hit');
      said = 'You throw ' + itemName(id) + ' at ' + foe.name + ' for ' + dmg + '.';
      if (foe.hp <= 0) said += foeFalls(foe, totals);
      else said += squealIfHurt(foe);
    }
    // It lands where the foe stood, as itself.
    placeDrops(foe.at, [{ item: carried.id, rarity: carried.rarity, traits: carried.traits }]);
    combatSay(said);
    combatSnapshot();
    flushGrowth();
    draw();
    if (!opts.noTurn && typeof window.VEFR_SPEND_TURN === 'function') window.VEFR_SPEND_TURN();
    return true;
  }
  window.VEFR_THROW = heroThrow;
  window.VEFR_THROWABLE = throwableId;
  // One enemy's attack: the hero loses its `atk`, clamped at zero.
  //
  // The number that is subtracted comes from the one resolver, so the
  // hero's own resistances are read here and nowhere else. An untyped
  // blow is the identity and the sentence is the bytes this always
  // read; a typed one says what the type did in words - never by colour,
  // never by the health bar alone (vefr#497).
  //
  // ADR 0021: a pack with a `fight` block rolls the monster's blow too - a
  // miss, or a critical - and the hero's guard takes from what lands, never
  // below 1; a trait with `thorns` answers a blow that landed (a foe is
  // never felled by it: it is left on 1, so a monster turn never kills).
  function enemyAttack(e) {
    var roll = rpgRoll(regionName, e.id, 'hero', 0);
    playOneShot('enemy:' + e.id, 'attack');
    if (roll && roll.miss) {
      hitAt(null, 'miss', 'miss');
      combatSay(verbWord('foe_miss', { what: e.name }));
      return false;
    }
    var heavy = !!(roll && roll.crit);
    var struck = heroTakes(heavy ? e.atk * roll.times : e.atk, e.dmgType);
    struck.damage = rpgGuarded(struck.damage, heroGuard());
    HERO_HP = Math.max(0, HERO_HP - struck.damage);
    playOneShot('hero', 'hurt');
    hitAt(null, (heavy ? 'CRIT ' : '') + '-' + struck.damage, heavy ? 'crit' : 'hurt');
    saveHeroHp();
    renderHp();
    var line;
    if (struck.how === 'immune') {
      line = e.name + ' hits you with ' + struck.type + ', and it cannot touch you.';
    } else if (struck.how === 'resisted' && struck.damage <= 0) {
      // A blow the resistance divides away entirely never says "for 0":
      // it says the one true thing, which is that it did not land.
      line = e.name + ' hits you with ' + struck.type
           + ', and your resistance turns it aside.';
    } else if (struck.how === 'resisted') {
      line = e.name + ' hits you with ' + struck.type + ' for ' + struck.damage
           + '; your resistance turns the rest aside.';
    } else if (struck.type) {
      line = e.name + ' hits you with ' + struck.type + ' for ' + struck.damage + '.';
    } else {
      line = e.name + ' hits you for ' + struck.damage + '.';
    }
    if (heavy) line = verbWord('foe_crit', { what: e.name }) + ' ' + line;
    var thorns = rpgTraitTotals().reactions.thorns;
    if (thorns && struck.damage > 0 && HERO_HP > 0 && e.hp > 1) {
      var back = Math.min(thorns.n, e.hp - 1);
      e.hp -= back;
      hitAt(e.at, String(back), 'hit');
      line += ' ' + itemName(thorns.from) + ' bites back for ' + back + '.';
    }
    // What the bite leaves behind (ADR 0024): a festering wound, dust in
    // the eyes. Only on a blow that landed, and never on the one that
    // felled the hero - the wake clears every state anyway.
    if (struck.damage > 0 && HERO_HP > 0) line += onHitSkills(e);
    combatSay(line);
    // A hit that reaches the hero is one practice count.
    sayGrowth(practiceSuffix(growBump('hits-taken')));
    soundCue('hurt');
    if (HERO_HP <= 0) { cozyDeath(e); return true; }
    // What the blow left behind, if anything: the hero is burning, and
    // the HUD line and this same live region are how that is said. A
    // blow that felled the hero leaves nothing to be burning - the
    // wake above has already cleared it.
    var lit = e.burns ? applyBurning(e.burns) : null;
    if (lit && lit.fresh) {
      combatSay(combatText() + ' ' + e.name + ' sets you alight: burning '
               + lit.status.turns + (lit.status.turns === 1 ? ' turn' : ' turns') + '.');
    }
    return false;
  }
  // The turn's flood is cut off here however far the pack's sights
  // reach (ADR 0014's turn cost). E0d's wake radius plus four is the
  // nearer of the two bounds and still wins below it.
  var FLOOD_CUTOFF = 24;
  // How near the hero a monster wakes: its own sight when that runs
  // past ten, ten otherwise. Asleep costs a turn nothing at all -
  // no flood, no step, no attack.
  function wakeRadius(e) { return Math.max(10, e.sight || 0); }
  // A sleeper does nothing, and there are three ways to stop being one:
  // the hero ends a turn inside its wake radius (Manhattan, E0d) or
  // inside its own sight (Chebyshev, the ADR's rule, added beside E0d's
  // rather than in place of it), a noise it can hear, or a hit. The
  // warden is never asleep at all.
  //
  // The room-reveal fog is not one of those ways and is not one of
  // those places: seeing a sleeper on the map tells you where it is and
  // leaves it where it is.
  function asleep(e) {
    if (isWarden(e)) return false;
    if (manhattan(e.at[0], e.at[1], hero[0], hero[1]) <= wakeRadius(e)) return false;
    return chebyshev(e.at[0], e.at[1], hero[0], hero[1]) > (e.sight || 0);
  }
  // Wake one monster, on its own account: it was hit, or it heard
  // something. No free turn - the hero's turn is not a monster phase -
  // and the group is left to the monster turn, which is the one place a
  // group is consulted.
  function wakeOne(e) {
    prepareMinds();
    if (!e || !e.alive || e.awake) return;
    e.awake = true;
    e.grace = false;
    e.wakeSpread = false;   // the turn has a group to catch up on
  }
  // ---- noise: the loud things, and how far they carry ----
  // Every number the floor is ever woken by is in this one block, in
  // tiles, measured Chebyshev from the hero - the source of all five.
  // The hero is the noise maker for every one of them.
  var NOISE_FIGHT = 12;     // fighting
  var NOISE_DOOR = 6;       // opening a door
  var NOISE_CHEST = 6;      // opening a chest
  var NOISE_STAIR = 8;      // using stairs
  var NOISE_BREAK = 8;      // breaking things
  // The radius for one loud event. The table is closed: a kind nobody
  // declared carries nothing, so a call site that gets its own spelling
  // wrong wakes nobody rather than waking the floor.
  //
  // `makeNoise(kind)` is the only way a loud event reaches the floor,
  // and this table is the only place a radius is written: four of the
  // five rows are asked by a real call site in the shipped player -
  // fighting in `heroAttack`, the other three in the interaction
  // dispatch (part 480) - and each is reached only by naming it
  // there. There are no per-kind wrappers, because a wrapper nobody
  // calls is a number nothing ever asks and a name nothing ever
  // spells. `break` is the fifth row and has no call site, because the
  // player has no break action to attach one to; the number is the
  // owner's and stays here ready for the day one exists.
  function noiseRadius(kind) {
    if (kind === 'fight') return NOISE_FIGHT;
    if (kind === 'door') return NOISE_DOOR;
    if (kind === 'chest') return NOISE_CHEST;
    if (kind === 'stair') return NOISE_STAIR;
    if (kind === 'break') return NOISE_BREAK;
    return 0;
  }
  function inEarshot(x, y, kind) {
    var r = noiseRadius(kind);
    if (!r) return false;
    return chebyshev(x, y, hero[0], hero[1]) <= r;
  }
  // The hero did something loud at their own tile: wake every sleeper
  // in earshot of it. `kind` is one of the five names above.
  function makeNoise(kind) {
    prepareMinds();
    if (!noiseRadius(kind)) return;
    for (var i = 0; i < enemies.length; i++) {
      var e = enemies[i];
      if (!e || !e.alive) continue;
      if (inEarshot(e.at[0], e.at[1], kind)) wakeOne(e);
    }
  }
  // A monster's group wakes with it: every other living member of that
  // group is awake in this same phase, and each one the wake caught
  // here spends it as its free turn. So a group wakes all at once and
  // never lands its first blow all at once. A monster with no group
  // wakes alone and acts at once, exactly as it always did.
  //
  // This is the one place a group is consulted, and the monster turn is
  // its only caller - the spread happens inside a monster phase, which
  // is what makes the free turn mean anything.
  function wakeGroup(e, awake) {
    if (!awake || !e) return false;
    e.wakeSpread = true;
    if (!e.group) return true;
    var members = groupMembers(e.group);
    for (var i = 0; i < members.length; i++) {
      var other = members[i];
      if (other === e || other.awake) continue;
      other.awake = true;
      other.grace = true;
      other.wakeSpread = true;
    }
    return true;
  }
  // One enemy's turn. Next to the hero -> hit them. Badly hurt with
  // the hero in sight -> step away down the map. In sight -> step one
  // tile closer, the short way round the floor rather than into a wall.
  // Out of sight -> drift toward the nearest other monster, so a pack
  // stays a pack instead of scattering into corners. Alone and out of
  // sight -> it holds still.
  //
  // The warden is the one thing on the floor that does not drift. ADR
  // 0014's owner decision 2 is that it hunts the hero, so out of the
  // hero's sight it walks at the hero the same way it walks at the hero
  // when the hero IS in sight: one tile closer, the short way round the
  // floor. It gives up the drift entirely, so a warden that happened
  // to spawn alone is not a monster that holds still on a floor with
  // nobody else on it.
  //
  // A member of a group is held to its leash instead: it never steps
  // past its home's line, on the line it fights from where it stands,
  // and with the hero out of sight it walks home and idles there awake.
  //
  // The warden is asked BEFORE the leash, because a warden that also
  // carries a `group` is a warden and a member at once, and the ADR
  // gives the two rules one answer between them: it hunts. A leash
  // member walks home when it loses the hero and holds on its line when
  // it is badly hurt, and a warden does neither - it is the one thing on
  // the floor with a hall to sit in and the hero to find. So the leash
  // branch below is only ever reached by a monster that is not a warden,
  // and a warden with a group walks out of its own home the same way it
  // walks out of its hall.
  function enemyAct(e, maps) {
    var d = manhattan(e.at[0], e.at[1], hero[0], hero[1]);
    skillsTick(e);
    if (d === 1) return enemyAttack(e);
    // A web or a spit from where it stands (ADR 0024), before it walks.
    if (d <= e.sight) {
      var reached = rangedSkill(e);
      if (reached !== null) return reached;
    }
    if (isWarden(e)) {
      if (d <= e.sight && badlyHurt(e)) {
        return stepAlong(e, distances(maps, hero[0], hero[1]), -1);
      }
      return stepAlong(e, distances(maps, hero[0], hero[1]), 1);
    }
    var leash = leashOf(e);
    if (leash) {
      if (d > e.sight) return stepHome(e, leash);
      // On the line: nothing between this monster and the hero but the
      // leash, and the hero is not close enough to hit. It holds.
      if (onLeashEdge(e, leash)) return false;
      if (badlyHurt(e)) return stepAlong(e, distances(maps, hero[0], hero[1]), -1, leash);
      return stepAlong(e, distances(maps, hero[0], hero[1]), 1, leash);
    }
    if (d <= e.sight) {
      if (badlyHurt(e)) return stepAlong(e, distances(maps, hero[0], hero[1]), -1);
      return stepAlong(e, distances(maps, hero[0], hero[1]), 1);
    }
    var ally = nearestAlly(e, maps);
    if (!ally) return false;
    return stepAlong(e, distances(maps, ally.at[0], ally.at[1]), 1);
  }
  // Every living enemy takes its turn in order, against the same
  // shared distance maps; an asleep one costs nothing and is skipped.
  // The hero's death ends the turn early (and wakes them elsewhere).
  function enemyTurn() {
    prepareMinds();
    // The harness reads this once, at the end of a run, so it is
    // reset per turn, not per flood: it always shows the last turn.
    window.VEFR_FLOOD_STATS = { floods: 0, tiles: 0, maxSpan: 0 };
    var roster = enemies.slice();
    var maps = turnMaps();
    // The flood only has to reach a little past the farthest wake:
    // every awake monster stands within its own wake radius of the
    // hero, and the flood reaches wakeRadius + 4 tiles from wherever
    // it starts, so no step an awake monster could take before is
    // lost - and never more than FLOOD_CUTOFF steps, which is the ADR's
    // turn cost. Known limit: a monster whose walk the long way round
    // runs farther than this can now hold still where it used to keep
    // coming.
    var far = 10;
    for (var j = 0; j < roster.length; j++) {
      if (roster[j].alive) far = Math.max(far, wakeRadius(roster[j]));
    }
    floodLimit = Math.min(far + 4, FLOOD_CUTOFF);
    // Who acts, in two passes. First every monster asks whether it is
    // awake: one that was already awake stays awake - a group, a hit, a
    // noise - and one that is not is woken here if the hero ended the
    // turn in its earshot. A monster that woke on its own has no free
    // turn, so it acts in this same phase and everything E0d did
    // happens exactly as it did.
    var awake = [];
    for (var k = 0; k < roster.length; k++) {
      if (!roster[k].alive) continue;
      if (!roster[k].awake && !asleep(roster[k])) {
        roster[k].awake = true;
        roster[k].wakeSpread = false;
      }
      awake[k] = roster[k].awake;
    }
    // Then the groups, through the one seam: anything awake that still
    // owes its group a wake gets the rest of it in this phase, so no
    // member of a group is awake later than any other.
    for (var s = 0; s < roster.length; s++) {
      if (!roster[s].alive || !awake[s] || roster[s].wakeSpread) continue;
      awake[s] = wakeGroup(roster[s], true);
    }
    // The spread woke members the pass above had already passed, so the
    // act list is read once more off the roster: everybody the group
    // caught acts in this same phase, minus the free turn.
    for (var a = 0; a < roster.length; a++) {
      if (roster[a].alive) awake[a] = roster[a].awake;
    }
    for (var i = 0; i < roster.length; i++) {
      if (!roster[i].alive || !awake[i]) continue;
      // The free turn a group wake grants: spent here, once. A monster
      // caught by its group's wake is awake from the next phase and
      // acts from the next phase, so a group wakes together and never
      // strikes together.
      if (roster[i].grace) { roster[i].grace = false; continue; }
      if (enemyAct(roster[i], maps)) {
        flushGrowth(); draw(); combatSnapshot(); return;
      }
    }
    flushGrowth();
    draw();
    combatSnapshot();
  }
  // Death is Cozy: health back to max, one plain line, and a wake at
  // the hero's baked wake point. Nothing is lost.
  //
  // Two events leave this function, both in `shapes.EVENTS` beside the
  // other eleven: `falls` says the hero's health reached zero, and `wakes`
  // says where the hero woke up. Both are facts, not places - a pack
  // cannot tell the difference between a death and an ordinary
  // arrival, and `enters` fires on both. `falls` is raised BEFORE the
  // hero moves, so it carries the region the hero fell in; `wakes`
  // after, so it carries the region they woke in. The killer is named
  // when there is one (an enemy called this) and left empty when there
  // is not, so the `defeats` mirror has nothing to pretend.
  //
  // A floor of the descent is the one place that wake point is not: the
  // descent answers for its own floors (the up-stair of the floor the
  // hero fell on, whole, with the run intact), and every other region -
  // the town, a baked one - wakes exactly where the pack says it does.
  // The descent therefore asks first, and `wakes` carries the region it
  // answered with, so an event sees the wake and not the fall. The line
  // follows that answer: it names the foot of the stair where the
  // descent wakes the hero, and the pack's own wake place everywhere
  // else.
  function cozyDeath(killer) {
    var wake = (window.VEFR_HERO && window.VEFR_HERO.wake) || {};
    var D = window.VEFR_DESCENT;
    // ADR 0021 `fall: "home"`: a fall on a generated floor wakes at the
    // pack's own wake point, and what the bag held stays where the hero
    // fell. A descent that names no `fall` wakes on the floor's up-stair.
    var home = !!(D && typeof D.fallsHome === 'function' && D.fallsHome(regionName));
    var left = home ? D.dropSatchel(regionName, hero.slice()) : 0;
    if (home) { renderBagPanel(); renderBagStrip(); renderVerbRow(); }
    var back = (!home && D && typeof D.deathResume === 'function')
      ? D.deathResume(regionName) : null;
    var said = back ? STAIR_DEATH_LINE : (home && left ? SATCHEL_DEATH_LINE : DEATH_LINE);
    // The fading line over the world keeps its own words; the second
    // argument keeps them off the quiet page once (vefr#484), because
    // the card below says them there with their "You fell."
    combatSay(said, true);
    fireRule('falls', { what: (killer && killer.id) || '',
                        where: regionName });
    HERO_HP = heroMax();
    saveHeroHp();
    renderHp();
    // Waking whole wakes unburnt: nothing is left of what did it
    // (vefr#497), the way the wake point is the same wherever it is.
    resetStatuses();
    var woke = regionName;
    if (back) {
      enterRegion(back.region, back.at);
      woke = back.region;
    } else if (wake.region && regions[wake.region]) {
      enterRegion(wake.region, wake.at);
      woke = wake.region;
    } else {
      hero = (town.hero_start || [1, 1]).slice();
      heroPublishAt();
      loadEnemies();
      draw();
    }
    fireRule('wakes', { where: woke });
    combatSnapshot();
    // A warm hush (vefr#484, mockup C): the fight is over, so the verb
    // row is closed, and the hero already stands at the wake point
    // behind the dim - one small quiet card near the bottom waits for
    // any key, tap or button. The row comes back on the next turn's
    // own rule, as it always did.
    closeEnemyVerbs();
    var vrow = document.getElementById('verb-row');
    if (vrow) vrow.hidden = true;
    showFallCard('You fell. ' + said, (home && left) ? SATCHEL_FALL_NOTE : '');
  }
  // The mind state of every monster, in the same order as `enemies` and
  // carrying the same `id`: whether it is on its feet, which group it
  // belongs to, whether it leads that group or wards the floor, and the
  // tile that group calls home. It is a sibling of `enemies` and not a
  // part of it: an enemy record is the fight as a harness has always
  // read it - six fields, no more - and four tests read it that way.
  // This is the ADR's part of the fight, kept beside it so the fight
  // itself did not have to change. Nothing in here is ever saved: it is
  // read off the live records and is dropped with them when the region
  // is left.
  function combatMinds() {
    var out = [];
    for (var i = 0; i < enemies.length; i++) {
      var e = enemies[i];
      if (!e) continue;
      out.push({ id: e.id, awake: !!e.awake, grace: !!e.grace,
                 group: e.group || '', leader: !!e.leader,
                 warden: !!e.warden,
                 home: e.spawn ? e.spawn.slice() : null });
    }
    return out;
  }
  // A harness-readable snapshot of the fight, refreshed every turn
  // (precedent: window.VEFR_DESK_LAST).
  function combatSnapshot() {
    // The mind state is read here too: the snapshot is the harness's
    // window onto the fight, and a region that has just been entered
    // has not run a monster turn yet, so it has no mind state to publish
    // until `prepareMinds` has made one.
    prepareMinds();
    window.VEFR_COMBAT = {
      region: regionName,
      hero: { hp: HERO_HP, max: heroMax(), atk: heroAtk(), at: hero.slice() },
      gold: heroGold(),
      enemies: enemies.map(function (e) {
        return { id: e.id, at: e.at.slice(), hp: e.hp, atk: e.atk,
                 sight: e.sight, alive: e.alive, yields: e.yields === true };
      }),
      minds: combatMinds(),
      bag: bagItems(),
      floor: floor.filter(function (d) { return d.region === regionName; })
        .map(function (d) {
          var out = { at: d.at.slice(), item: d.item, name: itemName(d.item) };
          // The drawn rarity rides in the snapshot too, so a harness can
          // see what the bag will say - and only when there is one, so a
          // pack that never rolls reads the snapshot it always read.
          if (d.rarity) {
            out.rarity = d.rarity;
            out.identified = d.identified === true;
          }
          return out;
        })
    };
    // The hero's status effects (part 425, vefr#497), only when there is one, so a pack with
    // no statuses reads the snapshot it always read. In memory only, like the store itself.
    if (typeof heroStatuses !== 'undefined' && heroStatuses.length) {
      window.VEFR_COMBAT.statuses = heroStatuses.map(function (st) {
        return { effect: st.effect, type: st.type, turns: st.turns, tick: st.tick };
      });
    }
    return window.VEFR_COMBAT;
  }
  // The bag and gold code lives outside this closure; give it a way to
  // refresh the snapshot after a change, so the harness always reads
  // the current fight (precedent: window.VEFR_DESK_LAST).
  window.refreshCombatSnapshot = combatSnapshot;

