"""Tests for pgm_map_studio.schemas.sketch (the sketch.json shape).

Hermetic — the crucial guarantee is that the cubic-Bézier control model
survives validation AND re-serialization unchanged: dict keyed by stringified
vertex index, with the `in`/`out` alias intact. The realistic shapes mirror the
fixtures in tests/studio/test_sketch_export.py (no real-sketch corpus exists —
sketches are user-local).
"""
import pytest
from pydantic import ValidationError

from pgm_map_studio.schemas.sketch import (
    BezierControl,
    Shape,
    SketchProject,
    SketchSetup,
)


# ── bezier controls: the part that must not silently degrade ────────────────────

def test_bezier_control_in_alias_loads_and_dumps_as_wire_key():
    bc = BezierControl.model_validate({"in": [1.0, 2.0], "out": [3.0, 4.0]})
    assert bc.in_ == [1.0, 2.0] and bc.out == [3.0, 4.0]
    # round-trips back to the literal "in" wire key (not "in_")
    assert bc.model_dump(by_alias=True, exclude_none=True) == {
        "in": [1.0, 2.0], "out": [3.0, 4.0]
    }


def test_bezier_control_handles_are_optional():
    assert BezierControl.model_validate({"out": [1.0, 1.0]}).in_ is None
    assert BezierControl.model_validate({"in": [1.0, 1.0]}).out is None


def test_polygon_controls_keyed_by_string_vertex_index_round_trip():
    raw = {
        "id": "p1", "type": "polygon",
        "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]],
        "controls": {
            "0": {"out": [3, 0]},          # out-handle of edge 0→1
            "1": {"in": [7, 0], "out": [10, 3]},
        },
    }
    s = Shape.model_validate(raw)
    assert set(s.controls.keys()) == {"0", "1"}
    assert s.controls["1"].in_ == [7.0, 0.0]
    # the controls dict survives a full by-alias round-trip with "in"/"out" keys
    dumped = s.model_dump(by_alias=True, exclude_none=True)
    assert dumped["controls"] == {
        "0": {"out": [3.0, 0.0]},
        "1": {"in": [7.0, 0.0], "out": [10.0, 3.0]},
    }


# ── shape types ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw", [
    {"id": "r", "type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 10, "max_z": 10},
    {"id": "c", "type": "circle", "center_x": 0, "center_z": 0, "radius": 5},
    {"id": "l", "type": "lasso", "vertices": [[0, 0], [10, 0], [5, 9]]},
])
def test_each_shape_type_validates(raw):
    assert Shape.model_validate(raw).type == raw["type"]


def test_shape_requires_type():
    with pytest.raises(ValidationError):
        Shape.model_validate({"id": "x", "min_x": 0})


def test_shape_operation_and_override_default():
    s = Shape.model_validate({"type": "rectangle"})
    assert s.operation == "add" and s.override is False


# ── setup + whole project ───────────────────────────────────────────────────────

def test_setup_mirror_mode_rejects_unknown_value():
    SketchSetup.model_validate({"mirror_mode": "rot_90"})       # ok
    with pytest.raises(ValidationError):
        SketchSetup.model_validate({"mirror_mode": "mirror_d1"})  # not a sketch mode


def test_full_sketch_project_mirrors_export_fixture():
    # shape of a real sketch.json (cf. tests/studio/test_sketch_export.py)
    m = SketchProject.model_validate({
        "id": "abc-123",
        "name": "Demo",
        "authors": [{"uuid": "u1", "name": "rocky", "contribution": "design"}],
        "setup": {
            "bbox": {"min_x": -100, "min_z": -100, "max_x": 100, "max_z": 100},
            "center": {"cx": 0, "cz": 0},
            "mirror_mode": "rot_180",
        },
        "layout": {
            "shapes": [
                {"id": "s1", "type": "rectangle",
                 "min_x": 10, "max_x": 50, "min_z": 10, "max_z": 50},
            ],
            "islands": [{"id": "isl_a", "name": "Alpha", "mirrors": True,
                         "shapeIds": ["s1"]}],
        },
        "export_slug": "demo-abc12345",
    })
    assert m.setup.mirror_mode == "rot_180"
    assert m.layout.islands[0].shapeIds == ["s1"]
    assert m.authors[0].name == "rocky"
