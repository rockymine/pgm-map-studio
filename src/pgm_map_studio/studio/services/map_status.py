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
    """Return basic display data from xml_data.json + symmetry.json, or {} if not present."""
    xml_path = out_dir / "xml_data.json"
    if not xml_path.exists():
        return {}
    try:
        d = json.loads(xml_path.read_text(encoding="utf-8"))
        wools = d.get("wools", [])
        info = {
            "name":      d.get("name", ""),
            "version":   d.get("version", ""),
            "gamemode":  d.get("gamemode", "ctw"),
            "objective": d.get("objective", ""),
            "teams":     len(d.get("teams", [])),
            "wools":     len({w.get("color") for w in wools}),  # unique wool colours
            "authors":   [{"uuid": a["uuid"], "role": a.get("role", "")}
                          for a in d.get("authors", []) if a.get("uuid")],
        }
    except Exception:
        return {}

    sym_path = out_dir / "symmetry.json"
    if sym_path.exists():
        try:
            sym = json.loads(sym_path.read_text(encoding="utf-8"))
            detected = [m["type"] for m in sym.get("modes", [])
                        if m.get("detected") and m.get("confidence", 0) >= 0.9]
            if detected:
                info["symmetry"] = detected[0]
        except Exception:
            pass

    return info
