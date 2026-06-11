"""Tests for pgm_map_studio.schemas.persisted (the xml_data.json shape).

Hermetic — synthetic data exercising the edge cases the corpus revealed
(full-corpus validation lives in tools/validate_schemas.py per convention):
inline-region spawn refs, `"oo"` infinity coords, `None` template coords.
"""
import pytest
from pydantic import ValidationError

from pgm_map_studio.schemas.persisted import MapProject, Region, Spawn, XYZ


def test_minimal_map_validates():
    m = MapProject.model_validate({"name": "demo", "teams": [{"id": "red-team"}]})
    assert m.name == "demo" and m.teams[0].id == "red-team"


def test_spawn_region_accepts_string_id():
    s = Spawn.model_validate({"team": "red-team", "region": "red-spawn"})
    assert s.region == "red-spawn"


def test_spawn_region_accepts_inline_region():
    s = Spawn.model_validate({
        "team": "red-team",
        "region": {"id": "red-spawn", "type": "cylinder",
                   "base": {"x": 0, "y": 12, "z": 0}, "radius": 2},
    })
    assert isinstance(s.region, Region) and s.region.type == "cylinder"


def test_coord_accepts_float_infinity_literal_and_none():
    # "oo" is PGM's infinity literal (infinite-height cuboid); None is a ${template}
    r = Region.model_validate({
        "id": "tall", "type": "cuboid",
        "min": {"x": 0, "y": 0, "z": 0},
        "max": {"x": 4, "y": "oo", "z": 4},
    })
    assert r.max.y == "oo"
    assert XYZ.model_validate({"x": 1.5, "y": None, "z": "-oo"}).y is None


def test_region_requires_type():
    with pytest.raises(ValidationError):
        Region.model_validate({"id": "x", "bounds_2d": {"min": {"x": 0, "z": 0},
                                                        "max": {"x": 1, "z": 1}}})


def test_string_id_children_and_grouped_wool():
    m = MapProject.model_validate({
        "name": "m",
        "regions": {
            "a": {"id": "a", "type": "rectangle"},
            "u": {"id": "u", "type": "union", "children": ["a"]},
        },
        "wools": [{"id": "red", "color": "red",
                   "monuments": [{"id": "red-blue", "team": "blue-team",
                                  "monument_region": "blue-mon"}]}],
    })
    assert m.regions["u"].children == ["a"]
    assert m.wools[0].monuments[0].team == "blue-team"


def test_extra_fields_ignored_not_rejected():
    # advanced filter leaf params we don't type yet must not break validation
    m = MapProject.model_validate({
        "name": "m",
        "filters": {"f": {"id": "f", "type": "material", "material": "iron block"}},
    })
    assert m.filters["f"].type == "material"
