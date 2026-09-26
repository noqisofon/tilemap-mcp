import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from server import mcp
    mcp.run()


if __name__ == "__main__":
    main()
