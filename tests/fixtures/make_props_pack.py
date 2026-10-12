"""A copy of the sample world whose town has one prop: a blocking stone.

The stone sits at [8, 8], an open tile in the sample town's lower-right
room. Its picture is a two-frame strip. `props` replaces the contract's
list; `pics` maps a picture name to the (width, height) of the PNG
written beside the town.
"""

import json
import shutil
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"
STONE = {"pic": "stone", "at": [8, 8], "frames": 2, "fps": 4}


def png(width: int, height: int) -> bytes:
    raw = b"".join(b"\x00" + b"\x00\x00\x00\x00" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def build(tmp_path: Path, props=None, pics=None) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(SAMPLE, pack)
    town = pack / "acts" / "act-1" / "town"
    contract_path = town / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["props"] = [dict(STONE)] if props is None else props
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    props_dir = town / "props"
    props_dir.mkdir(exist_ok=True)
    for name, (w, h) in ({"stone": (64, 32)} if pics is None else pics).items():
        (props_dir / f"{name}.png").write_bytes(png(w, h))
    return pack
