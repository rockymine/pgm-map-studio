"""Tests for pgm_map_studio.symmetry.datatypes (center-cell typology helpers)."""

import pytest

from pgm_map_studio.symmetry.datatypes import (
    classify_center_cell,
    is_square_center_cell,
    CENTER_CELLS,
    SQUARE_CENTER_CELLS,
    SymmetryResult,
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
                       center={'center_x': 2.5, 'center_z': 2.5})
    assert r.center_cell == '1x1'


def test_result_center_cell_defaults_to_2x2():
    r = SymmetryResult(status='unconfirmed', modes=[], center={})
    assert r.center_cell == '2x2'
