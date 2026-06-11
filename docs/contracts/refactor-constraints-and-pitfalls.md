# Refactor Constraints And Pitfalls

This document records the practical constraints behind the next refactor or migration pass.

It is not a schema spec. It is a strategy and risk note for future implementation work.

---

## 1. Current Reality

The current tool is not being built from theory. It was built by inspecting real processed map data and using imported maps as the development corpus.

That has been useful and should not be thrown away.

Important consequences:

- the current activity split exists because the imported data made the workflow visible
- `xml_data.json` is currently the closest thing to the full imported-map contract
- the app is still partly an explorer for existing maps, even though it is becoming an editor
- round-tripping back to valid XML is a hard requirement

The refactor should preserve those strengths instead of treating the current implementation as disposable.

---

## 2. What Is Still Missing

These are the major missing pieces that affect contract design, not just UI completeness.

### 2.1 Symmetry-aware editor authoring

Symmetry is already a core model.

Current state:

- imported maps persist symmetry in `symmetry.json`
- sketch uses symmetry actively for mirrored / rotated geometry

Missing state:

- editor-side authoring support for symmetry-aware regions
- for 2-team and 4-team maps, authors should eventually be able to define one source entity and derive the counterparts from the selected symmetry axis

This matters for:

- regions
- filters
- apply rules
- objectives
- spawn-linked structures

This is not optional metadata. It is part of the domain.

### 2.2 Filters and apply rules

These are currently underrepresented in the UI but are part of the target tool.

The contract pass must include them, even if the full editor UI is not built yet.

Risk:

- if the contract is finalized before filters / apply rules are modeled, the migration will likely harden the wrong shape and create another rewrite

### 2.3 Region composition authoring

The data model already includes composition concepts:

- union
- complement
- negative
- intersect
- grouping / ungrouping style workflows

Missing state:

- robust UI authoring flows for these operations
- clear editor contract for source regions, child references, anonymous children, and undoable transformations

---

## 3. Main Strategic Question

Should the missing pieces be implemented in the current tool before a larger refactor?

The answer is probably:

- do not fully finish the current UI just for its own sake
- but do model the missing data and API shapes before locking a new architecture

In other words:

- full feature-complete old-UI implementation is probably wasteful
- undefined contract areas are dangerous

The right threshold is:

- enough implementation or inspection to know what the real data shape must be
- not necessarily a polished end-user flow for every missing feature

---

## 4. Recommended Order

### 4.1 Inspect and formalize what already exists in `xml_data.json`

Before a migration:

- enumerate all major top-level collections and nested structures
- especially filters and apply-rule related data
- record which fields are XML-facing, which are editor-facing, and which are derived

### 4.2 Decide the symmetry authoring contract

This must be answered early:

- when the author creates one region on a symmetric map, are counterpart regions persisted explicitly?
- or is one source region persisted together with a symmetry relation? 

NOTE: mirror / translate region types exist and could be auto-computed, they already have a parent region

That choice has cascading effects across the editor.

### 4.3 Define rule contracts before rewriting the frontend

Even if filters are not fully wired in the current UI, the contract for them should be explicit before a Next.js migration begins.

### 4.4 Only then stabilize the API boundary

Once the missing high-impact areas are modeled:

- freeze request/response shapes
- keep `xml_data.json` as the imported-map persistence truth for now
- treat view-model endpoints as adapters around that truth

---

## 5. Pitfalls To Avoid

### 5.1 Treating the current tool as throwaway

That would lose:

- hard-won knowledge from real processed maps
- the activity split
- actual observed edge cases

### 5.2 Finalizing a contract too early

If symmetry-driven authoring, filters, and compound region authoring are still vague, the contract will be brittle.

### 5.3 Inventing a new persistence layer too early

The project already has a practical persistence layer:

- imported-map persistence through `xml_data.json`
- sketch persistence through `sketch.json`

The immediate need is not another storage concept. The immediate need is to define stable contracts around the current one.

### 5.4 Breaking XML round-tripping

The final system must still produce valid XML with correctly connected references and rule wiring.

Anything that makes the editor model more convenient but weakens round-tripping is the wrong trade.

NOTE: the round-trip is only PARTIALLY working (verified Phase 1, 2026-06-10).
`map.xml → MapXml → map.xml` (in-memory, via parser + xml_writer) IS solid across the corpus.
But `xml_data.json → MapXml` (the deserializer) is BROKEN for wools: `serializer.to_dict` writes
grouped wools while `deserializer.from_dict` reads flat (`d['monument']`) → KeyError, and four
tests in `tests/pgm/test_deserializer.py` fail today. It is latent only because no imported-map →
XML export route is wired yet. Repairing the JSON↔datamodel round-trip (grouped wools, region
`source_id` resolution, inline-child removal, spawn-as-reference) is a hard prerequisite before
any XML export ships. See `data-model.md` §0 and §13.

### 5.5 Replacing discovered domain behavior with idealized abstractions

The real maps came first. The abstractions should be derived from the map corpus and the XML model, not imposed on top of them.

---

## 6. Practical Guidance For Claude

When continuing this work, Claude should:

1. inspect actual `xml_data.json` samples, not just route code
2. trace how current JSON maps back to XML expectations
3. identify unresolved data-shape questions in:
   - symmetry
   - filters
   - apply rules
   - compound regions
4. propose contracts only after seeing the real payload shapes
5. avoid broad framework rewrite work until those areas are documented

---

## 7. Bottom Line

The main risk is not that the current app is imperfect.

The main risk is freezing the wrong contract before the missing domain-heavy pieces are modeled.

So the next pass should optimize for:

- understanding the real JSON model completely
- preserving XML round-trip requirements
- defining symmetry, rule, and compound-region contracts

Only after that should the frontend migration become the main focus.

