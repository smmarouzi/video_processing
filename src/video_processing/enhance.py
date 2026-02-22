"""
Upscaling and quality enhancement (denoise, sharpen, contrast/saturation).

Runs after trimming. Use scale for upscaling (e.g. 1920:1080).
"""

from typing import List, Optional

from video_processing._utils import run_ffmpeg


_PRESETS = {
    "light": ["hqdn3d=2:2:2:2", "unsharp=5:5:0.5:5:5:0.25", "eq=contrast=1.05:saturation=1.1"],
    "default": ["hqdn3d=4:4:3:3", "unsharp=5:5:0.8:5:5:0.4", "eq=contrast=1.1:saturation=1.2"],
    "strong": ["hqdn3d=6:6:5:5", "unsharp=5:5:1.2:5:5:0.6", "eq=contrast=1.2:saturation=1.35"],
}


def enhance_video(
    input_path: str,
    output_path: str,
    *,
    scale: Optional[str] = None,
    preset: str = "default",
    audio_normalize: bool = False,
    crf: int = 18,
) -> None:
    """
    Upscale and/or enhance video: denoise, sharpen, contrast/saturation.
    preset: light | default | strong.
    scale: e.g. '1920:1080' for 1080p upscaling.
    """
    filters: List[str] = []
    if scale:
        filters.append(f"scale={scale}:flags=lanczos")
    filters.extend(_PRESETS.get(preset, _PRESETS["default"]))
    vf = ",".join(filters)
    cmd = ["-i", input_path, "-vf", vf]
    if audio_normalize:
        cmd += ["-af", "dynaudnorm"]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium", "-c:a", "aac", output_path]
    run_ffmpeg(cmd)
