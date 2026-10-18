"""The playthrough driver, against a scripted game instead of a browser.

`vefr playthrough` opens Chromium; this file drives the same driver
against a stand-in page that answers the two published reads the driver
makes (`window.VEFR_HERO_AT` and the engine's fired marks) and turns
key presses into a walk over the pack's own map. What is checked here is
the driver's own decisions - which keys it presses, when it rests, what
it reports - with no browser in the way, so the shape of a play-through
is pinned even where Chromium is not installed.

The stand-in speaks the player's own rules for what it is given: a step
onto a labelled place fires `comes-near` with distance 0, the Talk
button fires it for the nearest speaker with the distance the game
measured, and Rest turns the watch on by exactly one phase. The
conditions it reads are `phase` and `flag`, which is what the fixture
rules here use.
"""

import contextlib
import json
import sys
from pathlib import Path

import pytest

from vefr import devtools, maplab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_mending_pack  # noqa: E402
import make_time_pack  # noqa: E402

KEYS = {'ArrowUp': (0, -1), 'ArrowDown': (0, 1),
        'ArrowLeft': (-1, 0), 'ArrowRight': (1, 0)}


class ScriptedGame:
    """A tiny stand-in for the woven player: the map, the phases, the
    rules it fires, and nothing else."""

    def __init__(self, pack):
        self.w = maplab.load_pack(Path(pack))
        self.region = next(iter(maplab.region_geometry(self.w)))
        geo = maplab.region_geometry(self.w)[self.region]
        self.rows, self.legend = geo['map'], geo.get('legend') or {}
        self.pois = (self.w.get('town') or {}).get('pois') or {}
        self.speakers = self.w.get('speakers') or {}
        self.phases = list(self.w.get('phases') or {})
        self.rest = bool((self.w.get('time') or {}).get('rest') is True)
        self.hero = list((self.w.get('town') or {}).get('hero_start') or [1, 1])
        self.phase = self.phases[0] if self.phases else None
        self.fired, self.why, self.box = [], [], False
        self.keys = []
        self.tiles = [tuple(self.hero)]
        self.rules = [r for r in (self.w.get('rules') or [])
                      if 'comes-near' in (r.get('when') or {})]

    # -- the game's own reading of a `comes-near` -----------------------
    def _holds(self, rule) -> bool:
        for cond in rule.get('if') or ():
            if 'phase' in cond and cond['phase'] != self.phase:
                return False
            if 'flag' in cond:
                return False   # nothing in this run ever sets a flag
        return True

    def _fire(self, who, distance) -> None:
        for rule in self.rules:
            near = rule['when']['comes-near']
            if near.get('who') != who or distance > near.get('distance', 0):
                continue
            if not self._holds(rule):
                continue
            self.fired.append(rule['id'])
            self.why.append({'id': rule['id'],
                             'why': f"rule '{rule['id']}' fired: the hero "
                                    f"came near {who}"})

    # -- what a key press does ------------------------------------------
    def step(self, key) -> None:
        if key in KEYS:
            self.keys.append(key)
            dx, dy = KEYS[key]
            at = [self.hero[0] + dx, self.hero[1] + dy]
            if maplab._map_tile_walkable(self.rows, self.legend, *at) is not True:
                return                      # a wall: the hero stays put
            self.hero = at
            self.tiles.append(tuple(at))
            label = self.pois.get(f'{at[0]},{at[1]}')
            if label:
                self._fire(label, 0)        # standing on a place is the contact
        elif key == 'r':
            self.keys.append(key)
            if self.rest and self.phases:
                at = self.phases.index(self.phase)
                self.phase = self.phases[(at + 1) % len(self.phases)]

    def talk(self) -> None:
        self.keys.append('#talk')
        best = None
        for key, spec in self.speakers.items():
            at = spec.get('at')
            if not at:
                continue
            d = abs(at[0] - self.hero[0]) + abs(at[1] - self.hero[1])
            if best is None or d < best[1]:
                best = (key, d)
        if best:
            self._fire(best[0], best[1])
            if best[1] <= 2:
                self.box = True

    def read(self) -> dict:
        return {'hero': {'x': self.hero[0], 'y': self.hero[1],
                         'region': self.region},
                'phase': self.phase,
                'fired': list(self.fired),
                'why': list(self.why)}

    def where(self) -> tuple:
        """Every tile the hero stood on, walking order."""
        return tuple(self.tiles)


class _Locator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector

    def count(self):
        return 1 if self.selector in self.page.there else 0

    def is_visible(self):
        return self.selector in self.page.there and not self.page.hidden


class _Keyboard:
    def __init__(self, page):
        self.page = page

    def press(self, key):
        self.page.game.step(key)


class ScriptedPage:
    """Just enough of a Playwright page for the driver: the two published
    reads, key presses, the three buttons the driver presses, and a
    screenshot that writes a byte."""

    def __init__(self, game):
        self.game = game
        self.there = {'#ts-enter', '#config', '#cfg-offline',
                      '#talk', '#npc-close'}
        self.hidden = set()
        self.keyboard = _Keyboard(self)
        self.shots = []

    def locator(self, selector):
        return _Locator(self, selector)

    def click(self, selector):
        assert selector in self.there, f'no {selector} on the page'
        if selector == '#cfg-offline':
            self.there.discard('#cfg-offline')
        elif selector == '#talk':
            self.game.talk()
        elif selector == '#npc-close':
            self.game.box = False

    def evaluate(self, script, arg=None):
        if script is devtools._READ_PLAY_JS:
            return self.game.read()
        if script is devtools._DISMISS_JS:
            closed = 1 if self.game.box else 0
            self.game.box = False
            return closed
        raise AssertionError(f'the driver evaluated something unexpected: '
                             f'{script[:60]}')

    def wait_for_function(self, expression, arg=None, timeout=None):
        return True

    def wait_for_timeout(self, ms):
        return None

    def screenshot(self, path=None):
        self.shots.append(path)
        if path:
            Path(path).write_bytes(b'\x89PNG not really, but a byte written')
        return b''


@pytest.fixture
def play(monkeypatch, capsys):
    """Run `vefr playthrough` against a scripted game; give back its code,
    its JSON report and the game it played."""
    def _play(pack, out):
        game = ScriptedGame(pack)
        page = ScriptedPage(game)

        @contextlib.contextmanager
        def _session(path, wait_ms, plant=None, size=None, seed=None):
            yield page

        monkeypatch.setattr(devtools, '_session', _session)
        rc = devtools.playthrough(pack=pack, out=out, json_out=True)
        printed = capsys.readouterr().out.strip().splitlines()
        return rc, json.loads(printed[-1]), game, page
    return _play


def _time_pack(tmp_path, name='time-test'):
    return make_time_pack.build(tmp_path, name=name)


def _mending_pack(tmp_path, rules):
    pack = make_mending_pack.build(tmp_path)
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world['rules'] = world['rules'] + rules
    (pack / 'world.json').write_text(json.dumps(world), encoding='utf-8')
    return pack


def test_rest_walks_the_watch_through_every_phase(play, tmp_path):
    """One Rest press between passes, never two: the driver stands each
    phase in turn and takes exactly the number of steps between them."""
    pack = _time_pack(tmp_path)
    rc, report, game, _page = play(pack, tmp_path / 'shots')

    assert rc == 0, report
    assert [p['name'] for p in report['phases']] == \
        ['whispers', 'lowwater', 'highwater']
    assert all(p['reached'] for p in report['phases']), report
    assert game.keys.count('r') == 3, game.keys
    assert len(game.where()) == 2, game.where()   # to the watcher, and back


def test_the_watch_only_answers_at_highwater(play, tmp_path):
    """The rule that reads the standing phase is a stop of highwater, so
    that is the one pass the driver walks and talks in - and it fires
    there, once."""
    pack = _time_pack(tmp_path)
    rc, report, game, _page = play(pack, tmp_path / 'shots')

    assert rc == 0, report
    assert [f['id'] for f in report['fired']] == ['boats-may-come-in']
    assert game.keys.count('#talk') == 1, game.keys
    # Two rests to get there, one after it: a press per phase boundary.
    assert game.keys == ['r', 'r', 'ArrowRight', '#talk', 'r'], game.keys
    assert game.where()[-1] == (2, 1), game.where()   # one tile off the watcher


def test_a_place_is_fired_by_the_walk_itself(play, tmp_path):
    """Standing on a labelled place is the contact: no button is pressed
    for it, and the rule fires off the step."""
    pack = _mending_pack(tmp_path, [
        {'id': 'stone-warms',
         'when': {'comes-near': {'who': 'the stone', 'distance': 0}},
         'then': [{'say': 'The stone is warm.'}]},
        {'id': 'keeper-nods',
         'when': {'comes-near': {'who': 'keeper', 'distance': 2}},
         'then': [{'say': 'The Keeper nods.'}]}])
    rc, report, game, _page = play(pack, tmp_path / 'shots')

    assert rc == 0, report
    fired = {f['id'] for f in report['fired']}
    assert fired == {'stone-warms', 'keeper-nods'}, report
    assert game.keys.count('#talk') == 1, game.keys      # once, for the keeper
    assert (7, 3) in game.where(), game.where()          # stood on the stone


def test_a_rule_whose_condition_never_holds_is_reported(play, tmp_path):
    """The run is a pass, not a failure of the walk: every phase is still
    reached, and the silent rule is named with what held it back."""
    pack = _time_pack(tmp_path)
    world = json.loads((pack / 'world.json').read_text(encoding='utf-8'))
    world['rules'].append({
        'id': 'the-watcher-agrees',
        'when': {'comes-near': {'who': 'watcher', 'distance': 2}},
        'if': [{'flag': 'asked-twice', 'is': True}],
        'then': [{'say': 'The Watcher agrees with that.'}]})
    (pack / 'world.json').write_text(json.dumps(world), encoding='utf-8')

    rc, report, _game, _page = play(pack, tmp_path / 'shots')
    assert rc == 1, report
    assert [n['id'] for n in report['never_fired']] == ['the-watcher-agrees']
    assert report['never_fired'][0]['conditions'] == \
        [{'flag': 'asked-twice', 'is': True}]
    assert all(p['reached'] for p in report['phases']), report


def test_a_place_the_hero_starts_on_is_stepped_onto(play, tmp_path):
    """Standing on a place fires nothing: the contact is the step ONTO
    the tile. A hero who opens the game on one steps off and back on,
    which is what a player does when a place will not speak to them."""
    pack = make_time_pack.build(tmp_path, name='here-test', time_block=None)
    world = json.loads((pack / 'world.json').read_text(encoding='utf-8'))
    world['town']['pois'] = {'1,1': 'the mooring post'}
    world['rules'] = [{
        'id': 'the-post-calls',
        'when': {'comes-near': {'who': 'the mooring post', 'distance': 0}},
        'then': [{'say': 'The post says hello.'}]}]
    (pack / 'world.json').write_text(json.dumps(world), encoding='utf-8')

    rc, report, game, _page = play(pack, tmp_path / 'shots')
    assert rc == 0, report
    assert [f['id'] for f in report['fired']] == ['the-post-calls']
    # Off the start tile and back onto it.
    assert game.where()[-1] == (1, 1) and len(game.where()) == 3, game.where()


def test_a_rule_naming_nothing_the_pack_declares_is_said_so(play, tmp_path):
    pack = _time_pack(tmp_path)
    world = json.loads((pack / 'world.json').read_text(encoding='utf-8'))
    world['rules'].append({
        'id': 'the-mayor-agrees',
        'when': {'comes-near': {'who': 'the mayor', 'distance': 2}},
        'then': [{'say': 'Nobody answers.'}]})
    (pack / 'world.json').write_text(json.dumps(world), encoding='utf-8')

    rc, report, _game, _page = play(pack, tmp_path / 'shots')
    assert rc == 1, report
    assert [u['id'] for u in report['unresolved']] == ['the-mayor-agrees']


def test_the_report_names_the_fired_rules_in_the_why_logs_words(play, tmp_path):
    pack = _time_pack(tmp_path)
    _rc, report, _game, _page = play(pack, tmp_path / 'shots')
    fired = {f['id']: f['why'] for f in report['fired']}
    assert 'came near watcher' in fired['boats-may-come-in']
    # A rule asked in every phase fires once per pass, and is reported
    # once: the report counts rules, not turns.
    assert len(report['fired']) == len(set(f['id'] for f in report['fired']))


def test_one_screenshot_is_written_per_phase(play, tmp_path):
    pack = _time_pack(tmp_path)
    out = tmp_path / 'shots'
    _rc, report, _game, page = play(pack, out)
    shots = [Path(p['screenshot']) for p in report['phases']]
    assert len(shots) == 3
    assert [s.name for s in shots] == \
        ['00-whispers.png', '01-lowwater.png', '02-highwater.png']
    assert all(s.exists() and s.stat().st_size > 0 for s in shots)
    assert page.shots == [str(s) for s in shots]


def test_the_pack_is_never_written_to(play, tmp_path):
    pack = _time_pack(tmp_path)
    before = {p: p.read_bytes() for p in sorted(pack.rglob('*')) if p.is_file()}
    play(pack, tmp_path / 'shots')
    after = {p: p.read_bytes() for p in sorted(pack.rglob('*')) if p.is_file()}
    assert after == before