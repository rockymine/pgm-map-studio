from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import BaseModel, ValidationError

from pgm_map_studio.studio.services import sketch_data, sketch_export
from pgm_map_studio.schemas import SketchLayout, SketchProject, SketchSetup

bp = Blueprint("sketch_api", __name__, url_prefix="/api/sketch")


def _reject(model: type[BaseModel], payload: dict):
    """Validate a PATCH body against `model`. Returns a 400 response tuple if it
    is malformed, or None if it is valid (a gate — the caller persists the
    original partial payload, not a dumped model, so PATCH stays partial)."""
    try:
        model.model_validate(payload)
        return None
    except ValidationError as exc:
        details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                   for e in exc.errors()]
        return jsonify({"error": "Invalid payload", "details": details[:10]}), 400


@bp.route("", methods=["GET"])
def list_all():
    return jsonify(sketch_data.list_sketches())


@bp.route("", methods=["POST"])
def create():
    sid = sketch_data.create_sketch()
    return jsonify({"id": sid}), 201


@bp.route("/<sid>")
def get(sid: str):
    try:
        data = sketch_data.load_sketch(sid)
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404
    # Serialize through the schema so the response matches the TS contract.
    # by_alias=True is required to emit the bezier "in" key (field is in_).
    return jsonify(SketchProject.model_validate(data).model_dump(by_alias=True))


@bp.route("/<sid>/setup", methods=["PATCH"])
def patch_setup(sid: str):
    payload = request.get_json(force=True) or {}
    if (err := _reject(SketchSetup, payload)):     # e.g. an unknown mirror_mode
        return err
    try:
        sketch_data.save_setup(sid, payload)
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404
    return jsonify({"ok": True})


@bp.route("/<sid>/layout", methods=["PATCH"])
def patch_layout(sid: str):
    payload = request.get_json(force=True) or {}
    # validates shape types + bezier controls ("in"/"out") + island records
    if (err := _reject(SketchLayout, {"shapes": payload.get("shapes", []),
                                      "islands": payload.get("islands", [])})):
        return err
    try:
        sketch_data.save_layout(sid, payload.get("shapes", []), payload.get("islands", []))
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404
    return jsonify({"ok": True})


@bp.route("/<sid>/overview", methods=["PATCH"])
def patch_overview(sid: str):
    payload = request.get_json(force=True) or {}
    # SketchProject validates the overview subset (name/version/objective/authors);
    # unrelated keys are ignored, and only _OVERVIEW_FIELDS are persisted.
    if (err := _reject(SketchProject, payload)):
        return err
    try:
        sketch_data.save_overview(sid, payload)
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404
    return jsonify({"ok": True})


@bp.route("/<sid>/export", methods=["POST"])
def post_export(sid: str):
    try:
        result = sketch_export.export_sketch(sid)
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:
        return jsonify({"error": f"Export failed: {exc}"}), 500
    return jsonify(result), 200
