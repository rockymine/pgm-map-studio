"""Wool source detection + availability (C12).

A CTW wool objective can be fully configured in XML and still be **unobtainable**
if nothing delivers the wool. This scans the world layers for where wool actually
exists — as a **block** (`wools.parquet`), an item in a **chest**
(`chests.parquet`), or a **wool-dropping spawner** (`spawners.parquet`) — and
powers three things (docs/requirements/editor-objectives.md Sub-step 3):

- **region query** — "what wool is in this rectangle?" (the author draws a room).
- **availability** — per declared wool, is its room sourced? (`error` if not;
  `info` if only a one-time source).
- **suggestions** — wool colours found anywhere but not yet declared.

`repeatable` = a spawner or a wool block inside a `<renewable>` region; anything
else (a bare block, a chest) is **one-time**. Core logic runs on a plain source
list (hermetic-testable); `load_wool_sources` does the parquet I/O.
"""
from __future__ import annotations

from pathlib import Path

from pgm_map_studio.minecraft.wool import WOOL_DAMAGE_TO_COLOR, normalize_wool_color
from pgm_map_studio.studio.services.region_encoder import _dict_to_shapely

# a source: {"type": "block"|"chest"|"spawner", "color": slug, "x","y","z": int, "count": int}


def load_wool_sources(output_dir: Path) -> tuple[list[dict], bool]:
    """Read the world layers into a unified wool-source list. Returns (sources,
    have_layers); have_layers is False when no parquet exists (xml-only map)."""
    import pandas as pd
    sources: list[dict] = []
    have = False

    wp = output_dir / "wools.parquet"
    if wp.exists():
        have = True
        df = pd.read_parquet(wp)
        for r in df.itertuples(index=False):
            sources.append({"type": "block", "color": normalize_wool_color(str(r.color)),
                            "x": int(r.world_x), "y": int(r.world_y), "z": int(r.world_z), "count": 1})

    cp = output_dir / "chests.parquet"
    if cp.exists():
        have = True
        df = pd.read_parquet(cp)
        wool = df[df["item_id"].astype(str).str.contains("wool", case=False, na=False)]
        for r in wool.itertuples(index=False):
            color = WOOL_DAMAGE_TO_COLOR.get(int(r.item_damage))
            if color:
                sources.append({"type": "chest", "color": color, "x": int(r.world_x),
                                "y": int(r.world_y), "z": int(r.world_z), "count": int(r.count)})

    sp = output_dir / "spawners.parquet"
    if sp.exists():
        have = True
        df = pd.read_parquet(sp)
        if "spawns_wool" in df.columns:
            for r in df[df["spawns_wool"]].itertuples(index=False):
                color = WOOL_DAMAGE_TO_COLOR.get(int(r.spawn_item_damage))
                if color:
                    sources.append({"type": "spawner", "color": color, "x": int(r.world_x),
                                    "y": int(r.world_y), "z": int(r.world_z),
                                    "count": int(getattr(r, "spawn_count", 1) or 1)})
    return sources, have


# ── geometry helpers ──────────────────────────────────────────────────────────

def _map_bbox(regions: dict) -> tuple:
    xs, zs = [], []
    for r in regions.values():
        b = r.get("bounds_2d")
        if b and all(isinstance(b.get("min", {}).get(k), (int, float)) for k in "xz"):
            xs += [b["min"]["x"], b["max"]["x"]]
            zs += [b["min"]["z"], b["max"]["z"]]
    if not xs:
        return (-256, -256, 256, 256)
    return (min(xs) - 8, min(zs) - 8, max(xs) + 8, max(zs) + 8)


def _renewable_geoms(data: dict) -> list:
    """Shapely geoms of the map's <renewable> regions (where blocks regrow)."""
    regions = data.get("regions", {})
    bbox = _map_bbox(regions)
    geoms = []
    for rn in data.get("renewables", []):
        rid = rn.get("region_id")
        reg = regions.get(rid) if isinstance(rid, str) else None
        g = _dict_to_shapely(reg, bbox, regions) if reg else None
        if g is not None and not g.is_empty:
            geoms.append(g)
    return geoms


def _in_region(source: dict, geom) -> bool:
    if geom is None:
        return True
    g = source.get("geom")                                # a PGM spawner covers a region…
    if g is not None:
        return bool(g.intersects(geom))
    import shapely                                         # …a physical source is a point
    return bool(shapely.contains_xy(geom, source["x"] + 0.5, source["z"] + 0.5))


def _is_renewable(source: dict, renewable_geoms: list) -> bool:
    if source["type"] in ("spawner", "pgm_spawner"):
        return True                                       # spawners regenerate by nature
    if source["type"] == "block":
        return any(_in_region(source, g) for g in renewable_geoms)
    return False                                          # a chest is a one-time stock


def pgm_spawner_sources(data: dict) -> list[dict]:
    """Wool sources declared as PGM `<spawner>` modules (`xml_data.spawners`) — a
    gameplay delivery the author adds, not a physical block. Region-based: the geom
    is the spawn∪player region; position is its centroid (for display only)."""
    from shapely.ops import unary_union
    regions = data.get("regions", {})
    bbox = _map_bbox(regions)
    out: list[dict] = []
    for sp in data.get("spawners", []):
        geoms = []
        for key in ("spawn_region", "player_region"):
            rid = sp.get(key)
            reg = regions.get(rid) if isinstance(rid, str) else None
            g = _dict_to_shapely(reg, bbox, regions) if reg else None
            if g is not None and not g.is_empty:
                geoms.append(g)
        geom = unary_union(geoms) if geoms else None
        cx = int(round(geom.centroid.x)) if geom else 0
        cz = int(round(geom.centroid.y)) if geom else 0
        for item in sp.get("items", []):
            if "wool" not in str(item.get("material", "")).lower():
                continue
            dmg = item.get("damage")
            color = WOOL_DAMAGE_TO_COLOR.get(int(dmg)) if dmg is not None else None
            if not color:
                continue
            out.append({"type": "pgm_spawner", "color": color, "x": cx, "y": 0, "z": cz,
                        "count": int(item.get("amount") or 1), "geom": geom})
    return out


# ── summaries ─────────────────────────────────────────────────────────────────

def summarize_sources(sources: list[dict], region_geom=None,
                      renewable_geoms: list | None = None) -> list[dict]:
    """Group sources by colour (optionally clipped to a region). Each entry:
    {color, total, source_types, repeatable, one_time, sources:[...]}."""
    renewable_geoms = renewable_geoms or []
    by_color: dict[str, dict] = {}
    for s in sources:
        if not _in_region(s, region_geom):
            continue
        e = by_color.setdefault(s["color"], {
            "color": s["color"], "total": 0, "source_types": set(),
            "repeatable": False, "one_time": False, "sources": []})
        e["total"] += s["count"]
        e["source_types"].add(s["type"])
        if _is_renewable(s, renewable_geoms):
            e["repeatable"] = True
        e["sources"].append({k: s[k] for k in ("type", "color", "x", "y", "z", "count")})
    out = []
    for e in by_color.values():
        e["one_time"] = not e["repeatable"]
        e["source_types"] = sorted(e["source_types"])
        out.append(e)
    return sorted(out, key=lambda e: e["color"])


def check_availability(data: dict, sources: list[dict]) -> list[dict]:
    """Per declared wool: is it obtainable? A **physical** source must be in the
    wool's room; a **PGM `<spawner>`** counts by colour (room-independent — the
    author's deliberate delivery, and the room is often undeclared). `error` if
    neither, `info` if only one-time, else `ok`."""
    regions = data.get("regions", {})
    bbox = _map_bbox(regions)
    renewable = _renewable_geoms(data)
    physical = [s for s in sources if s["type"] != "pgm_spawner"]
    pgm_colors = {s["color"] for s in sources if s["type"] == "pgm_spawner"}
    out = []
    for w in data.get("wools", []):
        color = normalize_wool_color(str(w.get("color", "")))
        room_id = w.get("wool_room_region")
        room = regions.get(room_id) if isinstance(room_id, str) else None
        room_geom = _dict_to_shapely(room, bbox, regions) if room else None
        phys = next((e for e in summarize_sources(physical, room_geom, renewable)
                     if e["color"] == color), None)
        has_pgm = color in pgm_colors

        if phys is None and not has_pgm:
            out.append({"wool_id": w.get("id", ""), "color": color, "obtainable": False,
                        "repeatable": False, "one_time": False, "severity": "error",
                        "source_types": [], "message":
                        f"{color} wool has no obtainable source — add a wool spawner"
                        f"{'' if room else ' (and declare its wool-room region)'}"})
            continue

        types = (phys["source_types"] if phys else []) + (["pgm_spawner"] if has_pgm else [])
        repeatable = bool(has_pgm or (phys and phys["repeatable"]))
        one_time = not repeatable
        out.append({"wool_id": w.get("id", ""), "color": color, "obtainable": True,
                    "repeatable": repeatable, "one_time": one_time,
                    "severity": "info" if one_time else "ok", "source_types": types,
                    "message": (f"{color} wool is obtainable but only one-time "
                                f"({'/'.join(types)}) — consider a renewable or spawner"
                                if one_time
                                else f"{color} wool is obtainable ({'/'.join(types)})")})
    return out


def suggest_wools(data: dict, sources: list[dict]) -> list[dict]:
    """Wool colours found anywhere but not yet declared as objectives."""
    declared = {normalize_wool_color(str(w.get("color", ""))) for w in data.get("wools", [])}
    renewable = _renewable_geoms(data)
    return [{"color": e["color"], "total": e["total"], "source_types": e["source_types"]}
            for e in summarize_sources(sources, None, renewable) if e["color"] not in declared]
