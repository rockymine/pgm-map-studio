# pgm_map_studio.symmetry

Detects global geometric symmetry from island polygon data and writes `symmetry.json`. No XML dependency. Reads `islands.json` produced by `pgm_map_studio.layout`.

## Modules

| Module | Purpose |
|---|---|
| `__init__.py` | Public API: `detect()`, `detect_from_data()`, `SymmetryResult` |
| `datatypes.py` | `SymmetryResult`, `GlobalSymmetryEntry`, `classify_center_cell`, `is_square_center_cell` |
| `detection.py` | Symmetry detection algorithms (IoU-based + centroid pairing) |
| `serializer.py` | `SymmetryResult → symmetry.json` |

## Key Concepts

**Six symmetry types detected** (the shared vocabulary — see the contract §7):

| Type | Description |
|---|---|
| `mirror_x` | Mirror across the vertical line X = center_x (flips X) |
| `mirror_z` | Mirror across the horizontal line Z = center_z (flips Z) |
| `mirror_d1` | Mirror across the **main diagonal** (`z−cz = x−cx`, NE–SW) |
| `mirror_d2` | Mirror across the **anti-diagonal** (`z−cz = −(x−cx)`, NW–SE) |
| `rot_180` | 180-degree rotational symmetry |
| `rot_90` | 90-degree rotational symmetry |

The diagonals are the definitive diagonal-mirror class — e.g. `vertex`, a 2-team map whose L-shaped
footprint reflects blue↔red across `normal="-1,0,-1"`, detected here as `mirror_d2` @ IoU 1.0.

**Center cell typology:** `classify_center_cell(cx, cz)` derives the center cell (`1x1`/`1x2`/`2x1`/`2x2`,
`{x-width}x{z-width}`) from the coordinate parity (half-integer → 1-wide, integer → 2-wide). It is a
**derived** label exposed as `SymmetryResult.center_cell`, never stored separately. `rot_90` and the
diagonal mirrors require a **square** cell (`is_square_center_cell` → `1x1`/`2x2`); axis-aligned
mirrors and `rot_180` accept any cell.

**Confidence scoring:** Combined weighted average of pair-centroid support (40%) and polygon IoU (60%).

**Island exclusion:** Non-playable islands (e.g. observer platforms) can be excluded via `exclude_islands` to avoid distorting the result.

**Status:** Written as `"unconfirmed"` by the pipeline. The viewer lets the user confirm or reject the detection (`"confirmed"` / `"none"`).

## Output schema (`symmetry.json`)

```json
{
  "status": "unconfirmed",
  "modes": [
    {"type": "mirror_x",  "detected": false, "confidence": 0.34},
    {"type": "mirror_z",  "detected": false, "confidence": 0.34},
    {"type": "mirror_d1", "detected": false, "confidence": 0.30},
    {"type": "mirror_d2", "detected": true,  "confidence": 1.0},
    {"type": "rot_180",   "detected": false, "confidence": 0.30},
    {"type": "rot_90",    "detected": false, "confidence": 0.44}
  ],
  "center": {"center_x": 238.5, "center_z": 306.5},
  "center_cell": "1x1",
  "primary": {"type": "mirror_d2", "confidence": 1.0}
}
```

`status` is written as `"unconfirmed"` by the pipeline. The viewer lets the user set it to `"confirmed"` or `"none"`. `primary` is `null` when no mode is detected. `center_cell` is derived from `center`.

## Usage

```python
from pgm_map_studio.symmetry import detect, detect_from_data
from pgm_map_studio.symmetry import serializer

# From file
result = detect("output/map_slug/islands.json")

# Or from data (list of island dicts)
result = detect_from_data(islands_data, exclude_islands=[3])

serializer.save(result, "output/map_slug/symmetry.json")
print(result.primary)  # {'type': 'rot_180', 'confidence': 1.0}
```
