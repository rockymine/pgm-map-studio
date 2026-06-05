# CTW Map Data Model

This document describes the data that defines a valid PGM Capture the Wool map — what must be configured, what can optionally be configured, and how the pieces relate to one another. It is organised by editor activity and is intended as the foundation for contextual design, user research, workflow design, and Gherkin scenario writing.

This document does not prescribe UI, field names, or JSON structure. It describes entities, their attributes, their semantic purpose, and the questions that need to be answered to define them.

---

## The Pipeline Foundation

Before any editing begins, the pipeline runs automatically on the imported map and produces three artefacts. These are the shared foundation for all subsequent activities.

### Layout layers

The pipeline scans the Minecraft world at multiple Y levels and produces one parquet file per layer. Each layer is a 2D block snapshot of the map at that height. Island shapes and the traversability analysis are derived from one chosen layer — the **scan layer**.

**The user must choose the scan layer.** The pipeline cannot reliably determine which layer is the playable ground plane; a CTW map may have infrastructure above and below the play surface. Choosing the wrong layer produces incorrect island detection and incorrect symmetry.

The scan layer choice affects everything downstream. It is the first decision the user makes.

### Islands

From the chosen scan layer, the pipeline detects **islands** — contiguous areas of solid ground. Each island has a polygon outline, a bounding box, and a centroid. Islands are the visual canvas for all spatial editing.

Islands may be non-playable (observer tower, mid-air decorations). The user can **exclude** these from analysis without removing them from the map.

### Symmetry

From the island shapes, the pipeline infers the most likely global symmetry of the map. Detected symmetry types: `rot_90`, `rot_180`, `mirror_x`, `mirror_z`. Each candidate carries a confidence score.

The pipeline outputs a **symmetry result** with:
- Status: `unconfirmed` (pipeline output) → `confirmed` or `none` (user decision)
- Detected modes with confidence scores
- Map center point (derived from island bounds)

**The user must confirm or reject the detected symmetry.** A confirmed symmetry unlocks the region mirroring engine, which can suggest counterpart regions throughout all editing activities. Without confirmation, no mirroring suggestions are made. The user can also override the detected axis or center point.

Symmetry confirmation also enables **validation**: for a confirmed `rot_180` with 2 teams, the editor can verify that spawn positions, wool room positions, and other spatial entities satisfy the expected relationship, surfacing violations as warnings.

---

## Activity: Overview

**Semantic purpose:** Establish the map's identity as it appears in the game lobby and match announcements.

### Entities

**Map identity**
- Name — displayed in the match listing and in-game
- Version — the map's version string, updated on each published revision
- Gamemode — always `ctw` in this tool
- Objective text — the short description shown to players at match start ("Capture the enemy's wool")

**Authors**
- One or more persons credited for the map
- Each author has a Minecraft account UUID (the stable identifier) and a display role
- Role: `author` (primary creator) or `contributor` (secondary credit)
- Optional contribution note — describes what the person contributed (e.g. "terrain", "XML")

### Questions that must be answered
- What is the map called?
- Who made it, and in what capacity?

### Dependencies
None. Overview is self-contained.

---

## Activity: Teams

**Semantic purpose:** Define the competing teams and establish how and where players enter the match.

### Entities

**Teams**
Each team has:
- A unique identifier (referenced by all other entities that are team-scoped)
- A display name
- A text color (how the team name appears in chat and on the scoreboard)
- A dye color (the Minecraft color used for team-tinted items and visual indicators)
- Player count limits: minimum to start, maximum allowed

A CTW map must have at least 2 teams. The island count from the layout suggests the team count; symmetry suggests the pairing.

**Kits**
A kit is a loadout given to a player. Each kit has:
- A unique identifier (referenced by spawn definitions and apply rules)
- Inventory items: one per slot. Each item has a material, stack size, damage value (variant selector), optional enchantments, optional unbreakable flag, optional team-color-tint flag
- Armor pieces: one per slot (helmet, chestplate, leggings, boots). Same attributes as items

Kits are shared: the same kit definition may be referenced by multiple spawns. A map may define one kit per team or share a single kit across all teams.

**Spawns**
A spawn definition ties a team to the region players respawn into. Each spawn has:
- A team reference
- A kit reference (optional — players can spawn with no kit)
- A facing direction (yaw, in degrees)
- A region — the spatial volume players materialise in

Observer spawns follow the same structure but are not associated with any team. A map should define one observer spawn.

A team may have multiple spawn definitions (e.g. different sub-regions for balance); a single spawn per team is the common case.

**Spawn regions**
The spawn region is the volume players land in. Common shapes are cuboid (rectangular box) and cylinder. The region must be large enough to disperse players on respawn. In the imported XML, the region is encoded inline within the spawn definition; in the editor, it is also registered in the region registry by ID so it can be referenced by rules.

**Spawn protection rules**
Maps should restrict spawn entry to the owning team. This is an access control rule on the spawn region:
- Which team(s) are denied entry
- Optional denial message shown to the blocked player

Semantic question: *"Which team owns this spawn? Should the enemy be blocked at the boundary?"*

**Spawn right-click protection**
Maps may also lock interactive blocks (chests, crafting tables, buttons) inside spawn from the opposing team. This is a separate rule on the same or an overlapping region.

### Statistics
- 80% of maps restrict spawn entry to the owning team
- 55% add right-click protection inside spawn areas

### Dependencies
None. Teams is the first entity step.

---

## Activity: Build Regions

**Semantic purpose:** Define where players are allowed to build, and enforce that all other areas are off-limits.

### Why boundary enforcement is not optional

Without explicit rules restricting where blocks can be placed, players can place blocks anywhere in the world — including across gaps that exist for gameplay purposes (a choke point, a hole that forces players around, a strategic separation between islands). The layout guides the player experience; unrestricted building undermines it entirely.

Every CTW map enforces a build boundary. Two equivalent approaches are used in practice:

**Approach A — Positive declaration + void filter**
The author declares a `build-region` covering all areas where building is intended. The complement of that region (`not-build-region`) is where building is restricted. The void filter is applied to the not-build-region: placement is denied wherever a column has no blocks at Y=0. The void filter and the build-region geometry work together — the build-region rectangles establish the horizontal extent, the void filter enforces the precise Y=0 footprint within those rectangles.

**Approach B — Pure geometry (no void filter)**
The author defines the non-buildable area as an explicit complement or union of regions, then applies `block-place="never"` to it. No void filter is used; the geometry is the sole authority. This requires the author to be more precise in their rectangles, but produces the same gameplay result.

### The void filter and the Y=0 parquet

The `<void/>` filter is a runtime check: it evaluates true for a block event if the column beneath has no blocks at Y=0. This is exactly what the scan layer parquet captures — the Y=0 block coverage of the map. The parquet is the analysis-time snapshot; the void filter is the runtime equivalent.

A consequence: bridges and elevated structures are not detected by the void filter, because they exist above Y=0. A bridge over a gap will appear as a void column to the filter unless an invisible block (block 36) or a natural block (leaves, logs) is placed at Y=0 underneath it as a silhouette. Maps with elevated lanes either use such silhouettes or declare the lane explicitly as part of the build-region to bring it inside the buildable boundary.

This means the scan layer parquet is the best available signal for pre-populating build region candidates. What the parquet shows as covered at Y=0 is what the void filter will treat as buildable ground; what the parquet shows as empty is what the void filter will treat as off-limits.

### The primary question

Semantic question: *"Where should players be allowed to build?"* 

The answer is the build-region. Everything outside it becomes the enforced boundary. The **playable boundary** is a derived result — it is the shape implied by the build-region declarations plus the Y=0 terrain, not a configuration input in its own right.

### Entities

**Max build height**
The absolute Y ceiling above which no block placement is permitted. Enforced as a placement denial rule on the region above this ceiling — typically an `above`-type region or a `<max-build-height>` declaration.

Semantic question: *"How high can players build?"*

**Build area regions**
The explicit declarations of where players may build. Cover:
- All island footprints where building is intended
- **Traversal gaps** — the open-air space between islands that players must bridge to reach enemy territory. These gaps have no blocks at Y=0 by definition; without including them in the build-region, players cannot bridge across and the map is untraversable.
- **Elevated or floating sections** — platforms, lanes, or structures above Y=0 that the design intends players to interact with. These are transparent to the void filter unless silhouetted at Y=0.

The layout provides island outlines; gaps between islands are the traversal candidates. Symmetry can suggest counterpart build-area rectangles automatically.

**Void protection rule**
A placement denial applied to the complement of the build-region, using the void filter condition. This is how Approach A expresses the boundary: anything outside the declared build-region and without Y=0 blocks underneath is off-limits.

Approach B maps express the same intent with `block-place="never"` on an explicitly drawn non-buildable region instead.

In both cases the break rule is usually asymmetric: breaking surface blocks at the boundary edge (leaves, logs, overhanging terrain) is often still allowed, while placement into void columns is not.

**Full block lockdowns**
Regions that must remain completely uneditable can be locked regardless of build boundary rules. Common zones: observer spawn, wool spawner positions, structural features that must not be destroyed.

Variants:
- Block all editing (no placement, no breaking)
- Block placement only (breaking still allowed)

Semantic question: *"Should this region be read-only?"*

**Block physics denial**
Maps may freeze block physics events in specific regions to prevent exploit or griefing scenarios:
- Redstone propagation (prevents redstone wire updates in wool rooms)
- Water and lava flow (prevents flooding)
- Gravity and ladder physics

Semantic question: *"Should water / lava / redstone be frozen in this region?"*

**Anti-climb rules**
Maps may prevent players from stacking blocks against specific surfaces (e.g. base walls) to climb over them. Implemented as a placement denial triggered by the surface block being placed against.

Semantic question: *"Should players be blocked from climbing this surface by stacking blocks against it?"*

### Statistics
- 68% of maps have at least one fully locked region (no placement, no breaking)
- 16% freeze block physics in specific regions
- 3% use anti-climb rules to prevent stacking against specific surfaces

### Dependencies
- Layout (for island boundaries and connectivity gap detection)
- Confirmed symmetry (for counterpart region suggestions)

---

## Activity: Objectives

**Semantic purpose:** Define the CTW wools — what players must capture to win — and the spatial rules that govern access to the wool rooms.

### Entities

**Wool objectives**
Each wool objective represents one team's capture task. A wool has:
- The **owning team** — the team that must capture this wool (they go into enemy territory to steal it)
- The **wool color** — which Minecraft wool block must be retrieved (14 valid colors)
- The **wool location** — the exact block position of the wool in the enemy wool room
- The **monument location** — the exact block position where the captured wool must be placed in the owning team's base
- The **monument region** — a region enclosing the monument slot (optional; used for validation and display)
- The **wool room region** — a region enclosing the enemy wool room (used for entry rules and spawner triggers)

In a standard 2-team CTW map each team captures one wool from the other's room, giving 2 wool objectives total. Maps with more teams or multiple wools per team scale accordingly.

Symmetry can suggest counterpart wool positions when a confirmed axis is present.

**Wool room access rules**
Access rules on the wool room derive directly from the team assignment:
- The opposing team gains entry and may edit the wool room (they need to steal the wool)
- The owning team is denied entry to their own wool room (the CTW mechanic)

Semantic question: *"Which team owns this wool room?"* (All access rules follow from the answer.)

Maps may also restrict right-click events (chests, buttons, interactive blocks) inside the wool room from the owning team, and may also apply to the opposing team for certain block types.

Maps should restrict block editing inside the wool room. Common configurations:
- Team check only: only the opposing team may edit anything
- Material whitelist: only specific block types (web, wood, clay, etc.) may be placed or broken by any player
- Original state protection: players may only remove blocks they placed themselves; original map blocks are protected regardless of team

**Wool availability — how wool gets into the room**

The XML defines *where* the wool must be placed and *where* it must be delivered, but it does not guarantee that wool is actually obtainable in the room. The author must ensure at least one of the following mechanisms is present:

- **Chest**: a chest placed in the wool room world containing the wool item. No XML configuration — it is a world block. `chests.parquet` can cross-reference a given wool room region to detect whether a chest with the correct wool color is already present.
- **Renewable wool block**: a wool block placed in the world inside a `<renewable>` region, so it regenerates after being taken. Requires both a renewable declaration and a matching block drop rule (the same paired mechanic described in the Filters section). `wools.parquet` contains all wool block positions and colors.
- **PGM mob spawner**: the `<spawners>` XML element that periodically spawns sheep (or other wool-dropping mobs) inside the wool room. Each spawner has a spawn region, a player region (a player must be present to trigger it), delay between spawns, max concurrent entities, and mob type with variant. `spawners.parquet` contains spawner positions and configuration.

It is possible to define a complete and valid-looking wool objective in XML — location, monument, wool room region, all access rules — and produce a map where players have no way to obtain the wool. The wool availability check is a validation concern: does the wool room region contain a chest with the right color, a renewable wool block, or a configured spawner?

**Kit grants at wool room entry**
Maps may define a PGM kit grant for attackers entering the wool room. The chest is the more common gear delivery mechanism; `chests.parquet` gives visibility into what is stocked for any given wool room region.

Semantic question: *"How does the attacker get the wool, and do they have what they need to do so?"*

### Statistics
- 96% of maps restrict wool room entry to the opposing team
- 97% restrict block editing inside wool rooms
- 55% add right-click protection inside wool rooms
- 8% define a PGM kit grant for wool room attackers; the remainder rely on chests

### Dependencies
- Teams must be defined (wool ownership references team IDs)
- Layout and symmetry for spatial suggestions

---

## Activity: Filters

**Semantic purpose:** Review all spatial event rules applied so far, and configure any advanced mechanics not covered by the earlier steps.

### Role of filters throughout the editor

Filters are not exclusive to the Filters activity. The high-prevalence rules are surfaced inline during the steps where they are relevant:
- Spawn protection rules → Teams step
- Wool room access rules → Objectives step
- Build lockdowns and void protection → Build Regions step

The Filters activity is the final overview of the complete rule set plus the authoring surface for mechanics that do not belong to a single earlier step.

### The apply rule

Every spatial event rule has the same structure. A rule applies to a **region** and may contain any combination of:

- **Spatial event filters**: `enter`, `leave`, `block` (place + break combined), `block_place`, `block_break`, `block_physics`, `block_place_against`, `use` (right-click)
- **General condition**: an additional filter that gates kit grants and velocity effects
- **Actions**: grant a kit on entry, lend a kit (revoke on exit), apply a velocity vector, show a denial message

All filter and region references in an apply rule are by ID. Filters are separate named entities in the filter registry.

### Filter entities

A filter is a named, reusable condition that evaluates to allow, deny, or abstain. Filters are composed from:

**Combiners:** `all` (AND), `any` (OR), `one` (XOR) — take a list of child filter IDs.

**Wrappers:** `not`, `deny`, `allow` — take a single child filter ID. Wrappers modify the logical sense of the child.

**Leaf matchers** — the actual conditions:

| Category | What it tests |
|---|---|
| Team | Player is on a specific team |
| Player state | Alive, dead, participating, observing, on the ground |
| Inventory | Player is carrying / wearing / holding a specific material |
| Block | Material match; void (column is air at Y=0); event cause (player, world, explosion, trample); original-state match against a region (`blocks`); adjacent block at an offset (`offset`) |
| Match timing | Match is running / started; elapsed time; delay after another filter becomes true; periodic pulse |
| Objective | A specific wool has been captured |
| Dynamic | PGM variable matches a value or range; mob spawn event matches an entity type |
| Static | `always` (unconditional allow); `never` (unconditional deny) |

### Advanced mechanics authored in Filters

**Time-gated features:** An action that activates only after N minutes of match time. Examples: spawn kit upgrades, area unlocks. Requires a `time` or `after` filter combined with an apply rule.

**Jump pads:** A region that launches players when entered. The apply rule carries a velocity vector; direction and magnitude define the launch arc. May be filtered to a team or match phase.

Semantic question: *"Where are the jump pads? In which direction and with what force?"*

**Map boundary enforcement:** A `leave=never` rule on the play boundary region prevents players from exiting the defined play area.

**Lend-kit zones:** A region where players receive a different loadout while present — the kit is granted on entry and revoked on exit. Used for defense-vs-attack zone differentiation and temporary ability grants (e.g. resistance in a healing zone).

**Zone-based resistance reset:** Applied to the complement of the spawn region. When players leave spawn, a reset kit clears the resistance effect granted inside spawn. Requires a `not`-wrapped spawn region.

**Variable-based conditions:** PGM variables can gate apply rules. Used in score-tracking mechanics, staged unlocks, and match-phase-dependent rules.

**Block renewal:** Specific block types in a region may be configured to regenerate automatically after being broken. This mechanic is not tied to any single activity — the renewal region can be any named region (a spawn bounding box, a wool room, a mid-map resource area). The common case in CTW is iron or gold blocks at spawn, but the mechanic is general.

Block renewal must be configured as a pair of two declarations:
- A **renewable**: scoped to a region, specifying the block type that regenerates (`renew-filter`), what it replaces (`replace-filter`, typically air), and the regeneration rate.
- A **block drop rule**: scoped to the same region, specifying that when the renewable block is broken it drops the item and is replaced by air. Without this, the block either stays as a floating item or is not re-queued for regeneration.

Removing either half breaks the mechanic.

Semantic questions: *"Which blocks should regenerate? In which region? At what rate?"*

### Statistics
- 51% of maps use block renewal (most commonly iron or gold blocks at spawn)
- 16% apply a zone-based resistance reset when players leave spawn
- 4% use velocity-based jump pads
- 2% use lend-kit zones for area-specific loadouts
- ~5 maps use time-gated features

### Dependencies
- All prior activities contribute filter definitions and apply rules visible here
- Regions must be defined before they can be referenced in rules

---

## Activity: Regions

**Semantic purpose:** Audit the complete spatial registry. Verify that every region has been assigned and that no regions are missing or mispositioned.

This activity does not author new regions. All regions are created during the steps above.

### The region registry

Every named region in the map lives in a flat registry keyed by ID. Composite regions reference their children by ID — there is no nesting. Anonymous child regions receive stable synthetic IDs derived from their parent.

**Where regions come from:**
- Spawn volumes → Teams
- Wool room enclosures, monument regions → Objectives
- Build areas, lockdown zones, void protection zones → Build Regions
- Spawner positions, jump pad zones, boundary regions → Filters / advanced rules
- Any region present in the imported XML that no editor step claimed

**Region types:**

| Family | Types | Key spatial attributes |
|---|---|---|
| Primitive | rectangle | 2D bounding box on the XZ plane |
| | cuboid | 3D min + max corners |
| | cylinder | base point, radius, height |
| | circle | center (XZ), radius |
| | sphere | origin, radius |
| | block / point | single position |
| Composite | union, negative, complement, intersect | list of child region IDs |
| Transform | mirror | source region ID + reflection axis (origin + normal) |
| | translate | source region ID + offset vector |
| Special | half | origin + normal (half-space) |
| | above | Y threshold |
| | everywhere | unbounded |
| | reference | alias to another region ID |

Transform regions (mirror, translate) are how confirmed symmetry is expressed in the XML — a mirror region is the counterpart of its source, defined by the symmetry axis.

### Region composition

Apply rules predominantly target composite regions rather than individual primitives. Composites serve three distinct roles:

**1. Grouping for shared rules (union)**
Multiple primitive regions may be grouped under a named union so that a single apply rule covers all of them. Examples: `spawns` (groups all team spawn cuboids — one rule protects all of them), `red-wool-rooms` / `blue-wool-rooms` (groups all wool room rectangles for a team — one rule locks them all), `void-area` (groups the full playable boundary for a single placement denial rule).

This is the primary reason composite regions exist: without grouping, every individual rectangle would need its own copy of every rule that applies to it. A 4-team map with 4 wool rooms would need 4 identical entry rules instead of one rule on a `woolrooms` union.

**2. Inversion for boundary rules (negative / complement)**
Instead of listing everything that should be denied, the author may list everything that should be allowed (the positive region) and invert it.

- `negative` wraps a single child (almost always a union) and means "everywhere except that child". Negative regions are nearly always rule targets rather than intermediate building blocks. The canonical build boundary is `<negative id="not-build-region"><union id="build-region">...</union></negative>`, with the apply rule targeting `not-build-region`.
- `complement` takes an ordered list: the first child is the outer space, the remaining children are subtracted from it. Often uses `everywhere` as the first child. Used when the boundary shape is more complex than a simple inversion — e.g. subtracting specific islands from the full world, or carving a hole out of a region.

**3. Building blocks (non-targeted composites)**
A composite may exist solely to be combined into a larger composite that carries the rule. Examples: a per-team `blue-wool-rooms` union built from individual room rectangles, itself a child of a global `woolrooms` union that the rule targets. A `build-region` union that is the sole child of a `not-build-region` negative. These intermediate composites are named for clarity but the rule lands on the outer composite.

**Intersect — geometric precision**
Intersect produces the overlap of its children and may be used for precise spatial clipping — most often combining half-spaces (`half`) with rectangles or `above` thresholds to define wedge-shaped or bounded volumes.

**Nesting depth**
Composites nest freely. A union may contain other unions — recursive grouping is common for multi-team maps where per-team groups are collected into an all-teams parent. The flat registry stores each composite once with its children referenced by ID; nesting is expressed by ID chains, not embedded objects.

### Statistics
- 58% of apply rules target composite regions; 40% target primitive regions (197 maps, 2 401 rules)
- Negative regions: 92% carry a direct apply rule — they are almost never intermediate building blocks
- Union regions: 56% carry a direct apply rule; 44% are intermediate building blocks only
- Complement regions: 48% carry a direct apply rule
- Intersect regions: 68% carry a direct apply rule
- Mirror / translate regions: 15–20% carry a direct apply rule; the remainder are children within targeted unions

**What the Regions activity surfaces:**
- All regions with their type, bounds, and which activity/entity owns them
- Unassigned regions — present in the imported XML but not claimed by any editor step; these require manual inspection
- Symmetry violations — regions that should be paired by the confirmed symmetry axis but whose counterpart is missing or outside tolerance

### Dependencies
All prior activities. Regions is the terminal audit step.

---

## Cross-Cutting: Symmetry and the Mirroring Engine

Once symmetry is confirmed, the mirroring engine can propose counterpart regions whenever a new region is defined in any activity. The user confirms or rejects each proposal individually — there is no batch accept.

Symmetry suggestions are configurable per region type. Example: the user may enable mirroring for spawn regions and wool room regions, but disable it for the mid-island build area (which may be intentionally asymmetric).

The mirroring engine uses the confirmed axis and center point to compute the transform. The counterpart is expressed as a `mirror` or `translate` region in the registry, not as a duplicate primitive — this preserves the intent and makes the relationship explicit.

---

## Validity

A map is exportable when all of the following hold:

| Condition | Activity responsible |
|---|---|
| At least 2 teams defined | Teams |
| Each team has at least one spawn | Teams |
| Each team has at least one wool objective | Objectives |
| Each wool has a monument position | Objectives |
| Islands are connected (players can reach enemy wool room from spawn) | Build Regions |
| No unresolved round-trip conflicts (imported XML has unknown elements the editor cannot re-serialize) | Export |

All other configuration is optional or carries a default.
