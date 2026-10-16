import os
import shutil
from pathlib import Path

import pytest
from vefr import player_build
from vefr import world as world_mod

# The pack resolves before any ratatoskr ferry fetch: whatever the
# environment points at. The bones never require the flesh to prove
# themselves.
#
# Tests use `worlds/sample-world/` as the tracked known-good pack -
# the demonstration pack ships with the engine, so every checkout
# runs the same story tests against the same geometry. The engine
# itself doesn't know any pack's name - the loader reads whatever
# pack the env var points at.
os.environ.setdefault('VEFR_WORLD', 'sample-world')

# The browser tests' fixtures (studio, browser, page, phone) load as a plugin
# rather than from a tests/browser/conftest.py, so that the order of file
# arguments cannot hide them; see tests/browser/fixtures.py and issue #425.
pytest_plugins = ["browser.fixtures"]

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='session', autouse=True)
def packaged_player():
    """Build web/packaged.html once for the whole session.

    The woven player is generated from web/player/parts/ and is not committed
    (vefr#523), so a fresh clone has no such file. Every test that reads it
    wants the same bytes, so build it before the first one and leave it alone.
    """
    return player_build.write(ROOT)


# conftest is imported before test modules are collected, and a few of them
# read the woven file at import time, so the build cannot wait for the fixture
# above. Both go through the same idempotent call: the second one is a read.
player_build.write(ROOT)


@pytest.fixture
def fixture_vefr_home(monkeypatch, tmp_path):
    """Point VEFR_HOME at a temp tree with the four-phase fixture
    pack so journey tests don't depend on any canon pack being
    on disk. The fixture is at tests/fixtures/four-phase-pack/;
    we copy it into a tmpdir's worlds/ so load_world() sees it.
    """
    fixture_src = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "four-phase-pack"
    home = tmp_path / "vefr-home"
    (home / "worlds" / "four-phase-pack").mkdir(parents=True)
    shutil.copytree(fixture_src, home / "worlds" / "four-phase-pack",
                    dirs_exist_ok=True)
    monkeypatch.setenv("VEFR_HOME", str(home))
    world_mod.load_world.cache_clear()
    yield home
    world_mod.load_world.cache_clear()
