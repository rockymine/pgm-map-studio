"""Visual debug for the buildability service (C14): where can players build?

Renders `studio.services.buildability.compute_buildability` over the map bbox as
a PNG you can eyeball:

  green   buildable      red  never        orange void-denied (no Y=0 block)
  yellow  restricted     darker = Y=0 terrain

See `docs` via plan C14 / docs/requirements/editor-build-regions.md.

    python tools/buildability_preview.py <map> [--out preview.png] [--margin 16]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from pgm_map_studio.studio.services.buildability import (  # noqa: E402
    CLASS_COLORS, CLASSES, compute_buildability,
)


def _find(map_name: str) -> Path | None:
    for root in ("/tmp/pgm-studio-output", "/tmp/pipeline_out", "/tmp/publicmaps_out"):
        hits = glob.glob(f"{root}/{map_name}/xml_data.json")
        if hits:
            return Path(hits[0])
    return None


def _islands_bbox(path: Path, data: dict, margin: int) -> tuple[int, int, int, int] | None:
    isl = path.parent / "islands.json"
    if isl.exists():
        islands = json.loads(isl.read_text())
        if islands:
            xs = [b for i in islands for b in (i["bounds"][0], i["bounds"][2])]
            zs = [b for i in islands for b in (i["bounds"][1], i["bounds"][3])]
            return (min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin)
    return None  # service falls back to region bounds


def _y0_columns(path: Path):
    y0 = path.parent / "layer_y0.parquet"
    if not y0.exists():
        return None
    import pandas as pd
    df = pd.read_parquet(y0)
    return set(zip(df["world_x"].tolist(), df["world_z"].tolist()))


def run(map_name: str, margin: int = 16) -> dict:
    path = _find(map_name)
    if path is None:
        raise SystemExit(f"map {map_name!r} not found in the output folders")
    data = json.loads(path.read_text())
    y0 = _y0_columns(path)
    bbox = _islands_bbox(path, data, margin)
    result = compute_buildability(data, y0, bbox, margin)
    # terrain grid for the render overlay
    min_x, min_z, _, _ = result["bbox"]
    terrain = np.zeros((result["height"], result["width"]), dtype=bool)
    for (x, z) in (y0 or ()):
        ix, iz = x - min_x, z - min_z
        if 0 <= ix < result["width"] and 0 <= iz < result["height"]:
            terrain[iz, ix] = True
    return {**result, "terrain": terrain, "map": map_name}


def render(result: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    def _rgb(hexstr):
        h = hexstr.lstrip("#")
        return [int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    colors = np.array([_rgb(CLASS_COLORS[c]) for c in CLASSES], dtype=float)
    img = colors[result["verdict"]]
    img[result["terrain"]] *= 0.55

    min_x, min_z, max_x, max_z = result["bbox"]
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(img, origin="lower", extent=[min_x, max_x, min_z, max_z], interpolation="nearest")
    ax.set_title(f"{result['map']} — buildability"
                 f"{'' if result['has_y0'] else '  (NO Y=0 layer)'}")
    ax.set_xlabel("x"); ax.set_ylabel("z")
    ax.legend(handles=[
        Patch(color=colors[0], label="buildable"),
        Patch(color=colors[1], label="never (outside playable)"),
        Patch(color=colors[2], label="void-denied (no Y=0 block)"),
        Patch(color=colors[3], label="restricted (team/material)"),
        Patch(facecolor="gray", label="· darker = Y=0 terrain"),
    ], loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a map's buildability preview.")
    ap.add_argument("map")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--margin", type=int, default=16)
    args = ap.parse_args()

    result = run(args.map, args.margin)
    out = args.out or Path(f"/tmp/buildability_{args.map}.png")
    render(result, out)

    total = result["width"] * result["height"]
    print(f"{args.map}: bbox={result['bbox']}, Y=0 layer={'yes' if result['has_y0'] else 'MISSING'}")
    for name in CLASSES:
        n = result["counts"][name]
        print(f"  {name:12} {n:8d}  ({100*n/total:5.1f}%)")
    print(f"  → {out}")


if __name__ == "__main__":
    main()
