# CLAUDE.md

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
