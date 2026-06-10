"""Tests for pgm_map_studio.pgm.deserializer — xml_data.json → MapXml.

Three tiers of coverage:
  1. Unit tests: from_dict with hand-crafted snippets reconstructs the right fields.
  2. Roundtrip (dict path): xml → MapXml → to_dict → from_dict preserves fields.
  3. Full roundtrip (export path): xml → to_dict → from_dict → to_xml → parse,
     the critical path for map.xml export from the editor.
"""

import json
import os
import tempfile
import textwrap
from pathlib import Path

import pytest

from pgm_map_studio.pgm.parser import MapXmlParser
from pgm_map_studio.pgm import serializer, deserializer
from pgm_map_studio.pgm.xml_writer import to_xml
from pgm_map_studio.pgm.datatypes import MapXml
from pgm_map_studio.pgm.regions import (
    Rectangle, Cuboid, Cylinder, Circle, Sphere, Block, Point,
    Union, Negative, Complement, Intersect, Mirror, Translate,
    Half, Reference, Everywhere, Above,
)
from pgm_map_studio.pgm.filters import (
    AllFilter, AnyFilter, OneFilter, NotFilter, DenyFilter, AllowFilter,
    TeamFilter, MaterialFilter, VoidFilter, CauseFilter, BlocksFilter,
    CarryingFilter, WearingFilter, HoldingFilter,
    AliveFilter, DeadFilter, ParticipatingFilter, ObservingFilter,
    MatchRunningFilter, MatchStartedFilter, GroundedFilter,
    NeverFilter, AlwaysFilter,
    TimeFilter, AfterFilter, PulseFilter, OffsetFilter, VariableFilter,
    CompletedFilter, ObjectiveFilter, KillStreakFilter, ClassFilter,
    RegionFilter, PlayerFilter, SpawnFilter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_xml(tmp_path: Path, content: str) -> str:
    p = tmp_path / "map.xml"
    p.write_text(textwrap.dedent(content))
    return str(p)


def _json_roundtrip(path: str) -> tuple[MapXml, MapXml]:
    """xml → MapXml → to_dict → from_dict. Returns (orig, restored)."""
    orig = MapXmlParser(path).parse()
    d = serializer.to_dict(orig)
    return orig, deserializer.from_dict(d)


def _full_roundtrip(path: str) -> tuple[MapXml, MapXml]:
    """xml → to_dict → from_dict → to_xml → parse. Returns (orig, re-parsed)."""
    orig = MapXmlParser(path).parse()
    restored = deserializer.from_dict(serializer.to_dict(orig))
    xml_str = to_xml(restored)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_str)
        tmp = f.name
    try:
        return orig, MapXmlParser(tmp).parse()
    finally:
        os.unlink(tmp)


MINIMAL = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Test Map</name>
    <version>1.0.0</version>
    <objective>Capture!</objective>
    <teams>
        <team id="red" color="dark red" max="16">Red</team>
        <team id="blue" color="blue" max="16">Blue</team>
    </teams>
    </map>
    """


# ---------------------------------------------------------------------------
# API: from_json, load
# ---------------------------------------------------------------------------

def test_from_json_returns_mapxml(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    d = serializer.to_dict(MapXmlParser(path).parse())
    result = deserializer.from_json(json.dumps(d))
    assert isinstance(result, MapXml)
    assert result.name == "Test Map"


def test_load_from_file(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    d = serializer.to_dict(MapXmlParser(path).parse())
    json_path = tmp_path / "xml_data.json"
    json_path.write_text(json.dumps(d))
    result = deserializer.load(json_path)
    assert result.name == "Test Map"


# ---------------------------------------------------------------------------
# Scalar fields
# ---------------------------------------------------------------------------

def test_name(tmp_path):
    orig, restored = _json_roundtrip(_write_xml(tmp_path, MINIMAL))
    assert restored.name == orig.name


def test_version(tmp_path):
    orig, restored = _json_roundtrip(_write_xml(tmp_path, MINIMAL))
    assert restored.version == orig.version


def test_objective(tmp_path):
    orig, restored = _json_roundtrip(_write_xml(tmp_path, MINIMAL))
    assert restored.objective == orig.objective


def test_gamemode_default():
    result = deserializer.from_dict({'name': 'x', 'version': '1.0.0', 'objective': 'y'})
    assert result.gamemode == 'ctw'


def test_gamemode_explicit():
    result = deserializer.from_dict({'gamemode': 'dtc'})
    assert result.gamemode == 'dtc'


def test_max_build_height_present(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <maxbuildheight>48</maxbuildheight>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    assert restored.max_build_height == 48


def test_max_build_height_absent():
    result = deserializer.from_dict({})
    assert result.max_build_height is None


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------

def test_authors_count(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <authors>
            <author uuid="aaaaaaaa-0000-0000-0000-000000000001"/>
            <author uuid="bbbbbbbb-0000-0000-0000-000000000002"/>
        </authors>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    assert len(restored.authors) == 2


def test_author_fields(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <contributors>
            <contributor uuid="cccccccc-0000-0000-0000-000000000003" contribution="terrain"/>
        </contributors>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    a = restored.authors[0]
    assert a.uuid == "cccccccc-0000-0000-0000-000000000003"
    assert a.role == "contributor"
    assert a.contribution == "terrain"


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

def test_teams_count(tmp_path):
    orig, restored = _json_roundtrip(_write_xml(tmp_path, MINIMAL))
    assert len(restored.teams) == 2


def test_team_fields(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <teams>
            <team id="red" color="dark red" dye-color="RED" max="12" min="2">Red Team</team>
        </teams>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    t = restored.teams[0]
    assert t.id == "red"
    assert t.color == "dark red"
    assert t.dye_color == "RED"
    assert t.max_players == 12
    assert t.min_players == 2
    assert t.name == "Red Team"


# ---------------------------------------------------------------------------
# Kits
# ---------------------------------------------------------------------------

def test_kit_fields(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <kits>
            <kit id="spawn-kit">
                <item slot="0" material="iron sword" amount="1" unbreakable="true" team-color="true">
                    <enchantment level="2">sharpness</enchantment>
                </item>
                <helmet material="leather helmet" team-color="true"/>
            </kit>
        </kits>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    k = restored.kits[0]
    assert k.id == "spawn-kit"
    item = k.items[0]
    assert item.slot == 0
    assert item.material == "iron sword"
    assert item.unbreakable is True
    assert item.team_color is True
    assert "sharpness" in item.enchantments
    armor = k.armor[0]
    assert armor.slot_name == "helmet"
    assert armor.team_color is True


# ---------------------------------------------------------------------------
# Spawns
# ---------------------------------------------------------------------------

def test_spawns_count(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <spawns>
            <default><region><cuboid min="-1,5,-1" max="1,5,1"/></region></default>
            <spawn team="red" yaw="90">
                <region><cuboid min="10,5,10" max="12,5,12"/></region>
            </spawn>
        </spawns>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    assert len(restored.spawns) == 1
    assert restored.observer_spawn is not None


def test_spawn_team_kit_yaw(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <kits><kit id="k"><item slot="0" material="stone"/></kit></kits>
        <spawns>
            <spawn team="red" kit="k" yaw="90">
                <region><cuboid min="10,5,10" max="12,5,12"/></region>
            </spawn>
        </spawns>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    s = restored.spawns[0]
    assert s.team == "red"
    assert s.kit == "k"
    assert s.yaw == 90.0


def test_spawn_region_reconstructed(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <spawns>
            <spawn team="red" yaw="0">
                <region><cuboid min="10,5,10" max="12,5,12"/></region>
            </spawn>
        </spawns>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    assert restored.spawns[0].region is not None
    assert isinstance(restored.spawns[0].region, Cuboid)


# ---------------------------------------------------------------------------
# Wools
# ---------------------------------------------------------------------------

def test_wool_fields(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <wools>
            <wool team="red" color="cyan" location="5,10,5">
                <monument><block>15,10,15</block></monument>
            </wool>
        </wools>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    w = restored.wools[0]
    assert w.team == "red"
    assert w.color == "cyan"
    assert w.location == (5.0, 10.0, 5.0)
    assert w.monument == (15.0, 10.0, 15.0)


def test_wool_monument_region_id(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <regions>
            <block id="red-mon">15,10,15</block>
        </regions>
        <wools>
            <wool team="red" color="cyan" location="5,10,5" monument="red-mon"/>
        </wools>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    assert restored.wools[0].monument_region_id == "red-mon"


# ---------------------------------------------------------------------------
# Spawners, renewables, block-drop rules
# ---------------------------------------------------------------------------

def test_spawner_fields(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <spawners>
            <spawner spawn-region="sr" player-region="pr" delay="2s" max-entities="3">
                <item material="wool" damage="11" amount="2"/>
            </spawner>
        </spawners>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    s = restored.spawners[0]
    assert s.spawn_region == "sr"
    assert s.player_region == "pr"
    assert s.delay == "2s"
    assert s.max_entities == 3
    assert s.items[0].material == "wool"
    assert s.items[0].damage == 11
    assert s.items[0].amount == 2


def test_renewable_fields(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <renewables>
            <renewable region="build" rate="3.0" renew-filter="rf" replace-filter="rp" grow="true"/>
        </renewables>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    r = restored.renewables[0]
    assert r.region_id == "build"
    assert r.rate == 3.0
    assert r.renew_filter == "rf"
    assert r.replace_filter == "rp"
    assert r.grow is True


def test_block_drop_rule_fields(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <block-drops>
            <rule region="build" filter="only-gold" wrong-tool="true">
                <replacement>air</replacement>
                <drops>
                    <item material="gold ingot" damage="0" amount="2" chance="0.5"/>
                </drops>
            </rule>
        </block-drops>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    r = restored.block_drop_rules[0]
    assert r.region_id == "build"
    assert r.filter_id == "only-gold"
    assert r.wrong_tool is True
    assert r.replacement == "air"
    item = r.items[0]
    assert item.material == "gold ingot"
    assert item.amount == 2
    assert item.chance == 0.5


# ---------------------------------------------------------------------------
# Apply rules
# ---------------------------------------------------------------------------

def test_apply_rule_fields(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <filters>
            <team id="only-red">red</team>
        </filters>
        <regions>
            <cuboid id="rz" min="0,60,0" max="10,70,10"/>
            <apply region="rz" enter="only-red" block-place="only-red"
                   block-break="only-red" kit="k" message="Red only"/>
        </regions>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    rule = restored.apply_rules[0]
    assert rule.region_id == "rz"
    assert rule.enter_filter == "only-red"
    assert rule.block_place_filter == "only-red"
    assert rule.block_break_filter == "only-red"
    assert rule.kit == "k"
    assert rule.message == "Red only"


def test_apply_rule_all_filter_fields():
    rule = deserializer._decode_apply_rule({
        'region': 'r',
        'enter': 'f-enter',
        'leave': 'f-leave',
        'block': 'f-block',
        'block_place': 'f-place',
        'block_break': 'f-break',
        'block_physics': 'f-phys',
        'block_place_against': 'f-against',
        'use': 'f-use',
        'filter': 'f-gen',
        'kit': 'k',
        'lend_kit': 'lk',
        'velocity': '0,2,0',
        'message': 'msg',
    })
    assert rule.region_id == 'r'
    assert rule.enter_filter == 'f-enter'
    assert rule.leave_filter == 'f-leave'
    assert rule.block_filter == 'f-block'
    assert rule.block_place_filter == 'f-place'
    assert rule.block_break_filter == 'f-break'
    assert rule.block_physics_filter == 'f-phys'
    assert rule.block_place_against_filter == 'f-against'
    assert rule.use_filter == 'f-use'
    assert rule.filter_id == 'f-gen'
    assert rule.kit == 'k'
    assert rule.lend_kit == 'lk'
    assert rule.velocity == '0,2,0'
    assert rule.message == 'msg'


# ---------------------------------------------------------------------------
# Region type decoding
# ---------------------------------------------------------------------------

def test_decode_rectangle():
    r = deserializer._decode_region({
        'id': 'rect', 'type': 'rectangle',
        'bounds_2d': {'min': {'x': -10, 'z': -5}, 'max': {'x': 10, 'z': 5}},
    })
    assert isinstance(r, Rectangle)
    assert r.min_x == -10.0
    assert r.max_z == 5.0


def test_decode_cuboid():
    r = deserializer._decode_region({
        'id': 'c', 'type': 'cuboid',
        'min': {'x': 0, 'y': 60, 'z': 0},
        'max': {'x': 10, 'y': 70, 'z': 10},
    })
    assert isinstance(r, Cuboid)
    assert r.min_y == 60.0
    assert r.max_x == 10.0


def test_decode_cylinder():
    r = deserializer._decode_region({
        'id': 'cy', 'type': 'cylinder',
        'base': {'x': 5, 'y': 64, 'z': 5},
        'radius': 8,
        'height': 10,
    })
    assert isinstance(r, Cylinder)
    assert r.radius == 8.0
    assert r.height == 10.0


def test_decode_cylinder_no_height():
    r = deserializer._decode_region({
        'id': 'cy', 'type': 'cylinder',
        'base': {'x': 0, 'y': 64, 'z': 0},
        'radius': 5,
    })
    assert r.height is None


def test_decode_circle():
    r = deserializer._decode_region({
        'id': 'ci', 'type': 'circle',
        'center': {'x': 0, 'z': 0},
        'radius': 20,
    })
    assert isinstance(r, Circle)
    assert r.radius == 20.0


def test_decode_sphere():
    r = deserializer._decode_region({
        'id': 'sp', 'type': 'sphere',
        'origin': {'x': 0, 'y': 64, 'z': 0},
        'radius': 5,
    })
    assert isinstance(r, Sphere)
    assert r.origin_y == 64.0


def test_decode_block():
    r = deserializer._decode_region({'id': 'b', 'type': 'block', 'position': {'x': 1, 'y': 64, 'z': 2}})
    assert isinstance(r, Block)
    assert r.x == 1.0


def test_decode_point():
    r = deserializer._decode_region({'id': 'p', 'type': 'point', 'position': {'x': 1.5, 'y': 64, 'z': 2.5}})
    assert isinstance(r, Point)
    assert r.x == 1.5


def test_decode_union():
    r = deserializer._decode_region({'id': 'u', 'type': 'union', 'children': ['a', 'b']})
    assert isinstance(r, Union)
    assert r.children == ['a', 'b']


def test_decode_negative():
    r = deserializer._decode_region({'id': 'n', 'type': 'negative', 'children': ['x']})
    assert isinstance(r, Negative)


def test_decode_complement():
    r = deserializer._decode_region({'id': 'c', 'type': 'complement', 'children': ['a', 'b']})
    assert isinstance(r, Complement)


def test_decode_intersect():
    r = deserializer._decode_region({'id': 'i', 'type': 'intersect', 'children': ['a']})
    assert isinstance(r, Intersect)


def test_decode_mirror():
    r = deserializer._decode_region({
        'id': 'm', 'type': 'mirror',
        'source_id': 'src',
        'origin': {'x': 0, 'y': 64, 'z': 0},
        'normal': {'x': 1, 'y': 0, 'z': 0},
    })
    assert isinstance(r, Mirror)
    assert r.source_id == 'src'
    assert r.normal_x == 1.0


def test_mirror_inline_region_ref_populates_source_id(tmp_path):
    # A9: a transform whose inline source is a <region id="X"/> reference must
    # record source_id="X" (not "") so it resolves in the registry and renders.
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <regions>
            <rectangle id="red-thing" min="0,0" max="5,5"/>
            <mirror id="blue-thing" normal="1,0,0" origin="10,0,0">
                <region id="red-thing"/>
            </mirror>
            <translate id="green-thing" offset="0,0,20">
                <region id="red-thing"/>
            </translate>
        </regions>
        </map>"""
    m = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    assert m.regions["blue-thing"].source_id == "red-thing"
    assert m.regions["green-thing"].source_id == "red-thing"


def test_decode_translate():
    r = deserializer._decode_region({
        'id': 't', 'type': 'translate',
        'source_id': 'src',
        'offset': {'x': 10, 'y': 0, 'z': 0},
    })
    assert isinstance(r, Translate)
    assert r.offset_x == 10.0


def test_decode_half():
    r = deserializer._decode_region({
        'id': 'h', 'type': 'half',
        'origin': {'x': 0, 'y': 64, 'z': 0},
        'normal': {'x': 0, 'y': 0, 'z': 1},
    })
    assert isinstance(r, Half)


def test_decode_reference():
    r = deserializer._decode_region({'id': 'ref', 'type': 'reference', 'ref_id': 'target'})
    assert isinstance(r, Reference)
    assert r.ref_id == 'target'


def test_decode_everywhere():
    r = deserializer._decode_region({'id': 'ev', 'type': 'everywhere'})
    assert isinstance(r, Everywhere)


def test_decode_above():
    r = deserializer._decode_region({'id': 'ab', 'type': 'above', 'y': 64})
    assert isinstance(r, Above)
    assert r.y == 64.0


def test_decode_region_infinity():
    import math
    r = deserializer._decode_region({
        'id': 'c', 'type': 'cuboid',
        'min': {'x': '-oo', 'y': '-oo', 'z': '-oo'},
        'max': {'x': 'oo', 'y': 'oo', 'z': 'oo'},
    })
    assert r.min_x == -math.inf
    assert r.max_x == math.inf


def test_decode_region_bounds_2d_set():
    r = deserializer._decode_region({
        'id': 'c', 'type': 'cuboid',
        'min': {'x': -5, 'y': 60, 'z': -5},
        'max': {'x': 5, 'y': 70, 'z': 5},
    })
    assert r.bounds_2d is not None
    assert r.bounds_2d['min']['x'] == -5.0
    assert r.bounds_2d['max']['z'] == 5.0


# ---------------------------------------------------------------------------
# Filter type decoding
# ---------------------------------------------------------------------------

def test_decode_all_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'all', 'children': ['a', 'b']})
    assert isinstance(f, AllFilter)
    assert f.children == ['a', 'b']


def test_decode_any_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'any', 'children': ['x']})
    assert isinstance(f, AnyFilter)


def test_decode_one_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'one', 'children': ['a', 'b', 'c']})
    assert isinstance(f, OneFilter)


def test_decode_not_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'not', 'child': 'g'})
    assert isinstance(f, NotFilter)
    assert f.child == 'g'


def test_decode_deny_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'deny', 'child': 'g'})
    assert isinstance(f, DenyFilter)


def test_decode_allow_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'allow', 'child': 'g'})
    assert isinstance(f, AllowFilter)


def test_decode_team_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'team', 'team': 'red'})
    assert isinstance(f, TeamFilter)
    assert f.team == 'red'


def test_decode_material_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'material', 'material': 'stone'})
    assert isinstance(f, MaterialFilter)


def test_decode_void_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'void'})
    assert isinstance(f, VoidFilter)


def test_decode_cause_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'cause', 'cause': 'explosion'})
    assert isinstance(f, CauseFilter)
    assert f.cause == 'explosion'


def test_decode_blocks_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'blocks', 'region': 'r', 'child': 'c'})
    assert isinstance(f, BlocksFilter)
    assert f.region == 'r'
    assert f.child == 'c'


def test_decode_carrying_filter():
    f = deserializer._decode_filter({
        'id': 'f', 'type': 'carrying',
        'material': 'iron_sword', 'damage': 1,
        'enchantments': 'sharpness:2', 'ignore_metadata': True,
    })
    assert isinstance(f, CarryingFilter)
    assert f.damage == 1
    assert f.ignore_metadata is True
    assert f.ignore_durability is True  # default


def test_decode_wearing_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'wearing', 'material': 'iron_helmet'})
    assert isinstance(f, WearingFilter)


def test_decode_holding_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'holding', 'material': 'bow'})
    assert isinstance(f, HoldingFilter)


@pytest.mark.parametrize("ftype,cls", [
    ('alive', AliveFilter), ('dead', DeadFilter),
    ('participating', ParticipatingFilter), ('observing', ObservingFilter),
    ('match-running', MatchRunningFilter), ('match-started', MatchStartedFilter),
    ('grounded', GroundedFilter), ('never', NeverFilter), ('always', AlwaysFilter),
])
def test_decode_simple_filters(ftype, cls):
    f = deserializer._decode_filter({'id': 'f', 'type': ftype})
    assert isinstance(f, cls)


def test_decode_time_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'time', 'duration': '5m'})
    assert isinstance(f, TimeFilter)
    assert f.duration == '5m'


def test_decode_after_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'after', 'filter': 'trig', 'duration': '0.5s'})
    assert isinstance(f, AfterFilter)
    assert f.filter_ref == 'trig'
    assert f.duration == '0.5s'


def test_decode_pulse_filter():
    f = deserializer._decode_filter({
        'id': 'f', 'type': 'pulse',
        'period': '1s', 'duration': '0.5s', 'filter': 'cond',
    })
    assert isinstance(f, PulseFilter)
    assert f.filter_ref == 'cond'


def test_decode_offset_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'offset', 'vector': '~0,~-1,~0', 'child': 'c'})
    assert isinstance(f, OffsetFilter)


def test_decode_variable_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'variable', 'var': 'score', 'value': '10', 'team': 'red'})
    assert isinstance(f, VariableFilter)
    assert f.var == 'score'
    assert f.team == 'red'


def test_decode_completed_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'completed', 'objective': 'blue-wool'})
    assert isinstance(f, CompletedFilter)
    assert f.objective == 'blue-wool'


def test_decode_objective_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'objective', 'objective': 'red-wool'})
    assert isinstance(f, ObjectiveFilter)


def test_decode_kill_streak_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'kill-streak', 'min': 3, 'max': 10})
    assert isinstance(f, KillStreakFilter)
    assert f.min == 3
    assert f.max == 10
    assert f.count is None


def test_decode_class_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'class', 'name': 'archer'})
    assert isinstance(f, ClassFilter)
    assert f.name == 'archer'


def test_decode_region_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'region', 'region': 'r'})
    assert isinstance(f, RegionFilter)
    assert f.region == 'r'


def test_decode_players_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'players', 'min': 1, 'max': 5})
    assert isinstance(f, PlayerFilter)
    assert f.min == 1
    assert f.max == 5


def test_decode_spawn_filter():
    f = deserializer._decode_filter({'id': 'f', 'type': 'spawn', 'mob': 'sheep'})
    assert isinstance(f, SpawnFilter)
    assert f.mob == 'sheep'


# ---------------------------------------------------------------------------
# Regions registry round-trip
# ---------------------------------------------------------------------------

def test_regions_registry_preserved(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <regions>
            <rectangle id="red-spawn" min="-11,-121" max="11,-94"/>
            <cuboid id="blue-base" min="-10,60,-10" max="10,70,10"/>
            <union id="all-spawns">
                <region id="red-spawn"/>
            </union>
        </regions>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    assert 'red-spawn' in restored.regions
    assert 'blue-base' in restored.regions
    assert 'all-spawns' in restored.regions
    assert isinstance(restored.regions['all-spawns'], Union)
    assert 'red-spawn' in restored.regions['all-spawns'].children


def test_filters_registry_preserved(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>M</name><version>1.0</version><objective>x</objective>
        <filters>
            <team id="only-red">red</team>
            <all id="red-alive">
                <filter id="only-red"/>
                <alive/>
            </all>
        </filters>
        </map>"""
    orig, restored = _json_roundtrip(_write_xml(tmp_path, xml))
    assert 'only-red' in restored.filters
    assert 'red-alive' in restored.filters
    assert isinstance(restored.filters['red-alive'], AllFilter)
    assert 'only-red' in restored.filters['red-alive'].children


# ---------------------------------------------------------------------------
# Full export roundtrip (xml → to_dict → from_dict → to_xml → parse)
# ---------------------------------------------------------------------------

FULL_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Export Test</name>
    <version>3.1.0</version>
    <objective>Capture the wool.</objective>
    <authors>
        <author uuid="aaaaaaaa-0000-0000-0000-000000000001"/>
    </authors>
    <teams>
        <team id="red" color="dark red" max="10">Red</team>
        <team id="blue" color="blue" max="10">Blue</team>
    </teams>
    <kits>
        <kit id="default-kit">
            <item slot="0" material="iron sword" unbreakable="true"/>
            <helmet material="leather helmet" team-color="true"/>
        </kit>
    </kits>
    <spawns>
        <default><region><cuboid min="-1,5,-1" max="1,5,1"/></region></default>
        <spawn team="red" kit="default-kit" yaw="90">
            <region><cuboid min="10,5,10" max="12,5,12"/></region>
        </spawn>
        <spawn team="blue" kit="default-kit" yaw="-90">
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
    <filters>
        <team id="only-red">red</team>
        <team id="only-blue">blue</team>
    </filters>
    <regions>
        <cuboid id="red-base" min="8,60,8" max="20,80,20"/>
        <apply region="red-base" enter="only-red" block-place="only-red" message="Red only"/>
    </regions>
    <renewables>
        <renewable region="red-base" rate="2.0"/>
    </renewables>
    <maxbuildheight>64</maxbuildheight>
    </map>
    """


def test_full_roundtrip_name(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert reparsed.name == orig.name


def test_full_roundtrip_version(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert reparsed.version == orig.version


def test_full_roundtrip_teams(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert {t.id for t in reparsed.teams} == {t.id for t in orig.teams}


def test_full_roundtrip_spawns(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert len(reparsed.spawns) == len(orig.spawns)
    assert reparsed.observer_spawn is not None


def test_full_roundtrip_wools(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert len(reparsed.wools) == len(orig.wools)
    orig_w = {(w.team, w.color) for w in orig.wools}
    re_w = {(w.team, w.color) for w in reparsed.wools}
    assert orig_w == re_w


def test_full_roundtrip_filters(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert 'only-red' in reparsed.filters
    assert 'only-blue' in reparsed.filters


def test_full_roundtrip_regions(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert 'red-base' in reparsed.regions


def test_full_roundtrip_apply_rules(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    enter_rules = [r for r in reparsed.apply_rules if r.enter_filter]
    orig_enter = [r for r in orig.apply_rules if r.enter_filter]
    assert len(enter_rules) == len(orig_enter)


def test_full_roundtrip_max_build_height(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert reparsed.max_build_height == orig.max_build_height


def test_full_roundtrip_kit(tmp_path):
    orig, reparsed = _full_roundtrip(_write_xml(tmp_path, FULL_XML))
    assert len(reparsed.kits) == len(orig.kits)
    assert reparsed.kits[0].id == orig.kits[0].id


def test_full_roundtrip_no_synthetic_ids(tmp_path):
    orig = MapXmlParser(_write_xml(tmp_path, FULL_XML)).parse()
    restored = deserializer.from_dict(serializer.to_dict(orig))
    xml_str = to_xml(restored)
    assert '__anon_' not in xml_str
    assert '__spawn_' not in xml_str


# ---------------------------------------------------------------------------
# Real-map roundtrips
# ---------------------------------------------------------------------------

TUMBLEWEED = Path('/media/sf_repos/CommunityMaps/ctw/tumbleweed/map.xml')
OUTBACK = Path('/media/sf_repos/CommunityMaps/ctw/outback_outback_edition/map.xml')
ANNEALING = Path('/media/sf_repos/CommunityMaps/ctw/annealing_iv/map.xml')


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_full_roundtrip_teams():
    orig, reparsed = _full_roundtrip(str(TUMBLEWEED))
    assert {t.id for t in reparsed.teams} == {t.id for t in orig.teams}


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_full_roundtrip_wools():
    orig, reparsed = _full_roundtrip(str(TUMBLEWEED))
    assert len(reparsed.wools) == len(orig.wools)


@pytest.mark.skipif(not ANNEALING.exists(), reason="Annealing IV not available")
def test_annealing_multi_monument_wool_roundtrip():
    """4-team map: each color is captured by 3 teams (one monument per team).

    Exercises the grouped<->flat wool bijection where one color groups several
    monuments. Round-trip must preserve every (team, color) pair and count.
    """
    orig, reparsed = _full_roundtrip(str(ANNEALING))
    assert len(reparsed.wools) == len(orig.wools)
    assert {(w.team, w.color) for w in reparsed.wools} == {(w.team, w.color) for w in orig.wools}
    # A color shared by multiple teams confirms the grouping path was used.
    from collections import Counter
    by_color = Counter(w.color for w in orig.wools)
    assert max(by_color.values()) > 1


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_full_roundtrip_filters():
    orig, reparsed = _full_roundtrip(str(TUMBLEWEED))
    for fid in ('only-blue', 'only-red', 'only-iron'):
        assert fid in reparsed.filters


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_full_roundtrip_apply_enter_rules():
    orig, reparsed = _full_roundtrip(str(TUMBLEWEED))
    assert (len([r for r in reparsed.apply_rules if r.enter_filter]) ==
            len([r for r in orig.apply_rules if r.enter_filter]))


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_no_synthetic_ids_after_json_path():
    orig = MapXmlParser(str(TUMBLEWEED)).parse()
    restored = deserializer.from_dict(serializer.to_dict(orig))
    assert '__anon_' not in to_xml(restored)


@pytest.mark.skipif(not OUTBACK.exists(), reason="Outback not available")
def test_outback_full_roundtrip_filters_count():
    orig, reparsed = _full_roundtrip(str(OUTBACK))
    from pgm_map_studio.pgm.xml_writer import _is_synthetic
    user_orig = {fid for fid in orig.filters
                 if not _is_synthetic(fid) and fid not in ('never', 'always')}
    user_re = {fid for fid in reparsed.filters
               if not _is_synthetic(fid) and fid not in ('never', 'always')}
    assert user_orig == user_re


@pytest.mark.skipif(not ANNEALING.exists(), reason="Annealing not available")
def test_annealing_full_roundtrip_enter_rules():
    orig, reparsed = _full_roundtrip(str(ANNEALING))
    assert len([r for r in reparsed.apply_rules if r.enter_filter]) == 8
