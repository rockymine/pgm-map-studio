"""Serializer: MapXml → dict → xml_data.json.

Omits optional fields at their default values per legacy conventions:
- rate=1.0, grow=False, wrong_tool=False, damage=0, amount=1, chance=1.0

``region_categories`` is NOT written — the viewer computes it at load time.
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
    FilterRef, KillStreakFilter, ClassFilter, RegionFilter,
    PlayerFilter, SpawnFilter,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def to_dict(xml_data: MapXml) -> dict[str, Any]:
    """Serialize MapXml to a JSON-serializable dict."""
    return {
        'name': xml_data.name,
        'version': xml_data.version,
        'gamemode': xml_data.gamemode,
        'objective': xml_data.objective,
        'max_build_height': xml_data.max_build_height,
        'authors': [_encode_author(a) for a in xml_data.authors],
        'kits': [_encode_kit(k) for k in xml_data.kits],
        'teams': [_encode_team(t) for t in xml_data.teams],
        'spawns': [_encode_spawn(s) for s in xml_data.spawns],
        'observer_spawn': _encode_spawn(xml_data.observer_spawn) if xml_data.observer_spawn else None,
        'wools': _encode_wools_grouped(xml_data.wools),
        'spawners': [_encode_spawner(s) for s in xml_data.spawners],
        'renewables': [_encode_renewable(r) for r in xml_data.renewables],
        'block_drop_rules': [_encode_block_drop_rule(r) for r in xml_data.block_drop_rules],
        'filters': {fid: _encode_filter(f) for fid, f in xml_data.filters.items()},
        'regions': {rid: _encode_region(r) for rid, r in xml_data.regions.items()},
        'apply_rules': [_encode_apply_rule(r) for r in xml_data.apply_rules],
    }


def to_json(xml_data: MapXml, indent: int = 2) -> str:
    """Serialize MapXml to a JSON string."""
    return json.dumps(to_dict(xml_data), indent=indent, sort_keys=False)


def save(xml_data: MapXml, output_path: str | Path) -> None:
    """Write MapXml to a JSON file."""
    path = Path(output_path)
    path.write_text(to_json(xml_data))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _coord(v: Any) -> Any:
    """Convert float to JSON-safe representation (inf → "oo", -inf → "-oo")."""
    if isinstance(v, float):
        if v == math.inf:
            return "oo"
        if v == -math.inf:
            return "-oo"
    return v


def _encode_bounds_2d(b: dict) -> dict:
    return {
        'min': {'x': _coord(b['min']['x']), 'z': _coord(b['min']['z'])},
        'max': {'x': _coord(b['max']['x']), 'z': _coord(b['max']['z'])},
    }


# ---------------------------------------------------------------------------
# Region encoder
# ---------------------------------------------------------------------------

def _encode_region(region: Region) -> dict[str, Any]:
    base: dict[str, Any] = {'id': region.id, 'type': region.region_type}

    if region.bounds_2d is not None:
        base['bounds_2d'] = _encode_bounds_2d(region.bounds_2d)

    if isinstance(region, Rectangle):
        # Only bounds_2d — no raw min_x/max_x fields
        pass

    elif isinstance(region, Cuboid):
        base['min'] = {
            'x': _coord(region.min_x), 'y': _coord(region.min_y), 'z': _coord(region.min_z),
        }
        base['max'] = {
            'x': _coord(region.max_x), 'y': _coord(region.max_y), 'z': _coord(region.max_z),
        }

    elif isinstance(region, Cylinder):
        base['base'] = {
            'x': _coord(region.base_x), 'y': _coord(region.base_y), 'z': _coord(region.base_z),
        }
        base['radius'] = _coord(region.radius)
        if region.height is not None:
            base['height'] = _coord(region.height)

    elif isinstance(region, Circle):
        base['center'] = {'x': _coord(region.center_x), 'z': _coord(region.center_z)}
        base['radius'] = _coord(region.radius)

    elif isinstance(region, Sphere):
        base['origin'] = {
            'x': _coord(region.origin_x), 'y': _coord(region.origin_y), 'z': _coord(region.origin_z),
        }
        base['radius'] = _coord(region.radius)

    elif isinstance(region, (Block, Point)):
        base['position'] = {
            'x': _coord(region.x), 'y': _coord(region.y), 'z': _coord(region.z),
        }

    elif isinstance(region, (Union, Negative, Complement, Intersect)):
        base['children'] = list(region.children)

    elif isinstance(region, Half):
        base['origin'] = {
            'x': _coord(region.origin_x), 'y': _coord(region.origin_y), 'z': _coord(region.origin_z),
        }
        base['normal'] = {
            'x': _coord(region.normal_x), 'y': _coord(region.normal_y), 'z': _coord(region.normal_z),
        }

    elif isinstance(region, Mirror):
        base['source_id'] = region.source_id
        base['origin'] = {
            'x': _coord(region.origin_x), 'y': _coord(region.origin_y), 'z': _coord(region.origin_z),
        }
        base['normal'] = {
            'x': _coord(region.normal_x), 'y': _coord(region.normal_y), 'z': _coord(region.normal_z),
        }

    elif isinstance(region, Translate):
        base['source_id'] = region.source_id
        base['offset'] = {
            'x': _coord(region.offset_x), 'y': _coord(region.offset_y), 'z': _coord(region.offset_z),
        }

    elif isinstance(region, Reference):
        base['ref_id'] = region.ref_id

    elif isinstance(region, Above):
        base['y'] = _coord(region.y)

    return base


# ---------------------------------------------------------------------------
# Other encoders
# ---------------------------------------------------------------------------

def _encode_author(a: Author) -> dict[str, Any]:
    result: dict[str, Any] = {'uuid': a.uuid, 'role': a.role}
    if a.contribution:
        result['contribution'] = a.contribution
    return result


def _encode_kit(k: Kit) -> dict[str, Any]:
    return {
        'id': k.id,
        'items': [_encode_kit_item(i) for i in k.items],
        'armor': [_encode_kit_armor(a) for a in k.armor],
    }


def _encode_kit_item(item: KitItem) -> dict[str, Any]:
    result: dict[str, Any] = {'slot': item.slot, 'material': item.material}
    if item.amount != 1:
        result['amount'] = item.amount
    if item.item_damage:
        result['damage'] = item.item_damage
    if item.unbreakable:
        result['unbreakable'] = True
    if item.team_color:
        result['team_color'] = True
    if item.enchantments:
        result['enchantments'] = item.enchantments
    return result


def _encode_kit_armor(armor: KitArmor) -> dict[str, Any]:
    result: dict[str, Any] = {'slot_name': armor.slot_name, 'material': armor.material}
    if armor.unbreakable:
        result['unbreakable'] = True
    if armor.team_color:
        result['team_color'] = True
    if armor.enchantments:
        result['enchantments'] = armor.enchantments
    return result


def _encode_team(t: Team) -> dict[str, Any]:
    return {
        'id': t.id,
        'name': t.name,
        'color': t.color,
        'dye_color': t.dye_color,
        'max_players': t.max_players,
        'min_players': t.min_players,
    }


def _encode_spawn(spawn: Spawn) -> dict[str, Any]:
    result: dict[str, Any] = {
        'team': spawn.team,
        'kit': spawn.kit,
        'yaw': spawn.yaw,
    }
    if spawn.region is not None:
        # Reference the region by id into the flat registry — geometry lives once
        # in `regions`, never duplicated inline on the spawn. The id is non-empty
        # for every parsed spawn region (named or synthetic). An id-less anonymous
        # region falls back to inline so geometry is never lost.
        result['region'] = spawn.region.id if spawn.region.id else _encode_region(spawn.region)
    return result


def _wool_slug(value: str) -> str:
    """Normalize a wool color or team into a stable id slug."""
    return str(value).strip().lower().replace(" ", "_")


def _encode_wools_grouped(wools: list[Wool]) -> list[dict[str, Any]]:
    """Serialize wools grouped by color into the studio's canonical format:
    [{id, color, location, wool_room_region, monuments: [{id, team, location, monument_region}]}].

    IDs are deterministic from content so they stay stable across round-trips:
    the wool group id is the color slug; a monument id is ``<color-slug>-<team-slug>``.
    The inverse lives in ``deserializer._decode_wools_entry``.
    """
    by_color: dict[str, dict[str, Any]] = {}
    for w in wools:
        cslug = _wool_slug(w.color)
        if w.color not in by_color:
            by_color[w.color] = {
                'id':               cslug,
                'color':            w.color,
                'location':         {'x': w.location[0], 'y': w.location[1], 'z': w.location[2]},
                'wool_room_region': w.wool_room_region,
                'monuments':        [],
            }
        by_color[w.color]['monuments'].append({
            'id':              f"{cslug}-{_wool_slug(w.team)}",
            'team':            w.team,
            'location':        {'x': w.monument[0], 'y': w.monument[1], 'z': w.monument[2]},
            'monument_region': w.monument_region_id,
        })
    return list(by_color.values())


def _encode_spawner(s: WoolSpawner) -> dict[str, Any]:
    result: dict[str, Any] = {
        'spawn_region': s.spawn_region,
        'player_region': s.player_region,
    }
    if s.delay:
        result['delay'] = s.delay
    if s.max_entities is not None:
        result['max_entities'] = s.max_entities
    if s.items:
        result['items'] = [_encode_spawner_item(i) for i in s.items]
    return result


def _encode_spawner_item(item: SpawnerItem) -> dict[str, Any]:
    result: dict[str, Any] = {'material': item.material}
    if item.damage:
        result['damage'] = item.damage
    if item.amount != 1:
        result['amount'] = item.amount
    return result


def _encode_renewable(r: Renewable) -> dict[str, Any]:
    result: dict[str, Any] = {'region_id': r.region_id}
    if r.rate != 1.0:
        result['rate'] = r.rate
    if r.renew_filter:
        result['renew_filter'] = r.renew_filter
    if r.replace_filter:
        result['replace_filter'] = r.replace_filter
    if r.grow:
        result['grow'] = True
    return result


def _encode_block_drop_rule(r: BlockDropRule) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if r.region_id:
        result['region_id'] = r.region_id
    if r.filter_id:
        result['filter_id'] = r.filter_id
    if r.replacement:
        result['replacement'] = r.replacement
    if r.wrong_tool:
        result['wrong_tool'] = True
    if r.items:
        result['items'] = [_encode_block_drop_item(i) for i in r.items]
    return result


def _encode_block_drop_item(item: BlockDropItem) -> dict[str, Any]:
    result: dict[str, Any] = {'material': item.material}
    if item.damage:
        result['damage'] = item.damage
    if item.amount != 1:
        result['amount'] = item.amount
    if item.chance != 1.0:
        result['chance'] = item.chance
    return result


def _encode_apply_rule(r: ApplyRule) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if r.enter_filter:
        result['enter'] = r.enter_filter
    if r.leave_filter:
        result['leave'] = r.leave_filter
    if r.block_filter:
        result['block'] = r.block_filter
    if r.block_place_filter:
        result['block_place'] = r.block_place_filter
    if r.block_break_filter:
        result['block_break'] = r.block_break_filter
    if r.block_physics_filter:
        result['block_physics'] = r.block_physics_filter
    if r.block_place_against_filter:
        result['block_place_against'] = r.block_place_against_filter
    if r.use_filter:
        result['use'] = r.use_filter
    if r.filter_id:
        result['filter'] = r.filter_id
    if r.region_id:
        result['region'] = r.region_id
    if r.kit:
        result['kit'] = r.kit
    if r.lend_kit:
        result['lend_kit'] = r.lend_kit
    if r.velocity:
        result['velocity'] = r.velocity
    if r.message:
        result['message'] = r.message
    return result


# ---------------------------------------------------------------------------
# Filter encoder
# ---------------------------------------------------------------------------

def _encode_filter(f: Filter) -> dict[str, Any]:
    """Serialize a Filter to a JSON-serializable dict."""
    base: dict[str, Any] = {'id': f.id, 'type': f.filter_type}

    if isinstance(f, (AllFilter, AnyFilter, OneFilter)):
        base['children'] = list(f.children)

    elif isinstance(f, (NotFilter, DenyFilter, AllowFilter)):
        base['child'] = f.child

    elif isinstance(f, TeamFilter):
        base['team'] = f.team

    elif isinstance(f, MaterialFilter):
        base['material'] = f.material

    elif isinstance(f, CauseFilter):
        base['cause'] = f.cause

    elif isinstance(f, BlocksFilter):
        base['region'] = f.region
        base['child'] = f.child

    elif isinstance(f, CarryingFilter):
        base['material'] = f.material
        if f.damage is not None:
            base['damage'] = f.damage
        if f.enchantments:
            base['enchantments'] = f.enchantments
        if f.ignore_metadata:
            base['ignore_metadata'] = True
        if not f.ignore_durability:
            base['ignore_durability'] = False

    elif isinstance(f, WearingFilter):
        base['material'] = f.material
        if f.damage is not None:
            base['damage'] = f.damage
        if f.ignore_metadata:
            base['ignore_metadata'] = True

    elif isinstance(f, HoldingFilter):
        base['material'] = f.material
        if f.damage is not None:
            base['damage'] = f.damage

    elif isinstance(f, TimeFilter):
        base['duration'] = f.duration

    elif isinstance(f, AfterFilter):
        if f.filter_ref:
            base['filter'] = f.filter_ref
        base['duration'] = f.duration

    elif isinstance(f, PulseFilter):
        base['period'] = f.period
        base['duration'] = f.duration
        if f.filter_ref:
            base['filter'] = f.filter_ref

    elif isinstance(f, OffsetFilter):
        base['vector'] = f.vector
        base['child'] = f.child

    elif isinstance(f, VariableFilter):
        base['var'] = f.var
        base['value'] = f.value
        if f.team:
            base['team'] = f.team

    elif isinstance(f, (CompletedFilter, ObjectiveFilter)):
        base['objective'] = f.objective

    elif isinstance(f, KillStreakFilter):
        if f.min is not None:
            base['min'] = f.min
        if f.max is not None:
            base['max'] = f.max
        if f.count is not None:
            base['count'] = f.count

    elif isinstance(f, ClassFilter):
        base['name'] = f.name

    elif isinstance(f, RegionFilter):
        base['region'] = f.region

    elif isinstance(f, PlayerFilter):
        if f.min is not None:
            base['min'] = f.min
        if f.max is not None:
            base['max'] = f.max

    elif isinstance(f, SpawnFilter):
        if f.mob:
            base['mob'] = f.mob

    return base
