"""Routes that serialize through the schemas return contract-shaped payloads.

These guard the *wiring*: /api/map/<name>/regions/tree and /api/sketch/<sid>
now build their response by passing data through the pydantic schema and
dumping it, so the JSON the frontend receives is exactly the generated TS
contract — and a drift between encoder and schema surfaces as a 500 here, not a
silently malformed payload in the browser.
"""
from __future__ import annotations

import json

import pytest

from pgm_map_studio.studio import create_app
from pgm_map_studio.schemas import RegionTreeResponse, SketchProject


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # point both the output root and the sketches dir at a temp area
    import pgm_map_studio.studio.services.config as cfg_mod
    import pgm_map_studio.studio.services.xml_data as xml_mod
    import pgm_map_studio.studio.routes.map_api as map_api_mod
    import pgm_map_studio.studio.services.sketch_data as sk_mod
    monkeypatch.setattr(cfg_mod, "get_output_root", lambda: tmp_path)
    monkeypatch.setattr(xml_mod, "get_output_root", lambda: tmp_path)
    monkeypatch.setattr(map_api_mod, "get_output_root", lambda: tmp_path)
    monkeypatch.setattr(sk_mod, "SKETCHES_DIR", tmp_path / "sketches")

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client(), tmp_path


# ── /regions/tree → RegionTreeResponse ──────────────────────────────────────────

def test_regions_tree_returns_schema_conformant_payload(client):
    c, root = client
    map_dir = root / "demo"
    map_dir.mkdir()
    (map_dir / "xml_data.json").write_text(json.dumps({
        "regions": {
            "blue-spawn": {"id": "blue-spawn", "type": "rectangle",
                           "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 10, "z": 4}}},
        },
    }), encoding="utf-8")
    (map_dir / "islands.json").write_text(json.dumps(
        [{"bounds": [-50, -50, 50, 50]}]), encoding="utf-8")

    resp = c.get("/api/map/demo/regions/tree")
    assert resp.status_code == 200
    # the response validates against the contract the frontend is typed against
    parsed = RegionTreeResponse.model_validate(resp.get_json())
    assert "bounding_box" in resp.get_json()
    assert any(n.id == "blue-spawn" for g in parsed.groups for n in g.regions)


# ── /api/sketch/<sid> → SketchProject (bezier alias must survive) ────────────────

def _write_sketch(root, sid):
    d = root / "sketches" / sid
    d.mkdir(parents=True)
    (d / "sketch.json").write_text(json.dumps({
        "id": sid, "name": "Demo", "gamemode": "ctw",
        "layout": {
            "shapes": [{
                "id": "s1", "type": "polygon",
                "vertices": [[0, 0], [10, 0], [5, 9]],
                "controls": {"0": {"in": [1, 1], "out": [3, 0]}},
            }],
            "islands": [],
        },
    }), encoding="utf-8")


def test_sketch_get_returns_schema_payload_with_bezier_in_key(client):
    c, root = client
    _write_sketch(root, "sid-1")

    resp = c.get("/api/sketch/sid-1")
    assert resp.status_code == 200
    body = resp.get_json()
    # the bezier handle key is the wire "in", not the python field name "in_"
    ctrl = body["layout"]["shapes"][0]["controls"]["0"]
    assert "in" in ctrl and "in_" not in ctrl
    assert ctrl["in"] == [1.0, 1.0]
    # and the whole payload is contract-shaped
    SketchProject.model_validate(body)


def test_sketch_get_missing_returns_404(client):
    c, _ = client
    assert c.get("/api/sketch/nope").status_code == 404
