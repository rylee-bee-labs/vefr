  // -- rules start --
  // The rules engine: one event in, the actions to perform out. Pure
  // logic only - no DOM, no clock, no randomness, no fetch, no network
  // - so tests/fixtures/rules_harness.mjs can run this exact text in a
  // bare node vm context with nothing but the built-ins.
  //
  // A rule is { id, on?, when, if?, then, once? }, the same shape
  // src/vefr/maplab.py's rules_errors checks at authoring time. The
  // events are the EVENTS table below, a twin of src/vefr/shapes.py's -
  // `tests/test_event_table.py` fails if the two drift. There is
  // deliberately no `says` event: the woven player has no place for the
  // player to type words, so an event waiting on typed speech could
  // never fire.
  //
  // The limits kept on purpose: a rule fires at most once per event,
  // the actions a rule returns are never fed back in as new events
  // (no chains - a `give` is not a `picks-up`), rules run in the order
  // the pack wrote them (there are no priorities), and a malformed or
  // unknown rule key is skipped without throwing.
  window.VEFR_RULES_ENGINE = (function () {
    // Each event's payload keys, exactly as the validator declares
    // them; `target` is the event's main thing - the place entered, or
    // the thing come near / opened / picked up, or the item used - and
    // is what a rule's `on` matches.
    var EVENTS = {
      'starts': { keys: [], target: null },
      'enters': { keys: ['place'], target: 'place' },
      'comes-near': { keys: ['who', 'distance'], target: 'who' },
      'opens': { keys: ['what'], target: 'what' },
      'picks-up': { keys: ['what'], target: 'what' },
      'uses-with': { keys: ['item', 'with'], target: 'item' },
      'defeats': { keys: ['what'], target: 'what' },
      'buys': { keys: ['what'], target: 'what' },
      'sells': { keys: ['what'], target: 'what' },
      'reads': { keys: ['what'], target: 'what' },
      'phase-changes': { keys: ['to'], target: 'to' },
      'falls': { keys: ['what', 'where'], target: 'what' },
      'wakes': { keys: ['where'], target: 'where' }
    };

    function isObj(v) {
      return typeof v === 'object' && v !== null && !Array.isArray(v);
    }

    function own(obj, key) {
      return Object.prototype.hasOwnProperty.call(obj, key);
    }

    // pack is what cli.weave_html bakes: { rules, flags, claims,
    // people }. Every declared flag starts off; every claim the pack's
    // people block lists is believed from the very first moment, with
    // the author's file as its source - a mistaken assumption the
    // author wrote down is believed before anything happens.
    function newState(pack) {
      if (!isObj(pack)) pack = {};
      var meanings = isObj(pack.flags) ? pack.flags : {};
      var flags = {};
      Object.keys(meanings).forEach(function (name) { flags[name] = false; });
      var beliefs = {};
      var people = isObj(pack.people) ? pack.people : {};
      Object.keys(people).forEach(function (pid) {
        var spec = people[pid];
        var list = isObj(spec) && Array.isArray(spec.believes)
          ? spec.believes : [];
        var held = {};
        list.forEach(function (claim) {
          if (typeof claim === 'string') {
            held[claim] = { value: true, source: 'written in the game file' };
          }
        });
        beliefs[pid] = held;
      });
      return {
        // What is true in the game: every declared flag, off.
        flags: flags,
        // What each person holds: a belief is its own flag and can be
        // wrong - { value, source } per (person, claim).
        beliefs: beliefs,
        // Rule ids that have fired at least once: `once` reads this.
        fired: {},
        // What the hero carries and where each person is. The engine
        // fills `items` from picks-up events and give actions; the
        // wiring fills `where` as people move - `is-in` reads it.
        items: {},
        where: {},
        // The phase the watch stands at while an event runs, put on by
        // the wiring before every run (255-time-rest.js's `time`). A
        // state with no phase (a bare engine run) has none, and a
        // `phase` condition simply does not pass.
        phase: null,
        // The baked pack, so run() needs no second argument.
        rules: Array.isArray(pack.rules) ? pack.rules : [],
        // Flag name -> the one line the pack declared (the why
        // sentence quotes it; a flag the pack never declared just
        // uses its name).
        meanings: meanings
      };
    }

    function setBelief(state, who, claim, value, source) {
      if (!isObj(state.beliefs[who])) state.beliefs[who] = {};
      state.beliefs[who][claim] = { value: value, source: source };
    }

    // A belief is held only when its value is true; nothing there
    // means the person does not believe the claim.
    function beliefValue(state, who, claim) {
      var held = isObj(state.beliefs[who]) ? state.beliefs[who] : null;
      var b = held && isObj(held[claim]) ? held[claim] : null;
      return b ? b.value === true : false;
    }

    // One condition: { ok, why } where `why` is the plain phrase that
    // passed, or null when the condition is malformed (which skips
    // the whole rule). `inv` flips the reading - a `not` wrapper
    // toggles it - and the phrase always states the reading that
    // actually passed.
    function evalCond(cond, state, inv) {
      if (!isObj(cond)) return null;
      var keys = Object.keys(cond);
      if (keys.indexOf('flag') !== -1 || keys.indexOf('is') !== -1) {
        // The flag form is the one condition with two top-level keys.
        if (keys.length !== 2 || typeof cond.flag !== 'string'
            || typeof cond.is !== 'boolean') return null;
        var actual = state.flags[cond.flag] === true;
        var want = inv ? !cond.is : cond.is;
        var phrase = "'" + cond.flag + "' was " + (want ? 'on' : 'off');
        var meaning = state.meanings[cond.flag];
        if (typeof meaning === 'string' && meaning) {
          phrase = "'" + cond.flag + "' (" + meaning + ") was "
            + (want ? 'on' : 'off');
        }
        return { ok: actual === want, why: phrase };
      }
      if (keys.length !== 1) return null;
      var key = keys[0];
      if (key === 'has') {
        if (typeof cond.has !== 'string') return null;
        var held = state.items[cond.has] === true;
        var wantHas = inv ? !held : held;
        return {
          ok: wantHas,
          why: 'the hero ' + (wantHas ? 'had ' : 'did not have ')
            + "'" + cond.has + "'"
        };
      }
      if (key === 'believes' || key === 'not-believes') {
        var p = cond[key];
        if (!isObj(p) || Object.keys(p).length !== 2
            || typeof p.who !== 'string' || typeof p.claim !== 'string') {
          return null;
        }
        var wantBelieves = (key === 'believes') !== inv;
        var does = beliefValue(state, p.who, p.claim);
        return {
          ok: does === wantBelieves,
          why: p.who + (wantBelieves ? ' believes ' : ' does not believe ')
            + "'" + p.claim + "'"
        };
      }
      if (key === 'is-in') {
        var q = cond['is-in'];
        if (!isObj(q) || Object.keys(q).length !== 2
            || typeof q.who !== 'string' || typeof q.place !== 'string') {
          return null;
        }
        var isIn = state.where[q.who] === q.place;
        var wantIn = inv ? !isIn : isIn;
        return {
          ok: wantIn,
          why: q.who + (wantIn ? ' was in ' : ' was not in ') + q.place
        };
      }
      // The STANDING phase (vefr E3): the one the watch is at while the
      // event happens, whatever the event was, so a rule can be about
      // the hour rather than about the thing that turned it. The wiring
      // puts the current phase on the state before every run; an engine
      // run with no phase (the bare node harness) has none, and then
      // the condition is simply not the one being asked about.
      if (key === 'phase') {
        if (typeof cond.phase !== 'string') return null;
        var isPhase = typeof state.phase === 'string'
          && state.phase === cond.phase;
        var wantPhase = inv ? !isPhase : isPhase;
        return {
          ok: wantPhase,
          why: wantPhase
            ? "the watch stood at '" + cond.phase + "'"
            : "the watch stood somewhere but '" + cond.phase + "'"
        };
      }
      if (key === 'not') {
        if (!isObj(cond.not)) return null;
        return evalCond(cond.not, state, !inv);
      }
      // 'all-of': every inner condition must pass. Under a `not` the
      // members are read as they are and the whole conjunction is
      // flipped, so the phrase stays one honest sentence.
      if (key === 'all-of') {
        if (!Array.isArray(cond['all-of'])) return null;
        var list = cond['all-of'];
        var parts = [];
        var allOk = true;
        for (var i = 0; i < list.length; i++) {
          var r = evalCond(list[i], state, false);
          if (!r) return null;
          parts.push(r.why);
          if (!r.ok) allOk = false;
        }
        var pass = inv ? !allOk : allOk;
        var joined = parts.join(', and ');
        if (inv && joined) joined = 'not (' + joined + ')';
        return { ok: pass, why: joined };
      }
      return null;
    }

    // Does this rule's `when` describe the event? true = it matches,
    // false = a well-formed `when` for some other event (no mark, no
    // fire), null = malformed (also no mark, no fire, no throw).
    function whenMatches(when, event, data) {
      if (!isObj(when)) return null;
      var keys = Object.keys(when);
      if (keys.length !== 1 || !own(EVENTS, keys[0])) return null;
      if (keys[0] !== event) return false;
      var payload = when[keys[0]];
      if (!isObj(payload)) return null;
      var want = EVENTS[keys[0]].keys;
      var pkeys = Object.keys(payload);
      if (pkeys.length !== want.length) return null;
      for (var i = 0; i < pkeys.length; i++) {
        if (want.indexOf(pkeys[i]) === -1) return null;
      }
      for (var j = 0; j < want.length; j++) {
        var k = want[j], v = payload[k];
        if (k === 'distance') {
          // "within N tiles": the rule's distance is the reach, the
          // event carries how close the hero actually came.
          if (typeof v !== 'number' || typeof data.distance !== 'number'
              || data.distance > v) return false;
        } else if (data[k] !== v) {
          return false;
        }
      }
      return true;
    }

    // One action of a rule's `then`, against the validator's list.
    // false means the whole rule is malformed and is skipped.
    function validAction(a) {
      if (!isObj(a)) return false;
      var keys = Object.keys(a);
      if (keys.length !== 1) return false;
      var key = keys[0], v = a[key];
      if (key === 'say') {
        if (typeof v === 'string') return true;
        if (isObj(v)) {
          return Object.keys(v).length === 2 && typeof v.who === 'string'
            && typeof v.line === 'string';
        }
        return false;
      }
      if (key === 'show' || key === 'hide' || key === 'reveal'
          || key === 'give' || key === 'takes' || key === 'set'
          || key === 'unset' || key === 'point-to' || key === 'complete-act') {
        return typeof v === 'string';
      }
      if (key === 'weather') return v === 'fog' || v === 'clear';
      if (key === 'believes' || key === 'stops-believing') {
        return isObj(v) && Object.keys(v).length === 2
          && typeof v.who === 'string' && typeof v.claim === 'string';
      }
      if (key === 'tells') {
        return isObj(v) && Object.keys(v).length === 3
          && typeof v.who === 'string' && typeof v.claim === 'string'
          && typeof v.to === 'string';
      }
      return false;
    }

    // The actions that change what is held are applied to the state
    // the player holds; everything else (say, show, hide, ...) is only
    // returned for the wiring to perform. Nothing here starts a new
    // run - there are no chains.
    function applyActions(state, actions) {
      for (var i = 0; i < actions.length; i++) {
        var a = actions[i];
        var key = Object.keys(a)[0], v = a[key];
        if (key === 'set') {
          state.flags[v] = true;
        } else if (key === 'unset') {
          state.flags[v] = false;
        } else if (key === 'give') {
          state.items[v] = true;
        } else if (key === 'takes') {
          // `give`'s pair: the hero stops carrying it. The engine's
          // model is presence, not counts - a delivery turns it in.
          delete state.items[v];
        } else if (key === 'believes') {
          setBelief(state, v.who, v.claim, true, 'saw it themselves');
        } else if (key === 'stops-believing') {
          setBelief(state, v.who, v.claim, false, 'stopped believing');
        } else if (key === 'tells') {
          // One step only: the receiver holds it, sourced to the
          // teller, so the why-log can trace it to where it started.
          setBelief(state, v.to, v.claim, true, 'told by ' + v.who);
        }
      }
    }

    // The one plain sentence a fired rule leaves behind: what
    // happened, and the conditions that said yes. One sentence, the
    // rule id first, a flag named by its declared meaning when the
    // pack wrote one, a belief as "who believes claim".
    function buildWhy(rule, event, data, phrases) {
      var phrase;
      if (event === 'starts') {
        phrase = 'the game began';
      } else if (event === 'enters') {
        phrase = 'the hero entered ' + data.place;
      } else if (event === 'comes-near') {
        var near = typeof rule.on === 'string' ? rule.on : null;
        var wp = isObj(rule.when) && isObj(rule.when['comes-near'])
          ? rule.when['comes-near'] : null;
        if (!near && wp && typeof wp.who === 'string') near = wp.who;
        if (!near) near = data.who;
        phrase = 'the hero came near ' + near;
      } else if (event === 'opens') {
        phrase = 'the hero opened ' + data.what;
      } else if (event === 'picks-up') {
        phrase = 'the hero picked up ' + data.what;
      } else if (event === 'defeats') {
        phrase = 'the hero defeated ' + data.what;
      } else if (event === 'buys') {
        phrase = 'the hero bought ' + data.what;
      } else if (event === 'sells') {
        phrase = 'the hero sold ' + data.what;
      } else if (event === 'reads') {
        phrase = 'the hero closed ' + data.what + ' having read it';
      } else if (event === 'phase-changes') {
        phrase = 'the watch turned to ' + data.to;
      } else if (event === 'falls') {
        // `what` is empty when nothing but the floor did it, so the
        // killer is named only when there is one to name.
        phrase = 'the hero fell in ' + data.where
          + (data.what ? ' to ' + data.what : '');
      } else if (event === 'wakes') {
        phrase = 'the hero woke in ' + data.where;
      } else {
        phrase = 'the hero used ' + data.item + ' with ' + data.with;
      }
      var live = [];
      for (var i = 0; i < phrases.length; i++) {
        if (phrases[i]) live.push(phrases[i]);
      }
      var text = "rule '" + rule.id + "' fired: " + phrase;
      if (live.length) text += ', and ' + live.join(', and ');
      return text + '.';
    }

    // Everything one rule needs to decide. null means skip: wrong
    // event, a condition said no, or malformed - with no mark left.
    function planRule(rule, event, data, state) {
      if (!isObj(rule)) return null;
      if (typeof rule.id !== 'string' || !rule.id) return null;
      if ('on' in rule && typeof rule.on !== 'string') return null;
      if ('once' in rule && typeof rule.once !== 'boolean') return null;
      if (whenMatches(rule.when, event, data) !== true) return null;
      var target = EVENTS[event].target;
      if ('on' in rule && target && data[target] !== rule.on) return null;
      var phrases = [];
      if ('if' in rule) {
        if (!Array.isArray(rule.if)) return null;
        for (var i = 0; i < rule.if.length; i++) {
          var r = evalCond(rule.if[i], state, false);
          if (!r) return null;    // malformed rule: skip, no mark
          if (!r.ok) return null; // a condition said no: no mark
          phrases.push(r.why);
        }
      }
      var then = rule.then;
      if (!Array.isArray(then) || !then.length) return null;
      for (var j = 0; j < then.length; j++) {
        if (!validAction(then[j])) return null;
      }
      return {
        id: rule.id,
        then: then,
        // `once` defaults to true: a rule runs once unless the pack
        // asks otherwise.
        once: 'once' in rule ? rule.once : true,
        why: buildWhy(rule, event, data, phrases)
      };
    }

    // run(state, event, data) -> { actions, fired }.
    // The actions come back in the order the rules were written, and
    // `fired` carries one { id, why } per rule that actually ran. The
    // state is the player's own object and may be updated in place;
    // nothing else is touched, and no returned action is ever fed
    // back in as an event.
    function run(state, event, data) {
      var out = { actions: [], fired: [] };
      if (!isObj(state)) return out;
      if (!isObj(state.flags)) state.flags = {};
      if (!isObj(state.beliefs)) state.beliefs = {};
      if (!isObj(state.fired)) state.fired = {};
      if (!isObj(state.items)) state.items = {};
      if (!isObj(state.where)) state.where = {};
      if (!isObj(state.meanings)) state.meanings = {};
      if (typeof event !== 'string' || !own(EVENTS, event)) return out;
      if (!isObj(data)) data = {};
      // A taken item is held from that moment. This is the event's
      // own record, not an action: it never starts another run.
      if (event === 'picks-up' && typeof data.what === 'string') {
        state.items[data.what] = true;
      }
      var rules = Array.isArray(state.rules) ? state.rules : [];
      for (var i = 0; i < rules.length; i++) {
        var plan = planRule(rules[i], event, data, state);
        if (!plan) continue;
        // Once marked, a `once` rule stays quiet for the whole game;
        // one event gives each rule at most one pass either way.
        if (plan.once && state.fired[plan.id]) continue;
        applyActions(state, plan.then);
        for (var j = 0; j < plan.then.length; j++) {
          out.actions.push(plan.then[j]);
        }
        state.fired[plan.id] = true;
        out.fired.push({ id: plan.id, why: plan.why });
      }
      return out;
    }

    return { newState: newState, run: run };
  })();
  // -- rules end --
