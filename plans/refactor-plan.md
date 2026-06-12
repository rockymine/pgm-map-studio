# Contract-First Refactor — Work Plan

Branch: `refactor/contract-first`. Spec: `docs/contracts/data-model.md`
(the *what*); this file is the *ordered how/status*. Status legend: `[ ]` todo, `[~]` in progress,
`[x]` done. Keep this file current as work lands.

**Conventions:** add a new task under the right workstream (A–E). Open `[ ]` items stay full (they
spec the work); **collapse a task to its one-line subject once it's `[x]` done** — the detail lives
in git + the auto-memory, not here.

The **round-trip repair** is pulled ahead of typed models because the data model (§13) marks it a
hard prerequisite and it was the keystone broken behaviour.

---

## Workstream A — Round-trip repair (FIRST PRIORITY)

Make `xml_data.json ↔ MapXml ↔ map.xml` lossless again. Each item: fix + tests green.

- [x] **A1. Grouped-wool deserializer.**
- [x] **A2. Deterministic wool/monument IDs in serializer.**
- [x] **A3. Region `source_id` resolution in `region_encoder`.**
- [x] **A4. Forbid inline-dict region children in `region_editor`** (+ generalized `ungroup`).
- [x] **A5. Spawn-as-reference in serializer.**
- [x] **A6. Align `wool_editor` IDs to the deterministic scheme.**
- [x] **A7. Corpus round-trip harness** (`tools/roundtrip_check.py`).
- [x] **A8. Robust coordinate parsing** (flag-and-continue on malformed literals).
- [x] **A9. Populate `source_id` for inline transform sources.**
- [x] **A10. XML-writer round-trip fidelity** (harness 350/350).
- [x] **A11. Sketch export → editor compatibility (bug).**

## Workstream B — Typed data models (Phase 2 proper)

> **Placement decided** (`frontend-stack.md`): B1/B4 land in a new framework-independent
> **`src/pgm_map_studio/schemas/`** package (pydantic) — persisted + view shapes; domain (B2) stays
> in `pgm/` as dataclasses. TS is **generated** from the pydantic schemas (→ JSON Schema →
> `openapi-typescript`) into `frontend/`. Adds a `pydantic` dependency (boundary only). This is the
> D1 de-risker.

- [x] **B1. Persisted `xml_data.json` typed** — `schemas/persisted.py` (`MapProject`), corpus-validated.
- [x] **B2. Imported-map domain typed** — `pgm` dataclasses, codec drift-guarded.
- [x] **B3. Sketch `sketch.json` typed** — `schemas/sketch.py` (`SketchProject`), bezier-faithful.
- [x] **B4. `/regions/tree` view-model + TS pipeline** — `schemas/view.py` → generated `contract.ts`;
  routes wired through the schemas (GET serialize, write validate/reject-4xx).
- [~] **B4a. Region authoring surface (view, not tree).** **Design + backend split done** —
  `docs/contracts/region-authoring.md`; `region_encoder.encode_region_authoring` → `primitives`
  (leaf building blocks) / `composed` (structures + `member_ids` + apply-rule `wiring`), flat, per-step
  `category`; typed `RegionAuthoringResponse` (→ `contract.ts`), `GET /regions/authoring`,
  `api.fetchRegionsAuthoring`. Corpus-smoke 345/345; encoder + conformance + route tests. *Remaining
  (D1/React): the stacked split panels + context-menu/keyboard-shortcut/command layer (shared with B6).*
- [x] **B5. Region categorization derivation** (`region_categorizer.py`; two-facet model — see
  `docs/contracts/region-categorization.md`).
- [ ] **B6. Editor undo/redo (command model).** A real editor needs undo/redo of user actions.
  Pure create/delete inversion is insufficient — e.g. deleting a wool's monument keeps the wool
  but removes the monument (a PATCH today). Decide the model: command objects with inverse ops, or
  snapshot/restore (a `restore_region`-style snapshot already exists for regions). Must span
  region/team/spawn/wool/monument/filter/apply edits. *Needs: design decision + clarification.*
- [x] **B7. Symmetry center typology + diagonal axis (model + contract)** — center-cell typology,
  diagonal-mirror class, axes model, `rot_n`; see `data-model.md` §7 + `geometry.md`. *(Canvas UI for
  diagonal/secondary axes remains D-series.)*
- [ ] **B8. Sketch–editor data-handling alignment.** *Investigated (autonomous session):* the two
  tools **already share the geometry format** — both import `canvas/transform.js`,
  `shared/converters.js`, `canvas-helpers.js`, `shape-render.js` (bbox object form per
  `docs/contracts/geometry.md`). So the lag isn't a geometry-format divergence; it's the **edit/persistence
  model**: the editor PATCHes each change to the backend and awaits the response before updating,
  while the sketch mutates an in-memory shapes array and debounce-saves. Fix = give the editor an
  optimistic in-memory model with async persist/validate (don't block the canvas on the round-trip).
  *Needs: design (the diagnosis is settled).*
- [ ] **B9. Template-driven import scaffolding.** Optionally start from a known XML template
  (`docs/xml_template.xml`) instead of blank. On import/load, ask — or infer from
  symmetry + layer parquet — how many teams/wools the map has, then pre-scaffold teams/wools/regions
  so editing is directed. *Needs: design + clarification.*
- [ ] **B10. Map vs Sketch project identity.** Exported sketches aren't promoted to genuine "maps";
  the model doesn't cleanly distinguish a sketch project from an imported/real map project. Define
  both project types and the sketch→map promotion on export (pairs with A11's export-artifact bug).
  *Needs: data-model decision (contract §11 open Q16/Q17).*
- [x] **B11. Editing validation model / invariants (design pass)** — `docs/contracts/validation-invariants.md`.
  *(Enforcement is Workstream C; traversability analysis is its own future feature.)*
- [x] **B12. Python geometry module + unified symmetry transforms** — `geometry.py` (CCW, 90°-exact);
  detection/sketch consolidated; JS parity test. See `geometry.md` §6.

## Workstream C — API stabilization (Phase 3)

- [x] **C1. Structured error envelope** `{error:{code,message}}` — enforced centrally
  (`studio/errors.py` after_request + HTTPException handler, scoped to `/api/`); `api.js`
  `apiErrorMessage` extracts it. `tests/studio/test_error_envelope.py`.
- [x] **C2. API contract documented** — `docs/contracts/api-schemas.md` (envelopes, error codes,
  naming & REST-vs-RPC conventions, route-family index).
- [x] **C3. Filters CRUD routes + service** (author-in-v1; reject-with-references on delete).
- [x] **C4. Apply-rules CRUD routes + service** (stable `rule_<n>` synthetic ids, dropped on XML export).
- [x] **C5. Region ops wired into `api.js`** — `groupRegions`/`ungroupRegion`/`restoreRegion`/
  `changeRegionType`/`removeFromGroup`/`setBaseChild`/`createCounterpart` (activity UI buttons = D-series).
- [x] **C6. bbox/center wire naming unified** to `{min_x,min_z,max_x,max_z}` + `{cx,cz}` — symmetry
  center migrated `center_x/center_z`→`cx/cz` (hard cut).
- [ ] **C7.** CTW import-eligibility check (supported symmetric-CTW signal; flag AD/arcade/gimmick).
- [x] **C8. Symmetric compound creation** — `group_regions` takes `type` (union/complement/intersect/negative);
  `change_region_type` test-backfilled.
- [~] **C9. Filter↔region wiring + intelligent templates.** **Doc + backend done; UI (D-series)
  remaining.** Design: `docs/contracts/filter-region-wiring.md` (supersedes the unstable
  `editor-filters.md`). Backend: `studio/services/filter_wiring.py` + `routes/wiring.py` —
  `GET /wiring/suggestions` (scans spawns/wools/build facets, proposes wirings, suggest+confirm) and
  `POST /wiring/apply` (executes a template, composing C8 `group_regions` + C3 `create_filter` + C4
  `create_apply_rule`). All four v1 templates: spawn protection (`enter=only-team`), wool-room
  defense (`enter=not-owner`), wool-room edit (`block=not-owner`), build/void enforcement
  (group build → `negative` → `block_place=deny(void)`). `tests/studio/test_filter_wiring.py` (15).
  *Remaining: the suggest/confirm **UI** — D-series, builds on these routes.*
- [x] **C10. Route conventions standardized + documented** (`api-schemas.md`): success `{ok:true,...}` /
  GET raw resource; error envelope (C1); **item routes pluralized** (`/regions/:id`, `/spawns/:id` —
  Werkzeug resolves static `/regions/group` ahead of the dynamic item route); RPC action-URLs for
  compound region ops; spawn keyed by `region_id`.
- [x] **C11. Intelligent team ID + colour defaults** — "+ Add team" now derives the next unused
  colour (`game-colors.js::nextTeamColor`, priority red/blue/green/yellow…) → id `<colour>-team`,
  name `<Colour> Team`, colour set; falls back to `new-team` when all 16 are used. `panels/teams-panel.js`
  + `tests/js/game-colors.test.js`. Browser-verified (red→blue→green, persisted correctly).
- [~] **C12. Wool availability + detection (backend done).** `services/wool_sources.py` finds wool from
  **physical** sources (world layers — `block`/`chest`/Minecraft-`spawner` block, colour-decoded via
  `minecraft/wool.py`) **and** the **PGM `<spawner>`** module (`xml_data.spawners`, region-based) — the
  author-added delivery, matched by colour (room-independent; 152 corpus maps use it). Obtainable =
  a physical source in the room **or** a PGM spawner of that colour; neither → `error` — **except** a
  PGM **dye** (`ink sack`) spawner (different damage scale, `minecraft/wool.py::DYE_DAMAGE_TO_COLOR`)
  flags the **sheep/dye** mechanic: still not auto-verifiable (`obtainable=False`) but a soft `warning`,
  not an error (sheep_ctw). Three typed routes:
  **POST `/wool-sources`** (what wool is in a drawn rectangle — colour + type + count + positions),
  **GET `/wool-availability`** (per declared wool: `error` if its room is unsourced, `info` if
  one-time-only, else `ok`; `repeatable` = spawner or renewable block), **GET `/wool-suggestions`**
  (colours found but not declared). `BuildabilityResponse`-style typed schemas → `contract.ts` +
  `api.fetch{WoolSourcesInRegion,WoolAvailability,WoolSuggestions}`. Hermetic tests + corpus oracle
  (`tools/gen_wool_oracle.py`; outback blocks / icecream chests / curly_wools spawner+red-error).
  *Next: the objectives-step UI (draw→query, suggestion prompts, availability badges) — D-series.*
- [~] **C13. Editor symmetry-aware authoring (source → derived counterparts).** **Region
  counterparts done (backend); other entity types + UI remaining.** `studio/services/symmetry_authoring.py`
  + `POST /region/:id/counterpart` (in `routes/regions.py`): given a source region + mode + center
  (falls back to `symmetry.json`), creates the counterpart per `data-model.md` §7 — reflections
  (`mirror_x/z/d1/d2`) as a native PGM `mirror`; `rot_180` as two ⟂ mirrors; `rot_90` **baked** to a
  concrete primitive via `geometry.rotate_*`. n-fold `rot_n` excluded (out of scope). Verified
  editor-created mirrors round-trip to `<mirror>` XML. `tests/studio/test_symmetry_authoring.py` (12).
  **Polygon-level equivalence** (`studio/services/region_geometry.py`: `regions_equivalent` /
  `is_counterpart`, IoU via `_dict_to_shapely`) validates counterparts against real geometry —
  corpus-oracle test on outback (rot_180 + ⟂ mirrors) + annealing (rot_90 orbit) all exact
  (`test_region_geometry.py`, 16). Ready to power C13 **dedup** + the B11/Regions **symmetry-violation
  review**. *Remaining: counterparts for filters/apply-rules/objectives/spawns + the map-level relation
  index + dedup wiring into create_counterpart + the canvas accept/reject UI (D-series); rot_90 bake of
  compound sources.*
- [~] **C14. Build-area buildability preview (map-correctness).** Show where players can/can't build.
  Buildability = region geometry × the **Y=0 layer** × block apply-rules (last-wins): `never`,
  `deny(void)`/`not(void)` (void = no block at Y=0), **region-as-filter gate** (build only *inside* a
  region — e.g. vertex `playable-area`), and **global** (region-less) rules; clipped to the map bbox
  (void/negatives are unbounded). **Done:** `tools/buildability_preview.py` — visual-debug PNG,
  validated on outback (void+positive), golden_drought_ii (partial void moats + carved bridging paths),
  vertex (region-gate, no void) — the three authoring approaches. **Service + route done:**
  `services/buildability.py` (`compute_buildability`, shared by the tool) + typed `BuildabilityResponse`
  (→ `contract.ts`, `api.fetchBuildability`) + `GET /buildability` (per-column verdict grid). Keeps the
  **4-class story** (buildable/never/void_denied/restricted) with canonical `CLASS_COLORS` surfaced in
  the payload, so the UI legend reads identically. Hermetic tests + corpus oracle
  (`tools/gen_buildability_oracle.py`, `tests/fixtures/buildability/`). *Next: the live canvas overlay
  (D-series UI).*

## Workstream D — UI migration (Phase 4)

- [ ] **D1.** Only after A–C are stable. Port/replace frontend; keep HTML/CSS patterns. **Target
  stack decided** in `docs/contracts/frontend-stack.md`: React + TypeScript + Vite (SPA)
  against the *existing* Flask API — keep all Python; not Next.js; not a full-stack rewrite; port
  incrementally per activity. The typed TS contract comes from B1–B4 (the D1 de-risker, below).
- [ ] **D2. 2.5D/3D coordinate editing.** Positioning point/block (monuments) and cuboid Y-coords
  is impractical in 2D today. Extend the build-step `layer_segments.parquet` side-depth view into a
  3D/2.5D selection view, or integrate the `/map-studio` plugin to push WorldEdit selections
  directly into the tool. *Needs: design + (plugin) hosting work (E1).*

## Workstream E — Hosting & deployment (Phase 5)

- [ ] **E1. Hosting + import pipeline.** The tool is to be hosted (easy to install/maintain) and is
  **not collaborative** — concurrent edits of the same map are isolated into independent per-session
  copies (single author per XML in practice; account for the edge case). The current tool already
  imports a map from an Overcast `//download` S3 zip link and opens it in the editor. Target: a Java
  plugin (`/map-studio`) that downloads the world, ships it to the server, and returns an edit link.
  The sketch→editor workflow stays separate and available. *Needs: stack selection + infra design
  (contract §0 explicitly defers auth/hosting).*

---

## Current focus

The typed data/API frame is locked (B1–B6 done above). What's left is the **frontend switch (D1)**
and the work that orbits it. The organising call: **don't sink UI into the dying Jinja/vanilla stack —
D1 rebuilds it in React.** So the buckets below are ordered by that, not by workstream. Target stack
+ migration strategy: `docs/contracts/frontend-stack.md`.

**① Shape D1, then run it.**
- **B4a — region authoring surface.** **Design done** (`region-authoring.md`): split view-model
  (primitives / composed / raw) + per-activity building blocks + group→engine-wires loop. Next:
  the `region_encoder` split is a backend change to do **now** (survives D1); the stacked panels +
  context-menu/shortcut/command UI build in React.
- **D1 — the switch (headline).** Port to a **React + TypeScript + Vite** SPA against the *existing*
  Flask API + generated `contract.ts`, activity by activity, shared TS canvas/geometry layer first.
  Old Jinja + new React coexist during the port. See `frontend-stack.md` (decision record + migration
  steps + the kickoff decisions: state layer, routing, styling).

**② Fold into D1 — UI over already-settled backends (building it now is throwaway).**
- **C9** filter↔region wiring UI — backend + routes done; only the suggest/confirm UI remains.
- **C13** symmetry-authoring UI (accept/reject counterparts) + counterparts for the non-region
  entities — region counterparts + equivalence done.
- **B6** undo/redo — the *command-model decision* can precede D1; the UI is React.
- **B8** sketch↔editor alignment — diagnosis settled (give the editor an optimistic in-memory model);
  lands naturally in the React rewrite.

**③ Backend/model features — independent of D1, not rebuilt by it (do anytime).**
- **B10** map-vs-sketch project identity (data-model decision; pairs with the export-artifact bug).
- **C7** CTW import-eligibility check · **C12** wool-availability validation (backend logic + tests).
- **B9** template-driven import scaffolding (pre-scaffold teams/wools from symmetry + layer).

**④ Post-D1 / hosting.**
- **D2** 2.5D/3D coordinate editing (Y-coords / monuments) · **E1** hosting + import pipeline.
