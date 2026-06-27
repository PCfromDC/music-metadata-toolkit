"""Embed album cover art into audio files.

Thin CLI wrapper over :mod:`utilities.core.cover_art`, which is the single
validated pipeline for all cover-art download/embed logic. This module keeps its
historical public function names (used by cli.py and older scripts) but every
embed now goes through the validated core - so empty/corrupt images can no
longer be written (the cause of the width=0/height=0 bug Jellyfin reported).
"""

import hashlib
import json
import os
import sys
from datetime import datetime

# Ensure the project root is importable whether run as a script or imported.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.core import cover_art
from utilities.core.cover_art import InvalidCoverArt


def get_knowledge_base_path():
    """Get path to .claude/knowledge folder."""
    base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, ".claude", "knowledge")


def log_cover_correction(album_path, image_url, old_hash=None, old_size_kb=None):
    """Log a cover art correction to the knowledge base for future learning."""
    kb_path = get_knowledge_base_path()
    if not os.path.exists(kb_path):
        print(f"  Knowledge base not found at {kb_path}, skipping learning")
        return

    parts = album_path.rstrip("/\\").replace("\\", "/").split("/")
    if len(parts) >= 2:
        album_name = parts[-1]
        artist_name = parts[-2]
        album_key = f"{artist_name}/{album_name}"
    else:
        album_key = parts[-1] if parts else "Unknown"
        artist_name = "Unknown"
        album_name = album_key

    today = datetime.now().strftime("%Y-%m-%d")

    corrections_file = os.path.join(kb_path, "corrections.json")
    try:
        if os.path.exists(corrections_file):
            with open(corrections_file, "r", encoding="utf-8") as f:
                corrections = json.load(f)
        else:
            corrections = {
                "_description": "Log of corrections applied during music library cleanup sessions",
                "corrections": [],
            }
        corrections["corrections"].append(
            {
                "album_path": album_path.replace("\\", "/"),
                "correction_type": "cover_art",
                "before": {
                    "hash": old_hash or "unknown",
                    "size_kb": old_size_kb or 0,
                    "description": "Replaced via embed_cover.py --force",
                },
                "after": {
                    "url": image_url,
                    "source": "itunes" if "mzstatic.com" in image_url else "manual",
                },
                "date": today,
            }
        )
        with open(corrections_file, "w", encoding="utf-8") as f:
            json.dump(corrections, f, indent=2)
        print("  Logged correction to: corrections.json")
    except Exception as e:
        print(f"  Warning: Failed to log correction: {e}")

    mapping_file = os.path.join(kb_path, "cover_art_mapping.json")
    try:
        if os.path.exists(mapping_file):
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        else:
            mapping = {"_description": "Known correct cover art URLs for albums", "albums": {}}
        mapping["albums"][album_key] = {
            "correct_url": image_url,
            "verified_date": today,
            "source": "itunes" if "mzstatic.com" in image_url else "manual",
            "notes": "Added automatically via embed_cover.py --force",
        }
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
        print(f"  Added to cover_art_mapping.json: {album_key}")
    except Exception as e:
        print(f"  Warning: Failed to update cover mapping: {e}")


def download_image(url, output_path=None):
    """Download a validated image from ``url``.

    Returns the bytes (when ``output_path`` is None) or True after writing the
    file. Returns None/False on failure (invalid or unreachable image).
    """
    try:
        data = cover_art.download_cover(url)
    except InvalidCoverArt as e:
        print(f"  Image download/validation failed: {e}")
        return None if output_path is None else False
    if output_path:
        with open(output_path, "wb") as f:
            f.write(data)
        return True
    return data


def extract_cover_from_file(filepath):
    """Extract embedded cover art bytes from an audio file. Returns bytes or None."""
    return cover_art.extract_cover_from_file(filepath)


def get_album_cover_hash(album_path):
    """Return (md5_hex, bytes) of the first track's embedded cover, or (None, None)."""
    from utilities.core.audio_file import AUDIO_EXTS

    for filename in sorted(os.listdir(album_path)):
        if os.path.splitext(filename)[1].lower() in AUDIO_EXTS:
            data = cover_art.extract_cover_from_file(os.path.join(album_path, filename))
            if data:
                return hashlib.md5(data).hexdigest(), data
    return None, None


def embed_cover_mp3(filepath, image_path):
    """Embed (validated) cover art into an MP3 file."""
    cover_art.embed_in_file(filepath, image_path)


def embed_cover_m4a(filepath, image_path):
    """Embed (validated) cover art into an M4A file."""
    cover_art.embed_in_file(filepath, image_path)


def embed_cover_flac(filepath, image_path):
    """Embed (validated) cover art into a FLAC file."""
    cover_art.embed_in_file(filepath, image_path)


def embed_cover_album(album_path, image_path, force=False):
    """Embed validated cover art into all audio files in an album folder.

    When ``force`` is False and the album already has identical embedded art,
    the operation is skipped. Returns the count of files embedded.
    """
    with open(image_path, "rb") as f:
        new_image_data = f.read()

    if not force:
        existing_hash, _ = get_album_cover_hash(album_path)
        if existing_hash and existing_hash == hashlib.md5(new_image_data).hexdigest():
            print("  Cover art already matches - skipping (use --force to override)")
            return 0

    result = cover_art.embed_in_album(album_path, new_image_data)
    for error in result["errors"]:
        print(f"  ERROR on {error}")
    print(f"  Embedded: {result['embedded']}/{result['total']} files")
    return int(result["embedded"])


def embed_cover_art(album_path, cover):
    """High-level entry point used by ``cli.py embed-cover``.

    ``cover`` may be an http(s) URL or a local image path. Downloads/validates,
    embeds into every track, and writes folder.jpg. Returns files embedded.
    """
    if isinstance(cover, str) and cover.startswith("http"):
        print("Downloading cover art...")
        data = cover_art.download_cover(cover)
    else:
        with open(cover, "rb") as f:
            data = f.read()

    print(f"Embedding cover art into: {album_path}")
    result = cover_art.embed_in_album(album_path, data)
    for error in result["errors"]:
        print(f"  ERROR on {error}")
    print(f"Done! Embedded cover art into {result['embedded']}/{result['total']} files.")
    return int(result["embedded"])


def sync_folder_jpg(album_path, image_path=None):
    """Sync folder.jpg with embedded cover art or a provided image."""
    folder_jpg = os.path.join(album_path, "folder.jpg")

    if image_path:
        with open(image_path, "rb") as f:
            image_data = f.read()
    else:
        _, image_data = get_album_cover_hash(album_path)
        if not image_data:
            print("  No embedded cover art found to sync")
            return False

    if os.path.exists(folder_jpg):
        with open(folder_jpg, "rb") as f:
            existing_data = f.read()
        if hashlib.md5(existing_data).hexdigest() == hashlib.md5(image_data).hexdigest():
            print("  folder.jpg already in sync")
            return True

    with open(folder_jpg, "wb") as f:
        f.write(image_data)
    print(f"  Updated folder.jpg ({len(image_data) // 1024}KB)")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python embed_cover.py <album_path> <image_url_or_path> [--force] [--verify]")
        print("       python embed_cover.py <album_path> --sync-folder")
        print("       python embed_cover.py <album_path> --show-current")
        sys.exit(1)

    album_path = sys.argv[1]
    force = "--force" in sys.argv
    verify = "--verify" in sys.argv

    if "--sync-folder" in sys.argv:
        print(f"Syncing folder.jpg from embedded art: {album_path}")
        sync_folder_jpg(album_path)
        sys.exit(0)

    if "--show-current" in sys.argv:
        print(f"Extracting current embedded cover art: {album_path}")
        existing_hash, existing_data = get_album_cover_hash(album_path)
        if existing_data:
            preview_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
            os.makedirs(preview_dir, exist_ok=True)
            album_name = os.path.basename(album_path.rstrip("/\\"))
            preview_path = os.path.join(preview_dir, f"{album_name}_current_cover.jpg")
            with open(preview_path, "wb") as f:
                f.write(existing_data)
            print(f"  Saved current cover to: {preview_path}")
            print(f"  Size: {len(existing_data) // 1024}KB")
            print(f"  Hash: {existing_hash}")
        else:
            print("  No embedded cover art found")
        sys.exit(0)

    if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
        print("Error: image_url_or_path is required")
        sys.exit(1)

    image_source = sys.argv[2]

    # Resolve the image to a local path (download URLs first, with validation).
    if image_source.startswith("http"):
        print("Downloading cover art...")
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        temp_image = os.path.join(temp_dir, "temp_cover.jpg")
        if not download_image(image_source, temp_image):
            print("Failed to download a valid image")
            sys.exit(1)
        image_path = temp_image
    else:
        image_path = image_source

    if verify:
        preview_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
        os.makedirs(preview_dir, exist_ok=True)
        album_name = os.path.basename(album_path.rstrip("/\\"))
        preview_path = os.path.join(preview_dir, f"{album_name}_new_cover_preview.jpg")
        with open(image_path, "rb") as f:
            preview_data = f.read()
        with open(preview_path, "wb") as f:
            f.write(preview_data)
        print("\n=== VERIFICATION MODE ===")
        print(f"Album: {album_name}")
        print(f"Preview saved to: {preview_path}")
        print(f"Size: {len(preview_data) // 1024}KB")
        print("To proceed, run again without --verify flag.")
        sys.exit(0)

    old_hash, old_data, old_size_kb = None, None, 0
    if force and image_source.startswith("http"):
        old_hash, old_data = get_album_cover_hash(album_path)
        old_size_kb = len(old_data) // 1024 if old_data else 0

    print(f"Embedding cover art into: {album_path}")
    count = embed_cover_album(album_path, image_path, force=force)

    if count > 0:
        print(f"\nDone! Embedded cover art into {count} files.")
        sync_folder_jpg(album_path, image_path)
        if force and image_source.startswith("http"):
            print("\n--- Learning from this correction ---")
            log_cover_correction(album_path, image_source, old_hash, old_size_kb if old_data else None)
    elif not force:
        print("\nNo files embedded (cover art already matches).")
