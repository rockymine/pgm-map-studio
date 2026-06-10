"""Region class hierarchy for PGM XML regions.

All regions carry a pre-computed `bounds_2d` field populated at parse time.
Composite regions (Union, Negative, Complement, Intersect) store children as
ID strings into the flat registry rather than inline Region objects.
Transform regions (Mirror, Translate) store a source_id string reference.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("pgm_map_studio")


# ---------------------------------------------------------------------------
# Coordinate parsing
# ---------------------------------------------------------------------------

def parse_coord(value: str) -> Optional[float]:
    """Parse a PGM coordinate value.

    - Template variable ``${variable_name}`` → ``None``
    - Infinity ``"oo"`` / ``"-oo"`` → ``float('inf')`` / ``float('-inf')``
    - Normal float or int literal → float
    - Malformed literal (e.g. a source typo like ``"5.185.5"``) → ``0.0`` with a
      warning, so one bad value flags-and-continues instead of failing the whole map.
    """
    value = value.strip()
    if '${' in value:
        return None
    if '$' in value:
        return None
    lower = value.lower()
    if lower == 'oo':
        return float('inf')
    if lower == '-oo':
        return float('-inf')
    try:
        return float(value)
    except ValueError:
        logger.warning("Malformed coordinate %r — treating as 0.0 (flag-and-continue)", value)
        return 0.0


def _b2d(min_x: float, min_z: float, max_x: float, max_z: float) -> dict:
    """Create a normalized bounds_2d dict (min always ≤ max)."""
    return {
        'min': {'x': min(min_x, max_x), 'z': min(min_z, max_z)},
        'max': {'x': max(min_x, max_x), 'z': max(min_z, max_z)},
    }


def reflect_point_2d(px: float, pz: float, nx: float, nz: float,
                     ox: float, oz: float) -> tuple[float, float]:
    """Reflect a point across the plane through (ox,oz) with horizontal normal (nx,nz).

    This is PGM's ``<mirror>`` semantics (``result = p − n·(2·(p−o)·n / |n|²)``), so
    it handles a **diagonal** normal (e.g. ``-1,0,-1``) correctly — that mirror swaps
    the x/z axes, unlike an axis-aligned flip. An all-zero horizontal normal (a purely
    vertical mirror) leaves the footprint unchanged.
    """
    n2 = nx * nx + nz * nz
    if n2 == 0:
        return px, pz
    d = 2.0 * ((px - ox) * nx + (pz - oz) * nz) / n2
    return px - nx * d, pz - nz * d


def reflect_bounds_2d(bounds: dict, nx: float, nz: float,
                      ox: float, oz: float) -> dict:
    """Reflect a ``bounds_2d`` AABB across a mirror plane, returning a new AABB.

    All four corners are reflected (a diagonal mirror rotates the box), then
    re-bounded — exact for axis-aligned and 45° normals, a tight superset otherwise.
    """
    mn, mx = bounds['min'], bounds['max']
    corners = [
        reflect_point_2d(x, z, nx, nz, ox, oz)
        for x in (mn['x'], mx['x']) for z in (mn['z'], mx['z'])
    ]
    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    return _b2d(min(xs), min(zs), max(xs), max(zs))


# ---------------------------------------------------------------------------
# Base region
# ---------------------------------------------------------------------------

@dataclass
class Region:
    id: str = ""
    region_type: str = "unknown"
    bounds_2d: Optional[dict] = field(default=None)


# ---------------------------------------------------------------------------
# Primitive regions
# ---------------------------------------------------------------------------

@dataclass
class Rectangle(Region):
    min_x: Optional[float] = None
    min_z: Optional[float] = None
    max_x: Optional[float] = None
    max_z: Optional[float] = None
    region_type: str = "rectangle"

    def __post_init__(self):
        if None not in (self.min_x, self.min_z, self.max_x, self.max_z):
            self.bounds_2d = _b2d(self.min_x, self.min_z, self.max_x, self.max_z)


@dataclass
class Cuboid(Region):
    min_x: Optional[float] = None
    min_y: Optional[float] = None
    min_z: Optional[float] = None
    max_x: Optional[float] = None
    max_y: Optional[float] = None
    max_z: Optional[float] = None
    region_type: str = "cuboid"

    def __post_init__(self):
        if None not in (self.min_x, self.min_z, self.max_x, self.max_z):
            self.bounds_2d = _b2d(self.min_x, self.min_z, self.max_x, self.max_z)


@dataclass
class Cylinder(Region):
    base_x: float = 0.0
    base_y: float = 0.0
    base_z: float = 0.0
    radius: float = 0.0
    height: Optional[float] = None
    region_type: str = "cylinder"

    def __post_init__(self):
        r = self.radius
        self.bounds_2d = _b2d(self.base_x - r, self.base_z - r,
                              self.base_x + r, self.base_z + r)


@dataclass
class Circle(Region):
    center_x: float = 0.0
    center_z: float = 0.0
    radius: float = 0.0
    region_type: str = "circle"

    def __post_init__(self):
        r = self.radius
        self.bounds_2d = _b2d(self.center_x - r, self.center_z - r,
                              self.center_x + r, self.center_z + r)


@dataclass
class Sphere(Region):
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    radius: float = 0.0
    region_type: str = "sphere"

    def __post_init__(self):
        r = self.radius
        self.bounds_2d = _b2d(self.origin_x - r, self.origin_z - r,
                              self.origin_x + r, self.origin_z + r)


@dataclass
class Block(Region):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    region_type: str = "block"

    def __post_init__(self):
        # Block (x, z) occupies [x, x+1] × [z, z+1]
        self.bounds_2d = _b2d(self.x, self.z, self.x + 1, self.z + 1)


@dataclass
class Point(Region):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    region_type: str = "point"

    def __post_init__(self):
        # Continuous coordinate — shown as 1×1 square centred on it
        self.bounds_2d = _b2d(self.x - 0.5, self.z - 0.5,
                              self.x + 0.5, self.z + 0.5)


# ---------------------------------------------------------------------------
# Composite regions — children are ID strings into the flat registry
# ---------------------------------------------------------------------------

@dataclass
class Union(Region):
    children: list[str] = field(default_factory=list)
    region_type: str = "union"


@dataclass
class Negative(Region):
    children: list[str] = field(default_factory=list)
    region_type: str = "negative"


@dataclass
class Complement(Region):
    children: list[str] = field(default_factory=list)
    region_type: str = "complement"


@dataclass
class Intersect(Region):
    children: list[str] = field(default_factory=list)
    region_type: str = "intersect"


# ---------------------------------------------------------------------------
# Transform regions — source referenced by ID in the flat registry
# ---------------------------------------------------------------------------

@dataclass
class Mirror(Region):
    source_id: str = ""
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    normal_x: float = 0.0
    normal_y: float = 0.0
    normal_z: float = 0.0
    region_type: str = "mirror"


@dataclass
class Translate(Region):
    source_id: str = ""
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_z: float = 0.0
    region_type: str = "translate"


# ---------------------------------------------------------------------------
# Half-space region
# ---------------------------------------------------------------------------

@dataclass
class Half(Region):
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    normal_x: float = 0.0
    normal_y: float = 0.0
    normal_z: float = 0.0
    region_type: str = "half"


# ---------------------------------------------------------------------------
# Reference and special regions
# ---------------------------------------------------------------------------

@dataclass
class Reference(Region):
    ref_id: str = ""
    region_type: str = "reference"


@dataclass
class Everywhere(Region):
    region_type: str = "everywhere"


@dataclass
class Above(Region):
    y: float = 0.0
    region_type: str = "above"
