"""Shared utilities: duration, FFmpeg runners."""

import subprocess
from typing import Iterable, List


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


def iter_ffmpeg_output(args: List[str]) -> Iterable[str]:
    """
    Run ffmpeg and yield merged stdout/stderr lines as they are produced.

    Useful for long-running commands where storing all logs in memory is wasteful.
    """
    process = subprocess.Popen(
        ["ffmpeg", "-hide_banner"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    try:
        for line in process.stdout:
            yield line
    finally:
        process.stdout.close()
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, process.args)
