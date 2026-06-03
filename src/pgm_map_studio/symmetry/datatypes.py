"""Data classes for symmetry detection results."""

from dataclasses import dataclass
from typing import Any, Optional

_SYMMETRY_ORDER: dict[str, int] = {
    'rot_90': 4,
    'rot_180': 2,
    'mirror_x': 1,
    'mirror_z': 1,
}


@dataclass
class GlobalSymmetryEntry:
    type: str
    detected: bool
    confidence: float



@dataclass
class SymmetryResult:
    """Result of geometric symmetry analysis.

    ``status`` is written as ``"unconfirmed"`` by the pipeline; the
    viewer allows the user to confirm or reject the detection and updates it
    to ``"confirmed"`` or ``"none"``.
    """
    status: str
    modes: list[GlobalSymmetryEntry]
    center: dict[str, float]   # {center_x, center_z}

    @property
    def primary(self) -> Optional[dict[str, Any]]:
        """Highest-confidence detected symmetry type, or None."""
        detected = [e for e in self.modes if e.detected]
        if not detected:
            return None
        best = max(
            detected,
            key=lambda e: (e.confidence, _SYMMETRY_ORDER.get(e.type, 0)),
        )
        return {'type': best.type, 'confidence': best.confidence}
