"""Pytest fixtures and path setup."""
import sys
from pathlib import Path

# Add src to path so "from video_processing ..." works
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
