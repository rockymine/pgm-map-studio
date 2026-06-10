"""Filter parser: builds a flat filter registry from a PGM <filters> element.

Every filter element that carries an ``id`` attribute — regardless of nesting
depth — is registered in the flat registry so it can be referenced by name
from apply rules or other filters.  Anonymous children receive stable synthetic
IDs of the form ``{parent_id}__anon_{xml_index}``.

The ``<filter id="ref"/>`` element is a pure reference; it resolves to the
target filter's ID and is never itself inserted into the registry.

Inline filter shorthand values (e.g. ``deny(void)``, ``all(only-blue,wr)``)
that appear as apply-rule attribute values are stored verbatim as strings —
they are PGM runtime expressions, not parseable IDs.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from .filters import (
    Filter, AllFilter, AnyFilter, OneFilter,
    NotFilter, DenyFilter, AllowFilter,
    TeamFilter, MaterialFilter, VoidFilter, CauseFilter,
    BlocksFilter, CarryingFilter, WearingFilter, HoldingFilter,
    AliveFilter, DeadFilter, ParticipatingFilter, ObservingFilter,
    MatchRunningFilter, MatchStartedFilter, GroundedFilter,
    NeverFilter, AlwaysFilter,
    TimeFilter, AfterFilter, PulseFilter,
    OffsetFilter, VariableFilter,
    CompletedFilter, ObjectiveFilter,
    FilterRef, KillStreakFilter, ClassFilter,
    RegionFilter, PlayerFilter, SpawnFilter,
)


class FilterParser:
    """Stateful parser that builds a flat filter registry from a <filters> element.

    The registry is pre-seeded with PGM built-in filter names (``never``,
    ``always``) so that maps using these without explicit ``<filters>``
    declarations don't produce dangling references.
    """

    def __init__(self):
        self._registry: dict[str, Filter] = {
            'never': NeverFilter(id='never'),
            'always': AlwaysFilter(id='always'),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_filters_elem(self, filters_elem: ET.Element) -> dict[str, Filter]:
        """Parse a <filters> element; return the flat registry."""
        for i, child in enumerate(filters_elem):
            f = self._parse_filter_node(child, parent_id="", index=i)
            if f is not None and not isinstance(f, FilterRef) and f.id:
                self._registry.setdefault(f.id, f)
        return self._registry

    def registry(self) -> dict[str, Filter]:
        """The flat filter registry, pre-seeded with the PGM built-ins
        (``never``/``always``) even when the map has no ``<filters>`` block."""
        return self._registry

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------

    def _parse_filter_node(
        self, elem: ET.Element, parent_id: str, index: int = 0
    ) -> Optional[Filter]:
        tag = elem.tag
        filter_id = elem.get('id', '')

        f: Optional[Filter] = None

        if tag in ('all', 'any', 'one'):
            f = self._parse_composite(elem, filter_id, parent_id, index, tag)
        elif tag in ('not', 'deny', 'allow'):
            f = self._parse_single_child(elem, filter_id, parent_id, index, tag)
        elif tag == 'team':
            f = TeamFilter(id=filter_id, team=(elem.text or '').strip())
        elif tag == 'material':
            f = MaterialFilter(id=filter_id, material=(elem.text or '').strip())
        elif tag == 'void':
            f = VoidFilter(id=filter_id)
        elif tag == 'cause':
            f = CauseFilter(id=filter_id, cause=(elem.text or '').strip())
        elif tag == 'blocks':
            f = self._parse_blocks(elem, filter_id, parent_id, index)
        elif tag == 'carrying':
            f = self._parse_item_filter(elem, filter_id, 'carrying')
        elif tag == 'wearing':
            f = self._parse_item_filter(elem, filter_id, 'wearing')
        elif tag == 'holding':
            f = self._parse_item_filter(elem, filter_id, 'holding')
        elif tag == 'alive':
            f = AliveFilter(id=filter_id)
        elif tag == 'dead':
            f = DeadFilter(id=filter_id)
        elif tag == 'participating':
            f = ParticipatingFilter(id=filter_id)
        elif tag == 'observing':
            f = ObservingFilter(id=filter_id)
        elif tag == 'match-running':
            f = MatchRunningFilter(id=filter_id)
        elif tag == 'match-started':
            f = MatchStartedFilter(id=filter_id)
        elif tag == 'grounded':
            f = GroundedFilter(id=filter_id)
        elif tag == 'never':
            f = NeverFilter(id=filter_id)
        elif tag == 'always':
            f = AlwaysFilter(id=filter_id)
        elif tag == 'time':
            f = TimeFilter(id=filter_id, duration=(elem.text or '').strip())
        elif tag == 'after':
            f = AfterFilter(
                id=filter_id,
                filter_ref=elem.get('filter', ''),
                duration=elem.get('duration', ''),
            )
        elif tag == 'pulse':
            f = PulseFilter(
                id=filter_id,
                period=elem.get('period', ''),
                duration=elem.get('duration', ''),
                filter_ref=elem.get('filter', ''),
            )
        elif tag == 'offset':
            f = self._parse_offset(elem, filter_id, parent_id, index)
        elif tag == 'variable':
            f = VariableFilter(
                id=filter_id,
                var=elem.get('var', ''),
                value=(elem.text or '').strip(),
                team=elem.get('team', ''),
            )
        elif tag == 'completed':
            f = CompletedFilter(id=filter_id, objective=(elem.text or '').strip())
        elif tag == 'objective':
            f = ObjectiveFilter(id=filter_id, objective=(elem.text or '').strip())
        elif tag == 'filter':
            # Pure reference — return a FilterRef but don't register it
            return FilterRef(ref_id=elem.get('id', ''))
        elif tag == 'kill-streak':
            f = KillStreakFilter(
                id=filter_id,
                min=_safe_int(elem.get('min')),
                max=_safe_int(elem.get('max')),
                count=_safe_int(elem.get('count')),
            )
        elif tag == 'class':
            f = ClassFilter(id=filter_id, name=(elem.text or '').strip())
        elif tag == 'region':
            f = RegionFilter(id=filter_id, region=elem.get('id', ''))
        elif tag == 'players':
            f = PlayerFilter(
                id=filter_id,
                min=_safe_int(elem.get('min')),
                max=_safe_int(elem.get('max')),
            )
        elif tag == 'spawn':
            f = SpawnFilter(id=filter_id, mob=(elem.text or '').strip())
        else:
            return None

        if f is None:
            return None

        # Assign synthetic ID to anonymous elements that need one
        if not f.id:
            if parent_id:
                f.id = f"{parent_id}__anon_{index}"
            else:
                return f  # top-level anonymous — skip registration

        # Register in flat registry (setdefault: first definition wins)
        if f.id and not isinstance(f, FilterRef):
            self._registry.setdefault(f.id, f)

        return f

    # ------------------------------------------------------------------
    # Composite helpers
    # ------------------------------------------------------------------

    def _parse_composite(
        self,
        elem: ET.Element,
        filter_id: str,
        parent_id: str,
        parent_index: int,
        tag: str,
    ) -> Filter:
        """Parse all/any/one with children stored as ID strings."""
        effective_id = filter_id or (
            f"{parent_id}__anon_{parent_index}" if parent_id else ""
        )

        child_ids: list[str] = []
        for i, child_elem in enumerate(elem):
            child = self._parse_filter_node(child_elem, effective_id, i)
            if child is not None:
                if isinstance(child, FilterRef):
                    child_ids.append(child.ref_id)
                elif child.id:
                    child_ids.append(child.id)

        cls_map = {'all': AllFilter, 'any': AnyFilter, 'one': OneFilter}
        return cls_map[tag](id=filter_id, children=child_ids)

    def _parse_single_child(
        self,
        elem: ET.Element,
        filter_id: str,
        parent_id: str,
        parent_index: int,
        tag: str,
    ) -> Filter:
        """Parse not/deny/allow — each wraps exactly one child filter."""
        effective_id = filter_id or (
            f"{parent_id}__anon_{parent_index}" if parent_id else ""
        )

        child_id = ""
        for i, child_elem in enumerate(elem):
            child = self._parse_filter_node(child_elem, effective_id, i)
            if child is not None:
                child_id = child.ref_id if isinstance(child, FilterRef) else child.id
                break  # only first child

        cls_map = {'not': NotFilter, 'deny': DenyFilter, 'allow': AllowFilter}
        return cls_map[tag](id=filter_id, child=child_id)

    def _parse_blocks(
        self,
        elem: ET.Element,
        filter_id: str,
        parent_id: str,
        parent_index: int,
    ) -> BlocksFilter:
        """Parse <blocks region="...">...</blocks> — original block state check."""
        effective_id = filter_id or (
            f"{parent_id}__anon_{parent_index}" if parent_id else ""
        )
        region = elem.get('region', '')

        child_id = ""
        for i, child_elem in enumerate(elem):
            child = self._parse_filter_node(child_elem, effective_id, i)
            if child is not None:
                child_id = child.ref_id if isinstance(child, FilterRef) else child.id
                break

        return BlocksFilter(id=filter_id, region=region, child=child_id)

    def _parse_item_filter(
        self, elem: ET.Element, filter_id: str, kind: str
    ) -> Filter:
        """Parse carrying/wearing/holding — contain a single <item> child."""
        ignore_metadata = elem.get('ignore-metadata', 'false').lower() == 'true'
        ignore_durability_str = elem.get('ignore-durability', 'true').lower()
        ignore_durability = ignore_durability_str != 'false'

        material = ""
        damage: Optional[int] = None
        enchantments = ""

        item_elem = elem.find('item')
        if item_elem is not None:
            material = item_elem.get('material', '').strip()
            dmg_str = item_elem.get('damage', '')
            if dmg_str:
                try:
                    damage = int(dmg_str)
                except ValueError:
                    pass
            enchantments = item_elem.get('enchantment', '').strip()
        else:
            # Some maps have text content instead of <item> child
            text = (elem.text or '').strip()
            if text:
                material = text

        if kind == 'carrying':
            return CarryingFilter(
                id=filter_id, material=material, damage=damage,
                enchantments=enchantments,
                ignore_metadata=ignore_metadata,
                ignore_durability=ignore_durability,
            )
        elif kind == 'wearing':
            return WearingFilter(
                id=filter_id, material=material, damage=damage,
                ignore_metadata=ignore_metadata,
            )
        else:  # holding
            return HoldingFilter(id=filter_id, material=material, damage=damage)

    def _parse_offset(
        self,
        elem: ET.Element,
        filter_id: str,
        parent_id: str,
        parent_index: int,
    ) -> OffsetFilter:
        """Parse <offset vector="...">...</offset>."""
        effective_id = filter_id or (
            f"{parent_id}__anon_{parent_index}" if parent_id else ""
        )
        vector = elem.get('vector', '')

        child_id = ""
        for i, child_elem in enumerate(elem):
            child = self._parse_filter_node(child_elem, effective_id, i)
            if child is not None:
                child_id = child.ref_id if isinstance(child, FilterRef) else child.id
                break

        return OffsetFilter(id=filter_id, vector=vector, child=child_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return None


def is_shorthand(value: str) -> bool:
    """Return True if a filter attribute value is an inline shorthand expression.

    Shorthand values contain ``(`` and are PGM runtime expressions such as
    ``deny(void)``, ``all(only-blue,wr-filter)``, or variable comparisons like
    ``var=1``.  They are stored verbatim rather than resolved as registry IDs.
    """
    return '(' in value
