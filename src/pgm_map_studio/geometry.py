"""Pure 2D geometry transforms — the Python peer of the JS transform.js /
converters.js layer, and the single home for the reflection/rotation converters
in ``docs/contracts/geometry.md`` §6.

This module is a **leaf**: it imports nothing from ``pgm`` / ``studio`` and holds
no domain knowledge. Bounds use the nested ``{"min": {"x","z"}, "max": {"x","z"}}``
form (the parser's ``bounds_2d``). Reflections follow PGM ``<mirror>`` semantics;
rotations are CCW about an origin, matching ``geometry.md`` §2.
"""
from __future__ import annotations

import math


def _norm_bounds(min_x: float, min_z: float, max_x: float, max_z: float) -> dict:
    """A normalised bounds_2d AABB (min always ≤ max)."""
    return {
        "min": {"x": min(min_x, max_x), "z": min(min_z, max_z)},
        "max": {"x": max(min_x, max_x), "z": max(min_z, max_z)},
    }


# ── Reflection (PGM <mirror> semantics) ─────────────────────────────────────────

def reflect_point_2d(px: float, pz: float, nx: float, nz: float,
                     ox: float, oz: float) -> tuple[float, float]:
    """Reflect a point across the plane through (ox,oz) with horizontal normal (nx,nz).

    PGM ``<mirror>`` semantics (``result = p − n·(2·(p−o)·n / |n|²)``), so a
    **diagonal** normal (e.g. ``-1,0,-1``) reflects across the 45° axis (swapping
    x/z), not just an axis-aligned flip. An all-zero horizontal normal (a purely
    vertical mirror) leaves the footprint unchanged.
    """
    n2 = nx * nx + nz * nz
    if n2 == 0:
        return px, pz
    d = 2.0 * ((px - ox) * nx + (pz - oz) * nz) / n2
    return px - nx * d, pz - nz * d


def reflect_bounds_2d(bounds: dict, nx: float, nz: float,
                      ox: float, oz: float) -> dict:
    """Reflect a bounds_2d AABB across a mirror plane, returning a new AABB.

    All four corners are reflected (a diagonal mirror rotates the box), then
    re-bounded — exact for axis-aligned and 45° normals, a tight superset otherwise.
    """
    mn, mx = bounds["min"], bounds["max"]
    corners = [
        reflect_point_2d(x, z, nx, nz, ox, oz)
        for x in (mn["x"], mx["x"]) for z in (mn["z"], mx["z"])
    ]
    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    return _norm_bounds(min(xs), min(zs), max(xs), max(zs))


# ── Rotation (CCW about an origin, per geometry.md §2) ───────────────────────────

def rotate_point_2d(px: float, pz: float, degrees: float,
                    ox: float, oz: float) -> tuple[float, float]:
    """Rotate a point by ``degrees`` **CCW** about (ox,oz).

    90° multiples use exact integer arithmetic (no float drift), matching the
    ``geometry.md`` §2 formulas: rot_90 ``(Δx,Δz)→(−Δz,Δx)``, rot_180
    ``(−Δx,−Δz)``, rot_270 ``(Δz,−Δx)``. Other angles use cos/sin and are only
    approximate on the block grid (crystallographic restriction — see §2).
    """
    dx, dz = px - ox, pz - oz
    d = degrees % 360
    if d == 0:
        rx, rz = dx, dz
    elif d == 90:
        rx, rz = -dz, dx
    elif d == 180:
        rx, rz = -dx, -dz
    elif d == 270:
        rx, rz = dz, -dx
    else:
        th = math.radians(d)
        c, s = math.cos(th), math.sin(th)
        rx, rz = dx * c - dz * s, dx * s + dz * c
    return ox + rx, oz + rz


def rotate_bounds_2d(bounds: dict, degrees: float, ox: float, oz: float) -> dict:
    """Rotate a bounds_2d AABB about (ox,oz) and re-bound.

    Exact for 90° multiples (the rotated box stays axis-aligned); for other
    angles it is the AABB of the rotated corners (a tight superset).
    """
    mn, mx = bounds["min"], bounds["max"]
    corners = [
        rotate_point_2d(x, z, degrees, ox, oz)
        for x in (mn["x"], mx["x"]) for z in (mn["z"], mx["z"])
    ]
    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    return _norm_bounds(min(xs), min(zs), max(xs), max(zs))
