"""Persisted models (B1) — the on-disk `xml_data.json` shape.

Typed code-first against the real corpus (validated by `tools/validate_schemas.py`
over all 345 maps), so these accept what the pipeline actually writes:
- most entity fields are omitted when default → modelled `Optional`;
- coordinate components can be `None` (PGM template variables `${…}`);
- `spawn.region` is a string id **or** an inline region dict;
- region/filter fields vary by `type` → one permissive model each (extra fields
  ignored rather than rejected — the codec, not this layer, owns round-trip).

Bounds here keep the nested parser form `{min:{x,z},max:{x,z}}`; the **view**
layer (`view.Bounds`) is the canonical flat `{min_x,…}` the wire/frontend use.
"""
from __future__ import annotations

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    # tolerate not-yet-typed fields (e.g. advanced filter leaf params) instead of
    # rejecting them — the persisted layer is permissive; the codec owns round-trip.
    model_config = ConfigDict(extra="ignore")


# A persisted coordinate value: a number, a PGM literal string (`"oo"`/`"-oo"`
# for infinity), or `None` (a `${template}` variable).
Coord = Optional[Union[float, str]]


class XZ(_Model):
    x: Coord = None
    z: Coord = None


class XYZ(_Model):
    x: Coord = None
    y: Coord = None
    z: Coord = None


class Bounds2d(_Model):
    """Nested extent-bound footprint (the parser artifact)."""
    min: XZ
    max: XZ


class Team(_Model):
    id: str
    name: str = ""
    color: str = ""
    dye_color: str = ""
    max_players: int = 0
    min_players: int = 0


class Author(_Model):
    uuid: str = ""
    role: str = ""
    contribution: Optional[str] = None
    name: Optional[str] = None          # sketch authors carry a name


class KitItem(_Model):
    slot: Optional[int] = None
    material: str = ""
    amount: Optional[int] = None
    damage: Optional[int] = None
    unbreakable: Optional[bool] = None
    team_color: Optional[bool] = None
    enchantments: Optional[str] = None


class KitArmor(_Model):
    slot_name: str = ""
    material: str = ""
    unbreakable: Optional[bool] = None
    team_color: Optional[bool] = None
    enchantments: Optional[str] = None


class Kit(_Model):
    id: str
    items: list[KitItem] = []
    armor: list[KitArmor] = []


class Region(_Model):
    """Any of the 17 region types — type-specific fields are all optional."""
    id: str = ""
    type: str
    bounds_2d: Optional[Bounds2d] = None
    # primitives
    min: Optional[XYZ] = None
    max: Optional[XYZ] = None
    base: Optional[XYZ] = None
    center: Optional[XZ] = None
    origin: Optional[XYZ] = None
    position: Optional[XYZ] = None
    radius: Coord = None
    height: Coord = None
    # compound — string-id refs into the flat registry (inline tolerated for legacy)
    children: Optional[list[Union[str, "Region"]]] = None
    # transform
    source_id: Optional[str] = None
    normal: Optional[XYZ] = None
    offset: Optional[XYZ] = None
    # special
    ref_id: Optional[str] = None
    y: Coord = None


class Spawn(_Model):
    team: str = ""
    kit: Optional[str] = None
    yaw: float = 0.0
    region: Optional[Union[str, Region]] = None   # string id or inline region


class Monument(_Model):
    id: str = ""
    team: str = ""
    location: Optional[XYZ] = None
    monument_region: Optional[str] = None


class Wool(_Model):
    id: str = ""
    color: str = ""
    location: Optional[XYZ] = None
    wool_room_region: Optional[str] = None
    monuments: list[Monument] = []
    team: Optional[str] = None            # derived owner, when present


class DropItem(_Model):
    material: str = ""
    damage: Optional[int] = None
    amount: Optional[int] = None
    chance: Optional[float] = None


class Spawner(_Model):
    spawn_region: Optional[str] = None
    player_region: Optional[str] = None
    delay: Optional[str] = None
    max_entities: Optional[int] = None
    items: list[DropItem] = []


class Renewable(_Model):
    region_id: Optional[str] = None
    rate: Optional[float] = None
    renew_filter: Optional[str] = None
    replace_filter: Optional[str] = None
    grow: Optional[bool] = None


class BlockDropRule(_Model):
    region_id: Optional[str] = None
    filter_id: Optional[str] = None
    replacement: Optional[str] = None
    wrong_tool: Optional[bool] = None
    items: list[DropItem] = []


class Filter(_Model):
    """Any filter — composite (children/child) or atomic (type-specific params)."""
    id: str = ""
    type: str
    children: Optional[list[str]] = None   # all / any / one
    child: Optional[str] = None            # not / deny / allow
    region: Optional[str] = None           # blocks / region


class ApplyRule(_Model):
    id: Optional[str] = None
    region: Optional[str] = None
    enter: Optional[str] = None
    leave: Optional[str] = None
    block: Optional[str] = None
    block_place: Optional[str] = None
    block_break: Optional[str] = None
    block_physics: Optional[str] = None
    block_place_against: Optional[str] = None
    use: Optional[str] = None
    filter: Optional[str] = None
    kit: Optional[str] = None
    lend_kit: Optional[str] = None
    velocity: Optional[str] = None
    message: Optional[str] = None


class ObserverSpawn(_Model):
    team: str = ""
    kit: Optional[str] = None
    yaw: Optional[float] = None
    region: Optional[Union[str, Region]] = None


class MapProject(_Model):
    """The persisted `xml_data.json` shape (imported map)."""
    name: str = ""
    version: Optional[str] = None
    gamemode: Optional[str] = None
    objective: Optional[str] = None
    max_build_height: Optional[float] = None
    authors: list[Author] = []
    kits: list[Kit] = []
    teams: list[Team] = []
    spawns: list[Spawn] = []
    observer_spawn: Optional[ObserverSpawn] = None
    wools: list[Wool] = []
    spawners: list[Spawner] = []
    renewables: list[Renewable] = []
    block_drop_rules: list[BlockDropRule] = []
    filters: dict[str, Filter] = {}
    regions: dict[str, Region] = {}
    apply_rules: list[ApplyRule] = []


Region.model_rebuild()
