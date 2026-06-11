"""filter_wiring — C9: suggest + apply the v1 filter↔region wiring templates.

See ``docs/contracts/filter-region-wiring.md``. A template is a pre-built
Filter + ApplyRule (+ compound) combination grounded in the corpus's most common
shapes. Templates emit **standard** entries through the C3/C4/C8 services — they
add no new persisted type. The flow is *suggest + confirm*: ``suggest`` scans a
map for signals and proposes wirings; the caller confirms and posts one back to
``apply_template``, which mutates *data* in place.
"""
from __future__ import annotations

from pgm_map_studio.studio.services import region_editor
from pgm_map_studio.studio.services.apply_rule_editor import create_apply_rule
from pgm_map_studio.studio.services.filter_editor import create_filter
from pgm_map_studio.studio.services.region_categorizer import derive_region_facets


class WiringError(Exception):
    """Bad template name or params."""


TEMPLATES = (
    "spawn_protection",
    "wool_room_defense",
    "wool_room_edit",
    "build_void_enforcement",
)


# ── shared helpers ──────────────────────────────────────────────────────────────

def _team_slug(team_id: str) -> str:
    return team_id[:-5] if team_id.endswith("-team") else team_id


def _ensure_team_filter(data: dict, team_id: str, *, negate: bool = False) -> str:
    """Idempotently ensure an ``only-<slug>`` (and, if negate, ``not-<slug>``)
    team filter exists. Returns the id to reference."""
    filters = data.setdefault("filters", {})
    slug = _team_slug(team_id)
    only_id = f"only-{slug}"
    if only_id not in filters:
        create_filter(data, {"type": "team", "team": team_id, "id": only_id})
    if not negate:
        return only_id
    not_id = f"not-{slug}"
    if not_id not in filters:
        create_filter(data, {"type": "not", "child": only_id, "id": not_id})
    return not_id


def _region_id(ref) -> str | None:
    if isinstance(ref, str):
        return ref
    if isinstance(ref, dict):
        return ref.get("id")
    return None


def _has_rule(data: dict, region_id: str, event: str) -> bool:
    return any(
        r.get("region") == region_id and r.get(event)
        for r in data.get("apply_rules", [])
    )


def _wool_owner(data: dict, wool: dict) -> str | None:
    """The defending (owning) team = the one team absent from this wool's
    monuments. Returns None when ambiguous (0 or >1 missing)."""
    if wool.get("team"):
        return wool["team"]
    team_ids = {t.get("id") for t in data.get("teams", []) if t.get("id")}
    monument_teams = {m.get("team") for m in wool.get("monuments", [])}
    missing = team_ids - monument_teams
    return missing.pop() if len(missing) == 1 else None


# ── appliers (one per template) ─────────────────────────────────────────────────

def apply_spawn_protection(data: dict, *, region: str, team: str) -> dict:
    fid = _ensure_team_filter(data, team)
    res = create_apply_rule(data, {
        "region": region, "enter": fid,
        "message": "You may not enter the enemy's spawn!",
    })
    return {"rule_id": res["id"], "filter_id": fid}


def apply_wool_room_defense(data: dict, *, region: str, owner: str) -> dict:
    fid = _ensure_team_filter(data, owner, negate=True)  # not-<owner>
    res = create_apply_rule(data, {
        "region": region, "enter": fid,
        "message": "You may not enter your own wool room!",
    })
    return {"rule_id": res["id"], "filter_id": fid}


def apply_wool_room_edit(data: dict, *, region: str, owner: str) -> dict:
    fid = _ensure_team_filter(data, owner, negate=True)  # only non-owners may edit
    res = create_apply_rule(data, {
        "region": region, "block": fid,
        "message": "You may not edit the wool room!",
    })
    return {"rule_id": res["id"], "filter_id": fid}


def apply_build_void_enforcement(data: dict, *, build_region_ids: list[str]) -> dict:
    """Group the build regions into a ``negative`` ("everywhere except build") and
    deny placement over the void there."""
    if not build_region_ids:
        raise WiringError("no build regions to enforce")
    neg = region_editor.group_regions(
        data, {"child_ids": list(build_region_ids), "type": "negative"}
    )
    res = create_apply_rule(data, {
        "region": neg["id"], "block_place": "deny(void)",
        "message": "You may not build here!",
    })
    return {"region_id": neg["id"], "rule_id": res["id"]}


_APPLIERS = {
    "spawn_protection": apply_spawn_protection,
    "wool_room_defense": apply_wool_room_defense,
    "wool_room_edit": apply_wool_room_edit,
    "build_void_enforcement": apply_build_void_enforcement,
}


def apply_template(data: dict, template: str, params: dict) -> dict:
    """Execute one template. Returns ``{"template", ...applier result}``.
    Raises WiringError on a bad template name or params."""
    fn = _APPLIERS.get(template)
    if fn is None:
        raise WiringError(f"unknown template {template!r}")
    try:
        result = fn(data, **(params or {}))
    except TypeError as exc:  # missing / extra params
        raise WiringError(f"invalid params for {template!r}: {exc}") from exc
    return {"template": template, **result}


# ── suggestions ─────────────────────────────────────────────────────────────────

def _any_void_enforcement(data: dict) -> bool:
    for rule in data.get("apply_rules", []):
        for ev in ("block_place", "block"):
            val = rule.get(ev)
            if isinstance(val, str) and "void" in val:
                return True
    return False


def suggest(data: dict) -> dict:
    """Scan the map and propose wirings the author can confirm. Returns
    ``{"suggestions": [{template, label, params}, …]}``."""
    regions = data.get("regions", {})
    out: list[dict] = []

    # Spawn protection — a team spawn region with no enter rule.
    for spawn in data.get("spawns", []):
        rid = _region_id(spawn.get("region"))
        team = spawn.get("team")
        if rid and team and rid in regions and not _has_rule(data, rid, "enter"):
            out.append({
                "template": "spawn_protection",
                "label": f"Protect {team} spawn from entry",
                "params": {"region": rid, "team": team},
            })

    # Wool-room defense + edit — a wool room with a derived owner.
    for wool in data.get("wools", []):
        rid = _region_id(wool.get("wool_room_region"))
        if not rid or rid not in regions:
            continue
        owner = _wool_owner(data, wool)
        if not owner:
            continue
        if not _has_rule(data, rid, "enter"):
            out.append({
                "template": "wool_room_defense",
                "label": f"Exclude {owner} from their own wool room",
                "params": {"region": rid, "owner": owner},
            })
        if not _has_rule(data, rid, "block"):
            out.append({
                "template": "wool_room_edit",
                "label": f"Restrict {owner}'s wool-room editing to opponents",
                "params": {"region": rid, "owner": owner},
            })

    # Build/void enforcement — build regions present, no void rule yet.
    build_ids = [
        rid for rid, facet in derive_region_facets(data).items()
        if facet.get("category") == "build"
    ]
    if build_ids and not _any_void_enforcement(data):
        out.append({
            "template": "build_void_enforcement",
            "label": "Enforce the void boundary outside the build regions",
            "params": {"build_region_ids": build_ids},
        })

    return {"suggestions": out}
