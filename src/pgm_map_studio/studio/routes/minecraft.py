from __future__ import annotations

from flask import Blueprint, jsonify, request

from pgm_map_studio.studio.services.mojang import lookup_player

bp = Blueprint("minecraft", __name__, url_prefix="/api/minecraft")


@bp.route("/player")
def player_lookup():
    name = request.args.get("name", "").strip()
    uuid = request.args.get("uuid", "").strip()
    query = uuid or name
    if not query:
        return jsonify({"error": "name or uuid required"}), 400
    try:
        result = lookup_player(query)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    return jsonify(result)
