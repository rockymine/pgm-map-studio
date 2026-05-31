import pytest
from pgm_map_studio.minecraft.wool import (
    WOOL_DAMAGE_TO_COLOR,
    WOOL_COLOR_TO_DAMAGE,
    normalize_wool_color,
)


def test_damage_to_color_has_sixteen_entries():
    assert len(WOOL_DAMAGE_TO_COLOR) == 16


def test_damage_to_color_covers_zero_to_fifteen():
    assert set(WOOL_DAMAGE_TO_COLOR.keys()) == set(range(16))


def test_color_to_damage_round_trips():
    for damage, color in WOOL_DAMAGE_TO_COLOR.items():
        assert WOOL_COLOR_TO_DAMAGE[color] == damage


def test_silver_is_damage_eight():
    assert WOOL_COLOR_TO_DAMAGE['silver'] == 8


def test_light_gray_alias_maps_to_eight():
    assert WOOL_COLOR_TO_DAMAGE['light_gray'] == 8
    assert WOOL_COLOR_TO_DAMAGE['light gray'] == 8


def test_normalize_lowercase():
    assert normalize_wool_color('RED') == 'red'


def test_normalize_strips_whitespace():
    assert normalize_wool_color('  blue  ') == 'blue'


def test_normalize_spaces_to_underscores():
    assert normalize_wool_color('light blue') == 'light_blue'


def test_normalize_hyphens_to_underscores():
    assert normalize_wool_color('light-blue') == 'light_blue'


def test_normalize_light_gray_to_silver():
    assert normalize_wool_color('light_gray') == 'silver'
    assert normalize_wool_color('Light Gray') == 'silver'
    assert normalize_wool_color('light gray') == 'silver'


def test_normalize_known_color_unchanged():
    assert normalize_wool_color('cyan') == 'cyan'
    assert normalize_wool_color('purple') == 'purple'
