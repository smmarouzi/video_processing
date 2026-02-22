#!/usr/bin/env python3
"""
Unified CLI for editing lecture videos (e.g. Farsi, up to ~2 hours).

Commands:
  process      Full pipeline: remove silence + enhance quality (default for one-shot)
  trim-silence Only remove silent sections
  enhance      Only improve picture/audio quality (denoise, sharpen, optional normalize)
  trim-range   Cut a segment by start/end time
"""

import argparse
import json
import os
import sys

# Ensure preprocess_video is importable when run as python src/edit_video.py from project root
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from preprocess_video import (
    LONG_VIDEO_THRESHOLD_SEC,
    detect_silence,
    enhance_video,
    get_duration_seconds,
    remove_silence,
    remove_silence_ffmpeg,
    trim_by_range,
)


def _add_common_io(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", "-i", required=True, help="Input video file")
    parser.add_argument("--output", "-o", required=True, help="Output video file")


def _add_silence_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--silence-threshold-db",
        type=float,
        default=-35.0,
        help="Silence threshold in dB (default: -35). Softer speech: try -40.",
    )
    parser.add_argument(
        "--silence-duration",
        type=float,
        default=1.0,
        help="Minimum silence duration in seconds to cut (default: 1.0).",
    )
    parser.add_argument(
        "--ease",
        type=float,
        default=0.0,
        help="Padding in seconds before each cut for smoother transitions.",
    )
    parser.add_argument(
        "--min-clip-duration",
        type=float,
        default=1.0,
        help="Minimum length of a kept segment in seconds.",
    )
    parser.add_argument(
        "--use-ffmpeg-trim",
        action="store_true",
        help=f"Use FFmpeg for cutting (recommended for videos over {LONG_VIDEO_THRESHOLD_SEC // 60} min).",
    )


def _add_enhance_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scale",
        default=None,
        help="Target resolution WIDTH:HEIGHT, e.g. 1920:1080.",
    )
    parser.add_argument("--no-denoise", action="store_true", help="Disable denoising.")
    parser.add_argument("--no-sharpen", action="store_true", help="Disable sharpening.")
    parser.add_argument("--no-eq", action="store_true", help="Disable contrast/saturation.")
    parser.add_argument(
        "--enhancement",
        choices=("light", "default", "strong"),
        default=None,
        help="Preset: strong = more visible denoise/sharpen/eq for low-quality video.",
    )
    parser.add_argument(
        "--audio-normalize",
        action="store_true",
        help="Normalize speech volume (good for lecture audio).",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="Encoding quality 0–51; lower = better (default: 18).",
    )


def _write_silence_list(silence_ranges, base_path: str) -> None:
    """Write silence segments to base_path.json and base_path.txt."""
    base = base_path.rstrip(".json").rstrip(".txt")
    records = [
        {"start_sec": s, "end_sec": e, "duration_sec": round(e - s, 2)}
        for s, e in silence_ranges
    ]
    total_removed = sum(e - s for s, e in silence_ranges)
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"segments": records, "total_removed_sec": round(total_removed, 2)}, f, indent=2)
    with open(base + ".txt", "w", encoding="utf-8") as f:
        f.write("Silence segments (extracted/removed)\n=====================================\n\n")
        for i, (start, end) in enumerate(silence_ranges, 1):
            dur = end - start
            m, s_ = divmod(int(round(start)), 60)
            h, m = divmod(m, 60)
            start_ts = f"{h}:{m:02d}:{s_:02d}" if h else f"{m}:{s_:02d}"
            m, s_ = divmod(int(round(end)), 60)
            h, m = divmod(m, 60)
            end_ts = f"{h}:{m:02d}:{s_:02d}" if h else f"{m}:{s_:02d}"
            f.write(f"Segment {i:2d}: {start_ts} - {end_ts}  ({dur:.2f} s)\n")
        f.write(f"\nTotal: {len(silence_ranges)} segment(s), {total_removed:.2f} s removed\n")


def cmd_process(args: argparse.Namespace) -> None:
    """Full pipeline: detect silence → remove silence → enhance."""
    temp = args.temp or (os.path.splitext(args.output)[0] + "_trimmed" + os.path.splitext(args.output)[1])
    silence_ranges = detect_silence(
        args.input,
        threshold_db=args.silence_threshold_db,
        min_silence_duration=args.silence_duration,
    )
    if getattr(args, "write_silence_list", None):
        _write_silence_list(silence_ranges, args.write_silence_list)
        total_removed = sum(e - s for s, e in silence_ranges)
        print("Silence: {} segment(s), {:.2f} s removed → {}.json / {}.txt".format(
            len(silence_ranges), total_removed,
            args.write_silence_list.rstrip(".json").rstrip(".txt"),
            args.write_silence_list.rstrip(".json").rstrip(".txt"),
        ))
    use_ffmpeg = args.use_ffmpeg_trim or (get_duration_seconds(args.input) > LONG_VIDEO_THRESHOLD_SEC)
    if use_ffmpeg:
        remove_silence_ffmpeg(
            args.input,
            temp,
            silence_ranges,
            ease=args.ease,
            min_clip_duration=args.min_clip_duration,
        )
    else:
        remove_silence(
            args.input,
            temp,
            silence_ranges,
            ease=args.ease,
            min_clip_duration=args.min_clip_duration,
        )
    enhance_video(
        temp,
        args.output,
        scale=args.scale,
        denoise=not args.no_denoise,
        sharpen=not args.no_sharpen,
        adjust_eq=not args.no_eq,
        audio_normalize=args.audio_normalize,
        enhancement_preset=getattr(args, "enhancement", None),
        crf=args.crf,
    )
    if temp != args.output and os.path.exists(temp):
        try:
            os.remove(temp)
        except OSError:
            pass


def cmd_trim_silence(args: argparse.Namespace) -> None:
    """Only remove silent sections; no quality enhancement."""
    silence_ranges = detect_silence(
        args.input,
        threshold_db=args.silence_threshold_db,
        min_silence_duration=args.silence_duration,
    )
    use_ffmpeg = args.use_ffmpeg_trim or (get_duration_seconds(args.input) > LONG_VIDEO_THRESHOLD_SEC)
    if use_ffmpeg:
        remove_silence_ffmpeg(
            args.input,
            args.output,
            silence_ranges,
            ease=args.ease,
            min_clip_duration=args.min_clip_duration,
        )
    else:
        remove_silence(
            args.input,
            args.output,
            silence_ranges,
            ease=args.ease,
            min_clip_duration=args.min_clip_duration,
        )


def cmd_enhance(args: argparse.Namespace) -> None:
    """Only enhance quality (denoise, sharpen, optional audio normalize)."""
    enhance_video(
        args.input,
        args.output,
        scale=args.scale,
        denoise=not args.no_denoise,
        sharpen=not args.no_sharpen,
        adjust_eq=not args.no_eq,
        audio_normalize=args.audio_normalize,
        enhancement_preset=getattr(args, "enhancement", None),
        crf=args.crf,
    )


def cmd_trim_range(args: argparse.Namespace) -> None:
    """Cut a segment by start and end time."""
    trim_by_range(
        args.input,
        args.output,
        start_sec=args.start,
        end_sec=args.end,
        reencode=args.reencode,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Edit lecture videos: remove silence, enhance quality, trim by time. Supports long (e.g. 2h) Farsi lectures.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # process
    p_process = subparsers.add_parser("process", help="Full pipeline: remove silence + enhance")
    _add_common_io(p_process)
    p_process.add_argument("--temp", default=None, help="Temp file for trimmed video")
    p_process.add_argument(
        "--write-silence-list",
        metavar="PATH",
        default=None,
        help="Write silence segments to PATH.json and PATH.txt (list of removed parts).",
    )
    _add_silence_args(p_process)
    _add_enhance_args(p_process)
    p_process.set_defaults(run=cmd_process)

    # trim-silence
    p_trim = subparsers.add_parser("trim-silence", help="Only remove silent parts")
    _add_common_io(p_trim)
    _add_silence_args(p_trim)
    p_trim.set_defaults(run=cmd_trim_silence)

    # enhance
    p_enhance = subparsers.add_parser("enhance", help="Only enhance video/audio quality")
    _add_common_io(p_enhance)
    _add_enhance_args(p_enhance)
    p_enhance.set_defaults(run=cmd_enhance)

    # trim-range
    p_range = subparsers.add_parser("trim-range", help="Extract a time range (e.g. 0 to 3600)")
    _add_common_io(p_range)
    p_range.add_argument("--start", type=float, default=0.0, help="Start time in seconds")
    p_range.add_argument("--end", type=float, default=None, help="End time in seconds (default: end of file)")
    p_range.add_argument("--reencode", action="store_true", help="Re-encode instead of stream copy")
    p_range.set_defaults(run=cmd_trim_range)

    args = parser.parse_args()
    args.run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
