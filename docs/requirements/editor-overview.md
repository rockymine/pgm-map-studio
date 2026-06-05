# Requirements: Overview

**Semantic purpose:** Establish the map's identity as it appears in the game lobby and match announcements.

*Author goals: Who made this map? What is it called? What are players trying to do?*

---

## Sub-step 1: Map Identity

**User requirements**
- Enter the map name (displayed in the match listing and in-game).
- Enter the version string (updated on each published revision).
- Gamemode is fixed as `ctw` — pre-filled and not user-editable.
- Enter the objective text (short description shown to players at match start, e.g. "Capture the enemy's wool").

**System requirements**
- Pre-fill gamemode as `ctw` and make it read-only.
- Store: name, version, gamemode, objective text.
- Validate: name is non-empty before Overview is considered complete.

---

## Sub-step 2: Authors

**User requirements**
- Add one or more authors; at least one is required.
- For each author: provide the Minecraft account UUID (the stable identifier), select a role (`author` for primary creator, `contributor` for secondary credit), and optionally provide a contribution note (e.g. "terrain", "XML").
- Authors can be removed or reordered.

**System requirements**
- Store each author as: UUID, role, optional contribution note.
- Validate: at least one author is defined before Overview is considered complete.
- UUID is the stored identifier; display name is presentational only. System should be able to resolve a UUID to a current Minecraft display name for confirmation, but must not store display name as the identifier.

---

## Step-level system requirements

- Overview has no dependencies on other activities and is self-contained.
- Overview data (name, version, gamemode, objective text, authors) has no gameplay effect but is required for correct match listing display and attribution.
