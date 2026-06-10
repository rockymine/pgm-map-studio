"""Tests for region_encoder.encode_region_tree."""
import pytest
from pgm_map_studio.studio.services.region_encoder import encode_region_tree


def _tree(regions, cats=None, bbox=None):
    return encode_region_tree(regions, cats or {}, bbox)


# ── grouping ──────────────────────────────────────────────────────────────────

def test_empty_regions_returns_empty():
    assert _tree({}) == []


def test_mirror_resolves_source_id():
    """A mirror/translate persists its source as `source_id` into the flat registry.

    Regression for the encoder previously reading `source`/`ref_region_id` only,
    which left every corpus transform region unresolved (no source node, no polygon).
    """
    regions = {
        "red-spawn": {
            "id": "red-spawn", "type": "rectangle",
            "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 10, "z": 10}},
        },
        "blue-spawn": {
            "id": "blue-spawn", "type": "mirror", "source_id": "red-spawn",
            "origin": {"x": 50, "y": 0, "z": 0}, "normal": {"x": 1, "y": 0, "z": 0},
            "bounds_2d": {"min": {"x": 90, "z": 0}, "max": {"x": 100, "z": 10}},
        },
    }
    bbox = {"min_x": -10, "min_z": -10, "max_x": 110, "max_z": 110}
    nodes = [n for grp in encode_region_tree(regions, {}, bbox) for n in grp["regions"]]
    mirror = next(n for n in nodes if n["type"] == "mirror")
    assert mirror["source"] is not None and mirror["source"]["id"] == "red-spawn"
    assert mirror["coords"]["source_id"] == "red-spawn"
    # source_id resolved -> reflected geometry computed (rect mirrored across x=50)
    poly = mirror.get("polygon_2d")
    assert poly is not None
    xs = [p[0] for p in poly["exterior"]]
    assert min(xs) == 90 and max(xs) == 100


def test_single_region_goes_to_other_by_default():
    result = _tree({"r1": {"id": "r1", "type": "rectangle",
                           "min_x": 0, "min_z": 0, "max_x": 10, "max_z": 10}})
    assert len(result) == 1
    assert result[0]["name"] == "other"
    assert result[0]["regions"][0]["id"] == "r1"


def test_category_assignment():
    regions = {
        "sp1": {"id": "sp1", "type": "cylinder",
                "base": {"x": 0, "y": 64, "z": 0}, "radius": 5, "height": 3},
        "wr1": {"id": "wr1", "type": "rectangle",
                "min_x": 5, "min_z": 5, "max_x": 15, "max_z": 15},
    }
    cats = {"sp1": "spawn", "wr1": "wool"}
    result = _tree(regions, cats)
    names = [g["name"] for g in result]
    assert "spawn" in names
    assert "wool" in names
    assert "other" not in names


def test_category_order():
    regions = {
        "r_other": {"id": "r_other", "type": "rectangle",
                    "min_x": 0, "min_z": 0, "max_x": 1, "max_z": 1},
        "r_spawn": {"id": "r_spawn", "type": "rectangle",
                    "min_x": 0, "min_z": 0, "max_x": 1, "max_z": 1},
        "r_build": {"id": "r_build", "type": "rectangle",
                    "min_x": 0, "min_z": 0, "max_x": 1, "max_z": 1},
    }
    cats = {"r_spawn": "spawn", "r_build": "build", "r_other": "other"}
    result = _tree(regions, cats)
    names = [g["name"] for g in result]
    assert names.index("spawn") < names.index("build") < names.index("other")


# ── child suppression ─────────────────────────────────────────────────────────

def test_named_children_not_duplicated_at_root():
    regions = {
        "parent": {"id": "parent", "type": "union", "children": [
            {"id": "child1", "type": "rectangle",
             "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5},
        ]},
        "child1": {"id": "child1", "type": "rectangle",
                   "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5},
    }
    result = _tree(regions)
    root_ids = [n["id"] for g in result for n in g["regions"]]
    # child1 is a named child of parent — must not appear at root
    assert "child1" not in root_ids
    # parent is at root; its children list encodes child1 once
    assert "parent" in root_ids
    parent_node = next(n for g in result for n in g["regions"] if n["id"] == "parent")
    assert parent_node["children"][0]["id"] == "child1"


# ── node encoding ─────────────────────────────────────────────────────────────

def test_rectangle_coords_encoded():
    regions = {"r": {"id": "r", "type": "rectangle",
                     "min_x": 10, "min_z": 20, "max_x": 30, "max_z": 40}}
    result = _tree(regions)
    node = result[0]["regions"][0]
    assert node["coords"]["min_x"] == 10
    assert node["coords"]["max_z"] == 40


def test_cylinder_coords_encoded():
    regions = {"cy": {"id": "cy", "type": "cylinder",
                      "base": {"x": 5, "y": 64, "z": 15},
                      "radius": 8, "height": 4}}
    result = _tree(regions)
    node = result[0]["regions"][0]
    c = node["coords"]
    assert c["base_x"] == 5
    assert c["radius"] == 8


def test_synthetic_label_for_anonymous_child():
    regions = {
        "u": {"id": "u", "type": "union", "children": [
            {"type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5},
        ]},
    }
    result = _tree(regions)
    children = result[0]["regions"][0]["children"]
    assert len(children) == 1
    assert children[0]["synthetic_id"] is True


def test_unknown_category_falls_back_to_other():
    regions = {"x": {"id": "x", "type": "rectangle",
                     "min_x": 0, "min_z": 0, "max_x": 1, "max_z": 1}}
    result = _tree(regions, {"x": "nonexistent_cat"})
    assert result[0]["name"] == "other"


# ── polygon_2d ────────────────────────────────────────────────────────────────

def test_polygon_2d_computed_for_union_when_bbox_given():
    pytest.importorskip("shapely")
    regions = {
        "u": {"id": "u", "type": "union", "children": [
            {"type": "rectangle", "id": "c1",
             "min_x": 0, "min_z": 0, "max_x": 10, "max_z": 10},
            {"type": "rectangle", "id": "c2",
             "min_x": 5, "min_z": 5, "max_x": 15, "max_z": 15},
        ]},
    }
    bbox = {"min_x": -100, "min_z": -100, "max_x": 100, "max_z": 100}
    result = _tree(regions, {}, bbox)
    node = result[0]["regions"][0]
    assert "polygon_2d" in node
    assert "exterior" in node["polygon_2d"]


def test_no_polygon_2d_without_bbox():
    regions = {
        "u": {"id": "u", "type": "union", "children": [
            {"type": "rectangle", "id": "c1",
             "min_x": 0, "min_z": 0, "max_x": 10, "max_z": 10},
        ]},
    }
    result = _tree(regions, {}, None)
    node = result[0]["regions"][0]
    assert "polygon_2d" not in node


def test_bounding_box_none_is_safe():
    regions = {"r": {"id": "r", "type": "rectangle",
                     "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5}}
    result = _tree(regions, {}, None)
    assert result[0]["regions"][0]["id"] == "r"
