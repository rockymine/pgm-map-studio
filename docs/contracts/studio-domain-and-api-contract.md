# Studio Domain And API Contract

This is the **verified** contract for the studio backend/frontend boundary. It supersedes the
first-pass draft. Every structural claim here was checked against the live `pgm` datamodel
(`src/pgm_map_studio/pgm/`), the service layer, `api.js`, and a corpus of **345 real maps**
(197 `CommunityMaps/ctw` + 148 `PublicMaps/ctw`).

Where the original draft was wrong, the correction is marked **[corrected]**. Decisions taken
with the author during the Phase 1 contract pass (2026-06-10) are marked **[decision]**.

The companion document `refactor-constraints-and-pitfalls.md` holds strategy/risk notes.
Coordinate rules are owned by `docs/cross-cutting.md` (authoritative) and only summarized here.

---

## 0. Phase 1 verified findings (read first)

These are the load-bearing facts the rest of the contract depends on.

1. **The JSON↔datamodel round-trip is currently broken for wools.** `serializer.to_dict`
   emits *grouped* wools; `deserializer.from_dict` reads *flat* (`d['monument']`) → `KeyError`.
   Four tests in `tests/pgm/test_deserializer.py` fail today. Only the in-memory
   `map.xml → MapXml → map.xml` path works. It is latent because **no imported-map → XML export
   route is wired** (`to_xml`/`deserializer.load` are used only in tests). It **must** be fixed
   before any XML-export feature ships. **[corrected]** (draft assumed round-trip was solved.)

2. **`xml_data.json` is the persistence truth for imported maps**, written by the pipeline XML
   step (`pgm.parser` → `pgm.serializer.save`). `sketch.json` is the sketch truth. Regenerate
   either suite's XML quickly with `tools/run_pipeline.py <root> <out> --xml-only --force`.

3. **The flat registry already exists.** The parser lifts every region — named *and* inline
   anonymous — into one flat `regions` dict keyed by id; anonymous regions get stable synthetic
   ids `"{parent_id}__anon_{index}"` (and `"__apply_{i}"` for inline apply-rule regions).
   Across 345 maps, compound children are **always string-id references, never inline dicts**.

4. The contract covers **all** persisted collections, including ones the draft omitted:
   `kits`, `spawners`, `renewables`, `block_drop_rules`, the full `filters` registry, and
   `apply_rules`. **[corrected]**

---

## 1. Persistence boundaries

| Layer | Files | Role |
|---|---|---|
| Global studio config | `~/.config/pgm-map-studio/config.json` | `maps_folder`, `output_folder` |
| Per-map pipeline config | `<output>/<slug>/` map config | scan layer, exclusions |
| **Imported-map truth** | `<output>/<slug>/xml_data.json` | author-editable map state (round-trips to XML) |
| Analysis outputs (derived) | `islands.json`, `symmetry.json`, `layer*.parquet` | regenerable |
| **Sketch truth** | `~/.config/pgm-map-studio/sketches/<id>/sketch.json` | one file per sketch session |

Three model layers apply to every concept and must not be conflated:

- **Persistence model** — what is on disk (`xml_data.json` entry, `sketch.json` entry).
- **Domain model** — the typed object (`pgm.datatypes` / `pgm.regions` / `pgm.filters`).
- **View model** — a transport shape for one UI workflow (`/regions/tree`, pixel payloads).

---

## 2. Coordinate & naming contract  **[decision: unify]**

Canonical, per `docs/cross-cutting.md`:

- **Bounding box** is the flat object `{ min_x, min_z, max_x, max_z }`, where `max_*` are
  **extent bounds** (+1 over the highest block index, applied exactly once). This is the wire
  and view-model shape everywhere.
- **Symmetry / mirror center** is `{ cx, cz }`.

Outliers to migrate onto the canonical shape:

- Persisted region `bounds_2d` uses nested `{min:{x,z},max:{x,z}}`. It is a **derived** PGM-parser
  artifact; the API normalizes it to flat `{min_x,min_z,max_x,max_z}`. It is never canonical
  author input.
- `symmetry.json` uses `center_x`/`center_z` → migrate to `cx`/`cz`.

Symmetry-mode vocabulary is shared by both workflows: `mirror_x`, `mirror_z`, `rot_90`, `rot_180`.
Transform formulas live in `cross-cutting.md` §2.

---

## 3. MapProject (imported map)

### Top-level persisted shape (verified present in 345/345 maps)

```
name, version, gamemode, objective, max_build_height,
authors[], kits[], teams[], spawns[], observer_spawn,
wools[], spawners[], renewables[], block_drop_rules[],
filters{}, regions{}, apply_rules[]
```

- `filters` and `regions` are **dicts keyed by id**; everything else is a list (or scalar).
- `region_categories` is written by the editor as a hint store but is **not** part of the
  datamodel and is deliberately dropped by the serializer — it is recomputed at load
  (see §10). Do not treat it as canonical persisted state.

### Gamemode / CTW eligibility  **[decision]**

`gamemode` is **absent from most files** (39% of CommunityMaps, 9% of PublicMaps declare
`<gamemode>`; casing varies `ctw`/`CTW`). Rule: **parsed `gamemode`, case-folded, wins when
present; absent ⇒ `ctw`.** An explicit non-CTW value (e.g. `ad`, attack/defend like `citadel`,
`lindorm`) excludes the map even if it has wools.

A map is a **supported symmetric CTW** iff, with teams `T` (`|T| ≥ 2`) and wools grouped by
color `C`, with `capturers(c)` = teams owning a monument of color `c` and
`defenders(c) = T − capturers(c)`:

1. every color has **exactly one** defender, and
2. every team **both attacks** (`∃c. t ∈ capturers(c)`) **and defends** (`∃c. t = defender(c)`).

Validated: **332/345 (96%)** qualify. Rejections are principled — attack/defend maps
(`team not both roles`: citadel, lindorm, rushers_vs_defenders), arcade shared-wool maps
(`contested`, 0 defenders: stratosphere, quadrosphere, mist, …), and assigned-subset gimmicks
(`ambiguous`, >1 defender: new_life_ctw, two-quarter). **Team count is n-team general** — the
corpus has 2, 3, 4, 5, 6, and 8; do not hardcode 2/4.

### Derived / view-only

- Derived: `islands`, `symmetry`, `analysis_status`, `available_layers`, region `bounds`,
  region `polygon_2d`, region `categories`, wool owner team (§6).
- View-only: `region_tree` (§5), `top_surface_pixels`, configure pixel payloads.

---

## 4. Region  **[corrected — the draft's `coords{}`/`source` model was wrong]**

`regions` is a flat dict keyed by id. Every region entry is:

```json
{ "id": "...", "type": "<RegionType>", "bounds_2d": { ... }, ...type-specific fields }
```

`bounds_2d` (nested form) is persisted by the parser but is **derived**, not author input.
Type-specific fields, exactly as emitted by `pgm.serializer._encode_region`:

| type | extra persisted fields |
|---|---|
| `rectangle` | (only `bounds_2d`) |
| `cuboid` | `min{x,y,z}`, `max{x,y,z}` |
| `cylinder` | `base{x,y,z}`, `radius`, `height?` |
| `circle` | `center{x,z}`, `radius` |
| `sphere` | `origin{x,y,z}`, `radius` |
| `block`, `point` | `position{x,y,z}` |
| `union`, `negative`, `complement`, `intersect` | `children: [id, …]` |
| `mirror` | `source_id`, `origin{x,y,z}`, `normal{x,y,z}` |
| `translate` | `source_id`, `offset{x,y,z}` |
| `half` | `origin{x,y,z}`, `normal{x,y,z}` |
| `reference` | `ref_id` |
| `above` | `y` |
| `everywhere` | (none) |

**RegionType set = these 17.** All 17 occur in the corpus (incl. `reference` ×30, `everywhere`,
`above`). The draft incorrectly dropped `above`/`everywhere` and doubted `reference`. **[corrected]**

### Region rules **[decision]**

- `id` is the canonical persistent identifier, unique across the map.
- **Compound `children` and transform `source_id` are always string-id references** into the flat
  registry. Inline-dict children are **forbidden** in persistence. The editor must register any
  new child/source as a named-or-synthetic registry entry and reference it by id. (The current
  `region_editor.group_regions` writes inline dicts — that is a bug to fix, not the contract.)
- `bounds_2d` (derived) and `polygon_2d` (derived, never persisted) stay out of canonical input.
- Category is a derived role (§10), not a region field.

### Known region bugs to fix (do not encode into the contract)

- `region_editor.group_regions` stores inline child dicts → must store string ids.
- `region_encoder` resolves mirror/translate via `source`/`ref_region_id`, but the persisted
  field is **`source_id`** → the 71 corpus transform regions don't render in the editor preview.
- `region_encoder` mirror does **axis-aligned reflection only** (`xfact/zfact` from non-zero
  normal component); it cannot reflect across a diagonal normal (see §7).

---

## 5. RegionTreeNode (view model)

`GET /regions/tree` is the canonical editor region view-model and must stay separate from
persistence. Node shape:

```json
{
  "tree_id": "...", "id": "... | \"\"", "type": "<RegionType>",
  "label": "...", "synthetic_id": false, "category": "spawn|wool|build|other",
  "bounds": { "min_x":0,"min_z":0,"max_x":0,"max_z":0 },
  "coords": {}, "source": null, "polygon_2d": null, "children": [ RegionTreeNode, … ]
}
```

Required: `tree_id`, `id`, `type`, `label`, `synthetic_id`, `category`, `children`. `bounds` is
the **flat** form (§2). All editor activities consume this one node contract.

---

## 6. Wool & Monument  **[decision: grouped is canonical]**

### Persisted (grouped) shape

```json
{
  "id": "<color-slug>",
  "color": "red",
  "location": { "x":0,"y":64,"z":0 },
  "wool_room_region": "wool_red_room | null",
  "monuments": [
    { "id": "<color>-<team>", "team": "blue-team",
      "location": { "x":10,"y":65,"z":20 }, "monument_region": "blue_monument | null" }
  ]
}
```

- **Group key is `color`, unique per map.** Lossless on 196/197 + 148/148; the one exception
  (`emergency_meeting`, same color at two locations) is treated as out-of-spec. **[decision]**
- **IDs are deterministic from content** — wool id = color slug, monument id = `color+team`.
  (The current serializer's random `uuid4()` per-serialize is a bug: IDs must be stable across
  round-trips.) **[decision][corrected]**
- **Capturing team = `monuments[].team`** (= the PGM `<wool team>` attribute, the team that must
  retrieve the wool). The serializer's grouped output carries **no top-level capturing team**;
  do not read one. **[corrected]**
- **Monument is dual-form:** a coordinate (`location`, the majority) **or** a region reference
  (`monument_region`, ~30% — `<wool monument="region-id">`). Both are first-class.
- **`wool_room_region` is editor-authored only — it never appears in PGM XML.** Do not expect it
  from import.
- **Owner / defending team is derived, never stored:** `all_teams − capturing_teams`; exactly one
  ⇒ owner; zero ⇒ `contested`; more than one ⇒ `ambiguous` (surfaced as validation state, not
  forced). Holds for ~96% of maps. **Do not derive owner from apply rules** (lossy: 0% in corpus).
  The "defender cannot enter their own wool room" convention is expressed as an apply rule on the
  wool-room region, authored by the user (§9), not read from the wool. **[decision]**

---

## 7. Symmetry  **[decision: source + relation, map-level index]**

Symmetry is a first-class model, not configure-step output. Persisted locations: imported maps
in `symmetry.json`; sketches in `sketch.json.setup.mirror_mode` + `setup.center`.

```json
{ "status": "unconfirmed|confirmed|none",
  "modes": [],
  "primary": { "type": "rot_180", "confidence": 1.0, "user_override": true },
  "center": { "cx": 0, "cz": 0 } }
```

### Authoring contract **[decision]**

- The author owns **one source entity**; counterparts derive from `(mode, center)`.
- The **relation lives in a map-level symmetry index** (in `symmetry.json`): author-source →
  generated-set + mode + center. **PGM regions stay pure** — no studio-only fields injected into
  region entries.
- **Reflection (`mirror_x`/`mirror_z`) and `rot_180`** are expressible with native PGM `mirror`
  regions and **work in the studio engine today** (`rot_180` = two axis-aligned mirrors, verified
  equal to true rotation). These may persist as `mirror` regions chained by `source_id`.
- **`rot_90` / `rot_270` counterparts are baked to concrete regions.** A 90° rotation requires a
  diagonal (45°) reflection plane; this is **not** renderable by the current axis-only mirror
  engine and is **unverified in real PGM**. So rotational counterparts are expanded to concrete
  geometry for both rendering and XML export, with provenance kept in the map-level index for
  regeneration. (Math for the mirror decomposition is recorded should the engine + a real PGM
  server test later justify it.) **[corrected — draft assumed mirror/translate covered rotation]**

Prerequisite fix: `region_encoder` must resolve transforms via `source_id` (§4).

---

## 8. Teams, Spawns, Kits

### Team
```json
{ "id":"red", "name":"Red", "color":"red", "dye_color":"", "max_players":0, "min_players":0 }
```
`id` unique; references from spawns/wools/filters survive rename. `dye_color` is frequently `""`.

### Spawn  **[decision: reference the registry]**
```json
{ "team":"red-team", "kit":"spawn-kit", "yaw":0.0, "region":"<region_id>" }
```
- Persist `region` as a **string id** into the flat registry, not an inline region object.
  This fixes a current bug where all 270 named spawn regions are stored **twice** (inline in the
  spawn *and* in `regions{}`), which lets the two copies diverge. **[corrected]**
- Whether XML re-emits `region="id"` or an inline `<region>` child is derived from the synthetic-id
  flag and handled by `xml_writer` (`_is_synthetic`) — not stored.
- `observer_spawn` is a single separate spawn (`team`/`kit` empty).

### Kit  **[now in scope]**
```json
{ "id":"spawn-kit",
  "items":[ {"slot":0,"material":"diamond sword","amount":1,"damage":0,
             "unbreakable":true,"team_color":false,"enchantments":"sharpness:1"} ],
  "armor":[ {"slot_name":"helmet","material":"...","unbreakable":false,
             "team_color":false,"enchantments":""} ] }
```
`enchantments` is a comma-joined `"name:level"` string. Kits are referenced by `spawn.kit` and
`apply_rule.kit`/`lend_kit`.

---

## 9. Filters & Rule systems  **[corrected — draft under-modeled these]**

### Filters — author fully in v1 **[decision]**

`filters` is a flat **id-keyed registry**, structurally analogous to `regions`: 5169 atomic +
2603 composite across the corpus. Encoded by `pgm.serializer._encode_filter`.

- **Composite** filters reference children **by id**: `all`/`any`/`one` use `children:[id,…]`;
  `not`/`deny`/`allow` use `child:id`; `blocks` uses `region` + `child`; `offset` uses
  `vector` + `child`.
- **Atomic** filters carry their own params: `material`, `team`, `void`, `cause`, `carrying`,
  `wearing`, `holding`, `time`, `after`, `pulse`, `variable`, `completed`/`objective`,
  `kill-streak`, `class`, `region`, `players`, `spawn`, plus nullary `never`/`always`/`alive`/
  `dead`/`participating`/`observing`/`match-running`/`match-started`/`grounded`.
- Referenced by `apply_rules.*`, `renewables.{renew,replace}_filter`,
  `block_drop_rules.filter_id`, and other filters. Editing must enforce reference integrity.
- The full type set above (≈25) was validated complete across 345 maps (no unknowns); unknown
  types fall back to a bare `Filter(type)`.

### Apply rules — author fully in v1 **[decision]**

`apply_rules` is a **flat list**. One rule, as encoded by `_encode_apply_rule`:

```json
{ "region":"<region_id>",
  "enter":"<filter>", "leave":"...", "block":"...", "block_place":"...",
  "block_break":"...", "block_physics":"...", "block_place_against":"...",
  "use":"...", "filter":"<general filter>",
  "kit":"...", "lend_kit":"...", "velocity":"X,Y,Z", "message":"..." }
```

- `region` is near-universal (3776/3946) and references the registry by id. `message` optional.
- **A rule may carry several event→filter keys at once** (725 rules have ≥2, up to 3) — this is
  canonical, not a normalization target.
- Event filters reference the filter registry by id; `enter`/`block`/etc. values are filter ids.
- **Assign each rule a stable synthetic id** (editor-side, kept in `xml_data.json`, dropped on XML
  export) so symmetry authoring can reference a rule's counterpart. **[decision]**
- This is how the "defender cannot enter their own wool room" rule is authored: an `enter` rule
  on the wool-room region denying the owning team.

### Spawners, Renewables, Block-drop rules — in scope, round-trip-preserved

```json
// spawner (mob/item): references regions by id
{ "spawn_region":"red-wool-spawn", "player_region":"red-wool-room",
  "delay":"4s", "max_entities":3, "items":[ {"material":"wool","damage":14,"amount":1} ] }

// renewable: references region + filters by id
{ "region_id":"spawns", "rate":1.0, "renew_filter":"only-iron",
  "replace_filter":"...", "grow":false }

// block_drop_rule: references region + filter by id
{ "region_id":"...", "filter_id":"...", "replacement":"...", "wrong_tool":false,
  "items":[ {"material":"wood","damage":0,"amount":1,"chance":0.0} ] }
```

These are modeled and must round-trip with intact references. Full authoring UI for them is not
required for v1, but the contract and round-trip carry them.

---

## 10. Region category (derived) **[corrected]**

Category is **not** a region field. `map_api._compute_categories` derives it with precedence:
actual spawn/wool/spawner references → stored `region_categories` editor hints → name heuristics
(`"build"` substring). `region_categories` is an editor hint store in `xml_data.json` that the
serializer drops; it lets newly-drawn, not-yet-linked regions show in the right category.

The four-bucket model (`spawn`/`wool`/`build`/`other`) is **insufficient** — it leaves ~76% of
named regions in `other`, misses monuments, and conflates region identity with filter targeting.
The full model is specified in [`region-categorization.md`](region-categorization.md): a two-facet
model (`category` ∈ {spawn, observer_spawn, wool_room, monument, wool_spawner, build, mechanic,
other} + orthogonal `roles` incl. `rule_container`, `time_gated`), with build derived from the
void-enforcement structure rather than naming. Categories remain **derived**; `region_categories`
stays as a user-override store only.

---

## 11. SketchProject (concept-first)  **[draft was accurate; confirmed]**

```
id, gamemode("ctw"), name, version, objective, authors[],
setup: { center:{cx,cz}, bbox:{min_x,max_x,min_z,max_z}, mirror_mode } | null,
layout: { shapes:[…], islands:[…] } | null,
export_slug | null
```

- Sketch authors carry `name` (imported-map authors carry only `uuid`/`role`/`contribution`).
- `setup` may be `null` while `layout` exists.
- **Shapes** (primary authored geometry):
  - `rectangle`: `min_x,min_z,max_x,max_z`
  - `circle`: `center_x,center_z,radius`
  - `polygon`: `vertices` (+ optional bezier `controls`)
  - `lasso`: `vertices`
  - shared: `id`, `type`, `operation:"add"|"subtract"`, `override:boolean`
- **Islands** (derived-but-persisted metadata): `{ id, name, mirrors, shapeIds }`. Polygon
  exterior/holes, bounds, centroid are derived only.

---

## 12. API surface

Error envelope **[decision]**: adopt the structured form **now** and update `api.js` to read
`.error.message`:
```json
{ "error": { "code": "region_conflict", "message": "id 'spawn_red' already in use" } }
```
Success: `{ "ok": true, ...resource }`. Status codes already in use: 400 invalid, 404 not found,
409 conflict, 422 unprocessable (sketch export), 201 created.

### Routes (verified present)

```
# config / sources / pipeline
GET/POST /api/config
GET  /api/sources ; GET /api/sources/:slug/status ; GET /api/sources/:slug/validate
POST /api/import-from-url
GET  /api/pipeline/:slug/run            (SSE)

# imported map (read + metadata)
GET  /api/map/:name
PATCH/api/map/:name/metadata            (name,version,objective,max_build_height,gamemode,authors)
GET  /api/map/:name/symmetry  ; PATCH /api/map/:name/symmetry
GET  /api/map/:name/islands
GET  /api/map/:name/config    ; PATCH /api/map/:name/config
GET  /api/map/:name/regions   ; GET /api/map/:name/regions/tree
GET  /api/map/:name/layers/top-surface
GET  /api/map/:name/segments?axis=x|z

# configure step
GET  /api/configure/:name/state
PATCH/api/configure/:name/scan-layer | exclude-island | exclude-block | symmetry
GET  /api/configure/:name/layers/:layer_type/pixels | block-types

# regions
POST /api/map/:name/regions
POST /api/map/:name/regions/group | ungroup | restore
PATCH/DELETE /api/map/:name/region/:region_id
POST /api/map/:name/region/:region_id/change-type | remove-from-group | set-base-child

# teams / spawns
POST /api/map/:name/teams ; PATCH/DELETE /api/map/:name/teams/:team_id
POST /api/map/:name/spawns ; PATCH/DELETE /api/map/:name/spawn/:region_id
PATCH/DELETE /api/map/:name/observer-spawn

# objectives (wools + monuments)
POST /api/map/:name/wools ; PATCH/DELETE /api/map/:name/wools/:wool_id
POST /api/map/:name/wools/:wool_id/monuments
PATCH/DELETE /api/map/:name/wools/:wool_id/monuments/:mon_id

# sketch
GET/POST /api/sketch ; GET /api/sketch/:sid
PATCH /api/sketch/:sid/setup | layout | overview ; POST /api/sketch/:sid/export

# v1 additions implied by §9 (to be added): filters CRUD, apply-rules CRUD
```

**Frontend gap [corrected]:** `api.js` does **not** call `regions/group|ungroup|restore`,
`change-type`, `remove-from-group`, or `set-base-child` — those backend ops are unwired today.

### Editor-facing contract requirements

- All editor activities consume the `/regions/tree` node (§5); no activity-specific node shapes.
- Each route family gets a documented request/response schema (regions, teams, spawns,
  wools/monuments, filters, apply-rules, sketch) before the frontend migration.
- Keep derived geometry (`bounds`, `polygon_2d`) and tree-only labels out of persisted input.

---

## 13. Round-trip requirements (hard)

1. `map.xml → MapXml → map.xml` must stay lossless (already tested on the corpus).
2. `xml_data.json → MapXml → map.xml` **must be repaired**: align `deserializer`/`xml_writer`
   to the **grouped** wool shape (decision §6), fix region inline-children + `source_id`
   resolution (§4), and persist spawns as registry references (§8).
3. Editor mutations must keep references valid (region ids, filter ids, team ids, wool/monument
   ids) and never introduce inline-dict region children.
4. Editor-only fields (`region_categories`, apply-rule synthetic ids) live in `xml_data.json`
   but are dropped on XML export by design — they must not be required for XML validity.

---

## 14. Resolved questions (formerly "open")

All Phase 1 open questions are resolved above:

- Region types supported: the 17 in §4 (incl. `reference`/`above`/`everywhere`).
- Inline children: forbidden in persistence; flat string-id registry only (§4).
- Category: derived/editor-hint, not a region field (§10).
- group/ungroup/restore: backend ops exist but are currently unwired in `api.js` (§12); they
  remain editor operations over the registry. **[decision]** Ungroup dissolves **any** compound
  type (union/complement/intersect/negative), promoting its **direct** children to top-level —
  **one level only** (nested compounds are promoted intact, not flattened). Dissolving an ordered
  compound (`complement`/`negative`) discards base/subtrahend semantics, so the response carries a
  `warning`. `set_base_child` is complement-only; `remove_from_group` works on any region with
  children; `change_region_type` converts freely among the four compound types.
- Symmetry counterparts: source + relation in a map-level index; reflection/`rot_180` via mirror
  regions, `rot_90`/`rot_270` baked to concrete (§7).
- Kit: first-class resource, in scope (§8).
- Multiple spawns per team: tolerated; spawn keyed by its region reference (§8).
- Wool team: capturing team = `monuments[].team`; owner derived (§6).
- Wool color uniqueness: yes, color is the group key (§6).
- Monuments: dual-form (coord or region ref); multiple monuments per wool, one per team (§6).
- Filters / apply-rules: full id-keyed registry + flat rule list, **authored in v1** (§9);
  apply-rules get stable synthetic ids.
- Symmetry × rules: counterpart references use stable ids; expanded via the map-level index (§7,§9).
- Sketch islands: persisted author metadata, geometry recomputed (§11).
- Project identity: imported-map slug and sketch id remain distinct project models.
- Source-of-truth vs cache: `xml_data.json`/`sketch.json` are editable truth; `islands.json`,
  `symmetry.json`, parquet, and all `bounds`/`polygon_2d` are derived/regenerable.

---

## 15. Next documents

1. `docs/contracts/api-schemas.md` — request/response schema per route family (incl. new
   filters + apply-rules CRUD).
2. `docs/contracts/domain-model.md` — typed entities, references, invariants (Phase 2 input).
3. `docs/contracts/project-storage.md` — imported-map + sketch layout, future hosted storage.
