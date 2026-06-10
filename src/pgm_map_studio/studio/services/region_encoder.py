"""region_encoder — encode the region tree for the Regions activity browser view.

Converts the flat ``regions`` dict from xml_data.json into a list of category
groups, each containing a recursive node tree with resolved bounds, type-specific
coordinates, and (for polygon-type regions) a Shapely-derived 2D polygon.

No I/O, no Flask.  Called by the ``/api/map/<name>/regions/tree`` route.
"""
from __future__ import annotations

# Display order + labels for the two-facet category taxonomy
# (see services/region_categorizer.py and docs/contracts/region-categorization.md).
_CATEGORY_ORDER  = [
    "spawn", "observer_spawn", "wool_room", "monument", "wool_spawner",
    "build", "mechanic", "other",
]
_CATEGORY_LABELS = {
    "spawn":          "Spawn",
    "observer_spawn": "Observer Spawn",
    "wool_room":      "Wool Rooms",
    "monument":       "Monuments",
    "wool_spawner":   "Wool Spawners",
    "build":          "Build",
    "mechanic":       "Mechanics",
    "other":          "Other",
}

_POLYGON_TYPES = frozenset({
    "circle", "half", "complement", "union", "intersect", "negative",
    "mirror", "translate",
})


# ── reference resolution ──────────────────────────────────────────────────────
# Compound children and transform sources are persisted as string ids into the
# flat registry (the editor may also use inline dicts). Resolve either form.

def _resolve_ref(ref, registry: dict | None) -> dict | None:
    """Resolve a child/source reference (string id or inline dict) to a region dict."""
    if isinstance(ref, str):
        return registry.get(ref) if registry else None
    if isinstance(ref, dict):
        return ref
    return None


def _resolve_source(region: dict, registry: dict | None) -> dict | None:
    """Resolve a mirror/translate source: inline ``source`` dict or ``source_id`` ref.

    Accepts the legacy ``ref_region_id`` key as a fallback.
    """
    src = region.get("source")
    if src is None:
        sid = region.get("source_id") or region.get("ref_region_id") or ""
        src = registry.get(sid) if (sid and registry) else None
    return src


# ── bounds / coords encoding ──────────────────────────────────────────────────

def _encode_bounds(region: dict) -> dict | None:
    bounds_2d = region.get("bounds_2d")
    if not bounds_2d:
        return None
    mn = bounds_2d.get("min", {})
    mx = bounds_2d.get("max", {})
    if "x" not in mn or "z" not in mn:
        return None
    min_x, min_z = mn["x"], mn["z"]
    max_x, max_z = mx["x"], mx["z"]
    t = region.get("type")
    if max_x == min_x and max_z == min_z:
        if t == "block":
            max_x = min_x + 1
            max_z = min_z + 1
        elif t == "point":
            min_x -= 0.5
            min_z -= 0.5
            max_x += 0.5
            max_z += 0.5
    return {"min_x": min_x, "min_z": min_z, "max_x": max_x, "max_z": max_z}


def _encode_coords(region: dict) -> dict | None:
    t = region.get("type")
    if t in ("rectangle", "cuboid"):
        mn = region.get("min") or region.get("bounds_2d", {}).get("min") or {}
        mx = region.get("max") or region.get("bounds_2d", {}).get("max") or {}
        return {
            "min_x": mn.get("x") if mn else region.get("min_x"),
            "min_y": mn.get("y") if mn else region.get("min_y"),
            "min_z": mn.get("z") if mn else region.get("min_z"),
            "max_x": mx.get("x") if mx else region.get("max_x"),
            "max_y": mx.get("y") if mx else region.get("max_y"),
            "max_z": mx.get("z") if mx else region.get("max_z"),
        }
    if t == "cylinder":
        base = region.get("base") or {}
        return {
            "base_x": base.get("x"), "base_y": base.get("y"), "base_z": base.get("z"),
            "radius": region.get("radius"), "height": region.get("height"),
        }
    if t == "circle":
        center = region.get("center") or {}
        return {"center_x": center.get("x"), "center_z": center.get("z"),
                "radius": region.get("radius")}
    if t == "sphere":
        origin = region.get("origin") or {}
        return {"origin_x": origin.get("x"), "origin_y": origin.get("y"),
                "origin_z": origin.get("z"), "radius": region.get("radius")}
    if t in ("block", "point"):
        pos = region.get("position") or {}
        return {"x": pos.get("x"), "y": pos.get("y"), "z": pos.get("z")}
    if t == "reference":
        return {"ref_id": region.get("ref_id", "")}
    if t == "half":
        origin = region.get("origin") or {}
        normal = region.get("normal") or {}
        return {
            "origin_x": origin.get("x"), "origin_y": origin.get("y"),
            "origin_z": origin.get("z"),
            "normal_x": normal.get("x"), "normal_y": normal.get("y"),
            "normal_z": normal.get("z"),
        }
    if t == "mirror":
        origin = region.get("origin") or {}
        normal = region.get("normal") or {}
        return {
            "source_id": region.get("source_id", "") or region.get("ref_region_id", "") or "",
            "origin_x": origin.get("x"), "origin_y": origin.get("y"),
            "origin_z": origin.get("z"),
            "normal_x": normal.get("x"), "normal_y": normal.get("y"),
            "normal_z": normal.get("z"),
        }
    if t == "translate":
        offset = region.get("offset") or {}
        return {
            "source_id": region.get("source_id", "") or region.get("ref_region_id", "") or "",
            "offset_x": offset.get("x"), "offset_y": offset.get("y"),
            "offset_z": offset.get("z"),
        }
    return None


# ── Shapely polygon computation ───────────────────────────────────────────────

def _half_to_shapely(origin_x, origin_z, normal_x, normal_z, bounds):
    from shapely.geometry import Polygon
    nx, nz = normal_x, normal_z
    ox, oz = origin_x, origin_z
    if nx == 0 and nz == 0:
        return None
    min_x, min_z, max_x, max_z = bounds
    poly = [(min_x, min_z), (max_x, min_z), (max_x, max_z), (min_x, max_z)]

    def dist(x, z):
        return nx * (x - ox) + nz * (z - oz)

    def cross_pt(p1, p2):
        d1, d2 = dist(*p1), dist(*p2)
        if abs(d1 - d2) < 1e-10:
            return p1
        t = d1 / (d1 - d2)
        return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))

    out = []
    n = len(poly)
    for i in range(n):
        curr, prev = poly[i], poly[(i - 1) % n]
        curr_in = dist(*curr) >= 0
        prev_in = dist(*prev) >= 0
        if curr_in:
            if not prev_in:
                out.append(cross_pt(prev, curr))
            out.append(curr)
        elif prev_in:
            out.append(cross_pt(prev, curr))

    if len(out) < 3:
        return None
    return Polygon(out)


def _reflect_geom(geom, nx: float, nz: float, ox: float, oz: float):
    """Reflect a Shapely geometry across the plane through (ox,oz) with normal (nx,nz).

    PGM ``<mirror>`` semantics via the reflection matrix ``R = I − 2·n̂·n̂ᵀ`` about the
    origin, so a diagonal normal (``-1,0,-1``) reflects across the 45° axis (swapping
    x/z) instead of collapsing to a 180° point flip. Subsumes the axis-aligned case.
    """
    from shapely.affinity import affine_transform
    n2 = nx * nx + nz * nz
    if n2 == 0:
        return geom
    r00 = 1 - 2 * nx * nx / n2
    r01 = -2 * nx * nz / n2
    r11 = 1 - 2 * nz * nz / n2
    # affine_transform matrix [a, b, d, e, xoff, yoff] applied about (ox, oz)
    return affine_transform(geom, [
        r00, r01, r01, r11,
        ox - r00 * ox - r01 * oz,
        oz - r01 * ox - r11 * oz,
    ])


def _dict_to_shapely(region: dict, bounds: tuple, registry: dict | None = None):
    """Convert a region dict to a Shapely 2D geometry.  bounds=(min_x,min_z,max_x,max_z)."""
    try:
        from shapely.geometry import box, Point
        from shapely.ops import unary_union
        from shapely.affinity import translate
    except ImportError:
        return None

    if not isinstance(region, dict):
        return None

    t = region.get("type")

    if t in ("rectangle", "cuboid"):
        mn = region.get("min") or region.get("bounds_2d", {}).get("min") or {}
        mx = region.get("max") or region.get("bounds_2d", {}).get("max") or {}
        mn_x = mn.get("x", 0) if mn else region.get("min_x", 0)
        mn_z = mn.get("z", 0) if mn else region.get("min_z", 0)
        mx_x = mx.get("x", 0) if mx else region.get("max_x", 0)
        mx_z = mx.get("z", 0) if mx else region.get("max_z", 0)
        if any(isinstance(v, str) for v in (mn_x, mn_z, mx_x, mx_z)):
            return None
        return box(min(mn_x, mx_x), min(mn_z, mx_z), max(mn_x, mx_x), max(mn_z, mx_z))

    if t == "cylinder":
        base = region.get("base") or {}
        bx, bz = base.get("x", 0), base.get("z", 0)
        r = region.get("radius", 0)
        if isinstance(r, str) or r <= 0:
            return None
        return Point(bx, bz).buffer(r, resolution=32)

    if t == "circle":
        center = region.get("center") or {}
        cx, cz = center.get("x", 0), center.get("z", 0)
        r = region.get("radius", 0)
        if isinstance(r, str) or r <= 0:
            return None
        return Point(cx, cz).buffer(r, resolution=32)

    if t == "sphere":
        origin = region.get("origin") or {}
        ox, oz = origin.get("x", 0), origin.get("z", 0)
        r = region.get("radius", 0)
        if isinstance(r, str) or r <= 0:
            return None
        return Point(ox, oz).buffer(r, resolution=32)

    if t == "block":
        pos = region.get("position") or {}
        x, z = pos.get("x", 0), pos.get("z", 0)
        return box(x, z, x + 1, z + 1)

    if t == "point":
        pos = region.get("position") or {}
        x, z = pos.get("x", 0), pos.get("z", 0)
        return box(x - 0.5, z - 0.5, x + 0.5, z + 0.5)

    if t == "half":
        origin = region.get("origin") or {}
        normal = region.get("normal") or {}
        return _half_to_shapely(
            origin.get("x", 0), origin.get("z", 0),
            normal.get("x", 0), normal.get("z", 0),
            bounds,
        )

    if t in ("complement", "union", "intersect", "negative"):
        children = region.get("children", [])
        child_geoms = [
            _dict_to_shapely(_resolve_ref(c, registry), bounds, registry) for c in children
        ]

        if t == "union":
            valid = [g for g in child_geoms if g is not None and not g.is_empty]
            return unary_union(valid) if valid else None

        if t == "complement":
            if not child_geoms or child_geoms[0] is None or child_geoms[0].is_empty:
                return None
            base = child_geoms[0]
            rest = [g for g in child_geoms[1:] if g is not None and not g.is_empty]
            if rest:
                base = base.difference(unary_union(rest))
                if not base.is_valid:
                    try:
                        from shapely.validation import make_valid
                        base = make_valid(base)
                    except Exception:
                        pass
            return base if not base.is_empty else None

        if t == "intersect":
            if not child_geoms or child_geoms[0] is None:
                return None
            result = child_geoms[0]
            for g in child_geoms[1:]:
                if g is not None and not g.is_empty:
                    result = result.intersection(g)
            return result if result is not None and not result.is_empty else None

        if t == "negative":
            from shapely.geometry import box as _shp_box
            min_x, min_z, max_x, max_z = bounds
            map_box = _shp_box(min_x, min_z, max_x, max_z)
            valid = [g for g in child_geoms if g is not None and not g.is_empty]
            result = map_box.difference(unary_union(valid)) if valid else map_box
            return result if not result.is_empty else None

    if t == "mirror":
        source = _resolve_source(region, registry)
        if source is None:
            return None
        src_geom = _dict_to_shapely(source, bounds, registry)
        if src_geom is None or src_geom.is_empty:
            return None
        origin = region.get("origin") or {}
        normal = region.get("normal") or {}
        nx, nz = normal.get("x", 0) or 0, normal.get("z", 0) or 0
        ox, oz = origin.get("x", 0) or 0, origin.get("z", 0) or 0
        return _reflect_geom(src_geom, nx, nz, ox, oz)

    if t == "translate":
        source = _resolve_source(region, registry)
        if source is None:
            return None
        src_geom = _dict_to_shapely(source, bounds, registry)
        if src_geom is None or src_geom.is_empty:
            return None
        offset = region.get("offset") or {}
        return translate(src_geom, xoff=offset.get("x", 0), yoff=offset.get("z", 0))

    if t == "reference":
        ref_id = region.get("ref_id", "")
        if ref_id and registry and ref_id in registry:
            return _dict_to_shapely(registry[ref_id], bounds, registry)
        return None

    return None


def _shapely_to_polygon_2d(geom) -> dict | None:
    if geom is None or geom.is_empty:
        return None
    if hasattr(geom, "geoms"):
        polys = [g for g in geom.geoms if hasattr(g, "exterior") and not g.is_empty]
    elif hasattr(geom, "exterior"):
        polys = [geom]
    else:
        return None
    if not polys:
        return None

    def _ring(coords):
        return [[round(x, 2), round(y, 2)] for x, y in coords]

    polygons = [
        {"exterior": _ring(p.exterior.coords), "holes": [_ring(h.coords) for h in p.interiors]}
        for p in polys
    ]
    return {"polygons": polygons, "exterior": polygons[0]["exterior"], "holes": polygons[0]["holes"]}


def _compute_polygon_2d(region: dict, bounds: tuple, registry: dict | None) -> dict | None:
    try:
        geom = _dict_to_shapely(region, bounds, registry)
        return _shapely_to_polygon_2d(geom)
    except Exception:
        return None


# ── node encoding ─────────────────────────────────────────────────────────────

def _collect_named_child_ids(region: dict, out: set[str]) -> None:
    for child in region.get("children", []):
        if isinstance(child, str):
            out.add(child)
        elif isinstance(child, dict):
            child_id = child.get("id") or ""
            if child_id:
                out.add(child_id)
            _collect_named_child_ids(child, out)


def _encode_node(region: dict, bounds: tuple | None = None,
                 registry: dict | None = None) -> dict:
    xml_id      = region.get("id") or ""
    region_type = region.get("type", "unknown")
    label       = xml_id if xml_id else f"({region_type})"
    if region_type == "reference":
        label = f"→ {region.get('ref_id', '?')}"

    children = []
    for child in region.get("children", []):
        if isinstance(child, str):
            if registry and child in registry:
                children.append(_encode_node(registry[child], bounds=bounds, registry=registry))
        elif isinstance(child, dict):
            children.append(_encode_node(child, bounds=bounds, registry=registry))
    raw_source  = _resolve_source(region, registry)
    source_node = _encode_node(raw_source, bounds=bounds, registry=registry) if raw_source else None

    node: dict = {
        "id":           xml_id,
        "type":         region_type,
        "label":        label,
        "bounds":       _encode_bounds(region),
        "coords":       _encode_coords(region),
        "is_negative":  region_type == "negative",
        "synthetic_id": not bool(xml_id),
        "children":     children,
        "source":       source_node,
    }

    if bounds is not None and region_type in _POLYGON_TYPES:
        polygon_2d = _compute_polygon_2d(region, bounds, registry)
        if polygon_2d is not None:
            node["polygon_2d"] = polygon_2d
            if node["bounds"] is None:
                xs = [p[0] for p in polygon_2d["exterior"]]
                zs = [p[1] for p in polygon_2d["exterior"]]
                if xs:
                    node["bounds"] = {
                        "min_x": min(xs), "min_z": min(zs),
                        "max_x": max(xs), "max_z": max(zs),
                    }
    return node


# ── public API ────────────────────────────────────────────────────────────────

def encode_region_tree(
    regions_dict: dict,
    categories: dict,
    bounding_box: dict | None = None,
) -> list[dict]:
    """Return root regions grouped into thematic categories for the browser.

    Args:
        regions_dict: {id: region_dict} from xml_data.json["regions"].
        categories:   {id: category_name} flat dict — "spawn", "wool", "build", "other".
        bounding_box: {min_x, min_z, max_x, max_z} or None.  Used for Shapely polygon
                      computation on composite region types.
    Returns:
        [{name, label, regions: [node, ...]}, ...] — only non-empty categories.
    """
    bounds: tuple | None = None
    if bounding_box:
        try:
            bounds = (
                float(bounding_box["min_x"]),
                float(bounding_box["min_z"]),
                float(bounding_box["max_x"]),
                float(bounding_box["max_z"]),
            )
        except (KeyError, TypeError, ValueError):
            bounds = None

    named_child_ids: set[str] = set()
    for region in regions_dict.values():
        _collect_named_child_ids(region, named_child_ids)

    root_nodes = [
        _encode_node(region, bounds=bounds, registry=regions_dict)
        for region_id, region in regions_dict.items()
        if region_id not in named_child_ids
    ]

    groups: dict[str, list[dict]] = {}
    for node in root_nodes:
        cat = categories.get(node["id"], "other")
        if cat not in _CATEGORY_ORDER:
            cat = "other"
        groups.setdefault(cat, []).append(node)

    seen = set(_CATEGORY_ORDER)
    ordered = _CATEGORY_ORDER + [c for c in groups if c not in seen]
    return [
        {
            "name":    cat,
            "label":   _CATEGORY_LABELS.get(cat, cat.title()),
            "regions": groups[cat],
        }
        for cat in ordered
        if cat in groups
    ]
