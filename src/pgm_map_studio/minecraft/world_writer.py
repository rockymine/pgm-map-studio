"""world_writer.py — Write (x, z) block positions into a Minecraft 1.8 Anvil world.

Creates a minimal PGM-loadable map directory:
  level.dat    — gzip-compressed NBT world metadata (format version 19133)
  region/      — Anvil .mca region files with blocks at the given Y level

Coordinate handling: uses Python floor division so negative world coordinates
(common in CTW maps) are placed in the correct region and chunk automatically.
"""
from __future__ import annotations

import logging
import time
import zlib
from io import BytesIO
from pathlib import Path
from typing import Iterable

from nbt import nbt as nbt_lib

logger = logging.getLogger("pgm_map_studio")


# ── NBT helpers ───────────────────────────────────────────────────────────────

def _bytes_tag(name: str, data: bytes | bytearray) -> nbt_lib.TAG_Byte_Array:
    t = nbt_lib.TAG_Byte_Array(name=name)
    t.value = bytearray(data)
    return t


def _pack_nibbles(nibbles: bytearray) -> bytearray:
    """Pack 4096 4-bit values into 2048 bytes (little-endian nibble pairs)."""
    out = bytearray(2048)
    for i in range(2048):
        out[i] = (nibbles[i * 2] & 0xF) | ((nibbles[i * 2 + 1] & 0xF) << 4)
    return out


# ── Section / chunk / region builders ────────────────────────────────────────

def _build_section(y_idx: int, blocks: bytearray, data: bytearray) -> nbt_lib.TAG_Compound:
    """Return a 1.8-format section TAG_Compound."""
    sec = nbt_lib.TAG_Compound()
    sec.tags += [
        nbt_lib.TAG_Byte(name="Y", value=y_idx),
        _bytes_tag("Blocks", blocks),
        _bytes_tag("Data", _pack_nibbles(data)),
        _bytes_tag("BlockLight", bytearray(2048)),
        _bytes_tag("SkyLight", bytearray(b"\xff" * 2048)),
    ]
    return sec


def _build_chunk(
    cx: int, cz: int, placements: list[tuple[int, int, int, int, int]]
) -> nbt_lib.NBTFile:
    """Return a 1.8-format chunk NBTFile.

    placements: [(local_x, world_y, local_z, block_id, block_data), ...]
    Blocks are indexed within a 16×16×16 section as y*256 + z*16 + x.
    """
    sections: dict[int, tuple[bytearray, bytearray]] = {}
    height_map = [0] * 256  # index: local_z * 16 + local_x

    for lx, wy, lz, bid, bdata in placements:
        y_idx, ly = divmod(wy, 16)
        if y_idx not in sections:
            sections[y_idx] = (bytearray(4096), bytearray(4096))
        blk, dat = sections[y_idx]
        idx = ly * 256 + lz * 16 + lx
        blk[idx] = bid & 0xFF
        dat[idx] = bdata & 0xF
        hm = lz * 16 + lx
        if wy + 1 > height_map[hm]:
            height_map[hm] = wy + 1

    root = nbt_lib.NBTFile()
    root.tags.append(nbt_lib.TAG_Int(name="DataVersion", value=0))

    level = nbt_lib.TAG_Compound()
    level.name = "Level"
    level.tags += [
        nbt_lib.TAG_Byte(name="V", value=1),
        nbt_lib.TAG_Int(name="xPos", value=cx),
        nbt_lib.TAG_Int(name="zPos", value=cz),
        nbt_lib.TAG_Long(name="LastUpdate", value=0),
        nbt_lib.TAG_Long(name="InhabitedTime", value=0),
        nbt_lib.TAG_Byte(name="TerrainPopulated", value=1),
        nbt_lib.TAG_Byte(name="LightPopulated", value=1),
    ]

    hm_tag = nbt_lib.TAG_Int_Array(name="HeightMap")
    hm_tag.value = height_map
    level.tags.append(hm_tag)

    biomes_tag = nbt_lib.TAG_Byte_Array(name="Biomes")
    biomes_tag.value = bytearray(256)
    level.tags.append(biomes_tag)

    secs_list = nbt_lib.TAG_List(name="Sections", type=nbt_lib.TAG_Compound)
    for y_idx in sorted(sections):
        blk, dat = sections[y_idx]
        secs_list.tags.append(_build_section(y_idx, blk, dat))
    level.tags.append(secs_list)

    for name in ("Entities", "TileEntities"):
        level.tags.append(nbt_lib.TAG_List(name=name, type=nbt_lib.TAG_Compound))

    root.tags.append(level)
    return root


def _compress_chunk(cx: int, cz: int, placements: list) -> bytes:
    chunk = _build_chunk(cx, cz, placements)
    buf = BytesIO()
    chunk.write_file(buffer=buf)
    return zlib.compress(buf.getvalue())


def _write_mca(rx: int, rz: int, chunks: dict[tuple[int, int], bytes], path: Path) -> None:
    """Write one .mca region file.

    chunks: {(cx, cz): zlib-compressed chunk bytes}
    The location header stores sector offsets (in 4 KiB units) from the file start.
    Two header sectors (8 KiB) precede chunk data, so data-section offset 0 = sector 2.
    """
    location_header = bytearray(4096)
    data_section = bytearray()

    for (cx, cz), compressed in chunks.items():
        slot = (cx % 32) + (cz % 32) * 32
        # 4-byte big-endian length (payload + 1 for the compression byte), then compression byte
        raw = (len(compressed) + 1).to_bytes(4, "big") + b"\x02" + compressed
        pad = (4096 - len(raw) % 4096) % 4096
        padded = raw + bytes(pad)

        sector_off = len(data_section) // 4096 + 2  # absolute from file start
        sector_cnt = len(padded) // 4096
        location_header[slot * 4 : slot * 4 + 3] = sector_off.to_bytes(3, "big")
        location_header[slot * 4 + 3] = sector_cnt

        data_section += padded

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(bytes(location_header))
        f.write(bytes(4096))        # timestamp table (all zeros)
        f.write(bytes(data_section))
        total = 8192 + len(data_section)
        rem = total % 4096
        if rem:
            f.write(bytes(4096 - rem))


def _write_level_dat(path: Path, level_name: str) -> None:
    """Write a gzip-compressed Minecraft 1.8 level.dat."""
    root = nbt_lib.NBTFile()
    data = nbt_lib.TAG_Compound()
    data.name = "Data"

    data.tags += [
        nbt_lib.TAG_Int(name="version", value=19133),
        nbt_lib.TAG_String(name="LevelName", value=level_name),
        nbt_lib.TAG_String(name="generatorName", value="flat"),
        nbt_lib.TAG_String(name="generatorOptions", value=""),
        nbt_lib.TAG_Int(name="generatorVersion", value=0),
        nbt_lib.TAG_Int(name="GameType", value=1),   # Creative
        nbt_lib.TAG_Byte(name="MapFeatures", value=0),
        nbt_lib.TAG_Long(name="RandomSeed", value=0),
        nbt_lib.TAG_Byte(name="hardcore", value=0),
        nbt_lib.TAG_Byte(name="allowCommands", value=1),
        nbt_lib.TAG_Byte(name="initialized", value=1),
        nbt_lib.TAG_Long(name="Time", value=0),
        nbt_lib.TAG_Long(name="DayTime", value=6000),
        nbt_lib.TAG_Long(name="LastPlayed", value=int(time.time() * 1000)),
        nbt_lib.TAG_Long(name="SizeOnDisk", value=0),
        nbt_lib.TAG_Int(name="SpawnX", value=0),
        nbt_lib.TAG_Int(name="SpawnY", value=64),
        nbt_lib.TAG_Int(name="SpawnZ", value=0),
        nbt_lib.TAG_Byte(name="raining", value=0),
        nbt_lib.TAG_Int(name="rainTime", value=0),
        nbt_lib.TAG_Byte(name="thundering", value=0),
        nbt_lib.TAG_Int(name="thunderTime", value=0),
        nbt_lib.TAG_Byte(name="Difficulty", value=1),
        nbt_lib.TAG_Byte(name="DifficultyLocked", value=0),
    ]

    rules = nbt_lib.TAG_Compound()
    rules.name = "GameRules"
    for k, v in [
        ("doMobSpawning", "false"),
        ("doDaylightCycle", "false"),
        ("doFireTick", "false"),
        ("doMobLoot", "false"),
        ("keepInventory", "false"),
        ("naturalRegeneration", "true"),
        ("doTileDrops", "true"),
        ("randomTickSpeed", "0"),
        ("commandBlockOutput", "false"),
    ]:
        rules.tags.append(nbt_lib.TAG_String(name=k, value=v))
    data.tags.append(rules)

    root.tags.append(data)
    root.write_file(str(path))


# ── Public API ────────────────────────────────────────────────────────────────

def write_world(
    blocks: Iterable[tuple[int, int]],
    world_dir: Path,
    y: int = 0,
    block_id: int = 1,
    block_data: int = 0,
    level_name: str = "sketch",
) -> None:
    """Write a Minecraft 1.8 world from a flat set of (world_x, world_z) positions.

    Places each block at the given Y with block_id / block_data (default: stone
    at Y=0). Writes level.dat and region/*.mca into world_dir (created if absent).

    Negative world coordinates are handled correctly via Python floor division:
    world_x=-246 → chunk cx=-16 → region rx=-1, local_x=10.
    """
    world_dir = Path(world_dir)

    # Group: region → chunk → placements
    regions: dict[tuple[int, int], dict[tuple[int, int], list]] = {}
    for wx, wz in blocks:
        cx, cz = wx // 16, wz // 16
        rx, rz = cx // 32, cz // 32
        lx, lz = wx % 16, wz % 16
        (regions
            .setdefault((rx, rz), {})
            .setdefault((cx, cz), [])
            .append((lx, y, lz, block_id, block_data)))

    (world_dir / "region").mkdir(parents=True, exist_ok=True)
    total_blocks = 0
    for (rx, rz), chunk_map in regions.items():
        compressed = {
            (cx, cz): _compress_chunk(cx, cz, placements)
            for (cx, cz), placements in chunk_map.items()
        }
        _write_mca(rx, rz, compressed, world_dir / "region" / f"r.{rx}.{rz}.mca")
        total_blocks += sum(len(p) for p in chunk_map.values())

    _write_level_dat(world_dir / "level.dat", level_name)
    logger.info(
        "world_writer: wrote %d region file(s), %d blocks at y=%d → %s",
        len(regions), total_blocks, y, world_dir,
    )
