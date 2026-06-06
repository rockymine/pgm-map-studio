from __future__ import annotations

import json

import pytest

from pgm_map_studio.studio.services import sketch_data


@pytest.fixture(autouse=True)
def tmp_sketches(tmp_path, monkeypatch):
    """Redirect sketch storage to a temp directory for every test."""
    monkeypatch.setattr(sketch_data, "SKETCHES_DIR", tmp_path / "sketches")


# ── create ────────────────────────────────────────────────────────────────


def test_create_sketch_returns_id():
    sid = sketch_data.create_sketch()
    assert isinstance(sid, str) and len(sid) == 36  # UUID4 with hyphens


def test_create_sketch_writes_file():
    sid = sketch_data.create_sketch()
    path = sketch_data.SKETCHES_DIR / sid / "sketch.json"
    assert path.exists()


def test_create_sketch_default_fields():
    sid = sketch_data.create_sketch()
    data = sketch_data.load_sketch(sid)
    assert data["id"] == sid
    assert data["gamemode"] == "ctw"
    assert data["name"] == ""
    assert data["version"] == "1.0"
    assert data["objective"] == ""
    assert data["authors"] == []


def test_create_sketch_unique_ids():
    ids = {sketch_data.create_sketch() for _ in range(5)}
    assert len(ids) == 5


# ── load ──────────────────────────────────────────────────────────────────


def test_load_sketch_round_trips():
    sid = sketch_data.create_sketch()
    data = sketch_data.load_sketch(sid)
    assert data["id"] == sid


def test_load_sketch_not_found_raises():
    with pytest.raises(KeyError):
        sketch_data.load_sketch("00000000-0000-0000-0000-000000000000")


# ── save / patch ──────────────────────────────────────────────────────────


def test_save_sketch_persists_name():
    sid = sketch_data.create_sketch()
    sketch_data.save_overview(sid, {"name": "My Map", "version": "1.2"})
    data = sketch_data.load_sketch(sid)
    assert data["name"] == "My Map"
    assert data["version"] == "1.2"


def test_save_sketch_ignores_unknown_keys():
    sid = sketch_data.create_sketch()
    sketch_data.save_overview(sid, {"name": "ok", "evil_key": "injected"})
    raw = json.loads(
        (sketch_data.SKETCHES_DIR / sid / "sketch.json").read_text()
    )
    assert "evil_key" not in raw


def test_save_sketch_preserves_gamemode():
    sid = sketch_data.create_sketch()
    sketch_data.save_overview(sid, {"gamemode": "koth"})  # not a writable field
    data = sketch_data.load_sketch(sid)
    assert data["gamemode"] == "ctw"


def test_save_sketch_authors():
    sid = sketch_data.create_sketch()
    authors = [{"uuid": "abc", "name": "rockymine", "role": "author", "contribution": None}]
    sketch_data.save_overview(sid, {"authors": authors})
    data = sketch_data.load_sketch(sid)
    assert data["authors"] == authors


def test_save_overview_not_found_raises():
    with pytest.raises(KeyError):
        sketch_data.save_overview("00000000-0000-0000-0000-000000000000", {"name": "x"})


# ── setup ──────────────────────────────────────────────────────────────────


def test_create_sketch_setup_is_none():
    sid = sketch_data.create_sketch()
    data = sketch_data.load_sketch(sid)
    assert data["setup"] is None


def test_save_setup_persists_bbox():
    sid = sketch_data.create_sketch()
    sketch_data.save_setup(sid, {
        "bbox": {"min_x": -256, "max_x": 256, "min_z": -256, "max_z": 256},
        "center": {"cx": 0, "cz": 0},
        "mirror_mode": "rot_180",
    })
    data = sketch_data.load_sketch(sid)
    assert data["setup"]["bbox"] == {"min_x": -256, "max_x": 256, "min_z": -256, "max_z": 256}


def test_save_setup_persists_center():
    sid = sketch_data.create_sketch()
    sketch_data.save_setup(sid, {
        "bbox": {"min_x": 0, "max_x": 128, "min_z": 0, "max_z": 128},
        "center": {"cx": 64, "cz": 64},
        "mirror_mode": "mirror_x",
    })
    data = sketch_data.load_sketch(sid)
    assert data["setup"]["center"] == {"cx": 64, "cz": 64}


def test_save_setup_persists_mirror_mode():
    sid = sketch_data.create_sketch()
    sketch_data.save_setup(sid, {
        "bbox": {"min_x": 0, "max_x": 128, "min_z": 0, "max_z": 128},
        "center": {"cx": 0, "cz": 0},
        "mirror_mode": "rot_90",
    })
    data = sketch_data.load_sketch(sid)
    assert data["setup"]["mirror_mode"] == "rot_90"


def test_save_setup_ignores_unknown_keys():
    sid = sketch_data.create_sketch()
    sketch_data.save_setup(sid, {
        "bbox": {"min_x": 0, "max_x": 64, "min_z": 0, "max_z": 64},
        "center": {"cx": 0, "cz": 0},
        "mirror_mode": "rot_180",
        "injected": "bad",
    })
    raw = json.loads(
        (sketch_data.SKETCHES_DIR / sid / "sketch.json").read_text()
    )
    assert "injected" not in raw["setup"]


def test_save_setup_not_found_raises():
    with pytest.raises(KeyError):
        sketch_data.save_setup("00000000-0000-0000-0000-000000000000", {})


# ── layout ─────────────────────────────────────────────────────────────────────

_SAMPLE_SHAPES = [
    {"id": "s1", "type": "rectangle", "operation": "add", "override": False,
     "min_x": -256, "max_x": 256, "min_z": -256, "max_z": 256},
    {"id": "s2", "type": "circle", "operation": "subtract", "override": False,
     "center_x": 0, "center_z": 0, "radius": 50},
]
_SAMPLE_ISLANDS = [
    {"id": "isl_1", "name": "Base", "color": "#4ade80", "mirrors": True},
]


def test_create_sketch_layout_is_none():
    sid = sketch_data.create_sketch()
    data = sketch_data.load_sketch(sid)
    assert data["layout"] is None


def test_save_layout_persists_shapes():
    sid = sketch_data.create_sketch()
    sketch_data.save_layout(sid, _SAMPLE_SHAPES, _SAMPLE_ISLANDS)
    data = sketch_data.load_sketch(sid)
    assert data["layout"]["shapes"] == _SAMPLE_SHAPES


def test_save_layout_persists_islands():
    sid = sketch_data.create_sketch()
    sketch_data.save_layout(sid, _SAMPLE_SHAPES, _SAMPLE_ISLANDS)
    data = sketch_data.load_sketch(sid)
    assert data["layout"]["islands"] == _SAMPLE_ISLANDS


def test_save_layout_overwrites_previous():
    sid = sketch_data.create_sketch()
    sketch_data.save_layout(sid, _SAMPLE_SHAPES, _SAMPLE_ISLANDS)
    new_shapes = [{"id": "s3", "type": "rectangle", "operation": "add", "override": False,
                   "min_x": 0, "max_x": 10, "min_z": 0, "max_z": 10}]
    sketch_data.save_layout(sid, new_shapes, [])
    data = sketch_data.load_sketch(sid)
    assert len(data["layout"]["shapes"]) == 1
    assert data["layout"]["shapes"][0]["id"] == "s3"
    assert data["layout"]["islands"] == []


def test_save_layout_empty_shapes_and_islands():
    sid = sketch_data.create_sketch()
    sketch_data.save_layout(sid, [], [])
    data = sketch_data.load_sketch(sid)
    assert data["layout"] == {"shapes": [], "islands": []}


def test_save_layout_not_found_raises():
    with pytest.raises(KeyError):
        sketch_data.save_layout("00000000-0000-0000-0000-000000000000", [], [])
