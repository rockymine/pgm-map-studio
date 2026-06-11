"""Typed boundary contract (pydantic) — the source of the generated TypeScript.

Framework-independent: composed by `studio` routes and read by the TS generator
(`tools/generate_ts_contract.py`). Domain types stay dataclasses in `pgm/`; these
schemas are the persisted + view shapes at the API boundary. See
`docs/contracts/frontend-stack.md` and `data-model.md`.
"""

from pgm_map_studio.schemas.view import (
    Bounds,
    Polygon2d,
    RegionTreeNode,
    RegionGroup,
    RegionTreeResponse,
)

# Models exported to the generated TypeScript contract, in emit order.
TS_CONTRACT_MODELS = [
    Bounds,
    Polygon2d,
    RegionTreeNode,
    RegionGroup,
    RegionTreeResponse,
]

__all__ = [
    "Bounds", "Polygon2d", "RegionTreeNode", "RegionGroup", "RegionTreeResponse",
    "TS_CONTRACT_MODELS",
]
