"""Tests for studio/services/spawn_editor.py."""
import pytest

from pgm_map_studio.studio.services.spawn_editor import (
    InvalidSpawnPayload,
    SpawnConflict,
    SpawnNotFound,
    add_spawn_link,
    delete_observer_spawn,
    delete_spawn_link,
    set_observer_spawn,
    update_spawn_link,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

def _data(*region_ids):
    """Minimal xml_data dict with the given region ids pre-populated."""
    return {"regions": {rid: {"id": rid, "type": "cylinder"} for rid in region_ids}}


def _data_with_spawn(region_id, team="red"):
    data = _data(region_id)
    data["spawns"] = [{"team": team, "kit": "", "yaw": 0.0, "region": region_id}]
    return data


def _data_with_observer(region_id):
    data = _data(region_id)
    data["observer_spawn"] = {"team": "", "kit": "", "yaw": 0.0, "region": region_id}
    return data


# ── add_spawn_link ────────────────────────────────────────────────────────────

class TestAddSpawnLink:
    def test_adds_to_spawns_list(self):
        data = _data("r1")
        add_spawn_link(data, {"region_id": "r1", "team": "red", "yaw": 90.0, "kit": "k"})
        assert len(data["spawns"]) == 1
        s = data["spawns"][0]
        assert s["region"] == "r1"
        assert s["team"] == "red"
        assert s["yaw"] == 90.0
        assert s["kit"] == "k"

    def test_missing_region_id_raises(self):
        data = _data("r1")
        with pytest.raises(InvalidSpawnPayload):
            add_spawn_link(data, {"team": "red"})

    def test_unknown_region_raises(self):
        data = _data("r1")
        with pytest.raises(SpawnNotFound):
            add_spawn_link(data, {"region_id": "missing", "team": "red"})

    def test_duplicate_raises_conflict(self):
        data = _data_with_spawn("r1", team="red")
        with pytest.raises(SpawnConflict):
            add_spawn_link(data, {"region_id": "r1", "team": "blue"})

    def test_inline_region_dict_form(self):
        """spawn.region stored as dict (legacy parsed form) should count as existing."""
        data = _data("r1")
        data["spawns"] = [{"team": "red", "kit": "", "yaw": 0.0, "region": {"id": "r1"}}]
        with pytest.raises(SpawnConflict):
            add_spawn_link(data, {"region_id": "r1", "team": "blue"})

    def test_defaults_applied(self):
        data = _data("r1")
        add_spawn_link(data, {"region_id": "r1"})
        s = data["spawns"][0]
        assert s["team"] == ""
        assert s["yaw"] == 0.0
        assert s["kit"] == ""

    def test_regions_in_list_form_still_found(self):
        """Freshly parsed xml_data has regions as a list — must not raise SpawnNotFound."""
        data = {"regions": [{"id": "r1", "type": "cylinder"}]}
        add_spawn_link(data, {"region_id": "r1", "team": "red"})
        assert data["spawns"][0]["region"] == "r1"
        assert isinstance(data["regions"], dict)


# ── update_spawn_link ─────────────────────────────────────────────────────────

class TestUpdateSpawnLink:
    def test_updates_team_yaw_kit(self):
        data = _data_with_spawn("r1", team="red")
        update_spawn_link(data, "r1", {"team": "blue", "yaw": 180.0, "kit": "sk"})
        s = data["spawns"][0]
        assert s["team"] == "blue"
        assert s["yaw"] == 180.0
        assert s["kit"] == "sk"

    def test_partial_update(self):
        data = _data_with_spawn("r1", team="red")
        update_spawn_link(data, "r1", {"yaw": 45.0})
        s = data["spawns"][0]
        assert s["team"] == "red"
        assert s["yaw"] == 45.0

    def test_unknown_region_raises(self):
        data = _data_with_spawn("r1")
        with pytest.raises(SpawnNotFound):
            update_spawn_link(data, "missing", {"team": "blue"})

    def test_inline_region_dict_form(self):
        data = _data("r1")
        data["spawns"] = [{"team": "red", "kit": "", "yaw": 0.0, "region": {"id": "r1"}}]
        update_spawn_link(data, "r1", {"team": "blue"})
        assert data["spawns"][0]["team"] == "blue"


# ── delete_spawn_link ─────────────────────────────────────────────────────────

class TestDeleteSpawnLink:
    def test_removes_spawn(self):
        data = _data_with_spawn("r1")
        delete_spawn_link(data, "r1")
        assert data["spawns"] == []

    def test_removes_correct_spawn_when_multiple(self):
        data = _data("r1", "r2")
        data["spawns"] = [
            {"team": "red", "kit": "", "yaw": 0.0, "region": "r1"},
            {"team": "blue", "kit": "", "yaw": 0.0, "region": "r2"},
        ]
        delete_spawn_link(data, "r1")
        assert len(data["spawns"]) == 1
        assert data["spawns"][0]["region"] == "r2"

    def test_unknown_region_raises(self):
        data = _data_with_spawn("r1")
        with pytest.raises(SpawnNotFound):
            delete_spawn_link(data, "missing")

    def test_no_spawns_raises(self):
        data = _data("r1")
        with pytest.raises(SpawnNotFound):
            delete_spawn_link(data, "r1")


# ── set_observer_spawn ────────────────────────────────────────────────────────

class TestSetObserverSpawn:
    def test_creates_observer_spawn(self):
        data = _data("obs")
        set_observer_spawn(data, {"region_id": "obs", "yaw": 90.0, "kit": "ok"})
        obs = data["observer_spawn"]
        assert obs["region"] == "obs"
        assert obs["team"] == ""
        assert obs["yaw"] == 90.0
        assert obs["kit"] == "ok"

    def test_replaces_existing_observer_spawn(self):
        data = _data_with_observer("obs1")
        data["regions"]["obs2"] = {"id": "obs2", "type": "point"}
        set_observer_spawn(data, {"region_id": "obs2"})
        assert data["observer_spawn"]["region"] == "obs2"

    def test_missing_region_id_raises(self):
        data = _data("obs")
        with pytest.raises(InvalidSpawnPayload):
            set_observer_spawn(data, {"yaw": 90.0})

    def test_unknown_region_raises(self):
        data = _data("obs")
        with pytest.raises(SpawnNotFound):
            set_observer_spawn(data, {"region_id": "missing"})

    def test_defaults_applied(self):
        data = _data("obs")
        set_observer_spawn(data, {"region_id": "obs"})
        obs = data["observer_spawn"]
        assert obs["yaw"] == 0.0
        assert obs["kit"] == ""

    def test_regions_in_list_form_still_found(self):
        """Freshly parsed xml_data has regions as a list — must not raise SpawnNotFound."""
        data = {"regions": [{"id": "obs", "type": "point"}]}
        set_observer_spawn(data, {"region_id": "obs"})
        assert data["observer_spawn"]["region"] == "obs"
        assert isinstance(data["regions"], dict)


# ── delete_observer_spawn ─────────────────────────────────────────────────────

class TestDeleteObserverSpawn:
    def test_removes_observer_spawn(self):
        data = _data_with_observer("obs")
        delete_observer_spawn(data)
        assert data["observer_spawn"] is None

    def test_no_observer_spawn_raises(self):
        data = _data("r1")
        with pytest.raises(SpawnNotFound):
            delete_observer_spawn(data)

    def test_null_observer_spawn_raises(self):
        data = _data("r1")
        data["observer_spawn"] = None
        with pytest.raises(SpawnNotFound):
            delete_observer_spawn(data)
