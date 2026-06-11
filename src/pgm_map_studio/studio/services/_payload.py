"""Shared payload-validation helpers for the map-editing editor services.

The editors own request-body validation (routes are thin exception-mappers that
turn `Invalid*Payload` into a 400). These helpers make that validation robust to
hostile input — a non-object body or a wrong-typed numeric field becomes a clean
`Invalid*Payload` (→ 400) instead of an `AttributeError`/`ValueError` (→ 500).

Each helper takes the editor's own exception class so the right error type (and
HTTP status) is raised.
"""
from __future__ import annotations

from typing import Any


def require_dict(payload: Any, exc: type[Exception]) -> dict:
    """Return `payload` if it is a dict, else raise `exc` (the body wasn't a JSON object)."""
    if not isinstance(payload, dict):
        raise exc("request body must be a JSON object")
    return payload


def coerce_int(value: Any, field: str, exc: type[Exception]) -> int:
    """`int(value)`, but a non-integer raises `exc` instead of ValueError/TypeError.

    Stays lenient like the old `int(...)` (accepts "20", 20.0, True) so existing
    frontend payloads keep working; only genuinely non-numeric values are rejected.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        raise exc(f"{field!r} must be an integer")


def coerce_float(value: Any, field: str, exc: type[Exception]) -> float:
    """`float(value)`, but a non-number raises `exc` instead of ValueError/TypeError."""
    try:
        return float(value)
    except (TypeError, ValueError):
        raise exc(f"{field!r} must be a number")
