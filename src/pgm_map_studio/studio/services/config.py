from __future__ import annotations

import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "pgm-map-studio"
_CONFIG_PATH = _CONFIG_DIR / "config.json"
_DEFAULTS = {"maps_folder": "", "output_folder": ""}


def load_config() -> dict:
    if _CONFIG_PATH.exists():
        try:
            return {**_DEFAULTS, **json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return dict(_DEFAULTS)


def save_config(updates: dict) -> None:
    cfg = load_config()
    for key in _DEFAULTS:
        if key in updates:
            cfg[key] = str(updates[key]).strip()
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get_output_root() -> Path:
    folder = load_config().get("output_folder", "").strip()
    return Path(folder) if folder else Path.home() / ".local" / "share" / "pgm-map-studio" / "output"


def get_maps_folder() -> Path | None:
    folder = load_config().get("maps_folder", "").strip()
    return Path(folder) if folder else None
