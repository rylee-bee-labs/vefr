// ---- dialog focus: Tab stays inside an open dialog, and comes back to the opener
// (issue #462). Every box that opens over the game here is a `role="dialog"`:
// the pause menu, a book, a character's line, a trade, the identify list, the
// two end cards. The page behind them never stops being focusable, so one Tab
// walked out of the box and into Menu, Messages, Talk, Whisper, Bag and Explore
// (run-004: "Keyboard focus during dialogs often drifted to underlying page
// buttons"; run-002 and run-003 found Close and Read on several Tabs away).
//
// Two rules, one for every dialog, so a new box gets them for free:
//   1. Tab and Shift+Tab cycle the controls of the dialog that is open, and
//      never step onto the page behind it.
//   2. A dialog that closes while the focus is on it - or on nothing, because
//      a browser drops focus to the body the moment the control holding it is
//      hidden - hands focus back to the control it was opened from. A close
//      that already put focus somewhere is left alone: the menu returning to
//      the Menu button, and Start over asking its question in the same box,
//      both know where they want the focus.
function bindDialogFocus() {
  var DIALOG = '[role="dialog"]';
  var records = [];         // one per dialog: {el: dialog, open: bool, opener: node}
  var outside = null;       // the last control focused outside every dialog

  // On screen now: not hidden, and not inside anything hidden. Every dialog in
  // this player opens and closes on the `hidden` attribute, but a dialog can
  // sit inside a hidden parent (the play surface is hidden until the game is
  // entered), so the ancestors are asked as well.
  function onScreen(el) {
    for (var cur = el; cur; cur = cur.parentElement) {
      if (cur.hidden) return false;
      if (cur.style && cur.style.display === 'none') return false;
    }
    return true;
  }

  // The stops a Tab walks inside one dialog, in the order it walks them. A
  // disabled control, one with tabindex="-1", and one inside a panel that is
  // hidden (the pause menu keeps ten panels, one open) are steps past.
  function stops(dialog) {
    var all = dialog.querySelectorAll(
      'a[href], button, input, select, textarea, [tabindex]');
    return Array.prototype.filter.call(all, function (el) {
      if (el.disabled) return false;
      if (el.getAttribute('tabindex') === '-1') return false;
      return onScreen(el);
    });
  }

  // The dialog a key belongs to: the last one on screen in the page. The
  // pause menu is last in the markup, so a box opened on top of it wins.
  // A page that is being torn down (a reload, a closed window) has no
  // document left to ask; nothing is open there.
  function alive() { return typeof document !== 'undefined' && !!document && !!document.querySelectorAll; }

  function topDialog() {
    if (!alive()) return null;
    var list = document.querySelectorAll(DIALOG);
    for (var i = list.length - 1; i >= 0; i--) {
      if (onScreen(list[i])) return list[i];
    }
    return null;
  }

  document.addEventListener('keydown', function (e) {
    // `defaultPrevented` first: Start over already owns the Tab between its
    // two buttons, and its handler runs before this one.
    if (e.key !== 'Tab' || e.defaultPrevented) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    var dialog = topDialog();
    if (!dialog) return;
    var here = stops(dialog);
    // A box with nothing to press keeps the Tab on itself rather than letting
    // it walk out into the page.
    if (!here.length) {
      e.preventDefault();
      if (dialog.focus) dialog.focus();
      return;
    }
    var at = here.indexOf(document.activeElement);
    var to;
    if (at === -1) to = e.shiftKey ? here[here.length - 1] : here[0];
    else if (e.shiftKey) to = here[(at - 1 + here.length) % here.length];
    else to = here[(at + 1) % here.length];
    e.preventDefault();
    to.focus();
  });

  function recordFor(dialog) {
    for (var i = 0; i < records.length; i++) {
      if (records[i].el === dialog) return records[i];
    }
    var rec = { el: dialog, open: false, opener: null };
    records.push(rec);
    return rec;
  }

  // Somewhere a focus can actually land: still in the page, still on screen.
  function landable(el) {
    return !!(el && el.focus && el !== document.body
              && el !== document.documentElement && onScreen(el));
  }

  // The one place that watches the dialogs. It is told about an open and a
  // close by the `hidden` attribute either way, so a dialog is trapped and
  // answered for without every surface that opens one knowing this part
  // exists.
  function sync() {
    if (!alive()) return;
    var list = document.querySelectorAll(DIALOG);
    for (var i = 0; i < list.length; i++) {
      var dialog = list[i];
      var rec = recordFor(dialog);
      var now = onScreen(dialog);
      if (now === rec.open) continue;
      rec.open = now;
      if (now) {
        rec.opener = outside;
        // A dialog that opens and leaves the focus on the page behind it would
        // let the next key act on the page: put the focus on its first control,
        // after the surface that opened it has had its own say.
        (function (d) {
          setTimeout(function () {
            if (!alive() || !onScreen(d) || topDialog() !== d) return;
            var a = document.activeElement;
            if (a && d.contains(a)) return;
            var first = stops(d)[0];
            if (first) first.focus(); else if (d.focus) d.focus();
          }, 0);
        })(dialog);
        continue;
      }
      var back = rec.opener;
      rec.opener = null;
      var here = document.activeElement;
      var lost = !here || here === document.body || here === document.documentElement
                 || dialog.contains(here);
      if (!lost) continue;
      // An opener that has since left the page (the book button of a panel
      // that closed with it) is no place to send the focus; the Menu button
      // is the one control every surface has.
      if (!landable(back)) back = document.getElementById('menu-open');
      // Another dialog still open (or just opened) owns the focus now: the
      // opener behind it is not where the next key should go.
      var still = topDialog();
      if (still && !(back && still.contains(back))) continue;
      if (landable(back)) { try { back.focus(); } catch (e) { /* gone */ } }
    }
  }

  // The opener is remembered as the last control focused outside every dialog,
  // which is known before a dialog moves focus into itself - a "who has the
  // focus now" read at open time would only ever answer with the dialog.
  document.addEventListener('focusin', function (e) {
    var d = topDialog();
    if (!d) { outside = e.target; return; }
    // A focus that lands on the page behind an open dialog (a script focusing
    // its own button, a click on the page) is brought back into the dialog.
    if (!d.contains(e.target)) {
      var first = stops(d)[0];
      if (first && first !== e.target) first.focus();
      else if (d.focus && d !== e.target) d.focus();
    }
  });

  if (window.MutationObserver) {
    new MutationObserver(sync).observe(document.documentElement,
      { attributes: true, subtree: true, attributeFilter: ['hidden'] });
  }
}
bindDialogFocus();
