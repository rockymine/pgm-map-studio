"""Tests for pgm_map_studio.pgm.xml_writer — XML roundtrip."""

import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pgm_map_studio.pgm.parser import MapXmlParser
from pgm_map_studio.pgm.xml_writer import to_xml, _is_synthetic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_xml(tmp_path: Path, content: str) -> str:
    p = tmp_path / "map.xml"
    p.write_text(textwrap.dedent(content))
    return str(p)


def _roundtrip(path: str) -> tuple:
    """Parse → export XML → re-parse. Returns (original, re-parsed)."""
    orig = MapXmlParser(path).parse()
    xml_str = to_xml(orig)
    # Write exported XML to a temp file and re-parse
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_str)
        tmp = f.name
    try:
        reparsed = MapXmlParser(tmp).parse()
    finally:
        os.unlink(tmp)
    return orig, reparsed


def _parse_xml(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str)


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
# _is_synthetic
# ---------------------------------------------------------------------------

def test_is_synthetic_anon():
    assert _is_synthetic('spawns__anon_0') is True


def test_is_synthetic_dunder_prefix():
    assert _is_synthetic('__spawn_blue') is True
    assert _is_synthetic('__observer_spawn') is True


def test_is_synthetic_named():
    assert _is_synthetic('red-spawn') is False
    assert _is_synthetic('only-blue') is False


# ---------------------------------------------------------------------------
# Basic structure of exported XML
# ---------------------------------------------------------------------------

def test_export_produces_xml_string(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    data = MapXmlParser(path).parse()
    xml_str = to_xml(data)
    assert xml_str.startswith('<?xml version="1.0"?>')
    root = _parse_xml(xml_str)
    assert root.tag == 'map'


def test_export_proto_attribute(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    data = MapXmlParser(path).parse()
    root = _parse_xml(to_xml(data))
    assert root.get('proto') == '1.5.0'


def test_no_synthetic_ids_in_output(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    data = MapXmlParser(path).parse()
    xml_str = to_xml(data)
    assert '__anon_' not in xml_str
    assert '__spawn_' not in xml_str
    assert '__apply_' not in xml_str
    assert '__observer_' not in xml_str


# ---------------------------------------------------------------------------
# Name / version / objective
# ---------------------------------------------------------------------------

def test_roundtrip_name(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    orig, reparsed = _roundtrip(path)
    assert reparsed.name == orig.name


def test_roundtrip_version(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    orig, reparsed = _roundtrip(path)
    assert reparsed.version == orig.version


def test_roundtrip_objective(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    orig, reparsed = _roundtrip(path)
    assert reparsed.objective == orig.objective


def test_gamemode_omitted_when_ctw(tmp_path):
    # ctw is the default — should not appear in output
    path = _write_xml(tmp_path, MINIMAL)
    data = MapXmlParser(path).parse()
    xml_str = to_xml(data)
    assert '<gamemode>' not in xml_str


def test_gamemode_written_when_not_ctw(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>Test Map</name><version>1.0.0</version>
        <gamemode>dtm</gamemode>
        <objective>Capture!</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    data = MapXmlParser(path).parse()
    xml_str = to_xml(data)
    assert '<gamemode>dtm</gamemode>' in xml_str


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------

def test_roundtrip_authors(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <authors>
            <author uuid="aaaaaaaa-0000-0000-0000-000000000001" contribution="design"/>
        </authors>
        <contributors>
            <contributor uuid="bbbbbbbb-0000-0000-0000-000000000002" contribution="xml"/>
        </contributors>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.authors) == 2
    author = next(a for a in reparsed.authors if a.role == 'author')
    assert author.uuid == 'aaaaaaaa-0000-0000-0000-000000000001'
    assert author.contribution == 'design'
    contrib = next(a for a in reparsed.authors if a.role == 'contributor')
    assert contrib.uuid == 'bbbbbbbb-0000-0000-0000-000000000002'


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

def test_roundtrip_teams(tmp_path):
    path = _write_xml(tmp_path, MINIMAL)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.teams) == len(orig.teams)
    red = next(t for t in reparsed.teams if t.id == 'red')
    assert red.color == 'dark red'
    assert red.max_players == 16


def test_roundtrip_team_dye_color(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams>
            <team id="yellow" color="yellow" dye-color="yellow" max="8">Yellow</team>
        </teams>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert reparsed.teams[0].dye_color == 'yellow'


# ---------------------------------------------------------------------------
# Kits
# ---------------------------------------------------------------------------

KIT_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>X</name><version>1.0</version><objective>X</objective>
    <teams><team id="red" color="dark red" max="8">Red</team></teams>
    <kits>
        <kit id="spawn-kit">
            <item slot="0" material="iron sword" unbreakable="true"/>
            <item slot="1" material="bow">
                <enchantment>infinity</enchantment>
            </item>
            <item slot="2" material="wood" amount="64" damage="3" team-color="true"/>
            <helmet material="leather helmet" unbreakable="true" team-color="true"/>
            <chestplate material="leather chestplate"/>
        </kit>
    </kits>
    </map>
    """


def test_roundtrip_kit_item_count(tmp_path):
    path = _write_xml(tmp_path, KIT_XML)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.kits) == 1
    assert reparsed.kits[0].id == 'spawn-kit'
    assert len(reparsed.kits[0].items) == 3


def test_roundtrip_kit_item_attrs(tmp_path):
    path = _write_xml(tmp_path, KIT_XML)
    orig, reparsed = _roundtrip(path)
    sword = next(i for i in reparsed.kits[0].items if i.material == 'iron sword')
    assert sword.slot == 0
    assert sword.unbreakable is True


def test_roundtrip_kit_enchantment(tmp_path):
    path = _write_xml(tmp_path, KIT_XML)
    orig, reparsed = _roundtrip(path)
    bow = next(i for i in reparsed.kits[0].items if i.material == 'bow')
    assert 'infinity' in bow.enchantments


def test_roundtrip_kit_amount_damage(tmp_path):
    path = _write_xml(tmp_path, KIT_XML)
    orig, reparsed = _roundtrip(path)
    wood = next(i for i in reparsed.kits[0].items if i.material == 'wood')
    assert wood.amount == 64
    assert wood.item_damage == 3
    assert wood.team_color is True


def test_roundtrip_kit_armor(tmp_path):
    path = _write_xml(tmp_path, KIT_XML)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.kits[0].armor) == 2
    helmet = next(a for a in reparsed.kits[0].armor if a.slot_name == 'helmet')
    assert helmet.unbreakable is True
    assert helmet.team_color is True


# ---------------------------------------------------------------------------
# Spawns
# ---------------------------------------------------------------------------

SPAWN_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Spawn Test</name><version>1.0</version><objective>X</objective>
    <teams>
        <team id="red" color="dark red" max="8">Red</team>
        <team id="blue" color="blue" max="8">Blue</team>
    </teams>
    <spawns>
        <default yaw="-90">
            <region><cuboid min="-1,5,-1" max="1,5,1"/></region>
        </default>
        <spawn team="red" kit="spawn-kit" yaw="90">
            <region><cuboid min="10,5,10" max="12,5,12"/></region>
        </spawn>
        <spawn team="blue" kit="spawn-kit" yaw="-90">
            <region><cuboid min="-10,5,-10" max="-12,5,-12"/></region>
        </spawn>
    </spawns>
    </map>
    """


def test_roundtrip_spawns_count(tmp_path):
    path = _write_xml(tmp_path, SPAWN_XML)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.spawns) == 2


def test_roundtrip_observer_spawn(tmp_path):
    path = _write_xml(tmp_path, SPAWN_XML)
    orig, reparsed = _roundtrip(path)
    assert reparsed.observer_spawn is not None
    assert reparsed.observer_spawn.yaw == -90.0


def test_roundtrip_spawn_team_kit(tmp_path):
    path = _write_xml(tmp_path, SPAWN_XML)
    orig, reparsed = _roundtrip(path)
    red = next(s for s in reparsed.spawns if s.team == 'red')
    assert red.kit == 'spawn-kit'
    assert red.yaw == 90.0


def test_roundtrip_spawn_region_preserved(tmp_path):
    path = _write_xml(tmp_path, SPAWN_XML)
    orig, reparsed = _roundtrip(path)
    red = next(s for s in reparsed.spawns if s.team == 'red')
    assert red.region is not None
    assert red.region.region_type == 'cuboid'


def test_no_synthetic_ids_in_spawn_output(tmp_path):
    path = _write_xml(tmp_path, SPAWN_XML)
    data = MapXmlParser(path).parse()
    xml_str = to_xml(data)
    assert '__spawn_' not in xml_str


# ---------------------------------------------------------------------------
# Wools
# ---------------------------------------------------------------------------

WOOL_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Wool Test</name><version>1.0</version><objective>X</objective>
    <teams>
        <team id="red" color="dark red" max="8">Red</team>
        <team id="blue" color="blue" max="8">Blue</team>
    </teams>
    <wools>
        <wool team="red" color="cyan" location="5,10,5">
            <monument><block>15,10,15</block></monument>
        </wool>
        <wool team="blue" color="orange" location="-5,10,-5">
            <monument><block>-15,10,-15</block></monument>
        </wool>
    </wools>
    </map>
    """


def test_roundtrip_wools_count(tmp_path):
    path = _write_xml(tmp_path, WOOL_XML)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.wools) == 2


def test_roundtrip_wool_fields(tmp_path):
    path = _write_xml(tmp_path, WOOL_XML)
    orig, reparsed = _roundtrip(path)
    cyan = next(w for w in reparsed.wools if w.color == 'cyan')
    assert cyan.team == 'red'
    assert cyan.location == (5.0, 10.0, 5.0)
    assert cyan.monument == (15.0, 10.0, 15.0)


# ---------------------------------------------------------------------------
# Filters roundtrip
# ---------------------------------------------------------------------------

def test_roundtrip_named_filters(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <filters>
            <team id="only-red">red</team>
            <material id="only-iron">iron block</material>
            <all id="iron-cause-world">
                <material id="only-iron2">iron block</material>
                <cause>world</cause>
            </all>
            <deny id="deny-chest">
                <material>chest</material>
            </deny>
        </filters>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert 'only-red' in reparsed.filters
    assert 'only-iron' in reparsed.filters
    assert 'iron-cause-world' in reparsed.filters
    assert 'deny-chest' in reparsed.filters


def test_roundtrip_nested_filter_ids(tmp_path):
    """Named child filters (with id) survive the roundtrip reachable from registry."""
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <filters>
            <all id="combo">
                <team id="only-red">red</team>
                <material id="only-iron">iron block</material>
            </all>
        </filters>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert 'only-red' in reparsed.filters
    assert 'only-iron' in reparsed.filters
    assert 'combo' in reparsed.filters


def test_multi_parent_filter_top_level(tmp_path):
    """Filter referenced by 2+ composites must survive as an independent entry."""
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <filters>
            <any id="shared">
                <material>web</material>
                <material>vine</material>
            </any>
            <all id="combo-a">
                <team>red</team>
                <filter id="shared"/>
            </all>
            <all id="combo-b">
                <void/>
                <filter id="shared"/>
            </all>
        </filters>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert 'shared' in reparsed.filters
    assert 'combo-a' in reparsed.filters
    assert 'combo-b' in reparsed.filters


def test_no_synthetic_filter_ids_in_output(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <filters>
            <deny id="deny-chest">
                <material>chest</material>
            </deny>
        </filters>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    data = MapXmlParser(path).parse()
    xml_str = to_xml(data)
    assert '__anon_' not in xml_str


# ---------------------------------------------------------------------------
# Regions roundtrip
# ---------------------------------------------------------------------------

def test_roundtrip_named_region(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <regions>
            <rectangle id="red-spawn" min="-11,-121" max="11,-94"/>
        </regions>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert 'red-spawn' in reparsed.regions
    r = reparsed.regions['red-spawn']
    assert r.region_type == 'rectangle'
    # bounds_2d should be normalized
    assert r.bounds_2d['min']['x'] == -11.0
    assert r.bounds_2d['max']['x'] == 11.0


def test_roundtrip_nested_named_regions(tmp_path):
    """Named children inside a composite survive as separate registry entries."""
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <regions>
            <union id="spawns">
                <rectangle id="red-spawn" min="0,0" max="20,20"/>
                <rectangle id="blue-spawn" min="-20,-20" max="0,0"/>
            </union>
        </regions>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert 'spawns' in reparsed.regions
    assert 'red-spawn' in reparsed.regions
    assert 'blue-spawn' in reparsed.regions
    u = reparsed.regions['spawns']
    assert 'red-spawn' in u.children
    assert 'blue-spawn' in u.children


def test_roundtrip_cuboid_region(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <regions>
            <cuboid id="box" min="-10,5,10" max="-12,5,12"/>
        </regions>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    from pgm_map_studio.pgm.regions import Cuboid
    assert isinstance(reparsed.regions['box'], Cuboid)


def test_children_are_strings_in_export(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <regions>
            <union id="u">
                <rectangle id="a" min="0,0" max="10,10"/>
                <rectangle id="b" min="20,20" max="30,30"/>
            </union>
        </regions>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert all(isinstance(c, str) for c in reparsed.regions['u'].children)


# ---------------------------------------------------------------------------
# Apply rules roundtrip
# ---------------------------------------------------------------------------

def test_roundtrip_apply_enter(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams>
            <team id="red" color="dark red" max="8">Red</team>
            <team id="blue" color="blue" max="8">Blue</team>
        </teams>
        <filters>
            <team id="only-blue">blue</team>
        </filters>
        <regions>
            <rectangle id="blue-spawn" min="0,0" max="10,10"/>
            <apply enter="only-blue" region="blue-spawn" message="No entry!"/>
        </regions>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    rule = next(r for r in reparsed.apply_rules if r.enter_filter == 'only-blue')
    assert rule.region_id == 'blue-spawn'
    assert rule.message == 'No entry!'


def test_roundtrip_apply_all_attrs(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <filters>
            <material id="only-iron">iron block</material>
            <all id="only-iron-world">
                <material>iron block</material>
                <cause>world</cause>
            </all>
            <deny id="deny-physics"><any><material>redstone wire</material></any></deny>
        </filters>
        <regions>
            <rectangle id="spawns" min="-10,-10" max="10,10"/>
            <rectangle id="woolrooms" min="-20,-20" max="20,20"/>
            <apply block-place="only-iron-world" block-break="only-iron" region="spawns" message="No editing spawn!"/>
            <apply kit="reset-kit" region="spawns"/>
            <apply block-physics="deny-physics" region="woolrooms"/>
        </regions>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    spawn_rule = next(r for r in reparsed.apply_rules if r.block_break_filter == 'only-iron')
    assert spawn_rule.block_place_filter == 'only-iron-world'
    assert spawn_rule.message == 'No editing spawn!'
    kit_rule = next(r for r in reparsed.apply_rules if r.kit == 'reset-kit')
    assert kit_rule.region_id == 'spawns'
    phys_rule = next(r for r in reparsed.apply_rules if r.block_physics_filter)
    assert phys_rule.block_physics_filter == 'deny-physics'


def test_roundtrip_apply_shorthand(tmp_path):
    """Inline shorthand filter values (deny(void)) survive verbatim."""
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <regions>
            <apply block-place="deny(void)" message="No void edits!"/>
        </regions>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    rule = reparsed.apply_rules[0]
    assert rule.block_place_filter == 'deny(void)'
    assert rule.message == 'No void edits!'


def test_roundtrip_apply_inline_region(tmp_path):
    """Inline region in apply (without region= attribute) survives."""
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <regions>
            <apply block-break="never" block-place="never" message="No editing!">
                <region>
                    <cuboid min="-52,17,-7" max="-45,26,-14"/>
                </region>
            </apply>
        </regions>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    rule = reparsed.apply_rules[0]
    assert rule.block_break_filter == 'never'
    assert rule.region_id != ''


# ---------------------------------------------------------------------------
# Spawners / renewables / block-drops
# ---------------------------------------------------------------------------

def test_roundtrip_spawner(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <spawners>
            <spawner spawn-region="wool-spawn" player-region="wool-room" delay="1.5s" max-entities="10">
                <item material="wool" damage="14"/>
            </spawner>
        </spawners>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.spawners) == 1
    s = reparsed.spawners[0]
    assert s.spawn_region == 'wool-spawn'
    assert s.delay == '1.5s'
    assert s.max_entities == 10
    assert s.items[0].material == 'wool'
    assert s.items[0].damage == 14


def test_roundtrip_renewable(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <renewables>
            <renewable region="spawns" rate="2.0" renew-filter="only-iron" replace-filter="only-air"/>
        </renewables>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.renewables) == 1
    r = reparsed.renewables[0]
    assert r.region_id == 'spawns'
    assert r.rate == 2.0
    assert r.renew_filter == 'only-iron'


def test_roundtrip_block_drop_rule(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <block-drops>
            <rule filter="only-iron" wrong-tool="true">
                <replacement>iron block</replacement>
                <drops><item material="iron ingot" chance="0.5"/></drops>
            </rule>
        </block-drops>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert len(reparsed.block_drop_rules) == 1
    r = reparsed.block_drop_rules[0]
    assert r.filter_id == 'only-iron'
    assert r.wrong_tool is True
    assert r.replacement == 'iron block'
    assert r.items[0].chance == pytest.approx(0.5)


def test_roundtrip_max_build_height(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <maxbuildheight>32</maxbuildheight>
        </map>
        """
    path = _write_xml(tmp_path, xml)
    orig, reparsed = _roundtrip(path)
    assert reparsed.max_build_height == 32


# ---------------------------------------------------------------------------
# Real map roundtrip tests
# ---------------------------------------------------------------------------

TUMBLEWEED = Path('/media/sf_repos/CommunityMaps/ctw/tumbleweed/map.xml')
OUTBACK = Path('/media/sf_repos/CommunityMaps/ctw/outback_outback_edition/map.xml')
ANNEALING = Path('/media/sf_repos/CommunityMaps/ctw/annealing_iv/map.xml')


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_roundtrip_metadata():
    orig, reparsed = _roundtrip(str(TUMBLEWEED))
    assert reparsed.name == orig.name
    assert reparsed.version == orig.version
    assert reparsed.max_build_height == orig.max_build_height


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_roundtrip_teams():
    orig, reparsed = _roundtrip(str(TUMBLEWEED))
    assert len(reparsed.teams) == len(orig.teams)
    orig_ids = {t.id for t in orig.teams}
    reparsed_ids = {t.id for t in reparsed.teams}
    assert orig_ids == reparsed_ids


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_roundtrip_wools():
    orig, reparsed = _roundtrip(str(TUMBLEWEED))
    assert len(reparsed.wools) == len(orig.wools)


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_roundtrip_spawns():
    orig, reparsed = _roundtrip(str(TUMBLEWEED))
    assert len(reparsed.spawns) == len(orig.spawns)
    assert reparsed.observer_spawn is not None


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_roundtrip_filters():
    orig, reparsed = _roundtrip(str(TUMBLEWEED))
    for fid in ('only-blue', 'only-red', 'only-iron', 'only-iron-regen', 'deny-chest'):
        assert fid in reparsed.filters, f"Missing filter: {fid}"


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_roundtrip_apply_enter_rules():
    orig, reparsed = _roundtrip(str(TUMBLEWEED))
    enter_rules = [r for r in reparsed.apply_rules if r.enter_filter]
    assert len(enter_rules) == len([r for r in orig.apply_rules if r.enter_filter])


@pytest.mark.skipif(not TUMBLEWEED.exists(), reason="Tumbleweed not available")
def test_tumbleweed_no_synthetic_ids_in_output():
    data = MapXmlParser(str(TUMBLEWEED)).parse()
    xml_str = to_xml(data)
    assert '__anon_' not in xml_str
    assert '__spawn_' not in xml_str
    # Output should be parseable
    root = _parse_xml(xml_str)
    assert root.tag == 'map'


@pytest.mark.skipif(not OUTBACK.exists(), reason="Outback not available")
def test_outback_roundtrip_filters_count():
    orig, reparsed = _roundtrip(str(OUTBACK))
    # All user-defined (non-synthetic, non-builtin) filters survive
    user_filters_orig = {fid for fid in orig.filters
                         if not _is_synthetic(fid) and fid not in ('never', 'always')}
    user_filters_re = {fid for fid in reparsed.filters
                       if not _is_synthetic(fid) and fid not in ('never', 'always')}
    assert user_filters_orig == user_filters_re


@pytest.mark.skipif(not OUTBACK.exists(), reason="Outback not available")
def test_outback_roundtrip_kit_rule():
    orig, reparsed = _roundtrip(str(OUTBACK))
    kit_rules_orig = [r for r in orig.apply_rules if r.kit]
    kit_rules_re = [r for r in reparsed.apply_rules if r.kit]
    assert len(kit_rules_re) == len(kit_rules_orig)


@pytest.mark.skipif(not ANNEALING.exists(), reason="Annealing not available")
def test_annealing_roundtrip_enter_rules():
    orig, reparsed = _roundtrip(str(ANNEALING))
    assert len([r for r in reparsed.apply_rules if r.enter_filter]) == 8


@pytest.mark.skipif(not ANNEALING.exists(), reason="Annealing not available")
def test_annealing_no_synthetic_ids():
    data = MapXmlParser(str(ANNEALING)).parse()
    xml_str = to_xml(data)
    assert '__anon_' not in xml_str
    assert '__spawn_' not in xml_str
