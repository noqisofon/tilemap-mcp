"""Drive tilemap_mcp over real MCP stdio, like an agent would, and check the results."""
import asyncio
import base64
import os
import sys
from pathlib import Path

# Ensure src/ is on sys.path
SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tilemap_mcp.sprites import (GROUND_ASCII, GROUND_LEGEND, OBJECTS_ASCII, OBJECTS_LEGEND, SPRITES)

DATA = Path("mcp_out").resolve()


async def call(s, tool, **args):
    return await s.call_tool(tool, args)


async def main():
    env = {**os.environ, "TILEMAP_DIR": str(DATA)}
    # Add SRC to PYTHONPATH so python -m tilemap_mcp finds the package
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + pythonpath if pythonpath else "")

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tilemap_mcp"],
        env=env,
    )
    async with stdio_client(params) as (rd, wr):
        async with ClientSession(rd, wr) as s:
            await s.initialize()
            tools = [t.name for t in (await s.list_tools()).tools]
            print("tools:", tools)

            def is_err(res):
                return getattr(res, "is_error", getattr(res, "isError", False))

            await call(s, "new_project", tile_size=16)
            for name, t in SPRITES.items():
                r = await call(s, "define_tile", name=name, palette=t["palette"], rows=t["rows"])
                assert not is_err(r), r
            await call(s, "create_map", width=10, height=8)
            r = await call(s, "set_map_from_ascii", layer="ground", grid=GROUND_ASCII, legend=GROUND_LEGEND)
            assert not is_err(r), r
            r = await call(s, "set_map_from_ascii", layer="objects", grid=OBJECTS_ASCII, legend=OBJECTS_LEGEND)
            assert not is_err(r), r

            # cell query + ascii round trip
            r = await call(s, "get_cell", x=4, y=3)
            print("get_cell(4,3):", r.content[0].text)
            r = await call(s, "dump_layer_ascii", layer="objects")
            print("dump objects:", r.content[0].text[:120], "...")

            # render returns an image content block
            r = await call(s, "render", scale=4, show_grid=True)
            kinds = [c.type for c in r.content]
            print("render content:", kinds)
            assert "image" in kinds
            img = next(c for c in r.content if c.type == "image")
            (DATA / "from_client.png").write_bytes(base64.b64decode(img.data))

            r = await call(s, "preview_tile", name="sword")
            assert any(c.type == "image" for c in r.content)

            # error paths should be readable, not crashes
            bad = await call(s, "place", layer="objects", x=99, y=0, tile="sword")
            print("out-of-range ->", is_err(bad), bad.content[0].text)
            bad = await call(s, "place", layer="objects", x=0, y=0, tile="nope")
            print("unknown tile ->", is_err(bad), bad.content[0].text[:80])
            bad = await call(s, "define_tile", name="x", palette={"a": "#fff"}, rows=["aaa"])
            print("bad rows     ->", is_err(bad), bad.content[0].text)
            bad = await call(s, "set_map_from_ascii", layer="objects", grid="?", legend={"#": "brick"})
            print("bad legend   ->", is_err(bad), bad.content[0].text)

            r = await call(s, "export_atlas", columns=4)
            print(r.content[0].text)

            # Test 1: Tile cloning & transformation
            r = await call(s, "clone_tile", src_name="sword", new_name="sword_left", flip_h=True)
            assert not is_err(r), r
            print("clone_tile:", r.content[0].text)

            # Test 2: Properties
            r = await call(s, "set_tile_properties", name="brick", solid=True, tags=["obstacle"])
            assert not is_err(r), r
            r = await call(s, "get_tile_properties", name="brick")
            print("get_tile_properties:", r.content[0].text)

            # Test 3: Map expansion & corridor carving (reproducing image 2!)
            r = await call(s, "resize_map", new_width=20, new_height=14, offset_x=2, offset_y=2)
            assert not is_err(r), r
            print("resize_map:", r.content[0].text)

            # Open a gap in the right wall and carve a corridor to the right
            r = await call(s, "place", layer="ground", x=11, y=5, tile="stone")
            r = await call(s, "place", layer="ground", x=11, y=6, tile="stone")
            r = await call(s, "carve_corridor", x1=12, y1=5, x2=18, y2=5, width=2, floor_tile="stone", wall_tile="brick")
            assert not is_err(r), r
            print("carve_corridor:", r.content[0].text)

            # Place stairs at the end of corridor
            r = await call(s, "place", layer="objects", x=18, y=5, tile="stairs")
            assert not is_err(r), r

            # Test 4: Viewport & Fog of War rendering (like image 2)
            r = await call(
                s, "render", scale=4, show_grid=False,
                view_rect=[0, 0, 20, 14],
                fog_of_war=True,
                light_sources=[{"x": 6, "y": 5, "radius": 7}, {"x": 16, "y": 5, "radius": 4}],
            )
            assert not is_err(r), r
            print("fog_of_war render OK")

            # Test 5: Prefab save & stamp
            r = await call(s, "save_prefab", name="corridor_end", x=17, y=4, w=3, h=4)
            assert not is_err(r), r
            print("save_prefab:", r.content[0].text)

            # Test 6: Animation (player walking right)
            frames = [
                [{"layer": "objects", "x": 6, "y": 5, "tile": "player"}],
                [{"layer": "objects", "x": 6, "y": 5, "tile": None}, {"layer": "objects", "x": 7, "y": 5, "tile": "player"}],
                [{"layer": "objects", "x": 7, "y": 5, "tile": None}, {"layer": "objects", "x": 8, "y": 5, "tile": "player"}],
            ]
            r = await call(s, "render_animation", frames=frames, scale=4, duration=150, gif_name="player_walk.gif")
            assert not is_err(r), r
            print("render_animation:", r.content[1].text if len(r.content) > 1 else r.content[0].text)

            # Test 7: Project save and load
            r = await call(s, "save_project_as", name="dungeon_room2")
            assert not is_err(r), r
            r = await call(s, "list_projects")
            print("list_projects:", r.content[0].text)
    print("files:", sorted(p.name for p in DATA.iterdir()))


if __name__ == "__main__":
    asyncio.run(main())
