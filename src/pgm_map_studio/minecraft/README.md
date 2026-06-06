# minecraft

Low-level Minecraft file I/O and block scanning. This package has no knowledge of PGM maps or game rules — it only knows how to read Minecraft world data.

## Modules

| Module | Purpose |
|---|---|
| `region_reader.py` | Streams chunks from Anvil `.mca` region files |
| `world_writer.py` | Writes (x, z) block positions into a Minecraft 1.8 Anvil world |
| `layers.py` | Layer extractors — scan the full map, one row per column |
| `features.py` | Feature extractors — locate specific block types, one row per instance |
| `colors.py` | Block ID → RGB colour lookup |
| `wool.py` | Wool damage values and colour name data |
| `sources.py` | Discover valid map folders in a repository |

## Two kinds of extractor

**Layer extractors** (`layers.py`) produce a 2D spatial grid over the entire map. They answer questions like "what is the top surface at every (x, z)?" and are the input to island detection.

| Class | Output columns | Description |
|---|---|---|
| `Y0Extractor` | `world_x, world_z, block_id, block_data` | Non-air blocks at world_y=0 |
| `SurfaceExtractor` | `world_x, world_z, world_y, block_id, block_data` | Highest qualifying block per column |
| `BedrockExtractor` | `world_x, world_z, world_y, block_id, block_data` | Lowest bedrock per column |
| `BaseExtractor` | `world_x, world_z, world_y, block_id, block_data` | Lowest solid block per column |
| `SegmentsExtractor` | `world_x, world_z, world_y_start, world_y_end` | All contiguous solid runs per column |

**Feature extractors** (`features.py`) locate specific block types and return per-instance data. Each maps to a named parquet file written by the pipeline.

| Class | Output file | Output columns |
|---|---|---|
| `WoolExtractor` | `wools.parquet` | `world_x, world_z, world_y, color` |
| `ResourceExtractor` | `resources.parquet` | `world_x, world_z, world_y, resource_type` |
| `ChestExtractor` | `chests.parquet` | `world_x, world_z, world_y, chest_type, slot, item_id, item_damage, count` |
| `SpawnerExtractor` | `spawners.parquet` | `world_x, world_z, world_y, entity_id, spawns_wool, …` |

`detect_double_chests()` is a post-processing helper that annotates `ChestExtractor` output with `is_double` and `chest_group_id` columns.

## Coordinate convention

All DataFrame columns use the `world_` prefix to distinguish world coordinates from the section-local (0–15) and chunk-local (0–255) values used internally during extraction. Every spatial axis is covered: `world_x`, `world_z`, `world_y` (or `world_y_start`/`world_y_end` for segment ranges).

## Map discovery

`sources.py` provides `find_maps(root)`, which recursively walks a repository directory (e.g. `CommunityMaps/`, `PublicMaps/`) and yields `MapSource` entries for every folder that contains a `region/` subdirectory. Game mode is inferred from the parent directory name.

```python
from pgm_map_studio.minecraft.sources import find_maps

for source in find_maps('/media/sf_repos/CommunityMaps'):
    print(source.slug, source.game_mode, source.has_xml)
```

## Notes

- All extractors return a `pandas.DataFrame`. Persistence (writing parquet files) is handled by the `layout` pipeline, not here.
- Extraction reads Minecraft 1.8.9 Anvil format. The `Add` nibble array is supported for block IDs > 255.
- Block 36 (PISTON_MOVING_PIECE) is used by many CTW maps as an invisible build-region boundary marker and is excluded from solid-block scans by default.
