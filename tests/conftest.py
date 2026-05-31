import pytest
from pathlib import Path


@pytest.fixture
def tmp_map_repo(tmp_path):
    """A temporary directory shaped like a map repository.

    Layout:
        repo/
          ctw/
            alpha/   region/  map.xml
            beta/    region/           (no xml)
          koth/
            gamma/   region/  map.xml
    """
    for slug, game_mode, with_xml in [
        ('alpha', 'ctw',  True),
        ('beta',  'ctw',  False),
        ('gamma', 'koth', True),
    ]:
        map_dir = tmp_path / game_mode / slug
        (map_dir / 'region').mkdir(parents=True)
        if with_xml:
            (map_dir / 'map.xml').write_text('<map/>')
    return tmp_path
