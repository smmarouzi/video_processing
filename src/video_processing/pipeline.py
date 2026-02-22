"""
Full pipeline: trim silence (with fades) -> enhance/upscale -> voice extract -> transcribe -> tag subjects.

Each step writes to an output path; pipeline runs in order. Steps can be toggled.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from video_processing.trim_silence import trim_silence_with_fades
from video_processing.enhance import enhance_video
from video_processing.voice import extract_audio, transcribe
from video_processing.tag_subjects import tag_subjects


def run_pipeline(
    input_path: str,
    output_dir: str,
    *,
    run_trim: bool = True,
    run_enhance: bool = True,
    run_voice_extract: bool = True,
    run_transcribe: bool = True,
    run_tag: bool = True,
    trim_options: Optional[Dict[str, Any]] = None,
    enhance_options: Optional[Dict[str, Any]] = None,
    transcribe_options: Optional[Dict[str, Any]] = None,
    tag_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run the full pipeline (or selected steps). Outputs are written under output_dir.
    Returns dict with paths and optional transcript/tags.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trim_opts = trim_options or {}
    enhance_opts = enhance_options or {}
    transcribe_opts = transcribe_options or {}
    tag_opts = tag_options or {}

    result: Dict[str, Any] = {"steps": [], "paths": {}}

    current_path = input_path

    if run_trim:
        trimmed = str(out_dir / "trimmed.mp4")
        trim_silence_with_fades(input_path, trimmed, **trim_opts)
        result["steps"].append("trim")
        result["paths"]["trimmed"] = trimmed
        current_path = trimmed

    if run_enhance:
        enhanced = str(out_dir / "enhanced.mp4")
        enhance_video(current_path, enhanced, **enhance_opts)
        result["steps"].append("enhance")
        result["paths"]["enhanced"] = enhanced
        current_path = enhanced

    if run_voice_extract:
        wav_path = str(out_dir / "audio.wav")
        extract_audio(current_path, wav_path)
        result["steps"].append("voice_extract")
        result["paths"]["audio"] = wav_path

    transcript_data: Optional[Dict[str, Any]] = None
    if run_transcribe:
        audio_path = result["paths"].get("audio")
        if not audio_path:
            audio_path = str(out_dir / "audio.wav")
            extract_audio(current_path, audio_path)
            result["paths"]["audio"] = audio_path
        try:
            transcript_path = str(out_dir / "transcript.json")
            transcript_data = transcribe(
                audio_path,
                output_path=transcript_path,
                **transcribe_opts,
            )
            result["steps"].append("transcribe")
            result["paths"]["transcript"] = transcript_path
            result["transcript"] = transcript_data
        except ImportError:
            result["steps"].append("transcribe_skipped")
            result["transcribe_skipped_reason"] = "openai-whisper not installed"

    if run_tag and transcript_data and transcript_data.get("segments"):
        tags_path = str(out_dir / "subject_tags.json")
        tagged = tag_subjects(
            transcript_data["segments"],
            output_path=tags_path,
            **tag_opts,
        )
        result["steps"].append("tag")
        result["paths"]["subject_tags"] = tags_path
        result["subject_tags"] = tagged

    result["paths"]["final_video"] = current_path
    return result
