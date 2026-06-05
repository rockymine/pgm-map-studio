# CTW Map — Domain and Authoring

---

## Part 1: Domain

### What is a Capture the Wool map?

CTW is a team-based gamemode built on PGM, a Minecraft competition framework. Two or more teams compete on a shared map. Each team must retrieve a specific wool block from inside enemy territory and carry it back to place at their monument. The first team to complete all their objectives wins.

The map is the arena. It defines where players spawn, where the wools are hidden, how space is divided, and what rules govern player interaction with the world. Everything that happens during a match — where players can go, what they can build, what equipment they carry — is encoded in the map's configuration.

---

### Layout and space

A CTW map occupies a Minecraft world. At its foundation is the ground plane — the layer of solid blocks at Y=0 — which defines what is on the map. Areas with solid ground at Y=0 are the islands: the spawn platforms, the wool room structures, the connecting terrain. Areas without ground at Y=0 are the void: the gaps between islands, and space beyond the map's edges.

This distinction shapes the entire play experience. Islands connected by bridgeable gaps produce a map where teams can engage across open space. A gap that cannot be bridged is a permanent barrier. The ground plane is not just terrain — it is the map's navigational grammar.

Most CTW maps are symmetric. A 180° rotation or a mirror reflection maps one team's half onto the other's. Symmetry is a fairness constraint: it ensures neither team has a structural advantage. It also makes the map predictable to read — what is true on one side is true on the other.

---

### Teams

A CTW map defines two or more teams. Each team has an identity — a name, a color, a dye color for tinted items, and player count limits — and a home territory on the map: a spawn and a monument.

Players enter the match through a spawn region, the spatial volume where they materialise on joining or respawning. Spawns are linked to kits — the full loadout a player receives on entry: every item, every armor piece, enchantments, material variants. A map may define one kit per team or share a single kit across all teams.

Teams are the root reference for the entire map. Every spatial rule, every objective, every access restriction derives from team identity in some way.

---

### The build boundary

Minecraft permits block placement anywhere by default. A CTW map must explicitly define where players are allowed to build, because the gaps between islands are not decorative — they are gameplay features. A gap that requires bridging creates exposure and risk. A hole that forces movement around it shapes routes. Without a build boundary, these features can be trivially bypassed.

The build boundary is defined by declaring the positive — the regions where building is intended — and enforcing a denial everywhere outside it. The mechanism that makes this precise is the void filter: a runtime check that denies block placement in any column without solid ground at Y=0. The Y=0 ground plane and the void filter are two expressions of the same fact, one at analysis time and one at runtime.

Bridges and elevated structures above Y=0 are invisible to the void filter unless silhouetted at ground level with an invisible marker block. An elevated lane intended as a traversal path must either be silhouetted or declared explicitly as a build region.

Beyond the outer boundary, specific zones may be locked entirely — observer spawns, spawner structures, map features that must survive intact. Physics events (water flow, redstone propagation) may be frozen in sensitive areas such as wool rooms.

---

### Objectives

Each team is assigned one or more wool objectives. A wool objective has four spatial components: the **wool location** (where the wool block sits in the enemy wool room), the **monument location** (where the captured wool must be placed in the team's own base), the **monument region** (the area surrounding the monument slot), and the **wool room region** (the enclosing space of the enemy wool room).

The wool room is the heart of the CTW gamemode. It is the territory each team must defend from the enemy and that each team must penetrate to win. The defining rule of CTW is that a team cannot enter its own wool room — only the opposing team may go in. This single constraint produces the central asymmetry of the game: every player is simultaneously an attacker on one side of the map and a defender on the other.

Wool must actually be obtainable in the room. The XML configuration defines where the wool must be delivered and where it must come from, but it does not guarantee that wool exists. A wool room may be stocked via a chest containing the wool item (a world build choice, no XML required), via a renewable wool block that regenerates when taken, or via a PGM mob spawner that periodically produces wool-dropping mobs. It is possible to define a complete and correct-looking wool objective and produce a room from which the wool cannot be obtained.

---

### Rules

Rules are what give a CTW map its character beyond the basic objectives. They govern who can go where, what can be built, what equipment is given, and what happens when players cross boundaries.

Every rule has the same structure: a region it applies to, the spatial events it responds to (entering, leaving, placing a block, breaking a block, right-clicking), and an action or denial. The region may be a single primitive shape or a composite — a named group of several primitives, an inversion of a declared area, or the overlap of two shapes. Grouping is what makes rules maintainable: a single entry rule on a `wool-rooms` union covers every wool room on the map without duplication.

Filters are the conditions that rules evaluate. They test the current event and player state: which team the player is on, what material is involved, whether the column beneath is void, whether a specific wool has already been captured. Filters compose freely — a complex condition is built from simpler named conditions, reused across multiple rules.

The rules collectively encode the designer's intentions: this spawn belongs to this team, this wool room is off-limits to its owners, these blocks regenerate when broken, this zone launches players in a specific direction.

---

## Part 2: Authoring

### What the pipeline gives you

Before authoring begins, the map's world files are analysed automatically. The pipeline produces three outputs that inform every subsequent decision.

The **scan layer** is a snapshot of the map's block data at a chosen Y level, revealing where islands are and where the gaps between them lie. The author must confirm which Y level represents the true ground plane — the pipeline cannot determine this reliably, because a map may have infrastructure above and below the play surface.

**Islands** are detected from the scan layer: contiguous areas of solid ground, each with an outline and bounding box. Non-playable islands — an observer tower, a decorative platform — should be excluded so they do not distort the analysis.

**Symmetry** is inferred from the island shapes. The pipeline proposes a symmetry type and center point; the author confirms or rejects it. A confirmed symmetry enables the editor to suggest counterpart regions automatically throughout the authoring process and to validate that the finished map satisfies the geometric relationship it implies.

---

### Identity

The first authoring step establishes the map's identity: name, version, gamemode, and the short description shown to players at match start. Authors are credited by Minecraft account UUID, with a role (author or contributor) and an optional note describing their contribution.

These fields are static metadata with no gameplay effect. They are required for the map to appear correctly in match listings and for proper attribution.

*Author goals: Who made this map? What is it called? What are players trying to do?*

---

### Teams and spawns

The author defines one entry per team: name, color, dye color, and player count limits. The island layout and confirmed symmetry guide the team count — two islands suggest two teams; four suggest four.

Each team receives a kit and a spawn. The kit is the complete loadout for that team. The spawn is a spatial region — the volume players appear in — linked to the kit and a facing direction.

Spawn access rules follow directly: which team owns each spawn, and whether the opposing team is denied entry at the boundary. A spawn may also have right-click protection on chests and interactive blocks inside it.

*Author goals: Who are the teams? Where do they start? What do they carry? Can the enemy walk into their spawn?*

---

### Build boundary

The author's primary spatial task is declaring where players are allowed to build. This is expressed as one or more build regions covering the islands and any intended traversal gaps. Everything outside these declarations becomes the enforced boundary.

The authoring question is one of intent: which gaps between islands should players be able to bridge? Including a gap in the build region makes it a traversal point. Excluding it makes it a permanent barrier. Elevated areas above Y=0 also need explicit declaration if players are meant to build there.

A maximum build height may be set to cap vertical construction. Additional lockdowns may be placed on specific regions — full lockdowns (no placement or breaking), physics freezes (no water flow, no redstone propagation), and anti-climb restrictions on specific surfaces.

*Author goals: Where can players build? Which gaps are bridgeable? What must remain untouched?*

---

### Objectives

For each team the author places a wool objective, requiring four spatial decisions: where the wool sits in the enemy room, where the monument slot is in the team's base, what region encloses the monument, and what region encloses the wool room.

Once the wool room region is established, access rules follow directly from team ownership. The opposing team gains entry; the owning team is excluded. Block editing rules protect the room's structure. Right-click protection may be added for chests and interactive blocks.

The author must also ensure the wool is obtainable. The most direct approach is placing a chest in the room containing the wool item — this is a world build choice with no XML counterpart. Alternatively, a renewable wool block or a PGM mob spawner can provide the wool. The pipeline can cross-reference the wool room region against the world data to detect which mechanisms are already present.

*Author goals: Where is the wool? Where must it be delivered? Who can enter the wool room, and what can they do there? Can the attacker actually get the wool?*

---

### Rules and advanced mechanics

The authoring steps above cover the rules present in nearly every CTW map. What remains is the mechanics specific to this map's design.

**Block renewal**: specific blocks in a region (typically iron or gold at spawn) regenerate after being broken. Requires a renewable declaration and a matching block drop rule — both must be present for the mechanic to work.

**Resistance reset**: players lose spawn-protection effects when they leave the spawn area. Applied to the complement of the spawn region.

**Jump pads**: regions that apply a velocity vector to players on entry, launching them in a defined direction and magnitude.

**Lend-kit zones**: regions where players receive a different loadout while present, revoked automatically on exit.

**Time-gated features**: actions or unlocks that activate only after a set duration into the match.

**Map boundary**: a leave-denial on the play boundary that prevents players from exiting the defined area entirely.

*Author goals: Are there resources that replenish? Should spawn protection expire on leaving spawn? Are there launch pads, zone-specific loadouts, or timed unlocks?*

---

### What makes a map complete

A map is ready to export when the following hold: at least two teams are defined, each team has a spawn, each team has at least one wool objective with a monument position, and the build boundary allows players to reach the enemy wool room from their spawn. All other configuration is optional or carries a default.

A map that meets these conditions can be exported as a valid `map.xml`.
