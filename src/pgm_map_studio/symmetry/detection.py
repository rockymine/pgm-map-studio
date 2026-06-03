"""Symmetry detection algorithms for island polygon data.

Reads islands.json produced by pgm_map_studio.layout and detects global
geometric symmetry (mirror_x, mirror_z, rot_180, rot_90) using a combination
of island-centroid pairing and polygon IoU verification.

Islands.json format (pgm_map_studio.layout output):
    [{"id": 1, "block_count": 7950,
      "bounds": [min_x, min_z, max_x, max_z],
      "polygon": {"type": "Polygon", "coordinates": [exterior, ...holes...]}}]

Polygon coordinates are [x, z] pairs (Shapely y = Minecraft z).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

from .datatypes import GlobalSymmetryEntry, SymmetryResult


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect(
    islands_path: str | Path,
    exclude_islands: Optional[list[int]] = None,
) -> SymmetryResult:
    """Detect symmetry from an islands.json file."""
    data = json.loads(Path(islands_path).read_text())
    return detect_from_data(data, exclude_islands=exclude_islands)


def detect_from_data(
    islands_data: list[dict],
    exclude_islands: Optional[list[int]] = None,
) -> SymmetryResult:
    """Detect symmetry from parsed islands.json data (list of island dicts).

    Args:
        islands_data:    List of island dicts as produced by layout.save_islands.
        exclude_islands: Island IDs to exclude from detection (observer islands etc).
    """
    exclude = set(exclude_islands or [])
    islands = [
        _prep_island(isl) for isl in islands_data
        if isl['id'] not in exclude
    ]

    if not islands:
        return SymmetryResult(
            symmetry_status='skipped',
            global_symmetry=[
                GlobalSymmetryEntry(t, False, 0.0, d)
                for t, d in _CANDIDATES
            ],
            center={'center_x': 0.0, 'center_z': 0.0},
        )

    bbox = _map_bbox(islands_data, exclude)
    # classify_center uses (min_x, max_x, min_z, max_z) order
    center_info = _classify_center(bbox[0], bbox[2], bbox[1], bbox[3])
    cx, cz = center_info['center_x'], center_info['center_z']

    pair_analysis = _aggregate_pair_transforms(islands, cx, cz)
    global_symmetry = _detect_global_symmetry(islands, cx, cz, pair_analysis)

    return SymmetryResult(
        symmetry_status='skipped',
        global_symmetry=global_symmetry,
        center={'center_x': cx, 'center_z': cz},
    )


# ---------------------------------------------------------------------------
# Island format adapter
# ---------------------------------------------------------------------------

def _prep_island(isl: dict) -> dict:
    """Convert pgm-map-studio island dict to the internal format used by detection."""
    bounds = isl['bounds']  # [min_x, min_z, max_x, max_z]
    center_x = (bounds[0] + bounds[2]) / 2.0
    center_z = (bounds[1] + bounds[3]) / 2.0
    coords = isl['polygon']['coordinates']
    exterior = coords[0] if coords else []
    return {
        'id': isl['id'],
        'area': isl['block_count'],
        'center': [center_x, center_z],
        'simplified_polygon': {'exterior': exterior},
    }


def _map_bbox(
    islands_data: list[dict], exclude: set[int]
) -> tuple[float, float, float, float]:
    """Return (min_x, min_z, max_x, max_z) of the map from island bounds."""
    bounds_list = [
        isl['bounds'] for isl in islands_data
        if isl['id'] not in exclude
    ]
    if not bounds_list:
        return 0.0, 0.0, 0.0, 0.0
    min_x = min(b[0] for b in bounds_list)
    min_z = min(b[1] for b in bounds_list)
    max_x = max(b[2] for b in bounds_list)
    max_z = max(b[3] for b in bounds_list)
    return min_x, min_z, max_x, max_z


# ---------------------------------------------------------------------------
# Center classification
# ---------------------------------------------------------------------------

def _classify_center(
    min_x: float, max_x: float, min_z: float, max_z: float
) -> dict:
    """Classify the map center from the bounding box."""
    width_x = max_x - min_x
    width_z = max_z - min_z
    center_x = (min_x + max_x) / 2.0
    center_z = (min_z + max_z) / 2.0
    return {'center_x': center_x, 'center_z': center_z,
            'width_x': int(width_x), 'width_z': int(width_z)}


# ---------------------------------------------------------------------------
# Symmetry candidates
# ---------------------------------------------------------------------------

_CANDIDATES = [
    ("mirror_x", "Mirror symmetry across X axis"),
    ("mirror_z", "Mirror symmetry across Z axis"),
    ("rot_180", "180-degree rotational symmetry"),
    ("rot_90", "90-degree rotational symmetry"),
]


# ---------------------------------------------------------------------------
# Island pairing
# ---------------------------------------------------------------------------

def _build_canonical_pairs(islands: list[dict]) -> list[tuple[dict, dict]]:
    by_area: dict[int, list[dict]] = defaultdict(list)
    for isl in islands:
        by_area[isl['area']].append(isl)

    pairs = []
    for area, group in by_area.items():
        if len(group) == 2:
            pairs.append((group[0], group[1]))
        elif len(group) >= 4:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    pairs.append((group[i], group[j]))
    return pairs


# ---------------------------------------------------------------------------
# Transform detection between centroid pairs
# ---------------------------------------------------------------------------

def _detect_pair_transform(
    a: dict, b: dict, center_x: float, center_z: float, tolerance: float = 2.0
) -> list[str]:
    ax, az = a['center']
    bx, bz = b['center']
    transforms = []

    if abs(2 * center_x - ax - bx) < tolerance and abs(az - bz) < tolerance:
        transforms.append('mirror_x')
    if abs(ax - bx) < tolerance and abs(2 * center_z - az - bz) < tolerance:
        transforms.append('mirror_z')
    if abs(2 * center_x - ax - bx) < tolerance and abs(2 * center_z - az - bz) < tolerance:
        transforms.append('rot_180')

    r90x = center_x + (az - center_z)
    r90z = center_z - (ax - center_x)
    if abs(r90x - bx) < tolerance and abs(r90z - bz) < tolerance:
        transforms.append('rot_90')

    r270x = center_x - (az - center_z)
    r270z = center_z + (ax - center_x)
    if abs(r270x - bx) < tolerance and abs(r270z - bz) < tolerance:
        transforms.append('rot_270')

    return transforms


def _aggregate_pair_transforms(
    islands: list[dict], center_x: float, center_z: float, tolerance: float = 3.0
) -> dict:
    pairs = _build_canonical_pairs(islands)
    transform_counts: dict[str, int] = {}
    pair_details = []

    for a, b in pairs:
        transforms = _detect_pair_transform(a, b, center_x, center_z, tolerance)
        for t in transforms:
            transform_counts[t] = transform_counts.get(t, 0) + 1
        pair_details.append({
            'island_a': a['id'], 'island_b': b['id'],
            'area': a['area'], 'transforms': transforms,
        })

    return {
        'pairs': pair_details,
        'transform_counts': transform_counts,
        'total_pairs': len(pairs),
    }


# ---------------------------------------------------------------------------
# Polygon IoU verification
# ---------------------------------------------------------------------------

def _transform_coords(
    exterior: list, transform: str, cx: float, cz: float
) -> np.ndarray:
    pts = np.array(exterior, dtype=float)
    if transform == 'mirror_x':
        pts[:, 0] = 2 * cx - pts[:, 0]
    elif transform == 'mirror_z':
        pts[:, 1] = 2 * cz - pts[:, 1]
    elif transform == 'rot_180':
        pts[:, 0] = 2 * cx - pts[:, 0]
        pts[:, 1] = 2 * cz - pts[:, 1]
    elif transform in ('rot_90', 'rot_270'):
        dx = pts[:, 0] - cx
        dz = pts[:, 1] - cz
        if transform == 'rot_90':
            pts[:, 0] = cx + dz
            pts[:, 1] = cz - dx
        else:
            pts[:, 0] = cx - dz
            pts[:, 1] = cz + dx
    return pts


def _verify_polygon_symmetry(
    islands: list[dict], cx: float, cz: float, transform: str
) -> float:
    """Return IoU of the original island set vs its transformed copy."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    original_shapes = []
    transformed_shapes = []

    for isl in islands:
        ext = isl['simplified_polygon'].get('exterior', [])
        if len(ext) < 3:
            continue
        try:
            orig = Polygon(ext)
            if not orig.is_valid:
                orig = make_valid(orig)
            if orig.is_empty:
                continue
            original_shapes.append(orig)

            t_ext = _transform_coords(ext, transform, cx, cz).tolist()
            trans = Polygon(t_ext)
            if not trans.is_valid:
                trans = make_valid(trans)
            if not trans.is_empty:
                transformed_shapes.append(trans)
        except Exception:
            continue

    if not original_shapes or not transformed_shapes:
        return 0.0

    try:
        orig_union = unary_union(original_shapes)
        trans_union = unary_union(transformed_shapes)
        intersection = orig_union.intersection(trans_union).area
        union_area = orig_union.union(trans_union).area
        if union_area < 1e-6:
            return 0.0
        return intersection / union_area
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Geometry-based pair support (handles groups of 4+ identical-area islands)
# ---------------------------------------------------------------------------

def _apply_transform_center(
    x: float, z: float, transform: str, cx: float, cz: float
) -> tuple[float, float]:
    if transform == 'mirror_x':
        return 2.0 * cx - x, z
    elif transform == 'mirror_z':
        return x, 2.0 * cz - z
    elif transform == 'rot_180':
        return 2.0 * cx - x, 2.0 * cz - z
    elif transform == 'rot_90':
        return cx + (z - cz), cz - (x - cx)
    elif transform == 'rot_270':
        return cx - (z - cz), cz + (x - cx)
    return x, z


def _geometric_pair_support(
    islands: list[dict], transform: str, cx: float, cz: float, tolerance: float = 3.0
) -> tuple[int, int]:
    by_area: dict[int, list[dict]] = defaultdict(list)
    for isl in islands:
        by_area[isl['area']].append(isl)

    supporting = total = 0

    for _area, group in by_area.items():
        self_sym = []
        needs_partner = []
        for isl in group:
            ix, iz = isl['center']
            ex, ez = _apply_transform_center(ix, iz, transform, cx, cz)
            dist = ((ex - ix) ** 2 + (ez - iz) ** 2) ** 0.5
            if dist < tolerance:
                self_sym.append(isl)
            else:
                needs_partner.append(isl)

        supporting += len(self_sym)
        total += len(self_sym)

        n = len(needs_partner)
        if n == 0:
            continue
        if n == 1:
            total += 1
            continue

        n_pairs = n // 2
        total += n_pairs
        if n % 2 == 1:
            total += 1

        unassigned = list(range(n))
        paired = 0
        while len(unassigned) >= 2:
            i = unassigned[0]
            ix, iz = needs_partner[i]['center']
            ex, ez = _apply_transform_center(ix, iz, transform, cx, cz)

            best_j = None
            best_dist = float('inf')
            for j in unassigned[1:]:
                bx, bz = needs_partner[j]['center']
                d = ((ex - bx) ** 2 + (ez - bz) ** 2) ** 0.5
                if d < best_dist:
                    best_dist = d
                    best_j = j

            unassigned.remove(i)
            if best_j is not None and best_dist < tolerance:
                unassigned.remove(best_j)
                paired += 1

        supporting += paired

    return supporting, total


# ---------------------------------------------------------------------------
# Global symmetry detection
# ---------------------------------------------------------------------------

_GROUP_IOU_THRESHOLD = 0.85


def _detect_global_symmetry(
    islands: list[dict], cx: float, cz: float, pair_analysis: dict
) -> list[GlobalSymmetryEntry]:
    n_pairs = pair_analysis['total_pairs']
    counts = pair_analysis['transform_counts']
    pairs = pair_analysis['pairs']

    ious = {t: _verify_polygon_symmetry(islands, cx, cz, t) for t, _ in _CANDIDATES}

    results = []
    for sym_type, description in _CANDIDATES:
        iou = ious[sym_type]

        if sym_type == 'rot_90':
            if counts.get('rot_90', 0) == 0 or counts.get('rot_270', 0) == 0:
                pair_support = 0.0
            else:
                compatible = {'rot_90', 'rot_270'}
                if ious.get('rot_180', 0) >= _GROUP_IOU_THRESHOLD:
                    compatible.add('rot_180')
                if (ious.get('mirror_x', 0) >= _GROUP_IOU_THRESHOLD and
                        ious.get('mirror_z', 0) >= _GROUP_IOU_THRESHOLD):
                    compatible.update(['mirror_x', 'mirror_z'])
                supporting = sum(
                    1 for p in pairs if compatible & set(p['transforms'])
                )
                pair_support = supporting / n_pairs if n_pairs > 0 else 0.0
        else:
            sup, tot = _geometric_pair_support(islands, sym_type, cx, cz)
            pair_support = sup / tot if tot > 0 else 0.0

        confidence = (0.4 * pair_support + 0.6 * iou) if n_pairs > 0 else iou
        confidence = round(confidence, 3)

        results.append(GlobalSymmetryEntry(
            type=sym_type,
            detected=confidence >= 0.60,
            confidence=confidence,
            description=description,
        ))

    return results
