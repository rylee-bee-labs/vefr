"""A ground that blends, in a real browser: the woven player lays the masked piece of the edges sheet.

The sample town's lane (`p`) runs down one column of grass. The pack names `"edges": "lane-edges"` for it:
a 4 x 4 picture of sixteen flat colours, piece `mask` in its own colour. The lane's top tile has only lane
to the south (mask 4), its bottom tile only lane to the north (mask 1) and the four between have lane both
ways (mask 5), so exactly those three colours must reach the canvas, the middle one about four times as
much, and none of the other thirteen. The same town with no edges lays no piece at all.
"""

import argparse
import json
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import zlib
from pathlib import Path

import pytest

from vefr import cli

SAMPLE = Path(__file__).resolve().parents[2] / "worlds" / "sample-world"

# Sixteen colours far apart from each other and from the town's own ground, in mask order.
PIECES = [(250, 0, 0), (0, 250, 0), (0, 0, 250), (250, 250, 0),
          (250, 0, 250), (0, 250, 250), (250, 125, 0), (125, 0, 250),
          (250, 250, 250), (125, 250, 0), (0, 125, 250), (250, 0, 125),
          (0, 250, 125), (125, 125, 250), (250, 125, 125), (125, 250, 250)]
PIECE_PX = 8


def _png(cells, cols, rows, px):
    """A tiny RGB PNG, cols x rows cells of px x px each, with the standard library only."""
    w, h = cols * px, rows * px
    raw = b""
    for y in range(h):
        raw += b"\x00" + b"".join(bytes(cells[(y // px) * cols + x // px]) for x in range(w))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    home = tmp_path_factory.mktemp("tile-edges-home")
    plain = home / "plain"
    shutil.copytree(SAMPLE, plain)
    pack = home / "pack"
    shutil.copytree(SAMPLE, pack)
    region = pack / "acts" / "act-1" / "town"
    (region / "tiles").mkdir()
    (region / "tiles" / "lane-edges.png").write_bytes(_png(PIECES, 4, 4, PIECE_PX))
    contract = json.loads((region / "contract.json").read_text(encoding="utf-8"))
    contract["legend"]["p"]["edges"] = "lane-edges"
    (region / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    for src, out in ((pack, "edges.html"), (plain, "plain.html")):
        rc = cli.cmd_build_web(argparse.Namespace(
            pack=str(src), out=str(home / out), pool=0, with_bundle=False, from_live=None))
        assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}/"
    for _ in range(120):
        try:
            urllib.request.urlopen(base + "edges.html", timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


def _open(page, url):
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    page.wait_for_timeout(600)  # the picture decodes, then the map redraws
    page.evaluate("window.VEFR_REDRAW()")


def _counts(page):
    return page.evaluate(
        """(cells) => {
          const c = document.querySelector('#play canvas') || document.querySelector('canvas');
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          const seen = cells.map(() => 0);
          for (let i = 0; i < d.length; i += 4) {
            for (let k = 0; k < cells.length; k++) {
              const [r, g, b] = cells[k];
              if (Math.abs(d[i] - r) < 6 && Math.abs(d[i + 1] - g) < 6 && Math.abs(d[i + 2] - b) < 6) seen[k]++;
            }
          }
          return seen;
        }""",
        [list(c) for c in PIECES])


def test_the_piece_drawn_is_the_one_the_neighbours_pick(page, woven):
    _open(page, woven + "edges.html")
    assert page.evaluate("window.VEFR_EDGES_DRAWN()") == 6
    seen = _counts(page)
    drawn = {k for k, n in enumerate(seen) if n}
    assert drawn == {1, 4, 5}, f"pieces on the canvas: {sorted(drawn)}; counts {seen}"
    # Four middle tiles to one end tile each (the hero may stand on one; allow for it).
    assert seen[5] > 2 * seen[1] and seen[5] > 2 * seen[4], seen


def test_a_town_with_no_edges_lays_no_piece(page, woven):
    _open(page, woven + "plain.html")
    assert page.evaluate("window.VEFR_EDGES_DRAWN()") == 0
    assert page.evaluate("JSON.stringify(window.VEFR_TILE_EDGES)") == "{}"
