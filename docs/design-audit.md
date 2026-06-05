# Design System Audit

Assessment of the current `/design` page against what the full editor and sketch workflows require. Organised as: what's solid, what's missing, what would currently be difficult to build, and what new tokens are needed.

---

## What's solid

The foundations and shared components are in good shape and need no new work:

- **Tokens** — color, spacing, radii, motion all complete. Every referenced token has a sensible value.
- **Buttons** — four variants (action-btn, --primary, --danger, btn-remove) cover all known use cases.
- **Form fields** — field-input, field-label, field-row, field-pick-row, author-row: sufficient for Overview and Teams panels.
- **List rows** — list-row with swatch, label, tag, hover/selected states. Compact variant exists.
- **Badges** — five semantic variants (success, warning, error, neutral, dim) cover all status needs.
- **Notifications** — all four types documented: topbar-error, toast, canvas-hint, panel-warning.
- **Workspace pattern** — workspace, workspace-sidebar, workspace-inspector, workspace-scroll, workspace-canvas documented and consistent.
- **Activity rail** — status dots (green/yellow/red) and active indicator documented.
- **Region tree** — region-row, indent-pipe, collapse-btn, cat-header pattern is complete.
- **Inspector detail** — detail-header, detail-geo-group, detail-prefixed-field, detail-bounds-input, detail-xml-pre documented.

---

## Gaps

### 1. Island tree — no design page entry

The sketch Layout activity uses a 2-level island tree (island header → shape children). This is structurally different from the region tree:

| Region tree | Island tree |
|---|---|
| type icon + indent pipes + label | color dot + editable inline name + shape count |
| `.region-row`, `.region-type-icon`, `.indent-pipe` | `.concept-island-header`, `.concept-island-name`, `.concept-island-count` |
| category dividers | no dividers |
| vis-btn on hover | mirror participation toggle (always visible or on hover) |

The island tree classes live in `concept.css` with no design page entry and no specification of how the participation toggle behaves. This needs a dedicated section showing the island group, the header row, and the shape child row together with all their interactive states.

### 2. Operation badges — not in the badge system

The sketch tool uses `.concept-op-badge--add` (teal) and `.concept-op-badge--sub` (red) to label shapes inside the island tree. These are distinct from the shared `.badge` variants: they use raw hex colors (`#0d948833 / #2dd4bf` and `#dc262633 / #f87171`) hardcoded in concept.css, not tokens. They need to be tokenised and added to the badge section.

### 3. Override button — undocumented pattern

The shield icon on shape child rows is a hover-reveal contextual button with two active states (teal = override-add, red = override-sub). No equivalent pattern exists in the design page. The button shares structural DNA with `.vis-btn` (hover-reveal, icon-only) but has two distinct active color states tied to add/subtract operation. Needs its own entry.

### 4. Draw toolbar — sketch tools entirely absent

The design page documents the **editor draw toolbar** only (rectangle, cuboid, cylinder, circle, point, block). The sketch toolbar adds tools and a second state axis that have no design page entry:

| Missing tool | Icon | Mode |
|---|---|---|
| Polygon | `pentagon` | drag to close or dblclick |
| Lasso | `lasso` | hold-drag |
| Add mode toggle | `plus-square` | operation state |
| Subtract mode toggle | `minus-square` | operation state |

The add/subtract toggle is a fundamentally different kind of control from the draw tool buttons: it selects an **operation** (how the drawn shape behaves) independently of the **tool** (what shape is drawn). The current toolbar section has no pattern for this dual-axis state.

### 5. Activity rail icons — sketch activities unspecified

The activity rail section shows status dot behaviour but doesn't specify which Lucide icon maps to which activity. Sketch has three activities and their icons are either provisional or absent:

| Sketch activity | Current icon | Status |
|---|---|---|
| Overview | `book-open-text` | Used in concept tool mock, not documented |
| Setup | — | No icon chosen yet |
| Layout | `pentagon` | Used in concept tool mock, not documented |

The editor activities (Configure, Overview, Teams, Build Regions, Objectives, Filters, Regions) also have no icon assignments documented.

### 6. Canvas — entirely absent from the design page

The canvas subbar is documented, but the SVG canvas surface itself has no design page entry. Everything needed to implement canvas rendering consistently is currently defined by scattered hardcoded hex values in JS files:

**Colors that need tokens (currently hardcoded in concept-canvas.js):**
- Add shape fill: `#0d9488` / stroke: `#0f766e`
- Subtract shape fill: `#dc2626` / stroke: `#b91c1c`
- Result polygon fill: `#6366f1` / stroke: `#4338ca`
- Island color palette (8 colours): `#4ade80 #60a5fa #f472b6 #fb923c #a78bfa #34d399 #facc15 #f87171`
- Center crosshair: `#a78bfa` (hardcoded)
- Draw preview stroke: `#94a3b8` (reuses --text-secondary; inconsistent)

**Patterns not documented:**
- Live mirror overlay rendering (lower opacity tint, separate SVG layer)
- Axis line / sector overlay for Setup (shows implied symmetry on canvas)
- Center crosshair marker (cross + circle)
- Result polygon fill-opacity vs primitive fill-opacity conventions
- Block image rendering (pixelated SVG `<image>` from offscreen canvas)
- Resize/vertex handle styling (square handle, `#0f172a` fill, `#94a3b8` stroke — all hardcoded)

### 7. Concept toast — duplicate of shared toast

The concept tool defines `.concept-toast` separately in concept.css with its own animation. This duplicates the shared `.toast` / `.toast--success` / `.toast--error` pattern from components.css. The concept toast is unstyled (no success/error variants — just a neutral info colour). It should be absorbed into the shared toast system with a neutral variant (`.toast--info` or similar), and `.concept-toast` removed.

### 8. Detail table — used but not documented

The sketch inspector uses a `.detail-table` for the rectangle geometry (showing MIN / MAX / SIZE columns) and a vertex table for polygon shapes. These exist in the concept tool's HTML but `.detail-table` is not defined in any CSS file and is not in the design page. It needs a component entry alongside the existing detail widget section.

### 9. Mirror participation toggle

Each island header needs a control for opting the island in or out of mirroring. No current pattern fits:
- `.vis-btn` is hover-only and only has one state (visible/hidden)
- `.filter-chip` works but is designed for filter bars, not tree rows
- A checkbox or small toggle inside the island header row needs to be specified — visible (not hover-only) since it communicates a persistent, meaningful state

---

## What would currently be difficult to implement

### Canvas colours inconsistent with the token system

Every canvas fill, stroke, and overlay colour is a hardcoded hex. Adding a canvas layer (e.g. the Setup axis overlay) means choosing an arbitrary colour with no reference. Before implementing the sketch canvas, all canvas colours need to go into tokens.css, and the design page needs a canvas colour section.

### Dual-axis toolbar (tool × operation)

The current `.draw-tool-btn` + `.draw-tool-btn--active` pattern handles a single active selection. The sketch toolbar needs two independent active states simultaneously: one active tool (which shape) and one active operation (add or subtract). The CSS pattern for this doesn't exist. Building it today would require either inventing a convention on the fly or misusing the existing classes.

### Island tree vs region tree coexistence

Both workflows need tree-structured sidebars, but with different visual patterns. The region tree uses `indent-pipe` and type icons; the island tree uses color dots and inline-editable names. If these ever appear in the same shell (e.g. after sketch exports and the editor opens), there needs to be a clear visual distinction and a documented rule for when to use which tree pattern.

### Per-island participation toggle placement

The toggle belongs in the island header row alongside the editable name. There's currently no pattern for a small persistent toggle control inside a list row header (vis-btn is hover-only; action-btn is too large; filter-chip is wrong context). Implementing this without first specifying the component would result in ad-hoc CSS.

### Simplify section (lasso inspector)

The simplify section in the concept tool inspector (area readout, tolerance input, Generalize button) uses `.concept-simplify-*` classes defined only in concept.css. This is a distinct widget — a numeric input paired with an action button and a read-only display value — that has no component equivalent in the design system. It would need to be specified before the inspector can be cleanly implemented.

---

## Tokens needed

All of these should go into `tokens.css` and be demonstrated on `/design`:

```css
/* Canvas — sketch operation colours */
--canvas-add-fill:    #0d9488;
--canvas-add-stroke:  #0f766e;
--canvas-sub-fill:    #dc2626;
--canvas-sub-stroke:  #b91c1c;

/* Canvas — result / island polygon */
--canvas-result-fill:   #6366f1;
--canvas-result-stroke: #4338ca;

/* Canvas — mirror overlay (live preview) */
--canvas-mirror-fill:    #6366f133;   /* result fill at ~20% */
--canvas-mirror-stroke:  #6366f188;

/* Canvas — symmetry axis indicator (Setup) */
--canvas-axis-color: #a78bfa;

/* Canvas — island color palette (8 slots) */
--island-color-0: #4ade80;
--island-color-1: #60a5fa;
--island-color-2: #f472b6;
--island-color-3: #fb923c;
--island-color-4: #a78bfa;
--island-color-5: #34d399;
--island-color-6: #facc15;
--island-color-7: #f87171;

/* Operation badge colours (to replace concept.css hardcodes) */
--op-add-bg:     #0d948833;
--op-add-text:   #2dd4bf;
--op-sub-bg:     #dc262633;
--op-sub-text:   #f87171;
```

---

## Summary by priority

| Gap | Effort | Blocks |
|---|---|---|
| Canvas color tokens | Low | Every sketch canvas feature |
| Draw toolbar — sketch tools + dual-axis pattern | Medium | Layout activity |
| Island tree component | Medium | Layout activity sidebar |
| Operation badges | Low | Island tree, shape children |
| Override button pattern | Low | Shape child rows |
| Activity rail icon assignments | Low | All activities |
| Mirror participation toggle | Medium | Island tree, Setup → Layout integration |
| Concept toast → shared toast | Low | Any sketch notification |
| Detail table component | Low | Sketch inspector |
| Canvas section on /design | High | All canvas work |
| Simplify widget | Low | Lasso inspector |
| Axis / mirror overlay spec | Medium | Setup and Layout canvases |
