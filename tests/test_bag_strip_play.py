"""The bag strip shows one picture per kind of thing carried, with a count.

Drives the shipped player in jsdom through the rolled-loot harness: three of
one kind is one picture with a count, more than eight kinds is eight
pictures and a `+N` pip, and the strip's words name each kind once.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "rolled_loot_harness.mjs"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_rolled_pack as mk  # noqa: E402

KINDS = {
    "tallow-stub": {"name": "a stub of tallow candle"},
    "moth-wing": {"name": "a moth wing"},
    "jar-lid": {"name": "a jar lid"},
    "bent-nail": {"name": "a bent nail"},
    "linen-scrap": {"name": "a scrap of linen"},
    "snail-shell": {"name": "a snail shell"},
    "chalk-stick": {"name": "a stick of chalk"},
    "dry-leaf": {"name": "a dry leaf"},
    "bottle-cork": {"name": "a bottle cork"},
    "horn-button": {"name": "a horn button"},
}
KIND_IDS = list(KINDS)
KIND_NAMES = [KINDS[i]["name"] for i in KIND_IDS]


def run(html, steps, bag):
    spec = json.dumps({"steps": steps, "bag": bag})
    result = subprocess.run(["node", str(HARNESS), str(html), spec],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr + result.stdout
    out = json.loads(result.stdout)
    assert out["errors"] == [], out["errors"]
    return out["final"]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    dest = tmp_path_factory.mktemp("bag-strip")
    pack = mk.build(dest, items={**mk.ITEMS, **KINDS})
    out = dest / "rolled-test.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    return out


def test_three_of_one_kind_is_one_picture_with_a_count(woven):
    bag = ["tallow-stub", "tallow-stub", "tallow-stub"]
    final = run(woven, [{"do": "openBag"}], bag)
    assert [kid["text"] for kid in final["stripKids"]] == ["3"], final["stripKids"]
    assert "bag-cell" in final["stripKids"][0]["cls"], final["stripKids"]
    assert final["strip"] == "Carrying: a stub of tallow candle (3).", final["strip"]
    assert final["bag"] == bag


def test_ten_kinds_are_eight_pictures_and_a_more_pip(woven):
    final = run(woven, [{"do": "openBag"}], KIND_IDS)
    kids = final["stripKids"]
    assert len(kids) == 9, kids
    assert all("bag-pip" in kid["cls"] for kid in kids), kids
    assert kids[-1]["cls"] == "bag-pip bag-pip--more", kids[-1]
    assert kids[-1]["text"] == "+2", kids[-1]
    assert sum("bag-pip--more" in kid["cls"] for kid in kids) == 1, kids


def test_exactly_eight_kinds_has_no_more_pip(woven):
    final = run(woven, [{"do": "openBag"}], KIND_IDS[:8])
    kids = final["stripKids"]
    assert len(kids) == 8, kids
    assert not any("bag-pip--more" in kid["cls"] for kid in kids), kids


def test_the_strip_names_each_kind_once_with_its_count(woven):
    final = run(woven, [{"do": "openBag"}], KIND_IDS)
    assert final["strip"] == "Carrying: " + ", ".join(KIND_NAMES) + ".", final["strip"]
    assert all(final["strip"].count(name) == 1 for name in KIND_NAMES), final["strip"]


def test_kinds_keep_first_seen_order_and_their_counts(woven):
    bag = ["moth-wing", "tallow-stub", "moth-wing", "tallow-stub", "tallow-stub"]
    final = run(woven, [{"do": "openBag"}], bag)
    assert final["strip"] == "Carrying: a moth wing (2), a stub of tallow candle (3).", final["strip"]
    assert [kid["text"] for kid in final["stripKids"]] == ["2", "3"], final["stripKids"]
