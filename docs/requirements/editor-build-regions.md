# Requirements: Build Regions

**Semantic purpose:** Define where players are allowed to build, and enforce that all other areas are off-limits.

*Author goals: Where can players build? Which gaps are bridgeable? What must remain untouched?*

---

## Sub-step 1: Max Build Height

**User requirements**
- Optionally set the maximum Y level above which no block placement is permitted.
- If unset, no vertical ceiling is enforced.

**System requirements**
- Store the max build height as a Y value.
- On export, encode as a placement denial rule on the above-threshold region.

---

## Sub-step 2: Build Area Declaration

**User requirements**
- Declare one or more build area regions covering all areas where building is intended. Must include:
  - Island footprints where building is intended.
  - Traversal gaps — the open-air space between islands players must bridge to reach enemy territory. Without these, players cannot cross and the map is untraversable.
  - Elevated or floating sections above Y=0 that players are intended to interact with (transparent to the void filter unless explicitly declared or silhouetted at Y=0).
- Choose which boundary enforcement approach to use:
  - **Approach A** — positive declaration + void filter: declare the build region, apply void filter to its complement.
  - **Approach B** — pure geometry: draw the non-buildable area explicitly, apply `block-place="never"` with no void filter.

**System requirements**
- Pre-populate island footprints from the included islands detected in Configure; user confirms or adjusts bounding rectangles.
- Surface gaps between included islands as traversal candidates — highlight connectivity gaps the user may want to include as bridgeable traversal regions.
- If symmetry is confirmed, offer to mirror each declared build area region to its counterpart.
- Store each build area region with its bounds.

---

## Sub-step 3: Boundary Enforcement

**Approach A — void filter + positive declaration**

*User requirements*
- Review the derived complement of the declared build region (everything outside).
- Confirm that a void filter placement denial is applied to the complement.

*System requirements*
- Derive the not-build-region as the negative/complement of the declared build regions.
- Store a placement denial rule: target = not-build-region, condition = void filter (deny placement in any column with no block at Y=0).
- Cross-reference the scan layer parquet: columns empty at Y=0 inside the not-build-region define the enforcement footprint.

**Approach B — pure geometry**

*User requirements*
- Draw the non-buildable region explicitly as a complement or union of shapes.

*System requirements*
- Store the non-buildable region and a `block-place="never"` denial rule with no void filter condition.

**Both approaches**

*System requirements*
- Surface break-rule asymmetry as a configurable option: breaking surface blocks at boundary edges (leaves, logs, overhanging terrain) is commonly still permitted even where placement is denied.
- Validate: the build boundary allows traversal from each team's spawn to the enemy wool room region (connectivity check). Surface as a warning if connectivity is not satisfied.

---

## Sub-step 4: Lockdowns and Physics

**User requirements**
- Mark specific regions as fully locked (no placement, no breaking) — 68% prevalence. Common zones: observer spawn, wool spawner positions, structural features that must not be destroyed.
- Optionally mark regions as placement-only locked (breaking still allowed).
- Optionally freeze block physics in specific regions (redstone propagation, water/lava flow, gravity/ladder physics) — 16% prevalence. Common zone: wool rooms.
- Optionally add anti-climb rules to prevent players from stacking blocks against specific surfaces — 3% prevalence.

**System requirements**
- Surface full lockdown inline as a common configuration (68% prevalence); physics freeze and anti-climb are secondary and optional.
- Store each lockdown rule as: region, variant (full / placement-only).
- Store each physics freeze rule as: region, physics event types frozen (redstone / water+lava / gravity / ladder).
- Store each anti-climb rule as: region, surface block material being placed against.

---

## Step-level system requirements

- Depends on: layout (island outlines, gap detection from Configure), confirmed symmetry (for mirror suggestions).
- The scan layer parquet is the primary input for pre-populating island footprints and evaluating void filter coverage.
- Connectivity validation (spawn → enemy wool room) requires wool room regions from Objectives; this check may surface as a cross-step validation at export time rather than inline.
