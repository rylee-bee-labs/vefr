"""`vefr look --sizes`, `--at` and `--seed` (issues #344, #353).

Three flags on the one developer verb that photographs a pack:

  - `--sizes WxH[,WxH]` photographs the pack at each size it names,
    one file per size with the size in the name, and repeats the
    containment report at every one of them;
  - `--at REGION X,Y` starts the run somewhere other than the world's
    start region, checked against the pack before a browser opens;
  - `--seed SEED` asks the game for a run seed of its own, through the
    player's own `?vefr-seed=` parameter.

Everything refused on the way in (a size that is not a size, a region
that is not a region, a seed that is not a seed) is answered without a
browser, and those are the tests that run everywhere. The tests that
open a real Chromium need Playwright and skip without it -
`VEFR_BROWSER_REQUIRED=1` makes the missing browser a failure.

The PNG dimensions are read out of the file's own IHDR chunk, never
out of its name: the whole point of `--sizes` is that the file holds
the size that was asked for, and a name would prove nothing.
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import vefr.cli as cli
from vefr import devtools

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"
PLAYER = ROOT / "web" / "player" / "parts" / "397-the-descent.js"
SHELL = ROOT / "web" / "player" / "parts" / "030-shell.html"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))


@pytest.fixture(scope="module")
def browser():
    """A headless Chromium for this module, or a skip.

    It overrides the shared `browser` of `tests/browser/fixtures.py`, which
    keeps a live Chromium open; this file's browser tests are the `vefr look`
    half of issue #344, so they belong here.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:      # noqa: BLE001 - not installed is a report
        if os.environ.get("VEFR_BROWSER_REQUIRED") == "1":
            pytest.fail(f"browser required but unavailable: {e}")
        pytest.skip(f"Playwright is not installed: {e}")
    with sync_playwright() as p:
        try:
            instance = p.chromium.launch()
        except Exception as e:  # noqa: BLE001 - Chromium not installed
            if os.environ.get("VEFR_BROWSER_REQUIRED") == "1":
                pytest.fail(f"browser required but unavailable: {e}")
            pytest.skip(f"no Chromium for Playwright: {e}")
        instance.close()
    # This is only the skip guard. It holds no live browser because
    # `devtools._session` opens its own `sync_playwright()` per `look`, and two
    # sync Playwright sessions cannot share one thread.
    yield instance


def _png_size(path):
    """`(width, height)` read out of the PNG's own IHDR chunk."""
    head = Path(path).read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    assert head[12:16] == b"IHDR", f"{path} has no IHDR chunk"
    return (int.from_bytes(head[16:20], "big"),
            int.from_bytes(head[20:24], "big"))


def _look(**kw):
    """`vefr look` through the front door, the way a shell would call it."""
    base = dict(html=None, pack=str(SAMPLE), out=None, steps="",
                json=True, scenario=None, sizes=None, at=None, seed=None)
    base.update(kw)
    return cli.cmd_look(SimpleNamespace(**base))


def _woven(pack, folder, name):
    out = Path(folder) / name
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    return out


# ------------------------------------------------------------------ sizes

def test_a_size_is_read_from_a_repeated_or_a_comma_separated_flag():
    """Both spellings say the same thing, and one value is one size."""
    assert devtools._parse_sizes(["390x844,1440x900"]) == (
        [(390, 844), (1440, 900)], None)
    assert devtools._parse_sizes(["390x844", "1440x900"]) == (
        [(390, 844), (1440, 900)], None)
    assert devtools._parse_sizes(["390x844"]) == ([(390, 844)], None)
    assert devtools._parse_sizes([" 390X844 "]) == ([(390, 844)], None)
    assert devtools._parse_sizes(None) == ([], None)
    assert devtools._parse_sizes([]) == ([], None)


@pytest.mark.parametrize("spec", ["900", "wide x tall", "390", "-1x844",
                                  "0x0", "390x", "390x844x1"])
def test_a_size_that_is_not_a_size_is_refused_before_a_browser_opens(spec):
    sizes, why = devtools._parse_sizes([spec])
    assert sizes is None and why, spec


def test_a_size_larger_than_a_screen_is_refused():
    sizes, why = devtools._parse_sizes([f"{devtools.SIZE_MAX + 1}x844"])
    assert sizes is None and "between 1" in why


def test_a_bad_size_is_a_usage_error_off_the_command_line(capsys):
    assert _look(sizes=["not-a-size"]) == 2
    assert "WxH" in capsys.readouterr().err


def test_every_size_gets_its_own_file_named_for_the_size():
    assert devtools._sized_path(Path("shots/look.png"), (390, 844)) == Path(
        "shots/look-390x844.png")
    assert devtools._sized_path(Path("look.png"), (1440, 900)) == Path(
        "look-1440x900.png")
    assert devtools._sized_path(Path("look"), (800, 600)) == Path("look-800x600")


# -------------------------------------------------------------------- at

def test_at_names_the_region_it_could_not_find(capsys):
    """A region that is not the pack's is refused, and the sentence says
    which region was asked for - before any browser opens."""
    assert _look(at="nowhere 1,1") == 2
    err = capsys.readouterr().err
    assert "nowhere" in err and "town" in err


def test_at_refuses_a_tile_that_is_off_the_map(capsys):
    assert _look(at="town 999,999") == 2
    assert "outside town" in capsys.readouterr().err


def test_at_refuses_a_tile_the_hero_cannot_stand_on(capsys):
    assert _look(at="town 0,0") == 2          # the border tile is solid
    assert "stand on" in capsys.readouterr().err


@pytest.mark.parametrize("spec", ["town", "town 4", "town a,b", "4,6"])
def test_at_refuses_anything_that_is_not_region_x_y(spec, capsys):
    assert _look(at=spec) == 2
    assert "--at takes REGION X,Y" in capsys.readouterr().err


def test_at_needs_a_pack_because_the_region_is_checked_against_it(capsys):
    assert _look(html="woven.html", at="town 4,6") == 2
    assert "needs --pack" in capsys.readouterr().err


def test_at_and_scenario_both_name_a_start_so_only_one_may_be_asked_for(capsys):
    assert _look(at="town 4,6", scenario="anything") == 2
    assert "both name a start" in capsys.readouterr().err


def test_a_valid_at_is_resolved_against_the_pack_without_a_browser():
    boot, problems = devtools.at_boot(SAMPLE, "town 4,6")
    assert not problems
    assert boot["start"] == {"region": "town", "at": [4, 6]}
    assert boot["storage"] is None, "--at plants no save keys; it is a start"


# ------------------------------------------------------------------ seed

def test_the_seed_parameter_is_the_same_word_in_python_and_the_player():
    """The player's `?vefr-seed=` and `--seed` are one name in two
    languages. If either moves without the other, `--seed` silently
    photographs the pack's own seed again."""
    source = PLAYER.read_text(encoding="utf-8")
    assert f"var SEED_PARAM = '{devtools.SEED_PARAM}'" in source
    assert f"var SEED_MAX = {devtools.SEED_MAX}" in source


@pytest.mark.parametrize("seed, why", [
    ("", "takes a seed"),
    ("   ", "takes a seed"),
    ("a" * (devtools.SEED_MAX + 1), "at most"),
    ("two\nlines", "plain text"),
])
def test_a_seed_that_is_not_a_seed_is_refused_before_a_browser_opens(seed, why, capsys):
    assert devtools._seed_or_refusal(seed) == (None, 2)
    assert _look(seed=seed) == 2
    assert why in capsys.readouterr().err


def test_a_seed_is_trimmed_and_asked_for_through_the_players_own_parameter():
    seed, refused = devtools._seed_or_refusal("  hello  ")
    assert refused is None and seed == "hello"
    uri = devtools._page_uri(SAMPLE / "world.json", seed)
    assert uri.endswith(f"?{devtools.SEED_PARAM}=hello")
    # A seed is a URL parameter value: encoded, so a space or an `&`
    # cannot smuggle a second parameter into the URL.
    assert devtools._page_uri(SAMPLE, "a b&c=d").endswith(
        f"?{devtools.SEED_PARAM}=a%20b%26c%3Dd")
    assert "?" not in devtools._page_uri(SAMPLE / "world.json", None)


# ---------------------------------------------------------- containment

def _at_size(stage, pieces, window):
    """One size's measurement, in the shape the page reports it in."""
    return {"stage": stage, "els": list(pieces), "vw": window[0], "vh": window[1]}


def _piece(left, top, right, bottom):
    return {"id": "the-piece", "l": left, "t": top, "r": right, "b": bottom}


def test_the_report_measures_the_stage_and_not_the_viewport():
    """A piece that has fallen out of the framed play panel and onto the
    page around it is inside the viewport and outside the stage. A
    report that measured the viewport would call this clean."""
    stage = {"x": 100, "y": 100, "w": 400, "h": 300}
    outside = devtools._containment(_at_size(stage, [_piece(8, 8, 120, 60)],
                                              (500, 400)))
    assert outside["measured"] == "stage"
    assert outside["stage"] == stage
    assert outside["outside"] == ["the-piece"]
    inside = devtools._containment(_at_size(stage, [_piece(120, 120, 200, 200)],
                                            (500, 400)))
    assert inside["outside"] == []


def test_a_piece_outside_the_stage_is_caught_at_a_phone_width_and_not_at_a_desktop_one():
    """The regression this reporting exists to prevent: a piece that sits
    inside the stage on a wide window and outside it on a phone. Measured
    once, the desktop answer would stand in for both."""
    desktop = {"x": 120, "y": 40, "w": 1040, "h": 640}
    phone = {"x": 0, "y": 0, "w": 390, "h": 844}
    piece = _piece(800, 120, 950, 200)          # the same box at both sizes
    assert devtools._containment(_at_size(desktop, [piece], (1280, 800)))[
        "outside"] == []
    caught = devtools._containment(_at_size(phone, [piece], (390, 844)))
    assert caught["outside"] == ["the-piece"]
    assert caught["window"] == [390, 844]


def test_a_game_that_published_no_stage_says_so_rather_than_looking_clean():
    report = devtools._containment(_at_size(None, [], (390, 844)))
    assert report["measured"] == "viewport-only"
    assert report["stage"] is None and report["outside"]


# --------------------------------------------------- the layout on disk

def test_the_verb_row_is_a_child_of_the_hud_frame():
    """The fix for #353 in the shell itself: the fight verbs are placed
    against `.hud-frame`, the painted play panel, and not against the
    page. As a sibling of the frame their offset parent was `#stage` -
    the whole page - and the row pinned to its bottom-left corner."""
    shell = SHELL.read_text(encoding="utf-8")
    frame = shell.index('<div class="hud-frame" id="hud-frame">')
    row = shell.index('id="verb-row"')
    frame_closes = shell.index("\n      </div>", frame)
    assert frame < row < frame_closes, "the verb row is not inside .hud-frame"


# ------------------------------------------------------------- the browser

@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """The shipped sample world, woven as-is."""
    return _woven(SAMPLE, tmp_path_factory.mktemp("look-sizes"), "sample.html")


def test_two_sizes_write_two_files_that_hold_the_size_that_was_asked_for(
        browser, woven, tmp_path, capsys):
    """`--sizes 390x844,1440x900` photographs the pack at both, and the
    PNG header is the proof - not the file's name."""
    out = tmp_path / "look.png"
    assert _look(html=str(woven), out=str(out), sizes=["390x844,1440x900"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [run["size"] for run in report["runs"]] == [[390, 844], [1440, 900]]
    paths = [Path(run["screenshot"]) for run in report["runs"]]
    assert paths == [tmp_path / "look-390x844.png", tmp_path / "look-1440x900.png"]
    for path, (width, height) in zip(paths, [(390, 844), (1440, 900)]):
        assert path.is_file(), path
        assert _png_size(path) == (width, height)
        assert str(width) in path.name, "the size is in the file's name too"


def test_one_size_is_todays_run(browser, woven, tmp_path, capsys):
    """`--sizes` with one value, and no `--sizes` at all, are the same
    run: the same file, holding the default viewport."""
    plain = tmp_path / "plain.png"
    assert _look(html=str(woven), out=str(plain)) == 0
    first = json.loads(capsys.readouterr().out)
    assert _png_size(plain) == tuple(devtools.DEFAULT_VIEWPORT)
    assert "screenshot" in first and "overlay_text" in first

    width, height = devtools.DEFAULT_VIEWPORT
    one = tmp_path / "one.png"
    assert _look(html=str(woven), out=str(one), sizes=[f"{width}x{height}"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["screenshot"] == str(one), (
        "one size writes --out itself, with no size in the name")
    assert sorted(second) == sorted(first), "one size is not today's run"
    assert _png_size(one) == _png_size(plain)


def test_the_containment_report_is_emitted_once_per_size(browser, woven,
                                                       tmp_path, capsys):
    assert _look(html=str(woven), out=str(tmp_path / "look.png"),
                 sizes=["390x844,1440x900"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["runs"]) == 2
    for run in report["runs"]:
        containment = run["containment"]
        assert containment["measured"] == "stage", run["size"]
        assert containment["window"] == run["size"]
        assert containment["outside"] == [], (run["size"], containment["outside"])
    # The two are measured, not copied: a phone in dock mode publishes the
    # whole window as its stage, and a desktop window publishes the map.
    stages = [run["containment"]["stage"] for run in report["runs"]]
    assert stages[0] != stages[1], stages


def test_at_starts_the_run_where_it_was_asked_to(browser, tmp_path, capsys):
    out = tmp_path / "at.png"
    assert _look(pack=str(SAMPLE), out=str(out), at="town 4,6") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["at"] == {"region": "town", "at": [4, 6]}
    assert out.is_file()


# ------------------------------------------------------ the seed, for real

@pytest.fixture(scope="module")
def descent_packs(tmp_path_factory):
    """Two descent fixture packs: one seeded `hello` in world.json, one
    carrying a different seed of its own. The parameter has to make the
    first answer as if the seed had been baked at weave time."""
    import make_descent_pack

    home = tmp_path_factory.mktemp("seed-packs")

    def one(run_seed):
        return make_descent_pack.build(home / run_seed, descent={
            "run_seed": run_seed,
            "entry": {"region": "town", "at": list(make_descent_pack.ENTRY_AT)},
            "sections": make_descent_pack.SECTIONS,
        })

    return one("hello"), one("run-a")


SEED_JS = """() => {
  const D = window.VEFR_DESCENT;
  if (!D || !D.on()) return null;
  const at = D.locate(1);
  return {
    param: D.seedParam(),
    baseSeed: D.baseSeed(),
    seedFor0: D.seedFor(0),
    seedFor1: D.seedFor(1),
    key: D.floorKey(D.seedFor(0), at.section, at.cycle, at.k),
    rows: (D.floorPlan(1, 0) || {rows: []}).rows,
  };
}"""


def _read_seed(html, seed=None):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            page.goto(devtools._page_uri(html, seed))
            page.click("#ts-enter")
            page.wait_for_function("window.VEFR_DESCENT", timeout=15000)
            page.wait_for_timeout(500)
            return page.evaluate(SEED_JS)
        finally:
            ctx.close()
            browser.close()


def test_the_seed_parameter_starts_the_descent_with_that_base_seed(
        browser, descent_packs, tmp_path):
    """`?vefr-seed=hello` is the same game as a pack baked with
    `run_seed: hello`: the same base seed and the same floor, drawn from
    the same key."""
    baked, other = descent_packs
    with_param = _read_seed(_woven(baked, tmp_path, "baked.html"),
                            seed="hello")
    without = _read_seed(_woven(baked, tmp_path, "baked2.html"))
    other_pack = _read_seed(_woven(other, tmp_path, "other.html"),
                            seed="hello")
    assert with_param["baseSeed"] == "hello"
    assert with_param["seedFor0"] == "hello"
    assert with_param["seedFor1"] == "hello/run-1", "a later run still derives"
    assert without["baseSeed"] == "hello"
    assert with_param["rows"] == without["rows"], (
        "the parameter drew a different floor than the baked seed")
    assert with_param["key"] == without["key"]
    assert other_pack["seedFor0"] == with_param["seedFor0"]
    assert other_pack["rows"] == with_param["rows"], (
        "the same seed gives the same floor whatever pack carries it")


def test_no_seed_parameter_leaves_the_pages_seed_exactly_as_it_was(
        browser, descent_packs, tmp_path):
    baked, other = descent_packs
    opened = _read_seed(_woven(baked, tmp_path, "plain.html"))
    assert opened["param"] == ""
    assert opened["baseSeed"] == "hello", "the pack's own seed still wins"
    its_own = _read_seed(_woven(other, tmp_path, "own.html"))
    assert its_own["baseSeed"] == "run-a"
    assert its_own["rows"] != opened["rows"], "the fixtures are not one floor"


def test_a_pack_with_no_descent_ignores_the_seed_exactly_as_it_did_today(
        browser, woven):
    """No descent means no seed to choose. The parameter is read by the
    descent, which is off, so the game is the game it was - and `vefr
    look --seed` still writes its screenshot."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        instance = p.chromium.launch()
        ctx = instance.new_context()
        page = ctx.new_page()
        try:
            page.goto(devtools._page_uri(woven, seed="hello"))
            page.click("#ts-enter")
            page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
            page.wait_for_timeout(400)
            state = page.evaluate(
                "() => ({on: !!(window.VEFR_DESCENT && window.VEFR_DESCENT.on()),"
                " url: location.search, combat: !!window.VEFR_COMBAT})")
            assert state["on"] is False, "the sample world does carry a descent"
            assert state["url"] == f"?{devtools.SEED_PARAM}=hello"
            assert state["combat"] is True, "the game came up and played"
        finally:
            ctx.close()
            instance.close()
    out = Path(woven).parent / "seeded.png"
    assert _look(html=str(woven), out=str(out), seed="hello") == 0
    assert out.is_file()