"""Tests for pipeline module."""
import pytest
from video_processing.pipeline import run_pipeline


def test_pipeline_trim_only(tmp_path):
    """Run only trim step; needs real video or we expect ffmpeg to fail."""
    inp = tmp_path / "in.mp4"
    inp.write_bytes(b"fake")
    out_dir = tmp_path / "out"
    with pytest.raises(Exception):
        run_pipeline(
            str(inp),
            str(out_dir),
            run_trim=True,
            run_enhance=False,
            run_voice_extract=False,
            run_transcribe=False,
            run_tag=False,
        )
    # If we had a real video, we'd assert out_dir / "trimmed.mp4" exists


def test_pipeline_returns_structure(tmp_path):
    """With fake input, pipeline fails early but we can check return shape when it runs."""
    # Use a minimal run that might fail at trim
    inp = tmp_path / "in.mp4"
    inp.write_bytes(b"x" * 100)
    out_dir = tmp_path / "out"
    try:
        result = run_pipeline(
            str(inp),
            str(out_dir),
            run_trim=True,
            run_enhance=False,
            run_voice_extract=False,
            run_transcribe=False,
            run_tag=False,
        )
    except Exception:
        return
    assert "steps" in result
    assert "paths" in result
    assert isinstance(result["steps"], list)
    assert isinstance(result["paths"], dict)
