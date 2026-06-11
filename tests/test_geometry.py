"""Tests for pgm_map_studio.geometry (reflection + rotation converters)."""
import math

from pgm_map_studio.geometry import (
    reflect_point_2d,
    reflect_bounds_2d,
    rotate_point_2d,
    rotate_bounds_2d,
)


# ── reflection (moved from test_regions.py) ─────────────────────────────────────

def test_reflect_point_axis_aligned_x():
    # normal (1,0) reflects across the vertical line x = ox
    assert reflect_point_2d(0, 5, 1, 0, 10, 0) == (20, 5)


def test_reflect_point_axis_aligned_z():
    assert reflect_point_2d(5, 0, 0, 1, 0, 10) == (5, 20)


def test_reflect_point_diagonal_swaps_axes():
    # normal (-1,-1) about (261,284): the vertex case — reflection swaps x/z
    x, z = reflect_point_2d(263, 340, -1, -1, 261, 284)
    assert (round(x), round(z)) == (205, 282)


def test_reflect_point_zero_normal_unchanged():
    assert reflect_point_2d(3, 4, 0, 0, 1, 1) == (3, 4)


def test_reflect_bounds_diagonal():
    b = {"min": {"x": 263, "z": 340}, "max": {"x": 273, "z": 348}}
    out = reflect_bounds_2d(b, -1, -1, 261, 284)
    assert out == {"min": {"x": 197, "z": 272}, "max": {"x": 205, "z": 282}}


# ── rotation (CCW per geometry.md §2) ───────────────────────────────────────────

def test_rotate_90_ccw_about_origin():
    # (Δx,Δz)=(1,0) → (−Δz,Δx)=(0,1)
    assert rotate_point_2d(1, 0, 90, 0, 0) == (0, 1)
    # (0,1) → (-1,0)
    assert rotate_point_2d(0, 1, 90, 0, 0) == (-1, 0)


def test_rotate_180():
    assert rotate_point_2d(10, 20, 180, 0, 0) == (-10, -20)
    assert rotate_point_2d(10, 20, 180, 5, 10) == (0, 0)


def test_rotate_270_is_inverse_of_90():
    assert rotate_point_2d(1, 0, 270, 0, 0) == (0, -1)


def test_rotate_about_offset_center():
    # 90° CCW about (5,5): (10,5) → (5,10)
    assert rotate_point_2d(10, 5, 90, 5, 5) == (5, 10)


def test_rotate_90_multiples_are_exact_no_float_drift():
    # exact integer arithmetic for 90° multiples (no cos/sin epsilon)
    assert rotate_point_2d(7, 3, 90, 0, 0) == (-3, 7)
    assert rotate_point_2d(7, 3, 360, 0, 0) == (7, 3)


def test_rotate_general_angle_uses_trig():
    x, z = rotate_point_2d(1, 0, 120, 0, 0)  # 3-fold; approximate
    assert math.isclose(x, math.cos(math.radians(120)))
    assert math.isclose(z, math.sin(math.radians(120)))


def test_rotate_bounds_90_stays_axis_aligned():
    b = {"min": {"x": 0, "z": 0}, "max": {"x": 4, "z": 2}}
    out = rotate_bounds_2d(b, 90, 0, 0)
    # corners (0,0),(4,0),(0,2),(4,2) rotate CCW → x in [-2,0], z in [0,4]
    assert out == {"min": {"x": -2, "z": 0}, "max": {"x": 0, "z": 4}}


def test_rotate_bounds_180_round_trips():
    b = {"min": {"x": 1, "z": 2}, "max": {"x": 5, "z": 8}}
    once = rotate_bounds_2d(b, 180, 0, 0)
    twice = rotate_bounds_2d(once, 180, 0, 0)
    assert twice == b
