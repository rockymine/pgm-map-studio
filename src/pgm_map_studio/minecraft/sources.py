"""Map source discovery.

Scans a map repository (e.g. CommunityMaps/, PublicMaps/) and yields
MapSource entries for every valid map folder found.

A valid map folder must contain a region/ subdirectory. map.xml is
optional — its absence signals that a stub needs to be generated later.

Typical layouts handled:

    repo/ctw/map-name/region/      → game_mode='ctw', slug='map-name'
    repo/map-name/region/          → game_mode inferred from repo dir name
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class MapSource:
    slug: str
    path: Path
    has_xml: bool
    game_mode: str


def find_maps(root: Path | str, _game_mode: str | None = None) -> Iterator[MapSource]:
    """Recursively yield MapSource for every valid map folder under root.

    Recurses into subdirectories that are not themselves map folders,
    so works with both flat (root/map/) and grouped (root/game_mode/map/)
    layouts. Does not recurse into a directory once it is identified as a
    map (i.e. map variants in subdirectories are not yielded separately).
    """
    root = Path(root)
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if (entry / 'region').is_dir():
            yield MapSource(
                slug=entry.name,
                path=entry,
                has_xml=(entry / 'map.xml').exists(),
                game_mode=_game_mode or root.name,
            )
        else:
            yield from find_maps(entry, _game_mode=entry.name)
