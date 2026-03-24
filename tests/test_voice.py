"""Tests for voice module."""
import builtins
import pytest
from video_processing.voice import extract_audio, transcribe


def test_extract_audio_requires_ffmpeg(tmp_path):
    out = tmp_path / "out.wav"
    (tmp_path / "fake.mp4").write_bytes(b"x")
    with pytest.raises(Exception):
        extract_audio(str(tmp_path / "fake.mp4"), str(out))


def test_transcribe_requires_whisper(monkeypatch):
    # Simulate missing dependency without downloading/loading a real model.
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "whisper":
            raise ImportError("No module named 'whisper'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError) as exc:
        transcribe("does_not_matter.wav", model_size="tiny")
    assert "whisper" in str(exc.value).lower()
