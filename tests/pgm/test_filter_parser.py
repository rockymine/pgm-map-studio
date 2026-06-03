"""Tests for pgm_map_studio.pgm.filter_parser."""

import xml.etree.ElementTree as ET
import pytest

from pgm_map_studio.pgm.filter_parser import FilterParser, is_shorthand
from pgm_map_studio.pgm.filters import (
    AllFilter, AnyFilter, OneFilter,
    NotFilter, DenyFilter, AllowFilter,
    TeamFilter, MaterialFilter, VoidFilter, CauseFilter,
    BlocksFilter, CarryingFilter, WearingFilter, HoldingFilter,
    AliveFilter, ParticipatingFilter, ObservingFilter,
    MatchRunningFilter, MatchStartedFilter,
    NeverFilter, AlwaysFilter,
    TimeFilter, AfterFilter, PulseFilter,
    OffsetFilter, VariableFilter,
    CompletedFilter, ObjectiveFilter, FilterRef,
    KillStreakFilter, ClassFilter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(xml_str: str) -> dict:
    root = ET.fromstring(f"<filters>{xml_str}</filters>")
    return FilterParser().parse_filters_elem(root)


# ---------------------------------------------------------------------------
# Leaf filters
# ---------------------------------------------------------------------------

def test_team_filter():
    reg = _parse('<team id="only-blue">blue-team</team>')
    assert 'only-blue' in reg
    f = reg['only-blue']
    assert isinstance(f, TeamFilter)
    assert f.team == 'blue-team'
    assert f.filter_type == 'team'


def test_team_filter_whitespace():
    reg = _parse('<team id="t">  red-team  </team>')
    assert reg['t'].team == 'red-team'


def test_material_filter():
    reg = _parse('<material id="only-iron">iron block</material>')
    f = reg['only-iron']
    assert isinstance(f, MaterialFilter)
    assert f.material == 'iron block'


def test_material_with_damage():
    reg = _parse('<material id="m">wool:14</material>')
    assert reg['m'].material == 'wool:14'


def test_material_numeric_id():
    reg = _parse('<material id="m">35:11</material>')
    assert reg['m'].material == '35:11'


def test_void_filter():
    reg = _parse('<void id="v"/>')
    assert isinstance(reg['v'], VoidFilter)


def test_void_filter_anonymous_ignored_at_top_level():
    reg = _parse('<void/>')
    # Anonymous top-level void is not registered; only the 2 built-ins (never/always) are present
    assert 'void' not in reg
    assert len([k for k in reg if k not in ('never', 'always')]) == 0


def test_cause_player():
    reg = _parse('<cause id="c">player</cause>')
    assert isinstance(reg['c'], CauseFilter)
    assert reg['c'].cause == 'player'


def test_cause_world():
    reg = _parse('<cause id="c">world</cause>')
    assert reg['c'].cause == 'world'


def test_cause_explosion():
    reg = _parse('<cause id="c">explosion</cause>')
    assert reg['c'].cause == 'explosion'


def test_alive_filter():
    reg = _parse('<alive id="alive"/>')
    assert isinstance(reg['alive'], AliveFilter)


def test_match_running_filter():
    reg = _parse('<match-running id="running"/>')
    assert isinstance(reg['running'], MatchRunningFilter)


def test_match_started_filter():
    reg = _parse('<match-started id="s"/>')
    assert isinstance(reg['s'], MatchStartedFilter)


def test_participating_filter():
    reg = _parse('<participating id="p"/>')
    assert isinstance(reg['p'], ParticipatingFilter)


def test_observing_filter():
    reg = _parse('<observing id="o"/>')
    assert isinstance(reg['o'], ObservingFilter)


def test_never_filter():
    reg = _parse('<never id="deny-all"/>')
    assert isinstance(reg['deny-all'], NeverFilter)


def test_always_filter():
    reg = _parse('<always id="allow-all"/>')
    assert isinstance(reg['allow-all'], AlwaysFilter)


def test_time_filter():
    reg = _parse('<time id="t">20m</time>')
    f = reg['t']
    assert isinstance(f, TimeFilter)
    assert f.duration == '20m'


def test_completed_filter():
    reg = _parse('<completed id="c">lime-wool</completed>')
    f = reg['c']
    assert isinstance(f, CompletedFilter)
    assert f.objective == 'lime-wool'


def test_objective_filter_legacy():
    reg = _parse('<objective id="o">centre-hub</objective>')
    f = reg['o']
    assert isinstance(f, ObjectiveFilter)
    assert f.objective == 'centre-hub'


def test_variable_filter():
    reg = _parse('<variable id="v" var="speed_upgrade_variable">1</variable>')
    f = reg['v']
    assert isinstance(f, VariableFilter)
    assert f.var == 'speed_upgrade_variable'
    assert f.value == '1'


def test_variable_with_team():
    reg = _parse('<variable id="v" var="fatigue" team="red-team">1</variable>')
    assert reg['v'].team == 'red-team'


def test_kill_streak_filter():
    reg = _parse('<kill-streak id="k" min="5" max="10"/>')
    f = reg['k']
    assert isinstance(f, KillStreakFilter)
    assert f.min == 5
    assert f.max == 10


def test_class_filter():
    reg = _parse('<class id="c">archer</class>')
    f = reg['c']
    assert isinstance(f, ClassFilter)
    assert f.name == 'archer'


# ---------------------------------------------------------------------------
# Combiners — children as ID strings
# ---------------------------------------------------------------------------

def test_all_filter_children_are_strings():
    reg = _parse('''
        <all id="iron-cause-world">
            <material id="only-iron">iron block</material>
            <cause id="by-world">world</cause>
        </all>
    ''')
    f = reg['iron-cause-world']
    assert isinstance(f, AllFilter)
    assert isinstance(f.children, list)
    assert all(isinstance(c, str) for c in f.children)
    assert 'only-iron' in f.children
    assert 'by-world' in f.children


def test_any_filter():
    reg = _parse('''
        <any id="deny-wools">
            <material>wool:0</material>
            <material>wool:14</material>
        </any>
    ''')
    f = reg['deny-wools']
    assert isinstance(f, AnyFilter)
    assert len(f.children) == 2


def test_one_filter():
    reg = _parse('''
        <one id="exactly-one">
            <team>red-team</team>
            <team>blue-team</team>
        </one>
    ''')
    assert isinstance(reg['exactly-one'], OneFilter)
    assert len(reg['exactly-one'].children) == 2


def test_all_children_registered_in_flat_registry():
    reg = _parse('''
        <all id="combo">
            <team id="only-red">red-team</team>
            <material id="only-iron">iron block</material>
        </all>
    ''')
    assert 'combo' in reg
    assert 'only-red' in reg
    assert 'only-iron' in reg


def test_deeply_nested_ids_all_registered():
    reg = _parse('''
        <all id="outer">
            <any id="inner">
                <not id="not-blue">
                    <team id="only-blue">blue-team</team>
                </not>
                <material id="only-air">air</material>
            </any>
        </all>
    ''')
    for rid in ('outer', 'inner', 'not-blue', 'only-blue', 'only-air'):
        assert rid in reg, f"Missing: {rid}"


def test_all_id_uniqueness():
    reg = _parse('''
        <all id="a">
            <team id="t1">red-team</team>
            <team id="t2">blue-team</team>
        </all>
        <any id="b">
            <material id="m1">iron block</material>
        </any>
    ''')
    ids = list(reg.keys())
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Single-child wrappers
# ---------------------------------------------------------------------------

def test_not_filter_wraps_single_child():
    reg = _parse('''
        <not id="not-blue">
            <team id="only-blue">blue-team</team>
        </not>
    ''')
    f = reg['not-blue']
    assert isinstance(f, NotFilter)
    assert isinstance(f.child, str)
    assert f.child == 'only-blue'


def test_deny_filter_wraps_any():
    reg = _parse('''
        <deny id="deny-redstone">
            <any id="redstone-types">
                <material>redstone wire</material>
                <material>redstone lamp on</material>
            </any>
        </deny>
    ''')
    assert isinstance(reg['deny-redstone'], DenyFilter)
    assert reg['deny-redstone'].child == 'redstone-types'


def test_allow_filter():
    reg = _parse('''
        <allow id="allow-iron">
            <material>iron block</material>
        </allow>
    ''')
    assert isinstance(reg['allow-iron'], AllowFilter)
    assert reg['allow-iron'].child != ''


def test_not_anonymous_child_gets_synthetic_id():
    reg = _parse('''
        <not id="not-void">
            <void/>
        </not>
    ''')
    f = reg['not-void']
    assert f.child != ''
    assert f.child in reg


# ---------------------------------------------------------------------------
# BlocksFilter
# ---------------------------------------------------------------------------

def test_blocks_filter():
    reg = _parse('''
        <blocks id="wr-filter" region="woolrooms">
            <any id="wr-materials">
                <material>web</material>
                <material>wood:0</material>
            </any>
        </blocks>
    ''')
    f = reg['wr-filter']
    assert isinstance(f, BlocksFilter)
    assert f.region == 'woolrooms'
    assert f.child == 'wr-materials'


def test_blocks_filter_nested_not():
    reg = _parse('''
        <blocks id="only-wool-room" region="wool-room-blocks">
            <not id="not-breakable">
                <any>
                    <material>air</material>
                    <material>chest</material>
                </any>
            </not>
        </blocks>
    ''')
    f = reg['only-wool-room']
    assert f.region == 'wool-room-blocks'
    assert f.child == 'not-breakable'


def test_deny_wrapping_blocks():
    reg = _parse('''
        <deny id="woolrooms-break-filter">
            <blocks id="wr-blocks" region="blocks-region">
                <not>
                    <any>
                        <material>air</material>
                        <material>iron block</material>
                    </any>
                </not>
            </blocks>
        </deny>
    ''')
    assert 'woolrooms-break-filter' in reg
    assert 'wr-blocks' in reg
    deny = reg['woolrooms-break-filter']
    assert deny.child == 'wr-blocks'


# ---------------------------------------------------------------------------
# Carrying / Wearing / Holding
# ---------------------------------------------------------------------------

def test_carrying_filter():
    reg = _parse('''
        <carrying id="carrying-wool">
            <item material="wool" damage="5"/>
        </carrying>
    ''')
    f = reg['carrying-wool']
    assert isinstance(f, CarryingFilter)
    assert f.material == 'wool'
    assert f.damage == 5


def test_carrying_ignore_metadata():
    reg = _parse('''
        <carrying id="c" ignore-metadata="true">
            <item material="gold pickaxe"/>
        </carrying>
    ''')
    assert reg['c'].ignore_metadata is True


def test_carrying_ignore_durability_false():
    reg = _parse('''
        <carrying id="c" ignore-durability="false">
            <item material="sword"/>
        </carrying>
    ''')
    assert reg['c'].ignore_durability is False


def test_wearing_filter():
    reg = _parse('''
        <wearing id="w" ignore-metadata="true">
            <item material="iron helmet"/>
        </wearing>
    ''')
    f = reg['w']
    assert isinstance(f, WearingFilter)
    assert f.material == 'iron helmet'


def test_holding_filter():
    reg = _parse('''
        <holding id="h">
            <item material="bow"/>
        </holding>
    ''')
    f = reg['h']
    assert isinstance(f, HoldingFilter)
    assert f.material == 'bow'


# ---------------------------------------------------------------------------
# AfterFilter / PulseFilter
# ---------------------------------------------------------------------------

def test_after_filter():
    reg = _parse('<after id="lime-seal-broke" filter="lime-seal-broke-filter" duration="0.5s"/>')
    f = reg['lime-seal-broke']
    assert isinstance(f, AfterFilter)
    assert f.filter_ref == 'lime-seal-broke-filter'
    assert f.duration == '0.5s'


def test_pulse_filter():
    reg = _parse('<pulse id="p" period="0.1s" duration="0.05s"/>')
    f = reg['p']
    assert isinstance(f, PulseFilter)
    assert f.period == '0.1s'
    assert f.duration == '0.05s'


def test_pulse_with_filter_ref():
    reg = _parse('<pulse id="p" period="5s" duration="1s" filter="some-filter"/>')
    assert reg['p'].filter_ref == 'some-filter'


# ---------------------------------------------------------------------------
# OffsetFilter
# ---------------------------------------------------------------------------

def test_offset_filter_relative():
    reg = _parse('''
        <offset id="below" vector="~0,~-1,~0">
            <material>air</material>
        </offset>
    ''')
    f = reg['below']
    assert isinstance(f, OffsetFilter)
    assert f.vector == '~0,~-1,~0'
    assert f.child in reg
    assert isinstance(reg[f.child], MaterialFilter)


def test_offset_filter_absolute():
    reg = _parse('''
        <offset id="o" vector="0,74,0">
            <material>air</material>
        </offset>
    ''')
    assert reg['o'].vector == '0,74,0'


def test_all_using_offset():
    reg = _parse('''
        <all id="gapple-seal-broke">
            <offset id="gapple-offset" vector="0,74,0">
                <material>air</material>
            </offset>
        </all>
    ''')
    assert 'gapple-seal-broke' in reg
    assert 'gapple-offset' in reg


# ---------------------------------------------------------------------------
# FilterRef — reference, not definition
# ---------------------------------------------------------------------------

def test_filter_ref_not_registered():
    reg = _parse('''
        <all id="combo">
            <team id="only-red">red-team</team>
            <filter id="woolrooms-filter"/>
        </all>
    ''')
    # FilterRef itself should not be in registry
    # but its ref_id is used in combo's children list
    combo = reg['combo']
    assert 'woolrooms-filter' in combo.children
    # woolrooms-filter is NOT in registry (it's just referenced, not defined here)
    assert 'woolrooms-filter' not in reg


# ---------------------------------------------------------------------------
# Synthetic IDs for anonymous elements
# ---------------------------------------------------------------------------

def test_anonymous_combiner_child_gets_synthetic_id():
    reg = _parse('''
        <all id="parent">
            <any>
                <material>web</material>
                <cause>world</cause>
            </any>
        </all>
    ''')
    parent = reg['parent']
    assert len(parent.children) == 1
    anon_id = parent.children[0]
    assert anon_id.startswith('parent__anon_')
    assert anon_id in reg
    assert isinstance(reg[anon_id], AnyFilter)


def test_synthetic_id_stability():
    xml = '''
        <all id="combo">
            <not id="not-blue">
                <team id="only-blue">blue-team</team>
            </not>
            <filter id="wr-filter"/>
        </all>
    '''
    reg1 = _parse(xml)
    reg2 = _parse(xml)
    assert list(reg1.keys()) == list(reg2.keys())


def test_synthetic_id_uniqueness():
    reg = _parse('''
        <any id="outer">
            <all id="inner-a">
                <material>air</material>
                <void/>
            </all>
            <all id="inner-b">
                <material>water</material>
            </all>
        </any>
    ''')
    ids = list(reg.keys())
    assert len(ids) == len(set(ids))


def test_no_inline_marker_in_ids():
    reg = _parse('''
        <all id="parent">
            <any>
                <material>air</material>
            </any>
        </all>
    ''')
    for rid in reg:
        assert '(inline)' not in rid


# ---------------------------------------------------------------------------
# Complex realistic patterns from CTW maps
# ---------------------------------------------------------------------------

def test_tumbleweed_filters():
    """Tumbleweed's filter block."""
    reg = _parse('''
        <deny id="deny-chest">
            <material>chest</material>
        </deny>
        <team id="only-blue">blue</team>
        <team id="only-red">red</team>
        <all id="only-iron-regen">
            <material id="only-iron">iron block</material>
            <cause>world</cause>
        </all>
    ''')
    assert isinstance(reg['deny-chest'], DenyFilter)
    assert isinstance(reg['only-blue'], TeamFilter)
    assert isinstance(reg['only-red'], TeamFilter)
    regen = reg['only-iron-regen']
    assert isinstance(regen, AllFilter)
    assert 'only-iron' in regen.children
    assert isinstance(reg['only-iron'], MaterialFilter)


def test_outback_void_block_pattern():
    """Outback's complex void + block material filter."""
    reg = _parse('''
        <any id="block-break-void-filter">
            <all id="void-leaves-all">
                <any id="void-materials">
                    <material>leaves</material>
                    <material>log</material>
                </any>
                <void/>
            </all>
            <not id="block-place-void-filter">
                <void/>
            </not>
        </any>
    ''')
    outer = reg['block-break-void-filter']
    assert isinstance(outer, AnyFilter)
    assert 'void-leaves-all' in outer.children
    assert 'block-place-void-filter' in outer.children

    inner = reg['void-leaves-all']
    assert isinstance(inner, AllFilter)
    assert 'void-materials' in inner.children

    not_filter = reg['block-place-void-filter']
    assert isinstance(not_filter, NotFilter)
    assert isinstance(reg[not_filter.child], VoidFilter)


def test_annealing_woolrooms_filter():
    """Annealing IV's team-specific woolroom filter with nested not."""
    reg = _parse('''
        <all id="blues-woolrooms-filter">
            <not id="not-blue">
                <team id="only-blue">blue-team</team>
            </not>
            <filter id="woolrooms-filter"/>
        </all>
    ''')
    f = reg['blues-woolrooms-filter']
    assert 'not-blue' in f.children
    assert 'woolrooms-filter' in f.children

    not_blue = reg['not-blue']
    assert isinstance(not_blue, NotFilter)
    assert not_blue.child == 'only-blue'
    assert isinstance(reg['only-blue'], TeamFilter)


def test_fall_of_babylon_carrying_completed():
    """fall_of_babylon's carrying + completed combination."""
    reg = _parse('''
        <all id="lime-near-and-last">
            <carrying id="carry-lime" ignore-durability="false">
                <item material="wool" damage="5"/>
            </carrying>
            <completed>cyan-wool</completed>
        </all>
    ''')
    f = reg['lime-near-and-last']
    assert isinstance(f, AllFilter)
    assert 'carry-lime' in f.children
    carrying = reg['carry-lime']
    assert carrying.material == 'wool'
    assert carrying.damage == 5
    # The anonymous completed filter
    completed_id = next(c for c in f.children if c != 'carry-lime')
    assert isinstance(reg[completed_id], CompletedFilter)
    assert reg[completed_id].objective == 'cyan-wool'


def test_fall_of_babylon_after_offset():
    """fall_of_babylon's after + offset pattern."""
    reg = _parse('''
        <after id="lime-seal-broke" filter="lime-seal-broke-filter" duration="0.5s"/>
        <all id="lime-seal-broke-filter">
            <offset id="lime-offset" vector="-119,61,134">
                <material>air</material>
            </offset>
        </all>
    ''')
    after = reg['lime-seal-broke']
    assert after.filter_ref == 'lime-seal-broke-filter'
    combo = reg['lime-seal-broke-filter']
    assert 'lime-offset' in combo.children
    offset = reg['lime-offset']
    assert offset.vector == '-119,61,134'


def test_variable_filter_in_all():
    """Variable filter used inside all combiner."""
    reg = _parse('''
        <all id="red-speed-boost">
            <alive/>
            <team id="only-red">red-team</team>
            <variable id="speed-var" var="speed_upgrade_variable">1</variable>
        </all>
    ''')
    f = reg['red-speed-boost']
    assert 'only-red' in f.children
    assert 'speed-var' in f.children
    assert isinstance(reg['speed-var'], VariableFilter)


# ---------------------------------------------------------------------------
# is_shorthand helper
# ---------------------------------------------------------------------------

def test_is_shorthand_true():
    assert is_shorthand('deny(void)') is True
    assert is_shorthand('all(only-blue,wr-filter)') is True
    assert is_shorthand('not(spawns)') is True


def test_is_shorthand_false():
    assert is_shorthand('only-blue') is False
    assert is_shorthand('woolrooms-filter') is False
    assert is_shorthand('') is False
