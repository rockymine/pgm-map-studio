"""Private scan helpers shared by layers.py and features.py."""

from typing import Iterator
import numpy as np


def _iter_chunk_sections(chunk) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
    """Yield (section_y, blocks_3d, data_3d) for every section in chunk.

    blocks_3d — (16, 16, 16) uint16, axis order [y, z, x], block IDs.
    data_3d   — (16, 16, 16) uint8,  axis order [y, z, x], damage nibbles.
    Sections are yielded in ascending Y order; malformed sections are skipped.
    """
    try:
        sections_nbt = chunk.data.get('Sections', [])
    except Exception:
        return

    parsed: list[tuple[int, np.ndarray, np.ndarray]] = []
    for sec in sections_nbt:
        try:
            y_raw = sec.get('Y')
            blocks_raw = sec.get('Blocks')
            data_raw = sec.get('Data')
            if y_raw is None or blocks_raw is None or data_raw is None:
                continue

            y_val: int = y_raw.value if hasattr(y_raw, 'value') else int(y_raw)
            blocks_bytes = bytes(blocks_raw.value) if hasattr(blocks_raw, 'value') else bytes(blocks_raw)
            data_bytes = bytes(data_raw.value) if hasattr(data_raw, 'value') else bytes(data_raw)
            if len(blocks_bytes) != 4096 or len(data_bytes) != 2048:
                continue

            blocks = np.frombuffer(blocks_bytes, dtype=np.uint8).astype(np.uint16)

            add_raw = sec.get('Add')
            if add_raw is not None:
                add_bytes = bytes(add_raw.value) if hasattr(add_raw, 'value') else bytes(add_raw)
                if len(add_bytes) == 2048:
                    add_packed = np.frombuffer(add_bytes, dtype=np.uint8)
                    add_nibbles = np.empty(4096, dtype=np.uint16)
                    add_nibbles[0::2] = add_packed & 0x0F
                    add_nibbles[1::2] = (add_packed >> 4) & 0x0F
                    blocks |= (add_nibbles << 8)

            data_packed = np.frombuffer(data_bytes, dtype=np.uint8)
            data_nibbles = np.empty(4096, dtype=np.uint8)
            data_nibbles[0::2] = data_packed & 0x0F
            data_nibbles[1::2] = (data_packed >> 4) & 0x0F

            parsed.append((y_val, blocks.reshape(16, 16, 16), data_nibbles.reshape(16, 16, 16)))
        except Exception:
            continue

    for item in sorted(parsed, key=lambda t: t[0]):
        yield item


def _build_full_blocks(chunk) -> np.ndarray:
    """Return a (256, 16, 16) uint16 block array populated from all sections."""
    full = np.zeros((256, 16, 16), dtype=np.uint16)
    for section_y, blocks_3d, _ in _iter_chunk_sections(chunk):
        y_start = section_y * 16
        if 0 <= y_start < 256:
            full[y_start:y_start + 16] = blocks_3d
    return full
