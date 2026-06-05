"""Bulk pipeline runner.

Runs the pgm-map-studio pipeline for every map found under a root directory.
Outputs land in <output_root>/<slug>/ with the standard pipeline file layout.
Already-complete outputs are skipped (cached) unless --force is passed.

Usage examples
--------------
# XML step only for all CTW maps (fast — no MCA parsing):
python tools/run_pipeline.py /media/sf_repos/CommunityMaps/ctw /tmp/pipeline_out --xml-only

# Full pipeline, 4 workers:
python tools/run_pipeline.py /media/sf_repos/CommunityMaps/ctw /tmp/pipeline_out --workers 4

# Force re-run XML step only:
python tools/run_pipeline.py /media/sf_repos/CommunityMaps/ctw /tmp/pipeline_out --xml-only --force
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pgm_map_studio.minecraft.sources import MapSource, find_maps
from pgm_map_studio import pipeline


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    slug: str
    ok: bool
    skipped: bool
    duration_s: float
    error: str = ""


# ---------------------------------------------------------------------------
# Per-map runner
# ---------------------------------------------------------------------------

def _run_one(source: MapSource, output_root: Path, xml_only: bool, force: bool) -> RunResult:
    t0 = time.monotonic()
    map_output = output_root / source.slug

    # Fast skip check (no I/O beyond stat):
    if not force:
        need_xml = source.has_xml and not (map_output / 'xml_data.json').exists()
        if xml_only and not need_xml:
            return RunResult(source.slug, ok=True, skipped=True, duration_s=0.0)

    try:
        if xml_only:
            map_output.mkdir(parents=True, exist_ok=True)
            pipeline.run_xml(source, map_output, force=force)
        else:
            pipeline.run(source, output_root, force=force)
        return RunResult(source.slug, ok=True, skipped=False, duration_s=time.monotonic() - t0)
    except Exception as exc:
        return RunResult(source.slug, ok=False, skipped=False,
                         duration_s=time.monotonic() - t0, error=str(exc))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk pgm-map-studio pipeline runner")
    parser.add_argument("maps_root",   help="Root directory containing map folders")
    parser.add_argument("output_root", help="Root directory for pipeline outputs")
    parser.add_argument("--xml-only",  action="store_true",
                        help="Run Step 3 (XML parse) only — skips MCA layout scan")
    parser.add_argument("--force",     action="store_true",
                        help="Re-run even when output files already exist")
    parser.add_argument("--workers",   type=int, default=4,
                        help="Parallel worker threads (default: 4)")
    parser.add_argument("--limit",     type=int, default=0,
                        help="Process at most N maps (0 = all)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show per-map log output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    maps_root   = Path(args.maps_root)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    sources = list(find_maps(maps_root))
    if args.xml_only:
        sources = [s for s in sources if s.has_xml]
    if args.limit:
        sources = sources[:args.limit]

    total = len(sources)
    print(f"Found {total} maps under {maps_root}"
          + (" (xml-only mode)" if args.xml_only else ""))

    results: list[RunResult] = []
    t_start = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_run_one, s, output_root, args.xml_only, args.force): s
            for s in sources
        }
        done = 0
        for fut in as_completed(futures):
            result = fut.result()
            results.append(result)
            done += 1
            if not result.skipped:
                status = "OK" if result.ok else "FAIL"
                timing = f"{result.duration_s:.1f}s"
                err    = f"  {result.error}" if result.error else ""
                print(f"[{done:>4}/{total}] {status} {timing:>6}  {result.slug}{err}")

    elapsed = time.monotonic() - t_start
    ok      = sum(1 for r in results if r.ok and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    failed  = sum(1 for r in results if not r.ok)

    print(f"\nDone in {elapsed:.1f}s — {ok} ran, {skipped} skipped, {failed} failed")

    if failed:
        print("\nFailures:")
        for r in results:
            if not r.ok:
                print(f"  {r.slug}: {r.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
