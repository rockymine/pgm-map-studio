"""Tests for pgm_map_studio.pgm.regions."""

import math
import pytest

from pgm_map_studio.pgm.regions import (
    parse_coord, Rectangle, Cuboid, Cylinder, Circle, Sphere,
    Block, Point, Union, _b2d,
)


# ---------------------------------------------------------------------------
# parse_coord
# ---------------------------------------------------------------------------

def test_parse_coord_normal_float():
    assert parse_coord("3.5") == 3.5


def test_parse_coord_negative():
    assert parse_coord("-45.5") == -45.5


def test_parse_coord_integer():
    assert parse_coord("10") == 10.0


def test_parse_coord_infinity():
    assert parse_coord("oo") == math.inf


def test_parse_coord_neg_infinity():
    assert parse_coord("-oo") == -math.inf


def test_parse_coord_infinity_uppercase():
    assert parse_coord("OO") == math.inf


def test_parse_coord_template_variable_dollar_brace():
    assert parse_coord("${some_var}") is None


def test_parse_coord_template_variable_plain_dollar():
    assert parse_coord("$var") is None


def test_parse_coord_whitespace_stripped():
    assert parse_coord("  5.0  ") == 5.0


def test_parse_coord_malformed_zeroed_with_warning(caplog):
    # A8: a source typo like '5.185.5' (two decimal points) must not raise; it is
    # zeroed with a warning so one bad value doesn't fail the whole map parse.
    import logging
    with caplog.at_level(logging.WARNING, logger="pgm_map_studio"):
        assert parse_coord("5.185.5") == 0.0
    assert any("Malformed coordinate" in r.message for r in caplog.records)


def test_malformed_coord_keeps_region_buildable():
    r = Rectangle(id="r", min_x=101.0, min_z=parse_coord("5.185.5"),
                  max_x=156.5, max_z=185.5)
    assert r.bounds_2d is not None and r.min_z == 0.0


# ---------------------------------------------------------------------------
# bounds_2d normalization
# ---------------------------------------------------------------------------

def test_rectangle_normalized_bounds_normal():
    r = Rectangle(min_x=-11.0, min_z=-121.0, max_x=11.0, max_z=-94.0)
    assert r.bounds_2d == {'min': {'x': -11.0, 'z': -121.0}, 'max': {'x': 11.0, 'z': -94.0}}


def test_rectangle_normalized_bounds_swapped():
    # PGM convention: max < min is valid XML, bounds_2d always min < max
    r = Rectangle(min_x=20.0, min_z=20.0, max_x=0.0, max_z=0.0)
    assert r.bounds_2d['min']['x'] == 0.0
    assert r.bounds_2d['min']['z'] == 0.0
    assert r.bounds_2d['max']['x'] == 20.0
    assert r.bounds_2d['max']['z'] == 20.0


def test_rectangle_none_coordinate_gives_no_bounds():
    r = Rectangle(min_x=None, min_z=0.0, max_x=10.0, max_z=10.0)
    assert r.bounds_2d is None


def test_cuboid_bounds_2d():
    c = Cuboid(min_x=0.0, min_y=0.0, min_z=5.0, max_x=10.0, max_y=10.0, max_z=15.0)
    assert c.bounds_2d == {'min': {'x': 0.0, 'z': 5.0}, 'max': {'x': 10.0, 'z': 15.0}}


def test_cylinder_bounds_2d():
    cyl = Cylinder(base_x=10.0, base_y=0.0, base_z=20.0, radius=5.0)
    b = cyl.bounds_2d
    assert b['min']['x'] == 5.0
    assert b['min']['z'] == 15.0
    assert b['max']['x'] == 15.0
    assert b['max']['z'] == 25.0


def test_circle_bounds_2d():
    c = Circle(center_x=0.0, center_z=0.0, radius=3.0)
    b = c.bounds_2d
    assert b['min']['x'] == -3.0
    assert b['min']['z'] == -3.0
    assert b['max']['x'] == 3.0
    assert b['max']['z'] == 3.0


def test_sphere_bounds_2d():
    s = Sphere(origin_x=5.0, origin_y=0.0, origin_z=-5.0, radius=10.0)
    b = s.bounds_2d
    assert b['min']['x'] == -5.0
    assert b['min']['z'] == -15.0
    assert b['max']['x'] == 15.0
    assert b['max']['z'] == 5.0


def test_block_bounds_expands_by_one():
    b = Block(x=5.0, y=0.0, z=7.0)
    assert b.bounds_2d == {'min': {'x': 5.0, 'z': 7.0}, 'max': {'x': 6.0, 'z': 8.0}}


def test_point_bounds_half_unit_square():
    p = Point(x=10.0, y=0.0, z=10.0)
    b = p.bounds_2d
    assert b['min']['x'] == pytest.approx(9.5)
    assert b['min']['z'] == pytest.approx(9.5)
    assert b['max']['x'] == pytest.approx(10.5)
    assert b['max']['z'] == pytest.approx(10.5)


# ---------------------------------------------------------------------------
# Composite regions have no auto-computed bounds_2d
# ---------------------------------------------------------------------------

def test_union_no_auto_bounds():
    u = Union(children=['a', 'b'])
    assert u.bounds_2d is None


# ---------------------------------------------------------------------------
# _b2d helper
# ---------------------------------------------------------------------------

def test_b2d_already_normalized():
    b = _b2d(1.0, 2.0, 3.0, 4.0)
    assert b == {'min': {'x': 1.0, 'z': 2.0}, 'max': {'x': 3.0, 'z': 4.0}}


def test_b2d_swapped():
    b = _b2d(5.0, 8.0, 2.0, 3.0)
    assert b['min']['x'] == 2.0
    assert b['max']['x'] == 5.0
    assert b['min']['z'] == 3.0
    assert b['max']['z'] == 8.0
