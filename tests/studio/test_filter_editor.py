"""Tests for studio/services/filter_editor.py (filters CRUD, C3)."""
import pytest

from pgm_map_studio.studio.services.filter_editor import (
    FilterConflict,
    FilterInUse,
    FilterNotFound,
    InvalidFilterPayload,
    create_filter,
    delete_filter,
    filter_references,
    list_filters,
    update_filter,
)


def _data(**over) -> dict:
    base = {
        "regions": {"spawns": {"id": "spawns", "type": "rectangle"}},
        "filters": {
            "only-blue": {"id": "only-blue", "type": "team", "team": "blue-team"},
            "not-blue": {"id": "not-blue", "type": "not", "child": "only-blue"},
        },
        "apply_rules": [],
        "renewables": [],
        "block_drop_rules": [],
    }
    base.update(over)
    return base


# ── create ────────────────────────────────────────────────────────────────────

def test_create_leaf_filter():
    data = _data()
    res = create_filter(data, {"id": "only-iron", "type": "material", "material": "iron block"})
    assert res == {"id": "only-iron"}
    assert data["filters"]["only-iron"]["material"] == "iron block"


def test_create_void_filter():
    data = _data()
    create_filter(data, {"id": "v", "type": "void"})
    assert data["filters"]["v"]["type"] == "void"


def test_create_composite_with_existing_children():
    data = _data()
    create_filter(data, {"id": "edit-deny", "type": "all",
                         "children": ["only-blue", "not-blue"]})
    assert data["filters"]["edit-deny"]["children"] == ["only-blue", "not-blue"]


def test_create_autogenerates_id():
    data = _data()
    res = create_filter(data, {"type": "void"})
    assert res["id"] == "void_1" and "void_1" in data["filters"]


def test_create_rejects_unknown_type():
    with pytest.raises(InvalidFilterPayload):
        create_filter(_data(), {"id": "x", "type": "bogus"})


def test_create_rejects_dangling_child():
    with pytest.raises(InvalidFilterPayload):
        create_filter(_data(), {"id": "x", "type": "not", "child": "ghost"})


def test_create_allows_builtin_child_ref():
    data = _data()
    create_filter(data, {"id": "wrap", "type": "not", "child": "never"})
    assert "wrap" in data["filters"]


def test_create_rejects_dangling_region_ref():
    with pytest.raises(InvalidFilterPayload):
        create_filter(_data(), {"id": "b", "type": "blocks", "region": "ghost", "child": "never"})


def test_create_rejects_duplicate_id():
    with pytest.raises(FilterConflict):
        create_filter(_data(), {"id": "only-blue", "type": "void"})


def test_create_rejects_self_reference():
    with pytest.raises(InvalidFilterPayload):
        create_filter(_data(), {"id": "loop", "type": "not", "child": "loop"})


# ── update ────────────────────────────────────────────────────────────────────

def test_update_changes_definition():
    data = _data()
    update_filter(data, "only-blue", {"type": "team", "team": "red-team"})
    assert data["filters"]["only-blue"]["team"] == "red-team"


def test_update_missing_raises():
    with pytest.raises(FilterNotFound):
        update_filter(_data(), "ghost", {"type": "void"})


# ── delete + references ───────────────────────────────────────────────────────

def test_delete_unreferenced():
    data = _data()
    create_filter(data, {"id": "lonely", "type": "void"})
    assert delete_filter(data, "lonely") == {"id": "lonely"}
    assert "lonely" not in data["filters"]


def test_delete_rejected_when_referenced_by_filter():
    # not-blue references only-blue
    with pytest.raises(FilterInUse) as exc:
        delete_filter(_data(), "only-blue")
    assert {"kind": "filter", "id": "not-blue"} in exc.value.references


def test_delete_rejected_when_referenced_by_apply_rule():
    data = _data(apply_rules=[{"id": "rule_1", "region": "spawns", "enter": "not-blue"}])
    with pytest.raises(FilterInUse) as exc:
        delete_filter(data, "not-blue")
    assert {"kind": "apply_rule", "id": "rule_1"} in exc.value.references


def test_delete_rejected_when_referenced_by_renewable():
    data = _data(renewables=[{"region_id": "spawns", "renew_filter": "only-blue"}])
    with pytest.raises(FilterInUse) as exc:
        delete_filter(data, "only-blue")
    assert any(r["kind"] == "renewable" for r in exc.value.references)


def test_delete_builtin_rejected():
    data = _data(filters={"never": {"id": "never", "type": "never"}})
    with pytest.raises(FilterInUse):
        delete_filter(data, "never")


def test_delete_missing_raises():
    with pytest.raises(FilterNotFound):
        delete_filter(_data(), "ghost")


def test_delete_after_unwiring():
    data = _data()
    # remove the only referrer, then the filter deletes cleanly
    del data["filters"]["not-blue"]
    assert delete_filter(data, "only-blue") == {"id": "only-blue"}


# ── list / usage ──────────────────────────────────────────────────────────────

def test_list_reports_usage():
    data = _data(apply_rules=[{"id": "rule_1", "region": "spawns", "enter": "not-blue"}])
    out = list_filters(data)
    assert "only-blue" in out["filters"]
    assert out["usage"]["only-blue"] == [{"kind": "filter", "id": "not-blue"}]
    assert {"kind": "apply_rule", "id": "rule_1"} in out["usage"]["not-blue"]


def test_filter_references_empty_for_unused():
    data = _data()
    create_filter(data, {"id": "free", "type": "void"})
    assert filter_references(data, "free") == []
