"""sketch_export — Rasterize a sketch layout to a synthetic scan layer.

Produces editor-ready output files in the configured output root:
  layer.parquet          — rasterized block columns (world_x, world_z, block_id, block_data)
  layer_segments.parquet — synthetic vertical segments at Y=0 for the editor side view
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

# Points per curved edge when discretizing Bézier polygons — matches JS BEZIER_SAMPLES.
_BEZIER_SAMPLES = 16


# ── Bézier discretization ────────────────────────────────────────────────────

def _sample_bezier_edge(p0, c1, c2, p3):
    """Sample _BEZIER_SAMPLES points along a cubic Bézier edge (endpoint excluded)."""
    pts = []
    for k in range(_BEZIER_SAMPLES):
        t = k / _BEZIER_SAMPLES
        u = 1.0 - t
        pts.append((
            u**3*p0[0] + 3*u**2*t*c1[0] + 3*u*t**2*c2[0] + t**3*p3[0],
            u**3*p0[1] + 3*u**2*t*c1[1] + 3*u*t**2*c2[1] + t**3*p3[1],
        ))
    return pts


def _discretize_bezier_polygon(vertices: list, controls: dict) -> list[tuple[float, float]]:
    """Convert a polygon with Bézier controls to a dense straight-segment ring."""
    n = len(vertices)
    ring = []
    for i in range(n):
        j = (i + 1) % n
        p0 = vertices[i]
        p3 = vertices[j]
        ci = controls.get(str(i)) or {}
        cj = controls.get(str(j)) or {}
        cp_out = ci.get("out")
        cp_in  = cj.get("in")
        if cp_out is not None or cp_in is not None:
            c1 = cp_out if cp_out is not None else p0
            c2 = cp_in  if cp_in  is not None else p3
            ring.extend(_sample_bezier_edge(p0, c1, c2, p3))
        else:
            ring.append((p0[0], p0[1]))
    return ring


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
            controls = shape.get("controls") or {}
            if controls:
                pts = _discretize_bezier_polygon(verts, controls)
                return Polygon(pts) if len(pts) >= 3 else None
            return Polygon([(v[0], v[1]) for v in verts])
    except Exception as exc:
        logger.debug("sketch_export: _shape_to_shapely error: %s", exc)
    return None


# ── Boolean island computation ────────────────────────────────────────────────

def _geom_components(geom) -> list:
    """Split a Shapely geometry into individual Polygon components."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]


def _poly_intersects(a, b) -> bool:
    """True only if a and b share positive area (touching edges don't count)."""
    try:
        inter = a.intersection(b)
        return not inter.is_empty and inter.area > 0
    except Exception:
        return False


def _map_islands_to_union(island_polys: list, components: list) -> list[int]:
    """For each island return the index of the union component it belongs to (-1 if none).

    Uses positive-area polygon intersection, matching the JS implementation.
    This correctly handles donut-shaped islands whose exterior centroid falls
    inside a hole and would otherwise match the wrong component.
    """
    result = []
    for poly in island_polys:
        matched = -1
        for j, comp in enumerate(components):
            if _poly_intersects(poly, comp):
                matched = j
                break
        result.append(matched)
    return result


def _normal_path_set(island_polys: list, after_sub) -> set[int]:
    """Return indices of islands that have solid area in after_sub.

    Islands NOT in this set are pure override-add islands (sitting in holes).
    When after_sub is empty, all islands are assumed to be on the normal path.

    Matches JS _normalPathSet which treats the exterior ring as a filled polygon
    (ignoring holes) when intersecting against after_sub components.
    """
    if after_sub is None or after_sub.is_empty:
        return set(range(len(island_polys)))
    comps = _geom_components(after_sub)
    result: set[int] = set()
    for i, poly in enumerate(island_polys):
        exterior_filled = Polygon(poly.exterior.coords)
        for comp in comps:
            if _poly_intersects(exterior_filled, comp):
                result.add(i)
                break
    return result


def _compute_island_polys(shapes: list[dict]) -> tuple[list, object, object, object]:
    """Run the 4-step boolean evaluation.

    Returns (island_polys, add_union, after_sub, after_override_add).

    Mirrors the JS computeIslands evaluation order:
      1. union(normal adds)          → add_union
      2. − union(normal subtracts)   → after_sub
      3. ∪ union(override adds)      → after_override_add
      4. − union(override subtracts) → final result / island_polys

    The three intermediate geometries are returned for use by _assign_shape_ids.
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

    add_union = _union(_group(False, False)) or Polygon()

    n_sub = _union(_group(True, False))
    after_sub = add_union.difference(n_sub) if n_sub and not add_union.is_empty else add_union

    ov_add = _union(_group(False, True))
    if ov_add:
        after_override_add = after_sub.union(ov_add) if not after_sub.is_empty else ov_add
    else:
        after_override_add = after_sub

    result = after_override_add
    ov_sub = _union(_group(True, True))
    if ov_sub and not result.is_empty:
        result = result.difference(ov_sub)

    if result is None or result.is_empty:
        return [], add_union, after_sub, after_override_add
    if result.geom_type == "Polygon":
        island_polys = [result]
    elif result.geom_type == "MultiPolygon":
        island_polys = list(result.geoms)
    else:
        island_polys = [g for g in getattr(result, "geoms", []) if g.geom_type == "Polygon"]
    return island_polys, add_union, after_sub, after_override_add


def _assign_shape_ids(
    shapes: list[dict],
    island_polys: list,
    add_union,
    after_sub,
    after_override_add,
) -> list[list[str]]:
    """Return the shape IDs contributing to each island polygon.

    Full port of the four-branch JS logic in geometry.js assignShapesToIslands.

    Normal subtract / add use add_union (not final island polys) to resolve
    which component a shape belongs to — the subtract/add area may no longer
    appear in the final island geometry. Override subtract uses after_override_add
    for the same reason.
    """
    if not island_polys:
        return []

    add_comps      = _geom_components(add_union)
    override_comps = _geom_components(after_override_add)

    to_normal_idx   = _map_islands_to_union(island_polys, add_comps)
    to_override_idx = _map_islands_to_union(island_polys, override_comps)
    normal_path     = _normal_path_set(island_polys, after_sub)

    results: list[list[str]] = [[] for _ in island_polys]

    for shape in shapes:
        sp = _shape_to_shapely(shape)
        if sp is None or sp.is_empty:
            continue
        is_sub      = shape.get("operation") == "subtract"
        is_override = bool(shape.get("override"))
        to_assign: set[int] = set()

        if is_sub and not is_override:
            # Normal subtract: attribute via add_union components (subtract area
            # is gone from final islands; can't use final-island intersection).
            for j, comp in enumerate(add_comps):
                if not _poly_intersects(sp, comp):
                    continue
                for i in range(len(island_polys)):
                    if to_normal_idx[i] == j and i in normal_path:
                        to_assign.add(i)

        elif is_sub and is_override:
            # Override subtract: attribute via after_override_add components,
            # same reasoning — cut area is absent from final polygons.
            for j, comp in enumerate(override_comps):
                if not _poly_intersects(sp, comp):
                    continue
                for i in range(len(island_polys)):
                    if to_override_idx[i] == j:
                        to_assign.add(i)

        elif is_override:
            # Override add: intersect directly against final island polygons.
            for i, isl_poly in enumerate(island_polys):
                if _poly_intersects(sp, isl_poly):
                    to_assign.add(i)

        else:
            # Normal add: resolve via add_union component, restricted to
            # normal-path islands. If a subtract split the component into
            # multiple peers, fall back to direct final-island intersection.
            for j, comp in enumerate(add_comps):
                if not _poly_intersects(sp, comp):
                    continue
                peers = [i for i in range(len(island_polys))
                         if to_normal_idx[i] == j and i in normal_path]
                if len(peers) == 1:
                    to_assign.add(peers[0])
                else:
                    for i in peers:
                        if _poly_intersects(sp, island_polys[i]):
                            to_assign.add(i)

        for i in to_assign:
            results[i].append(shape["id"])

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


def _write_segments_parquet(blocks: set[tuple[int, int]], path: Path) -> None:
    """Write a synthetic `layer_segments.parquet` for the editor's side view.

    The exported world places every island block at Y=0, so each occupied column
    is a single one-block-tall segment [0, 0]. Schema matches `SegmentsExtractor`
    (`world_x, world_z, world_y_start, world_y_end`). Without this file the editor's
    build-step side view shows "No segment data" (it would otherwise try to extract
    from a `maps_folder` world that doesn't exist for a sketch export).
    """
    if blocks:
        xs, zs = zip(*blocks)
        n = len(blocks)
        df = pd.DataFrame({
            "world_x":       np.array(list(xs), dtype=np.int32),
            "world_z":       np.array(list(zs), dtype=np.int32),
            "world_y_start": np.zeros(n, dtype=np.int32),
            "world_y_end":   np.zeros(n, dtype=np.int32),
        })
    else:
        df = pd.DataFrame({
            "world_x":       pd.array([], dtype="int32"),
            "world_z":       pd.array([], dtype="int32"),
            "world_y_start": pd.array([], dtype="int32"),
            "world_y_end":   pd.array([], dtype="int32"),
        })
    df.to_parquet(path, index=False)
    logger.debug("sketch_export: wrote layer_segments.parquet (%d columns)", len(blocks))


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
        # regions and filters are id-keyed dicts in the contract, not lists —
        # the editor's /regions/tree and category derivation iterate `.values()`.
        "filters":          {},
        "regions":          {},
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

    island_polys, add_union, after_sub, after_override_add = _compute_island_polys(shapes)

    if len(island_polys) < 2:
        raise ValueError(
            f"Export requires at least 2 islands; got {len(island_polys)}"
        )

    shape_ids_per_island = _assign_shape_ids(
        shapes, island_polys, add_union, after_sub, after_override_add,
    )
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
    _write_segments_parquet(all_blocks, out_dir / "layer_segments.parquet")
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
