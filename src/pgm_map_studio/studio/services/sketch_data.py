from __future__ import annotations

import json
import uuid
from pathlib import Path

SKETCHES_DIR = Path.home() / ".config" / "pgm-map-studio" / "sketches"

_OVERVIEW_FIELDS = {"name", "version", "objective", "authors"}

_SETUP_FIELDS = {"bbox", "center", "mirror_mode"}

_DEFAULTS: dict = {
    "gamemode":  "ctw",
    "name":      "",
    "version":   "1.0",
    "objective": "",
    "authors":   [],
    "setup":     None,
    "layout":    None,
}


def _path(sketch_id: str) -> Path:
    root = SKETCHES_DIR.resolve()
    resolved = (root / sketch_id).resolve()
    if not str(resolved).startswith(str(root) + "/"):
        raise KeyError(sketch_id)
    return resolved / "sketch.json"


def create_sketch() -> str:
    """Create a new blank sketch session. Returns the session ID."""
    sid = str(uuid.uuid4())
    p = _path(sid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"id": sid, **_DEFAULTS}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return sid


def load_sketch(sketch_id: str) -> dict:
    """Load a sketch session. Raises KeyError if not found."""
    p = _path(sketch_id)
    if not p.exists():
        raise KeyError(sketch_id)
    return json.loads(p.read_text(encoding="utf-8"))


def save_setup(sketch_id: str, fields: dict) -> None:
    """Persist setup fields (bbox, center, mirror_mode). Raises KeyError if not found."""
    data = load_sketch(sketch_id)
    setup = data.get("setup") or {}
    for key in _SETUP_FIELDS:
        if key in fields:
            setup[key] = fields[key]
    data["setup"] = setup
    _path(sketch_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def save_layout(sketch_id: str, shapes: list, islands: list) -> None:
    """Persist layout shapes and island metadata. Raises KeyError if not found."""
    data = load_sketch(sketch_id)
    data["layout"] = {"shapes": shapes, "islands": islands}
    _path(sketch_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def save_overview(sketch_id: str, fields: dict) -> None:
    """Persist overview fields (name, version, objective, authors). Raises KeyError if not found."""
    data = load_sketch(sketch_id)
    for key in _OVERVIEW_FIELDS:
        if key in fields:
            data[key] = fields[key]
    _path(sketch_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def list_sketches() -> list[dict]:
    """Return summary rows for all sketch sessions, newest-modified first."""
    if not SKETCHES_DIR.exists():
        return []
    rows = []
    for p in SKETCHES_DIR.glob("*/sketch.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            rows.append({
                "id":          data.get("id", p.parent.name),
                "name":        data.get("name", ""),
                "export_slug": data.get("export_slug"),
                "modified":    p.stat().st_mtime,
            })
        except Exception:
            pass
    rows.sort(key=lambda r: r["modified"], reverse=True)
    return rows


def save_export_slug(sketch_id: str, slug: str) -> None:
    """Record the output slug produced by a sketch export. Raises KeyError if not found."""
    data = load_sketch(sketch_id)
    data["export_slug"] = slug
    _path(sketch_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
