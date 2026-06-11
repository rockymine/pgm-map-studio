# API schemas

*Spec — the HTTP contract.* The request/response **shapes** are the pydantic
models in `src/pgm_map_studio/schemas/` (generated to `frontend/src/contract.ts`);
this doc covers the **conventions** every route follows — envelopes, error codes,
naming, REST-vs-RPC — plus a route-family index. The single JS client is
`studio/static/api.js`.

## Envelopes

**Success.** A *mutation* (POST/PATCH/DELETE) returns `{"ok": true, ...result}` —
`ok` plus any result fields the action produces (e.g. `{"ok": true, "id": "..."}`,
`{"ok": true, "bounds": {...}}`). A *read* (GET) returns the **resource itself**,
unwrapped (e.g. the map dict, the region tree, the sketch). Status is `200`, or
`201` on resource creation.

**Error.** Every `/api/` error is

```json
{"error": {"code": "<machine-readable>", "message": "<human-readable>"}}
```

plus any error-specific extra keys at the top level (e.g. `references` on a
409 filter-in-use). This is enforced centrally in `studio/errors.py`: routes keep
returning the simple `jsonify({"error": "..."}), <status>` form (or `abort(404)`)
and an `after_request` transformer + `HTTPException` handler rewrite both into the
envelope. The `code` defaults from the HTTP status:

| status | code            | meaning                                   |
|--------|-----------------|-------------------------------------------|
| 400    | `bad_request`   | malformed/invalid payload                 |
| 401    | `unauthorized`  | (reserved — auth is deferred, contract §0)|
| 403    | `forbidden`     | (reserved)                                |
| 404    | `not_found`     | map / entity / route missing              |
| 409    | `conflict`      | id clash, or resource in use (+`references`)|
| 415    | `unsupported_media_type` |                                  |
| 422    | `unprocessable` | semantically invalid (e.g. export needs ≥2 islands)|
| 500    | `internal`      | unexpected server error                   |

Non-`/api/` (HTML page) routes keep Flask's normal error pages — the envelope is
scoped to the JSON API.

The JS client reads the message via `apiErrorMessage(body)` (tolerant of the
legacy flat form) and throws `Error(message)`; activities surface that message.

## Naming & REST-vs-RPC conventions

- **Collections are plural**: `/api/map/<name>/teams`, `/wools`, `/spawns`,
  `/filters`, `/apply-rules`, `/regions`. Create = `POST` to the collection.
- **Item routes** live under the plural collection: `/teams/<id>`, `/wools/<id>`,
  `/filters/<id>`, `/apply-rules/<id>`, `/regions/<id>`, `/spawns/<region_id>`.
  Werkzeug resolves the static collection-action routes (`/regions/group`) ahead
  of the dynamic item route (`/regions/<id>`), so the two coexist safely.
- **Spawns are keyed by their linked `region_id`**, not a separate spawn id (a
  spawn *is* a team↔region link).
- **Compound / non-CRUD operations use RPC action-URLs**, not invented sub-resources:
  `/regions/group`, `/regions/ungroup`, `/regions/restore`,
  `/regions/<id>/change-type`, `/regions/<id>/remove-from-group`,
  `/regions/<id>/set-base-child`, `/regions/<id>/counterpart`. These mutate the
  region graph in ways that aren't a single resource CRUD.
- **Wool monuments are a sub-collection**: `/wools/<id>/monuments[/<mon_id>]`.

## Route families

Shapes: `M` = persisted `MapProject` slice, `RT` = `RegionTreeResponse`,
`SK` = `SketchProject` (all in `contract.ts`).

| Family | Routes | Notes |
|---|---|---|
| Config | `GET/POST /api/config` | app config (maps/output folders) |
| Sources | `GET /api/sources`, `…/<slug>/status`, `…/<slug>/validate`, `POST /api/import-from-url` | import an Overcast map |
| Pipeline | `GET /api/pipeline/<slug>/run` (SSE) | streamed build |
| Map data | `GET /api/map/<name>` · `/regions` · `/regions/tree`→`RT` · `/symmetry` · `/islands` · `/segments` · `/layers/top-surface` · `PATCH /metadata` · `/symmetry` | reads return the resource |
| Teams | `POST /teams`, `PATCH/DELETE /teams/<id>` | `M.teams[]` |
| Regions | `POST /regions`, `PATCH/DELETE /regions/<id>`, + RPC ops above | `M.regions{}`; tree view = `RT` |
| Spawns | `POST /spawns`, `PATCH/DELETE /spawns/<region_id>`, `PATCH/DELETE /observer-spawn` | keyed by region |
| Objectives | `POST /wools`, `PATCH/DELETE /wools/<id>`, `…/<id>/monuments[/<mon>]` | grouped-by-colour wools |
| Filters | `GET/POST /filters`, `PATCH/DELETE /filter/<id>` | delete rejects with `references` (409) |
| Apply-rules | `GET/POST /apply-rules`, `PATCH/DELETE /apply-rule/<id>` | synthetic `rule_<n>` ids |
| Sketch | `GET/POST /api/sketch`, `GET /<id>`→`SK`, `PATCH /<id>/{setup,layout,overview}`, `POST /<id>/export` | write routes validate against `SK` |
| Configure | `PATCH /api/configure/<name>/{scan-layer,exclude-island,exclude-block,symmetry}` | symmetry center is `{cx,cz}` |
| Minecraft | `GET /api/minecraft/player` | uuid/name lookup |

Symmetry/bbox wire naming is unified (C6): bbox `{min_x,min_z,max_x,max_z}`,
center `{cx,cz}` — see `geometry.md`.
