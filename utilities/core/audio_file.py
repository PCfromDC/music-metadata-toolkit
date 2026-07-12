"""Shared audio-file helpers: supported formats, iteration, and the canonical
directory-exclusion rules used by every library walk.

The exclusion rules live here (the module every walker already imports) so scan,
validate, dedupe, cover-repair, and folder-art all skip the *same* non-album
directories - NAS recycle bins, OS/system metadata dirs, and the toolkit's own
off-library backup stores - and can never drift apart.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

# Audio containers the toolkit reads/writes cover art for.
AUDIO_EXTS = {".mp3", ".m4a", ".mp4", ".flac"}

# Directory names that are never a real album folder. Their contents are usually
# deleted/stub files (recycle bins) or non-music system metadata, so counting them
# as albums/tracks pollutes every report. Compared case-insensitively.
EXCLUDED_DIR_NAMES = {
    ".recycle", "#recycle", "@eadir", "#snapshot",              # Synology / OMV / QNAP NAS
    "$recycle.bin", "recycler", "system volume information",    # Windows
    ".trashes", ".trash", ".spotlight-v100", ".fseventsd",      # macOS
    ".documentrevisions-v100", ".temporaryitems", ".ds_store",
    ".stfolder", ".stversions",                                 # Syncthing
    "lost+found", "found.000",
    "backups", ".cover_backup", "_duplicates",                  # the toolkit's own stores
}

# Any directory whose (lower-cased) name starts with one of these markers is a
# NAS/OS system dir - e.g. "@eaDir", "#recycle", "$RECYCLE.BIN", ".Trash-1000".
# Note: a bare "." prefix is deliberately NOT excluded, so real album/artist
# folders that legitimately start with a dot (".38 Special", "...And You Will
# Know Us by the Trail of Dead") are still scanned.
EXCLUDED_DIR_PREFIXES = ("@", "#", "$", ".trash", ".spotlight", ".fseventsd")


def is_excluded_dir(name) -> bool:
    """True if a single directory *name* is a recycle-bin / system / backup dir
    that must never be treated as an album folder."""
    n = os.path.basename(str(name).rstrip("/\\")).strip().lower()
    return n in EXCLUDED_DIR_NAMES or n.startswith(EXCLUDED_DIR_PREFIXES)


def is_excluded_path(root, path) -> bool:
    """True if any directory component of *path* relative to *root* is excluded,
    so a walk can prune whole subtrees (e.g. everything under ``.recycle/``)."""
    root_p, p = Path(root), Path(path)
    try:
        parts = p.relative_to(root_p).parts
    except ValueError:
        parts = p.parts
    return any(is_excluded_dir(part) for part in parts)


def prune_dirs(dirnames) -> None:
    """In-place filter of an ``os.walk`` *dirnames* list so the walk never
    descends into excluded directories. Mutates the list (os.walk contract)."""
    dirnames[:] = [d for d in dirnames if not is_excluded_dir(d)]


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
