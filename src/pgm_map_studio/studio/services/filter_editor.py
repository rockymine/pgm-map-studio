"""CRUD for the map's filter registry (``xml_data.json["filters"]``).

Filters are an id-keyed dict of encoded filter shapes (see
``pgm/serializer.py::_encode_filter`` for the canonical form). Composite filters
reference their children by id (``children`` list, or a single ``child``);
``after``/``pulse`` reference another filter via ``filter``; ``blocks``/``region``
reference a region.

Authoring rules (C3):
- A new filter's ``type`` must be a known PGM filter type.
- Every referenced child filter must already exist (or be a builtin); region refs
  must exist.
- A filter cannot be deleted while it's still referenced (by an apply-rule, another
  filter, a renewable, or a block-drop rule) — the caller must unwire it first.
- The builtin ``never``/``always`` filters are always-available and never deleted.
"""
from __future__ import annotations

# Known PGM filter types (mirror of pgm/deserializer.py::_decode_filter).
_KNOWN_TYPES: frozenset[str] = frozenset({
    "all", "any", "one", "not", "deny", "allow",
    "team", "material", "void", "cause", "blocks",
    "carrying", "wearing", "holding",
    "alive", "dead", "participating", "observing",
    "match-running", "match-started", "grounded", "never", "always",
    "time", "after", "pulse", "offset",
    "variable", "completed", "objective",
    "kill-streak", "class", "region", "players", "spawn",
})

# Always-available builtins — referenceable even if not materialised, never deletable.
_BUILTIN_FILTERS: frozenset[str] = frozenset({"never", "always"})


class InvalidFilterPayload(ValueError):
    """Bad create/update payload (unknown type, missing/dangling ref)."""


class FilterConflict(Exception):
    """The filter id is already in use."""


class FilterNotFound(Exception):
    """No filter with the given id."""


class FilterInUse(Exception):
    """The filter is still referenced and cannot be deleted."""

    def __init__(self, fid: str, references: list[dict]):
        self.references = references
        super().__init__(
            f"filter {fid!r} is referenced by {len(references)} "
            f"item(s); unwire them first"
        )


# ── reference helpers ─────────────────────────────────────────────────────────

def _filters(data: dict) -> dict:
    return data.setdefault("filters", {})


def filter_filter_refs(fdict: dict) -> set[str]:
    """Filter ids a filter references (children / child / after-pulse filter)."""
    refs: set[str] = set(fdict.get("children") or [])
    if fdict.get("child"):
        refs.add(fdict["child"])
    if fdict.get("filter"):            # after/pulse filter_ref
        refs.add(fdict["filter"])
    return refs


def _filter_region_refs(fdict: dict) -> set[str]:
    """Region ids a filter references (blocks/region filter targets)."""
    if fdict.get("type") in ("blocks", "region") and fdict.get("region"):
        return {fdict["region"]}
    return set()


def _apply_filter_refs(rule: dict) -> set[str]:
    keys = ("enter", "leave", "block", "block_place", "block_break",
            "block_physics", "block_place_against", "use", "filter")
    return {rule[k] for k in keys if rule.get(k)}


def filter_references(data: dict, fid: str) -> list[dict]:
    """Everywhere ``fid`` is referenced — apply-rules, other filters, renewables,
    block-drop rules. Each entry: ``{"kind": ..., "id"/"region": ...}``."""
    refs: list[dict] = []
    for rule in data.get("apply_rules", []) or []:
        if fid in _apply_filter_refs(rule):
            refs.append({"kind": "apply_rule", "id": rule.get("id", "")})
    for other_id, fdict in _filters(data).items():
        if other_id != fid and fid in filter_filter_refs(fdict):
            refs.append({"kind": "filter", "id": other_id})
    for ren in data.get("renewables", []) or []:
        if fid in (ren.get("renew_filter"), ren.get("replace_filter")):
            refs.append({"kind": "renewable", "region": ren.get("region_id", "")})
    for bdr in data.get("block_drop_rules", []) or []:
        if bdr.get("filter_id") == fid:
            refs.append({"kind": "block_drop_rule", "region": bdr.get("region_id", "")})
    return refs


# ── validation ────────────────────────────────────────────────────────────────

def _validate_payload(data: dict, payload: dict, *, self_id: str | None = None) -> None:
    ftype = payload.get("type")
    if ftype not in _KNOWN_TYPES:
        raise InvalidFilterPayload(f"unknown filter type {ftype!r}")
    filters = _filters(data)
    for ref in filter_filter_refs(payload):
        if ref == self_id:
            raise InvalidFilterPayload(f"filter {ref!r} cannot reference itself")
        if ref not in filters and ref not in _BUILTIN_FILTERS:
            raise InvalidFilterPayload(f"references unknown filter {ref!r}")
    regions = data.get("regions", {})
    for ref in _filter_region_refs(payload):
        if ref not in regions:
            raise InvalidFilterPayload(f"references unknown region {ref!r}")


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_filters(data: dict) -> dict:
    """All filters plus a usage map ``{fid: [references]}`` for the editor."""
    filters = _filters(data)
    return {
        "filters": filters,
        "usage": {fid: filter_references(data, fid) for fid in filters},
    }


def create_filter(data: dict, payload: dict) -> dict:
    """Insert a new filter. Returns ``{"id": fid}``.

    Raises InvalidFilterPayload / FilterConflict.
    """
    filters = _filters(data)
    fid = (payload.get("id") or "").strip()
    if not fid:
        ftype = payload.get("type", "filter")
        i = 1
        while f"{ftype}_{i}" in filters:
            i += 1
        fid = f"{ftype}_{i}"
    elif fid in filters:
        raise FilterConflict(f"filter id {fid!r} already in use")

    _validate_payload(data, payload, self_id=fid)
    filters[fid] = {**payload, "id": fid}
    return {"id": fid}


def update_filter(data: dict, fid: str, payload: dict) -> dict:
    """Replace an existing filter's definition (id is immutable). Returns ``{"id"}``."""
    filters = _filters(data)
    if fid not in filters:
        raise FilterNotFound(f"no filter {fid!r}")
    merged = {**payload, "id": fid}
    if "type" not in merged:
        merged["type"] = filters[fid].get("type")
    _validate_payload(data, merged, self_id=fid)
    filters[fid] = merged
    return {"id": fid}


def delete_filter(data: dict, fid: str) -> dict:
    """Delete a filter once it has no inbound references. Returns ``{"id"}``.

    Raises FilterNotFound / FilterInUse (with the references).
    """
    filters = _filters(data)
    if fid in _BUILTIN_FILTERS:
        raise FilterInUse(fid, [{"kind": "builtin"}])
    if fid not in filters:
        raise FilterNotFound(f"no filter {fid!r}")
    refs = filter_references(data, fid)
    if refs:
        raise FilterInUse(fid, refs)
    del filters[fid]
    return {"id": fid}
