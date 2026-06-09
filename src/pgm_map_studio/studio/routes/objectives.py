from __future__ import annotations

from flask import Blueprint, jsonify, request

from pgm_map_studio.studio.services import wool_editor
from pgm_map_studio.studio.services.wool_editor import InvalidWoolPayload, WoolNotFound, WoolEditorError
from pgm_map_studio.studio.services.xml_data import load_xml_data, save_xml_data

bp = Blueprint("objectives", __name__, url_prefix="/api/map")


@bp.route("/<name>/wools", methods=["POST"])
def add_wool(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = wool_editor.add_wool(data, body)
    except InvalidWoolPayload as exc:
        return jsonify({"error": str(exc)}), 400
    save_xml_data(data, path)
    return jsonify({"ok": True, **result}), 201


@bp.route("/<name>/wools/<wool_id>", methods=["PATCH"])
def update_wool(name: str, wool_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = wool_editor.update_wool(data, wool_id, body)
    except WoolNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except InvalidWoolPayload as exc:
        return jsonify({"error": str(exc)}), 400
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/wools/<wool_id>", methods=["DELETE"])
def delete_wool(name: str, wool_id: str):
    data, path = load_xml_data(name)
    try:
        wool_editor.delete_wool(data, wool_id)
    except WoolNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True})


@bp.route("/<name>/wools/<wool_id>/monuments", methods=["POST"])
def add_monument(name: str, wool_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = wool_editor.add_monument(data, wool_id, body)
    except WoolNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except InvalidWoolPayload as exc:
        return jsonify({"error": str(exc)}), 400
    save_xml_data(data, path)
    return jsonify({"ok": True, **result}), 201


@bp.route("/<name>/wools/<wool_id>/monuments/<mon_id>", methods=["PATCH"])
def update_monument(name: str, wool_id: str, mon_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = wool_editor.update_monument(data, wool_id, mon_id, body)
    except WoolNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except InvalidWoolPayload as exc:
        return jsonify({"error": str(exc)}), 400
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/wools/<wool_id>/monuments/<mon_id>", methods=["DELETE"])
def delete_monument(name: str, wool_id: str, mon_id: str):
    data, path = load_xml_data(name)
    try:
        wool_editor.delete_monument(data, wool_id, mon_id)
    except WoolNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True})
