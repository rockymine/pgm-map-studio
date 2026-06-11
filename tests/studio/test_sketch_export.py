"""Tests for sketch_export: rasterization, symmetry transforms, and end-to-end export."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from shapely.geometry import box

from pgm_map_studio.studio.services import sketch_data
from pgm_map_studio.studio.services.sketch_export import (
    _compute_island_polys,
    _make_slug,
    _match_metadata,
    _rasterise_full_layout,
    _rasterise_poly,
    _shape_to_shapely,
    export_sketch,
)


# ── _rasterise_poly ───────────────────────────────────────────────────────────

def test_rasterise_poly_unit_square():
    poly = box(0, 0, 1, 1)
    blocks = _rasterise_poly(poly)
    assert blocks == [(0, 0)]


def test_rasterise_poly_4x4_square():
    poly = box(0, 0, 4, 4)
    blocks = set(_rasterise_poly(poly))
    assert len(blocks) == 16
    assert (0, 0) in blocks
    assert (3, 3) in blocks
    assert (4, 0) not in blocks  # outside extent


def test_rasterise_poly_with_hole():
    from shapely.geometry import Polygon
    outer = [(0, 0), (6, 0), (6, 6), (0, 6)]
    inner = [(2, 2), (4, 2), (4, 4), (2, 4)]
    poly = Polygon(outer, [inner])
    blocks = set(_rasterise_poly(poly))
    assert (3, 3) not in blocks   # inside hole
    assert (0, 0) in blocks       # outside hole
    assert len(blocks) == 36 - 4  # 6×6 minus 2×2 hole


def test_rasterise_poly_empty():
    from shapely.geometry import Polygon
    assert _rasterise_poly(Polygon()) == []
    assert _rasterise_poly(None) == []


# (polygon symmetry transforms moved to region_geometry.transform_geom — see
#  tests/studio/test_region_geometry.py)


# ── _shape_to_shapely ─────────────────────────────────────────────────────────

def test_shape_to_shapely_rectangle():
    shape = {"type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 10, "max_z": 10}
    poly = _shape_to_shapely(shape)
    assert poly is not None
    assert abs(poly.area - 100) < 0.01


def test_shape_to_shapely_circle():
    shape = {"type": "circle", "center_x": 0, "center_z": 0, "radius": 10}
    poly = _shape_to_shapely(shape)
    assert poly is not None
    import math
    assert abs(poly.area - math.pi * 100) < 5  # approximate circle


def test_shape_to_shapely_lasso():
    shape = {"type": "lasso", "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]]}
    poly = _shape_to_shapely(shape)
    assert poly is not None
    assert abs(poly.area - 100) < 0.01


def test_shape_to_shapely_lasso_too_few_verts():
    shape = {"type": "lasso", "vertices": [[0, 0], [10, 0]]}
    assert _shape_to_shapely(shape) is None


# ── _compute_island_polys ─────────────────────────────────────────────────────

_RECT_A = {"id": "s1", "type": "rectangle",
           "min_x": -50, "max_x": -10, "min_z": -50, "max_z": -10,
           "operation": "add", "override": False}

_RECT_B = {"id": "s2", "type": "rectangle",
           "min_x": 10,  "max_x": 50,  "min_z": 10,  "max_z": 50,
           "operation": "add", "override": False}


def test_compute_island_polys_two_disconnected_rects():
    polys, _, _, _ = _compute_island_polys([_RECT_A, _RECT_B])
    assert len(polys) == 2


def test_compute_island_polys_subtract_splits():
    big = {"id": "s1", "type": "rectangle",
           "min_x": 0, "max_x": 100, "min_z": 0, "max_z": 50,
           "operation": "add", "override": False}
    cut = {"id": "s2", "type": "rectangle",
           "min_x": 45, "max_x": 55, "min_z": 0, "max_z": 50,
           "operation": "subtract", "override": False}
    polys, _, _, _ = _compute_island_polys([big, cut])
    assert len(polys) == 2


def test_compute_island_polys_override_add_immune():
    sub  = {"id": "s1", "type": "rectangle",
            "min_x": 0, "max_x": 100, "min_z": 0, "max_z": 100,
            "operation": "subtract", "override": False}
    over = {"id": "s2", "type": "rectangle",
            "min_x": 10, "max_x": 90, "min_z": 10, "max_z": 90,
            "operation": "add", "override": True}
    polys, _, _, _ = _compute_island_polys([sub, over])
    assert len(polys) == 1
    assert abs(polys[0].area - 80 * 80) < 1


def test_compute_island_polys_empty():
    polys, _, _, _ = _compute_island_polys([])
    assert polys == []


# ── _rasterise_full_layout ────────────────────────────────────────────────────

def test_rasterise_full_layout_rot_180_doubles_blocks():
    polys = [box(10, 10, 20, 20)]
    metas = [{"mirrors": True}]
    setup = {"mirror_mode": "rot_180", "center": {"cx": 0, "cz": 0}}
    blocks = _rasterise_full_layout(polys, metas, setup)
    # Primary 10×10 + rotated 10×10 mirror = 200 blocks (no overlap)
    assert len(blocks) == 200


def test_rasterise_full_layout_mirrors_false_no_copy():
    polys = [box(10, 10, 20, 20)]
    metas = [{"mirrors": False}]
    setup = {"mirror_mode": "rot_180", "center": {"cx": 0, "cz": 0}}
    blocks = _rasterise_full_layout(polys, metas, setup)
    assert len(blocks) == 100  # only primary sector


def test_rasterise_full_layout_rot_90_three_copies():
    polys = [box(10, 10, 20, 20)]
    metas = [{"mirrors": True}]
    setup = {"mirror_mode": "rot_90", "center": {"cx": 0, "cz": 0}}
    blocks = _rasterise_full_layout(polys, metas, setup)
    # 4 sectors (primary + 3 copies), no overlap far from origin
    assert len(blocks) == 400


# ── _make_slug ────────────────────────────────────────────────────────────────

def test_make_slug_basic():
    slug = _make_slug("My CTW Map", "abcd1234-5678")
    assert slug == "my-ctw-map-abcd1234"


def test_make_slug_empty_name():
    slug = _make_slug("", "abcd1234-5678")
    assert slug == "abcd1234"


def test_make_slug_special_chars():
    slug = _make_slug("Foo & Bar!!!", "aaaa0000")
    assert slug == "foo-bar-aaaa0000"


# ── export_sketch integration ─────────────────────────────────────────────────

@pytest.fixture()
def sketch_env(tmp_path, monkeypatch):
    """Patch SKETCHES_DIR and output_root to tmp_path."""
    monkeypatch.setattr(sketch_data, "SKETCHES_DIR", tmp_path / "sketches")
    import pgm_map_studio.studio.services.sketch_export as se
    monkeypatch.setattr(se, "get_output_root", lambda: tmp_path / "output")
    return tmp_path


def _make_two_island_sketch(sketch_env):
    sid = sketch_data.create_sketch()
    sketch_data.save_overview(sid, {"name": "Test Map", "version": "1.0"})
    sketch_data.save_setup(sid, {
        "bbox": {"min_x": -100, "max_x": 100, "min_z": -100, "max_z": 100},
        "center": {"cx": 0, "cz": 0},
        "mirror_mode": "rot_180",
    })
    sketch_data.save_layout(sid, [
        {"id": "s1", "type": "rectangle",
         "min_x": 10, "max_x": 50, "min_z": 10, "max_z": 50,
         "operation": "add", "override": False},
        {"id": "s2", "type": "rectangle",
         "min_x": -50, "max_x": -10, "min_z": -50, "max_z": -10,
         "operation": "add", "override": False},
    ], [
        {"id": "isl_a", "name": "Alpha", "mirrors": True, "shapeIds": ["s1"]},
        {"id": "isl_b", "name": "Beta",  "mirrors": True, "shapeIds": ["s2"]},
    ])
    return sid


def test_export_creates_output_files(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    out_dir = sketch_env / "output" / result["slug"]
    assert (out_dir / "layer.parquet").exists()
    assert (out_dir / "islands.json").exists()
    assert (out_dir / "symmetry.json").exists()
    assert (out_dir / "xml_data.json").exists()
    # A11: the editor side view needs layer_segments.parquet or it shows
    # "No segment data" (it can't fall back to a maps_folder world for a sketch).
    assert (out_dir / "layer_segments.parquet").exists()


def test_export_segments_parquet_schema(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    out_dir = sketch_env / "output" / result["slug"]
    df = pd.read_parquet(out_dir / "layer_segments.parquet")
    assert {"world_x", "world_z", "world_y_start", "world_y_end"} <= set(df.columns)
    assert len(df) > 0
    assert (df["world_y_start"] == 0).all() and (df["world_y_end"] == 0).all()


def test_export_regions_filters_are_dicts(sketch_env):
    # A11: regions/filters must be id-keyed dicts (not lists), or the editor's
    # /regions/tree (encode_region_tree → .values()) crashes and the canvas
    # stays stuck on "Loading map…".
    from pgm_map_studio.studio.services.region_encoder import encode_region_tree
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    out_dir = sketch_env / "output" / result["slug"]
    xml = json.loads((out_dir / "xml_data.json").read_text())
    assert isinstance(xml["regions"], dict) and isinstance(xml["filters"], dict)
    assert encode_region_tree(xml["regions"], {}, None) == []  # no crash


def test_export_layer_parquet_schema(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    out_dir = sketch_env / "output" / result["slug"]
    df = pd.read_parquet(out_dir / "layer.parquet")
    assert {"world_x", "world_z", "block_id", "block_data"} <= set(df.columns)
    assert len(df) > 0
    assert (df["block_id"] == 1).all()


def test_export_layer_includes_mirror_blocks(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    out_dir = sketch_env / "output" / result["slug"]
    df = pd.read_parquet(out_dir / "layer.parquet")
    # The two islands are rot_180 symmetric with each other (s1 at [10,50]×[10,50]
    # mirrors to [-50,-10]×[-50,-10] = s2's position, and vice versa).
    # Unique blocks = 2 × 40×40 = 3200 (mirror copies deduplicate with the other island).
    assert len(df) == 3200


def test_export_islands_json_content(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    out_dir = sketch_env / "output" / result["slug"]
    islands = json.loads((out_dir / "islands.json").read_text())
    # 2 primary islands × 2 (primary + rot_180 mirror copy each) = 4 total
    assert len(islands) == 4
    names = {i["name"] for i in islands}
    assert names == {"Alpha", "Beta"}
    assert all("polygon" in i for i in islands)
    # IDs must be sequential
    assert [i["id"] for i in islands] == [1, 2, 3, 4]


def test_export_symmetry_json_confirmed(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    out_dir = sketch_env / "output" / result["slug"]
    sym = json.loads((out_dir / "symmetry.json").read_text())
    assert sym["status"] == "confirmed"
    assert sym["primary"]["type"] == "rot_180"
    assert sym["center"]["cx"] == 0.0


def test_export_xml_data_json_identity(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    out_dir = sketch_env / "output" / result["slug"]
    xml = json.loads((out_dir / "xml_data.json").read_text())
    assert xml["name"] == "Test Map"
    assert xml["gamemode"] == "ctw"
    assert xml["sketch_session"] == sid


def test_export_slug_stable_on_reexport(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    r1 = export_sketch(sid)
    r2 = export_sketch(sid)
    assert r1["slug"] == r2["slug"]


def test_export_editor_url_uses_slug(sketch_env):
    sid = _make_two_island_sketch(sketch_env)
    result = export_sketch(sid)
    assert result["editor_url"].startswith("/editor?map=")
    assert result["slug"] in result["editor_url"]


def test_export_raises_on_fewer_than_two_islands(sketch_env):
    sid = sketch_data.create_sketch()
    sketch_data.save_layout(sid, [
        {"id": "s1", "type": "rectangle",
         "min_x": 0, "max_x": 20, "min_z": 0, "max_z": 20,
         "operation": "add", "override": False},
    ], [])
    with pytest.raises(ValueError, match="2 islands"):
        export_sketch(sid)


def test_export_raises_on_missing_sketch(sketch_env):
    with pytest.raises(KeyError):
        export_sketch("nonexistent-id")
