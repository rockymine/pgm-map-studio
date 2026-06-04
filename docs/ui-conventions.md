# UI Conventions

Living reference for how UI is built in PGM Map Studio.
The `/design` page (run the app, navigate to `/design`) is the visual counterpart —
every class documented here has a rendered example there.

---

## CSS file responsibilities

Ask one question before adding CSS:
**Does this class know anything about PGM, CTW, regions, or the editor's page structure?**

| No → | `components.css` |
| Yes → | `editor.css` |

| File | Owns | Never contains |
|---|---|---|
| `tokens.css` | CSS custom properties only (`:root`) | Any selector beyond `:root` |
| `components.css` | Game-agnostic UI patterns — buttons, badges, fields, list rows, panels, console, step rows, notifications, canvas subbar structure | Activity-specific IDs, workspace layout, game terminology |
| `editor.css` | App shell, topbar, workspace layouts, activity rail, region tree, history panel, context menu, inspector/detail, dashboard | Reusable component classes, design-page helpers |
| `design.css` | Layout helpers for the `/design` page only (`.ds-*`, `#ds-nav`) | Production component or structural classes |

---

## Selector rules

### IDs are for JavaScript, not CSS

```html
<div id="pt-left" class="workspace-sidebar">
```

- `id="pt-left"` → JS handle so `document.getElementById("pt-left")` works
- `class="workspace-sidebar"` → all styling

**Never use an ID selector in CSS to express a shared or repeated layout pattern.**
Only use an ID selector in CSS when the element is:
1. A truly one-of-a-kind page shell element (`#topbar`, `#activity-rail`, `#dashboard-layout`) **and**
2. Has no shared pattern to extract into a class

If you find yourself writing `#ov-left { width: 280px }` and `#pt-left { width: 240px }`,
that is the wrong approach — the width belongs on a class.

### Why this matters — specificity

ID selectors have specificity `(1,0,0)`. Class selectors have `(0,1,0)`.
An ID rule beats a class rule even if the class comes later in the file,
making the system fragile and hard to override.

```
#topbar          (1,0,0)  ← heaviest
.action-btn      (0,1,0)
button           (0,0,1)
*                (0,0,0)  ← lightest
```

### Selector reference

```css
button           /* type — every <button> */
.action-btn      /* class — any element with this class */
#topbar          /* id — the one element with this id (JS handle only) */
[hidden]         /* attribute */
[data-status="green"]::after  /* attribute + pseudo-element */
.action-btn:hover             /* pseudo-class (state) */
.sidebar-handle::before       /* pseudo-element (generated part) */
*                /* universal */

/* Combinators */
#pt-spawn-list .region-type-icon   /* descendant */
.workspace-scroll > .panel-section /* direct child */
.field + .field                    /* adjacent sibling */
```

---

## Design tokens

All CSS custom properties live in `tokens.css`. Never hardcode a value that has a token.

### Key tokens

```css
/* Sidebar widths — change here to affect all panels */
--sidebar-width:   280px;
--inspector-width: 280px;

/* Backgrounds */
--bg-base          /* page body */
--bg-panel         /* sidebars, topbar, panels */
--bg-selected      /* selected row, active button fill */
--bg-selected-hover /* row hover */

/* Text (muted → bright) */
--text-muted       /* section labels, metadata */
--text-dim         /* helper text, synthetic labels */
--text-secondary   /* field labels, secondary content */
--text-primary     /* default list/body text */
--text-bright      /* headings, topbar titles */
--text-white       /* hover/active states */

/* Border & accent */
--border           /* all dividers and input borders */
--accent           /* primary action border, active tool border */
--accent-light     /* active tool text, focus highlights */
--code-color       /* monospace/XML text */

/* Semantic status */
--color-success / --color-success-bg
--color-warning
--color-error / --color-error-bg / --color-error-light

/* Spacing scale */
--space-1: 4px   --space-2: 8px   --space-3: 12px
--space-4: 16px  --space-5: 20px  --space-6: 24px

/* Radii */
--radius-sm: 3px   --radius-md: 6px

/* Motion */
--transition-fast: 0.12s ease
```

---

## Workspace structure classes

Every editor activity workspace uses these four classes.
**Never repeat these properties on an ID selector.**

```css
.workspace          /* container — display:flex, flex:1, overflow:hidden */
.workspace-sidebar  /* left panel — width:--sidebar-width, bg-panel, flex col */
.workspace-inspector /* right panel — width:--inspector-width, bg-panel, flex col */
.workspace-scroll   /* inner scroll area — flex:1, overflow-y:auto, padding:16px 14px */
.workspace-canvas   /* canvas column — flex:1, flex col, overflow:hidden, bg:--bg-deep,
                       position:relative (positioning context for .canvas-hint overlays) */
```

Pattern in HTML:

```html
<div id="pt-workspace" class="workspace">
  <div id="pt-left" class="workspace-sidebar">
    <div id="pt-left-scroll" class="workspace-scroll"> … </div>
  </div>
  <div class="sidebar-handle" id="pt-left-handle"></div>
  <div id="pt-canvas-wrap" class="workspace-canvas"> … </div>
  <div class="sidebar-handle" id="pt-right-handle"></div>
  <div id="pt-right" class="workspace-inspector">
    <div id="pt-right-scroll" class="workspace-scroll"> … </div>
  </div>
</div>
```

The ID prefix (`ov-`, `pt-`) is an activity namespace — all workspaces live in the
DOM simultaneously, so IDs must be unique. The prefix prevents collisions.
CSS must never reference these prefixed IDs for shared layout.

---

## Component rules

### Buttons — four variants only

| Class | Use when |
|---|---|
| `.action-btn` | Any action — panels, topbar, sidebars |
| `.action-btn--primary` | Single primary action per section (Save, Open) |
| `.action-btn--danger` | Irreversible destructive actions only |
| `.btn-remove` | Inline row removal icon (✕) |
| `.draw-tool-btn` | Canvas toolbar tools (editor.css — editor-specific) |

Never add a new button variant without adding an example to `/design`.

### Badges — one system

`.badge` with semantic variants: `--success`, `--warning`, `--error`, `--neutral`, `--dim`.
Works both inline and standalone. Do not create a separate tag or badge system.

### Notifications — four types, no fifth

| Type | When |
|---|---|
| `#topbar-error.visible` | Unrecoverable page-level error |
| `.toast.visible` + `--success/--error` | Short-lived operation feedback |
| `.canvas-hint.visible` | Draw hints while a tool is active |
| `.panel-warning` | Persistent inline validation issue |

### List rows

Always use `.list-row` for teams, wools, spawns, islands.
For region tree rows use `.region-row` (editor.css — game-aware).

---

## Adding new UI

Before writing any new CSS:

1. Open `/design` — check if the class already exists.
2. If yes, use it.
3. If no, decide which file it belongs in (game-aware? → `editor.css`, generic? → `components.css`).
4. Write the class rule, add a demo to `/design`, then use it in the feature.

Never define a class solely inside a template's `<style>` block.
Never style a shared pattern via an ID selector.
Never hardcode a color, spacing value, or border-radius that has a token.
