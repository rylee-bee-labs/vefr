// ---- pause menu: journal, help, model settings ----
function bindMenu() {
  var menu = document.getElementById('menu');
  var opener = document.getElementById('menu-open');
  if (!MODEL_OPTIONAL) {
    var modelItem = menu.querySelector('[data-panel="model"]');
    if (modelItem) modelItem.closest('li').remove();
  }
  // The Album button exists only when the pack declares an album
  // (design/album.md): a pack without one has no shelf to show.
  if (!ALBUM_DEF) {
    var albumItem = menu.querySelector('[data-panel="album"]');
    if (albumItem) albumItem.closest('li').remove();
  }
  // Back to the library: the shelf the pack names for this game, when it
  // names one. A pack with no `player.library_url` bakes no URL, and the
  // row stays hidden rather than shown and refused - the same shape the
  // album and descent rows keep.
  var libraryRow = document.getElementById('menu-library-row');
  var libraryUrl = (window.VEFR_HERO && window.VEFR_HERO.library_url) || '';
  if (libraryRow && libraryUrl) {
    var libraryLink = document.getElementById('menu-library');
    if (libraryLink) libraryLink.setAttribute('href', libraryUrl);
    libraryRow.hidden = false;
  }
  function showPanel(name) {
    menu.querySelectorAll('[data-panel]').forEach(function (b) {
      b.setAttribute('aria-current', b.dataset.panel === name ? 'true' : 'false');
    });
    menu.querySelectorAll('[data-panel-body]').forEach(function (d) {
      d.hidden = d.dataset.panelBody !== name;
    });
  }
  window.openMenu = function () {
    menu.hidden = false; showPanel('journal');
    document.getElementById('menu-close').focus();
  };
  // Straight to the bag: a key and a button, not only the pause menu.
  window.openBag = function () {
    menu.hidden = false; showPanel('bag');
    document.getElementById('menu-close').focus();
  };
  window.closeMenu = function () { menu.hidden = true; opener.focus(); };
  opener.addEventListener('click', window.openMenu);
  document.getElementById('menu-close').addEventListener('click', window.closeMenu);
  menu.querySelectorAll('[data-panel]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (b.dataset.panel === 'startover') { showStartover(); return; }
      showPanel(b.dataset.panel);
      // The two evidence panels render on open: fresh, and only ever
      // from real records (the point-to hints; the fired rules).
      if (b.dataset.panel === 'next') renderNextPanel();
      if (b.dataset.panel === 'why') renderWhyPanel();
      if (b.dataset.panel === 'album') renderAlbumPanel();
    });
  });
  // Start over: one confirmation, safe by default (focus lands on
  // Cancel, never the destructive button); Escape and Cancel change
  // nothing; confirming clears every vefr- save on this site, then
  // reloads to the title screen.
  var startoverBody = document.getElementById('startover-body');
  var startoverCancel = document.getElementById('startover-cancel');
  var startoverConfirm = document.getElementById('startover-confirm');
  function showStartover() {
    showPanel('startover');
    if (startoverCancel) startoverCancel.focus();
  }
  window.cancelStartover = function () {
    showPanel('journal');
    var back = document.getElementById('menu-close');
    if (back) back.focus();
  };
  if (startoverCancel) startoverCancel.addEventListener('click', window.cancelStartover);
  if (startoverConfirm) startoverConfirm.addEventListener('click', function () {
    try { window.startoverKeys(store.raw()); } catch (e) { /* blocked storage: nothing to clear */ }  // every vefr- key on this site
    window.location.reload();
  });
  if (startoverBody) startoverBody.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab' || !startoverCancel || !startoverConfirm) return;
    e.preventDefault();
    (document.activeElement === startoverCancel ? startoverConfirm
                                                : startoverCancel).focus();
  });
  document.getElementById('menu-model').addEventListener('click', function () {
    menu.hidden = true;
    play.hidden = true; configBox.hidden = false;
    document.body.classList.remove('in-game');
    document.getElementById('cfg-url').value = llmUrl;
    document.getElementById('cfg-model').value = llmModel;
    document.getElementById('cfg-url').focus();
    // Returning keeps the running game; only the in-game frame comes back.
    var back = function () { document.body.classList.add('in-game'); };
    document.getElementById('cfg-save').addEventListener('click', back, { once: true });
    document.getElementById('cfg-offline').addEventListener('click', back, { once: true });
  });
}

