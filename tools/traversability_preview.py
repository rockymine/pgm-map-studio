"""Visual debug for the traversability check (plan C15).

Renders the navigability map (walkable surface ∪ bridgeable buildable) with the
connected components, and overlays every spawn + wool point. If any point lands
in a different component it's the disconnection the check warns about.

  dark     not navigable (void / never, no surface)
  green    walkable (a surface block to stand on)
  cyan     bridge-only (buildable gap, no surface)
  ● blue   spawn      ■ white  wool      red ring = isolated (unreachable)

    python tools/traversability_preview.py <map> [--out preview.png]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from pgm_map_studio.studio.services.traversability import (  # noqa: E402
    check_reachability, compute_navigability, navigation_points)


def _find(m: str) -> Path | None:
    hits = glob.glob(f"/tmp/pgm-studio-output/{m}/xml_data.json")
    return Path(hits[0]).parent if hits else None


def _cols(d: Path, layer: str):
    f = d / f"layer_{layer}.parquet"
    if not f.exists():
        return None
    import pandas as pd
    df = pd.read_parquet(f, columns=["world_x", "world_z"])
    return set(zip(df["world_x"].tolist(), df["world_z"].tolist()))


def _islands_bbox(d: Path, margin: int):
    isl = d / "islands.json"
    if isl.exists():
        islands = json.loads(isl.read_text())
        if islands:
            xs = [b for i in islands for b in (i["bounds"][0], i["bounds"][2])]
            zs = [b for i in islands for b in (i["bounds"][1], i["bounds"][3])]
            return (min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("map")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--margin", type=int, default=16)
    args = ap.parse_args()

    d = _find(args.map)
    if d is None:
        raise SystemExit(f"map {args.map!r} not found")
    data = json.loads((d / "xml_data.json").read_text())
    nav = compute_navigability(data, _cols(d, "surface"), _cols(d, "y0"),
                               _islands_bbox(d, args.margin), args.margin)
    points = navigation_points(data)
    result = check_reachability(nav, points)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    nz, nx = nav["height"], nav["width"]
    img = np.zeros((nz, nx, 3))
    img[~nav["navigable"]] = (0.12, 0.12, 0.14)              # not navigable
    img[nav["navigable"] & ~nav["surface"]] = (0.30, 0.75, 0.85)   # bridge-only (cyan)
    img[nav["surface"]] = (0.30, 0.69, 0.31)                # walkable surface (green)

    min_x, min_z, max_x, max_z = nav["bbox"]
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(img, origin="lower", extent=[min_x, max_x, min_z, max_z], interpolation="nearest")
    main_comp = max((p["component"] for p in result["points"] if p["component"] > 0),
                    key=[p["component"] for p in result["points"]].count, default=0)
    for p in result["points"]:
        iso = p["component"] != main_comp
        if p["kind"] == "spawn":
            ax.scatter(p["x"], p["z"], c="#1565c0", s=90, marker="o", edgecolors="white", zorder=3)
        else:
            ax.scatter(p["x"], p["z"], c="white", s=80, marker="s", edgecolors="black", zorder=3)
        if iso:
            ax.scatter(p["x"], p["z"], s=320, facecolors="none", edgecolors="red", linewidths=2.5, zorder=4)
        ax.annotate(p["name"], (p["x"], p["z"]), fontsize=7, color="black", zorder=5,
                    xytext=(4, 4), textcoords="offset points")
    ax.set_title(f"{args.map} — traversability: "
                 f"{'CONNECTED' if result['connected'] else f'{len(result['isolated'])} ISOLATED'}"
                 f"  ({result['component_count']} component(s))")
    ax.set_xlabel("x"); ax.set_ylabel("z")
    out = args.out or Path(f"/tmp/traversability_{args.map}.png")
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)

    print(f"{args.map}: connected={result['connected']}  components={result['component_count']}  "
          f"severity={result['severity']}")
    for p in result["points"]:
        print(f"  {p['kind']:6} {p['name']:12} comp={p['component']}")
    if result["isolated"]:
        print(f"  ISOLATED: {result['isolated']}")
    print(f"  → {out}")


if __name__ == "__main__":
    main()
