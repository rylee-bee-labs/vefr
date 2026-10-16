"""Hatch build hook: build web/packaged.html before the wheel or sdist is packaged.

web/packaged.html is generated from web/player/parts/ and is never committed
(vefr#523), so the wheel's force-include has nothing to pick up unless something
builds it first. This hook runs `vefr.player_build.write()` - the same join the
weaver and the tests use - against the repository root before any target collects
its files, so `pip install vefr @ git+...` ships vefr/web/packaged.html and a
pack author's repo can weave with an installed engine.

The hook runs in hatchling's isolated build environment, so it puts `src/` on
sys.path itself rather than importing an installed vefr (nothing else is needed:
the build is stdlib only).
"""
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class PlayerBuildHook(BuildHookInterface):
    """Generate web/packaged.html from the parts before packaging."""

    PLUGIN_NAME = 'player-build'

    def initialize(self, version, build_data):
        root = Path(self.root)
        sys.path.insert(0, str(root / 'src'))
        from vefr.player_build import write
        write(root)