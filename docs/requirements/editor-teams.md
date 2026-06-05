# Requirements: Teams

**Semantic purpose:** Define the competing teams and establish how and where players enter the match.

*Author goals: Who are the teams? Where do they start? What do they carry? Can the enemy walk into their spawn?*

---

## Sub-step 1: Team Definition

**User requirements**
- Define one or more teams; at least 2 are required for a valid map.
- For each team: assign a unique identifier (referenced by all subsequent entities), display name, text color (how the team name appears in chat and on the scoreboard), dye color (Minecraft color for team-tinted items and visual indicators), minimum player count to start, maximum player count allowed.

**System requirements**
- Suggest team count based on the number of included islands from the Configure step (2 islands → suggest 2 teams; 4 → 4).
- Store: team identifier, display name, text color, dye color, min players, max players.
- Validate: at least 2 teams are defined before Teams is considered complete.
- Enforce unique identifiers across teams; team IDs are the global reference for every subsequent activity.

---

## Sub-step 2: Kit Definition

**User requirements**
- Define one or more kits; a kit may be shared across teams.
- For each kit: assign a unique identifier, define inventory items per slot (material, stack size, damage/variant value, optional enchantments, optional unbreakable flag, optional team-color-tint flag), define armor pieces per slot (helmet, chestplate, leggings, boots — same attributes as items).
- A map may define one kit per team or a single shared kit for all teams.

**System requirements**
- Store each kit as: identifier, inventory slots (item attributes per slot), armor slots (item attributes per slot).
- Enforce unique kit identifiers.
- Allow a single kit to be referenced by multiple spawn definitions.

---

## Sub-step 3: Spawn Placement

**User requirements**
- Define at least one spawn per team.
- For each spawn: select the owning team, define the spawn region (the spatial volume players materialise in — cuboid or cylinder), optionally select a kit, set facing direction (yaw in degrees).
- Define an observer spawn with no team association (region + facing direction).
- A team may have multiple spawn definitions; one per team is the common case.

**System requirements**
- Store each spawn as: team reference, kit reference (optional), facing direction, region.
- If symmetry is confirmed, offer to mirror a defined spawn region to the counterpart team's position.
- Validate: each team has at least one spawn before Teams is considered complete.
- Surface a warning if a spawn region's bounds are below a minimum area threshold (too small to disperse players).

---

## Sub-step 4: Spawn Access Rules

**User requirements**
- For each spawn region, decide whether the opposing team is denied entry — default yes (80% of maps enforce this).
- If denied: optionally set a denial message shown to the blocked player.
- Optionally add right-click protection on interactive blocks (chests, crafting tables, buttons) inside the spawn region (55% of maps).

**System requirements**
- Surface spawn entry protection inline as the near-default choice (80% prevalence); must not be buried in the Filters step.
- Surface right-click protection inline but secondary to entry protection (55% prevalence).
- Store each spawn entry rule as: target region, denied team(s), optional denial message.
- Store each right-click protection rule as: target region, denied team(s).

---

## Step-level system requirements

- Teams depends on no prior authoring activity but receives island count and symmetry result from Configure.
- All team identifiers defined here are the shared reference namespace for all subsequent activities.
