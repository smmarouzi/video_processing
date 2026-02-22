#!/usr/bin/env python3
"""
Extract 5 minutes from a long video and run the full test pipeline:
  1. Trim to first 5 minutes
  2. Detect and remove silent sections (FFmpeg)
  3. Enhance quality (denoise, sharpen, eq, optional audio normalize)

Uses only FFmpeg (no MoviePy). Requires FFmpeg on PATH.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_duration_seconds(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def detect_silence(
    input_video: str,
    threshold_db: float = -35.0,
    min_silence_duration: float = 1.0,
) -> List[Tuple[float, float]]:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-vn", "-i", input_video,
            "-af", f"silencedetect=n={threshold_db}dB:d={min_silence_duration}",
            "-f", "null", "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    silence_ranges: List[Tuple[float, float]] = []
    pattern = re.compile(
        r"silence_end:\s*([0-9\.]+)\s*\|\s*silence_duration:\s*([0-9\.]+)"
    )
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        end_time = float(match.group(1))
        duration = float(match.group(2))
        start_time = end_time - duration
        silence_ranges.append((start_time, end_time))
    silence_ranges.sort(key=lambda t: t[0])
    return silence_ranges


def build_speech_segments(
    total_duration: float,
    silence_ranges: List[Tuple[float, float]],
    ease: float,
    min_clip_duration: float,
) -> List[Tuple[float, float]]:
    segments: List[Tuple[float, float]] = []
    last_end = 0.0
    for start_silence, end_silence in silence_ranges:
        seg_start = max(last_end, 0.0)
        seg_end = start_silence
        if ease > 0.0 and seg_start > 0.0:
            seg_start = max(0.0, seg_start - ease)
        if seg_end - seg_start >= min_clip_duration:
            segments.append((seg_start, seg_end))
        last_end = end_silence
    if total_duration - last_end >= min_clip_duration:
        seg_start = max(last_end, 0.0)
        if ease > 0.0 and seg_start > 0.0:
            seg_start = max(0.0, seg_start - ease)
        segments.append((seg_start, total_duration))
    return segments


def remove_silence_ffmpeg(
    input_video: str,
    output_video: str,
    silence_ranges: List[Tuple[float, float]],
    ease: float = 0.0,
    min_clip_duration: float = 1.0,
) -> None:
    total_duration = get_duration_seconds(input_video)
    segments = build_speech_segments(
        total_duration, silence_ranges, ease, min_clip_duration
    )
    if not segments:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-y", "-i", input_video,
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
                output_video,
            ],
            check=True,
        )
        return
    v_parts = [
        f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]"
        for i, (s, e) in enumerate(segments)
    ]
    a_parts = [
        f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]"
        for i, (s, e) in enumerate(segments)
    ]
    n = len(segments)
    concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_complex = ";".join(v_parts) + ";" + ";".join(a_parts) + ";" + f"{concat_in}concat=n={n}:v=1:a=1[outv][outa]"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-y", "-i", input_video,
            "-filter_complex", filter_complex, "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
            output_video,
        ],
        check=True,
    )


def _enhancement_filters(preset: str, scale: str = None) -> List[str]:
    """Preset: light, default, strong. Strong = more visible denoise/sharpen/eq."""
    filters = []
    if scale:
        filters.append(f"scale={scale}:flags=lanczos")
    if preset == "light":
        filters.extend(["hqdn3d=2:2:2:2", "unsharp=5:5:0.5:5:5:0.25", "eq=contrast=1.05:saturation=1.1"])
    elif preset == "strong":
        filters.extend(["hqdn3d=6:6:5:5", "unsharp=5:5:1.2:5:5:0.6", "eq=contrast=1.2:saturation=1.35"])
    else:  # default
        filters.extend(["hqdn3d=4:4:3:3", "unsharp=5:5:0.8:5:5:0.4", "eq=contrast=1.1:saturation=1.2"])
    return filters


def enhance_video(
    input_video: str,
    output_video: str,
    audio_normalize: bool = False,
    crf: int = 18,
    enhancement_preset: str = "default",
    scale: str = None,
) -> None:
    filters = _enhancement_filters(enhancement_preset, scale)
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", input_video, "-vf", ",".join(filters)]
    if audio_normalize:
        cmd += ["-af", "dynaudnorm"]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-c:a", "aac", output_video]
    subprocess.run(cmd, check=True)


def format_ts(sec: float) -> str:
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    if h:
        return "{}:{:02d}:{:02d}".format(h, m, s)
    return "{}:{:02d}".format(m, s)


def write_silence_list(
    silence_ranges: List[Tuple[float, float]],
    output_dir: str,
    base_name: str = "silence_segments",
) -> Tuple[str, str]:
    """Write silence segments to JSON and TXT. Returns (json_path, txt_path)."""
    records = [
        {"start_sec": s, "end_sec": e, "duration_sec": round(e - s, 2)}
        for s, e in silence_ranges
    ]
    total_removed = sum(e - s for s, e in silence_ranges)
    json_path = os.path.join(output_dir, base_name + ".json")
    txt_path = os.path.join(output_dir, base_name + ".txt")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"segments": records, "total_removed_sec": round(total_removed, 2)}, f, indent=2)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Silence segments (extracted/removed)\n")
        f.write("=====================================\n\n")
        for i, (start, end) in enumerate(silence_ranges, 1):
            dur = end - start
            f.write("Segment {:2d}: {} - {}  ({:.2f} s)\n".format(i, format_ts(start), format_ts(end), dur))
        f.write("\nTotal: {} segment(s), {:.2f} s removed\n".format(len(silence_ranges), total_removed))
    return json_path, txt_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract 5 min from long video and run silence trim + enhance.")
    parser.add_argument(
        "--input", "-i",
        default=os.path.join(PROJECT_ROOT, "GMT20250913-160508_Recording_1600x828.mp4"),
        help="Input video (default: project 2h recording)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=os.path.join(PROJECT_ROOT, "output", "two_hour_test"),
        help="Output directory",
    )
    parser.add_argument(
        "--length",
        type=float,
        default=300.0,
        help="Length of extracted segment in seconds (default: 300 = 5 min)",
    )
    parser.add_argument("--audio-normalize", action="store_true", help="Apply audio normalization")
    parser.add_argument(
        "--enhancement",
        choices=("light", "default", "strong"),
        default="strong",
        help="Enhancement strength: strong = more visible denoise/sharpen/eq (default: strong)",
    )
    parser.add_argument(
        "--scale",
        default=None,
        help="Upscale resolution WIDTH:HEIGHT, e.g. 1920:1080 (often helps low-res look better)",
    )
    parser.add_argument("--silence-threshold-db", type=float, default=-35.0)
    parser.add_argument("--silence-duration", type=float, default=1.0)
    parser.add_argument("--ease", type=float, default=0.0)
    parser.add_argument("--min-clip-duration", type=float, default=1.0)
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    segment_path = os.path.join(args.output_dir, "sample_5min.mp4")
    trimmed_path = os.path.join(args.output_dir, "sample_5min_trimmed.mp4")
    final_path = os.path.join(args.output_dir, "sample_5min_processed.mp4")

    print("Step 1: Extract first {:.0f} minutes...".format(args.length / 60))
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-y", "-i", args.input,
            "-to", str(args.length),
            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
            segment_path,
        ],
        check=True,
    )

    print("Step 2: Detect silence...")
    silence_ranges = detect_silence(
        segment_path,
        threshold_db=args.silence_threshold_db,
        min_silence_duration=args.silence_duration,
    )
    print("  Found {} silent region(s).".format(len(silence_ranges)))
    total_removed = sum(e - s for s, e in silence_ranges)
    print("  Total silence removed: {:.2f} s ({:.1f} min)".format(total_removed, total_removed / 60))

    # Write and print list of extracted silence segments
    json_path, txt_path = write_silence_list(silence_ranges, args.output_dir)
    print("  Silence list (JSON): ", json_path)
    print("  Silence list (TXT):  ", txt_path)
    print("\n  Extracted silence segments (start - end, duration):")
    for i, (start, end) in enumerate(silence_ranges, 1):
        print("    {:2d}. {} - {}  ({:.2f} s)".format(i, format_ts(start), format_ts(end), end - start))
    print()

    print("Step 3: Remove silent sections...")
    remove_silence_ffmpeg(
        segment_path,
        trimmed_path,
        silence_ranges,
        ease=args.ease,
        min_clip_duration=args.min_clip_duration,
    )

    print("Step 4: Enhance quality (preset={}, scale={})...".format(args.enhancement, args.scale or "none"))
    enhance_video(
        trimmed_path,
        final_path,
        audio_normalize=args.audio_normalize,
        crf=18,
        enhancement_preset=args.enhancement,
        scale=args.scale,
    )

    print("Done.")
    print("  Extracted 5 min:     ", segment_path)
    print("  After silence trim: ", trimmed_path)
    print("  Final (enhanced):   ", final_path)
    print("  Silence segments:   ", txt_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
