"""MCP server: let an AI agent build tile/sprite images by name and coordinate.

Run (stdio):  python server.py
Env:          TILEMAP_DIR   where projects / render.png / atlas go (default ./tilemap_data)
"""
from __future__ import annotations

import functools
import io
import os
import re
from pathlib import Path
from typing import Optional

from PIL import Image as PILImage

try:
    from mcp.server.fastmcp import FastMCP, Image
    from mcp.server.fastmcp.exceptions import ToolError
except (ModuleNotFoundError, ImportError):
    from mcp.server.mcpserver import MCPServer as FastMCP
    from mcp.server.mcpserver.utilities.types import Image
    from mcp.server.mcpserver.exceptions import ToolError

try:
    from tilemap_mcp.tilemap import Project, TilemapError
except ImportError:
    from tilemap import Project, TilemapError

DATA_DIR = Path(os.environ.get("TILEMAP_DIR", "tilemap_data")).resolve()
PROJECT_FILE = DATA_DIR / "project.json"
PROJECTS_DIR = DATA_DIR / "projects"

mcp = FastMCP(
    "tilemap",
    instructions=(
        "Build pixel-art tile maps and sprites by name and coordinate. Workflow: "
        "new_project -> define_tile (text pixel art) / clone_tile / import_tile_from_file -> "
        "create_map -> set_map_from_ascii / place / fill / border / carve_corridor -> "
        "render (optionally with view_rect camera window or fog_of_war) -> export_atlas. "
        "Coordinates are 0-based (x=column, y=row) from the top-left. "
        "Layers draw bottom to top with alpha, so put sprites on an upper layer over a floor tile."
    ),
)

_project: Project = Project.load(PROJECT_FILE) if PROJECT_FILE.exists() else Project()


def _save() -> None:
    _project.save(PROJECT_FILE)


# letters (incl. Japanese), digits, _ - . and spaces; no path separators, no leading dot, no ".."
_SAFE_NAME = re.compile(r"[\w\-. ]+")


def _safe_name(name: str, what: str = "name") -> str:
    """Names from the agent become file names: refuse anything that could leave the data dir."""
    if not _SAFE_NAME.fullmatch(name) or name.startswith(".") or ".." in name:
        raise TilemapError(
            f"invalid {what} {name!r}: use letters, digits, '_', '-', '.' or spaces only "
            f"(no slashes, no '..', no leading '.')"
        )
    return name


def _summary() -> str:
    prefabs = f", prefabs={sorted(_project.prefabs)}" if _project.prefabs else ""
    return (
        f"tile_size={_project.tile_size}, map={_project.width}x{_project.height}, "
        f"layers={[l['name'] for l in _project.layers]}, tiles={sorted(_project.tiles)}{prefabs}"
    )


def _guard(fn):
    """Turn TilemapError / ValueError into a readable ToolError for clean agent feedback."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except TilemapError as e:
            raise ToolError(str(e)) from None
        except ValueError as e:
            raise ToolError(str(e)) from None
    return wrapper


# ==================== PROJECT MANAGEMENT ====================

@mcp.tool()
@_guard
def new_project(tile_size: int = 16) -> str:
    """Start a fresh project (discards current tileset and map). tile_size in pixels (8, 16, 32...)."""
    global _project
    if not (4 <= tile_size <= 64):
        raise TilemapError("tile_size must be 4..64")
    _project = Project(tile_size)
    _save()
    return "new project. " + _summary()


@mcp.tool()
@_guard
def save_project_as(name: str) -> str:
    """Save the current project to a named file under projects/ (e.g. 'level_1', 'town')."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    target = PROJECTS_DIR / f"{_safe_name(name, 'project name')}.json"
    _project.save(target)
    return f"saved project as {name!r} to {target}"


@mcp.tool()
@_guard
def load_project(name: str) -> str:
    """Load a named project from projects/."""
    global _project
    target = PROJECTS_DIR / f"{_safe_name(name, 'project name')}.json"
    if not target.exists():
        raise TilemapError(f"project {name!r} not found in {PROJECTS_DIR}")
    _project = Project.load(target)
    _save()
    return f"loaded project {name!r}. " + _summary()


@mcp.tool()
@_guard
def list_projects() -> list[str]:
    """List all saved project names."""
    if not PROJECTS_DIR.exists():
        return []
    return sorted(p.stem for p in PROJECTS_DIR.glob("*.json"))


# ==================== TILE DEFINITION & MANIPULATION ====================

@mcp.tool()
@_guard
def define_tile(
    name: str,
    palette: dict[str, str],
    rows: list[str],
    solid: Optional[bool] = None,
    tags: Optional[list[str]] = None,
    meta: Optional[dict] = None,
) -> str:
    """Define (or redefine) a tile from text pixel art.

    palette: single-char -> color, e.g. {"r": "#c0392b", "k": "#000"}. '#rgb', '#rrggbb', '#rrggbbaa'.
    rows: exactly tile_size strings, each exactly tile_size chars. '.' or ' ' = transparent.
    solid: optional collision flag (True = impassable wall/obstacle).
    tags: optional semantic tags e.g. ["wall", "metal", "interactable"].
    meta: optional free-form properties exported to atlas.json (e.g. {"damage": 3}).
    """
    _project.define_tile(name, palette, rows, solid=solid, tags=tags, meta=meta)
    _save()
    return f"defined {name!r}. tiles now: {sorted(_project.tiles)}"


@mcp.tool()
@_guard
def clone_tile(
    src_name: str,
    new_name: str,
    flip_h: bool = False,
    flip_v: bool = False,
    rotate: int = 0,
) -> str:
    """Create a new tile by transforming an existing one.

    rotate: 0, 90, 180, or 270 degrees clockwise.
    flip_h: horizontal mirror.
    flip_v: vertical mirror.
    Useful for character facings, wall corners, directional stairs, and symmetry.
    """
    _project.clone_tile(src_name, new_name, flip_h=flip_h, flip_v=flip_v, rotate=rotate)
    _save()
    return f"cloned {src_name!r} -> {new_name!r} (rotate={rotate}, flip_h={flip_h}, flip_v={flip_v})"


@mcp.tool()
@_guard
def import_tile_from_file(
    name: str,
    file_path: str,
    solid: Optional[bool] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """Import an image file (PNG/JPG) as a tile, auto-extracting colors and text pixels."""
    p = Path(file_path).resolve()
    if not p.exists():
        raise TilemapError(f"file not found: {file_path}")
    img = PILImage.open(p)
    _project.import_tile_from_image(name, img, solid=solid, tags=tags)
    _save()
    return f"imported {name!r} from {p.name}"


@mcp.tool()
@_guard
def slice_tileset(file_path: str, prefix: str = "tile", solid: Optional[bool] = None) -> list[str]:
    """Slice an entire sprite sheet into tile_size x tile_size tiles and import them."""
    p = Path(file_path).resolve()
    if not p.exists():
        raise TilemapError(f"file not found: {file_path}")
    img = PILImage.open(p)
    imported = _project.slice_tileset(img, prefix=prefix, solid=solid)
    _save()
    return imported


@mcp.tool()
@_guard
def set_tile_properties(
    name: str,
    solid: Optional[bool] = None,
    tags: Optional[list[str]] = None,
    meta: Optional[dict] = None,
) -> str:
    """Set game properties on a tile (collision, tags, custom meta) for game engine exports."""
    _project.set_tile_properties(name, solid=solid, tags=tags, meta=meta)
    _save()
    return f"updated properties for {name!r}: {_project.get_tile_properties(name)}"


@mcp.tool()
@_guard
def get_tile_properties(name: str) -> dict:
    """Get metadata properties of a tile."""
    return _project.get_tile_properties(name)


@mcp.tool()
@_guard
def preview_tile(name: str, scale: int = 16) -> Image:
    """Render one tile enlarged on a checkerboard, to inspect the pixel art."""
    img = _project.tile_image(name)
    n = _project.tile_size
    checker = PILImage.new("RGBA", img.size, (60, 60, 60, 255))
    for y in range(n):
        for x in range(n):
            if (x + y) % 2:
                checker.putpixel((x, y), (90, 90, 90, 255))
    checker.alpha_composite(img)
    big = checker.resize((n * scale, n * scale), PILImage.NEAREST)
    buf = io.BytesIO()
    big.save(buf, "PNG")
    return Image(data=buf.getvalue(), format="png")


@mcp.tool()
@_guard
def list_tiles() -> str:
    """Summarize the project: tile size, map size, layers, tile names, prefabs."""
    return _summary()


# ==================== MAP CONSTRUCTION & EDITING ====================

@mcp.tool()
@_guard
def create_map(width: int, height: int, layers: Optional[list[str]] = None) -> str:
    """Create an empty map of width x height tiles (discards old map, keeps tiles)."""
    _project.create_map(width, height, layers)
    _save()
    return _summary()


@mcp.tool()
@_guard
def resize_map(new_width: int, new_height: int, offset_x: int = 0, offset_y: int = 0) -> str:
    """Expand or shrink the map without losing existing placed tiles.

    offset_x, offset_y: where existing tiles should shift (e.g. offset_x=5 moves existing map 5 tiles right).
    """
    _project.resize_map(new_width, new_height, offset_x, offset_y)
    _save()
    return f"resized map to {new_width}x{new_height} (offset=({offset_x},{offset_y})). " + _summary()


@mcp.tool()
@_guard
def add_layer(name: str) -> str:
    """Add an empty layer on top of existing layers."""
    _project.add_layer(name)
    _save()
    return _summary()


@mcp.tool()
@_guard
def place(layer: str, x: int, y: int, tile: Optional[str] = None) -> str:
    """Put one tile at (x, y) on a layer. tile omitted/null erases the cell."""
    _project.place(layer, x, y, tile)
    _save()
    return f"{layer}[{x},{y}] = {tile}"


@mcp.tool()
@_guard
def fill(layer: str, x: int, y: int, w: int, h: int, tile: Optional[str] = None) -> str:
    """Fill the w x h rectangle whose top-left is (x, y). tile omitted/null erases it."""
    _project.fill(layer, x, y, w, h, tile)
    _save()
    return f"filled {layer} {w}x{h} at ({x},{y}) with {tile}"


@mcp.tool()
@_guard
def border(layer: str, x: int, y: int, w: int, h: int, tile: str) -> str:
    """Draw a 1-tile-thick rectangle outline (walls around a room)."""
    _project.border(layer, x, y, w, h, tile)
    _save()
    return f"border {layer} {w}x{h} at ({x},{y}) with {tile}"


@mcp.tool()
@_guard
def carve_corridor(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    width: int = 2,
    floor_tile: str = "stone",
    wall_tile: Optional[str] = "brick",
    floor_layer: str = "ground",
    clear_layer: Optional[str] = "objects",
) -> str:
    """Dig an L-shaped corridor: horizontal from (x1, y1) to (x2, y1), then vertical to (x2, y2).

    (x, y) is the top-left of a width x width brush dragged along the path, so a corridor of
    width 2 ending at (18, 5) occupies x 18-19 and y 5-6 at its end. Lays floor tiles, clears
    the obstacle layer, and puts a 1-tile wall on every empty cell touching the corridor
    (existing tiles are never overwritten).
    """
    _project.carve_corridor(
        x1, y1, x2, y2,
        width=width,
        floor_tile=floor_tile,
        wall_tile=wall_tile,
        floor_layer=floor_layer,
        clear_layer=clear_layer,
    )
    _save()
    return f"carved corridor from ({x1},{y1}) to ({x2},{y2}) width={width}"


@mcp.tool()
@_guard
def set_map_from_ascii(
    layer: str, grid: str, legend: dict[str, Optional[str]], x: int = 0, y: int = 0
) -> str:
    """Stamp an ASCII grid onto a layer, top-left at (x, y)."""
    _project.set_from_ascii(layer, grid, legend, x, y)
    _save()
    return f"stamped {len(grid.splitlines())} rows on {layer!r} at ({x},{y})"


@mcp.tool()
@_guard
def get_cell(x: int, y: int) -> dict:
    """Which tile is at (x, y) on each layer."""
    return _project.get_cell(x, y)


@mcp.tool()
@_guard
def dump_layer_ascii(layer: str) -> dict:
    """Read a layer back as ASCII + legend ('.' = empty), to edit and re-stamp."""
    text, legend = _project.to_ascii(layer)
    return {"grid": text, "legend": legend}


# ==================== PREFABS / TEMPLATES ====================

@mcp.tool()
@_guard
def save_prefab(name: str, x: int, y: int, w: int, h: int, layers: Optional[list[str]] = None) -> str:
    """Save a w x h rectangular area across layers as a reusable prefab stamp (e.g. 'chest_2x2', 'fountain')."""
    _project.save_prefab(name, x, y, w, h, layers)
    _save()
    return f"saved prefab {name!r} ({w}x{h})"


@mcp.tool()
@_guard
def stamp_prefab(name: str, x: int, y: int, ignore_empty: bool = True) -> str:
    """Stamp a saved prefab at (x, y)."""
    _project.stamp_prefab(name, x, y, ignore_empty=ignore_empty)
    _save()
    return f"stamped prefab {name!r} at ({x},{y})"


# ==================== RENDERING & EXPORT ====================

@mcp.tool()
@_guard
def render(
    scale: int = 4,
    layers: Optional[list[str]] = None,
    show_grid: bool = False,
    transparent_background: bool = False,
    view_rect: Optional[list[int]] = None,
    fog_of_war: bool = False,
    light_sources: Optional[list[dict]] = None,
    revealed_cells: Optional[list[list[int]]] = None,
) -> list:
    """Render the map to a PNG (nearest-neighbor upscaled) and return it as an image.

    view_rect: [x, y, w, h] in tiles to render a specific camera view rather than whole map.
    fog_of_war: darkens areas outside light_sources or revealed_cells (dungeon vision / fog).
    light_sources: list of {"x": int, "y": int, "radius": int}.
    revealed_cells: list of [x, y] coordinates that are explored/visible.
    show_grid: overlays coordinate numbers on grid lines.
    """
    if not (1 <= scale <= 32):
        raise ValueError("scale must be 1..32")

    vr = tuple(view_rect) if view_rect else None
    rc = [tuple(c) for c in revealed_cells] if revealed_cells else None

    img = _project.render(
        scale=scale,
        layers=layers,
        show_grid=show_grid,
        background=None if transparent_background else "#000000",
        view_rect=vr,  # type: ignore[arg-type]
        fog_of_war=fog_of_war,
        light_sources=light_sources,
        revealed_cells=rc,  # type: ignore[arg-type]
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / "render.png"
    img.save(out_file)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return [
        Image(data=buf.getvalue(), format="png"),
        f"{img.width}x{img.height}px -> {out_file}",
    ]


@mcp.tool()
@_guard
def render_animation(
    frames: list[list[dict]],
    scale: int = 4,
    duration: int = 200,
    gif_name: str = "animation.gif",
) -> list:
    """Render an animated GIF by applying a sequence of tile changes per frame.

    frames: list of frames, where each frame is a list of {"layer": str, "x": int, "y": int, "tile": str|null}.
    duration: milliseconds per frame.
    gif_name: output filename under tilemap_data/.
    """
    if not frames:
        raise ValueError("frames list cannot be empty")
    imgs = _project.render_animation(frames, scale=scale)

    if not gif_name.lower().endswith(".gif"):
        gif_name += ".gif"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / _safe_name(gif_name, "gif_name")
    imgs[0].save(
        out_file,
        save_all=True,
        append_images=imgs[1:],
        duration=duration,
        loop=0,
    )

    buf = io.BytesIO()
    imgs[0].save(buf, "PNG")
    return [
        Image(data=buf.getvalue(), format="png"),
        f"Wrote animated GIF ({len(imgs)} frames) -> {out_file}",
    ]


@mcp.tool()
@_guard
def export_atlas(columns: int = 8) -> str:
    """Write atlas.png (grid sprite sheet), atlas.json (tile props), and tiled_map.json (Tiled TMJ format)."""
    meta = _project.export_atlas(DATA_DIR, columns)
    _save()
    tiled_note = " and tiled_map.json" if _project.width > 0 else ""
    return f"wrote {DATA_DIR / 'atlas.png'}, atlas.json{tiled_note} ({len(meta['tiles'])} tiles with collision/props)"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

