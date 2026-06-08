# pgm_map_studio.studio

Flask web application for PGM Map Studio. Serves three pages — **Dashboard**,
**Sketch**, and **Editor** — backed by a layered front end (page → activities
→ panels → canvases) and a layered back end (routes → services → JSON/parquet
data on disk).

## App factory

`create_app()` (in `__init__.py`) registers one blueprint per concern and
returns a configured `Flask` app. `run_server()` starts it on port 7892.

```python
from pgm_map_studio.studio import create_app, run_server

app = create_app()        # for testing / WSGI
run_server(port=7892)     # for local development — opens a browser tab
```

| Blueprint | Module | Mounted at |
|---|---|---|
| `pages` | `routes/pages.py` | `/`, `/editor`, `/sketch`, `/design` |
| `config` | `routes/config.py` | `/api/config` |
| `configure` | `routes/configure.py` | `/api/configure/...` |
| `sources` | `routes/sources.py` | `/api/sources/...` |
| `pipeline` | `routes/pipeline.py` | `/api/pipeline/...` |
| `map_api` | `routes/map_api.py` | `/api/map/<name>/...` |
| `regions` | `routes/regions.py` | `/api/map/<name>/regions/...` |
| `teams` | `routes/teams.py` | `/api/map/<name>/teams/...` |
| `spawns` | `routes/spawns.py` | `/api/map/<name>/spawns/...` |
| `minecraft` | `routes/minecraft.py` | `/api/minecraft/...` |
| `sketch_api` | `routes/sketch_api.py` | `/api/sketches/...` |

## Front-end layering

Every page follows the same pattern, from the bootstrap script down to the
canvas:

```
<page>-main.js / dashboard.js   — bootstrap: wires DOM, owns page-level state
        │  switches between …
        ▼
activities/<name>-activity.js   — owns a workspace section; activate/deactivate/resize
        │  delegates rendering + form logic to …
        ▼
panels/<name>-panel.js          — DOM population, validation, save/load via api.js
        │  delegates drawing to …
        ▼
canvas/<name>-canvas.js         — SVG rendering, pan/zoom, tool handling (extends CanvasBase)
```

- **Activities** are the unit the activity rail switches between. Each
  exposes `activate({...})`, `deactivate()`, `resize()`, and reports status
  via an `onStatusChange` callback (renders the coloured dot on its rail
  button). See `activities/overview-activity.js` for the minimal shape and
  `activities/configure-activity.js` / `sketch-layout-activity.js` for ones
  that also own a `ToolManager` and canvas tools.
- **Panels** hold the actual DOM/canvas wiring for an activity's workspace.
  An activity is mostly a thin shell around one panel; splitting them keeps
  `activate`/`deactivate`/`resize` consistent across activities while the
  panel focuses on data loading and form behaviour.
- **Canvases** extend `canvas/canvas-base.js` (`CanvasBase`), which provides
  shared pan/zoom/transform machinery (see `docs/cross-cutting.md` §2). They
  override hook methods (`_onViewportChanged`, `_onZoomChanged`, tool
  handlers) rather than re-implementing the viewport.
- All server communication goes through `static/api.js` — panels never call
  `fetch` directly. Add new endpoints there as named `fetch...`/`save...`
  functions.

## Pages

### Dashboard (`/`)

Template `templates/dashboard.html`, bootstrap `static/dashboard.js`.

Lists imported map sources and sketch sessions, shows per-map pipeline status,
runs the analysis pipeline (via SSE in `routes/pipeline.py`), and lets the
user import new sources from a folder or URL. It is the entry point into both
the Sketch and Editor pages — selecting a map or sketch links to `/editor?map=<slug>`
or `/sketch?id=<id>`.

Backed by `routes/sources.py`, `routes/pipeline.py`, `routes/config.py`,
`routes/minecraft.py` (player avatar lookups), and `services/config.py`,
`services/map_status.py`.

### Sketch (`/sketch?id=<sketch-id>`)

Template `templates/sketch.html`, bootstrap `static/sketch-main.js`.

Concept-first workflow for designing a new map before any world exists:
draw a bounding box and islands on a blank canvas, preview mirrored copies,
then export to a synthetic scan layer that hands off to the Editor. See
`docs/sketch-workflow.md` for the design rationale.

| Activity | Panel | Canvas |
|---|---|---|
| Overview | `sketch-overview-panel.js` | — |
| Setup | `sketch-setup-panel.js` | `sketch-setup-canvas.js` |
| Layout | `sketch-layout-panel.js` | `sketch-layout-canvas.js` (uses `concept-canvas.js` + `sketch/geometry.js`) |

A sketch session is identified by `?id=` and persisted as JSON under
`~/.config/pgm-map-studio/sketches/`. Backed by `routes/sketch_api.py` and
`services/sketch_data.py` (load/save session state) +
`services/sketch_export.py` (rasterises drawn shapes into a synthetic scan
layer and writes a new map source for the Editor to open).

### Editor (`/editor?map=<slug>`)

Template `templates/editor.html`, bootstrap `static/main.js`.

Existing-map workflow: import a scanned `.mca` world, confirm the detected
layout/symmetry, then edit teams, spawns, objectives, and regions directly
on the rendered map. See `plans/editor-vision.md` for the full activity list
and `docs/requirements/editor-*.md` for per-activity requirements.

| Activity | Panel | Canvas |
|---|---|---|
| Configure | (inline in `configure-activity.js`) | `configure-canvas.js` |
| Overview | `overview-panel.js` | `overview-canvas.js` |
| Teams | `teams-panel.js` | `map-canvas.js` |
| Objective, Regions | *stubs* — `STUB_IDS` in `main.js`, not yet implemented | — |

Backed by `routes/configure.py`, `routes/map_api.py`, `routes/regions.py`,
`routes/teams.py`, `routes/spawns.py`, and the corresponding services
(`region_builder.py`, `region_editor.py`, `region_tree.py`, `team_editor.py`,
`spawn_editor.py`, `xml_data.py`). Map data persists as `xml_data.json` /
`islands.json` / `symmetry.json` under the pipeline output directory
(see `pipeline/README.md`); `services/xml_data.py` is the single
load/save entry point — routes never read/write the file directly.

### Design (`/design`)

Template `templates/design.html`. Living visual reference for every CSS
component and token in `components.css` / `editor.css` / `tokens.css` /
`design.css`. Check it before writing new CSS — if a class already exists,
reuse it; if it doesn't, add it to the right stylesheet *and* a demo section
here in the same change. See `docs/ui-conventions.md`.

## Adding a new activity

1. Add the workspace markup to the page template (`<div id="<name>-workspace" hidden>…</div>`)
   and a button to the activity rail.
2. Write the panel (`panels/<name>-panel.js`): query its DOM, load data via
   `api.js` (add new `fetch`/`save` functions there if the backend doesn't
   exist yet), render into a canvas if needed, wire save/dirty-tracking.
3. Write the activity (`activities/<name>-activity.js`): thin wrapper around
   the panel exposing `activate`/`deactivate`/`resize` and an
   `onStatusChange` callback.
4. Register the activity in the page bootstrap (`main.js` / `sketch-main.js`):
   add it to the `ACTIVITIES` map, wire its rail button's click handler, and
   forward `onStatusChange` to the button's `data-status`.
5. If new server endpoints are needed: add a route to the matching blueprint
   in `routes/`, delegate the logic to a `services/` module (routes stay thin
   — validation/business logic lives in services and raises typed exceptions
   that the route maps to HTTP status codes; see `routes/teams.py` +
   `services/team_editor.py` for the pattern), and add `api.js` wrappers.
6. Read `docs/cross-cutting.md` before touching canvas, symmetry, coordinate,
   or shape/region code — it defines the single-implementation converters
   (`blockToExtentBounds`, `applySymmetry`, etc.) that all canvases must share.

## Shared front-end modules

- `static/shared/` — `tool-manager.js` (toolbar button state), `ui-helpers.js`
  (the two canonical notification types: `showSystemError`/`showToast`),
  `converters.js` (spatial conversions — single implementation per function),
  `region-render.js` / `block-render.js` (SVG shape + block-layer rendering
  shared between editor and sketch canvases), `game-colors.js`.
- `static/canvas/` — `canvas-base.js` (`CanvasBase`: pan/zoom/transform
  contract all canvases extend) and `transform.js` (pure coordinate math /
  SVG element helpers, bbox as `{min_x, min_z, max_x, max_z}`).
- `static/region/` — `region-registry.js` (selection-tree state machine used
  by the Editor's region tree) and `region-types.js`.
- `static/algorithms/` — `simplify.js`, the single home for polygon
  vertex-reduction algorithms (Visvalingam–Whyatt, etc.).

## Tests

- **Python** — `tests/studio/` (pytest), one file per `services`/`routes`
  module under test, e.g. `test_sketch_export.py`, `test_region_editor.py`,
  `test_configure_routes.py`. Run with `pytest` from the project root.
- **JavaScript** — `tests/js/*.test.js` (Vitest), covering the shared
  converters, canvas renderers, and algorithms (`tool-manager.test.js`,
  `converters.test.js`, `region-render.test.js`, `sketch-geometry.test.js`,
  `algorithms-simplify.test.js`). Run from the separate runner directory —
  see `docs/testing.md` for why and how.

## Running locally

Use the `run-studio` skill, or `run_server()` directly — the app listens on
**port 7892**. Restart the server after changing Python sources or Jinja2
templates (Flask caches templates at first load); static JS/CSS only need a
hard browser reload (`Ctrl+Shift+R`).
