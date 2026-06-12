"""Objective-chain traversability (validation-invariants.md §B).

A CTW map is unwinnable if a team cannot physically run **spawn → enemy wool →
back**, even when every structural rule holds. This is a connectivity check over
a **navigability map**:

    navigable column = walkable (a block in `layer_surface`) OR bridgeable
                       (a buildable column from the C14 buildability check)

Crucially the walkable layer is the **surface**, not Y=0 — a golden_drought base
or wool path sits *above* Y=0 (its column is void at Y=0 but has a surface to
stand on). Connected components (4-connectivity) are computed; the map is
traversable iff every spawn and wool location lands in one component.

WARN, aspirational (it over-approximates: any height step is allowed, since a
player can fall and bridge) — so it only flags a *clear* disconnection (an island
with no surface and no buildable bridge to the rest). See plan C15.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from pgm_map_studio.studio.services.buildability import compute_buildability

_BUILDABLE, _RESTRICTED = 0, 3       # buildability verdict codes that are bridgeable


def compute_navigability(data: dict, surface_columns: set | None,
                         y0_columns: set | None, bbox: tuple | None = None,
                         margin: int = 16) -> dict:
    """navigable = surface (walkable) ∪ buildable (bridgeable), over the map bbox."""
    b = compute_buildability(data, y0_columns, bbox, margin)
    nx, nz = b["width"], b["height"]
    min_x, min_z, _, _ = b["bbox"]

    surface = np.zeros((nz, nx), dtype=bool)
    for (x, z) in (surface_columns or ()):
        ix, iz = x - min_x, z - min_z
        if 0 <= ix < nx and 0 <= iz < nz:
            surface[iz, ix] = True

    bridgeable = (b["verdict"] == _BUILDABLE) | (b["verdict"] == _RESTRICTED)
    navigable = surface | bridgeable
    return {"bbox": b["bbox"], "width": nx, "height": nz,
            "navigable": navigable, "surface": surface, "verdict": b["verdict"],
            "have_layers": bool(surface_columns)}


def _region_centre(region: dict | None):
    if not isinstance(region, dict):
        return None
    b = region.get("bounds_2d")
    if not b:
        return None
    mn, mx = b.get("min", {}), b.get("max", {})
    if not all(isinstance(mn.get(k), (int, float)) for k in "xz"):
        return None
    return (int((mn["x"] + mx["x"]) / 2), int((mn["z"] + mx["z"]) / 2))


def navigation_points(data: dict) -> list[dict]:
    """The columns that must be mutually reachable: every spawn + every wool."""
    regions = data.get("regions", {})
    pts: list[dict] = []
    for sp in data.get("spawns", []):
        r = sp.get("region")
        c = _region_centre(regions.get(r) if isinstance(r, str) else r)
        if c:
            pts.append({"kind": "spawn", "name": sp.get("team", ""), "x": c[0], "z": c[1]})
    for w in data.get("wools", []):
        loc = w.get("location")
        if isinstance(loc, dict) and isinstance(loc.get("x"), (int, float)):
            pts.append({"kind": "wool", "name": w.get("color", ""),
                        "x": int(loc["x"]), "z": int(loc["z"])})
        else:
            c = _region_centre(regions.get(w.get("wool_room_region")))
            if c:
                pts.append({"kind": "wool", "name": w.get("color", ""), "x": c[0], "z": c[1]})
    return pts


def _label_at(labels, navigable, ix, iz, snap=3):
    """Component label at (ix,iz); if that column isn't navigable, snap to the
    nearest navigable column within `snap` (a spawn point can sit 1 block off)."""
    nz, nx = labels.shape
    best = 0
    for r in range(0, snap + 1):
        for dz in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, z = ix + dx, iz + dz
                if 0 <= x < nx and 0 <= z < nz and navigable[z, x]:
                    return int(labels[z, x])
    return best


def check_reachability(nav: dict, points: list[dict]) -> dict:
    """Connected-components over the navigability grid; the map is traversable iff
    every spawn + wool point lands in the same component."""
    from scipy import ndimage
    cross = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])      # 4-connectivity
    labels, _ = ndimage.label(nav["navigable"], structure=cross)
    min_x, min_z, _, _ = nav["bbox"]
    nx, nz = nav["width"], nav["height"]

    placed = []
    for p in points:
        ix, iz = p["x"] - min_x, p["z"] - min_z
        comp = _label_at(labels, nav["navigable"], ix, iz) if (0 <= ix < nx and 0 <= iz < nz) else 0
        placed.append({**p, "component": comp})

    comps = [pp["component"] for pp in placed if pp["component"] > 0]
    main = Counter(comps).most_common(1)[0][0] if comps else 0
    isolated = [{"kind": pp["kind"], "name": pp["name"]} for pp in placed if pp["component"] != main]
    connected = len(set(comps)) <= 1 and not any(pp["component"] == 0 for pp in placed)

    return {"connected": connected, "component_count": len(set(comps)),
            "points": placed, "isolated": isolated, "have_layers": nav["have_layers"],
            "severity": "ok" if connected else "warning",
            "message": ("spawn ↔ wool objective chain is traversable" if connected else
                        f"{len(isolated)} spawn/wool point(s) are not reachable from the rest "
                        f"— check build regions / bridgeable gaps")}


def check_traversability(data: dict, surface_columns: set | None, y0_columns: set | None,
                         bbox: tuple | None = None, margin: int = 16) -> dict:
    nav = compute_navigability(data, surface_columns, y0_columns, bbox, margin)
    return check_reachability(nav, navigation_points(data))
