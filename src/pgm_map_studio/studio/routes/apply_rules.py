from __future__ import annotations

from flask import Blueprint, jsonify, request

from pgm_map_studio.studio.services import apply_rule_editor
from pgm_map_studio.studio.services.apply_rule_editor import (
    ApplyRuleNotFound,
    InvalidApplyRulePayload,
)
from pgm_map_studio.studio.services.xml_data import load_xml_data, save_xml_data

bp = Blueprint("apply_rules", __name__, url_prefix="/api/map")


@bp.route("/<name>/apply-rules")
def list_apply_rules(name: str):
    data, path = load_xml_data(name)
    result = apply_rule_editor.list_apply_rules(data)
    save_xml_data(data, path)          # persist backfilled ids
    return jsonify(result)


@bp.route("/<name>/apply-rules", methods=["POST"])
def create_apply_rule(name: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = apply_rule_editor.create_apply_rule(data, body)
    except InvalidApplyRulePayload as exc:
        return jsonify({"error": str(exc)}), 400
    save_xml_data(data, path)
    return jsonify({"ok": True, **result}), 201


@bp.route("/<name>/apply-rule/<rule_id>", methods=["PATCH"])
def update_apply_rule(name: str, rule_id: str):
    body = request.get_json(silent=True) or {}
    data, path = load_xml_data(name)
    try:
        result = apply_rule_editor.update_apply_rule(data, rule_id, body)
    except InvalidApplyRulePayload as exc:
        return jsonify({"error": str(exc)}), 400
    except ApplyRuleNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})


@bp.route("/<name>/apply-rule/<rule_id>", methods=["DELETE"])
def delete_apply_rule(name: str, rule_id: str):
    data, path = load_xml_data(name)
    try:
        result = apply_rule_editor.delete_apply_rule(data, rule_id)
    except ApplyRuleNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    save_xml_data(data, path)
    return jsonify({"ok": True, **result})
