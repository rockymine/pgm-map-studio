"""Fixture-driven attribution tests for sketch_export._assign_shape_ids.

Each JSON file in tests/fixtures/attribution/ describes a shape scenario
using the same layout.shapes format as a saved sketch, plus an expected
section with per-island assertions. The same fixtures are consumed by the
JS Vitest suite to verify JS/Python parity.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import Point

from pgm_map_studio.studio.services.sketch_export import (
    _assign_shape_ids,
    _compute_island_polys,
)

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "attribution"


def _load_fixtures():
    return sorted(FIXTURE_DIR.glob("*.json"))


@pytest.mark.parametrize("fixture_path", _load_fixtures(), ids=lambda p: p.stem)
def test_attribution_fixture(fixture_path):
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    shapes = fixture["layout"]["shapes"]
    expected = fixture["expected"]

    island_polys, add_union, after_sub, after_override_add = _compute_island_polys(shapes)

    assert len(island_polys) == expected["island_count"], (
        f"{fixture['name']}: expected {expected['island_count']} islands, "
        f"got {len(island_polys)}"
    )

    ids_per = _assign_shape_ids(shapes, island_polys, add_union, after_sub, after_override_add)

    for assertion in expected["islands"]:
        sx, sz = assertion["sample_point"]
        pt = Point(sx, sz)
        idx = next(
            (i for i, poly in enumerate(island_polys) if poly.contains(pt)),
            None,
        )
        assert idx is not None, (
            f"{fixture['name']}: no island contains sample point ({sx}, {sz})"
        )
        contributors = ids_per[idx]
        for sid in assertion.get("must_contain", []):
            assert sid in contributors, (
                f"{fixture['name']}: island at ({sx},{sz}) missing '{sid}' "
                f"in contributors {contributors}"
            )
        for sid in assertion.get("must_not_contain", []):
            assert sid not in contributors, (
                f"{fixture['name']}: island at ({sx},{sz}) incorrectly contains '{sid}' "
                f"in contributors {contributors}"
            )
