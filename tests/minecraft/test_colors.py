from pgm_map_studio.minecraft.colors import block_color


def test_known_block_returns_correct_color():
    assert block_color(0, 0) == (0, 0, 0)       # air
    assert block_color(1, 0) == (112, 112, 112)  # stone
    assert block_color(57, 0) == (94, 237, 255)  # diamond block


def test_stained_wool_returns_correct_color():
    assert block_color(35, 0) == (221, 221, 221)  # white wool
    assert block_color(35, 14) == (153, 51, 51)   # red wool


def test_unknown_block_returns_int_tuple():
    result = block_color(9999, 0)
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert all(isinstance(v, int) for v in result)


def test_unknown_block_is_deterministic():
    assert block_color(9999, 0) == block_color(9999, 0)
    assert block_color(9999, 1) == block_color(9999, 1)


def test_block_without_data_variant_falls_back():
    # block 1 (stone) has no per-data variant, data=5 should still return a colour
    result = block_color(1, 5)
    assert isinstance(result, tuple)
    assert len(result) == 3
