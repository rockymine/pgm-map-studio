# Sketch Workflow — Vision and Mental Model

## Identity and role

Sketch is the concept-first entry point to the editor. It is for **new maps only** — it is not a mode for editing existing maps. The user draws a layout from scratch without an imported world or pipeline output.

The Sketch workflow replaces the Configure step. Where Configure derives the scan layer, island set, and symmetry from an imported world, Sketch produces the same three outputs by having the user define them directly:

| Configure (existing-map) | Sketch (concept-first) |
|---|---|
| Pipeline extracts scan layer parquet | User draws island shapes → rasterized to parquet |
| Island detection from scan layer | Islands emerge from boolean topology of drawn shapes |
| Symmetry inferred + user confirms | Symmetry axis set by user upfront, adjustable any time |

The sketch output is a **synthetic scan layer** — the drawn and mirrored island layout rasterized to the same parquet format that the layout extraction pipeline produces. Subsequent editor activities (Teams, Build Regions, Objectives, Filters, Regions) operate on this synthetic scan layer exactly as they would on a real imported map.

---

## Island model

The authoring surface has one flat pool of **primitive shapes** (rectangle, circle, polygon, lasso). Each shape is tagged as **add** or **subtract**. The system continuously recomputes islands from those shapes using boolean operations:

```
island polygons = connected_components(
    union(normal_adds) − union(normal_subtracts)
    ∪ union(override_adds) − union(override_subtracts)
)
```

Each connected component of the result is a separate island. Islands are never declared manually — they emerge automatically from the topology of what the user draws.

### Drawing rules

| Situation | Result |
|---|---|
| New add shape overlaps one island | Shape joins that island; polygon updated |
| New add shape overlaps no island | New island created; warning toast shown |
| New add shape overlaps two or more islands | All overlapping islands merged into one |
| Subtract shape overlaps one island | Hole carved; if result splits → two islands |
| Subtract shape overlaps two or more islands | Holes carved in all overlapping islands simultaneously |
| Subtract shape overlaps no island | Rejected (red preview, not committed) |
| Subtract shape removes all area of an island | Island deleted |

### Override mode

The default evaluation order is subtract-wins-over-add. Both add and subtract shapes have an **Override** flag that shifts them to a later evaluation step:

```
1. union(normal adds)
2. − union(normal subtracts)
3. ∪ union(override adds)       ← immune to normal subtracts
4. − union(override subtracts)  ← cuts through everything
```

Override is an escape hatch for geometry that can't be expressed with the default ordering — a bridge that must survive a surrounding cut, or a corridor that must win unconditionally.

---

## Symmetry model

### Main axis (required)

The user sets a main symmetry axis at session entry. It defines the inter-team relationship and determines how many team sectors the map has.

| Axis | Teams | Description |
|---|---|---|
| Mirror X | 2 | Reflection across Z = center_z |
| Mirror Z | 2 | Reflection across X = center_x |
| Rotate 180° | 2 | Half-turn rotation around center |
| Rotate 90° | 4 | Quadrant symmetry; only valid for four teams |

The axis may be changed at any time after session entry. Authored shapes are never moved, deleted, or modified when the axis changes — only the live preview recomputes.

### Per-island opt-out

Symmetry applies to all islands by default. The user can opt individual islands out of mirroring to introduce deliberate asymmetry. An opted-out island appears only in the authored sector; no counterpart is generated.

Example: the centre terrain is opted out so each team's approach path differs slightly. Spawn islands and wool rooms remain mirrored; the centre island does not.

This is the primary authoring affordance for controlled variation. The author designs the base layout with full symmetry active to establish parity, then opts out specific islands and adjusts them independently.

### Live preview overlay

When the main axis is active, the canvas shows mirrored or rotated copies of all participating islands as a **live overlay**. The overlay:

- Is computed in real time from authored shapes and the current axis and center.
- Is not stored as primitives and does not appear in the island tree or shape list.
- Updates immediately when the axis, center, any shape, or any per-island opt-out flag changes.
- Can be toggled on/off without affecting authored shapes.

The user is always editing only the **primary sector** — the shapes they explicitly drew. The rest of the map follows from symmetry.

### Center point

The center point is set at session entry and can be moved at any time. Moving the center does not affect authored shapes — it changes where the symmetry axis is anchored, and all mirrored previews recompute from the new center.

---

## Synthetic scan layer output

When the user is satisfied with the layout, Sketch exports a **synthetic scan layer**: the full island set (primary sector + all mirrored/rotated copies) rasterized to parquet format. Each block column covered by an island polygon is marked as solid at Y=0.

This parquet file is the same format produced by the layout extraction pipeline from a real Minecraft world. From the perspective of Teams, Build Regions, Objectives, and subsequent activities, it is indistinguishable from a scan layer derived from an imported map.

The Configure step is skipped for Sketch sessions. The three Configure outputs are produced by Sketch instead:

| Configure output | Sketch equivalent |
|---|---|
| Scan layer parquet | Synthetic scan layer from rasterized island polygons |
| Island set (with exclusions) | Islands from boolean computation; per-island opt-out serves the same role as exclusion |
| Symmetry result (confirmed axis + center) | Main axis + center from session entry |

---

## Activity structure

Sketch has three activities:

| Activity | Canvas mode | Purpose |
|---|---|---|
| **Overview** | Read-only (move + zoom) | Map name, version, authors |
| **Setup** | Center placement + move + zoom | Bounding box, center point, mirror mode |
| **Layout** | Full drawing + move + zoom | Draw islands, configure mirror participation |

**Export** is a button action, not an activity. It writes the synthetic scan layer and hands off to the main editor.

The center and mirror mode are set in Setup. The canvas in Layout reflects them immediately — the live overlay uses the Setup values. Changes to center or mirror mode in Setup recompute the live overlay in Layout if it is currently visible.

---

## Scope and constraints

- Sketch is the entry path only when no map folder has been imported.
- Intra-team secondary axes (symmetry within a single team's sector) are out of scope for the initial implementation. The architecture must not preclude adding them later.
- Sketch state (shapes, island names, axis, center, per-island opt-out flags) is serializable and restorable. The user may return to Sketch to revise the layout after having worked through downstream activities.
- The original authored shapes are retained alongside the synthetic scan layer. Re-opening Sketch restores the drawing session, not just the rasterized output.
