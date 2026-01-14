"""Fix World Cup Edition folder and track naming for consistency"""
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
import sys
sys.stdout.reconfigure(encoding='utf-8')

va_path = Path(r"/path/to/music/Various Artists")

# Step 1: Rename folder (remove [Disc 2])
print("=== Step 1: Rename folder ===")
old_folder = va_path / "Beginner's Guide to World Music - 2006 World Cup Edition [Disc 2]"
new_folder = va_path / "Beginner's Guide to World Music - 2006 World Cup Edition"

if old_folder.exists():
    old_folder.rename(new_folder)
    print(f"Renamed: {old_folder.name}")
    print(f"     To: {new_folder.name}")
else:
    print(f"Folder not found: {old_folder.name}")
    # Check if already renamed
    if new_folder.exists():
        print(f"Already renamed to: {new_folder.name}")

# Step 2: Rename tracks with disc prefix
print("\n=== Step 2: Rename tracks with disc prefix ===")
if new_folder.exists():
    for mp3 in sorted(new_folder.glob("*.mp3")):
        name = mp3.name
        # Check if already has disc prefix
        if name[0].isdigit() and name[1] == '-':
            print(f"  Already prefixed: {name}")
            continue

        # Add 2- prefix for disc 2
        new_name = f"2-{name}"
        new_path = mp3.parent / new_name
        mp3.rename(new_path)
        print(f"  {name} -> {new_name}")

# Step 3: Verify and update metadata
print("\n=== Step 3: Update metadata ===")
if new_folder.exists():
    for mp3 in sorted(new_folder.glob("*.mp3")):
        try:
            audio = MP3(str(mp3), ID3=EasyID3)
            audio['album'] = "Beginner's Guide to World Music - 2006 World Cup Edition"
            audio['albumartist'] = "Various Artists"
            audio['discnumber'] = "2/3"
            audio['genre'] = "World"
            audio.save()
            print(f"  Updated: {mp3.name}")
        except Exception as e:
            print(f"  Error on {mp3.name}: {e}")

print("\n=== Complete ===")
