"""Tests for pgm_map_studio.pgm.region_parser."""

import xml.etree.ElementTree as ET
import pytest

from pgm_map_studio.pgm.region_parser import RegionParser
from pgm_map_studio.pgm.regions import (
    Rectangle, Cuboid, Cylinder, Circle, Sphere, Block, Point,
    Union, Negative, Complement, Intersect, Mirror, Translate,
    Half, Everywhere, Above, Reference,
)


def _parse(xml_str: str) -> tuple[dict, list]:
    """Parse a <regions> element and return (registry, apply_rules)."""
    root = ET.fromstring(f"<regions>{xml_str}</regions>")
    return RegionParser().parse_regions_elem(root)


# ---------------------------------------------------------------------------
# Primitive regions
# ---------------------------------------------------------------------------

def test_rectangle_parsed():
    reg, _ = _parse('<rectangle id="r" min="-11,-121" max="11,-94"/>')
    assert 'r' in reg
    assert isinstance(reg['r'], Rectangle)
    b = reg['r'].bounds_2d
    assert b['min']['x'] == -11.0
    assert b['min']['z'] == -121.0
    assert b['max']['x'] == 11.0
    assert b['max']['z'] == -94.0


def test_rectangle_normalized_bounds_swapped_coords():
    reg, _ = _parse('<rectangle id="r" min="20,20" max="0,0"/>')
    b = reg['r'].bounds_2d
    assert b['min']['x'] == 0.0
    assert b['max']['x'] == 20.0


def test_cuboid_parsed():
    reg, _ = _parse('<cuboid id="c" min="-10,5,10" max="-12,5,12"/>')
    c = reg['c']
    assert isinstance(c, Cuboid)
    assert c.bounds_2d is not None


def test_cylinder_parsed():
    reg, _ = _parse('<cylinder id="c" base="0,5,0" radius="3" height="2"/>')
    c = reg['c']
    assert isinstance(c, Cylinder)
    assert c.base_x == 0.0
    assert c.radius == 3.0
    assert c.height == 2.0
    assert c.bounds_2d['min']['x'] == pytest.approx(-3.0)


def test_circle_parsed():
    reg, _ = _parse('<circle id="c" center="10,20" radius="5"/>')
    c = reg['c']
    assert isinstance(c, Circle)
    assert c.center_x == 10.0
    assert c.radius == 5.0


def test_sphere_parsed():
    reg, _ = _parse('<sphere id="s" origin="1,2,3" radius="7"/>')
    s = reg['s']
    assert isinstance(s, Sphere)
    assert s.origin_x == 1.0
    assert s.radius == 7.0


def test_block_parsed_with_position():
    reg, _ = _parse('<block id="b">5,10,15</block>')
    b = reg['b']
    assert isinstance(b, Block)
    assert b.x == 5.0
    assert b.z == 15.0
    # Block at (5,15) occupies [5,6]×[15,16]
    assert b.bounds_2d['min']['x'] == 5.0
    assert b.bounds_2d['max']['x'] == 6.0


def test_point_parsed():
    reg, _ = _parse('<point id="p">10,5,20</point>')
    p = reg['p']
    assert isinstance(p, Point)
    assert p.x == 10.0
    assert p.z == 20.0


# ---------------------------------------------------------------------------
# Composite regions — children are ID strings
# ---------------------------------------------------------------------------

def test_union_children_are_strings():
    reg, _ = _parse('''
        <union id="u">
            <rectangle id="a" min="0,0" max="10,10"/>
            <rectangle id="b" min="20,20" max="30,30"/>
        </union>
    ''')
    u = reg['u']
    assert isinstance(u, Union)
    assert u.children == ['a', 'b']


def test_negative_children_are_strings():
    reg, _ = _parse('''
        <negative id="n">
            <rectangle id="base" min="0,0" max="100,100"/>
        </negative>
    ''')
    assert isinstance(reg['n'], Negative)
    assert reg['n'].children == ['base']


def test_complement_children_are_strings():
    reg, _ = _parse('''
        <complement id="c">
            <rectangle id="first" min="0,0" max="50,50"/>
            <rectangle id="second" min="10,10" max="20,20"/>
        </complement>
    ''')
    assert isinstance(reg['c'], Complement)
    assert 'first' in reg['c'].children
    assert 'second' in reg['c'].children


def test_intersect_children_are_strings():
    reg, _ = _parse('''
        <intersect id="i">
            <rectangle id="a" min="0,0" max="50,50"/>
            <rectangle id="b" min="25,25" max="75,75"/>
        </intersect>
    ''')
    assert isinstance(reg['i'], Intersect)
    assert reg['i'].children == ['a', 'b']


# ---------------------------------------------------------------------------
# Flat registry — children registered individually
# ---------------------------------------------------------------------------

def test_composite_children_in_registry():
    reg, _ = _parse('''
        <union id="u">
            <rectangle id="a" min="0,0" max="10,10"/>
            <rectangle id="b" min="20,20" max="30,30"/>
        </union>
    ''')
    assert 'a' in reg
    assert 'b' in reg
    assert 'u' in reg


def test_child_registered_once():
    reg, _ = _parse('''
        <union id="parent">
            <rectangle id="child" min="0,0" max="10,10"/>
        </union>
    ''')
    # child appears in parent's children list and in registry — exactly once
    parent = reg['parent']
    assert parent.children.count('child') == 1
    assert list(reg.keys()).count('child') == 1


# ---------------------------------------------------------------------------
# Synthetic IDs for anonymous regions
# ---------------------------------------------------------------------------

def test_anonymous_child_gets_synthetic_id():
    reg, _ = _parse('''
        <union id="u">
            <rectangle min="0,0" max="10,10"/>
        </union>
    ''')
    u = reg['u']
    assert len(u.children) == 1
    anon_id = u.children[0]
    assert anon_id.startswith('u__anon_')
    assert anon_id in reg


def test_synthetic_id_no_inline_marker():
    reg, _ = _parse('''
        <union id="parent">
            <rectangle min="0,0" max="5,5"/>
        </union>
    ''')
    for rid in reg:
        assert '(inline)' not in rid


def test_synthetic_id_stability():
    xml = '''
        <union id="spawns">
            <rectangle min="-11,-121" max="11,-94"/>
            <rectangle min="-11,94" max="11,121"/>
        </union>
    '''
    reg1, _ = _parse(xml)
    reg2, _ = _parse(xml)
    assert list(reg1.keys()) == list(reg2.keys())
    assert reg1['spawns'].children == reg2['spawns'].children


def test_synthetic_id_uniqueness():
    reg, _ = _parse('''
        <union id="outer">
            <union id="inner">
                <rectangle min="0,0" max="5,5"/>
                <rectangle min="10,10" max="15,15"/>
            </union>
            <rectangle min="20,20" max="25,25"/>
        </union>
    ''')
    ids = list(reg.keys())
    assert len(ids) == len(set(ids))


def test_deep_nesting_stable_ids():
    reg, _ = _parse('''
        <union id="level1">
            <union id="level2">
                <complement id="level3">
                    <rectangle min="0,0" max="10,10"/>
                </complement>
            </union>
        </union>
    ''')
    ids = list(reg.keys())
    assert len(ids) == len(set(ids))
    assert 'level1' in reg
    assert 'level2' in reg
    assert 'level3' in reg


# ---------------------------------------------------------------------------
# bounds_2d of composite regions
# ---------------------------------------------------------------------------

def test_union_bounds_is_superset():
    reg, _ = _parse('''
        <union id="u">
            <rectangle id="a" min="0,0" max="10,10"/>
            <rectangle id="b" min="20,20" max="30,30"/>
        </union>
    ''')
    b = reg['u'].bounds_2d
    assert b['min']['x'] == 0.0
    assert b['min']['z'] == 0.0
    assert b['max']['x'] == 30.0
    assert b['max']['z'] == 30.0


# ---------------------------------------------------------------------------
# Named regions referenced by children
# ---------------------------------------------------------------------------

def test_named_region_referenced_by_parent():
    reg, _ = _parse('''
        <rectangle id="named" min="0,0" max="10,10"/>
        <union id="u">
            <region id="named"/>
        </union>
    ''')
    assert reg['u'].children == ['named']
    assert 'named' in reg


# ---------------------------------------------------------------------------
# Transform regions
# ---------------------------------------------------------------------------

def test_mirror_attribute_form():
    reg, _ = _parse('''
        <rectangle id="src" min="10,20" max="30,40"/>
        <mirror id="m" region="src" origin="0,0,0" normal="1,0,0"/>
    ''')
    assert isinstance(reg['m'], Mirror)
    assert reg['m'].source_id == 'src'
    assert reg['m'].normal_x == 1.0


def test_mirror_child_form():
    reg, _ = _parse('''
        <mirror id="m" origin="0,0,0" normal="0,0,1">
            <rectangle min="10,20" max="30,40"/>
        </mirror>
    ''')
    m = reg['m']
    assert isinstance(m, Mirror)
    assert m.source_id != ''


def test_translate_attribute_form():
    reg, _ = _parse('''
        <rectangle id="base" min="0,0" max="10,10"/>
        <translate id="t" region="base" offset="5,0,10"/>
    ''')
    t = reg['t']
    assert isinstance(t, Translate)
    assert t.source_id == 'base'
    assert t.offset_x == 5.0
    assert t.offset_z == 10.0


def test_translate_bounds_shifted():
    reg, _ = _parse('''
        <rectangle id="base" min="0,0" max="10,10"/>
        <translate id="t" region="base" offset="5,0,10"/>
    ''')
    b = reg['t'].bounds_2d
    assert b['min']['x'] == pytest.approx(5.0)
    assert b['min']['z'] == pytest.approx(10.0)
    assert b['max']['x'] == pytest.approx(15.0)
    assert b['max']['z'] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Special region types
# ---------------------------------------------------------------------------

def test_everywhere_parsed():
    reg, _ = _parse('<everywhere id="e"/>')
    assert isinstance(reg['e'], Everywhere)


def test_above_parsed():
    reg, _ = _parse('<above id="a" y="30"/>')
    assert isinstance(reg['a'], Above)
    assert reg['a'].y == 30.0


def test_half_parsed():
    reg, _ = _parse('<half id="h" origin="0,0,0" normal="0,1,0"/>')
    assert isinstance(reg['h'], Half)
    assert reg['h'].normal_y == 1.0


# ---------------------------------------------------------------------------
# Apply rules
# ---------------------------------------------------------------------------

def test_apply_rule_parsed():
    reg, rules = _parse('''
        <apply region="spawns" block-place="only-iron" message="No building here!"/>
    ''')
    assert len(rules) == 1
    assert rules[0].region_id == 'spawns'
    assert rules[0].block_place_filter == 'only-iron'
    assert rules[0].message == 'No building here!'


def test_apply_rule_block_filter():
    reg, rules = _parse('<apply region="r" block="deny-all"/>')
    assert rules[0].block_filter == 'deny-all'


def test_apply_rule_block_break():
    reg, rules = _parse('<apply region="r" block-break="only-iron"/>')
    assert rules[0].block_break_filter == 'only-iron'
