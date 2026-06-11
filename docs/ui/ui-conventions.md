# UI Conventions

The studio uses a small set of production structures. `/design` renders the same
classes and nesting used by Dashboard, Editor, and Sketch; it is the visual reference,
while this document defines the contract.

## CSS ownership

Stylesheets load in this order:

1. `tokens.css`: custom properties only.
2. `components.css`: reusable controls and panel composition.
3. `editor.css`: app shell, workspaces, canvas tools, dashboard, and game-aware UI.
4. `design.css`: `/design` gallery helpers only.

A shared selector has one owning file. Never copy a component rule into `editor.css`
to adjust one activity. Add a modifier to the owning component when the distinction is
reusable; otherwise add an activity-specific semantic class.

## Selectors and tokens

- Classes style elements. IDs are JavaScript references only.
- Do not style activity IDs such as `#ov-left` or `#pt-right`.
- Use existing color, spacing, radius, type, transition, and shadow tokens.
- The five text levels in `tokens.css` are the complete text hierarchy.
- Data-driven colors, element visibility, cursor state, and drag position/width may be
  set at runtime. Static layout must be expressed by a class.
- Production templates contain no inline `style` attributes.

## Application shell

Dashboard, Editor, and Sketch use the same shell:

```html
<header id="topbar" class="topbar">...</header>
<main id="main" class="app-body">
  <nav id="activity-rail" class="activity-rail">...</nav>
  <div id="activity-viewport" class="activity-viewport">...</div>
</main>
```

Dashboard places `.master-detail` inside the viewport. Editor and Sketch place one or
more `.workspace` elements there.

## Workspace

Use this structure for a three-column activity:

```html
<section class="workspace">
  <aside id="activity-left" class="workspace-sidebar">
    <div class="workspace-scroll">
      <section class="panel-section">...</section>
    </div>
  </aside>

  <div class="sidebar-handle"
       data-resize-target="activity-left"
       data-resize-side="left"></div>

  <div class="workspace-canvas">
    <div class="canvas-subbar">...</div>
    <svg class="canvas-surface">...</svg>
  </div>

  <div class="sidebar-handle"
       data-resize-target="activity-right"
       data-resize-side="right"></div>

  <aside id="activity-right" class="workspace-inspector">
    <div class="workspace-scroll">
      <section class="panel-section">...</section>
    </div>
  </aside>
</section>
```

Rules:

- A sidebar or inspector owns exactly one direct `.workspace-scroll`.
- A resizable panel has an adjacent `.sidebar-handle`.
- Resize behavior comes from `shared/panel-resize.js`; do not add local drag code.
- `.workspace-canvas` owns column layout. `.canvas-surface` owns the drawable area.
- `.canvas-subbar` is optional but always sits before the surface.

## Panel section

```html
<section class="panel-section">
  <header class="section-header section-header--ruled">
    <h2 class="section-title">Authors</h2>
    <div class="section-actions">...</div>
  </header>

  <div class="section-body">...</div>

  <footer class="section-footer">...</footer>
</section>
```

`section-header`, `section-body`, and `section-footer` are optional structural slots.
Direct controls are allowed when a section does not need an extra grouping element.
Use the ruled header by default in side panels.

Common content:

- `.panel-stack`: multiple sibling sections inside one inspector or sidebar state.
- `.section-heading`: a left-aligned title cluster for an icon or swatch plus
  `.section-title`; keep `.section-actions` as the optional right-side cluster.
- `.field`, `.field-row`: labels and form controls.
- `.coord-field`, `.coord-input`, `.detail-table`: coordinates and geometry.
- `.control-list`, `.check-row`: repeated toggles and options.
- `.panel-list`, `.list-row`: repeated selectable or editable records.
- `.author-list`, `.author-row`: author and contributor records.
- `.region-tree`, `.geo-row`: recursive game-region collections and their rows. Keep
  the tree inside the `.panel-section` that owns its ruled header.
- `.panel-empty`, `.panel-empty-msg`, `.list-empty`: empty states at their respective
  scopes.
- `.panel-warning`: persistent validation feedback inside a panel.

## Actions and status

Buttons:

- `.action-btn`
- `.action-btn--primary`
- `.action-btn--danger`
- `.action-btn--icon`
- `.btn-remove`

Layout modifiers such as `--fill`, `--full`, and `--push-end` change placement, not
visual meaning. Do not create another visual button family.

Badges use `.badge` with `--success`, `--warning`, `--error`, `--neutral`, or `--dim`.

Notifications are limited to `#topbar-error`, `.toast`, `.canvas-hint`, and
`.panel-warning`.

## Adding or changing UI

1. Open `/design` and find the closest production example.
2. Copy its structure and classes.
3. If a needed pattern is missing, add it to the owning CSS file.
4. Add or update the `/design` example in the same change.
5. Add a structural test when the rule is important enough that future work could
   silently break it.
6. Verify Dashboard, Editor, and Sketch at the affected panel widths.

Do not use `/design` as a second implementation. Its examples should remain small,
copyable fragments built from production classes.
