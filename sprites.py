"""Sample 16x16 tiles reproducing the attached dungeon room (written as text pixel art)."""

W = 16


def _pad(rows: list[str]) -> list[str]:
    """Right-pad hand-drawn rows with transparent pixels (too long is still an error)."""
    return [r.ljust(W, ".") for r in rows]


SPRITES: dict[str, dict] = {
    "brick": {
        "palette": {"k": "#1a1a1a", "R": "#e8663a", "r": "#d0401f"},
        "rows": [
            "kkkkkkkkkkkkkkkk",
            "RRRRRRRkRRRRRRRk",
            "rrrrrrrkrrrrrrrk",
            "rrrrrrrkrrrrrrrk",
            "kkkkkkkkkkkkkkkk",
            "RRRkRRRRRRRkRRRR",
            "rrrkrrrrrrrkrrrr",
            "rrrkrrrrrrrkrrrr",
            "kkkkkkkkkkkkkkkk",
            "RRRRRRRkRRRRRRRk",
            "rrrrrrrkrrrrrrrk",
            "rrrrrrrkrrrrrrrk",
            "kkkkkkkkkkkkkkkk",
            "RRRkRRRRRRRkRRRR",
            "rrrkrrrrrrrkrrrr",
            "rrrkrrrrrrrkrrrr",
        ],
    },
    "stone": {
        "palette": {"k": "#2b2e38", "d": "#4a4f5e", "l": "#5c6274"},
        "rows": [
            "kkkkkkkkkkkkkkkk",
            "kddddlllddddllld",
            "kdlllddkddlllddd",
            "kdldddddkdldddld",
            "kddddlldddddllld",
            "kllddddddlldddld",
            "kdddkkdddldddkdd",
            "kdddddkdddddkddd",
            "kdlldddddllddddd",
            "kddddldddddllddd",
            "kdlddddkddddldld",
            "kdddllddkdddddld",
            "kddddddddlddllld",
            "kllddkddddddddld",
            "kdddddkdddlllddd",
            "kddldddddddddddd",
        ],
    },
    "door": {
        "palette": {"k": "#3a1c08", "o": "#c8642a", "O": "#e08040", "y": "#f0c040"},
        "rows": [
            "..kkkkkkkkkkkk..",
            ".kooooooooooook.",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kooOooOooOyyOook",
            "kooOooOooOyyOook",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kooOooOooOooOook",
            "kkkkkkkkkkkkkkkk",
        ],
    },
    "sword": {
        "palette": {"k": "#20222a", "w": "#d8dde6", "g": "#8a90a0", "y": "#e0b040", "b": "#8a5a2a"},
        "rows": _pad([
            ".............kk",
            "............kwwk",
            "...........kwwgk",
            "..........kwwgk",
            ".........kwwgk",
            "........kwwgk",
            ".......kwwgk",
            "......kwwgk",
            ".....kwwgk",
            "....kyygkk",
            "...kyyykyk",
            "..kbbk.kk",
            ".kbbk",
            "kbbk",
            "kkk",
            "",
        ]),
    },
    "slime": {
        "palette": {"k": "#123a12", "g": "#4cc04c", "G": "#2e8f2e"},
        "rows": _pad([
            "", "", "", "",
            "....kkkkkkkk",
            "..kkggggggggkk",
            ".kggggggggggggk",
            ".kggkkggggkkggk",
            ".kggkkggggkkggk",
            ".kgggggggggggGk",
            ".kGgggkkkkgggGk",
            ".kGGgggggggggGk",
            "..kkGGGGGGGGkk",
            "....kkkkkkkk",
            "", "",
        ]),
    },
    "player": {
        "palette": {"w": "#ffffff", "k": "#000000"},
        "rows": _pad([
            "", "",
            "......wwww",
            ".....wwwwww",
            ".....wkwwkw",
            ".....wwwwww",
            "......wwww",
            ".....wwwwww",
            "....wwwwwwww",
            "....ww.ww.ww",
            "....ww.ww.ww",
            "......wwww",
            "......w..w",
            "......w..w",
            ".....ww..ww",
            "",
        ]),
    },
    "potion": {
        "palette": {"k": "#3a0a0a", "r": "#d02020", "R": "#ff6060", "g": "#c0c8d8", "o": "#a06030"},
        "rows": _pad([
            "", "",
            ".....kooook",
            "......kggk",
            "......kggk",
            ".....kggggk",
            "....kkrrrrkk",
            "...krrRRrrrrk",
            "..krrRrrrrrrrk",
            "..krrRrrrrrrrk",
            "..krrrrrrrrrrk",
            "..krrrrrrrrrrk",
            "...krrrrrrrrk",
            "....kkkkkkkk",
            "", "",
        ]),
    },
    "goblin": {
        "palette": {"b": "#8a4a20", "w": "#ffffff", "s": "#c08040"},
        "rows": _pad([
            "",
            "......bbbb",
            ".....bbbbbb",
            "....bbwbbwbb",
            ".....bbbbbb",
            "......bbbb",
            "....bbbbbbbb",
            "...sbbbbbbbb",
            "..sssbbbbbbbb",
            "..sssbbbbbbbbb",
            "..sss.bbbbbb",
            "......bb.bb",
            "......bb.bb",
            ".....bbb.bbb",
            "", "",
        ]),
    },
    "stairs": {
        "palette": {"b": "#7a5a3a", "B": "#a07a50", "k": "#111111"},
        "rows": [
            "bbbbbbbbbbbbbbbb",
            "bkkkkkkkkkkkkkkb",
            "bkkkkkkkkkkkkkkb",
            "bkkkkkkkkkBBBBkb",
            "bkkkkkkkkkBBBBkb",
            "bkkkkkkkkkBBBBkb",
            "bkkkkkBBBBBBBBkb",
            "bkkkkkBBBBBBBBkb",
            "bkkkkkBBBBBBBBkb",
            "bkkBBBBBBBBBBBkb",
            "bkkBBBBBBBBBBBkb",
            "bkkBBBBBBBBBBBkb",
            "bkkBBBBBBBBBBBkb",
            "bkkBBBBBBBBBBBkb",
            "bkkBBBBBBBBBBBkb",
            "bbbbbbbbbbbbbbbb",
        ],
    },
}

GROUND_ASCII = """\
##########
#........#
#........#
#........#
#........#
#........#
#........#
##########"""
GROUND_LEGEND = {"#": "brick", ".": "stone"}

OBJECTS_ASCII = """\
.....D....
..........
..S...m...
....@.....
..........
..p...g.>.
.........."""
OBJECTS_LEGEND = {
    ".": "", "D": "door", "S": "sword", "m": "slime",
    "@": "player", "p": "potion", "g": "goblin", ">": "stairs",
}
