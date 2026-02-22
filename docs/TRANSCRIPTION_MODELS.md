# Better free models for Farsi transcription

The default setup uses **Whisper** (openai-whisper). For Farsi, the **base** model often produces messy text; use at least **small**, or a larger/faster option below.

## Options (all free)

### 1. Whisper **small** (default for Farsi)

- **Use:** `--model small` (or rely on default: Farsi is auto-upgraded from base to small).
- **Install:** `pip install openai-whisper`
- **Quality:** Good Farsi, runs on CPU.
- **Command:**  
  `python -m video_processing transcribe -i audio.wav -o transcript.json --language fa --model small`

### 2. Whisper **medium** or **large-v3** (better quality, more RAM)

- **Use:** `--model medium` or `--model large-v3`
- **Quality:** Better Farsi, fewer errors.
- **Cost:** ~5GB (medium) or ~10GB (large-v3) RAM; GPU recommended for large-v3.
- **Command:**  
  `python -m video_processing transcribe -i audio.wav -o transcript.json --language fa --model large-v3`

### 3. **faster-whisper** (same quality, 4x–8x faster, less RAM)

- **Use:** `--backend faster_whisper` with any Whisper size (e.g. `--model large-v3`).
- **Install:** `pip install faster-whisper`
- **Quality:** Same as openai-whisper for the same model (e.g. large-v3).
- **Benefit:** Faster and lower memory, so **large-v3** is more practical on modest hardware.
- **Command:**  
  `python -m video_processing transcribe -i audio.wav -o transcript.json --language fa --model large-v3 --backend faster_whisper`

**Pipeline:**  
`python -m video_processing pipeline -i video.mp4 -o out --language fa --whisper-model large-v3 --transcribe-backend faster_whisper`

### 4. Farsi fine-tuned models (Hugging Face, optional)

These are specialized for Persian and can give better accuracy than generic Whisper:

- **hezarai/whisper-small-fa** (Hezar) – Whisper small fine-tuned on Common Voice Persian.  
  Use via Hezar: `pip install hezar` and their API; not wired into this CLI yet.
- **vhdm/whisper-large-fa-v1** – Whisper large-v3-turbo fine-tuned for Persian (reported ~14% WER).  
  Can be used with Hugging Face `transformers`; not wired into this CLI yet.

You can add support for these in `src/video_processing/voice.py` (e.g. a `backend="hezar"` or load from Hugging Face) if you want to use them inside this project.

## Summary

| Option                    | Quality (Farsi) | Speed / RAM      | Install              |
|---------------------------|-----------------|------------------|----------------------|
| Whisper small (default)   | Good            | OK on CPU        | openai-whisper      |
| Whisper medium/large-v3  | Better          | Heavy            | openai-whisper      |
| faster-whisper + large-v3| Same as above   | Faster, less RAM | faster-whisper       |

### 5. Punctuation restoration (Farsi)

Whisper usually does not output punctuation. To add periods, commas, and other marks after transcription:

- **Use:** `--restore-punctuation` when transcribing (or in the pipeline).
- **Install:** `pip install transformers torch protobuf` (and `sentencepiece` if required by the model).
- **Model:** For Farsi, the CLI uses **Aminrhmni/PersianAutomaticPunctuation** (Hugging Face). Runs automatically on the full text and on each segment when `--restore-punctuation` is set and `--language fa`.

**Command:**  
`python -m video_processing transcribe -i audio.wav -o transcript.json --language fa --restore-punctuation`

**Pipeline:**  
`python -m video_processing pipeline -i video.mp4 -o out --language fa --restore-punctuation`

---

**Recommendation:** For best free quality with this CLI, use **faster-whisper** and **large-v3**:

```bash
pip install faster-whisper
python -m video_processing transcribe -i audio.wav -o transcript.json --language fa --model large-v3 --backend faster_whisper
```
