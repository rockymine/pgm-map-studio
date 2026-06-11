"""Tests for studio/services/region_geometry.py (polygon-level region equivalence).

Includes a corpus oracle: real region footprints (hermetic — no live corpus
access), validating that generated counterparts coincide with the real authored
regions. Three maps cover distinct symmetry classes:
- ``townside_mini`` — a **pure rot_180** (chiral): the counterpart is *not*
  reachable by any reflection.
- ``outback_outback_edition`` — **axis-aligned D2** (rot_180 *and* both ⟂ mirrors).
- ``xion`` — **diagonal D2**: the counterpart is reached by rot_180 *and* a
  diagonal mirror (``mirror_d2``), but not by the axis-aligned mirrors.
- ``annealing_iv`` — a 4-team **rot_90** orbit.
"""
import pytest

from pgm_map_studio.studio.services.region_geometry import (
    counterpart_iou,
    is_counterpart,
    regions_equivalent,
)


def _rect(rid, minx, minz, maxx, maxz):
    return {"id": rid, "type": "rectangle",
            "bounds_2d": {"min": {"x": minx, "z": minz}, "max": {"x": maxx, "z": maxz}}}


def _data(*regions):
    return {"regions": {r["id"]: r for r in regions}}


# ── regions_equivalent (footprint identity) ─────────────────────────────────────

class TestRegionsEquivalent:
    def test_identical_rectangles_equivalent(self):
        d = _data(_rect("a", 0, 0, 10, 10), _rect("b", 0, 0, 10, 10))
        assert regions_equivalent(d, "a", "b") is True

    def test_different_rectangles_not_equivalent(self):
        d = _data(_rect("a", 0, 0, 10, 10), _rect("b", 50, 50, 60, 60))
        assert regions_equivalent(d, "a", "b") is False

    def test_partial_overlap_below_threshold(self):
        d = _data(_rect("a", 0, 0, 10, 10), _rect("b", 5, 5, 15, 15))
        assert regions_equivalent(d, "a", "b") is False  # IoU ≈ 0.14

    def test_missing_region_not_equivalent(self):
        d = _data(_rect("a", 0, 0, 10, 10))
        assert regions_equivalent(d, "a", "ghost") is False


# ── is_counterpart (transform then compare) ─────────────────────────────────────

class TestIsCounterpart:
    def test_mirror_x_counterpart(self):
        d = _data(_rect("src", 0, 0, 10, 4), _rect("tgt", 90, 0, 100, 4))
        assert is_counterpart(d, "src", "tgt", "mirror_x", 50, 0) is True

    def test_wrong_mode_not_counterpart(self):
        d = _data(_rect("src", 0, 0, 10, 4), _rect("tgt", 90, 0, 100, 4))
        assert is_counterpart(d, "src", "tgt", "mirror_z", 50, 0) is False

    def test_rot_90_counterpart(self):
        # rect [0,4]x[0,2] rot_90 CCW about origin → x∈[-2,0], z∈[0,4]
        d = _data(_rect("src", 0, 0, 4, 2), _rect("tgt", -2, 0, 0, 4))
        assert is_counterpart(d, "src", "tgt", "rot_90", 0, 0) is True

    def test_counterpart_iou_is_one_for_exact(self):
        d = _data(_rect("src", 0, 0, 10, 4), _rect("tgt", 90, 0, 100, 4))
        assert counterpart_iou(d, "src", "tgt", "mirror_x", 50, 0) == pytest.approx(1.0)


# ── corpus oracle ───────────────────────────────────────────────────────────────

# Real region footprints (bounds_2d) extracted from the maps; center (0,0) per
# their symmetry.json. outback is rot_180 with a perpendicular intra-team mirror;
# annealing is a 4-team rot_90.
OUTBACK = _data(  # outback_outback_edition — the four wool rooms, one per quadrant
    _rect("purple-woolroom",     -70, -137, -54, -121),
    _rect("pink-woolroom",        54, -137,  70, -121),
    _rect("light-blue-woolroom", -70,  121, -54,  137),
    _rect("blue-woolroom",        54,  121,  70,  137),
)

ANNEALING = _data(  # annealing_iv — the four team spawns (rot_90 orbit)
    _rect("blue-spawn",   -38, -100, -10,  -80),
    _rect("green-spawn", -100,   10, -80,   38),
    _rect("red-spawn",     10,   80,  38,  100),
    _rect("yellow-spawn",  80,  -38, 100,  -10),
)

TOWNSIDE = _data(  # townside_mini — a pure rot_180 (chiral, no mirror symmetry)
    _rect("blue-spawn",    -39,   5, -30,  40),
    _rect("red-spawn",      30, -40,  39,  -5),
    _rect("blue-woolroom",   7,  61,  16,  76),
    _rect("red-woolroom",  -16, -76,  -7, -61),
)


XION = _data(  # xion — diagonal-D2 (rot_180 + anti-diagonal mirror), center (-34.5,-151.5)
    _rect("blue-spawn",   22,  -95,  43,  -74),
    _rect("red-spawn",  -112, -229, -91, -208),
    _rect("blue-iron",    34,  -84,  62,  -55),
    _rect("red-iron",   -131, -248, -103, -219),
)
_XC, _ZC = -34.5, -151.5


class TestCorpusOracleXion:
    def test_rot_180_pairs_spawns(self):
        assert is_counterpart(XION, "blue-spawn", "red-spawn", "rot_180", _XC, _ZC)

    def test_diagonal_mirror_pairs_spawns(self):
        # the same pair is also an anti-diagonal (mirror_d2) reflection
        assert is_counterpart(XION, "blue-spawn", "red-spawn", "mirror_d2", _XC, _ZC)

    def test_rot_180_pairs_a_second_region(self):
        assert is_counterpart(XION, "blue-iron", "red-iron", "rot_180", _XC, _ZC)

    def test_not_axis_aligned_nor_other_diagonal(self):
        for mode in ("mirror_x", "mirror_z", "mirror_d1"):
            assert not is_counterpart(XION, "blue-spawn", "red-spawn", mode, _XC, _ZC), mode


class TestCorpusOracleTownside:
    def test_rot_180_pairs_spawns(self):
        assert is_counterpart(TOWNSIDE, "blue-spawn", "red-spawn", "rot_180", 0, 0)

    def test_rot_180_pairs_woolrooms(self):
        assert is_counterpart(TOWNSIDE, "blue-woolroom", "red-woolroom", "rot_180", 0, 0)

    def test_pure_rot_180_not_mirror(self):
        # the defining property: a chiral rot_180 — no reflection reaches the counterpart
        for mode in ("mirror_x", "mirror_z", "mirror_d1", "mirror_d2"):
            assert not is_counterpart(TOWNSIDE, "blue-spawn", "red-spawn", mode, 0, 0), mode


class TestCorpusOracleOutback:
    def test_mirror_x_pairs_purple_and_pink(self):
        assert is_counterpart(OUTBACK, "purple-woolroom", "pink-woolroom", "mirror_x", 0, 0)

    def test_mirror_z_pairs_purple_and_light_blue(self):
        assert is_counterpart(OUTBACK, "purple-woolroom", "light-blue-woolroom", "mirror_z", 0, 0)

    def test_rot_180_pairs_purple_and_blue(self):
        assert is_counterpart(OUTBACK, "purple-woolroom", "blue-woolroom", "rot_180", 0, 0)

    def test_wrong_mode_does_not_pair(self):
        # blue is the rot_180 opposite, not the mirror_x reflection
        assert not is_counterpart(OUTBACK, "purple-woolroom", "blue-woolroom", "mirror_x", 0, 0)

    def test_axis_aligned_map_has_no_diagonal_symmetry(self):
        assert not is_counterpart(OUTBACK, "purple-woolroom", "pink-woolroom", "mirror_d1", 0, 0)


class TestCorpusOracleAnnealing:
    def test_rot_90_orbit(self):
        # blue → yellow → red → green → blue (CCW)
        assert is_counterpart(ANNEALING, "blue-spawn", "yellow-spawn", "rot_90", 0, 0)
        assert is_counterpart(ANNEALING, "blue-spawn", "red-spawn", "rot_180", 0, 0)
        assert is_counterpart(ANNEALING, "blue-spawn", "green-spawn", "rot_270", 0, 0)

    def test_rot_90_is_not_rot_270_neighbour(self):
        # green is the rot_270 neighbour of blue, not its rot_90 counterpart
        assert not is_counterpart(ANNEALING, "blue-spawn", "green-spawn", "rot_90", 0, 0)

    def test_distinct_team_spawns_not_equivalent(self):
        assert not regions_equivalent(ANNEALING, "blue-spawn", "yellow-spawn")
