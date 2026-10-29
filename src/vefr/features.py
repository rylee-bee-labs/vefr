"""The features catalog - what VEFR can do, and what a pack uses.

`docs/features.json` is the one source of truth (owner data, never
written here). This module reads it, checks it cannot drift from the
repo, and scans a pack to say which features that pack uses.

`vefr features` (the CLI) and `GET /api/features` (the read-only route)
both return `report()`; the studio draws it as two shelves. The module
is the standard library plus the engine's own loaders: `maplab.load_pack`
for the pack, `library.load_library` for books. No model call ever runs
on this surface.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import elements, maplab
from .library import load_library
from .maplab import load_pack
from .paths import app_home

VALID_STATUSES = ("built", "partial", "proposed")
VALID_DETECTS = ("rules", "growth", "library", "items", "enemies", "fog",
                 "skin", "blueprint", "slots", "elements", "rpg", "always", "none")


def _root(root=None) -> Path:
    """The tree the catalog and its relative paths live under.

    Explicit `root` wins (the tests hand in a temp repo); otherwise the
    engine home, which is the checkout on a dev box.
    """
    return Path(root) if root is not None else app_home()


def _catalog_path(root=None) -> Path:
    return _root(root) / "docs" / "features.json"


def _read_catalog(root=None) -> tuple[list, list[str]]:
    """Return (features, errors). `features` is [] when the file is bad."""
    path = _catalog_path(root)
    if not path.is_file():
        return [], [f"features catalog not found at {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [], [f"features catalog is not valid JSON: {exc}"]
    except OSError as exc:
        return [], [f"features catalog could not be read: {exc}"]
    if not isinstance(data, dict):
        return [], ["features catalog must be an object with a 'features' list"]
    features = data.get("features")
    if not isinstance(features, list):
        return [], ["features catalog needs a 'features' list"]
    return features, []


def load_catalog(root=None) -> list:
    """The feature dicts from `<root>/docs/features.json` ([] if unreadable)."""
    features, _ = _read_catalog(root)
    return features


def _as_paths(value) -> list[str]:
    """The string paths in a docs/tests list; anything else is ignored."""
    if not isinstance(value, list):
        return []
    return [p for p in value if isinstance(p, str) and p]


def catalog_errors(root=None) -> list[str]:
    """Every drift problem in the catalog ([] when sound).

    One plain sentence per problem, each naming the feature and the
    field at fault, so an author knows what to fix without reading code.
    """
    features, errors = _read_catalog(root)
    if errors:
        return errors
    base = _root(root)
    seen: set = set()
    for index, feat in enumerate(features):
        if not isinstance(feat, dict):
            errors.append(f"feature at position {index} must be an object")
            continue
        fid = feat.get("id")
        if not isinstance(fid, str) or not fid.strip():
            errors.append(f"feature at position {index} needs a non-empty string id")
            label = str(feat.get("name") or f"#{index}")
            fid = None
        else:
            label = fid
            if fid in seen:
                errors.append(f"feature '{fid}' is a duplicate - feature ids must be unique")
            seen.add(fid)
        for field in ("name", "what"):
            value = feat.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"feature '{label}' needs a non-empty string '{field}'")
        status = feat.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"feature '{label}' status must be one of "
                          + ", ".join(VALID_STATUSES))
        detect = feat.get("detect")
        if detect not in VALID_DETECTS:
            errors.append(f"feature '{label}' detect must be one of "
                          + ", ".join(VALID_DETECTS))
        docs = _as_paths(feat.get("docs"))
        tests = _as_paths(feat.get("tests"))
        for field, paths in (("docs", docs), ("tests", tests)):
            for rel in paths:
                if not (base / rel).exists():
                    errors.append(f"feature '{label}' {field} path '{rel}' does not exist")
        design = feat.get("design")
        if design is not None:
            if not isinstance(design, str) or not (base / design).exists():
                errors.append(f"feature '{label}' design path '{design}' does not exist")
        if status in ("built", "partial"):
            if not docs:
                errors.append(f"feature '{label}' is {status} and needs at least one docs entry")
            if not tests:
                errors.append(f"feature '{label}' is {status} and needs at least one tests entry")
        if status == "proposed" and design is None:
            errors.append(f"feature '{label}' is proposed and needs a design")
    return errors


def _inside_pack(pack: Path, name: str) -> str | None:
    """The resolved path of `pack/name`, or None if it would leave the pack.

    Same shape as `cli._inside`: the pack directory is resolved first, and
    a file that is a link out of the pack is not followed.
    """
    base = os.path.realpath(pack)
    target = os.path.realpath(os.path.join(base, name))
    return target if target.startswith(base + os.sep) else None


def _read_json(path: Path) -> dict:
    """One JSON object from disk, or {} - the loader's contract read,
    without the loader's tracing side effects."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _region_contracts(pack: Path, w: dict) -> list[dict]:
    """Every region contract in the pack, in loader order.

    Mirrors how `world._load_region` reads a region: an acts-shape pack
    keeps each region's contract at `acts/<act>/<region>/contract.json`
    (read for every act, not just the first); a flat pack's single
    region is its `town` block from `maplab.load_pack`.
    """
    acts = pack / "acts"
    if acts.is_dir():
        contracts: list[dict] = []
        for act_dir in sorted(acts.iterdir()):
            if not act_dir.is_dir() or act_dir.name.startswith("."):
                continue
            act = _read_json(act_dir / "world.json")
            names = act.get("regions")
            if isinstance(names, dict):
                names = list(names)
            if not isinstance(names, list):
                continue
            for name in names:
                if not isinstance(name, str) or not name:
                    continue
                contract = _read_json(act_dir / name / "contract.json")
                if contract:
                    contracts.append(contract)
        return contracts
    town = w.get("town")
    if isinstance(town, dict) and town:
        return [town]
    # A flat pack that never declared a `town` block keeps its single
    # region's metadata at the top level.
    if any(key in w for key in ("fog", "enemies")):
        return [w]
    return []


def _enemy_count(contracts: list[dict]) -> int:
    total = 0
    for contract in contracts:
        listed = contract.get("enemies")
        if isinstance(listed, list):
            total += len(listed)
    return total


def _one_use(feat: dict, pack: Path, w: dict, config: dict,
             contracts: list[dict]) -> dict:
    """`{id, used, detail}` for one catalog feature against one pack.

    `used` is True, False, or None. None means the feature is not
    detectable from a pack at all (unknown, never "no").
    """
    detect = feat.get("detect")
    if detect == "always":
        used, detail = True, "always on"
    elif detect == "none":
        used, detail = None, "not detectable from a pack"
    elif detect == "rules":
        rules = config.get("rules")
        rules = rules if isinstance(rules, list) else []
        used, detail = bool(rules), f"{len(rules)} rules"
    elif detect == "growth":
        growth = w.get("growth")
        if not isinstance(growth, dict):
            used, detail = False, "no growth"
        elif growth.get("mode") == "levels":
            levels = growth.get("levels")
            xp = levels.get("xp") if isinstance(levels, dict) else None
            count = len(xp) if isinstance(xp, list) else 0
            used, detail = True, f"levels, {count} levels"
        elif growth.get("mode") == "practice":
            used, detail = True, "practice"
        else:
            used, detail = True, "growth"
    elif detect == "library":
        books = load_library(pack)
        used, detail = bool(books), f"{len(books)} books"
    elif detect == "items":
        items = config.get("items")
        count = len(items) if isinstance(items, dict) else 0
        used, detail = count > 0, f"{count} items"
    elif detect == "enemies":
        count = _enemy_count(contracts)
        used, detail = count > 0, f"{count} monsters"
    elif detect == "fog":
        count = sum(1 for contract in contracts if contract.get("fog"))
        used, detail = count > 0, f"{count} regions"
    elif detect == "blueprint":
        source = _inside_pack(pack, "blueprint.json")
        if source is not None and os.path.isfile(source):
            regions = _read_json(Path(source)).get("regions")
            count = len(regions) if isinstance(regions, dict) else 0
            used, detail = True, f"{count} regions"
        else:
            used, detail = False, "no blueprint"
    elif detect == "slots":
        # Equipment: an item that names one of the five slots. Counted
        # from the same shape the bake reads, so a pack that declares
        # slots and a pack the player can wear in are the same report.
        items = config.get("items")
        worn = 0
        if isinstance(items, dict):
            worn = sum(1 for spec in items.values()
                       if isinstance(spec, dict)
                       and spec.get("slot") in maplab.SLOTS)
        used, detail = worn > 0, f"{worn} wearable"
    elif detect == "elements":
        # Typed damage, read from the same two places the bake reads it:
        # the hero's own resistances (`player.resist`/`player.immune`)
        # and the hazards that deal a damage type or leave a burn. A pack
        # that names none of them has opted out, which is a "no" and not
        # an unknown.
        player = w.get("_player") or w.get("player")
        player = player if isinstance(player, dict) else {}
        resists = len(elements.resist_of(player)) or len(elements.immune_of(player))
        typed = sum(1 for contract in contracts
                    for e in (contract.get("enemies") or [])
                    if isinstance(e, dict) and (e.get("dmg_type") or e.get("burns")))
        said = []
        if resists:
            said.append("resistances")
        if typed:
            said.append(f"{typed} typed hazards")
        used, detail = bool(said), ", ".join(said) or "untyped damage"
    elif detect == "rpg":
        # The RPG core (ADR 0021), read from the places the pack names it:
        # the `fight` and `traits` blocks, the hero's guard and mana, an
        # item that casts or wears guard or mana, a shop's own stock and a
        # descent that resumes or falls home. A pack that names none of it
        # has opted out, which is a "no" and not an unknown.
        player = w.get("_player") or w.get("player")
        player = player if isinstance(player, dict) else {}
        items = config.get("items") if isinstance(config.get("items"), dict) else {}
        descent = config.get("descent") if isinstance(config.get("descent"), dict) else {}
        said = [key for key in ("fight", "traits") if isinstance(config.get(key), dict)]
        said += [f"player {key}" for key in ("guard", "mana") if key in player]
        if any(isinstance(spec, dict) and ("casts" in spec or set(spec.get("mods") or {})
                                           & {"guard", "mana"})
               for spec in items.values()):
            said.append("items")
        if any(isinstance(spec, dict) and "stock" in spec
               for spec in maplab._speaker_specs(w).values()):
            said.append("stock")
        said += [f"descent {key}" for key in ("resume", "fall") if key in descent]
        used, detail = bool(said), ", ".join(said) or "not used"
    elif detect == "skin":
        skin = config.get("skin")
        if skin is None:
            used, detail = False, "no skin"
        elif isinstance(skin, str):
            used, detail = True, skin
        elif isinstance(skin, dict):
            name = skin.get("name") or skin.get("id")
            used, detail = True, str(name) if name else "skin"
        else:
            used, detail = True, "skin"
    else:
        used, detail = None, "not detectable from a pack"
    return {"id": feat.get("id"), "used": used, "detail": detail}


def scan_pack(pack_dir, catalog: list | None = None) -> list:
    """One `{id, used, detail}` per catalog feature, for one pack.

    The pack is loaded through `maplab.load_pack` (the loader the
    validator uses); region contracts are read from disk the same way
    that loader does, so `fog` and `enemies` are seen per region.
    """
    pack = Path(pack_dir)
    features = catalog if catalog is not None else load_catalog()
    w = load_pack(pack)
    config = _read_json(pack / "world.json")
    contracts = _region_contracts(pack, w)
    return [_one_use(feat, pack, w, config, contracts) for feat in features]


def report(pack_dir=None, root=None) -> dict:
    """The whole picture: the catalog, and (optionally) one pack's uses.

    Every value is a plain JSON type, so the CLI and the API route can
    return it directly.
    """
    catalog = load_catalog(root)
    pack = None
    if pack_dir is not None:
        path = Path(pack_dir)
        pack = {"name": path.name, "uses": scan_pack(path, catalog=catalog)}
    return {"catalog": catalog, "pack": pack}
