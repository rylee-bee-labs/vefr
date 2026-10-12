// ---- the pack's rules: one event in, the page's own surfaces out ----
// fireRule is the ONE seam between the game and window.VEFR_RULES_ENGINE
// (the pure logic living between the "-- rules start/end --" markers).
// Every call site is one line at a point that already existed, and no
// returned action is ever fed back in as an event (a give is not a
// picks-up). With no engine or no baked rules it returns before ANY
// side effect at all - no DOM, no browser storage, no snapshot - which is
// every existing pack's path. Deterministic: no clock, no randomness,
// no model call lives here.
function fireRule(eventName, data) {
  // The album checks every event first, before the rules early return:
  // a pack with an album but no rules bakes VEFR_RULES = null, and the
  // return below would otherwise skip the sticker its `starts` earns.
  albumNotify(eventName, data);
  var engine = window.VEFR_RULES_ENGINE;
  var rules = window.VEFR_RULES;
  if (!engine || !Array.isArray(rules) || !rules.length) return;
  var state = rulesStateNow();
  if (!state) return;
  var out = engine.run(state, eventName, data || {});
  saveRulesState();   // a picks-up changes items even when no rule fires
  rulesWhyRecord(out.fired);
  for (var i = 0; i < out.actions.length; i++) {
    performRuleAction(out.actions[i]);
  }
}

// The one state the engine keeps: built once from the baked pack the
// first time a rule actually runs (a pack with no rules never builds
// one), and left on window for the menu's why panel. Every speaker's
// home region is filled in here: people do not move in this player,
// so `is-in` reads the bake as truth.
var RULES_STATE = null;
function rulesStateNow() {
  if (RULES_STATE) return RULES_STATE;
  var engine = window.VEFR_RULES_ENGINE;
  if (!engine) return null;
  RULES_STATE = engine.newState({
    rules: window.VEFR_RULES, flags: window.VEFR_FLAGS,
    claims: window.VEFR_CLAIMS, people: window.VEFR_PEOPLE
  });
  var groups = window.VEFR_SPEAKERS || {};
  Object.keys(groups).forEach(function (rg) {
    Object.keys(groups[rg]).forEach(function (k) {
      RULES_STATE.where[k] = rg;
    });
  });
  rulesStateLoad(RULES_STATE);
  window.VEFR_RULES_STATE = RULES_STATE;
  return RULES_STATE;
}

// One returned action onto a surface that ALREADY exists - never a new
// subsystem. set/unset/believes/stops-believing/tells were applied to
// the state by run() itself as it went; they have no page surface and
// need none - the next condition and the why panel read them back.
function performRuleAction(a) {
  if (!a || typeof a !== 'object') return;
  var key = Object.keys(a)[0], v = a[key];
  if (key === 'say') {
    // A string is the narrator: one line in the combat log. An object
    // names a speaker; an unknown speaker is skipped silently.
    if (typeof v === 'string') { combatSay(v); return; }
    if (v && typeof v === 'object') {
      var name = rulesSpeakerName(v.who);
      if (name) showSpeech(name, v.line || '', '');
    }
    return;
  }
  if (key === 'set') {
    // A flag is some other pack's business - except when it is a
    // warden's, because ADR 0015 Amendment 1 §2 makes the moment a pack
    // rule sets a `"challenge": "rule"` warden's flag the moment its
    // challenge is complete: the key it carries goes straight into the
    // bag, with a line, the same as on death. The descent owns that flag
    // and this asks it; every other flag falls through to nothing, as
    // `set` always did.
    var D = window.VEFR_DESCENT;
    if (D && typeof D.challengeSet === 'function') {
      var wardenKey = D.challengeSet(v);
      if (wardenKey && bagAdd(wardenKey, null, true)) {
        combatSay('You take ' + itemName(wardenKey) + '; it is in your bag.');
      }
    }
    return;
  }
  if (key === 'give') { bagAdd(v, null, true); return; }
  if (key === 'takes') { bagRemoveOne(v); return; }
  if (key === 'weather') {
    if (window.VEFR_RULES_WEATHER) window.VEFR_RULES_WEATHER(v === 'fog');
    return;
  }
  if (key === 'point-to') {
    if (window.VEFR_RULES_POINT_TO) window.VEFR_RULES_POINT_TO(v);
    return;
  }
  if (key === 'complete-act') { openActEnd(v); return; }
  if (key === 'show' || key === 'hide' || key === 'reveal') {
    if (window.VEFR_RULES_SURFACE) window.VEFR_RULES_SURFACE(key, v);
  }
}

// A speaker key to the name the pack gave it, searched across the
// baked regions; '' when the key names no speaker - the say action
// then skips rather than inventing a voice.
function rulesSpeakerName(key) {
  if (typeof key !== 'string') return '';
  var groups = window.VEFR_SPEAKERS || {};
  var regions = Object.keys(groups);
  for (var i = 0; i < regions.length; i++) {
    var spec = groups[regions[i]][key];
    if (spec && spec.name) return spec.name;
  }
  return '';
}

// The player's rule log: the last 20 fired rules as { id, why }, one
// entry per rule per fire, kept on window (VEFR_WHY) and mirrored to
// browser storage under the file's own per-world pattern (the same shape
// as vefr-fog-<world>-...). EVERY storage access is wrapped: a
// sandboxed iframe's browser storage throws, and a thrown log must never
// take the game down.
window.VEFR_WHY = [];
var rulesWhyLoaded = false;
function rulesWhyKey() {
  return 'vefr-rules-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}
function rulesWhyLoad() {
  if (rulesWhyLoaded) return;
  rulesWhyLoaded = true;
  var a = store.getJSON(rulesWhyKey(), []);
  window.VEFR_WHY = Array.isArray(a) ? a.filter(function (e) {
    return e && typeof e.id === 'string' && typeof e.why === 'string';
  }) : [];
}
function rulesWhyRecord(fired) {
  if (!Array.isArray(fired) || !fired.length) return;
  rulesWhyLoad();
  fired.forEach(function (f) {
    window.VEFR_WHY.push({ id: f.id, why: f.why });
  });
  while (window.VEFR_WHY.length > 20) window.VEFR_WHY.shift();
  store.setJSON(rulesWhyKey(), window.VEFR_WHY);
}

