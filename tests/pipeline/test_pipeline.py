"""Tests for pgm_map_studio.pipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pgm_map_studio.minecraft.sources import MapSource
from pgm_map_studio.pipeline import run, run_layout, run_symmetry, run_xml, PipelineResult
from pgm_map_studio.pipeline.config import (
    MapConfig, load_map_config, save_map_config,
)
from pgm_map_studio.symmetry.datatypes import GlobalSymmetryEntry, SymmetryResult


# ---------------------------------------------------------------------------
# MapConfig
# ---------------------------------------------------------------------------

def test_map_config_defaults():
    cfg = MapConfig()
    assert cfg.exclude_islands == []
    assert cfg.exclude_blocks == []
    assert cfg.scan_layer == 'surface'


def test_map_config_round_trip():
    cfg = MapConfig(exclude_islands=[3, 7], exclude_blocks=[36, 166], scan_layer='y0')
    assert MapConfig.from_dict(cfg.to_dict()) == cfg


def test_map_config_exclude_blocks_in_json(tmp_path):
    cfg = MapConfig(exclude_blocks=[36, 166])
    save_map_config(cfg, tmp_path)
    d = json.loads((tmp_path / 'map_config.json').read_text())
    assert d['exclude_blocks'] == [36, 166]
    loaded = load_map_config(tmp_path)
    assert loaded.exclude_blocks == [36, 166]


def test_save_and_load_map_config(tmp_path):
    cfg = MapConfig(exclude_islands=[2], scan_layer='base')
    save_map_config(cfg, tmp_path)
    assert (tmp_path / 'map_config.json').exists()
    loaded = load_map_config(tmp_path)
    assert loaded.exclude_islands == [2]
    assert loaded.scan_layer == 'base'


def test_load_map_config_missing_returns_defaults(tmp_path):
    cfg = load_map_config(tmp_path)
    assert cfg == MapConfig()


def test_map_config_json_schema(tmp_path):
    save_map_config(MapConfig(), tmp_path)
    d = json.loads((tmp_path / 'map_config.json').read_text())
    assert 'exclude_islands' in d
    assert 'scan_layer' in d


# ---------------------------------------------------------------------------
# run_symmetry — cache behaviour
# ---------------------------------------------------------------------------

def _make_islands_json(tmp_path: Path, n: int = 2) -> None:
    """Write a minimal islands.json with n synthetic symmetric islands."""
    half = 50
    islands = []
    for i in range(n):
        sign = 1 if i % 2 == 0 else -1
        cx, cz = sign * 30, sign * 60
        ext = [
            [cx - half, cz - half], [cx + half, cz - half],
            [cx + half, cz + half], [cx - half, cz + half],
            [cx - half, cz - half],
        ]
        islands.append({
            'id': i + 1,
            'block_count': half * half * 4,
            'bounds': [cx - half, cz - half, cx + half, cz + half],
            'polygon': {'type': 'Polygon', 'coordinates': [ext]},
        })
    (tmp_path / 'islands.json').write_text(json.dumps(islands))


def test_run_symmetry_creates_file(tmp_path):
    _make_islands_json(tmp_path)
    result = run_symmetry(tmp_path)
    assert result is not None
    assert (tmp_path / 'symmetry.json').exists()


def test_run_symmetry_output_schema(tmp_path):
    _make_islands_json(tmp_path)
    run_symmetry(tmp_path)
    d = json.loads((tmp_path / 'symmetry.json').read_text())
    assert 'status' in d
    assert 'modes' in d
    assert 'center' in d
    assert 'primary' in d
    assert 'description' not in d.get('modes', [{}])[0]


def test_run_symmetry_status_unconfirmed(tmp_path):
    _make_islands_json(tmp_path)
    result = run_symmetry(tmp_path)
    assert result.status == 'unconfirmed'


def test_run_symmetry_cached_not_rerun(tmp_path):
    _make_islands_json(tmp_path)
    run_symmetry(tmp_path)
    mtime = (tmp_path / 'symmetry.json').stat().st_mtime
    run_symmetry(tmp_path, force=False)
    assert (tmp_path / 'symmetry.json').stat().st_mtime == mtime


def test_run_symmetry_force_reruns(tmp_path):
    _make_islands_json(tmp_path)
    run_symmetry(tmp_path)
    mtime = (tmp_path / 'symmetry.json').stat().st_mtime
    import time; time.sleep(0.02)
    run_symmetry(tmp_path, force=True)
    assert (tmp_path / 'symmetry.json').stat().st_mtime > mtime


def test_run_symmetry_missing_islands_returns_none(tmp_path):
    result = run_symmetry(tmp_path)
    assert result is None
    assert not (tmp_path / 'symmetry.json').exists()


def test_run_symmetry_exclude_islands(tmp_path):
    _make_islands_json(tmp_path, n=4)
    result_all = run_symmetry(tmp_path)
    (tmp_path / 'symmetry.json').unlink()
    cfg = MapConfig(exclude_islands=[1, 2])
    result_excl = run_symmetry(tmp_path, config=cfg)
    # Both should return valid SymmetryResults; confidence may differ
    assert result_all is not None
    assert result_excl is not None


def test_run_symmetry_loads_from_cache(tmp_path):
    _make_islands_json(tmp_path)
    first = run_symmetry(tmp_path)
    second = run_symmetry(tmp_path, force=False)
    assert second is not None
    assert second.status == first.status
    assert len(second.modes) == len(first.modes)


# ---------------------------------------------------------------------------
# run_xml — cache and skip behaviour
# ---------------------------------------------------------------------------

TUMBLEWEED = Path('/media/sf_repos/CommunityMaps/ctw/tumbleweed/map.xml')


def _make_source(tmp_path: Path, has_xml: bool = True) -> MapSource:
    map_dir = tmp_path / 'mymap'
    map_dir.mkdir()
    (map_dir / 'region').mkdir()
    if has_xml:
        (map_dir / 'map.xml').write_text(
            '<map proto="1.5.0">'
            '<name>X</name><version>1.0</version><objective>X</objective>'
            '<teams><team id="r" color="dark red" max="8">R</team></teams>'
            '</map>'
        )
    return MapSource(slug='mymap', path=map_dir, has_xml=has_xml, game_mode='ctw')


def test_run_xml_no_map_xml_returns_none(tmp_path):
    source = _make_source(tmp_path, has_xml=False)
    result = run_xml(source, tmp_path / 'mymap')
    assert result is None
    assert not (tmp_path / 'mymap' / 'xml_data.json').exists()


def test_run_xml_creates_file(tmp_path):
    source = _make_source(tmp_path)
    out = tmp_path / 'mymap'
    result = run_xml(source, out)
    assert result is not None
    assert (out / 'xml_data.json').exists()


def test_run_xml_output_schema(tmp_path):
    source = _make_source(tmp_path)
    out = tmp_path / 'mymap'
    run_xml(source, out)
    d = json.loads((out / 'xml_data.json').read_text())
    for key in ('name', 'teams', 'regions', 'filters', 'apply_rules'):
        assert key in d
    assert 'region_categories' not in d


def test_run_xml_cached_not_rerun(tmp_path):
    source = _make_source(tmp_path)
    out = tmp_path / 'mymap'
    run_xml(source, out)
    mtime = (out / 'xml_data.json').stat().st_mtime
    run_xml(source, out, force=False)
    assert (out / 'xml_data.json').stat().st_mtime == mtime


def test_run_xml_force_reruns(tmp_path):
    source = _make_source(tmp_path)
    out = tmp_path / 'mymap'
    run_xml(source, out)
    mtime = (out / 'xml_data.json').stat().st_mtime
    import time; time.sleep(0.02)
    run_xml(source, out, force=True)
    assert (out / 'xml_data.json').stat().st_mtime > mtime


# ---------------------------------------------------------------------------
# map_config.json written on first run
# ---------------------------------------------------------------------------

def test_run_creates_map_config(tmp_path):
    source = _make_source(tmp_path)
    out = tmp_path

    # Patch layout step since we have no region files
    with patch('pgm_map_studio.pipeline._layout_pipeline.run') as mock_layout:
        from pgm_map_studio.layout.datatypes import MapLayout
        mock_layout.return_value = MapLayout(islands=[], bounds=(0, 0, 0, 0))

        run(source, out)

    assert (out / 'mymap' / 'map_config.json').exists()
    d = json.loads((out / 'mymap' / 'map_config.json').read_text())
    assert d['scan_layer'] == 'surface'
    assert d['exclude_islands'] == []


def test_run_layout_passes_exclude_blocks_to_scan_config(tmp_path):
    source = _make_source(tmp_path)
    out = tmp_path
    map_out = out / 'mymap'
    map_out.mkdir(parents=True, exist_ok=True)
    save_map_config(MapConfig(exclude_blocks=[36, 166]), map_out)

    captured = []

    with patch('pgm_map_studio.pipeline._layout_pipeline.run') as mock_layout:
        from pgm_map_studio.layout.datatypes import MapLayout

        def capture(source, output_dir, config, force):
            captured.append(config)
            return MapLayout(islands=[], bounds=(0, 0, 0, 0))

        mock_layout.side_effect = capture
        run(source, out)

    assert set(captured[0].exclude_ids) == {36, 166}


def test_run_respects_existing_map_config(tmp_path):
    source = _make_source(tmp_path)
    out = tmp_path
    map_out = out / 'mymap'
    map_out.mkdir(parents=True, exist_ok=True)
    save_map_config(MapConfig(exclude_islands=[5], scan_layer='y0'), map_out)

    captured_configs = []

    with patch('pgm_map_studio.pipeline._layout_pipeline.run') as mock_layout:
        from pgm_map_studio.layout.datatypes import MapLayout
        mock_layout.return_value = MapLayout(islands=[], bounds=(0, 0, 0, 0))

        def capture_scan_config(source, output_dir, config, force):
            captured_configs.append(config)
            return MapLayout(islands=[], bounds=(0, 0, 0, 0))

        mock_layout.side_effect = capture_scan_config
        run(source, out)

    assert captured_configs[0].layer == 'y0'


# ---------------------------------------------------------------------------
# PipelineResult fields
# ---------------------------------------------------------------------------

def test_pipeline_result_xml_ran_false_when_no_xml(tmp_path):
    source = _make_source(tmp_path, has_xml=False)

    with patch('pgm_map_studio.pipeline._layout_pipeline.run') as mock_layout:
        from pgm_map_studio.layout.datatypes import MapLayout
        mock_layout.return_value = MapLayout(islands=[], bounds=(0, 0, 0, 0))
        result = run(source, tmp_path)

    assert result.xml_ran is False
    assert result.xml_data is None


def test_pipeline_result_islands_count(tmp_path):
    source = _make_source(tmp_path)
    _make_islands_json(tmp_path / 'mymap', n=3)

    with patch('pgm_map_studio.pipeline._layout_pipeline.run') as mock_layout:
        from pgm_map_studio.layout.datatypes import Island, MapLayout
        from shapely.geometry import box
        fake_islands = [
            Island(id=i, polygon=box(0, 0, 10, 10), bounds=(0, 0, 10, 10), block_count=100)
            for i in range(1, 4)
        ]
        mock_layout.return_value = MapLayout(islands=fake_islands, bounds=(0, 0, 100, 100))
        result = run(source, tmp_path)

    assert result.islands_count == 3


# ---------------------------------------------------------------------------
# Real map integration tests
# ---------------------------------------------------------------------------

TUMBLEWEED_SRC = Path('/media/sf_repos/CommunityMaps/ctw/tumbleweed')
OUTBACK_SRC    = Path('/media/sf_repos/CommunityMaps/ctw/outback_outback_edition')


@pytest.mark.skipif(not TUMBLEWEED_SRC.exists(), reason="Tumbleweed not available")
def test_full_pipeline_tumbleweed(tmp_path):
    from pgm_map_studio.minecraft.sources import MapSource
    source = MapSource(
        slug='tumbleweed', path=TUMBLEWEED_SRC,
        has_xml=True, game_mode='ctw',
    )
    result = run(source, tmp_path)

    # All three steps should have run
    assert result.layout_ran
    assert result.symmetry_ran
    assert result.xml_ran

    out = tmp_path / 'tumbleweed'
    # All output files present
    for f in ('layer.parquet', 'islands.json', 'symmetry.json',
              'xml_data.json', 'map_config.json'):
        assert (out / f).exists(), f"Missing: {f}"

    # Symmetry correct
    assert result.symmetry is not None
    assert result.symmetry.primary is not None
    assert result.symmetry.primary['type'] == 'rot_180'

    # XML correct
    xml = json.loads((out / 'xml_data.json').read_text())
    assert xml['name'] == 'Tumbleweed'
    assert 'region_categories' not in xml

    # Islands detected
    assert result.islands_count > 0


@pytest.mark.skipif(not TUMBLEWEED_SRC.exists(), reason="Tumbleweed not available")
def test_pipeline_cache_skips_all_steps(tmp_path):
    from pgm_map_studio.minecraft.sources import MapSource
    source = MapSource(
        slug='tumbleweed', path=TUMBLEWEED_SRC,
        has_xml=True, game_mode='ctw',
    )
    run(source, tmp_path)

    # Second run should skip all steps
    result2 = run(source, tmp_path, force=False)
    assert not result2.layout_ran
    assert not result2.symmetry_ran
    assert not result2.xml_ran


@pytest.mark.skipif(not TUMBLEWEED_SRC.exists(), reason="Tumbleweed not available")
def test_force_symmetry_only(tmp_path):
    from pgm_map_studio.minecraft.sources import MapSource
    source = MapSource(
        slug='tumbleweed', path=TUMBLEWEED_SRC,
        has_xml=True, game_mode='ctw',
    )
    run(source, tmp_path)
    sym_mtime = (tmp_path / 'tumbleweed' / 'symmetry.json').stat().st_mtime
    xml_mtime  = (tmp_path / 'tumbleweed' / 'xml_data.json').stat().st_mtime

    import time; time.sleep(0.05)
    run(source, tmp_path, force_symmetry=True)

    assert (tmp_path / 'tumbleweed' / 'symmetry.json').stat().st_mtime > sym_mtime
    assert (tmp_path / 'tumbleweed' / 'xml_data.json').stat().st_mtime == xml_mtime
