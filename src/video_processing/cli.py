"""Command-line interface: trim, enhance, voice, tag, pipeline."""

import argparse
import sys
from pathlib import Path

# Ensure package is importable when run as python -m video_processing from repo root
if __name__ == "__main__":
    _src = Path(__file__).resolve().parent.parent
    if str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

from video_processing.trim_silence import get_silence_segments, trim_silence_with_fades
from video_processing.enhance import enhance_video
from video_processing.voice import extract_audio, transcribe
from video_processing.tag_subjects import tag_subjects
from video_processing.pipeline import run_pipeline


def _add_io(p: argparse.ArgumentParser) -> None:
    p.add_argument("--input", "-i", required=True, help="Input video path")
    p.add_argument("--output", "-o", required=True, help="Output path")


def cmd_trim(args: argparse.Namespace) -> None:
    from video_processing.trim_silence import detect_silence
    trim_silence_with_fades(
        args.input,
        args.output,
        threshold_db=args.silence_threshold_db,
        min_silence_duration=args.silence_duration,
        padding_before_silence=args.padding,
        min_clip_duration=args.min_clip_duration,
        fade_duration=args.fade_duration,
        write_silence_list_path=args.write_silence_list or None,
    )
    print("Trimmed (with fades):", args.output)


def cmd_enhance(args: argparse.Namespace) -> None:
    enhance_video(
        args.input,
        args.output,
        scale=args.scale or None,
        preset=args.preset,
        audio_normalize=args.audio_normalize,
        crf=args.crf,
    )
    print("Enhanced:", args.output)


def cmd_voice(args: argparse.Namespace) -> None:
    extract_audio(args.input, args.output, sample_rate=args.sample_rate)
    print("Audio extracted:", args.output)


def cmd_transcribe(args: argparse.Namespace) -> None:
    out = transcribe(
        args.input,
        output_path=args.output,
        model_size=args.model,
        language=args.language or None,
        backend=getattr(args, "backend", "openai"),
        add_punctuation=getattr(args, "restore_punctuation", False),
    )
    print("Transcription written to:", args.output)
    if args.print_text:
        print(out.get("text", "")[:2000])


def cmd_tag(args: argparse.Namespace) -> None:
    import json
    with open(args.transcript_path, encoding="utf-8") as f:
        data = json.load(f)
    segments = data.get("segments", [])
    if not segments:
        print("No segments in transcript; run transcribe first.", file=sys.stderr)
        sys.exit(1)
    tagged = tag_subjects(segments, output_path=args.output)
    print("Subject tags written to:", args.output)
    for t in tagged[:10]:
        print(f"  {t['start_sec']:.1f}-{t['end_sec']:.1f}s: {t['subject']}")


def cmd_pipeline(args: argparse.Namespace) -> None:
    result = run_pipeline(
        args.input,
        args.output_dir,
        run_trim=not args.no_trim,
        run_enhance=not args.no_enhance,
        run_voice_extract=not args.no_voice,
        run_transcribe=not args.no_transcribe,
        run_tag=not args.no_tag,
        trim_options={
            "threshold_db": args.silence_threshold_db,
            "min_silence_duration": args.silence_duration,
            "fade_duration": args.fade_duration,
            "write_silence_list_path": args.write_silence_list or None,
        },
        enhance_options={
            "scale": args.scale or None,
            "preset": args.preset,
            "audio_normalize": args.audio_normalize,
            "crf": args.crf,
        },
        transcribe_options={
            "model_size": args.whisper_model,
            "language": args.language or None,
            "backend": getattr(args, "transcribe_backend", "openai"),
            "add_punctuation": getattr(args, "restore_punctuation", False),
        },
    )
    print("Pipeline steps:", result["steps"])
    print("Outputs:", result["paths"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Video processing: trim, enhance, voice, tag, pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    # trim
    p_trim = sub.add_parser("trim", help="Trim silence with fades at cuts")
    _add_io(p_trim)
    p_trim.add_argument("--silence-threshold-db", type=float, default=-35.0)
    p_trim.add_argument("--silence-duration", type=float, default=1.0)
    p_trim.add_argument("--padding", type=float, default=0.0, help="Padding before silence (sec)")
    p_trim.add_argument("--min-clip-duration", type=float, default=0.5)
    p_trim.add_argument("--fade-duration", type=float, default=0.2)
    p_trim.add_argument("--write-silence-list", default=None, metavar="PATH")
    p_trim.set_defaults(run=cmd_trim)

    # enhance
    p_enhance = sub.add_parser("enhance", help="Upscale and enhance (denoise, sharpen, eq)")
    _add_io(p_enhance)
    p_enhance.add_argument("--scale", default=None, help="e.g. 1920:1080")
    p_enhance.add_argument("--preset", choices=("light", "default", "strong"), default="default")
    p_enhance.add_argument("--audio-normalize", action="store_true")
    p_enhance.add_argument("--crf", type=int, default=18)
    p_enhance.set_defaults(run=cmd_enhance)

    # voice (extract audio)
    p_voice = sub.add_parser("voice", help="Extract audio to WAV")
    _add_io(p_voice)
    p_voice.add_argument("--sample-rate", type=int, default=16000)
    p_voice.set_defaults(run=cmd_voice)

    # transcribe
    p_trans = sub.add_parser("transcribe", help="Transcribe audio (Whisper or faster-whisper)")
    p_trans.add_argument("--input", "-i", required=True, help="Input WAV or video")
    p_trans.add_argument("--output", "-o", required=True, help="Output JSON path")
    p_trans.add_argument("--model", default="small", help="Model: tiny, base, small, medium, large-v3 (small recommended for Farsi)")
    p_trans.add_argument("--language", default=None, help="e.g. fa for Farsi")
    p_trans.add_argument("--backend", choices=("openai", "faster_whisper"), default="openai",
        help="openai (default) or faster_whisper (faster, less RAM; pip install faster-whisper)")
    p_trans.add_argument("--restore-punctuation", action="store_true",
        help="Add punctuation (Farsi: pip install transformers torch; uses Hugging Face Persian model)")
    p_trans.add_argument("--print-text", action="store_true")
    p_trans.set_defaults(run=cmd_transcribe)

    # tag
    p_tag = sub.add_parser("tag", help="Tag subjects from transcript segments")
    p_tag.add_argument("--transcript-path", required=True)
    p_tag.add_argument("--output", "-o", required=True)
    p_tag.set_defaults(run=cmd_tag)

    # pipeline
    p_pipe = sub.add_parser("pipeline", help="Run full pipeline: trim -> enhance -> voice -> transcribe -> tag")
    p_pipe.add_argument("--input", "-i", required=True)
    p_pipe.add_argument("--output-dir", "-o", required=True)
    p_pipe.add_argument("--no-trim", action="store_true")
    p_pipe.add_argument("--no-enhance", action="store_true")
    p_pipe.add_argument("--no-voice", action="store_true")
    p_pipe.add_argument("--no-transcribe", action="store_true")
    p_pipe.add_argument("--no-tag", action="store_true")
    p_pipe.add_argument("--silence-threshold-db", type=float, default=-35.0)
    p_pipe.add_argument("--silence-duration", type=float, default=1.0)
    p_pipe.add_argument("--fade-duration", type=float, default=0.2)
    p_pipe.add_argument("--write-silence-list", default=None)
    p_pipe.add_argument("--scale", default=None)
    p_pipe.add_argument("--preset", default="default")
    p_pipe.add_argument("--audio-normalize", action="store_true")
    p_pipe.add_argument("--crf", type=int, default=18)
    p_pipe.add_argument("--whisper-model", default="small", help="tiny, base, small, medium, large-v3 (small+ for Farsi)")
    p_pipe.add_argument("--transcribe-backend", choices=("openai", "faster_whisper"), default="openai")
    p_pipe.add_argument("--restore-punctuation", action="store_true", help="Add punctuation to transcript (Farsi)")
    p_pipe.add_argument("--language", default=None)
    p_pipe.set_defaults(run=cmd_pipeline)

    args = parser.parse_args()
    args.run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
