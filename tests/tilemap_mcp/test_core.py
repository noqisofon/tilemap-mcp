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


# ---------- sprite sheets: Urizen-like layout (12px tiles, 1px margin, 1px spacing, black background) ----------

def make_sheet(cols=5, rows=3, tile=12, margin=1, spacing=1, filled=None, trailing_margin=True):
    """Opaque black sheet. Each cell in `filled` gets a 6x6 block of its colour at cell offset (3, 3)."""
    from PIL import Image

    filled = filled or {}
    extra = margin if trailing_margin else 0
    w = margin + cols * (tile + spacing) - spacing + extra
    h = margin + rows * (tile + spacing) - spacing + extra
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    for (r, c), colour in filled.items():
        x0, y0 = margin + c * (tile + spacing), margin + r * (tile + spacing)
        for y in range(3, 9):
            for x in range(3, 9):
                img.putpixel((x0 + x, y0 + y), colour + (255,))
    return img


URIZEN_LIKE = {(2, 0): (255, 0, 0), (2, 2): (0, 255, 0), (2, 3): (0, 0, 255), (0, 4): (255, 255, 0)}


def test_sheet_grid_with_margin_and_spacing():
    from tilemap_mcp.tilemap import sheet_cell_box, sheet_grid

    assert sheet_grid(make_sheet(cols=5, rows=3), 12, 1, 1) == (5, 3)
    assert sheet_grid(make_sheet(cols=5, rows=3, trailing_margin=False), 12, 1, 1) == (5, 3)
    assert sheet_grid(make_sheet(cols=62, rows=41), 12, 1, 1) == (62, 41)
    # the exact arithmetic of the PowerShell probe: startX = 1 + col * 13
    assert sheet_cell_box(3, 2, 12, 1, 1) == (1 + 3 * 13, 1 + 2 * 13, 1 + 3 * 13 + 12, 1 + 2 * 13 + 12)


def test_inspect_sheet_finds_content():
    from tilemap_mcp.tilemap import inspect_sheet

    sheet = make_sheet(filled=URIZEN_LIKE)
    img, info = inspect_sheet(sheet, 12, 1, 1, background="#000000")
    assert info["grid"] == {"cols": 5, "rows": 3}
    assert info["non_empty_cols_by_row"] == {"0": [4], "2": [0, 2, 3]}
    assert info["non_empty_count"] == 4 and info["empty_count"] == 11
    assert info["content_pixels"]["2,3"] == 36
    assert img.width > 100 and img.height > 60
    # without `background`, opaque black counts as content -> everything is "non-empty"
    _, info2 = inspect_sheet(sheet, 12, 1, 1)
    assert info2["non_empty_count"] == 15
    # part of a sheet
    _, info3 = inspect_sheet(sheet, 12, 1, 1, background="#000000", row_range=[2, 3], col_range=[0, 3])
    assert info3["non_empty_cols_by_row"] == {"2": [0, 2]}
    for bad in ([3, 4], [2, 2], [0, 9], [1]):
        try:
            inspect_sheet(sheet, 12, 1, 1, row_range=bad)
        except TilemapError:
            continue
        raise AssertionError(f"accepted row_range {bad}")


def test_import_sheet_cell_exact_size():
    p = Project(12)
    sheet = make_sheet(filled=URIZEN_LIKE)
    p.import_sheet_cell("blue", sheet, col=3, row=2, margin=1, spacing=1, transparent_color="#000000")
    img = p.tile_image("blue")
    assert img.size == (12, 12)
    assert img.getpixel((5, 5)) == (0, 0, 255, 255)          # the right cell was cut out
    assert img.getpixel((0, 0))[3] == 0                      # black background became transparent
    assert img.getpixel((2, 2))[3] == 0 and img.getpixel((3, 3))[3] == 255
    # without transparent_color the black stays opaque
    p.import_sheet_cell("blue_bg", sheet, col=3, row=2, margin=1, spacing=1)
    assert p.tile_image("blue_bg").getpixel((0, 0)) == (0, 0, 0, 255)
    # every other cell is really different (margin / spacing are honoured)
    p.import_sheet_cell("red", sheet, col=0, row=2, margin=1, spacing=1)
    p.import_sheet_cell("green", sheet, col=2, row=2, margin=1, spacing=1)
    assert p.tile_image("red").getpixel((5, 5)) == (255, 0, 0, 255)
    assert p.tile_image("green").getpixel((5, 5)) == (0, 255, 0, 255)
    p.import_sheet_cell("empty", sheet, col=1, row=2, margin=1, spacing=1, transparent_color="#000000")
    assert p.tile_image("empty").getchannel("A").getextrema() == (0, 0)  # fully transparent


def test_import_sheet_cell_size_mismatch():
    p = Project(16)
    sheet = make_sheet(filled=URIZEN_LIKE)
    try:
        p.import_sheet_cell("x", sheet, col=3, row=2, tile=12, margin=1, spacing=1)
    except TilemapError as e:
        assert "new_project(tile_size=12)" in str(e), e
    else:
        raise AssertionError("silently resized a 12px tile into a 16px project")
    assert "x" not in p.tiles
    p.import_sheet_cell("padded", sheet, col=3, row=2, tile=12, margin=1, spacing=1,
                        transparent_color="#000000", fit="pad")
    assert p.tile_image("padded").size == (16, 16)
    assert p.tile_image("padded").getpixel((3 + 2, 3 + 2)) == (0, 0, 255, 255)  # centred: +2 px
    p.import_sheet_cell("scaled", sheet, col=3, row=2, tile=12, margin=1, spacing=1, fit="scale")
    assert p.tile_image("scaled").size == (16, 16)
    try:
        p.import_sheet_cell("y", sheet, col=1, row=1, tile=12, margin=1, spacing=1, fit="bogus")
    except TilemapError:
        pass
    else:
        raise AssertionError("accepted fit='bogus'")
    for col, row in ((5, 0), (0, 3), (-1, 0)):
        try:
            p.import_sheet_cell("z", sheet, col=col, row=row, tile=12, margin=1, spacing=1, fit="pad")
        except TilemapError as e:
            assert "outside the sheet grid" in str(e)
        else:
            raise AssertionError(f"accepted cell {(col, row)}")


def test_slice_tileset_with_margin_skip_empty_and_limits():
    p = Project(12)
    sheet = make_sheet(filled=URIZEN_LIKE)
    names = p.slice_tileset(sheet, prefix="u", tile_size=12, margin=1, spacing=1,
                            background="#000000", skip_empty=True, transparent_color="#000000")
    assert names == ["u_0_4", "u_2_0", "u_2_2", "u_2_3"], names
    assert p.tile_image("u_2_3").getpixel((5, 5)) == (0, 0, 255, 255)
    # only a region
    q = Project(12)
    assert q.slice_tileset(sheet, prefix="r", margin=1, spacing=1, row_range=[2, 3], col_range=[1, 3]) == ["r_2_1", "r_2_2"]
    # too many tiles are refused before anything is imported
    q2 = Project(12)
    try:
        q2.slice_tileset(sheet, margin=1, spacing=1, max_tiles=5)
    except TilemapError as e:
        assert "max_tiles" in str(e)
    else:
        raise AssertionError("ignored max_tiles")
    assert not q2.tiles
    # mismatched size is refused as a whole, nothing imported
    q3 = Project(16)
    try:
        q3.slice_tileset(sheet, tile_size=12, margin=1, spacing=1)
    except TilemapError:
        pass
    else:
        raise AssertionError("mismatch accepted")
    assert not q3.tiles


def test_slice_tileset_old_behaviour_unchanged():
    """Plain sheets (no margin/spacing, project tile size) still work exactly as before."""
    from PIL import Image

    sheet = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    sheet.putpixel((3, 3), (255, 0, 0, 255))
    sheet.putpixel((16 + 4, 4), (0, 255, 0, 255))
    p = Project(16)
    assert p.slice_tileset(sheet, prefix="s") == ["s_0_0", "s_0_1"]
    assert p.tile_image("s_0_0").getpixel((3, 3)) == (255, 0, 0, 255)
    assert p.tile_image("s_0_1").getpixel((4, 4)) == (0, 255, 0, 255)


def test_startup_reports_data_dir():
    """Where data goes must be visible: warn on a relative / missing TILEMAP_DIR, stay quiet on an absolute one."""
    import contextlib
    import io

    def run_main(env_value):
        old = os.environ.get("TILEMAP_DIR")
        real_run = server.mcp.run
        server.mcp.run = lambda *a, **k: None          # do not actually serve
        buf = io.StringIO()
        try:
            if env_value is None:
                os.environ.pop("TILEMAP_DIR", None)
            else:
                os.environ["TILEMAP_DIR"] = env_value
            with contextlib.redirect_stderr(buf):
                server.main()
        finally:
            server.mcp.run = real_run
            if old is None:
                os.environ.pop("TILEMAP_DIR", None)
            else:
                os.environ["TILEMAP_DIR"] = old
        return buf.getvalue()

    absolute = str(Path(tempfile.mkdtemp(prefix="tilemap_abs_")))
    out = run_main(absolute)
    assert "data dir:" in out and "warning" not in out and "not set" not in out, out
    out = run_main("./tilemap_data")
    assert "relative path" in out and "Use an absolute path" in out, out
    out = run_main(None)
    assert "TILEMAP_DIR is not set" in out, out
    # every project summary the agent sees names the folder, so it can tell the user
    assert f"data_dir={server.DATA_DIR}" in server.list_tiles()
    assert f"data_dir={server.DATA_DIR}" in server.new_project(16)


def test_named_outputs_stay_inside_data_dir():
    """render/export_atlas `name` files results apart, and can never point outside the data folder."""
    old = server._project
    server._project = project(6, 4)
    data = server.DATA_DIR.resolve()
    try:
        # without a name: the old fixed locations
        server.render(scale=1)
        assert (data / "render.png").is_file()
        server.export_atlas()
        assert (data / "atlas.png").is_file() and (data / "tiled_map.json").is_file()

        # with a name: separate files, nothing overwritten
        server.render(scale=2, name="room A")
        server.render(scale=3, name="room_b")
        from PIL import Image
        assert Image.open(data / "renders" / "room A.png").size == (6 * 16 * 2, 4 * 16 * 2)
        assert Image.open(data / "renders" / "room_b.png").size == (6 * 16 * 3, 4 * 16 * 3)
        msg = server.export_atlas(name="dungeon_b1")
        assert str(data / "exports" / "dungeon_b1") in msg, msg
        for f in ("atlas.png", "atlas.json", "tiled_map.json"):
            assert (data / "exports" / "dungeon_b1" / f).is_file(), f

        # names cannot escape (checked before anything is written)
        before = {p for p in data.parent.rglob("*")}
        for bad in ("../x", "..\\x", "a/b", "/etc/passwd", "C:\\x", ".hidden", "", "x..y"):
            for call in (lambda n=bad: server.render(scale=1, name=n), lambda n=bad: server.export_atlas(name=n)):
                try:
                    call()
                except Exception as e:  # ToolError wrapping TilemapError
                    assert "invalid" in str(e), (bad, e)
                else:
                    raise AssertionError(f"accepted name {bad!r}")
        assert {p for p in data.parent.rglob("*")} == before, "a rejected name still wrote something"
    finally:
        server._project = old


def test_instructions_tell_the_agent_where_files_go():
    text = server.mcp.instructions if hasattr(server.mcp, "instructions") else None
    if text is None:  # mcp 2.x keeps it on a settings object
        text = getattr(getattr(server.mcp, "settings", None), "instructions", None)
    assert text and str(server.DATA_DIR) in text and "cannot choose another location" in text, text


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"{len(tests)} passed")
