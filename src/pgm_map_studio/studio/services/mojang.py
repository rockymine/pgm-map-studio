from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def lookup_player(name_or_uuid: str) -> dict:
    """Return {"uuid": str, "name": str}.  Raises ValueError on failure."""
    is_uuid = bool(_UUID_RE.match(name_or_uuid))
    if is_uuid:
        url = f"https://sessionserver.mojang.com/session/minecraft/profile/{name_or_uuid.replace('-', '')}"
    else:
        url = f"https://api.mojang.com/users/profiles/minecraft/{name_or_uuid}"

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Player not found: {name_or_uuid} ({exc.code})") from exc
    except Exception as exc:
        raise ValueError(f"Mojang lookup failed: {exc}") from exc

    raw_uuid = data.get("id", "")
    formatted = (
        f"{raw_uuid[0:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}-{raw_uuid[16:20]}-{raw_uuid[20:]}"
        if raw_uuid and "-" not in raw_uuid else raw_uuid
    )
    return {"uuid": formatted, "name": data.get("name", name_or_uuid)}
