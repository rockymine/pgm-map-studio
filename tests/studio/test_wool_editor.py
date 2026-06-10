"""Tests for wool_editor — grouped data model (color-unique wools, per-team monuments)."""
import pytest
from pgm_map_studio.studio.services.wool_editor import (
    add_wool, update_wool, delete_wool,
    add_monument, update_monument, delete_monument,
    _ensure_grouped, _migrate_to_grouped,
    InvalidWoolPayload, WoolNotFound,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _data(*wools):
    return {"wools": list(wools)}

def _wool(color="red", location=None, wool_room_region=None, monuments=None):
    from pgm_map_studio.studio.services.wool_editor import _gen_id
    return {
        "id": _gen_id(),
        "color": color,
        "location": location,
        "wool_room_region": wool_room_region,
        "monuments": monuments if monuments is not None else [],
    }

def _monument(team="blue", location=None, monument_region=None):
    from pgm_map_studio.studio.services.wool_editor import _gen_id
    return {
        "id": _gen_id(),
        "team": team,
        "location": location,
        "monument_region": monument_region,
    }

def _old_flat(team, color, location, monument, wool_room_region=None):
    """Produce one entry in the old flat format (pre-migration)."""
    return {
        "team": team,
        "color": color,
        "location": location,
        "monument": monument,
        "wool_room_region": wool_room_region,
    }


# ── migration ─────────────────────────────────────────────────────────────────

def test_migrate_groups_by_color():
    data = _data(
        _old_flat("blue", "red",   {"x": 1, "y": 2, "z": 3}, {"x": 10, "y": 11, "z": 12, "region_id": "b-red"}),
        _old_flat("red",  "red",   {"x": 1, "y": 2, "z": 3}, {"x": 20, "y": 21, "z": 22, "region_id": "r-red"}),
        _old_flat("blue", "green", {"x": 5, "y": 6, "z": 7}, {"x": 30, "y": 31, "z": 32}),
    )
    _ensure_grouped(data)
    wools = data["wools"]
    assert len(wools) == 2

    by_color = {w["color"]: w for w in wools}
    assert set(by_color) == {"red", "green"}

    red = by_color["red"]
    assert red["location"] == {"x": 1, "y": 2, "z": 3}
    assert len(red["monuments"]) == 2
    assert {m["team"] for m in red["monuments"]} == {"blue", "red"}

    green = by_color["green"]
    assert len(green["monuments"]) == 1
    assert green["monuments"][0]["monument_region"] is None


def test_migrate_maps_monument_region_id():
    data = _data(
        _old_flat("blue", "yellow", {"x": 0, "y": 0, "z": 0},
                  {"x": 1, "y": 2, "z": 3, "region_id": "b-yellow-mon"}),
    )
    _ensure_grouped(data)
    mon = data["wools"][0]["monuments"][0]
    assert mon["monument_region"] == "b-yellow-mon"


def test_migrate_assigns_ids():
    data = _data(_old_flat("blue", "red", {"x": 0, "y": 0, "z": 0}, {"x": 1, "y": 2, "z": 3}))
    _ensure_grouped(data)
    wool = data["wools"][0]
    assert wool["id"]
    assert wool["monuments"][0]["id"]


def test_migrate_idempotent_on_new_format():
    w = _wool("red")
    data = _data(w)
    _ensure_grouped(data)
    assert data["wools"][0] is w


def test_migrate_no_op_on_empty():
    data = {"wools": []}
    _ensure_grouped(data)
    assert data["wools"] == []


def test_infer_wool_team_from_missing_monument_team():
    teams = [{"id": "blue"}, {"id": "red"}, {"id": "green"}]
    w = _wool("red", monuments=[_monument("blue"), _monument("green")])
    data = {"teams": teams, "wools": [w]}
    _ensure_grouped(data)
    assert data["wools"][0]["team"] == "red"


def test_infer_wool_team_skips_when_team_already_set():
    teams = [{"id": "blue"}, {"id": "red"}]
    w = _wool("red", monuments=[_monument("blue")])
    w["team"] = "explicit-team"
    data = {"teams": teams, "wools": [w]}
    _ensure_grouped(data)
    assert data["wools"][0]["team"] == "explicit-team"


def test_infer_wool_team_skips_when_ambiguous():
    teams = [{"id": "blue"}, {"id": "red"}, {"id": "green"}]
    w = _wool("red", monuments=[_monument("blue")])  # two teams missing → ambiguous
    data = {"teams": teams, "wools": [w]}
    _ensure_grouped(data)
    assert data["wools"][0].get("team") is None


# ── add_wool ──────────────────────────────────────────────────────────────────

def test_add_wool_creates_grouped_entry():
    data = {}
    result = add_wool(data, {"color": "red"})
    wool = result["wool"]
    assert wool["color"] == "red"
    assert wool["location"] is None
    assert wool["wool_room_region"] is None
    assert wool["monuments"] == []
    assert wool["id"] == "red"  # deterministic: id = colour slug
    assert data["wools"] == [wool]


def test_add_wool_normalizes_color():
    data = {}
    result = add_wool(data, {"color": "Light Blue"})
    assert result["wool"]["color"] == "light_blue"


def test_add_wool_rejects_invalid_color():
    with pytest.raises(InvalidWoolPayload):
        add_wool({}, {"color": "neon_pink"})


def test_add_wool_rejects_duplicate_color():
    data = _data(_wool("red"))
    with pytest.raises(InvalidWoolPayload, match="already exists"):
        add_wool(data, {"color": "red"})


def test_add_wool_triggers_migration():
    data = _data(_old_flat("blue", "green", {"x": 0, "y": 0, "z": 0}, {"x": 1, "y": 2, "z": 3}))
    add_wool(data, {"color": "red"})
    colors = {w["color"] for w in data["wools"]}
    assert colors == {"green", "red"}


# ── update_wool ───────────────────────────────────────────────────────────────

def test_update_wool_color():
    w = _wool("red")
    data = _data(w)
    update_wool(data, w["id"], {"color": "green"})
    assert data["wools"][0]["color"] == "green"


def test_update_wool_location():
    w = _wool("red")
    data = _data(w)
    update_wool(data, w["id"], {"location": {"x": 1, "y": 2, "z": 3}})
    assert data["wools"][0]["location"] == {"x": 1, "y": 2, "z": 3}


def test_update_wool_clears_location_on_none():
    w = _wool("red", location={"x": 1, "y": 2, "z": 3})
    data = _data(w)
    update_wool(data, w["id"], {"location": None})
    assert data["wools"][0]["location"] is None


def test_update_wool_wool_room_region():
    w = _wool("red")
    data = _data(w)
    update_wool(data, w["id"], {"wool_room_region": "blue-woolroom"})
    assert data["wools"][0]["wool_room_region"] == "blue-woolroom"


def test_update_wool_not_found():
    with pytest.raises(WoolNotFound):
        update_wool({}, "nonexistent", {"color": "red"})


def test_update_wool_color_rekeys_id_and_monuments():
    w = _wool("red", monuments=[_monument("blue")])
    w["id"] = "red"
    w["monuments"][0]["id"] = "red-blue"
    data = _data(w)
    update_wool(data, "red", {"color": "green"})
    out = data["wools"][0]
    assert out["id"] == "green"  # content-derived id tracks the colour
    assert out["monuments"][0]["id"] == "green-blue"  # cascades to monuments


def test_update_wool_color_rejects_collision_with_other_wool():
    w1 = _wool("red"); w1["id"] = "red"
    w2 = _wool("green"); w2["id"] = "green"
    data = _data(w1, w2)
    with pytest.raises(InvalidWoolPayload, match="already exists"):
        update_wool(data, "red", {"color": "green"})


def test_deterministic_ids_match_serializer_scheme():
    # ids derived the same way pgm.serializer._encode_wools_grouped derives them
    from pgm_map_studio.studio.services.wool_editor import _wool_id, _monument_id
    assert _wool_id("Light Blue") == "light_blue"
    assert _monument_id("Light Blue", "blue-team") == "light_blue-blue-team"


# ── delete_wool ───────────────────────────────────────────────────────────────

def test_delete_wool_removes_entry():
    w = _wool("red")
    data = _data(w)
    delete_wool(data, w["id"])
    assert data["wools"] == []


def test_delete_wool_leaves_others():
    w1, w2 = _wool("red"), _wool("green")
    data = _data(w1, w2)
    delete_wool(data, w1["id"])
    assert len(data["wools"]) == 1
    assert data["wools"][0]["color"] == "green"


def test_delete_wool_not_found():
    with pytest.raises(WoolNotFound):
        delete_wool({}, "nonexistent")


# ── add_monument ──────────────────────────────────────────────────────────────

def test_add_monument_appends():
    w = _wool("red")
    data = _data(w)
    result = add_monument(data, w["id"], {"team": "blue"})
    mon = result["monument"]
    assert mon["team"] == "blue"
    assert mon["location"] is None
    assert mon["monument_region"] is None
    assert mon["id"] == "red-blue"  # deterministic: <colour>-<team>
    assert data["wools"][0]["monuments"] == [mon]


def test_add_monument_with_location():
    w = _wool("red")
    data = _data(w)
    result = add_monument(data, w["id"], {"team": "red", "location": {"x": 5, "y": 6, "z": 7}})
    assert result["monument"]["location"] == {"x": 5, "y": 6, "z": 7}


def test_add_monument_multiple_teams():
    w = _wool("red")
    data = _data(w)
    add_monument(data, w["id"], {"team": "blue"})
    add_monument(data, w["id"], {"team": "red"})
    assert len(data["wools"][0]["monuments"]) == 2


def test_add_monument_rejects_duplicate_team():
    w = _wool("red")
    data = _data(w)
    add_monument(data, w["id"], {"team": "blue"})
    with pytest.raises(InvalidWoolPayload, match="already exists"):
        add_monument(data, w["id"], {"team": "blue"})


def test_add_monument_wool_not_found():
    with pytest.raises(WoolNotFound):
        add_monument({}, "nonexistent", {"team": "blue"})


# ── update_monument ───────────────────────────────────────────────────────────

def test_update_monument_team():
    m = _monument("blue")
    w = _wool("red", monuments=[m])
    data = _data(w)
    update_monument(data, w["id"], m["id"], {"team": "red"})
    assert data["wools"][0]["monuments"][0]["team"] == "red"


def test_update_monument_team_rekeys_id():
    m = _monument("blue"); m["id"] = "red-blue"
    w = _wool("red", monuments=[m]); w["id"] = "red"
    data = _data(w)
    update_monument(data, "red", "red-blue", {"team": "green"})
    assert data["wools"][0]["monuments"][0]["id"] == "red-green"


def test_update_monument_team_rejects_duplicate():
    m1, m2 = _monument("blue"), _monument("red")
    w = _wool("red", monuments=[m1, m2])
    data = _data(w)
    with pytest.raises(InvalidWoolPayload, match="already exists"):
        update_monument(data, w["id"], m1["id"], {"team": "red"})


def test_update_monument_location():
    m = _monument("blue")
    w = _wool("red", monuments=[m])
    data = _data(w)
    update_monument(data, w["id"], m["id"], {"location": {"x": 1, "y": 2, "z": 3}})
    assert data["wools"][0]["monuments"][0]["location"] == {"x": 1, "y": 2, "z": 3}


def test_update_monument_region():
    m = _monument("blue")
    w = _wool("red", monuments=[m])
    data = _data(w)
    update_monument(data, w["id"], m["id"], {"monument_region": "blue-mon"})
    assert data["wools"][0]["monuments"][0]["monument_region"] == "blue-mon"


def test_update_monument_clears_region_on_empty():
    m = _monument("blue", monument_region="old-region")
    w = _wool("red", monuments=[m])
    data = _data(w)
    update_monument(data, w["id"], m["id"], {"monument_region": ""})
    assert data["wools"][0]["monuments"][0]["monument_region"] is None


def test_update_monument_wool_not_found():
    with pytest.raises(WoolNotFound):
        update_monument({}, "no-wool", "no-mon", {"team": "blue"})


def test_update_monument_not_found():
    w = _wool("red")
    data = _data(w)
    with pytest.raises(WoolNotFound):
        update_monument(data, w["id"], "nonexistent-mon", {"team": "blue"})


# ── delete_monument ───────────────────────────────────────────────────────────

def test_delete_monument_removes():
    m = _monument("blue")
    w = _wool("red", monuments=[m])
    data = _data(w)
    delete_monument(data, w["id"], m["id"])
    assert data["wools"][0]["monuments"] == []


def test_delete_monument_leaves_others():
    m1, m2 = _monument("blue"), _monument("red")
    w = _wool("red", monuments=[m1, m2])
    data = _data(w)
    delete_monument(data, w["id"], m1["id"])
    assert len(data["wools"][0]["monuments"]) == 1
    assert data["wools"][0]["monuments"][0]["team"] == "red"


def test_delete_monument_not_found():
    w = _wool("red")
    data = _data(w)
    with pytest.raises(WoolNotFound):
        delete_monument(data, w["id"], "nonexistent")
