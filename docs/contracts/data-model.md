# Data Model & API

The **canonical shape of every entity is the typed code**: the domain types in
`src/pgm_map_studio/pgm/` (`datatypes.py`, `regions.py`, `filters.py`) and the codec
(`serializer`/`deserializer`), plus the B1 view-models that generate the TypeScript types
(see `frontend-stack.md`). **When this document and the code disagree, the code wins.**

This doc is the human-readable map of those types — what each entity is, how they relate, and the
rules types alone can't express. It is **present-tense**: it states what is true now. History lives
in git and `plans/refactor-plan.md`; per-activity needs live in `docs/requirements/`; the
coordinate/transform math lives in `geometry.md`; the invariants in `validation-invariants.md`.

---

## 1. Persistence boundaries

| Layer | File | Role |
|---|---|---|
| Global config | `~/.config/pgm-map-studio/config.json` | `maps_folder`, `output_folder` |
| **Imported-map truth** | `<output>/<slug>/xml_data.json` | author-editable state; round-trips to `map.xml` |
| Analysis outputs (derived) | `islands.json`, `symmetry.json`, `layer*.parquet` | regenerable from the world |
| **Sketch truth** | `~/.config/pgm-map-studio/sketches/<id>/sketch.json` | one file per sketch session |

Three model layers, never conflated:

- **Persistence** — what is on disk (`xml_data.json` / `sketch.json`).
- **Domain** — the typed object (`pgm.datatypes` / `pgm.regions` / `pgm.filters`).
- **View** — a transport shape for one UI workflow (`/regions/tree`, pixel payloads).

`xml_data.json` is regenerated with `tools/run_pipeline.py <root> <out> --xml-only --force`.

---

## 2. Coordinate & naming

- **Bounding box** is the flat object `{ min_x, min_z, max_x, max_z }`; `max_*` are extent bounds
  (+1 over the highest block index, applied once). Wire and view-model shape everywhere.
- **Symmetry center** is `{ cx, cz }`; its cell typology is derived (§7).
- Persisted region `bounds_2d` uses the nested `{min:{x,z},max:{x,z}}` form — a **derived** parser
  artifact, normalized to the flat form at the API boundary, never author input.

Full coordinate system, the +1 rule, and transform formulas: `geometry.md`.

---

## 3. MapProject (imported map)

Top-level persisted shape (present in every corpus map):

```
name, version, gamemode, objective, max_build_height,
authors[], kits[], teams[], spawns[], observer_spawn,
wools[], spawners[], renewables[], block_drop_rules[],
filters{}, regions{}, apply_rules[]
```

- `filters` and `regions` are **dicts keyed by id**; everything else is a list or scalar.
- `region_categories` is an editor hint store; the serializer drops it and it is recomputed on load
  (§10) — not canonical persisted state.
- Derived (not persisted as truth): `islands`, `symmetry`, `analysis_status`, `available_layers`,
  region `bounds`/`polygon_2d`/`category`, wool owner team (§6).
- View-only: `region_tree` (§5), `top_surface_pixels`, configure pixel payloads.

**CTW eligibility.** `gamemode` is absent from most files (casing varies `ctw`/`CTW`); rule:
parsed `gamemode`, case-folded, wins when present; absent ⇒ `ctw`. An explicit non-CTW value (e.g.
`ad`, attack/defend) excludes the map even with wools. A map is a **supported symmetric CTW** iff,
with teams `T` (`|T| ≥ 2`) and wools grouped by color, with `capturers(c)` = teams owning a monument
of color `c` and `defenders(c) = T − capturers(c)`: (1) every color has exactly one defender, and
(2) every team both attacks and defends. Team count is **n-team general** (corpus has 2,3,4,5,6,8) —
do not hardcode 2/4. Rejections are principled (attack/defend, arcade shared-wool, assigned-subset).

---

## 4. Region (`pgm.regions`)

`regions` is a flat dict keyed by id. Each entry: `{ id, type, bounds_2d, …type-specific }`.
`bounds_2d` is derived (parser-populated), not author input. The **17 region types** and their
extra persisted fields (as emitted by `pgm.serializer._encode_region`):

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

Rules:
- `id` is the unique persistent identifier.
- **Compound `children` and transform `source_id` are always string-id references** into the flat
  registry — inline-dict children are forbidden in persistence. The editor registers any new
  child/source as a named-or-synthetic entry (anonymous regions get stable ids
  `"{parent}__anon_{i}"` / `"__apply_{i}"`) and references it by id.
- `bounds_2d` (derived) and `polygon_2d` (derived, never persisted) are not author input.
- Category is a derived role (§10), not a region field.

---

## 5. RegionTreeNode (view model)

`GET /regions/tree` is the editor region view-model — separate from persistence:

```json
{ "tree_id":"…", "id":"… | \"\"", "type":"<RegionType>", "label":"…",
  "synthetic_id": false, "category":"spawn|wool_room|monument|…", "facets": { … },
  "bounds": { "min_x":0,"min_z":0,"max_x":0,"max_z":0 },
  "polygon_2d": null, "children": [ RegionTreeNode, … ] }
```

`bounds` is the flat form (§2). Categories/roles come from `region-categorization.md`. All editor
activities consume this one node shape. *(B4a will make the tree a curated view — group by
category/roles, collapse synthetic rule-wiring — rather than the raw compound graph; see the plan.)*

---

## 6. Wool & Monument

Persisted **grouped-by-color** shape:

```json
{ "id":"<color-slug>", "color":"red", "location":{ "x":0,"y":64,"z":0 },
  "wool_room_region":"… | null",
  "monuments":[ { "id":"<color>-<team>", "team":"blue-team",
                  "location":{ "x":10,"y":65,"z":20 }, "monument_region":"… | null" } ] }
```

- **Group key is `color`, unique per map.** IDs are **deterministic from content** (wool = color
  slug, monument = `color+team`) so they are stable across round-trips.
- **Capturing team = `monuments[].team`** (the PGM `<wool team>` — the team that retrieves the wool).
  There is no top-level capturing team; do not read one.
- **Owner / defending team is derived, never stored:** `all_teams − capturing_teams`; exactly one ⇒
  owner, zero ⇒ `contested`, more than one ⇒ `ambiguous` (a validation state, not forced). Do **not**
  derive owner from apply rules.
- **Monument is dual-form:** a coordinate (`location`, the majority) or a region reference
  (`monument_region`). Both first-class.
- **`wool_room_region` is editor-authored only** — it never appears in PGM XML; don't expect it on
  import.
- The "defender cannot enter their own wool room" convention is an apply rule on the wool-room
  region (§9), authored by the user, not read from the wool.

---

## 7. Symmetry

First-class model. Imported maps persist it in `symmetry.json`; sketches in `sketch.json.setup`.

```json
{ "status":"unconfirmed|confirmed|none",
  "modes":[ { "type":"mirror_d2", "detected":true, "confidence":1.0 } ],
  "primary":{ "type":"mirror_d2", "confidence":1.0, "user_override":true },
  "center":{ "center_x":238.5, "center_z":306.5 }, "center_cell":"1x1" }
```

(`center_cell` is derived; `center` uses `center_x/center_z` on disk, renamed to `cx/cz` at the wire
boundary.)

**Mode vocabulary** (all about the center): four reflections `mirror_x`, `mirror_z`, `mirror_d1`
(main diagonal), `mirror_d2` (anti-diagonal); rotations `rot_180`, `rot_90`, and the general
`rot_<d>` with `d = 360/n` (`rot_120`/`rot_72`/`rot_60` for 3/5/6 teams). Formulas: `geometry.md`;
helpers: `symmetry.datatypes`.

**Center cell** (`1x1`/`1x2`/`2x1`/`2x2`) is derived from the center coordinate's parity (half-integer
→ 1-wide, integer → 2-wide). `rot_90` and the diagonals swap X↔Z, so they require a **square** cell
(`1x1`/`2x2`); reflections and `rot_180` accept any cell.

**Lattice exactness.** Only 2- and 4-fold rotation and reflections are exact on the block grid;
other `rot_n` (3/5/6/8-fold) are approximate (crystallographic restriction) — hand-built,
counterparts baked. Detection currently covers the lattice-exact subset; `rot_n` is modeled and
authorable, with n-fold detection + sketch authoring as follow-ups.

**Authoring axes.** A **primary axis** is always active (partitions teams = the mode). An **optional
secondary axis**, perpendicular and toggleable, subdivides each primary region — *intra-team
symmetry* (a team's two wools as mirror images). `sketch.json.setup` =
`{ center, center_cell (derived), mirror_mode (primary), secondary_axis:{orientation,enabled}|null, bbox }`.

**Counterparts.** The author owns one source entity; counterparts derive from `(mode, center)` via a
map-level index in `symmetry.json` (author-source → generated-set + mode + center). PGM regions stay
pure. All four reflections + `rot_180` persist as native PGM `mirror` regions chained by `source_id`
(diagonal reflection is renderable via `pgm.regions.reflect_*` / `region_encoder._reflect_geom`, and
real-PGM-verified by `vertex`). `rot_90`/`rot_270` and other `rot_n` **bake to concrete geometry**
(PGM has no rotation region type), with provenance in the index for regeneration.

Team/wool coupling (how many teams a mode requires): `validation-invariants.md`.

---

## 8. Teams, Spawns, Kits

```json
// team
{ "id":"red-team", "name":"Red", "color":"dark red", "dye_color":"", "max_players":0, "min_players":0 }

// spawn — region is a string id into the flat registry (never an inline region object)
{ "team":"red-team", "kit":"spawn-kit", "yaw":0.0, "region":"<region_id>" }

// kit — referenced by spawn.kit and apply_rule.kit/lend_kit
{ "id":"spawn-kit",
  "items":[ {"slot":0,"material":"diamond sword","amount":1,"damage":0,
             "unbreakable":true,"team_color":false,"enchantments":"sharpness:1"} ],
  "armor":[ {"slot_name":"helmet","material":"…","unbreakable":false,
             "team_color":false,"enchantments":""} ] }
```

- Team `id` is unique; references from spawns/wools/filters survive rename. `dye_color` is often `""`.
- A team may have multiple spawns. `observer_spawn` is a single separate spawn (`team`/`kit` empty).
- Whether XML re-emits `region="id"` or an inline `<region>` is derived from the synthetic-id flag by
  `xml_writer` (`_is_synthetic`), not stored. `enchantments` is a comma-joined `"name:level"` string.

---

## 9. Filters & rule systems

**Filters** (`pgm.filters`) — a flat id-keyed registry, structurally like `regions`:

- **Composite** filters reference children by id: `all`/`any`/`one` → `children:[id,…]`;
  `not`/`deny`/`allow` → `child:id`; `blocks` → `region` + `child`; `offset` → `vector` + `child`.
- **Atomic** filters carry their params: `material`, `team`, `void`, `cause`, `carrying`, `wearing`,
  `holding`, `time`, `after`, `pulse`, `variable`, `completed`/`objective`, `kill-streak`, `class`,
  `region`, `players`, `spawn`, plus nullary `never`/`always`/`alive`/`dead`/`participating`/
  `observing`/`match-running`/`match-started`/`grounded`.
- Referenced by `apply_rules.*`, `renewables.{renew,replace}_filter`, `block_drop_rules.filter_id`,
  and other filters. Editing enforces reference integrity. Unknown types fall back to `Filter(type)`.
- Full vocabulary + event×type matrices: `filter-use-cases.md`.

**Apply rules** — a flat list. One rule (`_encode_apply_rule`):

```json
{ "id":"rule_<n>", "region":"<region_id>",
  "enter":"…","leave":"…","block":"…","block_place":"…","block_break":"…",
  "block_physics":"…","block_place_against":"…","use":"…","filter":"<general filter>",
  "kit":"…","lend_kit":"…","velocity":"X,Y,Z","message":"…" }
```

- `region` references the registry by id; a rule may carry several event→filter keys at once
  (canonical, not a normalization target). Event values are filter ids.
- `id` is a **stable synthetic editor id** (`rule_<n>`), kept in `xml_data.json` and **dropped on XML
  export**, so symmetry authoring can reference a rule's counterpart.

**Spawners, renewables, block-drop rules** — modeled and round-trip-preserved; reference regions/
filters by id:

```json
{ "spawn_region":"red-wool-spawn", "player_region":"red-wool-room", "delay":"4s",
  "max_entities":3, "items":[ {"material":"wool","damage":14,"amount":1} ] }            // spawner
{ "region_id":"spawns", "rate":1.0, "renew_filter":"only-iron", "replace_filter":"…",
  "grow":false }                                                                         // renewable
{ "region_id":"…", "filter_id":"…", "replacement":"…", "wrong_tool":false,
  "items":[ {"material":"wood","damage":0,"amount":1,"chance":0.0} ] }                    // block_drop
```

---

## 10. Region category (derived)

Category is not a region field — it is derived (`map_api._compute_categories` + the full model in
`region-categorization.md`): a two-facet model (`category` ∈ {spawn, observer_spawn, wool_room,
monument, wool_spawner, build, mechanic, other} + orthogonal `roles` like `rule_container`,
`time_gated`), with build derived from void-enforcement structure, not naming. `region_categories`
in `xml_data.json` is a **user-override store only**, dropped by the serializer.

---

## 11. SketchProject (concept-first)

```
id, gamemode("ctw"), name, version, objective, authors[],
setup:  { center:{cx,cz}, center_cell, bbox:{min_x,max_x,min_z,max_z},
          mirror_mode, secondary_axis:{orientation,enabled}|null } | null,
layout: { shapes:[…], islands:[…] } | null,
export_slug | null
```

- Sketch authors carry `name` (imported-map authors carry `uuid`/`role`/`contribution`).
- **Shapes** (authored geometry): `rectangle` (`min_x,min_z,max_x,max_z`), `circle`
  (`center_x,center_z,radius`), `polygon`/`lasso` (`vertices`, polygon + optional bezier `controls`);
  shared `id`, `type`, `operation:"add"|"subtract"`, `override:boolean`.
- **Islands** (derived-but-persisted metadata): `{ id, name, mirrors, shapeIds }`; polygon
  exterior/holes, bounds, centroid are derived only.

---

## 12. API surface

Routes are defined in `studio/routes/*.py` (authoritative). Error envelope:
`{ "error": { "code":"…", "message":"…" } }`; success `{ "ok": true, …resource }`; status codes 400
/ 404 / 409 / 422 / 201.

```
# config / sources / pipeline
GET/POST /api/config ; GET /api/sources ; GET /api/sources/:slug/status|validate
POST /api/import-from-url ; GET /api/pipeline/:slug/run (SSE)

# imported map
GET /api/map/:name ; PATCH /api/map/:name/metadata
GET|PATCH /api/map/:name/symmetry ; GET /api/map/:name/islands
GET|PATCH /api/map/:name/config ; GET /api/map/:name/regions ; GET /api/map/:name/regions/tree
GET /api/map/:name/layers/top-surface ; GET /api/map/:name/segments?axis=x|z

# configure
GET /api/configure/:name/state
PATCH /api/configure/:name/scan-layer|exclude-island|exclude-block|symmetry
GET /api/configure/:name/layers/:layer_type/pixels|block-types

# regions
POST /api/map/:name/regions ; POST /api/map/:name/regions/group|ungroup|restore
PATCH|DELETE /api/map/:name/region/:region_id
POST /api/map/:name/region/:region_id/change-type|remove-from-group|set-base-child
POST /api/map/:name/region/:region_id/counterpart   # C13: symmetry counterpart(s) from a source

# teams / spawns / objectives
POST /api/map/:name/teams ; PATCH|DELETE /api/map/:name/teams/:team_id
POST /api/map/:name/spawns ; PATCH|DELETE /api/map/:name/spawn/:region_id
PATCH|DELETE /api/map/:name/observer-spawn
POST /api/map/:name/wools ; PATCH|DELETE /api/map/:name/wools/:wool_id
POST /api/map/:name/wools/:wool_id/monuments ; PATCH|DELETE /api/map/:name/wools/:wool_id/monuments/:mon_id

# filters / apply-rules (CRUD) + filter↔region wiring (C9)
POST /api/map/:name/filters ; PATCH|DELETE /api/map/:name/filters/:filter_id
POST /api/map/:name/apply-rules ; PATCH|DELETE /api/map/:name/apply-rules/:rule_id
GET  /api/map/:name/wiring/suggestions ; POST /api/map/:name/wiring/apply

# sketch
GET/POST /api/sketch ; GET /api/sketch/:sid
PATCH /api/sketch/:sid/setup|layout|overview ; POST /api/sketch/:sid/export
```

Editor contract: all activities consume the `/regions/tree` node (§5); derived geometry (`bounds`,
`polygon_2d`) and tree-only labels stay out of persisted input. Codec + editor-service signatures
live in the code (`pgm.serializer`/`pgm.deserializer` + `studio/services/`).

---

## 13. Round-trip invariants (hard — enforced by `tools/roundtrip_check.py`)

1. `map.xml → MapXml → map.xml` is lossless.
2. `xml_data.json → MapXml → map.xml` is lossless: grouped wool shape (§6), string-id region
   children + `source_id` resolution (§4), spawns as registry references (§8).
3. Editor mutations keep references valid (region/filter/team/wool/monument ids) and never introduce
   inline-dict region children.
4. Editor-only fields (`region_categories`, apply-rule synthetic ids) are dropped on XML export — they
   must not be required for XML validity.
