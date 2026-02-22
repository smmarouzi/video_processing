"""Tests for tag_subjects module."""
import json
import pytest
from video_processing.tag_subjects import tag_subjects


def test_tag_subjects_keyword_match():
    segments = [
        {"start": 0, "end": 5, "text": "این مقدمه است"},
        {"start": 5, "end": 10, "text": "یک مثال بزنیم"},
        {"start": 10, "end": 15, "text": "نتیجه می‌گیریم"},
    ]
    tagged = tag_subjects(segments)
    assert len(tagged) == 3
    assert tagged[0]["subject"] == "introduction"
    assert tagged[1]["subject"] == "example"
    assert tagged[2]["subject"] == "conclusion"


def test_tag_subjects_default_subject():
    segments = [{"start": 0, "end": 1, "text": "random content xyz"}]
    tagged = tag_subjects(segments, default_subject="other")
    assert tagged[0]["subject"] == "other"


def test_tag_subjects_output_path(tmp_path):
    segments = [{"start": 0, "end": 1, "text": "مقدمه"}]
    out = tmp_path / "tags.json"
    tag_subjects(segments, output_path=str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["subject"] == "introduction"
    assert data[0]["start_sec"] == 0
