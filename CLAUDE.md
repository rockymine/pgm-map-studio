# CLAUDE.md

## Where things stand — read this first

Mid **contract-first refactor** on branch `refactor/contract-first`: stabilize the data/API contract
(round-trip, typed models, categorization, filters) before the framework/UI migration and hosting.

**Read first, in order:**
- **`MEMORY.md`** (auto-memory at `/root/.claude/projects/-media-sf-repos/memory/`) — pinned
  decisions + session history across context resets (esp. `project_contract_phase1.md`).
- **`plans/refactor-plan.md`** — the ordered **status tracker** (Workstreams A–E) and its
  **"## Current focus"** section. The active driver. Keep it current as work lands.
- **`docs/README.md`** — the **documentation map**: what every doc is and its *kind* (spec /
  rationale / requirements / process). Start here when unsure where something belongs.
- **`docs/contracts/`** — the contract (the *what*): `data-model.md` (domain +
  API surface), `geometry.md` (coordinate/transform math + converters), `region-categorization.md`,
  `validation-invariants.md`, `frontend-stack.md` (D1 target stack).
  (Codec/service signatures live in the code — `pgm.serializer`/`deserializer` + `studio/services/`.)

Status (A round-trip complete, harness 350/350; B5 categorization, C3/C4 CRUD, B7 symmetry, B11
invariants done; ~920 py tests) lives in the plan + memory — **don't duplicate it here.**

## Environment & commands (easy to lose across sessions)

- **Python:** `/root/ctw-venv/bin/python` — the VirtualBox shared folder can't host a repo venv.
- **Tests:** `/root/ctw-venv/bin/python -m pytest` from repo root. JS: the shared folder can't host
  node_modules, so the runner lives at `/root/pgm-studio-tests/` — `cd /root/pgm-studio-tests &&
  node_modules/.bin/vitest run` (config points back at the shared-folder tests).
- **Round-trip harness (must stay green):** `/root/ctw-venv/bin/python tools/roundtrip_check.py`.
- **Dev server:** `./tools/studio-dev.sh restart|status|stop` (port 7892, http://localhost:7892;
  the `/run-studio` skill wraps it). Windows/Codex variant: `.\tools\studio-dev.ps1` (port 7893).
  Browser automation via the Chrome MCP tools.
- **Map corpus:** `/media/sf_repos/CommunityMaps/ctw` (199) + `/media/sf_repos/PublicMaps/ctw` (151)
  = 350 maps. Regenerate fresh `xml_data.json`: `tools/run_pipeline.py <maproot> <out> --xml-only
  --force` (current outputs at `/tmp/pipeline_out` + `/tmp/publicmaps_out`). Config:
  `~/.config/pgm-map-studio/config.json` (`maps_folder`, `output_folder=/tmp/pgm-studio-output`).
- **Git:** branch `refactor/contract-first`. Commit **only when the user explicitly asks**; end
  commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## The pgm round-trip core — do not break it

`src/pgm_map_studio/pgm/`: `parser` (map.xml → MapXml), `serializer`/`deserializer`
(MapXml ↔ `xml_data.json` dict), `xml_writer` (MapXml → map.xml). `regions.py`/`filters.py`/
`datatypes.py` are the typed domain. Enforced invariants (contract §13):
- Wools are **grouped by colour** with deterministic ids (wool = colour slug, monument =
  `colour-team`); capturing team lives on `monuments[].team`; owner is derived.
- `regions` and `filters` are **id-keyed dicts**, not lists.
- Compound `children` and transform `source_id` are **string-id references** into the flat
  registry — never inline dicts.
- Spawns reference their region by id; `never`/`always` are always-available built-in filters.

**Any change under `pgm/` (or a region/spawn/wool editor service): run the harness + `pytest`.**

## Implementation order — per activity (building an editor/sketch activity)

1. Read only the **activity-specific requirements** (`docs/requirements/<file>.md` or `docs/contracts/geometry.md`) + the relevant
   **contract** (`docs/contracts/*`).
2. **Check the tree** (`find src/`/`find tests/`) for what exists.
3. Read the **design doc**: `docs/contracts/ui-conventions.md` (UI), `plans/editor-vision.md` (editor),
   `docs/sketch-workflow.md` (sketch).
4. **Clarify unknowns** with `AskUserQuestion`; update the requirement/contract if scope changes.
5. **Write tests first** — pytest in `tests/` (mirroring `src/`) and/or Vitest, one test file per
   source file. For data-model work, validate against the corpus + harness.
6. **Verify** — `pytest`, the harness where relevant, the browser (`/run-studio`).
7. **Describe what was done and ask the user to test** before closing out.

## Geometry & canvas

Read `docs/contracts/geometry.md` before writing any **canvas, symmetry, coordinate, or shape/region**
code: the coordinate system (world space, +1 rule, axis orientation, bbox `{min_x,min_z,max_x,max_z}`),
symmetry formulas (mirror_x/z, diagonal d1/d2, rot_180/90, general rot_n + center-cell typology),
the shared canvas base, the `transform.js` interface, shape/region wire formats, and the **required
converters — each must have exactly one implementation** (with unit tests).

## UI — follow `docs/contracts/ui-conventions.md`; `/design` is the living visual reference

- **CSS split:** game-agnostic → `components.css`; editor/game-aware → `editor.css`; tokens →
  `tokens.css`; design-page helpers → `design.css`. **One owning file per selector** — never copy a
  component rule into `editor.css` to patch one activity.
- **Selectors:** classes for styling, IDs for JS refs only; never an ID selector for a shared layout
  pattern. No inline `style` in production templates (runtime data-driven values excepted).
- **Tokens:** never hardcode a colour/spacing/radius/transition that has a `tokens.css` variable.
- **Workspace layout:** `.workspace`, `.workspace-sidebar`, `.workspace-inspector`,
  `.workspace-scroll`, `.workspace-canvas`. Resizable panels get a `.sidebar-handle` with
  `data-resize-target`/`data-resize-side`; resize behaviour comes **only** from `shared/panel-resize.js`.
- **Components:** open `/design` first, copy the nearest production example. A missing pattern is
  added to the owning CSS file **and** a `/design` example in the same change (examples stay small,
  copyable, built from production classes — not a second implementation).
- **Buttons:** `.action-btn` + `--primary`/`--warn`/`--danger`, plus `.btn-remove`; layout modifiers
  (`--fill`/`--full`/`--push-end`) change placement only. **Badges:** `.badge` + `--success`/
  `--warning`/`--error`/`--neutral`/`--dim`. **Notifications:** only `#topbar-error`, `.toast`,
  `.canvas-hint`, `.panel-warning`.
- When adding an important UI contract (nesting rule, required attribute, forbidden pattern), add a
  test in `tests/studio/test_ui_structure.py`.

## Accessibility — WCAG AA

- Normal text ≥ 4.5:1 on its background; UI component boundaries (input borders, focus rings) ≥ 3:1.
  Decorative elements exempt.
- The five `tokens.css` text levels are the complete set — don't add a sixth dimmer level; floor is
  `--text-muted` (4.9:1). Never add a text colour below 4.5:1 on `--bg-panel`/`--bg-base`.
- Derived colour tokens via `color-mix()`/`oklch()` relative syntax (so they track their source),
  not hardcoded hex. Shadows belong in `--shadow-ring`/`--shadow-float`, never inline.

## Dev server — use the project scripts, not raw `fuser`/`Popen`

VM (port 7892, binds `0.0.0.0`): `./tools/studio-dev.sh restart`. PID/log in `.tmp/studio-dev-<port>`.

| Change | Action |
|---|---|
| Python (routes, services, models) | restart server + reload browser |
| Jinja2 templates (`templates/*.html`) | restart server + reload (Flask caches templates) |
| Static (`static/*.css`, `*.js`) | reload browser only |

Always hard-reload (`Ctrl+Shift+R`) after changes to bypass the cache.

## Tests

**Python:** pytest from repo root, one test file per source file mirroring `src/pgm_map_studio/`;
`test_<source>.py` / `test_<thing>_<condition>`. Synthetic fixtures only in `conftest.py` — no real
game files. Real-map integration/corpus tools go in `tools/` (e.g. `tools/roundtrip_check.py`), not
`tests/`; curated oracles under `tests/fixtures/`. **JS:** Vitest, tests in `tests/js/**/*.test.js`,
runner at `/root/pgm-studio-tests/` (see `docs/testing.md`).

## Requirements

Per-activity requirements live in `docs/requirements/` — editor workflow (`editor*.md`; note
`editor-filters.md` is **UNSTABLE**, superseded by the forthcoming
`docs/contracts/filter-region-wiring.md`) and sketch workflow (`sketch*.md`). Source docs:
`docs/map-data-model.md` + `docs/ctw-map-pamphlet.md` (editor), `docs/sketch-workflow.md` (sketch).
File format + derivation rules are documented in the requirements files themselves.

## Package READMEs

Every package under `src/pgm_map_studio/` gets a `README.md`: purpose, module listing, key concepts,
usage example. Keep it current when signatures change.
