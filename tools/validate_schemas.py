"""Validate every corpus xml_data.json against the persisted MapProject schema.

Like tools/roundtrip_check.py — an integration check over the real 350-map
corpus (not a hermetic unit test), proving the pydantic persisted contract
matches what the pipeline actually writes.

Run: python tools/validate_schemas.py
"""
from __future__ import annotations

import glob
import json
import sys

from pydantic import ValidationError

from pgm_map_studio.schemas.persisted import MapProject

_ROOTS = ["/tmp/pipeline_out", "/tmp/publicmaps_out"]


def main() -> None:
    files = sorted(f for root in _ROOTS for f in glob.glob(f"{root}/*/xml_data.json"))
    ok = fail = 0
    failures = []
    for f in files:
        try:
            MapProject.model_validate(json.load(open(f)))
            ok += 1
        except ValidationError as exc:
            fail += 1
            failures.append((f.split("/")[-2], exc.errors()[:3]))
    print(f"schema validation: {ok} ok, {fail} fail of {len(files)} maps")
    for name, errs in failures[:10]:
        print(f"  FAIL {name}: {errs}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
