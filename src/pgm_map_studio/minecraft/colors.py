"""Minecraft block ID → RGB colour lookup.

Based on Minecraft's MapColor enum (1.8/1.9 source). Stained blocks
(wool=35, stained glass=95, stained clay=159, carpet=171) use their
damage value as a sub-colour index into _STAIN_COLORS.
"""

_STAIN_COLORS: dict[int, tuple[int, int, int]] = {
    0:  (221, 221, 221),  1:  (216, 127,  51),  2:  (178,  76, 216),
    3:  (102, 153, 216),  4:  (229, 229,  51),  5:  (127, 204,  25),
    6:  (242, 127, 165),  7:  ( 76,  76,  76),  8:  (153, 153, 153),
    9:  ( 76, 127, 153),  10: (127,  63, 178),  11: ( 51,  76, 178),
    12: (102,  76,  51),  13: (102, 127,  51),  14: (153,  51,  51),
    15: ( 25,  25,  25),
}

_BLOCK_COLORS: dict[tuple[int, int], tuple[int, int, int]] = {}


def _bc(bid: int, r: int, g: int, b: int, data: int = -1) -> None:
    _BLOCK_COLORS[(bid, data)] = (r, g, b)


def _bc_stained(bid: int) -> None:
    for meta, rgb in _STAIN_COLORS.items():
        _BLOCK_COLORS[(bid, meta)] = rgb
    _BLOCK_COLORS[(bid, -1)] = _STAIN_COLORS[0]


_bc(0,    0,   0,   0)
_bc(1,  112, 112, 112)
_bc(2,  127, 178,  56)
_bc(3,  151,  94,  61)
_bc(4,  112, 112, 112)
_bc(7,   80,  80,  80)
_bc(8,   64,  64, 255)
_bc(9,   64,  64, 255)
_bc(10, 255,  90,   0)
_bc(11, 255,  90,   0)
_bc(12, 247, 214, 163)
_bc(13, 150, 140, 130)
_bc(14, 143, 119,  72)
_bc(15, 112, 112, 112)
_bc(16, 112, 112, 112)
_bc(17, 143, 119,  72)
_bc(18,   0, 124,   0)
_bc(19, 200, 200,  80)
_bc(20, 180, 210, 230)
_bc(21,  51,  76, 178)
_bc(22,  74, 144, 226)
_bc(24, 230, 200, 140)
_bc(25, 143, 119,  72)
_bc(26, 180, 100, 100)
_bc(30, 220, 220, 220)
_bc(31,   0, 160,   0)
_bc(35,  -1,  -1,  -1)
_bc(36, 255,   0, 255)   # piston extension — vibrant magenta for visibility
_bc(41, 250, 238,  77)
_bc(42, 200, 200, 210)
_bc(43, 120, 120, 120)
_bc(44, 120, 120, 120)
_bc(45, 168,  70,  55)
_bc(46, 255,  40,  40)
_bc(47, 143, 119,  72)
_bc(48, 100, 130, 100)
_bc(49,  35,  20,  55)
_bc(53, 143, 119,  72)
_bc(54, 143, 100,  50)
_bc(55, 200,   0,   0)
_bc(57,  94, 237, 255)
_bc(58, 143, 100,  50)
_bc(61,  80,  80,  80)
_bc(67, 112, 112, 112)
_bc(77, 112, 112, 112)
_bc(80, 240, 240, 255)
_bc(85, 143, 119,  72)
_bc(87, 112,   2,   0)
_bc(88, 100,  80,  50)
_bc(89, 240, 200, 100)
_bc(91, 240, 150,  20)
_bc(95,  -1,  -1,  -1)
_bc(96, 143, 119,  72)
_bc(97, 112, 112, 112)
_bc(98, 112, 112, 112)
_bc(103, 100, 170,  40)
_bc(106,   0, 160,   0)
_bc(107, 143, 119,  72)
_bc(108, 168,  70,  55)
_bc(109, 112, 112, 112)
_bc(111,  60, 130,  40)
_bc(112,  45,  20,  20)
_bc(120,  80,  80,  40)
_bc(121, 220, 220, 180)
_bc(123, 100,  80,  40)
_bc(124, 240, 200, 100)
_bc(125, 143, 119,  72)
_bc(126, 143, 119,  72)
_bc(128, 230, 200, 140)
_bc(129, 100, 200, 100)
_bc(130, 143, 100,  50)
_bc(131, 143, 119,  72)
_bc(133,   0, 200,  60)
_bc(134, 110,  80,  50)
_bc(135, 143, 119,  72)
_bc(136, 120,  80,  40)
_bc(138,  80, 220, 240)
_bc(139, 112, 112, 112)
_bc(143, 143, 119,  72)
_bc(144, 100, 100, 100)
_bc(145, 200, 200, 210)
_bc(146, 143, 100,  50)
_bc(148, 200, 200, 210)
_bc(155, 240, 235, 220)
_bc(156, 240, 235, 220)
_bc(159,  -1,  -1,  -1)
_bc(160,  -1,  -1,  -1)
_bc(161,   0, 124,   0)
_bc(162, 143, 119,  72)
_bc(163, 110,  80,  50)
_bc(164, 110,  60,  30)
_bc(165, 200, 220,  80)
_bc(166, 255,   0,   0)
_bc(167, 200, 200, 210)
_bc(168,  66, 140, 120)
_bc(169,  80, 220, 240)
_bc(170, 215, 185,  35)
_bc(171,  -1,  -1,  -1)
_bc(172, 160,  90,  40)
_bc(173,  25,  25,  25)
_bc(174, 200, 220, 255)
_bc(179, 230, 200, 140)
_bc(180, 230, 200, 140)
_bc(181, 230, 200, 140)
_bc(182, 230, 200, 140)
_bc(183, 110,  60,  30)
_bc(184, 190, 160, 100)
_bc(185, 120,  80,  40)
_bc(186, 110,  60,  30)
_bc(187, 143, 119,  72)
_bc(188, 110,  80,  50)
_bc(189, 190, 160, 100)
_bc(190, 120,  80,  40)
_bc(191, 110,  60,  30)
_bc(192, 143, 119,  72)
_bc(193, 190, 160, 100)
_bc(196, 110,  60,  30)

for _bid in (35, 95, 159, 160, 171):
    _bc_stained(_bid)


_BLOCK_NAMES: dict[int, str] = {
    0: "Air",          1: "Stone",             2: "Grass",         3: "Dirt",
    4: "Cobblestone",  7: "Bedrock",            8: "Water",         9: "Water",
    10: "Lava",        11: "Lava",             12: "Sand",         13: "Gravel",
    14: "Gold Ore",    15: "Iron Ore",         16: "Coal Ore",     17: "Wood",
    18: "Leaves",      19: "Sponge",           20: "Glass",        21: "Lapis Ore",
    22: "Lapis Block", 24: "Sandstone",        25: "Note Block",   26: "Bed",
    30: "Cobweb",      31: "Tall Grass",       36: "Piston Head",  41: "Gold Block",
    42: "Iron Block",  43: "Double Slab",      44: "Slab",         45: "Brick",
    46: "TNT",         47: "Bookshelf",        48: "Mossy Cobble", 49: "Obsidian",
    53: "Oak Stairs",  54: "Chest",            55: "Redstone Wire", 57: "Diamond Block",
    58: "Crafting Table", 61: "Furnace",       67: "Stone Stairs", 77: "Stone Button",
    80: "Snow",        85: "Oak Fence",        87: "Netherrack",   88: "Soul Sand",
    89: "Glowstone",   91: "Jack o'Lantern",   96: "Trapdoor",     97: "Monster Egg",
    98: "Stone Bricks", 103: "Melon",          106: "Vines",       107: "Fence Gate",
    108: "Brick Stairs", 109: "Stone Brick Stairs", 111: "Lily Pad", 112: "Nether Bricks",
    120: "End Portal Frame", 121: "End Stone", 123: "Redstone Lamp", 124: "Redstone Lamp",
    125: "Wood Slab",  126: "Wood Slab",       128: "Sandstone Stairs", 129: "Emerald Ore",
    130: "Ender Chest", 131: "Tripwire Hook",  133: "Emerald Block", 134: "Spruce Stairs",
    135: "Birch Stairs", 136: "Jungle Stairs", 138: "Beacon",      139: "Cobblestone Wall",
    143: "Wood Button", 144: "Mob Head",       145: "Anvil",       146: "Trapped Chest",
    148: "Comparator", 155: "Quartz Block",    156: "Quartz Stairs", 161: "Acacia Leaves",
    162: "Acacia Wood", 163: "Acacia Stairs",  164: "Dark Oak Stairs", 165: "Slime Block",
    166: "Barrier",    167: "Iron Trapdoor",   168: "Prismarine",  169: "Sea Lantern",
    170: "Hay Bale",   172: "Hardened Clay",   173: "Coal Block",  174: "Packed Ice",
    179: "Red Sandstone", 180: "Red Sandstone Stairs", 181: "Red Double Slab", 182: "Red Slab",
    183: "Spruce Fence Gate", 184: "Birch Fence Gate", 185: "Jungle Fence Gate",
    186: "Dark Oak Fence Gate", 187: "Acacia Fence Gate", 188: "Spruce Fence",
    189: "Birch Fence", 190: "Jungle Fence",  191: "Dark Oak Fence", 192: "Acacia Fence",
    193: "Spruce Door", 196: "Dark Oak Door",
}
_STAIN_COLOR_NAMES = [
    "White", "Orange", "Magenta", "Light Blue", "Yellow", "Lime",
    "Pink", "Gray", "Light Gray", "Cyan", "Purple", "Blue",
    "Brown", "Green", "Red", "Black",
]
_STAIN_BLOCK_BASE_NAMES = {
    35: "Wool", 95: "Stained Glass", 159: "Stained Clay",
    160: "Stained Glass Pane", 171: "Carpet",
}


def block_color(block_id: int, block_data: int) -> tuple[int, int, int]:
    """Return (r, g, b) for a block ID + data value.

    Falls back to a deterministic colour for unknown blocks.
    """
    key = (block_id, block_data)
    if key in _BLOCK_COLORS:
        return _BLOCK_COLORS[key]
    if (block_id, -1) in _BLOCK_COLORS:
        return _BLOCK_COLORS[(block_id, -1)]
    # Deterministic fallback — no numpy needed
    h = hash((block_id, block_data)) & 0xFFFFFF
    return ((h >> 16) & 0xFF + 80) % 220, ((h >> 8) & 0xFF + 80) % 220, (h & 0xFF + 80) % 220


def block_name(block_id: int, block_data: int) -> str:
    """Return a human-readable name for a block ID + data value."""
    if block_id in _STAIN_BLOCK_BASE_NAMES:
        color = _STAIN_COLOR_NAMES[block_data % 16] if 0 <= block_data < 16 else ""
        return f"{color} {_STAIN_BLOCK_BASE_NAMES[block_id]}" if color else _STAIN_BLOCK_BASE_NAMES[block_id]
    return _BLOCK_NAMES.get(block_id, f"Block {block_id}")
