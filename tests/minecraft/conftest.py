import pytest
from pathlib import Path


@pytest.fixture
def empty_region_dir(tmp_path):
    """A region directory that exists but contains no .mca files."""
    region = tmp_path / 'region'
    region.mkdir()
    return region


@pytest.fixture
def region_dir_with_non_mca(tmp_path):
    """A region directory containing only non-.mca files."""
    region = tmp_path / 'region'
    region.mkdir()
    (region / 'r.0.0.mcr').write_bytes(b'')
    (region / 'readme.txt').write_text('not a region file')
    return region
