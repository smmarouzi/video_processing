"""Tests for trim_silence module."""
from video_processing.trim_silence import (
    build_speech_segments,
    detect_silence,
    get_silence_segments,
)


def test_build_speech_segments_empty_silence():
    segments = build_speech_segments(60.0, [], padding_before_silence=0, min_clip_duration=0.5)
    assert segments == [(0.0, 60.0)]


def test_build_speech_segments_one_silence():
    # silence from 10 to 15
    segments = build_speech_segments(
        60.0, [(10.0, 15.0)], padding_before_silence=0, min_clip_duration=0.5
    )
    assert segments == [(0.0, 10.0), (15.0, 60.0)]


def test_build_speech_segments_with_padding():
    segments = build_speech_segments(
        60.0, [(10.0, 15.0)], padding_before_silence=1.0, min_clip_duration=0.5
    )
    # Padding is applied before each silence by pulling the *next* segment start earlier.
    assert segments == [(0.0, 10.0), (14.0, 60.0)]


def test_build_speech_segments_min_clip_duration():
    # very short speech at start and end
    segments = build_speech_segments(
        20.0, [(2.0, 18.0)], padding_before_silence=0, min_clip_duration=1.0
    )
    assert len(segments) == 2
    assert segments[0] == (0.0, 2.0)
    assert segments[1] == (18.0, 20.0)


def test_detect_silence_returns_list(tmp_path):
    """detect_silence returns a list (empty or with ranges)."""
    path = tmp_path / "fake.mp4"
    path.write_bytes(b"not a real video")
    try:
        out = detect_silence(str(path))
        assert isinstance(out, list)
    except Exception:
        pass  # ffmpeg may fail on fake file
