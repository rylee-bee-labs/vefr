// ---- what a blow is, and what it leaves behind ----
  // Damage types, resistances and one status effect (vefr#497, slice 1
  // of design/elemental-and-status-effects.md). A pack opts in by
  // naming them: `player.resist` / `player.immune` bake onto the hero,
  // and a hazard may carry the `dmg_type` of the blow it deals and a
  // `burns` block that leaves the hero burning for a count of turns.
  //
  // A pack that names none of this has none of it baked, and then every
  // function below answers "nothing here": the resolver hands back the
  // number it was given, the fight says the sentence it always said,
  // and the status line stays empty. That is the whole compatibility
  // promise, and `tests/test_elements.py` pins it.
  //
  // Three axes, kept apart on purpose (the design note): a damage type
  // is what the damage IS, a status effect is the STATE left on a
  // combatant, and resistance is the relationship between them.
  //
  // Nothing here is a colour. Every result is said in words and, while
  // a state lasts, written on the HUD line and announced on the live
  // region a screen reader is already reading - so the signal survives
  // with no colour sense at all (accessibility rule 2).

  // What a damage type may be called. Closed, because a pack that could
  // write "fiery" beside "fire" would be two mechanics under one word
  // again. The same list is `elements.DAMAGE_TYPES` on the engine side.
  var DAMAGE_TYPES = ['physical', 'fire', 'cold', 'lightning', 'poison',
                      'necrotic', 'acid', 'radiant', 'psychic', 'thunder'];
  // A damage type in lower case, or '' when the word names none. The
  // untyped blow - no `dmg_type` at all - is the identity here and
  // everywhere below.
  function normalDamageType(value) {
    if (typeof value !== 'string') return '';
    var word = value.trim().toLowerCase();
    return DAMAGE_TYPES.indexOf(word) === -1 ? '' : word;
  }

  // What the hero shrugs off. Both are read from the baked hero, and a
  // pack with neither key bakes neither, so these are `{}` and `[]` -
  // which is what a resistance of nothing looks like.
  function heroResist() {
    var r = (window.VEFR_HERO || {}).resist;
    var out = {};
    if (!r || typeof r !== 'object') return out;
    for (var key in r) {
      var name = normalDamageType(key);
      var n = r[key];
      if (name && typeof n === 'number' && isFinite(n) && n >= 1 && n <= 9) {
        out[name] = Math.floor(n);
      }
    }
    return out;
  }
  function heroImmune() {
    var list = (window.VEFR_HERO || {}).immune;
    var out = [];
    if (!Array.isArray(list)) return out;
    for (var i = 0; i < list.length; i++) {
      var name = normalDamageType(list[i]);
      if (name && out.indexOf(name) === -1) out.push(name);
    }
    return out;
  }

  // THE resolver: the one place a number is changed by a resistance.
  // Both damage paths call it (the hero's blow in `heroAttack`, the
  // hazard's in `enemyAttack`), because a resolver on one side only is
  // how fire resists and poison does not without anybody noticing.
  //
  // `amount` is the raw number; `dtype` the damage type or ''; `resist`
  // a {type: divisor} table and `immune` a list of types. The answer is
  // `{damage, how, type}` where `how` is 'hit', 'resisted' or 'immune',
  // so the caller has words to say and not only a number.
  //
  // An untyped blow is returned EXACTLY as it came in - not clamped,
  // not rounded - because that is the number every pack that has not
  // opted in has always dealt.
  function resolveDamage(amount, dtype, resist, immune) {
    var type = normalDamageType(dtype);
    if (!type) return { damage: amount, how: 'hit', type: '' };
    if (typeof amount !== 'number' || !isFinite(amount) || amount <= 0) {
      return { damage: 0, how: 'hit', type: type };
    }
    var raw = Math.floor(amount);
    if (Array.isArray(immune) && immune.indexOf(type) !== -1) {
      return { damage: 0, how: 'immune', type: type };
    }
    var divisor = (resist && typeof resist === 'object') ? resist[type] : 0;
    if (typeof divisor !== 'number' || !isFinite(divisor) || divisor < 2) {
      return { damage: raw, how: 'hit', type: type };
    }
    return { damage: Math.floor(raw / divisor), how: 'resisted', type: type };
  }
  // The hero's side of a blow: the same resolver, the hero's own words.
  function heroTakes(amount, dtype) {
    return resolveDamage(amount, dtype, heroResist(), heroImmune());
  }

  // ---- the one status effect: burning ----
  // A list of `{effect, type, turns, tick}` - the two properties the
  // design note says every status effect needs and the whole of its
  // data shape. It is NOT stored: a burn is the state of this play
  // session, and a reload puts the hero back whole, exactly as a
  // wounded monster is a new monster again on a rebuilt floor. That is
  // also why no save changes shape and no old save is read wrong.
  var heroStatuses = [];
  function findStatus(effect) {
    for (var i = 0; i < heroStatuses.length; i++) {
      if (heroStatuses[i].effect === effect) return heroStatuses[i];
    }
    return null;
  }
  // What a status is called in a sentence, and what it is costing.
  function statusWords(s) {
    var said = s.effect === 'burning' ? 'Burning' : s.effect;
    return said + ' (' + s.type + ', ' + s.turns + (s.turns === 1 ? ' turn' : ' turns') + ' left)';
  }
  // The HUD line beside the health, the way the torch's turns and the
  // level's xp sit beside it. Words, never a tint; hidden and cleared
  // when there is nothing to say, so a pack with no statuses keeps the
  // HUD it always had.
  function renderStatusHud() {
    var el = document.getElementById('hud-state');
    if (!el) return;
    if (!heroStatuses.length) {
      el.hidden = true;
      el.textContent = '';
      return;
    }
    el.hidden = false;
    el.textContent = heroStatuses.map(statusWords).join(' · ');
  }
  // A new region, and waking at the wake point: nothing burns across
  // either, the way a burning light does not travel.
  function resetStatuses() {
    heroStatuses = [];
    renderStatusHud();
  }
  // A hazard leaves the hero burning. There is no stacking and no
  // refresh rule here: a second blow keeps the longer of the two
  // durations and one tick, because "two burnings" is not a thing this
  // slice decides. The answer is `{status, fresh}` so the caller can
  // say "sets you alight" only on the blow that lit it, or null when
  // the hero cannot be alight at all.
  function applyBurning(spec) {
    if (!spec || spec.effect !== 'burning') return null;
    var tick = resolveDamage(spec.tick, spec.type, heroResist(), heroImmune());
    if (tick.damage <= 0) return null;   // resistance that ends it means never alight
    var held = findStatus('burning');
    if (held) {
      held.turns = Math.max(held.turns, spec.turns);
      held.tick = spec.tick;
      renderStatusHud();
      return { status: held, fresh: false };
    }
    var s = { effect: 'burning', type: spec.type, turns: spec.turns,
              tick: spec.tick };
    heroStatuses.push(s);
    renderStatusHud();
    return { status: s, fresh: true };
  }
  // One hero turn passes: every state ticks its damage, then counts
  // down, and the last one says so and goes.
  //
  // WHERE it runs is the whole of it (vefr#497, review #528): after
  // `enemyTurn()`, never before it. The hero's own damage always
  // resolved there - inside the monsters' turn, in `enemyAttack` - so
  // this is where a burn resolves too, and the established order is
  // untouched: the hero acts, the monsters act, and only then does the
  // fire the monsters lit take its turn. Ticking it earlier let a burn
  // fell a hero on their last health BEFORE the monsters moved - the
  // monsters then never acted at all, and a hazard whose blow was about
  // to land never landed. Called beside every `enemyTurn()` - the four
  // places the player's turn is over - and nowhere else, so a turn is a
  // turn.
  function statusTurn() {
    if (!heroStatuses.length) return;
    var said = [];
    var left = [];
    for (var i = 0; i < heroStatuses.length; i++) {
      var s = heroStatuses[i];
      var bite = resolveDamage(s.tick, s.type, heroResist(), heroImmune());
      if (bite.damage > 0) {
        HERO_HP = Math.max(0, HERO_HP - bite.damage);
        said.push('The ' + s.type + ' takes ' + bite.damage + ' from you.');
      } else {
        said.push('The ' + s.type + ' does no more.');
      }
      s.turns -= 1;
      if (s.turns > 0) {
        left.push(s);
      } else {
        said.push(s.effect === 'burning' ? 'The burning dies out of you.' : s.effect + ' ends.');
      }
    }
    heroStatuses = left;
    saveHeroHp();
    renderHp();
    renderStatusHud();
    // The turn's line keeps what the monsters said first, for the reason
    // `enemyAttack` joins its "sets you alight" the same way: a hero told
    // only that the fire took 2 would not know what lit it. Both halves
    // are on the live region, in the order they happened.
    var before = combatText();
    combatSay(before ? before + ' ' + said.join(' ') : said.join(' '));
    // The harness reads the fight's own snapshot, so the health this
    // tick just moved is published with the rest of the turn.
    combatSnapshot();
    // A burn that finished the hero is a death like any other: the same
    // wake, the same rules, the same reset. There is no second one, and
    // the monsters have already had their turn - so there is nothing
    // left here to stop.
    if (HERO_HP <= 0) cozyDeath({ id: 'burning' });
  }