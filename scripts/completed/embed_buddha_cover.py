"""Embed cover art into Buddha-Bar, Vol. 7 album"""
import shutil
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.id3 import APIC

album_path = Path(r"\\openmediavault\music\Various Artists\Buddha-Bar, Vol. 7")
cover_path = Path(r"D:\music cleanup\temp_buddha_cover.jpg")

# Read cover art
with open(cover_path, 'rb') as f:
    cover_data = f.read()

print(f"Cover art size: {len(cover_data):,} bytes")

# Get all MP3 files
mp3_files = list(album_path.glob("*.mp3"))
print(f"Found {len(mp3_files)} MP3 files")
print()

success = 0
for mp3_file in sorted(mp3_files):
    try:
        audio = MP3(str(mp3_file))
        if audio.tags is None:
            audio.add_tags()
        audio.tags.delall('APIC')
        audio.tags.add(
            APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=cover_data
            )
        )
        audio.save()
        print(f"OK: {mp3_file.name}")
        success += 1
    except Exception as e:
        print(f"FAILED: {mp3_file.name} - {e}")

print()
print(f"Embedded: {success}/{len(mp3_files)} tracks")

# Update folder.jpg
folder_jpg = album_path / "folder.jpg"
shutil.copy(cover_path, folder_jpg)
print(f"Updated folder.jpg ({len(cover_data):,} bytes)")
