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
- [ ] **A6. Align `wool_editor` IDs to the deterministic scheme** (consistency with A2).
- [ ] **A7. Corpus round-trip harness.** Tool/test that runs full `map.xml → json → map.xml`
  across CommunityMaps + PublicMaps and reports diffs (excluding known out-of-spec maps like
  `segment`'s malformed coord, arcade/AD maps).
- [ ] **A8. Robust coordinate parsing.** `parse_coord` hard-crashes a whole map on a malformed
  value (`segment/map.xml:79` `5.185.5`). Flag-and-continue (skip/zero the bad coord, record a
  warning) so one source typo doesn't lose the map. 1/345 today.
- [ ] **A9. Populate `source_id` for inline-anonymous transform sources.** 50/137 corpus
  mirror/translate regions persist an empty `source_id` (their source was an inline anonymous
  region). The parser should set `source_id` to that source's synthetic registry id so the
  transform resolves. Encoder side is already correct (A3).

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
