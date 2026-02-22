"""
Trim silent sections from video with smooth fades at cut points.

No hard jump after silence: each kept segment gets a short fade-in at the start
and fade-out at the end so transitions are smooth.
"""

import re
from typing import List, Optional, Tuple

from video_processing._utils import get_duration_seconds, run_ffmpeg, run_ffmpeg_capture


def detect_silence(
    input_path: str,
    threshold_db: float = -35.0,
    min_silence_duration: float = 1.0,
) -> List[Tuple[float, float]]:
    """Detect silent intervals (start_sec, end_sec) using FFmpeg silencedetect."""
    output = run_ffmpeg_capture([
        "-vn", "-i", input_path,
        "-af", f"silencedetect=n={threshold_db}dB:d={min_silence_duration}",
        "-f", "null", "-",
    ])
    pattern = re.compile(
        r"silence_end:\s*([0-9\.]+)\s*\|\s*silence_duration:\s*([0-9\.]+)"
    )
    ranges: List[Tuple[float, float]] = []
    for line in output.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        end_t = float(match.group(1))
        dur = float(match.group(2))
        ranges.append((end_t - dur, end_t))
    ranges.sort(key=lambda t: t[0])
    return ranges


def build_speech_segments(
    total_duration: float,
    silence_ranges: List[Tuple[float, float]],
    padding_before_silence: float = 0.0,
    min_clip_duration: float = 0.5,
) -> List[Tuple[float, float]]:
    """Convert silence ranges into kept (speech) segments (start, end)."""
    segments: List[Tuple[float, float]] = []
    last_end = 0.0
    for start_silence, end_silence in silence_ranges:
        seg_start = max(last_end, 0.0)
        seg_end = start_silence
        if padding_before_silence > 0 and seg_start > 0:
            seg_start = max(0.0, seg_start - padding_before_silence)
        if seg_end - seg_start >= min_clip_duration:
            segments.append((seg_start, seg_end))
        last_end = end_silence
    if total_duration - last_end >= min_clip_duration:
        seg_start = max(last_end, 0.0)
        if padding_before_silence > 0 and seg_start > 0:
            seg_start = max(0.0, seg_start - padding_before_silence)
        segments.append((seg_start, total_duration))
    return segments


def get_silence_segments(
    input_path: str,
    threshold_db: float = -35.0,
    min_silence_duration: float = 1.0,
    padding_before_silence: float = 0.0,
    min_clip_duration: float = 0.5,
) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    """
    Return (silence_ranges, speech_segments) for the input.
    speech_segments are the kept parts (start, end) in seconds.
    """
    duration = get_duration_seconds(input_path)
    silence_ranges = detect_silence(
        input_path,
        threshold_db=threshold_db,
        min_silence_duration=min_silence_duration,
    )
    speech_segments = build_speech_segments(
        duration,
        silence_ranges,
        padding_before_silence=padding_before_silence,
        min_clip_duration=min_clip_duration,
    )
    return silence_ranges, speech_segments


def trim_silence_with_fades(
    input_path: str,
    output_path: str,
    silence_ranges: Optional[List[Tuple[float, float]]] = None,
    *,
    threshold_db: float = -35.0,
    min_silence_duration: float = 1.0,
    padding_before_silence: float = 0.0,
    min_clip_duration: float = 0.5,
    fade_duration: float = 0.2,
    write_silence_list_path: Optional[str] = None,
) -> List[Tuple[float, float]]:
    """
    Trim silent sections and write video with fade-in/fade-out at each cut
    so there is no hard jump after silence.

    If silence_ranges is None, they are detected from input_path.
    Returns the list of silence ranges (for writing to file if needed).
    """
    duration = get_duration_seconds(input_path)
    if silence_ranges is None:
        silence_ranges = detect_silence(
            input_path, threshold_db=threshold_db,
            min_silence_duration=min_silence_duration,
        )
    segments = build_speech_segments(
        duration,
        silence_ranges,
        padding_before_silence=padding_before_silence,
        min_clip_duration=min_clip_duration,
    )

    if write_silence_list_path:
        import json
        base = write_silence_list_path.rstrip(".json").rstrip(".txt")
        records = [
            {"start_sec": s, "end_sec": e, "duration_sec": round(e - s, 2)}
            for s, e in silence_ranges
        ]
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump({
                "segments": records,
                "total_removed_sec": round(sum(e - s for s, e in silence_ranges), 2),
            }, f, indent=2)
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write("Silence segments (removed)\n==========================\n\n")
            for i, (s, e) in enumerate(silence_ranges, 1):
                f.write(f"Segment {i:2d}: {_ts(s)} - {_ts(e)}  ({e - s:.2f} s)\n")
            f.write(f"\nTotal: {len(silence_ranges)} segment(s)\n")

    if not segments:
        run_ffmpeg([
            "-i", input_path,
            "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
            output_path,
        ])
        return silence_ranges

    fade = min(fade_duration, 0.25)
    v_parts: List[str] = []
    a_parts: List[str] = []
    for i, (start, end) in enumerate(segments):
        seg_dur = end - start
        fade_out_st = max(0, seg_dur - fade)
        if seg_dur <= 2 * fade:
            v_parts.append(
                f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}]"
            )
            a_parts.append(
                f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}]"
            )
        else:
            v_parts.append(
                f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,"
                f"fade=t=in:st=0:d={fade},fade=t=out:st={fade_out_st}:d={fade}[v{i}]"
            )
            a_parts.append(
                f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d={fade},afade=t=out:st={fade_out_st}:d={fade}[a{i}]"
            )
    n = len(segments)
    concat_in = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_complex = ";".join(v_parts) + ";" + ";".join(a_parts) + ";" + f"{concat_in}concat=n={n}:v=1:a=1[outv][outa]"
    run_ffmpeg([
        "-i", input_path,
        "-filter_complex", filter_complex, "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
        output_path,
    ])
    return silence_ranges


def _ts(sec: float) -> str:
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
