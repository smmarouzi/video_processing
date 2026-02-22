"""Tests for enhance module."""
import pytest
from video_processing.enhance import _PRESETS, enhance_video


def test_presets_defined():
    assert "light" in _PRESETS
    assert "default" in _PRESETS
    assert "strong" in _PRESETS
    for v in _PRESETS.values():
        assert isinstance(v, list)
        assert len(v) >= 2


def test_enhance_requires_ffmpeg(tmp_path):
    out = tmp_path / "out.mp4"
    (tmp_path / "fake.mp4").write_bytes(b"x")
    with pytest.raises(Exception):  # ffmpeg will fail on fake input
        enhance_video(str(tmp_path / "fake.mp4"), str(out))
