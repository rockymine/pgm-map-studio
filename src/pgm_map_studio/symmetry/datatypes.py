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


# ---------------------------------------------------------------------------
# Symmetry-mode order / team-coupling (B7 + B11)
# ---------------------------------------------------------------------------
#
# The vocabulary is open on the rotation side: a general n-fold rotation is
# spelled ``rot_<degrees>`` where ``degrees = 360 // n`` (rot_180 = 2-fold,
# rot_90 = 4-fold, rot_120 = 3-fold, rot_72 = 5-fold, rot_60 = 6-fold,
# rot_45 = 8-fold). The four reflections are 2-element symmetries. Detection
# currently covers only the lattice-exact subset (reflections + rot_180/rot_90);
# rot_n for other n is modeled and authorable but not auto-detected yet.

_REFLECTIONS = frozenset({'mirror_x', 'mirror_z', 'mirror_d1', 'mirror_d2'})

# Modes that swap the X and Z axes and so require a square center cell.
_SWAP_AXES = frozenset({'rot_90', 'mirror_d1', 'mirror_d2'})


def rotation_degrees(mode: str) -> Optional[int]:
    """Return the rotation step in degrees for a ``rot_<d>`` mode, else None."""
    if not mode.startswith('rot_'):
        return None
    try:
        return int(mode[4:])
    except ValueError:
        return None


def team_orbit(mode: str) -> int:
    """Team-orbit size of a symmetry mode (the team-count divisor).

    Reflections partition the map into 2 mirror halves → orbit 2. An n-fold
    rotation `rot_<d>` has orbit ``n = 360 // d`` (rot_180 → 2, rot_90 → 4,
    rot_120 → 3, …). Unknown modes → 1 (no constraint). Note this differs from
    :data:`_SYMMETRY_ORDER`, which is a *display strength rank* for tie-breaks.
    """
    if mode in _REFLECTIONS:
        return 2
    deg = rotation_degrees(mode)
    if deg and 360 % deg == 0:
        return 360 // deg
    return 1


def is_lattice_exact(mode: str) -> bool:
    """True iff the mode is an *exact* symmetry of the square block grid.

    By the crystallographic restriction, only 2- and 4-fold rotation (and
    reflections) map the square lattice onto itself. `rot_120`/`rot_72`/`rot_60`/
    `rot_45` (3-, 5-, 6-, 8-fold) are necessarily **approximate** — their
    counterparts bake to concrete geometry; there is no clean PGM mirror and no
    pixel-perfect guarantee.
    """
    if mode in _REFLECTIONS:
        return True
    return team_orbit(mode) in (2, 4) and rotation_degrees(mode) in (180, 90)


def requires_square_cell(mode: str) -> bool:
    """True iff the mode swaps X↔Z and so needs a square (1x1/2x2) center cell."""
    return mode in _SWAP_AXES


def team_count_compatible(mode: str, n_teams: int) -> bool:
    """Strict team-count rule: ``n_teams`` is a positive multiple of the orbit.

    rot_90 ⇒ multiple of 4 (and ≥4); reflections/rot_180 ⇒ multiple of 2; a
    general `rot_<d>` ⇒ multiple of `n`. This is the *regular symmetric CTW*
    definition (B11 Q2); deviations are surfaced as non-blocking warnings, never
    hard-blocked during editing.
    """
    orbit = team_orbit(mode)
    return n_teams >= orbit and n_teams % orbit == 0


def wool_count_compatible(n_wools: int, n_teams: int) -> bool:
    """Strict wool rule: each team owns ``k`` colors → ``n_wools = k · n_teams``."""
    return n_teams > 0 and n_wools >= n_teams and n_wools % n_teams == 0


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
    center: dict[str, float]   # {cx, cz}

    @property
    def center_cell(self) -> str:
        """Derived center-cell typology (``1x1`` / ``1x2`` / ``2x1`` / ``2x2``).

        The center coordinate is the single source of truth; the cell typology
        is a derived label (see :func:`classify_center_cell`).
        """
        return classify_center_cell(
            self.center.get('cx', 0.0),
            self.center.get('cz', 0.0),
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
