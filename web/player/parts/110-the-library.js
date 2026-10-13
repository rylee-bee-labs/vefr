// ---- the library: books a world keeps, found and read in play ----
// A book is found on the map, from a resident, on the shelf from the
// start, or earned by an event the player can observe. No timers, no
// pressure: finding a book never costs anything. The baked list is
// window.VEFR_LIBRARY; a pack with no books is [].
var LIBRARY_KEY = 'vefr-library-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');

function libraryBooks() {
  return Array.isArray(window.VEFR_LIBRARY) ? window.VEFR_LIBRARY : [];
}

function booksFound() {
  var ids = store.getJSON(LIBRARY_KEY, []);
  return Array.isArray(ids) ? ids.filter(function (id) { return typeof id === 'string'; }) : [];
}

function bookIsFound(id) { return booksFound().indexOf(id) !== -1; }

function libraryRemember(id) {
  var ids = booksFound();
  if (ids.indexOf(id) === -1) {
    ids.push(id);
    store.setJSON(LIBRARY_KEY, ids);
  }
}

function libraryToast(book) {
  var live = document.getElementById('library-live');
  if (!live) return;
  live.textContent = 'You found a book: ' + ((book && book.title) || 'a book')
    + '. Open Books from the menu.';
}

function foundBook(book, how, open) {
  if (!book || !book.id) return;
  libraryRemember(book.id);
  libraryToast(book);
  renderBooksPanel();
  if (open !== false) openReader(book);
}

// Map books: grant when the hero stands on the named tile, on the map
// the book names (a room's book lies in that room, not the town).
function libraryOnTile(x, y, region) {
  libraryBooks().forEach(function (b) {
    if (!b || b.chest || b.found !== 'map' || !Array.isArray(b.at)) return;
    if ((b.region || 'town') !== region) return;
    if (b.at[0] === x && b.at[1] === y && !bookIsFound(b.id)) foundBook(b, 'map');
  });
}

// Resident books: grant when the nearest speaker answers. The reader
// stays closed here - the resident's own line is about to show in the
// speech box, and the toast points at the Books panel.
function libraryFromSpeaker(key) {
  libraryBooks().forEach(function (b) {
    if (!b || b.found !== 'resident' || b.speaker !== key) return;
    if (!bookIsFound(b.id)) foundBook(b, 'resident', false);
  });
}

// Earned books the player can see. `first-visit` fires on the first
// load in a world (no saved found-list yet); `book:<id>` once that
// book has been read. `bell`, `act-complete` and `rumor-verified` name
// events the woven player has no way to observe, so they stay unfound
// here rather than invent one.
function libraryFirstVisit() {
  // A first visit is the load with no saved found-list yet.
  if (store.get(LIBRARY_KEY) !== null) return;
  libraryBooks().forEach(function (b) {
    if (b && b.found === 'earned' && b.when === 'first-visit' && !bookIsFound(b.id)) {
      foundBook(b, 'first-visit');
    }
  });
}

function libraryAfterRead(book) {
  if (!book || !book.id) return;
  libraryBooks().forEach(function (b) {
    if (!b || b.found !== 'earned') return;
    if (b.when === 'book:' + book.id && !bookIsFound(b.id)) foundBook(b, 'read');
  });
}

// The reader: one page at a time, the author's words as plain text.
var readerBook = null;
var readerPage = 0;
var readerOpener = null;

function readerPageCount(book) {
  return Array.isArray(book && book.pages) ? book.pages.length : 0;
}

function renderReader() {
  if (!readerBook) return;
  var n = readerPageCount(readerBook);
  document.getElementById('reader-text').textContent =
    n ? String(readerBook.pages[readerPage] || '') : '';
  document.getElementById('reader-page-num').textContent =
    n ? 'Page ' + (readerPage + 1) + ' of ' + n : 'No pages';
  document.getElementById('reader-back').disabled = readerPage <= 0;
  document.getElementById('reader-next').disabled = readerPage >= n - 1;
}

function openReader(book) {
  if (!book) return;
  readerBook = book;
  readerPage = 0;
  readerOpener = document.activeElement;
  document.getElementById('reader-title').textContent = book.title || 'A book';
  document.getElementById('reader-page-num').textContent = '';
  document.getElementById('reader').hidden = false;
  renderReader();
  document.getElementById('reader').focus();
}

// complete-act: a story beat the pack says is finished. One end card on
// the same overlay surface as a note: "Keep exploring" (what Interact
// does) or "Start over" (which asks first, in the menu). It never
// advances to another act. window.VEFR_ACT_COMPLETE is the harness
// snapshot, like VEFR_COMBAT.
var actEndOpener = null;
function openActEnd(actId) {
  var card = document.getElementById('act-end');
  if (!card) return;
  soundCue('end');
  var w = window.VEFR_WORLD || {};
  document.getElementById('act-end-title').textContent = w.title || w.name || 'The end';
  document.getElementById('act-end-line').textContent =
    'This part of the story is complete. You can keep exploring, or start over.';
  actEndOpener = document.activeElement;
  card.hidden = false;
  window.VEFR_ACT_COMPLETE = { act: String(actId), shown: true };
  // A `starts` rule can fire before the play area is shown, when a focus
  // call lands nowhere: ask again once the screen has settled.
  var keepBtn = document.getElementById('act-end-keep');
  keepBtn.focus();
  setTimeout(function () { if (!card.hidden) keepBtn.focus(); }, 60);
}
function closeActEnd() {
  var card = document.getElementById('act-end');
  if (!card || card.hidden) return;
  card.hidden = true;
  if (window.VEFR_ACT_COMPLETE) window.VEFR_ACT_COMPLETE.shown = false;
  var back = actEndOpener;
  actEndOpener = null;
  try {
    if (back && back !== document.body && back.focus) back.focus();
    else document.getElementById('menu-open').focus();
  } catch (e) {}
}
document.addEventListener('DOMContentLoaded', function () {
  var keep = document.getElementById('act-end-keep');
  var so = document.getElementById('act-end-startover');
  if (keep) keep.addEventListener('click', closeActEnd);
  if (so) so.addEventListener('click', function () {
    closeActEnd();
    var open = document.getElementById('menu-open');
    if (open) open.click();
    var b = document.querySelector('#menu [data-panel="startover"]');
    if (b) b.click();
  });
});

function closeReader() {
  var reader = document.getElementById('reader');
  if (reader.hidden) return;
  var read = readerBook;
  var opener = readerOpener;
  reader.hidden = true;
  readerBook = null;
  readerOpener = null;
  // Closing a book after reading it is a fact the world may notice:
  // one `reads` per book closed.
  if (read && typeof read.id === 'string') fireRule('reads', { what: read.id });
  // Put focus back where it came from; a body opener (arrow-key play)
  // has nowhere to land, so fall back to the visible Menu button.
  if (opener && opener !== document.body && opener !== document.documentElement
      && opener.focus) {
    try { opener.focus(); } catch (e) {}
  } else {
    var fallback = document.getElementById('menu-open') || document.getElementById('talk');
    if (fallback && fallback.focus) { try { fallback.focus(); } catch (e) {} }
  }
  // A book just read can unlock an earned one (when: book:<id>).
  libraryAfterRead(read);
}

function readerTurn(delta) {
  if (!readerBook) return;
  var n = readerPageCount(readerBook);
  var next = readerPage + delta;
  if (next < 0 || next > n - 1) return;
  readerPage = next;
  renderReader();
}

function renderBooksPanel() {
  var list = document.getElementById('book-list');
  var count = document.getElementById('book-count');
  if (!list) return;
  var books = libraryBooks();
  list.textContent = '';
  if (!books.length) {
    if (count) count.textContent = 'No books in this world yet.';
    return;
  }
  var found = books.filter(function (b) {
    return b && (b.found === 'shelf' || bookIsFound(b.id));
  });
  found.forEach(function (b) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'cta';
    btn.textContent = b.title || 'A book';
    btn.addEventListener('click', function () {
      if (window.closeMenu) window.closeMenu();
      openReader(b);
    });
    list.appendChild(btn);
  });
  if (!found.length) {
    var p = document.createElement('p');
    p.className = 'empty';
    p.textContent = 'No books found yet.';
    list.appendChild(p);
  }
  var remaining = books.filter(function (b) {
    return b && !(b.found === 'shelf' || bookIsFound(b.id));
  }).length;
  if (count) {
    count.textContent = remaining ? remaining + ' still to find'
      : (found.length ? 'Every book found.' : '');
  }
}

// How long the panel stays up on the phone camera before it folds itself, in
// ms. Long enough to read the newest line on a phone, short enough that the
// panel is not over the hero by the time the hero has walked on (issue #430).
var FOLD_MS = 6000;
// On a touch screen the panel is one small line under the top bar, the newest
// thing said, and it fades sooner: the approved phone layout, one message at a
// time, gone after about three seconds (docs/design/storybook/DESIGN.md).
var TOUCH_FOLD_MS = 3000;
function touchMessages() {
  return !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
}
// The message stack is a small corner panel that can be folded away; the lines
// stay in the page (a screen reader still hears them) and the choice is remembered.
function bindMessagePanel() {
  var panel = document.getElementById('toasts');
  var toggle = document.getElementById('toasts-toggle');
  if (!panel || !toggle) return;
  var key = 'vefr-ui-messages-' + ((window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world');
  // A browser test cannot watch six real seconds, so the wait is read from the
  // page when there is one; without it the panel waits exactly as long as it
  // always does.
  function foldMs() {
    var asked = Number(window.VEFR_MESSAGES_FOLD_MS);
    return asked > 0 ? asked : (touchMessages() ? TOUCH_FOLD_MS : FOLD_MS);
  }
  var byHand = store.get(key) === '1';   // a fold by hand is the player's own, and is kept
  var foldTimer = null;
  // The fold the camera does is the same one the toggle does - the lines stay
  // in the page - but only a fold by hand is remembered.
  function setCollapsed(c) {
    panel.classList.toggle('is-collapsed', c);
    toggle.setAttribute('aria-expanded', c ? 'false' : 'true');
  }
  // A touch screen has no Messages button to unfold by hand, so a fold kept
  // from another visit never silences it there.
  function heldByHand() { return byHand && !touchMessages(); }
  function onPhoneCamera() {
    return touchMessages() || !!(window.VEFR_STAGE && window.VEFR_STAGE.phone);
  }
  function foldSoon() {
    if (!onPhoneCamera() || heldByHand()) return;
    if (foldTimer) clearTimeout(foldTimer);
    foldTimer = setTimeout(function () {
      foldTimer = null;
      // Asked again at the fold itself: a window turned sideways, or a line
      // that arrived before the camera published, must not fold a panel the
      // phone camera is no longer drawing under.
      if (!heldByHand() && onPhoneCamera()) setCollapsed(true);
    }, foldMs());
  }
  toggle.addEventListener('click', function () {
    var folded = !panel.classList.contains('is-collapsed');   // folded after this tap
    byHand = folded;
    if (folded && foldTimer) { clearTimeout(foldTimer); foldTimer = null; }
    setCollapsed(folded);
    store.set(key, folded ? '1' : '0');
    foldSoon();   // opened by hand, it folds itself again after the wait
  });
  if (heldByHand()) setCollapsed(true);
  else if (touchMessages()) foldSoon();
  // A new line is a line saying something NEW, not a line being written: a
  // step rewrites the same place name into #poi and the same hint into
  // #use-hint every turn, and a line going quiet clears itself, and neither
  // is a line shown. A line nobody can see (`.sr-only`, `hidden`) is not a
  // line shown either.
  var said = lineTexts();
  (function markOpening() {
    var lines = panel.querySelectorAll('p');
    var last = -1;
    for (var i = 0; i < said.length; i++) if (said[i]) last = i;
    if (last >= 0) lines[last].classList.add('is-newest');
  })();
  function lineTexts() {
    return Array.prototype.map.call(panel.querySelectorAll('p'), function (p) {
      if (p.classList.contains('sr-only') || p.hidden || p.closest('[hidden]')) return '';
      return p.textContent || '';
    });
  }
  if (window.MutationObserver) {
    new MutationObserver(function () {
      var now = lineTexts();
      var fresh = -1;
      for (var i = 0; i < now.length; i++) if (now[i] && now[i] !== said[i]) fresh = i;
      said = now;
      if (fresh < 0 || heldByHand() || !onPhoneCamera()) return;
      // The newest line is the one a touch screen shows; the others stay in
      // the page for a screen reader.
      var lines = panel.querySelectorAll('p');
      Array.prototype.forEach.call(lines, function (p, at) {
        p.classList.toggle('is-newest', at === fresh);
      });
      setCollapsed(false);
      foldSoon();
    }).observe(panel, { childList: true, characterData: true, subtree: true,
                        attributes: true, attributeFilter: ['hidden'] });
  }
}

function bindLibrary() {
  libraryFirstVisit();
  renderBooksPanel();
  bindMessagePanel();
  document.getElementById('reader-close').addEventListener('click', closeReader);
  document.getElementById('reader-back').addEventListener('click', function () { readerTurn(-1); });
  document.getElementById('reader-next').addEventListener('click', function () { readerTurn(1); });
  document.getElementById('trade-close').addEventListener('click', closeTrade);
  document.getElementById('identify-close').addEventListener('click', closeIdentify);
}

