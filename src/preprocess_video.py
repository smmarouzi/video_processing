#!/usr/bin/env python3
"""
Video preprocessing utility
===========================

This script provides a simple pipeline for improving the quality of a video
file and removing sections of silence.  It relies on two
components:

* **FFmpeg** for audio analysis and video post‑processing.
  The `silencedetect` filter reports periods of very low volume in the
  input's audio track.  A negative threshold in decibels and a minimum
  duration define what counts as "silence"【359725611545789†L100-L121】.  After trimming the silent
  sections the script calls ffmpeg again to apply a chain of filters for
  denoising, sharpening and colour correction based on guidance from
  recent FFmpeg tutorials【982189199068370†L194-L205】.

* **MoviePy** for cutting the video.  Once the silent intervals have been
  detected, MoviePy is used to concatenate the remaining segments.  Using
  MoviePy avoids audio desynchronisation problems that arise when
  trimming only the audio stream【359725611545789†L69-L79】.  A small amount of padding can
  optionally be applied around each cut to make transitions feel more
  natural.

Usage
-----

Run the script from the command line with at least the input and output
file names:

```
python preprocess_video.py --input input.mp4 --output output.mp4
```

Optional flags allow you to adjust the silence detection threshold, the
minimum silence duration, the ease‑in padding and the enhancement
filters.  See the argument parser in the `main` function for details.

Requirements
------------

* Python 3
* FFmpeg (must be available in your system's `PATH`)
* MoviePy (`pip install moviepy`)

"""

import argparse
import json
import os
import re
import subprocess
from typing import List, Tuple

from moviepy.editor import VideoFileClip, concatenate_videoclips

# Use FFmpeg for trimming when video is longer than this (seconds). Avoids loading 2h into RAM.
LONG_VIDEO_THRESHOLD_SEC = 30 * 60


def get_duration_seconds(path: str) -> float:
    """Return duration of media file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def _build_speech_segments(
    total_duration: float,
    silence_ranges: List[Tuple[float, float]],
    ease: float,
    min_clip_duration: float,
) -> List[Tuple[float, float]]:
    """Convert silence ranges into kept (speech) segments."""
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
    """Remove silent portions using FFmpeg filter_complex (no full load in RAM). Suitable for long videos."""
    total_duration = get_duration_seconds(input_video)
    segments = _build_speech_segments(
        total_duration, silence_ranges, ease, min_clip_duration
    )
    if not segments:
        # Copy through re-encode so pipeline is consistent
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-i",
                input_video,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-c:a",
                "aac",
                output_video,
            ],
            check=True,
        )
        return
    # Build filter_complex: trim each segment then concat
    v_parts: List[str] = []
    a_parts: List[str] = []
    for i, (start, end) in enumerate(segments):
        v_parts.append(
            f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]"
        )
        a_parts.append(
            f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]"
        )
    n = len(segments)
    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_complex = ";".join(v_parts) + ";" + ";".join(a_parts) + ";" + f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        input_video,
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        output_video,
    ]
    subprocess.run(cmd, check=True)


def detect_silence(
    input_video: str,
    threshold_db: float = -35.0,
    min_silence_duration: float = 1.0,
) -> List[Tuple[float, float]]:
    """Use ffmpeg's silencedetect filter to locate silent sections.

    Args:
        input_video: Path to the source video file.
        threshold_db: Silence threshold in dB (negative value).  Lower
            values detect quieter passages.
        min_silence_duration: Minimum time in seconds that the audio
            must remain below the threshold to be considered silence.

    Returns:
        A list of `(start, end)` tuples for each silent interval.  These
        times are expressed in seconds relative to the start of the
        video.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-vn",  # ignore video; speeds up processing【359725611545789†L115-L117】
        "-i",
        input_video,
        "-af",
        f"silencedetect=n={threshold_db}dB:d={min_silence_duration}",
        "-f",
        "null",
        "-",
    ]
    # Capture both stdout and stderr because ffmpeg writes filter logs
    # to stderr by default.
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = result.stdout
    silence_ranges: List[Tuple[float, float]] = []
    # ffmpeg outputs lines such as:
    # "silence_end: 86.7141 | silence_duration: 5.29422"
    pattern = re.compile(
        r"silence_end:\s*([0-9\.]+)\s*\|\s*silence_duration:\s*([0-9\.]+)"
    )
    for line in output.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        end_time = float(match.group(1))
        duration = float(match.group(2))
        start_time = end_time - duration
        silence_ranges.append((start_time, end_time))
    # Sort ranges just in case
    silence_ranges.sort(key=lambda tup: tup[0])
    return silence_ranges


def remove_silence(
    input_video: str,
    output_video: str,
    silence_ranges: List[Tuple[float, float]],
    ease: float = 0.0,
    min_clip_duration: float = 1.0,
) -> None:
    """Remove silent portions from a video using MoviePy (loads full video in RAM).

    Prefer remove_silence_ffmpeg for videos longer than ~30 minutes.
    """
    video = VideoFileClip(input_video)
    total_duration = video.duration
    segments = _build_speech_segments(
        total_duration, silence_ranges, ease, min_clip_duration
    )
    # Extract and concatenate segments
    if not segments:
        # No silence or only very short non‑silent sections; copy original
        video.write_videofile(
            output_video,
            codec="libx264",
            preset="ultrafast",
            audio_codec="aac",
        )
        video.close()
        return
    clips = []
    for start, end in segments:
        clips.append(video.subclip(start, end))
    final = concatenate_videoclips(clips)
    # Use the original fps if available; fallback to 30
    fps = getattr(video, "fps", None) or 30
    final.write_videofile(
        output_video,
        fps=fps,
        codec="libx264",
        preset="ultrafast",
        audio_codec="aac",
    )
    video.close()
    final.close()


def _enhancement_filters_from_preset(preset: str) -> List[str]:
    """Return FFmpeg video filters for preset: light, default, strong."""
    if preset == "light":
        return ["hqdn3d=2:2:2:2", "unsharp=5:5:0.5:5:5:0.25", "eq=contrast=1.05:saturation=1.1"]
    if preset == "strong":
        return ["hqdn3d=6:6:5:5", "unsharp=5:5:1.2:5:5:0.6", "eq=contrast=1.2:saturation=1.35"]
    # default
    return ["hqdn3d=4:4:3:3", "unsharp=5:5:0.8:5:5:0.4", "eq=contrast=1.1:saturation=1.2"]


def enhance_video(
    input_video: str,
    output_video: str,
    scale: str | None = None,
    denoise: bool = True,
    sharpen: bool = True,
    adjust_eq: bool = True,
    audio_normalize: bool = False,
    enhancement_preset: str | None = None,
    crf: int = 18,
) -> None:
    """Apply a quality‑enhancement filter chain to a video using ffmpeg.

    Optional audio normalization (dynaudnorm) evens out speech volume—useful
    for lecture recordings where the speaker moves or the mic level varies.

    If enhancement_preset is set (light|default|strong), it overrides
    denoise/sharpen/adjust_eq with a preset; strong gives more visible
    improvement for low-quality or compressed sources.

    Args:
        input_video: Path to the source video.
        output_video: Where to write the enhanced video.
        scale: A resolution string like '1920:1080' or None to keep the
            original size.
        denoise: Whether to apply denoising with `hqdn3d`.
        sharpen: Whether to apply sharpening with `unsharp`.
        adjust_eq: Whether to adjust contrast and saturation via the
            `eq` filter.
        audio_normalize: Whether to apply dynamic audio normalization for
            more consistent speech volume (e.g. for Farsi lecture audio).
        enhancement_preset: If set, use preset filters (light|default|strong)
            instead of individual denoise/sharpen/adjust_eq.
        crf: Constant rate factor for x264; lower values mean higher
            quality at the expense of larger file sizes.
    """
    filters: List[str] = []
    if scale:
        filters.append(f"scale={scale}:flags=lanczos")
    if enhancement_preset:
        filters.extend(_enhancement_filters_from_preset(enhancement_preset))
    else:
        if denoise:
            filters.append("hqdn3d=4:4:3:3")
        if sharpen:
            filters.append("unsharp=5:5:0.8:5:5:0.4")
        if adjust_eq:
            filters.append("eq=contrast=1.1:saturation=1.2")
    vf = ",".join(filters) if filters else None
    af = "dynaudnorm" if audio_normalize else None
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", input_video]
    if vf:
        cmd += ["-vf", vf]
    if af:
        cmd += ["-af", af]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-c:a", "aac", output_video]
    subprocess.run(cmd, check=True)


def trim_by_range(
    input_video: str,
    output_video: str,
    start_sec: float = 0.0,
    end_sec: float | None = None,
    reencode: bool = False,
) -> None:
    """Extract a time range from a video. Uses stream copy by default for speed.

    Args:
        input_video: Source video path.
        output_video: Output path.
        start_sec: Start time in seconds.
        end_sec: End time in seconds; None means end of file.
        reencode: If True, re-encode (slower but avoids keyframe issues).
    """
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", input_video]
    if start_sec > 0:
        cmd += ["-ss", str(start_sec)]
    if end_sec is not None:
        cmd += ["-to", str(end_sec)]
    if reencode:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-c:a", "aac"]
    else:
        cmd += ["-c", "copy"]
    cmd.append(output_video)
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Enhance video quality and remove silent sections."
            "\n\n"
            "The pipeline first detects silence using ffmpeg, then uses MoviePy"
            " to excise those sections, and finally calls ffmpeg again to"
            " improve visual quality."
        )
    )
    parser.add_argument("--input", required=True, help="Input video file")
    parser.add_argument("--output", required=True, help="Output video file")
    parser.add_argument(
        "--temp",
        default=None,
        help=(
            "Path to a temporary file for the trimmed video.  If not provided,"
            " the script will create one based on the output file name."
        ),
    )
    parser.add_argument(
        "--silence_threshold_db",
        type=float,
        default=-35.0,
        help=(
            "Silence threshold in dB.  Audio levels below this value are"
            " considered silence.  Typical values are between -30 and -40."
        ),
    )
    parser.add_argument(
        "--silence_duration",
        type=float,
        default=1.0,
        help=(
            "Minimum duration of silence (in seconds) to detect.  Shorter"
            " pauses will be kept."
        ),
    )
    parser.add_argument(
        "--ease",
        type=float,
        default=0.0,
        help=(
            "Padding (in seconds) added before each clip to smooth transitions."
        ),
    )
    parser.add_argument(
        "--min_clip_duration",
        type=float,
        default=1.0,
        help="Minimum duration (in seconds) for a non‑silent clip to be kept.",
    )
    parser.add_argument(
        "--scale",
        default=None,
        help=(
            "Target resolution as WIDTH:HEIGHT, e.g. 1920:1080.  If omitted,"
            " the video keeps its original dimensions."
        ),
    )
    parser.add_argument(
        "--no_denoise",
        action="store_true",
        help="Disable the hqdn3d denoising filter.",
    )
    parser.add_argument(
        "--no_sharpen",
        action="store_true",
        help="Disable the unsharp sharpening filter.",
    )
    parser.add_argument(
        "--no_eq",
        action="store_true",
        help="Disable contrast and saturation adjustments.",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help=(
            "Constant Rate Factor for x264 encoding.  Lower values mean higher"
            " quality and larger files."
        ),
    )
    parser.add_argument(
        "--use-ffmpeg-trim",
        action="store_true",
        help=(
            "Use FFmpeg for cutting silence (recommended for videos over ~30 min)"
            " to avoid loading the whole file into memory."
        ),
    )
    parser.add_argument(
        "--audio-normalize",
        action="store_true",
        help="Apply dynamic audio normalization for more even speech volume.",
    )
    parser.add_argument(
        "--enhancement",
        choices=("light", "default", "strong"),
        default=None,
        help=(
            "Enhancement preset: strong = more visible denoise/sharpen/eq for"
            " low-quality sources. If not set, uses --no_denoise/--no_sharpen/--no_eq."
        ),
    )
    parser.add_argument(
        "--write-silence-list",
        metavar="PATH",
        default=None,
        help=(
            "Write detected silence segments to PATH (JSON) and PATH.txt (readable)."
            " E.g. output/silence → output/silence.json and output/silence.txt"
        ),
    )
    args = parser.parse_args()
    # Determine temporary file name
    temp = args.temp
    if temp is None:
        base, ext = os.path.splitext(args.output)
        temp = f"{base}_trimmed{ext}"
    # Step 1: detect silence
    silence_ranges = detect_silence(
        args.input,
        threshold_db=args.silence_threshold_db,
        min_silence_duration=args.silence_duration,
    )
    # Optionally write and print list of extracted silence segments
    if args.write_silence_list:
        base = args.write_silence_list.rstrip(".json").rstrip(".txt")
        json_path = base + ".json"
        txt_path = base + ".txt"
        records = [
            {"start_sec": s, "end_sec": e, "duration_sec": round(e - s, 2)}
            for s, e in silence_ranges
        ]
        total_removed = sum(e - s for s, e in silence_ranges)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {"segments": records, "total_removed_sec": round(total_removed, 2)},
                f,
                indent=2,
            )
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Silence segments (extracted/removed)\n")
            f.write("=====================================\n\n")
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
        print(f"Silence list: {len(silence_ranges)} segment(s), {total_removed:.2f} s removed")
        print(f"  {json_path}")
        print(f"  {txt_path}")
    # Step 2: remove silent sections (use FFmpeg for long videos or when requested)
    use_ffmpeg_trim = args.use_ffmpeg_trim or (
        get_duration_seconds(args.input) > LONG_VIDEO_THRESHOLD_SEC
    )
    if use_ffmpeg_trim:
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
    # Step 3: apply quality enhancements
    enhance_video(
        temp,
        args.output,
        scale=args.scale,
        denoise=not args.no_denoise,
        sharpen=not args.no_sharpen,
        adjust_eq=not args.no_eq,
        audio_normalize=args.audio_normalize,
        enhancement_preset=args.enhancement,
        crf=args.crf,
    )
    # Clean up temporary file
    if temp != args.output and os.path.exists(temp):
        try:
            os.remove(temp)
        except OSError:
            pass


if __name__ == "__main__":
    main()