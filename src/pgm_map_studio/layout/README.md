# layout

Geometry extraction pipeline. Takes a Minecraft world (via `minecraft/`) and produces a `MapLayout` — a set of detected islands, each with an exact polygon boundary.

## Modules

| Module | Purpose |
|---|---|
| `config.py` | `ScanConfig` — which layer extractor to use, exclusions, height cap |
| `pipeline.py` | Orchestrate extraction + island detection for one map; cache to disk |
| `islands.py` | BFS connected-component detection + polygon construction |
| `datatypes.py` | `Island`, `MapLayout` |

## Data structures

**`Island`**

| Field | Type | Description |
|---|---|---|
| `id` | `int` | 1-based index, sorted by block_count descending |
| `polygon` | `shapely.Polygon` | Exact block-outline; interior rings are holes |
| `bounds` | `tuple[int,int,int,int]` | `(min_x, min_z, max_x, max_z)` — block extent |
| `block_count` | `int` | Number of blocks in the component |

**`MapLayout`** holds `islands: list[Island]` and `bounds` for the full map.

## Usage

```python
from pgm_map_studio.minecraft.sources import find_maps
from pgm_map_studio.layout.pipeline import run
from pgm_map_studio.layout.config import ScanConfig

source = next(find_maps('/media/sf_repos/CommunityMaps/ctw'))
layout = run(source, output_dir='/tmp/my-map', config=ScanConfig(layer='surface'))

for island in layout.islands:
    print(island.id, island.block_count, island.bounds)
```

## Layer choices

| `ScanConfig.layer` | Extractor | Best for |
|---|---|---|
| `'surface'` | `SurfaceExtractor` | Most maps — uses highest non-excluded block per column |
| `'y0'` | `Y0Extractor` | Flat bedrock maps where y=0 is the play surface |
| `'bedrock'` | `BedrockExtractor` | Maps where bedrock defines island footprints |
| `'base'` | `BaseExtractor` | Floating-island maps — lowest solid block per column |

## Cached outputs

All outputs are written to `output_dir` and skipped on subsequent runs unless `force=True`:

| File | Contents |
|---|---|
| `layer.parquet` | Block scan used for island detection |
| `wools.parquet` | Wool positions and colours |
| `resources.parquet` | Iron/gold/diamond block positions |
| `chests.parquet` | Chest inventory |
| `spawners.parquet` | Mob spawner configuration |
| `islands.json` | Detected islands (GeoJSON polygons + metadata) |

## Notes

- Holes are detected automatically — `unary_union` of unit squares produces interior rings for enclosed voids.
- Diagonal-only block connections (8-connectivity) can create touching-point polygon geometries; `make_valid()` resolves these and the largest part is kept.
- No skeleton or symmetry detection at this stage — those are deferred to later pipeline steps.
