"""Island detection and polygon construction.

Takes a block DataFrame (output of any layer extractor) and returns a list
of Island objects, each with an exact block-outline polygon and hole support.

Steps:
  1. Project blocks to unique (x, z) coordinates.
  2. BFS connected-component labelling (4- or 8-connectivity).
  3. Filter components below min_island_size.
  4. Build each island's polygon via unary_union of unit squares.
  5. Sort by block_count descending and assign sequential IDs.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import box, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid

from .datatypes import Island, MapLayout

logger = logging.getLogger('pgm_map_studio')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connected_components(
    coords: np.ndarray,
    connectivity: int,
) -> list[np.ndarray]:
    """BFS connected-component detection on a set of (x, z) integer coordinates.

    Returns a list of (N, 2) int32 arrays, one per component.
    """
    if connectivity == 8:
        deltas = [(dx, dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if dx or dz]
    else:
        deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    remaining: set[tuple[int, int]] = {(int(r[0]), int(r[1])) for r in coords}
    components: list[list[tuple[int, int]]] = []

    while remaining:
        start = next(iter(remaining))
        component: list[tuple[int, int]] = []
        queue: deque[tuple[int, int]] = deque([start])
        remaining.discard(start)
        while queue:
            x, z = queue.popleft()
            component.append((x, z))
            for dx, dz in deltas:
                nb = (x + dx, z + dz)
                if nb in remaining:
                    remaining.discard(nb)
                    queue.append(nb)
        components.append(component)

    return [np.array(c, dtype=np.int32) for c in components]


def _blocks_to_polygon(blocks: np.ndarray):
    """Build an exact Shapely polygon from (x, z) block coordinates.

    Each block at (x, z) occupies [x, x+1] × [z, z+1]. The union of all
    unit squares gives the exact boundary including concavities and holes
    (as interior rings).

    Diagonal-only connections produce touching-point geometries that
    make_valid() splits into MultiPolygons — we keep the largest part.
    """
    squares = [box(float(x), float(z), float(x) + 1.0, float(z) + 1.0) for x, z in blocks]
    poly = unary_union(squares)
    if not poly.is_valid:
        poly = make_valid(poly)
    if poly.geom_type == 'MultiPolygon':
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly


def _bounds_from_blocks(blocks: np.ndarray) -> tuple[int, int, int, int]:
    """Return (min_x, min_z, max_x, max_z) block extent (inclusive of block footprint)."""
    min_x, min_z = int(blocks[:, 0].min()), int(blocks[:, 1].min())
    max_x, max_z = int(blocks[:, 0].max()) + 1, int(blocks[:, 1].max()) + 1
    return (min_x, min_z, max_x, max_z)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_islands(
    df: pd.DataFrame,
    min_island_size: int = 10,
    connectivity: int = 8,
) -> list[Island]:
    """Detect islands from a layer extractor DataFrame.

    Args:
        df:               DataFrame with at least world_x and world_z columns.
        min_island_size:  Discard components with fewer blocks than this.
        connectivity:     4 or 8 neighbour connectivity.

    Returns:
        List of Island objects sorted by block_count descending, IDs 1-based.
    """
    coords = df[['world_x', 'world_z']].drop_duplicates().values
    if len(coords) == 0:
        return []

    logger.debug(f"Detecting islands from {len(coords)} blocks (connectivity={connectivity})...")
    components = _connected_components(coords, connectivity)
    logger.debug(f"  Found {len(components)} raw components")

    islands: list[Island] = []
    for blocks in components:
        if len(blocks) < min_island_size:
            continue
        poly = _blocks_to_polygon(blocks)
        bounds = _bounds_from_blocks(blocks)
        islands.append(Island(
            id=0,  # assigned after sorting
            polygon=poly,
            bounds=bounds,
            block_count=len(blocks),
        ))

    islands.sort(key=lambda i: i.block_count, reverse=True)
    for idx, island in enumerate(islands, start=1):
        island.id = idx

    logger.debug(f"  Kept {len(islands)} islands (min_size={min_island_size})")
    return islands


def save_islands(islands: list[Island], path: Path) -> None:
    """Serialise a list of islands to JSON (GeoJSON polygons)."""
    data = [
        {
            'id': isl.id,
            'block_count': isl.block_count,
            'bounds': list(isl.bounds),
            'polygon': mapping(isl.polygon),
        }
        for isl in islands
    ]
    path.write_text(json.dumps(data, indent=2))


def load_islands(path: Path) -> list[Island]:
    """Deserialise islands from a JSON file written by save_islands."""
    from shapely.geometry import shape

    data = json.loads(path.read_text())
    islands = []
    for entry in data:
        islands.append(Island(
            id=entry['id'],
            polygon=shape(entry['polygon']),
            bounds=tuple(entry['bounds']),
            block_count=entry['block_count'],
        ))
    return islands
