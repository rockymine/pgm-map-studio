"""Tests for studio/services/region_tree.py."""
from pgm_map_studio.studio.services.region_tree import remove_inline_children


class TestRemoveInlineChildren:
    def test_removes_matching_dict_child(self):
        regions = {
            "parent": {"children": [{"id": "target"}, {"id": "keep"}]},
        }
        remove_inline_children(regions, {"target"})
        assert regions["parent"]["children"] == [{"id": "keep"}]

    def test_removes_matching_string_child(self):
        # string-ref children: composite regions that name other top-level regions by ID
        regions = {
            "union": {"children": ["target", "keep"]},
        }
        remove_inline_children(regions, {"target"})
        assert regions["union"]["children"] == ["keep"]

    def test_mixed_string_and_dict_children(self):
        regions = {
            "union": {"children": ["target", {"id": "also_target"}, "keep", {"id": "keep2"}]},
        }
        remove_inline_children(regions, {"target", "also_target"})
        assert regions["union"]["children"] == ["keep", {"id": "keep2"}]

    def test_bystander_with_string_children_not_affected_by_unrelated_delete(self):
        # Deleting a leaf region must not crash even when other regions have string children.
        regions = {
            "leaf": {"type": "cylinder"},
            "composite": {"children": ["ref_a", "ref_b"]},
        }
        remove_inline_children(regions, {"leaf"})
        assert regions["composite"]["children"] == ["ref_a", "ref_b"]

    def test_no_children_key_is_skipped(self):
        regions = {"plain": {"type": "rectangle"}}
        remove_inline_children(regions, {"plain"})  # must not raise
        assert "children" not in regions["plain"]
