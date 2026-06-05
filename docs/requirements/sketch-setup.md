# Requirements: Sketch — Setup

**Semantic purpose:** Define the spatial context of the map — its extent, the symmetry center, and the mirror mode — before island drawing begins.

**Canvas mode:** Center placement and movement, plus move and zoom. No shape drawing.

---

## Sub-step 1: Bounding Box

**User requirements**
- Set the bounding box (min/max X and Z), which defines the canvas extent and the world space the map occupies.

**System requirements**
- Store: bounding box min/max X and Z.
- When bounding box changes, resize the canvas accordingly.
- Derive and display the size (width, depth in blocks) from the min/max values.
- Center is not moved automatically when the bounding box changes.

---

## Sub-step 2: Center Point

**User requirements**
- Place or move the center point directly on the canvas, or enter coordinates numerically. Both inputs update the same value.

**System requirements**
- Render a crosshair on the canvas at the current center position at all times.
- Center is draggable on the canvas; dragging updates the numeric inputs live.
- Numeric inputs update the crosshair position immediately on commit (blur or Enter).
- Store: center X, center Z.
- When center changes, update the axis visual (see Sub-step 3) immediately.

---

## Sub-step 3: Mirror Mode

**User requirements**
- Select the mirror mode that will apply to the map's symmetry:

| Mode | Teams | Description |
|---|---|---|
| Mirror X | 2 | Reflection across Z = center_z |
| Mirror Z | 2 | Reflection across X = center_x |
| Rotate 180° | 2 | Half-turn rotation around center |
| Rotate 90° | 4 | Quadrant symmetry |

- Mirror mode may be changed at any time; no authored shapes are affected.

**System requirements**
- Display a visual indication of the selected axis on the canvas (e.g. axis line or sector boundary overlay) anchored at the current center, so the author can see the implied layout before drawing.
- When mirror mode or center changes, update the axis visual immediately.
- Store: mirror mode.
- The selected mirror mode becomes the default symmetry applied to all newly created islands in the Layout activity.

---

## Dependencies

None. Setup is self-contained. Its outputs (bounding box, center, mirror mode) are consumed by Layout.
