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
