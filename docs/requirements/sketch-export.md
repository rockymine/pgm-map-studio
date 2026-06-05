# Requirements: Sketch — Export

**Semantic purpose:** Rasterize the complete map layout (all sectors) into a synthetic scan layer and hand off to the main editor, bypassing the Configure step.

Export is not an activity in the rail. It is an explicit user action available once the layout contains at least two islands.

---

## User requirements

- Trigger export when satisfied with the layout.

## System requirements

- Rasterize the complete layout — primary sector island polygons plus all mirrored or rotated copies in all sectors — into a parquet file matching the `layout_y0.parquet` format produced by the layout extraction pipeline. Each block column covered by an island polygon is marked as solid at Y=0.
- The rasterization always includes the full mirrored layout regardless of whether the mirror preview is currently toggled on or off in the Layout activity.
- Write this file as the synthetic scan layer for the map session.
- After export, the editor enters the post-Configure state:

| Configure output | Sketch equivalent |
|---|---|
| Scan layer parquet | Synthetic scan layer from rasterized island polygons |
| Island set | Islands from boolean computation; per-island participation flag serves the same role as island exclusion |
| Symmetry result (axis + center, confirmed) | Mirror mode + center from Setup |

- The Configure step is skipped entirely for Sketch sessions.
- Retain authored shapes, island names, per-island participation flags, bounding box, center, and mirror mode as restorable session state. Returning to Sketch after working through downstream activities must restore the full drawing session, not only the rasterized output.

## Gate

Export is available only when the layout contains at least two islands.
