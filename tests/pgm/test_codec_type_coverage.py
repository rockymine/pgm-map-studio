"""Cross-layer type-coverage guard for the imported-map domain (B2).

The pgm domain (`regions.py`, `filters.py`, `datatypes.py`) is the typed
imported-map model. This test pins the property that makes it a *contract*: the
xml_data.json codec round-trips every domain region/filter type back to its own
class — so the three layers (domain dataclasses ↔ serializer ↔ deserializer)
cannot silently drift. Add a new region/filter type without wiring both encode
and decode, and this fails.

(Per-field behaviour is covered by test_serializer.py / test_deserializer.py;
this is the completeness/no-degradation guarantee.)
"""
import pytest

from pgm_map_studio.pgm import filters as F
from pgm_map_studio.pgm import regions as R
from pgm_map_studio.pgm.deserializer import _decode_filter, _decode_region
from pgm_map_studio.pgm.serializer import _encode_filter, _encode_region

# One valid instance per concrete Region type (primitives need real coords so
# bounds_2d/derived fields populate). Missing a subclass here fails the parity test.
_REGION_SAMPLES = {
    R.Rectangle:  R.Rectangle(id="r", min_x=0, min_z=0, max_x=4, max_z=4),
    R.Cuboid:     R.Cuboid(id="r", min_x=0, min_y=0, min_z=0, max_x=4, max_y=8, max_z=4),
    R.Cylinder:   R.Cylinder(id="r", base_x=0, base_y=0, base_z=0, radius=2, height=3),
    R.Circle:     R.Circle(id="r", center_x=0, center_z=0, radius=2),
    R.Sphere:     R.Sphere(id="r", origin_x=0, origin_y=0, origin_z=0, radius=2),
    R.Block:      R.Block(id="r", x=1, y=1, z=1),
    R.Point:      R.Point(id="r", x=1, y=2, z=3),
    R.Union:      R.Union(id="r", children=["a", "b"]),
    R.Negative:   R.Negative(id="r", children=["a"]),
    R.Complement: R.Complement(id="r", children=["a"]),
    R.Intersect:  R.Intersect(id="r", children=["a", "b"]),
    R.Mirror:     R.Mirror(id="r", source_id="a", normal_x=1.0),
    R.Translate:  R.Translate(id="r", source_id="a", offset_x=5.0),
    R.Half:       R.Half(id="r", normal_y=1.0),
    R.Reference:  R.Reference(id="r", ref_id="a"),
    R.Everywhere: R.Everywhere(id="r"),
    R.Above:      R.Above(id="r", y=64.0),
}

# FilterRef models `<filter id="ref"/>`: the parser resolves it to a child id and
# never registers it, so it is by-design absent from the persisted codec.
_PARSER_INTERNAL_FILTERS = {F.FilterRef}


def test_region_samples_cover_every_concrete_type():
    assert set(_REGION_SAMPLES) == set(R.Region.__subclasses__()), (
        "Region subclasses and the round-trip samples have drifted — add a sample "
        "for any new region type (and wire its encode/decode)."
    )


@pytest.mark.parametrize("cls", list(_REGION_SAMPLES), ids=lambda c: c.__name__)
def test_region_type_round_trips_to_its_class(cls):
    decoded = _decode_region(_encode_region(_REGION_SAMPLES[cls]))
    assert type(decoded) is cls, (
        f"{cls.__name__} degraded to {type(decoded).__name__} through the codec"
    )


@pytest.mark.parametrize(
    "cls",
    sorted(set(F.Filter.__subclasses__()) - _PARSER_INTERNAL_FILTERS, key=lambda c: c.__name__),
    ids=lambda c: c.__name__,
)
def test_filter_type_round_trips_to_its_class(cls):
    # every persistable filter type carries its own tag and reconstructs by it
    decoded = _decode_filter(_encode_filter(cls(id="f")))
    assert type(decoded) is cls, (
        f"{cls.__name__} degraded to {type(decoded).__name__} through the codec"
    )


def test_filterref_is_parser_internal_not_persisted():
    # Guard the invariant so it isn't "fixed" by adding a decode branch: a
    # persisted type="filter" intentionally decodes to the base Filter, never FilterRef.
    assert F.FilterRef in F.Filter.__subclasses__()
    assert F.FilterRef().filter_type == "filter"
    decoded = _decode_filter({"id": "f", "type": "filter"})
    assert type(decoded) is F.Filter
