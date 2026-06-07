"""region_tree — traversal and mutation helpers for the region dict tree.

All functions operate on the in-memory dict structure stored in xml_data.json.
No I/O, no Flask. These are used by region_editor.py to locate and patch
nodes inside the tree without round-tripping through the file.
"""
from __future__ import annotations


def collect_named_child_ids(region: dict, out: set[str]) -> None:
    """Recursively collect IDs of all named children of *region*."""
    for child in region.get("children", []):
        child_id = child.get("id") or ""
        if child_id:
            out.add(child_id)
        collect_named_child_ids(child, out)


def collect_region_subtree_ids(regions: dict, region_id: str) -> list[str]:
    """Return region_id and all descendant IDs found in *regions* (depth-first)."""
    result = [region_id]
    for child in regions.get(region_id, {}).get("children", []):
        child_id = child.get("id")
        if child_id and child_id in regions:
            result.extend(collect_region_subtree_ids(regions, child_id))
    return result


def remove_inline_children(regions: dict, ids_to_remove: set[str]) -> None:
    """Remove inline child entries matching *ids_to_remove* from every region's children list."""
    for region in regions.values():
        children = region.get("children")
        if isinstance(children, list):
            region["children"] = [c for c in children if c.get("id") not in ids_to_remove]


def rename_in_children(region: dict, old_id: str, new_id: str) -> None:
    """Recursively rename *old_id* → *new_id* inside a region's children array."""
    for child in region.get("children", []):
        if child.get("id") == old_id:
            child["id"] = new_id
        rename_in_children(child, old_id, new_id)


def find_parent_of_child(
    regions: dict,
    target_id: str,
) -> tuple[dict, dict, int] | None:
    """Search all regions for a child with *target_id*.

    Returns (parent_dict, child_dict, child_index) or None if not found.
    """
    def _walk(region: dict) -> tuple[dict, dict, int] | None:
        for i, child in enumerate(region.get("children", [])):
            if child.get("id") == target_id:
                return region, child, i
            result = _walk(child)
            if result is not None:
                return result
        return None

    for region in regions.values():
        result = _walk(region)
        if result is not None:
            return result
    return None


def find_child_region(regions_dict: dict, target_sid: str) -> dict | None:
    """Find a region by synthetic ID, searching recursively through children.

    Synthetic IDs: named children use their own xml id; anonymous children at
    index i of a parent with sid P get sid ``f"{P}__{i}"``.
    Returns the mutable child dict, or None if not found.
    """
    def _walk(region: dict, region_sid: str) -> dict | None:
        for i, child in enumerate(region.get("children", [])):
            child_xml_id = child.get("id", "")
            child_sid = child_xml_id if child_xml_id else f"{region_sid}__{i}"
            if child_sid == target_sid:
                return child
            result = _walk(child, child_sid)
            if result is not None:
                return result
        return None

    for rid, region in regions_dict.items():
        region_sid = region.get("id", "") or rid
        result = _walk(region, region_sid)
        if result is not None:
            return result
    return None


def rename_embedded_region(container: list, old_id: str, new_id: str) -> None:
    """Rename the id field on any embedded region copy matching *old_id*."""
    for item in container:
        for embedded in _walk_embedded(item):
            if embedded.get("id") == old_id:
                embedded["id"] = new_id


def patch_embedded_region(container: list, region_id: str, new_bounds_2d: dict) -> None:
    """Update bounds_2d on any embedded region copy matching *region_id*."""
    for item in container:
        for embedded in _walk_embedded(item):
            if embedded.get("id") == region_id:
                embedded["bounds_2d"] = new_bounds_2d


def patch_all_embedded_regions(data: dict, region_id: str, new_bounds_2d: dict) -> None:
    """Propagate a bounds_2d change to all embedded copies in spawns, wools, and observer_spawn."""
    patch_embedded_region(data.get("spawns", []), region_id, new_bounds_2d)
    patch_embedded_region(data.get("wools",  []), region_id, new_bounds_2d)
    if obs := data.get("observer_spawn"):
        patch_embedded_region([obs], region_id, new_bounds_2d)


# ── internals ─────────────────────────────────────────────────────────────────

def _walk_embedded(item: dict):
    """Yield each region dict embedded inside a spawn/wool/observer_spawn item."""
    for field in ("region", "monument"):
        embedded = item.get(field)
        if isinstance(embedded, dict):
            yield from _walk_region_recursive(embedded)


def _walk_region_recursive(region: dict):
    yield region
    for child in region.get("children", []):
        yield from _walk_region_recursive(child)
