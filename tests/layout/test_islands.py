import json
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import shape

from pgm_map_studio.layout.islands import (
    detect_islands,
    save_islands,
    load_islands,
    _connected_components,
    _blocks_to_polygon,
    _bounds_from_blocks,
)


def _df(*positions):
    """Build a minimal layer DataFrame from (x, z) tuples."""
    xs, zs = zip(*positions) if positions else ([], [])
    return pd.DataFrame({'world_x': list(xs), 'world_z': list(zs)})


# ---------------------------------------------------------------------------
# _connected_components
# ---------------------------------------------------------------------------

def test_components_single_block():
    coords = np.array([[0, 0]])
    result = _connected_components(coords, connectivity=4)
    assert len(result) == 1
    assert len(result[0]) == 1


def test_components_two_separate_blocks_4conn():
    coords = np.array([[0, 0], [2, 0]])
    result = _connected_components(coords, connectivity=4)
    assert len(result) == 2


def test_components_two_adjacent_blocks():
    coords = np.array([[0, 0], [1, 0]])
    result = _connected_components(coords, connectivity=4)
    assert len(result) == 1
    assert len(result[0]) == 2


def test_components_diagonal_8conn_connects():
    coords = np.array([[0, 0], [1, 1]])
    result = _connected_components(coords, connectivity=8)
    assert len(result) == 1


def test_components_diagonal_4conn_separates():
    coords = np.array([[0, 0], [1, 1]])
    result = _connected_components(coords, connectivity=4)
    assert len(result) == 2


def test_components_rectangle():
    coords = np.array([[x, z] for x in range(3) for z in range(3)])
    result = _connected_components(coords, connectivity=4)
    assert len(result) == 1
    assert len(result[0]) == 9


# ---------------------------------------------------------------------------
# _bounds_from_blocks
# ---------------------------------------------------------------------------

def test_bounds_single_block():
    blocks = np.array([[5, 10]])
    assert _bounds_from_blocks(blocks) == (5, 10, 6, 11)


def test_bounds_rectangle():
    blocks = np.array([[0, 0], [2, 3]])
    min_x, min_z, max_x, max_z = _bounds_from_blocks(blocks)
    assert min_x == 0 and min_z == 0
    assert max_x == 3 and max_z == 4  # +1 for block extent


# ---------------------------------------------------------------------------
# _blocks_to_polygon
# ---------------------------------------------------------------------------

def test_polygon_single_block():
    poly = _blocks_to_polygon(np.array([[0, 0]]))
    assert poly.area == pytest.approx(1.0)


def test_polygon_two_adjacent_blocks():
    poly = _blocks_to_polygon(np.array([[0, 0], [1, 0]]))
    assert poly.area == pytest.approx(2.0)
    assert poly.geom_type == 'Polygon'


def test_polygon_donut_has_hole():
    # 3x3 ring with centre missing
    ring = [(x, z) for x in range(3) for z in range(3) if not (x == 1 and z == 1)]
    poly = _blocks_to_polygon(np.array(ring))
    assert poly.geom_type == 'Polygon'
    assert len(list(poly.interiors)) == 1
    assert poly.area == pytest.approx(8.0)


# ---------------------------------------------------------------------------
# detect_islands
# ---------------------------------------------------------------------------

def test_detect_empty_df():
    islands = detect_islands(pd.DataFrame(columns=['world_x', 'world_z']))
    assert islands == []


def test_detect_single_island():
    df = _df(*[(x, z) for x in range(5) for z in range(5)])
    islands = detect_islands(df, min_island_size=1)
    assert len(islands) == 1
    assert islands[0].id == 1
    assert islands[0].block_count == 25


def test_detect_two_separate_islands():
    blocks_a = [(x, z) for x in range(5) for z in range(5)]
    blocks_b = [(x + 20, z) for x in range(3) for z in range(3)]
    df = _df(*(blocks_a + blocks_b))
    islands = detect_islands(df, min_island_size=1)
    assert len(islands) == 2
    assert islands[0].block_count == 25  # largest first
    assert islands[1].block_count == 9


def test_detect_ids_are_sequential_from_one():
    blocks_a = [(x, z) for x in range(5) for z in range(5)]
    blocks_b = [(x + 20, z) for x in range(3) for z in range(3)]
    df = _df(*(blocks_a + blocks_b))
    islands = detect_islands(df, min_island_size=1)
    assert [i.id for i in islands] == [1, 2]


def test_detect_min_island_size_filters():
    blocks_a = [(x, z) for x in range(5) for z in range(5)]  # 25 blocks
    blocks_b = [(x + 20, z) for x in range(2) for z in range(2)]  # 4 blocks
    df = _df(*(blocks_a + blocks_b))
    islands = detect_islands(df, min_island_size=10)
    assert len(islands) == 1
    assert islands[0].block_count == 25


def test_detect_bounds_correct():
    df = _df(*[(x, z) for x in range(3) for z in range(3)])
    islands = detect_islands(df, min_island_size=1)
    assert islands[0].bounds == (0, 0, 3, 3)


def test_detect_polygon_has_correct_area():
    df = _df(*[(x, z) for x in range(4) for z in range(4)])
    islands = detect_islands(df, min_island_size=1)
    assert islands[0].polygon.area == pytest.approx(16.0)


def test_detect_hole_in_polygon():
    ring = [(x, z) for x in range(3) for z in range(3) if not (x == 1 and z == 1)]
    df = _df(*ring)
    islands = detect_islands(df, min_island_size=1)
    assert len(islands) == 1
    assert len(list(islands[0].polygon.interiors)) == 1


# ---------------------------------------------------------------------------
# save_islands / load_islands round-trip
# ---------------------------------------------------------------------------

def test_save_load_roundtrip(tmp_path):
    df = _df(*[(x, z) for x in range(5) for z in range(5)])
    islands = detect_islands(df, min_island_size=1)
    path = tmp_path / 'islands.json'
    save_islands(islands, path)
    loaded = load_islands(path)
    assert len(loaded) == 1
    assert loaded[0].id == islands[0].id
    assert loaded[0].block_count == islands[0].block_count
    assert loaded[0].bounds == islands[0].bounds
    assert loaded[0].polygon.area == pytest.approx(islands[0].polygon.area)


def test_save_produces_valid_json(tmp_path):
    df = _df(*[(x, z) for x in range(3) for z in range(3)])
    islands = detect_islands(df, min_island_size=1)
    path = tmp_path / 'islands.json'
    save_islands(islands, path)
    data = json.loads(path.read_text())
    assert isinstance(data, list)
    assert data[0]['polygon']['type'] == 'Polygon'
