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

## Workstream B — Typed data models (Phase 2 proper)

- [ ] **B1.** Separate persisted / domain / view models per the contract (§1).
- [ ] **B2.** Type the imported-map domain (regions, filters, rules) — build on `pgm.datatypes`.
- [ ] **B3.** Type sketch models.
- [ ] **B4.** Type the `/regions/tree` view-model node (§5) explicitly.

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

## Workstream D — UI migration (Phase 4)

- [ ] **D1.** Only after A–C are stable. Port/replace frontend; keep HTML/CSS patterns.

---

## Current focus

**A1 → A2** (grouped-wool round-trip + stable IDs). A3–A5 are the remaining round-trip bugs the
contract enumerated; do them before B (typed models build on a correct round-trip).
