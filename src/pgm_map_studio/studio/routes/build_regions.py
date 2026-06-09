from __future__ import annotations

import numpy as np
import pandas as pd
from flask import Blueprint, abort, jsonify, request

from pgm_map_studio.studio.services.config import get_maps_folder, get_output_root

bp = Blueprint("build_regions", __name__, url_prefix="/api/map")


def _resolve_out_dir(name: str):
    root = get_output_root().resolve()
    out_dir = (root / name).resolve()
    if not out_dir.is_relative_to(root):
        abort(400)
    return out_dir


def _load_or_extract_segments(name: str, out_dir) -> pd.DataFrame:
    segments_path = out_dir / "layer_segments.parquet"
    if segments_path.exists():
        return pd.read_parquet(segments_path)

    maps_folder = get_maps_folder()
    if not maps_folder:
        abort(404, description="layer_segments.parquet not found; re-run the pipeline")

    map_path = maps_folder / name
    if not (map_path / "region").exists():
        abort(404, description=f"Map region folder not found: {name}")

    from pgm_map_studio.minecraft.region_reader import RegionReader
    from pgm_map_studio.minecraft.layers import SegmentsExtractor

    reader = RegionReader(map_path / "region")
    df = SegmentsExtractor(reader).extract()
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(segments_path)
    return df


def _build_depth_map(df: pd.DataFrame, axis: str) -> dict | None:
    """Project vertical segments onto a 2D depth map.

    For axis='z', looking along Z: primary=world_x, depth=world_z.
    For axis='x', looking along X: primary=world_z, depth=world_x.

    Returns a flat int array where each value is 0-255 (nearest=0) or -1 (empty).
    Index = p_idx * y_count + y_idx.
    """
    if df.empty:
        return None

    primary_col = "world_x" if axis == "z" else "world_z"
    depth_col   = "world_z" if axis == "z" else "world_x"

    primary_min = int(df[primary_col].min())
    primary_max = int(df[primary_col].max())
    depth_min   = int(df[depth_col].min())
    depth_max   = int(df[depth_col].max())
    y_min       = int(df["world_y_start"].min())
    y_max       = int(df["world_y_end"].max())

    P = primary_max - primary_min + 1
    H = y_max - y_min + 1
    D = depth_max - depth_min + 1

    p_arr  = (df[primary_col].values    - primary_min).astype(np.int32)
    d_arr  = (df[depth_col].values      - depth_min).astype(np.int32)
    ys_arr = (df["world_y_start"].values - y_min).astype(np.int32)
    ye_arr = (df["world_y_end"].values   - y_min + 1).astype(np.int32)

    # front_depth[p, y] = minimum depth index (nearest block), D = empty sentinel
    front_depth = np.full((P, H), D, dtype=np.int32)
    for i in range(len(df)):
        s, e = int(ys_arr[i]), int(ye_arr[i])
        np.minimum(front_depth[int(p_arr[i]), s:e], int(d_arr[i]),
                   out=front_depth[int(p_arr[i]), s:e])

    # Normalize to 0-255; empty cells = -1
    empty = front_depth >= D
    if D > 1:
        norm = ((front_depth.astype(np.float32) / (D - 1)) * 255 + 0.5).astype(np.int16)
    else:
        norm = np.zeros((P, H), dtype=np.int16)
    norm[empty] = -1

    return {
        "axis":          axis,
        "primary_min":   primary_min,
        "primary_count": P,
        "y_min":         y_min,
        "y_count":       H,
        "depth":         norm.flatten().tolist(),
    }


@bp.route("/<name>/segments")
def get_segments(name: str):
    axis = request.args.get("axis", "z")
    if axis not in ("x", "z"):
        abort(400, description="axis must be 'x' or 'z'")

    out_dir = _resolve_out_dir(name)
    df = _load_or_extract_segments(name, out_dir)
    result = _build_depth_map(df, axis)
    if result is None:
        return jsonify({"error": "no segment data"}), 404

    return jsonify(result)
