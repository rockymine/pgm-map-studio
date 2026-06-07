from __future__ import annotations

from flask import Blueprint, jsonify, request

from pgm_map_studio.studio.services import spawn_editor
from pgm_map_studio.studio.services.spawn_editor import (
    InvalidSpawnPayload, SpawnConflict, SpawnNotFound,
    set_observer_spawn, delete_observer_spawn,
)
from pgm_map_studio.studio.services.xml_data import load_xml_data, save_xml_data

bp = Blueprint("spawns", __name__, url_prefix="/api/map")


@bp.route("/<name>/spawns", methods=["POST"])
def add_spawn(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        spawn_editor.add_spawn_link(data, body)
    except InvalidSpawnPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except SpawnNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except SpawnConflict as exc:
        return jsonify({"error": str(exc)}), 409
    save_xml_data(data, path)
    return jsonify({"ok": True}), 201


@bp.route("/<name>/spawn/<region_id>", methods=["PATCH"])
def update_spawn(name: str, region_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        spawn_editor.update_spawn_link(data, region_id, body)
    except SpawnNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True})


@bp.route("/<name>/spawn/<region_id>", methods=["DELETE"])
def delete_spawn(name: str, region_id: str):
    data, path = load_xml_data(name)
    try:
        spawn_editor.delete_spawn_link(data, region_id)
    except SpawnNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True})


@bp.route("/<name>/observer-spawn", methods=["PATCH"])
def patch_observer_spawn(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        set_observer_spawn(data, body)
    except InvalidSpawnPayload as exc:
        return jsonify({"error": str(exc)}), 400
    except SpawnNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True})


@bp.route("/<name>/observer-spawn", methods=["DELETE"])
def delete_observer_spawn_route(name: str):
    data, path = load_xml_data(name)
    try:
        delete_observer_spawn(data)
    except SpawnNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True})
