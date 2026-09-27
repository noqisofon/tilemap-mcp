"""Compatibility wrapper for sprites.py. Delegates to tilemap_mcp.sprites."""
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from tilemap_mcp.sprites import *  # noqa: F401, F403
from tilemap_mcp.sprites import (
    GROUND_ASCII,
    GROUND_LEGEND,
    OBJECTS_ASCII,
    OBJECTS_LEGEND,
    SPRITES,
)
