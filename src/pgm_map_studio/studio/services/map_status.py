from __future__ import annotations

import json
from pathlib import Path


PIPELINE_STEPS = [
    {"id": "layout",   "label": "Layout",   "file": "islands.json"},
    {"id": "symmetry", "label": "Symmetry", "file": "symmetry.json"},
    {"id": "xml",      "label": "XML",      "file": "xml_data.json"},
]


def check_pipeline_status(out_dir: Path) -> list[dict]:
    steps = []
    for step in PIPELINE_STEPS:
        path = out_dir / step["file"]
        done = path.exists()
        steps.append({
            "id":    step["id"],
            "label": step["label"],
            "file":  step["file"],
            "done":  done,
        })
    return steps


def is_editor_ready(out_dir: Path) -> bool:
    """True when xml_data.json exists (minimum for the editor to open)."""
    return (out_dir / "xml_data.json").exists()


def map_display_info(out_dir: Path) -> dict:
    """Return basic display data from xml_data.json, or {} if not present."""
    xml_path = out_dir / "xml_data.json"
    if not xml_path.exists():
        return {}
    try:
        d = json.loads(xml_path.read_text(encoding="utf-8"))
        return {
            "name":      d.get("name", ""),
            "version":   d.get("version", ""),
            "gamemode":  d.get("gamemode", "ctw"),
            "objective": d.get("objective", ""),
            "teams":     len(d.get("teams", [])),
            "wools":     len(d.get("wools", [])),
            "authors":   [a.get("name", a.get("uuid", "")) for a in d.get("authors", [])],
        }
    except Exception:
        return {}
