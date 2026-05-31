import pytest
from pathlib import Path
from pgm_map_studio.minecraft.region_reader import RegionReader


def test_raises_on_missing_directory(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        RegionReader(tmp_path / 'nonexistent')


def test_accepts_path_object(empty_region_dir):
    reader = RegionReader(empty_region_dir)
    assert reader.region_dir == empty_region_dir


def test_accepts_string_path(empty_region_dir):
    reader = RegionReader(str(empty_region_dir))
    assert reader.region_dir == empty_region_dir


def test_get_region_files_empty(empty_region_dir):
    reader = RegionReader(empty_region_dir)
    assert reader.get_region_files() == []


def test_get_region_files_ignores_non_mca(region_dir_with_non_mca):
    reader = RegionReader(region_dir_with_non_mca)
    assert reader.get_region_files() == []


def test_get_region_files_finds_mca(tmp_path):
    region = tmp_path / 'region'
    region.mkdir()
    (region / 'r.0.0.mca').write_bytes(b'')
    (region / 'r.-1.2.mca').write_bytes(b'')
    (region / 'r.0.0.mcr').write_bytes(b'')
    reader = RegionReader(region)
    names = [f.name for f in reader.get_region_files()]
    assert 'r.0.0.mca' in names
    assert 'r.-1.2.mca' in names
    assert 'r.0.0.mcr' not in names


def test_get_region_files_returns_sorted(tmp_path):
    region = tmp_path / 'region'
    region.mkdir()
    for name in ['r.1.0.mca', 'r.0.1.mca', 'r.0.0.mca']:
        (region / name).write_bytes(b'')
    reader = RegionReader(region)
    files = reader.get_region_files()
    assert files == sorted(files)


def test_iter_chunks_empty_dir_yields_nothing(empty_region_dir):
    reader = RegionReader(empty_region_dir)
    assert list(reader.iter_chunks()) == []
