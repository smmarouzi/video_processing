"""Shared utilities: duration, FFmpeg runner."""

import subprocess
from typing import List, Optional


def get_duration_seconds(path: str) -> float:
    """Return duration of media file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def run_ffmpeg(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with given args (e.g. ['-i', 'in.mp4', 'out.mp4'])."""
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-y"] + args,
        check=check,
    )


def run_ffmpeg_capture(args: List[str]) -> str:
    """Run ffmpeg with stdout/stderr captured (for silencedetect etc.)."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.stdout or ""
