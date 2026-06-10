"""Corpus round-trip fidelity harness.

Runs the full persistence round-trip over every real ``map.xml`` under one or
more roots and reports fidelity. This is the guardrail for the contract-first
refactor: any change to the parser / serializer / deserializer / xml_writer
should keep this green (modulo the known-bad exclusions).

Two checks per map:

1. JSON idempotence (exact):  ``to_dict(parse) == to_dict(from_dict(to_dict(parse)))``
   — catches any deserializer drift (wools, spawns, regions, filters, rules).
2. XML re-parse (semantic):   ``parse -> json -> MapXml -> to_xml -> parse`` and
   compare key invariants (team ids, wool (team,colour) set, named region ids,
   named filter ids, apply-rule count) — catches xml_writer issues.

Usage
-----
    python tools/roundtrip_check.py                       # both default suites
    python tools/roundtrip_check.py /path/to/maproot ...  # custom roots
    python tools/roundtrip_check.py --verbose             # list every diff

Exit code is non-zero if any non-excluded map fails, so it can gate CI.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pgm_map_studio.pgm import parser, serializer, deserializer, xml_writer

DEFAULT_ROOTS = [
    "/media/sf_repos/CommunityMaps/ctw",
    "/media/sf_repos/PublicMaps/ctw",
]

# Maps excluded for known, documented reasons (not round-trip regressions).
EXCLUSIONS: dict[str, str] = {
    "segment": "malformed source coordinate '5.185.5' (segment/map.xml:79) — see plan A8",
}


def _semantic(m) -> dict:
    """Order-independent invariants that must survive an XML re-parse."""
    return {
        "teams":   sorted(t.id for t in m.teams),
        "wools":   sorted(f"{w.team}/{w.color}" for w in m.wools),
        "regions": sorted(rid for rid in m.regions if "__" not in rid),
        "filters": sorted(fid for fid in m.filters if "__" not in fid),
        "applies": len(m.apply_rules),
        "spawns":  len(m.spawns),
    }


def _diff_keys(a: dict, b: dict) -> list[str]:
    return [k for k in a if a[k] != b.get(k)]


def _canonical(d: dict) -> dict:
    """A copy with derived fields dropped, for idempotence comparison.

    ``bounds_2d`` is a derived parser artifact (contract §4): primitives recompute
    it from their canonical coords on decode, but composites do not carry it through
    the datamodel — and no consumer needs them to. Comparing it would flag a
    derived-only difference, not a contract-meaningful drift.
    """
    out = dict(d)
    out["regions"] = {
        rid: {k: v for k, v in r.items() if k != "bounds_2d"}
        for rid, r in d.get("regions", {}).items()
    }
    return out


def check_map(xml_path: Path) -> tuple[bool, str]:
    """Return (ok, detail). detail is '' on success."""
    try:
        m1 = parser.parse(str(xml_path))
    except Exception as exc:
        return False, f"parse error: {exc}"

    try:
        d1 = serializer.to_dict(m1)
        d2 = serializer.to_dict(deserializer.from_dict(d1))
    except Exception as exc:
        return False, f"json round-trip raised: {exc}"
    c1, c2 = _canonical(d1), _canonical(d2)
    if c1 != c2:
        drift = _diff_keys(c1, c2)
        return False, f"json not idempotent (canonical); drift in: {drift}"

    tmp = None
    try:
        xml2 = xml_writer.to_xml(deserializer.from_dict(d1))
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
            f.write(xml2)
            tmp = f.name
        m3 = parser.parse(tmp)
    except Exception as exc:
        return False, f"xml write/re-parse raised: {exc}"
    finally:
        if tmp:
            os.unlink(tmp)

    diff = _diff_keys(_semantic(m1), _semantic(m3))
    if diff:
        return False, f"xml re-parse semantic drift in: {diff}"
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("roots", nargs="*", default=DEFAULT_ROOTS,
                    help="map root directories (default: CommunityMaps + PublicMaps ctw)")
    ap.add_argument("--verbose", action="store_true", help="print every failure detail")
    args = ap.parse_args()

    xmls: list[Path] = []
    for root in args.roots:
        xmls.extend(sorted(Path(root).glob("*/map.xml")))

    ok = excluded = failed = 0
    failures: list[tuple[str, str]] = []
    for xml_path in xmls:
        slug = xml_path.parent.name
        if slug in EXCLUSIONS:
            excluded += 1
            continue
        passed, detail = check_map(xml_path)
        if passed:
            ok += 1
        else:
            failed += 1
            failures.append((slug, detail))

    print(f"round-trip: {ok} ok, {failed} failed, {excluded} excluded "
          f"({len(xmls)} maps across {len(args.roots)} root(s))")
    if EXCLUSIONS:
        print("excluded:", ", ".join(f"{k} ({v})" for k, v in EXCLUSIONS.items()))
    if failures:
        print(f"\n{failed} failure(s):")
        for slug, detail in (failures if args.verbose else failures[:20]):
            print(f"  {slug}: {detail}")
        if not args.verbose and failed > 20:
            print(f"  ... and {failed - 20} more (use --verbose)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
