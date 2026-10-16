// ---- .vefr archive loader (ADR 0019, vefr#455) ----
//
// The shared Player's other front door. A woven file carries its game
// in the block that comes after this one (050); an archive carries it in
// a `.vefr` ZIP, and this block puts it in place. It runs BEFORE every
// part that reads a `window.VEFR_*` global while the page is still
// parsing, because several of those reads happen once, at parse time,
// and a game that arrives late would save to the wrong keys and draw no
// ground at all.
//
// The order is therefore: read what is already in this tab's cache
// (sessionStorage, synchronous, so the whole page sees a finished game),
// or fetch the archive, validate it, cache it, and reload once. The
// reload is the honest way to be early rather than late: a Player is
// built without the baked block (see `vefr archive`), so nothing may
// read a global before the game is installed.
//
// Dormant by default. A woven file folds its game into the block right
// after this one and leaves `vefrArchiveUrl` empty, so every line here is
// a no-op in one: only `vefr archive`'s Player build (or an explicit
// `?vefr=` on any build) ever wakes it. The handle is deliberately not a
// `window.VEFR_*` name: that namespace is the pack's baked data, and the
// loader is the engine, not a pack.
window.vefrArchiveUrl = window.vefrArchiveUrl || '';
//
// Validation mirrors src/vefr/vefrfile.py - the same refusals, in the
// same words, so a bad archive is refused the same way in a browser and
// on the command line. Nothing here ever runs archive content: the only
// things written into the page are the manifest's own game data and the
// four `doc` strings the engine itself baked.
var vefrArchive = (function () {
  'use strict';

  var MANIFEST = 'manifest.json';
  var GLOBALS = 'data/globals.json';
  var FORMAT = 'vefr-archive';
  var SCHEMA_VERSION = 1;
  var MAX_ENTRIES = 4096;
  var MAX_ENTRY_BYTES = 64 * 1024 * 1024;
  var MAX_TOTAL_BYTES = 256 * 1024 * 1024;
  var MAX_RATIO = 200;
  // sessionStorage is about 5 MB in most browsers; the fast path stays
  // well under it. A bigger game is a `vefr weave` today, and moves to
  // assets-as-files when the format grows a version (see the ADR).
  var MAX_CACHE_BYTES = 3500000;
  var SAFE_DATA_TYPES = {
    'image/png': 1, 'image/jpeg': 1, 'image/gif': 1, 'image/webp': 1,
    'image/svg+xml': 1, 'image/bmp': 1, 'audio/mpeg': 1, 'audio/ogg': 1,
    'audio/wav': 1, 'audio/webm': 1, 'font/woff': 1, 'font/woff2': 1
  };
  var TEXT = /\.(md|json|txt|yaml|yml|toml|cfg|ini)$/i;
  var ASSET = /\.(png|webp|jpe?g|gif|svg|bmp|ico|mp3|ogg|wav|m4a|aac|flac|woff2?|ttf|otf)$/i;

  var CACHE_KEY = 'vefr-archive:last';
  var GLOBAL_KEY = /^VEFR_[A-Z0-9_]+$/;
  var URL_RE = /https?:\/\/[^\s"'<>)\\]+/g;
  var DATA_RE = /data:([a-zA-Z0-9.+/-]+)[;,]/g;

  function refuse(sentence) {
    throw new Error(sentence);
  }

  // ---- the ZIP, read by hand: a central directory and two methods ----

  function zipEntries(bytes) {
    var view = new DataView(bytes);
    // The end-of-central-directory record is the last one, after a
    // comment of up to 64 KB.
    if (bytes.length < 22) refuse('this file is not a .vefr archive: a .vefr is a ZIP file');
    var start = Math.max(0, bytes.length - 65558);
    var eocd = -1;
    for (var i = bytes.length - 22; i >= start; i--) {
      if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) refuse('this file is not a .vefr archive: a .vefr is a ZIP file');
    var count = view.getUint16(eocd + 10, true);
    var offset = view.getUint32(eocd + 16, true);
    if (count === 0xffff || offset === 0xffffffff) {
      refuse('this .vefr is a ZIP64 archive; this Player reads the plain ZIP form');
    }
    if (count > MAX_ENTRIES) {
      refuse('this .vefr holds ' + count + ' entries; an archive may hold at most ' + MAX_ENTRIES);
    }
    var entries = [];
    var at = offset;
    var total = 0;
    for (var n = 0; n < count; n++) {
      if (at < 0 || at + 46 > bytes.length || view.getUint32(at, true) !== 0x02014b50) {
        refuse('this .vefr has a broken ZIP directory');
      }
      var method = view.getUint16(at + 10, true);
      var compressed = view.getUint32(at + 20, true);
      var size = view.getUint32(at + 24, true);
      var nameLen = view.getUint16(at + 28, true);
      var extraLen = view.getUint16(at + 30, true);
      var commentLen = view.getUint16(at + 32, true);
      var local = view.getUint32(at + 42, true);
      var name = utf8(bytes.subarray(at + 46, at + 46 + nameLen));
      entries.push({ name: name, method: method, compressed: compressed,
                     size: size, local: local, bytes: bytes, view: view });
      at += 46 + nameLen + extraLen + commentLen;
      total += size;
    }
    if (total > MAX_TOTAL_BYTES) {
      refuse('this .vefr expands to ' + total + ' bytes; an archive may expand to at most ' + MAX_TOTAL_BYTES);
    }
    return entries;
  }

  function utf8(chunk) {
    if (typeof TextDecoder === 'function') return new TextDecoder('utf-8').decode(chunk);
    var out = '';
    for (var i = 0; i < chunk.length; i++) out += String.fromCharCode(chunk[i]);
    return out;
  }

  function entryBytes(entry) {
    if (entry.size > MAX_ENTRY_BYTES) {
      refuse('refusing "' + entry.name + '": the archive declares ' + entry.size +
             ' bytes; an entry may be at most ' + MAX_ENTRY_BYTES);
    }
    if (entry.compressed && entry.size / entry.compressed > MAX_RATIO) {
      refuse('refusing "' + entry.name + '": it expands ' +
             Math.floor(entry.size / entry.compressed) + 'x, past the ' + MAX_RATIO +
             'x a picture ever needs');
    }
    var head = entry.local;
    if (head < 0 || head + 30 > entry.bytes.length ||
        entry.view.getUint32(head, true) !== 0x04034b50) {
      refuse('refusing "' + entry.name + '": its ZIP entry is broken');
    }
    var start = head + 30 + entry.view.getUint16(head + 26, true) +
                entry.view.getUint16(head + 28, true);
    var raw = entry.bytes.subarray(start, start + entry.compressed);
    if (entry.method === 0) {
      if (raw.length !== entry.size) refuse('refusing "' + entry.name + '": it is shorter than it declares');
      return Promise.resolve(raw);
    }
    if (entry.method !== 8) {
      refuse('refusing "' + entry.name + '": the archive uses a compression this Player does not read');
    }
    return inflate(raw, entry.size, entry.name);
  }

  // deflate-raw through the platform's own stream, counted as it lands.
  function inflate(raw, limit, name) {
    if (typeof DecompressionStream !== 'function') {
      refuse('this browser cannot open a .vefr: it has no DecompressionStream. Play this game from a woven HTML file instead.');
    }
    var stream = new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    var reader = stream.getReader();
    var chunks = [];
    var total = 0;
    function step() {
      return reader.read().then(function (part) {
        if (part.done) return new Uint8Array(chunks.reduce(function (a, c) { return a + c.length; }, 0));
        total += part.value.length;
        if (total > limit) {
          reader.cancel();
          refuse('refusing "' + name + '": it expands past ' + limit + ' bytes');
        }
        chunks.push(part.value);
        return step();
      });
    }
    return step();
  }

  // ---- what an archive may be ----

  function allowed(name) {
    // No suffix at all is content: a pack's LICENSE and README travel.
    var base = name.slice(name.lastIndexOf('/') + 1);
    return base.indexOf('.') < 0 || TEXT.test(name) || ASSET.test(name);
  }

  function safeName(name) {
    if (!name || name.trim() !== name) refuse('refusing the entry "' + name + '": an archive name may not be padded');
    if (name.indexOf('\\') >= 0) refuse('refusing the entry "' + name + '": archive names use "/"');
    if (name.charAt(0) === '/' || /^[A-Za-z]:/.test(name)) {
      refuse('refusing the entry "' + name + '": archive paths are relative');
    }
    var parts = name.split('/');
    for (var i = 0; i < parts.length; i++) {
      if (parts[i] === '' || parts[i] === '.' || parts[i] === '..') {
        refuse('refusing the entry "' + name + '": the path leaves the archive');
      }
    }
    if (name !== MANIFEST && name !== GLOBALS && name.indexOf('content/') !== 0 &&
        name.indexOf('assets/') !== 0) {
      refuse('refusing the entry "' + name + '": an archive holds a manifest, content/, assets/ and the game data - nothing else');
    }
    if (name !== MANIFEST && name !== GLOBALS && !allowed(name)) {
      refuse('refusing "' + name + '": an archive carries data and pictures, never anything that could run');
    }
  }

  function find(entries, name) {
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].name === name) return entries[i];
    }
    return null;
  }

  function checkManifest(manifest) {
    if (!manifest || typeof manifest !== 'object') refuse(MANIFEST + ' is not a JSON object');
    if (manifest.format !== FORMAT) {
      refuse('this file is not a .vefr archive: manifest format ' + JSON.stringify(manifest.format) +
             ', expected ' + JSON.stringify(FORMAT));
    }
    var version = manifest.schema_version;
    if (typeof version !== 'number') refuse('the manifest\'s schema_version is not a number');
    if (version > SCHEMA_VERSION) {
      refuse('this .vefr uses manifest schema ' + version + '; this vefr reads schema ' +
             SCHEMA_VERSION + ' - update the engine to play it');
    }
    var runtime = manifest.runtime || {};
    var floor = runtime.min_schema_version;
    if (typeof floor === 'number' && floor > SCHEMA_VERSION) {
      refuse('this .vefr needs a newer Player: it asks for schema ' + floor +
             ' at least, this Player reads schema ' + SCHEMA_VERSION);
    }
    if (!manifest.game || !manifest.game.id) refuse('the manifest names no game id');
    if (!Array.isArray(manifest.files)) refuse('the manifest lists no files');
    return manifest;
  }

  function walk(value, out) {
    if (typeof value === 'string') out.push(value);
    else if (Array.isArray(value)) value.forEach(function (v) { walk(v, out); });
    else if (value && typeof value === 'object') {
      Object.keys(value).forEach(function (key) {
        out.push(key);
        walk(value[key], out);
      });
    }
    return out;
  }

  function checkUrls(value, manifest) {
    var declared = ((manifest.network && manifest.network.allowed_urls) || []);
    var texts = walk(value, []);
    for (var i = 0; i < texts.length; i++) {
      var found = texts[i].match(URL_RE) || [];
      for (var j = 0; j < found.length; j++) {
        var ok = false;
        for (var k = 0; k < declared.length; k++) {
          if (found[j] === declared[k] ||
              found[j].indexOf(declared[k].replace(/\/$/, '') + '/') === 0) ok = true;
        }
        if (!ok) {
          refuse('the game data points at ' + found[j] + ', which its manifest does not declare - an archive reaches no network');
        }
      }
      var data = texts[i].match(DATA_RE) || [];
      for (var d = 0; d < data.length; d++) {
        if (!SAFE_DATA_TYPES[data[d].toLowerCase()]) {
          refuse('the game data carries a data:' + data[d] + ' URI; an archive carries pictures, sounds and fonts');
        }
      }
    }
  }

  function checkPayload(payload, manifest) {
    if (!payload || typeof payload !== 'object') refuse(GLOBALS + ' is not a JSON object');
    var globals = payload.globals;
    if (!globals || typeof globals !== 'object') refuse(GLOBALS + ' carries no "globals" object');
    Object.keys(globals).forEach(function (key) {
      if (!GLOBAL_KEY.test(key)) {
        refuse(GLOBALS + ' names "' + key + '": the game data is only window.VEFR_* globals');
      }
    });
    checkUrls(globals, manifest);
    checkUrls(payload.doc || {}, manifest);
    return payload;
  }

  // ---- the whole check, entry by entry, then install ----

  function openArchive(buffer) {
    var entries = zipEntries(new Uint8Array(buffer));
    entries.forEach(function (entry) { safeName(entry.name); });
    var manifestEntry = find(entries, MANIFEST);
    var globalsEntry = find(entries, GLOBALS);
    if (!manifestEntry) refuse('this archive has no ' + MANIFEST + ': it is not a .vefr archive');
    if (!globalsEntry) refuse('this archive has no ' + GLOBALS + ': it carries no game to play');
    var declared = {};
    return entryBytes(manifestEntry)
      .then(function (raw) { return JSON.parse(utf8(raw)); })
      .then(function (manifest) {
        checkManifest(manifest);
        manifest.files.forEach(function (row) {
          if (row && typeof row.path === 'string') declared[row.path] = row;
        });
        return entryBytes(globalsEntry)
          .then(function (raw) { return JSON.parse(utf8(raw)); })
          .then(function (payload) {
            var named = entries.filter(function (entry) { return entry.name !== MANIFEST; });
            return named.reduce(function (chain, entry) {
              return chain.then(function () {
                var row = declared[entry.name];
                if (!row) refuse('"' + entry.name + '" is in the archive but not in its manifest');
                return entryBytes(entry)
                  .then(function (raw) {
                    if (raw.length !== row.bytes) {
                      refuse('"' + entry.name + '" is ' + raw.length + ' bytes; its manifest says ' + row.bytes);
                    }
                    return matches(raw, row.sha256);
                  })
                  .then(function (same) {
                    if (!same) refuse('"' + entry.name + '" does not match its manifest digest');
                  });
              });
            }, Promise.resolve())
            .then(function () {
              Object.keys(declared).forEach(function (path) {
                if (!find(entries, path)) refuse('"' + path + '" is in the manifest but not in the archive');
              });
            })
            .then(function () { return { manifest: manifest, payload: checkPayload(payload, manifest) }; });
          });
      });
  }

  // The same SHA-256 as the manifest was written with, through the
  // platform's own digest - one implementation of SHA-256 in the world,
  // and it is the browser's. An insecure origin (a page opened from
  // file://) offers no digest at all, so there the byte length is the
  // only check; every other refusal above still holds.
  function matches(bytes, hex) {
    if (!hex || !/^[0-9a-f]{64}$/.test(hex)) refuse('the manifest does not give this file a sha256 digest');
    if (typeof crypto === 'undefined' || !crypto.subtle || !crypto.subtle.digest) return true;
    return crypto.subtle.digest('SHA-256', bytes).then(function (buffer) {
      var got = '';
      new Uint8Array(buffer).forEach(function (b) { got += ('0' + b.toString(16)).slice(-2); });
      if (got !== hex) return false;
      return true;
    });
  }

  // ---- install ----

  function install(opened) {
    var manifest = opened.manifest;
    var globals = opened.payload.globals;
    Object.keys(globals).forEach(function (key) { window[key] = globals[key]; });
    var doc = opened.payload.doc || {};
    if (doc.title) {
      document.title = doc.title;
      setText('#ts-title', doc.title);
      setText('.game-head h1', doc.title);
    }
    if (doc.tagline) {
      setText('.title-tagline', doc.tagline);
      setText('.game-head .tagline', doc.tagline);
    }
    if (doc.title_art_img) {
      var screen = document.getElementById('title-screen');
      if (screen) screen.insertAdjacentHTML('afterbegin', doc.title_art_img);
    }
    if (doc.fonts_css) {
      var style = document.createElement('style');
      style.id = 'vefr-archive-fonts';
      style.textContent = doc.fonts_css;
      document.head.appendChild(style);
    }
    // What a test or the console asks after a load: which manifest is in
    // play, and where it came from.
    vefrArchive.installed = { manifest: manifest, source: opened.source || 'archive' };
  }

  function setText(selector, text) {
    var el = document.querySelector(selector);
    if (el) el.textContent = text;
  }

  // ---- the two doors: a sibling URL, or a dropped file ----

  function cached(url) {
    try {
      var raw = sessionStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      var held = JSON.parse(raw);
      // A different archive is a different game: never install one tab's
      // game into another's page.
      return held && (held.url || '') === url ? held.opened : null;
    } catch (err) {
      return null;
    }
  }

  function remember(url, opened) {
    var text = JSON.stringify({ url: url, opened: opened });
    if (text.length > MAX_CACHE_BYTES) {
      return 'this .vefr is ' + Math.round(text.length / 100000) + ' KB; this Player opens archives up to about ' +
             Math.round(MAX_CACHE_BYTES / 100000) + ' KB in the browser. Play this game from a woven HTML file instead.';
    }
    try {
      sessionStorage.setItem(CACHE_KEY, text);
      return null;
    } catch (err) {
      return 'this browser refused to hold the game in its session store; play this game from a woven HTML file instead.';
    }
  }

  function waiting(message) {
    var enter = document.getElementById('ts-enter');
    if (enter) enter.disabled = true;
    var tagline = document.querySelector('.title-tagline');
    if (tagline) tagline.textContent = message;
    // Begin answers a key as well as its button, so the keys wait too.
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'f' ||
          event.key === 'F' || event.key === 'e' || event.key === 'E') {
        event.stopImmediatePropagation();
        event.preventDefault();
      }
    }, true);
  }

  function reload() {
    window.location.reload();
  }

  function loadBuffer(url, buffer, source) {
    return openArchive(buffer).then(function (opened) {
      opened.source = source;
      var complaint = remember(url, opened);
      if (complaint) {
        waiting(complaint);
        return;
      }
      reload();
    }).catch(function (err) {
      waiting(String(err && err.message ? err.message : err));
    });
  }

  function fromUrl(url) {
    waiting('opening the game…');
    return fetch(url).then(function (response) {
      if (!response.ok) throw new Error('the archive at ' + url + ' answered ' + response.status);
      return response.arrayBuffer();
    }).then(function (buffer) {
      return loadBuffer(url, buffer, 'network');
    }).catch(function (err) {
      waiting(String(err && err.message ? err.message : err));
      listenForDrops();
    });
  }

  function fromDrop(file) {
    if (!/\.vefr$/i.test(file.name)) {
      waiting('that is not a .vefr archive');
      return;
    }
    waiting('opening the game…');
    file.arrayBuffer().then(function (buffer) {
      // The cache is keyed by what this page asks for, so the game that
      // was just dropped is the one the reload installs.
      return loadBuffer(window.vefrArchiveUrl || '', buffer, 'file');
    }).catch(function (err) {
      waiting(String(err && err.message ? err.message : err));
    });
  }

  function listenForDrops() {
    var screen = document.getElementById('title-screen');
    if (screen && !document.getElementById('vefr-archive-drop')) {
      var hint = document.createElement('p');
      hint.id = 'vefr-archive-drop';
      hint.className = 'ts-byline';
      hint.textContent = 'or drop a .vefr archive anywhere on this page';
      screen.appendChild(hint);
    }
    window.addEventListener('dragover', function (event) { event.preventDefault(); });
    window.addEventListener('drop', function (event) {
      event.preventDefault();
      var files = event.dataTransfer && event.dataTransfer.files;
      if (files && files.length) fromDrop(files[0]);
    });
  }

  function start() {
    var params = new URLSearchParams(window.location.search);
    // An explicit `?vefr=` wins over the archive this build was written
    // beside, so one Player file can open any archive you point it at.
    var url = params.get('vefr') || window.vefrArchiveUrl || '';
    var held = cached(url);
    if (held) {
      // The fast path: the game is already in this tab, so every part
      // below sees a finished world as it parses.
      install(held);
      return held;
    }
    if (url) {
      fromUrl(url);
    } else if (window.vefrArchiveUrl) {
      listenForDrops();
    }
    return null;
  }

  return {
    installed: null,
    openArchive: openArchive,
    install: install,
    cached: cached,
    start: start,
    waiting: waiting,
    schemaVersion: SCHEMA_VERSION
  };
})();

// Started outside, because `install` records what it installed on this
// object and the object only exists once the closure has returned.
try {
  vefrArchive.start();
} catch (err) {
  vefrArchive.waiting(String(err && err.message ? err.message : err));
}
