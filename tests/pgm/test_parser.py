"""Tests for pgm_map_studio.pgm.parser."""

import textwrap
import pytest
from pathlib import Path

from pgm_map_studio.pgm.parser import MapXmlParser
from pgm_map_studio.pgm.regions import Rectangle, Cuboid, Cylinder, Union


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_xml(tmp_path: Path, content: str) -> str:
    p = tmp_path / "map.xml"
    p.write_text(textwrap.dedent(content))
    return str(p)


MINIMAL_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Test Map</name>
    <version>1.0.0</version>
    <objective>Capture the wools!</objective>
    <teams>
        <team id="red" color="dark red" max="16">Red Team</team>
        <team id="blue" color="blue" max="16" min="1">Blue Team</team>
    </teams>
    </map>
    """


# ---------------------------------------------------------------------------
# Basic info
# ---------------------------------------------------------------------------

def test_parse_name(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    assert data.name == "Test Map"


def test_parse_version(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    assert data.version == "1.0.0"


def test_parse_objective(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    assert data.objective == "Capture the wools!"


def test_parse_gamemode_default(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    assert data.gamemode == "ctw"


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

def test_teams_count(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    assert len(data.teams) == 2


def test_team_id_color_max(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    red = next(t for t in data.teams if t.id == 'red')
    assert red.color == 'dark red'
    assert red.max_players == 16


def test_team_min_players(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    blue = next(t for t in data.teams if t.id == 'blue')
    assert blue.min_players == 1


def test_team_min_players_default_zero(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    red = next(t for t in data.teams if t.id == 'red')
    assert red.min_players == 0


def test_team_dye_color(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams>
            <team id="y" color="yellow" dye-color="yellow" max="8">Yellow</team>
        </teams>
        </map>
        """
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    assert data.teams[0].dye_color == 'yellow'


# ---------------------------------------------------------------------------
# Kits
# ---------------------------------------------------------------------------

KIT_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Kit Map</name><version>1.0</version><objective>X</objective>
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


def test_kit_parsed(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, KIT_XML)).parse()
    assert len(data.kits) == 1
    assert data.kits[0].id == 'spawn-kit'


def test_kit_items(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, KIT_XML)).parse()
    kit = data.kits[0]
    assert len(kit.items) == 3


def test_kit_item_unbreakable(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, KIT_XML)).parse()
    sword = next(i for i in data.kits[0].items if i.material == 'iron sword')
    assert sword.unbreakable is True


def test_kit_item_amount_damage(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, KIT_XML)).parse()
    wood = next(i for i in data.kits[0].items if i.material == 'wood')
    assert wood.amount == 64
    assert wood.item_damage == 3


def test_kit_item_team_color(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, KIT_XML)).parse()
    wood = next(i for i in data.kits[0].items if i.material == 'wood')
    assert wood.team_color is True


def test_kit_enchantment_child_element(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, KIT_XML)).parse()
    bow = next(i for i in data.kits[0].items if i.material == 'bow')
    assert 'infinity' in bow.enchantments


def test_kit_armor_parsed(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, KIT_XML)).parse()
    kit = data.kits[0]
    assert len(kit.armor) == 2
    helmet = next(a for a in kit.armor if a.slot_name == 'helmet')
    assert helmet.unbreakable is True
    assert helmet.team_color is True


def test_kit_armor_material(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, KIT_XML)).parse()
    chest = next(a for a in data.kits[0].armor if a.slot_name == 'chestplate')
    assert chest.material == 'leather chestplate'


def test_kit_enchantment_attribute_form(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="r" color="red" max="8">R</team></teams>
        <kits>
            <kit id="k">
                <item slot="0" material="sword" enchantment="sharpness:2;fire_aspect:1"/>
            </kit>
        </kits>
        </map>
        """
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    enchants = data.kits[0].items[0].enchantments
    assert 'sharpness:2' in enchants
    assert 'fire_aspect:1' in enchants


# ---------------------------------------------------------------------------
# Spawns
# ---------------------------------------------------------------------------

SPAWN_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Spawn Map</name><version>1.0</version><objective>X</objective>
    <teams>
        <team id="red" color="dark red" max="16">Red</team>
        <team id="blue" color="blue" max="16">Blue</team>
    </teams>
    <spawns>
        <default yaw="-90">
            <region><cuboid min="-169,57,-43" max="-170,57,-42"/></region>
        </default>
        <spawn team="red" kit="spawn-kit" yaw="90">
            <region><cuboid min="10,5,10" max="12,5,12"/></region>
        </spawn>
        <spawn team="blue" kit="spawn-kit" region="blue-spawn"/>
    </spawns>
    <regions>
        <cuboid id="blue-spawn" min="-10,5,-10" max="-12,5,-12"/>
    </regions>
    </map>
    """


def test_spawns_count(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWN_XML)).parse()
    assert len(data.spawns) == 2


def test_spawn_team_kit_yaw(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWN_XML)).parse()
    red = next(s for s in data.spawns if s.team == 'red')
    assert red.kit == 'spawn-kit'
    assert red.yaw == 90.0


def test_spawn_inline_region(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWN_XML)).parse()
    red = next(s for s in data.spawns if s.team == 'red')
    assert red.region is not None
    assert isinstance(red.region, Cuboid)


def test_spawn_named_region_resolved(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWN_XML)).parse()
    blue = next(s for s in data.spawns if s.team == 'blue')
    assert blue.region is not None
    assert isinstance(blue.region, Cuboid)


def test_observer_spawn_detected(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWN_XML)).parse()
    assert data.observer_spawn is not None
    assert data.observer_spawn.yaw == -90.0


def test_observer_spawn_has_region(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWN_XML)).parse()
    assert data.observer_spawn.region is not None


# ---------------------------------------------------------------------------
# Wools
# ---------------------------------------------------------------------------

WOOL_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Wool Map</name><version>1.0</version><objective>X</objective>
    <teams>
        <team id="red" color="dark red" max="16">Red</team>
        <team id="blue" color="blue" max="16">Blue</team>
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


def test_wools_count(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, WOOL_XML)).parse()
    assert len(data.wools) == 2


def test_wool_team_color(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, WOOL_XML)).parse()
    cyan = next(w for w in data.wools if w.color == 'cyan')
    assert cyan.team == 'red'


def test_wool_location(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, WOOL_XML)).parse()
    cyan = next(w for w in data.wools if w.color == 'cyan')
    assert cyan.location == (5.0, 10.0, 5.0)


def test_wool_monument(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, WOOL_XML)).parse()
    cyan = next(w for w in data.wools if w.color == 'cyan')
    assert cyan.monument == (15.0, 10.0, 15.0)


# ---------------------------------------------------------------------------
# Spawners
# ---------------------------------------------------------------------------

SPAWNER_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Spawner Map</name><version>1.0</version><objective>X</objective>
    <teams><team id="red" color="dark red" max="8">Red</team></teams>
    <spawners>
        <spawner spawn-region="blue-wool-spawn" player-region="blue-woolroom"
                 delay="1.5s" max-entities="10">
            <item material="wool" damage="11" amount="1"/>
        </spawner>
        <spawner spawn-region="no-player"/>
    </spawners>
    </map>
    """


def test_spawner_parsed(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWNER_XML)).parse()
    assert len(data.spawners) == 1


def test_spawner_regions(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWNER_XML)).parse()
    s = data.spawners[0]
    assert s.spawn_region == 'blue-wool-spawn'
    assert s.player_region == 'blue-woolroom'


def test_spawner_delay_max_entities(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWNER_XML)).parse()
    s = data.spawners[0]
    assert s.delay == '1.5s'
    assert s.max_entities == 10


def test_spawner_items(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWNER_XML)).parse()
    items = data.spawners[0].items
    assert len(items) == 1
    assert items[0].material == 'wool'
    assert items[0].damage == 11


def test_spawner_missing_player_region_skipped(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, SPAWNER_XML)).parse()
    assert len(data.spawners) == 1  # the one without player-region is skipped


# ---------------------------------------------------------------------------
# Renewables
# ---------------------------------------------------------------------------

RENEWABLE_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Renewable Map</name><version>1.0</version><objective>X</objective>
    <teams><team id="red" color="dark red" max="8">Red</team></teams>
    <renewables>
        <renewable region="spawn-area" rate="2.0" renew-filter="only-iron"
                   replace-filter="only-air"/>
        <renewable region="grow-zone" grow="true"/>
        <renewable/>
    </renewables>
    </map>
    """


def test_renewable_parsed(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, RENEWABLE_XML)).parse()
    assert len(data.renewables) == 2


def test_renewable_fields(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, RENEWABLE_XML)).parse()
    r = next(r for r in data.renewables if r.region_id == 'spawn-area')
    assert r.rate == 2.0
    assert r.renew_filter == 'only-iron'
    assert r.replace_filter == 'only-air'
    assert r.grow is False


def test_renewable_grow(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, RENEWABLE_XML)).parse()
    r = next(r for r in data.renewables if r.region_id == 'grow-zone')
    assert r.grow is True
    assert r.rate == 1.0  # default


def test_renewable_without_region_skipped(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, RENEWABLE_XML)).parse()
    assert len(data.renewables) == 2  # third one (no region) is skipped


# ---------------------------------------------------------------------------
# Block-drop rules
# ---------------------------------------------------------------------------

BLOCK_DROP_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Block Drop Map</name><version>1.0</version><objective>X</objective>
    <teams><team id="red" color="dark red" max="8">Red</team></teams>
    <block-drops>
        <rule region="mining-area" filter="only-iron" wrong-tool="true">
            <replacement>air</replacement>
            <drops>
                <item material="iron ingot" chance="0.5"/>
                <item material="iron nugget" amount="3"/>
            </drops>
        </rule>
    </block-drops>
    </map>
    """


def test_block_drop_rule_parsed(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, BLOCK_DROP_XML)).parse()
    assert len(data.block_drop_rules) == 1


def test_block_drop_rule_fields(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, BLOCK_DROP_XML)).parse()
    r = data.block_drop_rules[0]
    assert r.region_id == 'mining-area'
    assert r.filter_id == 'only-iron'
    assert r.wrong_tool is True
    assert r.replacement == 'air'


def test_block_drop_items(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, BLOCK_DROP_XML)).parse()
    items = data.block_drop_rules[0].items
    assert len(items) == 2
    ingot = next(i for i in items if i.material == 'iron ingot')
    assert ingot.chance == pytest.approx(0.5)
    nugget = next(i for i in items if i.material == 'iron nugget')
    assert nugget.amount == 3


# ---------------------------------------------------------------------------
# Apply rules
# ---------------------------------------------------------------------------

APPLY_XML = """\
    <?xml version="1.0"?>
    <map proto="1.5.0">
    <name>Apply Map</name><version>1.0</version><objective>X</objective>
    <teams><team id="red" color="dark red" max="8">Red</team></teams>
    <regions>
        <rectangle id="spawn-area" min="-10,-10" max="10,10"/>
        <apply region="spawn-area" block-place="only-iron" block-break="deny-all"
               message="No editing spawn!"/>
        <apply region="global-area" block="deny-all"/>
    </regions>
    </map>
    """


def test_apply_rules_parsed(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, APPLY_XML)).parse()
    assert len(data.apply_rules) == 2


def test_apply_rule_region_and_filters(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, APPLY_XML)).parse()
    r = next(r for r in data.apply_rules if r.region_id == 'spawn-area')
    assert r.block_place_filter == 'only-iron'
    assert r.block_break_filter == 'deny-all'
    assert r.message == 'No editing spawn!'


def test_apply_rule_block_combined_filter(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, APPLY_XML)).parse()
    r = next(r for r in data.apply_rules if r.region_id == 'global-area')
    assert r.block_filter == 'deny-all'


# ---------------------------------------------------------------------------
# Max build height
# ---------------------------------------------------------------------------

def test_max_build_height(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <maxbuildheight>32</maxbuildheight>
        </map>
        """
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    assert data.max_build_height == 32


def test_max_build_height_absent(tmp_path):
    data = MapXmlParser(_write_xml(tmp_path, MINIMAL_XML)).parse()
    assert data.max_build_height is None


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------

def test_authors_parsed(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <authors>
            <author uuid="fe3608b7-1234-5678-9abc-def012345678"/>
            <author uuid="e2d2c2c6-1234-5678-9abc-def012345678" contribution="xml"/>
        </authors>
        <contributors>
            <contributor uuid="aabbccdd-1234-5678-9abc-def012345678" contribution="terrain"/>
        </contributors>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        </map>
        """
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    assert len(data.authors) == 3
    roles = [a.role for a in data.authors]
    assert roles.count('author') == 2
    assert roles.count('contributor') == 1
    contrib = next(a for a in data.authors if a.role == 'contributor')
    assert contrib.contribution == 'terrain'


# ---------------------------------------------------------------------------
# Regions in MapXml
# ---------------------------------------------------------------------------

def test_regions_flat_dict(tmp_path):
    xml = """\
        <?xml version="1.0"?>
        <map proto="1.5.0">
        <name>X</name><version>1.0</version><objective>X</objective>
        <teams><team id="red" color="dark red" max="8">Red</team></teams>
        <regions>
            <rectangle id="red-spawn" min="-10,-10" max="10,10"/>
            <union id="wool-rooms">
                <rectangle id="red-wool-room" min="0,0" max="5,5"/>
                <rectangle id="blue-wool-room" min="-5,-5" max="0,0"/>
            </union>
        </regions>
        </map>
        """
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    assert 'red-spawn' in data.regions
    assert 'wool-rooms' in data.regions
    assert 'red-wool-room' in data.regions
    assert 'blue-wool-room' in data.regions


def test_union_children_are_strings_in_mapxml(tmp_path):
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
    data = MapXmlParser(_write_xml(tmp_path, xml)).parse()
    u = data.regions['u']
    assert isinstance(u.children, list)
    assert all(isinstance(c, str) for c in u.children)


# ---------------------------------------------------------------------------
# Real map: Tumbleweed (integration smoke test)
# ---------------------------------------------------------------------------

TUMBLEWEED_PATH = Path('/media/sf_repos/CommunityMaps/ctw/tumbleweed/map.xml')


@pytest.mark.skipif(not TUMBLEWEED_PATH.exists(), reason="Tumbleweed map not available")
def test_tumbleweed_basic(tmp_path):
    data = MapXmlParser(str(TUMBLEWEED_PATH)).parse()
    assert data.name == "Tumbleweed"
    assert len(data.teams) == 2
    assert len(data.wools) == 4
    assert data.max_build_height == 29


@pytest.mark.skipif(not TUMBLEWEED_PATH.exists(), reason="Tumbleweed map not available")
def test_tumbleweed_regions_flat(tmp_path):
    data = MapXmlParser(str(TUMBLEWEED_PATH)).parse()
    assert len(data.regions) > 0
    for region in data.regions.values():
        if hasattr(region, 'children'):
            assert all(isinstance(c, str) for c in region.children)
