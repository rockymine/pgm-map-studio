# Region Categorization Contract

How the studio derives what a region *is* and what it's *used for*. This expands
`studio-domain-and-api-contract.md` §10 (which stated only that category is derived
with a thin spawn/wool/build/other model). It is grounded in analysis of the full
350-map CTW corpus.

Category is **derived, never persisted** (contract §4/§10). The editor's
`region_categories` map stays only as a store of **user overrides** of this derivation.

---

## 0. Why the four-bucket model is not enough

The current `_compute_categories` (in `routes/map_api.py`) categorizes ~23% of named
regions and dumps **76% into `other`**. Measured causes:

- It only tags the *referenced* region (often a top-level compound) and ignores the
  actual children — e.g. a `reds-woolroom` union is tagged but its child geometry falls
  to `other`.
- It **never reads `monument_region`** (monuments are invisible to it; in the grouped
  wool model they live at `wool.monuments[].monument_region`).
- It collapses three distinct objective roles — wool **storage**, wool **delivery**,
  wool **regeneration** — into one idea, or misses them entirely.
- It has no concept of **filter machinery**: many regions exist *only* to be a filter
  target (`negative`/`complement` wrappers like `not-spawns`, `not-build-area`) and have
  no intrinsic gameplay identity at all.

A multi-signal derivation with the model below categorizes **~91%** correctly, and the
residual `other` becomes a *meaningful* bucket (special mechanics + genuine rule targets)
rather than a dumping ground.

---

## 1. Two facets

A region has two orthogonal facets. Conflating them is the root mistake.

1. **`category`** — what the region *is* in gameplay (spatial/semantic identity).
2. **`roles`** — what the region is *used for* (rule machinery, conditional timing, the
   apply-rules/filters attached). A region may have a `category` *and* roles, or **only**
   a role (a pure filter target has no gameplay category).

The single most important rule: **a region's `category` is derived from intrinsic gameplay
signals, never from the fact that a filter is applied to it.** Filter targeting is a role.

---

## 2. `category` taxonomy

| value | meaning | primary signal |
|---|---|---|
| `spawn` | team spawn point + protected spawn area | `spawns[].region`; `enter=only-<team>` (with disambiguation) |
| `observer_spawn` | observer / `<default>` spawn | `observer_spawn.region` |
| `wool_room` | wool storage / defense | `wool_room_region`; `enter=not-<team>` (defender excluded) |
| `monument` | wool **delivery** objective | `wool.monuments[].monument_region` |
| `wool_spawner` | wool regeneration zone | `spawner.spawn_region` / `player_region` |
| `build` | buildable / traversable space (subtype `footprint` \| `traversal`) | void-structure (§5) |
| `mechanic` | special mechanic (subtype `kit` \| `shop` \| `renewable` \| …) | spawner/renewable refs, names |
| `other` | genuine uncategorized | — |

Objectives are **three categories, not one**: `wool_room` (source, defended),
`monument` (goal, delivery), `wool_spawner` (regeneration). A monument is gameplay-opposite
to a wool room and must not live under "wool".

Corpus distribution (named regions, after dropping block-targeting as a spatial signal):
`spawn` 19% · `wool_spawner` 15% · `wool_room` 14% · `monument` 9% · `build` (incl.
void-structure) · `observer_spawn` 1% · `mechanic` <2% · plus `rule_container` role 6% and
a residual `other`.

---

## 3. `roles` facet

Orthogonal flags/data attached to a region regardless of category:

- **`rule_container`** — the region exists primarily as a filter target, not as gameplay
  geometry. Always set for `negative`/`complement` regions, and for unions whose only
  signal is being a block/void apply-rule target (e.g. `not-spawns`, `not-build-area`,
  `void-area`, `no-bridges`). The editor should surface these under a "rule wiring" view,
  not as primary spawn/wool/build geometry.
- **`time_gated`** — the region's behavior is gated by an `after` / `time` / `pulse`
  filter; carries the resolved `duration`. This is how dynamic build extensions work
  (stalemate-breaker water lanes — see §5, §8). 21 corpus maps use time filters.
- **`rules`** — the apply-rules targeting the region and the filter ids they reference
  (the full rule wiring), for display and validation.

---

## 4. Derivation precedence

Assign `category` by the first matching signal (most reliable first). **Never overwrite a
category already set by a more reliable signal.**

1. **spawn** ← `spawns[].region`, **observer_spawn** ← `observer_spawn.region`. (Authoritative.)
2. **monument** ← `wool.monuments[].monument_region`.
3. **wool_spawner** ← `spawner.spawn_region` / `player_region`.
4. **wool_room** ← `wool.wool_room_region`; and ← `enter=not-<team>` rules (defender
   excluded — reliable, see §6).
5. **build** ← void-structure (§5).
6. **spawn | wool_room** ← `enter=only-<team>` rules, disambiguated: in `spawns[]` → spawn;
   monument/spawner-adjacent or wool-named → wool_room; else leave for name heuristics.
7. **mechanic** ← kit/shop/renewable references and names.
8. **name heuristics** on **primitives only** (not on `negative`/`complement`): `*spawn*`,
   `*wool*`/`*room*`/`wr`, `*monument*`, `*build*`/`*bridge*`/`*lane*` (build), etc.
9. **Constrained recursion** (§7).

Do **not** use `block` / `block-place` filter targeting as a `category` signal — record it
as a `roles.rules` entry instead. (In testing, treating it as "build" inflated build to 32%
of all regions, almost entirely false positives like `spawns` tagged build because it has an
iron-only rule.)

---

## 5. Build regions: static and time-gated

Build regions are derived from **rule structure**, not naming (`build` is <2% of regions by
name alone). PGM grants buildability to columns with a block at Y=0; authors carve buildable
space out of the void and enforce the boundary with a filter (`editor-build-regions.md`).

**Static (void-complement) — the common case.** A `negative`/`complement` region targeted by
a `void`/`never` placement filter is the enforcement wrapper (`void-area`, `not-build-area`,
`no-bridges`). It is a **`rule_container`**; its **children are the build space**:

> **build = children (recursively) of the void-enforcement negative, minus any child already
> categorized `spawn`/`wool_*`.**

This auto-captures `build-area`, `bridgeable-area`, `lanes`, `bridges`, and island footprints
without enumerating names, because they are simply "the not-void space that isn't a spawn or
wool room." Subtypes: island-like → `footprint`; bridge/lane/gap → `traversal`.

**Time-gated (dynamic).** A build region whose `block` rule is gated by an `after`/`time`/
`pulse` filter opens mid-match (anti-stalemate). Category is still `build`; add the
**`time_gated`** role with the duration. Examples: `add-water-lane` (30s), `golden_drought_vi`
`60m/80m/100m/120m`, `mame_…` `after-30m/60m/90m`.

**Pure-geometry (Approach B).** A non-buildable region with `block-place=never` and no void
filter is a `rule_container` (lockdown target), not a build region.

Caveat: a `lane` with **no** void parent and **no** rule (e.g. `ad_astra`'s `water-lanes`) is
*not* build — it's likely a movement mechanic. The structural rule correctly excludes it;
naming alone would not.

---

## 6. `enter`-filter polarity (spawn vs wool disambiguation)

`apply enter=<filter>` rules mark protected zones. Resolving the filter's team polarity:

- **`enter=not-<team>` → `wool_room`** — the team is *excluded* (defender can't enter their
  own wool room). Reliable: 50/52 = 96% in the corpus.
- **`enter=only-<team>` → ambiguous** — 447 spawn vs 445 wool_room corpus-wide. Some maps use
  `only-<owner>` to let *only* the owner into their wool room (opposite convention). Resolve
  with `spawns[]` / monument adjacency / name; otherwise leave as a neutral protected zone.

The polarity also reveals the **owning team** of a wool room (the excluded team), corroborating
the derived owner from the wool model (contract §6).

---

## 7. Compound and recursion rules

Compounds give PGM meaning and are needed for round-trip, but they break naive categorization.

- **`negative`/`complement` are containers, never spatial.** Flag `rule_container`; never
  assign them a gameplay category from their name (`not-spawns` is **not** a spawn) and never
  propagate a category into or out of them.
- **`union` recursion is constrained.** Propagate a union's category to its children **only**
  when the union's category came from an intrinsic spatial signal (e.g. a `reds-woolroom`
  union → its children are wool_room), and **never overwrite** a child's own direct category,
  and **never** recurse through a `negative`/`complement`.
- A child reached only through a `rule_container` keeps its own intrinsic category (or `other`
  + role), so wool monuments and spawn areas are never relabeled by the wrapper around them.

---

## 8. Worked examples

### `annealing_iv` (4-team)

| region | type | category | roles |
|---|---|---|---|
| `blue-spawn-point` | cylinder | spawn | |
| `blue-spawn` | rectangle | spawn | `enter=only-blue` |
| `blues-woolroom` | union | wool_room | `enter=not-blue` (blue defends), block rule |
| `blue-team-red-wool` | block | monument | |
| `blue-wool-spawn` | cuboid | wool_spawner | |
| `build-area` | union | build | |
| `not-build-area` | negative | — | `rule_container` (void enforcement) |
| `spawns` | union | spawn (from children) | `rule_container`, iron-only block rule |
| `not-spawns` | negative | — | `rule_container` |

Result: 34/35 named regions categorized; only `blocks-filter-region` is genuinely `other`.

### `icecream_sandwiched_ii` (time-gated build)

```
<any id="water-lane-building"><after id="add-water-lane" duration="30s" .../></any>
<union id="water-lanes"> → blue/red-water-lanes → lime/cyan/yellow/orange-water-lane
<apply region="building-water-lanes" block="water-lane-building" message="...void area!">
```

`water-lanes` and children → `category = build` (subtype `traversal`), `roles = {time_gated:
{duration: "30s"}, rules: [block=water-lane-building]}`. The full wiring round-trips; the model
surfaces *that it is a build region* and *that it opens after 30s*.

---

## 9. Ground-truth fixture

Curate a small, hand-verified fixture (test oracle), **not** per-map stored categories for all
350 (that would persist derived data — forbidden by the contract):

- Format: `{ region_id: { category, subtype?, roles[] } }` per map.
- Maps: `annealing_iv` (4-team, all patterns), a clean 2-team (e.g. `vertex`), a multi-wool
  2-team (e.g. `acapulco`), and a time-gated map (`icecream_sandwiched_ii`).
- The derivation is generated as a *proposed* labeling, then verified/corrected by a CTW author
  before it becomes the oracle. Tests assert the derivation matches, with a small allowlist for
  genuinely ambiguous regions.

---

## 10. Implementation notes

- Replace the thin `_compute_categories` with a typed `region_category` derivation module
  emitting `{category, subtype, roles}` per region; unit-tested on synthetic data and validated
  against the §9 fixture.
- Keep categories **derived**; `region_categories` in `xml_data.json` remains a user-override
  store only, layered on top of the derivation (overrides win).
- The `time_gated` role requires resolving `after`/`time`/`pulse` filters (already parsed) to a
  duration; reuse the filter registry.

## 11. Open edges

- `enter=only-<team>` ambiguity (spawn vs wool_room) — falls back to `spawns[]`/name; a small
  set stays neutral-protected.
- `mechanic` subtypes (kit/shop/renewable) are low-prevalence; start with a single `mechanic`
  bucket + free-text subtype rather than a rigid enum.
- Build subtype (`footprint` vs `traversal`) is best-effort from geometry/naming; not all maps
  make the distinction explicit.
