#!/usr/bin/env python3
"""Repair already-corrupted embedded album art across a music library.

The toolkit previously embedded invalid cover art - ffprobe/Jellyfin reported
``width=0, height=0`` for tracks whose APIC/covr/picture block held empty or
junk bytes. This tool finds those tracks, re-fetches a real cover (iTunes ->
MusicBrainz Cover Art Archive -> Discogs), and re-embeds it through the
validated core pipeline so the post-write ffprobe read-back proves real
dimensions.

Detection is ground-truth: every file is checked with ffprobe
(:func:`utilities.core.ffprobe.attached_pic_dims`) and cross-checked by
extracting the embedded bytes and running them through
:func:`utilities.core.cover_art.validate_image`. A track is flagged when the
cover stream reports non-positive dimensions, the embedded bytes are missing,
or the bytes fail to decode.

Safety:
  * MANDATORY backup - before any track in an album is rewritten, every audio
    file in that album is copied to a sibling ``backups/`` folder.
  * Every embed goes through ``core.cover_art`` (validated, hard-fail per file,
    fail-soft per album). Bytes are never embedded without validation.
  * Graceful - rate limits, missing API keys, and "no result" leave files
    untouched, log, and continue. A single album never crashes the batch.

CLI (via ``cli.py``)::

    python cli.py repair-covers "/path/to/music/Artist"
    python cli.py repair-covers "/path/to/music/Artist" --scan-only
    python cli.py repair-covers "/path/to/music/Artist" --dry-run
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Allow running as a script (python utilities/repair_covers.py ...).
if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mutagen import File as MutagenFile

from utilities.core.audio_file import is_audio_file, iter_audio_files
from utilities.core.cover_art import (
    InvalidCoverArt,
    download_cover,
    embed_in_album,
    extract_cover_from_file,
    validate_image,
)
from utilities.core.ffprobe import attached_pic_dims, ffprobe_available

# Directory (created inside each album) that holds pre-modification backups.
BACKUP_DIRNAME = "backups"

# Per-file diagnosis results.
STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_CORRUPT = "corrupt"


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def diagnose_file(filepath) -> str:
    """Classify a single track's embedded cover art.

    Returns one of :data:`STATUS_OK`, :data:`STATUS_MISSING`,
    :data:`STATUS_CORRUPT`. The ffprobe check is authoritative for the
    ``width=0`` corruption that Jellyfin reports; the byte decode catches
    payloads that are present but undecodable.
    """
    dims = attached_pic_dims(filepath) if ffprobe_available() else None

    # ffprobe found a cover stream but it has no real dimensions: this is the
    # exact corruption the repair tool exists to fix.
    if dims is not None and (dims[0] <= 0 or dims[1] <= 0):
        return STATUS_CORRUPT

    data = extract_cover_from_file(filepath)
    if not data:  # None or empty bytes
        return STATUS_MISSING

    try:
        validate_image(data)
    except InvalidCoverArt:
        return STATUS_CORRUPT

    return STATUS_OK


def diagnose_album(album_dir) -> Dict[str, object]:
    """Diagnose every track in an album folder.

    Returns ``{total, ok, missing, corrupt, needs_repair, bad_files}`` where
    ``bad_files`` lists ``(name, status)`` for the flagged tracks.
    """
    result: Dict[str, object] = {
        "total": 0,
        "ok": 0,
        "missing": 0,
        "corrupt": 0,
        "needs_repair": False,
        "bad_files": [],
    }
    for audio_file in iter_audio_files(album_dir):
        result["total"] = int(result["total"]) + 1
        status = diagnose_file(audio_file)
        result[status] = int(result[status]) + 1
        if status != STATUS_OK:
            result["bad_files"].append((audio_file.name, status))  # type: ignore[attr-defined]

    result["needs_repair"] = (int(result["missing"]) + int(result["corrupt"])) > 0
    return result


def find_album_folders(root) -> List[Path]:
    """Return every folder under ``root`` that directly contains audio files.

    ``root`` itself is included when it holds audio files. The ``backups/``
    folders this tool creates are skipped so re-runs do not treat them as
    albums.
    """
    root_path = Path(root)
    folders: List[Path] = []
    if not root_path.exists():
        return folders

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune backup folders from the walk so we never descend into them.
        dirnames[:] = [d for d in dirnames if d != BACKUP_DIRNAME]
        if Path(dirpath).name == BACKUP_DIRNAME:
            continue
        if any(is_audio_file(name) for name in filenames):
            folders.append(Path(dirpath))

    return sorted(folders)


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #
def read_album_artist(album_dir) -> Tuple[str, str]:
    """Best-effort ``(album, artist)`` for an album folder.

    Reads tags from the first readable track (album, then albumartist/artist),
    falling back to the folder name and ``Various Artists``.
    """
    for audio_file in iter_audio_files(album_dir):
        try:
            audio = MutagenFile(str(audio_file), easy=True)
        except Exception:
            audio = None
        if not audio:
            continue
        album = _first_tag(audio, "album")
        artist = _first_tag(audio, "albumartist") or _first_tag(audio, "artist")
        if album:
            return album, artist or "Various Artists"

    return Path(album_dir).name, "Various Artists"


def _first_tag(audio, key: str) -> Optional[str]:
    value = audio.get(key)
    if value:
        text = str(value[0]).strip()
        return text or None
    return None


# --------------------------------------------------------------------------- #
# Cover lookup (iTunes -> MusicBrainz CAA -> Discogs)
# --------------------------------------------------------------------------- #
def build_sources() -> List[object]:
    """Build the ordered source list, skipping any that fail to construct."""
    sources: List[object] = []
    # Imported lazily so a missing optional dependency in one adapter does not
    # break the whole tool.
    try:
        from sources.itunes import iTunesSource

        sources.append(iTunesSource())
    except Exception as exc:
        print(f"  [sources] iTunes unavailable: {exc}")
    try:
        from sources.musicbrainz import MusicBrainzSource

        sources.append(MusicBrainzSource())
    except Exception as exc:
        print(f"  [sources] MusicBrainz unavailable: {exc}")
    try:
        from sources.discogs import DiscogsSource

        sources.append(DiscogsSource())
    except Exception as exc:
        print(f"  [sources] Discogs unavailable: {exc}")
    return sources


def fetch_validated_cover(
    album: str,
    artist: str,
    sources: List[object],
    *,
    max_candidates: int = 3,
) -> Optional[bytes]:
    """Search ``sources`` in order and return the first validated cover bytes.

    All network/parse failures are caught and logged; a source that yields no
    usable cover is skipped. Returns ``None`` when nothing valid is found.
    """
    for source in sources:
        name = getattr(source, "name", source.__class__.__name__)
        try:
            matches = source.search_album(album, artist or "Various Artists")
        except Exception as exc:  # rate limit, network, parse, etc.
            print(f"  [{name}] search failed: {exc}")
            continue

        for match in matches[:max_candidates]:
            url = getattr(match, "cover_url", None)
            if not url:
                try:
                    url = source.get_cover_url(match.source_id)
                except Exception as exc:
                    print(f"  [{name}] cover lookup failed: {exc}")
                    url = None
            if not url:
                continue
            try:
                data = download_cover(url)  # validated; raises on bad image
            except InvalidCoverArt as exc:
                print(f"  [{name}] candidate rejected: {exc}")
                continue
            except Exception as exc:
                print(f"  [{name}] download error: {exc}")
                continue
            print(f"  [{name}] accepted cover ({len(data)} bytes)")
            return data

    return None


# --------------------------------------------------------------------------- #
# Backup
# --------------------------------------------------------------------------- #
def backup_album(album_dir) -> Optional[Path]:
    """Copy every audio file in ``album_dir`` to a sibling ``backups/`` folder.

    Existing backups are never overwritten (the first backup is the pristine
    one). Returns the backup folder, or ``None`` if there is nothing to back up.
    """
    files = list(iter_audio_files(album_dir))
    if not files:
        return None

    backup_dir = Path(album_dir) / BACKUP_DIRNAME
    backup_dir.mkdir(exist_ok=True)
    for audio_file in files:
        dest = backup_dir / audio_file.name
        if not dest.exists():
            shutil.copy2(audio_file, dest)
    return backup_dir


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def repair_library(
    path,
    *,
    scan_only: bool = False,
    dry_run: bool = False,
    cover_override: Optional[bytes] = None,
) -> Dict[str, object]:
    """Scan ``path`` for corrupted album art and repair what needs repairing.

    Args:
        path: Library / artist / album folder to scan.
        scan_only: Report only; never fetch or modify anything.
        dry_run: Detect and report the repair plan but make no changes.
        cover_override: Validated image bytes to embed instead of fetching from
            the network. Used for offline testing of the re-embed path; still
            validated by the core pipeline before any write.

    Returns a summary dict:
        ``{albums, needs_repair, repaired, failed, skipped, files_fixed, details}``
    """
    summary: Dict[str, object] = {
        "albums": 0,
        "needs_repair": 0,
        "repaired": 0,
        "failed": 0,
        "skipped": 0,
        "files_fixed": 0,
        "details": [],
    }

    if not ffprobe_available():
        print("[repair-covers] WARNING: ffprobe unavailable - falling back to "
              "Pillow byte-decode detection (cannot see ffprobe width=0 streams).")

    album_folders = find_album_folders(path)
    summary["albums"] = len(album_folders)
    if not album_folders:
        print(f"[repair-covers] No album folders with audio found under: {path}")
        return summary

    sources: List[object] = []  # built lazily on the first album that needs it

    for album_dir in album_folders:
        diag = diagnose_album(album_dir)
        rel = _display_name(path, album_dir)

        if not diag["needs_repair"]:
            continue

        summary["needs_repair"] = int(summary["needs_repair"]) + 1
        bad = diag["bad_files"]  # type: ignore[assignment]
        print(f"\n[FLAG] {rel}")
        print(f"  tracks={diag['total']} ok={diag['ok']} "
              f"missing={diag['missing']} corrupt={diag['corrupt']}")
        for fname, status in bad:  # type: ignore[union-attr]
            print(f"    - {fname}: {status}")

        detail: Dict[str, object] = {
            "album": rel,
            "total": diag["total"],
            "missing": diag["missing"],
            "corrupt": diag["corrupt"],
            "action": "flagged",
        }

        if scan_only:
            detail["action"] = "scan-only"
            summary["details"].append(detail)  # type: ignore[attr-defined]
            continue

        album_name, artist = read_album_artist(album_dir)
        print(f"  metadata: album='{album_name}' artist='{artist}'")

        if dry_run:
            detail["action"] = "dry-run (would re-fetch and re-embed)"
            summary["details"].append(detail)  # type: ignore[attr-defined]
            continue

        # Obtain a validated cover.
        if cover_override is not None:
            try:
                validate_image(cover_override)
                cover_data: Optional[bytes] = cover_override
            except InvalidCoverArt as exc:
                print(f"  cover_override invalid: {exc}")
                cover_data = None
        else:
            if not sources:
                sources = build_sources()
            cover_data = fetch_validated_cover(album_name, artist, sources)

        if cover_data is None:
            print("  no valid cover found - leaving album untouched")
            detail["action"] = "skipped (no cover found)"
            summary["skipped"] = int(summary["skipped"]) + 1
            summary["details"].append(detail)  # type: ignore[attr-defined]
            continue

        # MANDATORY backup before any write.
        backup_dir = backup_album(album_dir)
        if backup_dir is not None:
            print(f"  backed up tracks to: {backup_dir}")

        try:
            embed_result = embed_in_album(album_dir, cover_data)
        except InvalidCoverArt as exc:
            print(f"  embed aborted (invalid source): {exc}")
            detail["action"] = f"failed ({exc})"
            summary["failed"] = int(summary["failed"]) + 1
            summary["details"].append(detail)  # type: ignore[attr-defined]
            continue

        print(f"  re-embedded: embedded={embed_result['embedded']} "
              f"failed={embed_result['failed']} total={embed_result['total']}")
        for err in embed_result["errors"]:  # type: ignore[union-attr]
            print(f"    ! {err}")

        if int(embed_result["embedded"]) > 0:
            summary["repaired"] = int(summary["repaired"]) + 1
            summary["files_fixed"] = int(summary["files_fixed"]) + int(embed_result["embedded"])
            detail["action"] = (
                f"repaired ({embed_result['embedded']}/{embed_result['total']} tracks)"
            )
        else:
            summary["failed"] = int(summary["failed"]) + 1
            detail["action"] = "failed (no tracks embedded)"

        detail["embed"] = embed_result
        summary["details"].append(detail)  # type: ignore[attr-defined]

    return summary


def _display_name(root, album_dir) -> str:
    """Path of ``album_dir`` relative to ``root`` (or its name) for logging."""
    try:
        return str(Path(album_dir).relative_to(Path(root)))
    except ValueError:
        return Path(album_dir).name


# --------------------------------------------------------------------------- #
# Standalone entry point
# --------------------------------------------------------------------------- #
def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="repair_covers",
        description="Detect and repair corrupted embedded album art.",
    )
    parser.add_argument("path", help="Library / artist / album folder to scan")
    parser.add_argument("--scan-only", action="store_true",
                        help="Report corrupted albums without making changes")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show the repair plan without fetching or writing")
    args = parser.parse_args(argv)

    summary = repair_library(
        args.path, scan_only=args.scan_only, dry_run=args.dry_run
    )

    print("\n=== Repair Covers Summary ===")
    print(f"Album folders scanned: {summary['albums']}")
    print(f"Albums needing repair: {summary['needs_repair']}")
    if not args.scan_only and not args.dry_run:
        print(f"Albums repaired:       {summary['repaired']}")
        print(f"Tracks re-embedded:    {summary['files_fixed']}")
        print(f"Albums skipped:        {summary['skipped']}")
        print(f"Albums failed:         {summary['failed']}")
    if args.scan_only:
        print("(Scan only - no changes made)")
    if args.dry_run:
        print("(Dry run - no changes made)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
