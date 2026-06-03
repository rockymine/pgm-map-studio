"""Tests for apply rule parsing — all attributes, inline regions, serialization."""

import json
import textwrap
from pathlib import Path

import pytest

from pgm_map_studio.pgm.parser import MapXmlParser
from pgm_map_studio.pgm.datatypes import ApplyRule
from pgm_map_studio.pgm import serializer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_xml(tmp_path, content: str) -> str:
    p = tmp_path / "map.xml"
    p.write_text(textwrap.dedent(content))
    return str(p)


def _xml_with_applies(tmp_path, filters_xml: str, applies_xml: str) -> str:
    return _write_xml(tmp_path, f"""\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>Apply Test</name><version>1.0</version><objective>X</objective>
        <teams>
            <team id="red" color="dark red" max="8">Red</team>
            <team id="blue" color="blue" max="8">Blue</team>
        </teams>
        <filters>
        {filters_xml}
        </filters>
        <regions>
        {applies_xml}
        </regions>
        </map>
    """)


# ---------------------------------------------------------------------------
# enter attribute
# ---------------------------------------------------------------------------

def test_apply_enter_parsed(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<team id="only-blue">blue</team>',
        '<apply enter="only-blue" region="blue-spawn" message="No enemies!"/>',
    )
    data = MapXmlParser(path).parse()
    rule = data.apply_rules[0]
    assert rule.enter_filter == 'only-blue'
    assert rule.region_id == 'blue-spawn'
    assert rule.message == 'No enemies!'


def test_apply_enter_serialized(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<team id="only-blue">blue</team>',
        '<apply enter="only-blue" region="blue-spawn"/>',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    rule = d['apply_rules'][0]
    assert rule.get('enter') == 'only-blue'


def test_apply_enter_not_present_when_empty(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply block="deny-all" region="r"/>',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    rule = d['apply_rules'][0]
    assert 'enter' not in rule


# ---------------------------------------------------------------------------
# leave attribute
# ---------------------------------------------------------------------------

def test_apply_leave_parsed(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<never id="never"/>',
        '<apply leave="never" region="playspace" message="Cannot exit!"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].leave_filter == 'never'


# ---------------------------------------------------------------------------
# kit and lend-kit
# ---------------------------------------------------------------------------

def test_apply_kit_parsed(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply kit="reset-resistance-kit" region="not-spawns"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].kit == 'reset-resistance-kit'


def test_apply_kit_serialized(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply kit="reset-resistance-kit" region="not-spawns"/>',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    rule = d['apply_rules'][0]
    assert rule.get('kit') == 'reset-resistance-kit'


def test_apply_lend_kit_parsed(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply lend-kit="spectator" region="spectator-lanes"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].lend_kit == 'spectator'


def test_apply_lend_kit_serialized(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply lend-kit="spectator" region="spectator-lanes"/>',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    assert d['apply_rules'][0].get('lend_kit') == 'spectator'


# ---------------------------------------------------------------------------
# velocity
# ---------------------------------------------------------------------------

def test_apply_velocity_parsed(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply velocity="0.05,1.7,0" region="jump-pad"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].velocity == '0.05,1.7,0'


def test_apply_velocity_serialized(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply velocity="0.05,1.7,0" region="jump-pad"/>',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    assert d['apply_rules'][0].get('velocity') == '0.05,1.7,0'


# ---------------------------------------------------------------------------
# block-physics
# ---------------------------------------------------------------------------

def test_apply_block_physics_parsed(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<deny id="deny-physics"><any><material>redstone wire</material></any></deny>',
        '<apply block-physics="deny-physics" region="woolrooms"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].block_physics_filter == 'deny-physics'


def test_apply_block_physics_serialized(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<deny id="deny-physics"><any><material>flower pot</material></any></deny>',
        '<apply block-physics="deny-physics" region="r"/>',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    assert d['apply_rules'][0].get('block_physics') == 'deny-physics'


# ---------------------------------------------------------------------------
# filter attribute (condition for kit/velocity)
# ---------------------------------------------------------------------------

def test_apply_filter_attr_parsed(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<team id="only-red">red</team>',
        '<apply filter="only-red" kit="special-kit" region="special-zone"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].filter_id == 'only-red'


# ---------------------------------------------------------------------------
# block-place-against
# ---------------------------------------------------------------------------

def test_apply_block_place_against_parsed(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<never id="anti-climb-filter"/>',
        '<apply region="anti-climb-region" block-place-against="anti-climb-filter" message="No!"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].block_place_against_filter == 'anti-climb-filter'


# ---------------------------------------------------------------------------
# Inline shorthand filter values stored verbatim
# ---------------------------------------------------------------------------

def test_apply_shorthand_deny_void(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply block-place="deny(void)" message="No void edits!"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].block_place_filter == 'deny(void)'


def test_apply_shorthand_all_combiner(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply block-break="all(blue-team)" region="red-side"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].block_break_filter == 'all(blue-team)'


def test_apply_shorthand_serialized_verbatim(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '<apply enter="deny(blue-team)" region="blue-base"/>',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    assert d['apply_rules'][0]['enter'] == 'deny(blue-team)'


# ---------------------------------------------------------------------------
# Inline region child (apply without region= attribute)
# ---------------------------------------------------------------------------

def test_apply_inline_region_cuboid(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<never id="never"/>',
        '''\
        <apply block-break="never" block-place="never" message="No editing!">
            <region>
                <cuboid min="-52,17,-7" max="-45,26,-14"/>
            </region>
        </apply>
        ''',
    )
    data = MapXmlParser(path).parse()
    rule = data.apply_rules[0]
    assert rule.region_id != ''
    # The inline region should be in the regions registry
    assert rule.region_id in data.regions


def test_apply_inline_region_rectangle(tmp_path):
    path = _xml_with_applies(tmp_path, '',
        '''\
        <apply enter="only-blue" message="No!">
            <region><rectangle min="-10,-10" max="10,10"/></region>
        </apply>
        ''',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].region_id in data.regions


def test_apply_multiple_inline_regions_unique_ids(tmp_path):
    """Multiple apply elements with inline regions should get unique region IDs."""
    path = _xml_with_applies(tmp_path, '',
        '''\
        <apply block-break="never" message="No!">
            <region><cuboid min="0,0,0" max="5,5,5"/></region>
        </apply>
        <apply block-break="never" message="No!">
            <region><cuboid min="10,0,10" max="15,5,15"/></region>
        </apply>
        ''',
    )
    data = MapXmlParser(path).parse()
    r0 = data.apply_rules[0].region_id
    r1 = data.apply_rules[1].region_id
    assert r0 != r1
    assert r0 in data.regions
    assert r1 in data.regions


# ---------------------------------------------------------------------------
# All pre-existing apply attributes still work
# ---------------------------------------------------------------------------

def test_apply_block_still_works(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<deny id="deny-chest"><material>chest</material></deny>',
        '<apply block="deny-chest" region="wool-rooms" message="No chests!"/>',
    )
    data = MapXmlParser(path).parse()
    rule = data.apply_rules[0]
    assert rule.block_filter == 'deny-chest'
    assert rule.region_id == 'wool-rooms'
    assert rule.message == 'No chests!'


def test_apply_block_place_and_break(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<material id="only-iron">iron block</material>',
        '<apply block-place="only-iron" block-break="only-iron" region="spawns"/>',
    )
    data = MapXmlParser(path).parse()
    rule = data.apply_rules[0]
    assert rule.block_place_filter == 'only-iron'
    assert rule.block_break_filter == 'only-iron'


def test_apply_use_filter(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<team id="only-blue">blue</team>',
        '<apply use="only-blue" region="red-wool-rooms"/>',
    )
    data = MapXmlParser(path).parse()
    assert data.apply_rules[0].use_filter == 'only-blue'


# ---------------------------------------------------------------------------
# Serializer: omit empty fields
# ---------------------------------------------------------------------------

def test_serializer_omits_empty_apply_fields(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<team id="only-blue">blue</team>',
        '<apply enter="only-blue" region="blue-spawn"/>',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    rule = d['apply_rules'][0]
    # These should all be absent (empty string → omitted)
    for field in ('leave', 'block', 'block_place', 'block_break', 'block_physics',
                  'use', 'filter', 'kit', 'lend_kit', 'velocity'):
        assert field not in rule, f"Unexpected field: {field}"


# ---------------------------------------------------------------------------
# Serializer: top-level keys include filters
# ---------------------------------------------------------------------------

def test_serializer_has_filters_key(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<team id="only-blue">blue</team>',
        '',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    assert 'filters' in d
    assert isinstance(d['filters'], dict)


def test_filters_serialized_with_correct_structure(tmp_path):
    path = _xml_with_applies(tmp_path,
        '''\
        <team id="only-blue">blue</team>
        <all id="iron-world">
            <material id="only-iron">iron block</material>
            <cause>world</cause>
        </all>
        ''',
        '',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    filters = d['filters']
    assert 'only-blue' in filters
    assert filters['only-blue']['type'] == 'team'
    assert filters['only-blue']['team'] == 'blue'
    assert 'iron-world' in filters
    assert filters['iron-world']['type'] == 'all'
    assert 'children' in filters['iron-world']
    assert all(isinstance(c, str) for c in filters['iron-world']['children'])


def test_deny_filter_serialized(tmp_path):
    path = _xml_with_applies(tmp_path,
        '<deny id="deny-chest"><material>chest</material></deny>',
        '',
    )
    data = MapXmlParser(path).parse()
    d = serializer.to_dict(data)
    f = d['filters']['deny-chest']
    assert f['type'] == 'deny'
    assert 'child' in f
    assert isinstance(f['child'], str)


# ---------------------------------------------------------------------------
# Real map integration tests
# ---------------------------------------------------------------------------

TUMBLEWEED = Path('/media/sf_repos/CommunityMaps/ctw/tumbleweed/map.xml')
OUTBACK = Path('/media/sf_repos/CommunityMaps/ctw/outback_outback_edition/map.xml')
ANNEALING = Path('/media/sf_repos/CommunityMaps/ctw/annealing_iv/map.xml')


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_enter_filters():
    data = MapXmlParser(str(TUMBLEWEED)).parse()
    enter_rules = [r for r in data.apply_rules if r.enter_filter]
    assert len(enter_rules) >= 2, "Tumbleweed has enter filter rules"
    # Verify filters are registered
    for rule in enter_rules:
        if '(' not in rule.enter_filter:
            assert rule.enter_filter in data.filters, \
                f"enter filter '{rule.enter_filter}' not in filters registry"


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_filters_parsed():
    data = MapXmlParser(str(TUMBLEWEED)).parse()
    assert len(data.filters) > 0
    assert 'only-blue' in data.filters
    assert 'only-red' in data.filters
    assert 'only-iron-regen' in data.filters


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_block_physics_rule():
    data = MapXmlParser(str(TUMBLEWEED)).parse()
    # Tumbleweed doesn't have block-physics but other applies should still work
    assert len(data.apply_rules) >= 10


@pytest.mark.skipif(not OUTBACK.exists(), reason="Outback not available")
def test_outback_filters_fully_parsed():
    data = MapXmlParser(str(OUTBACK)).parse()
    # Outback has block-physics rule
    phys_rules = [r for r in data.apply_rules if r.block_physics_filter]
    assert len(phys_rules) >= 1

    # Kit rule
    kit_rules = [r for r in data.apply_rules if r.kit]
    assert len(kit_rules) >= 1
    assert kit_rules[0].kit == 'reset-resistance-kit'


@pytest.mark.skipif(not OUTBACK.exists(), reason="Outback not available")
def test_outback_filters_nested_ids():
    data = MapXmlParser(str(OUTBACK)).parse()
    # outback has nested filters with ids
    assert 'only-yellow' in data.filters
    assert 'only-purple' in data.filters
    assert 'only-iron' in data.filters
    assert 'only-air' in data.filters


@pytest.mark.skipif(not ANNEALING.exists(), reason="Annealing not available")
def test_annealing_all_enter_filters_captured():
    data = MapXmlParser(str(ANNEALING)).parse()
    enter_rules = [r for r in data.apply_rules if r.enter_filter]
    # Annealing has 8 enter rules (4 spawn protection + 4 wool room)
    assert len(enter_rules) == 8


@pytest.mark.skipif(not ANNEALING.exists(), reason="Annealing not available")
def test_annealing_json_valid(tmp_path):
    data = MapXmlParser(str(ANNEALING)).parse()
    d = serializer.to_dict(data)
    json_str = serializer.to_json(data)
    parsed = json.loads(json_str)
    # All apply rules with enter should have it
    for rule in parsed['apply_rules']:
        if 'enter' in rule:
            assert isinstance(rule['enter'], str)
    # All filter children should be strings
    for fid, f in parsed['filters'].items():
        if 'children' in f:
            for c in f['children']:
                assert isinstance(c, str), f"Non-string child in filter {fid}"
