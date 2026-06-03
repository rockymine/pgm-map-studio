import pandas as pd
import pytest
from unittest.mock import MagicMock
from pgm_map_studio.minecraft.features import (
    WoolExtractor,
    ResourceExtractor,
    ChestExtractor,
    SpawnerExtractor,
    DEFAULT_RESOURCE_BLOCKS,
    detect_double_chests,
)


def _mock_reader(chunks=()):
    reader = MagicMock()
    reader.iter_chunks.return_value = iter(chunks)
    return reader


# ---------------------------------------------------------------------------
# Empty-world behaviour
# ---------------------------------------------------------------------------

def test_wool_extractor_empty_world():
    df = WoolExtractor(_mock_reader()).extract()
    assert list(df.columns) == ['world_x', 'world_z', 'world_y', 'color']
    assert len(df) == 0


def test_resource_extractor_empty_world():
    df = ResourceExtractor(_mock_reader()).extract()
    assert list(df.columns) == ['world_x', 'world_z', 'world_y', 'resource_type']
    assert len(df) == 0


def test_chest_extractor_empty_world():
    df = ChestExtractor(_mock_reader()).extract()
    assert list(df.columns) == [
        'world_x', 'world_z', 'world_y', 'chest_type',
        'slot', 'item_id', 'item_damage', 'count',
    ]
    assert len(df) == 0


def test_spawner_extractor_empty_world():
    df = SpawnerExtractor(_mock_reader()).extract()
    assert 'world_x' in df.columns
    assert 'world_y' in df.columns
    assert 'spawns_wool' in df.columns
    assert 'entity_id' in df.columns
    assert len(df) == 0


# ---------------------------------------------------------------------------
# DEFAULT_RESOURCE_BLOCKS — no overlap with wool or spawners
# ---------------------------------------------------------------------------

def test_default_resources_excludes_wool():
    assert 35 not in DEFAULT_RESOURCE_BLOCKS


def test_default_resources_excludes_spawner_block():
    assert 52 not in DEFAULT_RESOURCE_BLOCKS


def test_default_resources_contains_ore_blocks():
    assert 41 in DEFAULT_RESOURCE_BLOCKS  # gold
    assert 42 in DEFAULT_RESOURCE_BLOCKS  # iron
    assert 57 in DEFAULT_RESOURCE_BLOCKS  # diamond


# ---------------------------------------------------------------------------
# detect_double_chests
# ---------------------------------------------------------------------------

def _chest_df(*positions):
    """Build a minimal chest DataFrame from (x, z, y) tuples."""
    return pd.DataFrame(
        [{'world_x': x, 'world_z': z, 'world_y': y} for x, z, y in positions]
    )


def test_detect_double_chests_empty():
    df = detect_double_chests(pd.DataFrame(columns=['world_x', 'world_z', 'world_y']))
    assert 'is_double' in df.columns
    assert 'chest_group_id' in df.columns
    assert len(df) == 0


def test_detect_double_chests_single():
    df = detect_double_chests(_chest_df((0, 0, 64)))
    assert df['is_double'].iloc[0] is False or df['is_double'].iloc[0] == False
    assert df['chest_group_id'].iloc[0] is not None


def test_detect_double_chests_adjacent_x():
    df = detect_double_chests(_chest_df((0, 0, 64), (1, 0, 64)))
    assert df['is_double'].all()
    assert df['chest_group_id'].iloc[0] == df['chest_group_id'].iloc[1]


def test_detect_double_chests_adjacent_z():
    df = detect_double_chests(_chest_df((0, 0, 64), (0, 1, 64)))
    assert df['is_double'].all()
    assert df['chest_group_id'].iloc[0] == df['chest_group_id'].iloc[1]


def test_detect_double_chests_different_y_not_double():
    df = detect_double_chests(_chest_df((0, 0, 64), (1, 0, 65)))
    assert not df['is_double'].any()


def test_detect_double_chests_diagonal_not_double():
    df = detect_double_chests(_chest_df((0, 0, 64), (1, 1, 64)))
    assert not df['is_double'].any()


def test_detect_double_chests_two_separate_pairs():
    df = detect_double_chests(_chest_df(
        (0, 0, 64), (1, 0, 64),   # pair A
        (10, 0, 64), (11, 0, 64), # pair B
    ))
    assert df['is_double'].all()
    group_ids = df['chest_group_id'].tolist()
    assert group_ids[0] == group_ids[1]
    assert group_ids[2] == group_ids[3]
    assert group_ids[0] != group_ids[2]
