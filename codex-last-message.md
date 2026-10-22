RESULT: partial

SELF-REVIEW:
1. Claims hold: the talk waits now use `VEFR_HERO_AT` and `VEFR_WHY`; the generated file was rebuilt and matched its parts byte for byte. Chromium behavior remains unverified.
2. Yes. Added browser regression tests for reserved shortcuts and Enter/Space activation, plus replaced fixed waits with state-based waits.
3. No. Changes are limited to the named player part and its tests.
4. No contradiction found. The default keyboard escape routes remain available.

CHANGED: `web/player/parts/076-keybinds.js`; `tests/browser/test_keybinds.py`; `tests/browser/test_talk_fires_near_rule.py`; `tests/test_talk_fires_near_rule.py`. Commit could not be created because `.git/index.lock` is unwritable in this environment.

CHECKS:

- `$ PYTHONPATH=src python scripts/build_player.py && PYTHONPATH=src python scripts/build_player.py --check && PYTHONPATH=src python - <<'PY' ...` → rebuilt 834671 bytes; parts check passed; zero-diff proof passed.
- `$ node --check web/player/parts/076-keybinds.js` → passed.
- `$ python -m compileall -q tests/browser/test_keybinds.py tests/browser/test_talk_fires_near_rule.py tests/test_talk_fires_near_rule.py` → passed.
- `$ git diff --check` → passed.
- `$ pytest -q tests/browser/test_keybinds.py tests/browser/test_talk_fires_near_rule.py tests/test_talk_fires_near_rule.py` → unavailable (`pytest: command not found`).
- `$ npm test` → unavailable (`npm: command not found`).

EVIDENCE: `web/player/parts/076-keybinds.js:268`; `tests/browser/test_keybinds.py:319`; `tests/browser/test_talk_fires_near_rule.py:99`; `tests/test_talk_fires_near_rule.py:99`; `.gitignore:30` excludes generated `web/packaged.html`, and `tests/test_player_build.py` checks exact build equality. `origin/main` is absent, so baseline-relative acceptance cannot be checked.

UNRESOLVED: Chromium tests and full project tests could not run because test tooling is absent; record this in the rolling “Review polish” issue. Commit also remains outstanding because the Git index is read-only.

NEXT: Apply the commit in a writable clone, then run the browser tests and `npm test`.