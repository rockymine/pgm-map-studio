from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from pgm_map_studio.studio.services import region_editor, symmetry_authoring
from pgm_map_studio.studio.services.region_editor import (
    InvalidRegionPayload,
    RegionConflict,
    RegionNotFound,
)
from pgm_map_studio.studio.services.symmetry_authoring import CounterpartError
from pgm_map_studio.studio.services.xml_data import load_xml_data, save_xml_data

bp = Blueprint("regions", __name__, url_prefix="/api/map")


@bp.route("/<name>/regions", methods=["POST"])
def create_region(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = region_editor.create_region(data, body)
    except InvalidRegionPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except RegionConflict as exc:
        return jsonify({"error": str(exc)}), 409
    save_xml_data(data, path)
    return jsonify({"ok": True, **result}), 201


@bp.route("/<name>/regions/group", methods=["POST"])
def group_regions(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = region_editor.group_regions(data, body)
    except InvalidRegionPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except RegionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except RegionConflict as exc:
        return jsonify({"error": str(exc)}), 409
    save_xml_data(data, path)
    return jsonify({"ok": True, **result}), 201


@bp.route("/<name>/regions/ungroup", methods=["POST"])
def ungroup_region(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = region_editor.ungroup_region(data, body)
    except InvalidRegionPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except RegionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/regions/restore", methods=["POST"])
def restore_region(name: str):
    body     = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    snapshot = body.get("snapshot")
    if not snapshot:
        return jsonify({"error": "snapshot required"}), 400
    data, path = load_xml_data(name)
    try:
        result = region_editor.restore_region(data, snapshot)
    except InvalidRegionPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except RegionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except RegionConflict as exc:
        return jsonify({"error": str(exc)}), 409
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/region/<region_id>", methods=["DELETE"])
def delete_region(name: str, region_id: str):
    data, path = load_xml_data(name)
    try:
        result = region_editor.delete_region(data, region_id)
    except RegionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/region/<region_id>", methods=["PATCH"])
def patch_region(name: str, region_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = region_editor.patch_region(data, region_id, body)
    except InvalidRegionPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except RegionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except RegionConflict as exc:
        return jsonify({"error": str(exc)}), 409
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/region/<region_id>/change-type", methods=["POST"])
def change_region_type(name: str, region_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = region_editor.change_region_type(data, region_id, body)
    except InvalidRegionPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except RegionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/region/<region_id>/remove-from-group", methods=["POST"])
def remove_from_group(name: str, region_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = region_editor.remove_from_group(data, region_id, body)
    except InvalidRegionPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except RegionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/region/<region_id>/set-base-child", methods=["POST"])
def set_base_child(name: str, region_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = region_editor.set_base_child(data, region_id, body)
    except InvalidRegionPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except RegionNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/region/<region_id>/counterpart", methods=["POST"])
def create_counterpart(name: str, region_id: str):
    """Create the symmetry counterpart(s) of a region (C13).

    Body: ``{"mode": "<mode>", "center": {"cx", "cz"}}``. When ``center`` is
    omitted it falls back to the confirmed center in ``symmetry.json``.
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    mode = str(body.get("mode", "")).strip()
    data, path = load_xml_data(name)

    center = body.get("center") if isinstance(body.get("center"), dict) else {}
    cx, cz = center.get("cx"), center.get("cz")
    if cx is None or cz is None:
        sym_path = path.parent / "symmetry.json"
        if sym_path.exists():
            sym_center = json.loads(sym_path.read_text(encoding="utf-8")).get("center", {})
            cx = sym_center.get("cx", sym_center.get("center_x"))
            cz = sym_center.get("cz", sym_center.get("center_z"))
    if cx is None or cz is None:
        return jsonify({"error": "center {cx,cz} required (absent from body and symmetry.json)"}), 400
    try:
        cx, cz = float(cx), float(cz)
    except (TypeError, ValueError):
        return jsonify({"error": "center cx/cz must be numbers"}), 400

    try:
        result = symmetry_authoring.create_counterpart(data, region_id, mode, cx, cz)
    except CounterpartError as exc:
        return jsonify({"error": str(exc)}), 400
    save_xml_data(data, path)
    return jsonify({"ok": True, **result}), 201
