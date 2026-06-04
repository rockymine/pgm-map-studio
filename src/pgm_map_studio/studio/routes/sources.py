from __future__ import annotations

import io
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, abort, jsonify, request, send_file

from pgm_map_studio.studio.services.config import get_maps_folder, get_output_root
from pgm_map_studio.studio.services.map_status import (
    check_pipeline_status,
    is_editor_ready,
    map_display_info,
)

bp = Blueprint("sources", __name__, url_prefix="/api")


@bp.route("/sources")
def list_sources():
    maps_folder = get_maps_folder()
    if not maps_folder or not maps_folder.exists():
        return jsonify({"error": "maps_folder not configured or does not exist"}), 400

    output_root = get_output_root()
    maps = []
    for path in sorted(maps_folder.iterdir()):
        if not path.is_dir():
            continue
        if not (path / "region").is_dir() and not _has_map_xml(path):
            continue
        slug = path.name
        out_dir = output_root / slug
        info = map_display_info(out_dir)
        maps.append({
            "slug":         slug,
            "display_name": info.get("name") or slug.replace("_", " ").title(),
            "has_xml":      (path / "map.xml").exists(),
            "has_region":   (path / "region").is_dir(),
            "editor_ready": is_editor_ready(out_dir),
            "info":         info,
        })
    return jsonify(maps)


@bp.route("/sources/<name>/status")
def source_status(name: str):
    out_dir = get_output_root() / name
    steps = check_pipeline_status(out_dir)
    info = map_display_info(out_dir)
    return jsonify({
        "steps":        steps,
        "all_done":     all(s["done"] for s in steps),
        "editor_ready": is_editor_ready(out_dir),
        "info":         info,
    })


@bp.route("/sources/<name>/validate")
def validate_source(name: str):
    maps_folder = get_maps_folder()
    if not maps_folder:
        return jsonify({"valid": False, "issues": ["maps_folder not configured"]})

    map_path = maps_folder / name
    if not map_path.exists():
        return jsonify({"valid": False, "issues": ["Map folder does not exist"]})

    blocking, warnings = [], []
    if not (map_path / "region").is_dir():
        blocking.append("Missing 'region' folder — required for layout analysis")
    if not (map_path / "map.xml").exists():
        warnings.append("No map.xml — XML step will be skipped")

    return jsonify({"valid": not blocking, "issues": blocking, "warnings": warnings})


@bp.route("/sources/<name>/thumbnail")
def source_thumbnail(name: str):
    maps_folder = get_maps_folder()
    candidates = []
    if maps_folder:
        candidates.append(maps_folder / name / "map.png")
    candidates.append(get_output_root() / name / "map.png")
    for p in candidates:
        if p.exists():
            return send_file(p, mimetype="image/png")
    abort(404)


@bp.route("/import-from-url", methods=["POST"])
def import_from_url():
    body = request.get_json(silent=True) or {}
    url  = body.get("url", "").strip()
    name_override = body.get("name", "").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400

    maps_folder = get_maps_folder()
    if not maps_folder or not maps_folder.exists():
        return jsonify({"error": "maps_folder not configured"}), 400

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        return jsonify({"error": f"Download failed: HTTP {exc.code}"}), 400
    except Exception as exc:
        return jsonify({"error": f"Download failed: {exc}"}), 400

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return jsonify({"error": "Downloaded file is not a valid ZIP"}), 400

    top_dirs = {e.split("/")[0] for e in zf.namelist() if e.split("/")[0]}
    zip_top = next(iter(top_dirs)) if len(top_dirs) == 1 else None

    def _norm(n: str) -> str:
        return n.strip().lower().replace(" ", "_")

    if name_override:
        slug = _norm(name_override)
    elif zip_top:
        slug = _norm(zip_top)
    else:
        slug = _norm(Path(urlparse(url).path).name) or "imported_map"

    dest = maps_folder / slug
    dest.mkdir(parents=True, exist_ok=True)

    for member in zf.infolist():
        rel = member.filename
        if zip_top:
            prefix = zip_top + "/"
            if not rel.startswith(prefix):
                continue
            rel = rel[len(prefix):]
            if not rel:
                continue
        target = dest / rel
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)

    if not (dest / "region").is_dir():
        return jsonify({"error": "ZIP does not contain a 'region' folder — not a valid Minecraft world"}), 400

    return jsonify({"slug": slug})


def _has_map_xml(path: Path) -> bool:
    return (path / "map.xml").exists() and not (path / "region").is_dir()
