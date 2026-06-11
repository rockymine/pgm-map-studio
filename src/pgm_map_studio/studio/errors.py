"""Structured error envelope for the JSON API (C1).

Every error response under ``/api/`` has the shape::

    {"error": {"code": "<machine-readable>", "message": "<human-readable>"}}

Routes keep returning the simple flat form (``jsonify({"error": "..."}), 404``)
or calling ``abort(404)``; this module's hooks rewrite both into the envelope so
the contract is enforced in one place rather than ~90 call sites. A route that
wants a specific code can emit the enveloped form directly — it's passed through
untouched. Extra keys on the body (e.g. ``references`` on a 409) are preserved.
"""
from __future__ import annotations

import json

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

# HTTP status → default machine-readable code.
_CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    415: "unsupported_media_type",
    422: "unprocessable",
    500: "internal",
}


def _code_for(status: int) -> str:
    return _CODE_BY_STATUS.get(status, "error")


def _envelope_flat_errors(response: Response) -> Response:
    """after_request: rewrite a flat ``{"error": "<str>"}`` JSON body into the envelope."""
    if response.status_code < 400 or not response.is_json:
        return response
    data = response.get_json(silent=True)
    if not isinstance(data, dict) or "error" not in data:
        return response
    err = data["error"]
    if isinstance(err, str):  # flat string → {code, message}; leave already-enveloped dicts alone
        data["error"] = {"code": _code_for(response.status_code), "message": err}
        response.set_data(json.dumps(data))
    return response


def _json_http_error(exc: HTTPException):
    """errorhandler: render abort()/HTTPException under /api/ as the JSON envelope.

    Scoped to /api/ so HTML page routes keep their normal error pages.
    """
    if not request.path.startswith("/api/"):
        return exc
    status = exc.code or 500
    return jsonify({"error": {"code": _code_for(status), "message": exc.description}}), status


def register_error_envelope(app: Flask) -> None:
    app.after_request(_envelope_flat_errors)
    app.register_error_handler(HTTPException, _json_http_error)
