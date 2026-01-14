"""Embed cover art into 70's Disco Ball Party Pack album"""
import os
import shutil
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC

album_path = Path(r"\\openmediavault\music\Various Artists\70's Disco Ball Party Pack")
cover_path = Path(r"D:\music cleanup\temp_disco_cover.jpg")

# Read cover art
with open(cover_path, 'rb') as f:
    cover_data = f.read()

print(f"Cover art size: {len(cover_data):,} bytes")
print(f"Album path: {album_path}")
print()

# Get all MP3 files
mp3_files = list(album_path.glob("*.mp3"))
print(f"Found {len(mp3_files)} MP3 files")
print()

success = 0
failed = 0

for mp3_file in sorted(mp3_files):
    try:
        audio = MP3(str(mp3_file))

        # Ensure ID3 tags exist
        if audio.tags is None:
            audio.add_tags()

        # Remove existing APIC frames
        audio.tags.delall('APIC')

        # Add new cover art
        audio.tags.add(
            APIC(
                encoding=3,  # UTF-8
                mime='image/jpeg',
                type=3,  # Front cover
                desc='Cover',
                data=cover_data
            )
        )

        audio.save()
        print(f"OK: {mp3_file.name}")
        success += 1

    except Exception as e:
        print(f"FAILED: {mp3_file.name} - {e}")
        failed += 1

print()
print(f"Embedded cover art: {success} successful, {failed} failed")

# Update folder.jpg
folder_jpg = album_path / "folder.jpg"
shutil.copy(cover_path, folder_jpg)
print(f"Updated folder.jpg ({len(cover_data):,} bytes)")
