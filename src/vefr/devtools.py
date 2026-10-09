"""`vefr publish` / `vefr look` / `vefr probe`, and the doctor's tooling checks.

The logic behind the front door's developer verbs (the cmd_find/vefr.find
split): `vefr.cli.cmd_publish` only resolves `--pack` and hands the rest
here. Nothing in this module touches the network or a model; the gallery
CLI is the only external process, and it is optional.

`publish` weaves the pack into a fresh, world-readable temp dir (nginx
served tempfile.mkdtemp's 0700 as 403) and asks the gallery to build it.
`look` screenshots the woven player and lists the text sitting over the
map; `probe` fires rule events and reads the player's why-log back.
`tooling_checks` answers, honestly, which optional dev tools this machine
has and how to install the ones it does not.
"""

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

# The install hint for the browser both devtools verbs drive.
BROWSER_HINT = 'uv run playwright install chromium'

# Where an absent gallery is documented - one hint, one place.
GALLERY_HINT = 'see ~/.agents/skills/gallery'

# The viewport `look` opens the woven player at when no size is asked
# for. Unchanged since the first `look`; `--sizes` is the way to say a
# different one.
DEFAULT_VIEWPORT = (1280, 800)

# The URL parameter the player reads a run seed from (`?vefr-seed=`),
# and the seed length the player itself caps it at. The name lives in
# `397-the-descent.js` too, and `tests/test_look_sizes.py` pins the two
# together, so neither can move without the other.
SEED_PARAM = 'vefr-seed'
SEED_MAX = 120

# `--sizes 390x844` - one width, one height, both whole and positive.
SIZE = re.compile(r'([0-9]{1,5})[xX]([0-9]{1,5})')
SIZE_MAX = 10000

# `--at REGION X,Y`: a region id (which may hold spaces) then one tile.
AT = re.compile(r'(.+?)\s+(-?\d+)\s*,\s*(-?\d+)')


def _gallery_bin(which=shutil.which, home=None):
    """The gallery CLI, or None.

    `$VEFR_GALLERY` wins when set - even a broken path, so a wrong
    override is refused instead of silently falling through to the
    bundled one. Otherwise PATH, then `~/.agents/bin/gallery`.
    """
    home = Path.home() if home is None else Path(home)
    env = os.environ.get('VEFR_GALLERY')
    if env:
        return env if Path(env).exists() else None
    found = which('gallery')
    if found:
        return found
    bundled = home / '.agents' / 'bin' / 'gallery'
    if bundled.exists():
        return str(bundled)
    return None


def _git_sha(pack: Path) -> str:
    """`git rev-parse --short HEAD` in `pack`, or `nogit`."""
    try:
        out = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=pack, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return 'nogit'
    return out.stdout.strip() or 'nogit'


def publish(pack, project=None, sha=None, live=False, dry_run=False) -> int:
    """Weave `pack` and hand the built file to the gallery CLI.

    The pack is woven into `index.html` inside a fresh temp dir, then
    the gallery's own `build` command carries it to the site. `dry_run`
    prints the command it would run and stops; otherwise the gallery's
    exit code passes straight through and the temp dir is always
    cleaned up.
    """
    from .cli import weave_html

    pack = Path(pack)
    project = project or pack.name
    if sha is None:
        sha = _git_sha(pack)
    gallery = _gallery_bin()
    if not gallery:
        print('gallery not found: set VEFR_GALLERY, put gallery on PATH, '
              f'or install it under ~/.agents/bin ({GALLERY_HINT})',
              file=sys.stderr)
        return 2

    dist = tempfile.mkdtemp(prefix='vefr-publish-')
    try:
        os.chmod(dist, 0o755)
        index = Path(dist) / 'index.html'
        index.write_text(weave_html(pack), encoding='utf-8')
        os.chmod(index, 0o644)

        cmd = [gallery, 'build', project, dist, '--sha', sha]
        if live:
            cmd.append('--live')
        if dry_run:
            print('would run: ' + ' '.join(cmd))
            return 0
        return subprocess.run(cmd).returncode
    finally:
        shutil.rmtree(dist, ignore_errors=True)


# ------------------------------------------------------------ look / probe

def _no_browser() -> None:
    """The one missing-browser message, on STDERR; callers return 2."""
    print(f'Playwright / Chromium not available: run `{BROWSER_HINT}`',
          file=sys.stderr)


@contextlib.contextmanager
def _player_file(html, pack):
    """The player file to open: `html`, or a weave of `pack` in a temp file.

    A woven copy is always removed afterwards. Woven ONCE per command,
    not once per size: every size photographs the same bytes.
    """
    if html is not None:
        yield Path(html)
        return
    from .cli import weave_html

    fd, tmp = tempfile.mkstemp(prefix='vefr-devtools-', suffix='.html')
    os.close(fd)
    temp = Path(tmp)
    try:
        temp.write_text(weave_html(Path(pack)), encoding='utf-8')
        yield temp
    finally:
        temp.unlink(missing_ok=True)


def _page_uri(html, seed=None):
    """The URI to open, carrying `?vefr-seed=` when a seed is asked for.

    The parameter is the player's own (ADR 0016's start-position seam,
    not a second save format): the woven game reads it and answers with
    that seed. Percent-encoded, because a seed is a URL parameter value
    and a URL is untrusted input.
    """
    uri = Path(html).resolve().as_uri()
    if not seed:
        return uri
    return f'{uri}?{SEED_PARAM}={quote(seed, safe="")}'


@contextlib.contextmanager
def _session(path, wait_ms, plant=None, size=None, seed=None):
    """Open the player file `path` in headless Chromium and press Begin.

    Yields the page once the game is up, or None when Playwright/Chromium
    is missing (the install hint goes to STDERR and the caller returns 2).
    `size` is the `(width, height)` viewport; without one the viewport is
    `DEFAULT_VIEWPORT`, which is what `look` always opened.
    `seed` rides the `?vefr-seed=` parameter.

    Playwright is imported here, lazily - nothing imports it at module load.

    `plant` is a scenario's save keys (`vefr.scenarios.storage`): written
    into the page's storage before any of the game's scripts run, so the
    player reads them as its own save. Only those keys are written; no
    other storage is read, cleared or enumerated.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:  # noqa: BLE001 - not installed is a report, not a crash
        _no_browser()
        yield None
        return

    width, height = size or DEFAULT_VIEWPORT
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:  # noqa: BLE001 - Chromium not installed
            _no_browser()
            yield None
            return
        page = browser.new_page(viewport={'width': width, 'height': height})
        if plant:
            page.add_init_script(_PLANT_JS % json.dumps(plant))
        page.goto(_page_uri(path, seed))
        page.click('#ts-enter')
        page.wait_for_timeout(wait_ms)
        try:
            yield page
        finally:
            browser.close()


# A scenario's save keys, written before the game's own scripts run. A
# browser that blocks storage leaves the game to start fresh; the arrival
# check below then says the scenario did not take.
_PLANT_JS = """(() => {
  const keys = %s;
  try { for (const k of Object.keys(keys)) localStorage.setItem(k, keys[k]); }
  catch (e) {}
})();"""

# Walk the hero in through the player's own arrival paths, then read the
# harness's window onto play back: where the hero is, and the world name the
# planted keys had to match.
_ARRIVE_JS = """(s) => {
  let entered = false;
  if (s.depth) {
    entered = !!(window.VEFR_DESCENT && window.VEFR_DESCENT.enterDescentFloor(s.depth));
  } else if (typeof window.VEFR_ENTER_REGION === 'function') {
    window.VEFR_ENTER_REGION(s.region, s.at || null);
    entered = true;
  }
  const c = window.VEFR_COMBAT || {};
  const floor = window.VEFR_DESCENT ? window.VEFR_DESCENT.floor : null;
  return {
    entered: entered,
    world: (window.VEFR_WORLD && window.VEFR_WORLD.name) || 'world',
    region: c.region || null,
    at: (c.hero && c.hero.at) || null,
    hp: (c.hero && c.hero.hp) || null,
    gold: (typeof c.gold === 'number') ? c.gold : null,
    depth: floor ? floor.depth : null,
    card: !!(window.VEFR_DESCENT && window.VEFR_DESCENT.cardShown && window.VEFR_DESCENT.cardShown()),
  };
}"""


def scenario_boot(pack, name):
    """`(boot, None)` for a pack's scenario, or `(None, sentences)`.

    `boot` holds what a session needs: the save keys to plant, the start
    to walk the hero to, and the world name those keys were written for.
    An invalid scenario is refused with the same sentences `vefr check`
    speaks, before any browser opens.
    """
    from . import maplab, scenarios

    w = maplab.load_pack(Path(pack))
    data, why = scenarios.load(pack, name)
    if why is not None:
        return None, [why]
    problems = scenarios.check(w, data)
    if problems:
        return None, [f'scenarios/{name}.json: {p}' for p in problems]
    return {'name': name, 'label': f'scenario {name!r}',
            'storage': scenarios.storage(w, data),
            'start': data['start'], 'world': scenarios.world_name(w),
            'gold': data.get('gold')}, None


def at_boot(pack, spec):
    """`(boot, None)` for a `--at REGION X,Y` start, or `(None, sentences)`.

    `--at` is a start-position override and nothing more: the small
    half of what a scenario does, for the case where the state is not
    worth a checked-in file (ADR 0016). It needs `--pack`, because the
    region and the tile are checked against the pack - with the same
    `vefr check` sentences - before any browser opens, and it cannot be
    combined with `--scenario`, which already names a start.
    """
    from . import maplab, scenarios

    # `REGION X,Y`, and a region id may itself contain spaces, so the
    # coordinates are matched off the end and everything before them is
    # the region.
    usage = f'--at takes REGION X,Y, such as --at town 4,6: {spec!r}'
    match = AT.fullmatch(str(spec).strip())
    if not match:
        return None, [usage]
    name = match.group(1).strip()
    x, y = int(match.group(2)), int(match.group(3))
    if not name:
        return None, [usage]
    w = maplab.load_pack(Path(pack))
    regions = maplab.region_geometry(w)
    if name not in regions:
        return None, [f'--at {name!r} is not a region of this pack; it has '
                      + (', '.join(sorted(regions)) or 'none')]
    geo = regions[name]
    walkable = maplab._map_tile_walkable(geo.get('map') or [],
                                         geo.get('legend') or {}, x, y)
    if walkable is None:
        rows = geo.get('map') or []
        size = f'{len(rows[0]) if rows else 0}x{len(rows)}'
        return None, [f'--at {[x, y]} is outside {name} ({size} tiles)']
    if not walkable:
        return None, [f'--at {[x, y]} is not a tile the hero can stand on in {name}']
    return {'name': None, 'label': f'--at {name} {x},{y}', 'storage': None,
            'start': {'region': name, 'at': [x, y]},
            'world': scenarios.world_name(w), 'gold': None}, None


def _arrive(page, boot):
    """Walk the hero to the boot's start; `(report, problem or None)`."""
    who = boot['label']
    page.wait_for_timeout(200)
    report = page.evaluate(_ARRIVE_JS, boot['start'])
    page.wait_for_timeout(300)
    start = boot['start']
    if report['world'] != boot['world']:
        return report, (f"the woven game names this world {report['world']!r}, "
                        f"but {who} was written for "
                        f"{boot['world']!r}")
    if report['card'] and boot.get('storage'):
        return report, (f'{who}: the game took the planted '
                        'state for a Release 1 save and opened its generation card')
    if boot.get('gold') is not None and report['gold'] != boot['gold']:
        return report, (f'{who} planted {boot["gold"]} gold '
                        f"and the game holds {report['gold']}")
    if not report['entered']:
        return report, f'{who}: the game would not enter its start'
    if 'depth' in start and report['depth'] != start['depth']:
        return report, (f'{who} asked for depth '
                        f"{start['depth']} and the hero is at depth {report['depth']}")
    if 'region' in start and report['region'] != start['region']:
        return report, (f'{who} asked for {start["region"]} '
                        f"and the hero is in {report['region']}")
    if start.get('at') and report['at'] != list(start['at']):
        return report, (f'{who} asked for {list(start["at"])} '
                        f"and the hero stands at {report['at']}")
    return report, None


# Visible leaves whose top is in the lower 40% of the viewport, or that
# sit in the toasts strip. `children.length === 0` is the leaf test.
_LEAF_JS = """() => {
  const floor = window.innerHeight * 0.6;
  const out = [];
  document.querySelectorAll('body *').forEach((el) => {
    if (el.children.length) return;
    const text = (el.innerText || '').trim();
    if (!text) return;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return;
    const rect = el.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    if (!el.closest('.toasts') && rect.top < floor) return;
    out.push({
      id: el.id || '',
      cls: (typeof el.className === 'string' ? el.className : ''),
      tag: el.tagName.toLowerCase(),
      y: Math.round(rect.top),
      text: text.slice(0, 90),
    });
  });
  return out;
}"""


# Every visible HUD piece and control, with its rectangle, plus the
# stage rectangle the player itself published (`440-the-camera.js`).
# The stage and not the viewport is what a containment report has to
# measure: a check that measures the viewport cannot tell a control that
# sits inside the framed play panel from one that has fallen out of it
# onto the page around it, which is how the fight verb row passed for
# years (issue #353).
_CONTAINMENT_JS = """() => {
  const sel = '#play .hud .glass, #play .hud button, #play .gbtn, #play .toasts p,'
    + ' #play .toasts-toggle, #dpad button, #play #interact, #play .acts button,'
    + ' #play .verb-row button';
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || el.hidden
        || el.closest('[hidden]')) continue;
    if (el.classList.contains('sr-only') || el.closest('.sr-only')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    out.push({id: el.id || (typeof el.className === 'string'
          ? el.className.split(' ')[0] : '') || el.tagName.toLowerCase(),
      l: r.left, t: r.top, r: r.right, b: r.bottom});
  }
  return {stage: window.VEFR_STAGE || null, els: out,
          vw: innerWidth, vh: innerHeight};
}"""


def _containment(info):
    """One size's containment report: what was measured and what fell out.

    `{measured: 'stage'|'viewport-only', stage, map, window, outside}`.
    `measured: 'viewport-only'` says out loud that the game published no
    stage, so a reader never mistakes an unmeasured run for a clean one.
    """
    stage = info.get('stage')
    window = [info.get('vw'), info.get('vh')]
    if not stage:
        return {'measured': 'viewport-only', 'stage': None, 'map': None,
                'window': window,
                'outside': ['the game published no window.VEFR_STAGE']}
    outside = [e['id'] for e in info['els']
               if e['l'] < stage['x'] - 1 or e['t'] < stage['y'] - 1
               or e['r'] > stage['x'] + stage['w'] + 1
               or e['b'] > stage['y'] + stage['h'] + 1]
    return {'measured': 'stage',
            'stage': {k: stage[k] for k in ('x', 'y', 'w', 'h')},
            'map': stage.get('map'),
            'window': window,
            'outside': outside}


def _parse_sizes(sizes):
    """`([(w, h), ...], sentence or None)` for a `--sizes` list.

    Each entry is one `WxH`, and the flag repeats or comma-separates, so
    `--sizes 390x844,1440x900` and `--sizes 390x844 --sizes 1440x900`
    say the same thing. A size that is not two positive whole numbers is
    a usage error, refused before any browser opens.
    """
    out = []
    for spec in sizes or ():
        for part in str(spec).split(','):
            part = part.strip()
            if not part:
                continue
            match = SIZE.fullmatch(part)
            if not match:
                return None, (f'use WxH, such as 390x844 or 1440x900: {part!r}')
            width, height = int(match.group(1)), int(match.group(2))
            if not 0 < width <= SIZE_MAX or not 0 < height <= SIZE_MAX:
                return None, (f'a viewport must be between 1 and {SIZE_MAX} '
                              f'pixels on a side: {part!r}')
            out.append((width, height))
    return out, None


def _sized_path(out: Path, size) -> Path:
    """`out` with the size in its name: `look.png` -> `look-390x844.png`."""
    return out.with_name(f'{out.stem}-{size[0]}x{size[1]}{out.suffix}')


def _seed_or_refusal(seed):
    """The seed to ask the game for, or `None` and a sentence on STDERR."""
    if seed is None:
        return None, None
    seed = str(seed).strip()
    if not seed:
        print('--seed takes a seed, such as --seed hello', file=sys.stderr)
        return None, 2
    if len(seed) > SEED_MAX or any(c in seed for c in '\r\n\t'):
        print(f'a seed is at most {SEED_MAX} characters of plain text',
              file=sys.stderr)
        return None, 2
    return seed, None


def _boot_or_refusal(verb, pack, scenario, at):
    """`(boot or None, exit code or None)`: where the run starts.

    A scenario needs `--pack`, and an invalid one is refused with its
    sentences before a browser opens. `--at` needs `--pack` too, because
    the region and the tile are checked against the pack the same way a
    scenario's are; the two name the same thing, so asking for both is
    refused rather than silently preferring one.
    """
    if scenario is not None and at is not None:
        print(f'vefr {verb} --at and --scenario both name a start; pass one',
              file=sys.stderr)
        return None, 2
    if at is not None and pack is None:
        print(f'vefr {verb} --at needs --pack: the region and the tile are '
              'checked against the pack', file=sys.stderr)
        return None, 2
    if at is not None:
        boot, problems = at_boot(pack, at)
    elif scenario is not None and pack is None:
        print(f'vefr {verb} --scenario needs --pack: a scenario lives in its '
              'pack', file=sys.stderr)
        return None, 2
    elif scenario is not None:
        boot, problems = scenario_boot(pack, scenario)
    else:
        return None, None
    if problems:
        for sentence in problems:
            print(sentence, file=sys.stderr)
        return None, 2
    return boot, None


def look(html=None, pack=None, out=None, steps='', json_out=False,
         scenario=None, sizes=None, at=None, seed=None) -> int:
    """Screenshot the woven player and list the text standing over the map.

    Opens `html` (or weaves `pack`), presses Begin, replays the comma-
    separated `steps` keys, then screenshots to `out` (default `look.png`)
    and reports every visible leaf in the lower 40% of the viewport or in
    the toasts strip: `{id, cls, tag, y, text}`. The tool for catching
    text that has drifted onto the map.

    `sizes` photographs the pack at each `WxH` it names, one file per
    size with the size in the name (`look-390x844.png`), and repeats
    the containment report at every one of them - a piece that sits
    inside the stage at 1280x800 can be outside it at 390x844, and a
    report measured once cannot see that. One size (or none) writes
    `out` exactly as before.

    `seed` asks the game for a run seed of its own, through the player's
    own `?vefr-seed=` parameter, and `at` (`REGION X,Y`) starts the run
    somewhere other than the world's start region. `scenario` (a name in
    the pack's `scenarios/`) opens the game in that state first: its
    save keys planted, the hero walked to its start.
    """
    if html is None and pack is None:
        print('vefr look needs --html or --pack', file=sys.stderr)
        return 2
    sizes, why = _parse_sizes(sizes)
    if why is not None:
        print(why, file=sys.stderr)
        return 2
    seed, refused = _seed_or_refusal(seed)
    if refused is not None:
        return refused
    boot, refused = _boot_or_refusal('look', pack, scenario, at)
    if refused is not None:
        return refused

    out = Path(out or 'look.png')
    wanted = sizes or [DEFAULT_VIEWPORT]
    runs = []
    arrival = None
    with _player_file(html, pack) as player:
        for size in wanted:
            path = out if len(wanted) == 1 else _sized_path(out, size)
            with _session(player, 800, plant=boot and boot['storage'],
                          size=size, seed=seed) as page:
                if page is None:
                    return 2
                if boot is not None:
                    arrival, problem = _arrive(page, boot)
                    if problem is not None:
                        print(problem, file=sys.stderr)
                        return 1
                for key in (k.strip() for k in steps.split(',') if k.strip()):
                    page.keyboard.press(key)
                    page.wait_for_timeout(250)
                page.wait_for_timeout(3000)
                page.screenshot(path=str(path))
                runs.append({'size': [size[0], size[1]], 'screenshot': str(path),
                             'containment': _containment(page.evaluate(_CONTAINMENT_JS)),
                             'overlay_text': page.evaluate(_LEAF_JS)})

    if json_out:
        if len(wanted) == 1:
            # One size is today's run, exactly: the same keys at the top level.
            report = {'screenshot': runs[0]['screenshot'],
                      'overlay_text': runs[0]['overlay_text'],
                      'containment': runs[0]['containment']}
        else:
            report = {'sizes': [list(s) for s in wanted], 'runs': runs}
        if arrival is not None and boot['name'] is not None:
            report['scenario'] = {'name': boot['name'], **arrival}
        if at is not None:
            report['at'] = dict(boot['start'])
        if seed is not None:
            report['seed'] = seed
        print(json.dumps(report))
        return 0
    for run in runs:
        if len(wanted) > 1:
            print(f'size: {run["size"][0]}x{run["size"][1]}')
        if arrival is not None:
            where = (f"depth {arrival['depth']}" if arrival['depth']
                     else arrival['region'])
            print(f'{boot["label"]} - {where} at {arrival["at"]}')
        print(f'screenshot: {run["screenshot"]}')
        report = run['containment']
        if report['stage']:
            stage = report['stage']
            print(f"stage: {stage['x']},{stage['y']} {stage['w']}x{stage['h']}")
        else:
            print('stage: none published by the game')
        print(f"containment: {len(report['outside'])} piece(s) outside "
              f"({report['measured']})"
              + (f" - {', '.join(report['outside'])}" if report['outside'] else ''))
        print(f'{"y":>6}  {"tag":<6} {"id":<18} text')
        for e in run['overlay_text']:
            print(f'{e["y"]:>6}  {e["tag"]:<6} {e["id"]:<18} {e["text"]}')
    return 0


def _parse_fire(spec: str):
    """`event:key=value[,key=value]` -> (event, data), or None if malformed.

    An integer-looking value becomes an int; anything else stays a string.
    """
    event, sep, rest = spec.partition(':')
    if not sep or not event:
        return None
    data = {}
    for pair in rest.split(','):
        key, eq, value = pair.partition('=')
        if not eq or not key:
            return None
        try:
            data[key] = int(value)
        except ValueError:
            data[key] = value
    return event, data


_FIRE_JS = '(s) => { if (window.fireRule) window.fireRule(s.event, s.data); }'
_READ_JS = """() => ({
  why: Array.isArray(window.VEFR_WHY) ? window.VEFR_WHY : [],
  flags: (window.VEFR_RULES_STATE && window.VEFR_RULES_STATE.flags) || {},
})"""


def probe(html=None, pack=None, fire=(), json_out=False, scenario=None) -> int:
    """Fire rule events at the woven player and read its why-log back.

    Each `event:key=value[,key=value]` spec calls the player's global
    `window.fireRule`; afterwards `window.VEFR_WHY` and the engine's
    flags are read out. A malformed spec is a usage error, refused before
    any browser is launched. With `scenario`, the events are fired in that
    scenario's state (see `look`).
    """
    parsed = []
    for spec in fire:
        event_data = _parse_fire(spec)
        if event_data is None:
            print('use event:key=value', file=sys.stderr)
            return 2
        parsed.append(event_data)

    if html is None and pack is None:
        print('vefr probe needs --html or --pack', file=sys.stderr)
        return 2
    boot, refused = _boot_or_refusal('probe', pack, scenario, None)
    if refused is not None:
        return refused

    arrival = None
    with _player_file(html, pack) as player, \
            _session(player, 300, plant=boot and boot['storage']) as page:
        if page is None:
            return 2
        if boot is not None:
            arrival, problem = _arrive(page, boot)
            if problem is not None:
                print(problem, file=sys.stderr)
                return 1
        for event, data in parsed:
            page.evaluate(_FIRE_JS, {'event': event, 'data': data})
            page.wait_for_timeout(50)
        report = page.evaluate(_READ_JS)

    fired = [{'event': e, 'data': d} for e, d in parsed]
    result = {'fired': fired, 'why': report['why'], 'flags': report['flags']}
    if arrival is not None:
        result['scenario'] = {'name': boot['name'], **arrival}
    if json_out:
        print(json.dumps(result))
        return 0
    for e in fired:
        print(f'fired {e["event"]} {e["data"]}')
    for w in result['why']:
        print(f'why {w.get("id")}: {w.get("why")}')
    for key, value in result['flags'].items():
        print(f'flag {key} = {value}')
    return 0


def tooling_checks(root, which=shutil.which, home=Path.home()) -> list[tuple[str, str, str]]:
    """Rows `(name, ok|missing, detail)` for the optional dev tools.

    `ok` means the tool was found and the detail says where; `missing`
    means the detail is the command that installs it. Informational
    only - a missing tool is never an error.
    """
    root = Path(root)
    home = Path(home)
    rows: list[tuple[str, str, str]] = []

    node = which('node')
    rows.append(('node', 'ok', node) if node
                else ('node', 'missing', 'install Node.js'))

    jsdom = root / 'node_modules' / 'jsdom'
    rows.append(('jsdom', 'ok', str(jsdom)) if jsdom.exists()
                else ('jsdom', 'missing', 'run npm ci'))

    chromium = sorted(home.glob('.cache/ms-playwright/chromium*'))
    rows.append(('chromium', 'ok', str(chromium[0])) if chromium
                else ('chromium', 'missing', 'run uv run playwright install chromium'))

    gallery = _gallery_bin(which=which, home=home)
    rows.append(('gallery', 'ok', gallery) if gallery
                else ('gallery', 'missing', GALLERY_HINT))
    return rows
