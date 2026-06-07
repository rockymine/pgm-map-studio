from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, abort, jsonify, request

from pgm_map_studio.studio.services.config import get_output_root
from pgm_map_studio.studio.services.xml_data import load_xml_data, save_xml_data

bp = Blueprint("map_api", __name__, url_prefix="/api/map")

_META_FIELDS = {"name", "version", "objective", "max_build_height", "gamemode", "authors"}


@bp.route("/<name>")
def get_map(name: str):
    data, _ = load_xml_data(name)
    return jsonify(data)


@bp.route("/<name>/metadata", methods=["PATCH"])
def patch_metadata(name: str):
    data, path = load_xml_data(name)
    payload = request.get_json(force=True) or {}
    for key, value in payload.items():
        if key in _META_FIELDS:
            data[key] = value
    save_xml_data(data, path)
    return jsonify({"ok": True})


@bp.route("/<name>/symmetry")
def get_symmetry(name: str):
    sym_path = get_output_root() / name / "symmetry.json"
    if not sym_path.exists():
        abort(404)
    return jsonify(json.loads(sym_path.read_text(encoding="utf-8")))


@bp.route("/<name>/symmetry", methods=["PATCH"])
def patch_symmetry(name: str):
    sym_path = get_output_root() / name / "symmetry.json"
    if not sym_path.exists():
        abort(404)
    sym = json.loads(sym_path.read_text(encoding="utf-8"))
    payload = request.get_json(force=True) or {}
    if "status" in payload:
        sym["status"] = payload["status"]
    sym_path.write_text(json.dumps(sym, indent=2), encoding="utf-8")
    return jsonify({"ok": True})


@bp.route("/<name>/islands")
def get_islands(name: str):
    islands_path = get_output_root() / name / "islands.json"
    if not islands_path.exists():
        abort(404)
    return jsonify(json.loads(islands_path.read_text(encoding="utf-8")))


@bp.route("/<name>/config")
def get_map_config(name: str):
    from pgm_map_studio.pipeline.config import load_map_config
    out_dir = get_output_root() / name
    cfg = load_map_config(out_dir)
    return jsonify(cfg.to_dict())


@bp.route("/<name>/config", methods=["PATCH"])
def patch_map_config(name: str):
    from pgm_map_studio.pipeline.config import load_map_config, save_map_config, MapConfig
    out_dir = get_output_root() / name
    cfg = load_map_config(out_dir)
    payload = request.get_json(force=True) or {}
    updated = {**cfg.to_dict(), **{k: v for k, v in payload.items() if k in cfg.to_dict()}}
    save_map_config(MapConfig.from_dict(updated), out_dir)
    return jsonify({"ok": True})


@bp.route("/<name>/regions")
def get_regions(name: str):
    data, _ = load_xml_data(name)
    regions = data.get("regions", {})

    islands_path = get_output_root() / name / "islands.json"
    bounding_box = None
    if islands_path.exists():
        islands = json.loads(islands_path.read_text(encoding="utf-8"))
        if islands:
            xs = [i["bounds"][0] for i in islands] + [i["bounds"][2] for i in islands]
            zs = [i["bounds"][1] for i in islands] + [i["bounds"][3] for i in islands]
            bounding_box = {"min_x": min(xs), "min_z": min(zs), "max_x": max(xs), "max_z": max(zs)}

    categories = _compute_categories(regions, data)
    return jsonify({
        "regions":     regions,
        "categories":  categories,
        "bounding_box": bounding_box,
    })


@bp.route("/<name>/layers/top-surface")
def layer_top_surface(name: str):
    parquet_path = get_output_root() / name / "layer.parquet"
    if not parquet_path.exists():
        abort(404)
    try:
        import pandas as pd
        from pgm_map_studio.minecraft.colors import block_color
        df = pd.read_parquet(parquet_path, columns=["world_x", "world_z", "block_id", "block_data"])
        bid_vals  = df["block_id"].astype(int)
        bdat_vals = df["block_data"].astype(int)
        unique_pairs = set(zip(bid_vals.tolist(), bdat_vals.tolist()))
        color_cache = {
            (bid, bdat): "#{:02x}{:02x}{:02x}".format(*block_color(bid, bdat))
            for bid, bdat in unique_pairs
        }
        colors = [color_cache[(bid, bdat)] for bid, bdat in zip(bid_vals, bdat_vals)]
        return jsonify({
            "xs":    df["world_x"].tolist(),
            "zs":    df["world_z"].tolist(),
            "colors": colors,
            "min_x": int(df["world_x"].min()), "min_z": int(df["world_z"].min()),
            "max_x": int(df["world_x"].max()), "max_z": int(df["world_z"].max()),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _compute_categories(regions: dict, data: dict) -> dict:
    """Categorise regions by their role in the map data.

    Precedence: actual spawn/wool references > stored region_categories hints > name heuristics.
    The stored hints let newly drawn (not-yet-linked) regions appear in the correct category.
    """
    cats: dict[str, str] = {}

    spawn_ids: set[str] = _region_id_set(data.get("spawns", []), "region")
    obs = data.get("observer_spawn")
    if obs:
        rid = _extract_region_id(obs.get("region"))
        if rid:
            spawn_ids.add(rid)

    wool_ids: set[str] = set()
    for wool in data.get("wools", []):
        if wool.get("wool_room_region"):
            wool_ids.add(wool["wool_room_region"])
    for spawner in data.get("spawners", []):
        for field in ("spawn_region", "player_region"):
            if spawner.get(field):
                wool_ids.add(spawner[field])

    hints: dict[str, str] = {}
    for cat_name, ids in data.get("region_categories", {}).items():
        for hint_id in ids:
            hints[hint_id] = cat_name

    for rid in regions:
        if rid in spawn_ids:
            cats[rid] = "spawn"
        elif rid in wool_ids:
            cats[rid] = "wool"
        elif "build" in rid.lower():
            cats[rid] = "build"
        else:
            cats[rid] = hints.get(rid, "other")

    return cats


def _extract_region_id(region) -> str:
    """Return the region ID from either a string ID or an inline region dict."""
    if isinstance(region, str):
        return region
    if isinstance(region, dict):
        return region.get("id", "")
    return ""


def _region_id_set(items: list, field: str) -> set[str]:
    """Collect region IDs from a list of objects that reference a region by field name."""
    return {rid for item in items if (rid := _extract_region_id(item.get(field)))}
