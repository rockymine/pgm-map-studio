"""View models (B4) — the transport shapes editor activities consume.

Typed to match what the studio encoders actually emit (code-first), not an
idealised shape. `RegionTreeNode` mirrors `region_encoder._encode_node`;
`RegionTreeResponse` mirrors the `GET /regions/tree` payload.

Coordinates use the canonical flat extent-bound bbox (`{min_x,min_z,max_x,max_z}`)
and `{cx,cz}` center (geometry.md §1 / data-model §2).
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class Bounds(BaseModel):
    """Extent-bound 2D bounding box (max = +1 over the highest block index)."""
    min_x: float
    min_z: float
    max_x: float
    max_z: float


class Polygon2d(BaseModel):
    """A 2D footprint: an exterior ring plus optional holes; points are [x, z]."""
    exterior: list[list[float]]
    holes: list[list[list[float]]] = []


class RegionTreeNode(BaseModel):
    """One node of the editor region tree (mirrors `region_encoder._encode_node`).

    `id` is `""` for synthetic regions; `bounds`/`source` are always present but
    nullable; `polygon_2d` is present only for resolvable polygon types.
    """
    id: str
    type: str
    label: str
    bounds: Optional[Bounds]
    coords: Optional[dict[str, Any]]   # None for composites with no own coords
    is_negative: bool
    synthetic_id: bool
    children: list["RegionTreeNode"]
    source: Optional["RegionTreeNode"]
    polygon_2d: Optional[Polygon2d] = None


class RegionGroup(BaseModel):
    """Root regions grouped by derived category (`GET /regions/tree` group)."""
    name: str
    label: str
    regions: list[RegionTreeNode]


class RegionTreeResponse(BaseModel):
    """The `GET /api/map/:name/regions/tree` payload."""
    groups: list[RegionGroup]
    bounding_box: Optional[Bounds] = None


# ── authoring split (B4a) — mirrors `region_encoder.encode_region_authoring` ──────

class WiringEntry(BaseModel):
    """One apply-rule event wired onto a region (e.g. `enter → only-blue`)."""
    event: str            # enter / block / block_break / kit / …
    value: str            # filter id, region id, or literal
    rule_id: Optional[str] = None


class AuthoringNode(BaseModel):
    """A flat authoring building block — a primitive or a composed structure."""
    id: str
    type: str
    label: str
    category: str
    bounds: Optional[Bounds]
    coords: Optional[dict[str, Any]]
    member_ids: list[str] = []          # composed: the region ids it groups
    wiring: list[WiringEntry] = []       # apply-rule events on this region
    polygon_2d: Optional[Polygon2d] = None


class RegionAuthoringResponse(BaseModel):
    """The `GET /api/map/:name/regions/authoring` payload: the primitives/composed split."""
    primitives: list[AuthoringNode]
    composed: list[AuthoringNode]
    bounding_box: Optional[Bounds] = None


# ── buildability (C14) — mirrors `services.buildability.compute_buildability` ─────

class BuildabilityResponse(BaseModel):
    """The `GET /api/map/:name/buildability` payload: a per-column verdict grid.

    `rows` holds `height` strings of `width` chars; each char is a verdict code
    indexing `classes` (`"0"`=buildable … `"3"`=restricted). Row 0 is `min_z`,
    char 0 is `min_x`. `colors` is the canonical legend (allow/deny *story*).
    `has_y0` is false when the Y=0 layer is missing (deny-void can't be resolved).
    """
    bbox: Bounds
    width: int
    height: int
    classes: list[str]
    colors: dict[str, str]
    counts: dict[str, int]
    rows: list[str]
    has_y0: bool


# ── wool sources & availability (C12) — mirrors `services.wool_sources` ──────────

class WoolSource(BaseModel):
    """One wool occurrence: a `block`, an item in a `chest`, or a `spawner`."""
    type: str
    color: str
    x: int
    y: int
    z: int
    count: int


class WoolColorSummary(BaseModel):
    """Wool of one colour found in a scan (region query). `repeatable` = a spawner
    or a renewable block; otherwise `one_time` (bare block / chest)."""
    color: str
    total: int
    source_types: list[str]
    repeatable: bool
    one_time: bool
    sources: list[WoolSource]


class WoolSourcesResponse(BaseModel):
    """`POST /api/map/:name/wool-sources` — what wool is in the drawn region.
    `have_layers` is false when the world layers are absent (xml-only map)."""
    colors: list[WoolColorSummary]
    have_layers: bool


class WoolAvailabilityEntry(BaseModel):
    """A declared wool's obtainability. `severity`: `error` (no source) /
    `info` (one-time only) / `ok`."""
    wool_id: str
    color: str
    obtainable: bool
    repeatable: bool
    one_time: bool
    severity: str
    message: str
    source_types: list[str]


class WoolAvailabilityResponse(BaseModel):
    """`GET /api/map/:name/wool-availability` — the per-wool validation."""
    wools: list[WoolAvailabilityEntry]
    have_layers: bool


class WoolSuggestion(BaseModel):
    """A wool colour found in the world but not yet declared as an objective."""
    color: str
    total: int
    source_types: list[str]


class WoolSuggestionsResponse(BaseModel):
    """`GET /api/map/:name/wool-suggestions` — colours to propose adding."""
    suggestions: list[WoolSuggestion]
    have_layers: bool


RegionTreeNode.model_rebuild()
