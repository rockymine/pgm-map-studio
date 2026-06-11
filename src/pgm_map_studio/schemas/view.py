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


RegionTreeNode.model_rebuild()
