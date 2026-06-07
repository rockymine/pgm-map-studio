from __future__ import annotations

from pgm_map_studio.studio.services.region_editor import _regions_dict


class SpawnEditorError(Exception):
    pass

class SpawnNotFound(SpawnEditorError):
    pass

class SpawnConflict(SpawnEditorError):
    pass

class InvalidSpawnPayload(SpawnEditorError):
    pass


def _spawn_region_id(spawn: dict) -> str:
    """Region ID for a spawn — handles both string (new) and dict (legacy) forms."""
    region = spawn.get("region")
    if isinstance(region, str):
        return region
    if isinstance(region, dict):
        return region.get("id", "")
    return ""


def add_spawn_link(data: dict, payload: dict) -> dict:
    region_id = (payload.get("region_id") or "").strip()
    if not region_id:
        raise InvalidSpawnPayload("region_id is required")

    regions = _regions_dict(data)
    if region_id not in regions:
        raise SpawnNotFound(f"region {region_id!r} not found")

    spawns: list = data.setdefault("spawns", [])
    if any(_spawn_region_id(s) == region_id for s in spawns):
        raise SpawnConflict(f"spawn for region {region_id!r} already exists")

    spawns.append({
        "team":   str(payload.get("team", "")),
        "kit":    str(payload.get("kit", "")),
        "yaw":    float(payload.get("yaw", 0.0)),
        "region": region_id,
    })
    return {}


def update_spawn_link(data: dict, region_id: str, payload: dict) -> dict:
    spawns: list = data.get("spawns", [])
    spawn = next((s for s in spawns if _spawn_region_id(s) == region_id), None)
    if spawn is None:
        raise SpawnNotFound(f"no spawn for region {region_id!r}")

    if "team" in payload:
        spawn["team"] = str(payload["team"])
    if "yaw" in payload:
        spawn["yaw"] = float(payload["yaw"])
    if "kit" in payload:
        spawn["kit"] = str(payload["kit"])
    return {}


def delete_spawn_link(data: dict, region_id: str) -> dict:
    spawns: list = data.get("spawns", [])
    if not any(_spawn_region_id(s) == region_id for s in spawns):
        raise SpawnNotFound(f"no spawn for region {region_id!r}")

    data["spawns"] = [s for s in spawns if _spawn_region_id(s) != region_id]
    return {}


def set_observer_spawn(data: dict, payload: dict) -> dict:
    """Set or replace the observer spawn (the <default> in <spawns>)."""
    region_id = (payload.get("region_id") or "").strip()
    if not region_id:
        raise InvalidSpawnPayload("region_id is required")
    regions = _regions_dict(data)
    if region_id not in regions:
        raise SpawnNotFound(f"region {region_id!r} not found")

    data["observer_spawn"] = {
        "team": "",
        "kit":  str(payload.get("kit", "")),
        "yaw":  float(payload.get("yaw", 0.0)),
        "region": region_id,
    }
    return {}


def delete_observer_spawn(data: dict) -> dict:
    """Remove the observer spawn."""
    if not data.get("observer_spawn"):
        raise SpawnNotFound("no observer spawn defined")
    data["observer_spawn"] = None
    return {}
