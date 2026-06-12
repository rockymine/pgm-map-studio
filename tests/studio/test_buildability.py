"""Hermetic tests for services.buildability.compute_buildability (C14).

Synthetic maps exercise each verdict source on a small explicit bbox: never,
deny(void) × the Y=0 layer, the region-as-filter gate, a global (region-less)
rule, and a restricted team filter. (Real-map oracles live in tools/ +
tests/fixtures/, per the corpus-tool convention.)
"""
from pgm_map_studio.studio.services.buildability import CLASSES, compute_buildability

BBOX = (0, 0, 10, 10)


def _rect(x0, z0, x1, z1):
    return {"type": "rectangle",
            "bounds_2d": {"min": {"x": x0, "z": z0}, "max": {"x": x1, "z": z1}}}


def _verdict(regions, rules, y0=None):
    return compute_buildability({"regions": regions, "apply_rules": rules}, y0, BBOX)["verdict"]


def test_never_denies_its_region():
    v = _verdict({"area": _rect(0, 0, 6, 6)}, [{"region": "area", "block": "never"}])
    assert (v[0:6, 0:6] == 1).all()   # never inside
    assert v[8, 8] == 0               # buildable outside (default)


def test_deny_void_only_bites_void_columns():
    # left half (x<5) has a Y=0 block → buildable; right half is void → denied
    y0 = {(x, z) for x in range(0, 5) for z in range(0, 10)}
    v = _verdict({"nb": _rect(0, 0, 10, 10)},
                 [{"region": "nb", "block_place": "deny(void)"}], y0)
    assert v[5, 2] == 0   # terrain column → buildable despite the rule
    assert v[5, 7] == 2   # void column → void_denied


def test_deny_void_skipped_without_y0_layer():
    v = _verdict({"nb": _rect(0, 0, 10, 10)},
                 [{"region": "nb", "block_place": "deny(void)"}], None)
    assert (v == 0).all()             # no Y=0 → can't resolve void → unchanged


def test_region_as_filter_gate_denies_outside():
    # a global rule: build only inside `playable`
    v = _verdict({"playable": _rect(2, 2, 8, 8)},
                 [{"region": None, "block_place": "playable"}])
    assert v[5, 5] == 0   # inside the gate → buildable
    assert v[0, 0] == 1   # outside the gate → never


def test_team_filter_is_restricted():
    v = _verdict({"area": _rect(0, 0, 6, 6)}, [{"region": "area", "block": "only-blue"}])
    assert v[2, 2] == 3


def test_result_shape_and_counts():
    r = compute_buildability(
        {"regions": {"area": _rect(0, 0, 6, 6)},
         "apply_rules": [{"region": "area", "block": "never"}]}, None, BBOX)
    assert r["width"] == 10 and r["height"] == 10
    assert r["has_y0"] is False
    assert set(r["counts"]) == set(CLASSES)
    assert r["counts"]["never"] == 36 and r["counts"]["buildable"] == 64
