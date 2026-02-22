#!/usr/bin/env python3
"""
Produce a higher-quality short sample from the project's sample video.

Uses only FFmpeg (no MoviePy). Steps:
1. Trim the input to the first 30 seconds (short sample).
2. Enhance that clip (denoise, sharpen, contrast/saturation, optional audio normalize).

Usage (from project root):
  python scripts/run_sample_enhance.py [--input path/to/video.mov] [--output-dir dir]

Requires: FFmpeg on your PATH.
Default input: vecteezy_bangkok-thailand-january-1-2023-central-world-shopping_23668344.mov
Outputs: <output_dir>/sample_30s.mp4 (trimmed), <output_dir>/sample_30s_enhanced.mp4 (enhanced).
"""

import argparse
import os
import subprocess
import sys
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def trim_by_range(
    input_video: str,
    output_video: str,
    start_sec: float = 0.0,
    end_sec: Optional[float] = None,
    reencode: bool = True,
) -> None:
    """Extract a time range. Re-encodes by default so ProRes/other codecs work in MP4."""
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", input_video]
    if start_sec > 0:
        cmd += ["-ss", str(start_sec)]
    if end_sec is not None:
        cmd += ["-to", str(end_sec)]
    if reencode:
        cmd += ["-c:v", "libx264", "-preset", "fast", "-c:a", "aac"]
    else:
        cmd += ["-c", "copy"]
    cmd.append(output_video)
    subprocess.run(cmd, check=True)


def enhance_video(
    input_video: str,
    output_video: str,
    audio_normalize: bool = False,
    crf: int = 18,
) -> None:
    """Apply denoise, sharpen, eq; optional audio normalization."""
    filters = ["hqdn3d=4:4:3:3", "unsharp=5:5:0.8:5:5:0.4", "eq=contrast=1.1:saturation=1.2"]
    vf = ",".join(filters)
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", input_video, "-vf", vf]
    if audio_normalize:
        cmd += ["-af", "dynaudnorm"]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-c:a", "aac", output_video]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a higher-quality short sample from a video.")
    parser.add_argument(
        "--input",
        "-i",
        default=os.path.join(
            PROJECT_ROOT,
            "vecteezy_bangkok-thailand-january-1-2023-central-world-shopping_23668344.mov",
        ),
        help="Input video (default: project sample .mov)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=os.path.join(PROJECT_ROOT, "output"),
        help="Directory for output files (default: output/)",
    )
    parser.add_argument(
        "--length",
        type=float,
        default=30.0,
        help="Length of sample in seconds (default: 30)",
    )
    parser.add_argument(
        "--audio-normalize",
        action="store_true",
        help="Apply audio normalization to the enhanced clip.",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    trimmed = os.path.join(args.output_dir, "sample_30s.mp4")
    enhanced = os.path.join(args.output_dir, "sample_30s_enhanced.mp4")

    print("Step 1: Trim to short sample ({} s)...".format(args.length))
    trim_by_range(args.input, trimmed, start_sec=0.0, end_sec=args.length)
    print("Step 2: Enhance quality (denoise, sharpen, eq)...")
    enhance_video(trimmed, enhanced, audio_normalize=args.audio_normalize, crf=18)
    print("Done.")
    print("  Trimmed sample:", trimmed)
    print("  Enhanced (higher quality):", enhanced)
    return 0


if __name__ == "__main__":
    sys.exit(main())
