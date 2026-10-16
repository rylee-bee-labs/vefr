"""The player is built from parts (docs/plans/player-split/PLAN.md). FROZEN CONTRACT.

The woven player's source is `web/player/parts/` + `web/player/manifest.json`, in the order the manifest lists them.
`web/packaged.html` is the join of those parts, GENERATED and never committed (vefr#523): a source checkout builds it
where it is read - `cli._template_candidates()` for the weaver, the session fixture in `tests/conftest.py` for the
tests, the hatch build hook for the wheel - and nothing outside the build reads the parts directly.
  - `build_player.py --check` exits 0 when the parts build cleanly (every listed part exists, no part is orphaned or
    listed twice), else 1 with one plain sentence per problem.
  - `build_player.py` (no flag) writes the file from the parts; `--root DIR` builds a copy elsewhere (tests).
  - the manifest is a JSON list of part file names under `web/player/parts/`; every listed file exists and no file in
    that folder is missing from the list (an orphan part would silently not ship).
  - parts are joined with nothing added or removed: byte-for-byte, every time.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import player_build

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_player.py"


def run(*args, root=None):
    cmd = [sys.executable, str(BUILD), *args]
    if root is not None:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def clone(tmp_path):
    """A checkout with the parts and nothing generated: the fresh-clone shape."""
    dest = tmp_path / "repo"
    (dest / "web").mkdir(parents=True)
    shutil.copytree(ROOT / "web" / "player", dest / "web" / "player")
    assert not (dest / "web" / "packaged.html").exists()
    return dest


def test_the_parts_build_cleanly():
    r = run("--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_manifest_matches_the_parts_folder():
    manifest = json.loads((ROOT / "web" / "player" / "manifest.json").read_text(encoding="utf-8"))
    parts = ROOT / "web" / "player" / "parts"
    listed = set(manifest)
    on_disk = {p.name for p in parts.iterdir() if p.is_file()}
    assert len(manifest) == len(listed), "a part is listed twice"
    assert listed == on_disk, f"missing {listed - on_disk}, orphaned {on_disk - listed}"


def test_no_two_parts_share_a_part_number():
    """The number in front of a part's name is that part's number, for good.

    `390-engine-delve-v2.js` is part 390 and `395-engine-delve-v3.js` is part
    395: the number says where the part loads and which slice owns it. Two
    parts under one number is a collision between two slices - the number
    stops naming a part, and the weave order is decided by list position
    rather than by the number a reader would look it up by.

    Slices are built as separate PRs against the same folder, so the collision
    is only visible when both are on disk at once. Claiming a number a slice
    already owns is how it happens: this caught the v3 twin claiming 395 while
    E1's `395-the-descent.js` was in flight in vefr#314. One number, one part,
    and the numbers increase in manifest order.
    """
    manifest = json.loads((ROOT / "web" / "player" / "manifest.json").read_text(encoding="utf-8"))
    numbers: dict[int, list[str]] = {}
    for name in manifest:
        head, _, _rest = name.partition("-")
        if not head.isdigit():
            pytest.fail(f"{name} has no leading part number")
        numbers.setdefault(int(head), []).append(name)
    shared = {n: names for n, names in numbers.items() if len(names) > 1}
    assert not shared, (
        "two parts share one number: "
        + ", ".join(f"{n}: {sorted(names)}" for n, names in sorted(shared.items())))
    order = [int(name.partition("-")[0]) for name in manifest]
    assert order == sorted(order), (
        "the part numbers do not increase in manifest order, so the weave "
        f"order is not the numeric one: {order}")


def test_the_generated_file_is_exactly_its_parts():
    data, problems = player_build.build(ROOT)
    assert not problems, problems
    assert data == (ROOT / "web" / "packaged.html").read_bytes()


def test_the_generated_file_is_never_committed():
    """The point of the rule: two PRs editing player code must not collide here."""
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert any(line.strip() == "/web/packaged.html" for line in ignored), \
        "web/packaged.html is not in .gitignore, so the generated file can be committed again"


def test_a_build_into_a_fresh_checkout_writes_the_file(tmp_path):
    repo = clone(tmp_path)
    assert run("--check", root=repo).returncode == 0
    assert run(root=repo).returncode == 0
    assert (repo / "web" / "packaged.html").is_file()
    manifest = json.loads((repo / "web" / "player" / "manifest.json").read_text(encoding="utf-8"))
    joined = b"".join((repo / "web" / "player" / "parts" / n).read_bytes() for n in manifest)
    assert (repo / "web" / "packaged.html").read_bytes() == joined


def test_the_build_is_deterministic(tmp_path):
    repo = clone(tmp_path)
    assert player_build.write(repo).read_bytes() == player_build.write(repo).read_bytes()


def test_editing_a_part_then_building_carries_it(tmp_path):
    repo = clone(tmp_path)
    manifest = json.loads((repo / "web" / "player" / "manifest.json").read_text(encoding="utf-8"))
    part = repo / "web" / "player" / "parts" / manifest[0]
    part.write_bytes(part.read_bytes() + b"<!-- edited part -->\n")
    assert run(root=repo).returncode == 0
    assert b"<!-- edited part -->" in (repo / "web" / "packaged.html").read_bytes()


def test_an_orphan_part_is_refused(tmp_path):
    repo = clone(tmp_path)
    (repo / "web" / "player" / "parts" / "zz-orphan.js").write_text("// not listed\n", encoding="utf-8")
    r = run("--check", root=repo)
    assert r.returncode == 1 and "zz-orphan.js" in (r.stdout + r.stderr)


def test_a_missing_part_is_refused(tmp_path):
    repo = clone(tmp_path)
    manifest = json.loads((repo / "web" / "player" / "manifest.json").read_text(encoding="utf-8"))
    (repo / "web" / "player" / "parts" / manifest[0]).unlink()
    r = run("--check", root=repo)
    assert r.returncode == 1 and manifest[0] in (r.stdout + r.stderr)


def test_parallel_builds_never_expose_a_partial_file(tmp_path):
    """Many builders at once (pytest-xdist workers, two weaves): a reader only ever sees the whole player."""
    import threading

    root = tmp_path / 'repo'
    shutil.copytree(ROOT / 'web' / 'player', root / 'web' / 'player')
    expected, problems = player_build.build(root)
    assert not problems
    target = root / player_build.TARGET
    target.write_bytes(b'stale')          # force every builder to actually write
    seen, stop = [], threading.Event()

    def reader():
        while not stop.is_set():
            if target.exists():
                data = target.read_bytes()
                if data != b'stale':
                    seen.append(len(data))

    def make_stale(n):
        # Swapped in whole, like the build: an in-place truncation here would be the test's own race.
        tmp = target.with_name(f'.stale.{n}')
        tmp.write_bytes(b'stale')
        tmp.replace(target)

    def builder(n):
        for i in range(5):
            player_build.write(root)
            make_stale(f'{n}.{i}')

    r = threading.Thread(target=reader)
    r.start()
    builders = [threading.Thread(target=builder, args=(n,)) for n in range(6)]
    for b in builders:
        b.start()
    for b in builders:
        b.join()
    stop.set()
    r.join()
    assert seen, 'the reader never saw a build'
    assert set(seen) == {len(expected)}, f'a reader saw a partial player: sizes {sorted(set(seen))}'
    assert not list((root / 'web').glob('.packaged.*.tmp')), 'a temp file was left behind'
