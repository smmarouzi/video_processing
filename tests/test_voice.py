"""Tests for voice module."""
import pytest
from video_processing.voice import extract_audio, transcribe


def test_extract_audio_requires_ffmpeg(tmp_path):
    out = tmp_path / "out.wav"
    (tmp_path / "fake.mp4").write_bytes(b"x")
    with pytest.raises(Exception):
        extract_audio(str(tmp_path / "fake.mp4"), str(out))


def test_transcribe_requires_whisper(tmp_path):
    # transcribe() imports whisper inside; if not installed, raises ImportError
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"fake wav")
    try:
        transcribe(str(wav), model_size="tiny")
    except ImportError as e:
        assert "whisper" in str(e).lower()
