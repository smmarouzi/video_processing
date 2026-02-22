"""
Video processing package: trim silence (with fades), enhance/upscale,
voice extraction & transcription, subject tagging, and full pipeline.
"""

from video_processing.trim_silence import (
    detect_silence,
    trim_silence_with_fades,
    build_speech_segments,
    get_silence_segments,
)
from video_processing.enhance import enhance_video
from video_processing.voice import extract_audio, transcribe
from video_processing.tag_subjects import tag_subjects
from video_processing.pipeline import run_pipeline

__all__ = [
    "detect_silence",
    "trim_silence_with_fades",
    "build_speech_segments",
    "get_silence_segments",
    "enhance_video",
    "extract_audio",
    "transcribe",
    "tag_subjects",
    "run_pipeline",
]
