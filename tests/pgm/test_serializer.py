"""Tests for pgm_map_studio.pgm.serializer."""

import json
import textwrap
from pathlib import Path

import pytest

from pgm_map_studio.pgm.parser import MapXmlParser
from pgm_map_studio.pgm import serializer
from pgm_map_studio.pgm.datatypes import (
    MapXml, Team, Author, Kit, KitItem, Spawn, Wool, Renewable, BlockDropRule,
    BlockDropItem, WoolSpawner, SpawnerItem, ApplyRule,
)
from pgm_map_studio.pgm.regions import Rectangle, Union, Cuboid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_xml(tmp_path: Path, content: str) -> str:
    p = tmp_path / "map.xml"
    p.write_text(textwrap.dedent(content))
    return str(p)


FULL_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Round Trip Map</name>
    <version>2.0.1</version>
    <objective>Capture!</objective>
    <authors>
        <author uuid="aaaaaaaa-0000-0000-0000-000000000001" contribution=""/>
    </authors>
    <teams>
        <team id="red" color="dark red" max="16">Red</team>
        <team id="blue" color="blue" max="16">Blue</team>
    </teams>
    <kits>
        <kit id="spawn-kit">
            <item slot="0" material="iron sword" unbreakable="true"/>
            <helmet material="leather helmet" team-color="true"/>
        </kit>
    </kits>
    <spawns>
        <default>
            <region><cuboid min="-1,5,-1" max="1,5,1"/></region>
        </default>
        <spawn team="red" kit="spawn-kit" yaw="90">
            <region><cuboid min="10,5,10" max="12,5,12"/></region>
        </spawn>
        <spawn team="blue" kit="spawn-kit" yaw="-90">
            <region><cuboid min="-10,5,-10" max="-12,5,-12"/></region>
        </spawn>
    </spawns>
    <wools>
        <wool team="red" color="cyan" location="5,10,5">
            <monument><block>15,10,15</block></monument>
        </wool>
        <wool team="blue" color="orange" location="-5,10,-5">
            <monument><block>-15,10,-15</block></monument>
        </wool>
    </wools>
    <spawners>
        <spawner spawn-region="red-wool" player-region="red-room" delay="1s">
            <item material="wool" damage="14"/>
        </spawner>
    </spawners>
    <renewables>
        <renewable region="spawn-area" rate="2.0" renew-filter="only-iron"/>
    </renewables>
    <block-drops>
        <rule filter="only-gold">
            <drops><item material="gold ingot" chance="0.75"/></drops>
        </rule>
    </block-drops>
    <regions>
        <rectangle id="red-spawn" min="-11,-121" max="11,-94"/>
        <union id="all-spawns">
            <rectangle id="blue-spawn-rect" min="-11,94" max="11,121"/>
        </union>
        <apply region="red-spawn" block-place="only-iron" message="No building!"/>
    </regions>
    <maxbuildheight>32</maxbuildheight>
    </map>
    """


# ---------------------------------------------------------------------------
# Top-level keys
# ---------------------------------------------------------------------------

def test_top_level_keys_present(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    for key in ('name', 'version', 'gamemode', 'objective', 'max_build_height',
                'authors', 'kits', 'teams', 'spawns', 'observer_spawn',
                'wools', 'spawners', 'renewables', 'block_drop_rules',
                'regions', 'apply_rules'):
        assert key in d, f"Missing key: {key}"


def test_region_categories_absent(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    assert 'region_categories' not in d


def test_json_is_valid(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    json_str = serializer.to_json(data)
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Field preservation in JSON
# ---------------------------------------------------------------------------

def test_name_preserved(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    assert d['name'] == 'Round Trip Map'


def test_max_build_height_preserved(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    assert d['max_build_height'] == 32


def test_teams_preserved(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    assert len(d['teams']) == 2


def test_observer_spawn_present(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    assert d['observer_spawn'] is not None


def test_observer_spawn_absent_is_null(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        </map>
        """
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    d = serializer.to_dict(data)
    assert d['observer_spawn'] is None


def test_empty_lists_serialized(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        </map>
        """
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    d = serializer.to_dict(data)
    assert d['kits'] == []
    assert d['spawners'] == []
    assert d['renewables'] == []
    assert d['apply_rules'] == []


# ---------------------------------------------------------------------------
# Rectangle serialization
# ---------------------------------------------------------------------------

def test_rectangle_has_no_raw_coords(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    rect = d['regions']['red-spawn']
    assert 'min_x' not in rect
    assert 'max_x' not in rect
    assert 'min_z' not in rect
    assert 'max_z' not in rect


def test_rectangle_has_bounds_2d(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    rect = d['regions']['red-spawn']
    assert 'bounds_2d' in rect
    b = rect['bounds_2d']
    assert 'min' in b and 'max' in b
    assert 'x' in b['min'] and 'z' in b['min']


# ---------------------------------------------------------------------------
# Composite region children are ID strings in JSON
# ---------------------------------------------------------------------------

def test_union_children_are_strings_in_json(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    d = serializer.to_dict(data)
    union = d['regions']['all-spawns']
    assert union['type'] == 'union'
    assert isinstance(union['children'], list)
    for child in union['children']:
        assert isinstance(child, str), f"Expected string child ID, got {type(child)}"


# ---------------------------------------------------------------------------
# Optional fields omitted at default
# ---------------------------------------------------------------------------

def test_renewable_rate_omitted_when_default(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <renewables>
            <renewable region="r"/>
        </renewables>
        </map>
        """
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    d = serializer.to_dict(data)
    assert 'rate' not in d['renewables'][0]


def test_renewable_grow_omitted_when_false():
    r = Renewable(region_id='x', grow=False)
    d = MapXml(renewables=[r])
    result = serializer.to_dict(d)
    assert 'grow' not in result['renewables'][0]


def test_block_drop_item_damage_omitted_when_zero():
    item = BlockDropItem(material='iron', damage=0, amount=2, chance=0.5)
    rule = BlockDropRule(items=[item])
    d = MapXml(block_drop_rules=[rule])
    result = serializer.to_dict(d)
    item_d = result['block_drop_rules'][0]['items'][0]
    assert 'damage' not in item_d


def test_block_drop_item_amount_omitted_when_one():
    item = BlockDropItem(material='iron', damage=0, amount=1, chance=0.5)
    rule = BlockDropRule(items=[item])
    d = MapXml(block_drop_rules=[rule])
    result = serializer.to_dict(d)
    item_d = result['block_drop_rules'][0]['items'][0]
    assert 'amount' not in item_d


def test_block_drop_item_chance_omitted_when_one():
    item = BlockDropItem(material='iron', damage=0, amount=1, chance=1.0)
    rule = BlockDropRule(items=[item])
    d = MapXml(block_drop_rules=[rule])
    result = serializer.to_dict(d)
    item_d = result['block_drop_rules'][0]['items'][0]
    assert 'chance' not in item_d


def test_kit_item_amount_omitted_when_one():
    item = KitItem(slot=0, material='sword', amount=1)
    kit = Kit(id='k', items=[item])
    d = MapXml(kits=[kit])
    result = serializer.to_dict(d)
    item_d = result['kits'][0]['items'][0]
    assert 'amount' not in item_d


# ---------------------------------------------------------------------------
# Save to file
# ---------------------------------------------------------------------------

def test_save_creates_file(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    out = tmp_path / "xml_data.json"
    serializer.save(data, out)
    assert out.exists()
    parsed = json.loads(out.read_text())
    assert parsed['name'] == 'Round Trip Map'


# ---------------------------------------------------------------------------
# Real map round-trip
# ---------------------------------------------------------------------------

TUMBLEWEED_PATH = Path('/media/sf_repos/CommunityMaps/ctw/tumbleweed/map.xml')


@pytest.mark.skipif(not TUMBLEWEED_PATH.exists(), reason="Tumbleweed map not available")
def test_tumbleweed_round_trip(tmp_path):
    data = MapXmlParser(str(TUMBLEWEED_PATH)).parse()
    d = serializer.to_dict(data)
    # Verify no region_categories key
    assert 'region_categories' not in d
    # All children in all unions/composites are strings
    for rid, region in d['regions'].items():
        if 'children' in region:
            for child in region['children']:
                assert isinstance(child, str), f"Non-string child in {rid}"
    # No raw rectangle coords
    for rid, region in d['regions'].items():
        if region['type'] == 'rectangle':
            assert 'min_x' not in region
            assert 'max_x' not in region
