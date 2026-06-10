"""Region parser: all XML region type parsers, synthetic ID injection, and registry building.

All named and anonymous regions end up in a single flat registry
(dict[str, Region]).  Composite regions reference their children by ID string.
Anonymous regions receive stable synthetic IDs of the form
``{parent_id}__anon_{xml_index}`` where ``xml_index`` is the child's
ordinal position in the parent XML element (0-based, fixed at parse time).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from .regions import (
    Region, Rectangle, Cuboid, Cylinder, Circle, Sphere, Block, Point,
    Union, Negative, Complement, Intersect, Mirror, Translate,
    Half, Reference, Everywhere, Above, _b2d, parse_coord, reflect_bounds_2d,
)
from .datatypes import ApplyRule


def _source_ref_id(child: Optional[Region]) -> str:
    """Resolve the registry id a transform's inline source points at.

    An inline ``<region id="X"/>`` source is parsed as a ``Reference`` whose own
    ``id`` is blank (references aren't registered), so use its ``ref_id``. A real
    inline region (named or synthetic) is registered, so use its ``id``.
    """
    if child is None:
        return ""
    if isinstance(child, Reference):
        return child.ref_id
    return child.id


class RegionParser:
    """Stateful parser that builds a flat region registry from a <regions> element."""

    def __init__(self):
        self._registry: dict[str, Region] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_regions_elem(
        self, regions_elem: ET.Element
    ) -> tuple[dict[str, Region], list[ApplyRule]]:
        """Parse a <regions> element, returning (registry, apply_rules)."""
        apply_rules: list[ApplyRule] = []
        apply_count = 0

        for child in regions_elem:
            if child.tag == 'apply':
                apply_rules.append(self._parse_apply(child, apply_count))
                apply_count += 1
            else:
                region = self._parse_region_node(child, parent_id="")
                if region is not None and region.id:
                    self._registry[region.id] = region

        return self._registry, apply_rules

    def parse_spawn_region(
        self, elem: ET.Element, synthetic_id: str
    ) -> Optional[Region]:
        """Parse a spawn's inline region child and register it under synthetic_id.

        Returns the Region object (also stored in the registry).
        """
        region = self._parse_region_element(elem, parent_id=synthetic_id)
        if region is not None:
            if not region.id:
                region.id = synthetic_id
            if region.id not in self._registry:
                self._registry[region.id] = region
        return region

    def resolve_reference(self, ref_id: str) -> Optional[Region]:
        """Look up a named region by ID in the registry."""
        return self._registry.get(ref_id)

    def registry(self) -> dict[str, Region]:
        """The flat region registry — named regions plus synthetic/inline ones
        (e.g. regions registered while parsing inline ``<spawn><region>`` blocks)."""
        return self._registry

    # ------------------------------------------------------------------
    # Internal — coordinate helpers
    # ------------------------------------------------------------------

    def _parse_coords(self, coord_str: str) -> tuple[Optional[float], ...]:
        """Parse 'x,y,z' coordinate string."""
        parts = coord_str.split(',')
        if len(parts) >= 3:
            return (parse_coord(parts[0]), parse_coord(parts[1]), parse_coord(parts[2]))
        return (0.0, 0.0, 0.0)

    def _parse_coords_2d(self, coord_str: str) -> tuple[Optional[float], Optional[float]]:
        """Parse 'x,z' coordinate string."""
        parts = coord_str.split(',')
        if len(parts) >= 2:
            return (parse_coord(parts[0]), parse_coord(parts[1]))
        return (0.0, 0.0)

    # ------------------------------------------------------------------
    # Internal — region node dispatch
    # ------------------------------------------------------------------

    def _parse_region_node(
        self, elem: ET.Element, parent_id: str, index: int = 0
    ) -> Optional[Region]:
        """Parse a single region XML element into a Region, register it, return it."""
        tag = elem.tag
        region_id = elem.get('id', '')

        # Dispatch to type-specific parser
        region: Optional[Region] = None
        if tag == 'rectangle':
            region = self._parse_rectangle(elem, region_id)
        elif tag == 'cuboid':
            region = self._parse_cuboid(elem, region_id)
        elif tag == 'cylinder':
            region = self._parse_cylinder(elem, region_id)
        elif tag == 'circle':
            region = self._parse_circle(elem, region_id)
        elif tag == 'sphere':
            region = self._parse_sphere(elem, region_id)
        elif tag == 'block':
            region = self._parse_block(elem, region_id)
        elif tag == 'point':
            region = self._parse_point(elem, region_id)
        elif tag in ('union', 'negative', 'complement', 'intersect'):
            region = self._parse_composite(elem, region_id, parent_id, index, tag)
        elif tag == 'everywhere':
            region = Everywhere(id=region_id)
        elif tag == 'above':
            y = parse_coord(elem.get('y', '0')) or 0.0
            region = Above(id=region_id, y=y)
        elif tag == 'half':
            region = self._parse_half(elem, region_id)
        elif tag == 'mirror':
            region = self._parse_mirror(elem, region_id, parent_id, index)
        elif tag == 'translate':
            region = self._parse_translate(elem, region_id, parent_id, index)
        elif tag == 'region':
            ref_id = elem.get('id', '')
            if ref_id and len(elem) == 0:
                # Pure reference — resolved at serialization time
                region = Reference(ref_id=ref_id)
                region.id = ''  # references don't get their own registry entry
                return region
            region = self._parse_region_element(elem, parent_id, index)

        if region is None:
            return None

        # Assign synthetic ID if anonymous
        if not region.id:
            if parent_id:
                region.id = f"{parent_id}__anon_{index}"
            else:
                return region  # top-level anonymous — skip

        # Register in flat registry
        if region.id:
            self._registry[region.id] = region

        return region

    def _parse_region_element(
        self, parent_elem: ET.Element, parent_id: str = "", index: int = 0
    ) -> Optional[Region]:
        """Parse the first child region of a container element."""
        for i, child in enumerate(parent_elem):
            return self._parse_region_node(child, parent_id, i)
        return None

    # ------------------------------------------------------------------
    # Internal — composite helper
    # ------------------------------------------------------------------

    def _parse_composite(
        self,
        elem: ET.Element,
        region_id: str,
        parent_id: str,
        parent_index: int,
        tag: str,
    ) -> Region:
        """Parse a composite region (union / negative / complement / intersect)."""
        effective_id = region_id or (
            f"{parent_id}__anon_{parent_index}" if parent_id else ""
        )

        child_ids: list[str] = []
        for i, child_elem in enumerate(elem):
            child = self._parse_region_node(child_elem, effective_id, i)
            if child is not None:
                if isinstance(child, Reference):
                    child_ids.append(child.ref_id)
                elif child.id:
                    child_ids.append(child.id)

        cls_map = {
            'union': Union,
            'negative': Negative,
            'complement': Complement,
            'intersect': Intersect,
        }
        cls = cls_map[tag]
        region = cls(id=region_id, children=child_ids)
        region.bounds_2d = self._union_bounds(child_ids)
        return region

    # ------------------------------------------------------------------
    # Internal — primitive parsers
    # ------------------------------------------------------------------

    def _parse_rectangle(self, elem: ET.Element, region_id: str) -> Rectangle:
        min_x, min_z = self._parse_coords_2d(elem.get('min', '0,0'))
        max_x, max_z = self._parse_coords_2d(elem.get('max', '0,0'))
        return Rectangle(id=region_id, min_x=min_x, min_z=min_z, max_x=max_x, max_z=max_z)

    def _parse_cuboid(self, elem: ET.Element, region_id: str) -> Cuboid:
        size_str = elem.get('size', '')
        has_min = elem.get('min') is not None
        has_max = elem.get('max') is not None

        if size_str and has_min and not has_max:
            mn = self._parse_coords(elem.get('min'))
            sz = self._parse_coords(size_str)
            min_c = mn
            max_c = tuple(
                (a + b) if a is not None and b is not None else None
                for a, b in zip(mn, sz)
            )
        elif size_str and has_max and not has_min:
            mx = self._parse_coords(elem.get('max'))
            sz = self._parse_coords(size_str)
            max_c = mx
            min_c = tuple(
                (a - b) if a is not None and b is not None else None
                for a, b in zip(mx, sz)
            )
        else:
            min_c = self._parse_coords(elem.get('min', '0,0,0'))
            max_c = self._parse_coords(elem.get('max', '0,0,0'))

        return Cuboid(
            id=region_id,
            min_x=min_c[0], min_y=min_c[1], min_z=min_c[2],
            max_x=max_c[0], max_y=max_c[1], max_z=max_c[2],
        )

    def _parse_cylinder(self, elem: ET.Element, region_id: str) -> Cylinder:
        base = self._parse_coords(elem.get('base', '0,0,0'))
        radius_str = elem.get('radius', '0')
        radius = float(radius_str) if radius_str else 0.0
        height = parse_coord(elem.get('height', '0'))
        return Cylinder(
            id=region_id,
            base_x=base[0] or 0.0, base_y=base[1] or 0.0, base_z=base[2] or 0.0,
            radius=radius, height=height,
        )

    def _parse_circle(self, elem: ET.Element, region_id: str) -> Circle:
        cx, cz = self._parse_coords_2d(elem.get('center', '0,0'))
        radius = float(elem.get('radius', '0'))
        return Circle(id=region_id, center_x=cx or 0.0, center_z=cz or 0.0, radius=radius)

    def _parse_sphere(self, elem: ET.Element, region_id: str) -> Sphere:
        origin = self._parse_coords(elem.get('origin', '0,0,0'))
        radius = float(elem.get('radius', '0'))
        return Sphere(
            id=region_id,
            origin_x=origin[0] or 0.0, origin_y=origin[1] or 0.0,
            origin_z=origin[2] or 0.0, radius=radius,
        )

    def _parse_block(self, elem: ET.Element, region_id: str) -> Block:
        coords = self._parse_coords(elem.text or '0,0,0')
        return Block(id=region_id, x=coords[0] or 0.0, y=coords[1] or 0.0, z=coords[2] or 0.0)

    def _parse_point(self, elem: ET.Element, region_id: str) -> Point:
        coords = self._parse_coords(elem.text or '0,0,0')
        return Point(id=region_id, x=coords[0] or 0.0, y=coords[1] or 0.0, z=coords[2] or 0.0)

    def _parse_half(self, elem: ET.Element, region_id: str) -> Half:
        origin = self._parse_coords(elem.get('origin', '0,0,0'))
        normal = self._parse_coords(elem.get('normal', '0,0,0'))
        return Half(
            id=region_id,
            origin_x=origin[0] or 0.0, origin_y=origin[1] or 0.0, origin_z=origin[2] or 0.0,
            normal_x=normal[0] or 0.0, normal_y=normal[1] or 0.0, normal_z=normal[2] or 0.0,
        )

    def _parse_mirror(
        self, elem: ET.Element, region_id: str, parent_id: str, index: int
    ) -> Mirror:
        origin = self._parse_coords(elem.get('origin', '0,0,0'))
        normal = self._parse_coords(elem.get('normal', '0,0,0'))
        ref_id = elem.get('region', '')

        if ref_id:
            source_id = ref_id
        else:
            effective_parent = region_id or (
                f"{parent_id}__anon_{index}" if parent_id else ""
            )
            child = self._parse_region_element(elem, effective_parent, 0)
            source_id = _source_ref_id(child)

        mirror = Mirror(
            id=region_id, source_id=source_id,
            origin_x=origin[0] or 0.0, origin_y=origin[1] or 0.0, origin_z=origin[2] or 0.0,
            normal_x=normal[0] or 0.0, normal_y=normal[1] or 0.0, normal_z=normal[2] or 0.0,
        )
        mirror.bounds_2d = self._mirror_bounds(source_id, mirror)
        return mirror

    def _parse_translate(
        self, elem: ET.Element, region_id: str, parent_id: str, index: int
    ) -> Translate:
        offset = self._parse_coords(elem.get('offset', '0,0,0'))
        ref_id = elem.get('region', '')

        if ref_id:
            source_id = ref_id
        else:
            effective_parent = region_id or (
                f"{parent_id}__anon_{index}" if parent_id else ""
            )
            child = self._parse_region_element(elem, effective_parent, 0)
            source_id = _source_ref_id(child)

        translate = Translate(
            id=region_id, source_id=source_id,
            offset_x=offset[0] or 0.0, offset_y=offset[1] or 0.0, offset_z=offset[2] or 0.0,
        )
        translate.bounds_2d = self._translate_bounds(source_id, translate)
        return translate

    def _parse_apply(self, elem: ET.Element, apply_index: int = 0) -> ApplyRule:
        rule = ApplyRule(
            enter_filter=elem.get('enter', ''),
            leave_filter=elem.get('leave', ''),
            block_filter=elem.get('block', ''),
            block_place_filter=elem.get('block-place', ''),
            block_break_filter=elem.get('block-break', ''),
            block_physics_filter=elem.get('block-physics', ''),
            block_place_against_filter=elem.get('block-place-against', ''),
            use_filter=elem.get('use', ''),
            filter_id=elem.get('filter', ''),
            region_id=elem.get('region', ''),
            kit=elem.get('kit', ''),
            lend_kit=elem.get('lend-kit', ''),
            velocity=elem.get('velocity', ''),
            message=elem.get('message', ''),
        )
        # Inline region child element — parse, assign unique synthetic ID, register
        if not rule.region_id:
            synthetic_parent = f"__apply_{apply_index}"
            for child in elem:
                child_region = self._parse_region_node(child, synthetic_parent, 0)
                if child_region and child_region.id:
                    rule.region_id = child_region.id
                    break
        return rule

    # ------------------------------------------------------------------
    # Internal — bounds_2d helpers for composite/transform regions
    # ------------------------------------------------------------------

    def _union_bounds(self, child_ids: list[str]) -> Optional[dict]:
        """Compute bounding box as union of all children's bounds_2d."""
        min_x = min_z = float('inf')
        max_x = max_z = float('-inf')
        found = False
        for cid in child_ids:
            child = self._registry.get(cid)
            if child and child.bounds_2d:
                b = child.bounds_2d
                min_x = min(min_x, b['min']['x'])
                min_z = min(min_z, b['min']['z'])
                max_x = max(max_x, b['max']['x'])
                max_z = max(max_z, b['max']['z'])
                found = True
        return _b2d(min_x, min_z, max_x, max_z) if found else None

    def _mirror_bounds(self, source_id: str, mirror: Mirror) -> Optional[dict]:
        """Compute bounds_2d for a Mirror region from its source's bounds."""
        source = self._registry.get(source_id)
        if source is None or source.bounds_2d is None:
            return None
        return reflect_bounds_2d(
            source.bounds_2d,
            mirror.normal_x, mirror.normal_z,
            mirror.origin_x, mirror.origin_z,
        )

    def _translate_bounds(self, source_id: str, translate: Translate) -> Optional[dict]:
        """Compute bounds_2d for a Translate region from its source's bounds."""
        source = self._registry.get(source_id)
        if source is None or source.bounds_2d is None:
            return None
        b = source.bounds_2d
        dx, dz = translate.offset_x, translate.offset_z
        return _b2d(
            b['min']['x'] + dx, b['min']['z'] + dz,
            b['max']['x'] + dx, b['max']['z'] + dz,
        )
