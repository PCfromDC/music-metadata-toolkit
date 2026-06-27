"""Shared audio-file helpers: supported formats and iteration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

# Audio containers the toolkit reads/writes cover art for.
AUDIO_EXTS = {".mp3", ".m4a", ".mp4", ".flac"}


def is_audio_file(path) -> bool:
    """True if ``path`` has a supported audio extension."""
    return os.path.splitext(str(path))[1].lower() in AUDIO_EXTS


def iter_audio_files(folder) -> Iterator[Path]:
    """Yield audio files directly inside ``folder``, sorted by name."""
    base = Path(folder)
    if not base.is_dir():
        return
    for entry in sorted(base.iterdir()):
        if entry.is_file() and entry.suffix.lower() in AUDIO_EXTS:
            yield entry
