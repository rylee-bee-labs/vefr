"""The norns, the squirrel, and the tree - the engine's three shapes.

Three CLI entry points:

    vefr      - the front door: one verb per job, wired to the same
                functions ratatoskr and norns call (doctor, check,
                chat, map, delve, weave, spark, test, ferry, handbok,
                skipa). `vefr norns ARGS...` and `vefr ratatoskr
                ARGS...` hand the tail to the old CLIs verbatim.

    ratatoskr - the squirrel. Ferries messages between the dev box,
                the deploy host, Gitea, the NAS, and the World Tree
                bundle. Subcommands: skipa, test, weave, ferry
                (deploy / carry / fetch).

    norns     - the weavers. Craft commands for shaping the world:
                chat, validate, build-map, delve, verify.

Run from any checkout; git decides which. In the container, the
same commands serve against the deployed world (deploy and
backup need a git checkout, so they stay on the dev side).

Your own game's name never appears here - that's the point. Whatever
story you point the engine at (your pack, someone else's, or none)
sits in worlds/, and these two commands stay the same no matter
whose story they're serving.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .maplab import (SKIN_PICTURE_KEYS, item_changes_of, item_grants_of,
                     item_rarity_of, item_roll_of,
                     item_slot_and_mods, item_traits_of, load_pack, prop_blocks,
                     validate)
from .paths import world_name
# The loader's tile convention (ordered variants) is the single source
# of the try-order the player bakes, so a pack's tiles/ is read the
# same way whoever resolves it.
from .world import _discover_tiles, tile_grid


# ---------------------------------------------------------------- envelope
# The machine face of every command that takes --json: the same stable
# envelope the Worlds CLI prints ({ok, status, changed, warnings, actions,
# data}) and the same exit codes, so scripts, agents and the studio's own
# residents read VEFR the way they read the rest of the estate.
EXIT_OK = 0           # did what it says
EXIT_ERROR = 1        # refused, invalid, failed
EXIT_USAGE = 2        # bad arguments (argparse's own code)
EXIT_UNAVAILABLE = 3  # a backend (Spark, the live stack) cannot be reached
EXIT_GATED = 4        # nothing changed; a person must approve (not an error)


def envelope(ok: bool, status: str, data=None, *, changed: bool = False,
             warnings=(), actions=()) -> dict:
    return {'ok': ok, 'status': status, 'changed': changed,
            'warnings': list(warnings), 'actions': list(actions), 'data': data}


def emit_json(env: dict) -> None:
    print(json.dumps(env, indent=2, default=str))


def rows_json(rows, keys) -> list:
    """Table rows -> list of dicts (the --json form of a status table)."""
    return [dict(zip(keys, r)) for r in rows]

GITEA_BASE = os.environ.get('VEFR_GITEA_URL', 'http://localhost:3000')

DEFAULT_URL = os.environ.get('VEFR_LIVE_URL', 'http://127.0.0.1:8820')
DEFAULT_DEPLOY_HOST = os.environ.get(
    'VEFR_DEPLOY_HOST',
    os.environ.get('VEFR_DEFAULT_DEPLOY_HOST', ''),
)
DEFAULT_BACKUP_LOCATION = os.environ.get(
    'VEFR_DEFAULT_BACKUP_LOCATION', '')
DEFAULT_BACKUP_HOST, _, NAS_DIR = DEFAULT_BACKUP_LOCATION.partition(':')

# Engine-shipped pack names: when one of these sits in the deploy
# host's rw bind (~/vefr-worlds/), it shadows the freshly built
# template and the running pack goes stale on every engine update
# (the 2026-09-01 deploy-day find).
ENGINE_PACKS = ('sample-world', 'lore')


def _deploy_toml(root: Path | None = None) -> dict:
    """deploy.toml - the per-host twin of deploy.toml.example - read
    with stdlib tomllib. The wrapper consumes it so the file is
    load-bearing config instead of documentation: host and image
    resolve from here whenever --flags and env are silent, and
    norns doctor falls back to its url for the live check. A
    missing or malformed file is an empty dict - a bad toml must
    never take the deploy path down."""
    base = root or repo_root() or Path.cwd()
    p = base / 'deploy.toml'
    if not p.exists():
        return {}
    try:
        import tomllib
        return tomllib.loads(p.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001 - broken config, not a broken deploy
        return {}
if not DEFAULT_BACKUP_LOCATION:
    # No silent defaults. Carry refuses to ssh an empty host and the
    # operator must declare VEFR_DEFAULT_BACKUP_LOCATION or pass
    # --nas-host + --backup-path. The deploy wrapper has the same
    # fail-closed shape (see cmd_deploy near line 747).
    DEFAULT_BACKUP_HOST, NAS_DIR = '', ''
BUNDLE_KEEP = 2
DEPLOY_EXCLUDES = ('.venv', '__pycache__', '.pytest_cache', '*.egg-info', '.git')


def repo_root():
    """The checkout you run from - None when installed (container)."""
    try:
        top = subprocess.run(('git', 'rev-parse', '--show-toplevel'),
                             capture_output=True, text=True).stdout.strip()
        if top:
            return Path(top)
    except Exception:  # noqa: BLE001
        pass
    return None


def pack_root() -> Path:
    """Where worlds/ lives: a checkout, or VEFR_HOME in the container."""
    r = repo_root()
    if r and (r / 'worlds').is_dir():
        return r
    from .paths import app_home
    return app_home()


def git_quiet(*args):
    r = repo_root()
    if not r:
        return ''
    return subprocess.run(('git',) + args, capture_output=True, text=True,
                          cwd=str(r)).stdout.strip()


# The userinfo of a URL - `scheme://user:secret@host`. Printing one is
# how a token ends up in a scrollback, a CI log, or a bug report, so
# sh() shows the shape and hides the secret. The command itself is
# untouched: only the echo is redacted.
_URL_USERINFO = re.compile(r'([a-zA-Z][a-zA-Z0-9+.\-]*://)([^/\s@]+)@')


def redact_arg(c) -> str:
    """The argument as it may be printed - a URL's password or token
    becomes `***`. `user:secret@host` keeps the user (who you are),
    `secret@host` (token only) keeps nothing."""
    s = str(c)

    def _swap(m):
        scheme, userinfo = m.group(1), m.group(2)
        user, sep, _secret = userinfo.partition(':')
        if not sep:
            return f'{scheme}***@'
        return f'{scheme}{user}:***@'

    return _URL_USERINFO.sub(_swap, s)


def sh(cmd, **kw):
    print(f'+ {" ".join(redact_arg(c) for c in cmd)}')
    return subprocess.run([str(c) for c in cmd], **kw)


def fetch(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def need_repo() -> Path:
    r = repo_root()
    if not r:
        raise SystemExit('this command needs a git checkout - '
                         'it is not available inside the container')
    return r


# --------------------------------------------------------------- skipa

def q1_sync() -> tuple:
    if not repo_root():
        return 'unavailable', 'no git checkout (container install)'
    branch_line = git_quiet('status', '-sb').splitlines()[0]
    if 'ahead' in branch_line or 'behind' in branch_line:
        return 'OUT-OF-SYNC', branch_line
    local = git_quiet('rev-parse', 'HEAD')[:7]
    remote = git_quiet('ls-remote', 'origin', '-h', 'refs/heads/main')[:7]
    if local != remote:
        return 'OUT-OF-SYNC', f'local {local} != remote {remote}'
    return 'in-sync', f'local == remote @ {local}'


def q2_dirty() -> tuple:
    if not repo_root():
        return 'unavailable', 'no git checkout (container install)'
    status = git_quiet('status', '--porcelain')
    dirty = len(status.splitlines()) if status else 0
    stashes = len(git_quiet('stash', 'list').splitlines())
    if dirty or stashes:
        return 'dirty', f'{dirty} uncommitted file(s), {stashes} stash(es)'
    # The reading row's fonts are tracked since 2026-09-01; an empty
    # web/fonts/ means the woff2 binaries never landed - the panel
    # 404s silently and the packaged file ships without them.
    fonts_dir = repo_root() / 'web' / 'fonts'
    have = len(list(fonts_dir.glob('*.woff2'))) if fonts_dir.is_dir() else 0
    fonts = f'fonts {have}/4' if have < 4 else 'fonts ok'
    return 'clean', f'0 uncommitted, 0 stashes; {fonts}'


def q3_deployment(url: str, deploy_host: str | None = None) -> tuple:
    try:
        h = fetch(f'{url.rstrip("/")}/api/health')
        if not (h.get('ok') and 'purpose' in h):
            return 'degraded', f'unexpected health payload: {h}'
    except Exception as e:  # noqa: BLE001
        return 'down', f'{url}: {e}'
    # The shadow check: an engine-shipped pack in the deploy host's
    # rw bind hides the freshly built template, so the running pack
    # goes stale on every engine update. A green deploy that serves
    # old content is worse than a red one.
    if not deploy_host:
        return 'healthy', 'container up, motto present'
    try:
        out = subprocess.run(
            ('ssh', '-o', 'ConnectTimeout=6', deploy_host,
             'ls ~/vefr-worlds/ 2>/dev/null'),
            capture_output=True, text=True, timeout=15).stdout.split()
    except Exception as e:  # noqa: BLE001
        return 'healthy', f'container up, motto present (shadow check skipped: {e})'
    shadowed = [p for p in out if p in ENGINE_PACKS]
    if shadowed:
        return ('shadowed',
                f'container up, but engine pack(s) {", ".join(shadowed)} in '
                f'~/vefr-worlds/ shadow the template - move them aside and '
                f'restart, or the running pack goes stale')
    return 'healthy', 'container up, motto present, no pack shadows'


def q4_world(url: str, pack: Path) -> tuple:
    errors = validate(load_pack(pack), pack_dir=pack)
    try:
        served = fetch(f'{url.rstrip("/")}/api/world')
        town_keys = ('tile', 'map', 'legend', 'pois', 'watch', 'sanctuary_tiles',
                     'water_by_phase', 'flood_tiles', 'hero_start')
        shim = {
            'phases': served['phases'],
            'speakers': {
                s['key']: {'name': s['name'], 'at': s['at'], 'near': s['near'],
                           'seeds': s.get('seeds', {})}
                for s in served['speakers']
            },
            'voices': {},
            'town': {k: served[k] for k in town_keys if k in served},
        }
        errors += ['live: ' + e for e in validate(shim)]
    except Exception as e:  # noqa: BLE001
        return 'unreachable', f'live check failed: {e}'
    if errors:
        return 'invalid', '; '.join(errors)
    return 'validated', 'pack and live deployment both pass maplab'


def q5_backups(nas_host: str) -> tuple:
    try:
        out = subprocess.run(
            ('ssh', '-o', 'ConnectTimeout=6', nas_host,
             f'ls -t {NAS_DIR}/vefr-*.bundle 2>/dev/null | head -1'),
            capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return 'unverified', f'ssh failed: {e}'
    if not out:
        return 'unverified', f'no bundles on {nas_host}:{NAS_DIR}'
    return 'fresh', f'{Path(out).name} on {nas_host} (newest bundle)'


def q6_vault(bazzite_host: str) -> tuple:
    try:
        out = subprocess.run(
            ('ssh', '-o', 'ConnectTimeout=6', bazzite_host,
             'ls ~/vefr-data/ 2>/dev/null | wc -l'),
            capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return 'unverified', f'ssh failed: {e}'
    n = out.splitlines()[-1] if out else '0'
    return 'persisted', f'~/vefr-data present ({n} entries)'


def q7_next(pack: Path) -> tuple:
    root = pack.parent.parent
    roadmap = root / 'ROADMAP.md'
    if not roadmap.exists():
        return 'unknown', 'no ROADMAP.md in this install'
    text = roadmap.read_text(encoding='utf-8')
    if '## Next' not in text:
        return 'unknown', 'no ## Next section in ROADMAP.md'
    nxt = text.split('## Next')[1].split('## ')[0]
    items = [ln.strip()[6:] for ln in nxt.splitlines() if ln.strip().startswith('- [ ]')]
    short = [i.split(':')[0].strip('**').strip() for i in items]
    return 'open', f'{len(items)} open: {"; ".join(short)}'


def cmd_skipa(args) -> int:
    pack = pack_root() / 'worlds' / world_name()
    url = args.url
    if url == DEFAULT_URL:
        # The silent default is the dev box itself, not the deploy
        # host. deploy.toml's url is the declared live endpoint.
        url = _deploy_toml().get('url') or url
    rows = [
        ('Q1', 'git local + Gitea remote in sync', *q1_sync()),
        ('Q2', 'local files needing push', *q2_dirty()),
        ('Q3', 'deployment healthy (bazzite)',
         *q3_deployment(url, args.deploy_host)),
        ('Q4', 'the world validated (pack + live)', *q4_world(url, pack)),
        ('Q5', 'backups fresh (NAS bundle)', *q5_backups(args.nas_host)),
        ('Q6', 'vault persisted (volume)', *q6_vault(args.deploy_host)),
        ('Q7', 'open items from the ROADMAP', *q7_next(pack)),
    ]
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if getattr(args, 'json', False):
        emit_json(envelope(True, 'answered', {
            'at': now, 'questions': rows_json(rows, ('id', 'question', 'status', 'answer'))}))
        return EXIT_OK
    print(f'ratatoskr skipa -- {now}')
    print()
    print('| Q  | Question | Status | Answer |')
    print('| -- | -------- | ------ | ------ |')
    for q, question, status, answer in rows:
        print(f'| {q} | {question} | {status} | {answer} |')
    print()
    print('the town keeps. <3')
    return 0


def cmd_vefr_skipa(args) -> int:
    """`vefr skipa` - the seven questions, with one stderr note.

    The questions are now part of `vefr doctor` (one check list),
    but skipa stays runnable with exactly its old output. The note
    goes to stderr only, so a script reading stdout sees the same
    bytes it always did.
    """
    print("skipa's seven questions are now part of `vefr doctor` - "
          'running skipa anyway', file=sys.stderr)
    return cmd_skipa(args)


# ------------------------------------------------------------------ map

def cmd_chat(args) -> int:
    from . import chat as chatmod

    name = chatmod.slugify(args.name)
    scaffold = pack_root() / 'worlds' / 'sample-world'
    dest = pack_root() / 'worlds' / name
    return chatmod.run_interview(dest, scaffold)


def cmd_migrate(args) -> int:
    """Migrate a flat-shape world pack to the acts tree.

    A flat pack has its `town`, `speakers`, and `map.md` at the
    top level. The acts shape splits these into per-region
    directories under `acts/<id>/<region>/`. The migrator
    creates the acts tree and rewrites `world.json` to the
    pack-level contract; the flat `town` data moves into
    `acts/<id>/town/` (a `town/contract.json` is written for
    town metadata; `map.md` is the walkable grid; `voices/`
    is the auto-discovered region voices).

    This is the safe path for the author's own canon: the
    migration is a copy, not a destructive move, and the engine
    supports both on-disk shapes indefinitely.
    """
    import json
    import shutil

    pack_name = args.pack
    src = pack_root() / 'worlds' / pack_name
    if not (src / 'world.json').exists():
        print(f'pack not found: {src}')
        return 1
    if (src / 'acts').is_dir():
        print(f'{src} is already in the acts shape - nothing to migrate')
        return 0
    config = json.loads((src / 'world.json').read_text(encoding='utf-8'))
    if 'town' not in config:
        print(f'{src} has no `town` block - is this a flat pack?')
        return 1

    acts_root = src / 'acts' / (args.act_id or 'act-1')
    town_dir = acts_root / 'town'
    town_dir.mkdir(parents=True, exist_ok=True)

    # town contract: every town-metadata field except `map` and
    # `voices` (those move into separate files). The canary shape.
    town_block = config['town']
    town_contract = {k: v for k, v in town_block.items()
                     if k not in ('map',)}
    act_contract = {
        'id': acts_root.name,
        'title': config.get('title', src.name),
        'regions': ['town'],
        'town': town_contract,
        'speakers': config.get('speakers', {}),
        'enemies': config.get('enemies', []),
        'bosses': config.get('bosses', []),
        'transitions': config.get('transitions', []),
    }
    (acts_root / 'world.json').write_text(
        json.dumps(act_contract, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    # map.md: the walkable grid as a plain text file.
    if town_block.get('map'):
        (town_dir / 'map.md').write_text(
            '\n'.join(town_block['map']) + '\n',
            encoding='utf-8',
        )

    # voices/: move any existing pack-level voices into the
    # region's voices dir. The loader discovers them by
    # convention; voice_file paths in the speaker contract
    # still resolve via resolve_voice_file().
    src_voices = src / 'voices'
    if src_voices.is_dir():
        dst_voices = town_dir / 'voices'
        dst_voices.mkdir(parents=True, exist_ok=True)
        for vf in src_voices.glob('*.md'):
            shutil.copy2(vf, dst_voices / vf.name)

    # Rewrite the pack-level world.json: keep metadata + canon,
    # remove town/speakers/map (they're in the act now).
    pack_contract = {
        k: v for k, v in config.items()
        if k not in ('town', 'speakers', 'enemies', 'bosses', 'transitions')
    }
    (src / 'world.json').write_text(
        json.dumps(pack_contract, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    # Validate the migrated pack end-to-end. We pass the absolute
    # pack path so tests (which monkeypatch pack_root) work, and
    # the production path resolves the same way through pack_root.
    from .maplab import load_pack as _load_pack
    from .maplab import validate as _validate
    unified = _load_pack(src)
    errors = _validate(unified, pack_dir=src)
    if errors:
        print(f'migrated but validation flagged {len(errors)} issue(s):')
        for e in errors:
            print(f'  FAIL: {e}')
        return 2
    print(f'migrated {src} to the acts shape - '
          f'{acts_root}/, {town_dir}/, pack-level world.json rewritten.')
    print('validates against the engine contract.')
    return 0


def _import_url(base: str, repo: str) -> str:
    """Accept 'owner/name' or a full https://... URL; return a cloneable URL."""
    if repo.startswith('http://') or repo.startswith('https://') or repo.startswith('git@'):
        return repo
    if '/' not in repo or repo.count('/') != 1:
        raise SystemExit(
            f"repo must be 'owner/name' or a full URL, got: {repo!r}"
        )
    return f'{base.rstrip("/")}/{repo}.git'


def _import_target(args) -> tuple[str, str]:
    """Where the clone lands: 'local' means current checkout, else an ssh host.

    Returns (target_host, worlds_dir) - worlds_dir is the directory on
    the target host that contains the per-pack subdirs. For 'local' we
    resolve to the checkout's worlds/. For an ssh host we look up the
    deploy-host layout by asking the host itself (`ratatoskr ferry deploy` puts
    the engine at ~/vefr/, so the worlds are at ~/vefr/worlds/).
    """
    if args.target == 'local':
        return 'local', str(pack_root() / 'worlds')
    # On a deploy host the engine checkout is ~/vefr/ (where
    # ratatoskr ferry deploy rsyncs to). The worlds live inside that checkout.
    return args.target, '~/vefr/worlds'


def cmd_import(args) -> int:
    """Clone (or pull) a story repo into worlds/<name>/.

    The engine and the story live in two Gitea repos on purpose - the
    engine is public-track MIT (rylee/vefr), the story is your own
    story pack. The world pack directory on disk is the seam; this command
    is how the latest of the story repo reaches that directory.

    By default targets the current checkout (so a dev box can land
    the story before shipping). --target <host> runs the clone over
    ssh on the deploy host - the same box the live game is on - so
    'I edited my story pack, ship it' is one command end-to-end.
    """
    base = args.base.rstrip('/')
    url = _import_url(base, args.repo)
    name = args.name or url.rsplit('/', 1)[-1].removesuffix('.git')
    target_host, worlds_dir = _import_target(args)
    target_path = f'{worlds_dir}/{name}'

    # Only the local target checks for an existing directory: an ssh
    # host may already have a pack under that name and the user wants
    # to overwrite - the ssh command itself does `test -d || clone`
    # and falls back to `git pull --ff-only` when --pull is set.
    if target_host == 'local':
        exists_local = (pack_root() / 'worlds' / name).exists()
        action = 'pull' if exists_local and args.pull else 'clone'
        if exists_local and not args.pull:
            print(
                f"worlds/{name}/ already exists - pass --pull to update, "
                f"or remove the directory first."
            )
            return 1
    else:
        action = 'pull' if args.pull else 'clone'

    plan = (
        f'{action} {url}\n'
        f'  -> {target_host}:{target_path}'
    )
    if args.dry_run:
        print('dry-run: would')
        print(plan)
        return 0
    print(plan)

    if target_host == 'local':
        cmd = (['git', 'pull', '--ff-only'] if action == 'pull'
               else ['git', 'clone', url, str(pack_root() / 'worlds' / name)])
        rc = subprocess.run(cmd, capture_output=True, text=True).returncode
        if rc:
            print(f'git {action} failed (rc={rc})')
            return rc
    else:
        # Three layouts on the deploy host:
        #   (a) no <name>/ at all           -> clone
        #   (b) <name>/ exists with .git    -> pull --ff-only (when --pull)
        #                                    else refuse (avoid clobbering
        #                                    a tracked story with a fresh
        #                                    clone - that would lose
        #                                    uncommitted edits)
        #   (c) <name>/ exists without .git -> first-time adoption: back
        #                                    the existing files up under
        #                                    .bak-<date>, clone fresh.
        #                                    The author usually wants to
        #                                    reconcile by hand anyway.
        inner = (
            f'cd {worlds_dir} && '
            f'if [ -d {name}/.git ]; then '
            f'  git -C {name} pull --ff-only; '
            f'elif [ -d {name} ]; then '
            f'  mv {name} {name}.bak-$(date +%Y%m%d-%H%M%S) && '
            f'  git clone {url} {name}; '
            f'else '
            f'  git clone {url} {name}; '
            f'fi'
        )
        rc = sh(('ssh', target_host, inner)).returncode
        if rc:
            return rc

    print(f'imported {name} from {url}')

    # Validate the freshly landed pack against its own contract.
    pack = pack_root() / 'worlds' / name
    if target_host != 'local':
        # maplab needs the pack on this machine too. We can't reach
        # bazzite's worlds/ from here without another ssh+rsync, and
        # the live game already validates itself via /api/world on
        # the deploy host. Print the validation command instead.
        print(f'validate on the deploy host: ssh {target_host} '
              f'"cd ~/vefr && norns validate --pack worlds/{name}"')
        return 0
    try:
        w = load_pack(pack)
        errors = validate(w, pack_dir=pack)
    except Exception as e:  # noqa: BLE001
        print(f'validate failed: {e}')
        return 2
    if errors:
        print(f'{len(errors)} problem(s) in {pack}:')
        for e in errors:
            print(f'  FAIL: {e}')
        return 2
    print(f'ok - {pack} validates against the pack contract.')
    return 0


# The seed count the stamp sweep inside `vefr check` draws, and what it
# calls them: the same `check-<n>` names, at the same 200 of them, that
# `vefr stamp check` sweeps - the default `stamp_check.report` is given.
# It used to be 8, on the reasoning that the sweep is the slow half. See
# `_stamp_findings` for the arithmetic that retired that reasoning and
# for what the raise costs.
CHECK_STAMP_SEEDS = 200


def _stamp_findings(pack_dir, seeds: int = CHECK_STAMP_SEEDS) -> list[str]:
    """Every stamp refusal `vefr check` prints for a pack, as sentences.

    **The seam (vefr#346).** `vefr check` used to run the shape checks and
    nothing else, so a pack could print `ok:` while carrying a REQUIRED
    stamp that never places - and a room that never places is a floor with
    no warden hall in it. The standalone gate that does catch it,
    `vefr stamp check`, was a separate command nobody had to run. This is
    the same `stamp_check.report` that command calls, so the two cannot
    drift: there is one copy of the rule, not two.

    **Why 200 seeds, and why that changed.** This seam shipped at 8 seeds
    on the reasoning that the sweep is the slow half and `vefr check` runs
    on every pack write. That reasoning priced the sweep and forgot what
    the sweep is FOR. The bar a required room has to clear is 100% - one
    floor in a hundred that loses its warden hall is a floor the hero
    walks into an empty hall - so a room placing on 99 of 100 floors is
    ALREADY a failure, and 8 seeds is a sample far too small to see it:
    `0.99**8 = 0.9227`, so the check printed `ok:` on 92 packs in 100
    carrying that room. A green light that is wrong 8 times in 100 is
    worse than no light, because the creator stops looking. Taking a 99%
    room 99% of the time takes `ceil(ln(0.01)/ln(0.99)) = 459` seeds - so
    200 is the same order as the standalone gate, and the two are now at
    one confidence instead of one of them being the weak one. 200 is also
    what this command ALREADY pays for: `vefr check` sweeps every Section
    at `locks.SECTION_SEEDS = 200` on the same pack and the same
    `check-<n>` names, so raising this adds no new class of work.

    **What the raise costs, measured.** Median of five runs each, same
    machine, same pack, source edited between the two halves. On a
    one-Section pack that ships three required stamps: **0.992s at 8
    seeds, 3.906s at 200** - a delta of 2.91s. The stamp sweep alone is
    0.12s at 8 and 3.03s at 200. On `worlds/sample-world`, which ships no
    `stamps/` at all, it is 0.065s at 8 and 0.061s at 200: no change,
    because the sweep is skipped before it costs anything. That is the
    honest shape of the trade - every pack in the tree today is the second
    case, and a pack that ships stamped rooms pays ~2.9s to stop being
    green for free.

    **A pack with no stamps says nothing.** No `stamps/` directory means
    there is no stamp pack to check, which is every pack in the tree
    today, so the sweep is skipped before it costs anything and prints
    no line - the cost of this change to a pack that ships no stamps is
    measured at 0.00s.
    """
    from . import stamp_check

    pack = Path(pack_dir)
    if not (pack / 'stamps').is_dir():
        return []
    code, lines = stamp_check.report(str(pack), seeds=seeds)
    if code == stamp_check.USAGE:
        # `stamps/` is there but `sections/` is not, or the sweep found
        # nothing to say. `stamp check` reports that as a usage error
        # about the command; inside `vefr check` the pack simply has no
        # stamped room to place, so it is silent and unchanged.
        return []
    # `report` returns [header, *problems, 'N problems'] by its own
    # docstring. The header and the count are `stamp check`'s framing; a
    # check prints the refusals and lets `vefr check`'s own summary carry
    # the rest. Each remaining line is the plain sentence `stamps.sentence`
    # built - `stamp <id>: <what is wrong> <json pointer>` - which already
    # names the stamp, so it is printed as it stands.
    return lines[1:-1]


def cmd_map(args) -> int:
    from .maplab import main as maplab_main
    # `vefr check --release` is the story-status gate (vefr #339): it
    # lists every draft word in the pack and, with --strict, prints the
    # same list before failing. It reads the pack's own files, so it is
    # skipped for `--live URL` (there is no pack on disk to read) and
    # for the other map commands.
    release_drafts: list = []
    if args.map_cmd == 'validate' \
            and (getattr(args, 'release', False) or getattr(args, 'strict', False)) \
            and not getattr(args, 'live', None) and getattr(args, 'pack', None):
        from . import story_status
        release_drafts = story_status.drafts(args.pack)
        for line in story_status.format_report(release_drafts):
            print(line)
    if args.map_cmd == 'validate':
        argv = ['validate', '--pack', str(args.pack)]
    elif args.map_cmd == 'build':
        argv = ['build', '--segments', args.segments, '--pack', str(args.pack)]
        if args.force:
            argv.append('--force')
    elif args.map_cmd == 'verify':
        argv = ['verify', '--url', args.url]
    else:
        raise SystemExit(f'unknown map command: {args.map_cmd}')
    rc = maplab_main(argv)
    # `vefr check` (and `norns validate`) prints the Blueprint note when
    # validation passed: a lock written by an older normalizer whose
    # output still matches is not an error, only worth re-running.
    if rc == 0 and args.map_cmd == 'validate' and getattr(args, 'pack', None):
        from . import blueprint
        for note in blueprint.notes(Path(str(args.pack))):
            print(note)
    # `vefr check` does not stop at the geometry. Three more gates run over
    # the same pack and each fails it on its own sentences: the item locks
    # (every key that cannot be obtained before its door), the Sections (a
    # sweep of every floor of every Section), and the stamped rooms (a
    # required room that never places). Each prints nothing at all on a
    # pack that does not carry that thing, and is otherwise unchanged.
    if args.map_cmd == 'validate' and getattr(args, 'pack', None):
        from . import locks
        pack_dir = Path(str(args.pack))
        findings = locks.findings(pack_dir)
        # ...and sweeps every Section of the pack, which is the E4 half:
        # every floor of every Section, over the section sweep's seeds.
        # A pack that ships no Sections sweeps nothing and is unchanged.
        findings += locks.section_findings(pack_dir)
        # ...and runs the stamp check over the same pack (vefr#346), so a
        # required room that never places cannot be green. The same
        # `stamp_check.report` `vefr stamp check` calls, over the same
        # `check-<n>` seeds and the same 200 of them as the Section sweep
        # above - see `_stamp_findings`. A pack with no `stamps/`
        # directory is silent and costs nothing.
        findings += _stamp_findings(pack_dir)
        for finding in findings:
            print(finding)
        if findings:
            return EXIT_ERROR
    # The release gate's own verdict, last: the list is already printed
    # above, so a strict run shows a human what is in the way before it
    # fails. A `--release` without `--strict` only ever lists.
    if release_drafts and getattr(args, 'strict', False):
        return EXIT_ERROR
    return rc


def _floor_names(first: str, count: int) -> list[str]:
    """The names for `count` generated floors, numbering from `first`.

    A trailing number is stepped up (floor-2 -> floor-2, floor-3, ...);
    a name with no number gets -2, -3, ... appended after the first.
    """
    import re

    m = re.fullmatch(r'(.*?)(\d+)', first)
    if m:
        base, start = m.group(1), int(m.group(2))
        return [f'{base}{start + i}' for i in range(count)]
    return [first] + [f'{first}-{i}' for i in range(2, count + 1)]


def _tile_walkable(rows: list[str], legend: dict, x: int, y: int) -> bool:
    """Walkability of one tile, mirroring maplab's door check.

    A legend `solid` flag wins; otherwise the legacy blocked-char
    fallback decides. Off-map is not walkable.
    """
    from .maplab import BLOCKED_FALLBACK

    if not rows or y < 0 or y >= len(rows) or x < 0 or x >= len(rows[0]):
        return False
    spec = legend.get(rows[y][x], {})
    if isinstance(spec, dict) and isinstance(spec.get('solid'), bool):
        return spec['solid'] is False
    return rows[y][x] not in BLOCKED_FALLBACK


def _take_the_down_stair(rows: list[str], at: tuple[int, int]) -> list[str]:
    """The rows of a bottom floor: its down-stair glyph taken back out.

    Only the tile the generator put the down anchor on becomes floor.
    `d` is a map tile like any other - a stamped room may draw one of
    its own, and a future generator may - so a blanket `replace('d', '.')`
    would erase those too. The stair goes back out at the coordinate it
    was placed at, which is the one thing that is certainly a stair.
    """
    from . import delve_v3

    x, y = at
    out = list(rows)
    out[y] = out[y][:x] + delve_v3.FLOOR + out[y][x + 1:]
    return out


def _named_floor_contract(contract_obj: dict, name_grammar, seed: str) -> dict:
    """A generated floor's contract, named from the pack's grammar.

    A pack without a `name` grammar gets the contract exactly as
    `delve.contract` wrote it. With one, the drawn name rides in
    `name` and `title` (both carry it, so either key reads) beside
    the unchanged geometry. A grammar that refuses expands to the
    empty string, and then the floor is simply unnamed - a broken
    grammar never writes half a name.
    """
    from .grammar import expand_seeded

    if not isinstance(name_grammar, dict):
        return contract_obj
    drawn = expand_seeded(name_grammar, seed)
    if not drawn:
        return contract_obj
    return {**contract_obj, 'name': drawn, 'title': drawn}


def _lay_floors(pack, act_dir, act, act_path, staged, names, announce) -> int:
    """Lay a batch of floors into the act, or leave the pack exactly as it was.

    A bake is ONE change. Either every floor of the Section lands and the pack
    still validates green, or the pack is byte-for-byte what it was before.

    It used not to be one change: `norns delve` wrote every floor and rewrote
    the act's world.json, and only THEN asked the validator - so a pack that
    failed left the floors and the rewritten act behind while exiting non-zero,
    which reads like "nothing was kept" and is the opposite. Here the act's
    bytes and the floors about to be replaced are set aside first, the write
    happens inside a try, and any failure OR exception puts both back before
    the error is returned. The floors are announced only once they are kept.
    """
    saved_act = act_path.read_bytes() if act_path.exists() else None
    saved_regions = {}
    for name in names:
        region = act_dir / name
        kept = None
        if region.is_dir():
            kept = {f.name: f.read_bytes()
                    for f in sorted(region.iterdir()) if f.is_file()}
        saved_regions[name] = kept

    def restore():
        for name in names:
            region = act_dir / name
            kept = saved_regions[name]
            if region.is_dir():
                for child in sorted(region.iterdir()):
                    if kept is None or child.name not in kept:
                        if child.is_dir():
                            shutil.rmtree(child, ignore_errors=True)
                        else:
                            child.unlink()
            if kept is None:
                if region.is_dir():
                    shutil.rmtree(region, ignore_errors=True)
            else:
                region.mkdir(parents=True, exist_ok=True)
                for child_name, data in kept.items():
                    (region / child_name).write_bytes(data)
        if saved_act is None:
            if act_path.exists():
                act_path.unlink()
        else:
            act_path.write_bytes(saved_act)

    try:
        for name, map_text, contract_text in staged:
            region = act_dir / name
            region.mkdir(parents=True, exist_ok=True)
            (region / 'map.md').write_text(map_text, encoding='utf-8')
            (region / 'contract.json').write_text(contract_text,
                                                   encoding='utf-8')
        act_path.write_text(json.dumps(act, indent=2, ensure_ascii=False)
                            + '\n', encoding='utf-8')
        errors = validate(load_pack(pack), pack_dir=pack)
    except Exception as exc:
        restore()
        print('nothing was kept: the Section was rolled back and the pack '
              'is as it was')
        print(f'  the bake raised: {type(exc).__name__}: {exc}')
        raise

    if errors:
        restore()
        print('nothing was kept: the Section was rolled back and the pack '
              'is as it was')
        print('the pack does not validate:')
        for e in errors:
            print(f'  FAIL: {e}')
        return EXIT_ERROR

    announce()
    print('the pack validates green')
    return EXIT_OK

def _bake_section(args, pack: Path, act_dir: Path, act: dict, act_path: Path,
                  from_region: str, from_at: tuple[int, int]) -> int:
    """`norns delve --section <id>`: lay a whole Section and wire its doors.

    The v3 path, and the one PLAN.md section 2's floor key exists for.
    Each floor is drawn by `generate_floor_v3` from the run seed, the
    Section and the floor number `k`, and the generator builds the floor
    key `run_seed/section.id/cycle/k` itself - the same string
    `sections.floor_key(args.seed, section, 0, k)` returns, and the key the
    floor is salted with and recorded under - so floors 2 and 3 of one
    Section, both `normal`, are two maps rather than one drawn twice.

    The doors are the elevator rule of PLAN.md section 4, as wiring:

    - the town (or wherever the descent starts) goes down into floor 1;
    - every floor's down-stair goes to the floor below, and the last floor
      has no down-stair at all;
    - a floor's up-stair climbs to the floor above it, EXCEPT on a landing,
      where it goes straight back to where the descent started. A Section's
      two landings are its first floor and its fifth (Stardew's every-five),
      and the engine offers them because the pack's data says so.

    Every written contract carries four additive keys - `section`, `k`,
    `floor_kind` and `landing` - plus the `floor_key` it was drawn from, so
    the player's descent menu and a stair-time regeneration both have
    something to name. Nothing an authored region carries is touched.
    """
    from . import delve as delve_mod
    from . import delve_v3, sections

    section_id = str(args.section)
    directory = pack / sections.SECTIONS_DIR
    path = directory / f'{section_id}.json'
    if not path.is_file():
        shipped = sorted(item.stem for item in directory.glob('*.json')) \
            if directory.is_dir() else []
        print(f"the pack has no section {section_id!r}"
              + (f' - it ships: {", ".join(shipped)}' if shipped
                 else ' - it ships no sections/ at all'))
        return EXIT_ERROR
    try:
        section = json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        print(f'{sections.SECTIONS_DIR}/{section_id}.json is not valid JSON')
        return EXIT_ERROR
    if not isinstance(section, dict):
        print(f'{sections.SECTIONS_DIR}/{section_id}.json must be an object')
        return EXIT_ERROR

    count = sections.floors(section)
    names = [sections.floor_region(section, k) for k in range(1, count + 1)]
    existing = list(act.get('regions') or [])
    collisions = [name for name in names
                  if name in existing or (act_dir / name).exists()]
    if collisions and not args.force:
        print('refusing to overwrite existing region(s): '
              + ', '.join(collisions))
        print('pass --force to overwrite them.')
        return EXIT_ERROR

    # Draw every floor in memory first, so a bad draw writes nothing.
    planned: list[dict] = []
    for k in range(1, count + 1):
        key = sections.floor_key(args.seed, section, 0, k)
        plan = delve_v3.generate_floor_v3(
            args.seed, sections.floor_size(section, key), section,
            sections.floor_kind(section, k, args.seed, 0), depth=k)
        up = plan['anchors']['up']
        down = plan['anchors']['down']
        rows = list(plan['rows'])
        if k == count:
            # The last floor of a Section is the bottom for now: the vault
            # stair that goes home from it is E8's, not this slice's. The
            # generator draws a down anchor on every floor it lays, so the
            # glyph and the anchor are taken back out here rather than
            # leaving a stair on a floor with nothing under it. Only the
            # tile the generator put the anchor on is a stair - a `d`
            # anywhere else on the map is some other tile and is left be.
            if down:
                rows = _take_the_down_stair(rows, (down[0], down[1]))
            down = None
        contract = delve_mod.contract(plan['w'], plan['h'], up,
                                      down_at=down if down else None)
        contract.update({
            'section': sections.section_id(section) or section_id,
            'k': k,
            'floor_kind': sections.floor_kind(section, k, args.seed, 0),
            'landing': sections.is_landing(section, k),
            'floor_key': key,
        })
        planned.append({'name': names[k - 1], 'rows': rows, 'up': up,
                        'down': down, 'contract': contract})

    wired: list[dict] = [{
        'from': from_region, 'at': list(from_at),
        'to': planned[0]['name'], 'to_at': list(planned[0]['up']),
    }]
    for index in range(len(planned) - 1):
        if planned[index]['down'] is None:
            continue
        wired.append({
            'from': planned[index]['name'], 'at': list(planned[index]['down']),
            'to': planned[index + 1]['name'],
            'to_at': list(planned[index + 1]['up']),
        })
    for index, floor in enumerate(planned):
        k = index + 1
        # A landing climbs to where the descent started; every other floor
        # climbs to the floor above it.
        if k == 1 or sections.is_landing(section, k):
            target, to_at = from_region, list(from_at)
        else:
            target, to_at = names[k - 2], list(planned[k - 2]['down'])
        wired.append({'from': floor['name'], 'at': list(floor['up']),
                      'to': target, 'to_at': to_at})

    kept = [t for t in (act.get('transitions') or [])
            if isinstance(t, dict)
            and (t.get('from') not in names or t.get('to') not in names)]
    act['regions'] = [r for r in existing if r not in names] + names
    act['transitions'] = kept + wired

    staged = [(floor['name'],
               '\n'.join(floor['rows']) + '\n',
               json.dumps(floor['contract'], indent=2, ensure_ascii=False)
               + '\n')
              for floor in planned]

    def announce():
        loaded = sections.load(pack)
        for floor in planned:
            contract = floor['contract']
            where = 'depth {0}'.format(
                sections.depth(section, contract['k'], loaded))
            where += ', up {0},{1}'.format(*floor['up'])
            where += ' down {0},{1}'.format(*floor['down']) \
                if floor['down'] else ' bottom'
            where += f", {contract['floor_kind']}"
            if contract['landing']:
                where += (f", a landing (sets "
                          f"{sections.landing_flag(section, contract['k'])})")
            print(f"  wrote acts/{act_dir.name}/{floor['name']}/ ({where})")
        lands = sections.landings(section)
        print(f"generated {count} floor(s) for section {section_id!r} "
              f"from seed {args.seed!r}; wired {len(wired)} transition(s)")
        print(f"  landings on floor(s) {', '.join(str(k) for k in lands)}"
              if lands else '  this Section has no landing floor')

    return _lay_floors(pack, act_dir, act, act_path, staged, names, announce)


def cmd_delve(args) -> int:
    """`norns delve` - generate dungeon floors and wire their stairs.

    Rules-only and deterministic: every floor comes from
    `vefr.delve.generate_floor` with a seed per floor, no model call.
    Each floor lands as a region directory (map.md + contract.json);
    the act's `world.json` gains the regions and the doors that join
    them: the `from-region`'s stair goes down to the first new floor,
    each floor's down-stair goes to the next, and every floor's
    up-stair climbs back. The last floor is the bottom for now and
    keeps no down-stair. A pack that carries a `grammars.name`
    grammar also gets each floor named from it (the drawn name rides
    in the region's contract; the directory keeps its `floor-N` name).
    Everything is written inside the pack, and an existing generated
    region is refused unless `--force` is passed.
    """
    import re

    from . import delve as delve_mod

    if args.floors < 1:
        print('--floors must be at least 1')
        return EXIT_USAGE

    p = Path(args.pack)
    if p.is_absolute() or '/' in str(args.pack):
        pack = (p if p.is_dir() else p.parent).resolve()
    else:
        pack = (pack_root() / 'worlds' / p).resolve()
    if not (pack / 'world.json').exists():
        print(f'pack not found at {pack}; pass --pack NAME or a path')
        return EXIT_ERROR

    acts_dir = pack / 'acts'
    act_dirs = ([d for d in sorted(acts_dir.iterdir())
                 if d.is_dir() and not d.name.startswith('.')]
                if acts_dir.is_dir() else [])
    if not act_dirs:
        print(f'{pack} has no acts/ tree - `norns delve` needs the acts shape')
        return EXIT_ERROR
    act_dir = act_dirs[0]
    act_path = act_dir / 'world.json'
    act = json.loads(act_path.read_text(encoding='utf-8'))
    # The pack-level grammars block (optional, additive). Only `name`
    # is read here; a pack with no block keeps today's naming exactly.
    try:
        grammars = json.loads(
            (pack / 'world.json').read_text(encoding='utf-8')).get(
                'grammars', {}) or {}
    except (OSError, ValueError):
        grammars = {}
    if not isinstance(grammars, dict):
        grammars = {}
    region_names = list(act.get('regions', []) or [])
    transitions = list(act.get('transitions', []) or [])

    if args.from_region not in region_names:
        print(f'--from-region {args.from_region!r} is not a region of '
              f'{act_dir.name} (regions: {region_names})')
        return EXIT_ERROR

    try:
        fx, fy = (int(v) for v in str(args.from_at).split(','))
    except (TypeError, ValueError):
        print('--from-at must be x,y (for example 4,5)')
        return EXIT_USAGE

    region_dir = act_dir / args.from_region
    map_path = region_dir / 'map.md'
    rows = ([ln for ln in map_path.read_text(encoding='utf-8').splitlines()
             if ln.strip()] if map_path.exists() else [])
    contract_path = region_dir / 'contract.json'
    legend = {}
    if contract_path.exists():
        legend = json.loads(
            contract_path.read_text(encoding='utf-8')).get('legend', {})
    if not _tile_walkable(rows, legend, fx, fy):
        print(f'--from-at ({fx},{fy}) is not a walkable tile in region '
              f"'{args.from_region}' - the author places the down-stair there")
        return EXIT_ERROR

    # A Section is baked whole, by its own id: its floors, its sizes, its
    # kinds and its landings come out of `sections/<id>.json` rather than
    # out of the flags below, which are the v2 generator's. Everything
    # above this point - the pack, the act, --from-region, --from-at - is
    # shared, so a Section is baked from the same stair a single floor is.
    if getattr(args, 'section', None):
        return _bake_section(args, pack, act_dir, act, act_path,
                             args.from_region, (fx, fy))

    # Names: an explicit --first-name wins; otherwise continue the
    # floor-N numbering after whatever the pack already has (a tool the
    # author can extend without renumbering by hand).
    if args.first_name:
        first = args.first_name
    else:
        nums = [int(m.group(1)) for name in region_names
                if (m := re.fullmatch(r'floor-(\d+)', name))]
        for child in act_dir.iterdir():
            if child.is_dir() and (m := re.fullmatch(r'floor-(\d+)', child.name)):
                nums.append(int(m.group(1)))
        first = f'floor-{max(nums) + 1}' if nums else 'floor-2'

    names = _floor_names(first, args.floors)
    # The pack's own name grammar (optional): when it has one, every
    # generated floor is also NAMED from it - drawn from the same seed
    # as the layout, so the same seed always names the same floor. The
    # region directory keeps its `floor-N` name (paths, doors and the
    # act's regions list are unchanged); the drawn name rides in the
    # contract for the player to read. A pack with no grammar keeps
    # exactly the naming it has today.
    name_grammar = (grammars.get('name')
                    if isinstance(grammars.get('name'), dict) else None)
    collisions = [n for n in names
                  if n in region_names or (act_dir / n).exists()]
    if collisions and not args.force:
        print('refusing to overwrite existing region(s): '
              + ', '.join(collisions))
        print('pass --force to overwrite them, or --first-name to pick '
              'another start.')
        return EXIT_ERROR

    # Draw every floor in memory first, so a bad size writes nothing.
    planned: list[tuple[str, list[str], tuple[int, int],
                        tuple[int, int] | None, dict]] = []
    try:
        for i, name in enumerate(names):
            floor_rows = delve_mod.generate_floor(
                f'{args.seed}:{name}', args.width, args.height, args.rooms)
            up = down = None
            for y, row in enumerate(floor_rows):
                for x, ch in enumerate(row):
                    if ch == 'u':
                        up = (x, y)
                    elif ch == 'd':
                        down = (x, y)
            if up is None or down is None:
                print(f'the generator produced no stairs for {name}; '
                      'nothing written')
                return EXIT_ERROR
            if i == len(names) - 1:
                # The bottom floor has no way down for now.
                floor_rows = [row.replace('d', '.') for row in floor_rows]
                down = None
            planned.append((
                name, floor_rows, up, down,
                _named_floor_contract(
                    delve_mod.contract(args.width, args.height, up,
                                       down_at=down),
                    name_grammar, f'{args.seed}:{name}:name'),
            ))
    except ValueError as e:
        print(f'cannot generate: {e}')
        return EXIT_USAGE

    # Doors. Down: from-region -> first floor, then floor N -> N+1. Up:
    # every floor climbs back to where it was entered from.
    wired: list[dict] = [{
        'from': args.from_region, 'at': [fx, fy],
        'to': names[0], 'to_at': list(planned[0][2]),
    }]
    for i in range(len(planned) - 1):
        wired.append({
            'from': names[i], 'at': list(planned[i][3]),
            'to': names[i + 1], 'to_at': list(planned[i + 1][2]),
        })
    for i, (name, _rows, up, _down, _c) in enumerate(planned):
        if i == 0:
            target, to_at = args.from_region, [fx, fy]
        else:
            target, to_at = names[i - 1], list(planned[i - 1][3])
        wired.append({'from': name, 'at': list(up),
                      'to': target, 'to_at': to_at})

    # Merge into the act contract: keep every existing region in order
    # (the first stays first), drop only stale doors touching the names
    # being (re)written, then append the new regions and doors.
    kept = [t for t in transitions
            if not (isinstance(t, dict)
                    and (t.get('from') in names or t.get('to') in names))]
    act['regions'] = [r for r in region_names if r not in names] + names
    act['transitions'] = kept + wired

    staged = [(name, '\n'.join(floor_rows) + '\n',
               json.dumps(contract_obj, indent=2, ensure_ascii=False) + '\n')
              for name, floor_rows, _up, _down, contract_obj in planned]

    def announce():
        for name, _rows, up, down, contract_obj in planned:
            where = 'up {0},{1}'.format(*up)
            where += ' down {0},{1}'.format(*down) if down else ' bottom'
            drawn = contract_obj.get('name')
            if drawn:
                where += f', named "{drawn}"'
            print(f'  wrote acts/{act_dir.name}/{name}/ ({where})')
        print(f'generated {len(names)} floor(s) for {pack.name} from seed '
              f'{args.seed!r}; wired {len(wired)} transition(s)')
        print(f'  {names[-1]} is the bottom for now (no stair down)')

    return _lay_floors(pack, act_dir, act, act_path, staged, names, announce)


def cmd_stamp_check(args) -> int:
    """`vefr stamp check` - ADR 0013's gate for a hand-drawn stamp pack.

    Four kinds of check in one report, in the order an author can fix
    them: what the reader refuses, what a Section cannot be swept for,
    what is too big for the floor it lands on, and what the floors
    actually did - how often each room placed, and whether every stamped
    room on a floor has a door in use and walkable anchors.

    The sweep is the slow half, so `--seeds` is the only thing that
    makes a check quick, and the header says how many it used. Every
    problem is one plain sentence with a JSON pointer; exit 1 when there
    is one, exit 2 when there is no pack to check at all.
    """
    from . import stamp_check

    if args.seeds < 0:
        print('--seeds cannot be negative')
        return EXIT_USAGE

    p = Path(args.pack)
    if p.is_absolute() or '/' in str(args.pack):
        pack = p.resolve()
    else:
        pack = (pack_root() / 'worlds' / p).resolve()

    code, lines = stamp_check.report(str(pack), seeds=args.seeds)
    for line in lines:
        print(line)
    return code


def _template_candidates() -> list[Path]:
    """Where web/packaged.html may live, in preference order.

    web/packaged.html is generated from web/player/parts/ and is never
    committed, so a source checkout builds it here (vefr.player_build)
    before anyone reads the path. A pip-installed wheel ships it as
    package data (hatch force-include: vefr/web/), which is what a
    pack author's repo sees when it runs `ratatoskr weave` against an
    installed engine. Container installs keep it under VEFR_HOME. Try
    all three and prefer whichever actually exists.
    """
    from .paths import app_home
    from .player_build import PlayerBuildError, write_if_parts

    here = Path(__file__).resolve()
    try:
        write_if_parts(here.parents[2])     # a checkout: build the file it is about to read
    except PlayerBuildError as exc:
        # A plain message, not a traceback: the parts on disk do not build (orphan or missing part).
        raise SystemExit(f'vefr: web/player/parts does not build:\n{exc}') from None
    return [
        here.parents[2] / 'web' / 'packaged.html',   # source checkout
        here.parent / 'web' / 'packaged.html',        # wheel package data
        app_home() / 'web' / 'packaged.html',         # container / VEFR_HOME
    ]


_PLAYER_FONTS = (
    ('Cinzel', 'Cinzel-Variable.woff2', '400 900'),
    ('Atkinson Hyperlegible Next', 'AtkinsonHyperlegibleNext-Regular.woff2', '400'),
    ('Atkinson Hyperlegible Next', 'AtkinsonHyperlegibleNext-Bold.woff2', '700'),
    ('Crimson Pro', 'CrimsonPro-Variable.woff2', '200 900'),
)

# The families the player's own stylesheet asks for: every pack ships them,
# skin or no skin. The rest of the list is there for a skin to choose from, and
# a woff2 only rides along in the woven file when a skin asked for it - a pack
# with no skin pays nothing for a font it cannot name.
_PLAYER_BASE_FONTS = ('Cinzel', 'Atkinson Hyperlegible Next')

_ART_TYPES = {'.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}


def _player_fonts_css(web_dir: Path, fonts: dict | None = None) -> str:
    """@font-face rules with the studio fonts inlined, so the woven file
    looks the same with no internet. Missing files are skipped and the
    player falls back to its system font stack.

    `fonts` is a skin's own `fonts` block: those families are inlined
    alongside the player's own two, and nothing else is. Left as None every
    bundled family is inlined (the studio's reading panel wants them all).
    """
    import base64
    wanted = None if fonts is None else {
        f for f in fonts.values() if isinstance(f, str)}
    rules = []
    for family, name, weight in _PLAYER_FONTS:
        if (wanted is not None and family not in _PLAYER_BASE_FONTS
                and family not in wanted):
            continue
        f = web_dir / 'fonts' / name
        if f.is_file():
            data = base64.b64encode(f.read_bytes()).decode('ascii')
            rules.append(f"@font-face {{ font-family: '{family}'; font-weight: {weight}; font-display: swap; "
                         f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}")
    return '\n  '.join(rules)


def _player_title_art(pack: Path, world: dict, web_dir: Path) -> str:
    """The title screen's picture, inlined: the pack's own
    (world.json "player": {"title_art": "<path in the pack>"}) or the
    engine's default front door. Also carries the pack's accent colour,
    when it names a valid hex one. Returns markup for the title screen."""
    import base64
    import re as _re
    player = world.get('player') if isinstance(world.get('player'), dict) else {}
    candidates = []
    own = player.get('title_art')
    if isinstance(own, str) and own:
        # Only a file inside the pack: resolve symlinks and '..', then
        # require the pack's own real path as the prefix.
        base = os.path.realpath(pack)
        target = os.path.realpath(os.path.join(base, own))
        if target.startswith(base + os.sep):
            candidates.append(Path(target))
    candidates.append(web_dir / 'art' / 'illustrations' / 'player-title.webp')
    art = ''
    for p in candidates:
        if p.is_file() and p.suffix.lower() in _ART_TYPES:
            data = base64.b64encode(p.read_bytes()).decode('ascii')
            art = (f'<img class="ts-art" src="data:{_ART_TYPES[p.suffix.lower()]};base64,{data}" alt="">')
            break
    accent = player.get('accent')
    if isinstance(accent, str) and _re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        r, g, b = (int(accent[i:i + 2], 16) / 255 for i in (1, 3, 5))
        lum = sum(w * (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
                  for w, c in zip((0.2126, 0.7152, 0.0722), (r, g, b)))
        on = '#1B1206' if lum > 0.18 else '#FFF8E8'
        art += f'<style>html:root {{ --accent: {accent}; --accent-on: {on}; }}</style>'
    return art


def _inside(base: str, *parts: str) -> str | None:
    """The resolved path of base/parts, or None if it would leave `base`.

    `base` must already be a real path. Every filesystem probe on a name
    that came from pack data (an act id, a region name, a tile file) goes
    through here first, so a name like '../x' can never make the weaver look
    outside the pack. The guard is the same shape `_player_sprites` uses.
    """
    target = os.path.realpath(os.path.join(base, *parts))
    return target if target.startswith(base + os.sep) else None


def _has_subdir(pack: Path | None, name: str) -> bool:
    """True when <pack>/<name> is a directory that stays inside the pack."""
    if pack is None:
        return False
    base = os.path.realpath(pack)
    target = _inside(base, name)
    return target is not None and os.path.isdir(target)


def _act_dir_for(pack: Path, act_id) -> Path | None:
    """The on-disk directory of an act, by the loader's convention.

    An act's `id` comes from its world.json and may differ from the
    directory name (see world._load_act). Prefer <pack>/acts/<id>/,
    else match the first <pack>/acts/*/world.json whose 'id' equals
    the act id. None when nothing matches, so no pack tiles are read
    for that act. Every candidate must resolve inside <pack>/acts.
    """
    if not isinstance(act_id, str) or not act_id or '\0' in act_id:
        return None
    base = os.path.realpath(pack)
    acts = _inside(base, 'acts')
    if acts is None or not os.path.isdir(acts):
        return None
    direct = _inside(acts, act_id)
    if direct is not None and os.path.isdir(direct):
        return Path(direct)
    for name in sorted(os.listdir(acts)):
        if name.startswith('.'):
            continue
        d = _inside(acts, name)
        if d is None or not os.path.isdir(d):
            continue
        world_json = _inside(d, 'world.json')
        if world_json is None or not os.path.isfile(world_json):
            continue
        try:
            with open(world_json, encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get('id') == act_id:
            return Path(d)
    return None


def _pack_tile_paths(pack: Path | None, region_dir: Path | None,
                     name: str) -> list[Path]:
    """The pack's own pictures for one tile name, in try-order.

    Only a file inside the pack is read - the same real-path guard
    _player_sprites takes - so a name like '../../../etc/passwd' that
    resolves outside the pack is skipped, never read. The variant
    order is the loader's (`world._discover_tiles`): the unnumbered
    picture first, then the numbered ones. Empty when the pack, the
    region, or the name has no pictures, so the caller falls through
    to the engine set.
    """
    # NOTE: `pack` is the guard the callers thread through (the real
    # path of the whole pack). When only a region_dir is given, the
    # region itself is the stricter guard base.
    if region_dir is None:
        return []
    if not isinstance(name, str) or not name or '\0' in name:
        return []
    region_real = os.path.realpath(region_dir)
    base = os.path.realpath(pack) if pack is not None else region_real
    if region_real != base and not region_real.startswith(base + os.sep):
        return []
    tiles_real = _inside(region_real, 'tiles')
    if tiles_real is None or not os.path.isdir(tiles_real):
        return []
    out: list[Path] = []
    for rel in _discover_tiles(Path(tiles_real)).get(name, []):
        target = _inside(tiles_real, rel)
        if target is None or not target.startswith(base + os.sep):
            continue
        f = Path(target)
        if os.path.isfile(target) and f.suffix.lower() in _ART_TYPES:
            out.append(f)
    return out


def _tile_data_uri(f: Path) -> str:
    """A picture as a data URI, keyed by the same art-type map the
    title art and sprites use."""
    import base64

    mime = _ART_TYPES[f.suffix.lower()]
    data = base64.b64encode(f.read_bytes()).decode('ascii')
    return f'data:{mime};base64,{data}'


def _tiles_for_legend(legend: dict, sanctuaries, web_dir: Path,
                      region_dir: Path | None = None,
                      pack: Path | None = None) -> dict[str, str | list[str] | dict]:
    """Resolve one legend's symbols to inlined tile pictures.

    Mirrors the studio Map Room's own `tileFor`: an explicit `"tile"`, else
    solid/sanctuary/deco pick stone-wall/rug/grass, else open ground picks
    grass or path by order. A region may bring its own pictures under
    `tiles/`; a symbol with more than one picture bakes a list in variant
    order, one picture bakes the same string shape as the engine set.
    When the pack has no picture for a name the engine set answers (only
    `<name>.webp`, exactly as today, so a pack with no tiles/ bakes
    byte-identically). A symbol with no tile on disk is skipped, and the
    player falls back to its base colour. A name whose first picture is a
    grid (`name.grid3x3.webp`) bakes ONE object `{src, cols, rows}`; the
    player draws cell (x mod cols, y mod rows) of that picture.
    """
    if not isinstance(legend, dict) or not legend:
        return {}
    sanctuaries = set(sanctuaries or [])
    open_chars = [
        ch for ch, spec in legend.items()
        if isinstance(spec, dict) and not spec.get('solid')
        and ch not in sanctuaries and not spec.get('deco')
    ]
    out: dict[str, str | list[str] | dict] = {}
    for ch, spec in legend.items():
        spec = spec if isinstance(spec, dict) else {}
        own = spec.get('tile')
        if isinstance(own, str) and own:
            name = own
        elif spec.get('solid') is True:
            name = 'stone-wall'
        elif ch in sanctuaries:
            name = 'rug'
        elif spec.get('deco'):
            name = 'grass'
        else:
            name = 'path' if open_chars.index(ch) > 0 else 'grass'
        # The pack's own pictures win; a region with none falls through
        # to the engine set, unchanged.
        pack_paths = _pack_tile_paths(pack, region_dir, name)
        if pack_paths:
            grid = tile_grid(pack_paths[0].stem)
            if grid:
                out[ch] = {'src': _tile_data_uri(pack_paths[0]),
                           'cols': grid[1], 'rows': grid[2]}
            elif len(pack_paths) == 1:
                out[ch] = _tile_data_uri(pack_paths[0])
            else:
                out[ch] = [_tile_data_uri(p) for p in pack_paths]
            continue
        f = web_dir / 'art' / 'tiles' / f'{name}.webp'
        if f.is_file():
            out[ch] = _tile_data_uri(f)
    return out


def _edges_for_legend(legend: dict, sanctuaries, web_dir: Path,
                      region_dir: Path | None = None,
                      pack: Path | None = None) -> dict[str, str]:
    """One legend's `edges` sheets as inlined pictures, keyed by symbol.

    A legend entry may carry `"edges": "<name>"`: ONE picture in the
    region's own `tiles/` (`<name>.webp` or `.png`), cut by the player into
    a 4 x 4 block of pieces. Piece `mask` (cell `mask % 4`, row `mask // 4`)
    is drawn over a tile whose neighbours share its symbol by the bits
    north 1, east 2, south 4, west 8. Pack art only - the engine set has no
    edges - and a symbol naming none bakes nothing, so a pack with no
    `edges` bakes `{}` and draws exactly as before. `sanctuaries` and
    `web_dir` are unused; the signature is `_tiles_for_legend`'s so
    `_player_region_tiles` can walk the regions once for both.
    """
    out: dict[str, str] = {}
    if not isinstance(legend, dict):
        return out
    for ch, spec in legend.items():
        name = spec.get('edges') if isinstance(spec, dict) else None
        if not (isinstance(name, str) and name):
            continue
        paths = _pack_tile_paths(pack, region_dir, name)
        if paths:
            out[ch] = _tile_data_uri(paths[0])
    return out


def _player_tile_edges(world: dict, web_dir: Path,
                       pack: Path | None = None) -> dict[str, dict[str, str]]:
    """Every region's edges sheets, keyed by region name, then symbol.

    Only regions whose legend names `edges` appear, so a pack with none
    bakes `{}` (`window.VEFR_TILE_EDGES`).
    """
    every = _player_region_tiles(world, web_dir, pack, per_legend=_edges_for_legend)
    return {rname: edges for rname, edges in every.items() if edges}


def _first_region_dir(pack: Path | None, world: dict) -> Path | None:
    """The on-disk directory of the first act's first region.

    Acts shape: <pack>/acts/<act-dir>/<region>; flat shape: the pack
    root itself (the one implicit town). None when the pack cannot be
    resolved, so resolution stays engine-only.
    """
    if pack is None:
        return None
    pack = Path(pack)
    if not _has_subdir(pack, 'acts'):
        return pack
    first_act = (world.get('acts') or [{}])[0]
    if not isinstance(first_act, dict):
        return None
    act_dir = _act_dir_for(pack, first_act.get('id'))
    if act_dir is None:
        return None
    region_name = next(iter(first_act.get('regions') or {}), None)
    if not isinstance(region_name, str) or not region_name:
        return None
    region = _inside(os.path.realpath(act_dir), region_name)
    return Path(region) if region is not None else None


def _player_tiles(world: dict, web_dir: Path, pack: Path | None = None,
                  region_dir: Path | None = None) -> dict[str, str | list[str]]:
    """The first region's ground tiles, keyed by map symbol.

    Kept as the single global the player used before regions existed; a
    pack with several regions also gets `_player_region_tiles`. `pack`
    and `region_dir`, when given, let the first region bring its own
    tiles/; without them resolution is the engine set, unchanged.
    """
    town = world.get('town') if isinstance(world.get('town'), dict) else {}
    if region_dir is None:
        region_dir = _first_region_dir(pack, world)
    return _tiles_for_legend(town.get('legend') or {},
                             town.get('sanctuary_tiles') or [], web_dir,
                             region_dir, pack)


def _player_region_tiles(world: dict, web_dir: Path,
                         pack: Path | None = None, per_legend=None
                         ) -> dict[str, dict[str, str | list[str]]]:
    """Every region's tiles, keyed by region name.

    Two regions can share a symbol for different ground - a town's '.' is
    grass, a dungeon's '.' is stone floor - so tiles travel with the
    region instead of being merged by symbol. `pack`, when given, lets
    each region bring its own tiles/ from its on-disk directory (the
    acts shape's <pack>/acts/<act-dir>/<region>, or the pack root for
    the flat shape); without it resolution is the engine set, unchanged.
    `per_legend` (default `_tiles_for_legend`) is what one region's legend
    is read with; `_player_tile_edges` walks the same regions for `edges`.
    """
    per_legend = per_legend or _tiles_for_legend
    pack_path = Path(pack) if pack is not None else None
    flat = pack_path is not None and not _has_subdir(pack_path, 'acts')
    # A flat pack keeps its geometry in world['town'], not in a region
    # contract. It only reads its own tiles when it actually brings a
    # tiles/ dir, so one with none bakes exactly what it did before.
    flat_town = world.get('town') if isinstance(world.get('town'), dict) else {}
    flat_tiles = _has_subdir(pack_path, 'tiles')
    out: dict[str, dict[str, str | list[str]]] = {}
    for act in (world.get('acts') or []):
        act = act if isinstance(act, dict) else {}
        act_dir = None
        if pack_path is not None and not flat:
            act_dir = _act_dir_for(pack_path, act.get('id'))
        for rname, rdata in (act.get('regions') or {}).items():
            contract = rdata.get('contract') if isinstance(rdata, dict) else None
            contract = contract if isinstance(contract, dict) else {}
            legend = contract.get('legend') or {}
            sanctuaries = contract.get('sanctuary_tiles') or []
            if flat:
                region_dir = pack_path
                if flat_tiles:
                    legend = flat_town.get('legend') or {}
                    sanctuaries = flat_town.get('sanctuary_tiles') or []
            elif act_dir is not None:
                region = _inside(os.path.realpath(act_dir), rname) if isinstance(rname, str) and rname else None
                region_dir = Path(region) if region is not None else None
            else:
                region_dir = None
            out[rname] = per_legend(legend, sanctuaries, web_dir,
                                    region_dir, pack_path)
    if not out:
        town = world.get('town') if isinstance(world.get('town'), dict) else {}
        rname = world.get('_region') or 'town'
        out[rname] = per_legend(
            town.get('legend') or {}, town.get('sanctuary_tiles') or [],
            web_dir, pack_path, pack_path)
    return out


def _descent_section_tiles(descent: dict, web_dir: Path,
                           pack: Path | None = None) -> dict:
    """Each Section's own tile pictures, keyed by Section id, for `window.VEFR_REGION_TILES`.

    A Section's `tiles` says which tileset each of the generator's glyphs is
    drawn with, which is what makes two Sections of one descent draw different
    ground. The pictures are resolved the way a baked region's are
    (`_tiles_for_legend`): the pack's own `tiles/` first, then the engine set,
    and a glyph with no picture on disk is simply absent, so the player falls
    back to that glyph's base colour.

    A Section that names no `tiles` is left out entirely rather than baked as
    the shared legend: its floors keep falling back to `window.VEFR_TILES`,
    which is exactly what they drew before a Section could say anything about
    its ground. So a pack with no `tiles` anywhere weaves as it always did.
    """
    from . import delve as delve_mod

    listed = descent.get('sections') if isinstance(descent, dict) else None
    out: dict[str, dict] = {}
    for section in (listed if isinstance(listed, list) else []):
        if not isinstance(section, dict) or not isinstance(section.get('tiles'), dict):
            continue
        sid = section.get('id')
        if not isinstance(sid, str) or not sid:
            continue
        out[sid] = _tiles_for_legend(delve_mod.section_legend(section), [],
                                     web_dir, pack, pack)
    return out


def _descent_section_decor(descent: dict, pack: Path | None) -> dict:
    """Each Section's decor pictures, inlined, keyed by Section id then picture name.

    A decor `pic` is read the way a prop's is, from the pack's own `props/`
    (`_prop_picture_path`). A picture with no file is absent, and the player
    draws nothing for it; a Section with no decor is left out entirely.
    """
    if pack is None:
        return {}
    from . import delve as delve_mod

    listed = descent.get('sections') if isinstance(descent, dict) else None
    out: dict[str, dict[str, str]] = {}
    for section in (listed if isinstance(listed, list) else []):
        sid = section.get('id') if isinstance(section, dict) else None
        if not isinstance(sid, str) or not sid:
            continue
        pictures: dict[str, str] = {}
        for entry in delve_mod.decor_of(section):
            pic = entry['pic']
            if pic in pictures:
                continue
            f = _prop_picture_path(Path(pack), None, pic)
            if f is not None:
                pictures[pic] = _tile_data_uri(f)
        if pictures:
            out[sid] = pictures
    return out


SPRITE_SCALE_MIN, SPRITE_SCALE_MAX = 0.2, 2.0


def _sprite_scales(world: dict) -> dict[str, float]:
    """The size of each character relative to the standard (1.0 = 1.5 tiles tall).

    A pack may name `player.sprite_scale`: `{"hearth-cat": 0.5}` draws that character at half height,
    feet still on the tile. Only finite numbers from SPRITE_SCALE_MIN to SPRITE_SCALE_MAX are baked; a bad
    entry is dropped here (and reported by `norns validate`), so the player never meets one.
    """
    import math

    player = world.get('player') if isinstance(world.get('player'), dict) else {}
    named = player.get('sprite_scale') if isinstance(player.get('sprite_scale'), dict) else {}
    out: dict[str, float] = {}
    for name, v in named.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            continue
        if SPRITE_SCALE_MIN <= v <= SPRITE_SCALE_MAX:
            out[str(name)] = float(v)
    return out


def _referenced_sprite_keys(world: dict) -> set[str]:
    """Every sprite key the world asks for: `hero`, each item's or
    enemy's `sprite`, and each speaker key. The world dict is assembled
    from several pack shapes, so each block is read defensively: a
    missing or oddly shaped block simply adds nothing.
    """
    keys: set[str] = {'hero'}

    def _sprite(spec) -> None:
        if (isinstance(spec, dict) and isinstance(spec.get('sprite'), str)
                and spec['sprite']):
            keys.add(spec['sprite'])

    def _speakers(block) -> None:
        if isinstance(block, dict):
            keys.update(k for k in block if isinstance(k, str) and k)

    def _enemies(block) -> None:
        if isinstance(block, list):
            for spec in block:
                _sprite(spec)

    items = world.get('items')
    if isinstance(items, dict):
        for spec in items.values():
            _sprite(spec)
    _speakers(world.get('speakers'))
    regions = world.get('regions')
    if isinstance(regions, dict):
        for rdata in regions.values():
            if isinstance(rdata, dict):
                _enemies(rdata.get('enemies'))
    town = world.get('town')
    if isinstance(town, dict):
        _enemies(town.get('enemies'))
    acts = world.get('acts')
    if isinstance(acts, list):
        for act in acts:
            if not isinstance(act, dict):
                continue
            _speakers(act.get('speakers'))
            act_regions = act.get('regions')
            if isinstance(act_regions, dict):
                for rdata in act_regions.values():
                    if not isinstance(rdata, dict):
                        continue
                    contract = rdata.get('contract')
                    if isinstance(contract, dict):
                        _enemies(contract.get('enemies'))
    return keys


def resolve_sprites(pack: Path, world: dict) -> dict[str, str]:
    """The pack's sprites, key -> pack-relative picture path.

    A key resolves when `player.sprites` lists it (the explicit entry
    wins over a file of the same name) or when something references it -
    an item's or an enemy's `sprite`, a speaker key, or `hero` - and
    `sprites/<key>.<art>` exists at the pack root. `*-sheet.*` files and
    `*.sheet.json` sidecars belong to the walk sheet and are never
    sprites by name, and a file nothing references and nothing lists is
    not baked. Every caller keeps its real-path guard on the read.
    """
    player = world.get('player')
    if not isinstance(player, dict):
        player = world.get('_player')
    player = player if isinstance(player, dict) else {}
    named = player.get('sprites') if isinstance(player.get('sprites'), dict) else {}
    out: dict[str, str] = {}
    for key, rel in named.items():
        if isinstance(rel, str) and rel:
            out[str(key)] = rel
    refs = _referenced_sprite_keys(world)
    base = os.path.realpath(pack)
    root = _inside(base, 'sprites')
    if root is None or not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        suffix = os.path.splitext(name)[1].lower()
        if suffix not in _ART_TYPES:
            continue
        key = name[:-len(suffix)]
        if not key or key.endswith('-sheet') or key in out or key not in refs:
            continue
        target = _inside(root, name)
        if target is None or not os.path.isfile(target):
            continue
        out[key] = f'sprites/{name}'
    return out


def _player_sprites(pack: Path, world: dict) -> dict[str, str]:
    """Inline the pack's character sprites, keyed by name.

    A pack names one sprite per character under `player.sprites` in
    world.json, relative to the pack root: `hero` for the player, and one
    named for each speaker key. A referenced key whose picture sits at
    `sprites/<key>.<art>` rides even when nothing lists it; the one
    resolution rule is `resolve_sprites`. Both the studio's live player
    and the woven player draw them where a character stands, falling back
    to the drawn figure when a name has no sprite. Only a file inside the
    pack is read - the same real-path guard the title art takes - so a
    namespaced path can never reach outside the pack.
    """
    import base64

    base = os.path.realpath(pack)
    out: dict[str, str] = {}
    for name, rel in resolve_sprites(pack, world).items():
        target = os.path.realpath(os.path.join(base, rel))
        if not target.startswith(base + os.sep):
            continue
        f = Path(target)
        if f.is_file() and f.suffix.lower() in _ART_TYPES:
            mime = _ART_TYPES[f.suffix.lower()]
            out[str(name)] = f'data:{mime};base64,{base64.b64encode(f.read_bytes()).decode("ascii")}'
    return out


def _player_sprite_sheets(pack: Path, world: dict) -> dict[str, dict]:
    """Inline the pack's optional walk sheets, keyed by sprite name.

    A sprite may carry a `<stem>.sheet.json` beside its picture naming
    a frame sheet (`image`, `frame`, `fps`, `directions`). The bake
    replaces the sheet's `image` name with a data URI; a missing or
    broken sheet drops the key entirely, so the player only ever meets
    a complete sheet and the weave never crashes. Any resolved sprite
    (explicit or found by name through `resolve_sprites`) keeps its
    sheet, so a `hero` found by name still bakes `hero.sheet.json`. The
    sheet's image resolves beside the sheet itself and goes through the
    same real-path guard the sprites take, so pack data can never read
    outside the pack. Returns {} for a pack with no sheets.
    """
    import base64

    base = os.path.realpath(pack)
    out: dict[str, dict] = {}
    for name, rel in resolve_sprites(pack, world).items():
        pic = _inside(base, rel)
        if pic is None:
            continue
        sheet_path = Path(pic).with_suffix('.sheet.json')
        if not sheet_path.is_file():
            continue
        try:
            sheet = json.loads(sheet_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(sheet, dict):
            continue
        image = sheet.get('image')
        if not isinstance(image, str) or not image:
            continue
        sheet_dir = os.path.realpath(sheet_path.parent)
        target = _inside(sheet_dir, image)
        if target is None or not os.path.isfile(target):
            continue
        art = Path(target)
        if art.suffix.lower() not in _ART_TYPES:
            continue
        blob = base64.b64encode(art.read_bytes()).decode('ascii')
        sheet = dict(sheet)
        sheet['image'] = f'data:{_ART_TYPES[art.suffix.lower()]};base64,{blob}'
        out[str(name)] = sheet
    return out


def _player_items(world: dict) -> dict[str, dict]:
    """The pack's item catalog, keyed by id.

    A pack's `items` maps an id to `{"name", "sprite"}`: the words the
    bag shows and the picture it draws (`sprite` names an entry in
    `player.sprites`). An entry with no id or no name is dropped, and a
    drop that names a missing item is dropped from what is baked, so the
    player never meets a thing the world cannot describe. `sprite` is
    optional; with none the marker falls back to a plain dot.

    The reward fields are optional and ride along only when the pack
    names them, so an older catalog bakes exactly as it always did:
    `value` (a positive int) is what a shop pays and asks; `heal` (a
    positive int) and `use` (a verb like "drink") make the item usable.
    A value that is not a positive int simply cannot be sold; a heal or
    use that is not a positive int / non-empty string is ignored.
    `light` (a torch's `radius`/`turns`, or `reveal: true`) rides along
    only when it forms a usable shape; maplab reports a broken one.
    `slot` and `mods` (the five slots and atk/hp) ride along under the
    same rule, read from the same helper the validator uses.
    `rarity`, `traits` and `roll` (ADR 0017) ride along under that rule
    too, read from `maplab.item_roll_of`, which is what the draw reads.
    """
    listed = world.get('items')
    if not isinstance(listed, dict):
        return {}
    out: dict[str, dict] = {}
    for iid, spec in listed.items():
        key = str(iid).strip()
        if not key or not isinstance(spec, dict):
            continue
        name = str(spec.get('name', '')).strip()
        if not name:
            continue
        sprite = spec.get('sprite')
        entry: dict = {'name': name,
                       'sprite': sprite if isinstance(sprite, str) else ''}
        for field in ('value', 'heal'):
            n = spec.get(field)
            if isinstance(n, int) and not isinstance(n, bool) and n > 0:
                entry[field] = n
        use = spec.get('use')
        if isinstance(use, str) and use.strip():
            entry['use'] = use.strip()
        # `keep`: usable and not consumable - a kept thing is used and
        # stays in the bag. Only `true` rides along, so a pack that
        # never asked bakes exactly what it always baked.
        if spec.get('keep') is True:
            entry['keep'] = True
        # `carry`: how many places a carried thing adds to the bag. Only a
        # positive whole number rides along, as `heal` does.
        carry = spec.get('carry')
        if isinstance(carry, int) and not isinstance(carry, bool) and carry > 0:
            entry['carry'] = carry
        # `light`: a torch's radius/turns or a one-shot reveal. Only a
        # valid, usable form is baked, so a broken one is a silent no-op
        # rather than a thing the player cannot use. maplab names it.
        light = spec.get('light')
        if isinstance(light, dict) and not isinstance(light, bool):
            lum: dict = {}
            radius, turns = light.get('radius'), light.get('turns')
            if (isinstance(radius, int) and not isinstance(radius, bool)
                    and 1 <= radius <= 20
                    and isinstance(turns, int) and not isinstance(turns, bool)
                    and 1 <= turns <= 999):
                lum = {'radius': radius, 'turns': turns}
            if light.get('reveal') is True:
                lum['reveal'] = True
            if lum:
                entry['light'] = lum
        # `slot` and `mods` (design/equipment.md, step 1): a wearable
        # thing and the stats it changes. Only a valid, usable shape
        # rides along - and `mods` only beside a `slot`, so a keepsake
        # stays a keepsake - which makes a broken one a silent no-op
        # rather than a thing the player cannot wear. maplab names it.
        slot, mods = item_slot_and_mods(spec)
        if slot is not None:
            entry['slot'] = slot
            if mods:
                entry['mods'] = mods
        # `rarity`, `traits` and `roll` (ADR 0017): what a drawn drop of
        # this thing may be. All three ride along only in the usable form
        # `maplab.item_roll_of` resolves, and only when the pack named
        # them, so an item written before this slice bakes byte for byte
        # what it always baked. The `roll` that rides is the RESOLVED one
        # - the defaults already filled in - so the woven player draws
        # from the numbers it can read without re-deciding them.
        rarity = item_rarity_of(spec)
        if rarity:
            entry['rarity'] = rarity
        traits = item_traits_of(spec)
        if traits:
            entry['traits'] = traits
        roll = item_roll_of(spec)
        if roll:
            entry['roll'] = {
                'rarity': {name: weight for name, weight in roll['rarity']},
                'traits': list(roll['traits']),
                'chance': roll['chance'], 'max': roll['max'],
            }
        # `spell` (ADR 0018): the spell this item teaches when it is used.
        # A spellbook is an ordinary item, so it rides along beside the
        # rest of the record and only when the pack named one - an item
        # written before this slice bakes byte for byte what it always
        # baked. The id itself is checked against the pack's own `spells`
        # by `maplab.item_spell_errors`; the bake carries the pack's word
        # either way, because a silent drop is worse than a sentence.
        taught = spec.get('spell')
        if isinstance(taught, str) and taught.strip():
            entry['spell'] = taught.strip()
        # `grants` and `changes` (the item-grants slice): the verbs this
        # thing hands the hero while it is carried or worn, and what it
        # does to a verb it names. Both ride along only in the usable form
        # `maplab.item_grants_of` / `item_changes_of` resolve, and only
        # when the pack named them, so an item written before this slice
        # bakes byte for byte what it always baked. The verb ids are
        # checked by `maplab.item_grants_errors` and carried either way -
        # a silent drop is worse than a sentence.
        grants = item_grants_of(spec)
        if grants:
            entry['grants'] = grants
        changes = item_changes_of(spec)
        if changes:
            entry['changes'] = changes
        out[key] = entry
    return out


def _player_spells(world: dict):
    """The pack's `spells` block as the woven player reads it, or None.

    ADR 0018. `{'schools': [...], 'spells': [{...}, ...]}` - the pack's
    own words in the pack's own order, resolved through the same readers
    `maplab.spells_errors` validated them with, so what the player is
    handed is what the check looked at.

    None when the pack declares no block at all, and then the weave
    carries no `window.VEFR_SPELLS` line: a pack with no spells bakes
    exactly the bytes it baked before this slice, and the player's
    `spellRecords` reads the missing global as no spells rather than as
    an empty object that looks like a pack that declared none of
    anything.
    """
    block = world.get('spells') if isinstance(world, dict) else None
    if not isinstance(block, dict):
        return None
    from .maplab import spells_of, spell_schools_of
    out: list[dict] = []
    for record in spells_of(world):
        entry: dict = {'id': str(record.get('id')).strip(),
                       'name': str(record.get('name') or '').strip(),
                       'school': str(record.get('school') or '').strip()}
        if not entry['id'] or not entry['name']:
            continue
        level, heal = record.get('level'), record.get('heal')
        if isinstance(level, int) and not isinstance(level, bool) and level >= 1:
            entry['level'] = level
        if isinstance(heal, int) and not isinstance(heal, bool) and heal >= 1:
            entry['heal'] = heal
        out.append(entry)
    return {'schools': spell_schools_of(world), 'spells': out}


def _drop_ids(value, items: set) -> list[str]:
    """The ids a `drops` value names, filtered to the catalog.

    A region enemy's `drops` is a list; a chest book's is a comma-
    separated string in its front matter. Both are read here so a drop
    is kept only when the item exists, in the order written, once each.
    """
    if isinstance(value, str):
        parts = value.split(',')
    elif isinstance(value, list):
        parts = value
    else:
        return []
    out: list[str] = []
    for part in parts:
        pid = str(part).strip()
        if pid and pid in items and pid not in out:
            out.append(pid)
    return out


def _rule_bakes(rule) -> bool:
    """Can this one rule actually run in the woven player?

    The same shape the engine's planRule() demands, checked at bake
    time: a rule that could never fire (bad id, unknown or malformed
    `when`, malformed `if` or `then`) is dropped whole - never baked
    half-broken. Pure shape logic: no clock, no model, no filesystem,
    and no id here ever becomes a path.
    """
    from .maplab import RULE_EVENTS, RULE_EVENT_KEYS

    if not isinstance(rule, dict):
        return False
    rid = rule.get('id')
    if not isinstance(rid, str) or not rid.strip():
        return False
    if 'on' in rule and not isinstance(rule['on'], str):
        return False
    if 'once' in rule and not isinstance(rule['once'], bool):
        return False
    when = rule.get('when')
    if not isinstance(when, dict) or len(when) != 1:
        return False
    event, payload = next(iter(when.items()))
    if event not in RULE_EVENTS or not isinstance(payload, dict):
        return False
    if set(payload) != set(RULE_EVENT_KEYS[event]):
        return False
    for key, value in payload.items():
        if key == 'distance':
            # The engine matches "within N tiles", 0 = standing on it
            # (a bool is not a number here either); anything outside
            # 0..9 can never fire.
            if (isinstance(value, bool) or not isinstance(value, int)
                    or not 0 <= value <= 9):
                return False
        elif not isinstance(value, str) or not value:
            return False
    if 'if' in rule and not _conditions_bake(rule['if']):
        return False
    then = rule.get('then')
    if not isinstance(then, list) or not then:
        return False
    return all(_action_bakes(a) for a in then)


def _conditions_bake(conds) -> bool:
    """Every condition in a rule's `if` is one the engine can evaluate.

    Mirrors evalCond's null (skip) cases exactly: the flag form is
    `flag`+`is` and nothing else, `believes`/`is-in` payloads carry
    exactly their two keys, and `not`/`all-of` recurse.
    """
    if not isinstance(conds, list):
        return False
    for cond in conds:
        if not isinstance(cond, dict):
            return False
        keys = set(cond)
        if keys == {'flag', 'is'}:
            if not isinstance(cond['flag'], str) or not isinstance(cond['is'], bool):
                return False
        elif len(keys) != 1:
            return False
        elif 'has' in cond:
            if not isinstance(cond['has'], str) or not cond['has']:
                return False
        elif 'believes' in cond or 'not-believes' in cond:
            payload = cond.get('believes', cond.get('not-believes'))
            if (not isinstance(payload, dict)
                    or set(payload) != {'who', 'claim'}
                    or not isinstance(payload.get('who'), str)
                    or not isinstance(payload.get('claim'), str)):
                return False
        elif 'is-in' in cond:
            payload = cond['is-in']
            if (not isinstance(payload, dict)
                    or set(payload) != {'who', 'place'}
                    or not isinstance(payload.get('who'), str)
                    or not isinstance(payload.get('place'), str)):
                return False
        elif 'not' in cond:
            if not _conditions_bake([cond['not']]):
                return False
        elif 'all-of' in cond:
            if not _conditions_bake(cond['all-of']):
                return False
        else:
            return False
    return True


def _action_bakes(action) -> bool:
    """One `then` action in the shape the engine's validAction() runs.

    Kept in lockstep with the engine: whatever it accepts is baked,
    whatever it skips is dropped before it reaches the file.
    """
    if not isinstance(action, dict) or len(action) != 1:
        return False
    key, value = next(iter(action.items()))
    if key == 'say':
        if isinstance(value, str):
            return True
        if isinstance(value, dict):
            return (set(value) == {'who', 'line'}
                    and isinstance(value.get('who'), str)
                    and isinstance(value.get('line'), str))
        return False
    if key in ('show', 'hide', 'reveal', 'give', 'takes', 'set', 'unset',
               'point-to', 'complete-act'):
        return isinstance(value, str) and bool(value)
    if key == 'weather':
        return value in ('fog', 'clear')
    if key in ('believes', 'stops-believing'):
        return (isinstance(value, dict) and set(value) == {'who', 'claim'}
                and isinstance(value.get('who'), str)
                and isinstance(value.get('claim'), str))
    if key == 'tells':
        return (isinstance(value, dict) and set(value) == {'who', 'claim', 'to'}
                and isinstance(value.get('who'), str)
                and isinstance(value.get('claim'), str)
                and isinstance(value.get('to'), str))
    return False


def _player_rules(world: dict) -> dict:
    """The pack's optional rule catalogs, baked for the woven player.

    Returns {} when the pack declares NONE of flags/claims/people/rules:
    the light bake, all four placeholders becoming the literal `null`,
    which is exactly the file every existing pack weaves.

    A pack that declares any of them gets the full four-key shape the
    engine reads - {"rules": [...], "flags": {}, "claims": {}, "people": {}}
    - with undeclared keys defaulting to empty. Entries that cannot run
    are DROPPED, never baked half-broken: a rule that could never fire
    stays out entirely, and a flag, claim or person entry in a shape the
    engine cannot read is dropped the same way. No id is ever turned
    into a filesystem path - this reads the already-loaded world dict
    and nothing else.
    """
    if not any(k in world for k in ('flags', 'claims', 'people', 'rules')):
        return {}
    out: dict = {'rules': [], 'flags': {}, 'claims': {}, 'people': {}}

    declared_flags = world.get('flags')
    if isinstance(declared_flags, dict):
        for name, line in declared_flags.items():
            if isinstance(name, str) and name and isinstance(line, str):
                out['flags'][name] = line

    declared_claims = world.get('claims')
    if isinstance(declared_claims, dict):
        for cname, spec in declared_claims.items():
            if (isinstance(cname, str) and cname and isinstance(spec, dict)
                    and isinstance(spec.get('meaning'), str)
                    and isinstance(spec.get('true'), bool)):
                out['claims'][cname] = spec

    declared_people = world.get('people')
    if isinstance(declared_people, dict):
        for pid, spec in declared_people.items():
            if not (isinstance(pid, str) and pid and isinstance(spec, dict)):
                continue
            believes = spec.get('believes')
            if not isinstance(believes, list):
                continue
            held = [c for c in believes if isinstance(c, str) and c]
            out['people'][pid] = {'believes': held}

    declared_rules = world.get('rules')
    if isinstance(declared_rules, list):
        out['rules'] = [r for r in declared_rules if _rule_bakes(r)]
    return out


def _album_entry_bakes(entry) -> bool:
    """Can this one sticker actually earn in the woven player?

    Mirrors the album engine's reading: a usable id, name and kind, a
    riddle for a riddle sticker, and a `when` in the same shape a rule
    bakes with. An entry the engine could not read is dropped whole,
    never baked half-broken. Pure shape logic: no clock, no model, no
    filesystem, and no id here ever becomes a path.
    """
    from .maplab import ALBUM_KINDS, ALBUM_SHINES, RULE_EVENTS, RULE_EVENT_KEYS

    if not isinstance(entry, dict):
        return False
    sid = entry.get('id')
    if not isinstance(sid, str) or not sid.strip():
        return False
    name = entry.get('name')
    if not isinstance(name, str) or not name:
        return False
    kind = entry.get('kind')
    if kind not in ALBUM_KINDS:
        return False
    if kind == 'riddle':
        riddle = entry.get('riddle')
        if not isinstance(riddle, str) or not riddle.strip():
            return False
    if 'shine' in entry and entry.get('shine') not in ALBUM_SHINES:
        return False
    when = entry.get('when')
    if not isinstance(when, dict) or len(when) != 1:
        return False
    event, payload = next(iter(when.items()))
    if event not in RULE_EVENTS or not isinstance(payload, dict):
        return False
    if set(payload) != set(RULE_EVENT_KEYS[event]):
        return False
    for key, value in payload.items():
        if key == 'distance':
            # The engine matches "within N tiles"; anything outside the
            # validator's 0..9 can never fire.
            if (isinstance(value, bool) or not isinstance(value, int)
                    or not 0 <= value <= 9):
                return False
        elif not isinstance(value, str) or not value:
            return False
    return True


def _player_album(world: dict) -> list | None:
    """The pack's optional sticker album, baked for the woven player.

    Returns None when the pack declares no `album`: the placeholder
    becomes the literal `null`, exactly the file every existing pack
    weaves. An entry that could never earn is DROPPED, never baked
    half-broken. No id is ever turned into a filesystem path - this
    reads the already-loaded world dict and nothing else.
    """
    if 'album' not in world:
        return None
    album = world.get('album')
    if not isinstance(album, list):
        return None
    return [entry for entry in album if _album_entry_bakes(entry)]


def _player_chest(web_dir: Path) -> str:
    """The chest picture, inlined.

    A chest is a container you open: the note inside it is a book, but the
    chest is what you see on the floor and what you use.
    """
    import base64

    f = web_dir / 'art' / 'icons' / 'ui' / 'open.webp'
    if not f.is_file():
        return ''
    return 'data:image/webp;base64,' + base64.b64encode(f.read_bytes()).decode('ascii')


def _player_door(web_dir: Path) -> str:
    """The door picture, inlined, so a transition can be drawn.

    A door is a tile you step on to enter another map. Without a picture it
    is an invisible hole in the floor, so the woven player draws this at
    every transition tile of the region you are in.
    """
    import base64

    f = web_dir / 'art' / 'tiles' / 'door.webp'
    if not f.is_file():
        return ''
    return 'data:image/webp;base64,' + base64.b64encode(f.read_bytes()).decode('ascii')


_WAY_PICTURE_NAMES = {'door': 'way-door', 'stairs-up': 'way-stairs-up',
                      'stairs-down': 'way-stairs-down', 'trapdoor': 'way-trapdoor'}


def _way_pictures(pack: Path, region_dir: Path | None) -> dict[str, str]:
    """A region's own way pictures by kind, inlined; a kind it does not name is absent."""
    out: dict[str, str] = {}
    for kind, name in _WAY_PICTURE_NAMES.items():
        paths = _pack_tile_paths(pack, region_dir, name)
        if paths:
            out[kind] = _tile_data_uri(paths[0])
    return out


def _player_way_icons(pack: Path | None) -> dict[str, str]:
    """The pack-wide way pictures, from its root tiles/, inlined by kind."""
    if pack is None:
        return {}
    return _way_pictures(Path(pack), Path(pack))


def _player_region_way_icons(world: dict, pack: Path | None) -> dict[str, dict[str, str]]:
    """Each region's own way pictures, keyed by region name; only regions that bring one."""
    if pack is None:
        return {}
    pack_path = Path(pack)
    flat = not _has_subdir(pack_path, 'acts')
    out: dict[str, dict[str, str]] = {}
    for act in (world.get('acts') or []):
        act = act if isinstance(act, dict) else {}
        act_dir = None if flat else _act_dir_for(pack_path, act.get('id'))
        for rname in (act.get('regions') or {}):
            if flat:
                region_dir = pack_path
            elif act_dir is not None:
                region = _inside(os.path.realpath(act_dir), rname) if isinstance(rname, str) and rname else None
                region_dir = Path(region) if region is not None else None
            else:
                region_dir = None
            if region_dir is None or os.path.realpath(region_dir) == os.path.realpath(pack_path):
                continue
            pictures = _way_pictures(pack_path, region_dir)
            if pictures:
                out[rname] = pictures
    return out


def _region_folder(act_dir: Path | None, rname) -> Path | None:
    """An act region's own folder, resolved inside the act directory, or None."""
    if act_dir is None or not isinstance(rname, str) or not rname or '\0' in rname:
        return None
    found = _inside(os.path.realpath(act_dir), rname)
    return Path(found) if found is not None else None


def _prop_picture_path(pack: Path, region_dir: Path | None, pic: str) -> Path | None:
    """The file a prop names: props/<pic>.webp or .png in the region, else the pack root."""
    if not isinstance(pic, str) or not pic or '\0' in pic:
        return None
    for root in (region_dir, pack):
        if root is None:
            continue
        folder = _inside(os.path.realpath(root), 'props')
        if folder is None or not os.path.isdir(folder):
            continue
        for ext in ('.webp', '.png'):
            target = _inside(folder, pic + ext)
            if target is not None and os.path.isfile(target):
                return Path(target)
    return None


def _prop_pictures(pack: Path, region_dir: Path | None, props: list) -> dict[str, str]:
    """The pictures a region's props name, inlined by name; a name with no file is absent."""
    out: dict[str, str] = {}
    for p in props:
        pic = p.get('pic') if isinstance(p, dict) else None
        if not isinstance(pic, str) or pic in out:
            continue
        f = _prop_picture_path(pack, region_dir, pic)
        if f is not None:
            out[pic] = _tile_data_uri(f)
    return out


def _player_prop_pics(world: dict, pack: Path | None) -> dict[str, dict[str, str]]:
    """Each region's prop pictures by region name; a region whose props name none is absent.

    Mirrors the weave's regions: the first act's, with the unified town
    standing in for a first region that has no map of its own, or the
    town alone when the pack has no acts.
    """
    if pack is None:
        return {}
    pack_path = Path(pack)
    flat = not _has_subdir(pack_path, 'acts')
    acts = world.get('acts') or [{}]
    first_act = acts[0] if isinstance(acts[0], dict) else {}
    town = world.get('town') if isinstance(world.get('town'), dict) else {}
    regions = first_act.get('regions') if isinstance(first_act.get('regions'), dict) else {}
    act_dir = None if flat else _act_dir_for(pack_path, first_act.get('id'))
    sources: list[tuple[str, dict, Path | None]] = []
    for i, (rname, rdata) in enumerate(regions.items()):
        rdata = rdata if isinstance(rdata, dict) else {}
        contract = rdata.get('contract') if isinstance(rdata.get('contract'), dict) else {}
        if i == 0 and not (rdata.get('map_text') or '').strip() and town.get('map'):
            contract = town
        region_dir = pack_path if flat else _region_folder(act_dir, rname)
        sources.append((rname, contract, region_dir))
    if not sources:
        sources.append((world.get('_region') or 'town', town, pack_path))
    out: dict[str, dict[str, str]] = {}
    for rname, contract, region_dir in sources:
        props = contract.get('props')
        if isinstance(props, list) and props:
            pics = _prop_pictures(pack_path, region_dir, props)
            if pics:
                out[rname] = pics
    return out


def _player_book_icons(web_dir: Path) -> dict[str, str]:
    """The 'found on the map' and 'given by someone' icons, inlined.

    A book with no picture is invisible: a map book is a floor tile you
    step on and a gifted one is only a line of text. The woven player draws
    these where a book can be found, so a player can see it.
    """
    import base64

    out: dict[str, str] = {}
    for kind, name in (('map', 'found-map'), ('resident', 'found-given')):
        f = web_dir / 'art' / 'icons' / 'library' / f'{name}.webp'
        if f.is_file():
            out[kind] = 'data:image/webp;base64,' + base64.b64encode(f.read_bytes()).decode('ascii')
    return out


def _baked_skin(pack: Path, world: dict) -> dict | None:
    """The pack's skin as one object with every picture inlined.

    `world["skin"]` names a folder inside the pack (design/ui-skin.md).
    Each picture a part names (`file`, `hover`, `pressed`, ...) becomes
    a data URI, so the woven file stays one offline file; `slice` and
    `hotspot` are kept as written. The optional `backdrop` is inlined the
    same way, and the optional `fonts` (the families the engine bundles)
    are carried through as written. A pack that names no skin - or whose
    skin cannot be read - bakes the literal `null` (rule 6: no skin, no
    change).
    """
    import base64

    skin_rel = world.get('skin')
    if not isinstance(skin_rel, str) or not skin_rel.strip():
        return None
    base = os.path.realpath(str(pack))
    skin_dir = _inside(base, skin_rel)
    if skin_dir is None or not os.path.isdir(skin_dir):
        return None
    skin_json = os.path.join(skin_dir, 'skin.json')
    if not os.path.isfile(skin_json):
        return None
    try:
        data = json.loads(Path(skin_json).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    out: dict = {k: data[k] for k in ('name', 'credit', 'ink', 'fonts') if k in data}
    backdrop = data.get('backdrop')
    if isinstance(backdrop, str) and backdrop.strip():
        target = _inside(skin_dir, backdrop)
        suffix = os.path.splitext(backdrop)[1].lower()
        if target is not None and os.path.isfile(target) and suffix in _ART_TYPES:
            blob = base64.b64encode(Path(target).read_bytes()).decode('ascii')
            out['backdrop'] = f'data:{_ART_TYPES[suffix]};base64,{blob}'
    parts_in = data.get('parts')
    parts_out: dict = {}
    if isinstance(parts_in, dict):
        for pname, spec in parts_in.items():
            if not isinstance(spec, dict):
                parts_out[pname] = spec
                continue
            baked: dict = {}
            for key, value in spec.items():
                target = (_inside(skin_dir, value)
                          if key in SKIN_PICTURE_KEYS
                          and isinstance(value, str) and value
                          else None)
                suffix = (os.path.splitext(value)[1].lower()
                          if isinstance(value, str) else '')
                if target is not None and os.path.isfile(target) \
                        and suffix in _ART_TYPES:
                    blob = base64.b64encode(
                        Path(target).read_bytes()).decode('ascii')
                    baked[key] = f'data:{_ART_TYPES[suffix]};base64,{blob}'
                else:
                    baked[key] = value
            parts_out[pname] = baked
    out['parts'] = parts_out
    return out


# The E7 mind keys a region's `enemies` record may carry into the bake
# (ADR 0014, "Monster AI"): which group a monster belongs to, whether it
# leads that group, how far the group may walk from home, which affix
# made it an elite, and whether it is the warden. The player's reader
# (`prepareMinds`, part 420) asks the baked spawn record for `group`,
# `leader` and `warden` and `groupLeash` asks any member for `leash`, so
# a pack that wrote them into a contract's `enemies` and got them dropped
# on the way to the file had a floor where wake-all, the leash and the
# warden could never fire. Each rides along only when the record names
# it, on the same rule as `xp`, so a pack that names none bakes the exact
# bytes it always did.
MIND_KEYS = ('group', 'leader', 'leash', 'elite', 'warden')


def weave_html(pack: Path, *, pool: dict | None = None,
               template: str | None = None, doc: dict | None = None) -> str:
    """Weave a pack into the single shareable HTML document.

    The packaging core behind `ratatoskr weave` and the served
    builder's "Make shareable file" button. Loads the resolved world
    (raw root folded under the validator's unified shape, acts carried
    through), folds it over web/packaged.html, and returns the finished
    document as a string. No writes and no model calls - `pool`, when
    present, is caller-supplied already-generated content.

    `template` folds the same substitutions over a different template -
    the `.vefr` exporter (ADR 0019) hands a JSON skeleton whose values
    are the very same baked ones, so an archive and a woven HTML of one
    pack are one game. `doc`, when a dict is passed, is filled with the
    four page-level values the template folds in around the data
    (`title`, `tagline`, `title_art_img`, `fonts_css`) so a Player that
    loads an archive wears the same face. Both are additive: with neither
    argument this weaves exactly what it always wove.
    """
    # A pack that carries a Blueprint refuses to weave when its
    # generated output is stale or invalid, with the same sentence
    # `vefr check` prints. A pack with neither file is unchanged (the
    # check is two existence probes and nothing else).
    from . import blueprint
    blueprint_errors = blueprint.check_errors(pack)
    if blueprint_errors:
        raise blueprint.BlueprintRefusal(' '.join(blueprint_errors))

    import json as _json

    # The player template reads town geometry, speakers, and creed off
    # VEFR_WORLD - all three live in acts/<id>/ for an acts-shape pack
    # and are invisible to the raw root file (a raw-only bake left the
    # town canvas blank and the tagline on its generic default).
    # load_pack is the validator's unified shape; it carries the
    # gold_rule read-fallback through creed_from, and raw root fields
    # ride along underneath.
    world = {
        **_json.loads((pack / 'world.json').read_text(encoding='utf-8')),
        **load_pack(pack),
    }
    # The packaged player reads the acts contract (verbs, floor,
    # tone, ruleset, cooking) straight off the baked world. The
    # validator's unified shape doesn't carry acts, so pull them
    # from the loader when the pack resolves under a worlds root;
    # packs woven from elsewhere keep the old behavior (defaults).
    if not world.get('acts'):
        from .world import load_world as _load_world
        try:
            loaded = _load_world(pack)
        except Exception:
            loaded = {}
        if loaded.get('acts'):
            world['acts'] = loaded['acts']
            world.setdefault('_current_act', 0)
    # The pack's item catalog: the bag shows a name and draws a sprite;
    # a drop that names a missing item is dropped from what is baked.
    items = _player_items(world)
    item_ids = set(items)
    title = world.get('title', pack.name)
    logbok = (pack / 'logbok.md').read_text(encoding='utf-8') if (pack / 'logbok.md').exists() else ''
    ledger = (pack / 'ledger.md').read_text(encoding='utf-8') if (pack / 'ledger.md').exists() else ''
    voices = {}
    if (pack / 'voices').exists():
        # Sorted: the woven file must not depend on the order the disk lists files.
        for sf in sorted((pack / 'voices').glob('*.md')):
            if sf.name.endswith('.fragments.md'):
                continue
            voices[sf.stem] = sf.read_text(encoding='utf-8')
    # The offline whisper banks: per-speaker fragments the composer
    # re-splices when a package has no pool and no model. The same
    # convention walk as voice discovery (pack root + act regions).
    from .world import fragments_for_pack
    fragments = fragments_for_pack(pack)
    # The pack's own books, baked into the file so a phone player can
    # find and read them offline. Fixed key order (the reader's shape);
    # `extra` is the pack's private notes and stays out of the file.
    # `region` scopes a map book to the map it lies on.
    from .library import found_words, load_library
    books = []
    for b in load_library(pack):
        extra = b.get('extra') if isinstance(b.get('extra'), dict) else {}
        entry = {k: b.get(k) for k in
                 ("id", "title", "kind", "found", "at", "speaker", "when", "pages", "region")}
        # A book pinned to a generated floor names where on it to lie; the
        # descent part chooses the tile each run (delve.place_books).
        if b.get('place'):
            entry['place'] = b['place']
        # `chest: yes` in a book's front matter puts it in a chest: the
        # player opens the chest rather than stepping on the book.
        entry['chest'] = str(extra.get('chest', '')).strip().lower() in ('yes', 'true', '1')
        # A chest may also hold items: `drops` is a comma-separated list
        # of catalog ids in the front matter, read from `extra` like
        # `chest`. Ids the catalog does not name are dropped.
        entry['drops'] = _drop_ids(extra.get('drops', ''), item_ids)
        entry['found_words'] = found_words(b)
        books.append(entry)

    # The act's regions, doors, and grouped speakers. A single-region
    # pack bakes one region and empty transitions; the woven player's
    # town stays exactly what VEFR_WORLD carried (the visual baseline
    # must not move). Regions come from the act's own region dirs
    # (map_text + contract); a pack woven without acts falls back to
    # the unified `town`.
    first_act = (world.get('acts') or [{}])[0]
    if not isinstance(first_act, dict):
        first_act = {}

    def _region_entry(contract: dict, map_text: str) -> dict:
        entry = {
            'map': [ln for ln in (map_text or '').splitlines() if ln.strip()],
            'legend': contract.get('legend', {}),
            'pois': contract.get('pois', {}),
            'poi_text': contract.get('poi_text', {}),
            'hero_start': contract.get('hero_start', [1, 1]),
            'sanctuary_tiles': contract.get('sanctuary_tiles', []),
            'watch': contract.get('watch', {}),
            'water_by_phase': contract.get('water_by_phase', {}),
            'flood_tiles': contract.get('flood_tiles', []),
            'tile': contract.get('tile', 32),
            'fog': contract.get('fog'),
            'bg': contract.get('bg', '#131311'),
            'hero_color': contract.get('hero_color', '#e8e5df'),
            'speaker_color': contract.get('speaker_color', '#8b939c'),
            'speaker_head': contract.get('speaker_head', '#d8d5df'),
        }
        if contract.get('props'):
            entry['props'] = contract['props']
        return entry

    regions: dict = {}
    act_regions = first_act.get('regions')
    if isinstance(act_regions, dict):
        for rname, rdata in act_regions.items():
            rdata = rdata if isinstance(rdata, dict) else {}
            regions[rname] = _region_entry(
                rdata.get('contract', {}) or {}, rdata.get('map_text', ''))
    if not regions:
        # No acts on disk (raw/out-of-root pack): the unified town is
        # the single region.
        town = world.get('town') if isinstance(world.get('town'), dict) else {}
        rname = world.get('_region') or 'town'
        regions[rname] = _region_entry(town, '\n'.join(town.get('map', [])))
    else:
        # A synthesized flat act keeps its geometry in the unified town
        # (the region dirs have no contract); fill the first region from
        # it so VEFR_REGIONS is truthful for flat packs too.
        first = next(iter(regions))
        town = world.get('town') if isinstance(world.get('town'), dict) else {}
        if not regions[first].get('map') and town.get('map'):
            regions[first] = _region_entry(town, '\n'.join(town.get('map', [])))

    # The living hazards of each region, from its contract's `enemies`
    # list. The baked shape is fixed (id, name, at, hp, atk, sprite) so
    # the player never has to guess; `sight` rides along only when the
    # contract names it (the player defaults to 6). A region that names
    # none - or has no contract - bakes [].
    enemies_by_region: dict[str, list] = {rname: [] for rname in regions}
    if isinstance(act_regions, dict):
        for rname, rdata in act_regions.items():
            if rname not in enemies_by_region:
                continue
            rdata = rdata if isinstance(rdata, dict) else {}
            contract = rdata.get('contract')
            contract = contract if isinstance(contract, dict) else {}
            listed = contract.get('enemies')
            listed = listed if isinstance(listed, list) else []
            out = []
            for e in listed:
                if not isinstance(e, dict):
                    continue
                entry = {
                    'id': e.get('id'),
                    'name': e.get('name'),
                    'at': e.get('at'),
                    'hp': e.get('hp'),
                    'atk': e.get('atk'),
                    'sprite': e.get('sprite', ''),
                    'drops': _drop_ids(e.get('drops', []), item_ids),
                }
                if 'sight' in e:
                    entry['sight'] = e.get('sight')
                # `xp` (design/growth.md) rides along only when the
                # contract names it, so a pack without one bakes the
                # exact bytes it always did.
                if 'xp' in e:
                    entry['xp'] = e.get('xp')
                # The five E7 mind keys, on the same rule as `xp` and
                # for the same reason: the player reads `group`,
                # `leader`, `leash` and `warden` off the baked spawn
                # record (parts 410/420), and nothing else tells it a
                # spawn is an elite. A pack that names none of them -
                # every pack but an E7 one - bakes the exact bytes it
                # always did, so a weave is unchanged by this loop.
                for key in MIND_KEYS:
                    if key in e:
                        entry[key] = e.get(key)
                out.append(entry)
            enemies_by_region[rname] = out

    # The hero's own numbers and wake point. `hp`/`atk` default to 6/2;
    # `wake` defaults to the act's first region at its hero_start. A
    # wake that names a region which does not exist is dropped, and a
    # wake tile that is missing or not walkable falls back to that
    # region's hero_start - the baked point is always real.
    player = world.get('player') if isinstance(world.get('player'), dict) else {}
    hero_hp = player.get('hp') if isinstance(player.get('hp'), int) else 6
    hero_hp = hero_hp if hero_hp > 0 else 6
    hero_atk = player.get('atk') if isinstance(player.get('atk'), int) else 2
    hero_atk = hero_atk if hero_atk > 0 else 2
    wake_region = next(iter(regions), 'town')
    wake_at = list(regions.get(wake_region, {}).get('hero_start') or [1, 1])
    wake = player.get('wake')
    if isinstance(wake, dict) and wake.get('region') in regions:
        wake_region = wake['region']
        region = regions[wake_region]
        at = wake.get('at')
        if (isinstance(at, list) and len(at) == 2
                and all(isinstance(v, int) for v in at)
                and _tile_walkable(region.get('map', []), region.get('legend', {}),
                                   at[0], at[1])
                and not prop_blocks(region.get('props'), at[0], at[1])):
            wake_at = [at[0], at[1]]
        else:
            wake_at = list(region.get('hero_start') or [1, 1])
    # The hero's purse: `world.player.gold` (default 0). It is the
    # starting gold a shop trades against; the player keeps it per world.
    hero_gold = player.get('gold')
    if not isinstance(hero_gold, int) or isinstance(hero_gold, bool) or hero_gold < 0:
        hero_gold = 0
    hero = {'hp': hero_hp, 'atk': hero_atk, 'gold': hero_gold,
            'wake': {'region': wake_region, 'at': wake_at}}
    # The shelf this game came from, when the pack names one: the woven
    # player is one offline file, but it keeps a way back to the library
    # page it was published from. Only an http(s) URL is baked - the
    # player draws it as a link, and a scheme it cannot follow is no link
    # at all. A pack with no `library_url` bakes no key, so every
    # existing pack's bytes are unchanged.
    library_url = player.get('library_url')
    if isinstance(library_url, str) and library_url.strip().lower().startswith(
            ('http://', 'https://')):
        hero['library_url'] = library_url.strip()

    transitions = first_act.get('transitions')
    if transitions is None:
        transitions = world.get('transitions', [])
    if not isinstance(transitions, list):
        transitions = []

    first_region_name = next(iter(regions), 'town')
    act_speakers = first_act.get('speakers')
    if not isinstance(act_speakers, dict):
        act_speakers = world.get('speakers', {}) or {}
    speaker_groups: dict = {}
    for key, spec in act_speakers.items():
        if not isinstance(spec, dict):
            continue
        rname = spec.get('region', first_region_name)
        speaker_groups.setdefault(rname, {})[key] = {
            'name': spec.get('name', key),
            'at': spec.get('at', [0, 0]),
            'seeds': spec.get('seeds', {}),
            'voice_file': spec.get('voice_file', ''),
        }

    # The shopkeepers: a speaker whose spec carries `"shop": "true"`
    # keeps the shop of its region. Baked as a small {region: key} map
    # rather than a per-speaker flag, so a speaker entry's shape stays
    # exactly what it always was (an old pack bakes no shops at all).
    # One shop per region; the first shopkeeper named wins.
    shops: dict = {}
    for key, spec in act_speakers.items():
        if not isinstance(spec, dict):
            continue
        if str(spec.get('shop', '')).strip().lower() not in ('true', 'yes', '1'):
            continue
        rname = spec.get('region', first_region_name)
        if rname in regions and rname not in shops:
            shops[rname] = key

    # Where the game begins: the act's `start` when it names a real
    # region, else empty (the player falls back to the first region).
    start = first_act.get('start')
    if not (isinstance(start, dict) and isinstance(start.get('region'), str)
            and start.get('region') in regions):
        start = {}

    template_candidates = _template_candidates()
    template_path = next(
        (p for p in template_candidates if p.exists()), template_candidates[0])
    if template is None:
        template = template_path.read_text(encoding='utf-8')

    tagline = world.get('creed') or 'the loom is strung; the world provides the thread.'
    out_html = template
    # Read once: the skin decides which families the woven file carries, and
    # the same object is what window.VEFR_SKIN gets below.
    skin = _baked_skin(pack, world)
    fonts_css = _player_fonts_css(template_path.parent, (skin or {}).get('fonts') or {})
    title_art_img = _player_title_art(pack, world, template_path.parent)
    # The archive Player's page-level values, kept beside the ones folded
    # into the template: same four values, one read (ADR 0019).
    if doc is not None:
        doc.update({'title': title, 'tagline': tagline,
                    'title_art_img': title_art_img, 'fonts_css': fonts_css})
    out_html = out_html.replace('{{fonts_css}}', fonts_css)
    out_html = out_html.replace('{{title_art_img}}', title_art_img)
    out_html = out_html.replace('{{title}}', title)
    out_html = out_html.replace('{{tagline}}', tagline)
    out_html = out_html.replace('{{world_json}}', _json.dumps(world, ensure_ascii=False))
    out_html = out_html.replace('{{tiles_json}}',
                                _json.dumps(_player_tiles(world, template_path.parent,
                                                          pack),
                                            ensure_ascii=False))
    out_html = out_html.replace('{{region_tiles_json}}',
                                _json.dumps(_player_region_tiles(world, template_path.parent,
                                                                 pack),
                                            ensure_ascii=False))
    out_html = out_html.replace('{{tile_edges_json}}',
                                _json.dumps(_player_tile_edges(world, template_path.parent,
                                                               pack),
                                            ensure_ascii=False))
    out_html = out_html.replace('{{sprites_json}}',
                                _json.dumps(_player_sprites(pack, world), ensure_ascii=False))
    out_html = out_html.replace('{{sprite_sheets_json}}',
                                _json.dumps(_player_sprite_sheets(pack, world), ensure_ascii=False))
    out_html = out_html.replace('{{sprite_scale_json}}',
                                _json.dumps(_sprite_scales(world), ensure_ascii=False))
    out_html = out_html.replace('{{items_json}}',
                                _json.dumps(items, ensure_ascii=False))
    out_html = out_html.replace('{{door_json}}',
                                _json.dumps(_player_door(template_path.parent)))
    out_html = out_html.replace('{{way_icons_json}}',
                                _json.dumps(_player_way_icons(pack), ensure_ascii=False))
    out_html = out_html.replace('{{region_way_icons_json}}',
                                _json.dumps(_player_region_way_icons(world, pack),
                                            ensure_ascii=False))
    out_html = out_html.replace('{{prop_pics_json}}',
                                _json.dumps(_player_prop_pics(world, pack),
                                            ensure_ascii=False))
    out_html = out_html.replace('{{chest_json}}',
                                _json.dumps(_player_chest(template_path.parent)))
    out_html = out_html.replace('{{book_icons_json}}',
                                _json.dumps(_player_book_icons(template_path.parent), ensure_ascii=False))
    out_html = out_html.replace('{{logbok_json}}', _json.dumps(logbok))
    out_html = out_html.replace('{{ledger_json}}', _json.dumps(ledger))
    out_html = out_html.replace('{{voices_json}}', _json.dumps(voices, ensure_ascii=False))
    out_html = out_html.replace('{{fragments_json}}', _json.dumps(fragments, ensure_ascii=False))
    # The pack's own grammars (optional): the offline sentence recipes
    # the woven file expands with no model and no pool. A pack with
    # none bakes an empty block, which is exactly the silence it has
    # always had.
    out_html = out_html.replace('{{grammars_json}}',
                                _json.dumps(world.get('grammars') or {},
                                            ensure_ascii=False))
    # The four optional rule catalogs, beside the other baked pack data.
    # A pack that declares none of them bakes the literal `null` four
    # times (every existing pack's file, unchanged); a pack that
    # declares any gets the full four-key shape with entries that
    # cannot run already dropped (_player_rules).
    rules_pack = _player_rules(world)
    out_html = out_html.replace(
        '{{rules_json}}',
        _json.dumps(rules_pack['rules'] if rules_pack else None,
                    ensure_ascii=False))
    out_html = out_html.replace(
        '{{flags_json}}',
        _json.dumps(rules_pack['flags'] if rules_pack else None,
                    ensure_ascii=False))
    out_html = out_html.replace(
        '{{claims_json}}',
        _json.dumps(rules_pack['claims'] if rules_pack else None,
                    ensure_ascii=False))
    out_html = out_html.replace(
        '{{people_json}}',
        _json.dumps(rules_pack['people'] if rules_pack else None,
                    ensure_ascii=False))
    # The pack's optional sticker album (design/album.md): the stickers
    # to earn, baked beside the rule data. A pack that declares none
    # bakes the literal `null` (every existing pack's file, unchanged);
    # an entry that could never earn is dropped whole (_player_album).
    out_html = out_html.replace('{{album_json}}',
                                _json.dumps(_player_album(world),
                                            ensure_ascii=False))
    # The pack's optional sound set (docs/guides/rulesets.md): the
    # literal `null` when the pack declares none, so every existing
    # pack weaves exactly as it did.
    out_html = out_html.replace('{{sound_json}}',
                                _json.dumps(world.get('sound'),
                                            ensure_ascii=False))
    out_html = out_html.replace('{{library_json}}', _json.dumps(books, ensure_ascii=False))
    out_html = out_html.replace('{{regions_json}}', _json.dumps(regions, ensure_ascii=False))
    # The pack's descent block (slice E1), resolved and with the engine's
    # own dungeon legend beside it, so the player draws a floor out of the
    # same tiles the baked floors use without inventing any of its own. A
    # pack that declares no descent bakes the literal `null`, and the
    # player grows no regions. The pack's Blueprint goes in beside them
    # too (ADR 0014): a Section names a family by id, so a floor that
    # cannot reach the Blueprint cannot say what that family is.
    from . import delve as delve_mod
    descent = delve_mod.descent_of(world, pack)
    if descent:
        descent = {**descent, 'legend': delve_mod.LEGEND,
                   'blueprint': delve_mod.blueprint_of(pack)}
        # The pack's stamps (ADR 0013), the same records `vefr check` sweeps
        # with, so a play floor carries the stamped rooms - the warden hall and
        # the vault among them - that the check walked. No stamps directory,
        # no key: such a pack weaves exactly as it did.
        stamp_dir = Path(pack) / 'stamps'
        if stamp_dir.is_dir():
            from . import stamps as stamps_mod
            descent['stamps'] = stamps_mod.load(stamp_dir)
        # The Sections' own ground (vefr#349): the pictures behind each
        # Section's `tiles`, resolved now and keyed by Section id, so a
        # play floor is drawn with its own Section's ground instead of the
        # pack's global tile set. A pack whose Sections name no `tiles`
        # bakes an empty table and draws exactly what it drew before.
        descent['section_tiles'] = _descent_section_tiles(
            descent, template_path.parent, pack)
        # The Sections' decor pictures (vefr#442), keyed by Section id and
        # then by picture name. A pack whose Sections name no decor bakes no
        # key, and weaves exactly as it did.
        section_decor = _descent_section_decor(descent, pack)
        if section_decor:
            descent['section_decor'] = section_decor
    out_html = out_html.replace('{{descent_json}}',
                                _json.dumps(descent or None, ensure_ascii=False))
    # The pack's optional town states (ADR 0015, E8c): the regions whose
    # look follows a story flag, each `use` an ordinary authored region
    # baked above with every other region. A pack that declares none bakes
    # the literal `null` and every one of its regions plays as it always
    # did.
    out_html = out_html.replace('{{town_states_json}}',
                                _json.dumps(world.get('town_states')
                                            if 'town_states' in world else None,
                                            ensure_ascii=False))
    out_html = out_html.replace('{{transitions_json}}',
                                _json.dumps(transitions, ensure_ascii=False))
    out_html = out_html.replace('{{speakers_json}}',
                                _json.dumps(speaker_groups, ensure_ascii=False))
    out_html = out_html.replace('{{shops_json}}',
                                _json.dumps(shops, ensure_ascii=False))
    out_html = out_html.replace('{{enemies_json}}',
                                _json.dumps(enemies_by_region, ensure_ascii=False))
    out_html = out_html.replace('{{hero_json}}', _json.dumps(hero, ensure_ascii=False))
    # The pack's optional skin (design/ui-skin.md): every picture inlined
    # as a data URI so the woven file stays one offline file. A pack
    # that names none bakes the literal `null`.
    out_html = out_html.replace('{{skin_json}}',
                                _json.dumps(skin, ensure_ascii=False))
    # The optional growth block (design/growth.md) beside the hero. A
    # pack that declares none bakes the literal `null`.
    out_html = out_html.replace('{{growth_json}}',
                                _json.dumps(world.get('growth'), ensure_ascii=False))
    # The pack's optional spells block (ADR 0018): the schools it teaches
    # and the spells in them, each with the level it is learned at. A pack
    # that declares none carries no `window.VEFR_SPELLS` line at all - the
    # additive rule the identify reader follows (test_identify.py's
    # `test_the_reader_needs_no_new_baked_block`), so a pack that names no
    # spells weaves byte for byte what it wove before this slice, and the
    # player reads the missing global as no spells.
    spells = _player_spells(world)
    if spells is None:
        out_html = out_html.replace(
            'window.VEFR_SPELLS = {{spells_json}};\n', '')
    else:
        out_html = out_html.replace('{{spells_json}}',
                                    _json.dumps(spells, ensure_ascii=False))
    out_html = out_html.replace('{{start_json}}', _json.dumps(start, ensure_ascii=False))
    # The woven pool: real generations baked into the file, so a
    # player with no LLM endpoint still hears the world. Empty unless
    # the caller generated one (the CLI's --pool; the web route never).
    out_html = out_html.replace('{{pool_json}}', _json.dumps(pool or {}, ensure_ascii=False))
    return out_html


def build_web(pack: Path, out_dir: Path, *, out_name: str | None = None,
              pool: dict | None = None) -> Path:
    """Weave a pack and write it into `out_dir`; return the file path.

    The packaging core both `ratatoskr weave` (cmd_build_web) and
    POST /api/builder/weave call, so the CLI and the served UI ship
    byte-identical files. `out_dir` is a directory the caller owns;
    the name defaults to <pack>-<date>.html and is overridable with
    out_name. No caller-supplied output path is ever accepted here.
    """
    from datetime import date

    pack = Path(pack)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = out_name or f'{pack.name}-{date.today().isoformat()}.html'
    out_path = out_dir / name
    out_path.write_text(weave_html(pack, pool=pool), encoding='utf-8')
    return out_path


def _resolve_pack(value) -> Path:
    """Where a `--pack NAME` or `--pack PATH` argument points.

    A bare name resolves under `worlds/`; anything path-shaped is made
    absolute, so `load_world` finds an out-of-root pack instead of
    joining a relative path under `worlds/` (which dropped acts). Shared
    by every verb that weaves or archives a pack, so they all name the
    same pack the same way.
    """
    if value is None:
        return pack_root() / 'worlds' / world_name()
    p = Path(value)
    if p.is_absolute() or '/' in str(value):
        return (p if p.is_dir() else p.parent).resolve()
    return pack_root() / 'worlds' / p


def _woven_pool(pack: Path, pool_n: int) -> dict:
    """Real generations to bake in as the offline fallback pool.

    Zero by default - the pool costs real generation time at weave - and
    `pack` is restored afterwards: weaving is a visitor in this world.
    """
    if not pool_n:
        return {}
    import os as _os

    from . import pool as pool_mod

    old_world_env = _os.environ.get('VEFR_WORLD')
    pool_mod.ensure_current_world(pack.name)
    try:
        print(f'weaving the pool: ~{pool_n} real generations per '
              'combination - this takes a few minutes against the '
              'live model...')
        pool = pool_mod.build_pool(
            samples=pool_n,
            pack_name=pack,
            progress=lambda combo, count: print(f'  {combo}: {count}'),
        )
    finally:
        if old_world_env is None:
            _os.environ.pop('VEFR_WORLD', None)
        else:
            _os.environ['VEFR_WORLD'] = old_world_env
    total = sum(len(v) for v in pool.values())
    print(f'pool woven: {total} lines across {len(pool)} combinations')
    return pool


def cmd_archive(args) -> int:
    """`vefr archive` - carry a world as one portable `.vefr` file (vefr#455).

    Two jobs behind one door (ADR 0019):

      vefr archive --pack NAME           write dist/<name>.vefr and the
                                         shared Player that opens it
      vefr archive --inspect FILE.vefr   validate one and print its manifest

    `vefr weave` is untouched: the self-contained HTML is still woven,
    and the archive is written beside it rather than instead of it. A
    pack that would refuse the weave - a stale Blueprint - refuses the
    archive with the same sentence, because the archive is woven by the
    same code.
    """
    from . import vefrfile

    if args.inspect:
        try:
            loaded = vefrfile.load_archive(args.inspect)
        except vefrfile.ArchiveRefusal as exc:
            print(f'refusing {args.inspect}: {exc}')
            return 1
        manifest = loaded.manifest
        if args.json:
            print(json.dumps(manifest, ensure_ascii=False, indent=1))
            return 0
        game, runtime = manifest['game'], manifest['runtime']
        print(f"{game['title']} ({game['id']})")
        print(f"  manifest schema {manifest['schema_version']}, written by "
              f"vefr {manifest['engine_version']}, "
              f"player contract {runtime['player_contract']}")
        print(f"  {len(loaded.globals)} game globals, "
              f"{len(manifest.get('capabilities') or [])} capabilities, "
              f"network {manifest.get('network', {}).get('policy')}")
        print(f"  licence: {manifest.get('provenance', {}).get('license')}")
        print('  digest    bytes  path')
        for row in manifest['files']:
            print(f"  {row['sha256'][:12]}  {row['bytes']:>8}  {row['path']}")
        return 0

    pack = _resolve_pack(args.pack)
    if not (pack / 'world.json').exists():
        print(f'pack not found at {pack}; pass --pack NAME or set VEFR_WORLD')
        return 1

    pool = _woven_pool(pack, getattr(args, 'pool', 0) or 0)
    out = Path(args.out) if args.out else Path('dist') / f'{pack.name}.vefr'
    player = None if args.no_player else Path(
        args.player or out.with_name(out.stem + '.player.html'))
    try:
        manifest = vefrfile.build_archive(pack, out, pool=pool, player=player)
    except vefrfile.ArchiveRefusal as exc:
        print(str(exc))
        return 1

    size_kb = out.stat().st_size / 1024
    print(f'wrote {out} ({size_kb:.1f} KB)')
    if player is not None:
        print(f'wrote {player} (the shared Player; it opens {out.name})')
        print('  open them together from any browser, or open the Player '
              'alone and drop the .vefr on it.')
    for line in (manifest.get('provenance', {}).get('not_carried') or []):
        print(f'  not carried: {line}')
    print(f"inspect it any time: vefr archive --inspect {out}")
    return 0


def cmd_build_web(args) -> int:
    """Bundle worlds/<name>/ + web/packaged.html into one self-contained file.

    The player opens the file, points it at any OpenAI-compatible LLM
    endpoint, and plays. No Python, no server, no internet: the pack's
    logbok, ledger, voices, and town are inlined as JSON inside the
    HTML. Distributable: send it as a single email attachment, host
    on any static site, open from a phone's Files app.

    The 'bones' shape carries through here. Whatever the engine reads
    from the pack on disk, the bundled file reads from a JS object.
    The packaging itself lives in weave_html/build_web so the served
    builder shares one implementation; this wrapper keeps the CLI's
    flags, output paths, and console lines unchanged.
    """
    # Bare name -> resolve under worlds/; any path -> made absolute,
    # so load_world below finds an out-of-root pack instead of
    # joining a relative path under worlds/ (which dropped acts).
    pack = _resolve_pack(args.pack)

    if not (pack / 'world.json').exists():
        print(f'pack not found at {pack}; pass --pack NAME or set VEFR_WORLD')
        return 1

    # The woven pool: real generations baked into the file, so a
    # player with no LLM endpoint still hears the world. Zero by
    # default - the pool costs real generation time at weave.
    pool = _woven_pool(pack, getattr(args, 'pool', 0) or 0)

    if args.out:
        out_path = Path(args.out)
        out_dir, out_name = out_path.parent, out_path.name
    else:
        out_dir, out_name = Path('dist'), None
    out_path = build_web(pack, out_dir, out_name=out_name, pool=pool)
    size_kb = out_path.stat().st_size / 1024
    print(f'wrote {out_path} ({size_kb:.1f} KB)')
    print('open it in any browser to play: offline, or connected to a model.')

    # Optional: also write <name>-<date>.tree.md alongside the HTML,
    # weaving every dev-UI tab into one document. The vault and
    # journal come from either --vault/--journal paths, the live
    # game's HTTP API (--from-live), or the env-driven defaults.
    # If nothing is reachable the build still succeeds, just without
    # play history.
    if args.with_bundle:
        from . import forge as _forge_mod, journal as _journal_mod
        from .export import export_story as _render

        # Pull vault + journal to local temp files. The export module
        # reads from disk paths only, so we materialize whatever source
        # we pick into the same shape.
        import tempfile as _tmp
        vault_path = Path(args.vault) if args.vault else None
        journal_path = Path(args.journal) if args.journal else None

        if args.from_live:
            # Fetch the live deployment's vault and journal over HTTP.
            import json as _json
            import urllib.request as _ur
            url = args.from_live.rstrip("/")
            with _ur.urlopen(f"{url}/api/vault", timeout=15) as r:
                vault_data = _json.loads(r.read().decode("utf-8")).get("items", [])
            with _ur.urlopen(f"{url}/api/journal", timeout=15) as r:
                journal_data = _json.loads(r.read().decode("utf-8")).get("entries", [])
            with _tmp.NamedTemporaryFile("w", suffix=".json", delete=False) as vf:
                _json.dump(vault_data, vf)
                vault_tmp = Path(vf.name)
            with _tmp.NamedTemporaryFile("w", suffix=".json", delete=False) as jf:
                _json.dump(journal_data, jf)
                journal_tmp = Path(jf.name)
            vault_path = vault_tmp
            journal_path = journal_tmp
            print(f"  pulled vault ({len(vault_data)} items) + "
                  f"journal ({len(journal_data)} entries) from {url}")
        else:
            from .paths import world_scoped as _scoped
            vault_path = vault_path or _scoped(_forge_mod.VAULT, pack.name)
            journal_path = journal_path or _scoped(_journal_mod.JOURNAL, pack.name)

        old_vault, old_journal = _forge_mod.VAULT, _journal_mod.JOURNAL
        _forge_mod.VAULT = vault_path
        _journal_mod.JOURNAL = journal_path
        _forge_mod.SCOPE_BY_WORLD = _journal_mod.SCOPE_BY_WORLD = False
        try:
            bundle_md = _render()
        finally:
            _forge_mod.VAULT = old_vault
            _journal_mod.JOURNAL = old_journal
            _forge_mod.SCOPE_BY_WORLD = _journal_mod.SCOPE_BY_WORLD = True

        bundle_path = out_path.with_name(out_path.stem + '.tree.md')
        bundle_path.write_text(bundle_md, encoding="utf-8")
        bundle_kb = bundle_path.stat().st_size / 1024
        print(f"wrote {bundle_path} ({bundle_kb:.1f} KB)")
        print("  one section per dev UI tab, woven from "
              f"{vault_path.name} + {journal_path.name}.")
    return 0

def cmd_deploy(args) -> int:
    """Ship this checkout to the deploy host.

    Behavior, in order:

      1. `--init` writes deploy.toml.example + the deploy guide,
         then exits. Does not touch the deploy host.
      2. Resolve the deploy host from --deploy-host / env. Refuse
         to run with the silent 'bazzite' default; force the user
         to declare their topology.
      3. Pre-flight (unless --skip-tests): the pytest suite +
         `norns validate --pack sample-world`. A broken main never
         reaches bazzite.
      4. rsync the checkout (DEPLOY_EXCLUDES hides .venv, caches,
         .git).
      5. `podman build` UNLESS the remote image's `vefr.engine_sha`
         label already matches the local HEAD (--rebuild forces it).
      6. `systemctl --user restart vefr` + ensure the ro/rw named
         volumes exist.
      7. /api/health probe + `maplab verify` (unless --no-health).

    Image name is `VEFR_DEPLOY_IMAGE` (default `localhost/vefr:latest`).
    The remote SHA check reads the `vefr.engine_sha` label that the
    Containerfile writes so a no-op deploy is one rsync + one
    restart, not a full image rebuild.
    """
    root = need_repo()

    if args.init:
        return _deploy_init(root)

    cfg = _deploy_toml(root)
    host = args.deploy_host
    declared_env = bool(os.environ.get('VEFR_DEPLOY_HOST'))
    declared_toml = 'host' in cfg
    if host == DEFAULT_DEPLOY_HOST and not declared_env and declared_toml:
        # --flag and env are silent: deploy.toml is the third voice.
        host = cfg['host']
    if not host and not declared_env and not declared_toml:
        # The silent default of 'bazzite' was a leak: a fresh
        # checkout would `ssh bazzite` and explode against a host
        # it cannot resolve. Force the operator to declare.
        print(
            'refusing to deploy: the deploy host is not declared.\n'
            '\n'
            '  export VEFR_DEPLOY_HOST=<your-host-or-ssh-alias>\n'
            '  uv run ratatoskr ferry deploy\n'
            '\n'
            'First time?  `uv run ratatoskr ferry deploy --init` writes\n'
            'deploy.toml.example + docs/guides/deploy.md to this checkout,\n'
            'or add host = "<your-host>" to deploy.toml.'
        )
        return 2

    url = args.url
    image = (os.environ.get('VEFR_DEPLOY_IMAGE')
             or cfg.get('image') or 'localhost/vefr:latest')

    if not args.skip_tests:
        if sh(('uv', 'run', '--group', 'test', 'pytest', '-q')).returncode:
            print('pre-flight: pytest failed; refusing to deploy')
            return 1
        if sh(('uv', 'run', '--group', 'test', 'norns', 'validate',
               '--pack', 'sample-world')).returncode:
            print('pre-flight: sample-world validate failed; refusing to deploy')
            return 1

    excludes = []
    for e in DEPLOY_EXCLUDES:
        excludes += ['--exclude', e]
    if sh(('rsync', '-a', '--delete', *excludes, f'{root}/',
           f'{host}:~/vefr/')).returncode:
        return 1

    if not args.rebuild:
        head_sha = subprocess.run(('git', '-C', str(root), 'rev-parse', 'HEAD'),
                                  capture_output=True, text=True).stdout.strip()
        inspect = subprocess.run(
            ('ssh', host, f'podman inspect --format "{{{{index .Config.Labels \\"vefr.engine_sha\\"}}}}" {image}'),
            capture_output=True, text=True)
        remote_sha = inspect.stdout.strip()
        if remote_sha and remote_sha == head_sha:
            print(f'image {image} already at HEAD ({head_sha[:12]}); skipping build')
        else:
            args.rebuild = True  # fall through to build below

    if args.rebuild:
        head_sha = subprocess.run(('git', '-C', str(root), 'rev-parse', 'HEAD'),
                                  capture_output=True, text=True).stdout.strip()
        if sh(('ssh', host,
               f'cd ~/vefr && podman build -q -t {image} '
               f'--build-arg ENGINE_SHA={head_sha} .')).returncode:
            return 1
    if sh(('ssh', host, 'systemctl --user restart vefr')).returncode:
        return 1

    # The ro + rw volumes may not exist on a fresh deploy host. The
    # engine boots fine without them (the image ships the template
    # at /app/worlds-template/ and an empty /app/worlds/), but the
    # canonical post-deploy state is both volumes present. Create
    # them so a `ratatoskr volumes list` from the deploy host shows
    # the right shape.
    sh(('ssh', host,
        'podman volume exists vefr-template 2>/dev/null || '
        'podman volume create vefr-template'))
    sh(('ssh', host,
        'podman volume exists vefr-worlds 2>/dev/null || '
        'podman volume create vefr-worlds'))

    if args.no_health:
        print('deployed (health check skipped). <3')
        return 0

    # Probe the deploy via an SSH-tunnelled localhost when the
    # operator didn't pass --url. This avoids depending on the dev
    # box's local DNS or /etc/hosts for the deploy host (the
    # "bazzite alias resolved to a stale LAN address" failure mode).
    import os as _os
    if url == DEFAULT_URL:
        local_port = '8820'
        ssh_args = ('ssh', '-o', 'ExitOnForwardFailure=yes',
                    '-L', f'{local_port}:127.0.0.1:8820', host)
        # No `-f`: ssh must stay in the foreground of this Popen so
        # the finally below can actually terminate it. `-fN` forks
        # past the captured pid, and every tunnel outlived its
        # deploy (the 2026-09-01 orphaned-tunnel find).
        forward = subprocess.Popen(('ssh', '-N', *ssh_args[1:]))
        try:
            probe_url = f'http://127.0.0.1:{local_port}'
        except Exception:
            forward.terminate()
            raise
        try:
            h = _wait_for_health(probe_url)
            print(f'health (via tunnel): {h}')
            from .maplab import main as maplab_main
            ok = maplab_main(['verify', '--url', probe_url])
            print('deployed. <3' if ok == 0
                  else 'deployed, but map verify flagged problems.')
            return ok
        finally:
            subprocess.run(('ssh', '-O', 'exit', host),
                           capture_output=True)
            try:
                _os.kill(forward.pid, 0)
            except (ProcessLookupError, OSError):
                pass
            forward.terminate()
    else:
        h = _wait_for_health(url)
        print(f'health: {h}')
        from .maplab import main as maplab_main
        ok = maplab_main(['verify', '--url', url])
        print('deployed. <3' if ok == 0
              else 'deployed, but map verify flagged problems.')
        return ok


def _wait_for_health(url: str, attempts: int = 20, delay: float = 1.5) -> str:
    """Poll /api/health up to `attempts` times, sleeping `delay` between.

    A fresh uvicorn + FastAPI cold start takes ~5-10s; the old fixed
    2s sleep gave up before the server was actually listening.
    Raises the last urllib error on exhaustion.
    """
    import time as _time
    last_err: Exception | None = None
    for _ in range(attempts):
        try:
            return fetch(f'{url.rstrip("/")}/api/health')
        except Exception as e:  # noqa: BLE001
            last_err = e
            _time.sleep(delay)
    raise RuntimeError(
        f'health check never went green after {attempts * delay:.0f}s: {last_err}'
    )


def _deploy_init(root: Path) -> int:
    """Write deploy.toml.example + docs/guides/deploy.md scaffolding.

    Idempotent: refuses to overwrite an existing deploy.toml.example
    unless --force is passed (currently via the CLI). Prints the
    next-step commands.
    """
    target = root / 'deploy.toml.example'
    if target.exists():
        print(f'{target} already exists; remove it first or pass --force.')
        return 1
    target.write_text(_DEPLOY_TOML_EXAMPLE, encoding='utf-8')
    print(f'wrote {target}')
    print('next:')
    print(f'  cp {target} {root / "deploy.toml"}')
    print(f'  edit {root / "deploy.toml"} to match your host')
    print(f'  export VEFR_DEPLOY_HOST=$(grep ^host {root / "deploy.toml"} | cut -d\\" -f2)')
    print('  uv run ratatoskr ferry deploy --skip-tests   # smoke test')
    return 0


_DEPLOY_TOML_EXAMPLE = '''\
# vefr deploy configuration (example - rename to deploy.toml and edit)
#
# This file is read by YOU; ratatoskr ferry deploy reads from
# environment variables. The convention below lets you keep your
# host + image names in one place and export them with one shell
# snippet. deploy.toml itself is gitignored.
#
# Required:
#   host   - SSH alias or user@host reachable from this dev box.
#            Must be reachable as `ssh <host>` without arguments.
#   image  - the podman image name/tag the quadlet runs. Defaults
#            to localhost/vefr:latest.
#
# Optional:
#   url    - the engine's HTTP endpoint (used for /api/health +
#            maplab verify after deploy). Defaults to
#            http://<host>:8820.

host  = "deploy-host"
image = "localhost/vefr:latest"
url   = "http://deploy-host:8820"
'''


# --------------------------------------------------------------- backup

def cmd_backup(args) -> int:
    root = need_repo()
    date = datetime.now(timezone.utc).strftime('%Y%m%d')
    name = f'vefr-{date}.bundle'
    tmp = Path('/tmp') / name
    if sh(('git', '-C', str(root), 'bundle', 'create', str(tmp), '--all')).returncode:
        return 1
    if sh(('scp', '-q', str(tmp), f'{args.nas_host}:{NAS_DIR}/{name}')).returncode:
        return 1
    # Clean up old bundles, preserving both historical
    # and current (vefr-*) bundles up to BUNDLE_KEEP.
    sh(('ssh', args.nas_host,
        f'cd {NAS_DIR} && ls -t vefr-*.bundle 2>/dev/null '
        f'| tail -n +{BUNDLE_KEEP + 1} | xargs -r rm -f'))
    tmp.unlink(missing_ok=True)
    listing = subprocess.run(
        ('ssh', args.nas_host, f'ls -t {NAS_DIR}/vefr-*.bundle'),
        capture_output=True, text=True).stdout.strip()
    print(f'bundles on {args.nas_host}:')
    print(listing)

    # Play history lives on the deploy host's bind-mounted volume
    # (~/<deploy-vol>/vault.json + journal.json), not in the repo -
    # the bundle alone would never preserve tonight's kept items or
    # the session journal. rsync the JSON files alongside the bundle
    # under a per-date directory so a snapshot is one date away.
    vol_remote = args.deploy_vol
    rsync = subprocess.run(
        ('ssh', args.deploy_host,
         f'mkdir -p {vol_remote} && '
         f'ls {vol_remote}/*.json 2>/dev/null'),
        capture_output=True, text=True)
    files_here = rsync.stdout.strip().splitlines()
    if files_here:
        # The deploy host may or may not have rsync; fall back to scp
        # if it doesn't. Either way, one snapshot per date is the goal.
        if sh(('ssh', args.nas_host, f'mkdir -p {NAS_DIR}/vefr-{date}')).returncode:
            print('warning: could not create snapshot dir on NAS')
        else:
            for f in files_here:
                leaf = Path(f).name
                if sh(('scp', '-q', f'{args.deploy_host}:{f}',
                       f'{args.nas_host}:{NAS_DIR}/vefr-{date}/{leaf}')).returncode:
                    print(f'warning: {leaf} not backed up')
                else:
                    print(f'  play history: {leaf}')
            # Mirror latest -> latest/, so 'the most recent snapshot'
            # has a stable name regardless of date.
            sh(('ssh', args.nas_host,
                f'rm -rf {NAS_DIR}/latest && '
                f'cp -r {NAS_DIR}/vefr-{date} {NAS_DIR}/latest'))
    else:
        print(f'no play history on {args.deploy_host}:{vol_remote} yet')

    print('backed up. <3')
    return 0


# ----------------------------------------------------------------- test

def cmd_test(args) -> int:
    need_repo()
    cmd = ('uv', 'run', '--group', 'test', 'pytest', '-q') + tuple(args.test_args)
    try:
        return sh(cmd).returncode
    except FileNotFoundError:
        print('uv not found - run ratatoskr test from a checkout with uv installed')
        return 1


# ----------------------------------------------------------------- mains

RATATOSKR_HELP = """ratatoskr - the squirrel who carries messages up and down Yggdrasil.

Subcommands for ferrying things between the engine and the
rest of the world:

  ratatoskr skipa         the seven questions - git/deploy sync,
                           local files needing push, deployment
                           health, world validation, backup
                           freshness, vault persistence, open
                           ROADMAP items
  ratatoskr test           the pytest suite (uv run --group test pytest),
                           extra args pass through: ratatoskr test -k chat
  ratatoskr ferry <verb>   ferry tools - carry the world between the
                           dev box, the deploy host, Gitea, the NAS,
                           and the World Tree bundle:

    ratatoskr ferry deploy   ship this checkout to --deploy-host,
                             rebuild the container, restart it,
                             verify health + the live map
    ratatoskr ferry carry    git bundle + play history (vault,
                             journal) -> --nas-host. The newest
                             two bundles are kept; play history
                             mirrors under vefr-<date>/ plus a
                             stable latest/ pointer.
    ratatoskr ferry fetch    clone or pull a story repo (Gitea,
                             --base) into worlds/<name>/. Pass
                             'owner/name' or a full git URL;
                             --target <deploy-host> ships straight
                             to the live box; --pull updates an
                             existing pack instead of re-cloning;
                             --dry-run prints the plan only.

  ratatoskr spark         the resident small brain and its service:

    ratatoskr spark install  acquire the pinned model (verified by
                             size + sha256), install + start the
                             quadlet, wire VEFR_SPARK_URL into the
                             engine, wait for health, smoke test.
                             --profile quality (Phi-4-mini Q4_K_M,
                             default) or tiny (Qwen3.5-0.8B Q8_0).
    ratatoskr spark status   model verified? service active? health?
    ratatoskr spark smoke    four functional probes through the live
                             engine's /api/spark routes: health,
                             NPC JSON, state-edit preservation,
                             escalation judgment.

  ratatoskr weave          package worlds/<name>/ + web/packaged.html
                           into one self-contained HTML file. Pair it
                           with --with-bundle to also write the
                           World Tree (a markdown document with one
                           section per dev UI tab, woven from
                           vault + journal). Send the pair to
                           someone - they open the HTML in a browser,
                           point at any OpenAI-compatible LLM URL,
                           and play.
"""

NORNS_HELP = """norns - the weavers of fate at the well beneath Yggdrasil.

Subcommands for shaping what the engine makes:

  norns chat        interview a new world into existence, against
                    your local model. Writes worlds/<name>/,
                    validates as it goes.
  norns validate    geometry checks against a pack (--pack defaults
                    to the currently selected world)
  norns verify      validate a live deployment's served world (--url)
  norns build-map   rebuild the map from run-length rows (--segments,
                    --pack, --force)
  norns delve       generate dungeon floors from a seed and wire their
                    stairs as region transitions (--pack, --seed,
                    --floors, --from-region, --from-at)

The shape of every world, the town's grid, and the keepers'
voices are yours - the bones and the flesh alike. The norns
only ever teach the engine how to speak.
"""


# --------------------------------------------------------------- volumes

def cmd_volumes_list(args) -> int:
    """List every pack the engine can see, with the source tagged.

    Source is 'canon' (rw volume, author-owned) or 'template'
    (ro volume, engine-owned). The same list the builder UI
    uses, in human-readable form.
    """
    from . import volumes as vol_mod
    rows = vol_mod.list_packs()
    if not rows:
        print("no packs found")
        return 0
    print(f"{'pack':<24} {'source':<10} path")
    print(f"{'----':<24} {'------':<10} ----")
    for r in rows:
        print(f"{r['name']:<24} {r['source']:<10} {r['path']}")
    return 0


def cmd_volumes_migrate(args) -> int:
    """Split a legacy ~/vefr-worlds/ bind mount into ro + rw
    Docker volumes. Idempotent; safe to re-run.
    """
    from . import volumes as vol_mod
    legacy = Path(args.legacy_root).expanduser() if args.legacy_root else None
    return vol_mod.migrate(legacy_root=legacy, dry_run=args.dry_run)


def cmd_volumes_export(args) -> int:
    """Export a pack to a host-side git repo for editing.

    The destination gets the pack's full file tree in
    engine-native layout (acts or flat), plus a README and
    an initial commit. After editing + committing, run
    `volumes import --pack <name> --from <dest>` to write
    the change back into the engine's volume.
    """
    from . import volumes as vol_mod
    return 0 if vol_mod.export_pack(
        args.pack, Path(args.dest).expanduser().resolve(),
        init_git=not args.no_git,
    ) else 1


def cmd_volumes_import(args) -> int:
    """Import a pack from a host-side directory into the volume.

    Validates the source via the engine's loader first; rejects
    packs that wouldn't pass maplab. Then copies the tree into
    the rw volume (or the dev-box engine checkout).
    """
    from . import volumes as vol_mod
    try:
        vol_mod.import_pack(
            args.pack, Path(args.from_path).expanduser().resolve(),
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"import failed: {e}")
        return 1
    return 0


def cmd_volumes_shell(args) -> int:
    """Drop into a shell inside the engine container.

    `--pack <name>` cds into the pack's volume path. No shell
    on the dev box; this is a bazzite/deploy-host convenience.
    """
    from . import volumes as vol_mod
    return vol_mod.shell(args.pack)


# --------------------------------------------------------------- art
# ADR 0011: a pack's art/ledger/round-NN.json. `check` validates the
# whole ledger dir; `credits` prints the generated markdown.

def cmd_art_check(args) -> int:
    """Validate every round-*.json in --ledger; exit 1 on any problem.

    --root is where each picture's `to` path resolves (normally the
    pack root); it defaults to the ledger dir's grandparent, since the
    ledger lives at <root>/art/ledger.
    """
    from . import art_ledger
    ledger = Path(args.ledger).expanduser()
    root = Path(args.root).expanduser() if args.root else ledger.parent.parent
    problems = art_ledger.check(ledger, root)
    if not problems:
        print("ok")
        return EXIT_OK
    for problem in problems:
        print(problem)
    return EXIT_ERROR


def cmd_art_credits(args) -> int:
    """Print the ledger's generated credits markdown."""
    from . import art_ledger
    print(art_ledger.credits(Path(args.ledger).expanduser()), end="")
    return EXIT_OK


def cmd_art_kit(args) -> int:
    """Report a skin kit's completeness; exit 1 on a missing piece.

    --kit is the manifest (art/skin-kit.json), --src the directory
    holding its pictures. The loader prints one line per piece and
    the total; a bad manifest is one plain sentence on stderr.
    """
    from . import skin_kit
    return skin_kit.run(Path(args.kit).expanduser(), Path(args.src).expanduser())


# --------------------------------------------------------- shared wiring
# The verbs vefr and ratatoskr spell the same way: one wiring, one set
# of flags, one set_defaults - both front doors parse identically.

def _add_ferry_flags(ap) -> None:
    """--url/--deploy-host/--deploy-vol/--nas-host: what deploy and carry
    read. ratatoskr declares them as globals; vefr declares them on the
    ferry verb. Same flags, same defaults, either way."""
    ap.add_argument('--url', default=DEFAULT_URL)
    ap.add_argument('--deploy-host', default=DEFAULT_DEPLOY_HOST)
    ap.add_argument('--deploy-vol', default='~/vefr-data',
                    help='bind-mounted game volume on --deploy-host')
    ap.add_argument('--nas-host', default=DEFAULT_BACKUP_HOST)


def _add_weave_parser(sub, **kw) -> None:
    """`weave` - package a world into one self-contained HTML file.

    The file-packaging command - top level in both front doors, away
    from the ferry sub-tree. Extra kwargs (description, epilog) dress
    it for `vefr weave --help`; ratatoskr passes none.
    """
    pw = sub.add_parser(
        'weave', help='package a world into one self-contained HTML file', **kw
    )
    pw.add_argument('--pack', default=None, help='world to bundle (default: current)')
    pw.add_argument('--out', default=None, help='output HTML path (default: dist/<name>-<date>.html)')
    pw.add_argument('--with-bundle', action='store_true',
                    help='also write <name>-<date>.tree.md alongside the HTML')
    pw.add_argument('--vault', default=None,
                    help='path to vault.json (default: $VEFR_VAULT)')
    pw.add_argument('--journal', default=None,
                    help='path to journal.json (default: $VEFR_JOURNAL)')
    pw.add_argument('--pool', type=int, default=0, metavar='N',
                    help='pre-generate N real outputs per mechanic/phase/'
                         'speaker combination and bake them into the file '
                         'as the offline fallback pool (needs a live model)')
    pw.add_argument('--from-live', default=None,
                    help='pull vault+journal from a live deployment URL')
    pw.set_defaults(fn=cmd_build_web)


def _add_archive_parser(sub, **kw) -> None:
    """`archive` - carry a world as one portable `.vefr` file (vefr#455).

    Beside `weave`, not instead of it: the woven HTML is still the
    self-contained file, and this is the versioned, inspectable archive
    the shared Player opens (ADR 0019).
    """
    ar = sub.add_parser(
        'archive',
        help='write a world as one portable .vefr game file',
        **kw
    )
    ar.add_argument('--pack', default=None,
                    help='world to archive (default: the resolved world)')
    ar.add_argument('--out', default=None,
                    help='output .vefr path (default: dist/<name>.vefr)')
    ar.add_argument('--player', default=None, metavar='PATH',
                    help='where to write the shared Player that opens it '
                         '(default: <archive>.player.html beside the archive)')
    ar.add_argument('--no-player', action='store_true',
                    help='write only the .vefr, no Player build')
    ar.add_argument('--pool', type=int, default=0, metavar='N',
                    help='bake N real outputs per mechanic/phase/speaker '
                         'combination into the archive as the offline '
                         'fallback pool (needs a live model)')
    ar.add_argument('--inspect', default=None, metavar='FILE',
                    help='validate an existing .vefr and print its manifest')
    ar.add_argument('--json', action='store_true',
                    help='print the manifest as JSON (with --inspect)')
    ar.set_defaults(fn=cmd_archive)


def _add_ferry_verbs(ferry_sub) -> None:
    """ferry's verbs: deploy, carry, fetch, scaffold - the same flags and
    set_defaults behind both front doors."""
    fd = ferry_sub.add_parser(
        'deploy',
        help='ship this checkout to --deploy-host (build image + restart + healthcheck)',
    )
    fd.add_argument(
        '--init', action='store_true',
        help="write deploy.toml.example + docs/guides/deploy.md scaffolding; "
             "does not contact the deploy host. Run once per checkout.",
    )
    fd.add_argument(
        '--skip-tests', action='store_true',
        help='skip the pytest + sample-world validate pre-flight gate',
    )
    fd.add_argument(
        '--rebuild', action='store_true',
        help='force `podman build` even when the image SHA matches the checkout '
             'HEAD (default: skip the build when nothing changed)',
    )
    fd.add_argument(
        '--no-health', action='store_true',
        help='skip the post-deploy /api/health probe + maplab verify',
    )
    fd.set_defaults(fn=cmd_deploy)

    fcp = ferry_sub.add_parser('carry', help='git bundle + play history -> --nas-host')
    fcp.set_defaults(fn=cmd_backup)

    fct = ferry_sub.add_parser(
        'fetch',
        help='clone or pull a story repo from Gitea into worlds/<name>/',
    )
    fct.add_argument(
        'repo',
        help="the story repo: 'owner/name' shorthand (resolved via "
             '--base) or a full git URL',
    )
    fct.add_argument(
        '--name', default=None,
        help='the worlds/ directory name (default: repo basename)',
    )
    fct.add_argument(
        '--base', default=GITEA_BASE,
        help='Gitea base URL for shorthand repo resolution',
    )
    fct.add_argument(
        '--target', default='local',
        help="where to land the pack: 'local' (this checkout) or "
             '<deploy-host> (ssh + clone there)',
    )
    fct.add_argument(
        '--pull', action='store_true',
        help="if worlds/<name>/ exists, do `git pull --ff-only` instead of clone",
    )
    fct.add_argument(
        '--dry-run', action='store_true',
        help='show what would happen, do nothing',
    )
    fct.set_defaults(fn=cmd_import)

    fs = ferry_sub.add_parser(
        'scaffold',
        help='export the active pack as a standalone git repo, ready for a new author',
    )
    fs.add_argument('dest', help='destination directory (created, must be empty)')
    fs.add_argument('--name', default=None,
                    help='the pack to export (default: the resolved world)')
    fs.add_argument('--push', action='store_true',
                    help='accepted and ignored: the by-hand push commands '
                         'are always printed, and vefr never uses your '
                         'origin credentials')
    fs.set_defaults(fn=cmd_scaffold)


def _add_spark_verbs(spark_sub) -> None:
    """spark's verbs: install, status, task, smoke - the same flags and
    set_defaults behind both front doors (see docs/guides/spark.md)."""
    si = spark_sub.add_parser(
        'install',
        help='acquire the pinned model, install + start the quadlet, '
             'wire the engine, verify health (idempotent)',
    )
    si.add_argument('--profile', default='quality', choices=('quality', 'tiny'),
                    help="spark-quality (Phi-4-mini Q4_K_M, default) or "
                         "spark-tiny (Qwen3.5-0.8B Q8_0)")
    si.add_argument('--host', default=DEFAULT_DEPLOY_HOST,
                    help='the machine Spark lives on (declared like ferry deploy)')
    si.add_argument('--image', default=None,
                    help='llama.cpp server image ref (default: pinned by digest)')
    si.set_defaults(fn=cmd_spark_install)

    ss = spark_sub.add_parser(
        'status',
        help='model verified? service active? health green?',
    )
    ss.add_argument('--profile', default='quality', choices=('quality', 'tiny'))
    ss.add_argument('--host', default=DEFAULT_DEPLOY_HOST)
    ss.add_argument('--spark-url', default=None,
                    help='probe this Spark endpoint instead of the default')
    ss.add_argument('--json', action='store_true', help='print the result envelope')
    ss.set_defaults(fn=cmd_spark_status)

    st = spark_sub.add_parser(
        'task',
        help='run one Spark task (npc, dialogue, lore, narrate, classify, '
             'state_edit) through the same checked doorway the studio uses',
    )
    st.add_argument('task', help='the task contract to use')
    st.add_argument('prompt', nargs='?', default=None,
                    help='the request (or -f FILE, or stdin)')
    st.add_argument('-f', '--file', default=None, help='read the request from FILE')
    st.add_argument('--speaker', default=None, help='a character id from the pack')
    st.add_argument('--state', default=None, help='a JSON file of runtime state')
    st.add_argument('--no-world', action='store_true', help="leave the world's canon out")
    st.add_argument('--spark-url', default=None, help='use this Spark endpoint')
    st.add_argument('--inspect', action='store_true',
                    help='print what WOULD be sent (no model call)')
    st.add_argument('--json', action='store_true', help='print the result envelope')
    st.set_defaults(fn=cmd_spark_task)

    smo = spark_sub.add_parser(
        'smoke',
        help='functional proof through the live engine\'s /api/spark routes',
    )
    smo.add_argument('--url', default=None,
                     help='the live engine URL (default: deploy.toml url)')
    smo.set_defaults(fn=cmd_spark_smoke)


def ratatoskr_main() -> int:
    ap = argparse.ArgumentParser(
        prog='ratatoskr', description=RATATOSKR_HELP,
        epilog="the same verbs now spell as vefr: vefr test, vefr weave, "
               "vefr ferry, vefr doctor (vefr --help)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_ferry_flags(ap)
    sub = ap.add_subparsers(dest='cmd', required=True)

    sk = sub.add_parser('skipa', help='the seven questions')
    sk.add_argument('--json', action='store_true', help='print the result envelope')
    sk.set_defaults(fn=cmd_skipa)

    pt = sub.add_parser(
        'test', help='the pytest suite (extra args pass through, e.g. -k chat)'
    )
    pt.set_defaults(fn=cmd_test)

    # `weave` is the file-packaging command - kept at top level so it's
    # easy to reach without the ferry sub-tree.
    _add_weave_parser(sub)

    # Ferry subcommand - carries things between places.
    ferry = sub.add_parser(
        'ferry', help='carry messages between dev box, deploy host, Gitea, NAS'
    )
    ferry_sub = ferry.add_subparsers(dest='ferry_verb', required=True)
    _add_ferry_verbs(ferry_sub)

    # Volumes subcommand - manage the ro/rw volume split on the
    # deploy host. `list` shows what's loaded; `migrate` does the
    # one-shot split of a legacy bind mount.
    volumes = sub.add_parser(
        'volumes',
        help='manage the ro template + rw canon Docker volumes',
    )
    volumes_sub = volumes.add_subparsers(dest='volumes_verb', required=True)
    volumes_list = volumes_sub.add_parser(
        'list', help='list every pack the engine can see'
    )
    volumes_list.set_defaults(fn=cmd_volumes_list)
    volumes_migrate = volumes_sub.add_parser(
        'migrate', help='split a legacy ~/vefr-worlds/ bind into ro+rw volumes'
    )
    volumes_migrate.add_argument(
        '--legacy-root', default=None,
        help='legacy worlds root (default: ~/vefr-worlds)',
    )
    volumes_migrate.add_argument(
        '--dry-run', action='store_true',
        help='print what would happen; do nothing',
    )
    volumes_migrate.set_defaults(fn=cmd_volumes_migrate)

    volumes_export = volumes_sub.add_parser(
        'export',
        help='export a pack to a host-side git repo for editing in vim',
    )
    volumes_export.add_argument('--pack', required=True,
                                 help='the world pack to export')
    volumes_export.add_argument('--dest', required=True,
                                 help='destination directory (created if missing)')
    volumes_export.add_argument('--no-git', action='store_true',
                                 help='skip the git init / initial commit')
    volumes_export.set_defaults(fn=cmd_volumes_export)

    volumes_import = volumes_sub.add_parser(
        'import',
        help='import a pack from a host-side directory into the rw volume',
    )
    volumes_import.add_argument('--pack', required=True,
                                 help='the world pack name to import as')
    volumes_import.add_argument('--from', dest='from_path', required=True,
                                 help='source directory (engine-native layout)')
    volumes_import.add_argument('--dry-run', action='store_true',
                                 help='validate only; do not write')
    volumes_import.set_defaults(fn=cmd_volumes_import)

    volumes_shell = volumes_sub.add_parser(
        'shell',
        help='drop into a shell inside the engine container',
    )
    volumes_shell.add_argument('--pack', default=None,
                                help='cd into the pack\'s volume path')
    volumes_shell.set_defaults(fn=cmd_volumes_shell)

    # Spark - the resident small brain and its service lifecycle.
    spark = sub.add_parser(
        'spark',
        help='VEFR\'s resident Spark: install, status, smoke',
    )
    spark_sub = spark.add_subparsers(dest='spark_verb', required=True)
    _add_spark_verbs(spark_sub)

    args, extra = ap.parse_known_args()
    if args.cmd == 'test':
        args.test_args = extra
    from .blueprint import BlueprintRefusal
    try:
        return args.fn(args)
    except BlueprintRefusal as exc:
        print(f'refused: {exc}', file=sys.stderr)
        return EXIT_ERROR


def cmd_handbok(args) -> int:
    """Write the mechanics manual from real play - norns handbok.

    Deterministic templating over real events, the same honesty rule
    as the export: the trace (data/trace.jsonl) says how each
    mechanic actually behaved - calls, latency, failures - and the
    session journal supplies real examples. No model pass.

    Everything is read for THIS pack and no other: the trace entries
    name their world, the journal is world-scoped, and the title
    comes from the pack's own file. A world with no applicable
    history fails closed - no manual is written - because a manual
    with another world's numbers in it is worse than none (the
    cross-pack case is pinned in tests/test_handbok.py).
    """
    import json as _json

    from . import trace as trace_mod
    from .journal import list_entries

    if getattr(args, 'pack', None) is None:
        pack = pack_root() / 'worlds' / world_name()
    else:
        p = Path(args.pack)
        pack = p if p.is_absolute() else pack_root() / 'worlds' / p
    if not (pack / 'world.json').exists():
        print(f'pack not found at {pack}; pass --pack NAME or set VEFR_WORLD')
        return 1
    world_id = pack.name

    # The title from this pack's own contract - never the world that
    # happens to be active.
    try:
        config = _json.loads((pack / 'world.json').read_text(encoding='utf-8'))
    except (OSError, _json.JSONDecodeError):
        config = {}
    title = config.get('title') or world_id

    # ---- the trace, read tolerantly, scoped to this pack ----
    events: list[dict] = []
    tpath = trace_mod.file_path()
    if tpath.exists():
        for line in tpath.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = _json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(ev, dict) and ev.get('world') == world_id:
                events.append(ev)

    by_route: dict[str, list[dict]] = {}
    for ev in events:
        by_route.setdefault(ev.get('route', '?'), []).append(ev)

    entries = list_entries(sid=getattr(args, 'session', None), world=world_id)
    by_kind: dict[str, list[dict]] = {}
    for e in entries:
        by_kind.setdefault(e.get('kind', '?'), []).append(e)

    if not events and not entries:
        print(f'no play history for {world_id} - not writing a handbok')
        return 1

    out: list[str] = [
        f"# {title} - handbok",
        '',
        'A mechanics manual, generated from real play: what the engine '
        'actually did, how long each thread of the loom took, and real '
        'examples from this playthrough. Regenerate with '
        '`norns handbok` - this file is a snapshot, not canon.',
        '',
    ]

    out.append('## The mechanics, as they ran')
    out.append('')
    if by_route:
        out.append('| call | runs | avg | slowest | failed |')
        out.append('|---|---|---|---|---|')
        for route in sorted(by_route):
            evs = by_route[route]
            ms = [e.get('ms', 0.0) for e in evs]
            failed = sum(1 for e in evs if e.get('ok') is False)
            out.append(
                f'| {route} | {len(evs)} | {sum(ms) / len(ms):.0f}ms '
                f'| {max(ms):.0f}ms | {failed} |'
            )
    else:
        out.append('_No trace for this pack yet - play it with the '
                   'server running, then rerun._')
    out.append('')

    out.append('## The phases, as they were walked')
    phases_seen = []
    for e in entries:
        ph = e.get('phase')
        if ph and ph not in phases_seen:
            phases_seen.append(ph)
    out.append(
        ', '.join(f'**{ph}**' for ph in phases_seen)
        or '_The world has not spoken yet._'
    )
    out.append('')

    out.append('## Real examples, from the session')
    out.append('')
    examples = {
        'rumor': 'a whisper heard',
        'npc_line': 'a line spoken',
        'item_forged': 'a relic kept',
        'stefna_letter': 'the letter found',
    }
    for kind, label in examples.items():
        evs = by_kind.get(kind, [])
        if not evs:
            continue
        out.append(f'### {label}')
        for e in evs[-2:]:
            text = e.get('whisper') or e.get('line') or e.get('lore') or e.get('letter') or ''
            out.append(f'> {_clean_example(text)}')
            out.append('')
        out.append('')

    out.append('## The session, counted')
    out.append('')
    if by_kind:
        for kind in sorted(by_kind):
            out.append(f'- {len(by_kind[kind])} {kind}')
    else:
        out.append('_Nothing yet. The world is waiting._')
    out.append('')

    out_path = pack / 'handbok.md'
    out_path.write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')
    print(f'handbok written: {out_path}')
    return 0


def _clean_example(text: str) -> str:
    """One line, quote-marked, truncated - a handbok is not a lore dump."""
    one = ' '.join(str(text or '').split())
    if len(one) > 240:
        one = one[:237] + '...'
    return f'\u201c{one}\u201d'


# ----------------------------------------------------------------- scaffold

def cmd_scaffold(args) -> int:
    """Export the active pack as a standalone, git-ready repo - ferry scaffold.

    For handing a world to someone who will make it their own: the
    pack's files as-is (canon, voices, map, ledger - the author's
    content), a README explaining what vefr is and which files are
    meant to be replaced with real art, and a fresh git history so
    their work starts at commit one. The repo is left unpushed: the
    command prints the two commands that send it, because putting a
    credential in the new repo's remote URL writes that credential to
    .git/config and echoes it to the terminal.
    """
    dest = Path(args.dest).resolve()
    if dest.exists() and any(dest.iterdir()):
        print(f'refusing: {dest} exists and is not empty')
        return 1

    name = args.name or world_name()
    src = pack_root() / 'worlds' / name
    if not (src / 'world.json').exists():
        print(f'pack not found at {src}; pass --name or set VEFR_WORLD')
        return 1

    # Derived artifacts regenerate on the next run; stash files are
    # transient. Everything else the author touched ships as-is.
    EXCLUDE = {'world-tree.md', 'handbok.md'}
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in EXCLUDE or item.name.endswith('.tmp') or item.name.endswith('.rewind.json'):
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    engine_sha = 'unknown'
    root = subprocess.run(
        ('git', 'rev-parse', '--show-toplevel'),
        capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent),
    )
    if root.returncode == 0:
        sha = subprocess.run(
            ('git', '-C', root.stdout.strip(), 'rev-parse', '--short', 'HEAD'),
            capture_output=True, text=True,
        )
        if sha.returncode == 0:
            engine_sha = sha.stdout.strip()

    # The engine's home, derived from this checkout's own origin -
    # runtime identity, never a hardcoded one.
    origin_url = ''
    if root.returncode == 0:
        o = subprocess.run(
            ('git', '-C', root.stdout.strip(), 'remote', 'get-url', 'origin'),
            capture_output=True, text=True,
        )
        if o.returncode == 0:
            u = o.stdout.strip()
            if u.startswith('git@'):
                u = 'https://' + u[4:].replace(':', '/', 1)
            origin_url = u.removesuffix('.git')

    engine_line = 'A world pack for vefr - a rumor engine for playable\nworlds, exported from engine commit'
    if origin_url:
        engine_line += f' [`{engine_sha}`]({origin_url}).'
    else:
        engine_line += f' `{engine_sha}`.'

    readme = f"""# {name}

{engine_line}

## What each file is

| File | What it is | Replaceable? |
|---|---|---|
| `world.json` | the world's shape: town, phases, voices, bonds | the schema is the engine's; the contents are yours |
| `logbok.md` | canon - the rules the story must never break | yours, entirely |
| `ledger.md` | the whispers the engine matches cadence against | yours, entirely |
| `voices/*.md` | each speaker's system prompt | yours, entirely |
| `map.md` | the walkable map (run-length rows + legend) | yours, entirely |

## Running it

```sh
git clone {origin_url if origin_url else '<the vefr engine checkout>'}
cd vefr && uv sync --group test
VEFR_WORLD={name} uv run uvicorn vefr.main:app --app-dir src --port 8820
```

Or point this directory's name at `worlds/` inside a vefr clone.

## Making it yours

This scaffold is a starting point, not a finished thing: drop in
your own artwork, rewrite the voices, replace the map. The engine
reads whatever the pack gives it.
"""
    (dest / 'README.md').write_text(readme, encoding='utf-8')
    if not (dest / 'LICENSE').exists() and not (dest / 'LICENSE.md').exists():
        (dest / 'LICENSE.md').write_text(
            f'{name} - all rights reserved by its author.\n'
            'Replace this file with the license you choose before sharing.\n',
            encoding='utf-8',
        )

    if sh(('git', '-C', str(dest), 'init', '-b', 'main')).returncode:
        print('git init failed - the files are copied; init by hand')
        return 1
    sh(('git', '-C', str(dest), 'add', '-A'))
    # Inline identity: the scaffolded repo is a fresh export, and the
    # exporting machine (or CI runner) may have no global git config.
    # Scoped via -c so we never touch the user's real config.
    if sh(('git', '-C', str(dest), '-c', 'user.name=vefr scaffold',
           '-c', 'user.email=vefr@scaffold.local', 'commit', '-m',
           f'world pack {name}, exported from vefr {engine_sha}')).returncode:
        print('commit failed - files are staged; commit by hand')
        return 1

    # The push is the author's, by hand. vefr never reads the engine
    # checkout's origin credentials, never calls a forge API with
    # them, and never writes one into the new repo's config - a token
    # in a remote URL is a token in a log, a backup, and a clone.
    print(f'scaffold ready: {dest} (git main, 1 commit)')
    print('push it yourself:')
    print(f'  git -C {dest} remote add origin <your repo url>')
    print(f'  git -C {dest} push -u origin main')
    return 0


# --------------------------------------------------------------- spark

def _spark_host(args) -> str:
    """The host Spark lives on, resolved like ferry deploy: --flag,
    then env, then deploy.toml. The silent 'bazzite' default is still
    refused - one resident llama.cpp process deserves a declared home."""
    host = getattr(args, 'host', None)
    cfg = _deploy_toml()
    declared_env = bool(os.environ.get('VEFR_DEPLOY_HOST'))
    declared_toml = 'host' in cfg
    if host == DEFAULT_DEPLOY_HOST and not declared_env and declared_toml:
        host = cfg['host']
    if host == 'bazzite' and not declared_env and not declared_toml:
        raise SystemExit(
            'refusing: the Spark host is not declared.\n'
            '  export VEFR_DEPLOY_HOST=<your-host-or-ssh-alias>\n'
            'or add host = "<your-host>" to deploy.toml.'
        )
    return host


def _k2_health(host: str) -> str:
    """K2's /health via ssh - recorded before and after every Spark
    service change. K2 is the escalation target; it must never be
    destabilized by Spark work."""
    out = subprocess.run(
        ('ssh', '-o', 'ConnectTimeout=6', host,
         'curl -s -m 5 http://127.0.0.1:8081/health'),
        capture_output=True, text=True, timeout=20).stdout.strip()
    return out or 'no answer'


def _quadlet_text(profile: dict, image: str) -> str:
    """The spark quadlet for one profile - CPU-only, loopback-only,
    pinned image, model-native template flags from spark.PROFILES."""
    kwargs = profile.get('chat_template_kwargs') or {}
    extra = ''
    if kwargs:
        import json as _json
        extra = " --chat-template-kwargs '" + _json.dumps(kwargs) + "'"
    alias = profile['alias']
    return f"""\
[Unit]
Description=spark - VEFR's resident small brain ({profile['key']} profile, CPU-only)

[Container]
Image={image}
ContainerName=spark
Network=host
Volume=%h/spark/models:/models:Z
Exec=--model /models/{profile['file']} --alias {alias} --host 127.0.0.1 --port 8082 -c 8192 -t 8 -ngl 0 --jinja{extra}

[Service]
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def _spark_model_ensure(host: str, profile: dict) -> str:
    """The model file on the Spark host, verified. Copies from the
    benchmark cache when present (no re-download), else pulls the
    pinned artifact from Hugging Face with resume. Returns the
    verification detail. Never commits the GGUF - it lives on the host."""
    remote_dir = '~/spark/models'
    repo, fname = profile['repo'], profile['file']
    # Fast path: the benchmark cache already has the pinned artifact.
    cache = f'~/llama-server/vefr-spark/models/{fname}'
    probe = subprocess.run(
        ('ssh', '-o', 'ConnectTimeout=6', host,
         f'test -f {cache} && echo cached || echo absent'),
        capture_output=True, text=True, timeout=20).stdout.strip()
    if probe == 'cached':
        print(f'  model found in benchmark cache: {cache}')
        rc = sh(('ssh', host,
                 f'mkdir -p {remote_dir} && '
                 f'cp -n {cache} {remote_dir}/{fname}')).returncode
    else:
        print(f'  downloading {fname} from huggingface.co/{repo} (resumes on retry)')
        rc = sh(('ssh', host,
                 f'mkdir -p {remote_dir} && curl -sS -L -C - '
                 f'--retry 5 --retry-delay 5 -o {remote_dir}/{fname} '
                 f'https://huggingface.co/{repo}/resolve/main/{fname}')).returncode
    if rc:
        return f'DOWNLOAD FAILED (rc={rc})'
    check = subprocess.run(
        ('ssh', host,
         f'sha256sum {remote_dir}/{fname}'),
        capture_output=True, text=True, timeout=120)
    got = check.stdout.strip().split()[0] if check.stdout.strip() else ''
    if not got:
        return f'HASH CHECK FAILED: {check.stderr.strip()[:200]}'
    if got != profile['sha256']:
        return (f'VERIFICATION FAILED: sha {got[:12]}... != pinned '
                f'{profile["sha256"][:12]} - remove the file and re-run')
    size_out = subprocess.run(
        ('ssh', host, f'stat -c %s {remote_dir}/{fname}'),
        capture_output=True, text=True, timeout=20).stdout.strip()
    return f'verified against pinned sha256 ({int(size_out or 0) / 1e9:.2f} GB)'


def _spark_image_ref(host: str) -> str:
    """The llama.cpp server image, pinned by digest so a re-run of
    `ratatoskr spark install` reconciles to the same artifact."""
    out = subprocess.run(
        ('ssh', '-o', 'ConnectTimeout=6', host,
         'podman images --digests --format "{{.Repository}}@{{.Digest}}" '
         '| grep "ghcr.io/ggml-org/llama.cpp" | head -1'),
        capture_output=True, text=True, timeout=20).stdout.strip()
    return out or 'ghcr.io/ggml-org/llama.cpp:server'


def cmd_spark_install(args) -> int:
    """One command from 'no Spark' to 'boring resident service':
    acquire the pinned model, verify it, install + start the quadlet,
    wire VEFR_SPARK_URL into the engine's environment, verify health,
    and leave K2 exactly as it was."""
    host = _spark_host(args)
    from . import spark as spark_mod
    prof = spark_mod.profile(args.profile)
    image = args.image or _spark_image_ref(host)

    print(f'spark install: profile={prof["key"]} host={host}')
    k2_pre = _k2_health(host)
    print(f'  k2 pre : {k2_pre}')

    detail = _spark_model_ensure(host, prof)
    print(f'  model: {detail}')
    if 'FAILED' in detail or 'mismatch' in detail:
        return 1

    quadlet = _quadlet_text(prof, image)
    rc = sh(('ssh', host,
             'mkdir -p ~/.config/containers/systemd ~/spark/models && '
             f"cat > ~/.config/containers/systemd/spark.container <<'QUADLET'\n"
             f'{quadlet}QUADLET')).returncode
    if rc:
        return rc
    # The engine learns Spark's endpoint from its own environment -
    # one configuration path, no machine-specific URLs in code.
    sh(('ssh', host,
        'grep -q VEFR_SPARK_URL ~/.config/containers/systemd/vefr.container || '
        'echo "Environment=VEFR_SPARK_URL=http://127.0.0.1:8082" '
        '>> ~/.config/containers/systemd/vefr.container'))
    sh(('ssh', host,
        'grep -q VEFR_SPARK_PROFILE ~/.config/containers/systemd/vefr.container || '
        f'echo "Environment=VEFR_SPARK_PROFILE={prof["key"]}" '
        '>> ~/.config/containers/systemd/vefr.container'))
    # Quadlet units are generated by systemd from the .container file:
    # daemon-reload materializes them and the [Install] section already
    # wires boot persistence. `systemctl enable` refuses generated
    # units ("transient or generated") - start is the correct verb.
    if sh(('ssh', host,
           'systemctl --user daemon-reload && '
           'systemctl --user start spark')).returncode:
        print('systemd start failed - check: ssh %s systemctl --user status spark' % host)
        return 1

    # llama.cpp loads the model before /health answers; poll long enough
    # for a cold page-in of a ~2.5 GB file from disk.
    print('  waiting for model load + health...')
    import time as _time
    up = False
    for _ in range(90):
        probe = subprocess.run(
            ('ssh', host, 'curl -s -m 3 http://127.0.0.1:8082/health'),
            capture_output=True, text=True, timeout=15).stdout.strip()
        if '"ok"' in probe:
            up = True
            break
        _time.sleep(2)
    if not up:
        print('spark never went healthy - logs: '
              f'ssh {host} podman logs spark')
        return 1
    smoke = subprocess.run(
        ('ssh', host,
         'curl -s -m 120 http://127.0.0.1:8082/v1/chat/completions '
         '-H "Content-Type: application/json" '
         '-d \'{"messages":[{"role":"user","content":"Reply with exactly: SPARK-OK"}],'
         '"max_tokens":16}\' | grep -o "SPARK-OK" | head -1'),
        capture_output=True, text=True, timeout=140).stdout.strip()
    sh(('ssh', host, 'systemctl --user restart vefr'))

    k2_post = _k2_health(host)
    ok = 'SPARK-OK' in smoke
    print(f'  smoke: {"SPARK-OK" if ok else "FAILED - " + smoke!r}')
    print(f'  k2 post: {k2_post}')
    print('spark installed. <3' if ok and k2_post == k2_pre
          else 'spark installed with warnings - see above.')
    return 0 if ok else 1


def cmd_spark_status(args) -> int:
    """The four facts: model verified? service running? health green?
    does Spark still know what is not its job?"""
    from . import spark as spark_mod
    prof = spark_mod.profile(args.profile)
    url = args.spark_url or spark_mod.spark_url()
    rows = []
    if spark_mod.is_remote(url):
        # Spark on another machine (e.g. a homelab appliance): its model file
        # and its service manager live there. Ask the server which file it
        # serves; the health probe below is the service's proof of life.
        host = url
        ok, detail = spark_mod.served_model(prof, url=url)
        rows.append(('model', 'ok' if ok else 'FAIL', detail))
        rows.append(('service', 'ok', 'runs on the Spark host; proven by health below'))
    else:
        host = _spark_host(args)
        ok, detail = spark_mod.verify_model(prof)
        rows.append(('model', 'ok' if ok else 'FAIL', detail))
        svc = subprocess.run(
            ('ssh', '-o', 'ConnectTimeout=6', host,
             'systemctl --user is-active spark'),
            capture_output=True, text=True, timeout=15).stdout.strip() or 'unknown'
        rows.append(('service', 'ok' if svc == 'active' else svc, f'systemctl --user is-active -> {svc}'))
    try:
        h = spark_mod.health(timeout=5, url=url)
        rows.append(('health', 'ok', f'{h["status"]} in {h["probe_ms"]}ms'))
    except Exception as exc:  # noqa: BLE001
        rows.append(('health', 'DOWN', f'{exc.__class__.__name__}'))
    healthy = all(s == 'ok' for _, s, _ in rows)
    if getattr(args, 'json', False):
        down = any(n == 'health' and s != 'ok' for n, s, _ in rows)
        emit_json(envelope(healthy, 'healthy' if healthy else ('unavailable' if down else 'unhealthy'), {
            'profile': prof['key'], 'host': host, 'url': url,
            'checks': rows_json(rows, ('name', 'status', 'detail'))}))
        return EXIT_OK if healthy else (EXIT_UNAVAILABLE if down else EXIT_ERROR)
    print(f'ratatoskr spark status (profile={prof["key"]}, host={host})')
    for name, status, detail in rows:
        print(f'  {name:<8} {status:<8} {detail}')
    return 0 if healthy else 1


def cmd_spark_smoke(args) -> int:
    """The functional proof, through the real integrated path: the
    live engine's /api/spark routes. Four probes: health, structured
    NPC generation, state-edit preservation, escalation judgment.
    Exit 0 only when all four hold."""
    url = (args.url or _deploy_toml().get('url') or DEFAULT_URL).rstrip('/')
    import json as _json
    import urllib.request as _ur

    def post(path: str, body: dict) -> dict:
        req = _ur.Request(f'{url}{path}', _json.dumps(body).encode(),
                          {'Content-Type': 'application/json'})
        with _ur.urlopen(req, timeout=300) as r:
            return _json.loads(r.read().decode())

    rows = []
    h = fetch(f'{url}/api/spark/health', timeout=10)
    rows.append(('health', 'ok' if h.get('ok') else 'FAIL',
                 f'{h.get("spark")} model={h.get("model")} {h.get("probe_ms", "?")}ms'))

    npc = post('/api/spark/task', {
        'task': 'npc',
        'user': 'Scene: dusk in Emberfield, a candle-maker\'s stall near the '
                'market well. Create one new NPC for this scene.'})
    npc_ok = (npc.get('ok') and isinstance(npc.get('result'), dict)
              and set(npc['result']) == {'id', 'name', 'role', 'personality',
                                         'location', 'dialogue_seed'})
    rows.append(('npc_json', 'ok' if npc_ok else 'FAIL', str(npc.get('result', npc.get('error', '')))[:90]))

    state = {'world': 'Emberfield', 'gold': 12,
             'npcs': [{'id': 'bray', 'trust': 2}, {'id': 'kestrel', 'trust': 2}]}
    edit = post('/api/spark/task', {
        'task': 'state_edit',
        'user': 'Update the world state: Kestrel now trusts the player completely. '
                "Set Kestrel's trust to 5. Return the complete updated state JSON and nothing else.",
        'state': state})
    kept = edit.get('ok') and edit.get('result', {}).get('npcs', [{}])[0].get('trust') == 2 \
        and edit.get('result', {}).get('npcs', [{}])[-1].get('trust') == 5 \
        and edit.get('result', {}).get('gold') == 12
    rows.append(('state_edit', 'ok' if kept else 'FAIL',
                 'target changed, rest preserved' if kept else 'preservation broken'))

    esc = post('/api/spark/escalate', {})
    rows.append(('escalation', 'ok' if esc.get('ok') else 'FAIL', esc.get('escalation', '')))

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'ratatoskr spark smoke -- {now} ({url})')
    print()
    print('| probe | status | detail |')
    print('| -- | ------ | ------ |')
    for name, status, detail in rows:
        print(f'| {name} | {status} | {detail} |')
    failed = sum(1 for _, s, _ in rows if s != 'ok')
    print()
    print('spark smoke: all green. <3' if not failed else f'spark smoke: {failed} failed')
    return 0 if not failed else 1


# ---------------------------------------------------------------- doctor

def _pytest_summary(repo: Path) -> tuple:
    """Run the gate quietly; return (status, detail)."""
    try:
        r = subprocess.run(
            (sys.executable, '-m', 'pytest', '-q', '--tb=no'),
            capture_output=True, text=True, cwd=str(repo), timeout=600,
        )
    except FileNotFoundError:
        return 'skip', 'pytest not installed - uv sync --group test'
    lines = (r.stdout or '').strip().splitlines()
    summary = lines[-1] if lines else 'no output'
    return ('ok', summary) if r.returncode == 0 else ('FAIL', summary)


def cmd_spark_task(args) -> int:
    """One Spark task through the checked doorway: context layers in,
    json_schema-locked output, validated result out, fail-closed.

    Plain mode (like `offload ask`): the result goes to stdout, one meta
    line to stderr, so it pipes. --json prints the envelope. Exit codes:
    0 validated, 1 the output failed its schema twice (nothing to apply),
    2 bad arguments, 3 Spark unreachable.
    """
    from . import spark as spark_mod
    if args.task not in spark_mod.TASK_CONTRACTS:
        print(f'spark task: unknown task {args.task!r}; one of: '
              + ', '.join(spark_mod.TASK_CONTRACTS), file=sys.stderr)
        return EXIT_USAGE
    if args.file:
        user = Path(args.file).read_text(encoding='utf-8')
    elif args.prompt is not None:
        user = args.prompt
    elif not sys.stdin.isatty():
        user = sys.stdin.read()
    else:
        print('spark task: give a request, -f FILE, or pipe one in', file=sys.stderr)
        return EXIT_USAGE
    state = json.loads(Path(args.state).read_text(encoding='utf-8')) if args.state else None
    kw = {'speaker': args.speaker, 'state': state, 'world': not args.no_world}
    if args.inspect:
        view = spark_mod.inspect_context(args.task, user, **kw)
        if args.json:
            emit_json(envelope(True, 'inspected', view))
        else:
            for m in view['messages']:
                print(f"--- {m['role']} ---\n{m['content']}")
            print(f"[{view['task']} · {view['model']} · ~{view['approx_prompt_words']} words · "
                  f"{view['schema']}]", file=sys.stderr)
        return EXIT_OK
    t0 = datetime.now(timezone.utc)
    try:
        result, meta = spark_mod.spark_call(args.task, user, url=args.spark_url, **kw)
    except spark_mod.SparkUnavailable as exc:
        if args.json:
            emit_json(envelope(False, 'unavailable', {'task': args.task},
                               warnings=[str(exc)], actions=['ratatoskr spark status']))
        else:
            print(f'spark task: {exc}', file=sys.stderr)
        return EXIT_UNAVAILABLE
    except spark_mod.SparkMalformed as exc:
        if args.json:
            emit_json(envelope(False, 'malformed', {'task': args.task}, warnings=[str(exc)],
                               actions=[f'ratatoskr spark task {args.task} --inspect']))
        else:
            print(f'spark task: {exc}', file=sys.stderr)
        return EXIT_ERROR
    secs = round((datetime.now(timezone.utc) - t0).total_seconds(), 1)
    payload = result.model_dump() if hasattr(result, 'model_dump') else result
    if args.json:
        emit_json(envelope(True, 'validated', {'task': args.task, 'result': payload,
                                               'profile_model': meta.get('model'), 'seconds': secs,
                                               'sections': meta.get('sections')}))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"[{args.task} · profile {meta.get('model')} · {secs}s · validation {meta.get('validation')}]",
              file=sys.stderr)
    return EXIT_OK


def _doctor_pack_row(pack: Path) -> tuple:
    """The pack row: load + geometry, neutral words, one line."""
    try:
        w = load_pack(pack)
        errors = validate(w, pack_dir=pack)
        if errors:
            return ('pack', 'FAIL',
                    f'{pack.name}: {len(errors)} problem(s) - '
                    f'norns validate --pack {pack}')
        return ('pack', 'ok',
                f'{pack.name}: geometry, reachability, voices pass')
    except Exception as exc:  # a missing/broken pack is doctor's business
        return ('pack', 'FAIL', f'{pack.name}: {exc}')


def _doctor_local_rows(pack: Path) -> list[tuple]:
    """git, tree, tests, pack - the rows norns doctor and vefr doctor share."""
    rows: list[tuple] = [('git',) + q1_sync()]
    tree = q2_dirty()
    if tree[0] != 'unavailable':
        rows.append(('tree',) + tree)

    repo = repo_root()
    if repo:
        rows.append(('tests',) + _pytest_summary(repo))
    else:
        rows.append(('tests', 'skip', 'no git checkout (container install)'))

    rows.append(_doctor_pack_row(pack))
    return rows


def _doctor_live_row() -> tuple:
    """The live row: VEFR_LIVE_URL, else the deploy.toml declared url."""
    repo = repo_root()
    live = os.environ.get('VEFR_LIVE_URL')
    if not live and repo:
        # No env var? deploy.toml's url is the operator's declared
        # live endpoint - one command tells the whole truth.
        live = _deploy_toml(repo).get('url')
    if not live:
        return ('live', 'skip',
                'set VEFR_LIVE_URL (or add url to deploy.toml) '
                'to check a running stack')
    try:
        payload = fetch(live.rstrip('/') + '/api/health', timeout=5)
        ok = bool(payload.get('ok'))
        return ('live', 'ok' if ok else 'DOWN', live)
    except Exception as exc:
        return ('live', 'DOWN', f'{live} - {exc.__class__.__name__}')


def _doctor_report(args, rows, header: str) -> int:
    """One line per check, then the counts - both doctors' shape.

    Exit 1 only when a local check FAILs; a slow or down remote is
    reported in its row, never counted as a failure.
    """
    failed = sum(1 for r in rows if r[1] == 'FAIL')
    skipped = sum(1 for r in rows if r[1] == 'skip')
    ok_n = len(rows) - failed - skipped
    from . import devtools

    # The optional dev tools: informational only. A missing tool never
    # changes the exit code and is never counted in the summary.
    tooling = devtools.tooling_checks(repo_root() or Path('.'))
    if getattr(args, 'json', False):
        emit_json(envelope(not failed, 'healthy' if not failed else 'unhealthy', {
            'checks': rows_json(rows, ('name', 'status', 'detail')),
            'counts': {'ok': ok_n, 'failed': failed, 'skipped': skipped},
            'tooling': rows_json(tooling, ('name', 'status', 'detail'))}))
        return EXIT_ERROR if failed else EXIT_OK
    print(header)
    for name, status, detail in rows:
        print(f'  {name:<6} {status:<12} {detail}')
    print(f'doctor: {ok_n} ok, {failed} failed, {skipped} skipped')
    print('tooling:')
    for name, status, detail in tooling:
        print(f'  {name}  {status}  {detail}')
    return 1 if failed else 0


def cmd_doctor(args) -> int:
    """Session-start health check - norns doctor.

    One command instead of the manual checklist: git sync state,
    the working tree, the test gate, the current pack's geometry,
    and (when VEFR_LIVE_URL is set) a running stack's /api/health.
    Neutral words only. Exit 1 only when something local is broken
    (tests, pack); a remote that answers slowly is reported, not
    failed.
    """
    pack = Path(args.pack)
    if not pack.is_absolute():
        pack = pack_root() / 'worlds' / pack
    rows = _doctor_local_rows(pack)
    rows.append(_doctor_live_row())
    return _doctor_report(args, rows, 'norns doctor')


def _resolved_pack() -> Path:
    """The world the engine is pointed at (VEFR_WORLD, else the default)."""
    return pack_root() / 'worlds' / world_name()


def _doctor_pack_path(pack_arg) -> Path:
    # NOTE: the plan says "keep --pack" - so vefr doctor resolves it
    # exactly like norns doctor: a worlds/ name or an absolute path.
    # The worlds/<name> spelling belongs to `vefr check` (maplab).
    p = Path(pack_arg)
    return p if p.is_absolute() else pack_root() / 'worlds' / p


def cmd_vefr_doctor(args) -> int:
    """`vefr doctor` - one check list, the whole estate asked once.

    norns doctor's rows (git, tree, tests, pack, live) plus the three
    answers skipa carried: the deployment (Q3), backup freshness (Q5)
    and vault persistence (Q6). Same neutral one-line-per-check style,
    same exit rule: 1 only when something local is broken; a slow or
    down remote is reported, not failed.
    """
    pack = (_doctor_pack_path(args.pack) if args.pack is not None
            else _resolved_pack())
    rows = _doctor_local_rows(pack)
    rows.append(_doctor_live_row())
    url = args.url
    if url == DEFAULT_URL:
        # The silent default is the dev box, not the deploy host -
        # deploy.toml's url is the declared live endpoint (skipa's rule).
        url = _deploy_toml().get('url') or url
    # NOTE: 'live' (doctor's row) and 'deploy' (skipa's Q3) both probe
    # /api/health - from different declarations (VEFR_LIVE_URL vs
    # --url/deploy.toml), and Q3 also runs the shadow check. Both stay,
    # so this stays ONE list, not two reports.
    rows.extend([
        ('deploy',) + q3_deployment(url, args.deploy_host),
        ('backup',) + q5_backups(args.nas_host),
        ('vault',) + q6_vault(args.deploy_host),
    ])
    return _doctor_report(args, rows, 'vefr doctor')


def cmd_storyteller_test(args) -> int:
    """norns storyteller-test - run a scene through one or all packs.

    Single-model: --model <id>
    Matrix: --matrix
    """
    from .storyteller import find_pack, list_packs
    from .storyteller_test import (
        audition_one,
        build_blind_map,
        list_fixtures,
        load_fixture,
        write_artifacts,
    )

    scene_id = getattr(args, "scene", None) or "sample-scene"
    available = list_fixtures()
    if scene_id not in available:
        print(f"unknown scene {scene_id!r}. available:")
        for sid in available:
            print(f"  - {sid}")
        if not available:
            print(
                "  (none found - set VEFR_STORYTELLER_FIXTURES to a "
                "directory of scene fixtures)"
            )
        return 1
    scene = load_fixture(scene_id)

    runs_per = max(1, int(getattr(args, "runs", 1) or 1))
    seed = getattr(args, "seed", None)
    if seed is not None:
        seed = int(seed)
    blind = bool(getattr(args, "blind", False))

    if getattr(args, "matrix", False):
        packs = list_packs()
    else:
        target = getattr(args, "model", None)
        if not target:
            print("--model <pack_id> is required (or pass --matrix)")
            return 1
        pack = find_pack(target)
        if pack is None:
            print(f"unknown storyteller pack {target!r}.")
            print("available packs:")
            for p in list_packs():
                print(f"  - {p.id} ({p.model})")
            return 1
        packs = [pack]

    print("=== STORYTELLER AUDITION ===")
    print(f"scene: {scene_id} v{scene.version}")
    print(f"runs per pack: {runs_per}")
    print(f"packs: {len(packs)}")
    print()

    results = []
    for pack in packs:
        for n in range(1, runs_per + 1):
            label = pack.id
            print(f"--- {label} | run {n}/{runs_per} ---")
            result = audition_one(pack, scene, run_number=n, seed=seed)
            results.append(result)
            if result.status == "ok":
                preview = result.response.strip().splitlines()
                for line in preview[:6]:
                    print(f"  {line}")
                if len(preview) > 6:
                    print(f"  ... ({len(preview) - 6} more lines)")
                print(f"  [{result.latency_s:.2f}s]")
            elif result.status == "skipped":
                print(f"  SKIPPED - {result.skip_reason}")
            else:
                print(f"  ERROR - {result.error}")
            print()

    out_dir = write_artifacts(results)

    if blind:
        bmap = build_blind_map(results)
        (out_dir / "blind_map.txt").write_text(
            "\n".join(f"{v} -> {k}" for k, v in bmap.items()),
            encoding="utf-8",
        )

    print(f"saved: {out_dir}")
    failed = sum(1 for r in results if r.status == "error")
    skipped = sum(1 for r in results if r.status == "skipped")
    ok = sum(1 for r in results if r.status == "ok")
    print(f"summary: {ok} ok, {skipped} skipped, {failed} error")
    return 1 if failed else 0


def cmd_storyteller_benchmark(args) -> int:
    """norns storyteller-benchmark - blind A/B/C/D capability review.

    Three modes:
      run       - execute the full benchmark, write blind review files
      reveal    - print the identity mapping + tech context for an existing run
      review    - print the blank review worksheet for an existing run
    """
    from .storyteller import find_pack, list_packs
    from .storyteller_benchmark import (
        default_packs,
        list_default_fixtures,
        render_reveal,
        run_benchmark,
    )

    mode = getattr(args, "benchmark_cmd", "run")

    if mode == "reveal":
        out_dir = Path(getattr(args, "out_dir", ""))
        if not out_dir.is_dir():
            print(f"not a directory: {out_dir}")
            return 1
        # Build pack-context strings from the current pack list so the
        # reveal can show model + license + quant next to each label.
        extra: dict[str, str] = {}
        for pack in list_packs():
            lic = pack.license
            spdx = (lic.spdx if lic else "") or "?"
            comm = (lic.commercial_use if lic else "") or "?"
            quant = (pack.install.recommended_quant if pack.install else "") or "?"
            extra[pack.id] = (
                f"model={pack.model}  quant={quant}  "
                f"license={spdx}  commercial_use={comm}"
            )
        print(render_reveal(out_dir, extra_context=extra))
        return 0

    if mode == "review":
        out_dir = Path(getattr(args, "out_dir", ""))
        worksheet = out_dir / "review" / "WORKSHEET.txt"
        if not worksheet.is_file():
            print(f"no worksheet at {worksheet}")
            return 1
        print(worksheet.read_text(encoding="utf-8"))
        return 0

    # mode == "run"
    fixtures = list_default_fixtures()
    if not fixtures:
        print("no benchmark fixtures found under tests/fixtures/storyteller/")
        return 1

    if getattr(args, "pack", None):
        packs = []
        for name in args.pack:
            pack = find_pack(name)
            if pack is None:
                print(f"unknown storyteller pack {name!r}")
                return 1
            packs.append(pack)
    elif getattr(args, "model", None):
        pack = find_pack(getattr(args, "model"))
        if pack is None:
            print(f"unknown storyteller pack {getattr(args, 'model')!r}")
            return 1
        packs = [pack]
    else:
        packs = default_packs()
        if getattr(args, "exclude", None):
            packs = [p for p in packs if p.id not in set(args.exclude)]

    if not packs:
        print("no storyteller packs configured; install one under data/storytellers/")
        return 1

    runs_per = max(1, int(getattr(args, "runs", 3) or 3))
    seed = getattr(args, "seed", None)
    if seed is not None:
        seed = int(seed)

    print("=== STORYTELLER CAPABILITY BENCHMARK ===")
    print(f"fixtures: {len(fixtures)}")
    print(f"packs: {len(packs)}")
    print(f"runs per (fixture, pack): {runs_per}")
    print(f"blind mapping seed: {seed if seed is not None else 'system-random'}")
    print()

    def progress(fixture_id: str, pack_id: str, run_number: int, status: str) -> None:
        marker = {"ok": ".", "skipped": "S", "error": "E"}.get(status, "?")
        print(f"  {fixture_id:24s} {pack_id:24s} run {run_number}: {marker}")

    out_dir, mapping = run_benchmark(
        packs,
        fixtures,
        runs_per=runs_per,
        seed=seed,
        progress=progress,
    )

    review_dir = out_dir / "review"
    print()
    print(f"saved blind review: {review_dir}")
    print(f"identity mapping (PRIVATE): {out_dir / 'identity.json'}")
    print()
    print("review order:")
    for f in sorted(review_dir.glob("[0-9][0-9]-*.txt")):
        print(f"  {f.name}")
    print()
    print(
        "open the review files in order. read prose. write your rankings "
        "in review/WORKSHEET.txt. do not open identity.json until you "
        "are done."
    )
    return 0


def norns_main() -> int:
    ap = argparse.ArgumentParser(
        prog='norns', description=NORNS_HELP,
        epilog="the same verbs now spell as vefr: vefr chat, vefr check, "
               "vefr map, vefr delve (vefr --help)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    craft = ap.add_subparsers(dest='craft_cmd', required=True)

    mc = craft.add_parser('chat', help='interview a new world into existence')
    mc.add_argument('--name', required=True, help='the new pack name (worlds/<name>)')
    mc.set_defaults(fn=cmd_chat)

    mm = craft.add_parser(
        'migrate', help='migrate a flat-shape pack to the acts tree'
    )
    mm.add_argument('--pack', required=True,
                    help='the world pack name (worlds/<pack>)')
    mm.add_argument('--act-id', default=None,
                    help='act id for the new tree (default: act-1)')
    mm.set_defaults(fn=cmd_migrate)

    mv = craft.add_parser('validate', help='geometry checks against the pack')
    mv.add_argument('--pack', default=None)
    mv.set_defaults(fn=cmd_map, map_cmd='validate', segments=None, force=False)

    mb = craft.add_parser('build-map', help='rebuild the map from run-length rows')
    mb.add_argument('--segments', required=True)
    mb.add_argument('--pack', default=None)
    mb.add_argument('--force', action='store_true')
    mb.set_defaults(fn=cmd_map, map_cmd='build')

    mdl = craft.add_parser(
        'delve',
        help='generate dungeon floors from a seed and wire their stairs',
    )
    mdl.add_argument('--pack', required=True,
                     help='world pack name (worlds/<name>) or a path')
    mdl.add_argument('--seed', required=True,
                     help='the determinism seed; the same seed redraws the same floors')
    mdl.add_argument('--floors', type=int, default=1,
                     help='how many floors to generate (default: 1)')
    mdl.add_argument('--from-region', required=True,
                     help='the region whose stair leads down')
    mdl.add_argument('--from-at', required=True,
                     help='the walkable stair tile in --from-region, as x,y')
    mdl.add_argument('--width', type=int, default=30)
    mdl.add_argument('--height', type=int, default=20)
    mdl.add_argument('--rooms', type=int, default=8)
    mdl.add_argument('--first-name', default=None,
                     help='first generated region name (default: floor-2, or '
                          'the next free floor-N after existing regions)')
    mdl.add_argument('--section', default=None,
                     help='bake a whole Section from sections/<id>.json: one '
                          'region per floor, its own size and kind per floor, '
                          'and the landings wired back to --from-region')
    mdl.add_argument('--force', action='store_true',
                     help='overwrite an existing generated region')
    mdl.set_defaults(fn=cmd_delve)

    mr = craft.add_parser('verify', help='validate a live deployment')
    mr.add_argument('--url', default=DEFAULT_URL)
    mr.set_defaults(fn=cmd_map, map_cmd='verify', segments=None, force=False,
                    pack=None)

    mh = craft.add_parser(
        'handbok', help='write the mechanics manual from real play'
    )
    mh.add_argument('--pack', default=None)
    mh.add_argument('--session', default=None,
                    help='play session to read (default: the default one)')
    mh.set_defaults(fn=cmd_handbok)

    md = craft.add_parser(
        'doctor',
        help='session-start health check: git, tests, pack, live stack',
    )
    md.add_argument('--pack', default=None)
    md.add_argument('--json', action='store_true', help='print the result envelope')
    md.set_defaults(fn=cmd_doctor)

    mt = craft.add_parser(
        'storyteller-test',
        help='run a VEFR scene through one or all Storyteller Packs',
    )
    mt.add_argument('--model', default=None,
                    help='pack id or model name to run (mutually exclusive with --matrix)')
    mt.add_argument('--matrix', action='store_true',
                    help='run the scene through every installed pack')
    mt.add_argument('--scene', default=None,
                    help='scene fixture id (default: sample-scene)')
    mt.add_argument('--runs', type=int, default=1,
                    help='repetitions per pack (default: 1; 3 recommended for creative models)')
    mt.add_argument('--seed', type=int, default=None,
                    help='record a seed for reproducibility (informational; providers that support it will)')
    mt.add_argument('--blind', action='store_true',
                    help='label outputs Storyteller A/B/C and write a blind_map.txt for later reveal')
    mt.set_defaults(fn=cmd_storyteller_test)

    mb = craft.add_parser(
        'storyteller-benchmark',
        help='run the blind A/B/C/D story capability benchmark',
    )
    bench = mb.add_subparsers(dest='benchmark_cmd')
    bench.required = True

    mb_run = bench.add_parser('run', help='execute the full benchmark and write blind review files')
    mb_run.add_argument('--model', default=None,
                        help='benchmark only this pack (default: every installed pack)')
    mb_run.add_argument('--pack', action='append', default=None,
                        help='restrict to one or more pack ids; may be repeated. '
                             'Overrides --model if both are passed.')
    mb_run.add_argument('--exclude', action='append', default=None,
                        help='drop these pack ids from the default roster; may be repeated.')
    mb_run.add_argument('--runs', type=int, default=3,
                        help='repetitions per (fixture, pack) (default: 3)')
    mb_run.add_argument('--seed', type=int, default=None,
                        help='seed the blind label assignment so mapping is reproducible (default: system-random)')
    mb_run.set_defaults(fn=cmd_storyteller_benchmark)

    mb_reveal = bench.add_parser('reveal',
                                 help='print identity mapping + tech context for an existing run')
    mb_reveal.add_argument('--out-dir', required=True,
                           help='the artifact directory the benchmark run wrote to')
    mb_reveal.set_defaults(fn=cmd_storyteller_benchmark)

    mb_review = bench.add_parser('review',
                                 help='print the blank review worksheet for an existing run')
    mb_review.add_argument('--out-dir', required=True,
                           help='the artifact directory the benchmark run wrote to')
    mb_review.set_defaults(fn=cmd_storyteller_benchmark)

    args = ap.parse_args()
    # validate / build-map / verify / doctor default --pack to the
    # resolved world; chat doesn't take --pack and doesn't need the
    # lookup.
    if args.craft_cmd in ('validate', 'build-map', 'verify', 'doctor') \
            and getattr(args, 'pack', None) is None:
        args.pack = pack_root() / 'worlds' / world_name()
    from .blueprint import BlueprintRefusal
    try:
        return args.fn(args)
    except BlueprintRefusal as exc:
        print(f'refused: {exc}', file=sys.stderr)
        return EXIT_ERROR


def cmd_find(args) -> int:
    """`vefr find` - a local, read-only search, delegated.

    The search itself lives in vefr.find (the cmd_chat/cmd_delve
    pattern): markdown lines and the journal go into an FTS5 index
    that exists only in memory for this run - nothing in the pack is
    written, moved, or migrated, and no HTTP route answers for it.

    Two distinct failures, never confused: a pack that is not there
    is refused (exit 1, named on its own line); a search that found
    nothing did what it was asked, so UNKNOWN prints and exit is 0.
    """
    from . import find as find_mod

    if getattr(args, 'pack', None) is None:
        pack = pack_root() / 'worlds' / world_name()
    else:
        p = Path(args.pack)
        if p.is_absolute():
            pack = p
        elif '/' in str(args.pack):
            # A path spelling (`--pack worlds/<name>`), resolved
            # against this run's cwd - the way cmd_delve/cmd_build_web
            # read it.
            pack = p.resolve()
        else:
            pack = pack_root() / 'worlds' / p
    # NOTE: the refusal checks world.json, not merely a directory -
    # the house pattern (cmd_handbok, cmd_build_web) and the more
    # restrictive reading: a directory that is not a pack is refused
    # the same way a missing one is.
    if not (pack / 'world.json').exists():
        print(f'pack not found at {pack}; pass --pack NAME or a path')
        return EXIT_ERROR

    hits = find_mod.search(args.query, pack)
    if not hits:
        print('UNKNOWN')
        return EXIT_OK
    for h in hits:
        print(f'{h.path}:{h.line} [{h.source}] {h.excerpt}')
    return EXIT_OK


def _authoring_pack(args) -> Path:
    """Resolve --pack for the read-only authoring verbs (where, explain) the
    same way cmd_find does: a bare name is worlds/<name>, a path spelling is
    resolved against this run's cwd, and no --pack is the resolved world."""
    if getattr(args, 'pack', None) is None:
        return pack_root() / 'worlds' / world_name()
    p = Path(args.pack)
    if p.is_absolute() or '/' in str(args.pack):
        return p.resolve()
    return pack_root() / 'worlds' / p


def _at_cell(xy) -> str:
    """` at x,y` for a record that carries a tile, and nothing otherwise."""
    if isinstance(xy, (list, tuple)) and len(xy) == 2 \
            and all(isinstance(v, int) for v in xy):
        return f' at {xy[0]},{xy[1]}'
    return ''


def where_hits(world: dict, thing_id: str) -> list[str]:
    """Every place the pack defines `thing_id`, one line each, in a fixed
    order: the act and region that hold it, and its map cell where the
    record has one. Read-only - the pack is loaded and never written.

    The records a thing id can name today: a speaker, an enemy, a named
    point of interest (a map cell whose `pois` value is the thing), and an
    item in the pack's catalog. A pack that names the thing nowhere gets [].
    """
    out: list[str] = []
    act = world.get('_act_id') or ''
    region = world.get('_region') or ''

    def where(a, r):
        return f'{a}/{r}' if a else (r or 'town')

    spec = (world.get('speakers') or {}).get(thing_id)
    if isinstance(spec, dict):
        r = spec.get('region') or region
        out.append(f'speaker {thing_id}: {where(act, r)}{_at_cell(spec.get("at"))}')
    for a in (world.get('acts') or []):
        aid = a.get('id') or act
        for rname, rdata in (a.get('regions') or {}).items():
            contract = (rdata or {}).get('contract') or {}
            for e in (contract.get('enemies') or []):
                if isinstance(e, dict) and e.get('id') == thing_id:
                    out.append(f'enemy {thing_id}: {where(aid, rname)}{_at_cell(e.get("at"))}')
            for cell, name in (contract.get('pois') or {}).items():
                if name == thing_id:
                    out.append(f'place {thing_id}: {where(aid, rname)} at {cell}')
    # A flat pack keeps its ground in `town`; the acts shape above already
    # covered the first region, so a duplicate line is dropped.
    for cell, name in ((world.get('town') or {}).get('pois') or {}).items():
        if name == thing_id:
            line = f'place {thing_id}: {where(act, region)} at {cell}'
            if line not in out:
                out.append(line)
    if thing_id in (world.get('items') or {}):
        out.append(f'item {thing_id}: the pack catalog (world.json)')
    return out


def cmd_where(args) -> int:
    """`vefr where <id>` - which act, region and map cell define a thing.

    A read-only authoring answer, the same failure shapes as cmd_find: a
    pack that is not there is refused (exit 1, named on its own line); an
    id the pack defines nowhere did what it was asked, so UNKNOWN prints
    and exit is 0.
    """
    from . import maplab

    pack = _authoring_pack(args)
    if not (pack / 'world.json').exists():
        print(f'pack not found at {pack}; pass --pack NAME or a path')
        return EXIT_ERROR
    hits = where_hits(maplab.load_pack(pack), args.thing)
    if not hits:
        print('UNKNOWN')
        return EXIT_OK
    for line in hits:
        print(line)
    return EXIT_OK


# The world.json blocks `vefr explain` knows, each with the validator
# sentences that belong to it. A block the pack declares none of reads
# as null and prints `ok` - declaring nothing is not a fault.
def _explain_blocks() -> dict:
    from . import maplab

    def _items(w, _pack):
        out: list[str] = []
        key_ids = maplab._door_key_items(w)
        spell_ids = maplab.spell_ids_of(w)
        verb_ids = maplab.pack_verbs(w)
        for iid, spec in (w.get('items') or {}).items():
            if isinstance(spec, dict):
                out.extend(maplab.item_light_errors(iid, spec))
                out.extend(maplab.item_slot_errors(iid, spec, key_ids))
                out.extend(maplab.item_roll_errors(iid, spec))
                out.extend(maplab.item_spell_errors(iid, spec, spell_ids))
                out.extend(maplab.item_grants_errors(iid, spec, verb_ids))
        return out

    return {
        'album': lambda w, p: maplab.album_errors(w, p),
        'bag': lambda w, p: maplab.bag_errors(w),
        'descent': lambda w, p: maplab.descent_errors(w, p),
        'display': lambda w, p: maplab.display_errors(w),
        'grammars': lambda w, p: maplab.grammar_errors(w.get('grammars') or {}),
        'growth': lambda w, p: maplab.growth_errors(w),
        'identify': lambda w, p: maplab.identify_errors(w),
        'items': _items,
        'player_words': lambda w, p: maplab.player_words_errors(w),
        'rules': lambda w, p: maplab.rules_errors(w, p),
        'saves': lambda w, p: maplab.saves_errors(w),
        'skin': lambda w, p: maplab.skin_errors(w, p),
        'sound': lambda w, p: maplab.sound_errors(w),
        'spells': lambda w, p: maplab.spells_errors(w),
        'town_states': lambda w, p: maplab.town_states_errors(w),
    }


def cmd_explain(args) -> int:
    """`vefr explain <block>` - the resolved block and its validation
    sentences.

    Prints the block exactly as the loader resolved it (null when the pack
    declares none), then one line per sentence the validator writes about
    that block, or `ok` when it writes none. Read-only. A block name the
    front door does not know is refused (exit 1) with the list it does.
    """
    from . import maplab

    pack = _authoring_pack(args)
    if not (pack / 'world.json').exists():
        print(f'pack not found at {pack}; pass --pack NAME or a path')
        return EXIT_ERROR
    blocks = _explain_blocks()
    if args.block not in blocks:
        print(f'no such block: {args.block}; try one of: '
              + ', '.join(sorted(blocks)))
        return EXIT_ERROR
    world = maplab.load_pack(pack)
    print(json.dumps(world.get(args.block), indent=2, ensure_ascii=False))
    sentences = blocks[args.block](world, pack)
    if sentences:
        for sentence in sentences:
            print(sentence)
    else:
        print('ok')
    return EXIT_OK


def cmd_publish(args) -> int:
    """`vefr publish` - weave the pack and hand it to the gallery.

    The weave and the gallery call live in vefr.devtools (the
    cmd_find/vefr.find split): this door only resolves --pack the way
    cmd_build_web does, then returns devtools.publish's code.
    """
    from . import devtools

    if args.pack is None:
        pack = pack_root() / 'worlds' / world_name()
    else:
        # Bare name -> worlds/<name>; any path -> made absolute, the
        # same resolution cmd_build_web gives --pack.
        p = Path(args.pack)
        if p.is_absolute() or '/' in str(args.pack):
            pack = (p if p.is_dir() else p.parent).resolve()
        else:
            pack = pack_root() / 'worlds' / p
    return devtools.publish(
        pack, project=args.project, sha=args.sha, live=args.live,
        dry_run=args.dry_run)


def _devtools_pack(pack_arg):
    """Resolve --pack for the devtools verbs the way cmd_build_web does."""
    if pack_arg is None:
        return _resolved_pack()
    p = Path(pack_arg)
    if p.is_absolute() or '/' in str(pack_arg):
        return (p if p.is_dir() else p.parent).resolve()
    return pack_root() / 'worlds' / p


def cmd_look(args) -> int:
    """`vefr look` - screenshot the woven player and list overlay text.

    The browser work lives in vefr.devtools (the cmd_find/vefr.find
    split): this door only resolves --pack when --html is not given.
    """
    from . import devtools

    pack = None if args.html else _devtools_pack(args.pack)
    return devtools.look(html=args.html, pack=pack, out=args.out,
                         steps=args.steps, json_out=args.json,
                         scenario=getattr(args, "scenario", None),
                         sizes=getattr(args, "sizes", None),
                         at=getattr(args, "at", None),
                         seed=getattr(args, "seed", None))


def cmd_probe(args) -> int:
    """`vefr probe` - fire rules at the woven player and read the why log.

    Like cmd_look, the browser work is devtools'; this door resolves
    --pack when --html is not given.
    """
    from . import devtools

    pack = None if args.html else _devtools_pack(args.pack)
    return devtools.probe(html=args.html, pack=pack, fire=args.fire or (),
                          json_out=args.json, scenario=getattr(args, "scenario", None))


def cmd_features(args) -> int:
    """`vefr features` - what VEFR can do, and what a pack uses.

    The catalog logic lives in vefr.features (the cmd_find/vefr.find
    split): this door only resolves --pack the way cmd_build_web does,
    then reports. Read-only: no model call, and scanning a pack reads
    its files without writing them.

    Three readings of the same catalog: --check is the drift gate,
    --json the whole report as one object, and the default a short
    table of every feature and (with --pack) which it uses.
    """
    from . import features

    if getattr(args, 'check', False):
        errors = features.catalog_errors()
        if errors:
            for line in errors:
                print(line)
            return EXIT_ERROR
        print('catalog ok')
        return EXIT_OK

    pack = None
    if getattr(args, 'pack', None) is not None:
        # Bare name -> worlds/<name>; any path -> made absolute, the
        # same resolution cmd_build_web gives --pack.
        p = Path(args.pack)
        if p.is_absolute() or '/' in str(args.pack):
            pack = (p if p.is_dir() else p.parent).resolve()
        else:
            pack = pack_root() / 'worlds' / p

    rep = features.report(pack)
    if getattr(args, 'json', False):
        print(json.dumps(rep))
        return EXIT_OK

    if rep['pack'] is not None:
        print(f"pack: {rep['pack']['name']}")
    uses = {u['id']: u for u in (rep['pack']['uses'] if rep['pack'] else [])}
    for feat in rep['catalog']:
        use = uses.get(feat.get('id'))
        if use is None:
            state, detail = 'unknown', feat.get('name', '')
        else:
            used = use.get('used')
            state = ('used' if used is True
                     else 'not used' if used is False else 'unknown')
            detail = use.get('detail') or feat.get('name', '')
        print(f"{feat.get('id', '')}  {feat.get('status', '')}  {state}  {detail}")
    print()
    return EXIT_OK


def cmd_normalize(args) -> int:
    """`vefr normalize` - expand a Blueprint and report or refresh its pack.

    Read-only without `--out`: one line per owned region and whether the
    committed output is fresh, exit 0 only when it is. With `--out` the
    pack is refreshed in place (or copied to a new/empty directory and
    refreshed there), then validated as a whole; a failure exits 1 with
    the validator's own sentences and leaves the previous bytes in place.
    The Blueprint library does the work; this door only resolves `--pack`.
    """
    from . import blueprint

    if getattr(args, 'pack', None) is None:
        pack = _resolved_pack()
    else:
        p = Path(args.pack)
        if p.is_absolute() or '/' in str(args.pack):
            pack = (p if p.is_dir() else p.parent).resolve()
        else:
            pack = pack_root() / 'worlds' / p
    out = Path(args.out).resolve() if getattr(args, 'out', None) else None

    if out is None and not (pack / 'blueprint.json').exists() \
            and not (pack / 'blueprint.lock.json').exists():
        # Nothing to be fresh about: say so, and succeed (a plain pack is fine).
        print(f'no blueprint.json in {pack}; nothing to normalize')
        return EXIT_OK

    result = blueprint.normalize(pack, out)
    if out is None:
        for region, count in result.regions.items():
            print(f'{region}: {count} enemies')
        if result.fresh:
            print('fresh')
            return EXIT_OK
        for line in result.errors:
            print(line)
        return EXIT_ERROR
    if result.errors:
        for line in result.errors:
            print(line)
        return EXIT_ERROR
    return EXIT_OK


# --------------------------------------------------------------- vefr
# The front door: one parser over the same functions the old commands
# call. No logic lives here - only wiring, flags, and help text.

VEFR_HELP = """vefr - the front door: make a world, check it, carry it, share it.

Every verb answers `vefr <verb> --help` with its own flags.
Two escape hatches run the old CLIs verbatim:
`vefr norns ARGS...` and `vefr ratatoskr ARGS...`.
"""

VEFR_EPILOG = """the journey, in the order an author walks it:

  chat      say what the game is; interview a world into being
            see: docs/guides/journey.md, docs/guides/world-creation.md
  map       draw the first place; the validator checks it
            see: docs/guides/world-creation.md
  delve     floors below the floors, drawn from a seed
  spark     the resident small brain, local and answerable
            see: docs/guides/spark.md, docs/guides/bundled-brain.md
  test      the gate before anything moves
  check     validate before you move on (--live checks the running stack)
            see: docs/guides/journey.md, docs/guides/world-creation.md
  weave     the shareable file: one self-contained HTML
            see: docs/guides/journey.md, docs/guides/world-creation.md
  archive   the portable game file: one .vefr, opened by the shared Player
            see: docs/adr/0019-vefr-archive-format.md
  handbok   the mechanics, counted from real play
  ferry     carry the world between the boxes
  doctor    session-start health: the whole estate, asked once
  skipa     the seven questions, now part of: vefr doctor

beside the journey: the read-only authoring answers `vefr where`
(which act, region and cell define a thing) and `vefr explain` (a
resolved block and its validator sentences); vefr-lore (see:
docs/guides/lore.md) and the volume tools under
`vefr ratatoskr volumes` (see: docs/guides/volumes.md).
"""


def vefr_main() -> int:
    """The `vefr` front door - Task 1's one entry point.

    Every verb set_defaults to the SAME function the old command
    calls (cmd_map's map_cmd attribute included); the two escape
    hatches hand argv to norns_main/ratatoskr_main untouched.
    """
    ap = argparse.ArgumentParser(
        prog='vefr', description=VEFR_HELP, epilog=VEFR_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest='cmd', required=True)

    # `find`: the seam the earlier NOTE named, filled - one parser,
    # one set_defaults, wired straight to cmd_find (which delegates
    # the search to vefr.find).
    fd = sub.add_parser(
        'find',
        help='local read-only search of the pack markdown and the journal',
        description='local, read-only search of the pack markdown and the journal',
        epilog='see: docs/guides/vefr-command.md',
    )
    fd.add_argument('query', help='what to look for: plain words, matched as terms')
    fd.add_argument('--pack', default=None,
                    help='world pack: a worlds/ name or a path '
                         '(default: the resolved world)')
    fd.set_defaults(fn=cmd_find)

    # `where` and `explain`: read-only authoring answers over the same
    # pack the front door already resolves - which act/region/cell hold
    # a thing, and what a resolved world.json block plus its validator
    # sentences look like. No model call, no writes.
    wh = sub.add_parser(
        'where',
        help='which act, region and map cell define a thing',
        description='read-only: which act, region and map cell define a thing',
        epilog='see: docs/guides/vefr-command.md',
    )
    wh.add_argument('thing', help='the id to locate: a speaker, an enemy, a place or an item')
    wh.add_argument('--pack', default=None,
                    help='world pack: a worlds/ name or a path '
                         '(default: the resolved world)')
    wh.set_defaults(fn=cmd_where)

    ex = sub.add_parser(
        'explain',
        help='a resolved world.json block and the validator sentences it earns',
        description='read-only: a resolved world.json block and the validator '
                    'sentences it earns',
        epilog='see: docs/guides/vefr-command.md',
    )
    ex.add_argument('block', help='the block to explain: growth, spells, skin, rules, ...')
    ex.add_argument('--pack', default=None,
                    help='world pack: a worlds/ name or a path '
                         '(default: the resolved world)')
    ex.set_defaults(fn=cmd_explain)

    pb = sub.add_parser(
        'publish',
        help='weave the pack and publish it to the gallery',
        description='weave the pack and publish it to the gallery',
        epilog='see: docs/guides/vefr-command.md',
    )
    pb.add_argument('--pack', default=None,
                    help='world pack: a worlds/ name or a path '
                         '(default: the resolved world)')
    pb.add_argument('--project', default=None,
                    help='gallery project name (default: the pack directory name)')
    pb.add_argument('--sha', default=None,
                    help='revision to record (default: HEAD of the pack)')
    pb.add_argument('--live', action='store_true',
                    help='mark the build live in the gallery')
    pb.add_argument('--dry-run', action='store_true',
                    help='print the gallery command without running it')
    pb.set_defaults(fn=cmd_publish)

    lk = sub.add_parser(
        'look',
        help='screenshot the woven player and list text over the map',
        description='screenshot the woven player and list text over the map',
        epilog='see: docs/guides/vefr-command.md',
    )
    lk.add_argument('--html', default=None,
                    help='a woven player HTML file to open')
    lk.add_argument('--pack', default=None,
                    help='weave this pack instead: a worlds/ name or a path')
    lk.add_argument('--out', default=None,
                    help='screenshot path (default: look.png)')
    lk.add_argument('--steps', default='',
                    help='comma-separated keys to press after Begin')
    lk.add_argument('--scenario', default=None, metavar='NAME',
                    help="open the game in the pack's scenarios/NAME.json "
                         'state first (needs --pack)')
    lk.add_argument('--sizes', action='append', default=None, metavar='WxH',
                    help='photograph the pack at this size; repeatable or '
                         'comma-separated, one file per size '
                         '(default: 1280x800)')
    lk.add_argument('--at', default=None, metavar='REGION X,Y',
                    help='start the run in this region at this tile '
                         '(needs --pack)')
    lk.add_argument('--seed', default=None, metavar='SEED',
                    help="ask the game for this run seed (the descent's "
                         '?vefr-seed= parameter)')
    lk.add_argument('--json', action='store_true', help='print the report as JSON')
    lk.set_defaults(fn=cmd_look)

    pr = sub.add_parser(
        'probe',
        help='fire rules at the woven player and read its why log',
        description='fire rules at the woven player and read its why log',
        epilog='see: docs/guides/vefr-command.md',
    )
    pr.add_argument('--html', default=None,
                    help='a woven player HTML file to open')
    pr.add_argument('--pack', default=None,
                    help='weave this pack instead: a worlds/ name or a path')
    pr.add_argument('--fire', action='append', default=None,
                    metavar='EVENT:KEY=VALUE',
                    help='fire this rule event (repeatable)')
    pr.add_argument('--scenario', default=None, metavar='NAME',
                    help="fire in the pack's scenarios/NAME.json state "
                         '(needs --pack)')
    pr.add_argument('--json', action='store_true', help='print the report as JSON')
    pr.set_defaults(fn=cmd_probe)

    ft = sub.add_parser(
        'features',
        help='the feature catalog: what VEFR can do, and what a pack uses',
        description='the feature catalog: every VEFR feature, its status, '
                    'and (with --pack) whether the pack uses it',
        epilog='see: docs/guides/vefr-command.md',
    )
    ft.add_argument('--pack', default=None,
                    help='scan this pack: a worlds/ name or a path '
                         '(default: catalog only)')
    ft.add_argument('--json', action='store_true',
                    help='print the report as one JSON object')
    ft.add_argument('--check', action='store_true',
                    help='print catalog drift errors and exit 1 if any')
    ft.set_defaults(fn=cmd_features)

    nz = sub.add_parser(
        'normalize',
        help='expand a Blueprint into generated enemies and write its lock',
        description='expand a Blueprint into the regions it owns, refresh '
                    'them and blueprint.lock.json, or report if they are fresh',
        epilog='see: docs/adr/0008-blueprint-format.md',
    )
    nz.add_argument('--pack', default=None,
                    help='world pack: a worlds/ name or a path '
                         '(default: the resolved world)')
    nz.add_argument('--out', default=None,
                    help='refresh this pack, or copy into a new/empty DIR; '
                         'omit for a read-only freshness report')
    nz.set_defaults(fn=cmd_normalize)

    dc = sub.add_parser(
        'doctor',
        help='session-start health: the whole estate, asked once',
        description='session-start health: git, tests, pack, live, backups, vault',
    )
    # NOTE: --url/--deploy-host/--nas-host are ratatoskr's globals,
    # declared here on the verb that reads them (the deployment,
    # backup and vault checks); the defaults are ratatoskr's own.
    dc.add_argument('--url', default=DEFAULT_URL)
    dc.add_argument('--deploy-host', default=DEFAULT_DEPLOY_HOST)
    dc.add_argument('--nas-host', default=DEFAULT_BACKUP_HOST)
    dc.add_argument('--pack', default=None,
                    help='world to check: a worlds/ name or a path '
                         '(default: the resolved world)')
    dc.add_argument('--json', action='store_true', help='print the result envelope')
    dc.set_defaults(fn=cmd_vefr_doctor)

    ck = sub.add_parser(
        'check',
        help='validate a pack, or a live deployment with --live URL',
        description='validate a pack; with --live URL, validate the running stack instead',
        epilog='see: docs/guides/journey.md, docs/guides/world-creation.md',
    )
    ck.add_argument('--pack', default=None,
                    help='world pack (default: the resolved world)')
    ck.add_argument('--live', default=None, metavar='URL',
                    help='validate this running deployment instead')
    ck.add_argument('--release', action='store_true',
                    help='list every draft word in the pack (vefr #339); '
                         'lists and exits 0')
    ck.add_argument('--strict', action='store_true',
                    help='exit non-zero when the pack holds a draft word; '
                         'the list is printed first either way')
    ck.set_defaults(fn=cmd_map, map_cmd='validate', segments=None, force=False)

    ch = sub.add_parser(
        'chat', help='interview a new world into existence',
        description='interview a new world into existence',
        epilog='see: docs/guides/journey.md, docs/guides/world-creation.md',
    )
    ch.add_argument('--name', required=True, help='the new pack name (worlds/<name>)')
    ch.set_defaults(fn=cmd_chat)

    mp = sub.add_parser(
        'map', help='rebuild the map from run-length rows',
        description='rebuild the map from run-length rows',
        epilog='see: docs/guides/world-creation.md',
    )
    mp.add_argument('--segments', required=True)
    mp.add_argument('--pack', default=None)
    mp.add_argument('--force', action='store_true')
    mp.set_defaults(fn=cmd_map, map_cmd='build')

    dl = sub.add_parser(
        'delve',
        help='generate dungeon floors from a seed',
        description='generate dungeon floors from a seed and wire their stairs',
    )
    dl.add_argument('--pack', required=True,
                    help='world pack name (worlds/<name>) or a path')
    dl.add_argument('--seed', required=True,
                    help='the determinism seed; the same seed redraws the same floors')
    dl.add_argument('--floors', type=int, default=1,
                    help='how many floors to generate (default: 1)')
    dl.add_argument('--from-region', required=True,
                    help='the region whose stair leads down')
    dl.add_argument('--from-at', required=True,
                    help='the walkable stair tile in --from-region, as x,y')
    dl.add_argument('--width', type=int, default=30)
    dl.add_argument('--height', type=int, default=20)
    dl.add_argument('--rooms', type=int, default=8)
    dl.add_argument('--first-name', default=None,
                    help='first generated region name (default: floor-2, or '
                         'the next free floor-N after existing regions)')
    dl.add_argument('--section', default=None,
                    help='bake a whole Section from sections/<id>.json: one '
                         'region per floor, its own size and kind per floor, '
                         'and the landings wired back to --from-region')
    dl.add_argument('--force', action='store_true',
                    help='overwrite an existing generated region')
    dl.set_defaults(fn=cmd_delve)

    st = sub.add_parser(
        'stamp', help='hand-drawn rooms: check a pack before a floor uses it',
        description='the stamped rooms of ADR 0013; `check` is the gate a '
                    'stamp pack passes before a floor lays one out',
        epilog='see: docs/adr/0013-stamp-format.md',
    )
    stamp_sub = st.add_subparsers(dest='stamp_verb', required=True)
    stc = stamp_sub.add_parser(
        'check',
        help='static, fit, sweep and graph checks over a stamp pack',
        description='four kinds of check over a stamp pack: what the reader '
                    'refuses, what is too big for the floor it lands on, '
                    'how often each room places, and whether every stamped '
                    'room on a floor has a door in use and walkable anchors',
    )
    stc.add_argument('--pack', required=True,
                     help='pack directory (stamps/ and sections/) or a path')
    stc.add_argument('--seeds', type=int, default=200,
                     help='how many check-<n> seeds to sweep (default: 200)')
    stc.set_defaults(fn=cmd_stamp_check)

    _add_weave_parser(
        sub,
        description='package a world into one self-contained HTML file',
        epilog='see: docs/guides/journey.md, docs/guides/world-creation.md',
    )

    # `archive` is weave's .vefr sibling (vefr#455, ADR 0019): the
    # versioned, inspectable game archive the shared Player opens. It
    # lives in the new door only - there is no `ratatoskr` spelling for
    # a verb the archives never had.
    _add_archive_parser(
        sub,
        description='write a world as one portable .vefr game file, or '
                    'inspect one',
        epilog='see: docs/adr/0019-vefr-archive-format.md',
    )

    sk = sub.add_parser(
        'spark', help='the resident small brain: install, status, smoke, task',
        description='the resident small brain: install, status, smoke, task',
        epilog='see: docs/guides/spark.md, docs/guides/bundled-brain.md',
    )
    spark_sub = sk.add_subparsers(dest='spark_verb', required=True)
    _add_spark_verbs(spark_sub)

    pt = sub.add_parser(
        'test', help='the pytest suite (extra args pass through)',
        description='the pytest suite; extra args pass through: vefr test -k chat',
    )
    pt.set_defaults(fn=cmd_test)

    fy = sub.add_parser(
        'ferry', help='carry things: deploy, carry, fetch, scaffold',
        description='carry things between boxes: deploy, carry, fetch, scaffold',
    )
    _add_ferry_flags(fy)
    ferry_sub = fy.add_subparsers(dest='ferry_verb', required=True)
    _add_ferry_verbs(ferry_sub)

    hb = sub.add_parser(
        'handbok', help='write the mechanics manual from real play',
        description='write the mechanics manual from real play',
    )
    hb.add_argument('--pack', default=None)
    hb.add_argument('--session', default=None,
                    help='play session to read (default: the default one)')
    hb.set_defaults(fn=cmd_handbok)

    skp = sub.add_parser(
        'skipa', help='the seven questions (legacy - now part of vefr doctor)',
        description='the seven questions (legacy - the same answers are part of vefr doctor)',
    )
    skp.add_argument('--url', default=DEFAULT_URL)
    skp.add_argument('--deploy-host', default=DEFAULT_DEPLOY_HOST)
    skp.add_argument('--nas-host', default=DEFAULT_BACKUP_HOST)
    skp.add_argument('--json', action='store_true', help='print the result envelope')
    skp.set_defaults(fn=cmd_vefr_skipa)

    art = sub.add_parser(
        'art', help='check a pack\'s art ledger, print its credits, or '
                    'report its skin kit',
        description='work with a pack\'s art/ledger (ADR 0011): validate '
                    'each round file, print generated credits, or report '
                    'the skin kit manifest',
        epilog='see: docs/adr/0011-art-ledger.md',
    )
    art_sub = art.add_subparsers(dest='art_verb', required=True)

    art_check = art_sub.add_parser(
        'check', help='validate every round-*.json in the ledger',
        description='validate keys, roles, ids, sha256 and the clean-credits '
                    'rule across a pack\'s art ledger',
    )
    art_check.add_argument('--ledger', required=True,
                           help='the art ledger directory (art/ledger)')
    art_check.add_argument('--root', default=None,
                           help='where picture `to` paths resolve (default: '
                                "the ledger dir's grandparent)")
    art_check.set_defaults(fn=cmd_art_check)

    art_credits = art_sub.add_parser(
        'credits', help='print the ledger as credits markdown',
        description='print generated credits, one line per picture',
    )
    art_credits.add_argument('--ledger', required=True,
                             help='the art ledger directory (art/ledger)')
    art_credits.set_defaults(fn=cmd_art_credits)

    art_kit = art_sub.add_parser(
        'kit', help='report a skin kit manifest\'s completeness',
        description='print one line per skin kit piece (drawn, derived or '
                    'missing) and the total, exiting 1 when a required '
                    'piece is missing',
    )
    art_kit.add_argument('--kit', required=True,
                         help='the skin kit manifest (art/skin-kit.json)')
    art_kit.add_argument('--src', required=True,
                         help='the directory holding the kit\'s pictures')
    art_kit.set_defaults(fn=cmd_art_kit)

    # Escape hatches: the old CLIs, run verbatim. add_help=False keeps
    # -h for the old CLI to answer; parse_known_args below captures the
    # tail; sys.argv hands it over so the old parser, its defaults and
    # its exit codes apply unchanged.
    sub.add_parser('norns', add_help=False,
                   help='run norns verbatim: vefr norns ARGS...')
    sub.add_parser('ratatoskr', add_help=False,
                   help='run ratatoskr verbatim: vefr ratatoskr ARGS...')

    args, extra = ap.parse_known_args()

    if args.cmd in ('norns', 'ratatoskr'):
        saved_argv = sys.argv
        sys.argv = [args.cmd] + extra
        try:
            return norns_main() if args.cmd == 'norns' else ratatoskr_main()
        finally:
            sys.argv = saved_argv

    if args.cmd == 'test':
        args.test_args = extra
    elif extra:
        ap.error(f'unrecognized arguments: {" ".join(extra)}')

    if args.cmd == 'check' and args.live:
        # --live turns `check` into `verify` - cmd_map with the same
        # map_cmd attribute norns verify passes.
        args.map_cmd = 'verify'
        args.url = args.live
    # check / map / doctor default --pack to the resolved world, the
    # way norns_main does for validate / build-map / verify / doctor.
    if args.cmd in ('check', 'map', 'doctor') \
            and getattr(args, 'pack', None) is None:
        args.pack = _resolved_pack()
    from .blueprint import BlueprintRefusal
    try:
        return args.fn(args)
    except BlueprintRefusal as exc:
        print(f'refused: {exc}', file=sys.stderr)
        return EXIT_ERROR


if __name__ == '__main__':
    sys.exit(ratatoskr_main())
