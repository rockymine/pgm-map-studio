"""Editor coverage for the real CTW filter/apply-rule vocabulary.

Each test builds a canonical pattern from docs/filter-use-cases.md through the C3/C4
editors and asserts it (a) creates and (b) survives the pgm codec round-trip
(``from_dict`` → ``to_dict``), i.e. an author can express the real corpus shapes and
they remain valid map data. The Appendix event×filter-type matrix is the source.
"""
import json

import pytest

from pgm_map_studio.pgm import deserializer, serializer
from pgm_map_studio.studio.services.apply_rule_editor import create_apply_rule
from pgm_map_studio.studio.services.filter_editor import create_filter


def _map() -> dict:
    """Minimal 2-team map with the regions the rules below target."""
    return {
        "name": "uc", "version": "1.0", "gamemode": "ctw",
        "teams": [{"id": "blue-team", "color": "blue"},
                  {"id": "red-team", "color": "red"}],
        "regions": {
            "blue-spawn": {"id": "blue-spawn", "type": "rectangle",
                           "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 4, "z": 4}}},
            "blues-woolroom": {"id": "blues-woolroom", "type": "rectangle",
                               "bounds_2d": {"min": {"x": 5, "z": 5}, "max": {"x": 9, "z": 9}}},
            "not-build-area": {"id": "not-build-area", "type": "rectangle",
                               "bounds_2d": {"min": {"x": 0, "z": 0}, "max": {"x": 20, "z": 20}}},
            "wool-blocks": {"id": "wool-blocks", "type": "rectangle",
                            "bounds_2d": {"min": {"x": 5, "z": 5}, "max": {"x": 9, "z": 9}}},
        },
        "filters": {}, "apply_rules": [],
        "renewables": [], "block_drop_rules": [],
    }


def _roundtrips(data: dict) -> dict:
    """Run data through the codec and return the re-serialized dict."""
    return serializer.to_dict(deserializer.from_dict(json.loads(json.dumps(data))))


# ── 1.1 spawn entry protection: team filter on enter ──────────────────────────

def test_spawn_entry_protection():
    data = _map()
    create_filter(data, {"id": "only-blue", "type": "team", "team": "blue-team"})
    create_apply_rule(data, {"region": "blue-spawn", "enter": "only-blue",
                             "message": "You may not enter the enemy's spawn!"})
    out = _roundtrips(data)
    assert out["filters"]["only-blue"] == {"id": "only-blue", "type": "team", "team": "blue-team"}
    assert out["apply_rules"][0]["enter"] == "only-blue"


# ── 1.2 wool-room access: not(team) on enter ──────────────────────────────────

def test_wool_room_access_not_team():
    data = _map()
    create_filter(data, {"id": "only-blue", "type": "team", "team": "blue-team"})
    create_filter(data, {"id": "not-blue", "type": "not", "child": "only-blue"})
    create_apply_rule(data, {"region": "blues-woolroom", "enter": "not-blue",
                             "message": "You may not enter your own wool room!"})
    out = _roundtrips(data)
    assert out["filters"]["not-blue"]["child"] == "only-blue"


# ── 2.1 spawn floor: material on block_break + all(material, cause) regen ─────

def test_spawn_iron_floor_and_regen_pair():
    data = _map()
    create_filter(data, {"id": "only-iron", "type": "material", "material": "iron block"})
    create_filter(data, {"id": "from-world", "type": "cause", "cause": "world"})
    create_filter(data, {"id": "only-iron-regen", "type": "all",
                         "children": ["only-iron", "from-world"]})
    create_apply_rule(data, {"region": "blue-spawn", "block_break": "only-iron",
                             "block_place": "only-iron-regen",
                             "message": "You may only break iron blocks in spawn!"})
    out = _roundtrips(data)
    assert out["filters"]["only-iron-regen"]["children"] == ["only-iron", "from-world"]
    assert out["apply_rules"][0]["block_break"] == "only-iron"


# ── 2.2 wool-room block protection: all(team, blocks) on block ────────────────

def test_wool_room_block_protection_all_team_blocks():
    data = _map()
    create_filter(data, {"id": "only-red", "type": "team", "team": "red-team"})
    create_filter(data, {"id": "wool-mats", "type": "blocks",
                         "region": "wool-blocks", "child": "never"})
    create_filter(data, {"id": "blues-wr-filter", "type": "all",
                         "children": ["only-red", "wool-mats"]})
    create_apply_rule(data, {"region": "blues-woolroom", "block": "blues-wr-filter",
                             "message": "You may not modify the wool room!"})
    out = _roundtrips(data)
    assert out["filters"]["blues-wr-filter"]["type"] == "all"
    assert out["filters"]["wool-mats"]["region"] == "wool-blocks"


# ── 2.3 full lockdown: builtin never on block ─────────────────────────────────

def test_full_lockdown_never():
    data = _map()
    create_apply_rule(data, {"region": "blue-spawn", "block": "never",
                             "message": "You may not modify the spawn area!"})
    assert _roundtrips(data)["apply_rules"][0]["block"] == "never"


# ── 2.4 void boundary: not(void) on block_place + inline deny(void) ───────────

def test_void_boundary_filter_and_inline():
    data = _map()
    create_filter(data, {"id": "is-void", "type": "void"})
    create_filter(data, {"id": "not-void", "type": "not", "child": "is-void"})
    create_apply_rule(data, {"region": "not-build-area", "block_place": "not-void",
                             "message": "You may not edit the void!"})
    # inline descriptor form is accepted as-is
    create_apply_rule(data, {"region": "not-build-area", "block_break": "deny(void)"})
    out = _roundtrips(data)
    assert out["filters"]["not-void"]["child"] == "is-void"
    assert out["apply_rules"][1]["block_break"] == "deny(void)"


# ── 2.5 physics denial: deny(any(material, material)) on block_physics ────────

def test_physics_denial_deny_any_materials():
    data = _map()
    create_filter(data, {"id": "redstone", "type": "material", "material": "redstone wire"})
    create_filter(data, {"id": "water", "type": "material", "material": "water"})
    create_filter(data, {"id": "phys-mats", "type": "any", "children": ["redstone", "water"]})
    create_filter(data, {"id": "deny-physics", "type": "deny", "child": "phys-mats"})
    create_apply_rule(data, {"region": "not-build-area", "block_physics": "deny-physics"})
    out = _roundtrips(data)
    assert out["filters"]["phys-mats"]["children"] == ["redstone", "water"]
    assert out["filters"]["deny-physics"]["child"] == "phys-mats"


# ── 3.x kit zone + 4.1 jump pad (velocity) ────────────────────────────────────

def test_kit_and_jump_pad_actions():
    data = _map()
    create_filter(data, {"id": "only-blue", "type": "team", "team": "blue-team"})
    create_apply_rule(data, {"region": "blues-woolroom", "lend_kit": "wool-room-kit"})
    create_apply_rule(data, {"region": "blue-spawn", "filter": "only-blue",
                             "velocity": "0,1.4,0"})
    out = _roundtrips(data)
    assert out["apply_rules"][0]["lend_kit"] == "wool-room-kit"
    assert out["apply_rules"][1]["velocity"] == "0,1.4,0"


# ── 6.1 time-gated: after(filter, duration) on block ──────────────────────────

def test_time_gated_after_filter():
    data = _map()
    create_filter(data, {"id": "is-void", "type": "void"})
    create_filter(data, {"id": "open-late", "type": "after",
                         "filter": "is-void", "duration": "30s"})
    create_apply_rule(data, {"region": "not-build-area", "block": "open-late",
                             "message": "void area!"})
    out = _roundtrips(data)
    assert out["filters"]["open-late"]["duration"] == "30s"
    assert out["filters"]["open-late"]["filter"] == "is-void"


# ── composition is unrestricted: an "odd" stack still builds & round-trips ─────

def test_unusual_but_valid_stack_is_allowed():
    # material on enter is semantically odd, but wrapping/stacking is the author's
    # call — the editor permits it (only dangling refs are rejected).
    data = _map()
    create_filter(data, {"id": "gold", "type": "material", "material": "gold block"})
    create_filter(data, {"id": "blue", "type": "team", "team": "blue-team"})
    create_filter(data, {"id": "odd", "type": "all", "children": ["gold", "blue"]})
    create_apply_rule(data, {"region": "blue-spawn", "enter": "odd"})
    assert _roundtrips(data)["filters"]["odd"]["children"] == ["gold", "blue"]
