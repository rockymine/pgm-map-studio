# Cross-Cutting Concerns

This document identifies the shared spatial, canvas, and data concerns that span both the editor workflow (existing-map import) and the sketch workflow (concept-first). It specifies the contracts that shared modules must satisfy and defines the coordinate system used throughout the studio.

The coordinate model is directly based on `CTWAnalysisWithClaudeCode/common/geometry/COORDINATE_SYSTEMS.md`, which is the authoritative reference for the analysis pipeline. Any rule stated there applies here unless explicitly noted otherwise.

---

## 1. Coordinate System

### The two spaces in the studio

The studio works in two spaces only. Canonical space and raster space from the analysis pipeline do not apply here.

**World space — block indices (integers)**

Block positions are integer `(x, z)` pairs. A block at index `x` occupies the continuous interval `[x, x+1]`. The studio uses this everywhere: parquet data, JSON payloads, drawn regions, PGM coordinates.

**SVG / screen space — pixels (floats)**

The canvas maps world space to SVG pixels. Coordinates in this space are floats used only inside canvas rendering code. They must never be stored in data structures or sent over the API.

### The +1 Rule

The most common source of off-by-one errors. A block at index `x` has its RIGHT edge at `x + 1`, not `x`. This has two consequences:

**Width** — a row of blocks from index `min_x` to `max_x` (inclusive) has width `max_x − min_x + 1`, not `max_x − min_x`.

**Extent bounds** — regions store `max_x` as the extent upper bound, which equals the highest block index + 1. So a single block at `x = 5` has `min_x = 5, max_x = 6`.

The +1 is applied **exactly once**, at the boundary between block indices and extent bounds:

```
Block indices  →  [apply +1]  →  Extent bounds
(integers)                       (what regions store)
```

**Where this fires:**
- Drawing a rectangle on the canvas: `max_x = Math.max(startBx, endBx) + 1`
- Converting a single block position to a display region: `max_x = x + 1`
- Reading a PGM `<block>` element (single block tag): `max_x = x + 1`

**Where it does NOT fire:**
- PGM `<rectangle>`, `<cuboid>` attributes — these already store extent bounds
- Sketch shapes — already stored as extent bounds after the draw completes
- Polygon vertices from boolean computation — already in continuous extent space

### Axis orientation

`+Z` points south, which is visually downward on a top-down map. In SVG, `y` also increases downward. This means the mapping `wz → svg_y` is natural — no axis inversion is needed. This is the opposite of matplotlib (which needs `invert_yaxis()` or `origin='upper'`), but correct for SVG-based canvas rendering.

| Axis | World | SVG | Direction |
|---|---|---|---|
| Horizontal | `x` | `svg.x` | East (right) |
| Vertical | `z` | `svg.y` | South (down) |

A transform `toSvg(wx, wz) → {x, y}` must map `wz` to `y`, not to `−y`.

### Bounding box format

All bounding boxes throughout the studio use the object form:

```js
{ min_x, min_z, max_x, max_z }
```

`max_x` and `max_z` are extent bounds (already +1 relative to the highest block index). This matches the PGM region format and the `bounds_2d` field computed by the Python region parser.

> The CTWAnalysis `transform.js` uses an array `[minX, maxX, minZ, maxZ]`. When porting code from that repo, convert to the object form.

### Rotation formulas

All symmetry transforms pivot around a center point `(cx, cz)`. The formulas operate on coordinates relative to that center. From COORDINATE_SYSTEMS.md (rotation is CCW in mathematical convention):

| Transform | Formula (relative to center) | Full formula |
|---|---|---|
| mirror_x | `(Δx, Δz) → (−Δx, Δz)` | `(x, z) → (2·cx − x, z)` |
| mirror_z | `(Δx, Δz) → (Δx, −Δz)` | `(x, z) → (x, 2·cz − z)` |
| mirror_d1 | `(Δx, Δz) → (Δz, Δx)` | `(x, z) → (cx + (z − cz), cz + (x − cx))` |
| mirror_d2 | `(Δx, Δz) → (−Δz, −Δx)` | `(x, z) → (cx − (z − cz), cz − (x − cx))` |
| rot_180 | `(Δx, Δz) → (−Δx, −Δz)` | `(x, z) → (2·cx − x, 2·cz − z)` |
| rot_90 CCW | `(Δx, Δz) → (−Δz, Δx)` | `(x, z) → (cx − (z − cz), cz + (x − cx))` |

`mirror_d1` reflects across the **main diagonal** (the line `z − cz = x − cx`, running NE–SW); it
swaps the centered coordinates. `mirror_d2` reflects across the **anti-diagonal** (`z − cz = −(x − cx)`,
running NW–SE); it swaps and negates them. These are the diagonal-mirror class (e.g. `vertex`).

**Visual note:** Because `+z` is south (down), a 90° CCW rotation in mathematical terms appears clockwise on the rendered map.

**Axis naming in the editor UI:** "Mirror X" means the mirror line runs in the X direction (a horizontal line at `z = cz`), so Z is flipped. "Mirror Z" means the mirror line runs in the Z direction (a vertical line at `x = cx`), so X is flipped. These match `mirror_z` and `mirror_x` in the formulas above respectively.

| UI label | Formula | Mirror line |
|---|---|---|
| Mirror X | `mirror_z` — flip Z | z = cz (horizontal) |
| Mirror Z | `mirror_x` — flip X | x = cx (vertical) |
| Mirror ⟋ (anti-diagonal) | `mirror_d2` | z − cz = −(x − cx) |
| Mirror ⟍ (main diagonal) | `mirror_d1` | z − cz = x − cx |
| Rotate 180° | `rot_180` | — |
| Rotate 90° | `rot_90 CCW` | — |

(Diagonal UI labels are provisional — the diagonal/secondary-axis canvas controls are D-series work.
The `mirror_d1`/`mirror_d2` **mode strings** above are settled and used by the detection model.)

### Center cell typology

A map's symmetry center lands on one of four cells — `1x1`, `1x2`, `2x1`, `2x2`
(`{x-width}x{z-width}` in blocks). It is **derived from the center coordinate's parity**, never
stored independently:

- Under the +1 extent convention, an **odd** block span gives a **half-integer** center (`.5`) that
  passes through the middle of a single column → **1-wide**; an **even** span gives an **integer**
  center (`.0`) on the boundary between two columns → **2-wide**.
- `axis_width(c) = 1 if frac(c) == .5 else 2`; `cell = "{x}x{z}"`.
  (`pgm_map_studio.symmetry.datatypes.classify_center_cell` / `is_square_center_cell`.)

**Which modes each cell allows:**

| Mode | Folds | Center cell requirement |
|---|---|---|
| `mirror_x` | X (across `x=cx`) | any — only the **X** parity is meaningful (the folded axis); Z is incidental |
| `mirror_z` | Z (across `z=cz`) | any — only the **Z** parity is meaningful; X is incidental |
| `rot_180` | X and Z | any |
| `rot_90` / `rot_270` | quarter-turn (X↔Z) | **square only** (`1x1` / `2x2`) |
| `mirror_d1` / `mirror_d2` | diagonal (X↔Z) | **square only** (`1x1` / `2x2`) |

The cell does **not** pin a single-axis mirror's axis: a `1x2` or `2x1` center is valid under
`mirror_x`, `mirror_z`, **and** `rot_180` (each constrains only the axis it folds; the perpendicular
dimension's parity is incidental). What a non-square cell *does* guarantee is that the map is
**not** `rot_90` and **not** a diagonal mirror — those swap X↔Z and so require equal parity. The
1-wide axis marks where a *shared central line* sits (a central column for `1x2`, a central row for
`2x1`), which is a real symmetry feature only when that axis is the one being mirrored.

### Symmetry axes — main + optional secondary

Authoring treats symmetry as **reflection axes through the center**, not a single op:

- A **primary axis** that is **always active** (partitions the map into teams = the chosen mode).
- An **optional secondary axis**, **toggleable on/off during editing**, that subdivides each
  primary region — *intra-team symmetry* (a team's two wools as mirror images). It is
  **perpendicular** to the primary in essentially all cases. Axis-aligned: `mirror_x` ⟂ `mirror_z`
  (compose to `rot_180`). Diagonal: `mirror_d1` ⟂ `mirror_d2` (also compose to `rot_180`). For
  `rot_90` (always square) all four reflection lines exist; either pair can be main vs optional.

The full axes model, persistence shape (`sketch.json.setup`), and counterpart-baking rules are in
`docs/contracts/studio-domain-and-api-contract.md` §7. The canvas controls are D-series.

---

## 2. Shared Canvas Base

Both the editor (`MapCanvas`) and the sketch tool (`ConceptCanvas`) implement identical pan/zoom machinery. This is a shared base that must not be duplicated.

**State:**
- `#scale`, `#panX`, `#panY` — current viewport transform
- `#viewportG` — the SVG `<g>` element to which the matrix is applied

**Behaviour:**
- Scroll wheel zoom centred on the cursor position
- Middle-click drag for pan
- `#applyViewportTransform()` writes `matrix(scale, 0, 0, scale, panX, panY)` to `#viewportG`
- `#clientToSvg(clientX, clientY)` converts screen pixels to base-SVG coordinates (before zoom/pan)
- `resize()` re-renders at new dimensions while preserving the current zoom/pan

**Current state:**  
Both `MapCanvas` and `ConceptCanvas` contain identical copies of this logic. Zoom constants are identical: `ZOOM_FACTOR = 1.15`, `ZOOM_MIN = 0.5`, `ZOOM_MAX = 200`. A `CanvasBase` class must be extracted so both inherit from it.

**Handles:**  
Resize handles and vertex drag handles live outside the `#viewportG` (screen-space, fixed size regardless of zoom). This is the same pattern in both canvases — the handle layer is appended to the SVG root, not to the viewport group.

---

## 3. Transform Module

Both projects have a `transform.js` file with the same algorithm but different bbox interfaces. The canonical module for the studio takes the object form:

```js
buildTransform({ min_x, min_z, max_x, max_z }, svgW, svgH)
  → (wx, wz) => { x, y }

buildInverseTransform({ min_x, min_z, max_x, max_z }, svgW, svgH)
  → (px, py) => { x, z }
```

The inverse returns `{x, z}` (world coordinates), not `{x, y}`.

**Additional helpers in this module:**
- `svgEl(tag, attrs, children)` — create an SVG element
- `ringToPath(ring, toSvg)` — `[[x,z],...]` → SVG path string
- `polyToPath(poly, toSvg)` — `{exterior, holes}` or `{polygons}` → compound SVG path
- `boundsToRingPath(bounds, toSvg)` — `{min_x,min_z,max_x,max_z}` → SVG path ring
- `clipHalfPlane(poly, ox, oz, nx, nz)` — Sutherland-Hodgman half-plane clip (already in pgm-map-studio transform.js)

Both canvases import from this single module.

### Coordinate-space difference between MapCanvas and SketchLayoutCanvas

`CanvasBase._clientToSvg()` returns base-SVG coordinates — pixels in the SVG's own coordinate system, before the viewport pan/zoom group is applied.

- **MapCanvas:** base-SVG pixels are *not* world coordinates. A `buildInverseTransform()` call is needed to convert them to world (block) coordinates.
- **SketchLayoutCanvas:** world coordinates are used directly as SVG base coordinates. No `buildTransform` is set up; pan and zoom are applied only through the viewport matrix. Base-SVG coordinates therefore equal world block coordinates.

Because of this, `SketchLayoutCanvas` passes an identity transform to all shared path helpers:

```js
const identityTransform = (x, z) => ({ x, y: z });

ringToPath(vertices, identityTransform);
polyToPath({ exterior, holes }, identityTransform);
renderShape(type, bounds, identityTransform, attrs);
```

This distinction is intentional. Do not generalise `_clientToSvg()` output across both canvases without accounting for it.

---

## 4. Shape and Region Format

The studio uses two shape vocabularies that must be kept aligned.

### Sketch shapes (drawn in Layout)

Used by the boolean island computation. Extent bounds already applied at draw time.

| Type | Key fields |
|---|---|
| rectangle | `min_x, max_x, min_z, max_z` |
| circle | `center_x, center_z, radius` |
| polygon | `vertices: [[x,z], ...]` |

### PGM region nodes (used by MapCanvas)

Used by the editor to display and edit XML regions. Extent bounds used throughout.

| Type | Key fields | `bounds` (for canvas) |
|---|---|---|
| rectangle | `min_x, min_z, max_x, max_z` | same |
| cuboid | `min_x, min_y, min_z, max_x, max_y, max_z` | XZ projection |
| cylinder | `base_x, base_z, radius` | `base ± radius` |
| circle | `center_x, center_z, radius` | `center ± radius` |
| sphere | `origin_x, origin_z, radius` | `origin ± radius` |
| block | `x, z` | `[x, x+1] × [z, z+1]` (+1 rule) |
| point | `x, z` | `[x−0.5, x+0.5] × [z−0.5, z+0.5]` |

Both vocabularies render to the same SVG shapes (rect, ellipse, path). The canvas rendering code is shared.

### Wire format for a drawn region

When a canvas draw tool completes, it emits a region node in this format:

```js
// Rectangle / cuboid
{ type: "rectangle" | "cuboid", min_x, min_z, max_x, max_z }

// Cylinder / circle
{ type: "cylinder" | "circle", center_x, center_z, radius }

// Point / block
{ type: "point" | "block", x, z }
```

Both editor and sketch draw tools must emit this format. The caller (activity code) decides what to do with it.

---

## 5. Required Converters

These functions must each have exactly one implementation, tested independently. No caller should apply raw `+ 1` or rotation arithmetic directly.

### Block position → extent bounds

```js
blockToExtentBounds(x, z)
  → { min_x: x, max_x: x + 1, min_z: z, max_z: z + 1 }
```

Used when displaying a single block coordinate (spawn point, wool location, monument) as a region on the canvas.

### Drawn block range → extent bounds

```js
drawnBoundsFromBlocks(b1x, b1z, b2x, b2z)
  → { min_x: Math.min(b1x, b2x),
      max_x: Math.max(b1x, b2x) + 1,
      min_z: Math.min(b1z, b2z),
      max_z: Math.max(b1z, b2z) + 1 }
```

Used by the rectangle draw tool in both canvases. The `+ 1` here is the single authoritative application of the +1 rule for canvas drawing.

### PGM region → 2D display bounds

```js
regionToBounds2d(region)
  → { min_x, max_x, min_z, max_z } | null
```

Dispatches by `region.type` to derive a bounding box for canvas display. Block adds +1; all others compute from their native coordinates. Returns null for composite and special regions that have no direct 2D footprint.

### Symmetry transform on a point

```js
applySymmetry(x, z, axis, cx, cz)
  → [x', z']
```

Where `axis` is one of `"mirror_x"`, `"mirror_z"`, `"rot_180"`, `"rot_90"` (and, once the diagonal/secondary-axis canvas work lands in the D-series, `"mirror_d1"`/`"mirror_d2"`). Applies the formula from Section 1. This is the only place the symmetry math is implemented. Both the editor mirroring engine and the sketch live preview use this function.

### Symmetry transform on extent bounds

```js
applySymmetryToBounds(bounds, axis, cx, cz)
  → { min_x, max_x, min_z, max_z }
```

Applies `applySymmetry` to all four corners and re-derives min/max. Used by the editor mirroring engine when suggesting counterpart regions.

### Rasterise polygon → block list

```js
rasterisePolygon(exterior, holes)
  → [[x, z], ...]
```

Given an island polygon in extent coordinates (output of the polygon-clipping boolean computation), returns all integer block indices `(x, z)` whose unit square `[x, x+1] × [z, z+1]` lies inside the polygon. This is the operation performed by sketch export to produce the synthetic scan layer parquet.

The inverse of `world_blocks_to_shapely` from the analysis pipeline. The polygon-clipping library's output is already in extent coordinates; no +1 conversion is needed before calling this.

### Sketch shape → PGM region (for export)

```js
sketchShapeToPgmRegion(shape)
  → PGM region object | null
```

| Sketch type | PGM region | Notes |
|---|---|---|
| rectangle | Rectangle | Direct remap of field names |
| circle | Circle | Direct remap |
| polygon | — | No PGM primitive equivalent; used only for island shaping, not exported as regions |

Sketch polygons are never converted to PGM regions. They contribute to the rasterised scan layer but do not produce named region entries in the XML.

---

## 6. Shared Toolbar

Both canvases expose a draw tool API: `setActiveTool(name | null)`. The toolbar buttons and active-state management are the same in both.

The concept tool's `ToolManager` class (`CTWAnalysisWithClaudeCode/map_viewer/static/shared/tool-manager.js`) is the correct extraction point. It:
- Manages which tool is currently active
- Highlights the active button
- Calls `canvas.setActiveTool()` on change

Both editor and sketch import a shared `ToolManager`. The editor's tool set is a subset of the sketch tool set:

| Tool | Editor | Sketch |
|---|---|---|
| Move/pan | ✓ | ✓ |
| Rectangle | ✓ | ✓ |
| Cylinder/Circle | ✓ | ✓ (circle only) |
| Polygon | — | ✓ |
| Lasso | — | ✓ |
| Point/Block | ✓ | — |

The add/subtract operation toggle (Sub mode) is sketch-only and not part of the shared toolbar.

---

## 7. Shared SVG Region Rendering

The visual rendering of a region node to SVG is the same in both canvases:
- `rectangle` / `cuboid` → `<rect>` via `boundsToRingPath`
- `cylinder` / `circle` / `sphere` → `<ellipse>` from centre ± radius
- Any region with `polygon_2d` → `<path>` via `polyToPath`

A shared `renderShape(type, boundsOrPoly, toSvg, attrs)` function avoids repeating this dispatch in both canvas implementations.

---

## 8. Test Cases

All converters above require unit tests. The rotation formulas in COORDINATE_SYSTEMS.md serve as the reference for symmetry test cases. Suggested cases:

**+1 rule**
- `drawnBoundsFromBlocks(3, 5, 3, 5)` → `{min_x:3, max_x:4, min_z:5, max_z:6}` (single block)
- `drawnBoundsFromBlocks(3, 5, 6, 9)` → `{min_x:3, max_x:7, min_z:5, max_z:10}`
- `blockToExtentBounds(7, 2)` → `{min_x:7, max_x:8, min_z:2, max_z:3}`

**Symmetry — mirror_x (flip X, vertical mirror line at x = cx)**
- `applySymmetry(10, 20, "mirror_x", 0, 0)` → `[-10, 20]`
- `applySymmetry(10, 20, "mirror_x", 5, 5)` → `[0, 20]`

**Symmetry — mirror_z (flip Z, horizontal mirror line at z = cz)**
- `applySymmetry(10, 20, "mirror_z", 0, 0)` → `[10, -20]`
- `applySymmetry(10, 20, "mirror_z", 5, 15)` → `[10, 10]`

**Symmetry — rot_180**
- `applySymmetry(10, 20, "rot_180", 0, 0)` → `[-10, -20]`
- `applySymmetry(10, 20, "rot_180", 5, 10)` → `[0, 0]`

**Symmetry — rot_90 CCW**
- `applySymmetry(1, 0, "rot_90", 0, 0)` → `[0, 1]`  (unit vector on X maps to unit vector on Z)
- `applySymmetry(0, 1, "rot_90", 0, 0)` → `[-1, 0]`

**Symmetry — mirror_d1 (main diagonal, swaps Δx/Δz)**
- `applySymmetry(10, 20, "mirror_d1", 0, 0)` → `[20, 10]`
- `applySymmetry(10, 20, "mirror_d1", 5, 5)` → `[20, 10]`  (point and center both shift; result is the X↔Z swap about the center)

**Symmetry — mirror_d2 (anti-diagonal, swaps and negates)**
- `applySymmetry(10, 20, "mirror_d2", 0, 0)` → `[-20, -10]`
- `applySymmetry(3, 1, "mirror_d2", 0, 0)` → `[-1, -3]`

**Bounds symmetry round-trip**
- `applySymmetryToBounds` applied twice with the same mirror axis should return the original bounds (true for all four reflections `mirror_x`/`mirror_z`/`mirror_d1`/`mirror_d2`, which are involutions).

**Rasterisation**
- A 2×2 extent polygon `[[0,0],[2,0],[2,2],[0,2]]` should yield exactly 4 block indices: `(0,0), (1,0), (0,1), (1,1)`.
- A 1.5-wide extent polygon should yield only the blocks whose unit squares fully or partially overlap, not those merely touching.

**PGM region bounds**
- `regionToBounds2d({type:"block", x:5, z:3})` → `{min_x:5, max_x:6, min_z:3, max_z:4}` (confirms +1 applied once)
- `regionToBounds2d({type:"cylinder", base_x:10, base_z:10, radius:5})` → `{min_x:5, max_x:15, min_z:5, max_z:15}`

---

## 9. What Is NOT Shared

These concerns are specific to one workflow and should not be generalised:

| Concern | Workflow | Reason |
|---|---|---|
| Boolean island computation (polygon-clipping) | Sketch only | Editor works with pre-computed parquet islands |
| Visvalingam–Whyatt simplification | Sketch only | Lasso shape simplification |
| Parquet read/write | Editor pipeline (Python) | Not a JS canvas concern |
| XML serialisation / round-trip safety | Editor only | Sketch produces a scan layer, not XML directly |
| Add/subtract operation mode | Sketch only | Editor regions have no subtraction concept |
| Island exclusion | Editor Configure only | Sketch's per-island participation flag is analogous but distinct |
