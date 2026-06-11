"""symmetry_authoring — C13: create counterpart regions from a source + symmetry.

The author owns one source region; this derives its counterpart(s) for a chosen
symmetry mode about the center, per ``data-model.md`` §7:

- **reflections** (``mirror_x``/``mirror_z``/``mirror_d1``/``mirror_d2``) persist
  as a native PGM ``mirror`` region chained by ``source_id``;
- **rot_180** = two perpendicular mirrors (native), so it emits two chained
  mirror regions;
- **rot_90** has no PGM rotation type, so it **bakes** to a concrete primitive
  region with rotated geometry.

General n-fold rotation (``rot_<n>`` for n∉{2,4}) is **not** supported here.
Geometry math comes from the leaf module ``pgm_map_studio.geometry``.
"""
from __future__ import annotations

from pgm_map_studio.geometry import (
    reflect_bounds_2d,
    rotate_bounds_2d,
    rotate_point_2d,
)
from pgm_map_studio.studio.services.region_editor import _regions_dict


class CounterpartError(Exception):
    pass


# mode → horizontal mirror normal (y = 0). d1 = main diagonal (swap),
# d2 = anti-diagonal (swap + negate). See geometry.md §2.
_MODE_NORMALS = {
    "mirror_x": (1.0, 0.0),
    "mirror_z": (0.0, 1.0),
    "mirror_d1": (1.0, -1.0),
    "mirror_d2": (1.0, 1.0),
}

SUPPORTED_MODES = (*_MODE_NORMALS, "rot_180", "rot_90")

_BAKEABLE_TYPES = {"rectangle", "cuboid", "cylinder", "circle", "sphere", "point", "block"}


def _fresh_id(regions: dict, prefix: str) -> str:
    i = 1
    while f"{prefix}_{i}" in regions:
        i += 1
    return f"{prefix}_{i}"


def _make_mirror(data: dict, source_id: str, mode: str, cx: float, cz: float) -> str:
    """Create a native PGM mirror region reflecting ``source_id`` about (cx,cz)."""
    regions = _regions_dict(data)
    nx, nz = _MODE_NORMALS[mode]
    src = regions[source_id]
    new_id = _fresh_id(regions, "mirror")
    region: dict = {
        "id": new_id,
        "type": "mirror",
        "source_id": source_id,
        "origin": {"x": cx, "y": 0.0, "z": cz},
        "normal": {"x": nx, "y": 0.0, "z": nz},
    }
    if src.get("bounds_2d"):
        region["bounds_2d"] = reflect_bounds_2d(src["bounds_2d"], nx, nz, cx, cz)
    regions[new_id] = region
    data.setdefault("region_categories", {}).setdefault("other", []).append(new_id)
    return new_id


def _bake_rot90(data: dict, source_id: str, cx: float, cz: float) -> str:
    """Bake a 90°-CCW rotation of a *primitive* source into a concrete region."""
    regions = _regions_dict(data)
    src = regions[source_id]
    stype = src.get("type")
    if stype not in _BAKEABLE_TYPES:
        raise CounterpartError(
            f"rot_90 bake not supported for region type {stype!r} "
            f"(only primitives; group/transform sources are out of scope)"
        )
    new_id = _fresh_id(regions, f"{stype}")
    region: dict = {"id": new_id, "type": stype}

    def _rot(pt: dict) -> dict:
        rx, rz = rotate_point_2d(pt["x"], pt["z"], 90, cx, cz)
        out = {"x": rx, "z": rz}
        if "y" in pt:
            out["y"] = pt["y"]
        return out

    if stype == "rectangle":
        pass  # geometry is bounds_2d only
    elif stype == "cuboid":
        b = rotate_bounds_2d(
            {"min": {"x": src["min"]["x"], "z": src["min"]["z"]},
             "max": {"x": src["max"]["x"], "z": src["max"]["z"]}}, 90, cx, cz)
        region["min"] = {"x": b["min"]["x"], "y": src["min"]["y"], "z": b["min"]["z"]}
        region["max"] = {"x": b["max"]["x"], "y": src["max"]["y"], "z": b["max"]["z"]}
    elif stype == "cylinder":
        region["base"] = _rot(src["base"])
        region["radius"] = src["radius"]
        if "height" in src:
            region["height"] = src["height"]
    elif stype == "circle":
        region["center"] = _rot(src["center"])
        region["radius"] = src["radius"]
    elif stype == "sphere":
        region["origin"] = _rot(src["origin"])
        region["radius"] = src["radius"]
    else:  # point, block
        region["position"] = _rot(src["position"])

    if src.get("bounds_2d"):
        region["bounds_2d"] = rotate_bounds_2d(src["bounds_2d"], 90, cx, cz)
    regions[new_id] = region
    data.setdefault("region_categories", {}).setdefault("other", []).append(new_id)
    return new_id


def create_counterpart(data: dict, source_id: str, mode: str,
                       cx: float, cz: float) -> dict:
    """Create the counterpart region(s) of ``source_id`` for ``mode`` about (cx,cz).

    Returns ``{"counterpart": id, "created": [ids…]}``. ``created`` lists every new
    region (rot_180 emits an intermediate mirror plus the final one).
    Raises CounterpartError on a missing source or unsupported mode/type.
    """
    regions = _regions_dict(data)
    if source_id not in regions:
        raise CounterpartError(f"source region {source_id!r} not found")

    if mode in _MODE_NORMALS:
        rid = _make_mirror(data, source_id, mode, cx, cz)
        return {"counterpart": rid, "created": [rid]}

    if mode == "rot_180":
        m1 = _make_mirror(data, source_id, "mirror_x", cx, cz)
        m2 = _make_mirror(data, m1, "mirror_z", cx, cz)  # ⟂ composition = 180° turn
        return {"counterpart": m2, "created": [m1, m2]}

    if mode == "rot_90":
        rid = _bake_rot90(data, source_id, cx, cz)
        return {"counterpart": rid, "created": [rid]}

    raise CounterpartError(
        f"unsupported mode {mode!r} (n-fold rot_n is out of scope; "
        f"use one of {', '.join(SUPPORTED_MODES)})"
    )
