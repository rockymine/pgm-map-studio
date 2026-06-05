# TODO

Status key: ✅ done · 🔲 pending · ⏸ deferred

---

## pgm/ package

- ✅ `datatypes.py` — `MapXml`, `Team`, `Wool`, `Spawn`, `Kit`, `ApplyRule`, etc.
- ✅ `regions.py` — region type hierarchy (Rectangle, Cuboid, Union, Mirror, Translate, etc.); flat registry; stable synthetic IDs; `bounds_2d`
- ✅ `filters.py` — filter type hierarchy (All, Any, Not, Deny, Team, Material, Blocks, Carrying, Variable, After, Offset, etc.)
- ✅ `region_parser.py` — all region type parsers; synthetic ID injection; reference resolution
- ✅ `filter_parser.py` — flat filter registry builder; nested id registration; built-in pre-seeding
- ✅ `parser.py` — top-level orchestrator (teams, kits, spawns, wools, spawners, renewables, block-drop rules, apply rules with all attributes)
- ✅ `serializer.py` — `MapXml → xml_data.json` (no `region_categories`; flat children as ID strings)
- ✅ `xml_writer.py` — roundtrip `MapXml → map.xml`; synthetic ID stripping; nesting reconstruction; external-reference promotion
- ✅ Tests (417 passing) and README
- 🔲 `xml/generator.py` — generate stub PGM XML from detected islands when no map.xml exists (concept workflow)

## symmetry/ package

- ✅ `datatypes.py` — `SymmetryResult`, `GlobalSymmetryEntry`
- ✅ `detection.py` — IoU-based detection (rot_180, rot_90, mirror_x, mirror_z); island exclusion; adapts pgm-map-studio islands.json format
- ✅ `serializer.py` — `SymmetryResult → symmetry.json`
- ✅ Tests and README

## pipeline/ package

- ✅ 3-step pipeline (`run_layout`, `run_symmetry`, `run_xml`) with `PipelineResult`
- ✅ Per-map `map_config.json` (`exclude_islands`, `exclude_blocks`, `scan_layer`)
- ✅ Cache behaviour: skip steps when outputs exist; individual `force_*` flags per step
- ✅ Warning when island detection produces no results (distinguishes config error vs wrong layer vs size threshold)
- 🔲 Map import: accept local folder, ZIP, or URL; extract to workspace output dir

## workspace/ package

- 🔲 Active map session: working directory, dirty-state tracking, config persistence

## viewer/ package

- 🔲 Update pipeline service to invoke actual `pipeline.run()` (currently stubs)
- 🔲 Rename all `map_data.json` references to `xml_data.json`
- 🔲 Remove `map_context.json` load paths and `poi_assignments` references
- 🔲 Remove `node_id` references (no skeleton)
- 🔲 Remove build-region overlay toggle
- 🔲 POI marker coordinates: read from `xml_data.json` directly (`spawns[].region`, `wools[].location`, `wools[].monument`)
- 🔲 `region_categories` on-the-fly computation at viewer load time
- 🔲 Port/rewrite remaining front-end JS/HTML as needed

## export/ package

- ✅ XML roundtrip implemented in `pgm/xml_writer.py`
- 🔲 Wire `xml_writer.to_xml()` into the viewer's save endpoint
- 🔲 `export/scaffold_export.py` — export minimal Minecraft world folder + map.xml as ZIP (concept workflow)

## CLI

- 🔲 Extend `cli.py`: `import`, `run`, `xml`, `viewer` subcommands

## docs/

- ✅ `filter-use-cases.md` — semantic clustering of CTW apply-rule patterns; proposed UX questions
- ✅ `testing.md`
- 🔲 Update `plans/port-requirements.md` status once viewer integration is complete

## misc

- 🔲 `LICENSE` file
- 🔲 Verify parquet cache invalidation works correctly when `map_config.json` changes
