# UI System Consolidation

## Goal

Make the studio shell and workspace panels predictable enough that a new activity can
be assembled from reference structures without inventing spacing, hierarchy, or local
CSS fixes.

This is a consolidation, not a visual redesign. Existing colors, typography, density,
and activity behavior remain unless a current inconsistency makes them unusable.

## Canonical composition

### Application shell

```text
topbar
app-body
  activity-rail
  activity-viewport
```

Dashboard, Editor, and Sketch share this shell. Dashboard uses a master-detail body;
Editor and Sketch place workspaces inside the activity viewport.

### Workspace

```text
workspace
  workspace-sidebar
    workspace-scroll
      panel-section
  sidebar-handle
  workspace-canvas
    canvas-subbar       (optional)
    canvas-surface
  sidebar-handle        (when an inspector exists)
  workspace-inspector  (optional)
    workspace-scroll
      panel-section
```

Rules:

- Every sidebar and inspector owns exactly one `.workspace-scroll`.
- A visible resizable panel has an adjacent `.sidebar-handle`.
- `.workspace-canvas` owns column layout; `.canvas-surface` owns the drawable area.
- Activity IDs are JavaScript handles only. Shared layout never depends on them.

### Panel section

```text
panel-section
  section-header        (optional)
    section-title
    section-actions     (optional)
  section-body
  section-footer        (optional)
```

Rules:

- `.panel-section` supplies vertical rhythm between its structural slots.
- `.panel-stack` supplies rhythm between multiple sibling sections in one panel state.
- `.section-header--ruled` is the default panel header.
- `.section-body` optionally groups related controls without adding outer panel spacing.
- `.section-footer` contains save, delete, navigation, and status actions.
- Lists use `.panel-list`; repeated author entries use `.author-list`.
- Empty states use `.panel-empty` for a whole panel or `.list-empty` inside a list.

### Common section content

```text
field
field-row
coord-row
control-list
panel-list
author-list
detail-table
```

These are compositions, not activity-specific components. Activity code may add
semantic classes for JavaScript hooks, but it should not recreate their layout.

## CSS ownership

- `tokens.css`: custom properties only.
- `components.css`: reusable controls and panel composition.
- `editor.css`: application shell, workspace, dashboard, canvas tools, and game-aware
  structures.
- `design.css`: `/design` gallery layout only.

Stylesheets load in that order so app-specific rules can intentionally refine shared
components. A shared selector must have one owning file.

## Documentation strategy

`/design` becomes a short component gallery, not an encyclopaedia.

It will contain:

1. Foundations: color, type, spacing.
2. Panel reference: form, list, authors, coordinates, controls, inspector.
3. Workspace reference: two-column and three-column production structures.
4. Canvas reference: subbar, tools, status, empty state.
5. Usage rules: concise do/don't guidance and links to this plan and
   `docs/ui-conventions.md`.

Examples use production classes and production nesting. Diagram-only mock classes are
removed. The rendered example itself is the reference implementation.

## Guardrails

Automated tests verify:

- Production templates contain no inline `style` attributes.
- Stylesheets load in the ownership order.
- Every workspace panel has a scroll container.
- Every inspector has a preceding resize handle.
- Shared selectors are not duplicated across component and app CSS.
- The design gallery renders the canonical structures.

## Migration order

1. Add tests and shared composition classes.
2. Normalize stylesheet order and remove duplicate CSS ownership.
3. Migrate Editor and Sketch workspaces.
4. Normalize generated author, list, coordinate, and inspector markup.
5. Model Dashboard as the shared shell plus a documented master-detail layout.
6. Replace `/design` with the compact production-backed gallery.
7. Update `docs/ui/ui-conventions.md`, run all tests, and visually verify each workflow.
