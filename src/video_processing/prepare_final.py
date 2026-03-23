"""
Full-length workflow: silence trim → enhance, with per-phase wall-clock timing.

Enhance runs after trim finishes (it needs the trimmed file). Parallelism comes from:
- optional multiple ffmpeg processes during *chunked* trim (`chunk_encode_workers`)
- multi-threaded libx264 during enhance (ffmpeg/x264 defaults, or `--encoder-threads`)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from video_processing._utils import get_duration_seconds
from video_processing.enhance import enhance_video
from video_processing.trim_silence import trim_silence_with_fades


def run_prepare_final(
    input_path: str,
    output_dir: str,
    *,
    threshold_db: float = -35.0,
    min_silence_duration: float = 1.0,
    padding_before_silence: float = 0.0,
    min_clip_duration: float = 0.5,
    fade_duration: float = 0.2,
    write_silence_list_path: Optional[str] = None,
    max_filter_segments: int = 120,
    chunk_encode_workers: int = 4,
    scale: Optional[str] = None,
    preset: str = "default",
    audio_normalize: bool = False,
    crf: int = 18,
    encoder_threads: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Trim silence on the full input, then enhance. Writes ``TIMING_REPORT.md`` and
    ``timing.json`` under *output_dir*.

    Outputs:
    - ``trimmed.mp4`` – after silence removal (with fades)
    - ``final.mp4`` – after enhance (deliverable)
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    trimmed_path = out / "trimmed.mp4"
    final_path = out / "final.mp4"

    input_duration = get_duration_seconds(input_path)

    t0 = time.perf_counter()
    trim_silence_with_fades(
        input_path,
        str(trimmed_path),
        threshold_db=threshold_db,
        min_silence_duration=min_silence_duration,
        padding_before_silence=padding_before_silence,
        min_clip_duration=min_clip_duration,
        fade_duration=fade_duration,
        write_silence_list_path=write_silence_list_path,
        max_filter_segments=max_filter_segments,
        chunk_encode_workers=chunk_encode_workers,
    )
    t1 = time.perf_counter()
    trim_sec = round(t1 - t0, 2)

    trimmed_duration = get_duration_seconds(str(trimmed_path))

    t2 = time.perf_counter()
    enhance_video(
        str(trimmed_path),
        str(final_path),
        scale=scale,
        preset=preset,
        audio_normalize=audio_normalize,
        crf=crf,
        encoder_threads=encoder_threads,
    )
    t3 = time.perf_counter()
    enhance_sec = round(t3 - t2, 2)

    final_duration = get_duration_seconds(str(final_path))
    total_sec = round(t3 - t0, 2)

    timing: Dict[str, Any] = {
        "input_path": input_path,
        "input_duration_sec": round(input_duration, 2),
        "trim_wall_sec": trim_sec,
        "trimmed_path": str(trimmed_path),
        "trimmed_duration_sec": round(trimmed_duration, 2),
        "enhance_wall_sec": enhance_sec,
        "final_path": str(final_path),
        "final_duration_sec": round(final_duration, 2),
        "total_wall_sec": total_sec,
        "settings": {
            "max_filter_segments": max_filter_segments,
            "chunk_encode_workers": chunk_encode_workers,
            "encoder_threads": encoder_threads,
            "preset": preset,
            "crf": crf,
            "scale": scale,
        },
    }

    json_path = out / "timing.json"
    json_path.write_text(json.dumps(timing, indent=2), encoding="utf-8")

    report_path = out / "TIMING_REPORT.md"
    lines = [
        "# Full video: trim → enhance (timing)",
        "",
        f"- **Input:** `{input_path}`",
        f"- **Input duration:** {timing['input_duration_sec']:.2f} s",
        "",
        "## Wall-clock",
        "",
        "| Phase | Seconds | Output |",
        "|--------|--------:|--------|",
        f"| Silence trim | **{trim_sec:.2f}** | `{trimmed_path.name}` |",
        f"| Enhance | **{enhance_sec:.2f}** | `{final_path.name}` |",
        f"| **Total** | **{total_sec:.2f}** | |",
        "",
        "## Output durations",
        "",
        f"- After trim: **{timing['trimmed_duration_sec']:.2f}** s",
        f"- After enhance (final): **{timing['final_duration_sec']:.2f}** s",
        "",
        "## Settings used",
        "",
        "```json",
        json.dumps(timing["settings"], indent=2),
        "```",
        "",
        "Parallelism: chunked trim may use multiple ffmpeg jobs (`chunk_encode_workers`); "
        "enhance is one pass (libx264 uses multiple threads by default unless restricted).",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")

    timing["paths"] = {
        "trimmed": str(trimmed_path),
        "final": str(final_path),
        "timing_json": str(json_path),
        "timing_report": str(report_path),
    }
    return timing
