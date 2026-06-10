# Contract-First Migration Plan

This plan is the starting point for the next major refactor / migration pass.

It is intentionally short. The detailed context lives in:

- [`docs/contracts/studio-domain-and-api-contract.md`](../docs/contracts/studio-domain-and-api-contract.md)
- [`docs/contracts/refactor-constraints-and-pitfalls.md`](../docs/contracts/refactor-constraints-and-pitfalls.md)

The goal is to stabilize the data and API boundary before changing frameworks or porting the UI.

---

## Main direction

Do not start with a frontend rewrite.

Do not assume the current contract is already solved.

Do not invent a new persistence layer first.

Start by understanding and documenting the current truth:

- actual API routes already in use
- actual `POST`, `PATCH`, `DELETE`, and `GET` payload shapes
- actual `xml_data.json` structures from processed maps
- actual `sketch.json` structures
- actual XML round-trip requirements

The current imported-map truth is still `xml_data.json`.

The current sketch truth is still `sketch.json`.

Those are the starting points for the contract work.

---

## Claude instructions

Claude should ask the author as many questions as needed to nail the contract down.

The point of this phase is not to be fast. The point is to remove ambiguity.

Claude must inspect for himself:

1. the existing Flask routes
2. the frontend API calls already used by the current app
3. actual `xml_data.json` examples from processed maps
4. actual `sketch.json` session files
5. the current service layer that reads, mutates, and writes these files

Claude should not rely only on existing docs or route names. He should verify payload shapes and structures from the code and sample data.

---

## Sequence

### Phase 1: Documentation first

Produce and refine contract docs before changing the implementation architecture.

Priority docs:

1. domain model
2. API schemas
3. XML round-trip rules
4. symmetry contract
5. filters and apply-rules contract

The first pass already exists in the `docs/contracts/` folder and should be reviewed, challenged, and tightened.

### Phase 2: Typed data models

Once the docs are stable enough:

- define typed backend models for the contract
- separate persisted models, derived models, and UI view-models

This should happen before any major framework migration.

### Phase 3: API stabilization

After the data models are defined:

- align the route payloads with the documented contract
- normalize error envelopes
- keep XML round-tripping intact

The storage target can still be JSON files at this stage. Database work can come later.

### Phase 4: UI migration

Only after the data layer and API boundary are stable:

- port or replace the backend/frontend architecture as needed
- keep the existing HTML/CSS/UI patterns where possible
- avoid reinventing the design system unnecessarily

The existing HTML, CSS, and much of the current frontend behavior may still be reusable even if the backend stack changes.

---

## High-priority unresolved areas

These must be part of the contract pass, not deferred away:

- symmetry as a first-class model
- symmetry-aware editor authoring
- filters
- apply rules
- compound regions
- group / ungroup / union / complement / negative editing flows

If these are left vague, the migration will freeze the wrong contract and force another rewrite later.

---

## Repository strategy

Stay in this repository.

Use a long-lived branch or worktree for migration work.

Do not start from a blank new repo unless there is a very strong reason to do so.

This repo already contains:

- the real map corpus knowledge
- current route behavior
- current JSON structures
- UI conventions
- sketch/editor integration work

That context is too valuable to throw away.

---

## Success condition for this phase

This phase is successful when:

- the contract docs are concrete enough that there are few or no structural open questions left
- symmetry, filters, and rules are accounted for in the contract
- the backend data model can be typed cleanly
- the API can be treated as stable enough for a future frontend migration

Only then should a bigger framework move become the main workstream.

