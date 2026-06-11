# Geometry & Canvas Contract

The shared spatial/canvas concerns that span both workflows — the editor (existing-map import) and
the sketch (concept-first). This doc owns the **geometry math**: the coordinate system, the transform
formulas, and the **required converters (exactly one implementation each)**. The data **model**
(region shapes, symmetry vocabulary + persistence, validation) is owned by
`data-model.md` — this doc references it rather than restating it.

---

## 1. Coordinate system

### Two spaces

- **World space — block indices (integers).** Block positions are integer `(x, z)`; a block at index
  `x` occupies the continuous interval `[x, x+1]`. Used everywhere: parquet, JSON payloads, drawn
  regions, PGM coordinates.
- **SVG / screen space — pixels (floats).** Only inside canvas rendering. Never stored in data
  structures or sent over the API.

### The +1 rule

A block at index `x` has its **right edge at `x + 1`**, not `x`. Consequences:

- **Width** of blocks `min_x..max_x` (inclusive) is `max_x − min_x + 1`.
- **Extent bounds** store `max_x` = highest block index + 1. A single block at `x = 5` →
  `min_x = 5, max_x = 6`.

The `+1` is applied **exactly once**, at the block-index → extent-bound boundary:

```
Block indices  →  [apply +1]  →  Extent bounds (what regions store)
```

- **Fires:** drawing a rectangle (`max = Math.max(b1,b2) + 1`); a single block position → display
  region (`max = x + 1`); reading a PGM `<block>` element.
- **Does NOT fire:** PGM `<rectangle>`/`<cuboid>` attributes (already extent bounds); sketch shapes
  (already extent after the draw); polygon vertices from boolean computation (already extent space).

### Axis orientation

`+Z` points south = visually **down** on a top-down map. SVG `y` also increases downward, so
`wz → svg_y` is natural (no inversion).

| Axis | World | SVG | Direction |
|---|---|---|---|
| Horizontal | `x` | `svg.x` | East (right) |
| Vertical | `z` | `svg.y` | South (down) |

A transform `toSvg(wx, wz) → {x, y}` maps `wz` to `y`, not `−y`.

### Bounding box format

All bounding boxes use the object form `{ min_x, min_z, max_x, max_z }`, where `max_*` are extent
bounds (already +1). This matches the PGM region format and the `bounds_2d` the Python parser
computes. (Symmetry center is `{ cx, cz }`.)

---

## 2. Symmetry transform formulas

The **math** for transforming a point/bounds about the center `(cx, cz)`. The symmetry **model** —
what the modes mean, which modes a center cell allows, the primary/secondary axes, counterpart
persistence — is owned by `data-model.md` §7.

| Transform | Δ-form (relative to center) | Full formula |
|---|---|---|
| `mirror_x` | `(Δx, Δz) → (−Δx, Δz)` | `(x, z) → (2cx − x, z)` |
| `mirror_z` | `(Δx, Δz) → (Δx, −Δz)` | `(x, z) → (x, 2cz − z)` |
| `mirror_d1` (main diagonal `z−cz = x−cx`) | `(Δx, Δz) → (Δz, Δx)` | `(x, z) → (cx + (z−cz), cz + (x−cx))` |
| `mirror_d2` (anti-diagonal `z−cz = −(x−cx)`) | `(Δx, Δz) → (−Δz, −Δx)` | `(x, z) → (cx − (z−cz), cz − (x−cx))` |
| `rot_180` | `(Δx, Δz) → (−Δx, −Δz)` | `(x, z) → (2cx − x, 2cz − z)` |
| `rot_90` (CCW) | `(Δx, Δz) → (−Δz, Δx)` | `(x, z) → (cx − (z−cz), cz + (x−cx))` |

**General n-fold rotation** `rot_<d>` with step `d = 360/n` (e.g. `rot_120`/`rot_72`/`rot_60`):
`(x, z) → (cx + Δx·cos θ − Δz·sin θ, cz + Δx·sin θ + Δz·cos θ)` with **θ = d°** (consistent with the
`rot_90` row at θ = 90°). Only `rot_180`/`rot_90` are exact on the block grid; other `rot_n` are
approximate (crystallographic restriction) and bake to concrete geometry — see contract §7.

**Visual note:** because `+z` is south (down), a mathematically-CCW rotation appears clockwise on the
rendered map.

**UI label → mirror line** (where the axis is drawn on the canvas):

| UI label | Formula | Mirror line |
|---|---|---|
| Mirror X | `mirror_z` (flip Z) | `z = cz` (horizontal) |
| Mirror Z | `mirror_x` (flip X) | `x = cx` (vertical) |
| Mirror ⟋ | `mirror_d2` | `z − cz = −(x − cx)` |
| Mirror ⟍ | `mirror_d1` | `z − cz = x − cx` |
| Rotate 180° | `rot_180` | — |
| Rotate 90° | `rot_90` | — |

(Diagonal/secondary-axis canvas controls are D-series; the mode strings are settled.)

**Center-cell parity** (the computation): `axis_width(c) = 1 if frac(c) == .5 else 2`, giving
`cell = "{x}x{z}"` ∈ `1x1`/`1x2`/`2x1`/`2x2` (`symmetry.datatypes.classify_center_cell`). Which cells
each mode permits is a model rule — contract §7.

---

## 3. Transform module (`transform.js`)

The single canonical transform module, object-bbox form:

```js
buildTransform({ min_x, min_z, max_x, max_z }, svgW, svgH)        → (wx, wz) => { x, y }
buildInverseTransform({ min_x, min_z, max_x, max_z }, svgW, svgH) → (px, py) => { x, z }   // world coords
```

Helpers in the same module: `svgEl(tag, attrs, children)`; `ringToPath(ring, toSvg)`;
`polyToPath(poly, toSvg)` (`{exterior,holes}` or `{polygons}` → compound path);
`boundsToRingPath(bounds, toSvg)`; `clipHalfPlane(poly, ox, oz, nx, nz)` (Sutherland–Hodgman). Both
canvases import from this one module.

---

## 4. Shared canvas base (`canvas-base.js`)

`CanvasBase` is the shared pan/zoom base both `MapCanvas` (editor) and `SketchLayoutCanvas` (sketch)
inherit from. It owns: `#scale`/`#panX`/`#panY`; the `#viewportG` matrix
(`matrix(scale,0,0,scale,panX,panY)`); scroll-wheel zoom centred on the cursor; middle-click pan;
`#clientToSvg()` (screen px → base-SVG, before pan/zoom); `resize()`. Zoom constants
`ZOOM_FACTOR=1.15`, `ZOOM_MIN=0.5`, `ZOOM_MAX=200`. **Resize/vertex handles live in screen space** —
appended to the SVG root, not `#viewportG`, so they stay fixed-size under zoom.

**Coordinate-space difference** (intentional — do not generalise `#clientToSvg()` across both):
- **MapCanvas:** base-SVG px are *not* world coords; needs `buildInverseTransform()` to reach world.
- **SketchLayoutCanvas:** world coords *are* the base-SVG coords (pan/zoom only via the viewport
  matrix), so it passes an identity transform to the shared path helpers:
  ```js
  const identityTransform = (x, z) => ({ x, y: z });
  ringToPath(vertices, identityTransform);
  ```

---

## 5. Canvas shape formats

Canonical persisted region shapes are owned by the contract (§4). This section covers only the
**canvas-facing** forms.

**Sketch shapes** (drawn in Layout; feed the boolean island computation; extent bounds at draw time):

| Type | Key fields |
|---|---|
| rectangle | `min_x, max_x, min_z, max_z` |
| circle | `center_x, center_z, radius` |
| polygon | `vertices: [[x,z], ...]` |

**Drawn-region wire format** (what a completed draw tool emits; the activity decides what to do):

```js
{ type: "rectangle" | "cuboid", min_x, min_z, max_x, max_z }   // rectangle / cuboid
{ type: "cylinder" | "circle", center_x, center_z, radius }    // cylinder / circle
{ type: "point" | "block", x, z }                              // point / block
```

**Per-type display bounds** (for the canvas; `regionToBounds2d` dispatches by type):

| Type | `bounds` derivation |
|---|---|
| rectangle / cuboid | as stored (cuboid = XZ projection) |
| cylinder | `base ± radius` · circle `center ± radius` · sphere `origin ± radius` |
| block | `[x, x+1] × [z, z+1]` (+1 rule) |
| point | `[x−0.5, x+0.5] × [z−0.5, z+0.5]` |

Composite/special regions return `null` (no direct 2D footprint).

---

## 6. Required converters

Each has **exactly one implementation**, tested independently. No caller applies raw `+1` or rotation
arithmetic directly.

```js
blockToExtentBounds(x, z)        → { min_x:x, max_x:x+1, min_z:z, max_z:z+1 }
drawnBoundsFromBlocks(b1x,b1z,b2x,b2z)
                                 → { min_x:min(b1x,b2x), max_x:max(b1x,b2x)+1,
                                     min_z:min(b1z,b2z), max_z:max(b1z,b2z)+1 }   // the +1 for drawing
regionToBounds2d(region)         → { min_x,max_x,min_z,max_z } | null            // dispatch by type (§5)
applySymmetry(x, z, axis, cx, cz)            → [x', z']      // the only home for the §2 formulas
applySymmetryToBounds(bounds, axis, cx, cz)  → { min_x,max_x,min_z,max_z }       // 4 corners, re-min/max
rasterisePolygon(exterior, holes)            → [[x,z], ...]  // integer blocks whose unit square is inside
sketchShapeToPgmRegion(shape)                → PGM region | null
```

- `applySymmetry` `axis` ∈ `mirror_x`/`mirror_z`/`rot_180`/`rot_90` today; `mirror_d1`/`mirror_d2`
  and `rot_<n>` land with the D-series canvas work — keep them formula-identical to the Python side.
- **Python peer:** `pgm_map_studio/geometry.py` is the canonical Python converter home (a pure-math
  leaf): `reflect_point_2d`/`reflect_bounds_2d` (PGM `<mirror>` semantics, any normal incl. diagonal)
  and `rotate_point_2d`/`rotate_bounds_2d` (CCW, 90°-multiples exact). The editor counterpart-creation
  (C13) and the parser use these. `detection.py` and `sketch_export.py` (via
  `region_geometry.transform_geom`) are consolidated onto this module — one implementation per
  converter. The JS `converters.js` is the necessary cross-language twin, kept in parity by a Vitest test.
- `rasterisePolygon` takes extent coords (boolean-clip output); no +1 before calling. Used by sketch
  export to build the synthetic scan layer.
- `sketchShapeToPgmRegion`: rectangle→Rectangle, circle→Circle; **polygons are never exported as PGM
  regions** (they shape the rasterised scan layer only).

---

## 7. Shared SVG rendering & toolbar

**Rendering** — one `renderShape(type, boundsOrPoly, toSvg, attrs)` dispatch for both canvases:
`rectangle`/`cuboid` → `<rect>` (via `boundsToRingPath`); `cylinder`/`circle`/`sphere` → `<ellipse>`
(centre ± radius); any region with `polygon_2d` → `<path>` (via `polyToPath`).

**Toolbar** — `ToolManager` (`tool-manager.js`) tracks the active tool, highlights its button, and
calls `canvas.setActiveTool(name | null)`. The editor tool set is a subset of the sketch's (both:
move/pan, rectangle, circle; editor-only: point/block; sketch-only: polygon, lasso, add/subtract).

---

## 8. Converter test cases

```
+1 rule
  drawnBoundsFromBlocks(3,5,3,5) → {min_x:3,max_x:4,min_z:5,max_z:6}   (single block)
  drawnBoundsFromBlocks(3,5,6,9) → {min_x:3,max_x:7,min_z:5,max_z:10}
  blockToExtentBounds(7,2)       → {min_x:7,max_x:8,min_z:2,max_z:3}

Symmetry (applySymmetry x, z, axis, cx, cz)
  mirror_x 10,20 @0,0 → [-10,20]   ; @5,5 → [0,20]
  mirror_z 10,20 @0,0 → [10,-20]   ; @5,15 → [10,10]
  rot_180  10,20 @0,0 → [-10,-20]  ; @5,10 → [0,0]
  rot_90    1,0  @0,0 → [0,1]      ;  0,1 @0,0 → [-1,0]
  mirror_d1 10,20 @0,0 → [20,10]   (X↔Z swap about center)
  mirror_d2 10,20 @0,0 → [-20,-10] ; 3,1 @0,0 → [-1,-3]
  applySymmetryToBounds twice with the same reflection axis → original (reflections are involutions)

Rasterisation
  2×2 extent poly [[0,0],[2,0],[2,2],[0,2]] → exactly (0,0),(1,0),(0,1),(1,1)
  a 1.5-wide extent poly yields only blocks whose unit square overlaps, not those merely touching

PGM region bounds
  regionToBounds2d({type:"block", x:5, z:3}) → {min_x:5,max_x:6,min_z:3,max_z:4}   (+1 once)
  regionToBounds2d({type:"cylinder", base_x:10, base_z:10, radius:5}) → {min_x:5,max_x:15,min_z:5,max_z:15}
```
