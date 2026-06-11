"""region_geometry — polygon-level region comparison.

Resolves regions to real 2D footprints (via ``region_encoder._dict_to_shapely``,
which handles primitives, compounds, and mirror/translate refs) and compares
them by **IoU** — a true geometric check, not a bounding-box proxy.

Two consumers:
- **C13** — skip creating a counterpart that already exists, and self-validate a
  generated counterpart against the real one.
- **B11 / Regions activity** — symmetry-violation review: does a region's
  expected `(mode, center)` counterpart actually exist in the map?

Transform math is single-sourced from ``pgm_map_studio.geometry`` (the same
reflect/rotate used by C13), applied to the resolved polygon via
``shapely.ops.transform``.
"""
from __future__ import annotations

from pgm_map_studio.geometry import reflect_point_2d, rotate_point_2d
from pgm_map_studio.studio.services.region_encoder import _dict_to_shapely

# mode → horizontal mirror normal (matches symmetry_authoring / geometry.md §2)
_REFLECTION_NORMALS = {
    "mirror_x": (1.0, 0.0),
    "mirror_z": (0.0, 1.0),
    "mirror_d1": (1.0, -1.0),
    "mirror_d2": (1.0, 1.0),
}

_DEFAULT_BOUNDS = (-100000.0, -100000.0, 100000.0, 100000.0)


def _map_bounds(data: dict) -> tuple:
    """Overall (min_x,min_z,max_x,max_z) from region bounds_2d — the clip extent
    passed to `_dict_to_shapely` for unbounded regions (everywhere/negative/half)."""
    xs_min, zs_min, xs_max, zs_max = [], [], [], []
    for r in (data.get("regions") or {}).values():
        bd = r.get("bounds_2d")
        if not bd:
            continue
        xs_min.append(bd["min"]["x"]); zs_min.append(bd["min"]["z"])
        xs_max.append(bd["max"]["x"]); zs_max.append(bd["max"]["z"])
    if not xs_min:
        return _DEFAULT_BOUNDS
    # pad so a negative/everywhere clip box comfortably contains the map
    pad = 64.0
    return (min(xs_min) - pad, min(zs_min) - pad, max(xs_max) + pad, max(zs_max) + pad)


def _resolve(data: dict, region_id: str, bounds: tuple):
    regions = data.get("regions") or {}
    region = regions.get(region_id)
    if region is None:
        return None
    return _dict_to_shapely(region, bounds, registry=regions)


def _iou(a, b) -> float:
    if a is None or b is None or a.is_empty or b.is_empty:
        return 0.0
    union = a.union(b).area
    if union <= 1e-9:
        return 0.0
    return a.intersection(b).area / union


def _transform_geom(geom, mode: str, cx: float, cz: float):
    """Reflect/rotate a shapely geometry about (cx,cz), via the geometry.py math."""
    from shapely.ops import transform as shp_transform

    if mode in _REFLECTION_NORMALS:
        nx, nz = _REFLECTION_NORMALS[mode]
        point = lambda x, z: reflect_point_2d(x, z, nx, nz, cx, cz)
    elif mode.startswith("rot_"):
        deg = int(mode[4:])
        point = lambda x, z: rotate_point_2d(x, z, deg, cx, cz)
    else:
        raise ValueError(f"unsupported mode {mode!r}")

    def _apply(xs, zs):
        try:                                   # vectorised path (shapely passes arrays)
            pairs = [point(x, z) for x, z in zip(xs, zs)]
            return [p[0] for p in pairs], [p[1] for p in pairs]
        except TypeError:                      # scalar fallback
            return point(xs, zs)

    return shp_transform(_apply, geom)


def regions_equivalent(data: dict, id_a: str, id_b: str,
                       *, threshold: float = 0.95, bounds: tuple | None = None) -> bool:
    """True iff regions ``id_a`` and ``id_b`` have the same footprint (IoU ≥ threshold)."""
    bounds = bounds or _map_bounds(data)
    return _iou(_resolve(data, id_a, bounds), _resolve(data, id_b, bounds)) >= threshold


def counterpart_iou(data: dict, source_id: str, target_id: str, mode: str,
                    cx: float, cz: float, *, bounds: tuple | None = None) -> float:
    """IoU between ``target`` and the ``mode``-transform of ``source`` about (cx,cz)."""
    bounds = bounds or _map_bounds(data)
    src = _resolve(data, source_id, bounds)
    tgt = _resolve(data, target_id, bounds)
    if src is None or tgt is None:
        return 0.0
    return _iou(_transform_geom(src, mode, cx, cz), tgt)


def is_counterpart(data: dict, source_id: str, target_id: str, mode: str,
                   cx: float, cz: float, *, threshold: float = 0.95,
                   bounds: tuple | None = None) -> bool:
    """True iff ``target`` is the ``mode`` counterpart of ``source`` about (cx,cz)."""
    return counterpart_iou(data, source_id, target_id, mode, cx, cz, bounds=bounds) >= threshold
