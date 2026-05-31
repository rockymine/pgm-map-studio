import logging
import os
from pathlib import Path
from typing import Iterator, Optional
import anvil

logger = logging.getLogger('pgm_map_studio')


class RegionReader:
    """Streaming access to chunks in a Minecraft Anvil region directory."""

    def __init__(self, region_dir: str | Path) -> None:
        self.region_dir = Path(region_dir)
        if not self.region_dir.exists():
            raise ValueError(f"Region directory does not exist: {region_dir}")

    def get_region_files(self) -> list[Path]:
        return sorted(self.region_dir.glob("r.*.*.mca"))

    def iter_chunks(self) -> Iterator[tuple[anvil.Chunk, int, int]]:
        """Yield (chunk, chunk_x, chunk_z) for every chunk in every region file."""
        for region_file in self.get_region_files():
            parts = region_file.stem.split('.')
            if len(parts) != 3:
                continue
            try:
                region_x = int(parts[1])
                region_z = int(parts[2])
            except ValueError:
                continue

            try:
                region = anvil.Region.from_file(str(region_file))
            except Exception as e:
                logger.warning(f"Failed to read region {region_file}: {e}")
                continue

            for local_x in range(32):
                for local_z in range(32):
                    try:
                        chunk = region.get_chunk(local_x, local_z)
                        if chunk is not None:
                            yield chunk, region_x * 32 + local_x, region_z * 32 + local_z
                    except Exception:
                        continue

    def get_section(self, chunk: anvil.Chunk, section_y: int) -> Optional[dict]:
        """Return section data dict for the given Y index, or None if absent."""
        try:
            sections = chunk.data.get('Sections', [])
            for section in sections:
                if section.get('Y') != section_y:
                    continue
                blocks = section.get('Blocks')
                data = section.get('Data')
                if blocks is None or data is None:
                    return None
                blocks = bytes(blocks.value) if hasattr(blocks, 'value') else bytes(blocks)
                data = bytes(data.value) if hasattr(data, 'value') else bytes(data)
                result = {'Y': section_y, 'Blocks': blocks, 'Data': data}
                add = section.get('Add')
                if add is not None:
                    result['Add'] = bytes(add.value) if hasattr(add, 'value') else bytes(add)
                return result
        except Exception:
            return None
        return None
