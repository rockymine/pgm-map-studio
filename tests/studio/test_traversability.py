"""Hermetic tests for services.traversability (validation-invariants §B).

The navigability map = walkable surface ∪ bridgeable buildable; the map is
traversable iff every spawn + wool lands in one connected component. (Real-map
behaviour is in tools/traversability_preview.py.)
"""
from pgm_map_studio.studio.services.traversability import check_traversability

BBOX = (0, 0, 25, 25)


def _rect(x0, z0, x1, z1):
    return {"type": "rectangle", "bounds_2d": {"min": {"x": x0, "z": z0}, "max": {"x": x1, "z": z1}}}


def test_connected_when_surface_links_spawn_and_wool():
    data = {"regions": {"sp": _rect(0, 0, 4, 4), "wr": _rect(20, 20, 24, 24)},
            "spawns": [{"team": "red", "region": "sp"}],
            "wools": [{"color": "red", "location": {"x": 22, "y": 1, "z": 22}}]}
    surface = {(x, z) for x in range(25) for z in range(25)}       # full walkable floor
    r = check_traversability(data, surface, None, BBOX)
    assert r["connected"] is True and r["component_count"] == 1 and r["severity"] == "ok"


def test_bridgeable_gap_keeps_it_connected():
    # a void gap (no surface) between spawn and wool, but it's buildable → bridgeable
    data = {"regions": {"sp": _rect(0, 0, 4, 4), "wr": _rect(20, 20, 24, 24)},
            "spawns": [{"team": "red", "region": "sp"}],
            "wools": [{"color": "red", "location": {"x": 22, "y": 1, "z": 22}}]}
    surface = {(x, z) for x in range(5) for z in range(25)} | {(x, z) for x in range(20, 25) for z in range(25)}
    r = check_traversability(data, surface, None, BBOX)   # no block rules → gap is buildable
    assert r["connected"] is True


def test_warns_when_never_wall_disconnects():
    # a `never`-build wall with no surface splits spawn from wool → not bridgeable
    data = {"regions": {"sp": _rect(0, 0, 4, 4), "wr": _rect(20, 20, 24, 24), "gap": _rect(5, 0, 20, 25)},
            "spawns": [{"team": "red", "region": "sp"}],
            "wools": [{"color": "red", "location": {"x": 22, "y": 1, "z": 22}}],
            "apply_rules": [{"region": "gap", "block": "never"}]}
    surface = {(x, z) for x in range(5) for z in range(25)} | {(x, z) for x in range(20, 25) for z in range(25)}
    r = check_traversability(data, surface, None, BBOX)
    assert r["connected"] is False and r["severity"] == "warning"
    assert r["component_count"] >= 2 and len(r["isolated"]) >= 1
