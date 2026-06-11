# pgm-map-studio

`pgm-map-studio` is a browser-based editor for authoring and editing PGM Capture-the-Wool maps.

The studio is an **editor**, not just a viewer. It supports two ways of entering the editing workflow:

* importing an existing Minecraft map, then analysing it through the pipeline;
* starting from a concept sketch, then exporting that sketch into the same data model used by imported maps.

Both paths share the same editor shell and the same core concepts: activities, map canvas, entity sidebars, inspectors, regions, filters, and symmetry handling.

## Entry points

An existing map can be imported from a map folder, ZIP file, or download URL. Import is explicitly triggered by the user. After import, the pipeline runs automatically and derives layout, symmetry, and XML data from the map. The first mandatory stop is **Configure**, because the pipeline cannot always know which scan layer or symmetry interpretation is correct. The user confirms these assumptions before continuing with the remaining editing activities.

A new map can also begin without an imported world. In that case, the user starts in Sketch and draws the island layout directly. Sketch is concept-first: it is used to define the initial structure of a new map, not to edit an existing Minecraft world. When the sketch is exported, it is rasterised into a synthetic scan layer in the same format produced by the import pipeline. The Editor can then continue from that generated map data as if the map had been imported.

## Activity layout

Most activities use the same three-column workspace:

* **Sidebar** — lists the relevant entities for the current activity, such as maps, islands, teams, wools, regions, or rules. Some activities also use the sidebar for navigation between related steps.
* **Canvas** — shows the map or sketch. It may be static for review-focused activities, or interactive for placement and editing. Interactive canvases provide common controls such as pan, zoom, selection, and activity-specific editing tools.
* **Inspector** — edits attributes of the selected entity, such as name, color, team ownership, coordinates, region ids, or rule settings. Some activities may not need an inspector.

Activities are designed to keep rule editing close to the object it belongs to. Spawn-related rules live in Teams, wool-room access lives in Objectives, and build or void constraints live in Build Regions.

## Sketch

Concept-first authoring for **new** maps with no imported world. The author draws an island layout. Sketch rasterises it to a **synthetic scan layer** in the pipeline's parquet format, so the Editor activities from Teams onward treat it like an imported map.

State lives in `sketch.json` (`docs/contracts/data-model.md` §11). Sketch is entered only when no map is imported.

### Activities

1. **Overview** — name, version, authors.
2. **Setup** — bounding box, center point, mirror mode / symmetry axis.
3. **Layout** — draw island shapes with add/subtract operations, override handling, per-island mirror participation, and live symmetry preview.

**Export** is a button, not an activity. It rasterises the full island set to the synthetic scan layer and hands off to the Editor.

Islands emerge from the boolean topology of the drawn shapes. They are never declared manually. Symmetry counterparts are a live preview and are not stored.

Per-activity requirements: `docs/requirements/sketch-*.md`.

## Editor

Edit an imported PGM Capture-the-Wool map and write back a valid `map.xml` in a round-trip-safe way.

Input is either a Minecraft world processed by the layout/symmetry pipeline or a Sketch export. State lives in `xml_data.json`; entity shapes are described in `docs/contracts/data-model.md`.

### Activities

1. **Configure** — choose the scan layer; review/exclude islands; confirm detected symmetry.
2. **Overview** — name, version, objective, authors.
3. **Teams** — teams, kits, spawn placement, spawn access rules.
4. **Build Regions** — max build height, build-area declaration, void/boundary enforcement, lockdowns, block physics.
5. **Objectives** — wool placement, wool-room access rules, wool availability.
6. **Regions** — spatial registry audit: inventory, unassigned regions, symmetry-violation review.

Rules and filters are authored inline in the relevant steps:

* spawn protection → Teams
* wool-room access → Objectives
* void enforcement → Build Regions

A dedicated filter↔region wiring surface is planned.

Per-activity requirements: `docs/requirements/editor-*.md`.
