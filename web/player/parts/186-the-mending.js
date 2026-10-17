// ---- mending: two carried things become one (E2) ----
// A pack that declares no `recipes` shows no Mend control anywhere and
// plays exactly as it did - the whole feature hangs off the one read of
// window.VEFR_WORLD.recipes below. A pack that declares them gives every
// bag row a "Mend with..." button: pick one thing, pick the second, and
// a preview names what the pair makes before anything is spent. Mend
// consumes one copy of each input and adds the output; Cancel changes
// nothing; a pair no recipe names says plainly that nothing fits. The
// mend fires the rules engine's `mends` event with the recipe id, so a
// pack can react to it, and the last mend is published on
// window.VEFR_LAST_MEND for the harness snapshots to read.
window.VEFR_LAST_MEND = null;

// The recipe being mended with, if one is chosen: the first pick waits
// for its partner; the plan stands until Mend or Cancel ends it. Both
// live only for as long as the panel is open - nothing is saved, so no
// pack that never mends has a new storage key.
var MEND_PICK = null;
var MEND_PLAN = null;

// The pack's recipes, or none at all. A record the shape refused is not
// here: `vefr check` names it, and play never guesses at it.
function mendRecipes() {
  var world = window.VEFR_WORLD;
  var listed = (world && Array.isArray(world.recipes)) ? world.recipes : [];
  return listed.filter(function (r) {
    return r && typeof r === 'object' && typeof r.id === 'string'
      && Array.isArray(r.inputs) && r.inputs.length === 2
      && typeof r.output === 'string';
  });
}
function mendOn() {
  return mendRecipes().length > 0;
}

// The recipe that mends this pair, either way round - mending the peg
// with the net is the same mend as mending the net with the peg.
function mendRecipeFor(a, b) {
  var found = null;
  mendRecipes().forEach(function (r) {
    if (found) return;
    var i = r.inputs;
    if ((i[0] === a && i[1] === b) || (i[0] === b && i[1] === a)) found = r;
  });
  return found;
}

// Is the pair still carried - one copy of each, two when a recipe mends
// a thing with itself? The preview can stand open while a rule or a
// trade changes the bag, so the mend asks again before it spends.
function mendPairCarried(a, b) {
  var need = {};
  need[a] = (need[a] || 0) + 1;
  need[b] = (need[b] || 0) + 1;
  var have = {};
  bagItems().forEach(function (id) { have[id] = (have[id] || 0) + 1; });
  return Object.keys(need).every(function (id) {
    return (have[id] || 0) >= need[id];
  });
}

// What the output grants, as verbs, when the pack gave it a `grants`.
// The shape of `grants` is the item-verbs slice's to settle; this reads
// the three ways a verb list is written (a list of names, a list of
// records naming one, a table keyed by verb) so the preview shows what
// it can while that slice lands, and shows nothing when the pack gave
// nothing - which is every pack today.
function mendGrantVerbs(def) {
  var grants = def && def.grants;
  if (!grants) return [];
  if (Array.isArray(grants)) {
    return grants.map(function (v) {
      if (typeof v === 'string') return v;
      if (v && typeof v === 'object' && typeof v.verb === 'string') return v.verb;
      return '';
    }).filter(function (v) { return !!v; });
  }
  if (typeof grants === 'object') return Object.keys(grants);
  return [];
}

// One bag row's Mend button, or null when the pack declares no recipes
// (renderBagPanel's row loop asks; a pack without recipes never sees a
// Mend control at all). While nothing is picked the button offers the
// first thing; once something is, the other rows offer the second, and
// the picked row offers to stop - unless a recipe mends the thing with
// itself and a second copy is carried, when it offers the second too.
function mendRowControl(id) {
  if (!mendOn()) return null;
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'cta';
  btn.dataset.item = id;
  btn.dataset.action = 'mend';
  if (MEND_PICK === null) {
    btn.textContent = 'Mend with...';
    btn.setAttribute('aria-label', 'Mend ' + itemName(id) + ' with something');
    btn.addEventListener('click', function () {
      MEND_PLAN = null;
      MEND_PICK = id;
      renderBagPanel();
    });
  } else if (MEND_PICK === id && !(mendRecipeFor(id, id)
             && mendPairCarried(id, id))) {
    btn.textContent = 'Stop mending';
    btn.setAttribute('aria-label', 'Stop mending with ' + itemName(id));
    btn.addEventListener('click', function () {
      MEND_PICK = null;
      MEND_PLAN = null;
      renderBagPanel();
    });
  } else {
    btn.textContent = 'Mend with this';
    btn.setAttribute('aria-label',
      'Mend ' + itemName(MEND_PICK) + ' with ' + itemName(id));
    btn.addEventListener('click', function () {
      mendPair(MEND_PICK, id);
    });
  }
  return btn;
}

// The second thing is chosen: a matched pair stands as a plan with its
// preview below the list; an unmatched one says plainly that nothing
// fits, and the first pick stays so another partner can be tried.
function mendPair(a, b) {
  var recipe = mendRecipeFor(a, b);
  MEND_PLAN = recipe ? { recipe: recipe, a: a, b: b } : null;
  renderBagPanel();
  if (!recipe) {
    bagSay('Nothing you carry mends ' + itemName(a) + ' with ' + itemName(b) + '.');
  }
}

// The preview under the list, redrawn with the panel: what the pair
// makes and what it grants, with Mend and Cancel. The words are all
// there on the first frame - nothing waits on a timer, so the screen
// reader reads what the eye reads.
function renderMendPanel() {
  var host = document.getElementById('mend-preview');
  if (!host) return;
  host.textContent = '';
  host.hidden = true;
  if (!mendOn()) return;
  if (MEND_PLAN) {
    var plan = MEND_PLAN;
    host.hidden = false;
    var line = document.createElement('p');
    line.className = 'status';
    line.textContent = 'Mending ' + itemName(plan.a) + ' and '
      + itemName(plan.b) + ' makes ' + itemName(plan.recipe.output) + '.';
    host.appendChild(line);
    var verbs = mendGrantVerbs(itemCatalog()[plan.recipe.output]);
    if (verbs.length) {
      var granted = document.createElement('p');
      granted.className = 'status';
      granted.textContent = 'It grants: ' + verbs.join(', ') + '.';
      host.appendChild(granted);
    }
    var mend = document.createElement('button');
    mend.type = 'button';
    mend.id = 'mend-confirm';
    mend.className = 'cta cta--gold';
    mend.textContent = 'Mend';
    mend.setAttribute('aria-label',
      'Mend ' + itemName(plan.a) + ' and ' + itemName(plan.b) + ' into '
      + itemName(plan.recipe.output));
    mend.addEventListener('click', doMend);
    host.appendChild(mend);
    var cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.id = 'mend-cancel';
    cancel.className = 'cta';
    cancel.textContent = 'Cancel';
    cancel.setAttribute('aria-label', 'Cancel mending ' + itemName(plan.a));
    cancel.addEventListener('click', cancelMend);
    host.appendChild(cancel);
  } else if (MEND_PICK) {
    bagSay('Mend ' + itemName(MEND_PICK)
      + ' with what? Choose the second thing.');
  }
}

// The mend itself: both inputs are spent, the output is carried, the
// pack hears the `mends` event and the last mend is published. The
// output always fits - two things became one, and a full bag never
// refuses the thing it just made.
function doMend() {
  var plan = MEND_PLAN;
  if (!plan) return;
  if (!mendPairCarried(plan.a, plan.b)) {
    MEND_PLAN = null;
    MEND_PICK = null;
    renderBagPanel();
    bagSay('Nothing mended: the things to mend are no longer carried.');
    return;
  }
  MEND_PLAN = null;
  MEND_PICK = null;
  bagRemoveOne(plan.a);
  bagRemoveOne(plan.b);
  bagAdd(plan.recipe.output, null, true);
  window.VEFR_LAST_MEND = {
    recipe: plan.recipe.id,
    inputs: [plan.a, plan.b],
    output: plan.recipe.output
  };
  fireRule('mends', { recipe: plan.recipe.id });
  renderBagPanel();
  bagSay(plan.recipe.say
    || ('You mend ' + itemName(plan.a) + ' and ' + itemName(plan.b)
      + ' into ' + itemName(plan.recipe.output) + '.'));
}

// Cancel: the plan and the pick are let go, the bag is untouched.
function cancelMend() {
  MEND_PLAN = null;
  MEND_PICK = null;
  renderBagPanel();
  bagSay('Nothing mended.');
}