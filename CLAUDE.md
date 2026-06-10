# CLAUDE.md

## Where things stand — read this first

This project is mid **contract-first refactor** on branch `refactor/contract-first`. The goal of
the refactor is to stabilize the data/API contract (round-trip, typed models, categorization,
filters) before the larger framework/UI migration and hosting.

**Source of truth for the work:**
- `plans/refactor-plan.md` — the ordered **status tracker** (Workstreams A–E). Keep it current as
  work lands; each task is tagged with what it needs (none / audit / clarification).
- `docs/contracts/` — the **contract** (the *what*):
  - `studio-domain-and-api-contract.md` — verified domain model + API surface (grounded in the real
    code + a 350-map corpus, not idealized).
  - `region-categorization.md` — the two-facet region model (`category` + `roles`).
  - `refactor-constraints-and-pitfalls.md` — strategy/risk notes.
  - `plans/contract-first-migration-plan.md` — the original phased intent.
- Auto-memory at `/root/.claude/projects/-media-sf-repos/memory/` (esp. `project_contract_phase1.md`)
  records every decision and the session history across context resets — read `MEMORY.md` first.

**Done — Workstream A (round-trip repair):** `xml_data.json ↔ MapXml ↔ map.xml` is lossless again.
The corpus harness `tools/roundtrip_check.py` is **green (350/350)**. The sketch-export→editor bug
(A11) is fixed and browser-verified. Full Python suite passes (~893 tests).

**Done — B5 (region categorization derivation):** `studio/services/region_categorizer.py`
implements the two-facet model (`docs/contracts/region-categorization.md`): `category` ∈ {spawn,
observer_spawn, wool_room, monument, wool_spawner, build, mechanic, other} + orthogonal `roles`
(`rule_container`, `rule_group`, `time_gated`, plus `<event>=<filter_id>` wiring). Build is derived
from void-enforcement *structure*, never naming. Other signals: spawner regions are wool only when
the spawner dispenses wool (else `mechanic`); the author `apply message` text and the break-floor-
material+deny-place pattern classify spawn/wool protection zones; renewables/velocity/kit →
`mechanic`; a region used as a `block_place` filter → `build` (permissive placement). Reproduces the
rockymine-verified `annealing_iv` oracle exactly (~23% → ~80% categorized corpus-wide). Tests in `tests/studio/test_region_categorizer.py`;
fixtures + vendored inputs under `tests/fixtures/region_categories/` (all four — annealing_iv,
acapulco, icecream, vertex — **rockymine-verified**). Categories stay **derived**;
`region_categories` is a **user-override store only**.

**Done — C3/C4 (filters & apply-rules CRUD):** `studio/services/filter_editor.py` +
`apply_rule_editor.py` + routes. Reject-with-references on delete; stable `rule_<n>` synthetic ids
(dropped on XML export). Backend only. The codec + editor-service signatures are captured in
`docs/contracts/data-layer-api.md`; the filter *vocabulary* + region-*geometry* matrices (what
attaches where) in `docs/filter-use-cases.md` (Appendix). All four categorization fixtures are now
rockymine-verified.

**Current focus & sequencing — read `plans/refactor-plan.md` "## Current focus" first.** The goal is
a solid typed frame to switch the framework (D1). Four core shapes are settled (Region, Filter,
ApplyRule, Wool — see `data-layer-api.md`). The **one model-defining gate left is Symmetry**: do
**B7** (center typology + diagonal axis) and lock the contract's symmetry section (how counterparts
persist) — plus B11-as-design and finishing `filter-region-wiring.md` — **before** locking the typed
models **B1–B4** (fold C6 + B4a-design in). Then API polish (C1/C2/C5/C10), then features + D1.
**C8/C9 are not B1–B4 gates** (authoring/UX over already-settled shapes). The readiness test: when
Symmetry and SketchShape are describable without hand-waving, do B1–B4.

**Other queued work** (in `plans/refactor-plan.md`): B6–B11, C1–C12, D1–D2, E1. Several need
rockymine's design input (tagged). `docs/requirements/editor-filters.md` is flagged **unstable** —
the filter↔region wiring design will live in a new `docs/contracts/filter-region-wiring.md` (C9).

## Environment & commands (easy to lose across sessions)

- **Python:** `/root/ctw-venv/bin/python` — the VirtualBox shared folder can't host a repo venv.
- **Tests:** `/root/ctw-venv/bin/python -m pytest` from repo root. JS: `cd /root/pgm-studio-tests &&
  node_modules/.bin/vitest run`.
- **Round-trip harness (must stay green):** `/root/ctw-venv/bin/python tools/roundtrip_check.py`.
- **Dev server:** `./tools/studio-dev.sh restart|status|stop` (port 7892, http://localhost:7892).
  The `/run-studio` skill wraps it. Browser automation via the Chrome MCP tools.
- **Map corpus:** `/media/sf_repos/CommunityMaps/ctw` (199) + `/media/sf_repos/PublicMaps/ctw` (151)
  = 350 maps. Regenerate fresh `xml_data.json`:
  `tools/run_pipeline.py <maproot> <out> --xml-only --force` (fast; outputs currently at
  `/tmp/pipeline_out` + `/tmp/publicmaps_out`). Config (`maps_folder`,
  `output_folder=/tmp/pgm-studio-output`): `~/.config/pgm-map-studio/config.json`.
- **Git:** branch `refactor/contract-first`. Commit **only when the user explicitly asks**; end
  commit messages with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` line.

## The pgm round-trip core — do not break it

`src/pgm_map_studio/pgm/`: `parser` (map.xml → MapXml), `serializer`/`deserializer`
(MapXml ↔ `xml_data.json` dict), `xml_writer` (MapXml → map.xml). `regions.py` / `filters.py` /
`datatypes.py` are the typed domain. Invariants now enforced (see contract §13):
- Wools are **grouped by colour** with deterministic ids (wool = colour slug, monument =
  `colour-team`); capturing team lives on `monuments[].team`; owner is derived.
- `regions` and `filters` are **id-keyed dicts**, not lists.
- Compound `children` and transform `source_id` are **string-id references** into the flat
  registry — never inline dicts.
- Spawns reference their region by id; `never`/`always` are always-available built-in filters.

Any change under `pgm/` (or to region/spawn/wool editor services): run the harness + `pytest`.

## Implementation order — per activity (when building an editor/sketch activity)

1. **Read the requirements** (`docs/requirements/<file>.md` or `docs/cross-cutting.md`) and the
   relevant **contract** (`docs/contracts/*`).
2. **Check the tree** — `find src/` / `find tests/` — to know what exists.
3. **Read the design doc** — `docs/ui-conventions.md` (UI); `plans/editor-vision.md` (editor);
   `docs/sketch-workflow.md` (sketch).
4. **Clarify unknowns** with `AskUserQuestion`; update the requirement/contract if scope changes.
5. **Write tests first** — pytest in `tests/` (mirroring `src/`) and/or Vitest; one test file per
   source file. For data-model work, validate against the corpus + harness.
6. **Follow the rest of this CLAUDE.md** (cross-cutting, UI, dev server, package READMEs).
7. **Verify** — `pytest`, the harness where relevant, and the browser (`/run-studio`).
8. **Describe what was done and ask the user to test** before closing it out.

`plans/implementation-plan.md` is the original Phase 0→1→2 activity plan; the **active driver is now
`plans/refactor-plan.md`**.

---

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

- **CSS file split:** game-agnostic patterns → `components.css`. Editor/game-aware patterns → `editor.css`. Tokens → `tokens.css`. Design-page helpers → `design.css`. One owning file per selector — never copy a component rule into `editor.css` to patch one activity.
- **Selectors:** use classes for styling, IDs for JS references only. Never use an ID selector to express a shared layout pattern. Production templates contain no inline `style` attributes (runtime data-driven values excepted).
- **Tokens:** never hardcode a color, spacing, radius, or transition that has a CSS variable in `tokens.css`.
- **Workspace layout:** use `.workspace`, `.workspace-sidebar`, `.workspace-inspector`, `.workspace-scroll`, `.workspace-canvas`. Resizable panels get an adjacent `.sidebar-handle` with `data-resize-target` and `data-resize-side` attributes. Resize behavior comes exclusively from `shared/panel-resize.js` — do not write local drag code.
- **Components:** open `/design` first. Copy the nearest production example structure. If a needed pattern is absent, add it to the owning CSS file and add a `/design` example in the same change. Do not use `/design` as a second implementation — examples must stay small, copyable fragments built from production classes.
- **Buttons:** five variants — `.action-btn`, `--primary`, `--warn`, `--danger`, `.btn-remove`. Layout modifiers (`--fill`, `--full`, `--push-end`) change placement only, not visual meaning.
- **Badges:** one system — `.badge` with `--success`, `--warning`, `--error`, `--neutral`, `--dim`.
- **Notifications:** four types only — `#topbar-error`, `.toast`, `.canvas-hint`, `.panel-warning`.
- **Structural tests:** when adding an important UI contract (nesting rule, required attribute, forbidden pattern), add a test in `tests/studio/test_ui_structure.py` so future work cannot silently break it.

The `/design` page (start the app, navigate to `/design`) is the living visual reference. Full contracts in `docs/ui-conventions.md` and `plans/ui-system-consolidation.md`.

## Accessibility

All text and interactive elements must meet **WCAG AA** contrast minimums:

- **Normal text** (< 18pt / 14pt bold, i.e. all sizes in this app): 4.5:1 against its background.
- **UI component boundaries** (input borders, focus rings): 3:1 against adjacent colour.
- Decorative elements (dividers, inactive canvas shapes) are exempt.

**Token rules:**

- Never introduce a new text colour token below 4.5:1 on `--bg-panel` or `--bg-base`. Verify with the formula `(lighter + 0.05) / (darker + 0.05)` or a contrast checker before committing.
- The five text levels in `tokens.css` are the complete set — do not add a sixth dimmer level to express "quiet" text. Use `--text-muted` (4.9:1) as the floor.
- Derived colour tokens (opacity variants, darkened strokes, tinted surfaces) must be expressed with `color-mix()` or `oklch()` relative syntax rather than hardcoded hex. This ensures they track their source token if the source changes.
- Shadow values belong in `--shadow-ring` / `--shadow-float` — do not write inline `box-shadow` values in component rules.

## Dev server

Use the project scripts — not raw `fuser`/`Popen` one-liners.

**VirtualBox / Claude (Linux VM) — port 7892, binds to `0.0.0.0`:**
```bash
./tools/studio-dev.sh restart   # or start / stop / status
```
Reachable from Windows host at `http://localhost:7892/`. The `/run-studio` skill wraps this script.

**Windows / Codex local — port 7893, binds to `127.0.0.1`:**
```powershell
.\tools\studio-dev.ps1 restart   # or start / stop / status
```
Reachable at `http://127.0.0.1:7893/`. No firewall prompt needed.

PID and log files go to `.tmp/studio-dev-<port>.pid` / `.tmp/studio-dev-<port>.log`.

**When to restart vs when to just reload:**

| Change type | Action needed |
|---|---|
| Python source (routes, services, models) | Restart server + reload browser |
| Jinja2 templates (`templates/*.html`) | Restart server + reload browser (Flask caches templates in memory at first load) |
| Static files (`static/*.css`, `static/*.js`) | Reload browser only — no restart needed |

Always use `Ctrl+Shift+R` (hard reload) in the browser after any change to bypass the browser cache. A normal reload may serve stale CSS or JS.

## Tests

**Python:** pytest (`pytest` from project root). One test file per source file, mirroring `src/pgm_map_studio/` under `tests/`. File naming: `test_<source_filename>.py`. Function naming: `test_<thing>_<condition>`. Fixtures in `conftest.py` — synthetic data only, no real game files. Integration/corpus tools using real maps go in `tools/` (e.g. `tools/roundtrip_check.py`), not `tests/`. Curated corpus oracles (e.g. categorization fixtures) live under `tests/fixtures/`.

**JavaScript:** Vitest. Test files in `tests/js/**/*.test.js`. The VirtualBox shared folder cannot host node_modules, so the runner lives locally:
- Runner: `/root/pgm-studio-tests/` (package.json + node_modules installed there)
- Config: `/root/pgm-studio-tests/vitest.config.js` (points to shared folder tests)
- Run: `cd /root/pgm-studio-tests && node_modules/.bin/vitest run`

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
- `editor-filters.md` — rule review and advanced mechanics — **UNSTABLE/OUTDATED**; see C9 / the
  forthcoming `docs/contracts/filter-region-wiring.md`
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

## Reference Project

`/media/sf_repos/CTWAnalysisWithClaudeCode` contains the older implementation this project was ported from. Code may be copied from it **with caution** — it uses different naming conventions and includes analysis/match modules that are not relevant here.

**Path:** `/media/sf_repos/CTWAnalysisWithClaudeCode`

**Run the old viewer (port 7891):**
```bash
cd /media/sf_repos/CTWAnalysisWithClaudeCode && /root/.venv-ctw/bin/python ctw.py viewer
```
Kill with `fuser -k 7891/tcp`.

**What is useful to copy from:**

| Source path | Purpose | Notes |
|---|---|---|
| `map_viewer/static/shared/tool-manager.js` | ToolManager class | Direct port candidate |
| `map_viewer/static/canvas/concept-canvas.js` | ConceptCanvas drawing logic | Port carefully — different bbox interface |
| `map_viewer/static/shared/transform.js` | Old transform utilities | Already ported; uses array bbox `[minX,maxX,minZ,maxZ]` — convert to object form |
| `layout_analysis/region_reader.py` | Anvil `.mca` reader | Clean, well-contained |
| `island_analysis/detection.py` | Connected-component island detection | Solid logic |
| `island_analysis/polygon.py` | Shapely polygon simplification | Port as-is |
| `symmetry_analysis/builder.py` | Symmetry detection | Well-contained |
| `xml_analysis/builder.py` | PGM XML parser | Core parser — already ported to `pgm/` |
| `map_viewer/services/*_editor.py` | Region/team/spawn/wool edit managers | Useful reference for editor services |

**What to ignore:**
- `match_analysis/` — DuckDB match event processing, not relevant
- `ingestion/` — remote API fetcher, not relevant
- `island_analysis/profile*.py`, `statistics.py` — research/archive
- `scripts/` — one-time migration scripts
- Any `.venv` inside the repo — cannot execute from shared folder (VirtualBox protocol error)

**Key differences from this project:**
- Uses `map_data.json` / `map_context.json` — this project uses `xml_data.json` / `islands.json` / `symmetry.json`
- Bounding boxes are arrays `[minX, maxX, minZ, maxZ]` — this project uses `{min_x, max_x, min_z, max_z}` objects
- Has `#primaryId` and skeleton analysis code not present here
- `transform.js` exports are compatible but bbox interface differs — always convert when porting

Full file classification in `plans/00_assessment.md`.
