"""Data classes for symmetry detection results."""

from dataclasses import dataclass
from typing import Any, Optional

# Strength rank used to break ties when several symmetry types are detected at
# equal confidence (higher = stronger / more constraining). The two diagonal
# reflections (``mirror_d1`` / ``mirror_d2``) rank alongside the axis-aligned
# mirrors — all four are order-2 reflections; only the axis angle differs.
_SYMMETRY_ORDER: dict[str, int] = {
    'rot_90': 4,
    'rot_180': 2,
    'mirror_x': 1,
    'mirror_z': 1,
    'mirror_d1': 1,
    'mirror_d2': 1,
}

# The four center-cell typologies (X-width × Z-width). A map center lands either
# on a block boundary (even span → 2-wide on that axis) or through the middle of
# a block column (odd span → 1-wide). With the +1 extent convention the center
# coordinate's fractional part encodes this directly: ``.0`` → 2, ``.5`` → 1.
CENTER_CELLS = ('1x1', '1x2', '2x1', '2x2')

# Center-cell typologies compatible with rot_90 / diagonal-mirror symmetry: the
# center cell must be square (equal X/Z parity), so only 1x1 and 2x2 qualify.
SQUARE_CENTER_CELLS = ('1x1', '2x2')


def _axis_width(coord: float) -> int:
    """Return the center-cell width (1 or 2 blocks) along one axis.

    ``coord`` is an extent-bound center (``(min + max) / 2`` of integer block
    extents), so it is exactly integer or half-integer. A half-integer center
    runs through the middle of a single block column (1-wide); an integer center
    sits on the boundary between two columns (2-wide).
    """
    frac = coord % 1.0
    return 1 if abs(frac - 0.5) < 1e-6 else 2


def classify_center_cell(cx: float, cz: float) -> str:
    """Classify the center cell typology as ``"{x_width}x{z_width}"``.

    Returns one of :data:`CENTER_CELLS` (``1x1`` / ``1x2`` / ``2x1`` / ``2x2``).
    """
    return f'{_axis_width(cx)}x{_axis_width(cz)}'


def is_square_center_cell(cell: str) -> bool:
    """True iff ``cell`` is a square center cell (rot_90 / diagonal compatible)."""
    return cell in SQUARE_CENTER_CELLS


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
    def center_cell(self) -> str:
        """Derived center-cell typology (``1x1`` / ``1x2`` / ``2x1`` / ``2x2``).

        The center coordinate is the single source of truth; the cell typology
        is a derived label (see :func:`classify_center_cell`).
        """
        return classify_center_cell(
            self.center.get('center_x', 0.0),
            self.center.get('center_z', 0.0),
        )

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
