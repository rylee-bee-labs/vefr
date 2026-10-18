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
from collections import deque
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
    """Walk the hero to the boot's start; `(report, problem or None)`.

    `who` names the boot: its `label` where it has one, else its `name`,
    so a hand-built boot from before `label` existed still reads as itself.
    """
    who = boot.get('label') or boot.get('name') or 'this look'
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


# ------------------------------------------------------------ playthrough
#
# `probe` fires events at the game; a playthrough plays it. The plan is
# read off the pack (no script knows any pack's story): every phase the
# pack declares, and for each one the stops the rules that name that
# phase in `comes-near` ask for - the speaker to walk up to, the place to
# stand on. Then Rest, when the pack declared a Rest, and the next
# phase. Read-only toward the pack: it plays and reports, and it never
# writes a byte of one.

# The step each direction makes on the map, and the shipped key for it
# (`window.VEFR_KEYBINDS`, the one keybinds table part 076 keeps, names
# those; the driver asks the page for the player's own choices and falls
# back to these).
_DIRECTIONS = (('ArrowUp', 0, -1), ('ArrowDown', 0, 1),
                ('ArrowLeft', -1, 0), ('ArrowRight', 1, 0))
_ACTIONS = (('up', 0, -1), ('down', 0, 1), ('left', -1, 0), ('right', 1, 0))

# Every wait is bounded by one of these. Nothing here sleeps blindly: a
# wait is either a poll for something the page publishes, or a cap on
# how long the driver will keep trying to make one step land.
_SETTLE_MS = 1500
_TURN_MS = 3000

# One read of what the game is doing right now: the hero's published
# tile (`window.VEFR_HERO_AT`), the standing phase
# (`window.VEFR_TIME()`), the engine's own fired marks
# (`window.VEFR_RULES_STATE.fired`), the why-log (`window.VEFR_WHY`,
# the same source `probe` reads), and the keybinds as they stand.
# Read-only - it asks the page nothing.
_READ_PLAY_JS = """() => {
  const h = window.VEFR_HERO_AT || null;
  const t = (typeof window.VEFR_TIME === 'function') ? window.VEFR_TIME() : null;
  const s = window.VEFR_RULES_STATE || {};
  return {
    hero: h ? { x: h.x, y: h.y, region: h.region } : null,
    phase: (t && t.phase) || null,
    fired: Object.keys(s.fired || {}),
    why: Array.isArray(window.VEFR_WHY) ? window.VEFR_WHY : [],
    keys: (typeof window.VEFR_KEYBINDS === 'function') ? window.VEFR_KEYBINDS() : null,
  };
}"""

# The game is in play: its own play pane is showing. Not a phase test and
# not an engine test - a pack with no phases still plays, a pack with
# phases still has one behind the title screen, and a pack on a surface
# with no map (the kitchen, the desk) publishes no combat snapshot at all.
_PLAYING_JS = """() => {
  const pane = document.getElementById('play');
  return !!(pane && !pane.hidden);
}"""

# Put away whatever is standing over the game: a speaker's box (with its
# Continue button) and the pause menu. A line the rules said is drawn in
# a floating bubble or a speaker box, not in one place, so the driver
# reads the engine's marks rather than the page's text.
_DISMISS_JS = """() => {
  let closed = 0;
  const box = document.getElementById('npc-box');
  if (box && !box.hidden) {
    const btn = document.getElementById('npc-close');
    if (btn) btn.click(); else box.hidden = true;
    closed++;
  }
  const menu = document.getElementById('menu');
  const opener = document.getElementById('menu-open');
  if (menu && opener && !menu.hidden) { opener.click(); closed++; }
  return closed;
}"""

# A slug a phase name can be a filename: the letters, digits and dashes
# of the name, and nothing else.
_SLUG = re.compile(r'[^A-Za-z0-9._-]+')


def _slug(text: str) -> str:
    """`text` reduced to something safe to write into a filename."""
    return _SLUG.sub('-', str(text)).strip('-') or 'phase'


def _pack_pois(w: dict) -> dict:
    """Every labelled place in the pack: `{region: {label: [x, y]}}`.

    A POI's label IS its id (docs/guides/rules.md), so a `comes-near`
    that names a place is answered here. The flat shape keeps its pois in
    the town block; an acts-shape pack keeps them in each region's
    contract, which the loader also carries for the first region as the
    unified `town`.
    """
    out: dict = {}
    town = w.get('town')
    if isinstance(town, dict) and isinstance(town.get('pois'), dict):
        region = w.get('_region') or 'town'
        out.setdefault(region, {})
        _read_pois(out[region], town['pois'])
    for act in (w.get('acts') or []):
        for name, data in (act.get('regions') or {}).items():
            contract = (data or {}).get('contract') or {}
            if isinstance(contract.get('pois'), dict):
                out.setdefault(name, {})
                _read_pois(out[name], contract['pois'])
    return out


def _read_pois(into: dict, pois: dict) -> None:
    """`{"7,3": "the stone"}` -> `into["the stone"] = [7, 3]`."""
    for key, label in pois.items():
        if not isinstance(label, str):
            continue
        parts = str(key).split(',')
        if len(parts) != 2:
            continue
        try:
            at = [int(parts[0]), int(parts[1])]
        except ValueError:
            continue
        into.setdefault(label, at)


def _names_a_phase(rule: dict) -> bool:
    """True when any `if` condition (inside `not`/`all-of` too) names a phase."""
    def walk(cond):
        if not isinstance(cond, dict):
            return False
        if isinstance(cond.get('phase'), str):
            return True
        if isinstance(cond.get('not'), dict) and walk(cond['not']):
            return True
        return any(walk(sub) for sub in cond.get('all-of') or ())
    return any(walk(c) for c in rule.get('if') or ())


def _phases_of(rule: dict, phases: list) -> list:
    """The phases a rule's `if` speaks for.

    `{"phase": "x"}` asks for that one; `{"not": {"phase": "x"}}` asks
    for every other; `all-of` is both at once. A rule with no phase
    condition is asked in every phase, so a flag it waits for can be set
    in any of them before it is retried.
    """
    wanted: set = set()
    banned: set = set()

    def walk(cond, negated=False):
        if not isinstance(cond, dict):
            return
        name = cond.get('phase')
        if isinstance(name, str):
            (banned if negated else wanted).add(name)
        inner = cond.get('not')
        if isinstance(inner, dict):
            walk(inner, not negated)
        for sub in cond.get('all-of') or ():
            walk(sub, negated)

    for cond in rule.get('if') or ():
        walk(cond)
    if not wanted and not banned:
        return list(phases)
    return [p for p in phases if (not wanted or p in wanted) and p not in banned]


def playthrough_plan(pack) -> dict:
    """The walk, read off the pack: phases, and the stops each one owes.

    `{world, phases: [{name, rules, stops}], rules, unresolved}`.
    `stops` are the people and places to visit, each carrying the rule
    ids that asked for it; `unresolved` are the `comes-near` rules whose
    `who` names nothing the pack declares - a pack author's typo, told
    to them here rather than as a rule that never fires.

    The phases are the pack's own, in the order it wrote them, when it
    declared `"time"` (that block is what makes a phase a place time can
    move to). A pack with no `time` gets one pass: there is nothing to
    turn the watch on, so there is no second phase to walk.
    """
    from . import maplab

    pack = Path(pack)
    w = maplab.load_pack(pack)
    phases = list((w.get('phases') or {}).keys())
    rest = bool((w.get('time') or {}).get('rest') is True)
    if rest:
        passes = phases or [None]
    else:
        passes = phases[:1] or [None]

    geometry = maplab.region_geometry(w)
    speakers = w.get('speakers') or {}
    pois = _pack_pois(w)
    default_region = w.get('_region') or ('town' if 'town' in geometry
                                         else next(iter(geometry), None))

    rules: dict = {}
    for rule in (w.get('rules') or []):
        if not isinstance(rule, dict):
            continue
        when = rule.get('when')
        if not isinstance(when, dict) or 'comes-near' not in when:
            continue
        near = when['comes-near']
        if not isinstance(near, dict):
            continue
        who = near.get('who')
        distance = near.get('distance')
        if not isinstance(who, str):
            continue
        distance = distance if isinstance(distance, int) else 0
        rules[rule.get('id') or who] = {
            'id': rule.get('id') or who,
            'who': who, 'distance': distance,
            'phases': _phases_of(rule, passes),
            # Whether its `if` names a phase at all: a rule scoped to every phase on purpose
            # still drives revisits; a rule with no phase condition does not.
            'phase_scoped': _names_a_phase(rule),
            'conditions': rule.get('if') or [],
            'stop': _resolve_stop(w, geometry, speakers, pois, who, distance,
                                  default_region),
        }

    # One stop per (who, kind) per phase: two rules about the same
    # keeper are one walk, and the walk takes the widest reach either of
    # them declared, so the event the game sends satisfies both.
    plan_phases = []
    for name in passes:
        stops: dict = {}
        wanted = [r for r in rules.values() if name in r['phases']]
        for rule in wanted:
            stop = rule['stop']
            if stop is None:
                continue
            key = (stop['who'], stop['kind'])
            here = stops.get(key)
            if here is None:
                stops[key] = dict(stop, distance=stop['distance'],
                                  rules=[rule['id']])
            else:
                here['distance'] = max(here['distance'], stop['distance'])
                here['rules'].append(rule['id'])
        plan_phases.append({
            'name': name,
            'rules': [r['id'] for r in wanted],
            'stops': [stops[k] for k in sorted(stops)],
        })
    return {
        'world': w.get('name') or pack.name,
        'pack': str(pack),
        # The loaded pack itself, so the driver walks the same geometry
        # the plan was read from instead of reading it twice.
        '_world': w,
        'rest': rest,
        'phases': plan_phases,
        'rules': rules,
        'unresolved': [
            {'id': r['id'], 'who': r['who'], 'distance': r['distance'],
             'why': f'{r["who"]!r} is not a speaker or a labelled place '
                    'this pack declares'}
            for r in rules.values() if r['stop'] is None
        ],
    }


def _resolve_stop(w, geometry, speakers, pois, who, distance, default_region):
    """Where to stand to hear `comes-near` about `who`, or None.

    A speaker is a tile `distance` away (the Talk button fires the event
    with the distance the game measured); a labelled place is the tile
    itself, because standing on it is what fires it.
    """
    spec = speakers.get(who)
    if isinstance(spec, dict) and _is_at(spec.get('at')):
        region = spec.get('region') or default_region
        return {'who': who, 'kind': 'speaker', 'at': list(spec['at']),
                'region': region, 'distance': distance}
    for region, labels in pois.items():
        if who in labels:
            return {'who': who, 'kind': 'place', 'at': list(labels[who]),
                    'region': region, 'distance': distance}
    return None


def _is_at(value) -> bool:
    """True for a `[x, y]` pair of whole numbers."""
    return (isinstance(value, list) and len(value) == 2
            and all(isinstance(v, int) for v in value))


def _walkable(geometry: dict, props, x: int, y: int) -> bool:
    """Can the hero stand on this tile of this region?

    The player's own rule (part 480's `tileOpen`): inside the map, not
    solid in the legend, not under a prop. The validator's fallback
    alphabet is deliberately not applied - a driver that walks the same
    ground the hero does is the whole point, and a second reading of what
    a `#` means would route the walk against walls the hero walks through
    (or the other way round).
    """
    from . import maplab

    rows = geometry.get('map') or []
    if not rows or y < 0 or y >= len(rows):
        return False
    row = rows[y]
    if x < 0 or x >= len(row):
        return False
    if ((geometry.get('legend') or {}).get(row[x]) or {}).get('solid'):
        return False
    return not maplab.prop_blocks(props, x, y)


def walk_path(w: dict, region: str, start, goal, props=None) -> list | None:
    """The steps from `start` to `goal`, as `[(dx, dy), ...]`, or None.

    Breadth-first over the region's own map and legend (props included,
    because a prop the hero cannot walk through is a wall), so the path
    is a real one over the geometry the pack wrote rather than a guess
    at the hero walking in a straight line. None when `goal` cannot be
    reached at all - a wall, a prop, or a region the pack has no map for.
    """
    from . import maplab

    geometry = maplab.region_geometry(w).get(region) or {}
    rows = geometry.get('map') or []
    if not rows:
        return None
    if props is None:
        props = geometry.get('props')
    start_t, goal_t = tuple(start), tuple(goal)
    if start_t == goal_t:
        return []
    if not _walkable(geometry, props, *goal_t):
        return None
    came: dict = {start_t: None}
    queue = deque([start_t])
    while queue:
        x, y = queue.popleft()
        for _, dx, dy in _DIRECTIONS:
            tile = (x + dx, y + dy)
            if tile in came or not _walkable(geometry, props, *tile):
                continue
            came[tile] = (x, y)
            if tile == goal_t:
                queue.clear()
                break
            queue.append(tile)
    if goal_t not in came:
        return None
    steps: list = []
    at = goal_t
    while came[at] is not None:
        prev = came[at]
        steps.append((at[0] - prev[0], at[1] - prev[1]))
        at = prev
    steps.reverse()
    return steps


def _approach_tile(geometry, at, distance, kind='place', props=None):
    """A walkable tile within `distance` of `at`, as close as the map allows.

    For a place this is the tile itself: standing on a labelled place is
    what fires `comes-near`, and the reach it declares is a ceiling the
    contact satisfies whatever it is. For a speaker it is a tile one step
    off, when the map offers one - the Talk button reaches two, and a
    pack whose people are solid is not walked into - and the speaker's own
    tile when the rule's reach is that tight.
    """
    rows = geometry.get('map') or []
    if not rows:
        return None
    if props is None:
        props = geometry.get('props')
    exact = [at[0], at[1]] if _walkable(geometry, props, *at) else None
    if kind == 'place' and exact:
        return exact
    best = None
    for y in range(len(rows)):
        for x in range(len(rows[0])):
            if not _walkable(geometry, props, x, y):
                continue
            if kind != 'place' and [x, y] == exact:
                continue
            d = abs(x - at[0]) + abs(y - at[1])
            if d > distance:
                continue
            if best is None or d < best[0]:
                best = (d, [x, y])
    return best[1] if best else exact


def _key_for(dx: int, dy: int, binds: dict | None = None):
    """The key that steps `(dx, dy)`, or None.

    The player's own keybinds are asked first (`window.VEFR_KEYBINDS`, the
    one table part 076 keeps), so a run against a save whose keys were
    changed walks on those letters; the shipped defaults are the fallback.
    """
    action = next((name for name, kx, ky in _ACTIONS if (kx, ky) == (dx, dy)),
                  None)
    if action and isinstance(binds, dict):
        for key in binds.get(action) or ():
            if isinstance(key, str) and key:
                return key
    for key, kx, ky in _DIRECTIONS:
        if (kx, ky) == (dx, dy):
            return key
    return None


def _rest_key(binds: dict | None = None):
    """The key Rest answers to, as the player's own table says it."""
    if isinstance(binds, dict):
        for key in binds.get('rest') or ():
            if isinstance(key, str) and key:
                return key
    return 'r'


def _read(page) -> dict:
    """What the game is doing right now (never raises on a dead page)."""
    try:
        return page.evaluate(_READ_PLAY_JS) or {}
    except Exception:  # noqa: BLE001 - a page mid-reload reads as nothing
        return {}


def _dismiss(page) -> None:
    """Put away the speaker box and the menu, the way a player does."""
    try:
        page.evaluate(_DISMISS_JS)
    except Exception:  # noqa: BLE001 - a box that is not there is closed
        pass


def _settle(page, ms: int = _SETTLE_MS) -> dict:
    """Wait - bounded - for the hero to stop moving, and read the page.

    The hero's published tile is the thing to poll: it is written on
    arrival and after every step, so a stable tile is a turn that has
    finished. Nothing here sleeps a fixed time and hopes.
    """
    deadline = ms
    step = 60
    last = _read(page)
    while deadline > 0:
        page.wait_for_timeout(step)
        deadline -= step
        now = _read(page)
        if now.get('hero') == last.get('hero'):
            return now
        last = now
    return last


def _press(page, key: str) -> None:
    """One key press, then put away anything it opened."""
    page.keyboard.press(key)
    _settle(page)
    _dismiss(page)


#: A phase's stops are walked again while new rules keep firing (a rule may need what a later
#: stop hands over: the Mending Shift's bench wants the fid the Warden gives), up to this many
#: rounds, so visit order stops mattering without an endless walk.
PLAYTHROUGH_ROUNDS = 3


def playthrough(html=None, pack=None, out=None, json_out=False,
                viewport=None, strict=False) -> int:
    """Play a pack the way a person does, and report what it saw.

    Walks, talks and rests through the pack's own phases, taking the
    plan from the pack rather than from a script: every phase it
    declares, and for each phase the stops the rules that name that
    phase in `comes-near`. Reads the engine's own marks afterwards
    (`window.VEFR_RULES_STATE.fired`, the why-log `probe` reads), writes
    one screenshot per phase into `out`, and never edits the pack.

    Exit `0` when every phase was reached and every rule a reached phase
    asked for either fired or was held back by its own conditions (a story
    has exclusive outcomes: one run cannot fire all three endings), `1`
    when a phase was unreachable or a rule with no conditions stayed silent
    (its trigger never happened), and `2` when the run could not start at
    all. `strict=True` also fails on condition-held rules.
    """
    if pack is None:
        print('vefr playthrough needs --pack: the plan comes from the '
              'pack, not from a script', file=sys.stderr)
        return 2
    try:
        plan = playthrough_plan(pack)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    out = Path(out or 'playthrough')
    out.mkdir(parents=True, exist_ok=True)
    run = {'phases': [], 'notes': []}

    with _player_file(html, pack) as player, \
            _session(player, 300, size=viewport) as page:
        if page is None:
            return 2
        if not _begin(page):
            run['notes'].append('the game did not open its play pane; '
                                'nothing was played')
            report = playthrough_report(plan, run)
            _print_playthrough(report, json_out)
            return 2

        for index, phase in enumerate(plan['phases']):
            name = phase['name']
            reached = _reach_phase(page, name, plan)
            entry = {'name': name, 'reached': reached, 'notes': [],
                     'stops': []}
            if reached:
                seen = len(_read(page).get('fired') or [])
                for round_no in range(PLAYTHROUGH_ROUNDS):
                    for stop in phase['stops']:
                        visit = _visit(page, plan, stop)
                        if round_no == 0:
                            entry['stops'].append(visit)
                    fired_now = set(_read(page).get('fired') or [])
                    now = len(fired_now)
                    # Only rules scoped to THIS phase drive another round: a rule with no
                    # phase condition may fire in any phase, and is not this phase's to chase.
                    waiting = [rid for rid, rule in plan['rules'].items()
                               if name in rule['phases']
                               and rule.get('phase_scoped',
                                            len(rule['phases']) < len(plan['phases']))
                               and rid not in fired_now]
                    if now == seen or not waiting:
                        break       # nothing new fired, or nothing of this phase is left to fire
                    seen = now
                    if round_no + 1 < PLAYTHROUGH_ROUNDS:
                        entry['notes'].append(
                            f'round {round_no + 2}: walked the stops again, '
                            'because the last round fired something new')
                entry['screenshot'] = str(
                    out / f'{index:02d}-{_slug(name or "pass")}.png')
                page.screenshot(path=entry['screenshot'])
                if plan['rest'] and name is not None:
                    _press_rest(page)
            else:
                entry['screenshot'] = None
                entry['notes'].append(
                    f'phase {name!r} was never reached: the watch stood at '
                    f'{_standing(page)!r} every time it was asked')
            run['phases'].append(entry)

        run['why'] = _read(page).get('why') or []
        run['fired'] = _read(page).get('fired') or []

    report = playthrough_report(plan, run, strict=strict)
    _print_playthrough(report, json_out)
    return 0 if report['ok'] else 1


def _begin(page) -> bool:
    """Press Begin, take the first-run setup if it asks, and wait for play.

    A pack's phase is readable behind the title screen, so "the phase is
    there" is not "the game is playing": the visible start button is
    pressed first, exactly as a player would, and the wait is on the play
    pane itself rather than on any one pack's phase.
    """
    try:
        enter = page.locator('#ts-enter')
        if enter.count() and enter.is_visible():
            enter.click()
    except Exception:  # noqa: BLE001 - no title screen to press is fine
        pass
    try:
        page.wait_for_function(_PLAYING_JS, timeout=_TURN_MS)
        config = page.locator('#config')
        if config.count() and config.is_visible():
            # The first run asks which model to use before it plays. A
            # playthrough talks to nobody, so it takes the offline
            # button the player would.
            page.click('#cfg-offline')
            page.wait_for_function(_PLAYING_JS, timeout=_TURN_MS)
    except Exception:  # noqa: BLE001 - the play pane never came up
        return False
    _dismiss(page)
    return True


_HERO_JS = '() => !!window.VEFR_HERO_AT'


def _hero(page):
    """Where the hero is, or None when the page has not said.

    A town publishes its tile as it boots, which is after the play pane
    appears, so the first read of a run can legitimately find nothing
    there; one bounded wait for it settles that. None for good means a
    pack playing a surface with no map - nothing to walk, said plainly
    rather than guessed at.
    """
    where = _read(page).get('hero')
    if where is None:
        try:
            page.wait_for_function(_HERO_JS, timeout=_TURN_MS)
            where = _read(page).get('hero')
        except Exception:  # noqa: BLE001 - no map here to wait for
            return None
    return where or None


def _standing(page):
    """The phase the game is standing at right now, or None."""
    return _read(page).get('phase')


def _press_rest(page) -> bool:
    """One press of Rest: the button the pack drew, else its own key.

    The button is `#rest` (it carries `data-rest`), and its key is R; a
    pack that declared `"rest": true` has both, and a pack that did not
    has neither, so the driver never presses anything a pack never
    offered.
    """
    before = _standing(page)
    try:
        pressed = False
        for selector in ('#rest', '[data-rest]'):
            button = page.locator(selector)
            if button.count() and button.is_visible():
                button.click()
                pressed = True
                break
        if not pressed:
            page.keyboard.press(_rest_key(_read(page).get('keys')))
    except Exception:  # noqa: BLE001 - a refused press reads as no turn
        return False
    _settle(page)
    _dismiss(page)
    return _standing(page) != before


def _reach_phase(page, name, plan) -> bool:
    """Stand the watch in `name`, resting as many times as it takes.

    One press turns the watch on by exactly one phase, so the walk from
    wherever the save left off to the phase this pass is about is one
    press per step, bounded by the number of phases the pack declares -
    a watch that will not move is a phase this run did not reach, not a
    loop.
    """
    if name is None or not plan['rest']:
        return True
    for _ in range(len(plan['phases']) + 1):
        if _standing(page) == name:
            return True
        if not _press_rest(page):
            break
    return _standing(page) == name


def _visit(page, plan, stop) -> dict:
    """Walk to one stop and do what the game expects there.

    A place is fired by standing on it, so the walk itself is the visit; a
    speaker is fired by the Talk button, so the walk is followed by one
    press of it and the box it opens is put away again. The path is
    recomputed from the hero's published tile after every step, so a step
    the map refused is a step the driver sees and routes around.
    """
    from . import maplab

    w = plan['_world']
    region = stop['region']
    geometry = maplab.region_geometry(w).get(region) or {}
    where = _hero(page) or {}
    if where.get('region') and where['region'] != region:
        return {**stop, 'walked': False,
                'note': f'the hero is in {where["region"]}, and '
                        f'{stop["who"]} is in {region}'}
    goal = _approach_tile(geometry, stop['at'], stop['distance'], stop['kind'])
    if goal is None:
        return {**stop, 'walked': False,
                'note': f'no tile within {stop["distance"]} of '
                        f'{stop["at"]} in {region} is walkable'}
    outcome = _walk_to(page, w, region, where, goal)
    if isinstance(outcome, str):
        return {**stop, 'walked': False, 'note': outcome}
    if stop['kind'] == 'place' and [where.get('x'), where.get('y')] == goal:
        # Already standing on it. The contact is the step ONTO a place, so
        # a hero who started here has to step off and back on - which is
        # what a player does when a place will not speak to them.
        off = _step_off(page, w, region, goal)
        if off is not None:
            outcome = _walk_to(page, w, region,
                               {'x': off[0], 'y': off[1]}, goal)
            if isinstance(outcome, str):
                return {**stop, 'walked': False, 'note': outcome}
    if stop['kind'] == 'speaker':
        try:
            page.click('#talk')
            _settle(page)
        except Exception:  # noqa: BLE001 - a refused talk reads as a miss
            return {**stop, 'walked': outcome, 'note': 'the Talk button '
                    'was not there to press'}
        _dismiss(page)
    return {**stop, 'walked': outcome, 'note': ''}


def _step_off(page, w, region, goal):
    """One step off a tile the hero is already on, and the tile reached.

    None when every tile around it is a wall - a hero boxed in on a place
    cannot circle it, and the report says the rule stayed silent rather
    than pretending the walk was enough.
    """
    from . import maplab

    geometry = maplab.region_geometry(w).get(region) or {}
    binds = _read(page).get('keys')
    for _, dx, dy in _DIRECTIONS:
        tile = [goal[0] + dx, goal[1] + dy]
        key = _key_for(dx, dy, binds)
        if key is None or not _walkable(geometry, geometry.get('props'), *tile):
            continue
        _press(page, key)
        here = _read(page).get('hero') or {}
        if (here.get('x'), here.get('y')) == tuple(tile):
            return tile
    return None


def _walk_to(page, w, region, where, goal):
    """Press the hero along a real path to `goal`.

    Returns True when the hero stood there, False when a step was refused
    but it was standing there anyway, and a sentence when it never got
    there. The path is replanned from wherever the hero actually is after
    every refused step, up to a bound, so a prop or a monster the pack's
    own geometry does not know about costs a detour and not the walk.
    """
    start = (where.get('x'), where.get('y'))
    if None in start:
        return ('the player published no hero position '
                '(window.VEFR_HERO_AT), so nothing could be walked')
    steps = walk_path(w, region, start, goal)
    if steps is None:
        return (f'no path in {region} from {list(start)} to {list(goal)}')
    tries = 0
    while steps:
        if tries > len(steps) * 4 + 8:
            return f'the hero never reached {list(goal)} in {region}'
        dx, dy = steps.pop(0)
        seen = _read(page)
        key = _key_for(dx, dy, seen.get('keys'))
        if key is None:
            return f'no key walks {dx},{dy}'
        before = seen.get('hero')
        _press(page, key)
        now = _read(page).get('hero')
        tries += 1
        if now == before:
            # A refused step: re-plan from here rather than pressing on
            # into the wall the same way.
            here = ((now or {}).get('x'), (now or {}).get('y'))
            if None in here:
                return 'the player stopped publishing the hero position'
            steps = walk_path(w, region, here, goal) or []
    here = _read(page).get('hero') or {}
    return (here.get('x'), here.get('y')) == tuple(goal)


def playthrough_report(plan: dict, run: dict, strict: bool = False) -> dict:
    """The playthrough report, from the plan and what the run saw.

    `{world, phases, fired, never_fired, unresolved, notes, ok}`. `fired`
    is the engine's own marks, in the why-log's own words where the log
    has them; `never_fired` is every rule a reached phase named in
    `comes-near` that stayed silent - with the condition that held it
    back when the why-log says which one, and the pack's own `if` when
    the log is silent, so a reader is never left with a bare id.
    """
    reached = {p['name'] for p in run.get('phases', []) if p.get('reached')}
    # The engine's marks are one key per rule, so they are already unique;
    # de-duplicated here because a rule that fired three times over a run
    # is still one rule that fired, and a report that says otherwise is
    # counting turns, not rules.
    fired = list(dict.fromkeys(run.get('fired') or []))
    why = {}
    for entry in run.get('why') or []:
        if isinstance(entry, dict) and entry.get('id'):
            why[entry['id']] = entry.get('why')

    never = []
    for rid, rule in plan['rules'].items():
        if rid in fired:
            continue
        if not any(name in reached for name in rule['phases']):
            continue    # its phase was never reached: not this run's fault
        never.append({
            'id': rid, 'who': rule['who'], 'distance': rule['distance'],
            'phases': list(rule['phases']),
            # The why-log's sentence when it has one; else the pack's own
            # conditions, said as the thing to go and check.
            'held_by': why.get(rid),
            'conditions': rule['conditions'],
        })

    unreachable = [p['name'] for p in run.get('phases', [])
                   if not p.get('reached')]
    # A silent rule with its own `if` was held back by the story (an exclusive ending, an item
    # not carried): reported, not a failure unless `strict`. A silent rule with no conditions
    # means its trigger never happened, which is the walk's failure.
    # ...and held back only if its stop was really walked: a rule whose trigger never happened is
    # missed whatever its conditions say.
    walked = {stop.get('who') for p in run.get('phases', []) if p.get('reached')
              for stop in p.get('stops', []) if stop.get('walked')}
    missed = [n for n in never if not n['conditions'] or n['who'] not in walked]
    ok = not unreachable and not plan['unresolved'] and not (never if strict else missed)
    return {
        'world': plan['world'],
        'phases': [{'name': p['name'], 'reached': p.get('reached'),
                    'screenshot': p.get('screenshot'),
                    'stops': p.get('stops', []), 'notes': p.get('notes', [])}
                   for p in run.get('phases', [])],
        'fired': [{'id': rid, 'why': why.get(rid)} for rid in fired],
        'never_fired': never,
        'missed': [n['id'] for n in missed],
        'strict': strict,
        'unresolved': plan['unresolved'],
        'unreachable': unreachable,
        'notes': run.get('notes', []),
        'ok': ok,
    }


def _conditions_sentence(conditions) -> str:
    """The pack's own `if` conditions, in one clause a reader can check."""
    if not conditions:
        return ''
    return ', '.join(json.dumps(c) for c in conditions)


def _print_playthrough(report: dict, json_out: bool) -> None:
    """The report as JSON, or as the sentences a person reads."""
    if json_out:
        print(json.dumps(report))
        return
    phases = report['phases']
    reached = [p['name'] for p in phases if p.get('reached')]
    print(f"playthrough: {report['world']} - "
          f"{len(reached)} of {len(phases)} phase(s) reached")
    for phase in phases:
        mark = 'ok' if phase.get('reached') else 'UNREACHED'
        name = phase['name'] or '(one pass)'
        print(f"  phase {name}: {mark}")
        if phase.get('screenshot'):
            print(f'    screenshot: {phase["screenshot"]}')
        for stop in phase.get('stops', []):
            said = 'walked' if stop.get('walked') else 'not walked'
            line = f"    {stop['who']} ({stop['kind']}): {said}"
            if stop.get('note'):
                line += f" - {stop['note']}"
            print(line)
        for note in phase.get('notes', []):
            print(f'    {note}')
    if report['fired']:
        print(f"rules fired ({len(report['fired'])}):")
        for entry in report['fired']:
            print(f"  {entry['id']}: {entry['why'] or '(no why-log sentence)'}")
    else:
        print('rules fired (0)')
    if report['never_fired']:
        held_n = len(report['never_fired']) - len(report.get('missed') or [])
        print(f"never fired ({len(report['never_fired'])}: {held_n} held back by their own "
              f"conditions, {len(report.get('missed') or [])} whose trigger never happened):")
        for entry in report['never_fired']:
            held = entry.get('held_by') or (
                f'the pack asks for {_conditions_sentence(entry["conditions"])}'
                if entry['conditions'] else 'nothing in the why-log says')
            if entry['id'] not in (report.get('missed') or []):
                print(f"  {entry['id']}: comes-near {entry['who']} within "
                      f"{entry['distance']} - held back by {held}")
            else:
                print(f"  {entry['id']}: MISSED - comes-near {entry['who']} within "
                      f"{entry['distance']} never happened")
    for entry in report['unresolved']:
        print(f"unresolved: rule {entry['id']} names {entry['why']}")
    for note in report['notes']:
        print(note)
    print('playthrough ok' if report['ok'] else 'playthrough failed')


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
