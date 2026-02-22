"""
Tag video subjects/topics at exact seconds.

Uses transcript segments (from voice.transcribe) to assign subject tags
per time range. Output: list of {start_sec, end_sec, subject/tags}.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Simple keyword -> subject mapping (extend or replace with LLM/NER)
_DEFAULT_TOPICS: Dict[str, List[str]] = {
    "introduction": ["مقدمه", "intro", "introduction", "سلام", "خوش آمد"],
    "definition": ["تعریف", "definition", "معنی", "meaning"],
    "example": ["مثال", "example", "نمونه", "sample"],
    "conclusion": ["نتیجه", "conclusion", "جمع‌بندی", "خلاصه", "summary"],
    "question": ["سوال", "question", "پرسش", "؟"],
}


def tag_subjects(
    segments: List[Dict[str, Any]],
    *,
    topic_keywords: Optional[Dict[str, List[str]]] = None,
    default_subject: str = "general",
    output_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Assign subject tags to segments by keyword match on segment text.
    segments: list of {"start", "end", "text"} (e.g. from voice.transcribe).
    topic_keywords: map subject name -> list of keywords (default: Farsi/English).
    Returns list of {"start_sec", "end_sec", "subject", "text"}.
    """
    topics = topic_keywords or _DEFAULT_TOPICS
    tagged: List[Dict[str, Any]] = []
    for seg in segments:
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = (seg.get("text") or "").strip()
        subject = default_subject
        text_lower = text.lower()
        for subj, keywords in topics.items():
            if any(kw.lower() in text_lower for kw in keywords):
                subject = subj
                break
        tagged.append({
            "start_sec": round(start, 2),
            "end_sec": round(end, 2),
            "subject": subject,
            "text": text[:200],
        })

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(tagged, f, ensure_ascii=False, indent=2)

    return tagged
