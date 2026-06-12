"""Hermetic tests for services.wool_sources (C12).

The core logic runs on a plain source list, so these need no parquet I/O
(real-map detection is covered by the corpus oracle in tools/ + fixtures).
"""
from shapely.geometry import box

from pgm_map_studio.studio.services.wool_sources import (
    check_availability, suggest_wools, summarize_sources)


def _src(type_, color, x, z, count=1, y=10):
    return {"type": type_, "color": color, "x": x, "y": y, "z": z, "count": count}


def _rect(x0, z0, x1, z1):
    return {"type": "rectangle",
            "bounds_2d": {"min": {"x": x0, "z": z0}, "max": {"x": x1, "z": z1}}}


# ── summarize / region filter ─────────────────────────────────────────────────

def test_summarize_groups_by_colour_and_counts():
    src = [_src("block", "red", 0, 0), _src("block", "red", 1, 1), _src("chest", "blue", 5, 5, count=3)]
    summ = {e["color"]: e for e in summarize_sources(src)}
    assert summ["red"]["total"] == 2 and summ["red"]["source_types"] == ["block"]
    assert summ["blue"]["total"] == 3 and summ["blue"]["source_types"] == ["chest"]


def test_region_filter_clips_to_drawn_rectangle():
    src = [_src("block", "red", 1, 1), _src("block", "blue", 50, 50)]
    summ = summarize_sources(src, box(-1, -1, 10, 10))
    assert [e["color"] for e in summ] == ["red"]      # blue is outside


def test_repeatable_classification():
    # spawner is always repeatable; a bare block/chest is one-time
    assert summarize_sources([_src("spawner", "blue", 0, 0)])[0]["repeatable"] is True
    assert summarize_sources([_src("chest", "blue", 0, 0)])[0]["one_time"] is True
    # a block inside a <renewable> geom is repeatable
    e = summarize_sources([_src("block", "red", 5, 5)], None, [box(0, 0, 10, 10)])[0]
    assert e["repeatable"] is True


# ── availability (the validation) ─────────────────────────────────────────────

_AVAIL_DATA = {"regions": {"room": _rect(0, 0, 10, 10)},
               "wools": [{"id": "red", "color": "red", "wool_room_region": "room"}]}


def test_availability_error_when_unsourced():
    a = check_availability(_AVAIL_DATA, [])[0]
    assert a["obtainable"] is False and a["severity"] == "error"


def test_availability_info_when_one_time_only():
    a = check_availability(_AVAIL_DATA, [_src("block", "red", 5, 5)])[0]
    assert a["obtainable"] is True and a["severity"] == "info" and a["one_time"] is True


def test_availability_ok_when_repeatable():
    a = check_availability(_AVAIL_DATA, [_src("spawner", "red", 5, 5)])[0]
    assert a["severity"] == "ok" and a["repeatable"] is True


def test_availability_source_must_be_in_the_room():
    a = check_availability(_AVAIL_DATA, [_src("block", "red", 99, 99)])[0]  # outside room
    assert a["obtainable"] is False and a["severity"] == "error"


# ── suggestions ───────────────────────────────────────────────────────────────

def test_suggest_undeclared_colours_only():
    data = {"regions": {}, "wools": [{"color": "red"}]}
    src = [_src("block", "red", 0, 0), _src("block", "blue", 1, 1), _src("chest", "lime", 2, 2)]
    colors = {s["color"] for s in suggest_wools(data, src)}
    assert colors == {"blue", "lime"}      # red is already declared


# ── PGM <spawner> module (xml-declared, region-based source) ──────────────────

from pgm_map_studio.studio.services.wool_sources import pgm_spawner_sources


def test_pgm_spawner_makes_wool_obtainable_by_colour():
    # room undeclared (None) — the PGM spawner still makes it obtainable, by colour
    data = {"regions": {"room": _rect(0, 0, 10, 10), "spawn": _rect(2, 2, 8, 8)},
            "wools": [{"id": "red", "color": "red", "wool_room_region": None}],
            "spawners": [{"spawn_region": "spawn", "player_region": "room",
                          "items": [{"material": "wool", "damage": 14}]}]}   # 14 = red
    src = pgm_spawner_sources(data)
    assert src and src[0]["type"] == "pgm_spawner" and src[0]["color"] == "red"
    a = check_availability(data, src)[0]
    assert a["obtainable"] and a["severity"] == "ok" and "pgm_spawner" in a["source_types"]


def test_no_physical_and_no_spawner_is_error():
    data = {"regions": {"room": _rect(0, 0, 10, 10)},
            "wools": [{"id": "red", "color": "red", "wool_room_region": "room"}],
            "spawners": []}
    a = check_availability(data, [])[0]
    assert a["obtainable"] is False and a["severity"] == "error"


def test_pgm_spawner_region_query_matches_by_overlap():
    data = {"regions": {"spawn": _rect(2, 2, 8, 8)},
            "spawners": [{"spawn_region": "spawn", "items": [{"material": "wool", "damage": 11}]}]}  # blue
    src = pgm_spawner_sources(data)
    hit = summarize_sources(src, box(0, 0, 5, 5))            # rect overlaps the spawn region
    assert hit and hit[0]["color"] == "blue" and hit[0]["repeatable"] is True
    assert summarize_sources(src, box(50, 50, 60, 60)) == []  # rect elsewhere → nothing
