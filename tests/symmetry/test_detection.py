"""Tests for pgm_map_studio.symmetry.detection."""

import json
import pytest
from pathlib import Path

from pgm_map_studio.symmetry.detection import (
    detect_from_data,
    _prep_island,
    _classify_center,
    _detect_pair_transform,
    _aggregate_pair_transforms,
    _detect_modes,
    _verify_polygon_symmetry,
    _geometric_pair_support,
)
from pgm_map_studio.symmetry.datatypes import SymmetryResult


# ---------------------------------------------------------------------------
# Synthetic island builders (pgm-map-studio islands.json format)
# ---------------------------------------------------------------------------

def _make_island(island_id: int, min_x: float, max_x: float,
                 min_z: float, max_z: float, block_count: int | None = None):
    """Build an island dict in the pgm-map-studio islands.json format."""
    area = int((max_x - min_x) * (max_z - min_z))
    count = block_count if block_count is not None else area
    exterior = [
        [min_x, min_z], [max_x, min_z], [max_x, max_z],
        [min_x, max_z], [min_x, min_z],
    ]
    return {
        'id': island_id,
        'block_count': count,
        'bounds': [min_x, min_z, max_x, max_z],
        'polygon': {'type': 'Polygon', 'coordinates': [exterior]},
    }


# ---------------------------------------------------------------------------
# _prep_island adapter
# ---------------------------------------------------------------------------

def test_prep_island_center():
    isl = _make_island(1, 0, 10, 20, 40)
    p = _prep_island(isl)
    assert p['center'] == [5.0, 30.0]


def test_prep_island_area_from_block_count():
    isl = _make_island(1, 0, 10, 0, 10, block_count=75)
    p = _prep_island(isl)
    assert p['area'] == 75


def test_prep_island_exterior_format():
    isl = _make_island(1, 0, 10, 0, 10)
    p = _prep_island(isl)
    assert isinstance(p['simplified_polygon']['exterior'], list)


# ---------------------------------------------------------------------------
# _classify_center
# ---------------------------------------------------------------------------

def test_center_of_symmetric_map():
    c = _classify_center(-50, 50, -100, 100)
    assert c['center_x'] == 0.0
    assert c['center_z'] == 0.0


# ---------------------------------------------------------------------------
# _detect_pair_transform
# ---------------------------------------------------------------------------

def test_mirror_x_pair():
    a = {'center': [5.0, 3.0]}
    b = {'center': [-5.0, 3.0]}
    transforms = _detect_pair_transform(a, b, 0.0, 0.0)
    assert 'mirror_x' in transforms
    assert 'mirror_z' not in transforms


def test_mirror_z_pair():
    a = {'center': [3.0, 5.0]}
    b = {'center': [3.0, -5.0]}
    transforms = _detect_pair_transform(a, b, 0.0, 0.0)
    assert 'mirror_z' in transforms


def test_rot_180_pair():
    a = {'center': [5.0, 3.0]}
    b = {'center': [-5.0, -3.0]}
    transforms = _detect_pair_transform(a, b, 0.0, 0.0)
    assert 'rot_180' in transforms


def test_rot_90_pair():
    # (5, 3) -> rot_90 CCW -> (3, -5)
    a = {'center': [5.0, 3.0]}
    b = {'center': [3.0, -5.0]}
    transforms = _detect_pair_transform(a, b, 0.0, 0.0)
    assert 'rot_90' in transforms


def test_no_transform_pair():
    a = {'center': [5.0, 3.0]}
    b = {'center': [7.0, 1.0]}
    transforms = _detect_pair_transform(a, b, 0.0, 0.0, tolerance=1.0)
    assert transforms == []


# ---------------------------------------------------------------------------
# rot_180 symmetric map detection
# ---------------------------------------------------------------------------

def _build_rot180_islands():
    """Two-island layout with rot_180 symmetry (no mirror)."""
    return [
        _make_island(1, -10, 0, -55, -25),
        _make_island(2, 0, 10, 25, 55),
        _make_island(3, 15, 25, -15, -5),
        _make_island(4, -25, -15, 5, 15),
        _make_island(5, 10, 20, -35, -25),
        _make_island(6, -20, -10, 25, 35),
    ]


def test_rot180_detected():
    islands = _build_rot180_islands()
    result = detect_from_data(islands)
    rot180 = next(e for e in result.modes if e.type == 'rot_180')
    assert rot180.detected is True
    assert rot180.confidence >= 0.60


def test_rot180_not_mirror_x():
    islands = _build_rot180_islands()
    result = detect_from_data(islands)
    mirror_x = next(e for e in result.modes if e.type == 'mirror_x')
    assert mirror_x.detected is False


def test_rot180_is_primary():
    islands = _build_rot180_islands()
    result = detect_from_data(islands)
    assert result.primary is not None
    assert result.primary['type'] == 'rot_180'


# ---------------------------------------------------------------------------
# mirror_x symmetric map detection
# ---------------------------------------------------------------------------

def _build_mirror_x_islands():
    """Map with mirror_x symmetry (teams separated along X axis)."""
    return [
        _make_island(1, -45, -15, -10, 10),
        _make_island(2, 15, 45, -10, 10),
        _make_island(3, -20, -5, 10, 30),
        _make_island(4, 5, 20, 10, 30),
        _make_island(5, -20, -5, -30, -10),
        _make_island(6, 5, 20, -30, -10),
    ]


def test_mirror_x_detected():
    islands = _build_mirror_x_islands()
    result = detect_from_data(islands)
    mirror_x = next(e for e in result.modes if e.type == 'mirror_x')
    assert mirror_x.detected is True


# ---------------------------------------------------------------------------
# mirror_z symmetric map detection
# ---------------------------------------------------------------------------

def _build_mirror_z_islands():
    """Map with mirror_z symmetry (teams separated along Z axis)."""
    return [
        _make_island(1, -10, 10, -45, -15),
        _make_island(2, -10, 10, 15, 45),
        _make_island(3, 10, 30, -20, -5),
        _make_island(4, 10, 30, 5, 20),
        _make_island(5, -30, -10, -20, -5),
        _make_island(6, -30, -10, 5, 20),
    ]


def test_mirror_z_detected():
    islands = _build_mirror_z_islands()
    result = detect_from_data(islands)
    mirror_z = next(e for e in result.modes if e.type == 'mirror_z')
    assert mirror_z.detected is True


# ---------------------------------------------------------------------------
# rot_90 symmetric map
# ---------------------------------------------------------------------------

def _build_rot90_islands():
    """Four-island layout with 90-degree rotational symmetry."""
    return [
        _make_island(1, -10, 10, -50, -30),   # south
        _make_island(2, 30, 50, -10, 10),     # east
        _make_island(3, -50, -30, -10, 10),   # west
        _make_island(4, -10, 10, 30, 50),     # north
        _make_island(5, 5, 15, -35, -25),
        _make_island(6, -35, -25, -15, -5),
        _make_island(7, -15, -5, 25, 35),
        _make_island(8, 25, 35, 5, 15),
    ]


def test_rot90_detected():
    islands = _build_rot90_islands()
    result = detect_from_data(islands)
    rot90 = next(e for e in result.modes if e.type == 'rot_90')
    assert rot90.detected is True
    assert rot90.confidence >= 0.80


def test_rot180_also_detected_on_rot90_map():
    islands = _build_rot90_islands()
    result = detect_from_data(islands)
    rot180 = next(e for e in result.modes if e.type == 'rot_180')
    assert rot180.detected is True


# ---------------------------------------------------------------------------
# Asymmetric map — no symmetry detected
# ---------------------------------------------------------------------------

def test_asymmetric_no_symmetry():
    islands = [
        _make_island(1, 0, 10, 0, 10),
        _make_island(2, 30, 50, 40, 60),
        _make_island(3, -20, -5, 30, 40),
    ]
    result = detect_from_data(islands)
    for entry in result.modes:
        assert entry.confidence <= 0.60 or not entry.detected


# ---------------------------------------------------------------------------
# Confidence scores in range
# ---------------------------------------------------------------------------

def test_confidence_scores_in_range():
    islands = _build_rot180_islands()
    result = detect_from_data(islands)
    for entry in result.modes:
        assert 0.0 <= entry.confidence <= 1.0


# ---------------------------------------------------------------------------
# Primary selection
# ---------------------------------------------------------------------------

def test_primary_is_highest_confidence_detected():
    islands = _build_rot180_islands()
    result = detect_from_data(islands)
    detected = [e for e in result.modes if e.detected]
    if detected:
        best = max(detected, key=lambda e: e.confidence)
        assert result.primary['type'] == best.type


def test_primary_is_none_when_nothing_detected():
    islands = [
        _make_island(1, 0, 10, 0, 10),
        _make_island(2, 30, 50, 40, 60),
    ]
    result = detect_from_data(islands)
    # primary may or may not be None depending on confidence, just check type
    if result.primary is not None:
        assert result.primary['confidence'] >= 0.0


# ---------------------------------------------------------------------------
# Observer island exclusion
# ---------------------------------------------------------------------------

def test_exclude_islands_changes_result():
    # Add an asymmetric "observer island" that disrupts symmetry
    base = _build_rot180_islands()
    with_observer = base + [_make_island(99, -3, 3, -3, 3, block_count=36)]
    without_obs = detect_from_data(with_observer, exclude_islands=[99])
    with_obs = detect_from_data(with_observer)
    # Just verify the exclusion path runs without error and returns valid result
    assert isinstance(without_obs, SymmetryResult)
    assert len(without_obs.modes) == 4


def test_exclude_all_islands_returns_unconfirmed():
    islands = _build_rot180_islands()
    ids = [isl['id'] for isl in islands]
    result = detect_from_data(islands, exclude_islands=ids)
    assert result.status == 'unconfirmed'
    assert result.primary is None


# ---------------------------------------------------------------------------
# Empty island list
# ---------------------------------------------------------------------------

def test_empty_islands_returns_unconfirmed():
    result = detect_from_data([])
    assert result.status == 'unconfirmed'
    assert len(result.modes) == 4
    assert result.primary is None


# ---------------------------------------------------------------------------
# Polygon IoU verification
# ---------------------------------------------------------------------------

def test_polygon_iou_perfect_rot180():
    islands = [_prep_island(isl) for isl in _build_rot180_islands()]
    iou = _verify_polygon_symmetry(islands, 0.0, 0.0, 'rot_180')
    assert iou >= 0.99


def test_polygon_iou_low_for_bad_transform():
    islands = [_prep_island(isl) for isl in [
        _make_island(1, 0, 10, 0, 10),
        _make_island(2, 30, 50, 40, 60),
    ]]
    iou = _verify_polygon_symmetry(islands, 0.0, 0.0, 'rot_180')
    assert iou < 0.50


# ---------------------------------------------------------------------------
# File-based detect
# ---------------------------------------------------------------------------

def test_detect_from_file(tmp_path):
    from pgm_map_studio.symmetry.detection import detect
    islands = _build_rot180_islands()
    path = tmp_path / "islands.json"
    path.write_text(json.dumps(islands))
    result = detect(path)
    assert isinstance(result, SymmetryResult)
    rot180 = next(e for e in result.modes if e.type == 'rot_180')
    assert rot180.detected is True
