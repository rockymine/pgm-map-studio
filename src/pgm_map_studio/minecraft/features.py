"""Feature extractors — locate specific block types, one row per instance.

Each extractor scans for a particular block type and returns per-instance
data with type-specific fields. They answer "where are the X blocks,
and what are they?"

- WoolExtractor      — wool blocks with color name (→ wools.parquet)
- ResourceExtractor  — iron/gold/diamond blocks with resource type (→ resources.parquet)
- ChestExtractor     — chest inventory from tile entity NBT (→ chests.parquet)
- SpawnerExtractor   — mob spawner config from tile entity NBT (→ spawners.parquet)

detect_double_chests() is a post-processing helper for ChestExtractor output.
"""

import logging
from typing import Optional
import numpy as np
import pandas as pd

from .region_reader import RegionReader
from ._helpers import _iter_chunk_sections
from .wool import WOOL_DAMAGE_TO_COLOR

logger = logging.getLogger('pgm_map_studio')


def _nbt_val(tag):
    """Return the Python scalar value of an NBT tag."""
    return tag.value if hasattr(tag, 'value') else tag


# ---------------------------------------------------------------------------
# WoolExtractor
# ---------------------------------------------------------------------------

class WoolExtractor:
    """Wool blocks (block_id=35) with color name derived from damage value.

    Returns DataFrame: world_x, world_z, y, color
    """

    def __init__(self, region_reader: RegionReader) -> None:
        self.reader = region_reader

    def extract(self) -> pd.DataFrame:
        all_wx, all_wz, all_y, all_color = [], [], [], []

        for chunk, chunk_x, chunk_z in self.reader.iter_chunks():
            for section_y, blocks_3d, data_3d in _iter_chunk_sections(chunk):
                yy, zz, xx = np.where(blocks_3d == 35)
                if len(yy) == 0:
                    continue
                all_wx.append((chunk_x * 16 + xx).astype(np.int32))
                all_wz.append((chunk_z * 16 + zz).astype(np.int32))
                all_y.append((section_y * 16 + yy).astype(np.int32))
                damage = data_3d[yy, zz, xx]
                all_color.append(
                    np.array([WOOL_DAMAGE_TO_COLOR.get(int(d), 'white') for d in damage])
                )

        if not all_wx:
            return pd.DataFrame(columns=['world_x', 'world_z', 'y', 'color'])
        return pd.DataFrame({
            'world_x': np.concatenate(all_wx),
            'world_z': np.concatenate(all_wz),
            'y':       np.concatenate(all_y),
            'color':   np.concatenate(all_color),
        })


# ---------------------------------------------------------------------------
# ResourceExtractor
# ---------------------------------------------------------------------------

DEFAULT_RESOURCE_BLOCKS: dict[int, str] = {
    41: 'gold_block',
    42: 'iron_block',
    57: 'diamond_block',
}


class ResourceExtractor:
    """Iron, gold, and diamond blocks with resource type label.

    Returns DataFrame: world_x, world_z, y, resource_type
    """

    def __init__(
        self,
        region_reader: RegionReader,
        target_blocks: dict[int, str] | None = None,
    ) -> None:
        self.reader = region_reader
        self.target_blocks = target_blocks if target_blocks is not None else DEFAULT_RESOURCE_BLOCKS

    def extract(self) -> pd.DataFrame:
        all_wx, all_wz, all_y, all_rt = [], [], [], []

        for chunk, chunk_x, chunk_z in self.reader.iter_chunks():
            for section_y, blocks_3d, _ in _iter_chunk_sections(chunk):
                for block_id, label in self.target_blocks.items():
                    yy, zz, xx = np.where(blocks_3d == block_id)
                    if len(yy) == 0:
                        continue
                    all_wx.append((chunk_x * 16 + xx).astype(np.int32))
                    all_wz.append((chunk_z * 16 + zz).astype(np.int32))
                    all_y.append((section_y * 16 + yy).astype(np.int32))
                    all_rt.append(np.full(len(yy), label, dtype=object))

        if not all_wx:
            return pd.DataFrame(columns=['world_x', 'world_z', 'y', 'resource_type'])
        return pd.DataFrame({
            'world_x':      np.concatenate(all_wx),
            'world_z':      np.concatenate(all_wz),
            'y':            np.concatenate(all_y),
            'resource_type': np.concatenate(all_rt),
        })


# ---------------------------------------------------------------------------
# ChestExtractor
# ---------------------------------------------------------------------------

_CHEST_TILE_IDS = frozenset({'Chest', 'TrappedChest'})


class ChestExtractor:
    """Chest and trapped chest inventory from tile entity NBT.

    Returns DataFrame: world_x, world_z, y, chest_type, slot, item_id, item_damage, count
    """

    def __init__(self, region_reader: RegionReader) -> None:
        self.reader = region_reader

    def extract(self) -> pd.DataFrame:
        rows: list[dict] = []

        for chunk, _, _ in self.reader.iter_chunks():
            try:
                tile_entities = chunk.data.get('TileEntities', [])
            except Exception:
                continue

            for te in tile_entities:
                try:
                    te_id = _nbt_val(te.get('id'))
                    if te_id not in _CHEST_TILE_IDS:
                        continue
                    chest_type = 'trapped_chest' if te_id == 'TrappedChest' else 'chest'
                    wx = int(_nbt_val(te.get('x')))
                    wy = int(_nbt_val(te.get('y')))
                    wz = int(_nbt_val(te.get('z')))
                    for item in te.get('Items', []):
                        rows.append({
                            'world_x':    wx,
                            'world_z':    wz,
                            'y':          wy,
                            'chest_type': chest_type,
                            'slot':       int(_nbt_val(item.get('Slot'))),
                            'item_id':    str(_nbt_val(item.get('id', ''))),
                            'item_damage': int(_nbt_val(item.get('Damage', 0))),
                            'count':      int(_nbt_val(item.get('Count', 1))),
                        })
                except Exception:
                    continue

        if not rows:
            return pd.DataFrame(columns=[
                'world_x', 'world_z', 'y', 'chest_type',
                'slot', 'item_id', 'item_damage', 'count',
            ])
        return pd.DataFrame(rows)


def detect_double_chests(chest_df: pd.DataFrame) -> pd.DataFrame:
    """Annotate a chest DataFrame with double-chest grouping.

    Two chests form a double chest when they share the same Y level and
    are exactly 1 block apart in X or Z. Returns a copy of chest_df with
    two extra columns:

        is_double      — True if this chest is part of a double chest
        chest_group_id — integer ID shared by both halves of a double;
                         single chests get their own unique ID
    """
    if chest_df.empty:
        result = chest_df.copy()
        result['is_double'] = pd.Series(dtype=bool)
        result['chest_group_id'] = pd.Series(dtype='Int64')
        return result

    pos_set: set[tuple[int, int, int]] = {
        (int(r.world_x), int(r.world_z), int(r.y))
        for r in chest_df[['world_x', 'world_z', 'y']].drop_duplicates().itertuples()
    }

    group_id: dict[tuple[int, int, int], int] = {}
    is_double: dict[tuple[int, int, int], bool] = {}
    next_id = 0

    for pos in sorted(pos_set):
        if pos in group_id:
            continue
        x, z, y = pos
        partner = next(
            (
                (x + dx, z + dz, y)
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if (x + dx, z + dz, y) in pos_set
            ),
            None,
        )
        if partner is not None and partner not in group_id:
            group_id[pos] = group_id[partner] = next_id
            is_double[pos] = is_double[partner] = True
        else:
            group_id[pos] = next_id
            is_double[pos] = False
        next_id += 1

    result = chest_df.copy()
    result['is_double'] = result.apply(
        lambda r: is_double.get((int(r.world_x), int(r.world_z), int(r.y)), False), axis=1
    )
    result['chest_group_id'] = result.apply(
        lambda r: group_id.get((int(r.world_x), int(r.world_z), int(r.y)), -1), axis=1
    ).astype('Int64')
    return result


# ---------------------------------------------------------------------------
# SpawnerExtractor
# ---------------------------------------------------------------------------

_NULLABLE_INT_COLS = [
    'spawn_item_damage', 'spawn_count', 'spawn_range',
    'min_spawn_delay', 'max_spawn_delay',
    'required_player_range', 'max_nearby_entities',
]

_SPAWNER_COLUMNS = [
    'world_x', 'world_z', 'y', 'entity_id',
    'spawns_wool', 'spawn_item_id', 'spawn_item_damage',
    'spawn_count', 'spawn_range', 'min_spawn_delay', 'max_spawn_delay',
    'required_player_range', 'max_nearby_entities',
]


class SpawnerExtractor:
    """Mob spawner configuration from tile entity NBT.

    The spawns_wool flag is True when SpawnData.Item.id == 'minecraft:wool',
    identifying spawners used as wool respawn mechanisms in CTW maps.

    Returns DataFrame: world_x, world_z, y, entity_id, spawns_wool,
                       spawn_item_id, spawn_item_damage, spawn_count,
                       spawn_range, min_spawn_delay, max_spawn_delay,
                       required_player_range, max_nearby_entities
    """

    def __init__(self, region_reader: RegionReader) -> None:
        self.reader = region_reader

    def extract(self) -> pd.DataFrame:
        rows: list[dict] = []

        for chunk, _, _ in self.reader.iter_chunks():
            try:
                tile_entities = chunk.data.get('TileEntities', [])
                if not tile_entities:
                    continue
            except Exception:
                continue

            for te in tile_entities:
                row = self._parse(te)
                if row is not None:
                    rows.append(row)

        if not rows:
            df = pd.DataFrame(columns=_SPAWNER_COLUMNS)
        else:
            df = pd.DataFrame(rows)

        for col in _NULLABLE_INT_COLS:
            if col in df.columns:
                df[col] = df[col].astype('Int64')
        return df

    def _parse(self, te) -> Optional[dict]:
        try:
            te_id = _nbt_val(te.get('id'))
            if te_id != 'MobSpawner':
                return None
            x_raw, y_raw, z_raw = te.get('x'), te.get('y'), te.get('z')
            if x_raw is None or y_raw is None or z_raw is None:
                return None

            row: dict = {
                'world_x':               int(_nbt_val(x_raw)),
                'world_z':               int(_nbt_val(z_raw)),
                'y':                     int(_nbt_val(y_raw)),
                'entity_id':             self._str(te.get('EntityId')),
                'spawns_wool':           False,
                'spawn_item_id':         None,
                'spawn_item_damage':     None,
                'spawn_count':           self._int(te.get('SpawnCount')),
                'spawn_range':           self._int(te.get('SpawnRange')),
                'min_spawn_delay':       self._int(te.get('MinSpawnDelay')),
                'max_spawn_delay':       self._int(te.get('MaxSpawnDelay')),
                'required_player_range': self._int(te.get('RequiredPlayerRange')),
                'max_nearby_entities':   self._int(te.get('MaxNearbyEntities')),
            }

            spawn_data = te.get('SpawnData')
            if spawn_data is not None:
                item = spawn_data.get('Item')
                if item is not None:
                    item_id = self._str(item.get('id'))
                    item_dmg = self._int(item.get('Damage'))
                    if item_id is not None:
                        row['spawn_item_id'] = item_id
                        row['spawn_item_damage'] = item_dmg
                        row['spawns_wool'] = item_id.lower() in ('minecraft:wool', 'wool', '35')

            return row
        except Exception:
            return None

    @staticmethod
    def _int(tag) -> Optional[int]:
        if tag is None:
            return None
        try:
            return int(tag.value if hasattr(tag, 'value') else tag)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _str(tag) -> Optional[str]:
        if tag is None:
            return None
        raw = tag.value if hasattr(tag, 'value') else tag
        return str(raw) if raw is not None else None
