"""Route-naming conventions (C10): plural item routes coexist with the static
collection-action routes.

After pluralizing `/region/<id>` → `/regions/<id>`, the dynamic item route sits
next to static action routes like `/regions/group`. Werkzeug must resolve the
static rule first; this pins that so a future refactor can't silently reroute
`/regions/group` into `patch_region` with `id="group"`.
"""
from __future__ import annotations

import pytest

from pgm_map_studio.studio import create_app


@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.mark.parametrize("method,url,endpoint", [
    ("GET",    "/api/map/m/regions/authoring",     "map_api.get_regions_authoring"),
    ("GET",    "/api/map/m/regions/tree",          "map_api.get_regions_tree"),
    ("PATCH",  "/api/map/m/regions/r1",            "regions.patch_region"),
    ("DELETE", "/api/map/m/regions/r1",            "regions.delete_region"),
    ("POST",   "/api/map/m/regions/group",         "regions.group_regions"),
    ("POST",   "/api/map/m/regions/ungroup",       "regions.ungroup_region"),
    ("POST",   "/api/map/m/regions/restore",       "regions.restore_region"),
    ("POST",   "/api/map/m/regions/r1/change-type", "regions.change_region_type"),
    ("POST",   "/api/map/m/regions/r1/counterpart", "regions.create_counterpart"),
    ("PATCH",  "/api/map/m/spawns/r1",             "spawns.update_spawn"),
    ("DELETE", "/api/map/m/spawns/r1",             "spawns.delete_spawn"),
])
def test_route_resolves_to_expected_endpoint(app, method, url, endpoint):
    with app.test_request_context(url, method=method):
        from flask import request
        assert request.url_rule is not None, f"{method} {url} did not match any route"
        assert request.url_rule.endpoint == endpoint
