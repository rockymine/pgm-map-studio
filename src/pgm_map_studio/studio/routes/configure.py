from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Blueprint, abort, jsonify, request

from pgm_map_studio.pipeline.config import load_map_config, save_map_config
from pgm_map_studio.studio.services.config import get_maps_folder, get_output_root

logger = logging.getLogger("pgm_map_studio")

bp = Blueprint("configure", __name__, url_prefix="/api/configure")

_VALID_LAYER_TYPES    = {"surface", "y0", "bedrock", "base"}
_VALID_SYMMETRY_TYPES = {"rot_90", "rot_180", "mirror_x", "mirror_z"}


@bp.route("/<name>/state")
def get_state(name: str):
    out_dir = get_output_root() / name
    if not out_dir.exists():
        abort(404)
    cfg = load_map_config(out_dir)

    sym_path = out_dir / "symmetry.json"
    symmetry_status = "unconfirmed"
    if sym_path.exists():
        sym = json.loads(sym_path.read_text(encoding="utf-8"))
        symmetry_status = sym.get("status", "unconfirmed")

    return jsonify({
        "scan_layer":           cfg.scan_layer,
        "scan_layer_confirmed": cfg.scan_layer_confirmed,
        "exclude_islands":      cfg.exclude_islands,
        "exclude_blocks":       cfg.exclude_blocks,
        "symmetry_status":      symmetry_status,
        "configure_complete":   symmetry_status != "unconfirmed",
    })


@bp.route("/<name>/scan-layer", methods=["PATCH"])
def patch_scan_layer(name: str):
    out_dir = get_output_root() / name
    if not out_dir.exists():
        abort(404)
    payload = request.get_json(force=True) or {}
    layer     = payload.get("scan_layer")
    confirmed = bool(payload.get("confirmed", False))

    if layer is not None and layer not in _VALID_LAYER_TYPES:
        return jsonify({"error": f"Invalid layer type: {layer!r}"}), 400

    cfg = load_map_config(out_dir)
    if layer is not None:
        cfg.scan_layer = layer
    if confirmed:
        cfg.scan_layer_confirmed = True
    if "exclude_blocks" in payload:
        cfg.exclude_blocks = [int(b) for b in payload["exclude_blocks"]]
    save_map_config(cfg, out_dir)
    return jsonify({"ok": True, "scan_layer": cfg.scan_layer,
                    "scan_layer_confirmed": cfg.scan_layer_confirmed})


@bp.route("/<name>/exclude-island", methods=["PATCH"])
def patch_exclude_island(name: str):
    out_dir = get_output_root() / name
    if not out_dir.exists():
        abort(404)
    payload   = request.get_json(force=True) or {}
    island_id = payload.get("island_id")
    excluded  = bool(payload.get("excluded", True))

    if island_id is None:
        return jsonify({"error": "island_id is required"}), 400
    try:
        island_id = int(island_id)
    except (ValueError, TypeError):
        return jsonify({"error": "island_id must be an integer"}), 400

    cfg = load_map_config(out_dir)
    if excluded:
        if island_id not in cfg.exclude_islands:
            cfg.exclude_islands.append(island_id)
    else:
        cfg.exclude_islands = [i for i in cfg.exclude_islands if i != island_id]
    save_map_config(cfg, out_dir)
    return jsonify({"ok": True, "exclude_islands": cfg.exclude_islands})


@bp.route("/<name>/exclude-block", methods=["PATCH"])
def patch_exclude_block(name: str):
    out_dir = get_output_root() / name
    if not out_dir.exists():
        abort(404)
    payload  = request.get_json(force=True) or {}
    block_id = payload.get("block_id")
    excluded = bool(payload.get("excluded", True))

    if block_id is None:
        return jsonify({"error": "block_id is required"}), 400
    try:
        block_id = int(block_id)
    except (ValueError, TypeError):
        return jsonify({"error": "block_id must be an integer"}), 400

    cfg = load_map_config(out_dir)
    if excluded:
        if block_id not in cfg.exclude_blocks:
            cfg.exclude_blocks.append(block_id)
    else:
        cfg.exclude_blocks = [b for b in cfg.exclude_blocks if b != block_id]
    save_map_config(cfg, out_dir)
    return jsonify({"ok": True, "exclude_blocks": cfg.exclude_blocks})


@bp.route("/<name>/symmetry", methods=["PATCH"])
def patch_symmetry(name: str):
    out_dir  = get_output_root() / name
    if not out_dir.exists():
        abort(404)
    sym_path = out_dir / "symmetry.json"

    payload = request.get_json(force=True) or {}
    if sym_path.exists():
        sym = json.loads(sym_path.read_text(encoding="utf-8"))
    else:
        sym = {"status": "unconfirmed", "modes": [], "primary": None, "center": None}

    status = payload.get("status")
    if status in ("confirmed", "none"):
        sym["status"] = status

    confirmed_type = payload.get("confirmed_type")
    if confirmed_type is not None:
        if confirmed_type not in _VALID_SYMMETRY_TYPES:
            return jsonify({"error": f"Invalid symmetry type: {confirmed_type!r}"}), 400
        sym["primary"] = {"type": confirmed_type, "confidence": 1.0, "user_override": True}
    elif status == "none":
        sym["primary"] = None

    if "cx" in payload or "cz" in payload:
        current = sym.get("center") or {}
        sym["center"] = {
            "cx": float(payload.get("cx", current.get("cx", 0.0))),
            "cz": float(payload.get("cz", current.get("cz", 0.0))),
        }

    sym_path.write_text(json.dumps(sym, indent=2), encoding="utf-8")
    return jsonify({"ok": True})


@bp.route("/<name>/layers/<layer_type>/pixels")
def get_layer_pixels(name: str, layer_type: str):
    """Return coloured pixel data for a specific layer extractor type."""
    if layer_type not in _VALID_LAYER_TYPES:
        return jsonify({"error": f"Unknown layer type: {layer_type!r}"}), 400
    out_dir = get_output_root() / name
    if not out_dir.exists():
        abort(404)
    parquet_path = _resolve_layer_parquet(name, layer_type, out_dir, load_map_config(out_dir))
    if parquet_path is None:
        return jsonify({"error": "World files not available for this map"}), 404
    return _pixels_from_parquet(parquet_path)


@bp.route("/<name>/layers/<layer_type>/block-types")
def get_layer_block_types(name: str, layer_type: str):
    """Return aggregated block-type info (name, colour, count) for a layer.

    Returns a flat list sorted by count descending. The client is responsible
    for splitting into included/excluded based on its in-memory state.
    """
    if layer_type not in _VALID_LAYER_TYPES:
        return jsonify({"error": f"Unknown layer type: {layer_type!r}"}), 400
    out_dir = get_output_root() / name
    if not out_dir.exists():
        abort(404)
    cfg = load_map_config(out_dir)
    parquet_path = _resolve_layer_parquet(name, layer_type, out_dir, cfg)
    if parquet_path is None:
        return jsonify([])
    return _block_types_from_parquet(parquet_path)


# ── helpers ───────────────────────────────────────────────────────────────

def _resolve_layer_parquet(name: str, layer_type: str, out_dir: Path, cfg) -> Path | None:
    """Return the parquet path for layer_type, generating a cache if needed."""
    canonical  = out_dir / "layer.parquet"
    cache_path = out_dir / f"layer_{layer_type}.parquet"
    if layer_type == cfg.scan_layer and canonical.exists():
        return canonical
    if cache_path.exists():
        return cache_path
    return _generate_layer_cache(name, layer_type, out_dir, cache_path)


def _generate_layer_cache(name: str, layer_type: str, out_dir: Path, cache_path: Path):
    """Run the appropriate extractor and save a cached parquet. Returns path or None."""
    maps_folder = get_maps_folder()
    if not maps_folder:
        return None
    region_dir = maps_folder / name / "region"
    if not region_dir.is_dir():
        return None

    try:
        from pgm_map_studio.minecraft.region_reader import RegionReader
        from pgm_map_studio.minecraft.layers import (
            Y0Extractor, SurfaceExtractor, BedrockExtractor, BaseExtractor,
        )
        reader = RegionReader(region_dir)
        if layer_type == "y0":
            df = Y0Extractor(reader).extract()
        elif layer_type == "surface":
            df = SurfaceExtractor(reader).extract()
        elif layer_type == "bedrock":
            df = BedrockExtractor(reader).extract()
        else:  # base
            df = BaseExtractor(reader).extract()

        df.to_parquet(cache_path)
        logger.info(f"[{name}] Cached layer_{layer_type}.parquet ({len(df)} blocks)")
        return cache_path
    except Exception as exc:
        logger.warning(f"[{name}] Layer generation failed for {layer_type}: {exc}")
        return None


def _pixels_from_parquet(path: Path):
    try:
        import pandas as pd
        from pgm_map_studio.minecraft.colors import block_color

        df = pd.read_parquet(path, columns=["world_x", "world_z", "block_id", "block_data"])
        bid_vals  = df["block_id"].astype(int)
        bdat_vals = df["block_data"].astype(int)
        unique_pairs = set(zip(bid_vals.tolist(), bdat_vals.tolist()))
        color_cache = {
            (bid, bdat): "#{:02x}{:02x}{:02x}".format(*block_color(bid, bdat))
            for bid, bdat in unique_pairs
        }
        colors = [color_cache[(bid, bdat)] for bid, bdat in zip(bid_vals, bdat_vals)]
        return jsonify({
            "xs":     df["world_x"].tolist(),
            "zs":     df["world_z"].tolist(),
            "colors": colors,
            "min_x":  int(df["world_x"].min()),
            "min_z":  int(df["world_z"].min()),
            "max_x":  int(df["world_x"].max()),
            "max_z":  int(df["world_z"].max()),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _block_types_from_parquet(path: Path):
    """Return one entry per distinct block_id, summing counts across data variants.

    Color is taken from the most-common data variant for that block_id.
    """
    try:
        import pandas as pd
        from pgm_map_studio.minecraft.colors import block_color, block_name

        df = pd.read_parquet(path, columns=["block_id", "block_data"])

        # Find dominant data value per block_id (most frequent)
        by_pair = (
            df.groupby(["block_id", "block_data"])
            .size()
            .reset_index(name="count")
        )
        dominant = (
            by_pair.sort_values("count", ascending=False)
            .drop_duplicates(subset=["block_id"])
            .set_index("block_id")["block_data"]
        )

        # Aggregate total count per block_id
        totals = by_pair.groupby("block_id")["count"].sum().sort_values(ascending=False)

        result = []
        for bid, total in totals.items():
            bid = int(bid)
            bdat = int(dominant[bid])
            r, g, b = block_color(bid, bdat)
            result.append({
                "block_id": bid,
                "name": block_name(bid, bdat),
                "color": "#{:02x}{:02x}{:02x}".format(r, g, b),
                "count": int(total),
            })

        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
