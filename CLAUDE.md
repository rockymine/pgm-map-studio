# CLAUDE.md

## UI

All UI work must follow `docs/ui-conventions.md`.

Key rules — read the doc for full detail:

- **CSS file split:** game-agnostic patterns → `components.css`. Editor/game-aware patterns → `editor.css`. Tokens → `tokens.css`. Design-page helpers → `design.css`.
- **Selectors:** use classes for styling, IDs for JS references only. Never use an ID selector to express a shared layout pattern.
- **Tokens:** never hardcode a color, spacing, radius, or transition that has a CSS variable in `tokens.css`.
- **Workspace layout:** use `.workspace`, `.workspace-sidebar`, `.workspace-inspector`, `.workspace-scroll`, `.workspace-canvas`. Do not repeat these properties on ID selectors.
- **Components:** check `/design` before writing any new CSS. If the class exists, use it. If it doesn't, add it to the right CSS file and add a demo to `/design` in the same change.
- **Buttons:** four variants only — `.action-btn`, `--primary`, `--danger`, `.btn-remove`.
- **Badges:** one system — `.badge` with `--success`, `--warning`, `--error`, `--neutral`, `--dim`.
- **Notifications:** four types only — `#topbar-error`, `.toast`, `.canvas-hint`, `.panel-warning`.

The `/design` page (start the app, navigate to `/design`) is the living visual reference.

## Tests

- Framework: pytest (`pytest` from project root)
- One test file per source file, mirroring `src/pgm_map_studio/` under `tests/`
- File naming: `test_<source_filename>.py`
- Function naming: `test_<thing>_<condition>`
- Fixtures in `conftest.py` — synthetic data only, no real game files
- Integration tests (real `.mca` files) go in `tools/`, not `tests/`

See `docs/testing.md` for full rationale and examples.

## Package READMEs

Every package under `src/pgm_map_studio/` gets a `README.md` covering: purpose, module listing, key concepts, and a usage example.
