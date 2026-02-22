"""
Voice extraction and transcription.

- Extract audio track to WAV (for downstream use or transcription).
- Transcribe with Whisper or faster-whisper (optional deps); supports Farsi and others.
- Optional punctuation restoration (Farsi: Hugging Face Persian model; others: optional).

Better free options for Farsi:
- --model small (default for fa): good quality, runs on CPU.
- --model medium or large-v3: better quality, needs more RAM/GPU.
- --backend faster_whisper: same quality as Whisper, 4x–8x faster, less RAM; use with --model large-v3.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from video_processing._utils import run_ffmpeg


def restore_punctuation(
    text: str,
    language: str = "fa",
    *,
    model_id: Optional[str] = None,
    max_chunk_chars: int = 400,
) -> str:
    """
    Add punctuation to raw transcript text using a Hugging Face model.
    Requires: pip install transformers torch protobuf (sentencepiece may be needed for MT5).

    language: "fa" for Farsi (uses Persian punctuation model); other languages not yet supported.
    """
    text = (text or "").strip()
    if not text:
        return text

    if language == "fa" or (model_id and "persian" in model_id.lower()):
        model_id = model_id or "Aminrhmni/PersianAutomaticPunctuation"
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
        except ImportError:
            raise ImportError(
                "Punctuation restoration requires: pip install transformers torch"
            ) from None
        try:
            # MT5/Persian model uses SentencePiece; use slow tokenizer to avoid conversion errors
            tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=False)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
            pipe = pipeline(
                "text2text-generation",
                model=model,
                tokenizer=tokenizer,
                max_length=min(256, max_chunk_chars + 50),
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load punctuation model {model_id}: {e}. "
                "Ensure transformers, torch, and protobuf are installed (pip install transformers torch protobuf)."
            ) from e

        # Process in chunks to avoid overflow (model has max length)
        chunks = []
        for i in range(0, len(text), max_chunk_chars):
            chunk = text[i : i + max_chunk_chars]
            if not chunk.strip():
                continue
            out = pipe(chunk, max_length=min(256, len(chunk) + 50))
            if out and isinstance(out, list) and len(out) > 0:
                gen = out[0].get("generated_text", "").strip()
                chunks.append(gen if gen else chunk)
            else:
                chunks.append(chunk)
        return " ".join(chunks) if chunks else text

    # Fallback: simple period after common sentence endings (weak)
    if not text.endswith((".", "?", "!")):
        text = text + "."
    return text


def extract_audio(
    input_path: str,
    output_wav_path: str,
    *,
    sample_rate: int = 16000,
    mono: bool = True,
) -> None:
    """Extract audio from video to WAV (16kHz mono by default for Whisper)."""
    cmd = [
        "-i", input_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1" if mono else "2",
        output_wav_path,
    ]
    run_ffmpeg(cmd)


def _transcribe_faster_whisper(
    audio_path: str,
    model_size: str,
    language: Optional[str],
) -> Dict[str, Any]:
    """Use faster-whisper (CTranslate2); same quality, faster and less RAM."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper backend requires: pip install faster-whisper"
        ) from None

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments_gen, info = model.transcribe(audio_path, language=language)
    segments_list = list(segments_gen)
    text = " ".join(s.text for s in segments_list).strip()
    out: Dict[str, Any] = {"text": text}
    out["segments"] = [
        {"start": s.start, "end": s.end, "text": (s.text or "").strip()}
        for s in segments_list
    ]
    return out


def _transcribe_openai_whisper(
    audio_path: str,
    model_size: str,
    language: Optional[str],
) -> Dict[str, Any]:
    """Use openai-whisper (PyTorch)."""
    try:
        import whisper
    except ImportError:
        raise ImportError(
            "Transcription requires: pip install openai-whisper"
        ) from None

    model = whisper.load_model(model_size)
    result = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=False,
    )
    out = {"text": result.get("text", "").strip()}
    if result.get("segments"):
        out["segments"] = [
            {"start": s["start"], "end": s["end"], "text": (s.get("text") or "").strip()}
            for s in result["segments"]
        ]
    else:
        out["segments"] = []
    return out


def transcribe(
    audio_path: str,
    output_path: Optional[str] = None,
    *,
    model_size: Optional[str] = None,
    language: Optional[str] = None,
    return_segments: bool = True,
    backend: str = "openai",
    add_punctuation: bool = False,
) -> Dict[str, Any]:
    """
    Transcribe audio with Whisper or faster-whisper.

    Backends:
    - openai: pip install openai-whisper (default).
    - faster_whisper: pip install faster-whisper — same quality, 4x–8x faster, less RAM.

    model_size: tiny, base, small, medium, large-v2, large-v3 (and large for openai).
    For Farsi, prefer at least "small"; "medium" or "large-v3" are better if you have RAM/GPU.
    If language is "fa" and model_size is "base", "small" is used automatically for better Farsi.

    language: e.g. "fa" for Farsi, None for auto-detect.

    add_punctuation: if True, run a punctuation restoration model on the transcript
        (for Farsi: pip install transformers torch; uses Aminrhmni/PersianAutomaticPunctuation).
    """
    if model_size is None:
        model_size = "base"
    if language == "fa" and model_size == "base":
        model_size = "small"

    if backend == "faster_whisper":
        out = _transcribe_faster_whisper(audio_path, model_size, language)
    else:
        out = _transcribe_openai_whisper(audio_path, model_size, language)

    if add_punctuation and out.get("text") and language == "fa":
        try:
            out["text"] = restore_punctuation(out["text"], language="fa")
            if out.get("segments"):
                for seg in out["segments"]:
                    if seg.get("text"):
                        seg["text"] = restore_punctuation(seg["text"], language="fa", max_chunk_chars=200)
        except Exception as e:
            out["_punctuation_error"] = str(e)

    if not return_segments and "segments" in out:
        del out["segments"]

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    return out
