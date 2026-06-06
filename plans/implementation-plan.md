# Implementation Plan

This plan is the single source of truth for what to build next and in what order. Each phase must be fully complete before moving to the next. The implementation order within each activity is defined in `CLAUDE.md`.

---

## Status key

✅ done · 🔲 pending · 🚧 in progress · ⏸ deferred

---

## Phase 0 — Cross-Cutting Infrastructure

These modules are prerequisites for both the Sketch and Editor workflows. No new activity should be started until all of Phase 0 is complete.

See `docs/cross-cutting.md` for full contracts, formulas, test cases, and the rationale for each item.

| # | Item | Requirements source | Status |
|---|---|---|---|
| 0.1 | **CanvasBase extraction** — shared pan/zoom/transform base class; `MapCanvas` and `ConceptCanvas` both inherit from it. Zoom constants: `ZOOM_FACTOR=1.15`, `ZOOM_MIN=0.5`, `ZOOM_MAX=200`. | `cross-cutting.md §2` | ✅ |
| 0.2 | **Unified transform.js** — single module with `buildTransform`, `buildInverseTransform`, `svgEl`, `ringToPath`, `polyToPath`, `boundsToRingPath`, `clipHalfPlane`. Both canvases import from here. | `cross-cutting.md §3` | ✅ |
| 0.3 | **Required converters** — `blockToExtentBounds`, `drawnBoundsFromBlocks`, `regionToBounds2d`, `applySymmetry`, `applySymmetryToBounds`, `rasterisePolygon`, `sketchShapeToPgmRegion`. Each has exactly one implementation with unit tests from `cross-cutting.md §8`. | `cross-cutting.md §5, §8` | ✅ |
| 0.4 | **ToolManager extraction** — shared toolbar class managing active tool, button highlight state, and `canvas.setActiveTool()`. | `cross-cutting.md §6` | ✅ |
| 0.5 | **Shared SVG region rendering** — `renderRegionShape(type, boundsOrPoly, toSvg, attrs)` dispatch function; avoids duplication between editor and sketch canvases. | `cross-cutting.md §7` | ✅ |

**Tests (Phase 0.1–0.3 complete):**
- 37 Vitest tests in `tests/js/converters.test.js` — all passing
- Runner: `cd /root/pgm-studio-tests && node_modules/.bin/vitest run`
- `MapCanvas` verified in browser (all 10 SVG layers rendered, no JS errors)

---

## Phase 1 — Sketch (Concept-First) Workflow

Entry path for new maps with no imported world. Produces the same three Configure outputs (scan layer, islands, symmetry) synthetically. See `docs/requirements/sketch.md` (index) and `docs/sketch-workflow.md` (mental model).

### 1.1 — Sketch: Overview

Requirements: `docs/requirements/sketch-overview.md`
Mental model: `docs/sketch-workflow.md §Identity and role`

| Sub-step | Summary |
|---|---|
| Map identity | Map name, version, gamemode (fixed `ctw`), objective text |
| Authors | UUID input, role (author / contributor), contribution note; UUID resolves to display name |
| Validation | Name non-empty + at least one author before Sketch is considered complete |
| Canvas | Read-only (pan + zoom only); shows current island layout if any |

Status: ✅

---

### 1.2 — Sketch: Setup

Requirements: `docs/requirements/sketch-setup.md`
Mental model: `docs/sketch-workflow.md §Symmetry model`

| Sub-step | Summary |
|---|---|
| Bounding box | min/max X and Z; canvas resizes; derived width/depth shown |
| Center point | Canvas crosshair draggable + numeric inputs; both update same value |
| Mirror mode | Mirror X / Mirror Z / Rotate 180° / Rotate 90°; axis line shown on canvas |

Status: ✅

---

### 1.3 — Sketch: Layout

Requirements: `docs/requirements/sketch-layout.md`
Mental model: `docs/sketch-workflow.md §Island model`, `§Symmetry model §Live preview overlay`

| Sub-step | Summary |
|---|---|
| Shape drawing | Rectangle, Circle, Polygon, Lasso; snapped to block grid; add / subtract tag |
| Boolean recompute | After every shape change; 4-step evaluation order; connected-component island emergence |
| Override mode | Shield toggle per shape; add-override immune to normal subtracts; subtract-override cuts last |
| Mirror preview | Live overlay of mirrored/rotated island copies; per-island opt-out; toggle visibility |
| Primitives overlay | Semi-transparent shape overlay beneath island polygons |
| Sidebar | 2-level tree: island header (name, color, mirror toggle) → shape children (op badge, shield, remove) |
| Inspector | Shape type, operation, coordinate table; lasso: area + Visvalingam–Whyatt controls |
| Handles | Resize handles (8-point) for rectangles; vertex drag for polygons; screen-space fixed size |

Status: ✅

---

### 1.4 — Sketch: Export

Requirements: `docs/requirements/sketch-export.md`
Mental model: `docs/sketch-workflow.md §Synthetic scan layer output`

| Item | Summary |
|---|---|
| Rasterise | Full layout (all sectors) → `layout_y0.parquet` format using `rasterisePolygon` |
| Gate | Export available only when layout has ≥ 2 islands |
| Handoff | Editor enters post-Configure state; Configure step skipped |
| Session state | Shapes, island names, participation flags, bbox, center, mirror mode all restorable |

Status: ✅

---

## Phase 2 — Editor (Existing-Map) Workflow

Entry path for maps imported from an existing Minecraft world. See `docs/requirements/editor.md` (index) and `plans/editor-vision.md` (activity order, notifications, symmetry suggestions).

### 2.1 — Editor: Configure

Requirements: `docs/requirements/editor-configure.md`
Vision: `plans/editor-vision.md §Activity Structure`

| Sub-step | Summary |
|---|---|
| Scan layer selection | Present Y-level layers from pipeline; user picks canonical scan layer; blocking decision |
| Island review & exclusion | Show detected islands (polygon, bbox, centroid); reversible exclusion |
| Symmetry confirmation | Show candidates with confidence scores; user confirms / overrides / rejects; activates mirroring engine and symmetry validation |

Status: 🔲

---

### 2.2 — Editor: Overview

Requirements: `docs/requirements/editor-overview.md`
Vision: `plans/editor-vision.md`

Extends the Sketch Overview panel. Same fields; reads from `xml_data.json` on load and persists edits back.

Status: 🚧 (M1 shell exists; needs API wiring and save persistence)

---

### 2.3 — Editor: Teams

Requirements: `docs/requirements/editor-teams.md`
Vision: `plans/editor-vision.md §Teams includes spawn placement`

Includes team CRUD, spawn placement, and inline spawn-protection filter setup.

Status: 🚧 (M1 shell exists; needs filter integration and status indicator logic)

---

### 2.4 — Editor: Build Regions

Requirements: `docs/requirements/editor-build-regions.md`
Vision: `plans/editor-vision.md §Build Regions before Objectives`

Defines max build height, traversable build areas, boundary enforcement, lockdowns, and physics. Inline block-editing filter setup.

Status: 🔲

---

### 2.5 — Editor: Objectives

Requirements: `docs/requirements/editor-objectives.md`

Wool objective placement, wool room access rules (inline filter), wool availability check. Requires Teams to be valid.

Status: 🔲

---

### 2.6 — Editor: Filters

Requirements: `docs/requirements/editor-filters.md`
Reference: `docs/filter-use-cases.md`

Final overview of all applied rules. Catch-all for mechanics not handled inline (jump pads, time-gated unlocks, anti-climb, resistance reset, block renewal summary).

Status: 🔲

---

### 2.7 — Editor: Regions

Requirements: `docs/requirements/editor-regions.md`
Vision: `plans/editor-vision.md §Regions Activity`

Flat list of all regions: type, bounds, assignments. Filter/sort by type, team, or assignment status. Unassigned regions highlighted. Full hierarchy view also available.

Status: 🔲

---

### 2.8 — Editor: Export

Vision: `plans/editor-vision.md §Export`

XML preview before download; round-trip safety check; download gated on Build Regions validity.

Status: 🔲

---

## Notes

- **Activity status indicators** (None / Yellow / Green / Red) must be wired up for each activity at implementation time. The exact "required fields" definition per activity comes from the requirements doc. See `plans/editor-vision.md §Activity Status`.
- **Symmetry suggestions** (mirroring engine) activate after Configure step 3 confirmation and apply inline in Teams, Build Regions, and Objectives. See `plans/editor-vision.md §Symmetry-Driven Suggestions`.
- **Notifications** use the four canonical types already implemented in M1. Per-activity trigger mapping is defined at implementation time. See `plans/editor-vision.md §Notification System`.
- The configure.html template currently exists as a placeholder. It will be fully implemented in Phase 2.1.
