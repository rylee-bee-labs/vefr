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
  // Stakes are asked here for the same reason, and answer the same way:
  // an offer is the game saying a line, so it is said whatever the
  // rules say. With no stakes baked this asks one question and returns.
  stakesOffer(eventName, data);
  var engine = window.VEFR_RULES_ENGINE;
  var rules = window.VEFR_RULES;
  if (!engine || !Array.isArray(rules) || !rules.length) return;
  var state = rulesStateNow();
  if (!state) return;
  // The STANDING phase goes on the state before the run, so a rule's
  // `phase` condition reads the hour the event happened in (vefr E3),
  // whatever the event was. One assignment, every event.
  state.phase = STATE.get().phase;
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

// ---- stakes: the risk a pack offers, and the answer that is the
// player's own (vefr#504) ----
// One opt-in pack field, window.VEFR_STAKES, baked as the literal null
// for every pack that declares none - which is every pack until a game
// asks for this. A pack that writes no stakes is never asked anything,
// and a pack that writes them is asked only what it wrote: there is no
// default, no global rule, no loss that happens on its own, and no
// other pack's stakes reach this one.
//
// The asking, kept to what the decision said and no more:
//   - WHERE: the pack's own `when`, read by the rules engine's own
//     predicate, so a stake means the same event a rule means and a
//     second reading of the shape can never drift from the first;
//   - TO WHOM: only while the hero really carries the `risk`. There is
//     nothing to ask about otherwise, and no ask is made;
//   - ON WHAT TERMS: the pack's own `say`, then the two costs named -
//     what would be put down, what could be gained - and the two keys
//     that answer. Y puts the risk down and takes the reward; N walks
//     away. The same two answers are also two buttons under the line,
//     because a phone player has no keys at all;
//   - AND WHAT WALKING AWAY COSTS: nothing. No flag, no timer, no turn,
//     nothing taken. The offer is not remembered as refused, so the next
//     time the pack's `when` matches the player is asked again - which
//     is what makes this reversible rather than a punishment. Staking
//     is its own memory: the risk leaves the bag, so the carry check
//     above stops asking on its own.
//
// The offer is asked as two on-screen buttons as well as the two keys,
// so a phone can answer it either way (vefr#504; the accessibility
// contract: a phone has no Y and no N).
var STAKE_PENDING = null;   // the offer waiting for an answer, or null
var STAKES_TAKEN = [];      // the ids the player has staked, in order

// The pack's offers, or an empty list, so every check below asks one
// question and moves on.
function stakesOffered() {
  return Array.isArray(window.VEFR_STAKES) ? window.VEFR_STAKES : [];
}

// Is the hero really carrying this id right now? The bag is the truth -
// an id the pack's catalog no longer holds is not carried, whatever a
// save once said.
function stakesCarries(id) {
  return bagCarried().some(function (c) { return c.id === id; });
}

// One event in: the first offer the pack wrote that matches it, that the
// hero can be asked, and that is not already being answered. An offer
// waits for its answer before another is asked - two questions at once
// would be two risks the player never chose to weigh.
function stakesOffer(eventName, data) {
  if (STAKE_PENDING) return;
  var offers = stakesOffered();
  if (!offers.length) return;
  var engine = window.VEFR_RULES_ENGINE;
  if (!engine || typeof engine.matchesWhen !== 'function') return;
  for (var i = 0; i < offers.length; i++) {
    var s = offers[i];
    if (!s || typeof s.id !== 'string') continue;
    if (engine.matchesWhen(s.when, eventName, data || {}) !== true) continue;
    if (!stakesCarries(s.risk)) continue;
    STAKE_PENDING = s;
    combatSay(s.say + ' Risk: ' + itemName(s.risk) + '. Gain: '
      + itemName(s.reward) + '. [Y] stake it, [N] walk away.');
    stakesShow(s);
    return;
  }
}

// ---- the offer, answerable without a keyboard (vefr#504) ----
// The keys are still the keys: Y and N answer exactly as before. What
// the buttons add is that the offer can now be ANSWERED at all on a
// phone, which before this a player on one could not do - they could
// read the offer, and could only walk away from it by standing still.
//
// Both buttons run the same two functions the keys run, so there is one
// answer to an offer and one set of consequences, whichever way the
// player gave it. The row lives under the offer line in the top corner
// and the fight verbs live at the foot of the frame, so answering never
// stands over a verb the player might want next.
function stakesHost() {
  return document.getElementById('stake-ask');
}

// Take the buttons away: the offer is answered, or there is no offer.
function stakesClose() {
  var host = stakesHost();
  if (!host) return;
  while (host.firstChild) host.removeChild(host.firstChild);
  host.hidden = true;
}

function stakeButton(id, cls, label, said, run) {
  var b = document.createElement('button');
  b.type = 'button';
  b.id = id;
  b.className = cls;
  b.textContent = label;
  // The accessible name keeps the words on the face of the button and
  // then names what the answer costs, so a screen reader hears the
  // choice and not just its name.
  b.setAttribute('aria-label', label + ': ' + said);
  b.addEventListener('click', run);
  return b;
}

function stakesShow(s) {
  var host = stakesHost();
  if (!host) return;
  stakesClose();
  var walk = stakeButton('stake-walk', 'stake-btn',
    'Walk away', 'keep ' + itemName(s.risk) + ' and lose nothing', stakeWalk);
  var take = stakeButton('stake-take', 'stake-btn stake-btn--take',
    'Take the stake', 'put ' + itemName(s.risk) + ' down and gain '
      + itemName(s.reward), stakeTake);
  host.appendChild(take);
  host.appendChild(walk);
  host.hidden = false;
  // Focus opens on the answer that costs nothing. A player who walked
  // to this tile by accident should not have to read a button before
  // they can press one.
  walk.focus();
}

// Y: the player's own answer, the only thing that takes anything away.
// Both moves go through the surfaces the game already had - the bag
// and the line - so nothing here is a new subsystem.
function stakeTake() {
  var s = STAKE_PENDING;
  if (!s) return;
  STAKE_PENDING = null;
  stakesClose();
  // The risk must still be in the bag at the moment of answering: the offer may have been open
  // while the player used or dropped it. No risk put down, no reward, and the stake is not spent
  // (#535 review: the reward was granted for free).
  if (!bagRemoveOne(s.risk)) {
    combatSay('You no longer carry ' + itemName(s.risk) + ', so there is nothing to stake.');
    return;
  }
  STAKES_TAKEN.push(s.id);
  if (bagAdd(s.reward, null, true)) {
    combatSay('You put ' + itemName(s.risk) + ' down. You take '
      + itemName(s.reward) + '.');
  } else {
    combatSay('You put ' + itemName(s.risk) + ' down, and nothing comes '
      + 'back for it.');
  }
}

// N: the walk-away. Nothing leaves the bag, nothing is remembered
// against the player, and the next matching event asks again.
function stakeWalk() {
  if (!STAKE_PENDING) return;
  STAKE_PENDING = null;
  stakesClose();
  combatSay('You walk away from it. Nothing is lost.');
}

// One key answers an offer and nothing else: Y takes the risk, N walks
// away, and every other key is left to mean what it always meant. A
// player who presses neither keeps everything, which is the whole of
// what "optional" has to promise.
function stakesKey(e) {
  if (!STAKE_PENDING || e.repeat) return false;
  var k = (e.key && e.key.length === 1) ? e.key.toLowerCase() : '';
  if (k === 'y') { stakeTake(); return true; }
  if (k === 'n') { stakeWalk(); return true; }
  return false;
}

// What the stakes are doing, as the published snapshot the browser tests
// read: how many the pack declared, the offer waiting for an answer
// (null when none), and the ids the player has staked. `pending` is
// also how a reader knows the offer is OPEN - it is the offer's id
// while the two buttons are on screen and null the moment one of them
// has answered, so nothing else has to be published for it.
window.VEFR_STAKES_STATE = function () {
  return {
    declared: stakesOffered().length,
    pending: STAKE_PENDING ? STAKE_PENDING.id : null,
    taken: STAKES_TAKEN.slice()
  };
};

