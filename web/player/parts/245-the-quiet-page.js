// ---- the quiet page and the calm fall card (vefr#484, mockup C) ----
// The Journal is one quiet page: every line the world said, in order,
// newest at the top, older lines a little quieter (never lighter than
// the contrast floor), whispers and falls interleaved as plain lines
// among them. No tabs, no chips, no grouping - the page reads like a
// letter someone kept.
//
// The page is written at the two seams where the world says words:
// `combatSay`, the one plain sentence the fight and the finds speak
// with, and `showSpeech`, whoever is talking. A line lands on the page
// at the moment it is said, so nowhere else needs to know the page
// exists - and the fading line over the world is exactly what it was.
//
// Computed per call and never cached, like the player's own settings
// keys: a world that arrives late still finds its own key, and a reader
// sees one place where the name is spelled.
function pageKey() {
  return 'vefr-page-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
}

// One line on the page. `who` is the caption a spoken line carries -
// the whisper's "You overhear <the speaker>", a resident's own name -
// and a line with no speaker is a plain line, as the fight's are.
function journalSay(line, who) {
  var text = String(line || '').trim();
  if (!text) return;
  var log = store.getJSON(pageKey(), []);
  log.push({ line: text, who: who || '', at: new Date().toISOString() });
  store.setJSON(pageKey(), log);
  renderJournalPage(log);
}

// The page itself, newest first: the newest line is full ink and the
// older ones step down to the quieter ink, one list read top to bottom.
function renderJournalPage(log) {
  var page = document.getElementById('journal-page');
  if (!page) return;
  log = log || store.getJSON(pageKey(), []);
  page.textContent = '';
  if (!log.length) {
    var empty = document.createElement('li');
    empty.className = 'empty';
    empty.textContent = 'Nothing yet. Listen for a whisper to hear what people are saying.';
    page.appendChild(empty);
    return;
  }
  for (var i = log.length - 1; i >= 0; i--) {
    var entry = log[i] || {};
    var li = document.createElement('li');
    if (i === log.length - 1) li.className = 'newest';
    if (entry.who) {
      var who = document.createElement('span');
      who.className = 'who';
      who.textContent = entry.who;
      li.appendChild(who);
      var q = document.createElement('q');
      q.textContent = entry.line;
      li.appendChild(q);
    } else {
      li.textContent = entry.line;
    }
    page.appendChild(li);
  }
}

// The panel's own Close, at the top of the page: the Journal is the
// panel it always was, opened the way the Bag opens, and one Close
// closes the whole menu, as Resume does.
(function () {
  var close = document.getElementById('journal-close');
  if (close) close.addEventListener('click', function () {
    if (window.closeMenu) window.closeMenu();
  });
})();
renderJournalPage();

// ---- the fall, as a warm hush ----
// The world dims deep and one small quiet card waits near the bottom,
// holding the words the game already says. Nothing is asked of the
// player: no timer, no flash, no shake, and any key, tap or button
// continues. The focus moves onto the card and comes back to the
// control that had it (045-dialog-focus.js keeps the Tab inside it);
// the dim fades in over a moment, and the reduced-motion blankets -
// the OS's own query and the player's switch - make it instant, the
// same answer every other motion reads.
var fallOpener = null;
function showFallCard(line) {
  var card = document.getElementById('fall');
  if (!card || !card.hidden) return;
  document.getElementById('fall-line').textContent = line || '';
  // The words are kept on the quiet page the moment they are said.
  journalSay(line);
  fallOpener = document.activeElement;
  card.hidden = false;
  var keep = document.getElementById('fall-keep');
  if (keep) keep.focus();
}
function closeFall() {
  var card = document.getElementById('fall');
  if (!card || card.hidden) return;
  card.hidden = true;
  var back = fallOpener;
  fallOpener = null;
  try {
    if (back && back !== document.body && back !== document.documentElement
        && back.isConnected && back.focus) back.focus();
    else document.getElementById('menu-open').focus();
  } catch (e) { /* gone */ }
}
(function () {
  var card = document.getElementById('fall');
  if (!card) return;
  document.getElementById('fall-keep').addEventListener('click', closeFall);
  // A tap anywhere on the hush continues it: the dim is the card's own
  // waiting room, and the one button is another way to say go on.
  card.addEventListener('click', closeFall);
})();