"""Tests for studio/services/apply_rule_editor.py (apply-rules CRUD, C4)."""
import json

import pytest

from pgm_map_studio.studio.services.apply_rule_editor import (
    ApplyRuleNotFound,
    InvalidApplyRulePayload,
    create_apply_rule,
    delete_apply_rule,
    list_apply_rules,
    update_apply_rule,
)


def _data(**over) -> dict:
    base = {
        "regions": {"spawns": {"id": "spawns", "type": "rectangle"},
                    "blues-woolroom": {"id": "blues-woolroom", "type": "union"}},
        "filters": {"not-blue": {"id": "not-blue", "type": "not", "child": "only-blue"},
                    "only-iron": {"id": "only-iron", "type": "material", "material": "iron block"}},
        "apply_rules": [],
    }
    base.update(over)
    return base


# ── synthetic ids ─────────────────────────────────────────────────────────────

def test_backfill_assigns_stable_ids():
    data = _data(apply_rules=[{"region": "spawns", "enter": "not-blue"},
                              {"region": "blues-woolroom", "block": "not-blue"}])
    rules = list_apply_rules(data)["apply_rules"]
    assert [r["id"] for r in rules] == ["rule_1", "rule_2"]
    # idempotent: a second pass keeps the same ids
    assert [r["id"] for r in list_apply_rules(data)["apply_rules"]] == ["rule_1", "rule_2"]


def test_backfill_respects_existing_ids():
    data = _data(apply_rules=[{"id": "rule_5", "region": "spawns", "enter": "not-blue"},
                              {"region": "spawns", "block": "only-iron"}])
    rules = list_apply_rules(data)["apply_rules"]
    assert rules[0]["id"] == "rule_5"
    assert rules[1]["id"] == "rule_6"        # max+1, no collision


# ── create ────────────────────────────────────────────────────────────────────

def test_create_assigns_id_and_appends():
    data = _data()
    res = create_apply_rule(data, {"region": "spawns", "enter": "not-blue"})
    assert res["id"] == "rule_1"
    assert data["apply_rules"][0]["enter"] == "not-blue"


def test_create_global_rule_without_region():
    data = _data()
    create_apply_rule(data, {"block_place": "spawns"})   # region-as-filter style
    assert data["apply_rules"][0]["block_place"] == "spawns"


def test_create_rejects_empty():
    with pytest.raises(InvalidApplyRulePayload):
        create_apply_rule(_data(), {"message": ""})


def test_create_rejects_unknown_region():
    with pytest.raises(InvalidApplyRulePayload):
        create_apply_rule(_data(), {"region": "ghost", "enter": "not-blue"})


def test_create_rejects_unknown_filter():
    with pytest.raises(InvalidApplyRulePayload):
        create_apply_rule(_data(), {"region": "spawns", "enter": "ghost"})


def test_create_accepts_inline_filter_descriptor():
    data = _data()
    create_apply_rule(data, {"region": "spawns", "block": "deny(void)"})
    assert data["apply_rules"][0]["block"] == "deny(void)"


def test_create_accepts_builtin_filter():
    data = _data()
    create_apply_rule(data, {"region": "spawns", "block": "never"})
    assert data["apply_rules"][0]["block"] == "never"


# ── update / delete ───────────────────────────────────────────────────────────

def test_update_preserves_id():
    data = _data()
    rid = create_apply_rule(data, {"region": "spawns", "enter": "not-blue"})["id"]
    update_apply_rule(data, rid, {"region": "spawns", "block": "only-iron",
                                  "message": "no edit"})
    rule = data["apply_rules"][0]
    assert rule["id"] == rid and rule["block"] == "only-iron" and "enter" not in rule


def test_update_missing_raises():
    with pytest.raises(ApplyRuleNotFound):
        update_apply_rule(_data(), "rule_9", {"region": "spawns", "enter": "not-blue"})


def test_delete_by_id():
    data = _data()
    rid = create_apply_rule(data, {"region": "spawns", "enter": "not-blue"})["id"]
    assert delete_apply_rule(data, rid) == {"id": rid}
    assert data["apply_rules"] == []


def test_delete_missing_raises():
    with pytest.raises(ApplyRuleNotFound):
        delete_apply_rule(_data(), "rule_9")


def test_ids_survive_deleting_a_different_rule():
    data = _data(apply_rules=[{"region": "spawns", "enter": "not-blue"},
                              {"region": "spawns", "block": "only-iron"}])
    rules = list_apply_rules(data)["apply_rules"]
    first_id = rules[0]["id"]
    delete_apply_rule(data, rules[1]["id"])
    assert data["apply_rules"][0]["id"] == first_id   # unchanged


# ── round-trip safety: synthetic ids are dropped on XML export ────────────────

def test_rule_ids_are_dropped_on_export():
    from pgm_map_studio.pgm import deserializer, serializer
    data = {
        "name": "t", "version": "1.0", "regions": {}, "filters": {},
        "apply_rules": [{"id": "rule_1", "region": "spawns", "enter": "not-blue"}],
    }
    model = deserializer.from_dict(json.loads(json.dumps(data)))
    out = serializer.to_dict(model)
    assert "id" not in out["apply_rules"][0]          # synthetic, not in the model
    assert out["apply_rules"][0].get("enter") == "not-blue"
