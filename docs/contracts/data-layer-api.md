# Data-layer API reference (codec + editor services)

A reference snapshot of the **current** signatures around the `xml_data.json` data layer — the
PGM codec and the studio editor services — as an anchor for refactoring (B1–B4 model split, C1
error-envelope unification, C5 route wiring). **This is a map, not a contract**: when you change a
signature here, update this file. Last synced: 2026-06-10 (after C3/C4).

> The canonical *meaning* of the data lives in `studio-domain-and-api-contract.md` and
> `region-categorization.md`. This file is just the function/route surface.

## 1. PGM codec — `src/pgm_map_studio/pgm/`

Round-trip core: `map.xml → parser → MapXml → serializer → xml_data.json (dict)` and back via
`deserializer`; `MapXml → xml_writer → map.xml`. The dict is what every editor service mutates.

**Entry points**
- `serializer.to_dict(MapXml) -> dict` · `to_json(MapXml, indent=2) -> str` · `save(MapXml, path)`
- `deserializer.from_dict(dict) -> MapXml` · `from_json(str) -> MapXml` · `load(path) -> MapXml`

**Per-entity codec** (private `_encode_*` / `_decode_*`, paired & symmetric):
region · author · kit (+item/armor) · team · spawn · wools (grouped) · spawner (+item) · renewable ·
block_drop_rule (+item) · **apply_rule** · **filter**. Reuse these to validate editor payloads (decode
a payload dict → domain object → encode) instead of hand-rolling per-type checks.

**Dict shapes that matter for CRUD**
- `regions`: **id-keyed dict**; compound `children` and transform `source_id` are **string-id refs**.
- `filters`: **id-keyed dict**; `{id, type, …}`. Composite → `children:[id]`; single-child wrapper →
  `child:id`; `after`/`pulse` → `filter:id`; `blocks`/`region` → `region:id`. Known types enumerated
  in `_decode_filter` (mirrored in `filter_editor._KNOWN_TYPES`).
- `apply_rules`: **flat list**, no id in the PGM model. Event keys `enter/leave/block/block_place/
  block_break/block_physics/block_place_against/use/filter`; `region`; actions `kit/lend_kit/velocity/
  message`. Values may be a filter id, a **region used as a filter**, a builtin (`never`/`always`), or
  an **inline descriptor** (`deny(void)`, `all(a, b)`). The editor adds a synthetic `rule_<n>` `id`
  (see §3), dropped on XML export.

## 2. Editor services — `src/pgm_map_studio/studio/services/`

All follow the same shape: `fn(data: dict, …) -> dict` mutating the `xml_data.json` dict in place,
raising service-specific exceptions; the matching route loads/saves and maps exceptions to HTTP.

| service | functions | exceptions |
|---|---|---|
| `region_editor` | `create_region`, `group_regions`, `change_region_type`, `remove_from_group`, `set_base_child`, `ungroup_region`, `delete_region`, `restore_region`, `patch_region` | `RegionNotFound`/`RegionConflict`/`InvalidRegionPayload` (← `RegionEditorError`) |
| `team_editor` | `add_team`, `update_team`, `delete_team` | `TeamNotFound`/`TeamConflict`/`InvalidTeamPayload` |
| `spawn_editor` | `add_spawn_link`, `update_spawn_link`, `delete_spawn_link`, `set_observer_spawn`, `delete_observer_spawn` | `SpawnNotFound`/`SpawnConflict`/`InvalidSpawnPayload` |
| `wool_editor` | `add_wool`, `update_wool`, `delete_wool`, `add_monument`, `update_monument`, `delete_monument` | `WoolNotFound`/`InvalidWoolPayload` |
| `filter_editor` (C3) | `list_filters`, `create_filter`, `update_filter`, `delete_filter`; helpers `filter_references`, `filter_filter_refs` | `InvalidFilterPayload`/`FilterConflict`/`FilterNotFound`/`FilterInUse(references)` |
| `apply_rule_editor` (C4) | `list_apply_rules`, `create_apply_rule`, `update_apply_rule`, `delete_apply_rule`; helper `_ensure_rule_ids` | `InvalidApplyRulePayload`/`ApplyRuleNotFound` |
| `region_categorizer` (B5) | `derive_region_facets(data) -> {id:{category,roles}}`, `categorize_regions(data) -> {id:category}` | — |
| `xml_data` | `load_xml_data(name) -> (dict, Path)`, `save_xml_data(data, path)` | (Flask `abort` 400/404) |

Note the **inconsistency to unify later** (C-series): exception *names* differ per service and only
`region_editor` has a common base; routes map them ad-hoc to 400/409/404 with a flat
`{"error": str}` body (no structured `{error:{code,message}}` envelope anywhere yet — that's C1).

## 3. Synthetic apply-rule ids (C4)

`apply_rule_editor` assigns `rule_<n>` (n = 1 + max existing suffix) into the rule dict — an
**editor-only field persisted in `xml_data.json`, dropped on XML export** (`_decode_apply_rule`
ignores unknown keys; `_encode_apply_rule` never emits `id`). `_ensure_rule_ids(data)` backfills
id-less rules on first access; ids are stable and never reused. The on-disk corpus files carry no
ids, so the round-trip harness is unaffected.

## 4. Route surface (id-keyed CRUD)

Blueprints under `/api/map`, registered in `studio/__init__.py`. New in C3/C4:

- Filters: `GET /<name>/filters` · `POST /<name>/filters` · `PATCH /<name>/filter/<fid>` ·
  `DELETE /<name>/filter/<fid>` (409 + `references` when in use).
- Apply-rules: `GET /<name>/apply-rules` · `POST /<name>/apply-rules` ·
  `PATCH /<name>/apply-rule/<rule_id>` · `DELETE /<name>/apply-rule/<rule_id>`.

Existing families follow the same `/<name>/<collection>` + `/<name>/<entity>/<id>` convention
(`regions`, `teams`, `spawns`, plus `map_api` reads incl. `/regions` → `facets`, `/regions/tree`).
No `api.js` client methods or UI for filters/apply-rules yet (deferred to C9).
