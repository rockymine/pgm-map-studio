"""Routes for C9 filter↔region wiring: suggestions + apply-template."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from pgm_map_studio.studio.services import filter_wiring
from pgm_map_studio.studio.services.apply_rule_editor import InvalidApplyRulePayload
from pgm_map_studio.studio.services.filter_editor import FilterConflict, InvalidFilterPayload
from pgm_map_studio.studio.services.region_editor import (
    InvalidRegionPayload,
    RegionConflict,
    RegionNotFound,
)
from pgm_map_studio.studio.services.xml_data import load_xml_data, save_xml_data

bp = Blueprint("wiring", __name__, url_prefix="/api/map")


@bp.route("/<name>/wiring/suggestions", methods=["GET"])
def suggestions(name: str):
    data, _ = load_xml_data(name)
    return jsonify(filter_wiring.suggest(data))


@bp.route("/<name>/wiring/apply", methods=["POST"])
def apply(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = filter_wiring.apply_template(
            data, body.get("template", ""), body.get("params") or {}
        )
    except (filter_wiring.WiringError, InvalidApplyRulePayload,
            InvalidFilterPayload, InvalidRegionPayload, RegionNotFound) as exc:
        return jsonify({"error": str(exc)}), 400
    except (FilterConflict, RegionConflict) as exc:
        return jsonify({"error": str(exc)}), 409
    save_xml_data(data, path)
    return jsonify({"ok": True, **result}), 201
