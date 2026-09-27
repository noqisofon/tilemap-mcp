"""Rebuild the attached room directly through the core library."""
from pathlib import Path

from tilemap_mcp.sprites import (
    GROUND_ASCII,
    GROUND_LEGEND,
    OBJECTS_ASCII,
    OBJECTS_LEGEND,
    SPRITES,
)
from tilemap_mcp.tilemap import Project

out = Path("demo_out")
out.mkdir(exist_ok=True)

p = Project(16)
for name, t in SPRITES.items():
    p.define_tile(name, t["palette"], t["rows"])
p.create_map(10, 8)
p.set_from_ascii("ground", GROUND_ASCII, GROUND_LEGEND)
p.set_from_ascii("objects", OBJECTS_ASCII, OBJECTS_LEGEND, x=0, y=0)

p.render(scale=4).save(out / "room.png")
p.render(scale=4, show_grid=True).save(out / "room_grid.png")
p.export_atlas(out)
p.save(out / "project.json")
print("ok", sorted(p.tiles))
