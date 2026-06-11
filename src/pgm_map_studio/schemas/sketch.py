"""Sketch models (B3) — the on-disk `sketch.json` shape (authoring sessions).

Unlike `persisted.py` (which mirrors the pipeline's snake_case `xml_data.json`),
`sketch.json` is written straight from the browser's JSON payloads
(`sketch_api` → `sketch_data`), so it carries **JS-origin naming**: camelCase
`shapeIds`, `cx`/`cz`, and the bezier `in`/`out` control keys.

The crucial detail is the cubic-Bézier model on polygon/lasso shapes (kept in
exact lock-step with `studio/static/sketch/geometry.js` and `sketch_export.py`):

- `controls` is a **dict keyed by the *stringified vertex index*** (`"0"`, `"1"`,
  …), not a list;
- each entry is `{ in?: [x, z], out?: [x, z] }` — `out` is the out-handle of
  vertex *i* (start of edge i→j), `in` the in-handle of vertex *j* (end);
- for edge i→j the cubic is `(p_i, controls[i].out, controls[j].in, p_j)`; a
  missing handle falls back to its endpoint, and an edge with neither handle is a
  straight segment.

`in` is a Python keyword, so `BezierControl.in_` is aliased to the wire key
`"in"` (the TS generator emits the alias).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import ConfigDict, Field

from pgm_map_studio.schemas.persisted import Author, _Model

# A 2D point `[x, z]` (sketch coords are plain numbers — no `"oo"`/`${}`).
Point = list[float]

MirrorMode = Literal["mirror_x", "mirror_z", "rot_180", "rot_90"]


class Bbox(_Model):
    """The sketch's world-space working bounds (flat min/max)."""
    min_x: float
    min_z: float
    max_x: float
    max_z: float


class Center(_Model):
    cx: float = 0.0
    cz: float = 0.0


class SketchSetup(_Model):
    bbox: Optional[Bbox] = None
    center: Optional[Center] = None
    mirror_mode: MirrorMode = "rot_180"


class BezierControl(_Model):
    # `in`/`out` tangent handles, each a `[x, z]` point. `in` is a Python keyword
    # → aliased; populate_by_name lets either the field name or the alias load it.
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    in_: Optional[Point] = Field(default=None, alias="in")
    out: Optional[Point] = None


class Shape(_Model):
    """A draw primitive — fields vary by `type` (rectangle/circle/polygon/lasso)."""
    id: str = ""
    type: str
    operation: str = "add"        # "add" | "subtract"
    override: bool = False
    # rectangle
    min_x: Optional[float] = None
    min_z: Optional[float] = None
    max_x: Optional[float] = None
    max_z: Optional[float] = None
    # circle
    center_x: Optional[float] = None
    center_z: Optional[float] = None
    radius: Optional[float] = None
    # polygon / lasso
    vertices: Optional[list[Point]] = None
    controls: Optional[dict[str, BezierControl]] = None   # keyed by str(vertex index)


class IslandMeta(_Model):
    """Persisted island record — geometry is recomputed from shapes on load;
    only the user-set metadata + its shapeId set survive (camelCase from JS)."""
    id: str = ""
    name: str = ""
    mirrors: bool = True
    shapeIds: list[str] = []


class SketchLayout(_Model):
    shapes: list[Shape] = []
    islands: list[IslandMeta] = []


class SketchProject(_Model):
    """The persisted `sketch.json` shape (one authoring session)."""
    id: str = ""
    gamemode: str = "ctw"
    name: str = ""
    version: str = "1.0"
    objective: str = ""
    authors: list[Author] = []
    setup: Optional[SketchSetup] = None
    layout: Optional[SketchLayout] = None
    export_slug: Optional[str] = None
