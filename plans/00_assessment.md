# CTWAnalysisWithClaudeCode — Feature Classification & Migration Plan

---

## Part 1: File Classification

### REQUIRED — Workflow 1 (Existing-map)

| File | Purpose |
|---|---|
| `layout_analysis/region_reader.py` | Reads Minecraft Anvil `.mca` region files chunk-by-chunk |
| `layout_analysis/extractors.py` | Six block-extraction strategies (Y0, top surface, bedrock, density, solid, vertical segments) |
| `layout_analysis/pipeline.py` | `analyze_layout()` — orchestrates extraction |
| `layout_analysis/map_layout_config.py` | Per-map config (layer choice, exclusion block IDs, bounding box) |
| `island_analysis/detection.py` | `detect_islands()`, `find_island_holes()` — connected-component analysis |
| `island_analysis/pipeline.py` | `detect_and_enrich()`, `build_polygons()` |
| `island_analysis/datatypes.py` | `IslandBlocks`, `IslandPolygon`, `Island`, `CanonicalIsland` |
| `island_analysis/polygon.py` | Shapely polygon simplification/smoothing |
| `island_analysis/canonicalize.py` | D4 canonical form for islands |
| `skeleton_analysis/pipeline.py` | Full 9-step skeleton pipeline; `process_island()` |
| `skeleton_analysis/` (rest) | Rasterize, nodes, edges, merge, prune, builder, exporter |
| `symmetry_analysis/builder.py` | `classify_center()`, symmetry detection from island geometry |
| `symmetry_analysis/datatypes.py` | `SymmetryResult` |
| `xml_analysis/builder.py` | `MapXMLParser.parse()` — teams, spawns, wools, regions, kits |
| `xml_analysis/datatypes.py` | `MapData`, `Team`, `Wool`, `Spawn`, `Kit`, `Region`, `MapXmlContext` |
| `xml_analysis/regions.py` | Region geometry types: `Rectangle`, `Cuboid`, `Union`, `Mirror`, `Translate`, etc. |
| `xml_analysis/build_regions.py` | Build region extraction via void decomposition |
| `xml_analysis/pipeline.py` | `analyze_xml()` entry point |
| `xml_analysis/exporter.py` | JSON export helpers |
| `map_analysis/pipeline.py` | `run_island_geometry()`, `assemble_map()` |
| `map_analysis/datatypes.py` | `IslandAnalysis`, `MapContext`, `IslandGeometryResult` |
| `map_analysis/builder.py` | Island construction from geometry + XML |
| `map_analysis/grid_base.py` | `GridBase`, `rasterize_map_polygons()` |
| `map_analysis/poi_annotation.py` | POI assignment (spawn/wool → island) |
| `map_analysis/team_assignment.py` | Team color/slug resolution |
| `map_analysis/geometry_graph.py` | Inter-island connectivity graph |
| `map_viewer/app.py` | Flask app factory; blueprint registration |
| `map_viewer/routes/pages.py` | Static pages |
| `map_viewer/routes/map_data.py` | `GET /api/map/<slug>` — serve map context |
| `map_viewer/routes/regions.py` | Region CRUD endpoints |
| `map_viewer/routes/teams.py` | Team endpoints |
| `map_viewer/routes/spawns.py` | Spawn endpoints |
| `map_viewer/routes/wools.py` | Wool endpoints |
| `map_viewer/routes/minecraft.py` | Minecraft-specific endpoints |
| `map_viewer/services/config.py` | Config management service |
| `map_viewer/services/map_data.py` | Map context loading service |
| `map_viewer/services/pipeline.py` | Pipeline orchestration service |
| `map_viewer/services/regions.py` | Region service |
| `map_viewer/services/region_editor.py` | In-memory XML region manipulation |
| `map_viewer/services/region_tree.py` | Region tree traversal |
| `map_viewer/services/region_xml.py` | XML serialization/deserialization |
| `map_viewer/services/teams.py` | Team service |
| `map_viewer/services/team_editor.py` | Team edit manager |
| `map_viewer/services/spawns.py` | Spawn service |
| `map_viewer/services/spawn_editor.py` | Spawn edit manager |
| `map_viewer/services/wools.py` | Wool service |
| `map_viewer/services/wool_editor.py` | Wool edit manager |
| `common/geometry/coordinates.py` | `BoundingBox`, `Point2D`, coordinate helpers |
| `common/geometry/transforms.py` | `CanonicalTransform` — D4 world↔canonical space |
| `common/wool.py` | `WOOL_DAMAGE_TO_COLOR`, `normalize_wool_color()` |
| `common/visualization/block_colors.py` | Block ID → display color |
| `common/json_export.py` | `save_json()`, `load_json()` |

### REQUIRED — Workflow 2 (Concept-first)

| File | Purpose |
|---|---|
| `map_viewer/routes/concept.py` | Concept visualization endpoints (partial — needs extension) |
| `xml_analysis/regions.py` | Region types needed to build XML from drawn shapes |
| `map_analysis/grid_base.py` | Grid rasterization to back a drawn canvas |
| All viewer routes/services above | Shared with workflow 1 |

### NOT REQUIRED

| File / Module | Reason |
|---|---|
| `match_analysis/` (entire module) | Match event processing, DuckDB schema, life segments, position events — research/archive only |
| `match_analysis/traffic/` | Traffic graph from player movement data — archive |
| `ingestion/` | Fetches match/map data from remote API — archive |
| `ctw/commands/matches.py` | Match CLI commands |
| `ctw/commands/maps.py` | Map metadata commands (mostly match-DB backed) |
| `ctw/commands/db.py` | Raw SQL runner against DuckDB |
| `ctw/commands/purge.py` | Database cleanup |
| `ctw/commands/debug.py` | Debug diagnostics (layout-blocks, symmetry debug, etc.) — keep as internal dev tool at most |
| `island_analysis/profile.py` | Island shape profiling / classification — research |
| `island_analysis/profile_review.py` | Profile review web server — research |
| `island_analysis/statistics.py` | Cross-map statistics — research |
| `layout_analysis/audit.py` | Audit/validation scripts |
| `layout_analysis/fork_analysis.py` | Fork shape analysis — research |
| `layout_analysis/resources_plot.py` | Resource block plotting — research |
| `map_viewer/services/mojang.py` | Mojang API (player skins) — cosmetic, low priority |
| `match_analysis/visualization.py` | Match visualization (not map visualization) |

### IGNORE (generated / broken / duplicate)

| Path | Reason |
|---|---|
| `output/` | Generated pipeline artifacts |
| `match_logs/` | Raw parquet data |
| `map_folders/` | Input world data (not tracked) |
| `match_analysis/metadata.db` | Generated DuckDB database |
| `scripts/migrate_*.py` | One-time DB migrations |
| `scripts/backfill_*.py` | One-time backfill scripts |
| `scripts/compact_db.py` | DB maintenance |
| `scripts/verify_compact_db.py` | DB verification |
| `docs/demo/generate_demo.py` | Demo asset generator |
| `overview.py` | Unclear purpose, not examined |
| `__pycache__/` | Bytecode |

---

## Part 2: Essential Features Summary

**The core pipeline that pgm-map-studio needs:**

1. **Map Ingestion** — load a Minecraft world from a local folder, ZIP, or download URL. The old code assumes a pre-extracted folder in `map_folders/`. ZIP/URL import is missing and must be written fresh.

2. **Layout Extraction** — read Anvil `.mca` region files, apply one of six extraction strategies, produce a 2D block coordinate array. This is solid code in `layout_analysis/` and can be ported with minor cleanup.

3. **Island Detection** — connected-component analysis on the block grid to find discrete landmasses/platforms, then simplify them into Shapely polygons. `island_analysis/detection.py` and `island_analysis/polygon.py` are clean and reusable.

4. **Skeleton Graphs** — medial-axis thinning on each island to extract a navigation skeleton with nodes (endpoints/junctions) and edges. Used for connectivity. `skeleton_analysis/pipeline.py` is a 9-step pipeline that can be simplified.

5. **Symmetry Detection** — detect mirror/rotation symmetry from island geometry. `symmetry_analysis/builder.py` is well-contained.

6. **XML Parsing** — `xml_analysis/builder.py` (`MapXMLParser`) parses PGM `map.xml`: teams, wools, spawns, regions, kits. The region type hierarchy in `xml_analysis/regions.py` is comprehensive and directly reusable.

7. **Assembly** — `map_analysis/pipeline.py` combines geometry + symmetry + XML into a `MapContext` with fully annotated `Island` objects (team, spawn, wool, role). This is the central data model.

8. **Viewer (Flask)** — `map_viewer/` is the user-facing product: a Flask app with blueprints for browsing map geometry and editing regions/teams/spawns/wools in-browser, with XML serialization back out. The `*_editor.py` services (region, team, spawn, wool) are the key interactive components.

9. **Concept Mode** — `map_viewer/routes/concept.py` exists but is minimal. This is the entry point for workflow 2.

---

## Part 3: Migration Plan

### Proposed New Structure

```
src/pgm_map_studio/
├── cli.py                       # entry point (exists, extend)
│
├── minecraft/                   # Minecraft file I/O layer
│   ├── region_reader.py         # ← layout_analysis/region_reader.py
│   ├── extractors.py            # ← layout_analysis/extractors.py
│   ├── block_colors.py          # ← common/visualization/block_colors.py
│   └── wool.py                  # ← common/wool.py
│
├── layout/                      # Geometry extraction and island analysis
│   ├── config.py                # ← layout_analysis/map_layout_config.py (simplified)
│   ├── pipeline.py              # ← layout_analysis/pipeline.py
│   ├── islands.py               # ← island_analysis/detection.py + pipeline.py
│   ├── polygon.py               # ← island_analysis/polygon.py
│   ├── canonicalize.py          # ← island_analysis/canonicalize.py
│   ├── skeleton.py              # ← skeleton_analysis/pipeline.py (simplified)
│   └── symmetry.py              # ← symmetry_analysis/builder.py
│
├── xml/                         # PGM XML read/write
│   ├── parser.py                # ← xml_analysis/builder.py
│   ├── datatypes.py             # ← xml_analysis/datatypes.py
│   ├── regions.py               # ← xml_analysis/regions.py
│   ├── generator.py             # NEW: stub XML from geometry
│   └── serializer.py            # ← xml_analysis/exporter.py + map_viewer/services/region_xml.py
│
├── pipeline/                    # Assembly and import orchestration
│   ├── importer.py              # NEW: folder / ZIP / URL import
│   ├── geometry.py              # ← map_analysis/pipeline.py (geometry half)
│   ├── assembly.py              # ← map_analysis/pipeline.py (assembly half)
│   ├── datatypes.py             # ← map_analysis/datatypes.py
│   ├── grid_base.py             # ← map_analysis/grid_base.py
│   └── geometry_graph.py        # ← map_analysis/geometry_graph.py
│
├── workspace/                   # Session/workspace state
│   ├── workspace.py             # NEW: active map session
│   └── config.py                # ← ctw/config.py (stripped, no match-DB logic)
│
├── viewer/                      # Flask web UI
│   ├── app.py                   # ← map_viewer/app.py
│   ├── routes/
│   │   ├── pages.py             # ← map_viewer/routes/pages.py
│   │   ├── map_data.py          # ← map_viewer/routes/map_data.py
│   │   ├── regions.py           # ← map_viewer/routes/regions.py
│   │   ├── teams.py             # ← map_viewer/routes/teams.py
│   │   ├── spawns.py            # ← map_viewer/routes/spawns.py
│   │   ├── wools.py             # ← map_viewer/routes/wools.py
│   │   ├── minecraft.py         # ← map_viewer/routes/minecraft.py
│   │   ├── concept.py           # ← map_viewer/routes/concept.py (extend)
│   │   └── import_.py           # NEW: import workflow endpoints
│   └── services/
│       ├── map_data.py          # ← map_viewer/services/map_data.py
│       ├── pipeline.py          # ← map_viewer/services/pipeline.py
│       ├── region_editor.py     # ← map_viewer/services/region_editor.py
│       ├── region_tree.py       # ← map_viewer/services/region_tree.py
│       ├── region_xml.py        # ← map_viewer/services/region_xml.py
│       ├── team_editor.py       # ← map_viewer/services/team_editor.py
│       ├── spawn_editor.py      # ← map_viewer/services/spawn_editor.py
│       └── wool_editor.py       # ← map_viewer/services/wool_editor.py
│
└── export/                      # Export outputs
    ├── xml_export.py            # ← map_viewer XML write-back, cleaned up
    ├── concept_export.py        # NEW: drawn layout → XML
    └── scaffold_export.py       # NEW: concept → world scaffold ZIP
```

---

### Functionality to Keep and Optimize

| Old module | Action | Note |
|---|---|---|
| `layout_analysis/region_reader.py` | Port as-is | Clean, well-contained Anvil reader |
| `layout_analysis/extractors.py` | Port, drop `demo.py`/`audit.py` | Six strategies are all useful |
| `island_analysis/detection.py` | Port as-is | Solid connected-component logic |
| `island_analysis/polygon.py` | Port as-is | Shapely simplification is good |
| `skeleton_analysis/pipeline.py` | Port + simplify | 9 steps can be a single clean function; drop canonicalize grouping (was for cross-map batch) |
| `xml_analysis/builder.py` | Port as-is | Core XML parser; well-tested |
| `xml_analysis/regions.py` | Port as-is | Region hierarchy is comprehensive |
| `map_analysis/pipeline.py` | Split into `geometry.py` + `assembly.py` | Currently one large file with two distinct concerns |
| `map_analysis/grid_base.py` | Port as-is | Used by viewer canvas |
| `map_viewer/app.py` | Port + restructure imports | Remove match-DB blueprint references |
| `map_viewer/services/*_editor.py` | Port as-is | These are the user-facing value; well-tested |
| `common/geometry/` | Merge into `pipeline/datatypes.py` or keep standalone | `BoundingBox`, `Point2D`, `CanonicalTransform` are used everywhere |
| `layout_analysis/map_layout_config.py` | Simplify | Remove `map_layouts.json` file dependency; embed defaults, accept overrides via workspace config |

---

### Workflow Mapping per File

| File | Workflow 1 (Existing-map) | Workflow 2 (Concept-first) |
|---|---|---|
| `minecraft/region_reader.py` | ✓ (reads world files) | — |
| `minecraft/extractors.py` | ✓ (block extraction) | — |
| `layout/pipeline.py` | ✓ (geometry step) | — |
| `layout/islands.py` | ✓ (island detection) | ✓ (drawn islands also become island objects) |
| `layout/skeleton.py` | ✓ (skeleton for viewer) | ✓ (drawn layout skeleton) |
| `layout/symmetry.py` | ✓ (auto-detect) | ✓ (inform symmetry tool) |
| `xml/parser.py` | ✓ (read existing XML) | — |
| `xml/regions.py` | ✓ (parse + edit) | ✓ (generate from drawn shapes) |
| `xml/generator.py` (NEW) | ✓ (stub XML from geometry) | ✓ (XML from concept) |
| `xml/serializer.py` | ✓ (write edited XML) | ✓ (write generated XML) |
| `pipeline/importer.py` (NEW) | ✓ (folder/ZIP/URL) | — |
| `pipeline/geometry.py` | ✓ | — |
| `pipeline/assembly.py` | ✓ | partial (for drawn maps) |
| `workspace/workspace.py` (NEW) | ✓ (session state) | ✓ (session state) |
| `viewer/routes/import_.py` (NEW) | ✓ | — |
| `viewer/routes/concept.py` | — | ✓ |
| `viewer/routes/regions.py` | ✓ | ✓ |
| `viewer/services/*_editor.py` | ✓ | ✓ |
| `export/xml_export.py` | ✓ | ✓ |
| `export/concept_export.py` (NEW) | — | ✓ |
| `export/scaffold_export.py` (NEW) | — | ✓ |

---

### Import/Dependency Adjustments

All internal imports currently look like `from layout_analysis.pipeline import analyze_layout` — these become `from pgm_map_studio.layout.pipeline import analyze_layout`.

Key rewrites:
- `from common.geometry.coordinates import BoundingBox` → `from pgm_map_studio.pipeline.datatypes import BoundingBox`
- `from common.wool import ...` → `from pgm_map_studio.minecraft.wool import ...`
- `from xml_analysis.builder import MapXMLParser` → `from pgm_map_studio.xml.parser import MapXMLParser`
- `from map_viewer.services.region_editor import RegionEditor` → `from pgm_map_studio.viewer.services.region_editor import RegionEditor`
- `ctw/common.py` (`resolve_map_folder` etc.) → replaced by `workspace.workspace.Workspace`

External dependencies to keep: `shapely`, `numpy`, `flask`, `nbtlib` (or `anvil-parser` — check which one `region_reader.py` uses), `lxml` or stdlib `xml.etree`.

External dependencies to drop: `duckdb`, `pandas`, `scikit-image`, `matplotlib`, `scipy` (only needed for match analysis and static plots).

---

### CLI Commands / Routes for the New Repo

**CLI (`pgm-map-studio <command>`):**

| Command | Description | Workflow |
|---|---|---|
| `pgm-map-studio import <path>` | Import from folder, ZIP, or URL | 1 |
| `pgm-map-studio run <map>` | Full geometry pipeline | 1 |
| `pgm-map-studio xml <map>` | Parse or generate stub XML | 1 |
| `pgm-map-studio export xml <map>` | Write edited XML back to disk | 1 |
| `pgm-map-studio viewer [--port N]` | Start Flask viewer | 1 + 2 |
| `pgm-map-studio concept new` | Start blank concept canvas | 2 |
| `pgm-map-studio export scaffold <map>` | Export world scaffold ZIP | 2 |

**Viewer HTTP routes (`/api/...`):**

| Route | Description | Workflow |
|---|---|---|
| `POST /api/import` | Receive folder/ZIP/URL, run pipeline | 1 |
| `GET /api/map/<slug>` | Serve `map_context.json` | 1 |
| `GET/POST /api/regions/<slug>` | Region CRUD | 1 + 2 |
| `GET/POST /api/teams/<slug>` | Team CRUD | 1 + 2 |
| `GET/POST /api/spawns/<slug>` | Spawn CRUD | 1 + 2 |
| `GET/POST /api/wools/<slug>` | Wool CRUD | 1 + 2 |
| `GET /api/concept/<id>` | Serve concept canvas state | 2 |
| `POST /api/concept/<id>/shape` | Add primitive shape | 2 |
| `POST /api/concept/<id>/export/xml` | Generate XML from concept | 2 |
| `POST /api/concept/<id>/export/scaffold` | Generate world scaffold ZIP | 2 |

---

### Missing Pieces

| Gap | Priority | Notes |
|---|---|---|
| **ZIP/URL importer** (`pipeline/importer.py`) | High | Old code requires pre-extracted folders; needs `zipfile` extraction + optional HTTP download + world root detection |
| **Stub XML generator** (`xml/generator.py`) | High | `build_regions.py` does void decomposition but doesn't produce full PGM XML from scratch; needs team/wool/spawn scaffolding |
| **Workspace/session model** (`workspace/workspace.py`) | High | Old code uses global file paths + `ctw_config.yaml`; new tool needs an in-memory session with a working directory and dirty-state tracking |
| **Concept canvas drawing** | High | `routes/concept.py` is skeletal; needs a proper front-end canvas (SVG or `<canvas>`) and backend shape model |
| **Concept → XML export** (`export/concept_export.py`) | High | No equivalent in old repo — must convert drawn shapes (rectangles, circles, polygons) into PGM region XML, including build regions, spawns, wool placement |
| **World scaffold export** (`export/scaffold_export.py`) | Medium | No equivalent at all — needs to generate a minimal Minecraft world folder (level.dat + empty region files or a simple flat-world template) packaged as a ZIP; the map-maker server expects a standard world folder + `map.xml` |
| **Front-end for concept workflow** | Medium | The old viewer JS was built for map inspection, not drawing; the concept workflow needs shape tools (draw island, place spawn, place wool, set build region) |
| **Pyproject / packaging** | Done | Already created; add dependencies once ported |
| **Tests** | Medium | Old repo has tests for editors and parsers; port these directly |
