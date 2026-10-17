/* vefr/web/launcher.js: the game-neutral launcher (vefr#454, step 1).
 *
 * Lists the games the server has woven (GET /api/launcher/games) and
 * opens each in the existing woven Player (GET /api/launcher/play/<file>)
 * inside this page's one sandboxed frame. The shell owns nothing a
 * game owns: no title screen, no controls, no saves - each game keeps
 * its own face, and the frame's sandbox (allow-scripts, no origin) is
 * the same line the studio play pane holds.
 *
 * A game's strings arrive from packs that may have been imported, so
 * they are placed as text (textContent) and never as markup. */
(function () {
  'use strict';

  var list = document.getElementById('launcher-games');
  var empty = document.getElementById('launcher-empty');
  var error = document.getElementById('launcher-error');
  var surface = document.getElementById('launcher-surface');
  var frame = document.getElementById('launcher-frame');
  var nowPlaying = document.getElementById('launcher-now');
  var back = document.getElementById('launcher-back');

  function render(games) {
    list.textContent = '';
    empty.hidden = games.length !== 0;
    games.forEach(function (game) {
      var item = document.createElement('li');
      var play = document.createElement('button');
      play.type = 'button';
      play.className = 'launcher-game';
      play.setAttribute('data-name', game.name);
      var title = document.createElement('span');
      title.className = 'launcher-game-title';
      title.textContent = game.title; /* the game's own name, as text */
      var file = document.createElement('span');
      file.className = 'launcher-game-file';
      file.textContent = game.name;
      play.appendChild(title);
      play.appendChild(file);
      item.appendChild(play);
      list.appendChild(item);
    });
  }

  function open(name, title) {
    /* The existing player, whole: its own title screen waits inside
     * the frame. The bar shows only the game's own name, as text. */
    frame.removeAttribute('src'); /* a fresh document, never a stale one */
    frame.src = '/api/launcher/play/' + encodeURIComponent(name);
    nowPlaying.textContent = title;
    surface.hidden = false;
    back.focus();
  }

  function close() {
    /* Leaving stops the game: the frame is emptied, not left running
     * behind the list. A game's own saves are the game's affair. */
    frame.removeAttribute('src');
    surface.hidden = true;
    nowPlaying.textContent = '';
    var first = list.querySelector('.launcher-game');
    if (first) first.focus();
  }

  list.addEventListener('click', function (e) {
    var btn = e.target.closest('.launcher-game');
    if (!btn) return;
    open(btn.getAttribute('data-name'),
         btn.querySelector('.launcher-game-title').textContent);
  });

  back.addEventListener('click', close);

  fetch('/api/launcher/games')
    .then(function (r) { return r.json(); })
    .then(function (data) { render((data && data.games) || []); })
    .catch(function () { error.hidden = false; });
}());