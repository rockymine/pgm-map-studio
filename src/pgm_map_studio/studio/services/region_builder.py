"""region_builder — build and update in-memory region dicts.

Pure data-transformation functions: no I/O, no Flask, no side-effects.
All functions operate on the same dict shape stored in xml_data.json.
"""
from __future__ import annotations


def _bounds(min_x: float, min_z: float, max_x: float, max_z: float) -> dict:
    return {"min": {"x": min_x, "z": min_z}, "max": {"x": max_x, "z": max_z}}


def build_region_dict(region_type: str, body: dict, region_id: str) -> dict:
    """Build a new region dict from a validated request payload.

    Raises KeyError/TypeError/ValueError on missing or malformed fields.
    """
    if region_type in ("rectangle", "cuboid"):
        min_x = int(round(float(body["min_x"])))
        min_z = int(round(float(body["min_z"])))
        max_x = int(round(float(body["max_x"])))
        max_z = int(round(float(body["max_z"])))
        region: dict = {
            "id": region_id, "type": region_type,
            "min_x": min_x, "min_z": min_z,
            "max_x": max_x, "max_z": max_z,
            "bounds_2d": _bounds(min_x, min_z, max_x, max_z),
        }
        if region_type == "cuboid":
            region["min_y"] = int(round(float(body.get("min_y", 0))))
            region["max_y"] = int(round(float(body.get("max_y", 256))))
        return region

    if region_type in ("point", "block"):
        px = int(round(float(body["x"])))
        pz = int(round(float(body["z"])))
        py = int(round(float(body.get("y", 64))))
        bounds_2d = (
            _bounds(px, pz, px + 1, pz + 1)
            if region_type == "block"
            else _bounds(px - 0.5, pz - 0.5, px + 0.5, pz + 0.5)
        )
        return {
            "id": region_id, "type": region_type,
            "position": {"x": px, "y": py, "z": pz},
            "bounds_2d": bounds_2d,
        }

    if region_type == "cylinder":
        bx = float(body["base_x"])
        bz = float(body["base_z"])
        by = float(body.get("base_y", 64))
        r  = float(body["radius"])
        h  = float(body.get("height", 10))
        return {
            "id": region_id, "type": "cylinder",
            "base": {"x": bx, "y": by, "z": bz},
            "radius": r, "height": h,
            "bounds_2d": _bounds(bx - r, bz - r, bx + r, bz + r),
        }

    if region_type == "circle":
        cx = float(body["center_x"])
        cz = float(body["center_z"])
        r  = float(body["radius"])
        return {
            "id": region_id, "type": "circle",
            "center": {"x": cx, "z": cz},
            "radius": r,
            "bounds_2d": _bounds(cx - r, cz - r, cx + r, cz + r),
        }

    raise ValueError(f"unsupported type {region_type!r}")


def build_union_bounds(children: list[dict]) -> tuple[dict | None, float, float, float, float]:
    """Compute bounds_2d for a union from its children.

    Returns (bounds_2d, min_x, min_z, max_x, max_z).
    bounds_2d is None when no child has bounds_2d.
    """
    bounded = [c for c in children if c.get("bounds_2d")]
    if bounded:
        min_x = min(c["bounds_2d"]["min"]["x"] for c in bounded)
        min_z = min(c["bounds_2d"]["min"]["z"] for c in bounded)
        max_x = max(c["bounds_2d"]["max"]["x"] for c in bounded)
        max_z = max(c["bounds_2d"]["max"]["z"] for c in bounded)
        bounds_2d: dict | None = {"min": {"x": min_x, "z": min_z}, "max": {"x": max_x, "z": max_z}}
    else:
        bounds_2d = None
        min_x = min_z = max_x = max_z = 0.0
    return bounds_2d, min_x, min_z, max_x, max_z


def apply_coord_update(region: dict, region_type: str, coords: dict) -> dict | None:
    """Apply coordinate field updates to *region* in-place and recompute bounds_2d.

    Returns the new bounds_2d dict, or None if no 2D footprint changed
    (e.g. cuboid Y-only edits).
    """
    if region_type == "rectangle":
        for k in ("min_x", "min_z", "max_x", "max_z"):
            if k in coords:
                region[k] = coords[k]
        new_bounds = _bounds(
            region.get("min_x", 0), region.get("min_z", 0),
            region.get("max_x", 0), region.get("max_z", 0),
        )
        region["bounds_2d"] = new_bounds
        return new_bounds

    if region_type == "cuboid":
        for k in ("min_y", "max_y"):
            if k in coords:
                region[k] = coords[k]
        return None  # Y-only; 2D bounds unchanged

    if region_type == "cylinder":
        base = region.setdefault("base", {})
        for field, key in (("base_x", "x"), ("base_y", "y"), ("base_z", "z")):
            if field in coords:
                base[key] = coords[field]
        if "radius" in coords:
            region["radius"] = coords["radius"]
        if "height" in coords:
            region["height"] = coords["height"]
        bx, bz = base.get("x", 0), base.get("z", 0)
        r = float(region.get("radius", 0))
        new_bounds = _bounds(bx - r, bz - r, bx + r, bz + r)
        region["bounds_2d"] = new_bounds
        return new_bounds

    if region_type == "circle":
        center = region.setdefault("center", {})
        if "center_x" in coords:
            center["x"] = coords["center_x"]
        if "center_z" in coords:
            center["z"] = coords["center_z"]
        if "radius" in coords:
            region["radius"] = coords["radius"]
        cx, cz = center.get("x", 0), center.get("z", 0)
        r = float(region.get("radius", 0))
        new_bounds = _bounds(cx - r, cz - r, cx + r, cz + r)
        region["bounds_2d"] = new_bounds
        return new_bounds

    if region_type in ("block", "point"):
        pos = region.setdefault("position", {})
        for k in ("x", "y", "z"):
            if k in coords:
                pos[k] = coords[k]
        px, pz = pos.get("x", 0), pos.get("z", 0)
        new_bounds = (
            _bounds(px, pz, px + 1, pz + 1)
            if region_type == "block"
            else _bounds(px - 0.5, pz - 0.5, px + 0.5, pz + 0.5)
        )
        region["bounds_2d"] = new_bounds
        return new_bounds

    return None
