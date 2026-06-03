"""Serializer: SymmetryResult → symmetry.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .datatypes import SymmetryResult


def to_dict(result: SymmetryResult) -> dict[str, Any]:
    """Serialize SymmetryResult to a JSON-serializable dict."""
    return {
        'symmetry_status': result.symmetry_status,
        'global_symmetry': [
            {
                'type': e.type,
                'detected': e.detected,
                'confidence': e.confidence,
                'description': e.description,
            }
            for e in result.global_symmetry
        ],
        'center': result.center,
        'primary': result.primary,
    }


def to_json(result: SymmetryResult, indent: int = 2) -> str:
    """Serialize SymmetryResult to a JSON string."""
    return json.dumps(to_dict(result), indent=indent)


def save(result: SymmetryResult, output_path: str | Path) -> None:
    """Write SymmetryResult to a JSON file."""
    path = Path(output_path)
    path.write_text(to_json(result))
