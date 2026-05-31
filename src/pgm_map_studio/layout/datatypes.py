from __future__ import annotations

from dataclasses import dataclass
from shapely.geometry import Polygon


@dataclass
class Island:
    id: int
    polygon: Polygon
    bounds: tuple[int, int, int, int]  # (min_x, min_z, max_x, max_z) — block extent
    block_count: int


@dataclass
class MapLayout:
    islands: list[Island]
    bounds: tuple[int, int, int, int]  # (min_x, min_z, max_x, max_z) of full map
