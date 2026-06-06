"""sketch_export — Rasterize a sketch layout to a synthetic scan layer.

Produces editor-ready output files in the configured output root:
  layer.parquet   — rasterized block columns (world_x, world_z, block_id, block_data)
  islands.json    — island polygons with sketch metadata (name, mirrors)
  symmetry.json   — confirmed symmetry axis + center from Setup
  xml_data.json   — map identity from Overview
  <map_name>/level.dat    — Minecraft 1.8 world metadata (gzip NBT)
  <map_name>/region/*.mca — Anvil region files with island blocks placed at Y=0
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
from shapely.affinity import affine_transform
from shapely.geometry import Point, Polygon, box, mapping
from shapely.ops import unary_union

from pgm_map_studio.minecraft.world_writer import write_world
from pgm_map_studio.studio.services import sketch_data
from pgm_map_studio.studio.services.config import get_output_root

logger = logging.getLogger("pgm_map_studio")

# Synthetic block ID for all rasterized blocks (stone = 1).
_SYNTHETIC_BLOCK_ID = 1

# Points per quarter-circle when approximating circles.
# 16 × 4 = 64 total points — matches JS CIRCLE_POINTS = 64.
_CIRCLE_RESOLUTION = 16


# ── Shape → Shapely ───────────────────────────────────────────────────────────

def _shape_to_shapely(shape: dict):
    """Convert a sketch shape dict to a Shapely geometry, or None on failure."""
    t = shape.get("type")
    try:
        if t == "rectangle":
            return box(shape["min_x"], shape["min_z"],
                       shape["max_x"], shape["max_z"])
        if t == "circle":
            return Point(shape["center_x"], shape["center_z"]).buffer(
                shape["radius"], quad_segs=_CIRCLE_RESOLUTION)
        if t in ("polygon", "lasso"):
            verts = shape.get("vertices", [])
            if len(verts) < 3:
                return None
            return Polygon([(v[0], v[1]) for v in verts])
    except Exception as exc:
        logger.debug("sketch_export: _shape_to_shapely error: %s", exc)
    return None


# ── Boolean island computation ────────────────────────────────────────────────

def _compute_island_polys(shapes: list[dict]) -> list:
    """Run the 4-step boolean evaluation and return a list of Shapely Polygons.

    Mirrors the JS computeIslands evaluation order:
      1. union(normal adds)
      2. − union(normal subtracts)
      3. ∪ union(override adds)
      4. − union(override subtracts)
    """

    def _group(is_sub: bool, is_override: bool):
        return [s for s in shapes
                if (s.get("operation") == "subtract") == is_sub
                and bool(s.get("override")) == is_override]

    def _union(group):
        polys = [p for s in group
                 if (p := _shape_to_shapely(s)) is not None and not p.is_empty]
        if not polys:
            return None
        u = unary_union(polys)
        return u if not u.is_empty else None

    result = _union(_group(False, False)) or Polygon()

    n_sub = _union(_group(True, False))
    if n_sub and not result.is_empty:
        result = result.difference(n_sub)

    ov_add = _union(_group(False, True))
    if ov_add:
        result = result.union(ov_add) if not result.is_empty else ov_add

    ov_sub = _union(_group(True, True))
    if ov_sub and not result.is_empty:
        result = result.difference(ov_sub)

    if result is None or result.is_empty:
        return []
    if result.geom_type == "Polygon":
        return [result]
    if result.geom_type == "MultiPolygon":
        return list(result.geoms)
    return [g for g in getattr(result, "geoms", []) if g.geom_type == "Polygon"]


def _assign_shape_ids(shapes: list[dict], island_polys: list) -> list[list[str]]:
    """Return the shape IDs contributing to each island polygon."""
    results: list[list[str]] = [[] for _ in island_polys]
    for shape in shapes:
        sp = _shape_to_shapely(shape)
        if sp is None or sp.is_empty:
            continue
        for i, isl_poly in enumerate(island_polys):
            try:
                if sp.intersects(isl_poly):
                    results[i].append(shape["id"])
            except Exception:
                pass
    return results


def _match_metadata(
    shape_ids_per_island: list[list[str]],
    saved_meta: list[dict],
) -> list[dict | None]:
    """Match each computed island to saved metadata by shapeId set overlap."""
    matched: list[dict | None] = []
    for shape_ids in shape_ids_per_island:
        shape_id_set = set(shape_ids)
        best, best_score = None, 0
        for meta in saved_meta:
            overlap = len(shape_id_set & set(meta.get("shapeIds", [])))
            if overlap > best_score:
                best_score, best = overlap, meta
        matched.append(best if best_score > 0 else None)
    return matched


# ── Symmetry transforms ───────────────────────────────────────────────────────

def _mirror_poly(poly, axis: str, cx: float, cz: float):
    """Apply a symmetry transform to a Shapely polygon.

    Shapely affine_transform matrix [a, b, d, e, xoff, yoff]:
      x' = a*x + b*y + xoff
      y' = d*x + e*y + yoff
    """
    if axis == "mirror_x":
        return affine_transform(poly, [-1, 0, 0, 1, 2 * cx, 0])
    if axis == "mirror_z":
        return affine_transform(poly, [1, 0, 0, -1, 0, 2 * cz])
    if axis == "rot_180":
        return affine_transform(poly, [-1, 0, 0, -1, 2 * cx, 2 * cz])
    if axis == "rot_90":
        # new_x = cx − (z − cz),  new_z = cz + (x − cx)
        return affine_transform(poly, [0, -1, 1, 0, cx + cz, cz - cx])
    if axis == "rot_270":
        # new_x = cx + (z − cz),  new_z = cz − (x − cx)
        return affine_transform(poly, [0, 1, -1, 0, cx - cz, cz + cx])
    raise ValueError(f"Unknown symmetry axis: {axis!r}")


# ── Rasterization ─────────────────────────────────────────────────────────────

def _rasterise_poly(poly) -> list[tuple[int, int]]:
    """Rasterize a Shapely polygon to a list of integer (x, z) block coordinates.

    Uses block-centre sampling (x + 0.5, z + 0.5) — matching JS rasterisePolygon.
    """
    if poly is None or poly.is_empty:
        return []
    minx, minz, maxx, maxz = poly.bounds
    result = []
    for x in range(math.floor(minx), math.ceil(maxx)):
        for z in range(math.floor(minz), math.ceil(maxz)):
            if poly.contains(Point(x + 0.5, z + 0.5)):
                result.append((x, z))
    return result


def _rasterise_full_layout(
    island_polys: list,
    island_metas: list[dict | None],
    setup: dict,
) -> set[tuple[int, int]]:
    """Rasterize primary sector + all mirror copies for participating islands."""
    mode = (setup or {}).get("mirror_mode", "rot_180")
    center = (setup or {}).get("center") or {}
    cx = float(center.get("cx", 0))
    cz = float(center.get("cz", 0))

    copy_axes = ["rot_90", "rot_180", "rot_270"] if mode == "rot_90" else [mode]

    all_blocks: set[tuple[int, int]] = set()
    for poly, meta in zip(island_polys, island_metas):
        all_blocks.update(_rasterise_poly(poly))
        if (meta or {}).get("mirrors", True):
            for axis in copy_axes:
                all_blocks.update(_rasterise_poly(_mirror_poly(poly, axis, cx, cz)))

    return all_blocks


# ── Output writers ────────────────────────────────────────────────────────────

def _write_layer_parquet(blocks: set[tuple[int, int]], path: Path) -> None:
    if blocks:
        xs, zs = zip(*blocks)
        n = len(blocks)
        df = pd.DataFrame({
            "world_x":   np.array(list(xs), dtype=np.int32),
            "world_z":   np.array(list(zs), dtype=np.int32),
            "block_id":  np.full(n, _SYNTHETIC_BLOCK_ID, dtype=np.uint16),
            "block_data": np.zeros(n, dtype=np.uint8),
        })
    else:
        df = pd.DataFrame({
            "world_x":   pd.array([], dtype="int32"),
            "world_z":   pd.array([], dtype="int32"),
            "block_id":  pd.array([], dtype="uint16"),
            "block_data": pd.array([], dtype="uint8"),
        })
    df.to_parquet(path, index=False)
    logger.debug("sketch_export: wrote layer.parquet (%d blocks)", len(blocks))


def _island_entry(id_: int, poly, meta: dict | None) -> dict | None:
    """Build a single islands.json entry for a polygon. Returns None if empty.

    The stored polygon is derived from the rasterized blocks (union of unit
    squares), so its vertices align with the block grid — matching what the
    pipeline would produce from scan-layer data.
    """
    blocks = _rasterise_poly(poly)
    if not blocks:
        return None
    xs, zs = zip(*blocks)
    grid_poly = unary_union([box(x, z, x + 1, z + 1) for x, z in blocks])
    return {
        "id":          id_,
        "block_count": len(blocks),
        "bounds":      [int(min(xs)), int(min(zs)), int(max(xs)) + 1, int(max(zs)) + 1],
        "polygon":     mapping(grid_poly),
        "name":        (meta or {}).get("name", f"Island {id_}"),
    }


def _write_islands_json(
    island_polys: list,
    island_metas: list[dict | None],
    setup: dict,
    path: Path,
) -> None:
    mode = (setup or {}).get("mirror_mode", "rot_180")
    center = (setup or {}).get("center") or {}
    cx = float(center.get("cx", 0))
    cz = float(center.get("cz", 0))
    copy_axes = ["rot_90", "rot_180", "rot_270"] if mode == "rot_90" else [mode]

    data = []
    counter = 1
    for poly, meta in zip(island_polys, island_metas):
        entry = _island_entry(counter, poly, meta)
        if entry:
            data.append(entry)
            counter += 1
        if (meta or {}).get("mirrors", True):
            for axis in copy_axes:
                mirrored = _mirror_poly(poly, axis, cx, cz)
                entry = _island_entry(counter, mirrored, meta)
                if entry:
                    data.append(entry)
                    counter += 1

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.debug("sketch_export: wrote islands.json (%d islands)", len(data))


def _write_symmetry_json(setup: dict, path: Path) -> None:
    mode = (setup or {}).get("mirror_mode", "rot_180")
    center = (setup or {}).get("center") or {}
    cx = float(center.get("cx", 0))
    cz = float(center.get("cz", 0))
    data = {
        "status": "confirmed",
        "modes":  [{"type": mode, "detected": True, "confidence": 1.0}],
        "center": {"center_x": cx, "center_z": cz},
        "primary": {"type": mode, "confidence": 1.0},
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_xml_data_json(sketch: dict, path: Path) -> None:
    data = {
        "name":             sketch.get("name", ""),
        "version":          sketch.get("version", "1.0"),
        "gamemode":         "ctw",
        "objective":        sketch.get("objective", ""),
        "authors":          sketch.get("authors", []),
        "teams":            [],
        "wools":            [],
        "kits":             [],
        "filters":          [],
        "regions":          [],
        "max_build_height": 256,
        "sketch_session":   sketch.get("id", ""),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Slug derivation ───────────────────────────────────────────────────────────

def _make_slug(name: str, sketch_id: str) -> str:
    """Derive a stable URL-safe slug from a map name + sketch ID."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    suffix = sketch_id[:8]
    return f"{s}-{suffix}" if s else suffix


def _world_folder_name(name: str) -> str:
    """Convert a map name to a lowercase-underscore folder name."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "world"


# ── Public entry point ────────────────────────────────────────────────────────

def export_sketch(sketch_id: str) -> dict:
    """Rasterize the sketch layout and write editor-ready output files.

    Returns:
        dict with 'slug' and 'editor_url'.

    Raises:
        KeyError  if sketch_id is not found.
        ValueError if fewer than 2 islands are computed.
    """
    data = sketch_data.load_sketch(sketch_id)
    setup  = data.get("setup") or {}
    layout = data.get("layout") or {}
    shapes = layout.get("shapes", [])
    saved_islands = layout.get("islands", [])

    island_polys = _compute_island_polys(shapes)

    if len(island_polys) < 2:
        raise ValueError(
            f"Export requires at least 2 islands; got {len(island_polys)}"
        )

    shape_ids_per_island = _assign_shape_ids(shapes, island_polys)
    island_metas = _match_metadata(shape_ids_per_island, saved_islands)
    for i, meta in enumerate(island_metas):
        if meta is None:
            island_metas[i] = {"name": f"Island {i + 1}", "mirrors": True}

    all_blocks = _rasterise_full_layout(island_polys, island_metas, setup)

    # Reuse existing slug if already exported, otherwise derive a new one.
    slug = data.get("export_slug") or _make_slug(data.get("name", ""), sketch_id)

    out_dir = get_output_root() / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_layer_parquet(all_blocks, out_dir / "layer.parquet")
    _write_islands_json(island_polys, island_metas, setup, out_dir / "islands.json")
    _write_symmetry_json(setup, out_dir / "symmetry.json")
    _write_xml_data_json(data, out_dir / "xml_data.json")
    map_name = data.get("name", slug)
    world_dir = out_dir / _world_folder_name(map_name)
    write_world(all_blocks, world_dir, y=0, level_name=map_name)

    if not data.get("export_slug"):
        sketch_data.save_export_slug(sketch_id, slug)

    copy_count = 3 if (setup or {}).get("mirror_mode") == "rot_90" else 1
    total_islands = sum(
        1 + (copy_count if (m or {}).get("mirrors", True) else 0)
        for m in island_metas
    )
    logger.info(
        "sketch_export: exported sketch %s → %s (%d blocks, %d islands)",
        sketch_id, slug, len(all_blocks), total_islands,
    )
    return {"slug": slug, "editor_url": f"/editor?map={quote(slug)}"}
