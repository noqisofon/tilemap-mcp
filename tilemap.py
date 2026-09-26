"""tilemap core: text-defined tiles, layered maps, PNG rendering.

State (tileset + layers) is plain JSON; PNGs are always derived from it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

TRANSPARENT_CHARS = {".", " "}


class TilemapError(ValueError):
    """Raised for user-facing mistakes (bad tile rows, unknown names...)."""


def _parse_color(c: str) -> tuple[int, int, int, int]:
    c = c.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) == 6:
        c += "ff"
    if len(c) != 8:
        raise TilemapError(f"bad color {c!r}: use #rgb, #rrggbb or #rrggbbaa")
    try:
        return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]
    except ValueError:
        raise TilemapError(f"bad color {c!r}: not hex") from None


class Project:
    def __init__(self, tile_size: int = 16):
        self.tile_size = tile_size
        # name -> {"palette": {char: "#hex"}, "rows": [str, ...], "props": dict}
        self.tiles: dict[str, dict] = {}
        self.prefabs: dict[str, dict] = {}
        self.width = 0
        self.height = 0
        # ordered bottom -> top; each: {"name": str, "grid": [[tile|None]*w]*h}
        self.layers: list[dict] = []
        self._img_cache: dict[str, Image.Image] = {}

    # ---------- tiles ----------
    def define_tile(
        self,
        name: str,
        palette: dict[str, str],
        rows: list[str],
        solid: Optional[bool] = None,
        tags: Optional[list[str]] = None,
        meta: Optional[dict] = None,
    ) -> None:
        if not name:
            raise TilemapError("tile name is empty")
        n = self.tile_size
        if len(rows) != n:
            raise TilemapError(f"tile {name!r}: need {n} rows, got {len(rows)}")
        for y, row in enumerate(rows):
            if len(row) != n:
                raise TilemapError(
                    f"tile {name!r}: row {y} has {len(row)} chars, need {n}: {row!r}"
                )
            for ch in row:
                if ch not in palette and ch not in TRANSPARENT_CHARS:
                    raise TilemapError(
                        f"tile {name!r}: row {y} uses {ch!r} which is not in the palette "
                        f"(use '.' for transparent)"
                    )
        for ch, col in palette.items():
            if len(ch) != 1:
                raise TilemapError(f"palette key {ch!r} must be a single character")
            _parse_color(col)
        tile_data: dict = {
            "palette": dict(palette),
            "rows": list(rows),
            "props": {},
        }
        if solid is not None:
            tile_data["props"]["solid"] = solid
        if tags is not None:
            tile_data["props"]["tags"] = list(tags)
        if meta is not None:
            tile_data["props"]["meta"] = dict(meta)
        self.tiles[name] = tile_data
        self._img_cache.pop(name, None)

    def clone_tile(
        self,
        src_name: str,
        new_name: str,
        flip_h: bool = False,
        flip_v: bool = False,
        rotate: int = 0,
    ) -> None:
        """Create a new tile by transforming an existing one (flip and/or 90-degree rotations)."""
        if src_name not in self.tiles:
            raise TilemapError(f"unknown tile {src_name!r}; defined: {sorted(self.tiles)}")
        if rotate not in (0, 90, 180, 270):
            raise TilemapError(f"rotate must be 0, 90, 180, or 270 (got {rotate})")

        src = self.tiles[src_name]
        pal = dict(src["palette"])
        rows = list(src["rows"])
        n = self.tile_size

        if rotate == 90:
            rows = ["".join(rows[n - 1 - x][y] for x in range(n)) for y in range(n)]
        elif rotate == 180:
            rows = [r[::-1] for r in rows[::-1]]
        elif rotate == 270:
            rows = ["".join(rows[x][n - 1 - y] for x in range(n)) for y in range(n)]

        if flip_h:
            rows = [r[::-1] for r in rows]
        if flip_v:
            rows = rows[::-1]

        props = dict(src.get("props", {}))
        self.define_tile(
            new_name,
            pal,
            rows,
            solid=props.get("solid"),
            tags=props.get("tags"),
            meta=props.get("meta"),
        )

    def import_tile_from_image(
        self,
        name: str,
        img: Image.Image,
        solid: Optional[bool] = None,
        tags: Optional[list[str]] = None,
        meta: Optional[dict] = None,
    ) -> None:
        """Import a tile from a PIL image, extracting palette and text rows automatically."""
        n = self.tile_size
        if img.size != (n, n):
            img = img.resize((n, n), Image.NEAREST)
        img = img.convert("RGBA")

        symbols = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!#$%&*+-/;<=>?@^_~"
        color_to_sym: dict[str, str] = {}
        palette: dict[str, str] = {}

        rows = []
        for y in range(n):
            row_chars = []
            for x in range(n):
                r, g, b, a = img.getpixel((x, y))
                if a == 0:
                    row_chars.append(".")
                else:
                    hex_col = f"#{r:02x}{g:02x}{b:02x}" + (f"{a:02x}" if a < 255 else "")
                    if hex_col not in color_to_sym:
                        if len(color_to_sym) >= len(symbols):
                            raise TilemapError(f"tile {name!r} exceeds {len(symbols)} unique colors")
                        sym = symbols[len(color_to_sym)]
                        color_to_sym[hex_col] = sym
                        palette[sym] = hex_col
                    row_chars.append(color_to_sym[hex_col])
            rows.append("".join(row_chars))

        self.define_tile(name, palette, rows, solid=solid, tags=tags, meta=meta)

    def slice_tileset(
        self,
        img: Image.Image,
        prefix: str = "tile",
        solid: Optional[bool] = None,
    ) -> list[str]:
        """Slice a sprite sheet into grid tiles and import them."""
        n = self.tile_size
        cols = img.width // n
        rows = img.height // n
        imported = []
        for y in range(rows):
            for x in range(cols):
                sub = img.crop((x * n, y * n, (x + 1) * n, (y + 1) * n))
                tname = f"{prefix}_{y}_{x}"
                self.import_tile_from_image(tname, sub, solid=solid)
                imported.append(tname)
        return imported

    def set_tile_properties(
        self,
        name: str,
        solid: Optional[bool] = None,
        tags: Optional[list[str]] = None,
        meta: Optional[dict] = None,
    ) -> None:
        if name not in self.tiles:
            raise TilemapError(f"unknown tile {name!r}; defined: {sorted(self.tiles)}")
        props = self.tiles[name].setdefault("props", {})
        if solid is not None:
            props["solid"] = solid
        if tags is not None:
            props["tags"] = list(tags)
        if meta is not None:
            props["meta"] = dict(meta)

    def get_tile_properties(self, name: str) -> dict:
        if name not in self.tiles:
            raise TilemapError(f"unknown tile {name!r}; defined: {sorted(self.tiles)}")
        return self.tiles[name].get("props", {})

    def tile_image(self, name: str) -> Image.Image:
        if name not in self.tiles:
            raise TilemapError(f"unknown tile {name!r}; defined: {sorted(self.tiles)}")
        if name not in self._img_cache:
            t = self.tiles[name]
            n = self.tile_size
            img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
            px = img.load()
            pal = {ch: _parse_color(c) for ch, c in t["palette"].items()}
            for y, row in enumerate(t["rows"]):
                for x, ch in enumerate(row):
                    if ch in pal:
                        px[x, y] = pal[ch]
            self._img_cache[name] = img
        return self._img_cache[name]

    # ---------- map ----------
    def create_map(self, width: int, height: int, layers: Optional[list[str]] = None) -> None:
        if not (1 <= width <= 256 and 1 <= height <= 256):
            raise TilemapError("width/height must be 1..256")
        self.width, self.height = width, height
        self.layers = []
        for lname in layers or ["ground", "objects"]:
            self.add_layer(lname)

    def add_layer(self, name: str) -> None:
        if self.width == 0:
            raise TilemapError("create_map first")
        if any(l["name"] == name for l in self.layers):
            raise TilemapError(f"layer {name!r} already exists")
        self.layers.append(
            {"name": name, "grid": [[None] * self.width for _ in range(self.height)]}
        )

    def _layer(self, name: str) -> dict:
        for l in self.layers:
            if l["name"] == name:
                return l
        raise TilemapError(f"unknown layer {name!r}; layers: {[l['name'] for l in self.layers]}")

    def _check_xy(self, x: int, y: int) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise TilemapError(f"({x},{y}) is outside the {self.width}x{self.height} map")

    def place(self, layer: str, x: int, y: int, tile: Optional[str]) -> None:
        """tile=None (or "") erases the cell."""
        l = self._layer(layer)
        self._check_xy(x, y)
        if tile:
            self.tile_image(tile)  # validates
        l["grid"][y][x] = tile or None

    def fill(self, layer: str, x: int, y: int, w: int, h: int, tile: Optional[str]) -> None:
        self._check_xy(x, y)
        self._check_xy(x + w - 1, y + h - 1)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.place(layer, xx, yy, tile)

    def border(self, layer: str, x: int, y: int, w: int, h: int, tile: str) -> None:
        self._check_xy(x, y)
        self._check_xy(x + w - 1, y + h - 1)
        for xx in range(x, x + w):
            self.place(layer, xx, y, tile)
            self.place(layer, xx, y + h - 1, tile)
        for yy in range(y, y + h):
            self.place(layer, x, yy, tile)
            self.place(layer, x + w - 1, yy, tile)

    def set_from_ascii(
        self, layer: str, grid: str, legend: dict[str, Optional[str]], x: int = 0, y: int = 0
    ) -> None:
        lines = [ln for ln in grid.split("\n")]
        while lines and not lines[-1].strip("\r"):
            lines.pop()
        while lines and not lines[0].strip("\r"):
            lines.pop(0)
        # validate everything before mutating
        for j, line in enumerate(lines):
            line = line.rstrip("\r")
            for i, ch in enumerate(line):
                if ch not in legend:
                    raise TilemapError(
                        f"ascii char {ch!r} at row {j}, col {i} is not in legend "
                        f"(map it to \"\" for empty)"
                    )
                self._check_xy(x + i, y + j)
                if legend[ch]:
                    self.tile_image(legend[ch])  # type: ignore[arg-type]
        for j, line in enumerate(lines):
            for i, ch in enumerate(line.rstrip("\r")):
                self.place(layer, x + i, y + j, legend[ch])

    def get_cell(self, x: int, y: int) -> dict[str, Optional[str]]:
        self._check_xy(x, y)
        return {l["name"]: l["grid"][y][x] for l in self.layers}

    def to_ascii(self, layer: str) -> tuple[str, dict[str, str]]:
        """Dump a layer as ascii + auto legend (a-z A-Z 0-9; '.' = empty)."""
        l = self._layer(layer)
        symbols = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        legend: dict[str, str] = {}
        rev: dict[str, str] = {}
        out = []
        for row in l["grid"]:
            line = ""
            for t in row:
                if t is None:
                    line += "."
                    continue
                if t not in rev:
                    if len(rev) >= len(symbols):
                        raise TilemapError("too many distinct tiles for ascii dump")
                    rev[t] = symbols[len(rev)]
                    legend[rev[t]] = t
                line += rev[t]
            out.append(line)
        return "\n".join(out), legend

    def resize_map(
        self, new_width: int, new_height: int, offset_x: int = 0, offset_y: int = 0
    ) -> None:
        """Resize the map and shift existing tiles by (offset_x, offset_y)."""
        if self.width == 0:
            raise TilemapError("create_map first")
        if not (1 <= new_width <= 512 and 1 <= new_height <= 512):
            raise TilemapError("new_width/new_height must be 1..512")

        for layer in self.layers:
            old_grid = layer["grid"]
            new_grid = [[None] * new_width for _ in range(new_height)]
            for y in range(self.height):
                for x in range(self.width):
                    nx = x + offset_x
                    ny = y + offset_y
                    if 0 <= nx < new_width and 0 <= ny < new_height:
                        new_grid[ny][nx] = old_grid[y][x]
            layer["grid"] = new_grid

        self.width = new_width
        self.height = new_height

    def carve_corridor(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        width: int = 2,
        floor_tile: str = "stone",
        wall_tile: Optional[str] = "brick",
        floor_layer: str = "ground",
        clear_layer: Optional[str] = "objects",
    ) -> None:
        """Carve an L-shaped corridor: horizontal from (x1,y1) to (x2,y1), then vertical to (x2,y2).

        (x, y) is the top-left cell of a width x width brush that is dragged along the path, so a
        straight corridor ends in a clean width x width block. Lays floor tiles, clears the
        obstacle layer, and puts wall tiles on every still-empty floor-layer cell touching the
        corridor (existing tiles, e.g. a room's own walls, are never overwritten).
        """
        self._check_xy(x1, y1)
        self._check_xy(x2, y2)
        if width < 1:
            raise TilemapError("corridor width must be >= 1")

        corridor_cells: set[tuple[int, int]] = set()

        def stamp(bx: int, by: int) -> None:
            for dy in range(width):
                for dx in range(width):
                    corridor_cells.add((bx + dx, by + dy))

        # Horizontal leg from x1 to x2 at y1
        step_x = 1 if x2 >= x1 else -1
        for x in range(x1, x2 + step_x, step_x):
            stamp(x, y1)

        # Vertical leg from y1 to y2 at x2
        step_y = 1 if y2 >= y1 else -1
        for y in range(y1, y2 + step_y, step_y):
            stamp(x2, y)

        # Place floor and clear obstacle layer
        for cx, cy in corridor_cells:
            if 0 <= cx < self.width and 0 <= cy < self.height:
                self.place(floor_layer, cx, cy, floor_tile)
                if clear_layer:
                    try:
                        self.place(clear_layer, cx, cy, None)
                    except TilemapError:
                        pass

        # Border with walls: every empty cell 8-adjacent to the corridor
        if wall_tile:
            fl = self._layer(floor_layer)
            for cx, cy in corridor_cells:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        wx, wy = cx + dx, cy + dy
                        if (
                            0 <= wx < self.width
                            and 0 <= wy < self.height
                            and (wx, wy) not in corridor_cells
                            and fl["grid"][wy][wx] is None
                        ):
                            self.place(floor_layer, wx, wy, wall_tile)

    def save_prefab(
        self, name: str, x: int, y: int, w: int, h: int, layers: Optional[list[str]] = None
    ) -> None:
        """Save a w x h rectangle across layers as a reusable prefab stamp."""
        self._check_xy(x, y)
        self._check_xy(x + w - 1, y + h - 1)
        wanted = set(layers) if layers else None
        layers_data: dict[str, list[list[Optional[str]]]] = {}
        for l in self.layers:
            if wanted is not None and l["name"] not in wanted:
                continue
            grid_slice = []
            for yy in range(y, y + h):
                grid_slice.append([l["grid"][yy][xx] for xx in range(x, x + w)])
            layers_data[l["name"]] = grid_slice
        self.prefabs[name] = {"w": w, "h": h, "layers": layers_data}

    def stamp_prefab(self, name: str, x: int, y: int, ignore_empty: bool = True) -> None:
        """Stamp a saved prefab at (x, y)."""
        if name not in self.prefabs:
            raise TilemapError(f"unknown prefab {name!r}; defined: {sorted(self.prefabs)}")
        pref = self.prefabs[name]
        w, h = pref["w"], pref["h"]
        self._check_xy(x, y)
        self._check_xy(x + w - 1, y + h - 1)
        for lname, grid in pref["layers"].items():
            if not any(l["name"] == lname for l in self.layers):
                self.add_layer(lname)
            l = self._layer(lname)
            for dy in range(h):
                for dx in range(w):
                    val = grid[dy][dx]
                    if val is None and ignore_empty:
                        continue
                    l["grid"][y + dy][x + dx] = val

    # ---------- render ----------
    def render(
        self,
        scale: int = 4,
        layers: Optional[list[str]] = None,
        show_grid: bool = False,
        background: Optional[str] = "#000000",
        view_rect: Optional[tuple[int, int, int, int]] = None,
        fog_of_war: bool = False,
        light_sources: Optional[list[dict]] = None,
        revealed_cells: Optional[list[tuple[int, int]]] = None,
    ) -> Image.Image:
        """Render the map.

        view_rect: (vx, vy, vw, vh) in tile coordinates to render a specific camera window.
        fog_of_war: if True, darkens tiles not in revealed_cells or within light_sources.
        light_sources: list of {"x": int, "y": int, "radius": int}.
        """
        if self.width == 0:
            raise TilemapError("create_map first")
        n = self.tile_size

        if view_rect:
            vx, vy, vw, vh = view_rect
            if vw <= 0 or vh <= 0:
                raise TilemapError("view_rect width and height must be > 0")
            img_w, img_h = vw * n, vh * n
        else:
            vx, vy, vw, vh = 0, 0, self.width, self.height
            img_w, img_h = self.width * n, self.height * n

        base = Image.new(
            "RGBA",
            (img_w, img_h),
            _parse_color(background) if background else (0, 0, 0, 0),
        )

        wanted = set(layers) if layers else None
        for l in self.layers:
            if wanted is not None and l["name"] not in wanted:
                continue
            for y, row in enumerate(l["grid"]):
                # check if row is within view_rect
                if not (vy <= y < vy + vh):
                    continue
                for x, t in enumerate(row):
                    if not (vx <= x < vx + vw):
                        continue
                    if t:
                        dest_x = (x - vx) * n
                        dest_y = (y - vy) * n
                        base.alpha_composite(self.tile_image(t), (dest_x, dest_y))

        # Fog of war / lighting overlay
        if fog_of_war:
            visible_set: set[tuple[int, int]] = set()
            if revealed_cells:
                visible_set.update(tuple(c) for c in revealed_cells)
            if light_sources:
                for ls in light_sources:
                    lx, ly, r = ls["x"], ls["y"], ls.get("radius", 4)
                    for dy in range(-r, r + 1):
                        for dx in range(-r, r + 1):
                            if dx * dx + dy * dy <= r * r:
                                visible_set.add((lx + dx, ly + dy))

            # Apply dark overlay to non-visible cells within the viewport
            fog = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
            fpx = ImageDraw.Draw(fog)
            for y in range(vy, vy + vh):
                for x in range(vx, vx + vw):
                    if (x, y) not in visible_set:
                        dest_x = (x - vx) * n
                        dest_y = (y - vy) * n
                        fpx.rectangle(
                            [(dest_x, dest_y), (dest_x + n, dest_y + n)],
                            fill=(0, 0, 0, 235),
                        )
            base.alpha_composite(fog)

        img = base.resize((base.width * scale, base.height * scale), Image.NEAREST)
        if show_grid:
            img = self._draw_grid(img, n * scale, vx, vy, vw, vh)
        return img

    def _draw_grid(
        self, img: Image.Image, cell: int, vx: int = 0, vy: int = 0, vw: int = 0, vh: int = 0
    ) -> Image.Image:
        pad = 22
        vw = vw or self.width
        vh = vh or self.height
        out = Image.new("RGBA", (img.width + pad, img.height + pad), (24, 24, 28, 255))
        out.paste(img, (pad, pad))
        d = ImageDraw.Draw(out)
        font = ImageFont.load_default()
        for i in range(vw + 1):
            d.line([(pad + i * cell, pad), (pad + i * cell, out.height)], fill=(255, 0, 255, 140))
        for j in range(vh + 1):
            d.line([(pad, pad + j * cell), (out.width, pad + j * cell)], fill=(255, 0, 255, 140))
        for i in range(vw):
            x_coord = vx + i
            d.text((pad + i * cell + cell // 2 - 4, 4), str(x_coord), fill=(255, 255, 255, 255), font=font)
        for j in range(vh):
            y_coord = vy + j
            d.text((3, pad + j * cell + cell // 2 - 5), str(y_coord), fill=(255, 255, 255, 255), font=font)
        return out

    def export_atlas(self, out_dir: Path, columns: int = 8) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        names = sorted(self.tiles)
        n = self.tile_size
        cols = max(1, min(columns, len(names) or 1))
        rows = -(-len(names) // cols) if names else 1
        atlas = Image.new("RGBA", (cols * n, rows * n), (0, 0, 0, 0))
        meta: dict = {"tile_size": n, "columns": cols, "rows": rows, "tiles": {}}
        for i, name in enumerate(names):
            cx, cy = i % cols, i // cols
            atlas.paste(self.tile_image(name), (cx * n, cy * n))
            tile_entry = {
                "index": i,
                "x": cx * n,
                "y": cy * n,
            }
            props = self.tiles[name].get("props", {})
            if props:
                tile_entry.update(props)
            meta["tiles"][name] = tile_entry
        atlas.save(out_dir / "atlas.png")
        (out_dir / "atlas.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        return meta

    def render_animation(
        self,
        frames: list[list[dict]],
        scale: int = 4,
        layers: Optional[list[str]] = None,
        background: Optional[str] = "#000000",
        view_rect: Optional[tuple[int, int, int, int]] = None,
    ) -> list[Image.Image]:
        """Render a sequence of frames by applying temporary tile changes.

        frames: list of frames, where each frame is a list of
                {"layer": str, "x": int, "y": int, "tile": Optional[str]}.
        """
        rendered: list[Image.Image] = []
        for changes in frames:
            revert = []
            for ch in changes:
                l = self._layer(ch["layer"])
                x, y = ch["x"], ch["y"]
                self._check_xy(x, y)
                revert.append((ch["layer"], x, y, l["grid"][y][x]))
                self.place(ch["layer"], x, y, ch.get("tile"))

            frame_img = self.render(
                scale=scale, layers=layers, background=background, view_rect=view_rect
            )
            rendered.append(frame_img)

            for lname, rx, ry, orig in revert:
                self.place(lname, rx, ry, orig)

        return rendered

    # ---------- persistence ----------
    def to_json(self) -> dict:
        return {
            "tile_size": self.tile_size,
            "tiles": self.tiles,
            "prefabs": self.prefabs,
            "width": self.width,
            "height": self.height,
            "layers": self.layers,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Project":
        p = cls(data["tile_size"])
        p.tiles = data["tiles"]
        p.prefabs = data.get("prefabs", {})
        p.width, p.height = data["width"], data["height"]
        p.layers = data["layers"]
        return p

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1, ensure_ascii=False))

    @classmethod
    def load(cls, path: Path) -> "Project":
        return cls.from_json(json.loads(path.read_text()))
