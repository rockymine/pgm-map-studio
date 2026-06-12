"""Minecraft wool block game data — damage values and color names.

Damage 8 uses 'silver', the name stored in PGM map files
(also known as 'light_gray' in modern Minecraft).
"""

WOOL_DAMAGE_TO_COLOR: dict[int, str] = {
    0:  'white',
    1:  'orange',
    2:  'magenta',
    3:  'light_blue',
    4:  'yellow',
    5:  'lime',
    6:  'pink',
    7:  'gray',
    8:  'silver',
    9:  'cyan',
    10: 'purple',
    11: 'blue',
    12: 'brown',
    13: 'green',
    14: 'red',
    15: 'black',
}

WOOL_COLOR_TO_DAMAGE: dict[str, int] = {v: k for k, v in WOOL_DAMAGE_TO_COLOR.items()}
WOOL_COLOR_TO_DAMAGE.update({
    'light_gray': 8,
    'light gray': 8,
    'light blue': 3,
})

_ALIASES: dict[str, str] = {
    'light_gray': 'silver',
    'light gray': 'silver',
    'light blue': 'light_blue',
}

# Dye = the 1.8 `ink sack` item, whose damage encodes colour on a **different**
# scale from wool (roughly inverted: dye 0 = black, wool 0 = white). Values map to
# the same wool-colour slugs (light-gray → 'silver') so a dye colour can be matched
# to a wool colour. Used to read sheep-CTW dye spawners (kill sheep → dye the wool).
DYE_DAMAGE_TO_COLOR: dict[int, str] = {
    0:  'black',   1:  'red',     2:  'green',  3:  'brown',
    4:  'blue',    5:  'purple',  6:  'cyan',   7:  'silver',
    8:  'gray',    9:  'pink',    10: 'lime',   11: 'yellow',
    12: 'light_blue', 13: 'magenta', 14: 'orange', 15: 'white',
}


def normalize_wool_color(color: str) -> str:
    """Normalize a wool color name to the canonical form used in WOOL_DAMAGE_TO_COLOR.

    Handles spaces, underscores, hyphens, case, and alternate names
    (e.g. 'Light Gray', 'light_gray', 'light gray' → 'silver').
    """
    key = color.strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    return key.replace(' ', '_').replace('-', '_')
