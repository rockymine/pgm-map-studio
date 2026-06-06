"""Tests for minecraft/world_writer.py.

Writes a minimal world to a tmp directory, then reads it back with the
existing RegionReader to verify blocks are placed at the correct positions.
"""
import struct
from pathlib import Path

import pytest
import anvil
from nbt import nbt as nbt_lib

from pgm_map_studio.minecraft.world_writer import (
    write_world,
    _pack_nibbles,
    _build_section,
    _build_chunk,
)
from pgm_map_studio.minecraft.region_reader import RegionReader
from pgm_map_studio.minecraft._helpers import _build_full_blocks


# ── nibble packing ────────────────────────────────────────────────────────────

def test_pack_nibbles_basic():
    # Two blocks: lo=0x3, hi=0xA → packed byte should be 0xA3
    nibbles = bytearray([3, 0xA] + [0] * 4094)
    result = _pack_nibbles(nibbles)
    assert result[0] == 0x3 | (0xA << 4)
    assert all(b == 0 for b in result[1:])


def test_pack_nibbles_roundtrip():
    import numpy as np
    rng = np.random.default_rng(42)
    nibbles = bytearray(rng.integers(0, 16, size=4096).tolist())
    packed = _pack_nibbles(nibbles)
    # Unpack
    unpacked = bytearray(4096)
    for i, b in enumerate(packed):
        unpacked[i * 2]     = b & 0xF
        unpacked[i * 2 + 1] = (b >> 4) & 0xF
    assert unpacked == nibbles


# ── section builder ───────────────────────────────────────────────────────────

def test_build_section_has_required_tags():
    blocks = bytearray(4096)
    data = bytearray(4096)
    blocks[0] = 1  # stone at local (0,0,0)
    sec = _build_section(0, blocks, data)
    tag_names = {t.name for t in sec.tags}
    assert {"Y", "Blocks", "Data", "BlockLight", "SkyLight"} <= tag_names


def test_build_section_y_index():
    sec = _build_section(7, bytearray(4096), bytearray(4096))
    y_tag = next(t for t in sec.tags if t.name == "Y")
    assert y_tag.value == 7


def test_build_section_blocks_stored_correctly():
    blocks = bytearray(4096)
    # Local (x=3, y=2, z=5) → index = 2*256 + 5*16 + 3 = 512 + 80 + 3 = 595
    blocks[595] = 4  # cobblestone
    data = bytearray(4096)
    data[595] = 2  # data nibble

    sec = _build_section(0, blocks, data)
    blk_tag = next(t for t in sec.tags if t.name == "Blocks")
    dat_tag = next(t for t in sec.tags if t.name == "Data")

    assert blk_tag.value[595] == 4
    # Packed: index 595 is odd position of pair (297), hi nibble
    packed_idx = 595 // 2
    nibble_pos = 595 % 2
    if nibble_pos == 0:
        assert dat_tag.value[packed_idx] & 0xF == 2
    else:
        assert (dat_tag.value[packed_idx] >> 4) & 0xF == 2


# ── chunk builder ─────────────────────────────────────────────────────────────

def test_build_chunk_has_level_tag():
    chunk = _build_chunk(0, 0, [])
    assert "Level" in chunk


def test_build_chunk_chunk_coordinates():
    chunk = _build_chunk(5, -3, [])
    level = chunk["Level"]
    assert level["xPos"].value == 5
    assert level["zPos"].value == -3


def test_build_chunk_height_map():
    # Place a block at world_y=7, local (1, 2)
    chunk = _build_chunk(0, 0, [(1, 7, 2, 1, 0)])
    level = chunk["Level"]
    hm = level["HeightMap"].value
    hm_idx = 2 * 16 + 1  # lz * 16 + lx
    assert hm[hm_idx] == 8  # y + 1


def test_build_chunk_places_block_in_section():
    # world_y=5 → section y_idx=0, local_y=5
    # local x=3, z=7 → section index = 5*256 + 7*16 + 3 = 1280 + 112 + 3 = 1395
    chunk = _build_chunk(0, 0, [(3, 5, 7, 1, 0)])
    level = chunk["Level"]
    sections = level["Sections"].tags
    assert len(sections) == 1
    sec = sections[0]
    assert sec["Y"].value == 0
    assert sec["Blocks"].value[1395] == 1


def test_build_chunk_multiple_sections():
    # Place blocks at y=5 (section 0) and y=20 (section 1)
    chunk = _build_chunk(0, 0, [(0, 5, 0, 1, 0), (0, 20, 0, 2, 0)])
    level = chunk["Level"]
    y_indices = {s["Y"].value for s in level["Sections"].tags}
    assert y_indices == {0, 1}


# ── write_world integration ───────────────────────────────────────────────────

@pytest.fixture
def world_dir(tmp_path):
    return tmp_path / "test_world"


def test_write_world_creates_level_dat(world_dir):
    write_world([(0, 0)], world_dir)
    assert (world_dir / "level.dat").exists()


def test_write_world_level_dat_readable(world_dir):
    write_world([(0, 0)], world_dir, level_name="My Map")
    nbt = nbt_lib.NBTFile(str(world_dir / "level.dat"), "rb")
    assert nbt["Data"]["LevelName"].value == "My Map"
    assert nbt["Data"]["version"].value == 19133  # 1.8 format


def test_write_world_creates_region_files(world_dir):
    write_world([(0, 0), (32, 48)], world_dir)
    region_files = list((world_dir / "region").glob("r.*.*.mca"))
    assert len(region_files) >= 1


def test_write_world_single_block_positive_coords(world_dir):
    blocks = {(17, 33)}
    write_world(blocks, world_dir)
    reader = RegionReader(world_dir / "region")
    found = set()
    for chunk, cx, cz in reader.iter_chunks():
        full = _build_full_blocks(chunk)
        for lx in range(16):
            for lz in range(16):
                if full[0, lz, lx] != 0:
                    found.add((cx * 16 + lx, cz * 16 + lz))
    assert found == blocks


def test_write_world_negative_coords(world_dir):
    # Coordinates from the "polygon inside hole test" sketch
    blocks = {(-246, -247), (-28, -25), (-157, -175)}
    write_world(blocks, world_dir)
    reader = RegionReader(world_dir / "region")
    found = set()
    for chunk, cx, cz in reader.iter_chunks():
        full = _build_full_blocks(chunk)
        for lx in range(16):
            for lz in range(16):
                if full[0, lz, lx] != 0:
                    found.add((cx * 16 + lx, cz * 16 + lz))
    assert found == blocks


def test_write_world_spans_multiple_regions(world_dir):
    # Force blocks into two different 512×512 regions
    blocks = {(0, 0), (600, 600)}
    write_world(blocks, world_dir)
    region_files = list((world_dir / "region").glob("r.*.*.mca"))
    assert len(region_files) == 2


def test_write_world_custom_block_id_and_data(world_dir):
    write_world([(5, 5)], world_dir, block_id=35, block_data=14, y=0)
    reader = RegionReader(world_dir / "region")
    for chunk, cx, cz in reader.iter_chunks():
        from pgm_map_studio.minecraft._helpers import _iter_chunk_sections
        for _, blk3d, dat3d in _iter_chunk_sections(chunk):
            lx, lz = 5 % 16, 5 % 16
            assert blk3d[0, lz, lx] == 35
            assert dat3d[0, lz, lx] == 14
            return


def test_write_world_custom_y_level(world_dir):
    write_world([(0, 0)], world_dir, y=17)
    reader = RegionReader(world_dir / "region")
    for chunk, cx, cz in reader.iter_chunks():
        full = _build_full_blocks(chunk)
        assert full[17, 0, 0] == 1
        assert full[0, 0, 0] == 0
        return


def test_write_world_all_blocks_round_trip(world_dir):
    # A 5×5 grid of blocks, all at Y=0
    blocks = {(x, z) for x in range(5) for z in range(5)}
    write_world(blocks, world_dir)
    reader = RegionReader(world_dir / "region")
    found = set()
    for chunk, cx, cz in reader.iter_chunks():
        full = _build_full_blocks(chunk)
        for lx in range(16):
            for lz in range(16):
                if full[0, lz, lx] != 0:
                    found.add((cx * 16 + lx, cz * 16 + lz))
    assert found == blocks


def test_write_world_mca_file_is_valid_4kib_multiple(world_dir):
    write_world([(0, 0)], world_dir)
    for mca in (world_dir / "region").glob("r.*.*.mca"):
        assert mca.stat().st_size % 4096 == 0
