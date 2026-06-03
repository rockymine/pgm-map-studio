# pgm_map_studio.pgm

Parses a PGM `map.xml` file and produces a `MapXml` dataclass and `xml_data.json`. No knowledge of block geometry, islands, or symmetry.

## Modules

| Module | Purpose |
|---|---|
| `__init__.py` | Public API: `MapXml`, `parse()` |
| `datatypes.py` | `MapXml`, `Team`, `Kit`, `Spawn`, `Wool`, `WoolSpawner`, `Renewable`, `BlockDropRule`, `ApplyRule`, `Author`, `KitItem`, `KitArmor` |
| `regions.py` | Region class hierarchy + coordinate parsing (`parse_coord`) |
| `parser.py` | Top-level orchestrator: teams, kits, spawns, wools, spawners, renewables, block_drop_rules, apply_rules |
| `region_parser.py` | All region type parsers; synthetic ID injection; flat registry building |
| `serializer.py` | `MapXml → dict → xml_data.json` |

## Key Concepts

**Flat registry:** All named and anonymous regions live once in `MapXml.regions`. Composite regions (`Union`, `Negative`, `Complement`, `Intersect`) store children as ID strings, not inline objects.

**Stable synthetic IDs:** Anonymous child regions receive `{parent_id}__anon_{xml_index}` IDs — deterministic and stable across re-parses of the same XML.

**Normalized `bounds_2d`:** Every region carries a pre-computed `bounds_2d` field (min always ≤ max). Rectangular regions correct for the PGM convention where `max < min` is valid XML.

**No `region_categories`:** Category assignment (spawn/wool/build/other) is computed at viewer load time from region IDs, not stored in `xml_data.json`.

## Usage

```python
from pgm_map_studio.pgm import parse
from pgm_map_studio.pgm import serializer

xml_data = parse("path/to/map.xml")
serializer.save(xml_data, "output/xml_data.json")
```
