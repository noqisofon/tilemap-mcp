"""Compatibility wrapper for tilemap.py. Delegates to tilemap_mcp.tilemap."""
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from tilemap_mcp.tilemap import *  # noqa: F401, F403
from tilemap_mcp.tilemap import Project, TilemapError
