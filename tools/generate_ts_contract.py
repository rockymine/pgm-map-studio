"""Generate the TypeScript contract (frontend/src/contract.ts) from the pydantic
schemas in `pgm_map_studio.schemas`.

The pydantic models are the single source of truth; this emits matching TS
interfaces so the frontend cannot drift from the API. A test
(`tests/test_schemas.py`) asserts the checked-in file equals `render()`, so a
schema change without regeneration fails CI.

Run: `python tools/generate_ts_contract.py`
"""
from __future__ import annotations

import typing
from pathlib import Path

from pydantic import BaseModel

from pgm_map_studio.schemas import TS_CONTRACT_MODELS

_OUT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "contract.ts"

_PRIMITIVES = {str: "string", int: "number", float: "number", bool: "boolean"}


def _ts_type(ann) -> str:
    """Map a (resolved) Python annotation to a TypeScript type."""
    if ann in _PRIMITIVES:
        return _PRIMITIVES[ann]
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return ann.__name__

    origin = typing.get_origin(ann)
    args = typing.get_args(ann)

    if origin is typing.Literal:
        return " | ".join(f'"{a}"' if isinstance(a, str) else str(a) for a in args)
    if origin in (list, set, tuple):
        return f"{_ts_type(args[0])}[]"
    if origin is dict:
        return f"Record<string, {_ts_type(args[1])}>" if len(args) == 2 else "Record<string, unknown>"
    if origin is typing.Union or origin is getattr(__import__("types"), "UnionType", None):
        non_none = [a for a in args if a is not type(None)]
        ts = " | ".join(_ts_type(a) for a in non_none) or "unknown"
        if type(None) in args:
            ts += " | null"
        return ts
    return "unknown"


def _emit_interface(model: type[BaseModel]) -> str:
    lines = [f"export interface {model.__name__} {{"]
    for name, field in model.model_fields.items():
        wire = field.alias or name          # emit the JSON key (e.g. "in", not "in_")
        optional = "" if field.is_required() else "?"
        lines.append(f"  {wire}{optional}: {_ts_type(field.annotation)};")
    lines.append("}")
    return "\n".join(lines)


def render() -> str:
    header = (
        "// GENERATED from pgm_map_studio.schemas — DO NOT EDIT.\n"
        "// Regenerate: python tools/generate_ts_contract.py\n"
    )
    body = "\n\n".join(_emit_interface(m) for m in TS_CONTRACT_MODELS)
    return f"{header}\n{body}\n"


def main() -> None:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
