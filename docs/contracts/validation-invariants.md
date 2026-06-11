# Editing Validation Model & Invariants (B11)

Status: **design pass, locked 2026-06-10** (rockymine review). This is the *what* — the catalog of
invariants the typed models (B1–B4) encode and the editor surfaces. **Enforcement code is
Workstream C**; this doc decides the rules and their severity, grounded in the 345-map corpus
(`/tmp/pipeline_out` 197 + `/tmp/publicmaps_out` 148).

Companion: symmetry shapes + `team_orbit`/`team_count_compatible`/`wool_count_compatible`/
`requires_square_cell`/`is_lattice_exact` live in `pgm_map_studio.symmetry.datatypes`; the symmetry
model itself is `data-model.md` §7.

## Posture **[decision — Q1]**

Editing is **iterative**, so a map is routinely *transiently* invalid mid-edit. Therefore:

- **WARN (default):** violations surface as **non-blocking inline guards / a readiness checklist**.
  The author is never stopped from reaching a transient invalid state. "Is this a complete, playable,
  *regular* symmetric CTW" is a checklist, not a gate.
- **HARD (referential integrity only):** the editor refuses actions that would **dangle a
  reference** — deleting a team/filter/region still referenced elsewhere (already enforced for
  filters/apply-rules in C3/C4 via reject-with-references), or writing a reference to a non-existent
  id. These are data-corruption, not authoring-incompleteness.
- **ENGINE-PRECONDITION:** the **auto-mirror / counterpart / team-scaffold** engine *requires* the
  strict symmetry coupling (Group C) to run. It doesn't block manual editing — it just won't *offer*
  auto-generation when the relationship doesn't hold.

Severity tags below: **[HARD]**, **[WARN]**, **[ENGINE]**.

---

## Group A — Structural integrity **[HARD]**

Broken data, not incomplete authoring. Corpus violations are genuine source defects.

| Invariant | Holds | Counterexample |
|---|---|---|
| Team `id` non-empty **and** unique within the map | 344/345 | `kytriak_te` — two teams with empty `""` ids |
| Wool `color` non-empty **and** unique per map (it is the group key) | **345/345** | — (structurally enforced by grouped-by-colour keying) |
| `monument.team` references an existing team | 344/345 | `kytriak_te` — monuments name `red`/`blue`, but team ids are `""` |
| A monument belongs to exactly one wool; monument teams are **distinct within a wool** (a team captures a colour at most once) | — | — |
| Every cross-reference resolves: spawn→region, wool/monument→team, apply/filter/renewable/block-drop→filter/region (C3/C4) | enforced | — |

Owner/defender team stays **derived**, never stored (`all_teams − capturing_teams`; see contract §6,
the 5c rule) — it is a *computed* field, so it has no integrity rule of its own.

---

## Group B — CTW completeness **[WARN]**

"Is this a finished, playable CTW?" — surfaced as a readiness checklist. Real maps violate these
transiently (mid-build) and a few violate them by design (minigames/arcade), so none hard-block.

| Invariant | Holds | Notes / counterexample |
|---|---|---|
| Map has **≥2 teams** | 344/345 | `easter_egg_hunt` (1 team) — a non-CTW minigame |
| Map has **≥1 wool**; every team **owns ≥1 wool colour** | 345/345 | every map with teams has wools |
| Each wool has **≥1 monument** (else uncapturable = dead objective) | 341/345 | the 4 misses are all the parse-broken `segment` map |
| Each wool is **obtainable** (a source: spawn region / spawner dispensing it / block-drop / renewable) | — | this is **C12** (wool-availability); referenced here, owned there |
| The **objective chain is traversable** — each team can physically run spawn → enemy wool → return | — | spatial/connectivity analysis (see below); heavy, own feature |
| Each **team has ≥1 spawn** | 338/345 | 7 misses: `kytriak_te`, `molcein`, `banana_split` — warn, do not block |
| Map is a **supported symmetric CTW** (5c): every colour has exactly one defender, every team both attacks and defends | 332/345 | the 13 are meaningful — arcade shared-wool (`quadrosphere`, `tebulas_ii`), assigned-subset gimmicks (`two-quarter`, `new_life_ctw`); warn as "non-standard", never block |

### Objective-chain traversability **[WARN — spatial analysis]** *(rockymine 2026-06-10)*

The hardest completeness signal: a map is **unwinnable** if a team cannot actually *retrieve* an
enemy wool, even when every structural rule above holds. The full capture chain — **spawn → reach
each enemy wool the team must obtain → return it to the team's monument** — must be physically
runnable. It decomposes into:

- **A. Obtainable** — the wool can be picked up at all (a real source exists). This is **C12**
  (wool-availability).
- **B. Reachable & returnable** — a physical route exists from the team's spawn to each required
  wool room and back to its monument, given **map geometry + build regions**:
  - **island connectivity** (`islands.json`) — which islands are joined, and which gaps are
    *bridgeable* vs hard voids;
  - **build / void enforcement** (build-regions step + `layer_y0.parquet`) — where a player may
    build a crossing vs where the void/`deny` filters stop them (a stone-bottom map with no build
    region between islands is **not** crossable — cf. the B5 build-mechanics domain notes);
  - **route gating** — team-only / locked / time-gated regions along the path.

This is a **graph/path problem**, not an inline guard — connectivity over islands + buildable gaps,
with the build-region and void model as edge constraints. It is **WARN** and **aspirational**: it
needs real spatial analysis and is best treated as its own feature (it depends on the island graph,
the build-regions model, and C12). Catalogued here so the readiness model accounts for it; not a
near-term inline check.

The regular CTW shape (for the readiness summary): **`wool_count = k · team_count`** (k colours per
team — usually k=1; k=2 for the 4-team-8-wool maps `corrupted_paradise`, `forgotten_kingdom`,
`old_life`, `philosophers_stone`) and **`monuments-per-wool = team_count − 1`** (every non-owner
captures). Verified up the whole chain: 2t→1, 3t→2, 4t→3, 5t→4 (`ruedigers_pentawool`), 6t→5
(`thunderbolt`), 8t→7 (`octawool`/`summertime`/`road_trip`).

---

## Group C — Symmetry ↔ team/wool coupling **[WARN + ENGINE]**

The strict relationship below is the **definition of a *regular* symmetric CTW** (Q2 = strict
divisibility). Per the posture it is **WARN** for manual editing (arcade/gimmick/in-progress maps are
flagged non-standard, not rejected) and an **ENGINE precondition** for auto-mirroring/scaffolding.

Let `order(mode)` be the **team orbit** (`symmetry.datatypes.team_orbit`): `2` for the four
reflections and `rot_180`, `4` for `rot_90`, and `n` for a general `rot_<360/n>`.

1. **Team count** — `team_count_compatible(mode, n_teams)`: `n_teams` is a positive multiple of
   `order(mode)` (and `≥ order`). So `rot_90 ⇒ %4` (both corpus rot_90 maps, `annealing_iv` +
   `corrupted_paradise`, are exactly 4 teams), reflections/`rot_180 ⇒ %2`, `rot_120 ⇒ %3`, etc.
2. **Wool count** — `wool_count_compatible(n_wools, n_teams)`: `n_wools` is a positive multiple of
   `n_teams` (the `k`-colours-per-team relationship above).
3. **Square center cell** — `requires_square_cell(mode)`: `rot_90` and the diagonals
   (`mirror_d1`/`mirror_d2`) **swap X↔Z**, so they need a square center cell (`1x1`/`2x2`);
   axis-aligned mirrors and `rot_180` accept any cell (B7). Confirmed: both rot_90 maps are `2x2`.

### General n-fold rotation `rot_n` **[decision — Q3: model it]**

Odd / non-{2,4}-team maps are real (`tridente` 3t, `ruedigers_pentawool` 5t, `thunderbolt` 6t) and
their symmetry is **n-fold rotation** (`rot_120`/`rot_72`/`rot_60`), now first-class in the
vocabulary. **Crystallographic restriction** (`is_lattice_exact`): only **2- and 4-fold** rotation
and reflections are *exact* on the square block grid; `rot_3`/`rot_5`/`rot_6`/`rot_8` are necessarily
**approximate** — hand-built, counterparts **baked to concrete geometry** (no clean PGM mirror, no
pixel-perfect guarantee). So `rot_n` (n∉{2,4}) is **authorable + modeled** but the mirror engine
treats it as bake-only, and the readiness checklist marks it "approximate symmetry".

---

## What this gates / what follows

- **Gates B1–B4:** the typed models encode these invariants as their validity predicates (the
  symmetry helpers already exist; teams/wools/monuments get the Group A/B predicates).
- **Enforcement (Workstream C):** inline guards, the readiness checklist, and the
  auto-mirror/scaffold preconditions are implemented over the typed models. C12 owns wool-availability.
- **Follow-ups (not this pass):** `rot_n` **detection** (n∉{2,4}; needs island data to verify);
  `rot_n` + secondary-axis **sketch authoring UI** (D-series); **objective-chain traversability**
  analysis (island connectivity + build/void edges + C12) — its own spatial-analysis feature.

## Corpus reference (345 maps)

```
team count : 1→1(easter_egg_hunt)  2→306  3→2  4→31  5→1  6→1  8→3
wool count : 1→4  2→94  3→5  4→215  5→1  6→16  7→1  8→8  10→1
mons/wool  : 0→4(segment)  1→1057  2→25  3→124  4→8  5→6  7→24  12→1(tebulas_ii)
colour uniqueness : 345/345 (no map repeats a wool colour)
```
