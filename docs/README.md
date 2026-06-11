# Documentation Map

Every doc here is exactly **one kind**. Mixing kinds is what made the docs confusing; keep them apart.

| Kind | Tense | Answers | Where history goes |
|---|---|---|---|
| **Spec** | present only | "what *is* true" | nowhere — git + the plan hold the past |
| **Rationale** | present | "*why* it's true" (domain, statistics) | — |
| **Requirements** | present | "what each activity needs" | — |
| **Process** | past/future | "what we did / will do" | this is the home for history |

**The rule:** a *spec never narrates its own history* — no "corrected", "decided", "still broken",
no changelog. It states what's true now. Shapes live in **typed code** (`pgm/` + the B1 view-models →
generated TypeScript); the spec docs *explain* and point at the code. When a doc and the code
disagree, **the code wins**.

---

## Spec — present-tense truth (what B1 / TypeScript derive from)

| Doc | Owns |
|---|---|
| `contracts/data-model.md` | **The entity model + API surface.** Persistence boundaries, every entity's shape, round-trip invariants. The map of the typed code. |
| `contracts/geometry.md` | Coordinate system, the +1 rule, transform formulas, the required canvas/geometry **converters** (one implementation each). |
| `contracts/region-categorization.md` | How a region's `category` + `roles` are **derived** (two-facet model). |
| `contracts/validation-invariants.md` | Editing invariants (severity, the symmetry↔team coupling, traversability). |
| `filter-use-cases.md` | The filter **vocabulary** + event×filter-type matrices. *(Its corpus statistics are research — Rationale — bundled in an appendix.)* |
| `ui/ui-conventions.md` | CSS/UI conventions; the `/design` page is the live visual reference. |

## Rationale — the *why* (feeds requirements; may carry statistics)

| Doc | Purpose |
|---|---|
| `map-data-model.md` | Activity-framed domain narrative, statistics, and the "questions that must be answered". The semantic source the requirements derive from. **Not** a second definition of shapes (those are in `data-model.md`). |
| `ctw-map-pamphlet.md` | CTW domain narrative — author goals, why constraints exist. |
| `sketch-workflow.md` | Sketch concept model (island booleans, override mode, symmetry tiers, export). |

## Requirements — per-activity (what the user/system needs)

`requirements/` — one file per activity. Editor workflow: `editor.md` (index) + `editor-*.md`.
Sketch workflow: `sketch.md` (index) + `sketch-*.md`. (`editor-filters.md` is **unstable** —
superseded by the planned `filter-region-wiring.md`, C9.)

## Process — tracking / decisions / history (history lives here, not in specs)

| Doc | Purpose |
|---|---|
| `../plans/refactor-plan.md` | **The active driver** — ordered status tracker (Workstreams A–E) + "Current focus". |
| `../plans/editor-vision.md` | Editor design vision. |
| `contracts/frontend-stack-decision.md` | The D1 target stack decision (React + TS + Vite; keep Python). |
| `ui/ui-system-consolidation.md` | UI system consolidation notes. |
| `testing.md` | How to run the Python + JS test suites. |


## Planned docs (tracked, not yet written)

`api-schemas.md` (C2) · `filter-region-wiring.md` (C9) · `project-storage.md` (B10/E1). See the plan.

## When adding a doc

1. Decide its **kind** first. If it's a spec, it must be present-tense and not duplicate another
   spec's content — point instead (one owner per topic).
2. Add a row here.
3. If it restates shapes, stop — those belong in the typed code + `data-model.md`.
