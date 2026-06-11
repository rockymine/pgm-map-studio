"""Map-editing write routes reject malformed input with 4xx, never 500.

The editor services validate presence/conflicts but historically coerced types
(`int(payload["max_players"])`) and assumed a dict body — so a wrong-typed field
or a non-object JSON body crashed with a 500 instead of a clean 400. This pins
the hardened behaviour: hostile input is a client error (4xx), never a server
error (5xx).
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
        "name": "m",
        "teams": [{"id": "red", "name": "Red", "color": "red"}],
        "spawns": [], "wools": [], "filters": {},
        "regions": {"r1": {"id": "r1", "type": "rectangle",
                           "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 4, "z": 4}}}},
        "apply_rules": [],
    }), encoding="utf-8")
    app = create_app()
    app.config["TESTING"] = False          # exercise the real error path, not re-raise
    return app.test_client()


# Each create/POST route that takes a JSON object body.
_CREATE_ROUTES = [
    "/api/map/m/teams",
    "/api/map/m/wools",
    "/api/map/m/spawns",
    "/api/map/m/filters",
    "/api/map/m/apply-rules",
    "/api/map/m/regions",
]


@pytest.mark.parametrize("url", _CREATE_ROUTES)
@pytest.mark.parametrize("body", [[1, 2, 3], "a string", 42], ids=["array", "string", "number"])
def test_non_object_body_is_client_error(client, url, body):
    resp = client.post(url, json=body)
    assert resp.status_code != 500, f"{url} 500'd on non-object body {body!r}"
    assert 400 <= resp.status_code < 500


def test_team_bad_numeric_field_is_400(client):
    resp = client.post("/api/map/m/teams", json={"id": "blue", "max_players": "abc"})
    assert resp.status_code == 400


def test_team_patch_bad_numeric_field_is_400(client):
    resp = client.patch("/api/map/m/teams/red", json={"max_players": "lots"})
    assert resp.status_code == 400


def test_spawn_patch_bad_yaw_is_400(client):
    # establish a spawn first, then PATCH it with a bad yaw
    assert client.post("/api/map/m/spawns",
                       json={"region_id": "r1", "team": "red"}).status_code == 201
    resp = client.patch("/api/map/m/spawns/r1", json={"yaw": "sideways"})
    assert resp.status_code == 400


# inline-body routes (read the body directly, not via a guarded editor)

@pytest.mark.parametrize("url", ["/api/map/m/regions/restore",
                                 "/api/map/m/regions/r1/counterpart"])
def test_inline_body_routes_reject_non_object(client, url):
    resp = client.post(url, json=[1, 2, 3])
    assert resp.status_code != 500
    assert 400 <= resp.status_code < 500


def test_counterpart_non_numeric_center_is_400(client):
    resp = client.post("/api/map/m/regions/r1/counterpart",
                       json={"mode": "mirror_x", "center": {"cx": "x", "cz": "y"}})
    assert resp.status_code == 400
