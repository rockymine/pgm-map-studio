"""Generate / verify the wool-source + availability oracle (C12).

A readable golden of `services.wool_sources` on real maps: the whole-map source
summary (colour → total / source_types / repeatable), the per-wool availability
(obtainable / severity), and the suggestions. Fixtures:
`tests/fixtures/wool_sources/<map>.json`.

    python tools/gen_wool_oracle.py            # (re)write
    python tools/gen_wool_oracle.py --check    # fail if drifted

Maps chosen to exercise all three source types: outback (wool blocks),
icecream_sandwiched_ii (wool in chests), curly_wools_ix (a wool spawner — and a
red wool that is NOT obtainable → an availability error).
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from pgm_map_studio.studio.services.wool_sources import (  # noqa: E402
    check_availability, load_wool_sources, suggest_wools, summarize_sources)

_MAPS = ["outback_outback_edition", "icecream_sandwiched_ii", "curly_wools_ix"]
_FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures" / "wool_sources"


def _oracle(map_name: str) -> dict | None:
    hits = glob.glob(f"/tmp/pgm-studio-output/{map_name}/xml_data.json")
    if not hits:
        return None
    out_dir = Path(hits[0]).parent
    data = json.loads((out_dir / "xml_data.json").read_text())
    sources, have = load_wool_sources(out_dir)
    return {
        "map": map_name,
        "have_layers": have,
        "sources": [{"color": e["color"], "total": e["total"],
                     "source_types": e["source_types"], "repeatable": e["repeatable"]}
                    for e in summarize_sources(sources)],
        "availability": [{"color": a["color"], "obtainable": a["obtainable"],
                          "severity": a["severity"]} for a in check_availability(data, sources)],
        "suggestions": [{"color": s["color"], "source_types": s["source_types"]}
                        for s in suggest_wools(data, sources)],
    }


def main() -> None:
    check = "--check" in sys.argv
    _FIXTURES.mkdir(parents=True, exist_ok=True)
    drift = 0
    for m in _MAPS:
        oracle = _oracle(m)
        if oracle is None:
            print(f"  SKIP {m}: not in corpus"); continue
        path = _FIXTURES / f"{m}.json"
        text = json.dumps(oracle, indent=2) + "\n"
        if check:
            if not path.exists() or path.read_text() != text:
                print(f"  DRIFT {m}: rerun without --check"); drift += 1
            else:
                print(f"  ok {m}  ({len(oracle['sources'])} colours, "
                      f"{sum(1 for a in oracle['availability'] if a['severity']=='error')} errors)")
        else:
            path.write_text(text)
            print(f"  wrote {path.name}  ({len(oracle['sources'])} colours)")
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
