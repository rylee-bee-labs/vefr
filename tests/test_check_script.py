"""scripts/check - the step table, the verdict contract, and the exit codes.

The script is the answer to "will this PR merge?", so what is pinned here is
the behaviour a human leans on:

- every step reports PASS / FAIL / SKIP, and a blocking FAIL exits non-zero;
- a tool that is not installed is a SKIP with a reason, never a silent pass;
- --list names every CI step and which ones are CI-only, under a column
  header that sits where the values do;
- the step table carries the CI commands, so CI and the script cannot drift
  apart silently;
- CONTRIBUTING names exactly the flags the script takes, so the docs
  describe this tool and not a smaller one;
- a run that skipped every step exits 0 and says so, and every doc that
  sends a reader to this tool says the same thing, so no doc sells a
  SKIPped step as a gate that passed;
- --merge-ready answers on the MERGED tree, in a worktree that leaves no
  commit on the branch and nothing behind.

Everything runs against a fake repo and stub tools on PATH: no network, no uv,
no real test suite. `python3 -m pytest tests/test_check_script.py` is enough.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"

# A PATH that contains no uv, npm or gitleaks even on a machine that has
# them, so "tool missing -> SKIP" is a fact of the test, not of the host.
BARE_PATH = "/usr/bin:/bin"


# ---------------------------------------------------------------- step table


def run_check(cwd, *args, env=None):
    """Run scripts/check in `cwd` and return the CompletedProcess."""
    full_env = dict(os.environ)
    full_env["PATH"] = BARE_PATH
    if env:
        full_env.update(env)
    return subprocess.run([str(CHECK), *args], cwd=str(cwd), env=full_env,
                          capture_output=True, text=True, timeout=180)


@pytest.fixture(scope="module")
def step_table():
    result = run_check(ROOT, "--list", "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_step_table_parses(step_table):
    """Every row parses into a complete, well-formed step."""
    assert isinstance(step_table, list) and step_table
    required = {"id", "phase", "blocking", "speed", "title", "command", "skip_hint"}
    seen = set()
    for row in step_table:
        assert required <= set(row), f"row is missing fields: {row}"
        assert row["id"] not in seen, f"duplicate step id: {row['id']}"
        seen.add(row["id"])
        assert row["phase"] in {"fast", "full", "never"}, row
        assert row["speed"] in {"fast", "slow", "ci-only"}, row
        assert isinstance(row["blocking"], bool), row
        assert row["title"], row
        assert row["command"], f"no command for {row['id']}"
        # A step that never runs locally is exactly the CI-only set, and it
        # always carries the reason it cannot.
        assert (row["phase"] == "never") == (row["speed"] == "ci-only"), row
        if row["phase"] == "never":
            assert row["skip_hint"], f"CI-only step without a reason: {row['id']}"
        assert "|" not in row["command"], row


def test_step_table_covers_every_ci_gate(step_table):
    """The ci.yml gate runs, the script knows about.

    This is the drift tripwire: a new check in ci.yml that no step in the
    table knows about fails here, in a clone, without a network.
    """
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    gate = ci.split("  gate:", 1)[1]
    # environment prep and the pin-bump skip decision, not checks
    setup = ("uv python install", "uv sync", "python3 scripts/ci_pin_only.py")
    commands = [line.strip() for line in gate.splitlines()
                if line.strip().startswith("run: ")]
    commands = [c[len("run: "):].strip() for c in commands]
    commands = [c for c in commands if not c.startswith(setup)]
    assert commands, "no gate commands parsed out of ci.yml"

    table_commands = " || ".join(row["command"] for row in step_table)
    for command in commands:
        assert command in table_commands, f"ci.yml runs a step the table lacks: {command}"


def test_secret_scan_is_redacted(step_table):
    """The local secret scan must never print a secret it found."""
    gitleaks = next(row for row in step_table if row["id"] == "gitleaks")
    assert "--redact" in gitleaks["command"]
    assert "--no-banner" in gitleaks["command"]
    assert "--log-opts=" in gitleaks["command"]
    assert gitleaks["phase"] == "fast", "the diff scan belongs in the pre-push subset"


def test_browser_and_a11y_are_marked_ci_only(step_table):
    """Steps that need a browser or a service are listed, never silently dropped."""
    ci_only = {row["id"] for row in step_table if row["phase"] == "never"}
    for step in ("browser-tests", "axe-a11y", "visual-regression", "lychee",
                 "claims-policy", "contract-freshness"):
        assert step in ci_only
    reasons = " ".join(row["skip_hint"] for row in step_table if row["phase"] == "never")
    assert "Chromium" in reasons


def test_list_output_marks_ci_only_steps():
    result = run_check(ROOT, "--list")
    assert result.returncode == 0, result.stderr
    assert "ci-only" in result.stdout
    assert "browser-tests" in result.stdout
    assert "--merge-ready" in result.stdout


def test_list_output_has_a_column_header(step_table):
    """--list names its columns, above the rows that use them.

    The header is output, not decoration: a reader who cannot tell `phase`
    from `speed` cannot read the table, and the columns only line up if
    both lines come out of the same format string. So the header must be
    there, above the first step, and sit where the values sit - a refactor
    that drops it fails here instead of quietly shipping it.
    """
    result = run_check(ROOT, "--list")
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()

    header = next((n for n, line in enumerate(lines)
                   if line.split()[:3] == ["step", "speed", "phase"]), None)
    assert header is not None, f"--list prints no column header:\n{result.stdout}"
    assert lines[header].rstrip().endswith("what it does"), lines[header]

    first_step = step_table[0]
    first_row = next((n for n in range(header + 1, len(lines))
                      if lines[n].split() and lines[n].split()[0] == first_step["id"]), None)
    assert first_row is not None, f"no row for {first_step['id']}:\n{result.stdout}"

    # The labels sit exactly where that row's values do, so the two lines
    # are read as one table instead of two guesses.
    row = lines[first_row]
    speed_at = row.index(first_step["speed"])
    phase_at = row.index(first_step["phase"], speed_at + len(first_step["speed"]))
    assert lines[header].index("speed") == speed_at, lines[header]
    assert lines[header].index("phase") == phase_at, lines[header]


# ----------------------------------------------------------- the docs


def _documented_check_flags():
    """The flags CONTRIBUTING's gate section attributes to scripts/check.

    Only lines that talk about `scripts/check` count, so the `uv run ...`
    commands in the same section are not read as modes of the tool.
    """
    gate = _gate_section()
    flags = set()
    for line in gate.splitlines():
        if "scripts/check" in line and "check_public_surface" not in line:
            flags |= set(re.findall(r"--[a-z][a-z-]*", line))
    return flags


def test_documented_flags_are_the_scripts_flags():
    """CONTRIBUTING's gate section takes scripts/check's flags, and all of them.

    This branch adds the tool, so what the docs say about it has to be true:
    no flag the script does not have, and no flag it has that the docs leave
    out. A change described as a smaller thing than it is - a docs tweak on
    top of a 500-line script - is what a reviewer is asked to take on faith.
    """
    helped = run_check(ROOT, "--help")
    assert helped.returncode == 0, helped.stderr
    script_flags = set(re.findall(r"--[a-z][a-z-]*", helped.stdout))
    assert script_flags == {"--fast", "--full", "--list", "--merge-ready", "--json"}, (
        "scripts/check grew or lost a flag; say so in CONTRIBUTING's gate section"
    )
    assert _documented_check_flags() == script_flags, (
        "CONTRIBUTING's gate section must name every flag scripts/check takes, "
        f"and no others: documented {sorted(_documented_check_flags())}, "
        f"script {sorted(script_flags)}"
    )


# A doc may send a reader to this tool; it may not promise more than the tool
# does. These are the phrases a review of this branch rejected, kept as the
# tripwire: a doc that calls the runner the gate, or says a local run knows a
# PR will merge, is a claim the exit code does not back.
OVERCLAIMS = (
    "the one command for the gate",
    "the one command that answers",
    "known to be mergeable",
    "will this PR merge?",
)


def _docs_pointing_at_the_runner():
    """Every tracked markdown file, plus the script's own header, that names
    `scripts/check`. `check_public_surface.py` is a different tool."""
    docs = []
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        text = path.read_text(errors="replace")
        mentions_runner = any(
            "scripts/check" in line and "check_public_surface" not in line
            for line in text.splitlines()
        )
        if mentions_runner:
            docs.append((path.relative_to(ROOT), text))
    header = "\n".join(
        line for line in CHECK.read_text().splitlines()
        if line.startswith("#") and not line.startswith("#!")
    )
    return docs + [("scripts/check header", header)]


def test_docs_say_a_skip_is_not_a_pass():
    """A doc that points at the runner must say what a SKIP means for it.

    The tool skips what this machine has no tool for and still exits 0, so a
    green run is not a green gate. Every doc that tells a reader to run it -
    CONTRIBUTING, AGENTS.md, ROADMAP.md and the script's own header - has to
    say that, or the reader is sold a gate that never ran.
    """
    docs = _docs_pointing_at_the_runner()
    assert {str(name) for name, _ in docs} >= {
        "AGENTS.md", "CONTRIBUTING.md", "ROADMAP.md", "scripts/check header",
    }, f"the docs stopped naming the runner: {[str(n) for n, _ in docs]}"

    for name, text in docs:
        skip_lines = [line for line in text.splitlines() if "skip" in line.lower()]
        assert any("pass" in line.lower() for line in skip_lines), (
            f"{name} sends a reader to scripts/check without saying that a "
            f"SKIPped step is not a pass"
        )
        for phrase in OVERCLAIMS:
            assert phrase not in text, f"{name} still claims: {phrase!r}"

    # And the same rule for the tool's own usage text, which is what a reader
    # who typed --help saw first.
    usage = run_check(ROOT, "--help").stdout
    assert "A SKIP is not a pass" in usage, usage
    for phrase in OVERCLAIMS:
        assert phrase not in usage, f"--help still claims: {phrase!r}"


def test_a_run_that_skipped_everything_says_so(feature_branch, fake_home):
    """Exit 0 with nothing checked is reported as nothing checked.

    This is the behaviour the doc claim above has to match: a bare machine
    skips every tool step and the run still succeeds, so the summary carries
    the skip count, and CONTRIBUTING's gate section states the same
    condition in the same words.
    """
    result = run_check(feature_branch, "--full",
                       env={"PATH": BARE_PATH, "HOME": str(fake_home)})
    assert result.returncode == 0, result.stdout
    skipped = [line for line in result.stdout.splitlines() if line.startswith("SKIP")]
    assert skipped, "the bare machine skipped nothing, so this proves nothing"

    summary = verdict(result.stdout, "check")
    assert summary.startswith("PASS"), summary
    assert "no blocking step that could run here failed" in summary, summary
    assert f"({len(skipped)} SKIPped: not checked)" in summary, summary

    gate = _gate_section()
    assert "no blocking step that could run here failed" in gate, (
        "CONTRIBUTING's gate section must say what a zero exit means here"
    )
    assert "SKIP" in gate and "not a pass" in gate, gate


def _gate_section():
    """CONTRIBUTING's Test gate section - the block the flags come from too."""
    gate = CONTRIBUTING.read_text().split("## Test gate", 1)[1]
    return gate.split("\n## ", 1)[0]


# ------------------------------------------------------------- fake repo


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _stub(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def fake_repo(tmp_path):
    """A repo shaped like vefr's, with an origin, committed on main.

    Carries the files the fast steps actually touch: scripts/check itself,
    the public-surface guard, a src module and the test that sits beside it.
    """
    origin = tmp_path / "origin.git"
    _git("init", "--quiet", "--bare", str(origin), cwd=tmp_path)
    _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=origin)

    repo = tmp_path / "work"
    repo.mkdir()
    _git("init", "--quiet", "-b", "main", ".", cwd=repo)
    _git("config", "user.email", "probe@local", cwd=repo)
    _git("config", "user.name", "probe", cwd=repo)
    _git("remote", "add", "origin", str(origin), cwd=repo)

    (repo / "src" / "vefr").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "scripts").mkdir()
    (repo / "worlds" / "sample-world").mkdir(parents=True)
    (repo / "src" / "vefr" / "widget.py").write_text("VALUE = 1\n")
    (repo / "tests" / "test_widget.py").write_text("def test_widget():\n    assert True\n")
    (repo / "worlds" / "sample-world" / "world.json").write_text("{}\n")
    shutil.copy2(CHECK, repo / "scripts" / "check")
    (repo / "scripts" / "check_public_surface.py").write_text(
        "import sys\nsys.exit(0)\n"
    )
    _git("add", "-A", cwd=repo)
    _git("commit", "--quiet", "-m", "main", cwd=repo)
    _git("push", "--quiet", "-u", "origin", "main", cwd=repo)
    return repo


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return home


def make_tools(tmp_path, fake_home, names=("uv", "gitleaks", "npm", "actionlint")):
    """Stub tools on PATH. STUB_FAIL_MATCH makes one of them fail."""
    bindir = tmp_path / "bin"
    body = (
        'echo "[stub $(basename "$0")] $*"\n'
        'if [ -n "${STUB_FAIL_MATCH:-}" ]; then\n'
        '  case "$*" in *"$STUB_FAIL_MATCH"*) echo "[stub] failing on $STUB_FAIL_MATCH"; exit 3;; esac\n'
        "fi\n"
        "exit 0\n"
    )
    for name in names:
        _stub(bindir / name, body)
    return {"PATH": f"{bindir}:{BARE_PATH}", "HOME": str(fake_home)}


@pytest.fixture
def tools(tmp_path, fake_home):
    return make_tools(tmp_path, fake_home)


@pytest.fixture
def feature_branch(fake_repo):
    """A branch that touches src/vefr/widget.py and nothing else."""
    _git("checkout", "--quiet", "-b", "feature", cwd=fake_repo)
    (fake_repo / "src" / "vefr" / "widget.py").write_text("VALUE = 2\n")
    _git("commit", "--quiet", "-am", "tweak the widget", cwd=fake_repo)
    return fake_repo


def verdict(output, step_id):
    """The PASS/FAIL/SKIP verdict line for one step."""
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == step_id and parts[0] in {"PASS", "FAIL", "SKIP"}:
            return line
    raise AssertionError(f"no verdict for {step_id} in:\n{output}")


# --------------------------------------------------------------- fast mode


def test_fast_mode_runs_the_preexisting_steps(feature_branch, tools):
    """With tools present, --fast is green and reaches the changed tests."""
    result = run_check(feature_branch, "--fast", env=tools)
    assert result.returncode == 0, result.stdout
    assert verdict(result.stdout, "ruff").startswith("PASS")
    assert verdict(result.stdout, "public-surface").startswith("PASS")
    assert verdict(result.stdout, "sample-world").startswith("PASS")
    assert verdict(result.stdout, "gitleaks").startswith("PASS")
    # src/vefr/widget.py changed, so its test module is the one under pytest.
    assert "tests/test_widget.py" in result.stdout
    assert "the CI command" in result.stdout


def test_fast_mode_stays_out_of_the_slow_steps(feature_branch, tools):
    """--fast is the pre-push subset: the slow steps do not run."""
    result = run_check(feature_branch, "--fast", env=tools)
    assert result.returncode == 0, result.stdout
    ran = {line[4:].strip() for line in result.stdout.splitlines() if line.startswith("--- ")}
    assert ran == {"ruff", "pytest-changed", "public-surface", "sample-world", "gitleaks"}


def test_failing_step_exits_non_zero(feature_branch, tools):
    """A blocking FAIL is a non-zero exit, with the tool's own output shown."""
    result = run_check(feature_branch, "--fast", env={**tools, "STUB_FAIL_MATCH": "ruff"})
    assert result.returncode != 0
    assert verdict(result.stdout, "ruff").startswith("FAIL")
    assert "failing on ruff" in result.stdout, "the failure output must not be swallowed"
    assert verdict(result.stdout, "check").startswith("FAIL")


def test_failing_public_surface_guard_blocks(feature_branch, tools):
    """The guard is a real step, not decoration: its exit code is the run's."""
    (feature_branch / "scripts" / "check_public_surface.py").write_text(
        "import sys\nsys.exit(1)\n"
    )
    result = run_check(feature_branch, "--fast", env=tools)
    assert result.returncode != 0
    assert verdict(result.stdout, "public-surface").startswith("FAIL")


def test_missing_tool_is_skip_with_a_reason(feature_branch, fake_home):
    """No gitleaks, no uv: SKIP with an install hint, and still a zero exit.

    The honest reading: this machine could not run the step. It is never
    reported as a pass.
    """
    result = run_check(feature_branch, "--fast",
                       env={"PATH": BARE_PATH, "HOME": str(fake_home)})
    assert result.returncode == 0, result.stdout
    for step_id in ("ruff", "sample-world", "gitleaks"):
        line = verdict(result.stdout, step_id)
        assert line.startswith("SKIP"), line
        assert len(line.split()) > 2, f"SKIP without a reason: {line}"
    assert "gitleaks is not installed" in result.stdout


def test_full_mode_with_no_toolchain_skips_everything(feature_branch, fake_home):
    """--full on a bare machine reports what it could not run, and says so.

    A step that needs a tool nobody installed is a SKIP with a reason - not a
    FAIL for a missing uv, and never a pass.
    """
    result = run_check(feature_branch, "--full",
                       env={"PATH": BARE_PATH, "HOME": str(fake_home)})
    assert result.returncode == 0, result.stdout
    assert "FAIL" not in result.stdout, result.stdout
    for step_id in ("ruff", "pytest", "packs-validate", "npm-ci", "actionlint",
                    "zizmor", "vulture", "deptry"):
        assert verdict(result.stdout, step_id).startswith("SKIP"), step_id
    assert verdict(result.stdout, "public-surface").startswith("PASS")


def test_ci_only_steps_never_run_locally(feature_branch, tools):
    """Browser and service steps are listed as CI-only, not attempted."""
    result = run_check(feature_branch, "--full", env=tools)
    assert result.returncode == 0, result.stdout
    for step_id in ("browser-tests", "axe-a11y", "lychee", "claims-policy"):
        assert f"--- {step_id}" not in result.stdout, f"{step_id} ran locally"


# ----------------------------------------------------------- runner ladder


def test_ci_venv_is_used_when_uv_is_absent(feature_branch, tmp_path, fake_home):
    """Bazzite: no uv, but the shared CI venv runs pytest - named in the output."""
    (fake_home / ".local" / "share" / "ci-venv" / "bin").mkdir(parents=True)
    _stub(fake_home / ".local" / "share" / "ci-venv" / "bin" / "python",
          'echo "[stub ci-venv] $*"\nexit 0\n')
    env = make_tools(tmp_path, fake_home, names=("gitleaks",))
    result = run_check(feature_branch, "--fast", env=env)
    assert verdict(result.stdout, "pytest-changed").startswith("PASS")
    assert "ci-venv" in result.stdout
    assert "-m pytest -q tests/test_widget.py" in result.stdout


def test_runner_override_is_honoured(feature_branch, tools):
    """VEFR_CHECK_PYTEST_RUNNER picks a rung; the label says it is not parity."""
    result = run_check(feature_branch, "--fast",
                       env={**tools, "VEFR_CHECK_PYTEST_RUNNER": "uv-with"})
    assert "uv run --with pytest" in result.stdout
    assert "not CI parity" in result.stdout


def test_default_runner_is_the_ci_command(feature_branch, tools):
    """With uv present the script runs the command CI runs, and says so."""
    result = run_check(feature_branch, "--fast", env=tools)
    assert "uv run --group test pytest -q tests/test_widget.py" in result.stdout
    assert "runner: uv (the CI command)" in result.stdout


# ------------------------------------------------------------- merge-ready


def test_merge_ready_on_a_clean_merge(feature_branch, tools):
    """The will-it-merge answer: full check on the merged tree, branch untouched."""
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(feature_branch),
                            capture_output=True, text=True, check=True).stdout.strip()
    result = run_check(feature_branch, "--merge-ready", env=tools)
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(feature_branch),
                           capture_output=True, text=True, check=True).stdout.strip()

    assert result.returncode == 0, result.stdout
    assert "merge conflicts" not in result.stdout
    assert verdict(result.stdout, "merge-ready").startswith("PASS")
    assert before == after, "merge-ready committed something on the branch"
    _assert_no_worktree_left(feature_branch)


def test_merge_ready_reports_conflicts(feature_branch, tools):
    """A conflicting main is a FAIL, named per file, and still leaves no trace."""
    _git("checkout", "--quiet", "main", cwd=feature_branch)
    (feature_branch / "src" / "vefr" / "widget.py").write_text("VALUE = 3\n")
    _git("commit", "--quiet", "-am", "main moves the same line", cwd=feature_branch)
    _git("push", "--quiet", "origin", "main", cwd=feature_branch)
    _git("checkout", "--quiet", "feature", cwd=feature_branch)

    result = run_check(feature_branch, "--merge-ready", env=tools)
    assert result.returncode != 0
    assert "merge conflicts with origin/main" in result.stdout
    assert "src/vefr/widget.py" in result.stdout
    assert verdict(result.stdout, "merge-ready").startswith("FAIL")
    _assert_no_worktree_left(feature_branch)


def test_merge_ready_says_so_before_it_works(feature_branch, tools):
    """Nothing is committed and nothing is pushed - stated, not assumed."""
    result = run_check(feature_branch, "--merge-ready", env=tools)
    assert "nothing is committed on your branch and nothing is pushed" in result.stdout
    assert "vefr check: full" in result.stdout, "the merged tree is checked in full"


def test_merge_ready_without_origin_is_a_fail(fake_repo, tools):
    """No default branch to merge: say so instead of checking a stale tree."""
    _git("remote", "remove", "origin", cwd=fake_repo)
    result = run_check(fake_repo, "--merge-ready", env=tools)
    assert result.returncode != 0
    assert "no origin/main to merge" in result.stdout
    # The fast path is honest about it too, rather than reporting "no changed
    # tests" as if the branch had simply not touched any.
    fast = run_check(fake_repo, "--fast", env=tools)
    assert "fetch the default branch" in fast.stdout


def _assert_no_worktree_left(repo):
    listed = subprocess.run(["git", "worktree", "list"], cwd=str(repo),
                            capture_output=True, text=True, check=True).stdout
    assert len(listed.strip().splitlines()) == 1, f"a worktree was left behind:\n{listed}"


# ------------------------------------------------------------------ guards


def test_check_is_executable():
    assert CHECK.is_file(), "scripts/check is missing"
    assert os.access(CHECK, os.X_OK), "scripts/check is not executable"


def test_check_is_bash_with_strict_mode():
    lines = CHECK.read_text().splitlines()
    assert lines[0].startswith("#!") and "bash" in lines[0]
    first_code = next(line for line in lines if line and not line.startswith("#"))
    assert first_code == "set -euo pipefail", "strict mode is part of the contract"


if __name__ == "__main__":  # pragma: no cover - convenience only
    sys.exit(pytest.main([__file__, "-q"]))