"""Tests for the Workshop screen's room acknowledgment logic.

The acknowledgments are deterministic: they pattern-match on journal
entry text and world data to produce contextual messages. No model
calls involved. This test exercises detectAcknowledgments(),
countRooms(), and extractKeptItem() via a node VM sandbox that loads
the actual workshop.js.

Skips gracefully when node isn't installed — same zero-setup promise
as the other web tests.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not installed - this repo's engine tests never require it",
)

HarnessScript = r"""import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const ROOT = process.argv[2];
const SPEC = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

/* ---------- minimal DOM ---------- */
class El {
  constructor(tag) {
    this.tagName = (tag || 'div').toUpperCase();
    this.id = '';
    this.className = '';
    this.dataset = {};
    this.attrs = {};
    this.style = { _props: {} };
    this.children = [];
    this.parent = null;
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this._text = '';
    this._html = '';
  }
  get textContent() {
    let s = this._text || '';
    for (const c of this.children) s += c.textContent;
    return s;
  }
  set textContent(v) { this._text = String(v); this.children = []; }
  set innerHTML(v) { this._html = String(v); if (v === '') this.children = []; }
  get innerHTML() { return this._html === undefined ? '' : this._html; }
  setAttribute(k, v) { this.attrs[k] = String(v); const m = String(k).match(/^data-([\w-]+)$/); if (m) this.dataset[m[1]] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  querySelectorAll(sel) { return []; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  addEventListener(t, fn) { (this.listeners[t] ||= []).push(fn); }
  click() {}
  dispatch(type, extra = {}) { const ev = { type, target: this, ...extra }; for (const fn of this.listeners[type] || []) fn(ev); }
}

const root = new El('body');
const byId = new Map();

function mk(tag, id, cls, parent) {
  const e = new El(tag);
  e.id = id || '';
  e.className = cls || '';
  if (parent) parent.appendChild(e);
  if (e.id) byId.set(e.id, e);
  return e;
}

mk('div', 'vefr-main', '', root);

const store = {};
const sandbox = {
  console, setTimeout, clearTimeout, Promise, Math, JSON, Date, Array, Object, String,
  Number, Boolean, Error, URLSearchParams,
  history: { replaceState: () => {} },
  localStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  },
  location: { origin: 'http://localhost', pathname: '/', href: 'http://localhost/', search: '' },
  document: {
    documentElement: root,
    getElementById: (id) => byId.get(id) || null,
    querySelector: (s) => root.querySelector(s),
    querySelectorAll: (s) => root.querySelectorAll(s),
    createElement: (t) => new El(t),
    addEventListener: () => {},
    body: root,
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

sandbox.fetch = (url, opts) => {
  return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
};

const ctxVm = vm.createContext(sandbox);

// Load shell.js (provides VEFR_SHELL)
vm.runInContext('"use strict";\n' + read('web/shell.js'), ctxVm, { filename: 'shell.js' });

// Load workshop.js (provides VEFR_WORKSHOP)
vm.runInContext('"use strict";\n' + read('web/screens/workshop.js'), ctxVm, { filename: 'workshop.js' });

// Run tests
const results = [];
for (const t of SPEC.tests) {
  try {
    // Set up state via test helpers
    if (t.journal) sandbox.window.VEFR_WORKSHOP._testSetJournal(t.journal);
    if (t.world !== undefined) sandbox.window.VEFR_WORKSHOP._testSetWorld(t.world);

    // Evaluate expression
    const val = sandbox.window.VEFR_WORKSHOP[t.fn](...t.args);
    results.push({ name: t.name, ok: t.expect === undefined || JSON.stringify(val) === JSON.stringify(t.expect), value: val });
  } catch (err) {
    results.push({ name: t.name, ok: false, error: err.message });
  }
}

let pass = 0, fail = 0;
for (const r of results) {
  if (r.ok) {
    pass++;
    console.log('ok   ' + r.name);
  } else {
    fail++;
    console.log('FAIL ' + r.name + (r.error ? ' -- ' + r.error : ' -- got ' + JSON.stringify(r.value)));
  }
}
console.log(pass + ' passed, ' + fail + ' failed');
if (fail > 0) process.exit(1);
console.log('workshop ack harness passed');
"""


def _run_harness(tests):
    """Run workshop ack tests through the node VM harness."""
    with tempfile.TemporaryDirectory() as td:
        harness = Path(td) / "workshop_ack_harness.mjs"
        harness.write_text(HarnessScript, encoding="utf-8")
        spec = Path(td) / "spec.json"
        spec.write_text(json.dumps({"tests": tests}), encoding="utf-8")
        return subprocess.run(
            ["node", str(harness), str(ROOT), str(spec)],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ},
        )


def test_detect_quiet_when_no_entries():
    """No journal entries and no world -> 'the world is quiet'."""
    result = _run_harness([{
        "name": "quiet default",
        "fn": "detectAcknowledgments",
        "args": [],
        "journal": [],
        "world": None,
        "expect": {"type": "quiet", "message": "the world is quiet"},
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_detect_forge_acknowledgment():
    """Journal entry with 'forge' keyword -> 'you forged something new'."""
    result = _run_harness([{
        "name": "forge ack",
        "fn": "detectAcknowledgments",
        "args": [],
        "journal": [{"text": "you forge a blade", "kind": "forge"}],
        "world": None,
        "expect": {"type": "forge", "message": "you forged something new"},
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_detect_keep_acknowledgment():
    """Journal entry with 'kept' keyword -> 'the house remembers'."""
    result = _run_harness([{
        "name": "keep ack",
        "fn": "detectAcknowledgments",
        "args": [],
        "journal": [{"text": "you kept the old knife", "kind": "keep"}],
        "world": None,
        "expect": {"type": "keep", "message": "the house remembers", "item": "you kept the old knife"},
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_detect_map_acknowledgment():
    """Journal entry with 'room' keyword -> 'your world has N rooms'."""
    result = _run_harness([{
        "name": "map ack",
        "fn": "detectAcknowledgments",
        "args": [],
        "journal": [{"text": "you built a new room", "kind": "map"}],
        "world": {"regions": {"town": {}, "forest": {}}, "acts": []},
        "expect": {"type": "map", "message": "your world has 2 rooms now"},
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_count_rooms_from_regions():
    """countRooms counts keys in world.regions."""
    result = _run_harness([{
        "name": "count rooms",
        "fn": "countRooms",
        "args": [],
        "journal": [],
        "world": {"regions": {"town": {}, "forest": {}, "cave": {}}},
        "expect": 3,
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_count_rooms_from_acts():
    """countRooms falls back to counting act.regions when top-level regions is empty."""
    result = _run_harness([{
        "name": "count rooms from acts",
        "fn": "countRooms",
        "args": [],
        "journal": [],
        "world": {"regions": {}, "acts": [{"regions": {"a": {}}}, {"regions": {"b": {}, "c": {}}}]},
        "expect": 3,
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_extract_kept_item_from_entry():
    """extractKeptItem pulls name from entry.item or entry.name."""
    result = _run_harness([{
        "name": "extract kept item",
        "fn": "extractKeptItem",
        "args": [{"item": "old knife"}],
        "journal": [],
        "world": None,
        "expect": "old knife",
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_extract_kept_item_fallback_to_text():
    """extractKeptItem falls back to truncated text when no item/name field."""
    result = _run_harness([{
        "name": "extract kept item fallback",
        "fn": "extractKeptItem",
        "args": [{"text": "a long description of the item that was kept"}],
        "journal": [],
        "world": None,
        "expect": "a long description of the item that was \u2026",
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_priority_keep_over_forge():
    """Keep entries take priority over forge when both exist (latest-first scan)."""
    result = _run_harness([{
        "name": "keep beats forge",
        "fn": "detectAcknowledgments",
        "args": [],
        "journal": [
            {"text": "you forge a blade", "kind": "forge"},
            {"text": "you kept the old knife", "kind": "keep"},
        ],
        "world": None,
        "expect": {"type": "keep", "message": "the house remembers", "item": "you kept the old knife"},
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_map_fallback_when_no_journal():
    """When journal is empty but world has regions, show room count."""
    result = _run_harness([{
        "name": "map fallback",
        "fn": "detectAcknowledgments",
        "args": [],
        "journal": [],
        "world": {"regions": {"town": {}, "forest": {}}},
        "expect": {"type": "map", "message": "your world has 2 rooms now"},
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_vault_in_entry_text():
    """Entry text containing 'vault' triggers keep acknowledgment."""
    result = _run_harness([{
        "name": "vault text triggers keep",
        "fn": "detectAcknowledgments",
        "args": [],
        "journal": [{"text": "stored in the vault: a silver ring"}],
        "world": None,
        "expect": {"type": "keep", "message": "the house remembers", "item": "stored in the vault: a silver ring"},
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout


def test_crafted_triggers_forge():
    """Entry text containing 'crafted' triggers forge acknowledgment."""
    result = _run_harness([{
        "name": "crafted triggers forge",
        "fn": "detectAcknowledgments",
        "args": [],
        "journal": [{"text": "you crafted a new tool"}],
        "world": None,
        "expect": {"type": "forge", "message": "you forged something new"},
    }])
    assert result.returncode == 0, f"harness failed:\n{result.stdout}\n{result.stderr}"
    assert "workshop ack harness passed" in result.stdout
