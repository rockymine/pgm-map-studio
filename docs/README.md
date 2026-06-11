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
| `contracts/filter-region-wiring.md` | How filters attach to regions (the wiring relationship) + the v1 suggestion templates. |
| `contracts/api-schemas.md` | HTTP contract: success/error **envelopes**, error codes, naming & REST-vs-RPC conventions, route-family index. |
| `contracts/region-authoring.md` | The region **authoring** surface (B4a): the primitives/composed/raw split view-model, per-activity building blocks, the group→engine-wires loop, the command/shortcut model. |
| `filter-use-cases.md` | The filter **vocabulary** + event×filter-type matrices. *(Its corpus statistics are research — Rationale — bundled in an appendix.)* |
| `contracts/ui-conventions.md` | CSS/UI conventions; the `/design` page is the live visual reference. |

## Tool overviews

Brief goal + activity structure for each workflow live **code-adjacent**:
`src/pgm_map_studio/studio/README.md` to understand the tool.

## Requirements — per-activity (what the user/system needs)

`requirements/` — one file per activity. Editor workflow: `editor.md` (index) + `editor-*.md`.
Sketch workflow: `sketch.md` (index) + `sketch-*.md`. (`editor-filters.md` is **unstable** —
superseded by `filter-region-wiring.md`, C9.)

## Process — tracking / decisions / history (history lives here, not in specs)

| Doc | Purpose |
|---|---|
| `../plans/refactor-plan.md` | **The active driver** — ordered status tracker (Workstreams A–E) + "Current focus". |
| `contracts/frontend-stack.md` | The D1 target stack decision (React + TS + Vite; keep Python). |
| `testing.md` | How to run the Python + JS test suites. |


## Planned docs (tracked, not yet written)

`api-schemas.md` (C2) · `project-storage.md` (B10/E1). See the plan.

## When adding a doc

1. Decide its **kind** first. If it's a spec, it must be present-tense and not duplicate another
   spec's content — point instead (one owner per topic).
2. Add a row here.
3. If it restates shapes, stop — those belong in the typed code + `data-model.md`.
