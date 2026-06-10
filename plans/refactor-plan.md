# Contract-First Refactor — Work Plan

Branch: `refactor/contract-first`. Spec: `docs/contracts/studio-domain-and-api-contract.md`
(the *what*); this file is the *ordered how/status*. Status legend: `[ ]` todo, `[~]` in progress,
`[x]` done. Keep this file current as work lands.

The phase order follows `plans/contract-first-migration-plan.md`, but the **round-trip repair**
is pulled ahead of typed models because the contract (§13) marks it a hard prerequisite and it is
the keystone broken behaviour.

---

## Workstream A — Round-trip repair (FIRST PRIORITY)

Make `xml_data.json ↔ MapXml ↔ map.xml` lossless again. Each item: fix + tests green.

- [x] **A1. Grouped-wool deserializer.** `deserializer.from_dict` ungroups grouped wool JSON into
  the flat `Wool` domain list (one `Wool` per monument); legacy flat format still handled. Fixed
  the 4 failing round-trip tests; added a 4-team multi-monument regression test (annealing_iv).
  Validated: full `map.xml → json → MapXml → map.xml` now passes 344/345 (only `segment`'s
  malformed-coord source defect fails).
- [x] **A2. Deterministic wool/monument IDs in serializer.** `_encode_wools_grouped` now derives
  IDs from content (wool = color slug; monument = `color-team`); no more per-serialize `uuid4`.
- [x] **A3. Region `source_id` resolution in `region_encoder`.** Mirror/translate (and compound
  string-id children) now resolve via `source_id`/registry in both the node builder and the
  geometry (`_dict_to_shapely`); `_encode_coords` emits `source_id`. Added a regression test.
  Validated: every transform with a non-empty `source_id` resolves (87/87 in registry); corpus
  transform polygons went 0% → 62% (remainder = empty-source_id, see A9).
- [x] **A4. Forbid inline-dict region children in `region_editor`.** `group_regions` now stores
  string-id children; `ungroup`/`remove_from_group`/`set_base_child` use the str|dict-tolerant
  `_child_id` (they previously crashed on the corpus's string-id unions). Added tests. Verified:
  an editor-grouped union now round-trips through deserialize → `to_xml` (was impossible before).
  Also generalized `ungroup` (decision): dissolves any compound type, one level only, with a
  `warning` when dissolving an ordered compound (complement/negative). Contract §14 updated.
- [x] **A5. Spawn-as-reference in serializer.** `_encode_spawn` now emits `region` as a string id
  into the flat registry (id-less anonymous regions fall back to inline). Consumers were already
  string-tolerant (`spawn_editor`, `teams-panel`). Also fixed a latent parser gap: a map with
  inline `<spawn><region>` but no `<regions>` block now exposes those regions in `data.regions`
  (added `region_parser.registry()`). Validated: 1175/1175 spawn regions serialize as resolved
  string refs, zero duplication (was 270 duplicated); round-trip faithful.
- [x] **A6. Align `wool_editor` IDs to the deterministic scheme** (consistency with A2). Wool id =
  colour slug, monument id = `colour-team` (matches the serializer); no more `uuid4`. Ids are
  re-keyed on colour/team rename (wool colour change cascades to monument ids), with a dup-colour
  guard added to `update_wool` and a dup-team guard to `update_monument`. Tests added.
- [x] **A7. Corpus round-trip harness.** `tools/roundtrip_check.py` runs the full round-trip over
  both suites with two checks per map: JSON idempotence (canonical, derived `bounds_2d` excluded)
  and an XML re-parse semantic compare. It immediately found a real round-trip bug — a named
  mirror/translate source with a single parent was referenced by name but never written top-level,
  so it vanished on re-parse; fixed in `xml_writer` (named sources forced top-level). Current
  baseline: **337 ok, 9 failed (tracked as A10), 1 excluded (`segment`, A8)**.
- [x] **A8. Robust coordinate parsing.** `parse_coord` now zeroes a malformed literal (e.g.
  `5.185.5`) with a warning instead of raising, so one source typo no longer fails the whole map.
  `segment` parses and round-trips; removed from the harness exclusions (now 341 ok, 9 A10, 0
  excluded). Tests added.
- [x] **A9. Populate `source_id` for inline transform sources.** Root cause was narrower than
  thought: a transform whose inline source is a `<region id="X"/>` reference parsed it as a
  `Reference` (blank id), leaving `source_id=""`. `_parse_mirror`/`_parse_translate` now resolve
  the reference's `ref_id` (helper `_source_ref_id`). Result: empty `source_id` 50 → 0 across the
  corpus; transform render resolution 62% → 96%. Test added.
- [x] **A10. XML-writer round-trip fidelity (9 maps).** Surfaced by A7. (a) A named region
  referenced from a *synthetic* region (apply-rule/spawn inline region) was emitted as a bare
  `<region id=.../>` reference but never written top-level (`_region_elem_inline` uses a single-
  region dict); now `_write_regions_block` forces any named child/source of a synthetic region to
  be top-level (fixed 8 maps). (b) `never`/`always` built-ins were seeded only when a `<filters>`
  block existed; the parser now always exposes the seeded filter registry (fixed kytriak_te).
  **Harness now 350 ok, 0 failed, 0 excluded.** Regression tests added.
- [ ] **A11. Sketch export → editor compatibility (bug).** Exported sketches don't reliably open
  in the editor — canvases show "Loading map…" / "No segment data", because the editor's required
  `layer_*.parquet` (notably `layer_segments.parquet`, and `layer.parquet`/top-surface) aren't
  produced by sketch export. Either have the export synthesise the layers the editor canvases need,
  or make the editor degrade gracefully when they're absent. *Needs: investigation (doable now).*
  *(From rockymine message §1.)*

## Workstream B — Typed data models (Phase 2 proper)

- [ ] **B1.** Separate persisted / domain / view models per the contract (§1).
- [ ] **B2.** Type the imported-map domain (regions, filters, rules) — build on `pgm.datatypes`.
- [ ] **B3.** Type sketch models.
- [ ] **B4.** Type the `/regions/tree` view-model node (§5) explicitly.
- [ ] **B5. Region categorization derivation.** Replace the thin `_compute_categories` with the
  two-facet model in `docs/contracts/region-categorization.md` (`category` + `roles`; build from
  void-structure; `rule_container`/`time_gated` roles; constrained compound recursion). Validates
  current 23% categorized → ~91%. Back it with a hand-verified ground-truth fixture
  (annealing_iv, vertex, acapulco, icecream_sandwiched_ii). Keep categories derived; keep
  `region_categories` as user-overrides only.
- [ ] **B6. Editor undo/redo (command model).** A real editor needs undo/redo of user actions.
  Pure create/delete inversion is insufficient — e.g. deleting a wool's monument keeps the wool
  but removes the monument (a PATCH today). Decide the model: command objects with inverse ops, or
  snapshot/restore (a `restore_region`-style snapshot already exists for regions). Must span
  region/team/spawn/wool/monument/filter/apply edits. *Needs: design decision + clarification.*
  *(rockymine §1 "Undo/Redo".)*
- [ ] **B7. Symmetry center typology + diagonal axis.** Model the center cell explicitly: a map
  center can fall on a `1x1`, `1x2`, `2x1`, or `2x2` block cell (x/z parity). Add diagonal (45°)
  rotation-axis support in the sketch tool so rot_90 layouts authored on a diagonal axis are
  expressible. (Note: a diagonal-axis rot_90 and an axis-aligned rot_90 yield the **same** detected
  symmetry class — order-4 rotation about the center; the axis angle changes only the authoring/
  mirror-line convention, not the symmetry. So detection needn't change; authoring does.) Touches
  symmetry datatypes + `cross-cutting.md` (model) and the sketch setup canvas (UI, see D-series).
  *Needs: design + clarification.* *(rockymine §1 "Symmetry Axis and Center Point".)*
- [ ] **B8. Shared geometry format / sketch–editor data-handling alignment.** The sketch tool edits
  in-memory (instant); the editor round-trips every change through JSON + backend validation
  (laggy). Confirm both share one geometry format (`cross-cutting.md` mandates a single
  `transform.js` + bbox object form) and align data-handling — e.g. optimistic in-memory edits with
  async persist/validate. *Needs: investigation (partly doable now) + design.* *(rockymine §1
  "Performance and implementation drift".)*
- [ ] **B9. Template-driven import scaffolding.** Optionally start from a known XML template
  (`docs/xml_template.xml`, Ruediger_LP's) instead of blank. On import/load, ask — or infer from
  symmetry + layer parquet — how many teams/wools the map has, then pre-scaffold teams/wools/regions
  so editing is directed. *Needs: design + clarification.* *(rockymine §1 "working off of xml
  templates".)*
- [ ] **B10. Map vs Sketch project identity.** Exported sketches aren't promoted to genuine "maps";
  the model doesn't cleanly distinguish a sketch project from an imported/real map project. Define
  both project types and the sketch→map promotion on export (pairs with A11's export-artifact bug).
  *Needs: data-model decision (contract §11 open Q16/Q17).* *(rockymine §1 "sketches … not promoted
  to 'maps'".)*
- [ ] **B11. Editing validation model / invariants.** Prevent invalid states: a wool needs ≥1 team;
  a monument needs its wool + team; a map needs ≥2 teams; rot_90 needs 4 teams; mirror supports 2+
  (creative edge cases, e.g. `ruedigers_pentawool`). Model invariants centrally; surface as inline
  guards (enforcement in C). *Needs: requirements pass + clarification.* *(rockymine §1 "Validation
  Model while editing".)*

## Workstream C — API stabilization (Phase 3)

- [ ] **C1.** Structured error envelope `{error:{code,message}}` across routes + `api.js`.
- [ ] **C2.** Documented request/response schema per route family (`api-schemas.md`).
- [ ] **C3.** Filters CRUD routes + service (author-in-v1).
- [ ] **C4.** Apply-rules CRUD routes + service, incl. stable synthetic rule ids.
- [ ] **C5.** Wire region group/ungroup/restore/change-type into `api.js` (currently unwired).
- [ ] **C6.** Unify bbox/center naming to `{min_x,min_z,max_x,max_z}` + `{cx,cz}` at the API
  boundary; migrate `symmetry.json` `center_x/center_z` → `cx/cz`.
- [ ] **C7.** CTW import-eligibility check (supported symmetric-CTW signal; flag AD/arcade/gimmick).
- [ ] **C8. Symmetric compound creation.** Creation is union-only today; negative/complement/
  intersect need the `group → change_region_type` dance, and `change_region_type` has **zero
  tests**. Add an optional `type` to `group_regions` (default `union`) to create any compound
  directly (set_base_child for complement ordering), and backfill `change_region_type` tests.
  Makes create symmetric with the now-generalized ungroup. (Authoring, not round-trip.)
- [ ] **C9. Filter↔region wiring + intelligent templates.** Routes/UI to attach filters to
  regions/unions, plus the tool *suggesting/questioning* filters from map setup. v1 must cover
  (a) wiring the positive build regions with the correct void/never filter in the build step
  (auto-group + apply, using `layer_y0.parquet`), and (b) apply-enter rules. Surface the most
  common corpus filter usages as "intelligent templates". Start from `docs/filter-use-cases.md`,
  extended across the full dataset; `docs/requirements/editor-filters.md` is **outdated** and needs
  rewriting. *Needs: corpus analysis (partly doable) + heavy clarification.* *(rockymine §1
  "Filters, Regions and their Relation".)*
- [ ] **C10. Route consistency audit + CRUD conventions.** Audit existing add/update/delete routes
  for consistent shapes, naming, and status codes so new features slot in cleanly (ties to C1
  envelope + C2 schemas). *Needs: audit (doable now).* *(rockymine §3 "Routes concern".)*
- [ ] **C11. Intelligent team/wool ID + colour defaults.** Teams currently default to id
  `new-team-n`, name `New Team`, chat colour blue. Instead pick the next unused colour and derive
  id `<colour>-team`, name `<Colour> Team` (mirrors the wool colour-as-key scheme). Cap at the
  16-colour Minecraft limit; realistic cap 8 (corpus max team count = 8). Low-effort, well-specified
  — **knock-down candidate, needs no input.** *(rockymine §1 "Intelligent ID and color defaults".)*
- [ ] **C12. Wool availability validation.** A map is unplayable if no wool is obtainable.
  Implement the availability check (`docs/requirements/editor-objectives.md` Sub-step 3); PGM
  spawner / renewable / block-drop must be configurable as wool sources. *Needs: requirements pass.*
  *(rockymine §1 "Wool existence validation".)*

## Workstream D — UI migration (Phase 4)

- [ ] **D1.** Only after A–C are stable. Port/replace frontend; keep HTML/CSS patterns.
- [ ] **D2. 2.5D/3D coordinate editing.** Positioning point/block (monuments) and cuboid Y-coords
  is impractical in 2D today. Extend the build-step `layer_segments.parquet` side-depth view into a
  3D/2.5D selection view, or integrate the `/map-studio` plugin to push WorldEdit selections
  directly into the tool. *Needs: design + (plugin) hosting work (E1).* *(rockymine §4.)*

## Workstream E — Hosting & deployment (Phase 5)

- [ ] **E1. Hosting + import pipeline.** The tool is to be hosted (easy to install/maintain) and is
  **not collaborative** — concurrent edits of the same map are isolated into independent per-session
  copies (single author per XML in practice; account for the edge case). The current tool already
  imports a map from an Overcast `//download` S3 zip link and opens it in the editor. Target: a Java
  plugin (`/map-studio`) that downloads the world, ships it to the server, and returns an edit link.
  The sketch→editor workflow stays separate and available. *Needs: stack selection + infra design
  (contract §0 explicitly defers auth/hosting).* *(rockymine §2 "Stack selection".)*

---

## Current focus

**Workstream A (A1–A10) is complete** — round-trip harness green (350/350). B6–B11, C9–C12, D2, E1
were added from rockymine's message (`docs/contracts/a-message-from-rockymine.md`) and mostly need
his clarification/design input.

**Autonomous session (rockymine away):** doing only what needs no input — (1) this task writeup;
(2) **A11** sketch-export→editor bug; (3) safe investigations that sharpen tasks (B8 shared
geometry, C10 route audit); possibly (4) **C11** team id/colour defaults (well-specified). Holding
all of B and the feature-heavy C/D/E items for rockymine.

**Knock-down candidates (no input needed):** A11 (bug), C10 (audit), C11 (defaults), C8 (symmetric
compound creation + `change_region_type` tests).
