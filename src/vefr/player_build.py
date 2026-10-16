"""Build web/packaged.html from web/player/parts/ (docs/plans/player-split/PLAN.md).

The woven player's source lives in web/player/parts/, in the order
web/player/manifest.json lists them. The build joins them byte for byte into
web/packaged.html. That file is GENERATED and never committed: a source
checkout builds it on demand - the weaver builds it when it looks for the
template, the test session builds it once in tests/conftest.py, and the hatch
build hook builds it before packaging - and the wheel ships it as package data
so `pip install vefr` can weave from anywhere. Nothing reads the parts directly,
so every consumer still reads one file.

Never edit web/packaged.html by hand: edit a part, then build.

  uv run python scripts/build_player.py            rewrite web/packaged.html from the parts
  uv run python scripts/build_player.py --check    exit 1 if the parts do not build cleanly
"""
import json
import os
import tempfile
from pathlib import Path

# Where the source lives, relative to a repository root. The parts are the only
# source of truth; TARGET is build output and is in .gitignore.
PARTS = Path('web') / 'player' / 'parts'
MANIFEST = Path('web') / 'player' / 'manifest.json'
TARGET = Path('web') / 'packaged.html'


class PlayerBuildError(RuntimeError):
    """The parts on disk do not build. The message lists every problem found."""


def build(root: Path) -> tuple[bytes, list[str]]:
    """The concatenated player, or `b""` and the plain list of problems."""
    root = Path(root)
    player = root / 'web' / 'player'
    manifest = json.loads((player / 'manifest.json').read_text(encoding='utf-8'))
    parts = player / 'parts'
    problems = []
    listed = set(manifest)
    if len(listed) != len(manifest):
        problems.append('a part is listed twice in web/player/manifest.json')
    on_disk = {p.name for p in parts.iterdir() if p.is_file()}
    for name in sorted(on_disk - listed):
        problems.append(f'orphaned part not in the manifest: {name}')
    for name in sorted(listed - on_disk):
        problems.append(f'manifest names a missing part: {name}')
    if problems:
        return b'', problems
    return b''.join((parts / n).read_bytes() for n in manifest), []


def write(root: Path) -> Path:
    """Build the parts in `root` and write web/packaged.html; return its path.

    The write is skipped when the file on disk is already exactly the parts, so
    building on every weave costs one read rather than a 755 KB write.
    """
    root = Path(root)
    data, problems = build(root)
    if problems:
        raise PlayerBuildError('\n'.join(problems))
    target = root / TARGET
    if not (target.is_file() and target.read_bytes() == data):
        # Atomic: write a sibling temp file, then os.replace it over the target. Parallel builders
        # (pytest-xdist workers each importing tests/conftest.py, two weaves at once) then only ever
        # see the old file or the whole new one, never a truncated or half-written player.
        fd, tmp = tempfile.mkstemp(prefix='.packaged.', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as fh:
                fh.write(data)
            os.chmod(tmp, 0o644)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    return target


def write_if_parts(root: Path) -> Path | None:
    """Build `root` when it is a source checkout (it owns web/player/parts/).

    A wheel install ships the built file as package data and has no parts, so it
    returns None and the caller keeps reading the shipped file.
    """
    root = Path(root)
    if not (root / PARTS).is_dir():
        return None
    return write(root)
