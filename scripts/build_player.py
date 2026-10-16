"""Build web/packaged.html from its parts (docs/plans/player-split/PLAN.md).

The build itself lives in `vefr.player_build`, so the weaver, the test session
and the hatch build hook all join the parts the same way. This is the command
line over it. The generated file is never committed: it is built where it is
read, and `--check` asks whether the parts build cleanly, not whether a
committed file is stale.

  uv run python scripts/build_player.py            rewrite web/packaged.html from the parts
  uv run python scripts/build_player.py --check    exit 1 if the parts do not build cleanly
  --root DIR                                       use DIR instead of the repository (tests)
"""
import argparse
import sys
from pathlib import Path

from vefr import player_build


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true',
                    help='build the parts and report, without writing the file')
    ap.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args(argv)
    root = Path(args.root)
    data, problems = player_build.build(root)
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        return 1
    if args.check:
        print(f'ok: the parts build cleanly into web/packaged.html '
              f'({len(data)} bytes, {len(data.splitlines())} lines)')
        return 0
    target = player_build.write(root)
    print(f'wrote {target.relative_to(root)} ({len(data)} bytes)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())