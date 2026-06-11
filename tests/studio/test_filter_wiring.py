"""Tests for studio/services/filter_wiring.py (C9 templates + suggestions)."""
import pytest

from pgm_map_studio.studio.services import filter_wiring as fw


def _rect(rid):
    return {"id": rid, "type": "rectangle",
            "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 10, "z": 10}}}


# ── appliers ────────────────────────────────────────────────────────────────────

class TestAppliers:
    def setup_method(self):
        self.data = {
            "teams": [{"id": "blue-team"}, {"id": "red-team"}],
            "regions": {"blue-spawn": _rect("blue-spawn"), "red-room": _rect("red-room"),
                        "b1": _rect("b1"), "b2": _rect("b2")},
            "filters": {}, "apply_rules": [],
            "spawns": [], "wools": [],
        }

    def test_spawn_protection_creates_filter_and_rule(self):
        res = fw.apply_spawn_protection(self.data, region="blue-spawn", team="blue-team")
        assert self.data["filters"]["only-blue"] == {"type": "team", "team": "blue-team", "id": "only-blue"}
        rule = next(r for r in self.data["apply_rules"] if r["id"] == res["rule_id"])
        assert rule["region"] == "blue-spawn" and rule["enter"] == "only-blue"

    def test_wool_room_defense_uses_not_owner(self):
        res = fw.apply_wool_room_defense(self.data, region="red-room", owner="red-team")
        assert self.data["filters"]["not-red"]["type"] == "not"
        assert self.data["filters"]["not-red"]["child"] == "only-red"
        rule = next(r for r in self.data["apply_rules"] if r["id"] == res["rule_id"])
        assert rule["enter"] == "not-red"

    def test_wool_room_edit_uses_block(self):
        res = fw.apply_wool_room_edit(self.data, region="red-room", owner="red-team")
        rule = next(r for r in self.data["apply_rules"] if r["id"] == res["rule_id"])
        assert rule["block"] == "not-red"

    def test_build_void_groups_negative_and_denies_void(self):
        res = fw.apply_build_void_enforcement(self.data, build_region_ids=["b1", "b2"])
        neg = self.data["regions"][res["region_id"]]
        assert neg["type"] == "negative" and neg["children"] == ["b1", "b2"]
        rule = next(r for r in self.data["apply_rules"] if r["id"] == res["rule_id"])
        assert rule["region"] == res["region_id"] and rule["block_place"] == "deny(void)"

    def test_build_void_empty_raises(self):
        with pytest.raises(fw.WiringError):
            fw.apply_build_void_enforcement(self.data, build_region_ids=[])

    def test_ensure_team_filter_idempotent(self):
        fw.apply_spawn_protection(self.data, region="blue-spawn", team="blue-team")
        fw.apply_spawn_protection(self.data, region="b1", team="blue-team")
        only_blue = [f for f in self.data["filters"] if f == "only-blue"]
        assert len(only_blue) == 1  # not duplicated


# ── apply_template dispatch ─────────────────────────────────────────────────────

class TestApplyTemplate:
    def setup_method(self):
        self.data = {"teams": [{"id": "blue-team"}],
                     "regions": {"blue-spawn": _rect("blue-spawn")},
                     "filters": {}, "apply_rules": []}

    def test_dispatch_runs_applier(self):
        res = fw.apply_template(self.data, "spawn_protection",
                                {"region": "blue-spawn", "team": "blue-team"})
        assert res["template"] == "spawn_protection" and "rule_id" in res

    def test_unknown_template_raises(self):
        with pytest.raises(fw.WiringError):
            fw.apply_template(self.data, "nope", {})

    def test_bad_params_raises(self):
        with pytest.raises(fw.WiringError):
            fw.apply_template(self.data, "spawn_protection", {"region": "blue-spawn"})  # no team


# ── suggestions ─────────────────────────────────────────────────────────────────

class TestSuggest:
    def setup_method(self):
        self.data = {
            "teams": [{"id": "blue-team"}, {"id": "red-team"}],
            "regions": {"blue-spawn": _rect("blue-spawn"), "red-room": _rect("red-room")},
            "filters": {}, "apply_rules": [],
            "spawns": [{"team": "blue-team", "region": "blue-spawn"}],
            # red wool captured by blue → red-team is the (defending) owner
            "wools": [{"color": "red", "wool_room_region": "red-room",
                       "monuments": [{"team": "blue-team"}]}],
        }

    def _templates(self):
        return {s["template"] for s in fw.suggest(self.data)["suggestions"]}

    def test_suggests_spawn_protection(self):
        s = next(x for x in fw.suggest(self.data)["suggestions"]
                 if x["template"] == "spawn_protection")
        assert s["params"] == {"region": "blue-spawn", "team": "blue-team"}

    def test_suggests_wool_room_defense_with_derived_owner(self):
        s = next(x for x in fw.suggest(self.data)["suggestions"]
                 if x["template"] == "wool_room_defense")
        assert s["params"] == {"region": "red-room", "owner": "red-team"}

    def test_suggests_wool_room_edit(self):
        assert "wool_room_edit" in self._templates()

    def test_no_spawn_suggestion_once_wired(self):
        fw.apply_template(self.data, "spawn_protection",
                          {"region": "blue-spawn", "team": "blue-team"})
        assert "spawn_protection" not in self._templates()

    def test_no_wool_defense_suggestion_once_wired(self):
        fw.apply_template(self.data, "wool_room_defense",
                          {"region": "red-room", "owner": "red-team"})
        assert "wool_room_defense" not in self._templates()

    def test_ambiguous_owner_skips_wool_suggestions(self):
        # both teams have monuments on this wool → no single defender
        self.data["wools"][0]["monuments"] = [{"team": "blue-team"}, {"team": "red-team"}]
        templates = self._templates()
        assert "wool_room_defense" not in templates and "wool_room_edit" not in templates
