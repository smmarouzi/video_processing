# Video processing pipeline

Modular toolkit for lecture-style videos: **trim silence** (with smooth fades), **upscale & enhance**, **voice extraction & transcription**, and **subject tagging** by time. Includes a full pipeline and tests for each module.

## After cloning the repo

### 1. Requirements

- **Python 3.9+**
- **FFmpeg** on your `PATH` (for trim, enhance, voice extract)
- Optional: **Whisper** for transcription (`pip install openai-whisper`)

### 2. Virtual environment (recommended)

Use a dedicated virtual environment instead of your system (or conda `base`) Python:

```bash
cd video_processing
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# On Windows:  .venv\Scripts\activate
```

You should see `(.venv)` in your prompt. Run all following `pip` and `python` commands in this environment. To leave it later: `deactivate`.

### 3. Install (editable, from repo root)

```bash
pip install -e .
```

For transcription support:

```bash
pip install -e ".[transcribe]"
# Optional faster backend for transcription performance:
pip install -e ".[faster-whisper]"
```

### 4. Run the CLI

From the repo root with the venv activated (and `pip install -e .` already done):

```bash
# List commands
python -m video_processing --help

# Full lecture: silence trim → enhance, with wall-clock timing report (recommended for long videos)
python -m video_processing prepare-final -i lecture.mp4 -o output_dir

# Trim silence only (with fades at cuts)
python -m video_processing trim -i input.mp4 -o trimmed.mp4

# Enhance / upscale
python -m video_processing enhance -i trimmed.mp4 -o enhanced.mp4 --scale 1920:1080 --preset strong

# Extract audio to WAV
python -m video_processing voice -i enhanced.mp4 -o audio.wav

# Transcribe (requires Whisper; use --model small or larger for Farsi)
python -m video_processing transcribe -i audio.wav -o transcript.json --language fa --model small
# Better quality: --model large-v3 --backend faster_whisper (pip install faster-whisper)
# Add punctuation (Farsi): --restore-punctuation (needs: pip install transformers torch protobuf)

# Tag subjects from transcript
python -m video_processing tag --transcript-path transcript.json -o subject_tags.json

# Full pipeline (trim -> enhance -> voice -> transcribe -> tag)
python -m video_processing pipeline -i input.mp4 -o output_dir
```

Without editable install, set `PYTHONPATH`:

```bash
cd video_processing
PYTHONPATH=src python -m video_processing trim -i input.mp4 -o trimmed.mp4
```

---

## Modules

| Module | Role |
|--------|------|
| **trim_silence** | Detect silence, cut it out, and add **short fades** at each cut so there is no hard jump after silence. |
| **enhance** | Upscale (e.g. 1080p) and enhance: denoise, sharpen, contrast/saturation. Runs after trimming. |
| **voice** | Extract audio to WAV; optional **transcription** with Whisper (Farsi and others). |
| **tag_subjects** | Tag video **subjects at exact seconds** using transcript segments (keyword-based; extend with LLM if needed). |
| **pipeline** | Run all steps in order; steps can be toggled. |

### Trim silence (with fades)

- Detects silent intervals (FFmpeg `silencedetect`).
- Keeps only speech segments and concatenates them.
- Applies a **fade-in at the start** and **fade-out at the end** of each kept segment so transitions are smooth (no jump into the next part after silence).
- Optional: write a list of removed silence segments to JSON/TXT.

```bash
python -m video_processing trim -i in.mp4 -o out.mp4 --fade-duration 0.2 --write-silence-list out/silence
```

For long videos with many cuts, trimming auto-switches to a **chunked** mode when segment count exceeds `--max-filter-segments` (default: `120`). In chunked mode, **`--chunk-workers N`** runs several ffmpeg encodes at once (default **4** on `prepare-final`).

### Full video: trim → enhance + timing (`prepare-final`)

One command for a **full-length** file: silence trim, then enhancement, with a **wall-clock report**.

```bash
python -m video_processing prepare-final -i lecture_2h.mp4 -o output_dir
```

Writes under `output_dir`:

| File | Purpose |
|------|---------|
| `trimmed.mp4` | After silence removal (with fades) |
| `final.mp4` | After enhance (deliverable) |
| `TIMING_REPORT.md` | Human-readable trim / enhance / total seconds |
| `timing.json` | Same timing + settings (machine-readable) |

Useful options: `--chunk-workers`, `--max-filter-segments`, `--preset`, `--scale`, `--encoder-threads`, `--write-silence-list PATH`.

**Note:** Enhance **must** run after trim (it needs the trimmed file). “Parallel” here means **parallel chunk encodes during trim** plus **multi-threaded libx264** during enhance—not overlapping trim and enhance on the same output.

### Enhance / upscale

- Runs **after** trimming (or use `prepare-final` which runs both in order).
- Options: `--scale 1920:1080`, `--preset light|default|strong`, `--audio-normalize`, `--crf 18`, `--encoder-threads N` (ffmpeg `-threads` before libx264).

### Voice extraction and transcription

- **Extract**: video → WAV (16 kHz mono by default).
- **Transcribe**: WAV → JSON with `text` and `segments` (start/end/text). Uses Whisper; e.g. `--language fa` for Farsi. Optional **punctuation restoration** for Farsi: `--restore-punctuation` (see [docs/TRANSCRIPTION_MODELS.md](docs/TRANSCRIPTION_MODELS.md)).

### Subject tagging

- Input: transcript JSON with `segments` (each with `start`, `end`, `text`).
- Output: list of `{ start_sec, end_sec, subject, text }` at exact seconds. Default uses keyword rules (Farsi/English); you can pass custom `topic_keywords` in code.

---

## Pipeline

Runs in order: **trim** → **enhance** → **voice extract** → **transcribe** → **tag**. All outputs go under the given output directory.

```bash
python -m video_processing pipeline -i lecture.mp4 -o output_dir
```

Output directory will contain:

- `trimmed.mp4` – after silence trim (with fades)
- `enhanced.mp4` – after upscale/enhance
- `audio.wav` – extracted audio
- `transcript.json` – if Whisper installed
- `subject_tags.json` – if transcript exists

Skip steps with `--no-trim`, `--no-enhance`, `--no-voice`, `--no-transcribe`, `--no-tag`.

---

## Testing

From repo root:

```bash
pip install -e ".[dev]"          # or: pip install pytest
# Optional: pip install -e ".[transcribe]" for Whisper
python -m pytest tests/ -v
```

- **tests/test_trim_silence.py** – segment building, fade logic
- **tests/test_enhance.py** – presets
- **tests/test_voice.py** – extract/transcribe (transcribe requires Whisper)
- **tests/test_tag_subjects.py** – keyword tagging
- **tests/test_pipeline.py** – pipeline structure

Run a single module:

```bash
python -m pytest tests/test_trim_silence.py -v
python -m pytest tests/test_tag_subjects.py -v
```

---

## Project layout

```
video_processing/
├── README.md
├── pyproject.toml
├── requirements.txt
├── docs/
│   └── TRANSCRIPTION_MODELS.md
├── src/
│   └── video_processing/
│       ├── __init__.py
│       ├── _utils.py
│       ├── trim_silence.py   # silence detection + trim with fades
│       ├── enhance.py       # upscale + denoise/sharpen/eq
│       ├── voice.py         # extract audio + transcribe (Whisper)
│       ├── tag_subjects.py  # tag subjects at exact seconds
│       ├── pipeline.py      # run all steps
│       ├── prepare_final.py # timed trim → enhance for full videos
│       ├── cli.py           # CLI entry
│       └── __main__.py
├── tests/
│   ├── test_trim_silence.py
│   ├── test_enhance.py
│   ├── test_voice.py
│   ├── test_tag_subjects.py
│   └── test_pipeline.py
└── scripts/                 # legacy/convenience scripts
```

---

## Options reference

- **prepare-final**: `--silence-threshold-db`, `--silence-duration`, `--padding`, `--min-clip-duration`, `--fade-duration`, `--max-filter-segments`, `--chunk-workers` (default 4), `--write-silence-list`, `--scale`, `--preset`, `--audio-normalize`, `--crf`, `--encoder-threads`
- **Trim**: same silence options as above; `--chunk-workers` default 1
- **Enhance**: `--scale`, `--preset light|default|strong`, `--audio-normalize`, `--crf`, `--encoder-threads`
- **Transcribe**: `--model small|medium|large-v3` (small+ for Farsi), `--backend openai|faster_whisper`, `--language fa`, `--restore-punctuation` (Farsi)
- **Pipeline**: same options plus `--no-trim`, `--no-enhance`, etc., `--whisper-model`, `--transcribe-backend`, `--language`, `--restore-punctuation`

**Better free models for Farsi:** see [docs/TRANSCRIPTION_MODELS.md](docs/TRANSCRIPTION_MODELS.md) (Whisper small/medium/large-v3, faster-whisper, and Farsi fine-tuned options).

Farsi: use `--language fa` in transcribe and pipeline. Subject tags use built-in Farsi/English keywords; override or extend in code via `tag_subjects(..., topic_keywords=...)`.
