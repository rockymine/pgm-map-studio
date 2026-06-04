from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, stream_with_context

from pgm_map_studio.studio.services.config import get_maps_folder, get_output_root

bp = Blueprint("pipeline", __name__, url_prefix="/api")


@bp.route("/pipeline/<name>/run")
def run_pipeline(name: str):
    force = request.args.get("force", "0") == "1"
    force_layout   = request.args.get("force_layout",   "0") == "1"
    force_symmetry = request.args.get("force_symmetry", "0") == "1"
    force_xml      = request.args.get("force_xml",      "0") == "1"

    maps_folder = get_maps_folder()
    if not maps_folder:
        return jsonify({"error": "maps_folder not configured"}), 400

    map_path = maps_folder / name
    if not map_path.exists():
        return jsonify({"error": f"Map not found: {name}"}), 404

    output_root = get_output_root()

    def generate():
        q: queue.Queue = queue.Queue()

        def _send(event: str, data: dict):
            q.put(f"event: {event}\ndata: {json.dumps(data)}\n\n")

        def _thread():
            try:
                _run(map_path, output_root, name, force, force_layout, force_symmetry, force_xml, _send)
            except Exception as exc:
                _send("error", {"message": str(exc)})
            finally:
                q.put(None)

        threading.Thread(target=_thread, daemon=True).start()
        while True:
            item = q.get()
            if item is None:
                break
            yield item

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _run(map_path: Path, output_root: Path, name: str, force: bool,
         force_layout: bool, force_symmetry: bool, force_xml: bool, send) -> None:
    from pgm_map_studio.minecraft.sources import MapSource
    from pgm_map_studio.pipeline import run as pipeline_run

    source = MapSource(
        slug=name,
        path=map_path,
        has_xml=(map_path / "map.xml").exists(),
        game_mode="ctw",
    )
    out_dir = output_root / name
    out_dir.mkdir(parents=True, exist_ok=True)

    send("step", {"id": "layout", "status": "running"})
    try:
        result = pipeline_run(
            source, output_root,
            force=force,
            force_layout=force_layout,
            force_symmetry=force_symmetry,
            force_xml=force_xml,
        )
        send("step", {"id": "layout",   "status": "done"})
        send("step", {"id": "symmetry", "status": "done"})
        send("step", {"id": "xml",      "status": "done" if result.xml_ran or (out_dir / "xml_data.json").exists() else "skipped"})
        send("done", {"slug": name})
    except Exception as exc:
        send("step", {"id": "layout", "status": "error", "message": str(exc)})
        raise
