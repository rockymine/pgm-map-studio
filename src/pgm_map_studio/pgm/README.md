# pgm_map_studio.pgm

Parses a PGM `map.xml` file and produces a `MapXml` dataclass and `xml_data.json`. No knowledge of block geometry, islands, or symmetry.

## Modules

| Module | Purpose |
|---|---|
| `__init__.py` | Public API: `MapXml`, `parse()` |
| `datatypes.py` | `MapXml`, `Team`, `Kit`, `Spawn`, `Wool`, `WoolSpawner`, `Renewable`, `BlockDropRule`, `ApplyRule`, `Author`, `KitItem`, `KitArmor` |
| `regions.py` | Region class hierarchy + coordinate parsing (`parse_coord`) |
| `filters.py` | Filter class hierarchy |
| `parser.py` | Top-level orchestrator: teams, kits, spawns, wools, spawners, renewables, block_drop_rules, apply_rules |
| `filter_parser.py` | All filter type parsers |
| `region_parser.py` | All region type parsers; synthetic ID injection; flat registry building |
| `serializer.py` | `MapXml → dict → xml_data.json` |
| `deserializer.py` | `xml_data.json → MapXml` |
| `xml_writer.py` | `MapXml → map.xml` export |

## Key Concepts

**Flat registry:** All named and anonymous regions live once in `MapXml.regions`. Composite regions (`Union`, `Negative`, `Complement`, `Intersect`) store children as ID strings, not inline objects. Filters follow the same pattern.

**Stable synthetic IDs:** Anonymous child regions receive `{parent_id}__anon_{xml_index}` IDs — deterministic and stable across re-parses of the same XML.

**Normalized `bounds_2d`:** Every region carries a pre-computed `bounds_2d` field (min always ≤ max). Rectangular regions correct for the PGM convention where `max < min` is valid XML.

**No `region_categories`:** Category assignment (spawn/wool/build/other) is computed at viewer load time from region IDs, not stored in `xml_data.json`.

## xml_data.json Format

Fields are grouped below by editor activity. All fields are present in the top-level object; the grouping reflects which activity owns each field in the editor.

### Overview

Map identity and authorship.

```json
{
  "name": "Map Name",
  "version": "1.0.0",
  "gamemode": "ctw",
  "objective": "Capture the enemy's wool.",
  "max_build_height": 100,
  "authors": [
    { "uuid": "xxxxxxxx-...", "role": "author" },
    { "uuid": "yyyyyyyy-...", "role": "contributor", "contribution": "terrain" }
  ]
}
```

- `role`: `"author"` | `"contributor"`
- `max_build_height`: omitted when null (PGM default applies)
- `contribution`: omitted when empty

### Teams

Team definitions, player kits, and spawn placements.

```json
{
  "teams": [
    { "id": "red", "name": "Red", "color": "dark red", "dye_color": "RED", "max_players": 10, "min_players": 1 }
  ],
  "kits": [
    {
      "id": "default-kit",
      "items": [
        { "slot": 0, "material": "iron_sword", "enchantments": "sharpness:1" }
      ],
      "armor": [
        { "slot_name": "helmet", "material": "iron_helmet", "team_color": true }
      ]
    }
  ],
  "spawns": [
    { "team": "red", "kit": "default-kit", "yaw": 90.0, "region": { "id": "red-spawn", "type": "cuboid", ... } }
  ],
  "observer_spawn": { "team": "", "kit": "", "yaw": 0.0, "region": { ... } }
}
```

Kit item optional fields (omitted at default): `amount` (default 1), `damage` (default 0), `unbreakable`, `team_color`, `enchantments`.

Armor optional fields (omitted at default): `unbreakable`, `team_color`, `enchantments`.

`slot_name` is one of: `helmet`, `chestplate`, `leggings`, `boots`.

Spawn region is encoded inline (not referenced by ID) because it belongs exclusively to that spawn entry.

### Build Region

Block regeneration and drop overrides that control how build areas behave.

```json
{
  "renewables": [
    { "region_id": "build-region", "rate": 2.0, "renew_filter": "only-tnt", "replace_filter": "is-air", "grow": true }
  ],
  "block_drop_rules": [
    {
      "region_id": "build-region",
      "filter_id": "only-players",
      "replacement": "air",
      "wrong_tool": false,
      "items": [
        { "material": "log", "damage": 0, "amount": 1, "chance": 0.5 }
      ]
    }
  ]
}
```

Optional fields omitted at defaults: `rate` (1.0), `grow` (false), `wrong_tool` (false), `damage` (0), `amount` (1), `chance` (1.0).

### Objectives

CTW wool objectives and their wool-room mob spawners.

```json
{
  "wools": [
    {
      "team": "red",
      "color": "blue",
      "location": { "x": 10.5, "y": 64.0, "z": 30.5 },
      "monument": { "x": -5.0, "y": 64.0, "z": 0.0, "region_id": "red-monument" },
      "wool_room_region": "blue-wool-room"
    }
  ],
  "spawners": [
    {
      "spawn_region": "blue-spawner-pos",
      "player_region": "blue-wool-room",
      "delay": "5s",
      "max_entities": 5,
      "items": [{ "material": "sheep", "damage": 11, "amount": 1 }]
    }
  ]
}
```

- `wool.location`: exact block position of the wool block in the enemy wool room
- `wool.monument`: exact block position of the monument slot in the owning team's base; `region_id` is the surrounding monument region (omitted when absent)
- `wool.wool_room_region`: region enclosing the enemy wool room, used for entry detection
- `spawner.spawn_region`: region where the mob spawns
- `spawner.player_region`: region where a player must be present to trigger the spawner
- `spawner.delay` / `max_entities`: omitted when absent

### Regions

Flat registry of every named and anonymous region. Keys are region IDs; values are region objects.

```json
{
  "regions": {
    "red-base": { "id": "red-base", "type": "cuboid", "bounds_2d": { "min": {"x": -10, "z": -10}, "max": {"x": 10, "z": 10} }, "min": {"x": -10, "y": 60, "z": -10}, "max": {"x": 10, "y": 80, "z": 10} },
    "all-bases": { "id": "all-bases", "type": "union", "children": ["red-base", "blue-base"] }
  }
}
```

All region objects carry `id`, `type`, and `bounds_2d` (pre-computed axis-aligned bounding box on the XZ plane). Coordinate values `"oo"` / `"-oo"` represent positive / negative infinity.

| Type | Additional fields |
|---|---|
| `rectangle` | `bounds_2d` only (no raw min/max) |
| `cuboid` | `min {x,y,z}`, `max {x,y,z}` |
| `cylinder` | `base {x,y,z}`, `radius`, `height` (optional) |
| `circle` | `center {x,z}`, `radius` |
| `sphere` | `origin {x,y,z}`, `radius` |
| `block` | `position {x,y,z}` |
| `point` | `position {x,y,z}` |
| `union` | `children: [id, ...]` |
| `negative` | `children: [id, ...]` |
| `complement` | `children: [id, ...]` |
| `intersect` | `children: [id, ...]` |
| `mirror` | `source_id`, `origin {x,y,z}`, `normal {x,y,z}` |
| `translate` | `source_id`, `offset {x,y,z}` |
| `half` | `origin {x,y,z}`, `normal {x,y,z}` |
| `reference` | `ref_id` |
| `everywhere` | *(no extra fields)* |
| `above` | `y` |

### Filters

Flat filter registry plus the spatial apply rules that bind filters to regions.

```json
{
  "filters": {
    "only-red": { "id": "only-red", "type": "team", "team": "red" },
    "red-and-alive": { "id": "red-and-alive", "type": "all", "children": ["only-red", "alive"] }
  },
  "apply_rules": [
    {
      "region": "build-zone",
      "enter": "only-red",
      "block_place": "only-red",
      "block_break": "only-red",
      "kit": "default-kit",
      "message": "Only red team may build here."
    }
  ]
}
```

All filter objects carry `id` and `type`. Apply rule fields are all optional; only non-empty fields are written.

#### Filter types

| Category | Types | Extra fields |
|---|---|---|
| Combiners | `all`, `any`, `one` | `children: [id, ...]` |
| Wrappers | `not`, `deny`, `allow` | `child: id` |
| Team / player | `team` | `team` |
| Player state | `alive`, `dead`, `participating`, `observing`, `grounded` | — |
| Kill streak | `kill-streak` | `min`, `max`, `count` (any combination) |
| Class | `class` | `name` |
| Player count | `players` | `min`, `max` |
| Inventory | `carrying` | `material`, `damage`, `enchantments`, `ignore_metadata` |
| | `wearing` | `material`, `damage`, `ignore_metadata` |
| | `holding` | `material`, `damage` |
| Block / world | `material` | `material` |
| | `void` | — |
| | `cause` | `cause` |
| | `blocks` | `region`, `child` |
| | `offset` | `vector`, `child` |
| | `region` | `region` |
| Match timing | `match-running`, `match-started` | — |
| | `time` | `duration` |
| | `after` | `filter` (optional), `duration` |
| | `pulse` | `period`, `duration`, `filter` (optional) |
| Objective | `completed` | `objective` |
| | `objective` | `objective` (deprecated alias) |
| Dynamic | `variable` | `var`, `value`, `team` (optional) |
| | `spawn` | `mob` (optional) |
| Static | `never`, `always` | — |

#### Apply rule fields

| Field | Meaning |
|---|---|
| `region` | Region ID the rule is scoped to |
| `enter` | Filter ID for region-entry events |
| `leave` | Filter ID for region-leave events |
| `block` | Filter ID for any block event (place + break combined) |
| `block_place` | Filter ID for block placement |
| `block_break` | Filter ID for block breaking |
| `block_physics` | Filter ID for block physics (water flow, gravity, etc.) |
| `block_place_against` | Filter ID for the surface being placed against |
| `use` | Filter ID for right-click / use events |
| `filter` | General filter condition (gate for `kit` / `velocity`) |
| `kit` | Kit ID to give on region entry |
| `lend_kit` | Kit ID given on entry and revoked on leave |
| `velocity` | Launch vector string `"X,Y,Z"` |
| `message` | Denial message shown to the player when an event is blocked |

## Usage

**Import path (existing map):**

```python
from pgm_map_studio.pgm import parse, to_xml
from pgm_map_studio.pgm import serializer

xml_data = parse("path/to/map.xml")
serializer.save(xml_data, "output/xml_data.json")
```

**Export path (new map or editor-only map):**

```python
from pgm_map_studio.pgm import from_dict, to_xml
import json

d = json.loads(Path("output/xml_data.json").read_text())
xml_data = from_dict(d)
Path("output/map.xml").write_text(to_xml(xml_data))
```

Or using the file helper:

```python
from pgm_map_studio.pgm import load, to_xml

xml_data = load("output/xml_data.json")
Path("output/map.xml").write_text(to_xml(xml_data))
```

**Full roundtrip (import → edit → re-export):**

```python
# Import
xml_data = parse("path/to/map.xml")
serializer.save(xml_data, "output/xml_data.json")

# ... editor modifies xml_data.json ...

# Export
xml_data = load("output/xml_data.json")
Path("output/map.xml").write_text(to_xml(xml_data))
```
