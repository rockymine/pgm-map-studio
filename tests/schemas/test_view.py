"""Tests for pgm_map_studio.schemas.view + the generated TS contract.

Two guarantees:
- **conformance**: the pydantic view models accept what the studio encoder
  actually emits (so the typed contract matches reality);
- **no drift**: the checked-in frontend/src/contract.ts equals the generator's
  output (a schema change without regeneration fails here).
"""
import importlib.util
from pathlib import Path

import pytest
from pydantic import ValidationError

from pgm_map_studio.schemas import Bounds, RegionTreeNode, RegionTreeResponse
from pgm_map_studio.studio.services.region_encoder import encode_region_tree

_ROOT = Path(__file__).resolve().parents[2]


# ── basic model behaviour ───────────────────────────────────────────────────────

def test_bounds_round_trips():
    b = Bounds(min_x=0, min_z=0, max_x=10, max_z=4)
    assert b.model_dump() == {"min_x": 0, "min_z": 0, "max_x": 10, "max_z": 4}


def test_region_tree_node_requires_core_fields():
    with pytest.raises(ValidationError):
        RegionTreeNode(id="x", type="rectangle")  # missing label/bounds/coords/...


def test_region_tree_node_recursive_children():
    node = RegionTreeNode(
        id="u", type="union", label="u", bounds=None, coords={}, is_negative=False,
        synthetic_id=False, source=None,
        children=[RegionTreeNode(id="r", type="rectangle", label="r",
                                 bounds=Bounds(min_x=0, min_z=0, max_x=1, max_z=1),
                                 coords={}, is_negative=False, synthetic_id=False,
                                 children=[], source=None)],
    )
    assert node.children[0].id == "r"


# ── conformance: the schema accepts the real encoder output ─────────────────────

def test_encoder_output_validates_against_schema():
    regions = {
        "blue-spawn": {"id": "blue-spawn", "type": "rectangle",
                       "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 10, "z": 4}}},
        "spawns": {"id": "spawns", "type": "union", "children": ["blue-spawn"],
                   "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 10, "z": 4}}},
        "build-area": {"id": "build-area", "type": "rectangle",
                       "bounds_2d": {"min": {"x": -5, "z": -5}, "max": {"x": 5, "z": 5}}},
        "not-build": {"id": "not-build", "type": "negative", "children": ["build-area"]},
    }
    categories = {"blue-spawn": "spawn", "spawns": "spawn",
                  "build-area": "build", "not-build": "other"}
    bbox = {"min_x": -50, "min_z": -50, "max_x": 50, "max_z": 50}

    groups = encode_region_tree(regions, categories, bbox)
    parsed = RegionTreeResponse.model_validate({"groups": groups, "bounding_box": bbox})

    # the union node carries its rectangle child; the negative node is flagged
    spawn_group = next(g for g in parsed.groups if g.name == "spawn")
    spawns_node = next(n for n in spawn_group.regions if n.id == "spawns")
    assert spawns_node.children[0].id == "blue-spawn"
    other_group = next(g for g in parsed.groups if g.name == "other")
    assert other_group.regions[0].is_negative is True


# ── no drift: generated TS matches the schemas ──────────────────────────────────

def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "gen_ts_contract", _ROOT / "tools" / "generate_ts_contract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generated_ts_contract_is_up_to_date():
    expected = _load_generator().render()
    actual = (_ROOT / "frontend" / "src" / "contract.ts").read_text(encoding="utf-8")
    assert actual == expected, (
        "frontend/src/contract.ts is stale — run `python tools/generate_ts_contract.py`"
    )
