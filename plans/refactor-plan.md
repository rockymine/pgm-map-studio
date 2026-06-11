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

- [~] **B1. Persisted `xml_data.json` typed** — `schemas/persisted.py` (pydantic `MapProject` +
  all entities), **validated against all 345 corpus maps** (`tools/validate_schemas.py`; caught the
  `"oo"` infinity-coord literal, inline-region spawn refs, `None` template coords → `Coord =
  float|str|None`). Generated into the TS contract; `tests/schemas/test_persisted.py`. *Remaining:
  the sketch `sketch.json` shape (overlaps B3), and wiring `studio` routes to return/validate via the
  models.* The view side (B4) already carries the canonical flat `{min_x..}`/`{cx,cz}` naming (C6);
  persisted keeps the on-disk nested `bounds_2d` (the C6 on-disk migration is separate).
- [x] **B2. Imported-map domain typed** — already realized by the `pgm` dataclasses (kept as
  dataclasses, not pydantic, per the B-note): `datatypes.py` (`MapXml` + 14 entities), `regions.py`
  (`Region` + 17 types), `filters.py` (`Filter` + 36 types). Verified complete + aligned across
  layers and **locked with a drift-guard** (`tests/pgm/test_codec_type_coverage.py`): the codec
  round-trips every region/filter type back to its own class (adding a type without wiring
  encode+decode now fails). One escape hatch left intentionally: `Region.bounds_2d: Optional[dict]`
  (derived cache; typed at the persisted boundary as `Bounds2d`). Wools stay **native-flat** in the
  domain (one per `<wool>`) and are grouped-by-colour with `monuments[].team` only at the persisted
  boundary (`serializer._encode_wools_grouped` ↔ `deserializer._decode_wools_entry`) — the canonical
  contract shape, owner-team derived.
- [x] **B3. Sketch `sketch.json` typed** — `schemas/sketch.py` (`SketchProject` + setup/layout/
  shape/island). **Cubic-Bézier model kept in lock-step with `geometry.js`/`sketch_export.py`:**
  `controls` = dict keyed by stringified vertex index, `{in?,out?}` handles; `in` aliased
  (Python keyword) and round-trips by-alias. `mirror_mode` is a strict `Literal`. Forced three TS-
  generator gains (alias emission, typed `Record<string,V>` — also retyped `regions`/`filters` —
  `Literal` unions). Validated against 26 real local sketches (`tools/validate_schemas.py`, incl. 7
  with bezier data); `tests/schemas/test_sketch.py`. *Remaining: a sketch **view** model is deferred
  until the sketch SPA needs one (the persisted shape is what `/api/sketch` returns today).*
- [x] **B4. `/regions/tree` view-model typed** — `schemas/view.py` (pydantic `RegionTreeNode`/
  `RegionGroup`/`RegionTreeResponse`, code-first match to `region_encoder`) + the **TS pipeline**:
  `tools/generate_ts_contract.py` → `frontend/src/contract.ts`, with a conformance test (encoder
  output validates) and a no-drift test (checked-in TS == generator). This is the schemas/TS
  foundation B1/B3 build on. *(Still: wire the route to validate/serialize via the model; fold C6
  naming; persisted shapes = B1.)*
- [ ] **B4a. Region tree = view, not model (de-clutter).**
  Today `/regions/tree` renders the **raw PGM compound tree** verbatim: anonymous
  `union`/`complement`/`negative` scaffolding, voidmatchers, wrappers, and every synthetic
  `__anon` child are shown as-is, so on structurally heavy maps (golden_drought_ii, hydrolock_ii)
  the tree is unreadable — it's the *model*, not a *view*. The fix is a **view-model that breaks
  the literal tree**: present regions grouped by their derived `category`/`roles` (B5 facets),
  promote the meaningful named regions, and **collapse or hide pure rule-wiring/synthetic compounds**
  (rule_container wrappers, anonymous intermediates) behind an "advanced/raw" toggle rather than
  inline. This is the UI face of the **persisted-vs-view model split** (B1) and the "individual
  region child" policy: the canonical model keeps the full compound graph for round-trip; the editor
  shows a curated, category-first tree. Touches `region_encoder.encode_region_tree` (or a new
  view-builder) + `region/region-tree.js` + the regions/objectives/build panels. *Needs: design.*
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
- [x] **B12. Python geometry module + unified symmetry transforms.** `pgm_map_studio/geometry.py`
  (pure-math leaf) owns `reflect_*` (moved from `pgm/regions.py`) + `rotate_*` (CCW, 90°-exact).
  `detection.py` + `sketch_export.py` (via `region_geometry.transform_geom`) consolidated onto it —
  detection's CW `rot_90`/`rot_270` swap fixed. JS `converters.js` keeps its necessary twin with a
  Vitest **parity** block. One implementation per converter (`geometry.md` §6).

## Workstream C — API stabilization (Phase 3)

- [ ] **C1.** Structured error envelope `{error:{code,message}}` across routes + `api.js`.
- [ ] **C2.** Documented request/response schema per route family (`api-schemas.md`).
- [x] **C3. Filters CRUD routes + service** (author-in-v1; reject-with-references on delete).
- [x] **C4. Apply-rules CRUD routes + service** (stable `rule_<n>` synthetic ids, dropped on XML export).
- [ ] **C5.** Wire region group/ungroup/restore/change-type into `api.js` (currently unwired).
- [ ] **C6.** Unify bbox/center naming to `{min_x,min_z,max_x,max_z}` + `{cx,cz}` at the API
  boundary; migrate `symmetry.json` `center_x/center_z` → `cx/cz`.
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
- [ ] **C10. Route consistency audit + CRUD conventions.** *Audited (autonomous session).*
  Inconsistencies to resolve: (1) **singular/plural** mixed — `/teams` + `/teams/:id` and
  `/wools` + `/wools/:id` (plural) vs `/regions` POST + `/region/:id` and `/spawns` POST +
  `/spawn/:region_id` (plural-create, singular-item); (2) **success envelope** mixed — most
  mutations return `{ok:true, ...result}`, spawns return bare `{ok:true}`, sketch PATCH `{ok:true}`,
  sketch GET/POST and config GET return raw data; (3) **error envelope** flat `{"error":"..."}`
  string (C1 fixes); (4) **REST vs RPC** mixed — collection POST for create, but action URLs for
  region ops (`/regions/group`, `/region/:id/change-type`, `/set-base-child`); (5) spawn is keyed
  by its linked `region_id`, not a spawn id. Standardize naming + envelopes; decide REST vs RPC for
  compound ops.
- [ ] **C11. Intelligent team/wool ID + colour defaults.** Teams currently default to id
  `new-team-n`, name `New Team`, chat colour blue. Instead pick the next unused colour and derive
  id `<colour>-team`, name `<Colour> Team` (mirrors the wool colour-as-key scheme). Cap at the
  16-colour Minecraft limit; realistic cap 8 (corpus max team count = 8). *Investigated:* the
  current defaults are set **client-side** in `panels/teams-panel.js:447` (`new-team[-n]` / `New
  Team` / `blue`), posting to `add_team` (which only requires an `id`). So this is a **frontend**
  change (next-unused-colour picker + id/name derivation), needing in-browser verification — **not**
  a backend-only knock-down;
- [ ] **C12. Wool availability validation.** A map is unplayable if no wool is obtainable.
  Implement the availability check (`docs/requirements/editor-objectives.md` Sub-step 3); PGM
  spawner / renewable / block-drop must be configurable as wool sources. *Needs: requirements pass.*
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

**Goal:** a ground-solid data/API frame so the frontend framework can be **switched (D1)** against
typed, stable shapes — not polished endpoints.

**Canonical shapes already settled** (describable without hand-waving — see
`docs/contracts/data-model.md` + `region-categorization.md`): **Region** (id-keyed, string-id
children, compound recursion, enforced round-trip core), **Filter** + **ApplyRule** (taxonomy
complete, wiring = region+event→filter+actions, synthetic ids), **Wool** (grouped-by-colour,
deterministic ids, derived owner). Four of the six core entities are locked.

### Sequencing (the order to run B/C — assessment 2026-06-10)

Model-defining work → **lock B1–B4** → API polish → features → D1. The blunt readiness test: *when
you can describe Region/Filter/ApplyRule/Symmetry/Wool/SketchShape without hand-waving, do B1–B4.*
**Symmetry is now described** (B7 model+contract locked 2026-06-10) — only **SketchShape** still
hand-waves on the modeling side.

1. **Close the symmetry model (the gate).** ✅ **B7 model+contract done** — center typology +
   diagonal-mirror class + axes model locked in contract §7 / `docs/contracts/geometry.md`; counterpart
   persistence corrected (all four reflections via native PGM mirror, only rot_90/270 bake). The
   diagonal/secondary-axis **canvas UI** is deferred to D-series (it doesn't gate B1–B4). B1's
   persisted/domain/view split and **B3** (sketch symmetry) are now unblocked on the symmetry side.
   ✅ **B11 design done** — `validation-invariants.md` catalogs the invariants (incl. rot_90/diagonal
   ⇒ square-cell + strict team/wool divisibility + rot_n) for the typed models to encode.
   ✅ **Filter↔region wiring design done** — `docs/contracts/filter-region-wiring.md` settles the
   wiring relationship + the v1 templates and confirms it adds **no new typed shape** (wiring =
   apply_rules + filters over regions, surfaced as `roles`). **The B1–B4 gate is now closed.**
2. **Lock B1–B4 (the typed frame).** B1 persisted/domain/view split · B2 imported-map domain · B3
   sketch · B4 `/regions/tree` view node. **Fold C6** (canonical bbox/center wire naming) and the
   **B4a** tree-as-view *design* in here — both are shape decisions the framework switch consumes,
   not polish.
3. **API polish (cheap once typed, pointless before).** C1 error envelope · C2 schemas · C5 wire
   region ops into `api.js` · C10 route consistency.
4. **Features + framework switch.** C8, **C9** wiring UI/templates, B6 undo/redo, C7/C11/C12, then
   **D1** (port the frontend onto the typed view-models + stable error contract), E1 hosting.

**Not B1–B4 gates** (despite appearances): **C8** is authoring convenience (doesn't change the
Region shape; does carry `change_region_type`-has-no-tests debt — do opportunistically) and **C9** is
UI/templates over the already-settled wiring shape. Both come *after* typing.

**The de-risker for D1 specifically:** B4 + B4a + C6 + C1 — the typed, consistently-named view-models
and the error contract the new frontend builds against. Treat those four as the real "frame."
