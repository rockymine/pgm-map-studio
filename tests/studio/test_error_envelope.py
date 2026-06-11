"""The structured error envelope (C1): every /api error is {error:{code,message}}.

Enforced centrally in studio/errors.py (an after_request transformer for flat
`{"error": "..."}` returns + an HTTPException handler for abort()), so routes
keep returning the simple form. Non-/api (HTML page) errors are left alone.
"""
from __future__ import annotations

import json

import pytest

from pgm_map_studio.studio import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import pgm_map_studio.studio.services.xml_data as xml_mod
    monkeypatch.setattr(xml_mod, "get_output_root", lambda: tmp_path)
    map_dir = tmp_path / "m"
    map_dir.mkdir()
    (map_dir / "xml_data.json").write_text(json.dumps({
        "name": "m", "teams": [{"id": "red", "name": "Red", "color": "red"}],
        "spawns": [], "wools": [], "filters": {}, "regions": {}, "apply_rules": [],
    }), encoding="utf-8")
    app = create_app()
    return app.test_client()


def _err(resp):
    return resp.get_json()["error"]


def test_flat_400_is_enveloped(client):
    resp = client.post("/api/map/m/teams", json={})        # "id is required"
    assert resp.status_code == 400
    assert _err(resp) == {"code": "bad_request", "message": "id is required"}


def test_flat_409_conflict_code(client):
    resp = client.post("/api/map/m/teams", json={"id": "red"})
    assert resp.status_code == 409
    assert _err(resp)["code"] == "conflict"
    assert "already in use" in _err(resp)["message"]


def test_not_found_code(client):
    resp = client.delete("/api/map/m/teams/ghost")
    assert resp.status_code == 404
    assert _err(resp)["code"] == "not_found"


def test_abort_based_error_is_enveloped(client):
    # load_xml_data aborts 404 for a missing map (not a flat jsonify return)
    resp = client.get("/api/map/does-not-exist/regions")
    assert resp.status_code == 404
    assert _err(resp)["code"] == "not_found"
    assert isinstance(_err(resp)["message"], str)


def test_extra_keys_preserved_alongside_envelope(client):
    # FilterInUse returns 409 with a `references` list — must survive the rewrite.
    # Create a filter, reference it from an apply-rule, then try to delete it.
    client.post("/api/map/m/filters", json={"id": "f1", "type": "material", "material": "iron block"})
    client.post("/api/map/m/apply-rules", json={"region": "everywhere", "block": "f1"})
    resp = client.delete("/api/map/m/filter/f1")
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["error"]["code"] == "conflict"
    assert "references" in body            # extra key preserved alongside the envelope


def test_non_api_route_not_enveloped(client):
    # an HTML page 404 keeps Flask's normal (non-JSON) error response
    resp = client.get("/definitely-not-a-page")
    assert resp.status_code == 404
    assert resp.get_json(silent=True) is None
