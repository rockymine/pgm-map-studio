"""Tests for studio/services/region_editor.py and region_builder.py."""
import pytest

from pgm_map_studio.studio.services.region_editor import (
    InvalidRegionPayload,
    RegionConflict,
    RegionNotFound,
    create_region,
    delete_region,
    group_regions,
    patch_region,
    restore_region,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _rect(region_id: str) -> dict:
    return {
        "id": region_id, "type": "rectangle",
        "min_x": 0, "min_z": 0, "max_x": 10, "max_z": 10,
        "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 10, "z": 10}},
    }


def _cyl(region_id: str) -> dict:
    return {
        "id": region_id, "type": "cylinder",
        "base": {"x": 0.0, "y": 64.0, "z": 0.0},
        "radius": 5.0, "height": 10.0,
        "bounds_2d": {"min": {"x": -5.0, "z": -5.0}, "max": {"x": 5.0, "z": 5.0}},
    }


# ── create_region ─────────────────────────────────────────────────────────────

class TestCreateRegion:
    def test_auto_id_rectangle(self):
        data = {}
        result = create_region(data, {"type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5})
        assert result["id"] == "region_1"
        assert "region_1" in data["regions"]

    def test_auto_id_increments(self):
        data = {"regions": {"region_1": _rect("region_1")}}
        result = create_region(data, {"type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5})
        assert result["id"] == "region_2"

    def test_explicit_id(self):
        data = {}
        result = create_region(data, {"type": "point", "id": "my_point", "x": 10, "y": 64, "z": 10})
        assert result["id"] == "my_point"
        assert "my_point" in data["regions"]

    def test_cylinder_auto_id(self):
        data = {}
        result = create_region(data, {"type": "cylinder", "base_x": 0, "base_z": 0, "radius": 5})
        assert result["id"] == "cylinder_1"

    def test_point_auto_id(self):
        data = {}
        result = create_region(data, {"type": "point", "x": 0, "y": 64, "z": 0})
        assert result["id"] == "point_1"

    def test_category_recorded(self):
        data = {}
        create_region(data, {
            "type": "cylinder", "base_x": 0, "base_z": 0, "radius": 5, "category": "spawn",
        })
        assert "cylinder_1" in data["region_categories"]["spawn"]

    def test_default_category_is_other(self):
        data = {}
        create_region(data, {"type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5})
        assert "region_1" in data["region_categories"]["other"]

    def test_unsupported_type_raises(self):
        with pytest.raises(InvalidRegionPayload):
            create_region({}, {"type": "polygon"})

    def test_duplicate_id_raises(self):
        data = {"regions": {"r1": _rect("r1")}}
        with pytest.raises(RegionConflict):
            create_region(data, {"type": "rectangle", "id": "r1", "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5})

    def test_missing_field_raises(self):
        with pytest.raises(InvalidRegionPayload):
            create_region({}, {"type": "rectangle"})  # missing coordinate fields

    def test_rectangle_bounds_2d_set(self):
        data = {}
        create_region(data, {"type": "rectangle", "min_x": -10, "min_z": -5, "max_x": 10, "max_z": 5})
        r = data["regions"]["region_1"]
        assert r["bounds_2d"]["min"] == {"x": -10, "z": -5}
        assert r["bounds_2d"]["max"] == {"x": 10, "z": 5}

    def test_cylinder_bounds_2d_set(self):
        data = {}
        create_region(data, {"type": "cylinder", "base_x": 0.0, "base_z": 0.0, "radius": 5.0})
        r = data["regions"]["cylinder_1"]
        assert r["bounds_2d"]["min"]["x"] == -5.0
        assert r["bounds_2d"]["max"]["x"] == 5.0

    def test_point_bounds_2d_set(self):
        data = {}
        create_region(data, {"type": "point", "x": 10, "y": 64, "z": 20})
        r = data["regions"]["point_1"]
        assert r["bounds_2d"]["min"] == {"x": 9.5, "z": 19.5}
        assert r["bounds_2d"]["max"] == {"x": 10.5, "z": 20.5}


# ── group_regions ─────────────────────────────────────────────────────────────

class TestGroupRegions:
    def setup_method(self):
        self.data = {"regions": {"r1": _rect("r1"), "r2": _rect("r2")}}

    def test_creates_union(self):
        result = group_regions(self.data, {"child_ids": ["r1", "r2"]})
        assert result["id"] == "union_1"
        assert "union_1" in self.data["regions"]
        assert self.data["regions"]["union_1"]["type"] == "union"

    def test_explicit_union_id(self):
        result = group_regions(self.data, {"child_ids": ["r1", "r2"], "id": "my_union"})
        assert result["id"] == "my_union"

    def test_union_bounds_computed(self):
        self.data["regions"]["r1"]["bounds_2d"] = {"min": {"x": 0, "z": 0}, "max": {"x": 10, "z": 10}}
        self.data["regions"]["r2"]["bounds_2d"] = {"min": {"x": 5, "z": 5}, "max": {"x": 20, "z": 20}}
        result = group_regions(self.data, {"child_ids": ["r1", "r2"]})
        assert result["bounds"]["min_x"] == 0
        assert result["bounds"]["max_z"] == 20

    def test_too_few_children_raises(self):
        with pytest.raises(InvalidRegionPayload):
            group_regions(self.data, {"child_ids": ["r1"]})

    def test_missing_child_raises(self):
        with pytest.raises(RegionNotFound):
            group_regions(self.data, {"child_ids": ["r1", "ghost"]})

    def test_duplicate_union_id_raises(self):
        self.data["regions"]["union_1"] = _rect("union_1")
        with pytest.raises(RegionConflict):
            group_regions(self.data, {"child_ids": ["r1", "r2"], "id": "union_1"})


# ── delete_region ─────────────────────────────────────────────────────────────

class TestDeleteRegion:
    def test_delete_top_level(self):
        data = {
            "regions": {"r1": _rect("r1")},
            "region_categories": {"other": ["r1"]},
        }
        result = delete_region(data, "r1")
        assert "r1" not in data["regions"]
        assert "r1" not in data["region_categories"]["other"]
        assert result["snapshot"]["root_id"] == "r1"
        assert result["snapshot"]["category"] == "other"

    def test_delete_removes_from_category(self):
        data = {
            "regions": {"r1": _rect("r1")},
            "region_categories": {"spawn": ["r1"]},
        }
        delete_region(data, "r1")
        assert "r1" not in data["region_categories"]["spawn"]

    def test_delete_named_inline_child(self):
        child = {"id": "child1", "type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5}
        parent = {"id": "parent", "type": "union", "children": [child],
                  "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 5, "z": 5}}}
        data = {"regions": {"parent": parent}}
        result = delete_region(data, "child1")
        assert data["regions"]["parent"]["children"] == []
        assert result["snapshot"]["category"] is None

    def test_delete_subtree(self):
        child = {"id": "child1", "type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 5, "max_z": 5}
        parent = {"id": "parent", "type": "union", "children": [child],
                  "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 5, "z": 5}}}
        data = {
            "regions": {"parent": parent, "child1": child},
            "region_categories": {"other": ["parent", "child1"]},
        }
        delete_region(data, "parent")
        assert "parent" not in data["regions"]
        assert "child1" not in data["regions"]

    def test_not_found_raises(self):
        with pytest.raises(RegionNotFound):
            delete_region({"regions": {}}, "ghost")

    def test_delete_succeeds_when_bystander_has_string_children(self):
        # Regression: remove_inline_children crashed on string-ref children when
        # deleting any region while the registry contained composite regions that
        # reference other named regions by string ID rather than inline dicts.
        data = {
            "regions": {
                "target": _cyl("target"),
                "composite": {"id": "composite", "type": "union", "children": ["ref_a", "ref_b"]},
            },
            "region_categories": {"spawn": ["target"]},
        }
        result = delete_region(data, "target")
        assert "target" not in data["regions"]
        assert data["regions"]["composite"]["children"] == ["ref_a", "ref_b"]
        assert result["snapshot"]["root_id"] == "target"


# ── restore_region ────────────────────────────────────────────────────────────

class TestRestoreRegion:
    def test_restore_top_level(self):
        data = {"regions": {}}
        snapshot = {
            "root_id": "r1",
            "category": "spawn",
            "region_entries": {"r1": _rect("r1")},
        }
        result = restore_region(data, snapshot)
        assert result["id"] == "r1"
        assert "r1" in data["regions"]
        assert "r1" in data["region_categories"]["spawn"]

    def test_restore_conflict_raises(self):
        data = {"regions": {"r1": _rect("r1")}}
        snapshot = {"root_id": "r1", "category": "other", "region_entries": {"r1": _rect("r1")}}
        with pytest.raises(RegionConflict):
            restore_region(data, snapshot)

    def test_restore_inline_child(self):
        parent = {"id": "parent", "type": "union", "children": []}
        data = {"regions": {"parent": parent}}
        child = {"id": "", "type": "rectangle"}
        snapshot = {
            "root_id": "parent__0",
            "category": None,
            "parent_id": "parent",
            "child_index": 0,
            "region_entries": {"parent__0": child},
        }
        restore_region(data, snapshot)
        assert data["regions"]["parent"]["children"] == [child]

    def test_restore_missing_parent_raises(self):
        snapshot = {
            "root_id": "parent__0",
            "category": None,
            "parent_id": "ghost",
            "child_index": 0,
            "region_entries": {"parent__0": {}},
        }
        with pytest.raises(RegionNotFound):
            restore_region({"regions": {}}, snapshot)

    def test_invalid_snapshot_raises(self):
        with pytest.raises(InvalidRegionPayload):
            restore_region({}, {"root_id": "", "region_entries": {}})

    def test_delete_then_restore_roundtrip(self):
        data = {
            "regions": {"r1": _rect("r1")},
            "region_categories": {"spawn": ["r1"]},
        }
        del_result = delete_region(data, "r1")
        assert "r1" not in data["regions"]
        restore_region(data, del_result["snapshot"])
        assert "r1" in data["regions"]
        assert "r1" in data["region_categories"]["spawn"]


# ── patch_region ──────────────────────────────────────────────────────────────

class TestPatchRegion:
    def _data(self) -> dict:
        return {
            "regions": {"r1": _rect("r1")},
            "region_categories": {"other": ["r1"]},
        }

    def test_rename(self):
        data = self._data()
        patch_region(data, "r1", {"id": "r1_renamed"})
        assert "r1_renamed" in data["regions"]
        assert "r1" not in data["regions"]
        assert "r1_renamed" in data["region_categories"]["other"]
        assert "r1" not in data["region_categories"]["other"]

    def test_rename_updates_spawn_reference(self):
        data = {
            "regions": {"r1": _rect("r1")},
            "region_categories": {"spawn": ["r1"]},
            "spawns": [{"team": "red", "region": "r1", "yaw": 0, "kit": ""}],
        }
        patch_region(data, "r1", {"id": "spawn_red"})
        assert data["spawns"][0]["region"] == "spawn_red"

    def test_bounds_update(self):
        data = self._data()
        result = patch_region(data, "r1", {"bounds": {"min_x": 1, "min_z": 1, "max_x": 9, "max_z": 9}})
        assert "bounds" in result
        assert data["regions"]["r1"]["bounds_2d"]["min"]["x"] == 1

    def test_coords_update_cylinder(self):
        data = {"regions": {"c1": _cyl("c1")}, "region_categories": {"other": ["c1"]}}
        result = patch_region(data, "c1", {"coords": {"radius": 10.0}})
        assert "bounds" in result
        assert result["bounds"]["min_x"] == -10.0

    def test_coords_update_cylinder_center(self):
        data = {"regions": {"c1": _cyl("c1")}, "region_categories": {"other": ["c1"]}}
        patch_region(data, "c1", {"coords": {"base_x": 20.0, "base_z": 30.0}})
        r = data["regions"]["c1"]
        assert r["base"]["x"] == 20.0
        assert r["base"]["z"] == 30.0
        assert r["bounds_2d"]["min"]["x"] == 15.0

    def test_coords_update_point(self):
        data = {}
        create_region(data, {"type": "point", "x": 0, "y": 64, "z": 0})
        result = patch_region(data, "point_1", {"coords": {"x": 10, "z": 20}})
        assert "bounds" in result
        r = data["regions"]["point_1"]
        assert r["position"]["x"] == 10
        assert r["position"]["z"] == 20

    def test_empty_payload_raises(self):
        data = self._data()
        with pytest.raises(InvalidRegionPayload):
            patch_region(data, "r1", {})

    def test_not_found_raises(self):
        with pytest.raises(RegionNotFound):
            patch_region({"regions": {}}, "ghost", {"id": "new"})

    def test_rename_conflict_raises(self):
        data = {"regions": {"r1": _rect("r1"), "r2": _rect("r2")}, "region_categories": {}}
        with pytest.raises(RegionConflict):
            patch_region(data, "r1", {"id": "r2"})

    def test_rename_noop_same_id(self):
        data = self._data()
        patch_region(data, "r1", {"id": "r1"})
        assert "r1" in data["regions"]


# ── region_builder helpers ────────────────────────────────────────────────────

class TestBuildRegionDict:
    def test_rectangle(self):
        from pgm_map_studio.studio.services.region_builder import build_region_dict
        r = build_region_dict("rectangle", {"min_x": -5, "min_z": -5, "max_x": 5, "max_z": 5}, "r1")
        assert r["type"] == "rectangle"
        assert r["min_x"] == -5
        assert r["bounds_2d"]["max"] == {"x": 5, "z": 5}

    def test_cuboid_default_y(self):
        from pgm_map_studio.studio.services.region_builder import build_region_dict
        r = build_region_dict("cuboid", {"min_x": 0, "min_z": 0, "max_x": 10, "max_z": 10}, "c")
        assert r["min_y"] == 0
        assert r["max_y"] == 256

    def test_cylinder(self):
        from pgm_map_studio.studio.services.region_builder import build_region_dict
        r = build_region_dict("cylinder", {"base_x": 0, "base_z": 0, "radius": 8}, "cyl")
        assert r["radius"] == 8.0
        assert r["bounds_2d"]["min"]["x"] == -8.0

    def test_point(self):
        from pgm_map_studio.studio.services.region_builder import build_region_dict
        r = build_region_dict("point", {"x": 5, "y": 64, "z": 10}, "p")
        assert r["position"] == {"x": 5, "y": 64, "z": 10}
        assert r["bounds_2d"]["min"] == {"x": 4.5, "z": 9.5}

    def test_unsupported_raises(self):
        from pgm_map_studio.studio.services.region_builder import build_region_dict
        with pytest.raises(ValueError):
            build_region_dict("hexagon", {}, "h")


class TestBuildUnionBounds:
    def test_two_bounded_children(self):
        from pgm_map_studio.studio.services.region_builder import build_union_bounds
        children = [
            {"bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 10, "z": 10}}},
            {"bounds_2d": {"min": {"x": 5, "z": 5}, "max": {"x": 20, "z": 20}}},
        ]
        bounds_2d, min_x, min_z, max_x, max_z = build_union_bounds(children)
        assert min_x == 0 and min_z == 0
        assert max_x == 20 and max_z == 20

    def test_no_bounded_children(self):
        from pgm_map_studio.studio.services.region_builder import build_union_bounds
        bounds_2d, min_x, min_z, max_x, max_z = build_union_bounds([{}])
        assert bounds_2d is None
        assert min_x == min_z == max_x == max_z == 0.0
