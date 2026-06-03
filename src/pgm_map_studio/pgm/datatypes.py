"""Data classes for parsed PGM map.xml data."""

from dataclasses import dataclass, field
from typing import Optional

from .regions import Region
from .filters import Filter


@dataclass
class Team:
    id: str
    color: str
    max_players: int = 0
    min_players: int = 0
    name: str = ""
    dye_color: str = ""


@dataclass
class Author:
    uuid: str = ""
    role: str = "author"       # "author" | "contributor"
    contribution: str = ""


@dataclass
class KitItem:
    slot: int = 0
    material: str = ""
    amount: int = 1
    item_damage: int = 0
    unbreakable: bool = False
    team_color: bool = False
    enchantments: str = ""     # comma-joined "name:level" pairs


@dataclass
class KitArmor:
    slot_name: str = ""        # helmet | chestplate | leggings | boots
    material: str = ""
    unbreakable: bool = False
    team_color: bool = False
    enchantments: str = ""


@dataclass
class Kit:
    id: str = ""
    items: list[KitItem] = field(default_factory=list)
    armor: list[KitArmor] = field(default_factory=list)


@dataclass
class Spawn:
    team: str = ""
    kit: str = ""
    yaw: float = 0.0
    region: Optional[Region] = None


@dataclass
class Wool:
    team: str
    color: str
    location: tuple[float, float, float]
    monument: tuple[float, float, float]
    monument_region_id: Optional[str] = None
    wool_room_region: Optional[str] = None


@dataclass
class SpawnerItem:
    material: str
    damage: int = 0
    amount: int = 1


@dataclass
class WoolSpawner:
    spawn_region: str
    player_region: str
    delay: str = ""
    max_entities: Optional[int] = None
    items: list[SpawnerItem] = field(default_factory=list)


@dataclass
class ApplyRule:
    # Spatial filter attributes
    enter_filter: str = ""           # enter=
    leave_filter: str = ""           # leave=
    block_filter: str = ""           # block= (place + break combined)
    block_place_filter: str = ""     # block-place=
    block_break_filter: str = ""     # block-break=
    block_physics_filter: str = ""   # block-physics= (water flow, etc.)
    block_place_against_filter: str = ""  # block-place-against=
    use_filter: str = ""             # use= (right-click)
    filter_id: str = ""              # filter= (general condition for kit/velocity)
    # Region
    region_id: str = ""              # region= or inline region child
    inline_region: Optional[Region] = None  # kept for compat; never populated
    # Actions
    kit: str = ""                    # kit= (give on enter)
    lend_kit: str = ""               # lend-kit= (give on enter, remove on leave)
    velocity: str = ""               # velocity= "X,Y,Z"
    message: str = ""                # message= (shown when event denied)


@dataclass
class Renewable:
    region_id: str = ""
    rate: float = 1.0
    renew_filter: str = ""
    replace_filter: str = ""
    grow: bool = False


@dataclass
class BlockDropItem:
    material: str = ""
    damage: int = 0
    amount: int = 1
    chance: float = 1.0


@dataclass
class BlockDropRule:
    region_id: str = ""
    filter_id: str = ""
    replacement: str = ""
    wrong_tool: bool = False
    items: list[BlockDropItem] = field(default_factory=list)


@dataclass
class MapXml:
    name: str = ""
    version: str = ""
    gamemode: str = "ctw"
    objective: str = ""
    max_build_height: Optional[int] = None
    authors: list[Author] = field(default_factory=list)
    kits: list[Kit] = field(default_factory=list)
    teams: list[Team] = field(default_factory=list)
    spawns: list[Spawn] = field(default_factory=list)
    observer_spawn: Optional[Spawn] = None
    wools: list[Wool] = field(default_factory=list)
    spawners: list[WoolSpawner] = field(default_factory=list)
    renewables: list[Renewable] = field(default_factory=list)
    block_drop_rules: list[BlockDropRule] = field(default_factory=list)
    filters: dict[str, Filter] = field(default_factory=dict)
    regions: dict[str, Region] = field(default_factory=dict)
    apply_rules: list[ApplyRule] = field(default_factory=list)
