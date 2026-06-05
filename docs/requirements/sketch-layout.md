# Requirements: Sketch — Layout

**Semantic purpose:** Draw the island layout by placing and combining primitive shapes. Configure which islands participate in the mirror mode and preview the full symmetric map.

**Canvas mode:** Full drawing tools (rectangle, circle, polygon, lasso), plus move and zoom.

*Author goals: Where are the islands? Which gaps are bridgeable? Where should the layout break symmetry deliberately?*

---

## Sub-step 1: Shape Drawing

**User requirements**
- Draw primitive shapes on the canvas:
  - **Rectangle** — drag to define bounds
  - **Circle** — two-click: center then radius
  - **Polygon** — click vertices, double-click or click first vertex to close
  - **Lasso** — hold mouse and drag to trace a freeform outline; release to close
- All coordinates snap to integer block positions.
- Tag each shape as **add** or **subtract**; toggle freely at any time.
- Islands emerge automatically from the boolean topology of drawn shapes — no manual island creation.
- Rename islands inline in the sidebar.
- Select a shape on the canvas or in the sidebar to populate the inspector.
- Delete shapes via the sidebar remove button or Delete/Backspace when selected.
- Resize rectangles using 8-point handles; drag polygon vertices to adjust shape.

**System requirements**
- Recompute island polygons after every shape addition, deletion, geometry change, or operation toggle.
- Boolean evaluation order: normal-add union → normal-subtract difference → override-add union → override-subtract difference.
- Assign each shape to its island(s) by polygon intersection, not centroid. A subtract shape spanning two islands must appear under both in the sidebar.
- Show a warning toast when a new add shape creates a disconnected island.
- Sidebar: 2-level tree — island header (editable name, shape count, color dot, mirror participation toggle) → shape children (operation badge, type label, shield toggle, remove button). Operation badge is clickable to toggle add/subtract.
- Inspector for selected shape: type badge, operation badge, coordinate table (MIN/MAX/SIZE per axis). Lasso shapes additionally show area and Visvalingam–Whyatt simplification controls (tolerance input, Generalize button).
- Resize handles and vertex drag handles are screen-space fixed size regardless of zoom level.

---

## Sub-step 2: Override Mode

**User requirements**
- Enable the override flag (shield toggle in the sidebar) on any shape that must win over the default evaluation order:
  - **Override add** — unioned in after normal subtraction; immune to normal subtract shapes.
  - **Override subtract** — cuts last; carves through everything including override add shapes.

**System requirements**
- Include the override flag in boolean evaluation order (steps 3 and 4).
- Reflect the active override state visually on the shape row (shield icon tinted teal for override add, red for override subtract).

---

## Sub-step 3: Mirror Preview and Participation

**User requirements**
- Toggle the mirror preview on or off at any time. The toggle does not affect which islands participate — it only controls canvas visibility.
- Per-island: toggle whether the island participates in the mirror mode. Default is **on** for every newly created island.
- Non-participating islands remain visible in the authored sector but generate no mirrored copies.

**System requirements**
- New islands inherit mirror participation = on by default.
- Live mirror overlay: when enabled, compute mirrored or rotated copies of all participating islands using the axis and center from Setup. Render as a visually distinct layer (lower opacity or alternate tint) to distinguish from authored shapes.
- Non-participating islands are excluded from the overlay.
- The live overlay is never stored as shapes. Serialising sketch state exports only authored shapes and per-island participation flags.
- When center or mirror mode changes in Setup, recompute and redraw the live overlay immediately if it is currently visible.
- Mirror participation toggle is exposed on the island header row in the sidebar.

---

## Sub-step 4: Primitives Overlay

**User requirements**
- Toggle the Primitives overlay to inspect individual shapes beneath the computed island polygons.

**System requirements**
- When enabled, render each primitive shape as a semi-transparent overlay on the canvas (add shapes in one tint, subtract shapes in another).
- The overlay does not affect the island computation or any stored state.

---

## Dependencies

- Depends on Setup for bounding box (canvas extent), center point (mirror axis anchor), and mirror mode (symmetry type).
- Changes to center or mirror mode in Setup recompute the live overlay in Layout immediately if the preview is currently on.
