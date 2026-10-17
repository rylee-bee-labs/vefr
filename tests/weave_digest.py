"""The behaviour-neutral guard, measured at the merge base (vefr#529).

The no-skin weave digest and the two baked-data digests were committed constants
in `tests/test_skin_validator.py` and `tests/test_identify.py`. Every PR that
touched the player had to re-measure one of those lines, and every merge made
the next open PR merge `main`, re-weave twice and re-push before CI could
start: three open player PRs, three serial rounds. The pin guarded a refactor -
"a refactor of the player must not change behaviour" - and charged every
feature PR for it, because every feature PR moved the same bytes on purpose.

So nothing is committed, and the guard is measured where it matters:

  * a PR that claims to be behaviour-neutral (the `refactor` label, which CI
    passes down as `VEFR_REFACTOR=1`) must reproduce the digest the merge base
    prints. The base is woven in a temp worktree at `git merge-base HEAD
    origin/main`, with this branch's fixture packs as the inputs, so the
    comparison is main's engine against this branch's engine and nothing is
    written into the tree;
  * every other PR checks what a pin never could and still can: the weave is
    deterministic (twice, equal) and the digest is a well-formed sha256.

Both halves are skipped with a plain reason - never a pass - when there is no
`origin/main` to measure against, which is what a plain local clone looks like.
Run locally against a real remote with:

  VEFR_REFACTOR=1 uv run pytest -q tests/test_skin_validator.py

This module is also the measuring program for the merge-base worktree: run as
`python tests/weave_digest.py --measure <root>` it builds that tree's player,
weaves its sample world and prints its digests as JSON on stdout.
"""

import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# CI sets this from the PR's labels (see .github/workflows/ci.yml). Anything
# else - unset, empty, "false" - means "this PR is allowed to change bytes".
REFACTOR_ENV = "VEFR_REFACTOR"
_TRUTHY = {"1", "true", "yes", "on"}

SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")


class NotMeasurable(Exception):
    """The merge-base guard cannot run here. The message is the skip reason."""


def data_blocks(html: str) -> str:
    """Every baked data line the weave carries: the `window.VEFR_*`
    assignments, in file order, joined."""
    return "\n".join(re.findall(r"^window\.VEFR_[A-Z_]+ = .*?;$", html,
                                re.M | re.S))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def is_sha256(digest: str) -> bool:
    """A digest that looks like the thing it claims to be."""
    return bool(SHA256_RE.match(digest or ""))


def claims_behaviour_neutral() -> bool:
    return os.environ.get(REFACTOR_ENV, "").strip().lower() in _TRUTHY


def assert_unchanged_from_merge_base(name: str, digest: str) -> None:
    """The byte-for-byte guard, for a branch that claims to be neutral.

    `name` is one of the keys `measure()` returns, `digest` this branch's
    value for it. Raises `AssertionError` when the merge base prints a
    different one - a "refactor" that moved a byte is not a refactor - and
    `NotMeasurable` (skip this test) when there is nothing to measure
    against, or when the branch never claimed to be neutral.
    """
    if not claims_behaviour_neutral():
        raise NotMeasurable(
            f"this branch does not claim to be behaviour-neutral "
            f"({REFACTOR_ENV} is unset), so its bytes are its own to choose")
    base = merge_base_digests()
    if base.get(name) is None:
        raise NotMeasurable(
            f"the merge base could not measure '{name}'; nothing to compare")
    if digest != base[name]:
        raise AssertionError(
            f"this branch claims to be behaviour-neutral ({REFACTOR_ENV} is "
            f"set) but '{name}' moved: {base[name]} at the merge base, "
            f"{digest} here. A refactor must weave the same bytes - drop the "
            f"claim, or keep the change that moves them.")


# --- measuring ---------------------------------------------------------------

def measure(root: Path) -> dict:
    """The digests a checkout at `root` prints, as {name: sha256}.

    The player is built from that tree's own parts first (it is generated and
    never committed), so what is measured is the tree's engine over the tree's
    parts. The rolled fixture pack is woven too when that tree carries the
    fixture builder.
    """
    from vefr import cli, player_build

    player_build.write(root)
    sample = cli.weave_html(root / "worlds" / "sample-world")
    digests = {"no_skin_weave": sha256(sample),
               "sample_data": sha256(data_blocks(sample))}

    fixture = root / "tests" / "fixtures" / "make_identify_pack.py"
    if not fixture.is_file():
        return digests
    sys.path.insert(0, str(fixture.parent))
    import make_identify_pack  # noqa: E402 - the tree under measurement owns it

    scratch = Path(tempfile.mkdtemp(prefix="vefr-mergebase-pack-"))
    try:
        rolled = make_identify_pack.build(scratch / "rolled", reader=False)
        digests["rolled_data"] = sha256(data_blocks(cli.weave_html(rolled)))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return digests


@functools.lru_cache(maxsize=1)
def merge_base_digests() -> dict:
    """Weave `git merge-base HEAD origin/main` in a temp worktree, once.

    `git worktree add` takes the repo lock, which a parallel pytest session
    (`-n auto`) can lose; that one failure is worth a retry.
    """
    base = _merge_base()
    for attempt in range(3):
        try:
            return _weave_in_a_worktree(base)
        except _Locked:
            if attempt == 2:
                raise NotMeasurable(
                    "git could not take the repo lock to add the merge-base "
                    "worktree; nothing was measured")
            time.sleep(0.5 * (attempt + 1))
    raise NotMeasurable("the merge base was never measured")  # pragma: no cover


def _weave_in_a_worktree(base: str) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="vefr-mergebase-"))
    worktree = tmp / "base"
    try:
        try:
            _git("worktree", "add", "--detach", "--quiet", str(worktree), base)
        except _GitError as err:
            if "cannot lock" in str(err):
                raise _Locked(str(err))
            raise NotMeasurable(f"the merge-base worktree failed to check out: {err}")
        _copy_fixture_builders(worktree)
        return _measure(worktree)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                       cwd=ROOT, capture_output=True, text=True, check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def _merge_base() -> str:
    head = _git("rev-parse", "HEAD")
    if not _have("refs/remotes/origin/main"):
        raise NotMeasurable(
            "no origin/main in this clone, so there is no merge base to "
            "measure against (fetch it, or let CI do it)")
    try:
        base = _git("merge-base", "HEAD", "origin/main")
    except _GitError:
        raise NotMeasurable(
            "HEAD and origin/main share no history, so there is no merge "
            "base to measure against")
    if base == head:
        raise NotMeasurable("HEAD is origin/main; there is nothing to compare")
    return base


def _have(ref: str) -> bool:
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref],
                          cwd=ROOT, capture_output=True, text=True,
                          check=False).returncode == 0


class _GitError(RuntimeError):
    pass


class _Locked(RuntimeError):
    """Another git held the repo lock; worth one retry."""


def _git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=False)
    if done.returncode:
        raise _GitError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def _copy_fixture_builders(worktree: Path) -> None:
    """This branch's fixture builders, over the base tree's.

    The builders are the inputs to the measurement, the engine is what is
    under it: a refactor that moved a fixture's bytes is a changed input, and
    it fails the comparison rather than hiding inside a stale builder.
    """
    from_dir = ROOT / "tests" / "fixtures"
    to_dir = worktree / "tests" / "fixtures"
    if not from_dir.is_dir():
        return
    to_dir.mkdir(parents=True, exist_ok=True)
    for builder in sorted(from_dir.glob("*.py")):
        target = to_dir / builder.name
        if not target.is_file() or target.read_bytes() != builder.read_bytes():
            shutil.copyfile(builder, target)


def _measure(worktree: Path) -> dict:
    """Run this module, inside `worktree`, as the measuring program."""
    env = dict(os.environ, VEFR_MEASURE_ROOT=str(worktree))
    # The worktree's own src first, and its editable-install hook off the
    # meta_path, so the vefr that answers is main's and not this branch's.
    env["PYTHONPATH"] = os.pathsep.join(
        [str(worktree / "src"), str(Path(__file__).resolve().parent),
         env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    done = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--measure"],
        cwd=worktree, env=env, capture_output=True, text=True, check=False)
    if done.returncode == 0:
        return json.loads(done.stdout)
    last = (done.stderr.strip().splitlines() or ["?"])[-1]
    raise NotMeasurable(f"the merge base could not be woven: {last}")


def _measure_main(argv: list[str]) -> int:
    """`python tests/weave_digest.py --measure`, run inside the base worktree."""
    root = Path(os.environ.get("VEFR_MEASURE_ROOT", os.environ.get("PWD", ".")))
    src = root / "src"
    sys.path.insert(0, str(src))
    sys.meta_path = [f for f in sys.meta_path if "editable" not in
                     f"{getattr(f, '__module__', '')} {getattr(f, '__name__', '')}".lower()]
    import vefr  # noqa: E402 - the sys.path above is the point
    if not Path(vefr.__file__).resolve().is_relative_to(root.resolve()):
        raise SystemExit(f"measured the wrong engine: {vefr.__file__}")
    json.dump(measure(root), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(_measure_main(sys.argv[1:]))
