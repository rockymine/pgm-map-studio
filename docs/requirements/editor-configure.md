# Requirements: Configure

**Semantic purpose:** Establish the shared analytical foundation — scan layer, islands, and symmetry — that all subsequent editing activities depend on. No map authoring is possible until this step is complete.

---

## Sub-step 1: Scan Layer Selection

**User requirements**
- User must be presented with the available Y-level layers produced by the pipeline and must choose one as the scan layer.
- User must be able to visually distinguish layers (the 2D block snapshot at each Y) to make an informed choice — they need to identify which layer is the playable ground plane.
- This is a blocking decision; the step must not proceed until a layer is selected.

**System requirements**
- Pipeline must scan the imported world at multiple Y levels and produce one parquet file per layer, each a 2D block snapshot.
- System must present all available layers to the user for selection.
- System must store the selected layer as the canonical scan layer for this map session.
- Changing the scan layer after islands or symmetry have been reviewed must warn the user that island detection and symmetry will be recomputed and prior decisions (exclusions, symmetry confirmation) will be reset.

---

## Sub-step 2: Island Review and Exclusion

**User requirements**
- User must be shown the islands detected from the chosen scan layer — contiguous areas of solid ground, each with a polygon outline, bounding box, and centroid.
- User must be able to exclude individual islands from analysis (e.g. observer tower, decorative platform) without removing them from the world.
- Exclusion must be reversible — the user may reinstate an excluded island.

**System requirements**
- From the scan layer, system must detect islands as contiguous solid-ground regions and compute for each: polygon outline, bounding box, centroid.
- System must distinguish included islands from excluded islands and exclude the latter from all downstream analysis (symmetry inference, team count suggestion, spatial canvas for editing).
- System must persist island exclusion decisions as part of the map session state.

---

## Sub-step 3: Symmetry Confirmation

**User requirements**
- User must be shown the pipeline's detected symmetry candidates, each with its type (`rot_90`, `rot_180`, `mirror_x`, `mirror_z`) and confidence score, and the inferred map center point.
- User must choose one of three outcomes: confirm the top candidate as-is, confirm with an override (change the detected axis or center point), or reject symmetry entirely (`none`).
- User must be able to override the axis or center point independently without rejecting and re-confirming.
- Symmetry status `unconfirmed` must not persist past the Configure step.

**System requirements**
- From the included islands, system must infer the most likely global symmetry and produce a symmetry result containing: detected modes with confidence scores, inferred map center point, and initial status `unconfirmed`.
- System must transition symmetry status to `confirmed` or `none` based on user decision and store the final axis, center point, and status.
- On confirmation, system must activate the **mirroring engine**: throughout all subsequent activities, whenever a region is defined the system may propose a counterpart computed from the confirmed axis and center point. The user confirms or rejects each proposal individually — no batch accept.
- On confirmation, system must activate **symmetry validation**: for applicable symmetry types and team counts, the system must check that spatial entities (spawn positions, wool room positions) satisfy the expected geometric relationship and surface violations as warnings.
- If symmetry is set to `none`, system must suppress all mirroring suggestions and all symmetry validation for this map.

---

## Step-level system requirements

- The Configure step must complete fully before any authoring activity (Overview, Teams, Build Regions, Objectives, Filters, Regions) is accessible.
- All three artefacts — scan layer choice, island set (with exclusions), symmetry result — must be stored as the shared foundation of the map session and readable by every subsequent activity.
