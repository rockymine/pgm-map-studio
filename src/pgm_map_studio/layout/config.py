from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LayerChoice = Literal['surface', 'y0', 'bedrock', 'base']


@dataclass
class ScanConfig:
    """Per-map extraction configuration.

    layer:            which layer extractor to use for island detection.
    exclude_ids:      block IDs to treat as air during extraction.
    max_build_height: ignore blocks at or above this Y level (surface extractor only).
    min_island_size:  discard islands smaller than this many blocks.
    """
    layer: LayerChoice = 'surface'
    exclude_ids: list[int] = field(default_factory=list)
    max_build_height: int | None = None
    min_island_size: int = 10
