"""Layer extractors — scan the full map and return a 2D spatial grid.

Each extractor produces one row per column (or per matching block in a
specific layer). They answer "what does the terrain/surface look like?"
and are the first step in the geometry pipeline.

- Y0Extractor       — non-air blocks at world y=0
- SurfaceExtractor  — highest qualifying block per column (top-down)
- BedrockExtractor  — lowest bedrock block per column
- BaseExtractor     — lowest non-excluded non-air block per column
- SegmentsExtractor — all contiguous solid Y-ranges per column
"""

import logging
import numpy as np
import pandas as pd

from .region_reader import RegionReader
from ._helpers import _iter_chunk_sections, _build_full_blocks

logger = logging.getLogger('pgm_map_studio')

# Non-solid decorative block IDs skipped when skip_non_solid=True.
# Water (8, 9) is intentionally omitted — it forms walkable surfaces in CTW.
NON_SOLID_BLOCK_IDS: frozenset[int] = frozenset({
    6, 31, 32, 37, 38, 39, 40, 50, 55, 59, 63, 65, 66, 69, 70, 71, 72,
    75, 76, 77, 78, 83, 104, 105, 106, 115, 141, 142, 143, 147, 148, 166,
})

# Block 36 (PISTON_MOVING_PIECE) is used by many CTW maps as an invisible
# build-region boundary marker — excluded from segment extraction too.
_SEGMENTS_EXTRA_EXCLUDE: frozenset[int] = frozenset({36})


class Y0Extractor:
    """Non-air blocks at world y=0.

    Returns DataFrame: world_x, world_z, block_id, block_data
    """

    def __init__(self, region_reader: RegionReader) -> None:
        self.reader = region_reader

    def extract(self) -> pd.DataFrame:
        all_wx, all_wz, all_id, all_dt = [], [], [], []
        for chunk, chunk_x, chunk_z in self.reader.iter_chunks():
            for section_y, blocks_3d, data_3d in _iter_chunk_sections(chunk):
                if section_y != 0:
                    continue
                zz, xx = np.where(blocks_3d[0] != 0)
                if len(zz):
                    all_wx.append((chunk_x * 16 + xx).astype(np.int32))
                    all_wz.append((chunk_z * 16 + zz).astype(np.int32))
                    all_id.append(blocks_3d[0][zz, xx].astype(np.uint16))
                    all_dt.append(data_3d[0][zz, xx])
                break
        if not all_wx:
            return pd.DataFrame(columns=['world_x', 'world_z', 'block_id', 'block_data'])
        return pd.DataFrame({
            'world_x': np.concatenate(all_wx),
            'world_z': np.concatenate(all_wz),
            'block_id': np.concatenate(all_id),
            'block_data': np.concatenate(all_dt),
        })


class SurfaceExtractor:
    """Highest non-excluded non-air block per column (top-down scan).

    Optionally caps at max_build_height to ignore structures above the
    playable ceiling (observer islands, decorative birds, etc.).

    Returns DataFrame: world_x, world_z, y, block_id, block_data
    """

    def __init__(
        self,
        region_reader: RegionReader,
        exclude_ids: set[int] | None = None,
        skip_non_solid: bool = False,
        max_build_height: int | None = None,
    ) -> None:
        self.reader = region_reader
        self._exclude: set[int] = set(exclude_ids) if exclude_ids else set()
        if skip_non_solid:
            self._exclude |= NON_SOLID_BLOCK_IDS
        self._max_y = max_build_height

    def extract(self) -> pd.DataFrame:
        all_wx, all_wz, all_y, all_id, all_dt = [], [], [], [], []

        for chunk, chunk_x, chunk_z in self.reader.iter_chunks():
            found_y = np.full((16, 16), -1, dtype=np.int16)
            found_id = np.zeros((16, 16), dtype=np.uint16)
            found_dt = np.zeros((16, 16), dtype=np.uint8)

            sections = sorted(_iter_chunk_sections(chunk), key=lambda t: t[0], reverse=True)
            for section_y, blocks_3d, data_3d in sections:
                if np.all(found_y >= 0):
                    break
                if self._max_y is not None and section_y * 16 > self._max_y:
                    continue

                solid = blocks_3d != 0
                for exc in self._exclude:
                    solid &= blocks_3d != exc

                if self._max_y is not None:
                    limit = self._max_y - section_y * 16 + 1
                    if 0 < limit < 16:
                        solid[limit:] = False

                not_found = found_y < 0
                to_process = not_found & solid.any(axis=0)
                if not np.any(to_process):
                    continue

                argmax_rev = np.argmax(solid[::-1], axis=0)
                highest_local_y = (15 - argmax_rev).astype(np.int16)
                zz, xx = np.where(to_process)
                local_ys = highest_local_y[zz, xx]

                found_y[zz, xx] = (section_y * 16 + local_ys).astype(np.int16)
                found_id[zz, xx] = blocks_3d[local_ys, zz, xx]
                found_dt[zz, xx] = data_3d[local_ys, zz, xx]

            zz, xx = np.where(found_y >= 0)
            if len(zz):
                all_wx.append((chunk_x * 16 + xx).astype(np.int32))
                all_wz.append((chunk_z * 16 + zz).astype(np.int32))
                all_y.append(found_y[zz, xx])
                all_id.append(found_id[zz, xx])
                all_dt.append(found_dt[zz, xx])

        if not all_wx:
            return pd.DataFrame(columns=['world_x', 'world_z', 'y', 'block_id', 'block_data'])
        return pd.DataFrame({
            'world_x': np.concatenate(all_wx),
            'world_z': np.concatenate(all_wz),
            'y': np.concatenate(all_y),
            'block_id': np.concatenate(all_id),
            'block_data': np.concatenate(all_dt),
        })


class BedrockExtractor:
    """Lowest bedrock block (block_id=7) per column.

    Returns DataFrame: world_x, world_z, y, block_data
    """

    def __init__(self, region_reader: RegionReader) -> None:
        self.reader = region_reader

    def extract(self) -> pd.DataFrame:
        all_wx, all_wz, all_y, all_dt = [], [], [], []

        for chunk, chunk_x, chunk_z in self.reader.iter_chunks():
            found_y = np.full((16, 16), -1, dtype=np.int16)
            found_dt = np.zeros((16, 16), dtype=np.uint8)

            for section_y, blocks_3d, data_3d in _iter_chunk_sections(chunk):
                if np.all(found_y >= 0):
                    break
                bedrock = blocks_3d == 7
                to_process = (found_y < 0) & bedrock.any(axis=0)
                if not np.any(to_process):
                    continue
                first_y = np.argmax(bedrock, axis=0)
                zz, xx = np.where(to_process)
                local_ys = first_y[zz, xx]
                found_y[zz, xx] = (section_y * 16 + local_ys).astype(np.int16)
                found_dt[zz, xx] = data_3d[local_ys, zz, xx]

            zz, xx = np.where(found_y >= 0)
            if len(zz):
                all_wx.append((chunk_x * 16 + xx).astype(np.int32))
                all_wz.append((chunk_z * 16 + zz).astype(np.int32))
                all_y.append(found_y[zz, xx])
                all_dt.append(found_dt[zz, xx])

        if not all_wx:
            return pd.DataFrame(columns=['world_x', 'world_z', 'y', 'block_data'])
        return pd.DataFrame({
            'world_x': np.concatenate(all_wx),
            'world_z': np.concatenate(all_wz),
            'y': np.concatenate(all_y),
            'block_data': np.concatenate(all_dt),
        })


_DEFAULT_BASE_EXCLUDE: frozenset[int] = frozenset({36})


class BaseExtractor:
    """Lowest non-excluded non-air block per column (bottom-up scan).

    Works for bedrock-based maps, raised-floor maps, and floating-island
    maps — unlike BedrockExtractor it also returns the block_id.

    Returns DataFrame: world_x, world_z, y, block_id, block_data
    """

    def __init__(
        self,
        region_reader: RegionReader,
        exclude_ids: set[int] | None = None,
    ) -> None:
        self.reader = region_reader
        self._exclude: frozenset[int] = (
            frozenset(exclude_ids) if exclude_ids is not None else _DEFAULT_BASE_EXCLUDE
        )

    def extract(self) -> pd.DataFrame:
        all_wx, all_wz, all_y, all_id, all_dt = [], [], [], [], []

        for chunk, chunk_x, chunk_z in self.reader.iter_chunks():
            found_y = np.full((16, 16), -1, dtype=np.int16)
            found_id = np.zeros((16, 16), dtype=np.uint16)
            found_dt = np.zeros((16, 16), dtype=np.uint8)

            for section_y, blocks_3d, data_3d in _iter_chunk_sections(chunk):
                if np.all(found_y >= 0):
                    break
                solid = blocks_3d != 0
                for exc in self._exclude:
                    solid &= blocks_3d != exc
                to_process = (found_y < 0) & solid.any(axis=0)
                if not np.any(to_process):
                    continue
                first_y = np.argmax(solid, axis=0)
                zz, xx = np.where(to_process)
                local_ys = first_y[zz, xx]
                found_y[zz, xx] = (section_y * 16 + local_ys).astype(np.int16)
                found_id[zz, xx] = blocks_3d[local_ys, zz, xx]
                found_dt[zz, xx] = data_3d[local_ys, zz, xx]

            zz, xx = np.where(found_y >= 0)
            if len(zz):
                all_wx.append((chunk_x * 16 + xx).astype(np.int32))
                all_wz.append((chunk_z * 16 + zz).astype(np.int32))
                all_y.append(found_y[zz, xx])
                all_id.append(found_id[zz, xx])
                all_dt.append(found_dt[zz, xx])

        if not all_wx:
            return pd.DataFrame(columns=['world_x', 'world_z', 'y', 'block_id', 'block_data'])
        return pd.DataFrame({
            'world_x': np.concatenate(all_wx),
            'world_z': np.concatenate(all_wz),
            'y': np.concatenate(all_y),
            'block_id': np.concatenate(all_id),
            'block_data': np.concatenate(all_dt),
        })


class SegmentsExtractor:
    """All contiguous solid Y-ranges per column.

    For each (x, z) column records every unbroken run of non-excluded,
    non-air blocks as an inclusive interval [y_start, y_end]. A column
    with a bedrock floor and an elevated platform yields two rows.

    Returns DataFrame: world_x, world_z, y_start, y_end
    """

    def __init__(
        self,
        region_reader: RegionReader,
        exclude_ids: set[int] | None = None,
        skip_non_solid: bool = True,
        min_run_length: int = 1,
    ) -> None:
        self.reader = region_reader
        self._exclude: frozenset[int] = frozenset(exclude_ids) if exclude_ids else frozenset()
        if skip_non_solid:
            self._exclude = self._exclude | NON_SOLID_BLOCK_IDS | _SEGMENTS_EXTRA_EXCLUDE
        self.min_run_length = min_run_length

    def extract(self) -> pd.DataFrame:
        all_wx, all_wz, all_ys, all_ye = [], [], [], []

        for chunk, chunk_x, chunk_z in self.reader.iter_chunks():
            full_blocks = _build_full_blocks(chunk)
            solid = full_blocks != 0
            for exc in self._exclude:
                solid &= full_blocks != exc

            flat = solid.reshape(256, 256)
            padded = np.zeros((258, 256), dtype=bool)
            padded[1:257] = flat
            d = np.diff(padded.view(np.int8), axis=0)

            starts = np.argwhere(d == 1)
            ends = np.argwhere(d == -1)
            if len(starts) == 0:
                continue

            order_s = np.lexsort((starts[:, 0], starts[:, 1]))
            order_e = np.lexsort((ends[:, 0], ends[:, 1]))
            starts = starts[order_s]
            ends = ends[order_e]

            y_start = starts[:, 0].astype(np.int16)
            y_end = (ends[:, 0] - 1).astype(np.int16)
            col_idx = starts[:, 1]

            if self.min_run_length > 1:
                keep = (y_end - y_start + 1) >= self.min_run_length
                y_start, y_end, col_idx = y_start[keep], y_end[keep], col_idx[keep]

            if len(y_start) == 0:
                continue

            x_local = (col_idx % 16).astype(np.int32)
            z_local = (col_idx // 16).astype(np.int32)
            all_wx.append((chunk_x * 16 + x_local).astype(np.int32))
            all_wz.append((chunk_z * 16 + z_local).astype(np.int32))
            all_ys.append(y_start)
            all_ye.append(y_end)

        if not all_wx:
            return pd.DataFrame(columns=['world_x', 'world_z', 'y_start', 'y_end'])
        return pd.DataFrame({
            'world_x': np.concatenate(all_wx),
            'world_z': np.concatenate(all_wz),
            'y_start': np.concatenate(all_ys),
            'y_end': np.concatenate(all_ye),
        })
