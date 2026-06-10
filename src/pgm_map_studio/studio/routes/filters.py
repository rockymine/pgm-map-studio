from __future__ import annotations

from flask import Blueprint, jsonify, request

from pgm_map_studio.studio.services import filter_editor
from pgm_map_studio.studio.services.filter_editor import (
    FilterConflict,
    FilterInUse,
    FilterNotFound,
    InvalidFilterPayload,
)
from pgm_map_studio.studio.services.xml_data import load_xml_data, save_xml_data

bp = Blueprint("filters", __name__, url_prefix="/api/map")


@bp.route("/<name>/filters")
def list_filters(name: str):
    data, _ = load_xml_data(name)
    return jsonify(filter_editor.list_filters(data))


@bp.route("/<name>/filters", methods=["POST"])
def create_filter(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = filter_editor.create_filter(data, body)
    except InvalidFilterPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except FilterConflict as exc:
        return jsonify({"error": str(exc)}), 409
    save_xml_data(data, path)
    return jsonify({"ok": True, **result}), 201


@bp.route("/<name>/filter/<fid>", methods=["PATCH"])
def update_filter(name: str, fid: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = filter_editor.update_filter(data, fid, body)
    except InvalidFilterPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except FilterNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/filter/<fid>", methods=["DELETE"])
def delete_filter(name: str, fid: str):
    data, path = load_xml_data(name)
    try:
        result = filter_editor.delete_filter(data, fid)
    except FilterNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except FilterInUse as exc:
        return jsonify({"error": str(exc), "references": exc.references}), 409
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})
