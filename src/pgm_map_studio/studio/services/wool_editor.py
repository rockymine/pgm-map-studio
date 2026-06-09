from __future__ import annotations

import uuid

VALID_WOOL_COLORS = {
    "white", "orange", "magenta", "light_blue", "yellow", "lime",
    "pink", "gray", "silver", "cyan", "purple", "blue", "brown",
    "green", "red", "black",
}


class WoolEditorError(Exception):
    pass

class WoolNotFound(WoolEditorError):
    pass

class InvalidWoolPayload(WoolEditorError):
    pass


def _gen_id() -> str:
    return uuid.uuid4().hex[:8]


def _normalize_color(raw: str) -> str:
    return str(raw).strip().lower().replace(" ", "_")


# ── migration ─────────────────────────────────────────────────────────────────

def _is_old_format(wools: list) -> bool:
    """Old format: flat list with 'team' key. New format: grouped with 'monuments' list."""
    return bool(wools) and "team" in wools[0] and "monuments" not in wools[0]


def _migrate_to_grouped(wools: list) -> list:
    """Convert [{team, color, location, monument, wool_room_region}]
    → [{id, color, location, wool_room_region, monuments: [{id, team, location, monument_region}]}].
    """
    by_color: dict[str, dict] = {}
    for w in wools:
        color = w.get("color", "")
        if color not in by_color:
            by_color[color] = {
                "id":               _gen_id(),
                "color":            color,
                "location":         w.get("location"),
                "wool_room_region": w.get("wool_room_region"),
                "monuments":        [],
            }
        mon_raw = w.get("monument")
        if mon_raw and isinstance(mon_raw, dict):
            by_color[color]["monuments"].append({
                "id":              _gen_id(),
                "team":            w.get("team", ""),
                "location":        {k: mon_raw[k] for k in ("x", "y", "z") if k in mon_raw},
                "monument_region": mon_raw.get("region_id"),
            })
    return list(by_color.values())


def _infer_wool_teams(data: dict) -> None:
    """For wools without an owning team, infer it as the one team absent from monuments.
    Only sets the field when the inference is unambiguous (exactly one team missing)."""
    team_ids = {t.get("id") for t in data.get("teams", []) if t.get("id")}
    if not team_ids:
        return
    for wool in data.get("wools", []):
        if wool.get("team") is not None:
            continue
        monument_teams = {m.get("team") for m in wool.get("monuments", [])}
        missing = team_ids - monument_teams
        if len(missing) == 1:
            wool["team"] = missing.pop()


def _ensure_grouped(data: dict) -> None:
    """Migrate wools in-place from the old flat format to the grouped format if needed."""
    wools = data.get("wools", [])
    if wools and _is_old_format(wools):
        data["wools"] = _migrate_to_grouped(wools)
    _infer_wool_teams(data)


# ── helpers ───────────────────────────────────────────────────────────────────

def _find_wool(data: dict, wool_id: str) -> dict:
    wool = next((w for w in data.get("wools", []) if w.get("id") == wool_id), None)
    if wool is None:
        raise WoolNotFound(f"wool {wool_id!r} not found")
    return wool


def _find_monument(wool: dict, mon_id: str) -> dict:
    mon = next((m for m in wool.get("monuments", []) if m.get("id") == mon_id), None)
    if mon is None:
        raise WoolNotFound(f"monument {mon_id!r} not found in wool {wool.get('id')!r}")
    return mon


# ── wool CRUD ─────────────────────────────────────────────────────────────────

def add_wool(data: dict, payload: dict) -> dict:
    _ensure_grouped(data)
    color = _normalize_color(payload.get("color") or "white")
    if color not in VALID_WOOL_COLORS:
        raise InvalidWoolPayload(f"invalid wool color {color!r}")
    if any(w.get("color") == color for w in data.get("wools", [])):
        raise InvalidWoolPayload(f"wool color {color!r} already exists")
    wool: dict = {
        "id":               _gen_id(),
        "color":            color,
        "team":             None,
        "location":         None,
        "wool_room_region": None,
        "monuments":        [],
    }
    data.setdefault("wools", []).append(wool)
    return {"wool": wool}


def update_wool(data: dict, wool_id: str, payload: dict) -> dict:
    _ensure_grouped(data)
    wool = _find_wool(data, wool_id)
    if "color" in payload:
        color = _normalize_color(payload["color"])
        if color not in VALID_WOOL_COLORS:
            raise InvalidWoolPayload(f"invalid wool color {color!r}")
        wool["color"] = color
    if "team" in payload:
        wool["team"] = (payload["team"] or "").strip() or None
    if "location" in payload:
        wool["location"] = payload["location"] or None
    if "wool_room_region" in payload:
        wool["wool_room_region"] = (payload["wool_room_region"] or "").strip() or None
    return {"wool": wool}


def delete_wool(data: dict, wool_id: str) -> dict:
    _ensure_grouped(data)
    wools = data.get("wools", [])
    if not any(w.get("id") == wool_id for w in wools):
        raise WoolNotFound(f"wool {wool_id!r} not found")
    data["wools"] = [w for w in wools if w.get("id") != wool_id]
    return {}


# ── monument CRUD ─────────────────────────────────────────────────────────────

def add_monument(data: dict, wool_id: str, payload: dict) -> dict:
    _ensure_grouped(data)
    wool = _find_wool(data, wool_id)
    team = str(payload.get("team") or "")
    if team and any(m.get("team") == team for m in wool.get("monuments", [])):
        raise InvalidWoolPayload(f"monument for team {team!r} already exists on this wool")
    mon: dict = {
        "id":              _gen_id(),
        "team":            team,
        "location":        payload.get("location") or None,
        "monument_region": (payload.get("monument_region") or "").strip() or None,
    }
    wool.setdefault("monuments", []).append(mon)
    return {"monument": mon}


def update_monument(data: dict, wool_id: str, mon_id: str, payload: dict) -> dict:
    _ensure_grouped(data)
    wool = _find_wool(data, wool_id)
    mon  = _find_monument(wool, mon_id)
    if "team" in payload:
        mon["team"] = str(payload["team"])
    if "location" in payload:
        mon["location"] = payload["location"] or None
    if "monument_region" in payload:
        mon["monument_region"] = (payload["monument_region"] or "").strip() or None
    return {"monument": mon}


def delete_monument(data: dict, wool_id: str, mon_id: str) -> dict:
    _ensure_grouped(data)
    wool = _find_wool(data, wool_id)
    mons = wool.get("monuments", [])
    if not any(m.get("id") == mon_id for m in mons):
        raise WoolNotFound(f"monument {mon_id!r} not found in wool {wool_id!r}")
    wool["monuments"] = [m for m in mons if m.get("id") != mon_id]
    return {}
