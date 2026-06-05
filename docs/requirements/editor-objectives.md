# Requirements: Objectives

**Semantic purpose:** Define the CTW wools — what players must capture to win — and the spatial rules that govern access to the wool rooms.

*Author goals: Where is the wool? Where must it be delivered? Who can enter the wool room, and what can they do there? Can the attacker actually get the wool?*

---

## Sub-step 1: Wool Objective Placement

**User requirements**
- Define one wool objective per team capture task. Standard case: 2 objectives for a 2-team map (each team captures one wool from the other's room).
- For each wool objective:
  - Select the owning team (the team that must capture this wool — they go into enemy territory to steal it).
  - Select wool color (one of 14 valid Minecraft wool colors).
  - Set wool location — the exact block position of the wool in the enemy wool room.
  - Set monument location — the exact block position where the captured wool must be placed in the owning team's base.
  - Define monument region — a region enclosing the monument slot (optional but used for validation and display).
  - Define wool room region — a region enclosing the enemy wool room (required; used for entry rules and spawner triggers).

**System requirements**
- If symmetry is confirmed, offer to mirror a wool objective's spatial positions to derive the counterpart team's objective.
- Validate: each team has at least one wool objective with a monument position before export.
- Wool location and monument location are single block positions. Monument region and wool room region are spatial volumes.

---

## Sub-step 2: Wool Room Access Rules

**User requirements**
- Confirm team ownership of each wool room (all access rules derive from this single answer).
- Entry rule: confirm that the opposing team gains entry and the owning team is denied — 96% of maps enforce this. Optionally set a denial message.
- Block editing rule: confirm editing restrictions inside the wool room — 97% of maps restrict this. Choose variant:
  - Team check only: only the opposing team may edit anything.
  - Material whitelist: only specific block types (web, wood, clay, etc.) may be placed or broken.
  - Original state protection: players may only remove blocks they themselves placed; original map blocks are protected regardless of team.
- Optionally add right-click protection on interactive blocks (chests, buttons) inside the wool room — 55% of maps.
- Optionally define a kit grant for attackers entering the wool room — 8% of maps; the remainder rely on chests.

**System requirements**
- Surface entry rule and editing rule inline as near-universal defaults (96–97% prevalence).
- Surface right-click protection inline but secondary (55% prevalence).
- Surface kit grant as optional/advanced (8% prevalence).
- Store entry rule as: wool room region, denied team (owning team), optional denial message.
- Store editing rule as: wool room region, variant (team-check / material-whitelist / original-state).
- Store right-click rule as: wool room region, denied team(s).
- Store kit grant as: wool room region, enter trigger, kit reference.

---

## Sub-step 3: Wool Availability Check

**User requirements**
- Review whether the wool is actually obtainable in each wool room. A wool objective can be fully configured in XML — location, monument, wool room region, all access rules — and still be unreachable if no delivery mechanism is present.
- For any room without a detected mechanism, choose at least one:
  - **Chest** — a chest placed in the wool room world containing the wool item. A world build choice with no XML counterpart.
  - **Renewable wool block** — a wool block in the room inside a `<renewable>` region, regenerating when taken. Requires both a renewable declaration and a matching block drop rule; both halves must be present.
  - **PGM mob spawner** — periodically spawns wool-dropping mobs. Configure: spawn region, player presence region (a player must be present to trigger it), spawn delay, max concurrent entities, mob type and variant.

**System requirements**
- Cross-reference each wool room region against `chests.parquet` to detect existing chests containing the matching wool color.
- Cross-reference each wool room region against `wools.parquet` to detect existing wool block positions and colors.
- Cross-reference each wool room region against `spawners.parquet` to detect configured spawners.
- Surface a warning for any wool room where none of the three mechanisms is detected.
- If a mob spawner is configured: store spawn region, player presence region, spawn delay, max concurrent entities, mob type and variant.

---

## Step-level system requirements

- Depends on: Teams (wool ownership references team IDs), layout and symmetry (for spatial suggestions).
- The wool availability check is a validation concern, not just a configuration one: it requires parquet cross-reference at validation time.
- Connectivity check (can a player reach this wool room from spawn?) is a joint responsibility of Build Regions and Objectives; surface at export validation if not already caught inline.
