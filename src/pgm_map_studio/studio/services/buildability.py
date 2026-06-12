"""Buildability — where can players build on a map? (C14)

PGM builds everywhere by default; an XML carves that down with block / block-place
apply-rules over regions. Buildability is a join of **region geometry × the Y=0
layer × rule order** (last rule wins):

- `never`                         → not buildable (hard).
- `deny(void)` / `not(void)`      → not buildable only where **void** (no block at Y=0).
- a region id used as a filter    → buildable only *inside* that region (deny outside).
- a region-less (global) rule     → applies to the whole map.
- team/material filter            → restricted.

Per-column verdict over the map bbox (void/negatives are unbounded → clipped).
No I/O: callers pass the Y=0 columns (or None). See `tools/buildability_preview.py`
for a visual debugger and plan C14.
"""
from __future__ import annotations

import numpy as np

from pgm_map_studio.studio.services.region_encoder import _dict_to_shapely

# verdict codes → class names (index = code)
CLASSES = ["buildable", "never", "void_denied", "restricted"]
_BUILDABLE, _NEVER, _VOID, _RESTRICTED = 0, 1, 2, 3

# Canonical legend colours — the *story* of what allows/denies building. Shared by
# the API, the debug tool, and the UI overlay so all three read identically.
CLASS_COLORS = {
    "buildable":   "#4caf50",   # green  — default-allow
    "never":       "#c62828",   # red    — never / outside the playable region
    "void_denied": "#f57c00",   # orange — deny(void): no block at Y=0
    "restricted":  "#fbc02d",   # yellow — team / material conditional
}

_BLOCK_EVENTS = ("block_place", "block")   # placement-relevant events


def classify_filter(value: str, filters: dict, seen=None) -> str:
    """Classify a block filter value → 'never' | 'void' (deny-in-void) | 'allow' | 'other'."""
    seen = seen or set()
    if not value or value in seen:
        return "other"
    if value == "never":
        return "never"
    if value in ("always", "allow"):
        return "allow"
    if value == "deny(void)" or ("void" in value and value not in filters):
        return "void"
    f = filters.get(value)
    if not isinstance(f, dict):
        return "other"
    t = f.get("type")
    if t == "void":
        return "void"
    if t == "never":
        return "never"
    if t in ("not", "deny", "allow"):
        return classify_filter(f.get("child", ""), filters, seen | {value})
    if t in ("any", "all", "one"):
        kinds = [classify_filter(c, filters, seen | {value}) for c in f.get("children", [])]
        if "void" in kinds:
            return "void"
        if "never" in kinds:
            return "never"
    return "other"


def region_bbox(data: dict, margin: int) -> tuple[int, int, int, int]:
    """Map bbox from the union of region footprints, padded by `margin`."""
    xs, zs = [], []
    for r in data.get("regions", {}).values():
        b = r.get("bounds_2d")
        if b and all(isinstance(b.get("min", {}).get(k), (int, float)) for k in "xz"):
            xs += [b["min"]["x"], b["max"]["x"]]
            zs += [b["min"]["z"], b["max"]["z"]]
    if not xs:
        return (-64, -64, 64, 64)
    return (int(min(xs)) - margin, int(min(zs)) - margin,
            int(max(xs)) + margin, int(max(zs)) + margin)


def compute_buildability(
    data: dict,
    y0_columns: set | None = None,
    bbox: tuple[int, int, int, int] | None = None,
    margin: int = 16,
) -> dict:
    """Per-column buildability verdict over the map bbox.

    `y0_columns` is the set of `(x, z)` ints with a block at Y=0 (a column not in
    it is *void*); `None` means no Y=0 data (void can't be resolved → deny-void
    rules are skipped). Returns `{bbox, width, height, verdict (np.uint8 grid,
    row 0 = min_z), counts, has_y0}`.
    """
    import shapely

    regions = data.get("regions", {})
    filters = data.get("filters", {})
    rules = data.get("apply_rules", [])

    if bbox is None:
        bbox = region_bbox(data, margin)
    min_x, min_z, max_x, max_z = bbox
    nx, nz = max_x - min_x, max_z - min_z

    void = None
    has_y0 = y0_columns is not None
    if has_y0:
        terrain = np.zeros((nz, nx), dtype=bool)
        for (x, z) in y0_columns:
            ix, iz = x - min_x, z - min_z
            if 0 <= ix < nx and 0 <= iz < nz:
                terrain[iz, ix] = True
        void = ~terrain

    xs = np.arange(min_x, max_x) + 0.5
    zs = np.arange(min_z, max_z) + 0.5
    gx, gz = np.meshgrid(xs, zs)
    all_true = np.ones((nz, nx), dtype=bool)

    def _mask(ref):
        if ref is None:                       # region-less rule = whole map
            return all_true
        region = regions.get(ref) if isinstance(ref, str) else ref
        geom = _dict_to_shapely(region, bbox, regions) if region else None
        if geom is None or geom.is_empty:
            return None
        return shapely.contains_xy(geom, gx, gz)

    verdict = np.zeros((nz, nx), dtype=np.uint8)
    for rule in rules:
        inreg = _mask(rule.get("region"))
        if inreg is None:
            continue
        for ev in _BLOCK_EVENTS:
            val = rule.get(ev)
            if not val:
                continue
            if val in regions:                # region-as-filter gate: build only inside it
                gate = _mask(val)
                if gate is not None:
                    verdict[inreg & ~gate] = _NEVER
                continue
            kind = classify_filter(val, filters)
            if kind == "never":
                verdict[inreg] = _NEVER
            elif kind == "void" and void is not None:
                verdict[inreg & void] = _VOID
            elif kind == "other":
                verdict[inreg] = _RESTRICTED
            # 'allow' / unresolved-void → no change

    counts = {CLASSES[c]: int((verdict == c).sum()) for c in range(len(CLASSES))}
    return {"bbox": bbox, "width": nx, "height": nz,
            "verdict": verdict, "counts": counts, "has_y0": has_y0}
