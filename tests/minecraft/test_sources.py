import pytest
from pathlib import Path
from pgm_map_studio.minecraft.sources import find_maps, MapSource


def test_finds_maps_in_grouped_layout(tmp_map_repo):
    sources = list(find_maps(tmp_map_repo))
    slugs = {s.slug for s in sources}
    assert slugs == {'alpha', 'beta', 'gamma'}


def test_infers_game_mode_from_parent(tmp_map_repo):
    sources = {s.slug: s for s in find_maps(tmp_map_repo)}
    assert sources['alpha'].game_mode == 'ctw'
    assert sources['beta'].game_mode == 'ctw'
    assert sources['gamma'].game_mode == 'koth'


def test_detects_has_xml(tmp_map_repo):
    sources = {s.slug: s for s in find_maps(tmp_map_repo)}
    assert sources['alpha'].has_xml is True
    assert sources['beta'].has_xml is False
    assert sources['gamma'].has_xml is True


def test_path_points_to_map_folder(tmp_map_repo):
    sources = {s.slug: s for s in find_maps(tmp_map_repo)}
    assert sources['alpha'].path == tmp_map_repo / 'ctw' / 'alpha'


def test_ignores_directories_without_region(tmp_path):
    (tmp_path / 'not-a-map').mkdir()
    (tmp_path / 'not-a-map' / 'some_file.txt').write_text('x')
    sources = list(find_maps(tmp_path))
    assert sources == []


def test_flat_layout_uses_root_name_as_game_mode(tmp_path):
    map_dir = tmp_path / 'my-map'
    (map_dir / 'region').mkdir(parents=True)
    sources = list(find_maps(tmp_path))
    assert len(sources) == 1
    assert sources[0].game_mode == tmp_path.name


def test_returns_sorted_by_slug(tmp_map_repo):
    sources = list(find_maps(tmp_map_repo))
    slugs = [s.slug for s in sources]
    assert slugs == sorted(slugs)


def test_map_source_is_frozen():
    src = MapSource(slug='test', path=Path('/tmp'), has_xml=False, game_mode='ctw')
    with pytest.raises(Exception):
        src.slug = 'other'
