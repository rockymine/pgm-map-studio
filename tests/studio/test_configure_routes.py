from __future__ import annotations

import json
import pytest

from pgm_map_studio.studio import create_app
from pgm_map_studio.pipeline.config import MapConfig, save_map_config


@pytest.fixture()
def app_ctx(tmp_path, monkeypatch):
    """Shared context: monkeypatched output root + test client + map dir."""
    import pgm_map_studio.studio.services.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "get_output_root", lambda: tmp_path)
    import pgm_map_studio.studio.routes.configure as configure_mod
    monkeypatch.setattr(configure_mod, "get_output_root", lambda: tmp_path)

    map_dir = tmp_path / "testmap"
    map_dir.mkdir()

    flask_app = create_app()
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()
    return client, map_dir


def _write_symmetry(map_dir, status="unconfirmed"):
    sym = {
        "status": status,
        "modes": [
            {"type": "rot_180",  "detected": True,  "confidence": 1.0},
            {"type": "rot_90",   "detected": True,  "confidence": 1.0},
            {"type": "mirror_x", "detected": False, "confidence": 0.4},
            {"type": "mirror_z", "detected": False, "confidence": 0.4},
        ],
        "center": {"cx": 0.0, "cz": 0.0},
        "primary": {"type": "rot_90", "confidence": 1.0},
    }
    (map_dir / "symmetry.json").write_text(json.dumps(sym), encoding="utf-8")


# ── /api/configure/<name>/state ───────────────────────────────────────────

def test_get_state_404_unknown_map(app_ctx):
    client, _ = app_ctx
    r = client.get("/api/configure/no_such_map/state")
    assert r.status_code == 404


def test_get_state_defaults(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.get("/api/configure/testmap/state")
    assert r.status_code == 200
    data = r.get_json()
    assert data["scan_layer"] == "surface"
    assert data["scan_layer_confirmed"] is False
    assert data["symmetry_status"] == "unconfirmed"
    assert data["configure_complete"] is False
    assert data["exclude_blocks"] == []


def test_get_state_includes_exclude_blocks(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(exclude_blocks=[8, 30]), map_dir)
    data = client.get("/api/configure/testmap/state").get_json()
    assert data["exclude_blocks"] == [8, 30]


def test_get_state_complete_when_symmetry_confirmed(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    _write_symmetry(map_dir, status="confirmed")
    data = client.get("/api/configure/testmap/state").get_json()
    assert data["configure_complete"] is True
    assert data["symmetry_status"] == "confirmed"


def test_get_state_complete_when_symmetry_none(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    _write_symmetry(map_dir, status="none")
    data = client.get("/api/configure/testmap/state").get_json()
    assert data["configure_complete"] is True


# ── /api/configure/<name>/scan-layer ─────────────────────────────────────

def test_patch_scan_layer_updates(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.patch("/api/configure/testmap/scan-layer",
                     json={"scan_layer": "y0", "confirmed": True})
    assert r.status_code == 200
    data = r.get_json()
    assert data["scan_layer"] == "y0"
    assert data["scan_layer_confirmed"] is True


def test_patch_scan_layer_persists(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    client.patch("/api/configure/testmap/scan-layer", json={"scan_layer": "base"})
    from pgm_map_studio.pipeline.config import load_map_config
    cfg = load_map_config(map_dir)
    assert cfg.scan_layer == "base"


def test_patch_scan_layer_rejects_invalid(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.patch("/api/configure/testmap/scan-layer", json={"scan_layer": "bogus"})
    assert r.status_code == 400


def test_patch_scan_layer_confirmed_only(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.patch("/api/configure/testmap/scan-layer", json={"confirmed": True})
    assert r.status_code == 200
    assert r.get_json()["scan_layer_confirmed"] is True


# ── /api/configure/<name>/exclude-island ─────────────────────────────────

def test_exclude_island_adds(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.patch("/api/configure/testmap/exclude-island",
                     json={"island_id": 3, "excluded": True})
    assert r.status_code == 200
    assert 3 in r.get_json()["exclude_islands"]


def test_exclude_island_remove(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(exclude_islands=[2, 3]), map_dir)
    r = client.patch("/api/configure/testmap/exclude-island",
                     json={"island_id": 2, "excluded": False})
    assert r.status_code == 200
    body = r.get_json()
    assert 2 not in body["exclude_islands"]
    assert 3 in body["exclude_islands"]


def test_exclude_island_no_duplicates(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(exclude_islands=[5]), map_dir)
    client.patch("/api/configure/testmap/exclude-island",
                 json={"island_id": 5, "excluded": True})
    from pgm_map_studio.pipeline.config import load_map_config
    assert load_map_config(map_dir).exclude_islands.count(5) == 1


def test_exclude_island_missing_id_returns_400(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.patch("/api/configure/testmap/exclude-island", json={})
    assert r.status_code == 400


# ── /api/configure/<name>/exclude-block ──────────────────────────────────

def test_exclude_block_adds(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.patch("/api/configure/testmap/exclude-block",
                     json={"block_id": 8, "excluded": True})
    assert r.status_code == 200
    assert 8 in r.get_json()["exclude_blocks"]


def test_exclude_block_remove(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(exclude_blocks=[8, 30]), map_dir)
    r = client.patch("/api/configure/testmap/exclude-block",
                     json={"block_id": 8, "excluded": False})
    assert r.status_code == 200
    body = r.get_json()
    assert 8 not in body["exclude_blocks"]
    assert 30 in body["exclude_blocks"]


def test_exclude_block_no_duplicates(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(exclude_blocks=[18]), map_dir)
    client.patch("/api/configure/testmap/exclude-block",
                 json={"block_id": 18, "excluded": True})
    from pgm_map_studio.pipeline.config import load_map_config
    assert load_map_config(map_dir).exclude_blocks.count(18) == 1


def test_exclude_block_missing_id_returns_400(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.patch("/api/configure/testmap/exclude-block", json={})
    assert r.status_code == 400


def test_exclude_block_invalid_id_returns_400(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    r = client.patch("/api/configure/testmap/exclude-block",
                     json={"block_id": "not_a_number"})
    assert r.status_code == 400


# ── /api/configure/<name>/symmetry ───────────────────────────────────────

def test_patch_symmetry_confirm(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    _write_symmetry(map_dir)
    r = client.patch("/api/configure/testmap/symmetry", json={"status": "confirmed"})
    assert r.status_code == 200
    sym = json.loads((map_dir / "symmetry.json").read_text())
    assert sym["status"] == "confirmed"


def test_patch_symmetry_none_clears_primary(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    _write_symmetry(map_dir)
    client.patch("/api/configure/testmap/symmetry", json={"status": "none"})
    sym = json.loads((map_dir / "symmetry.json").read_text())
    assert sym["status"] == "none"
    assert sym["primary"] is None


def test_patch_symmetry_confirmed_type_override(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    _write_symmetry(map_dir)
    client.patch("/api/configure/testmap/symmetry",
                 json={"status": "confirmed", "confirmed_type": "mirror_x"})
    sym = json.loads((map_dir / "symmetry.json").read_text())
    assert sym["primary"]["type"] == "mirror_x"
    assert sym["primary"]["user_override"] is True


def test_patch_symmetry_center_override(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    _write_symmetry(map_dir)
    client.patch("/api/configure/testmap/symmetry",
                 json={"status": "confirmed", "cx": 5.0, "cz": -3.5})
    sym = json.loads((map_dir / "symmetry.json").read_text())
    assert sym["center"]["cx"] == 5.0
    assert sym["center"]["cz"] == -3.5


def test_patch_symmetry_invalid_type_returns_400(app_ctx):
    client, map_dir = app_ctx
    save_map_config(MapConfig(), map_dir)
    _write_symmetry(map_dir)
    r = client.patch("/api/configure/testmap/symmetry",
                     json={"status": "confirmed", "confirmed_type": "diagonal"})
    assert r.status_code == 400
