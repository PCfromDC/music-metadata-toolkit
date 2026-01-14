import os
import sys
import hashlib
import json
from datetime import datetime
import requests
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC
from mutagen.id3 import ID3, APIC


def get_knowledge_base_path():
    """Get path to .claude/knowledge folder."""
    base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, '.claude', 'knowledge')


def log_cover_correction(album_path, image_url, old_hash=None, old_size_kb=None):
    """Log a cover art correction to the knowledge base for future learning.

    Args:
        album_path: Full path to the album folder
        image_url: URL of the correct cover art
        old_hash: Hash of the old (wrong) cover art
        old_size_kb: Size of the old cover art in KB
    """
    kb_path = get_knowledge_base_path()
    if not os.path.exists(kb_path):
        print(f"  Knowledge base not found at {kb_path}, skipping learning")
        return

    # Extract artist/album from path (expects .../Artist/Album format)
    parts = album_path.rstrip('/\\').replace('\\', '/').split('/')
    if len(parts) >= 2:
        album_name = parts[-1]
        artist_name = parts[-2]
        album_key = f"{artist_name}/{album_name}"
    else:
        album_key = parts[-1] if parts else "Unknown"
        artist_name = "Unknown"
        album_name = album_key

    today = datetime.now().strftime('%Y-%m-%d')

    # Update corrections.json
    corrections_file = os.path.join(kb_path, 'corrections.json')
    try:
        if os.path.exists(corrections_file):
            with open(corrections_file, 'r', encoding='utf-8') as f:
                corrections = json.load(f)
        else:
            corrections = {"_description": "Log of corrections applied during music library cleanup sessions", "corrections": []}

        # Add new correction
        correction_entry = {
            "album_path": album_path.replace('\\', '/'),
            "correction_type": "cover_art",
            "before": {
                "hash": old_hash or "unknown",
                "size_kb": old_size_kb or 0,
                "description": "Replaced via embed_cover.py --force"
            },
            "after": {
                "url": image_url,
                "source": "itunes" if "mzstatic.com" in image_url else "manual"
            },
            "date": today
        }
        corrections["corrections"].append(correction_entry)

        with open(corrections_file, 'w', encoding='utf-8') as f:
            json.dump(corrections, f, indent=2)
        print(f"  Logged correction to: corrections.json")
    except Exception as e:
        print(f"  Warning: Failed to log correction: {e}")

    # Update cover_art_mapping.json
    mapping_file = os.path.join(kb_path, 'cover_art_mapping.json')
    try:
        if os.path.exists(mapping_file):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
        else:
            mapping = {"_description": "Known correct cover art URLs for albums", "albums": {}}

        # Add/update album mapping
        mapping["albums"][album_key] = {
            "correct_url": image_url,
            "verified_date": today,
            "source": "itunes" if "mzstatic.com" in image_url else "manual",
            "notes": "Added automatically via embed_cover.py --force"
        }

        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2)
        print(f"  Added to cover_art_mapping.json: {album_key}")
    except Exception as e:
        print(f"  Warning: Failed to update cover mapping: {e}")

def download_image(url, output_path=None):
    """Download image from URL. Returns bytes if output_path is None."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
        return response.content
    return None if output_path is None else False


def extract_cover_from_file(filepath):
    """Extract embedded cover art from an audio file. Returns bytes or None."""
    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext == '.mp3':
            audio = MP3(filepath, ID3=ID3)
            for key in audio.tags:
                if key.startswith('APIC'):
                    return audio.tags[key].data
        elif ext in ['.m4a', '.mp4']:
            audio = MP4(filepath)
            if 'covr' in audio and audio['covr']:
                return bytes(audio['covr'][0])
        elif ext == '.flac':
            audio = FLAC(filepath)
            if audio.pictures:
                return audio.pictures[0].data
    except Exception:
        pass
    return None


def get_album_cover_hash(album_path):
    """Get MD5 hash of embedded cover art from first track with cover."""
    audio_extensions = {'.mp3', '.m4a', '.mp4', '.flac'}

    for filename in sorted(os.listdir(album_path)):
        ext = os.path.splitext(filename)[1].lower()
        if ext in audio_extensions:
            filepath = os.path.join(album_path, filename)
            cover_data = extract_cover_from_file(filepath)
            if cover_data:
                return hashlib.md5(cover_data).hexdigest(), cover_data
    return None, None

def embed_cover_mp3(filepath, image_path):
    """Embed cover art into MP3 file"""
    audio = MP3(filepath, ID3=ID3)

    # Read image data
    with open(image_path, 'rb') as f:
        image_data = f.read()

    # Determine mime type
    mime = 'image/jpeg' if image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg') else 'image/png'

    # Remove existing cover art
    audio.tags.delall('APIC')

    # Add new cover art
    audio.tags.add(
        APIC(
            encoding=3,  # UTF-8
            mime=mime,
            type=3,  # Front cover
            desc='Cover',
            data=image_data
        )
    )
    audio.save()

def embed_cover_m4a(filepath, image_path):
    """Embed cover art into M4A file"""
    audio = MP4(filepath)

    # Read image data
    with open(image_path, 'rb') as f:
        image_data = f.read()

    # Determine format
    if image_path.lower().endswith('.png'):
        image_format = MP4Cover.FORMAT_PNG
    else:
        image_format = MP4Cover.FORMAT_JPEG

    audio['covr'] = [MP4Cover(image_data, imageformat=image_format)]
    audio.save()

def embed_cover_album(album_path, image_path, force=False):
    """Embed cover art into all audio files in album folder.

    Args:
        album_path: Path to album folder
        image_path: Path to cover art image file
        force: If False, compare with existing art and skip if identical

    Returns:
        Count of files embedded
    """
    audio_extensions = {'.mp3', '.m4a', '.mp4', '.flac'}
    count = 0

    # Read new image data and compute hash
    with open(image_path, 'rb') as f:
        new_image_data = f.read()
    new_hash = hashlib.md5(new_image_data).hexdigest()

    # Check existing cover art if not forcing
    if not force:
        existing_hash, existing_data = get_album_cover_hash(album_path)
        if existing_hash and existing_hash == new_hash:
            print("  Cover art already matches - skipping (use --force to override)")
            return 0

    for filename in os.listdir(album_path):
        ext = os.path.splitext(filename)[1].lower()
        if ext in audio_extensions:
            filepath = os.path.join(album_path, filename)
            try:
                if ext == '.mp3':
                    embed_cover_mp3(filepath, image_path)
                elif ext in ['.m4a', '.mp4']:
                    embed_cover_m4a(filepath, image_path)
                elif ext == '.flac':
                    embed_cover_flac(filepath, image_path)
                count += 1
                print(f"  Embedded: {filename}")
            except Exception as e:
                print(f"  ERROR on {filename}: {e}")

    return count


def embed_cover_flac(filepath, image_path):
    """Embed cover art into FLAC file"""
    from mutagen.flac import Picture

    audio = FLAC(filepath)

    # Read image data
    with open(image_path, 'rb') as f:
        image_data = f.read()

    # Determine mime type
    if image_path.lower().endswith('.png'):
        mime = 'image/png'
    else:
        mime = 'image/jpeg'

    # Remove existing pictures
    audio.clear_pictures()

    # Add new cover art
    pic = Picture()
    pic.type = 3  # Front cover
    pic.mime = mime
    pic.desc = 'Cover'
    pic.data = image_data
    audio.add_picture(pic)
    audio.save()


def sync_folder_jpg(album_path, image_path=None):
    """Sync folder.jpg with embedded cover art or provided image."""
    folder_jpg = os.path.join(album_path, 'folder.jpg')

    if image_path:
        # Use provided image
        with open(image_path, 'rb') as f:
            image_data = f.read()
    else:
        # Extract from tracks
        _, image_data = get_album_cover_hash(album_path)
        if not image_data:
            print("  No embedded cover art found to sync")
            return False

    # Compare with existing folder.jpg
    if os.path.exists(folder_jpg):
        with open(folder_jpg, 'rb') as f:
            existing_data = f.read()
        if hashlib.md5(existing_data).hexdigest() == hashlib.md5(image_data).hexdigest():
            print("  folder.jpg already in sync")
            return True

    # Write folder.jpg
    with open(folder_jpg, 'wb') as f:
        f.write(image_data)
    print(f"  Updated folder.jpg ({len(image_data) // 1024}KB)")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python embed_cover.py <album_path> <image_url_or_path> [--force] [--verify]")
        print("       python embed_cover.py <album_path> --sync-folder")
        print("       python embed_cover.py <album_path> --show-current")
        print("")
        print("Options:")
        print("  --force        Embed even if cover art matches existing")
        print("  --verify       Save preview and prompt before embedding")
        print("  --sync-folder  Sync folder.jpg from embedded track art")
        print("  --show-current Extract and save current embedded art for review")
        sys.exit(1)

    album_path = sys.argv[1]
    force = '--force' in sys.argv
    verify = '--verify' in sys.argv

    # Handle --sync-folder mode
    if '--sync-folder' in sys.argv:
        print(f"Syncing folder.jpg from embedded art: {album_path}")
        sync_folder_jpg(album_path)
        sys.exit(0)

    # Handle --show-current mode (extract embedded art for review)
    if '--show-current' in sys.argv:
        print(f"Extracting current embedded cover art: {album_path}")
        existing_hash, existing_data = get_album_cover_hash(album_path)
        if existing_data:
            # Save to outputs folder for Claude to view
            preview_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs')
            os.makedirs(preview_dir, exist_ok=True)
            album_name = os.path.basename(album_path.rstrip('/\\'))
            preview_path = os.path.join(preview_dir, f'{album_name}_current_cover.jpg')
            with open(preview_path, 'wb') as f:
                f.write(existing_data)
            print(f"  Saved current cover to: {preview_path}")
            print(f"  Size: {len(existing_data) // 1024}KB")
            print(f"  Hash: {existing_hash}")
            print(f"\n  Review this image to verify it matches the album.")
        else:
            print("  No embedded cover art found")
        sys.exit(0)

    if len(sys.argv) < 3 or sys.argv[2].startswith('--'):
        print("Error: image_url_or_path is required")
        sys.exit(1)

    image_source = sys.argv[2]

    # If URL, download first
    if image_source.startswith('http'):
        print(f"Downloading cover art...")
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        temp_image = os.path.join(temp_dir, 'temp_cover.jpg')
        if not download_image(image_source, temp_image):
            print("Failed to download image")
            sys.exit(1)
        image_path = temp_image
    else:
        image_path = image_source

    # Handle --verify mode: save preview and prompt
    if verify:
        preview_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs')
        os.makedirs(preview_dir, exist_ok=True)
        album_name = os.path.basename(album_path.rstrip('/\\'))
        preview_path = os.path.join(preview_dir, f'{album_name}_new_cover_preview.jpg')

        # Copy to preview location
        with open(image_path, 'rb') as f:
            preview_data = f.read()
        with open(preview_path, 'wb') as f:
            f.write(preview_data)

        print(f"\n=== VERIFICATION MODE ===")
        print(f"Album: {album_name}")
        print(f"Preview saved to: {preview_path}")
        print(f"Size: {len(preview_data) // 1024}KB")
        print(f"\nPlease review the image before embedding.")
        print(f"To proceed, run again without --verify flag.")
        print(f"To force embed: python embed_cover.py \"{album_path}\" \"{image_source}\" --force")
        sys.exit(0)

    # Capture old cover info before embedding (for learning)
    old_hash, old_data = None, None
    if force and image_source.startswith('http'):
        old_hash, old_data = get_album_cover_hash(album_path)
        old_size_kb = len(old_data) // 1024 if old_data else 0

    print(f"Embedding cover art into: {album_path}")
    count = embed_cover_album(album_path, image_path, force=force)

    if count > 0:
        print(f"\nDone! Embedded cover art into {count} files.")
        # Sync folder.jpg with newly embedded art
        sync_folder_jpg(album_path, image_path)

        # Log correction to knowledge base for learning (only for forced URL embeds)
        if force and image_source.startswith('http'):
            print("\n--- Learning from this correction ---")
            log_cover_correction(album_path, image_source, old_hash, old_size_kb if old_data else None)
    elif not force:
        print("\nNo files embedded (cover art already matches).")
