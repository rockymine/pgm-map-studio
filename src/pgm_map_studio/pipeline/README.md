# pgm_map_studio.pipeline

Three-step map analysis pipeline. Orchestrates Layout → Symmetry → XML into a single call, with per-step caching and per-map configuration.

## Steps

| Step | Module | Outputs | Depends on |
|---|---|---|---|
| 1 Layout | `layout.pipeline` | `layer.parquet`, `wools.parquet`, `resources.parquet`, `chests.parquet`, `spawners.parquet`, `islands.json` | — |
| 2 Symmetry | `symmetry.detection` | `symmetry.json` | Step 1 |
| 3 XML | `pgm.parser` + `pgm.serializer` | `xml_data.json` | — |

Steps 1 and 3 are independent. Step 2 depends on Step 1. There is no assembly step.

## Output layout

```
{output_dir}/{map_slug}/
├── layer.parquet
├── wools.parquet
├── resources.parquet
├── chests.parquet
├── spawners.parquet
├── islands.json
├── symmetry.json
├── xml_data.json
└── map_config.json     ← user-editable per-map config
```

## Per-map config (`map_config.json`)

Written with defaults on the first run. Edit to tune per-map behaviour:

```json
{
  "exclude_islands": [],
  "scan_layer": "surface"
}
```

| Field | Default | Description |
|---|---|---|
| `exclude_islands` | `[]` | Island IDs excluded from symmetry detection (e.g. observer platforms) |
| `exclude_blocks` | `[]` | Block IDs treated as air during the scan (e.g. `[36]` for PISTON_MOVING_PIECE boundary markers) |
| `scan_layer` | `"surface"` | Layer extractor: `"surface"`, `"y0"`, `"bedrock"`, `"base"` |

After editing `exclude_islands`, re-run only Step 2 with `force_symmetry=True` — no need to rescan the world.

## Usage

```python
from pathlib import Path
from pgm_map_studio.minecraft.sources import MapSource
from pgm_map_studio.pipeline import run

source = MapSource(slug='tumbleweed', path=Path('/maps/tumbleweed'),
                   has_xml=True, game_mode='ctw')

# Full run (skips cached steps automatically)
result = run(source, output_dir=Path('/output'))

print(result.islands_count)          # number of islands detected
print(result.symmetry.primary)       # {'type': 'rot_180', 'confidence': 1.0}

# Re-run only symmetry after editing map_config.json
run(source, output_dir=Path('/output'), force_symmetry=True)

# Force everything
run(source, output_dir=Path('/output'), force=True)
```

## Individual steps

```python
from pgm_map_studio.pipeline import run_layout, run_symmetry, run_xml

islands    = run_layout(source, output_dir)
symmetry   = run_symmetry(output_dir, config=cfg, force=True)
xml_data   = run_xml(source, output_dir)
```
