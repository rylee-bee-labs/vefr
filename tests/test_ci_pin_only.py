"""scripts/ci_pin_only.py decides whether CI may skip the long steps for a Play-Nice pin bump.

The yes behind it covers "a change that only bumps a version line", so the diff CONTENT is checked,
not just the file path. Every doubt must give only=false (everything runs).
"""

import importlib.util
import sys
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ci_pin_only.py"
PIN = ".project/contracts/adoption.yaml"
OLD = "a" * 40
NEW = "b" * 40

BASE = f"""schema: play-nice/adoption-v1
source:
  # 2026-11-01: auto re-pin, fast-forward from 4fa9afe (1 commit(s); 0 file(s) under contracts/ changed)
  revision: {OLD}
always:
  - secrets-and-data
"""


def load():
    spec = importlib.util.spec_from_file_location("ci_pin_only", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(cwd, *args):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env)


def make_pr(tmp_path, edits, *, merge=True):
    """A repo whose HEAD is a merge of a PR branch (the `edits` mapping path -> new text) into main."""
    repo = tmp_path / "repo"
    (repo / ".project/contracts").mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    (repo / PIN).write_text(BASE)
    (repo / "README.md").write_text("hello\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "pr")
    for rel, text in edits.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "pr")
    git(repo, "checkout", "-q", "main")
    if merge:
        git(repo, "merge", "-q", "--no-ff", "-m", "merge", "pr")
    else:
        git(repo, "merge", "-q", "--ff-only", "pr")
    return repo


def run(repo, event="pull_request"):
    env = {**os.environ, "EVENT_NAME": event}
    env.pop("GITHUB_OUTPUT", None)
    res = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


BUMP = BASE.replace(
    f"revision: {OLD}",
    "# 2026-11-02: auto re-pin, fast-forward from aaaaaaa (1 commit(s); 0 file(s) under contracts/ changed)\n"
    f"  revision: {NEW}",
)


def test_real_re_pin_shape_is_pin_only(tmp_path):
    assert run(make_pr(tmp_path, {PIN: BUMP})) == "only=true"


def test_revision_alone_is_pin_only(tmp_path):
    assert run(make_pr(tmp_path, {PIN: BASE.replace(OLD, NEW)})) == "only=true"


def test_pin_plus_another_line_of_the_same_file_is_not(tmp_path):
    assert run(make_pr(tmp_path, {PIN: BUMP.replace("  - secrets-and-data\n", "")})) == "only=false"


def test_other_comment_in_the_same_file_is_not(tmp_path):
    other = BUMP.replace("source:\n", "source:\n  # a note anyone could write\n")
    assert run(make_pr(tmp_path, {PIN: other})) == "only=false"


def test_other_key_in_the_same_file_is_not(tmp_path):
    assert run(make_pr(tmp_path, {PIN: BUMP.replace("schema:", "schema2:")})) == "only=false"


def test_pin_plus_a_second_file_is_not(tmp_path):
    assert run(make_pr(tmp_path, {PIN: BUMP, "README.md": "changed\n"})) == "only=false"


def test_other_file_alone_is_not(tmp_path):
    assert run(make_pr(tmp_path, {"README.md": "changed\n"})) == "only=false"


def test_a_push_event_is_not(tmp_path):
    assert run(make_pr(tmp_path, {PIN: BUMP}), event="push") == "only=false"
    assert run(make_pr(tmp_path / "x", {PIN: BUMP}), event="") == "only=false"


def test_checkout_that_is_not_a_merge_commit_is_not(tmp_path):
    assert run(make_pr(tmp_path, {PIN: BUMP}, merge=False)) == "only=false"


def test_a_broken_git_call_is_not(tmp_path):
    empty = tmp_path / "not-a-repo"
    empty.mkdir()
    env = {**os.environ, "EVENT_NAME": "pull_request", "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    res = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=empty, env=env, capture_output=True, text=True
    )
    assert res.stdout.strip() == "only=false"
    env["PATH"] = str(tmp_path / "no-git-here")
    res = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=empty, env=env, capture_output=True, text=True
    )
    assert res.stdout.strip() == "only=false"


def test_writes_github_output(tmp_path):
    repo = make_pr(tmp_path, {PIN: BUMP})
    out = tmp_path / "gh_out"
    env = {**os.environ, "EVENT_NAME": "pull_request", "GITHUB_OUTPUT": str(out)}
    subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=repo, env=env, check=True, capture_output=True
    )
    assert out.read_text() == "only=true\n"


@pytest.mark.parametrize(
    "diff",
    [
        "",  # nothing changed: doubt
        f"diff --git a/{PIN} b/{PIN}\nindex 1..2 100644\n--- a/{PIN}\n+++ b/{PIN}\n@@ -1 +1 @@\n-  revision: {OLD}\n+  revision: {NEW}\n\\ No newline at end of file\n",
        f"diff --git a/{PIN} b/{PIN}\nold mode 100644\nnew mode 100755\n",
        f"diff --git a/{PIN} b/{PIN}\nindex 1..2 100644\n--- a/{PIN}\n+++ b/{PIN}\n@@ -1 +1 @@\n+  revision: {NEW}\n",
        f"diff --git a/{PIN} b/{PIN}\nindex 1..2 100644\n--- a/{PIN}\n+++ b/{PIN}\n@@ -1 +1 @@\n-  revision: {OLD}\n+  revision: not-a-sha\n",
        f"diff --git a/{PIN} b/{PIN}\nindex 1..2 100644\n--- a/{PIN}\n+++ b/{PIN}\n@@ -1 +1 @@\n-  # 2026-11-01: auto re-pin, old\n-  revision: {OLD}\n+  revision: {NEW}\n",
    ],
)
def test_odd_diffs_are_not(diff):
    assert load().is_pin_only(diff) is False


def test_workflows_call_the_script_and_gate_the_heavy_steps():
    for name, job_marker in (("ci.yml", "gate:"), ("dev-guards.yml", "browser:")):
        text = (ROOT / ".github" / "workflows" / name).read_text()
        assert "python3 scripts/ci_pin_only.py" in text, name
        assert "id: pin" in text and "steps.pin.outputs.only != 'true'" in text, name
        assert job_marker in text
