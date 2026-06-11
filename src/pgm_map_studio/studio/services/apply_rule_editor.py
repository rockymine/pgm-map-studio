"""CRUD for the map's apply-rules (``xml_data.json["apply_rules"]``).

Apply-rules are a flat list of encoded rule dicts (see
``pgm/serializer.py::_encode_apply_rule``): a region (or none, for a global rule),
optional event→filter keys (``enter``/``block``/``block_break``/…), and actions
(``kit``/``lend_kit``/``velocity``/``message``).

The list has no ids in the PGM model, so the editor assigns a **stable synthetic id**
(``rule_<n>``) — an editor-only field persisted in ``xml_data.json`` and dropped on
XML export (``_decode_apply_rule`` ignores unknown keys; ``_encode_apply_rule`` never
emits it). Ids are backfilled on first access and never reused.

Filter/region refs may be registry ids *or* inline descriptors (``deny(void)``,
``all(a, b)``) — only plain-id refs that don't resolve are rejected.
"""
from __future__ import annotations

import re

from pgm_map_studio.studio.services._payload import require_dict

_RULE_FILTER_KEYS = (
    "enter", "leave", "block", "block_place", "block_break",
    "block_physics", "block_place_against", "use", "filter",
)
_ACTION_KEYS = ("kit", "lend_kit", "velocity", "message")
_ID_PREFIX = "rule_"
_SIMPLE_REF = re.compile(r"[A-Za-z0-9_-]+")
_BUILTIN_FILTERS = frozenset({"never", "always"})
_BUILTIN_REGIONS = frozenset({"everywhere", "nowhere"})


class InvalidApplyRulePayload(ValueError):
    """Bad create/update payload (empty, or a dangling plain-id ref)."""


class ApplyRuleNotFound(Exception):
    """No apply-rule with the given id."""


def _rules(data: dict) -> list:
    return data.setdefault("apply_rules", [])


def _ensure_rule_ids(data: dict) -> list:
    """Backfill ``rule_<n>`` on any id-less rule; ids, once set, are stable."""
    rules = _rules(data)
    used = {r["id"] for r in rules if isinstance(r, dict) and r.get("id")}
    next_n = 1 + max(
        (int(m.group(1)) for r in used if (m := re.fullmatch(_ID_PREFIX + r"(\d+)", r))),
        default=0,
    )
    for rule in rules:
        if isinstance(rule, dict) and not rule.get("id"):
            rule["id"] = f"{_ID_PREFIX}{next_n}"
            next_n += 1
    return rules


def _is_simple_ref(value: str) -> bool:
    """A bare id (validatable), vs an inline filter descriptor like ``deny(void)``."""
    return bool(_SIMPLE_REF.fullmatch(value))


def _validate(data: dict, payload: dict) -> None:
    require_dict(payload, InvalidApplyRulePayload)
    if not any(payload.get(k) for k in (*_RULE_FILTER_KEYS, *_ACTION_KEYS, "region")):
        raise InvalidApplyRulePayload("apply-rule has no region, filter, or action")
    regions = data.get("regions", {})
    filters = data.get("filters", {})
    region = payload.get("region")
    if region and _is_simple_ref(region) \
            and region not in regions and region not in _BUILTIN_REGIONS:
        raise InvalidApplyRulePayload(f"references unknown region {region!r}")
    # A block/place/break/enter filter value may be a filter id, a *region* used as
    # a filter (region-as-filter, e.g. vertex's block_place="playable-area"), a
    # builtin, or an inline descriptor — only reject a plain id that resolves to none.
    for key in _RULE_FILTER_KEYS:
        val = payload.get(key)
        if val and _is_simple_ref(val) \
                and val not in filters and val not in regions and val not in _BUILTIN_FILTERS:
            raise InvalidApplyRulePayload(f"{key} references unknown filter/region {val!r}")


def _find(data: dict, rule_id: str) -> dict:
    for rule in _ensure_rule_ids(data):
        if rule.get("id") == rule_id:
            return rule
    raise ApplyRuleNotFound(f"no apply-rule {rule_id!r}")


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_apply_rules(data: dict) -> dict:
    return {"apply_rules": _ensure_rule_ids(data)}


def create_apply_rule(data: dict, payload: dict) -> dict:
    """Append a new apply-rule with a fresh ``rule_<n>`` id. Returns ``{"id"}``."""
    _validate(data, payload)
    rules = _ensure_rule_ids(data)
    used = {r["id"] for r in rules if r.get("id")}
    n = 1
    while f"{_ID_PREFIX}{n}" in used:
        n += 1
    rule = {k: v for k, v in payload.items() if k != "id"}
    rule["id"] = f"{_ID_PREFIX}{n}"
    rules.append(rule)
    return {"id": rule["id"]}


def update_apply_rule(data: dict, rule_id: str, payload: dict) -> dict:
    """Replace an apply-rule's fields (id preserved). Returns ``{"id"}``."""
    rule = _find(data, rule_id)
    _validate(data, payload)
    rule.clear()
    rule.update({k: v for k, v in payload.items() if k != "id"})
    rule["id"] = rule_id
    return {"id": rule_id}


def delete_apply_rule(data: dict, rule_id: str) -> dict:
    """Remove an apply-rule by id. Returns ``{"id"}``. Raises ApplyRuleNotFound."""
    rules = _ensure_rule_ids(data)
    for i, rule in enumerate(rules):
        if rule.get("id") == rule_id:
            rules.pop(i)
            return {"id": rule_id}
    raise ApplyRuleNotFound(f"no apply-rule {rule_id!r}")
