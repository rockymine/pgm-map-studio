"""Generate / verify the buildability oracle for real maps (C14).

A readable golden of `services.buildability.compute_buildability` on real maps:
the bbox, per-class counts (buildable / never / void_denied / restricted), and
whether the Y=0 layer was present. The full per-column grid is too large to pin;
the counts are the regression signature. Fixtures:
`tests/fixtures/buildability/<map>.json`.

    python tools/gen_buildability_oracle.py            # (re)write
    python tools/gen_buildability_oracle.py --check    # fail if drifted

The three maps exercise the authoring approaches: outback (void filter + positive
build), golden_drought_ii (partial void moats + carved bridging paths), vertex
(region-gate, no void).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))           # tools/
from buildability_preview import run                      # noqa: E402

_MAPS = ["outback_outback_edition", "golden_drought_ii", "vertex"]
_FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "buildability"


def _oracle(map_name: str) -> dict | None:
    try:
        r = run(map_name)
    except SystemExit:
        return None
    return {"map": map_name, "bbox": list(r["bbox"]),
            "has_y0": r["has_y0"], "counts": r["counts"]}


def main() -> None:
    check = "--check" in sys.argv
    _FIXTURES.mkdir(parents=True, exist_ok=True)
    drift = 0
    for m in _MAPS:
        oracle = _oracle(m)
        if oracle is None:
            print(f"  SKIP {m}: not in corpus")
            continue
        path = _FIXTURES / f"{m}.json"
        text = json.dumps(oracle, indent=2) + "\n"
        if check:
            if not path.exists() or path.read_text() != text:
                print(f"  DRIFT {m}: oracle out of date — rerun without --check"); drift += 1
            else:
                print(f"  ok {m}  {oracle['counts']}")
        else:
            path.write_text(text)
            print(f"  wrote {path.name}  {oracle['counts']}")
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
