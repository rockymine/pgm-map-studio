"""Typed boundary contract (pydantic) — the source of the generated TypeScript.

Framework-independent: composed by `studio` routes and read by the TS generator
(`tools/generate_ts_contract.py`). Domain types stay dataclasses in `pgm/`; these
schemas are the persisted + view shapes at the API boundary. See
`docs/contracts/frontend-stack.md` and `data-model.md`.
"""

from pgm_map_studio.schemas.view import (
    AuthoringNode,
    Bounds,
    BuildabilityResponse,
    Polygon2d,
    RegionAuthoringResponse,
    RegionGroup,
    RegionTreeNode,
    RegionTreeResponse,
    IsolatedPoint,
    NavPoint,
    TraversabilityResponse,
    WiringEntry,
    WoolAvailabilityEntry,
    WoolAvailabilityResponse,
    WoolColorSummary,
    WoolSource,
    WoolSourcesResponse,
    WoolSuggestion,
    WoolSuggestionsResponse,
)
from pgm_map_studio.schemas.persisted import (
    ApplyRule,
    Author,
    BlockDropRule,
    Bounds2d,
    DropItem,
    Filter,
    Kit,
    KitArmor,
    KitItem,
    MapProject,
    Monument,
    ObserverSpawn,
    Region,
    Renewable,
    Spawn,
    Spawner,
    Team,
    Wool,
    XYZ,
    XZ,
)
from pgm_map_studio.schemas.sketch import (
    BezierControl,
    Bbox,
    Center,
    IslandMeta,
    Shape,
    SketchLayout,
    SketchProject,
    SketchSetup,
)

# Models exported to the generated TypeScript contract (TS interfaces are hoisted,
# so order is cosmetic): view models, then the persisted map shape.
TS_CONTRACT_MODELS = [
    # view (B4)
    Bounds, Polygon2d, RegionTreeNode, RegionGroup, RegionTreeResponse,
    WiringEntry, AuthoringNode, RegionAuthoringResponse, BuildabilityResponse,
    WoolSource, WoolColorSummary, WoolSourcesResponse,
    WoolAvailabilityEntry, WoolAvailabilityResponse,
    WoolSuggestion, WoolSuggestionsResponse,
    NavPoint, IsolatedPoint, TraversabilityResponse,
    # persisted (B1)
    XZ, XYZ, Bounds2d, Team, Author, KitItem, KitArmor, Kit, Region, Spawn,
    Monument, Wool, DropItem, Spawner, Renewable, BlockDropRule, Filter,
    ApplyRule, ObserverSpawn, MapProject,
    # sketch (B3)
    Bbox, Center, SketchSetup, BezierControl, Shape, IslandMeta, SketchLayout,
    SketchProject,
]

__all__ = [m.__name__ for m in TS_CONTRACT_MODELS] + ["TS_CONTRACT_MODELS"]
