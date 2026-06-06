from __future__ import annotations

from flask import Blueprint, jsonify, request

from pgm_map_studio.studio.services import sketch_data

bp = Blueprint("sketch_api", __name__, url_prefix="/api/sketch")


@bp.route("", methods=["POST"])
def create():
    sid = sketch_data.create_sketch()
    return jsonify({"id": sid}), 201


@bp.route("/<sid>")
def get(sid: str):
    try:
        return jsonify(sketch_data.load_sketch(sid))
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404


@bp.route("/<sid>/setup", methods=["PATCH"])
def patch_setup(sid: str):
    payload = request.get_json(force=True) or {}
    try:
        sketch_data.save_setup(sid, payload)
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404
    return jsonify({"ok": True})


@bp.route("/<sid>/layout", methods=["PATCH"])
def patch_layout(sid: str):
    payload = request.get_json(force=True) or {}
    shapes  = payload.get("shapes", [])
    islands = payload.get("islands", [])
    if not isinstance(shapes, list) or not isinstance(islands, list):
        return jsonify({"error": "shapes and islands must be arrays"}), 400
    try:
        sketch_data.save_layout(sid, shapes, islands)
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404
    return jsonify({"ok": True})


@bp.route("/<sid>/overview", methods=["PATCH"])
def patch_overview(sid: str):
    payload = request.get_json(force=True) or {}
    try:
        sketch_data.save_overview(sid, payload)
    except KeyError:
        return jsonify({"error": "Sketch not found"}), 404
    return jsonify({"ok": True})
