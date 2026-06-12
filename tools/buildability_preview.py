"""Visual debug: where can players build on a map?

PGM lets players build *everywhere* by default; an XML restricts that with
block / block-place apply-rules over regions. The hard case is the **void
filter**: a column is "void" when it has no block at Y=0, and a `deny(void)`
(or `not(void)`) placement filter denies building only in void columns — so
buildability is a join of **XML region geometry × the Y=0 layer × rule order**.

This renders that join over the map bounding box (the void/negative regions are
unbounded, so we clip to it) as a PNG you can eyeball:

  green   buildable (default-allow, not denied)
  red     never — a `never` block rule (e.g. outside the playable region)
  orange  void-denied — in a deny-void region AND no block at Y=0
  yellow  restricted — a team/material block filter (only-blue, only-iron, …)
  ·       Y=0 terrain (bedrock/blocks) drawn faintly so you can check the void
          denial bites only on the empty columns

See docs/contracts/region-authoring.md and docs/requirements/editor-build-regions.md.

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
from pgm_map_studio.studio.services.region_encoder import _dict_to_shapely  # noqa: E402

_BLOCK_EVENTS = ("block_place", "block")   # placement-relevant events (last wins)


def _find(map_name: str) -> Path | None:
    for root in ("/tmp/pgm-studio-output", "/tmp/pipeline_out", "/tmp/publicmaps_out"):
        hits = glob.glob(f"{root}/{map_name}/xml_data.json")
        if hits:
            return Path(hits[0])
    return None


def _classify(value: str, filters: dict, seen=None) -> str:
    """Classify a block filter value → 'never' | 'void' (deny-in-void) | 'other'."""
    seen = seen or set()
    if not value or value in seen:
        return "other"
    if value == "never":
        return "never"
    if value in ("always", "allow"):
        return "allow"
    if value == "deny(void)" or ("void" in value and value not in filters):
        return "void"
    f = filters.get(value)
    if not isinstance(f, dict):
        return "other"
    t = f.get("type")
    if t == "void":
        return "void"
    if t == "never":
        return "never"
    if t in ("not", "deny", "allow"):
        return _classify(f.get("child", ""), filters, seen | {value})
    if t in ("any", "all", "one"):
        kinds = [_classify(c, filters, seen | {value}) for c in f.get("children", [])]
        if "void" in kinds:
            return "void"
        if "never" in kinds:
            return "never"
    return "other"


def _bbox(data: dict, path: Path, margin: int) -> tuple[int, int, int, int]:
    """Map bounding box (clip the unbounded void/negative regions). islands.json,
    else the union of region footprints, padded by `margin`."""
    isl = path.parent / "islands.json"
    if isl.exists():
        islands = json.loads(isl.read_text())
        if islands:
            xs = [b for i in islands for b in (i["bounds"][0], i["bounds"][2])]
            zs = [b for i in islands for b in (i["bounds"][1], i["bounds"][3])]
            return (min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin)
    xs, zs = [], []
    for r in data.get("regions", {}).values():
        b = r.get("bounds_2d")
        if b and all(isinstance(b["min"].get(k), (int, float)) for k in "xz"):
            xs += [b["min"]["x"], b["max"]["x"]]
            zs += [b["min"]["z"], b["max"]["z"]]
    if not xs:
        return (-64, -64, 64, 64)
    return (int(min(xs)) - margin, int(min(zs)) - margin, int(max(xs)) + margin, int(max(zs)) + margin)


def compute(map_name: str, margin: int = 16):
    import pandas as pd
    path = _find(map_name)
    if path is None:
        raise SystemExit(f"map {map_name!r} not found in the output folders")
    data = json.loads(path.read_text())
    regions = data.get("regions", {})
    filters = data.get("filters", {})
    rules = data.get("apply_rules", [])

    min_x, min_z, max_x, max_z = _bbox(data, path, margin)
    nx, nz = max_x - min_x, max_z - min_z
    bounds = (min_x, min_z, max_x, max_z)        # clip the negatives to the display box

    # Y=0 terrain mask (a column is void where this is False).
    terrain = np.zeros((nz, nx), dtype=bool)
    y0 = path.parent / "layer_y0.parquet"
    have_y0 = y0.exists()
    if have_y0:
        df = pd.read_parquet(y0)
        ix = (df["world_x"].to_numpy() - min_x)
        iz = (df["world_z"].to_numpy() - min_z)
        ok = (ix >= 0) & (ix < nx) & (iz >= 0) & (iz < nz)
        terrain[iz[ok], ix[ok]] = True
    void = ~terrain

    # column-centre sample grid (matches rasterisation: x+0.5, z+0.5)
    import shapely
    xs = np.arange(min_x, max_x) + 0.5
    zs = np.arange(min_z, max_z) + 0.5
    gx, gz = np.meshgrid(xs, zs)

    all_true = np.ones((nz, nx), dtype=bool)

    def _mask(region_ref):
        if region_ref is None:                     # global rule (no region) = whole map
            return all_true
        region = regions.get(region_ref) if isinstance(region_ref, str) else region_ref
        geom = _dict_to_shapely(region, bounds, regions) if region else None
        if geom is None or geom.is_empty:
            return None
        return shapely.contains_xy(geom, gx, gz)

    # 0 buildable · 1 never/outside-gate · 2 void-denied · 3 restricted ; last rule wins
    verdict = np.zeros((nz, nx), dtype=np.uint8)
    applied = 0
    for rule in rules:
        inreg = _mask(rule.get("region"))
        if inreg is None:
            continue
        for ev in _BLOCK_EVENTS:
            val = rule.get(ev)
            if not val:
                continue
            if val in regions:                     # region-as-filter gate: build allowed
                gate = _mask(val)                  # only *inside* this region → deny outside it
                if gate is not None:
                    verdict[inreg & ~gate] = 1
                    applied += 1
                continue
            kind = _classify(val, filters)
            if kind == "never":
                verdict[inreg] = 1
            elif kind == "void":
                verdict[inreg & void] = 2          # non-void in region = abstain (no change)
            elif kind == "other":
                verdict[inreg] = 3
            # 'allow' → no change
            applied += 1
    return {"verdict": verdict, "terrain": terrain, "have_y0": have_y0,
            "bbox": bounds, "rules_applied": applied, "map": map_name}


def render(result: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    v = result["verdict"]
    colors = np.array([
        [ 76, 175,  80],   # 0 buildable  green
        [198,  40,  40],   # 1 never       red
        [245, 124,   0],   # 2 void-denied orange
        [251, 192,  45],   # 3 restricted  yellow
    ], dtype=float) / 255.0
    img = colors[v]
    # darken cells that have Y=0 terrain, so void vs terrain is visible
    img[result["terrain"]] *= 0.55

    min_x, min_z, max_x, max_z = result["bbox"]
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(img, origin="lower", extent=[min_x, max_x, min_z, max_z], interpolation="nearest")
    ax.set_title(f"{result['map']} — buildability  ({result['rules_applied']} block rules"
                 f"{'' if result['have_y0'] else ', NO Y=0 layer'})")
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

    result = compute(args.map, args.margin)
    out = args.out or Path(f"/tmp/buildability_{args.map}.png")
    render(result, out)

    v = result["verdict"]
    total = v.size
    names = {0: "buildable", 1: "never", 2: "void-denied", 3: "restricted"}
    print(f"{args.map}: bbox={result['bbox']}, {result['rules_applied']} block rules, "
          f"Y=0 layer={'yes' if result['have_y0'] else 'MISSING'}")
    for k, name in names.items():
        n = int((v == k).sum())
        print(f"  {name:12} {n:8d}  ({100*n/total:5.1f}%)")
    print(f"  → {out}")


if __name__ == "__main__":
    main()
