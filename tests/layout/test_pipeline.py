import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pgm_map_studio.layout.config import ScanConfig
from pgm_map_studio.layout.pipeline import run, _map_bounds
from pgm_map_studio.minecraft.sources import MapSource


def _make_source(tmp_path: Path) -> MapSource:
    region_dir = tmp_path / 'region'
    region_dir.mkdir()
    return MapSource(slug='test', path=tmp_path, has_xml=False, game_mode='ctw')


def _layer_df(n=25):
    """Synthetic layer DataFrame forming a single 5×5 island."""
    xs = [x for x in range(5) for _ in range(5)]
    zs = [z for _ in range(5) for z in range(5)]
    return pd.DataFrame({'world_x': xs[:n], 'world_z': zs[:n], 'block_id': [1] * n})


# ---------------------------------------------------------------------------
# _map_bounds
# ---------------------------------------------------------------------------

def test_map_bounds_empty():
    assert _map_bounds(pd.DataFrame(columns=['world_x', 'world_z'])) == (0, 0, 0, 0)


def test_map_bounds_correct():
    df = pd.DataFrame({'world_x': [0, 4], 'world_z': [0, 6]})
    assert _map_bounds(df) == (0, 0, 5, 7)


# ---------------------------------------------------------------------------
# ScanConfig defaults
# ---------------------------------------------------------------------------

def test_scan_config_defaults():
    cfg = ScanConfig()
    assert cfg.layer == 'surface'
    assert cfg.exclude_ids == []
    assert cfg.max_build_height is None
    assert cfg.min_island_size == 10


# ---------------------------------------------------------------------------
# run() — mocked extractors
# ---------------------------------------------------------------------------

@patch('pgm_map_studio.layout.pipeline.RegionReader')
@patch('pgm_map_studio.layout.pipeline.SurfaceExtractor')
@patch('pgm_map_studio.layout.pipeline.WoolExtractor')
@patch('pgm_map_studio.layout.pipeline.ResourceExtractor')
@patch('pgm_map_studio.layout.pipeline.ChestExtractor')
@patch('pgm_map_studio.layout.pipeline.SpawnerExtractor')
def test_run_produces_map_layout(
    MockSpawner, MockChest, MockResource, MockWool, MockSurface, MockReader, tmp_path
):
    layer_df = _layer_df()
    MockSurface.return_value.extract.return_value = layer_df
    for mock in (MockWool, MockResource, MockChest, MockSpawner):
        mock.return_value.extract.return_value = pd.DataFrame()

    source = _make_source(tmp_path)
    layout = run(source, tmp_path / 'out', ScanConfig(layer='surface', min_island_size=1))

    assert len(layout.islands) == 1
    assert layout.islands[0].block_count == 25


@patch('pgm_map_studio.layout.pipeline.RegionReader')
@patch('pgm_map_studio.layout.pipeline.SurfaceExtractor')
@patch('pgm_map_studio.layout.pipeline.WoolExtractor')
@patch('pgm_map_studio.layout.pipeline.ResourceExtractor')
@patch('pgm_map_studio.layout.pipeline.ChestExtractor')
@patch('pgm_map_studio.layout.pipeline.SpawnerExtractor')
def test_run_writes_expected_files(
    MockSpawner, MockChest, MockResource, MockWool, MockSurface, MockReader, tmp_path
):
    layer_df = _layer_df()
    MockSurface.return_value.extract.return_value = layer_df
    for mock in (MockWool, MockResource, MockChest, MockSpawner):
        mock.return_value.extract.return_value = pd.DataFrame()

    source = _make_source(tmp_path)
    out = tmp_path / 'out'
    run(source, out, ScanConfig(layer='surface', min_island_size=1))

    assert (out / 'layer.parquet').exists()
    assert (out / 'islands.json').exists()
    assert (out / 'wools.parquet').exists()
    assert (out / 'resources.parquet').exists()
    assert (out / 'chests.parquet').exists()
    assert (out / 'spawners.parquet').exists()


@patch('pgm_map_studio.layout.pipeline.RegionReader')
@patch('pgm_map_studio.layout.pipeline.SurfaceExtractor')
@patch('pgm_map_studio.layout.pipeline.WoolExtractor')
@patch('pgm_map_studio.layout.pipeline.ResourceExtractor')
@patch('pgm_map_studio.layout.pipeline.ChestExtractor')
@patch('pgm_map_studio.layout.pipeline.SpawnerExtractor')
def test_run_uses_cache_on_second_call(
    MockSpawner, MockChest, MockResource, MockWool, MockSurface, MockReader, tmp_path
):
    layer_df = _layer_df()
    MockSurface.return_value.extract.return_value = layer_df
    for mock in (MockWool, MockResource, MockChest, MockSpawner):
        mock.return_value.extract.return_value = pd.DataFrame()

    source = _make_source(tmp_path)
    out = tmp_path / 'out'
    run(source, out, ScanConfig(layer='surface', min_island_size=1))

    # Second run — extractor should not be called again
    MockSurface.reset_mock()
    run(source, out, ScanConfig(layer='surface', min_island_size=1))
    MockSurface.return_value.extract.assert_not_called()
