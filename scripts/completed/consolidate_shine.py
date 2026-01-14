"""Consolidate Shine - The Complete Classics multi-disc album"""
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
import shutil
import sys
sys.stdout.reconfigure(encoding='utf-8')

va_path = Path(r"/path/to/music/Various Artists")
disc1_folder = va_path / "Shine_ The Complete Classics"
disc2_folder = va_path / "Shine - The Complete Classics"

print("=== Step 1: Add disc prefix to Disc 1 tracks ===")
if disc1_folder.exists():
    for mp3 in sorted(disc1_folder.glob("*.mp3")):
        name = mp3.name
        if not name.startswith("1-"):
            new_name = f"1-{name}"
            new_path = mp3.parent / new_name
            mp3.rename(new_path)
            print(f"  {name} -> {new_name}")
        else:
            print(f"  Already prefixed: {name}")

print()
print("=== Step 2: Add disc prefix to Disc 2 tracks ===")
if disc2_folder.exists():
    for mp3 in sorted(disc2_folder.glob("*.mp3")):
        name = mp3.name
        if not name.startswith("2-"):
            new_name = f"2-{name}"
            new_path = mp3.parent / new_name
            mp3.rename(new_path)
            print(f"  {name} -> {new_name}")
        else:
            print(f"  Already prefixed: {name}")

print()
print("=== Step 3: Move Disc 1 tracks to consolidated folder ===")
if disc1_folder.exists():
    for mp3 in sorted(disc1_folder.glob("*.mp3")):
        dest = disc2_folder / mp3.name
        shutil.move(str(mp3), str(dest))
        print(f"  Moved: {mp3.name}")

print()
print("=== Step 4: Update metadata for all tracks ===")
if disc2_folder.exists():
    for mp3 in sorted(disc2_folder.glob("*.mp3")):
        audio = MP3(str(mp3), ID3=EasyID3)
        audio['album'] = "Shine - The Complete Classics"
        # Set disc number based on filename prefix
        if mp3.name.startswith("1-"):
            audio['discnumber'] = "1/2"
        elif mp3.name.startswith("2-"):
            audio['discnumber'] = "2/2"
        audio.save()
        print(f"  Updated: {mp3.name}")

print()
print("=== Step 5: Remove empty folder ===")
if disc1_folder.exists():
    # Check if folder is empty (no mp3s left)
    remaining = list(disc1_folder.glob("*.mp3"))
    if not remaining:
        # Also move folder.jpg if exists
        folder_jpg = disc1_folder / "folder.jpg"
        if folder_jpg.exists():
            print(f"  Note: folder.jpg exists in disc1, keeping in disc2")
        disc1_folder.rmdir()
        print(f"  Deleted empty folder: {disc1_folder.name}")
    else:
        print(f"  Folder not empty, {len(remaining)} files remain")

print()
print("=== Verification ===")
if disc2_folder.exists():
    tracks = sorted(disc2_folder.glob("*.mp3"))
    print(f"Total tracks: {len(tracks)}")
    disc1_count = len([t for t in tracks if t.name.startswith("1-")])
    disc2_count = len([t for t in tracks if t.name.startswith("2-")])
    print(f"Disc 1 tracks: {disc1_count}")
    print(f"Disc 2 tracks: {disc2_count}")

print()
print("=== Complete ===")
