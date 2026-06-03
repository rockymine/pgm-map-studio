"""Three-step map analysis pipeline.

    Step 1 — Layout   (independent):  region scan → layer.parquet, islands.json, …
    Step 2 — Symmetry (needs Step 1): island geometry → symmetry.json
    Step 3 — XML      (independent):  map.xml → xml_data.json

Each step is cached: if its output file(s) already exist and force=False the
step is skipped.  Steps 2 and 3 can be individually re-run without repeating
the full scan (pass force_symmetry=True or force_xml=True).

Per-map configuration is read from {output_dir}/map_config.json (created with
defaults on the first run).  The most important field is exclude_islands, which
lets the user mark non-playable observer islands so they do not distort the
symmetry result.

Public API
----------
run(source, output_dir, ...) -> PipelineResult
run_layout(source, output_dir, config, force) -> list[Island]
run_symmetry(output_dir, config, force) -> SymmetryResult | None
run_xml(source, output_dir, force) -> MapXml | None
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pgm_map_studio.minecraft.sources import MapSource
from pgm_map_studio.layout.config import ScanConfig
from pgm_map_studio.layout.datatypes import Island
import pgm_map_studio.layout.pipeline as _layout_pipeline

from pgm_map_studio.symmetry.detection import detect_from_data
from pgm_map_studio.symmetry.datatypes import GlobalSymmetryEntry, SymmetryResult
from pgm_map_studio.symmetry.serializer import save as _save_symmetry

from pgm_map_studio.pgm.parser import parse as _parse_xml
from pgm_map_studio.pgm.datatypes import MapXml
from pgm_map_studio.pgm.serializer import save as _save_xml_data

from .config import MapConfig, load_map_config, save_map_config

logger = logging.getLogger('pgm_map_studio')


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """Summary of a pipeline run."""
    map_slug: str
    output_dir: Path
    layout_ran: bool
    symmetry_ran: bool
    xml_ran: bool
    islands_count: int
    symmetry: Optional[SymmetryResult]
    xml_data: Optional[MapXml]


# ---------------------------------------------------------------------------
# Public API — full pipeline
# ---------------------------------------------------------------------------

def run(
    source: MapSource,
    output_dir: Path,
    force: bool = False,
    force_layout: bool = False,
    force_symmetry: bool = False,
    force_xml: bool = False,
) -> PipelineResult:
    """Run the full three-step pipeline for one map.

    Args:
        source:          MapSource from find_maps().
        output_dir:      Root output directory; per-map dir is output_dir/source.slug.
        force:           Re-run all steps (overrides individual flags).
        force_layout:    Re-run Step 1 even if outputs exist.
        force_symmetry:  Re-run Step 2 even if symmetry.json exists.
        force_xml:       Re-run Step 3 even if xml_data.json exists.
    """
    map_output = Path(output_dir) / source.slug
    map_output.mkdir(parents=True, exist_ok=True)

    config = load_map_config(map_output)
    if not (map_output / 'map_config.json').exists():
        save_map_config(config, map_output)

    do_layout   = force or force_layout
    do_symmetry = force or force_symmetry
    do_xml      = force or force_xml

    # Capture pre-run cache state to determine what actually ran
    had_islands   = (map_output / 'islands.json').exists()
    had_symmetry  = (map_output / 'symmetry.json').exists()
    had_xml       = (map_output / 'xml_data.json').exists()

    islands    = run_layout(source, map_output, config, force=do_layout)
    sym_result = run_symmetry(map_output, config, force=do_symmetry)
    xml_data   = run_xml(source, map_output, force=do_xml)

    return PipelineResult(
        map_slug=source.slug,
        output_dir=map_output,
        layout_ran=do_layout or not had_islands,
        symmetry_ran=do_symmetry or not had_symmetry,
        xml_ran=source.has_xml and (do_xml or not had_xml),
        islands_count=len(islands),
        symmetry=sym_result,
        xml_data=xml_data,
    )


# ---------------------------------------------------------------------------
# Individual steps
# ---------------------------------------------------------------------------

def run_layout(
    source: MapSource,
    output_dir: Path,
    config: Optional[MapConfig] = None,
    force: bool = False,
) -> list[Island]:
    """Step 1 — Layout: region scan → parquet files + islands.json."""
    cfg = config or MapConfig()
    scan_cfg = ScanConfig(layer=cfg.scan_layer, exclude_ids=list(cfg.exclude_blocks))
    logger.info(f"[{source.slug}] Step 1: Layout (layer={cfg.scan_layer}, exclude_blocks={cfg.exclude_blocks})")
    layout = _layout_pipeline.run(source, output_dir, config=scan_cfg, force=force)
    return layout.islands


def run_symmetry(
    output_dir: Path,
    config: Optional[MapConfig] = None,
    force: bool = False,
) -> Optional[SymmetryResult]:
    """Step 2 — Symmetry: islands.json → symmetry.json.

    Returns None if islands.json is missing.
    Loads from cache (symmetry.json) when force=False and file exists.
    """
    islands_path = Path(output_dir) / 'islands.json'
    if not islands_path.exists():
        logger.warning(f"  Symmetry skipped: islands.json not found in {output_dir}")
        return None

    sym_path = Path(output_dir) / 'symmetry.json'
    if sym_path.exists() and not force:
        logger.debug(f"  symmetry.json exists, loading from cache")
        return _load_symmetry_result(sym_path)

    exclude = list(config.exclude_islands) if config else []
    logger.info(f"  Step 2: Symmetry (exclude_islands={exclude})")
    islands_data = json.loads(islands_path.read_text())
    result = detect_from_data(islands_data, exclude_islands=exclude)
    _save_symmetry(result, sym_path)
    logger.info(f"  Saved symmetry.json  primary={result.primary}")
    return result


def run_xml(
    source: MapSource,
    output_dir: Path,
    force: bool = False,
) -> Optional[MapXml]:
    """Step 3 — XML: map.xml → xml_data.json.

    Skipped (returns None) when no map.xml exists.
    Returns None (from cache) when xml_data.json exists and force=False;
    the caller reads the file directly if needed.
    """
    if not source.has_xml:
        logger.debug(f"  XML skipped: no map.xml for {source.slug}")
        return None

    xml_path = Path(output_dir) / 'xml_data.json'
    if xml_path.exists() and not force:
        logger.debug(f"  xml_data.json exists, skipping")
        return None

    map_xml_file = source.path / 'map.xml'
    logger.info(f"  Step 3: XML  ({map_xml_file})")
    xml_data = _parse_xml(str(map_xml_file))
    _save_xml_data(xml_data, xml_path)
    logger.info(
        f"  Saved xml_data.json  "
        f"({len(xml_data.regions)} regions, {len(xml_data.filters)} filters)"
    )
    return xml_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_symmetry_result(path: Path) -> SymmetryResult:
    """Reconstruct a SymmetryResult from a saved symmetry.json."""
    d = json.loads(path.read_text())
    return SymmetryResult(
        status=d.get('status', 'unconfirmed'),
        modes=[
            GlobalSymmetryEntry(
                type=e['type'],
                detected=e['detected'],
                confidence=e['confidence'],
            )
            for e in d.get('modes', [])
        ],
        center=d.get('center', {'center_x': 0.0, 'center_z': 0.0}),
    )
