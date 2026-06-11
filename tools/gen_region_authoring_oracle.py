"""Generate / verify the region-authoring split oracle for real maps.

A readable golden file of `region_encoder.encode_region_authoring` (B4a): for a
map, the **primitives** vs **composed** split, each node trimmed to the fields
that define the *authoring view* — `id`, `type`, `category`, composed
`member_ids`, and the apply-rule `wiring` (`event`→`value`). Geometry
(coords/polygon/bounds) is omitted: it's noise for reading the split and is
covered by other tests.

Oracle lives in `tests/fixtures/region_authoring/<map>.json`; the corpus it reads
(`/tmp/pipeline_out` + `/tmp/publicmaps_out`) is the curated CTW set.

    python tools/gen_region_authoring_oracle.py            # (re)write the oracles
    python tools/gen_region_authoring_oracle.py --check    # fail if they've drifted

See docs/contracts/region-authoring.md.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pgm_map_studio.studio.services.region_categorizer import categorize_regions
from pgm_map_studio.studio.services.region_encoder import encode_region_authoring

# Maps to pin — picked to exercise the model: outback (full spawn/wool/build wiring
# + the all-vs-team wool grouping) and annealing_iv (the void block-break allowlist).
_MAPS = ["outback_outback_edition", "annealing_iv"]
_FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "region_authoring"


def _find(map_name: str) -> Path | None:
    hits = glob.glob(f"/tmp/pipeline_out/{map_name}/xml_data.json") + \
           glob.glob(f"/tmp/publicmaps_out/{map_name}/xml_data.json")
    return Path(hits[0]) if hits else None


def _node(n: dict, composed: bool) -> dict:
    out = {"id": n["id"], "type": n["type"], "category": n["category"]}
    if composed:
        out["member_ids"] = n["member_ids"]
    out["wiring"] = [{"event": w["event"], "value": w["value"]} for w in n["wiring"]]
    return out


def _oracle(map_name: str) -> dict | None:
    p = _find(map_name)
    if p is None:
        return None
    d = json.loads(p.read_text())
    split = encode_region_authoring(
        d.get("regions", {}), categorize_regions(d), d.get("apply_rules", []), None)
    return {
        "map": map_name,
        "counts": {"primitives": len(split["primitives"]), "composed": len(split["composed"])},
        "primitives": [_node(n, False) for n in split["primitives"]],
        "composed":   [_node(n, True) for n in split["composed"]],
    }


def main() -> None:
    check = "--check" in sys.argv
    _FIXTURES.mkdir(parents=True, exist_ok=True)
    drift = missing = 0
    for m in _MAPS:
        oracle = _oracle(m)
        if oracle is None:
            print(f"  SKIP {m}: not in corpus"); missing += 1; continue
        path = _FIXTURES / f"{m}.json"
        text = json.dumps(oracle, indent=2) + "\n"
        if check:
            if not path.exists() or path.read_text() != text:
                print(f"  DRIFT {m}: oracle out of date — rerun without --check"); drift += 1
            else:
                print(f"  ok {m}  (primitives={oracle['counts']['primitives']}, "
                      f"composed={oracle['counts']['composed']})")
        else:
            path.write_text(text)
            print(f"  wrote {path.relative_to(_FIXTURES.parent.parent.parent)}  "
                  f"(primitives={oracle['counts']['primitives']}, composed={oracle['counts']['composed']})")
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
