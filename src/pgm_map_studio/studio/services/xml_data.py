from __future__ import annotations

import json
from pathlib import Path

from flask import abort

from .config import get_output_root


def load_xml_data(name: str) -> tuple[dict, Path]:
    path = get_output_root() / name / "xml_data.json"
    if not path.exists():
        abort(404)
    return json.loads(path.read_text(encoding="utf-8")), path


def save_xml_data(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
