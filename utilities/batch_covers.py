#!/usr/bin/env python3
"""Unified batch cover-art tool.

Replaces six near-identical one-off scripts (batch_embed_missing_covers,
batch_remaining_covers, batch_putumayo_covers, retry_remaining_covers,
retry_failed_covers, restore_all_covers) with a single flag-driven utility.

EVERY image embed routes through utilities.core.cover_art, so art is validated
(Pillow pre-gate) and verified after write (ffprobe read-back, the engine
Jellyfin uses). Bad bytes are never embedded.

Modes (pick one):
  --missing   Embed art into albums whose tracks have no valid embedded cover
              (ffprobe reports no attached_pic, or dimensions of 0).
  --retry     Same selection as --missing, but online downloads are retried with
              backoff. Use after a --missing pass left network failures behind.
  --restore   Re-embed each album's existing folder.jpg into its tracks (recover
              from a folder.jpg backup when embedded art was lost).

Cover source:
  --image PATH   Use one local image for every album (offline / testing). When
                 omitted, --missing/--retry look the cover up online via
                 MusicBrainz -> Cover Art Archive using the album folder name.
                 --restore always reads each album's folder.jpg.

Examples:
  python utilities/batch_covers.py "/music/Various Artists" --missing
  python utilities/batch_covers.py "/music/Various Artists" --retry
  python utilities/batch_covers.py "/music/Various Artists" --restore
  python utilities/batch_covers.py "/music/Various Artists" --missing --image cover.jpg
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Iterator, List, Optional

import requests

# Allow `python utilities/batch_covers.py` to import the utilities.core package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utilities.core.audio_file import iter_audio_files  # noqa: E402
from utilities.core.cover_art import (  # noqa: E402
    DEFAULT_HEADERS,
    InvalidCoverArt,
    download_cover,
    embed_in_album,
    extract_cover_from_file,
    validate_image,
)
from utilities.core.ffprobe import attached_pic_dims, ffprobe_available  # noqa: E402

MUSICBRAINZ_SEARCH = "https://musicbrainz.org/ws/2/release/?query={query}&fmt=json&limit=1"
COVER_ART_ARCHIVE = "https://coverartarchive.org/release/{release_id}/front-1200"


# --------------------------------------------------------------------------- #
# Album discovery and art detection
# --------------------------------------------------------------------------- #
def iter_albums(library_path) -> Iterator[Path]:
    """Yield album folders under ``library_path``.

    An album is any directory that directly contains audio files. The library
    path itself is yielded when it holds audio directly (single-album input);
    otherwise its immediate subdirectories are scanned.
    """
    base = Path(library_path)
    if not base.is_dir():
        return
    if any(iter_audio_files(base)):
        yield base
        return
    for child in sorted(base.iterdir()):
        if child.is_dir() and any(iter_audio_files(child)):
            yield child


def album_has_valid_art(album_path) -> bool:
    """True if the album's first track already carries valid embedded art.

    Uses ffprobe (Jellyfin's engine) as ground truth; falls back to a Pillow
    decode of the extracted bytes when ffprobe is unavailable. Albums with no
    audio files are treated as having art (nothing to do).
    """
    files = list(iter_audio_files(album_path))
    if not files:
        return True
    probe = files[0]
    if ffprobe_available():
        dims = attached_pic_dims(probe)
        return bool(dims and dims[0] > 0 and dims[1] > 0)
    data = extract_cover_from_file(probe)
    if not data:
        return False
    try:
        validate_image(data)
        return True
    except InvalidCoverArt:
        return False


# --------------------------------------------------------------------------- #
# Cover-art sources
# --------------------------------------------------------------------------- #
def lookup_cover_url(album_name: str, *, timeout: int = 15) -> Optional[str]:
    """Resolve a Cover Art Archive front-cover URL for ``album_name``.

    Searches MusicBrainz for the first matching release, then builds the Cover
    Art Archive URL. Returns ``None`` when no release is found or the lookup
    fails. Sleeps 1s first to respect MusicBrainz rate limits.
    """
    time.sleep(1)
    url = MUSICBRAINZ_SEARCH.format(query=urllib.parse.quote(album_name))
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        releases = response.json().get("releases") or []
    except (requests.RequestException, ValueError) as exc:
        print(f"    [warn] MusicBrainz lookup failed: {exc}")
        return None
    if not releases:
        return None
    return COVER_ART_ARCHIVE.format(release_id=releases[0]["id"])


def download_with_retries(url: str, *, retries: int, backoff: int) -> bytes:
    """Download validated cover bytes, retrying transient failures with backoff."""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            return download_cover(url)
        except InvalidCoverArt as exc:
            last_error = exc
            if attempt < retries:
                print(f"    [warn] download attempt {attempt} failed, retrying...")
                time.sleep(backoff)
    raise InvalidCoverArt(str(last_error) if last_error else "download failed")


def folder_jpg_bytes(album_path) -> Optional[bytes]:
    """Return the album's folder.jpg bytes, or ``None`` if absent/unreadable."""
    candidate = Path(album_path) / "folder.jpg"
    if not candidate.is_file():
        return None
    try:
        return candidate.read_bytes()
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# Per-album processing
# --------------------------------------------------------------------------- #
def resolve_source(
    album_path: Path,
    mode: str,
    image_bytes: Optional[bytes],
    *,
    retries: int,
    backoff: int,
) -> Optional[bytes]:
    """Return validated cover bytes for one album, or ``None`` if unavailable."""
    if mode == "restore":
        return folder_jpg_bytes(album_path)
    if image_bytes is not None:
        return image_bytes
    cover_url = lookup_cover_url(album_path.name)
    if not cover_url:
        return None
    try:
        return download_with_retries(cover_url, retries=retries, backoff=backoff)
    except InvalidCoverArt as exc:
        print(f"    [warn] {exc}")
        return None


def run(
    library_path: str,
    mode: str,
    *,
    image_path: Optional[str] = None,
    dry_run: bool = False,
    retries: int = 1,
    backoff: int = 3,
) -> dict:
    """Process all albums under ``library_path`` for the chosen ``mode``.

    Returns a summary dict with album- and file-level counts.
    """
    image_bytes: Optional[bytes] = None
    if image_path:
        image_bytes = Path(image_path).read_bytes()
        validate_image(image_bytes)  # fail fast on a bad local image

    albums = list(iter_albums(library_path))
    summary = {
        "albums": len(albums),
        "embedded": 0,
        "skipped": 0,
        "no_source": 0,
        "failed": 0,
        "files_embedded": 0,
        "files_failed": 0,
    }

    print(f"=== batch_covers ({mode}) ===")
    print(f"Library: {library_path}")
    print(f"Albums found: {len(albums)}\n")

    for index, album in enumerate(albums, 1):
        print(f"[{index}/{len(albums)}] {album.name}")

        # --restore re-embeds existing art; only touch albums missing valid art.
        if album_has_valid_art(album):
            print("  [skip] already has valid embedded art")
            summary["skipped"] += 1
            continue

        if dry_run:
            print("  [dry-run] would embed cover art")
            summary["embedded"] += 1
            continue

        data = resolve_source(album, mode, image_bytes, retries=retries, backoff=backoff)
        if data is None:
            reason = "no folder.jpg" if mode == "restore" else "no cover source found"
            print(f"  [skip] {reason}")
            summary["no_source"] += 1
            continue

        try:
            # In restore mode folder.jpg IS the source, so don't rewrite it.
            result = embed_in_album(album, data, write_folder_jpg=(mode != "restore"))
        except InvalidCoverArt as exc:
            print(f"  [error] {exc}")
            summary["failed"] += 1
            continue

        summary["files_embedded"] += int(result["embedded"])
        summary["files_failed"] += int(result["failed"])
        if int(result["embedded"]) > 0:
            print(f"  [ok] embedded into {result['embedded']}/{result['total']} files")
            summary["embedded"] += 1
        else:
            print("  [error] no files embedded")
            summary["failed"] += 1
        for error in result["errors"]:
            print(f"    - {error}")

    _print_summary(summary)
    return summary


def _print_summary(summary: dict) -> None:
    print("\n=== Summary ===")
    print(f"Albums:          {summary['albums']}")
    print(f"Embedded:        {summary['embedded']}")
    print(f"Already had art: {summary['skipped']}")
    print(f"No source:       {summary['no_source']}")
    print(f"Failed:          {summary['failed']}")
    print(f"Files embedded:  {summary['files_embedded']}")
    print(f"Files failed:    {summary['files_failed']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified batch cover-art embedding (validated via utilities.core).",
    )
    parser.add_argument("library", help="Path to an artist/library folder or a single album")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--missing",
        action="store_const",
        dest="mode",
        const="missing",
        help="Embed art into albums lacking valid embedded cover art (default)",
    )
    group.add_argument(
        "--retry",
        action="store_const",
        dest="mode",
        const="retry",
        help="Like --missing, but retry online downloads with backoff",
    )
    group.add_argument(
        "--restore",
        action="store_const",
        dest="mode",
        const="restore",
        help="Re-embed each album's existing folder.jpg into its tracks",
    )
    parser.add_argument(
        "--image",
        help="Local image file to use as the cover for every album (offline/testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=None,
        help="Online download attempts per album (default 3 for --retry, else 1)",
    )
    parser.add_argument(
        "--backoff",
        type=int,
        default=3,
        help="Seconds to wait between download retries (default 3)",
    )
    parser.set_defaults(mode="missing")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    retries = args.retries if args.retries is not None else (3 if args.mode == "retry" else 1)
    try:
        run(
            args.library,
            args.mode,
            image_path=args.image,
            dry_run=args.dry_run,
            retries=retries,
            backoff=args.backoff,
        )
    except (InvalidCoverArt, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
