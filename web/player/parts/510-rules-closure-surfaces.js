  // ---- the rules engine's three closure-only surfaces ----
  // fireRule lives at top level (the title card and the bag call it);
  // these three hand it what only this closure owns. All three are
  // registered during setup, before any event can fire.
  // `weather`: the player's own darkness preference, the Display
  // switch's exact path. A pack's fog declaration is never deleted -
  // it is the player's choice - and the toggle's label and
  // aria-pressed are re-read from the honest fogOn every time.
  window.VEFR_RULES_WEATHER = function (on) {
    if (on !== fogPrefOn()) setFogPref(on);
    var want = fogEnabled();
    if (want !== fogOn) {
      fogOn = want;
      if (!fogOn && exploring()) exploreStop('Stopped.');
      resize();
      draw();
    }
    renderFogToggle();
    if (fogLive) fogLive.textContent = fogOn ? 'Darkness on.' : 'Darkness off.';
  };
  // `point-to`: one plain hint line. The direction is from the hero
  // toward the way the transitions declare into the target region -
  // the door out of this region when one starts here, else the
  // declared entrance the hero would land at. A pack that declares no
  // way there still gets one honest line, without a direction.
  window.VEFR_RULES_POINT_TO = function (place) {
    var fromHere = null, entrance = null;
    var list = transitions();
    for (var i = 0; i < list.length; i++) {
      var t = list[i];
      if (t.to === place && !entrance && Array.isArray(t.to_at)) entrance = t.to_at;
      if (t.from === regionName && t.to === place && Array.isArray(t.at)) {
        fromHere = t.at;
        break;
      }
    }
    var at = fromHere || entrance;
    // The words the player reads for the place (vefr#363): a floor of a
    // labelled Section is its title ("the Cellar, floor 1"), anything
    // else the region id exactly as before. The id stays the record's
    // key, so the rules and the save never see the label.
    var D = window.VEFR_DESCENT;
    var shown = (D && typeof D.placeName === 'function') ? D.placeName(place) : place;
    if (!at) {
      var lost = playerWord('where_next.no_way', { place: shown });
      combatSay(lost);
      rulesNextRecord(place, lost, shown);
      return;
    }
    var dx = at[0] - hero[0], dy = at[1] - hero[1];
    var vert = dy < 0 ? 'north' : (dy > 0 ? 'south' : '');
    var horiz = dx < 0 ? 'west' : (dx > 0 ? 'east' : '');
    var dir = vert && horiz ? vert + '-' + horiz : (vert || horiz);
    // The line the player reads to know what to do, spoken from the
    // message table rather than built here: a pack may name its own
    // word for it (part 340), and a pack that names none gets these
    // exact bytes.
    var line = dir
      ? playerWord('where_next.reach', { place: shown, direction: dir })
      : playerWord('where_next.here', { place: shown });
    combatSay(line);
    // The hint is an intention, not a flash: it stays in the menu's
    // Where next? panel until the world points somewhere new.
    rulesNextRecord(place, line, shown);
  };
  // show/hide/reveal: the floor is the only surface a thing has in
  // this player - an item can lie where the hero stands (shown) or be
  // taken back out of sight (hidden). A speaker or a region has no
  // show/hide surface to walk up, so naming one is skipped silently
  // (the exact gap is on the commit), and a reveal AS A MONSTER would
  // need place_enemy, which the rule vocabulary does not have.
  window.VEFR_RULES_SURFACE = function (verb, id) {
    if (!itemCatalog()[id]) return;
    if (verb === 'hide') {
      var before = floor.length;
      floor = floor.filter(function (d) { return !d || d.item !== id; });
      if (floor.length !== before) saveFloor();
      return;
    }
    for (var i = 0; i < floor.length; i++) {
      var d = floor[i];
      if (d && d.item === id && d.region === regionName
          && d.at[0] === hero[0] && d.at[1] === hero[1]) return;
    }
    placeDrops(hero, [id]);
  };

  // The verbs. The journal is local storage - same honest shape as
  // the server route's entries, minus the server.
  renderCombatLog(store.getJSON(COMBAT_KEY, []));
  /* The act's verbs are the pack's own vocabulary; baked defaults
     keep the old costume when the act declares none. The list lives
     in surfaceVerbs() so the row and the enemy menu share one home. */
  (function () {
    var row = document.getElementById('verb-row');
    var verbs = surfaceVerbs();
    verbs.forEach(function (pair) {
      var b = document.createElement('button');
      b.type = 'button';
      b.dataset.verb = pair[0];
      b.textContent = pair[1];
      row.appendChild(b);
    });
  })();
  document.getElementById('verb-row').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-verb]');
    if (!b) return;
    b.disabled = true;
    recordVerb(b.dataset.verb);
    // With an enemy named, the press resolves against it and the
    // monsters take their turn, exactly as after a bump. With no
    // target the press is only journalled, as it always was.
    if (VERB_TARGET) {
      var done = applyVerb(b.dataset.verb, b.textContent, VERB_TARGET);
      if (done !== false) {
        lightTick();
        enemyTurn();
      }
      closeEnemyVerbs();
      updateUse();
    }
    window.setTimeout(function () { b.disabled = false; }, 400);
  });
  canvas.addEventListener('click', tryNPC);
  document.getElementById('dpad').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-dir]'); if (!b) return;
    var d = b.dataset.dir;
    if (d === 'up') move(0, -1); else if (d === 'down') move(0, 1);
    else if (d === 'left') move(-1, 0); else if (d === 'right') move(1, 0);
  });
  setupTouchControls({ move: move, act: doInteract, exploring: exploring, exploreStop: exploreStop });
  document.addEventListener('keydown', function (e) {
    if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
    // Any key but the toggle itself halts an autoexplore walk.
    if (exploring() && e.key !== 'o' && e.key !== 'O') exploreStop('Stopped.');
    // The Interact keys keep the loop going: while a note or a speech box
    // is up they CONTINUE it (next page, then close) instead of needing a
    // click. A focused button handles its own Enter and Space, and a held
    // key never carries on into the next thing.
    var interactKey = e.key === 'e' || e.key === 'E' || e.key === 'f' || e.key === 'F'
      || e.key === ' ' || e.key === 'Enter';
    var nativeClick = e.target && e.target.tagName === 'BUTTON'
      && (e.key === ' ' || e.key === 'Enter');
    // The end card (complete-act) wins over everything: Interact and Escape
    // continue the game; the buttons handle their own Enter and Space.
    var actEndCard = document.getElementById('act-end');
    if (actEndCard && !actEndCard.hidden) {
      if (e.key === 'Escape' || (interactKey && !nativeClick)) {
        e.preventDefault();
        if (!e.repeat) closeActEnd();
      }
      return;
    }
    // While the reader is open, its keys win and movement stops.
    var readerOpen = !document.getElementById('reader').hidden;
    if (readerOpen) {
      if (e.key === 'Escape') { e.preventDefault(); closeReader(); }
      else if (interactKey && !nativeClick) {
        e.preventDefault();
        if (!e.repeat) {
          var nextBtn = document.getElementById('reader-next');
          document.getElementById(nextBtn.disabled ? 'reader-close' : 'reader-next').click();
        }
      }
      else if (e.key === 'ArrowLeft' || e.key === 'a' || e.key === 'A') { e.preventDefault(); readerTurn(-1); }
      else if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') { e.preventDefault(); readerTurn(1); }
      return;
    }
    // While the Trade panel is open, Escape closes it and movement stops.
    var tradeOpen = !document.getElementById('trade').hidden;
    if (tradeOpen) {
      if (e.key === 'Escape') { e.preventDefault(); closeTrade(); }
      else if ((e.key === 'e' || e.key === 'E' || e.key === 'f' || e.key === 'F') && !e.repeat) {
        e.preventDefault(); closeTrade();
      }
      return;
    }
    // While the identify panel is open, the same two keys close it and
    // movement stops, exactly as they do for the Trade panel above.
    var identifyOpen = !document.getElementById('identify').hidden;
    if (identifyOpen) {
      if (e.key === 'Escape') { e.preventDefault(); closeIdentify(); }
      else if ((e.key === 'e' || e.key === 'E' || e.key === 'f' || e.key === 'F') && !e.repeat) {
        e.preventDefault(); closeIdentify();
      }
      return;
    }
    var menuOpen = !document.getElementById('menu').hidden;
    if (e.key === 'Escape') {
      closeEnemyVerbs();
      var soBody = document.getElementById('startover-body');
      if (menuOpen && soBody && !soBody.hidden) {
        e.preventDefault(); window.cancelStartover(); return;
      }
      if (menuOpen) window.closeMenu(); else window.openMenu();
      return;
    }
    if (menuOpen || play.hidden) return;
    var box = document.getElementById('npc-box');
    // A speech box is up: Interact continues (closes) it, never starts a
    // second talk underneath.
    if (!box.hidden && interactKey && !nativeClick) {
      e.preventDefault();
      if (!e.repeat) document.getElementById('npc-close').click();
      return;
    }
    if (interactKey && e.repeat) return;
    // A focused button handles its own Enter and Space.
    var onButton = e.target && e.target.tagName === 'BUTTON';
    if (e.key === 'ArrowUp') { e.preventDefault(); move(0, -1); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); move(0, 1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); move(-1, 0); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); move(1, 0); }
    else if (e.key === 'w' || e.key === 'W') { e.preventDefault(); move(0, -1); }
    else if (e.key === 's' || e.key === 'S') { e.preventDefault(); move(0, 1); }
    else if (e.key === 'a' || e.key === 'A') { e.preventDefault(); move(-1, 0); }
    else if (e.key === 'd' || e.key === 'D') { e.preventDefault(); move(1, 0); }
    else if (e.key === 'e' || e.key === 'E') doInteract();
    else if (e.key === 'f' || e.key === 'F') doInteract();
    else if (e.key === 'q' || e.key === 'Q') document.getElementById('whisper').click();
    else if (e.key === 'b' || e.key === 'B') { if (window.openBag) window.openBag(); }
    else if (e.key === 'o' || e.key === 'O') startExplore();
    else if (e.key === 'v' || e.key === 'V') toggleFog();
    else if (!onButton && (e.key === ' ' || e.key === 'Enter')) {
      e.preventDefault();
      if (!box.hidden) box.hidden = true; else doInteract();
    }
  });
  loadFog();
  seeNow();
  loadHeroHp();
  renderHp();
  loadFloor();
  loadEnemies();
  combatSnapshot();
  resize();
  heroSetPose('idle');   // the hero starts standing, facing down
  draw();
  updateUse();
}
