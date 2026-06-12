from __future__ import annotations

from flask import Blueprint, jsonify, request

from pgm_map_studio.schemas import (
    WoolAvailabilityResponse,
    WoolSourcesResponse,
    WoolSuggestionsResponse,
)
from pgm_map_studio.studio.services import wool_editor, wool_sources
from pgm_map_studio.studio.services.config import get_output_root
from pgm_map_studio.studio.services.wool_editor import InvalidWoolPayload, WoolNotFound, WoolEditorError
from pgm_map_studio.studio.services.xml_data import load_xml_data, save_xml_data

bp = Blueprint("objectives", __name__, url_prefix="/api/map")


# ── wool availability / detection (C12) ───────────────────────────────────────

@bp.route("/<name>/wool-sources", methods=["POST"])
def wool_sources_in_region(name: str):
    """What wool is in a drawn rectangle? Body: {bounds:{min_x,min_z,max_x,max_z}}."""
    body = request.get_json(silent=True) or {}
    b = body.get("bounds") or {}
    data, _ = load_xml_data(name)
    sources, have = wool_sources.load_wool_sources(get_output_root() / name)
    region_geom = None
    try:
        from shapely.geometry import box
        region_geom = box(float(b["min_x"]), float(b["min_z"]), float(b["max_x"]), float(b["max_z"]))
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "bounds {min_x,min_z,max_x,max_z} required"}), 400
    colors = wool_sources.summarize_sources(sources, region_geom, wool_sources._renewable_geoms(data))
    payload = WoolSourcesResponse.model_validate({"colors": colors, "have_layers": have})
    return jsonify(payload.model_dump())


@bp.route("/<name>/wool-availability")
def wool_availability(name: str):
    """Per declared wool: is its room sourced? (error / info / ok)."""
    data, _ = load_xml_data(name)
    sources, have = wool_sources.load_wool_sources(get_output_root() / name)
    wools = wool_sources.check_availability(data, sources)
    payload = WoolAvailabilityResponse.model_validate({"wools": wools, "have_layers": have})
    return jsonify(payload.model_dump())


@bp.route("/<name>/wool-suggestions")
def wool_suggestions(name: str):
    """Wool colours found in the world but not yet declared as objectives."""
    data, _ = load_xml_data(name)
    sources, have = wool_sources.load_wool_sources(get_output_root() / name)
    suggestions = wool_sources.suggest_wools(data, sources)
    payload = WoolSuggestionsResponse.model_validate({"suggestions": suggestions, "have_layers": have})
    return jsonify(payload.model_dump())


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
