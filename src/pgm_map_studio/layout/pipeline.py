"""Layout pipeline — scan one map and detect its islands.

Entry point: run(source, output_dir, config, force)

Outputs written to output_dir:
    layer.parquet      — block scan used for island detection
    wools.parquet      — wool block positions and colours
    resources.parquet  — iron/gold/diamond block positions
    chests.parquet     — chest inventory
    spawners.parquet   — mob spawner configuration
    islands.json       — detected islands (polygon + bounds + block_count)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from pgm_map_studio.minecraft.region_reader import RegionReader
from pgm_map_studio.minecraft.layers import (
    Y0Extractor, SurfaceExtractor, BedrockExtractor, BaseExtractor, SegmentsExtractor,
)
from pgm_map_studio.minecraft.features import (
    WoolExtractor, ResourceExtractor, ChestExtractor, SpawnerExtractor,
)
from pgm_map_studio.minecraft.sources import MapSource

from .config import ScanConfig
from .datatypes import Island, MapLayout
from .islands import detect_islands, save_islands

logger = logging.getLogger('pgm_map_studio')


def run(
    source: MapSource,
    output_dir: Path,
    config: ScanConfig | None = None,
    force: bool = False,
) -> MapLayout:
    """Scan a map and detect its islands.

    Args:
        source:     MapSource from find_maps().
        output_dir: Directory to write parquet and JSON outputs.
        config:     Extraction configuration. Defaults to ScanConfig().
        force:      Re-run even if output files already exist.

    Returns:
        MapLayout with detected islands.
    """
    cfg = config or ScanConfig()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = RegionReader(source.path / 'region')

    layer_df = _run_layer(reader, cfg, output_dir, force)
    _run_features(reader, output_dir, force)
    islands = _run_islands(layer_df, cfg, output_dir, force)

    bounds = _map_bounds(layer_df)
    return MapLayout(islands=islands, bounds=bounds)


# ---------------------------------------------------------------------------
# Internal steps
# ---------------------------------------------------------------------------

def _run_layer(
    reader: RegionReader,
    cfg: ScanConfig,
    output_dir: Path,
    force: bool,
) -> pd.DataFrame:
    """Run the configured layer extractor, writing layer.parquet if needed."""
    path = output_dir / 'layer.parquet'
    if path.exists() and not force:
        logger.debug(f"  layer.parquet exists, loading from cache")
        return pd.read_parquet(path)

    logger.debug(f"  Running {cfg.layer} extractor...")
    exclude = set(cfg.exclude_ids)

    if cfg.layer == 'y0':
        df = Y0Extractor(reader).extract()
        if exclude:
            df = df[~df['block_id'].isin(exclude)].reset_index(drop=True)
    elif cfg.layer == 'surface':
        df = SurfaceExtractor(
            reader, exclude_ids=exclude, max_build_height=cfg.max_build_height
        ).extract()
    elif cfg.layer == 'bedrock':
        df = BedrockExtractor(reader).extract()
    elif cfg.layer == 'base':
        df = BaseExtractor(reader, exclude_ids=exclude).extract()
    else:
        raise ValueError(f"Unknown layer: {cfg.layer!r}")

    df.to_parquet(path)
    logger.debug(f"  Saved layer.parquet ({len(df)} blocks)")
    return df


def _run_features(reader: RegionReader, output_dir: Path, force: bool) -> None:
    """Run feature extractors, writing parquet files if needed."""
    steps = [
        ('wools.parquet',          lambda: WoolExtractor(reader).extract()),
        ('resources.parquet',      lambda: ResourceExtractor(reader).extract()),
        ('chests.parquet',         lambda: ChestExtractor(reader).extract()),
        ('spawners.parquet',       lambda: SpawnerExtractor(reader).extract()),
        ('layer_segments.parquet', lambda: SegmentsExtractor(reader).extract()),
    ]
    for filename, extractor_fn in steps:
        path = output_dir / filename
        if path.exists() and not force:
            logger.debug(f"  {filename} exists, skipping")
            continue
        logger.debug(f"  Running extractor for {filename}...")
        df = extractor_fn()
        df.to_parquet(path)
        logger.debug(f"  Saved {filename} ({len(df)} rows)")


def _run_islands(
    layer_df: pd.DataFrame,
    cfg: ScanConfig,
    output_dir: Path,
    force: bool,
) -> list[Island]:
    """Detect islands from the layer DataFrame, writing islands.json if needed."""
    from .islands import load_islands

    path = output_dir / 'islands.json'
    if path.exists() and not force:
        logger.debug(f"  islands.json exists, loading from cache")
        return load_islands(path)

    islands = detect_islands(layer_df, min_island_size=cfg.min_island_size)
    save_islands(islands, path)
    logger.debug(f"  Saved islands.json ({len(islands)} islands)")
    return islands


def _map_bounds(df: pd.DataFrame) -> tuple[int, int, int, int]:
    """Derive overall map bounds from a layer DataFrame."""
    if df.empty:
        return (0, 0, 0, 0)
    min_x = int(df['world_x'].min())
    min_z = int(df['world_z'].min())
    max_x = int(df['world_x'].max()) + 1
    max_z = int(df['world_z'].max()) + 1
    return (min_x, min_z, max_x, max_z)
