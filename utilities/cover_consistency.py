#!/usr/bin/env python3
"""Cover consistency: make each track's embedded art match the album's folder image.

The album ``folder.jpg`` (or ``cover``/``front``) is treated as the source of
truth. For every album that has a folder image, this tool:

1. **Validates the folder image** - it must decode (Pillow) and, when ffprobe is
   available, report real ``dims > 0`` (the same ground truth Jellyfin uses). An
   invalid folder image is NEVER propagated; the album is flagged instead.
2. **Compares the folder image to each track's embedded art perceptually** - a
   difference hash (dHash) so a picture that was merely re-encoded or resized
   still counts as a match (most ``folder.jpg`` files were generated FROM the
   embedded art and re-encoded, so their bytes differ but the image is the same).
3. **Embeds the folder image into every mismatched track** - any track whose
   embedded art is missing or perceptually different from the folder image is
   brought into line, so the whole album matches ``folder.jpg``.

Albums with NO folder image are left to ``generate_folder_art`` (which derives one
from embedded art); this tool only *propagates* an existing, validated folder
image inward.

Safety (shared three-mode contract):
  * ``--scan-only``  report only - never reads embedded art beyond hashing, never writes.
  * ``--dry-run`` (default) - compute the full plan (which tracks would change) but write nothing.
  * ``--execute`` - the only mode that writes. Before any track in an album is
    rewritten, every audio file in that album is copied OFF-LIBRARY to
    ``D:\\music_backup\\_album_backups\\<artist>\\<album>\\`` (never inside the
    album), and each embed goes through the validated core pipeline
    (``core.cover_art.embed_in_file``: validate -> write -> ffprobe read-back).

CLI (via ``cli.py``)::

    python cli.py sync-covers "/path/to/music"            # dry-run (default)
    python cli.py sync-covers "/path/to/music" --scan-only
    python cli.py sync-covers "/path/to/music" --execute
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Allow running as a script (python utilities/cover_consistency.py ...).
if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from utilities.core.audio_file import iter_audio_files
from utilities.core.cover_art import (
    InvalidCoverArt,
    embed_in_file,
    extract_cover_from_file,
    validate_image,
)
from utilities.core.ffprobe import ffprobe_available
from utilities.generate_folder_art import ffmpeg_image_dims
from utilities.repair_covers import backup_album, find_album_folders

# Folder-image discovery (mirrors generate_folder_art).
IMG_EXT = (".jpg", ".jpeg", ".png")
FOLDER_STEMS = ("folder", "cover", "front")

# dHash size -> 64-bit hash. Two images are "the same picture" when their hashes
# differ by <= MATCH_THRESHOLD bits. A re-encode/resize of the same art lands
# around 0-4; genuinely different covers are typically >20, so 8 is comfortably
# separating without false merges.
HASH_SIZE = 8
MATCH_THRESHOLD = 8

LOG_DEFAULT = "outputs/cover_sync.log"


# --------------------------------------------------------------------------- #
# Perceptual hash
# --------------------------------------------------------------------------- #
def dhash(data: bytes, hash_size: int = HASH_SIZE) -> Optional[int]:
    """Difference hash of image *bytes* as a ``hash_size*hash_size``-bit int.

    Robust to re-encoding and scaling (compares relative brightness of adjacent
    pixels). Returns ``None`` if the bytes cannot be decoded as an image.
    """
    try:
        img = Image.open(io.BytesIO(data)).convert("L").resize(
            (hash_size + 1, hash_size), Image.LANCZOS
        )
    except Exception:
        return None
    px = img.load()
    bits = 0
    idx = 0
    for y in range(hash_size):
        for x in range(hash_size):
            bits |= (1 if px[x, y] < px[x + 1, y] else 0) << idx
            idx += 1
    return bits


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two hashes."""
    return bin(a ^ b).count("1")


def images_match(a: Optional[int], b: Optional[int], threshold: int = MATCH_THRESHOLD) -> bool:
    """True if two dHashes are within *threshold* bits (both must be present)."""
    if a is None or b is None:
        return False
    return hamming(a, b) <= threshold


# --------------------------------------------------------------------------- #
# Folder image
# --------------------------------------------------------------------------- #
def find_folder_image(album_dir) -> Optional[Path]:
    """Return the album's folder image (folder/cover/front .jpg/.jpeg/.png), or None."""
    best: Optional[Path] = None
    for entry in sorted(Path(album_dir).iterdir()):
        if entry.is_file() and entry.suffix.lower() in IMG_EXT and entry.stem.lower() in FOLDER_STEMS:
            # Prefer a 'folder' stem, then 'cover', then 'front'.
            if best is None or FOLDER_STEMS.index(entry.stem.lower()) < FOLDER_STEMS.index(best.stem.lower()):
                best = entry
    return best


def validate_folder_image(data: bytes) -> bool:
    """True if the folder image is a real, decodable cover with positive dims.

    Pillow decode + magic bytes via ``validate_image``; when ffprobe is present,
    also require ffmpeg to read positive dimensions (catches the width=0 case
    Pillow alone accepts).
    """
    try:
        validate_image(data)
    except InvalidCoverArt:
        return False
    if ffprobe_available():
        dims = ffmpeg_image_dims(data)
        if not dims or dims[0] <= 0 or dims[1] <= 0:
            return False
    return True


# --------------------------------------------------------------------------- #
# Per-album check
# --------------------------------------------------------------------------- #
# status values
NO_FOLDER_IMAGE = "no_folder_image"   # nothing to propagate (generate_folder_art's job)
FOLDER_INVALID = "folder_invalid"     # folder image is corrupt/0x0 -> flagged, never propagated
CONSISTENT = "consistent"             # every track already matches the folder image
NEEDS_SYNC = "needs_sync"             # >=1 track missing/different -> would embed folder image


@dataclass
class AlbumResult:
    album: Path
    status: str
    folder_image: Optional[Path] = None
    total_tracks: int = 0
    mismatches: List[Tuple[Path, str]] = field(default_factory=list)  # (track, 'no_art'|'different')
    embedded: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)


def check_album(album_dir) -> AlbumResult:
    """Diagnose one album's folder<->embedded cover consistency (no writes)."""
    album = Path(album_dir)
    folder_img = find_folder_image(album)
    if folder_img is None:
        return AlbumResult(album=album, status=NO_FOLDER_IMAGE)

    try:
        folder_bytes = folder_img.read_bytes()
    except OSError as exc:
        return AlbumResult(album=album, status=FOLDER_INVALID, folder_image=folder_img,
                           errors=[f"read {folder_img.name}: {exc}"])

    if not validate_folder_image(folder_bytes):
        return AlbumResult(album=album, status=FOLDER_INVALID, folder_image=folder_img,
                           errors=[f"{folder_img.name}: invalid/unreadable cover"])

    folder_hash = dhash(folder_bytes)
    result = AlbumResult(album=album, status=CONSISTENT, folder_image=folder_img)
    for track in iter_audio_files(album):
        result.total_tracks += 1
        art = extract_cover_from_file(track)
        if not art:
            result.mismatches.append((track, "no_art"))
            continue
        if not images_match(folder_hash, dhash(art)):
            result.mismatches.append((track, "different"))
    if result.mismatches:
        result.status = NEEDS_SYNC
    return result


def sync_album(album_dir, *, execute: bool, backup_root=None) -> AlbumResult:
    """Check an album and, in *execute* mode, embed the folder image into every
    mismatched track (after backing the album up OFF-LIBRARY). Returns the result
    with ``embedded``/``failed`` populated."""
    result = check_album(album_dir)
    if result.status != NEEDS_SYNC or not execute:
        return result

    folder_bytes = result.folder_image.read_bytes()
    backup_album(result.album, backup_root=backup_root)  # off-library copy before any rewrite
    for track, _reason in result.mismatches:
        try:
            embed_in_file(track, folder_bytes)  # validated write + ffprobe read-back
            result.embedded += 1
        except Exception as exc:  # fail-soft per file
            result.failed += 1
            result.errors.append(f"{track.name}: {exc}")
    return result


# --------------------------------------------------------------------------- #
# Library orchestration
# --------------------------------------------------------------------------- #
def sync_library(
    path,
    *,
    scan_only: bool = False,
    dry_run: bool = False,
    execute: bool = False,
    log_path: Optional[str] = None,
    backup_root=None,
) -> Dict[str, object]:
    """Walk ``path`` and reconcile embedded art with each album's folder image.

    Exactly one of scan_only / dry_run / execute governs writes; execute is the
    only mode that modifies audio. Returns a summary dict.
    """
    # Resolve mode (execute wins, then scan_only, else dry-run default).
    do_execute = bool(execute) and not scan_only
    summary: Dict[str, object] = {
        "albums": 0,
        "with_folder_image": 0,
        "consistent": 0,
        "needs_sync": 0,
        "no_folder_image": 0,
        "folder_invalid": 0,
        "tracks_to_embed": 0,
        "tracks_embedded": 0,
        "tracks_failed": 0,
        "flagged": [],       # albums needing human attention (folder_invalid)
        "details": [],       # per-album needs_sync detail
        "mode": "execute" if do_execute else ("scan-only" if scan_only else "dry-run"),
    }

    albums = find_album_folders(path)  # shares recycle/system/backup exclusions
    log_fh = None
    if do_execute:
        lp = Path(log_path or LOG_DEFAULT)
        lp.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(lp, "a", encoding="utf-8")

    try:
        for album in albums:
            summary["albums"] = int(summary["albums"]) + 1
            res = sync_album(album, execute=do_execute, backup_root=backup_root)

            if res.status == NO_FOLDER_IMAGE:
                summary["no_folder_image"] = int(summary["no_folder_image"]) + 1
                continue
            summary["with_folder_image"] = int(summary["with_folder_image"]) + 1

            if res.status == FOLDER_INVALID:
                summary["folder_invalid"] = int(summary["folder_invalid"]) + 1
                summary["flagged"].append({"album": str(res.album), "errors": res.errors})  # type: ignore[attr-defined]
                continue
            if res.status == CONSISTENT:
                summary["consistent"] = int(summary["consistent"]) + 1
                continue

            # NEEDS_SYNC
            summary["needs_sync"] = int(summary["needs_sync"]) + 1
            summary["tracks_to_embed"] = int(summary["tracks_to_embed"]) + len(res.mismatches)
            summary["tracks_embedded"] = int(summary["tracks_embedded"]) + res.embedded
            summary["tracks_failed"] = int(summary["tracks_failed"]) + res.failed
            summary["details"].append({  # type: ignore[attr-defined]
                "album": str(res.album),
                "folder_image": res.folder_image.name if res.folder_image else None,
                "mismatched": [(t.name, r) for t, r in res.mismatches],
                "embedded": res.embedded,
                "failed": res.failed,
            })
            if log_fh and res.embedded:
                for track, reason in res.mismatches:
                    log_fh.write(f"{album}\t{track.name}\t{reason}\tembedded_folder_image\n")
    finally:
        if log_fh:
            log_fh.close()

    return summary


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_summary(summary: Dict[str, object]) -> None:
    print("\n=== Cover Consistency Summary ===")
    print(f"Mode:                 {summary['mode']}")
    print(f"Albums scanned:       {summary['albums']}")
    print(f"  with folder image:  {summary['with_folder_image']}")
    print(f"  consistent:         {summary['consistent']}")
    print(f"  need sync:          {summary['needs_sync']}")
    print(f"  no folder image:    {summary['no_folder_image']} (handled by folder-art step)")
    print(f"  folder image bad:   {summary['folder_invalid']} (flagged, NOT propagated)")
    verb = "embedded" if summary["mode"] == "execute" else "would embed"
    print(f"Tracks {verb}: {summary['tracks_to_embed']}"
          + (f"  (ok {summary['tracks_embedded']}, failed {summary['tracks_failed']})"
             if summary["mode"] == "execute" else ""))
    flagged = summary.get("flagged") or []
    if flagged:
        print(f"\nFLAGGED - folder image invalid ({len(flagged)}):")
        for f in flagged[:25]:
            print(f"  {f['album']}")
    if summary["mode"] != "execute":
        print("(no changes made)")


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Reconcile embedded track art with the album folder image "
                    "(folder.jpg authoritative; perceptual match; write into mismatched tracks).")
    parser.add_argument("path", help="Library / artist / album folder")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scan-only", action="store_true", help="Report only; never write")
    mode.add_argument("--dry-run", action="store_true", help="Show the plan; write nothing (default)")
    mode.add_argument("--execute", action="store_true", help="Embed folder image into mismatched tracks")
    parser.add_argument("--log", default=None, help=f"Execute-mode log path (default {LOG_DEFAULT})")
    args = parser.parse_args(argv)

    summary = sync_library(
        args.path,
        scan_only=args.scan_only,
        dry_run=args.dry_run or not (args.scan_only or args.execute),
        execute=args.execute,
        log_path=args.log,
    )
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
