# CLAUDE.md

## Cross-cutting concerns

Read `docs/cross-cutting.md` before writing any canvas, symmetry, coordinate, or shape/region code. It defines:
- The coordinate system (world space, +1 rule, axis orientation, bbox format)
- Symmetry rotation formulas and UI label → formula mapping
- Shared canvas base (pan/zoom/transform, shared between editor and sketch)
- Unified `transform.js` interface
- Shape and region wire formats
- Required converters (`blockToExtentBounds`, `drawnBoundsFromBlocks`, `applySymmetry`, `rasterisePolygon`, etc.) — each must have exactly one implementation
- Unit test cases for all converters

## UI

All UI work must follow `docs/ui-conventions.md`.

Key rules — read the doc for full detail:

- **CSS file split:** game-agnostic patterns → `components.css`. Editor/game-aware patterns → `editor.css`. Tokens → `tokens.css`. Design-page helpers → `design.css`.
- **Selectors:** use classes for styling, IDs for JS references only. Never use an ID selector to express a shared layout pattern.
- **Tokens:** never hardcode a color, spacing, radius, or transition that has a CSS variable in `tokens.css`.
- **Workspace layout:** use `.workspace`, `.workspace-sidebar`, `.workspace-inspector`, `.workspace-scroll`, `.workspace-canvas`. Do not repeat these properties on ID selectors.
- **Components:** check `/design` before writing any new CSS. If the class exists, use it. If it doesn't, add it to the right CSS file and add a demo to `/design` in the same change.
- **Buttons:** four variants only — `.action-btn`, `--primary`, `--danger`, `.btn-remove`.
- **Badges:** one system — `.badge` with `--success`, `--warning`, `--error`, `--neutral`, `--dim`.
- **Notifications:** four types only — `#topbar-error`, `.toast`, `.canvas-hint`, `.panel-warning`.

The `/design` page (start the app, navigate to `/design`) is the living visual reference.

## Dev server

The studio runs on **port 7892** via the `run-studio` skill.

**When to restart vs when to just reload:**

| Change type | Action needed |
|---|---|
| Python source (routes, services, models) | Restart server + reload browser |
| Jinja2 templates (`templates/*.html`) | Restart server + reload browser (Flask caches templates in memory at first load) |
| Static files (`static/*.css`, `static/*.js`) | Reload browser only — no restart needed |

Always use `Ctrl+Shift+R` (hard reload) in the browser after any change to bypass the browser cache. A normal reload may serve stale CSS or JS.

## Tests

- Framework: pytest (`pytest` from project root)
- One test file per source file, mirroring `src/pgm_map_studio/` under `tests/`
- File naming: `test_<source_filename>.py`
- Function naming: `test_<thing>_<condition>`
- Fixtures in `conftest.py` — synthetic data only, no real game files
- Integration tests (real `.mca` files) go in `tools/`, not `tests/`

See `docs/testing.md` for full rationale and examples.

## Requirements

Per-activity requirements live in `docs/requirements/`. One file per activity, prefixed by workflow.

**Editor workflow** (existing-map import path):
- `editor.md` — index
- `editor-configure.md` — scan layer, islands, symmetry
- `editor-overview.md` — map name, version, authors
- `editor-teams.md` — teams, kits, spawns, spawn access rules
- `editor-build-regions.md` — build area, boundary enforcement, lockdowns
- `editor-objectives.md` — wool objectives, wool room access, availability check
- `editor-filters.md` — rule review and advanced mechanics
- `editor-regions.md` — spatial registry audit

**Sketch workflow** (concept-first / new map path):
- `sketch.md` — index
- `sketch-overview.md` — map name, version, authors; read-only canvas
- `sketch-setup.md` — bounding box, center placement, mirror mode
- `sketch-layout.md` — shape drawing, override mode, mirror preview, per-island participation
- `sketch-export.md` — rasterisation to synthetic scan layer, editor handoff

**Source documents for existing-map activities:** `docs/map-data-model.md` (entities, questions to answer, statistics, dependencies) and `docs/ctw-map-pamphlet.md` (author goals, domain narrative, why constraints exist).

**Source document for Sketch:** `docs/sketch-workflow.md` — island boolean model, override mode, symmetry tiers, synthetic scan layer output.

**Format per file:**

```
# Requirements: <Activity>

**Semantic purpose:** one sentence from map-data-model.md

*Author goals: question framing from ctw-map-pamphlet.md (where present)*

---

## Sub-step N: <Name>

**User requirements**
- What the user must decide or supply — derived from "questions that must be answered" and entity attributes in map-data-model.md, framed by author goals from ctw-map-pamphlet.md.

**System requirements**
- What the system must compute, store, validate, or suggest — derived from entity relationships, pipeline outputs, statistics (high prevalence → surface inline; low prevalence → optional/advanced), and validity conditions.

---

## Step-level system requirements
- Requirements that span the whole activity rather than one sub-step.
```

**Derivation rules:**
- User requirements = "questions that must be answered" + entity attributes the user supplies + author goal framing
- System requirements = pipeline outputs, pre-population from parquet data, mirroring engine hooks, validation rules, statistics-driven prioritisation (surface inline if >50%, optional if <20%)
- Statistics drive UI priority, not feature inclusion — every mechanic in map-data-model.md is in scope

## Package READMEs

Every package under `src/pgm_map_studio/` gets a `README.md` covering: purpose, module listing, key concepts, and a usage example.
