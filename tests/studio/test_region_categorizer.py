"""Tests for the two-facet region categorization derivation.

Two layers:
  1. Synthetic unit tests — one rule of the contract per test, on hand-built data.
  2. Corpus oracles — the derivation reproduced against author-curated fixtures
     under tests/fixtures/region_categories/ (annealing_iv is verified; the others
     are proposed regression locks — see that dir's README).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pgm_map_studio.studio.services.region_categorizer import (
    categorize_regions,
    derive_region_facets,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "region_categories"


def _facets(data: dict) -> dict:
    return derive_region_facets(data)


def _cat(data: dict, rid: str) -> str:
    return _facets(data)[rid]["category"]


def _roles(data: dict, rid: str) -> list:
    return _facets(data)[rid]["roles"]


def _rect(rid: str) -> dict:
    return {"id": rid, "type": "rectangle", "min_x": 0, "min_z": 0, "max_x": 4, "max_z": 4}


# ── direct gameplay signals (contract §4.1–4.4) ───────────────────────────────

def test_spawn_from_spawns_reference():
    data = {"regions": {"s": _rect("s")}, "spawns": [{"region": "s"}]}
    assert _cat(data, "s") == "spawn"


def test_spawn_from_inline_region_dict():
    data = {"regions": {"s": _rect("s")}, "spawns": [{"region": _rect("s")}]}
    assert _cat(data, "s") == "spawn"


def test_observer_spawn():
    data = {"regions": {"o": _rect("o")}, "observer_spawn": {"region": "o"}}
    assert _cat(data, "o") == "observer_spawn"


def test_monument_from_grouped_wool():
    data = {
        "regions": {"m": _rect("m")},
        "wools": [{"color": "red", "monuments": [{"team": "blue", "monument_region": "m"}]}],
    }
    assert _cat(data, "m") == "monument"


def test_monument_from_wools_as_dict():
    data = {
        "regions": {"m": _rect("m")},
        "wools": {"red": {"color": "red", "monuments": [{"monument_region": "m"}]}},
    }
    assert _cat(data, "m") == "monument"


def test_spawner_spawn_region_is_wool_spawner():
    data = {"regions": {"sp": _rect("sp")},
            "spawners": [{"spawn_region": "sp", "items": [{"material": "wool"}]}]}
    assert _cat(data, "sp") == "wool_spawner"


def test_spawner_player_region_is_wool_room_not_spawner():
    # The refinement annealing_iv pins: player_region is the wool *room*.
    data = {"regions": {"pr": _rect("pr")},
            "spawners": [{"player_region": "pr", "items": [{"material": "wool"}]}]}
    assert _cat(data, "pr") == "wool_room"


def test_wool_spawner_requires_wool_item():
    data = {"regions": {"sp": _rect("sp")},
            "spawners": [{"spawn_region": "sp", "items": [{"material": "wool", "damage": 3}]}]}
    assert _cat(data, "sp") == "wool_spawner"


def test_non_wool_spawner_dispenser_is_mechanic():
    # icecream's gap-spawner dispenses golden apples → its dispenser is a mechanic.
    data = {
        "regions": {"sp": _rect("sp")},
        "spawners": [{"spawn_region": "sp", "items": [{"material": "golden apple"}]}],
    }
    assert _cat(data, "sp") == "mechanic"


def test_non_wool_spawner_player_region_keeps_identity():
    # The player_region a non-wool spawner feeds is often a real wool room
    # (peloponnesia gapple spawner → lime-woolroom); it must not become mechanic.
    data = {
        "regions": {"sp": _rect("sp"), "lime-woolroom": _rect("lime-woolroom")},
        "spawners": [{"spawn_region": "sp", "player_region": "lime-woolroom",
                      "items": [{"material": "golden apple"}]}],
    }
    assert _cat(data, "sp") == "mechanic"
    assert _cat(data, "lime-woolroom") == "wool_room"   # by name, not stolen


def test_wool_room_region_reference():
    data = {"regions": {"wr": _rect("wr")},
            "wools": [{"color": "red", "wool_room_region": "wr"}]}
    assert _cat(data, "wr") == "wool_room"


# ── enter polarity (contract §6) ──────────────────────────────────────────────

def test_enter_not_team_is_wool_room():
    data = {
        "regions": {"r": _rect("r")},
        "filters": {},
        "apply_rules": [{"enter": "not-blue", "region": "r"}],
    }
    assert _cat(data, "r") == "wool_room"
    assert "enter=not-blue" in _roles(data, "r")


def test_enter_only_team_spawn_named_is_spawn():
    data = {
        "regions": {"blue-spawn": _rect("blue-spawn")},
        "apply_rules": [{"enter": "only-blue", "region": "blue-spawn"}],
    }
    assert _cat(data, "blue-spawn") == "spawn"
    assert _roles(data, "blue-spawn") == ["enter=only-blue"]


def test_enter_only_team_wool_named_is_wool_room():
    data = {
        "regions": {"blue-woolroom": _rect("blue-woolroom")},
        "apply_rules": [{"enter": "only-red", "region": "blue-woolroom"}],
    }
    assert _cat(data, "blue-woolroom") == "wool_room"


def test_enter_only_unnamed_stays_other():
    data = {
        "regions": {"zone-a": _rect("zone-a")},
        "apply_rules": [{"enter": "only-blue", "region": "zone-a"}],
    }
    assert _cat(data, "zone-a") == "other"


# ── mechanic signals: renewables, velocity, kit ───────────────────────────────

def test_renewable_region_is_mechanic():
    data = {
        "regions": {"iron-regen": _rect("iron-regen")},
        "renewables": [{"region_id": "iron-regen", "renew_filter": "only-iron"}],
    }
    assert _cat(data, "iron-regen") == "mechanic"


def test_velocity_boost_region_is_mechanic():
    data = {
        "regions": {"portal-vel": _rect("portal-vel")},
        "apply_rules": [{"region": "portal-vel", "velocity": "0,1.4,0"}],
    }
    assert _cat(data, "portal-vel") == "mechanic"


def test_kit_region_is_mechanic():
    data = {
        "regions": {"jumping-area": _rect("jumping-area")},
        "apply_rules": [{"region": "jumping-area", "kit": "resistance-kit"}],
    }
    assert _cat(data, "jumping-area") == "mechanic"


def test_spawn_protection_kit_is_spawn_not_mechanic():
    # mushroom_gorge base-sides: a spawn-protection / spawn-regen kit ⇒ spawn.
    data = {
        "regions": {"blue-base-sides": _rect("blue-base-sides"),
                    "base-sides": _rect("base-sides")},
        "apply_rules": [
            {"filter": "only-blue", "region": "blue-base-sides", "lend_kit": "spawn-protection"},
            {"region": "base-sides", "kit": "spawn-regen"},
        ],
    }
    assert _cat(data, "blue-base-sides") == "spawn"
    assert _cat(data, "base-sides") == "spawn"


def test_leave_spawn_kit_is_not_spawn():
    # A "remove-spawn-effect" kit fires *outside* spawn — not a spawn signal.
    data = {
        "regions": {"wool-lanes": _rect("wool-lanes")},
        "apply_rules": [{"region": "wool-lanes", "kit": "remove-spawn-effect"}],
    }
    assert _cat(data, "wool-lanes") != "spawn"


def test_mechanic_action_does_not_steal_named_wool_room():
    # A wool-rooms union with wool regen is still a wool room (mechanic is a fallback).
    data = {
        "regions": {
            "blue-wool": _rect("blue-wool"), "red-wool": _rect("red-wool"),
            "wool-rooms": {"id": "wool-rooms", "type": "union",
                           "children": ["blue-wool", "red-wool"]},
        },
        "renewables": [{"region_id": "wool-rooms", "renew_filter": "only-wool"}],
    }
    assert _cat(data, "wool-rooms") == "wool_room"


def test_renewable_on_negative_keeps_rule_container():
    data = {
        "regions": {
            "inner": _rect("inner"),
            "neg": {"id": "neg", "type": "negative", "children": ["inner"]},
        },
        "renewables": [{"region_id": "neg"}],
    }
    assert _cat(data, "neg") == "other"
    assert "rule_container" in _roles(data, "neg")


# ── permissive placement build (vertex playable-area) ─────────────────────────

def test_region_as_block_place_filter_is_build():
    # vertex's global rule: block_place uses the *region* playable-area as a filter
    # ("you may place where you're inside it") → that region is the build area.
    data = {
        "regions": {
            "blue-side": _rect("blue-side"), "red-side": _rect("red-side"),
            "playable-area": {"id": "playable-area", "type": "union",
                              "children": ["blue-side", "red-side"]},
        },
        "filters": {"deny-bottom-layer": {"id": "deny-bottom-layer", "type": "deny",
                                          "child": "deny-bottom-layer__a"},
                    "deny-bottom-layer__a": {"id": "deny-bottom-layer__a", "type": "void"}},
        "apply_rules": [{"block_place": "playable-area", "block_break": "deny-bottom-layer"}],
    }
    assert _cat(data, "playable-area") == "build"
    assert _cat(data, "blue-side") == "build"   # recurses into children
    assert _cat(data, "red-side") == "build"


# ── apply-message signal (rockymine) ──────────────────────────────────────────

def test_message_spawn_classifies_unnamed_zone():
    data = {
        "regions": {"blue-prot": _rect("blue-prot")},
        "apply_rules": [{"enter": "only-blue", "region": "blue-prot",
                         "message": "You may not enter the opponent's spawn!"}],
    }
    assert _cat(data, "blue-prot") == "spawn"


def test_message_wool_room():
    data = {
        "regions": {"zone": _rect("zone")},
        "apply_rules": [{"block": "f", "region": "zone",
                         "message": "You may not edit the wool room!"}],
    }
    assert _cat(data, "zone") == "wool_room"


def test_message_spawner_is_mechanic_not_spawn():
    data = {
        "regions": {"zone": _rect("zone")},
        "apply_rules": [{"block": "never", "region": "zone",
                         "message": "You may not break the spawner"}],
    }
    assert _cat(data, "zone") == "mechanic"


def test_message_void_yields_no_category():
    data = {
        "regions": {"zone": _rect("zone")},
        "apply_rules": [{"block": "f", "region": "zone",
                         "message": "You may not edit the void!"}],
    }
    assert _cat(data, "zone") == "other"


@pytest.mark.parametrize("material", ["iron block", "gold block"])
def test_break_only_material_plus_deny_place_is_spawn(material):
    # The spawn-floor pattern is material-generic: some maps let players break
    # only iron in spawn, others only gold (rockymine).
    data = {
        "regions": {"spawn-protection": _rect("spawn-protection")},
        "filters": {
            "break-only": {"id": "break-only", "type": "material", "material": material},
            "deny-players": {"id": "deny-players", "type": "deny", "child": "deny-players__a"},
            "deny-players__a": {"id": "deny-players__a", "type": "team", "team": "x"},
        },
        "apply_rules": [{"block_break": "break-only", "block_place": "deny-players",
                         "region": "spawn-protection"}],
    }
    assert _cat(data, "spawn-protection") == "spawn"


# ── build: void-enforcement structure (contract §5) ───────────────────────────

def test_build_from_void_enforcement_negative():
    data = {
        "regions": {
            "build-area": _rect("build-area"),
            "not-build-area": {"id": "not-build-area", "type": "negative",
                               "children": ["build-area"]},
        },
        "filters": {
            "void-f": {"id": "void-f", "type": "not", "child": "void-f__anon_0"},
            "void-f__anon_0": {"id": "void-f__anon_0", "type": "void"},
        },
        "apply_rules": [{"block_place": "void-f", "region": "not-build-area"}],
    }
    assert _cat(data, "build-area") == "build"
    # the negative wrapper itself is a rule_container, not build
    assert _cat(data, "not-build-area") == "other"
    assert "rule_container" in _roles(data, "not-build-area")


def test_build_recurses_into_children():
    data = {
        "regions": {
            "area": {"id": "area", "type": "union", "children": ["area__anon_0"]},
            "area__anon_0": _rect("area__anon_0"),
            "no-build": {"id": "no-build", "type": "negative", "children": ["area"]},
        },
        "filters": {"v": {"id": "v", "type": "void"}},
        "apply_rules": [{"block_break": "v", "region": "no-build"}],
    }
    assert _cat(data, "area") == "build"
    assert _facets(data)["area__anon_0"]["category"] == "build"


def test_negative_without_void_filter_is_not_build():
    data = {
        "regions": {
            "inner": _rect("inner"),
            "not-inner": {"id": "not-inner", "type": "negative", "children": ["inner"]},
        },
        "filters": {"k": {"id": "k", "type": "material", "material": "iron block"}},
        "apply_rules": [{"block_break": "k", "region": "not-inner"}],
    }
    assert _cat(data, "inner") != "build"


# ── build: time-gated (contract §5, §8) ───────────────────────────────────────

def test_time_gated_build():
    data = {
        "regions": {"water-lanes": _rect("water-lanes")},
        "filters": {
            "open-late": {"id": "open-late", "type": "after", "duration": "30s"},
        },
        "apply_rules": [{"block": "open-late", "region": "water-lanes"}],
    }
    assert _cat(data, "water-lanes") == "build"
    assert "time_gated=30s" in _roles(data, "water-lanes")


# ── roles: rule wiring + flags ────────────────────────────────────────────────

def test_rule_events_allowlisted_and_sorted():
    data = {
        "regions": {"r": _rect("r")},
        "filters": {},
        "apply_rules": [
            {"block_place": "fp", "block_break": "fb", "region": "r"},
            {"block_physics": "phys", "use": "u", "kit": "k", "region": "r"},
        ],
    }
    # block_physics / use / kit are excluded; the rest are event-sorted.
    assert _roles(data, "r") == ["block_break=fb", "block_place=fp"]


def test_rule_container_only_for_negative_type():
    data = {
        "regions": {
            "child": _rect("child"),
            "neg": {"id": "neg", "type": "negative", "children": ["child"]},
        },
    }
    assert "rule_container" in _facets(data)["neg"]["roles"]
    assert _facets(data)["child"]["roles"] == []


# ── compound resolution + rule_group (contract §3, §7) ────────────────────────

def test_rule_group_over_uniform_wool_rooms():
    data = {
        "regions": {
            "blues-wr": _rect("blues-wr"),
            "reds-wr": _rect("reds-wr"),
            "woolrooms": {"id": "woolrooms", "type": "union",
                          "children": ["blues-wr", "reds-wr"]},
        },
        "filters": {},
        "spawners": [{"player_region": "blues-wr", "items": [{"material": "wool"}]},
                     {"player_region": "reds-wr", "items": [{"material": "wool"}]}],
        "apply_rules": [{"block_break": "wr-filter", "region": "woolrooms"}],
    }
    assert _cat(data, "woolrooms") == "wool_room"
    assert "rule_group" in _roles(data, "woolrooms")


def test_not_rule_group_through_opaque_complement():
    # A union wrapping an anonymous complement (spawns sculpted around monuments)
    # is NOT a rule_group, but still inherits its base category (spawn).
    data = {
        "regions": {
            "blue-spawn": _rect("blue-spawn"),
            "mon": {"id": "mon", "type": "block", "x": 1, "y": 1, "z": 1},
            "spawns__anon_0__anon_0": {"id": "spawns__anon_0__anon_0", "type": "union",
                                       "children": ["blue-spawn"]},
            "spawns__anon_0": {"id": "spawns__anon_0", "type": "complement",
                               "children": ["spawns__anon_0__anon_0", "mon"]},
            "spawns": {"id": "spawns", "type": "union", "children": ["spawns__anon_0"]},
        },
        "filters": {},
        "spawns": [{"region": "blue-spawn"}],
        "apply_rules": [{"block_break": "iron", "region": "spawns"}],
    }
    facets = _facets(data)
    assert facets["spawns"]["category"] == "spawn"
    assert "rule_group" not in facets["spawns"]["roles"]


def test_rule_group_detected_even_when_union_pre_categorized_by_message():
    # A message on the union pre-sets its category; the structural rule_group flag
    # must still be detected (regression: the flag was hidden by early-return).
    data = {
        "regions": {
            "blues-wr": _rect("blues-wr"),
            "reds-wr": _rect("reds-wr"),
            "woolrooms": {"id": "woolrooms", "type": "union",
                          "children": ["blues-wr", "reds-wr"]},
        },
        "filters": {},
        "spawners": [{"player_region": "blues-wr", "items": [{"material": "wool"}]},
                     {"player_region": "reds-wr", "items": [{"material": "wool"}]}],
        "apply_rules": [{"block_break": "wr-filter", "region": "woolrooms",
                         "message": "You may not edit the wool room!"}],
    }
    facets = _facets(data)
    assert facets["woolrooms"]["category"] == "wool_room"
    assert "rule_group" in facets["woolrooms"]["roles"]


def test_rule_group_not_fired_over_other_peers():
    data = {
        "regions": {
            "zone-a": _rect("zone-a"),
            "zone-b": _rect("zone-b"),
            "zones": {"id": "zones", "type": "union", "children": ["zone-a", "zone-b"]},
        },
        "filters": {},
        "apply_rules": [{"block_break": "f", "region": "zones"}],
    }
    facets = _facets(data)
    assert "rule_group" not in facets["zones"]["roles"]


def test_complement_takes_base_category_negative_does_not():
    data = {
        "regions": {
            "spawn-a": _rect("spawn-a"),
            "carve": {"id": "carve", "type": "block", "x": 1, "y": 1, "z": 1},
            "comp": {"id": "comp", "type": "complement", "children": ["spawn-a", "carve"]},
            "neg": {"id": "neg", "type": "negative", "children": ["spawn-a"]},
        },
        "spawns": [{"region": "spawn-a"}],
    }
    facets = _facets(data)
    assert facets["comp"]["category"] == "spawn"   # base child propagates
    assert facets["neg"]["category"] == "other"    # whole-world wrapper, no identity


# ── name heuristics (contract §4.8) ───────────────────────────────────────────

def test_name_heuristic_spawner_is_mechanic_not_spawn():
    # "spawner" → mechanic (ambiguous item); real wool spawners come from the
    # item-gated signal, never from the name alone.
    data = {"regions": {"gap-spawner": _rect("gap-spawner")}}
    assert _cat(data, "gap-spawner") == "mechanic"


def test_name_heuristic_wr_token_is_wool_room_but_wrapper_is_not():
    # "wr"/"wrs"/"wr2" are wool-room abbreviations; "wrapper" (a void-mechanic
    # region) must NOT match — regression for the substring catching "w-r-apper".
    data = {"regions": {
        "blue-wrs": _rect("blue-wrs"),
        "red-wr2": _rect("red-wr2"),
        "blue-base-wrapper": _rect("blue-base-wrapper"),
    }}
    assert _cat(data, "blue-wrs") == "wool_room"
    assert _cat(data, "red-wr2") == "wool_room"
    assert _cat(data, "blue-base-wrapper") == "other"


def test_name_heuristic_lane_is_not_build():
    # §5 caveat: a lane with no void parent and no rule is NOT build.
    data = {"regions": {"water-lane": _rect("water-lane")}}
    assert _cat(data, "water-lane") == "other"


# ── overrides (contract §10) ──────────────────────────────────────────────────

def test_region_categories_override_wins():
    data = {"regions": {"r": _rect("r")}, "region_categories": {"build": ["r"]}}
    # derivation alone would give 'other'; the user override wins in the flat map.
    assert _cat(data, "r") == "other"            # facets are pure derivation
    assert categorize_regions(data)["r"] == "build"  # overrides layered on top


def test_categorize_regions_flat_shape():
    data = {"regions": {"s": _rect("s")}, "spawns": [{"region": "s"}]}
    cats = categorize_regions(data)
    assert cats == {"s": "spawn"}


# ── curated oracles ───────────────────────────────────────────────────────────

ORACLE_MAPS = ["annealing_iv", "vertex", "acapulco", "icecream_sandwiched_ii"]


@pytest.mark.parametrize("map_name", ORACLE_MAPS)
def test_oracle_fixture(map_name):
    """Derivation reproduces the curated fixture for every named region.

    annealing_iv is author-verified (the correctness oracle); the rest are
    proposed regression locks. See tests/fixtures/region_categories/README.md.
    """
    data = json.loads((FIXTURE_DIR / "inputs" / f"{map_name}.json").read_text())
    oracle = json.loads((FIXTURE_DIR / f"{map_name}.json").read_text())
    facets = derive_region_facets(data)
    mismatches = {
        rid: {"expected": exp, "got": facets.get(rid)}
        for rid, exp in oracle.items()
        if facets.get(rid) != exp
    }
    assert not mismatches, f"{map_name}: {json.dumps(mismatches, indent=2)}"
