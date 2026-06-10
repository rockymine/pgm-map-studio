"""Top-level PGM map.xml parser.

Orchestrates parsing of teams, kits, spawns, wools, spawners, renewables,
block_drop_rules, and apply_rules.  Region parsing is delegated to RegionParser.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional

from .datatypes import (
    MapXml, Team, Author, Kit, KitItem, KitArmor, Spawn, Wool,
    WoolSpawner, SpawnerItem, Renewable, BlockDropRule, BlockDropItem,
)
from .region_parser import RegionParser
from .filter_parser import FilterParser
from .regions import Region, Block, Point, parse_coord, Reference


def parse(xml_path: str) -> MapXml:
    """Parse a PGM map.xml file and return a MapXml dataclass."""
    return MapXmlParser(xml_path).parse()


class MapXmlParser:
    """Parser for PGM map.xml files."""

    def __init__(self, xml_path: str):
        self.xml_path = xml_path
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        self._region_parser = RegionParser()
        self._filter_parser = FilterParser()

    def parse(self) -> MapXml:
        """Parse the entire XML file and return MapXml."""
        self._resolve_variants(self.root)
        self._resolve_constants(self.root)

        data = MapXml()
        data.name = self._get_text('name', '')
        data.version = self._get_text('version', '')
        data.gamemode = self._get_text('gamemode', 'ctw') or 'ctw'
        data.objective = self._get_text('objective', '')
        data.authors = self._parse_authors()
        data.teams = self._parse_teams()
        data.kits = self._parse_kits()
        data.spawns, data.observer_spawn = self._parse_spawns()

        # Filters — parse before regions so filter IDs are available
        filters_elem = self.root.find('filters')
        if filters_elem is not None:
            data.filters = self._filter_parser.parse_filters_elem(filters_elem)

        # Regions and apply rules — must come before wools (monument ref lookup)
        regions_elem = self.root.find('regions')
        if regions_elem is not None:
            data.regions, data.apply_rules = self._region_parser.parse_regions_elem(
                regions_elem
            )
        else:
            # No <regions> block, but inline spawn regions may have been registered
            # during _parse_spawns; expose them so every spawn region id resolves.
            data.regions = self._region_parser.registry()

        # Resolve named spawn region references against the registry
        self._resolve_spawn_regions(data)

        data.wools = self._parse_wools(data.regions)
        data.spawners = self._parse_spawners()
        data.renewables = self._parse_renewables()
        data.block_drop_rules = self._parse_block_drop_rules()
        data.max_build_height = self._parse_max_build_height()

        return data

    # ------------------------------------------------------------------
    # Variant and constant resolution (verbatim from legacy)
    # ------------------------------------------------------------------

    def _resolve_variants(self, element: ET.Element) -> None:
        for child in list(element):
            self._resolve_variants(child)

        new_children = []
        changed = False
        for child in list(element):
            if child.tag in ('if', 'unless'):
                changed = True
                variants = {v.strip() for v in child.get('variant', '').split(',')}
                include = (child.tag == 'if' and 'default' in variants) or \
                          (child.tag == 'unless' and 'default' not in variants)
                if include:
                    new_children.extend(child)
            else:
                new_children.append(child)

        if changed:
            for child in list(element):
                element.remove(child)
            for child in new_children:
                element.append(child)

    def _resolve_constants(self, root: ET.Element) -> None:
        constants: dict[str, str] = {}
        for elem in root.iter('constant'):
            cid = elem.get('id', '').strip()
            value = (elem.text or '').strip()
            if cid:
                constants[cid] = value

        if not constants:
            return

        pattern = re.compile(r'\$\{([^}]+)\}')

        def _sub(value: str) -> str:
            return pattern.sub(lambda m: constants.get(m.group(1), m.group(0)), value)

        for elem in root.iter():
            for attr, val in list(elem.attrib.items()):
                if '${' in val:
                    elem.set(attr, _sub(val))

    # ------------------------------------------------------------------
    # Simple helpers
    # ------------------------------------------------------------------

    def _get_text(self, tag: str, default: str = '') -> str:
        elem = self.root.find(tag)
        return elem.text if elem is not None and elem.text else default

    # ------------------------------------------------------------------
    # Section parsers
    # ------------------------------------------------------------------

    def _parse_authors(self) -> list[Author]:
        authors: list[Author] = []
        authors_elem = self.root.find('authors')
        for elem in (list(authors_elem) if authors_elem is not None else []):
            if elem.tag == 'author':
                uuid = elem.get('uuid', '')
                if uuid:
                    authors.append(Author(uuid=uuid, role='author',
                                          contribution=elem.get('contribution', '')))
        contributors_elem = self.root.find('contributors')
        for elem in (list(contributors_elem) if contributors_elem is not None else []):
            if elem.tag == 'contributor':
                uuid = elem.get('uuid', '')
                if uuid:
                    authors.append(Author(uuid=uuid, role='contributor',
                                          contribution=elem.get('contribution', '')))
        return authors

    def _parse_teams(self) -> list[Team]:
        teams: list[Team] = []
        teams_elem = self.root.find('teams')
        if teams_elem is None:
            return teams
        for team_elem in teams_elem.findall('team'):
            teams.append(Team(
                id=team_elem.get('id', ''),
                color=team_elem.get('color', ''),
                max_players=int(team_elem.get('max', '0')),
                min_players=int(team_elem.get('min', '0')),
                name=team_elem.text or '',
                dye_color=team_elem.get('dye-color', ''),
            ))
        return teams

    def _parse_kits(self) -> list[Kit]:
        kits: list[Kit] = []
        kits_elem = self.root.find('kits')
        if kits_elem is None:
            return kits

        for kit_elem in kits_elem.findall('kit'):
            kit_id = kit_elem.get('id', '')
            if not kit_id:
                continue

            items: list[KitItem] = []
            for item_elem in kit_elem.findall('item'):
                material = item_elem.get('material', '').strip()
                if not material:
                    continue
                slot_str = item_elem.get('slot', '0')
                try:
                    slot = int(slot_str)
                except ValueError:
                    continue
                items.append(KitItem(
                    slot=slot,
                    material=material,
                    amount=int(item_elem.get('amount', '1')),
                    item_damage=int(item_elem.get('damage', '0')),
                    unbreakable=item_elem.get('unbreakable', '').lower() in ('true', '1', 'yes'),
                    team_color=item_elem.get('team-color', '').lower() in ('true', '1', 'yes'),
                    enchantments=self._collect_enchantments(item_elem),
                ))

            armor: list[KitArmor] = []
            for slot_name in ('helmet', 'chestplate', 'leggings', 'boots'):
                armor_elem = kit_elem.find(slot_name)
                if armor_elem is None:
                    continue
                material = armor_elem.get('material', '').strip()
                if not material:
                    continue
                armor.append(KitArmor(
                    slot_name=slot_name,
                    material=material,
                    unbreakable=armor_elem.get('unbreakable', '').lower() in ('true', '1', 'yes'),
                    team_color=armor_elem.get('team-color', '').lower() in ('true', '1', 'yes'),
                    enchantments=self._collect_enchantments(armor_elem),
                ))

            if items or armor:
                kits.append(Kit(id=kit_id, items=items, armor=armor))

        return kits

    @staticmethod
    def _collect_enchantments(elem: ET.Element) -> str:
        parts: list[str] = []
        attr = elem.get('enchantment', '').strip()
        if attr:
            for token in attr.split(';'):
                token = token.strip()
                if not token:
                    continue
                if ':' in token:
                    raw_name, _, raw_level = token.rpartition(':')
                    name = raw_name.strip().replace(' ', '_')
                    try:
                        level = int(raw_level.strip())
                    except ValueError:
                        level = 1
                else:
                    name = token.replace(' ', '_')
                    level = 1
                parts.append(f"{name}:{level}")
        for child in elem:
            if child.tag == 'enchantment':
                name = (child.text or '').strip().replace(' ', '_')
                try:
                    level = int(child.get('level', '1'))
                except ValueError:
                    level = 1
                if name:
                    parts.append(f"{name}:{level}")
        return ','.join(parts)

    def _parse_spawns(self) -> tuple[list[Spawn], Optional[Spawn]]:
        spawns: list[Spawn] = []
        observer_spawn: Optional[Spawn] = None
        spawns_elem = self.root.find('spawns')
        if spawns_elem is None:
            return spawns, observer_spawn

        spawn_elements, default_elem = self._collect_spawn_elements(spawns_elem)
        for spawn_elem, inherited_kit in spawn_elements:
            spawns.append(self._parse_spawn_element(spawn_elem, inherited_kit))

        if default_elem is not None:
            observer_spawn = self._parse_spawn_element(default_elem)

        return spawns, observer_spawn

    def _collect_spawn_elements(
        self, parent: ET.Element, inherited_kit: str = ''
    ) -> tuple[list[tuple[ET.Element, str]], Optional[ET.Element]]:
        spawn_results: list[tuple[ET.Element, str]] = []
        default_elem: Optional[ET.Element] = None
        for child in parent:
            if child.tag == 'spawn':
                spawn_results.append((child, inherited_kit))
            elif child.tag == 'default':
                if default_elem is None:
                    default_elem = child
            elif child.tag == 'spawns':
                kit = child.get('kit', '') or inherited_kit
                nested, nested_default = self._collect_spawn_elements(child, kit)
                spawn_results.extend(nested)
                if nested_default is not None and default_elem is None:
                    default_elem = nested_default
        return spawn_results, default_elem

    def _parse_spawn_element(self, elem: ET.Element, inherited_kit: str = '') -> Spawn:
        team = elem.get('team', '')
        region: Optional[Region] = None
        region_attr = elem.get('region', '')

        if region_attr:
            # Named reference — will be resolved after regions are parsed
            region = Reference(ref_id=region_attr)
        else:
            region_elem = elem.find('region')
            if region_elem is None:
                region_elem = elem.find('regions')
            if region_elem is not None:
                synthetic_id = f"__spawn_{team}" if team else "__observer_spawn"
                region = self._region_parser.parse_spawn_region(region_elem, synthetic_id)

        yaw_str = elem.get('yaw', '0')
        try:
            yaw = float(yaw_str)
        except ValueError:
            yaw = 0.0

        return Spawn(
            team=team,
            kit=elem.get('kit', '') or inherited_kit,
            yaw=yaw,
            region=region,
        )

    def _resolve_spawn_regions(self, data: MapXml) -> None:
        """Replace Reference objects on spawns with actual Region from registry."""
        for spawn in data.spawns:
            if isinstance(spawn.region, Reference):
                resolved = self._region_parser.resolve_reference(spawn.region.ref_id)
                if resolved is not None:
                    spawn.region = resolved
        if data.observer_spawn and isinstance(data.observer_spawn.region, Reference):
            resolved = self._region_parser.resolve_reference(
                data.observer_spawn.region.ref_id
            )
            if resolved is not None:
                data.observer_spawn.region = resolved

    def _parse_wools(self, regions: dict[str, Region]) -> list[Wool]:
        wools: list[Wool] = []
        wools_elems = self.root.findall('wools')
        if not wools_elems:
            return wools

        for wools_elem in wools_elems:
            outer_team = wools_elem.get('team', '')
            for wool_elem, inherited_team in self._collect_wool_elements(wools_elem, outer_team):
                location = self._parse_coords(wool_elem.get('location', '0,0,0'))
                monument, monument_region_id = self._resolve_monument(wool_elem, regions)
                wools.append(Wool(
                    team=wool_elem.get('team', '') or inherited_team,
                    color=wool_elem.get('color', ''),
                    location=location,
                    monument=monument,
                    monument_region_id=monument_region_id,
                ))
        return wools

    def _collect_wool_elements(
        self, parent: ET.Element, inherited_team: str = ''
    ) -> list[tuple[ET.Element, str]]:
        results = []
        for child in parent:
            if child.tag == 'wool':
                results.append((child, inherited_team))
            elif child.tag == 'wools':
                team = child.get('team', '') or inherited_team
                results.extend(self._collect_wool_elements(child, team))
        return results

    def _resolve_monument(
        self, wool_elem: ET.Element, regions: dict[str, Region]
    ) -> tuple[tuple[float, float, float], Optional[str]]:
        for tag in ('monument/block', 'monument/point'):
            child = wool_elem.find(tag)
            if child is not None and child.text:
                return self._parse_coords(child.text), None
        monument_ref = wool_elem.get('monument')
        if monument_ref:
            region = regions.get(monument_ref)
            if region is not None and isinstance(region, (Block, Point)):
                return (region.x, region.y, region.z), monument_ref
        return (0.0, 0.0, 0.0), None

    def _parse_spawners(self) -> list[WoolSpawner]:
        spawners: list[WoolSpawner] = []
        for spawner_elem in self.root.findall('.//spawners/spawner'):
            spawn_region = spawner_elem.get('spawn-region', '').strip()
            player_region = spawner_elem.get('player-region', '').strip()
            if not spawn_region or not player_region:
                continue

            delay = spawner_elem.get('delay', '')
            max_entities_str = spawner_elem.get('max-entities', '')
            max_entities: Optional[int] = (
                int(max_entities_str) if max_entities_str.isdigit() else None
            )

            items: list[SpawnerItem] = []
            for item_elem in spawner_elem.findall('item'):
                material = item_elem.get('material', '').strip()
                try:
                    damage = int(item_elem.get('damage', '0'))
                    amount = int(item_elem.get('amount', '1'))
                except ValueError:
                    damage, amount = 0, 1
                items.append(SpawnerItem(material=material, damage=damage, amount=amount))

            spawners.append(WoolSpawner(
                spawn_region=spawn_region,
                player_region=player_region,
                delay=delay,
                max_entities=max_entities,
                items=items,
            ))
        return spawners

    def _parse_renewables(self) -> list[Renewable]:
        renewables: list[Renewable] = []
        for elem in self.root.findall('.//renewables/renewable'):
            region_id = elem.get('region', '').strip()
            if not region_id:
                continue
            try:
                rate = float(elem.get('rate', '1.0'))
            except ValueError:
                rate = 1.0
            renewables.append(Renewable(
                region_id=region_id,
                rate=rate,
                renew_filter=elem.get('renew-filter', '').strip(),
                replace_filter=elem.get('replace-filter', '').strip(),
                grow=elem.get('grow', 'false').strip().lower() == 'true',
            ))
        return renewables

    def _parse_block_drop_rules(self) -> list[BlockDropRule]:
        rules: list[BlockDropRule] = []
        for elem in self.root.findall('.//block-drops/rule'):
            region_id = elem.get('region', '').strip()
            filter_id = elem.get('filter', '').strip()
            wrong_tool = elem.get('wrong-tool', 'false').strip().lower() == 'true'

            replacement_elem = elem.find('replacement')
            replacement = (replacement_elem.text or '').strip() if replacement_elem is not None else ''

            items: list[BlockDropItem] = []
            drops_elem = elem.find('drops')
            if drops_elem is not None:
                for item_elem in drops_elem.findall('item'):
                    material = item_elem.get('material', '').strip()
                    if not material:
                        continue
                    try:
                        damage = int(item_elem.get('damage', '0'))
                        amount = int(item_elem.get('amount', '1'))
                        chance = float(item_elem.get('chance', '1.0'))
                    except ValueError:
                        damage, amount, chance = 0, 1, 1.0
                    items.append(BlockDropItem(material=material, damage=damage,
                                               amount=amount, chance=chance))

            rules.append(BlockDropRule(
                region_id=region_id, filter_id=filter_id,
                replacement=replacement, wrong_tool=wrong_tool, items=items,
            ))
        return rules

    def _parse_max_build_height(self) -> Optional[int]:
        elem = self.root.find('maxbuildheight')
        if elem is not None and elem.text:
            try:
                return int(elem.text.strip())
            except ValueError:
                return None
        return None

    def _parse_coords(self, coord_str: str) -> tuple[float, float, float]:
        parts = coord_str.split(',')
        if len(parts) >= 3:
            return (
                parse_coord(parts[0]) or 0.0,
                parse_coord(parts[1]) or 0.0,
                parse_coord(parts[2]) or 0.0,
            )
        return (0.0, 0.0, 0.0)
