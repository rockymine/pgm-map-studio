# Requirements: Filters

> ⚠️ **UNSTABLE / OUTDATED (2026-06-10).** This document predates the contract-first refactor and
> does not reflect the current filter/region model. The current filter↔region wiring and
> intelligent-template design lives in `docs/contracts/filter-region-wiring.md` (see plan task C9).
> Do not treat the contents below as authoritative until this notice is removed.

**Semantic purpose:** Review all spatial event rules applied so far, and configure any advanced mechanics not covered by the earlier steps. The high-prevalence rules (spawn protection, wool room access, build lockdowns) are surfaced inline during their originating activities; this step covers the complete rule audit and the remaining mechanics.

*Author goals: Are there resources that replenish? Should spawn protection expire on leaving spawn? Are there launch pads, zone-specific loadouts, or timed unlocks?*

---

## Sub-step 1: Rule Review

**User requirements**
- Review the complete set of apply rules accumulated across all prior activities.
- Inspect each rule's structure: region target, spatial event filters (enter, leave, block, block_place, block_break, block_physics, block_place_against, use), general condition, actions (kit grant, lend-kit, velocity vector, denial message).
- No authoring occurs in this sub-step — audit only.

**System requirements**
- Assemble and display the complete rule registry, with each rule attributed to its originating activity.
- Allow the user to navigate from a rule to the activity where it was defined.
- Display each rule's full structure: region ID, event filters, general condition, actions.
- All filter and region references are by ID; the system must resolve IDs to display names for readability.

---

## Sub-step 2: Block Renewal

**User requirements**
- Decide whether specific blocks in a region should regenerate after being broken — 51% of maps, most commonly iron or gold blocks at spawn.
- For each renewal: select the region, select the block type that regenerates (`renew-filter`), select what it replaces when re-spawning (`replace-filter`, typically air), set the regeneration rate.
- Must also configure the paired block drop rule for the same region: when the renewable block is broken it drops as an item and is replaced by air. Both halves must be present for the mechanic to work.

**System requirements**
- Surface block renewal prominently (51% prevalence).
- Enforce that both halves of the renewal pair are present: renewable declaration + block drop rule. Warn if either half is configured without the other.
- Store renewable: region, renew-filter (block type), replace-filter, regeneration rate.
- Store block drop rule: region, block type, drop item, replacement (air).

---

## Sub-step 3: Resistance Reset

**User requirements**
- Decide whether spawn-protection effects are revoked when players leave spawn — 16% of maps.
- If yes: the apply rule targets the complement of the spawn region; a reset kit clears the resistance effect on leave.

**System requirements**
- Surface as an optional toggle scoped to each team's spawn region.
- Store the apply rule as: target = complement of spawn region, event = leave, action = revoke resistance kit.
- Requires spawn regions to be defined (Teams dependency).

---

## Sub-step 4: Jump Pads

**User requirements**
- Define any regions that launch players on entry — 4% of maps.
- For each jump pad: define the trigger region, set the velocity vector (direction and magnitude), optionally restrict to a team or match phase.

**System requirements**
- Store each jump pad as: region, velocity vector, optional team filter, optional match phase filter.
- Apply rule: target = region, event = enter, action = apply velocity.

---

## Sub-step 5: Lend-kit Zones

**User requirements**
- Define any regions where players receive a different loadout while present, revoked automatically on exit — 2% of maps.
- For each zone: define the region, select the kit to lend, optionally restrict to a team.

**System requirements**
- Store each lend-kit zone as: region, kit reference, optional team filter.
- Apply rule: target = region, event = enter → grant kit; event = leave → revoke kit.

---

## Sub-step 6: Map Boundary

**User requirements**
- Decide whether players should be prevented from exiting the defined play area.
- If yes: identify the play boundary region.

**System requirements**
- Store a leave-denial rule on the play boundary region.
- Apply rule: target = play boundary, event = leave, action = deny.

---

## Sub-step 7: Time-gated and Variable-based Features

**User requirements**
- Optionally define actions that activate only after a set match duration (spawn kit upgrades, area unlocks) — rare (~5 maps).
- Optionally define rules gated on PGM variable values (score tracking, staged unlocks, match-phase conditions).
- For each: define the trigger condition (time filter, `after` filter, or variable filter), the apply rule, and the action.

**System requirements**
- Store time-gated rules: region, `time` or `after` filter with duration, action.
- Store variable-gated rules: region, variable reference, comparison value, action.
- Surface these as advanced authoring; they should appear after all core mechanics are configured.

---

## Step-level system requirements

- Filters depends on all prior activities; all apply rules and region definitions from prior steps are visible here.
- The filter registry is flat and shared: every named filter is reusable across any rule, referenced by ID.
- Every apply rule has the same structure regardless of which activity produced it: region, spatial event filters, general condition, actions.
