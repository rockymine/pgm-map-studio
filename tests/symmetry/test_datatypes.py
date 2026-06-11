"""Tests for pgm_map_studio.symmetry.datatypes (center-cell typology helpers)."""

import pytest

from pgm_map_studio.symmetry.datatypes import (
    classify_center_cell,
    is_square_center_cell,
    CENTER_CELLS,
    SQUARE_CENTER_CELLS,
    SymmetryResult,
    rotation_degrees,
    team_orbit,
    is_lattice_exact,
    requires_square_cell,
    team_count_compatible,
    wool_count_compatible,
)


# ---------------------------------------------------------------------------
# classify_center_cell — one source of truth: the center coordinate's parity
# ---------------------------------------------------------------------------

def test_integer_center_is_2x2():
    # .0 on both axes -> boundary between columns -> 2-wide each
    assert classify_center_cell(0.0, 0.0) == '2x2'


def test_half_integer_center_is_1x1():
    # .5 on both axes -> through the middle of a column -> 1-wide each
    assert classify_center_cell(2.5, 2.5) == '1x1'


def test_mixed_center_x_even_z_odd_is_2x1():
    assert classify_center_cell(10.0, 2.5) == '2x1'


def test_mixed_center_x_odd_z_even_is_1x2():
    assert classify_center_cell(2.5, 10.0) == '1x2'


def test_negative_half_integer_is_1_wide():
    assert classify_center_cell(-2.5, -3.5) == '1x1'


def test_negative_integer_is_2_wide():
    assert classify_center_cell(-4.0, -8.0) == '2x2'


def test_all_classifications_are_valid_cells():
    for cx, cz in [(0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (0.5, 0.5)]:
        assert classify_center_cell(cx, cz) in CENTER_CELLS


# ---------------------------------------------------------------------------
# is_square_center_cell — rot_90 / diagonal-mirror compatibility
# ---------------------------------------------------------------------------

def test_square_cells_are_square():
    for cell in SQUARE_CENTER_CELLS:
        assert is_square_center_cell(cell) is True


def test_non_square_cells_are_not_square():
    for cell in ('1x2', '2x1'):
        assert is_square_center_cell(cell) is False


# ---------------------------------------------------------------------------
# SymmetryResult.center_cell property — derived from center, never stored twice
# ---------------------------------------------------------------------------

def test_result_center_cell_derived_from_center():
    r = SymmetryResult(status='unconfirmed', modes=[],
                       center={'cx': 2.5, 'cz': 2.5})
    assert r.center_cell == '1x1'


def test_result_center_cell_defaults_to_2x2():
    r = SymmetryResult(status='unconfirmed', modes=[], center={})
    assert r.center_cell == '2x2'


# ---------------------------------------------------------------------------
# Rotation order / general rot_n (B7 + B11)
# ---------------------------------------------------------------------------

def test_rotation_degrees_parsed():
    assert rotation_degrees('rot_90') == 90
    assert rotation_degrees('rot_120') == 120
    assert rotation_degrees('mirror_x') is None


def test_team_orbit_reflections_is_2():
    for m in ('mirror_x', 'mirror_z', 'mirror_d1', 'mirror_d2'):
        assert team_orbit(m) == 2


def test_team_orbit_rotations():
    assert team_orbit('rot_180') == 2   # 2-fold
    assert team_orbit('rot_90') == 4    # 4-fold
    assert team_orbit('rot_120') == 3   # 3-fold (tridente)
    assert team_orbit('rot_72') == 5    # 5-fold (pentawool)
    assert team_orbit('rot_60') == 6    # 6-fold (thunderbolt)


def test_lattice_exact_only_2_and_4_fold():
    for m in ('mirror_x', 'mirror_d2', 'rot_180', 'rot_90'):
        assert is_lattice_exact(m) is True
    for m in ('rot_120', 'rot_72', 'rot_60', 'rot_45'):
        assert is_lattice_exact(m) is False


def test_requires_square_cell_swaps_axes():
    for m in ('rot_90', 'mirror_d1', 'mirror_d2'):
        assert requires_square_cell(m) is True
    for m in ('mirror_x', 'mirror_z', 'rot_180', 'rot_120'):
        assert requires_square_cell(m) is False


def test_team_count_compatible_strict():
    assert team_count_compatible('rot_90', 4) is True
    assert team_count_compatible('rot_90', 8) is True
    assert team_count_compatible('rot_90', 2) is False   # rot_90 needs ≥4, %4
    assert team_count_compatible('rot_90', 6) is False
    assert team_count_compatible('mirror_x', 2) is True
    assert team_count_compatible('mirror_x', 3) is False  # reflection needs even
    assert team_count_compatible('rot_120', 3) is True    # pentawool-style n-fold
    assert team_count_compatible('rot_72', 5) is True


def test_wool_count_compatible_k_colors_per_team():
    assert wool_count_compatible(4, 4) is True   # 1 color/team
    assert wool_count_compatible(8, 4) is True   # 2 colors/team
    assert wool_count_compatible(2, 4) is False  # fewer wools than teams
    assert wool_count_compatible(5, 4) is False  # not a multiple
    assert wool_count_compatible(5, 5) is True   # pentawool
