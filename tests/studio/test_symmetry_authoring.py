"""Tests for studio/services/symmetry_authoring.py (C13 counterpart creation)."""
import pytest

from pgm_map_studio.studio.services.symmetry_authoring import (
    CounterpartError,
    create_counterpart,
)


def _rect(rid, minx, minz, maxx, maxz):
    return {"id": rid, "type": "rectangle",
            "bounds_2d": {"min": {"x": minx, "z": minz}, "max": {"x": maxx, "z": maxz}}}


def _data(*regions):
    return {"regions": {r["id"]: r for r in regions}}


# ── reflections → native PGM mirror regions ─────────────────────────────────────

class TestReflections:
    def setup_method(self):
        self.data = _data(_rect("blue-spawn", 0, 0, 10, 4))

    def test_mirror_x_creates_native_mirror(self):
        res = create_counterpart(self.data, "blue-spawn", "mirror_x", 50, 50)
        m = self.data["regions"][res["counterpart"]]
        assert m["type"] == "mirror"
        assert m["source_id"] == "blue-spawn"
        assert m["normal"] == {"x": 1.0, "y": 0.0, "z": 0.0}
        assert m["origin"] == {"x": 50, "y": 0.0, "z": 50}

    def test_mirror_x_reflects_bounds(self):
        res = create_counterpart(self.data, "blue-spawn", "mirror_x", 50, 50)
        m = self.data["regions"][res["counterpart"]]
        # reflect x across x=50: [0,10] → [90,100]
        assert m["bounds_2d"] == {"min": {"x": 90, "z": 0}, "max": {"x": 100, "z": 4}}

    def test_mirror_d2_diagonal_normal(self):
        res = create_counterpart(self.data, "blue-spawn", "mirror_d2", 0, 0)
        m = self.data["regions"][res["counterpart"]]
        assert m["normal"] == {"x": 1.0, "y": 0.0, "z": 1.0}  # anti-diagonal (vertex case)

    def test_mirror_d1_diagonal_normal(self):
        res = create_counterpart(self.data, "blue-spawn", "mirror_d1", 0, 0)
        m = self.data["regions"][res["counterpart"]]
        assert m["normal"] == {"x": 1.0, "y": 0.0, "z": -1.0}  # main diagonal


# ── rot_180 → two perpendicular mirrors ─────────────────────────────────────────

class TestRot180:
    def test_emits_two_chained_mirrors(self):
        data = _data(_rect("r", 0, 0, 10, 4))
        res = create_counterpart(data, "r", "rot_180", 50, 50)
        assert len(res["created"]) == 2
        m1_id, m2_id = res["created"]
        assert res["counterpart"] == m2_id
        m1, m2 = data["regions"][m1_id], data["regions"][m2_id]
        assert m1["source_id"] == "r"           # first mirror reflects the source
        assert m2["source_id"] == m1_id          # second reflects the first (⟂)
        assert m1["normal"] != m2["normal"]      # perpendicular


# ── rot_90 → baked concrete primitives ──────────────────────────────────────────

class TestRot90Bake:
    def test_rectangle_rotates_bounds_stays_rectangle(self):
        data = _data(_rect("r", 0, 0, 4, 2))
        res = create_counterpart(data, "r", "rot_90", 0, 0)
        out = data["regions"][res["counterpart"]]
        assert out["type"] == "rectangle"
        assert "source_id" not in out  # baked, not a transform
        # 90° CCW about origin: x∈[-2,0], z∈[0,4]
        assert out["bounds_2d"] == {"min": {"x": -2, "z": 0}, "max": {"x": 0, "z": 4}}

    def test_cuboid_swaps_xz_keeps_y(self):
        data = _data({"id": "c", "type": "cuboid",
                      "min": {"x": 0, "y": 60, "z": 0}, "max": {"x": 4, "y": 70, "z": 2},
                      "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 4, "z": 2}}})
        res = create_counterpart(data, "c", "rot_90", 0, 0)
        out = data["regions"][res["counterpart"]]
        assert out["type"] == "cuboid"
        assert out["min"]["y"] == 60 and out["max"]["y"] == 70  # Y preserved
        assert (out["min"]["x"], out["max"]["x"]) == (-2, 0)
        assert (out["min"]["z"], out["max"]["z"]) == (0, 4)

    def test_point_position_rotated(self):
        data = _data({"id": "p", "type": "point", "position": {"x": 10, "y": 64, "z": 0}})
        res = create_counterpart(data, "p", "rot_90", 0, 0)
        out = data["regions"][res["counterpart"]]
        assert out["type"] == "point"
        assert out["position"] == {"x": 0, "z": 10, "y": 64}  # (10,0)→(0,10), y kept

    def test_cylinder_base_rotated_radius_kept(self):
        data = _data({"id": "cy", "type": "cylinder",
                      "base": {"x": 10, "y": 0, "z": 0}, "radius": 5, "height": 8})
        res = create_counterpart(data, "cy", "rot_90", 0, 0)
        out = data["regions"][res["counterpart"]]
        assert out["base"]["x"] == 0 and out["base"]["z"] == 10
        assert out["radius"] == 5 and out["height"] == 8

    def test_rot90_compound_source_unsupported(self):
        data = {"regions": {"u": {"id": "u", "type": "union", "children": ["a", "b"]}}}
        with pytest.raises(CounterpartError):
            create_counterpart(data, "u", "rot_90", 0, 0)


# ── errors ──────────────────────────────────────────────────────────────────────

class TestErrors:
    def test_missing_source_raises(self):
        with pytest.raises(CounterpartError):
            create_counterpart(_data(), "ghost", "mirror_x", 0, 0)

    def test_nfold_mode_unsupported(self):
        data = _data(_rect("r", 0, 0, 4, 2))
        with pytest.raises(CounterpartError):
            create_counterpart(data, "r", "rot_120", 0, 0)
