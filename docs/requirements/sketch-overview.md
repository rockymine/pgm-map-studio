# Requirements: Sketch — Overview

**Semantic purpose:** Establish the map's identity before layout begins.

**Canvas mode:** Read-only — move and zoom only. No drawing or placement.

---

## User requirements

- Enter map name, version, and objective text.
- Add one or more authors with Minecraft account UUID, role (`author` / `contributor`), and optional contribution note.

## System requirements

- Store: name, version, gamemode (fixed `ctw`), objective text, authors.
- Resolve UUID to display name for confirmation; UUID is the stored identifier.
- Validate: name non-empty, at least one author, before Sketch is considered complete.
- Canvas renders the current island layout (if any) as a read-only reference; no interaction beyond pan and zoom.

---

## Dependencies

None. Overview is self-contained and has no dependency on Setup or Layout.
