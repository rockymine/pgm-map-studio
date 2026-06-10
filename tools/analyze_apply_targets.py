#!/usr/bin/env python3
"""Corpus analysis: what region *types* do apply rules target, per event?

For every apply rule across all xml_data.json files, resolve its ``region`` to the
geometry type of the referenced region and tabulate event x region-type. Surfaces
combinations that are geometrically odd (e.g. ``enter`` on a single ``block``/``point``).

Usage:
    python tools/analyze_apply_targets.py [root ...]
        (default roots: /tmp/pipeline_out /tmp/publicmaps_out)
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter, defaultdict

EVENTS = ("enter", "leave", "block", "block_place", "block_break",
          "block_physics", "block_place_against", "use", "filter")

# Geometry buckets for readability.
AREA_TYPES = {"rectangle", "cuboid", "cylinder", "circle", "sphere", "half",
              "above", "everywhere", "block-2d"}
POINTY_TYPES = {"block", "point"}            # 0/1-block — odd to "enter"
COMPOUND_TYPES = {"union", "complement", "negative", "intersect"}
TRANSFORM_TYPES = {"mirror", "translate"}


def region_type(region_ref, regions: dict) -> str:
    """Resolve a rule's region reference to a geometry type label."""
    if not region_ref:
        return "(none/global)"
    if region_ref in ("everywhere", "nowhere"):
        return f"builtin:{region_ref}"
    r = regions.get(region_ref)
    if r is None:
        return "(unresolved/inline)"
    return r.get("type", "?")


def main(roots: list[str]) -> None:
    files = [p for root in roots for p in glob.glob(f"{root}/*/xml_data.json")]
    maps = 0
    type_total = Counter()
    event_x_type: dict[str, Counter] = defaultdict(Counter)
    # collect concrete examples of the odd combos
    odd_examples: list[str] = []

    for path in files:
        try:
            d = json.load(open(path))
        except Exception:
            continue
        maps += 1
        regions = d.get("regions", {})
        mname = path.split("/")[-2]
        for rule in d.get("apply_rules", []):
            rtype = region_type(rule.get("region"), regions)
            for ev in EVENTS:
                if rule.get(ev):
                    event_x_type[ev][rtype] += 1
                    type_total[rtype] += 1
                    if ev in ("enter", "use") and rtype in POINTY_TYPES and len(odd_examples) < 20:
                        odd_examples.append(f"{mname}: {ev} on {rtype} region "
                                            f"{rule.get('region')!r}")

    print(f"maps: {maps}   files: {len(files)}\n")

    print("=== region-type distribution across all apply targets ===")
    for t, n in type_total.most_common():
        print(f"  {t:22s} {n}")

    print("\n=== event x region-type ===")
    width = max(len(e) for e in EVENTS)
    for ev in EVENTS:
        c = event_x_type[ev]
        if not c:
            continue
        top = "  ".join(f"{t}:{n}" for t, n in c.most_common(8))
        print(f"  {ev:<{width}} (n={sum(c.values())})\n      {top}")

    print("\n=== geometrically odd: enter/use on a single block/point ===")
    odd = sum(event_x_type[e][t] for e in ("enter", "use") for t in POINTY_TYPES)
    print(f"  count: {odd}")
    for ex in odd_examples:
        print(f"    {ex}")


if __name__ == "__main__":
    roots = sys.argv[1:] or ["/tmp/pipeline_out", "/tmp/publicmaps_out"]
    main(roots)
