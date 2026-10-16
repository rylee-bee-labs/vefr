"""The packaged file's pool-draw runtime, executed for real.

`ratatoskr weave --pool N` bakes `window.VEFR_POOL` into the
dist/<world>.html single file; the file's own poolDraw() then serves
lines when no live endpoint answers. Until now that runtime was only
ever exercised by hand - the DOM harness runs index.html, not the
packaged file (it pulls in canvas + the full app).

This test closes that gap the cheap-but-real way: it builds a real
packaged file through cmd_build_web with the generators monkeypatched
to canned outputs (no LLM), extracts the ACTUAL shipped pool block
from the built HTML - `const POOL_USED` through the end of
poolDraw(), between the file's own section markers - plus the baked
window.VEFR_POOL line, and hands both to tests/fixtures/pool_harness.mjs,
which executes them in a node vm sandbox and drives the semantics:
asked-for combo first, no repeats, cross-combo fallthrough, null when
spent, persistence across reload.

Known limit, stated plainly: this does NOT drive the packaged app's
button-level flow (click -> fetch fail -> catch -> poolDraw) in a
stub DOM - packaged.html's town canvas makes the full-app harness a
bigger job. The catch-block wiring is asserted statically instead.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = Path(__file__).resolve().parent / "fixtures" / "pool_harness.mjs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not installed - this repo's engine tests never require it",
)


class _Canned:
    """Stand-in generation output: only the attrs build_pool reads."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump(self):  # noqa: D102 - mirrors the pydantic API
        return dict(self.__dict__)


@pytest.fixture()
def canned_generators(monkeypatch):
    """Deterministic generations: every combo fills, every line unique."""
    counter = {"n": 0}

    def rumor(phase):
        counter["n"] += 1
        return types.SimpleNamespace(
            speaker="Ember", whisper=f"canned whisper {phase} {counter['n']}",
            is_true=True)

    def line(phase, key=None):
        counter["n"] += 1
        return types.SimpleNamespace(
            speaker="Ember", line=f"canned line {phase} {key} {counter['n']}")

    def letter():
        counter["n"] += 1
        return types.SimpleNamespace(letter=f"canned letter {counter['n']}")

    def item():
        counter["n"] += 1
        return types.SimpleNamespace(
            model_dump=lambda: {"name": f"canned item {counter['n']}",
                                "kind": "trinket", "bond": [], "lore": "x"})

    from vefr import forge, generator, npc, stefna

    monkeypatch.setattr(generator, "generate_rumor", rumor)
    monkeypatch.setattr(npc, "generate_line", line)
    monkeypatch.setattr(stefna, "generate_letter", letter)
    monkeypatch.setattr(forge, "forge_item", item)


def _build_packaged_file(tmp_path, monkeypatch):
    """Build a real packaged file with a small canned pool baked in."""
    from vefr import cli

    out = tmp_path / "packaged.html"
    args = types.SimpleNamespace(
        pack="sample-world", out=str(out), pool=2, with_bundle=False,
        vault=None, journal=None, from_live=None)
    rc = cli.cmd_build_web(args)
    assert rc == 0, "cmd_build_web failed"
    return out.read_text(encoding="utf-8")


def _extract(html: str) -> str:
    """The shipped pool code: the VEFR_POOL line + the poolDraw block,
   taken verbatim from the built file between its own section markers."""
    pool_line = re.search(r"window\.VEFR_POOL = .*?;\n", html)
    block = re.search(
        r"// ---- the woven pool ----.*?(?=// ---- town ----)",
        html, re.DOTALL)
    if not (pool_line and block):
        raise AssertionError("packaged file's pool section markers not found")
    return pool_line.group(0) + "\n" + block.group(0)


def test_packaged_pool_draw_semantics(tmp_path, monkeypatch, canned_generators):
    html = _build_packaged_file(tmp_path, monkeypatch)

    # The bake: real (here, canned) generations landed in the file.
    assert "window.VEFR_POOL = {" in html
    assert '"rumor:dusk"' in html
    assert "canned whisper dusk" in html
    # The canary bank rode along: the keeper's fragments are inlined.
    assert "The stone keeps what is brought to it." in html

    # The wiring: the rumor and npc catch blocks must reach the pool,
    # and past the pool into the composer, then the fragment banks.
    assert "poolDraw(phaseKey)" in html
    assert "composeWhisper(phaseKey)" in html
    assert "poolDraw(key)" in html
    assert "composeLine(key)" in html
    assert "whisperFromFragments()" in html
    assert "composeFromFragments(nearest.key, 'line')" in html
    # The banks are inlined and the status lines are honest about
    # provenance: pool, pool's cloth, fragments, silence.
    assert "window.VEFR_FRAGMENTS = " in html
    assert "From the game's saved lines." in html
    assert "Mixed from the game's saved lines." in html
    assert "From the characters' own lines." in html
    assert "From this character's own lines." in html
    assert "Nothing came back (" in html

    code = _extract(html)

    # The pool as baked: whisper combos have 2 entries (pool=2),
    # letter/forge specials have 3.
    pool_line = re.search(r"window\.VEFR_POOL = (.*?);\n", code)
    pool = json.loads(pool_line.group(1))
    assert pool["rumor:dusk"] and pool["letter"] and pool["forge"]

    spec = {"code": code, "pool": pool}
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(spec, f)
        spec_path = f.name
    try:
        result = subprocess.run(
            ["node", str(HARNESS), spec_path],
            capture_output=True, text=True, timeout=30,
            env={**os.environ},
        )
    finally:
        Path(spec_path).unlink(missing_ok=True)
    assert result.returncode == 0, (
        f"pool harness failed:\n{result.stdout}\n{result.stderr}")
    assert "pool harness passed" in result.stdout


def test_chat_endpoint_normalizes_the_config_url(tmp_path, monkeypatch, canned_generators):
    """The setup placeholder ends in `/v1`; a naive join once appended
    `/v1/chat/completions` to it and produced `/v1/v1/...` (seen live).
    The shipped joiner must collapse every input shape onto exactly one
    endpoint, so run the built file's own function over the cases."""
    html = _build_packaged_file(tmp_path, monkeypatch)

    match = re.search(r"function chatEndpoint\(base\) \{.*?\n\}", html, re.DOTALL)
    assert match, "chatEndpoint missing from packaged file"
    code = match.group(0)

    cases = [
        # (input, expected)
        ("http://192.168.1.5:11434", "http://192.168.1.5:11434/v1/chat/completions"),
        # The defect: base URL as the placeholder itself shows it.
        ("http://192.168.1.5:11434/v1", "http://192.168.1.5:11434/v1/chat/completions"),
        # Trailing slashes and a pasted full endpoint must also land once.
        ("http://192.168.1.5:11434/v1/", "http://192.168.1.5:11434/v1/chat/completions"),
        ("http://192.168.1.5:11434/", "http://192.168.1.5:11434/v1/chat/completions"),
        ("http://192.168.1.5:11434/v1/chat/completions",
         "http://192.168.1.5:11434/v1/chat/completions"),
    ]
    driver = (
        code + "\n"
        "const cases = " + json.dumps(cases) + ";\n"
        "let bad = [];\n"
        "for (const [input, expected] of cases) {\n"
        "  const got = chatEndpoint(input);\n"
        "  if (got !== expected) bad.push({input, expected, got});\n"
        "}\n"
        "if (bad.length) { console.error(JSON.stringify(bad, null, 2)); process.exit(1); }\n"
        "console.log('endpoint join passed');\n"
    )
    result = subprocess.run(
        ["node", "-e", driver],
        capture_output=True, text=True, timeout=30, env={**os.environ},
    )
    assert result.returncode == 0, (
        f"chatEndpoint failed:\n{result.stdout}\n{result.stderr}")
    assert "endpoint join passed" in result.stdout


def test_setup_gate_allows_offline_play(tmp_path, monkeypatch, canned_generators):
    """First-run setup once hard-gated `alert('both URL and model are
    required.')` - no way past it without an endpoint, even though the
    woven pool exists precisely to carry offline play. The built file
    must offer the offline path, remember the choice, and never fetch
    a relative URL when no endpoint is set."""
    html = _build_packaged_file(tmp_path, monkeypatch)

    # The hard gate is gone; half-filled (a typo) still warns.
    assert "both URL and model are required." not in html
    assert "fill in both, or leave both blank" in html
    # Games play without a model (docs/adr/0003): Begin goes straight in,
    # and a saved endpoint is ignored unless the pack opts in with
    # "player": {"model": "optional"}, which offers it in the pause menu.
    assert "configured: true" in html
    assert "window.VEFR_WORLD.player.model === 'optional'" in html
    assert "if (!MODEL_OPTIONAL) { llmUrl = ''; llmModel = ''; }" in html
    assert "config.configured || (llmUrl && llmModel)" not in html
    # The copy names the affordance where the player decides.
    assert "Leave both blank to play offline" in html
    # Offline never fetches a relative URL: the post helper rejects
    # straight into the existing pool/fragment fallbacks, and no caller
    # joins the endpoint by hand anymore.
    assert "offline - no endpoint set" in html
    assert "llmUrl + '/v1/chat/completions'" not in html
    assert "await llmPost(body)" in html
    assert "llmPost({" in html


def test_packaged_carries_the_surface_costume(tmp_path, monkeypatch, canned_generators):
    """The combat costume rides in the packaged file too - the web UI
    half landed in 06eed41; the packaged half was the gap. The built
    file must carry the HP bar, the encounter prompt, the verb row,
    and the data-surface branch that shows all of it only for
    combat-surface packs."""
    html = _build_packaged_file(tmp_path, monkeypatch)

    # Markup.
    assert 'id="hud-hp"' in html and 'id="hud-hp-fill"' in html
    assert 'id="encounter-prompt"' in html
    assert 'id="verb-row"' in html and "['attack', 'Strike']" in html
    # The verb row is rendered at play time from the act's own
    # verbs (or the baked defaults) - never static pack-named buttons.
    assert 'aria-label="Combat actions"></div>' in html
    # The surface comes from the pack at play time, not from the
    # template - a plain pack never sees the costume.
    assert "setAttribute('data-surface'" in html
    assert 'body[data-surface="plain"] .hud-hp' in html
    assert 'body[data-surface="investigation"] .verb-row' in html
    # The verbs record honestly, locally - same no-failure contract
    # as the server route, minus the server.
    assert "store.getJSON(COMBAT_KEY" in html
    # Engine neutrality: the costume never names a pack's phase
    # vocabulary. (The live app once grew a lines dict keyed by the
    # author's own phase names; the packaged file must not repeat it.)
    template = (Path(__file__).resolve().parents[1] / "web" / "packaged.html").read_text(encoding="utf-8")
    for phase_key in ("doubts", "feared", "awed"):
        assert f"'{phase_key}'" not in template, (
            f"packaged template must not hardcode phase name '{phase_key}'"
        )


def test_player_title_art_and_accent(tmp_path):
    """The woven title screen carries a picture: the pack's own when
    world.json names one inside the pack, else the engine's default;
    a valid accent colour comes with readable button text."""
    from vefr.cli import _player_title_art, _player_fonts_css

    web = Path(__file__).resolve().parents[1] / "web"
    pack = tmp_path / "pack"
    (pack / "assets").mkdir(parents=True)
    (pack / "assets" / "title.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

    own = _player_title_art(pack, {"player": {"title_art": "assets/title.png", "accent": "#C98049"}}, web)
    assert 'src="data:image/png;base64,' in own
    assert "--accent: #C98049; --accent-on: #1B1206;" in own

    default = _player_title_art(pack, {}, web)
    assert 'src="data:image/webp;base64,' in default

    outside = tmp_path / "secret.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\nsecret")
    escaped = _player_title_art(pack, {"player": {"title_art": "../secret.png", "accent": "red"}}, web)
    assert "image/png" not in escaped and "--accent" not in escaped

    assert "font-family: 'Cinzel'" in _player_fonts_css(web)


def _hero(html: str) -> dict:
    """The baked `window.VEFR_HERO` as the player reads it."""
    m = re.search(r"window\.VEFR_HERO = (.*?);\n", html)
    assert m, "no VEFR_HERO line in the weave"
    return json.loads(m.group(1))


def test_a_pack_that_names_a_library_gets_a_way_back(tmp_path):
    """#488: `player.library_url`, when the pack names an http(s) shelf,
    rides the hero payload the weave already bakes - no new `VEFR_*`
    line, and a pack that names none bakes no library_url (the row and
    its code are engine bytes in every weave, so the no-skin weave digest
    did move once, with this change) - and the pause menu grows its 'Back
    to the library' row from it. A scheme that is not a link is not baked
    at all, rather than baked and left for a browser to interpret."""
    from vefr import cli

    sample = cli.weave_html(ROOT / "worlds" / "sample-world")
    assert "library_url" not in _hero(sample)
    # The row and the code that fills it are the engine's, in every pack.
    assert 'id="menu-library-row"' in sample
    assert "document.getElementById('menu-library-row')" in sample
    assert "Back to the library" in sample

    pack = tmp_path / "pack"
    shutil.copytree(ROOT / "worlds" / "sample-world", pack)
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world.setdefault("player", {})["library_url"] = \
        "https://library.example.com/vefr/sample-world"
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
    assert _hero(cli.weave_html(pack))["library_url"] == \
        "https://library.example.com/vefr/sample-world"

    for bad in ("javascript:alert(1)", "library.example.com", "  "):
        world["player"]["library_url"] = bad
        (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
        assert "library_url" not in _hero(cli.weave_html(pack)), bad
