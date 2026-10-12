"""The browser fixtures survive any order of file arguments (issue #425).

`pytest tests/browser/a.py tests/test_x.py tests/browser/b.py` used to fail
b.py's tests with "fixture 'browser' not found": pytest 9 tied the fixtures of
tests/browser/conftest.py to the first `tests/browser` node, and the file in
between made pytest collect `tests/` again, giving b.py a second node without
them. The fixtures now load as a plugin (tests/browser/fixtures.py). This runs
pytest's setup plan, which resolves every fixture without starting Chromium.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a_test_file_between_two_browser_files_keeps_their_fixtures():
    args = ["tests/browser/test_way_icons.py", "tests/test_props.py",
            "tests/browser/test_camera_zoom.py"]
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         "--setup-plan", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    out = run.stdout + run.stderr
    assert "not found" not in out, out[-3000:]
    assert run.returncode == 0, out[-3000:]
    # The plan reached the browser tests on both sides of tests/test_props.py.
    assert "SETUP    S browser" in out, out[-3000:]
    assert "test_camera_zoom.py::" in out, out[-3000:]
