"""Browser tests: a throwaway studio (its own data folder) and a Chromium page.

Run: uv run playwright install chromium   (once), then  uv run pytest tests/browser
Without Chromium these skip, unless VEFR_BROWSER_REQUIRED=1 (CI's browser job),
where a missing browser is a failure, not a quiet skip.

These fixtures are a plugin that `tests/conftest.py` loads through
`pytest_plugins`, not a `tests/browser/conftest.py`. Pytest 9 ties a conftest's
fixtures to the one Directory node it collected first, and an argument list
that names a file in `tests/` between two browser files (for example
`tests/browser/a.py tests/test_x.py tests/browser/b.py`) makes it collect
`tests/` again, which gives `tests/browser` a second node without them:
"fixture 'browser' not found" (issue #425). A plugin's fixtures belong to the
session, so no collection order can lose them.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def studio(tmp_path_factory):
    """Base URL of a studio started from this checkout with a fresh VEFR_DATA_DIR."""
    port = _free_port()
    data = tmp_path_factory.mktemp("vefr-data")
    env = {**os.environ, "VEFR_DATA_DIR": str(data)}
    log = open(data / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "vefr.main:app", "--app-dir", str(ROOT / "src"),
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            urllib.request.urlopen(base + "/api/health", timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the test studio never came up; see {data / 'server.log'}")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - no browser installed here
            if os.environ.get("VEFR_BROWSER_REQUIRED") == "1":
                raise
            pytest.skip(f"Chromium isn't installed ({exc.__class__.__name__}); "
                        "run: uv run playwright install chromium")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1100, "height": 1400})
    pg = ctx.new_page()
    yield pg
    ctx.close()


@pytest.fixture
def phone(browser):
    ctx = browser.new_context(viewport={"width": 390, "height": 1400})
    pg = ctx.new_page()
    yield pg
    ctx.close()
