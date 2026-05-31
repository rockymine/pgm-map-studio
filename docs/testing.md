# Testing conventions

## Framework

pytest with pytest-cov for coverage.

## Structure

Tests live in `tests/`, mirroring `src/pgm_map_studio/` — one test file per source file under a matching subfolder:

```
tests/
├── conftest.py              # shared fixtures (temp dirs, synthetic map folders, etc.)
├── minecraft/
│   ├── conftest.py          # fixtures scoped to this module
│   ├── test_region_reader.py
│   ├── test_block_scan.py
│   ├── test_colors.py
│   ├── test_wool.py
│   └── test_sources.py
├── layout/
│   └── ...
```

## Naming

- Test files: `test_<source_filename>.py`
- Test functions: `test_<thing_under_test>_<condition>`, e.g. `test_normalize_wool_color_handles_spaces`

## Running

```bash
pytest
```

Configured via `[tool.pytest.ini_options]` in `pyproject.toml` — no flags needed.

## Fixtures

Fixtures in `conftest.py` build the minimum synthetic structure needed (e.g. a temp directory shaped like a valid map folder) rather than shipping real game data files.

Extractor tests that require real Anvil `.mca` files are integration tests. These live in `tools/` as manual scripts and are not part of the `pytest` suite.
