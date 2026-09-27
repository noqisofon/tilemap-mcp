"""Core regression tests (no MCP needed for most): python -m tests.tilemap_mcp.test_core"""
import os
import sys
import tempfile
from pathlib import Path

# Ensure src/ is on sys.path when running directly
SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("TILEMAP_DIR", str(Path(tempfile.mkdtemp(prefix="tilemap_test_")) / "data"))

from tilemap_mcp import server
from tilemap_mcp.sprites import SPRITES
from tilemap_mcp.tilemap import Project, TilemapError


def project(w=24, h=16) -> Project:
    p = Project(16)
    for n, t in SPRITES.items():
        p.define_tile(n, t["palette"], t["rows"])
    p.create_map(w, h)
    return p


def cells(p: Project, tile: str) -> set[tuple[int, int]]:
    g = p.layers[0]["grid"]
    return {(x, y) for y, row in enumerate(g) for x, t in enumerate(row) if t == tile}


def test_corridor_walls_are_one_tile_thick():
    for width in (1, 2, 3):
        p = project()
        p.carve_corridor(3, 3, 14, 9, width=width, floor_tile="stone", wall_tile="brick")
        floor, wall = cells(p, "stone"), cells(p, "brick")
        assert floor, width
        # every wall touches the corridor (8-neighbourhood) ...
        for wx, wy in wall:
            assert any((wx + dx, wy + dy) in floor for dx in (-1, 0, 1) for dy in (-1, 0, 1)), (width, wx, wy)
        # ... and every empty cell touching the corridor is a wall (sealed)
        for fx, fy in floor:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    c = (fx + dx, fy + dy)
                    if 0 <= c[0] < p.width and 0 <= c[1] < p.height:
                        assert c in floor or c in wall, (width, c)


def test_straight_corridor_ends_square():
    p = project()
    p.carve_corridor(2, 5, 10, 5, width=2, floor_tile="stone", wall_tile="brick")
    floor = cells(p, "stone")
    assert floor == {(x, y) for x in range(2, 12) for y in (5, 6)}, sorted(floor)


def test_corridor_keeps_existing_walls_and_clears_objects():
    p = project()
    p.fill("ground", 0, 0, 24, 16, "brick")  # solid rock
    p.place("objects", 5, 5, "slime")
    p.carve_corridor(4, 5, 8, 5, width=1, floor_tile="stone", wall_tile="door")
    assert p.get_cell(5, 5) == {"ground": "stone", "objects": None}
    assert p.get_cell(5, 4)["ground"] == "brick"  # not overwritten by wall_tile


def test_resize_keeps_tiles():
    p = project(10, 8)
    p.place("objects", 1, 1, "sword")
    p.resize_map(20, 14, offset_x=2, offset_y=3)
    assert p.get_cell(3, 4)["objects"] == "sword"
    p.resize_map(3, 3)  # shrink: cell falls off, no crash
    assert p.width == 3


def test_flip_rotate_roundtrip():
    p = project()
    p.clone_tile("sword", "a", rotate=90)
    p.clone_tile("a", "b", rotate=270)
    assert p.tiles["b"]["rows"] == p.tiles["sword"]["rows"]
    p.clone_tile("sword", "c", flip_h=True)
    p.clone_tile("c", "d", flip_h=True)
    assert p.tiles["d"]["rows"] == p.tiles["sword"]["rows"]


def test_import_roundtrip():
    p = project()
    p.import_tile_from_image("slime2", p.tile_image("slime"))
    assert p.tile_image("slime2").tobytes() == p.tile_image("slime").tobytes()


def test_safe_names():
    for bad in ("../x", "..\\x", "a/b", ".hidden", "", "x..y", "C:evil"):
        try:
            server._safe_name(bad)
        except TilemapError:
            continue
        raise AssertionError(f"accepted {bad!r}")
    for good in ("dungeon_b1", "town main", "ダンジョン1F", "lvl-2.v3"):
        assert server._safe_name(good) == good
    # and the tools really refuse to write outside the data dir
    for fn, arg in ((server.save_project_as, "../../escaped"),):
        try:
            fn(arg)
        except Exception as e:  # ToolError wrapping TilemapError
            assert "invalid" in str(e), e
        else:
            raise AssertionError("path traversal accepted")
    assert not (server.DATA_DIR.parent / "escaped.json").exists()
    assert not (server.DATA_DIR / "escaped.json").exists()


def test_tiled_json_export():
    p = project(10, 8)
    p.set_tile_properties("brick", solid=True, tags=["wall"])
    p.place("ground", 0, 0, "brick")
    p.place("objects", 1, 1, "sword")
    tiled = p.to_tiled_json()
    assert tiled["width"] == 10
    assert tiled["height"] == 8
    assert tiled["tilewidth"] == 16
    assert len(tiled["layers"]) == 2
    assert tiled["layers"][0]["data"][0] > 0  # brick gid
    assert tiled["layers"][0]["data"][1] == 0  # empty
    # Check properties in tileset
    brick_tile = next(t for t in tiled["tilesets"][0]["tiles"] if t["type"] == "brick")
    assert any(prop["name"] == "solid" and prop["value"] is True for prop in brick_tile["properties"])
    # keys that Tiled itself always writes (strict readers need them)
    assert tiled["nextlayerid"] == len(tiled["layers"]) + 1
    assert tiled["nextobjectid"] == 1


def test_tiled_export_rebuilds_same_picture():
    """atlas.png + tiled_map.json alone must be enough to redraw exactly what render() draws."""
    import json
    import tempfile

    from PIL import Image, ImageChops

    p = project(12, 9)
    p.fill("ground", 0, 0, 12, 9, "stone")
    p.border("ground", 0, 0, 12, 9, "brick")
    p.place("objects", 3, 4, "slime")
    p.place("objects", 8, 2, "sword")
    out = Path(tempfile.mkdtemp(prefix="tiled_")) / "out"
    p.export_atlas(out, columns=4)
    tm = json.loads((out / "tiled_map.json").read_text())
    ts = tm["tilesets"][0]
    atlas = Image.open(out / ts["image"]).convert("RGBA")
    assert atlas.size == (ts["imagewidth"], ts["imageheight"])
    n = tm["tilewidth"]
    canvas = Image.new("RGBA", (tm["width"] * n, tm["height"] * n), (0, 0, 0, 255))
    for layer in tm["layers"]:
        for i, gid in enumerate(layer["data"]):
            if gid == 0:
                continue
            idx = gid - ts["firstgid"]
            sx, sy = (idx % ts["columns"]) * n, (idx // ts["columns"]) * n
            canvas.alpha_composite(
                atlas.crop((sx, sy, sx + n, sy + n)), ((i % tm["width"]) * n, (i // tm["width"]) * n)
            )
    assert ImageChops.difference(canvas, p.render(scale=1)).getbbox() is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"{len(tests)} passed")
