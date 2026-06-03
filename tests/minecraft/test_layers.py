import numpy as np
import pytest
from unittest.mock import MagicMock
from pgm_map_studio.minecraft.layers import (
    Y0Extractor,
    SurfaceExtractor,
    BedrockExtractor,
    BaseExtractor,
    SegmentsExtractor,
    NON_SOLID_BLOCK_IDS,
)


def _mock_reader(chunks=()):
    reader = MagicMock()
    reader.iter_chunks.return_value = iter(chunks)
    return reader


# ---------------------------------------------------------------------------
# Empty-world behaviour
# ---------------------------------------------------------------------------

def test_y0_extractor_empty_world():
    df = Y0Extractor(_mock_reader()).extract()
    assert list(df.columns) == ['world_x', 'world_z', 'block_id', 'block_data']
    assert len(df) == 0


def test_surface_extractor_empty_world():
    df = SurfaceExtractor(_mock_reader()).extract()
    assert list(df.columns) == ['world_x', 'world_z', 'world_y', 'block_id', 'block_data']
    assert len(df) == 0


def test_bedrock_extractor_empty_world():
    df = BedrockExtractor(_mock_reader()).extract()
    assert list(df.columns) == ['world_x', 'world_z', 'world_y', 'block_id', 'block_data']
    assert len(df) == 0


def test_base_extractor_empty_world():
    df = BaseExtractor(_mock_reader()).extract()
    assert list(df.columns) == ['world_x', 'world_z', 'world_y', 'block_id', 'block_data']
    assert len(df) == 0


def test_segments_extractor_empty_world():
    df = SegmentsExtractor(_mock_reader()).extract()
    assert list(df.columns) == ['world_x', 'world_z', 'world_y_start', 'world_y_end']
    assert len(df) == 0


# ---------------------------------------------------------------------------
# NON_SOLID_BLOCK_IDS sanity checks
# ---------------------------------------------------------------------------

def test_water_not_in_non_solid():
    assert 8 not in NON_SOLID_BLOCK_IDS
    assert 9 not in NON_SOLID_BLOCK_IDS


def test_air_not_in_non_solid():
    assert 0 not in NON_SOLID_BLOCK_IDS


def test_torch_in_non_solid():
    assert 50 in NON_SOLID_BLOCK_IDS
