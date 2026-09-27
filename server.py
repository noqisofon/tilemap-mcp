"""Compatibility wrapper for server.py. Delegates to tilemap_mcp.server."""
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from tilemap_mcp.server import *  # noqa: F401, F403
from tilemap_mcp.server import (
    DATA_DIR,
    PROJECT_FILE,
    PROJECTS_DIR,
    _guard,
    _project,
    _safe_name,
    _save,
    _summary,
    main,
    mcp,
)

if __name__ == "__main__":
    main()
