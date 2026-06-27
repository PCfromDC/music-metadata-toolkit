"""ffprobe ground-truth helpers - the same engine Jellyfin uses for cover art.

The toolkit's album art was being read by Jellyfin (which uses ffmpeg/ffprobe to
extract embedded pictures) as ``width=0, height=0`` - i.e. invalid. To validate
exactly what the consumer sees, we run ffprobe against the saved file.

ffprobe is resolved from the ``static-ffmpeg`` package (which downloads a bundled
binary on first use), falling back to one on PATH. If none is available the
caller falls back to a Pillow decode and treats consumer-parity as unverified.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from typing import Optional, Tuple


@lru_cache(maxsize=1)
def get_ffprobe() -> Optional[str]:
    """Return a path to an ffprobe binary, or ``None`` if unavailable."""
    try:
        from static_ffmpeg import run

        _, ffprobe = run.get_or_fetch_platform_executables_else_raise()
        if ffprobe:
            return ffprobe
    except Exception:
        pass
    return shutil.which("ffprobe")


def ffprobe_available() -> bool:
    """True if an ffprobe binary can be resolved."""
    return get_ffprobe() is not None


def attached_pic_dims(filepath) -> Optional[Tuple[int, int]]:
    """Return ``(width, height)`` of the file's embedded cover (attached_pic) stream.

    Returns ``None`` if there is no cover stream, ffprobe is unavailable, or the
    probe fails. A returned ``(0, 0)`` means ffprobe found a cover stream but it
    has no real dimensions - exactly the corruption Jellyfin reports.
    """
    ffprobe = get_ffprobe()
    if not ffprobe:
        return None
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    for stream in data.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        disposition = stream.get("disposition", {})
        if disposition.get("attached_pic") == 1 or stream.get("codec_name") in (
            "mjpeg",
            "png",
        ):
            width = int(stream.get("width", 0) or 0)
            height = int(stream.get("height", 0) or 0)
            return (width, height)
    return None
