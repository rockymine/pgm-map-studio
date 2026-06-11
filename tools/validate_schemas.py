"""Validate the persisted contract against real on-disk data.

Like tools/roundtrip_check.py — an integration check over the real corpus (not
a hermetic unit test), proving the pydantic contract matches what gets written:
- every map's `xml_data.json` against `MapProject` (the 350-map corpus);
- any local sketch session's `sketch.json` against `SketchProject` (best-effort —
  sketches are user-local under ~/.config, so this is empty on a fresh machine).

Run: python tools/validate_schemas.py
"""
from __future__ import annotations

import glob
import json
import sys

from pydantic import BaseModel, ValidationError

from pgm_map_studio.schemas.persisted import MapProject
from pgm_map_studio.schemas.sketch import SketchProject
from pgm_map_studio.studio.services.sketch_data import SKETCHES_DIR

_MAP_ROOTS = ["/tmp/pipeline_out", "/tmp/publicmaps_out"]


def _validate(files: list[str], model: type[BaseModel], label: str) -> int:
    ok = fail = 0
    failures = []
    for f in files:
        try:
            model.model_validate(json.load(open(f)))
            ok += 1
        except ValidationError as exc:
            fail += 1
            failures.append((f.split("/")[-2], exc.errors()[:3]))
    print(f"{label}: {ok} ok, {fail} fail of {len(files)}")
    for name, errs in failures[:10]:
        print(f"  FAIL {name}: {errs}")
    return fail


def main() -> None:
    maps = sorted(f for root in _MAP_ROOTS for f in glob.glob(f"{root}/*/xml_data.json"))
    sketches = sorted(glob.glob(str(SKETCHES_DIR / "*" / "sketch.json")))

    fail = _validate(maps, MapProject, "xml_data.json → MapProject")
    if sketches:
        fail += _validate(sketches, SketchProject, "sketch.json → SketchProject")
    else:
        print("sketch.json → SketchProject: no local sketches to check")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
