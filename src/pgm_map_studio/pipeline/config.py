"""Per-map pipeline configuration.

Stored at {output_dir}/{map_slug}/map_config.json and user-editable between
pipeline runs.  The most common use: add island IDs to exclude_islands so the
symmetry step ignores non-playable observer platforms.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pgm_map_studio.layout.config import LayerChoice


@dataclass
class MapConfig:
    """Per-map overrides for pipeline behaviour."""
    exclude_islands: list[int] = field(default_factory=list)
    exclude_blocks: list[int] = field(default_factory=list)
    scan_layer: LayerChoice = 'surface'
    scan_layer_confirmed: bool = False

    def to_dict(self) -> dict:
        return {
            'exclude_islands': self.exclude_islands,
            'exclude_blocks': self.exclude_blocks,
            'scan_layer': self.scan_layer,
            'scan_layer_confirmed': self.scan_layer_confirmed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'MapConfig':
        return cls(
            exclude_islands=d.get('exclude_islands', []),
            exclude_blocks=d.get('exclude_blocks', []),
            scan_layer=d.get('scan_layer', 'surface'),
            scan_layer_confirmed=d.get('scan_layer_confirmed', False),
        )


def load_map_config(output_dir: Path) -> MapConfig:
    """Load map_config.json, returning defaults if absent."""
    path = output_dir / 'map_config.json'
    if path.exists():
        return MapConfig.from_dict(json.loads(path.read_text()))
    return MapConfig()


def save_map_config(config: MapConfig, output_dir: Path) -> None:
    """Write map_config.json, creating it if absent."""
    path = output_dir / 'map_config.json'
    path.write_text(json.dumps(config.to_dict(), indent=2))
