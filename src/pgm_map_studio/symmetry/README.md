# pgm_map_studio.symmetry

Detects global geometric symmetry from island polygon data and writes `symmetry.json`. No XML dependency. Reads `islands.json` produced by `pgm_map_studio.layout`.

## Modules

| Module | Purpose |
|---|---|
| `__init__.py` | Public API: `detect()`, `detect_from_data()`, `SymmetryResult` |
| `datatypes.py` | `SymmetryResult`, `GlobalSymmetryEntry` |
| `detection.py` | Symmetry detection algorithms (IoU-based + centroid pairing) |
| `serializer.py` | `SymmetryResult → symmetry.json` |

## Key Concepts

**Four symmetry types detected:**

| Type | Description |
|---|---|
| `mirror_x` | Left-right mirror across X = center_x |
| `mirror_z` | Front-back mirror across Z = center_z |
| `rot_180` | 180-degree rotational symmetry |
| `rot_90` | 90-degree rotational symmetry |

**Confidence scoring:** Combined weighted average of pair-centroid support (40%) and polygon IoU (60%).

**Island exclusion:** Non-playable islands (e.g. observer platforms) can be excluded via `exclude_islands` to avoid distorting the result.

**`symmetry_status`:** Written as `"skipped"` by the pipeline. The viewer lets the user confirm or reject the detection (`"confirmed"` / `"none"`).

## Usage

```python
from pgm_map_studio.symmetry import detect, detect_from_data
from pgm_map_studio.symmetry import serializer

# From file
result = detect("output/map_slug/islands.json")

# Or from data (list of island dicts)
result = detect_from_data(islands_data, exclude_islands=[3])

serializer.save(result, "output/map_slug/symmetry.json")
print(result.primary)  # {'type': 'rot_180', 'confidence': 1.0, ...}
```
