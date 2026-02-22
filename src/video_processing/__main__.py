"""CLI entry point: python -m video_processing ..."""
import sys
from pathlib import Path

# When run as python -m video_processing from repo root (no install), ensure src is on path
if __name__ == "__main__":
    _pkg_dir = Path(__file__).resolve().parent
    _src = _pkg_dir.parent
    if _src.name == "src" and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

from video_processing.cli import main

if __name__ == "__main__":
    main()
