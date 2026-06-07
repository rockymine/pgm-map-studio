"""Deserializer: xml_data.json dict → MapXml.

Inverse of serializer.py.  Accepts the dict produced by serializer.to_dict()
(or loaded from an xml_data.json file) and reconstructs a MapXml dataclass
suitable for passing directly to xml_writer.to_xml().

Omitted optional fields revert to dataclass defaults (same defaults used by
the serializer when omitting them).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

from .datatypes import (
    MapXml, Team, Author, Kit, KitItem, KitArmor, Spawn, Wool,
    WoolSpawner, SpawnerItem, Renewable, BlockDropRule, BlockDropItem, ApplyRule,
)
from .regions import (
    Region, Rectangle, Cuboid, Cylinder, Circle, Sphere, Block, Point,
    Union, Negative, Complement, Intersect, Mirror, Translate,
    Half, Reference, Everywhere, Above,
)
from .filters import (
    Filter, AllFilter, AnyFilter, OneFilter,
    NotFilter, DenyFilter, AllowFilter,
    TeamFilter, MaterialFilter, VoidFilter, CauseFilter,
    BlocksFilter, CarryingFilter, WearingFilter, HoldingFilter,
    AliveFilter, DeadFilter, ParticipatingFilter, ObservingFilter,
    MatchRunningFilter, MatchStartedFilter, GroundedFilter,
    NeverFilter, AlwaysFilter,
    TimeFilter, AfterFilter, PulseFilter,
    OffsetFilter, VariableFilter, CompletedFilter, ObjectiveFilter,
    KillStreakFilter, ClassFilter, RegionFilter, PlayerFilter, SpawnFilter,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def from_dict(d: dict[str, Any]) -> MapXml:
    """Reconstruct a MapXml from a JSON-serializable dict."""
    regions = {rid: _decode_region(r) for rid, r in d.get('regions', {}).items()}
    filters = {fid: _decode_filter(f) for fid, f in d.get('filters', {}).items()}

    obs_raw = d.get('observer_spawn')
    return MapXml(
        name=d.get('name', ''),
        version=d.get('version', ''),
        gamemode=d.get('gamemode', 'ctw'),
        objective=d.get('objective', ''),
        max_build_height=d.get('max_build_height'),
        authors=[_decode_author(a) for a in d.get('authors', [])],
        kits=[_decode_kit(k) for k in d.get('kits', [])],
        teams=[_decode_team(t) for t in d.get('teams', [])],
        spawns=[_decode_spawn(s, regions) for s in d.get('spawns', [])],
        observer_spawn=_decode_spawn(obs_raw, regions) if obs_raw else None,
        wools=[_decode_wool(w) for w in d.get('wools', [])],
        spawners=[_decode_spawner(s) for s in d.get('spawners', [])],
        renewables=[_decode_renewable(r) for r in d.get('renewables', [])],
        block_drop_rules=[_decode_block_drop_rule(r) for r in d.get('block_drop_rules', [])],
        filters=filters,
        regions=regions,
        apply_rules=[_decode_apply_rule(r) for r in d.get('apply_rules', [])],
    )


def from_json(json_str: str) -> MapXml:
    """Reconstruct a MapXml from a JSON string."""
    return from_dict(json.loads(json_str))


def load(path: str | Path) -> MapXml:
    """Load a MapXml from an xml_data.json file."""
    return from_dict(json.loads(Path(path).read_text()))


# ---------------------------------------------------------------------------
# Coordinate helper
# ---------------------------------------------------------------------------

def _coord(v: Any) -> float:
    if v == 'oo':
        return math.inf
    if v == '-oo':
        return -math.inf
    return float(v)


# ---------------------------------------------------------------------------
# Region decoder
# ---------------------------------------------------------------------------

def _decode_region(d: dict[str, Any]) -> Region:
    rid = d.get('id', '')
    rtype = d.get('type', '')

    if rtype == 'rectangle':
        b = d['bounds_2d']
        return Rectangle(
            id=rid,
            min_x=_coord(b['min']['x']),
            min_z=_coord(b['min']['z']),
            max_x=_coord(b['max']['x']),
            max_z=_coord(b['max']['z']),
        )

    if rtype == 'cuboid':
        mn, mx = d['min'], d['max']
        return Cuboid(
            id=rid,
            min_x=_coord(mn['x']), min_y=_coord(mn['y']), min_z=_coord(mn['z']),
            max_x=_coord(mx['x']), max_y=_coord(mx['y']), max_z=_coord(mx['z']),
        )

    if rtype == 'cylinder':
        base = d['base']
        return Cylinder(
            id=rid,
            base_x=_coord(base['x']),
            base_y=_coord(base['y']),
            base_z=_coord(base['z']),
            radius=_coord(d['radius']),
            height=_coord(d['height']) if 'height' in d else None,
        )

    if rtype == 'circle':
        c = d['center']
        return Circle(
            id=rid,
            center_x=_coord(c['x']),
            center_z=_coord(c['z']),
            radius=_coord(d['radius']),
        )

    if rtype == 'sphere':
        o = d['origin']
        return Sphere(
            id=rid,
            origin_x=_coord(o['x']),
            origin_y=_coord(o['y']),
            origin_z=_coord(o['z']),
            radius=_coord(d['radius']),
        )

    if rtype in ('block', 'point'):
        p = d['position']
        cls = Block if rtype == 'block' else Point
        return cls(id=rid, x=_coord(p['x']), y=_coord(p['y']), z=_coord(p['z']))

    if rtype in ('union', 'negative', 'complement', 'intersect'):
        cls = {'union': Union, 'negative': Negative,
               'complement': Complement, 'intersect': Intersect}[rtype]
        return cls(id=rid, children=list(d.get('children', [])))

    if rtype == 'mirror':
        o, n = d['origin'], d['normal']
        return Mirror(
            id=rid,
            source_id=d.get('source_id', ''),
            origin_x=_coord(o['x']), origin_y=_coord(o['y']), origin_z=_coord(o['z']),
            normal_x=_coord(n['x']), normal_y=_coord(n['y']), normal_z=_coord(n['z']),
        )

    if rtype == 'translate':
        off = d['offset']
        return Translate(
            id=rid,
            source_id=d.get('source_id', ''),
            offset_x=_coord(off['x']),
            offset_y=_coord(off['y']),
            offset_z=_coord(off['z']),
        )

    if rtype == 'half':
        o, n = d['origin'], d['normal']
        return Half(
            id=rid,
            origin_x=_coord(o['x']), origin_y=_coord(o['y']), origin_z=_coord(o['z']),
            normal_x=_coord(n['x']), normal_y=_coord(n['y']), normal_z=_coord(n['z']),
        )

    if rtype == 'reference':
        return Reference(id=rid, ref_id=d.get('ref_id', ''))

    if rtype == 'everywhere':
        return Everywhere(id=rid)

    if rtype == 'above':
        return Above(id=rid, y=_coord(d['y']))

    # Unknown type — return bare Region so the registry stays intact
    return Region(id=rid, region_type=rtype)


# ---------------------------------------------------------------------------
# Filter decoder
# ---------------------------------------------------------------------------

def _decode_filter(d: dict[str, Any]) -> Filter:
    fid = d.get('id', '')
    ftype = d.get('type', '')

    if ftype == 'all':
        return AllFilter(id=fid, children=list(d.get('children', [])))
    if ftype == 'any':
        return AnyFilter(id=fid, children=list(d.get('children', [])))
    if ftype == 'one':
        return OneFilter(id=fid, children=list(d.get('children', [])))

    if ftype == 'not':
        return NotFilter(id=fid, child=d.get('child', ''))
    if ftype == 'deny':
        return DenyFilter(id=fid, child=d.get('child', ''))
    if ftype == 'allow':
        return AllowFilter(id=fid, child=d.get('child', ''))

    if ftype == 'team':
        return TeamFilter(id=fid, team=d.get('team', ''))
    if ftype == 'material':
        return MaterialFilter(id=fid, material=d.get('material', ''))
    if ftype == 'void':
        return VoidFilter(id=fid)
    if ftype == 'cause':
        return CauseFilter(id=fid, cause=d.get('cause', ''))

    if ftype == 'blocks':
        return BlocksFilter(id=fid, region=d.get('region', ''), child=d.get('child', ''))

    if ftype == 'carrying':
        return CarryingFilter(
            id=fid,
            material=d.get('material', ''),
            damage=d.get('damage'),
            enchantments=d.get('enchantments', ''),
            ignore_metadata=d.get('ignore_metadata', False),
            ignore_durability=d.get('ignore_durability', True),
        )
    if ftype == 'wearing':
        return WearingFilter(
            id=fid,
            material=d.get('material', ''),
            damage=d.get('damage'),
            ignore_metadata=d.get('ignore_metadata', False),
        )
    if ftype == 'holding':
        return HoldingFilter(
            id=fid,
            material=d.get('material', ''),
            damage=d.get('damage'),
        )

    _SIMPLE: dict[str, type] = {
        'alive': AliveFilter, 'dead': DeadFilter,
        'participating': ParticipatingFilter, 'observing': ObservingFilter,
        'match-running': MatchRunningFilter, 'match-started': MatchStartedFilter,
        'grounded': GroundedFilter, 'never': NeverFilter, 'always': AlwaysFilter,
    }
    if ftype in _SIMPLE:
        return _SIMPLE[ftype](id=fid)

    if ftype == 'time':
        return TimeFilter(id=fid, duration=d.get('duration', ''))
    if ftype == 'after':
        return AfterFilter(
            id=fid,
            filter_ref=d.get('filter', ''),
            duration=d.get('duration', ''),
        )
    if ftype == 'pulse':
        return PulseFilter(
            id=fid,
            period=d.get('period', ''),
            duration=d.get('duration', ''),
            filter_ref=d.get('filter', ''),
        )
    if ftype == 'offset':
        return OffsetFilter(id=fid, vector=d.get('vector', ''), child=d.get('child', ''))

    if ftype == 'variable':
        return VariableFilter(
            id=fid,
            var=d.get('var', ''),
            value=d.get('value', ''),
            team=d.get('team', ''),
        )
    if ftype == 'completed':
        return CompletedFilter(id=fid, objective=d.get('objective', ''))
    if ftype == 'objective':
        return ObjectiveFilter(id=fid, objective=d.get('objective', ''))

    if ftype == 'kill-streak':
        return KillStreakFilter(
            id=fid,
            min=d.get('min'),
            max=d.get('max'),
            count=d.get('count'),
        )
    if ftype == 'class':
        return ClassFilter(id=fid, name=d.get('name', ''))
    if ftype == 'region':
        return RegionFilter(id=fid, region=d.get('region', ''))
    if ftype == 'players':
        return PlayerFilter(id=fid, min=d.get('min'), max=d.get('max'))
    if ftype == 'spawn':
        return SpawnFilter(id=fid, mob=d.get('mob', ''))

    return Filter(id=fid, filter_type=ftype)


# ---------------------------------------------------------------------------
# Other decoders
# ---------------------------------------------------------------------------

def _decode_author(d: dict[str, Any]) -> Author:
    return Author(
        uuid=d.get('uuid', ''),
        role=d.get('role', 'author'),
        contribution=d.get('contribution', ''),
    )


def _decode_kit(d: dict[str, Any]) -> Kit:
    return Kit(
        id=d.get('id', ''),
        items=[_decode_kit_item(i) for i in d.get('items', [])],
        armor=[_decode_kit_armor(a) for a in d.get('armor', [])],
    )


def _decode_kit_item(d: dict[str, Any]) -> KitItem:
    return KitItem(
        slot=d.get('slot', 0),
        material=d.get('material', ''),
        amount=d.get('amount', 1),
        item_damage=d.get('damage', 0),
        unbreakable=d.get('unbreakable', False),
        team_color=d.get('team_color', False),
        enchantments=d.get('enchantments', ''),
    )


def _decode_kit_armor(d: dict[str, Any]) -> KitArmor:
    return KitArmor(
        slot_name=d.get('slot_name', ''),
        material=d.get('material', ''),
        unbreakable=d.get('unbreakable', False),
        team_color=d.get('team_color', False),
        enchantments=d.get('enchantments', ''),
    )


def _decode_team(d: dict[str, Any]) -> Team:
    return Team(
        id=d.get('id', ''),
        color=d.get('color', ''),
        max_players=d.get('max_players', 0),
        min_players=d.get('min_players', 0),
        name=d.get('name', ''),
        dye_color=d.get('dye_color', ''),
    )


def _decode_spawn(d: dict[str, Any], regions: dict[str, Region]) -> Spawn:
    region: Optional[Region] = None
    r_raw = d.get('region')
    if r_raw is not None:
        if isinstance(r_raw, str):
            region = regions.get(r_raw)
        else:
            region = _decode_region(r_raw)
    return Spawn(
        team=d.get('team', ''),
        kit=d.get('kit', ''),
        yaw=float(d.get('yaw', 0.0)),
        region=region,
    )


def _decode_wool(d: dict[str, Any]) -> Wool:
    loc = d['location']
    mon = d['monument']
    return Wool(
        team=d.get('team', ''),
        color=d.get('color', ''),
        location=(float(loc['x']), float(loc['y']), float(loc['z'])),
        monument=(float(mon['x']), float(mon['y']), float(mon['z'])),
        monument_region_id=mon.get('region_id'),
        wool_room_region=d.get('wool_room_region'),
    )


def _decode_spawner(d: dict[str, Any]) -> WoolSpawner:
    return WoolSpawner(
        spawn_region=d.get('spawn_region', ''),
        player_region=d.get('player_region', ''),
        delay=d.get('delay', ''),
        max_entities=d.get('max_entities'),
        items=[_decode_spawner_item(i) for i in d.get('items', [])],
    )


def _decode_spawner_item(d: dict[str, Any]) -> SpawnerItem:
    return SpawnerItem(
        material=d.get('material', ''),
        damage=d.get('damage', 0),
        amount=d.get('amount', 1),
    )


def _decode_renewable(d: dict[str, Any]) -> Renewable:
    return Renewable(
        region_id=d.get('region_id', ''),
        rate=float(d.get('rate', 1.0)),
        renew_filter=d.get('renew_filter', ''),
        replace_filter=d.get('replace_filter', ''),
        grow=d.get('grow', False),
    )


def _decode_block_drop_rule(d: dict[str, Any]) -> BlockDropRule:
    return BlockDropRule(
        region_id=d.get('region_id', ''),
        filter_id=d.get('filter_id', ''),
        replacement=d.get('replacement', ''),
        wrong_tool=d.get('wrong_tool', False),
        items=[_decode_block_drop_item(i) for i in d.get('items', [])],
    )


def _decode_block_drop_item(d: dict[str, Any]) -> BlockDropItem:
    return BlockDropItem(
        material=d.get('material', ''),
        damage=d.get('damage', 0),
        amount=d.get('amount', 1),
        chance=float(d.get('chance', 1.0)),
    )


def _decode_apply_rule(d: dict[str, Any]) -> ApplyRule:
    return ApplyRule(
        enter_filter=d.get('enter', ''),
        leave_filter=d.get('leave', ''),
        block_filter=d.get('block', ''),
        block_place_filter=d.get('block_place', ''),
        block_break_filter=d.get('block_break', ''),
        block_physics_filter=d.get('block_physics', ''),
        block_place_against_filter=d.get('block_place_against', ''),
        use_filter=d.get('use', ''),
        filter_id=d.get('filter', ''),
        region_id=d.get('region', ''),
        kit=d.get('kit', ''),
        lend_kit=d.get('lend_kit', ''),
        velocity=d.get('velocity', ''),
        message=d.get('message', ''),
    )
