"""Test helpers: synthesize tiny real audio files and in-memory images.

Audio is generated with the bundled ffmpeg (via static-ffmpeg) so the fixtures
are genuine MP3/M4A/FLAC streams that mutagen and ffprobe accept.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

from PIL import Image


def get_ffmpeg() -> str:
    from static_ffmpeg import run

    ffmpeg, _ = run.get_or_fetch_platform_executables_else_raise()
    return ffmpeg


def make_image_bytes(fmt: str = "JPEG", size=(640, 640), color=(200, 30, 30)) -> bytes:
    """Return encoded image bytes for a solid-color image."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    return buffer.getvalue()


def make_audio(path, codec: str = "libmp3lame") -> Path:
    """Create a ~0.2s silent audio file at ``path`` using ``codec``.

    codec: ``libmp3lame`` (.mp3), ``aac`` (.m4a), ``flac`` (.flac).
    """
    ffmpeg = get_ffmpeg()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "0.2",
            "-c:a",
            codec,
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return Path(path)
