"""Fix Beginner's Guide to World Music folders"""
import shutil
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
import sys
sys.stdout.reconfigure(encoding='utf-8')

va_path = Path(r"/path/to/music/Various Artists")

# Step 1: Rename World Cup Edition folder
print("=== Step 1: Rename World Cup Edition folder ===")
old_wc = va_path / "Beginner's Guide to World Music - 2006 Wo"
new_wc = va_path / "Beginner's Guide to World Music - 2006 World Cup Edition [Disc 2]"

if old_wc.exists():
    old_wc.rename(new_wc)
    print(f"Renamed: {old_wc.name}")
    print(f"     To: {new_wc.name}")
else:
    print(f"Folder not found: {old_wc.name}")

# Step 2: Create consolidated Vol. 2 folder
print("\n=== Step 2: Create consolidated Vol. 2 folder ===")
vol2_folder = va_path / "Beginner's Guide to World Music, Vol. 2"
vol2_folder.mkdir(exist_ok=True)
print(f"Created: {vol2_folder.name}")

# Step 3: Move Disc 1 tracks
print("\n=== Step 3: Move Disc 1 (World Party) tracks ===")
disk1_folder = va_path / "Beginner's Guide To Worldmusic- Disk 1 W"
if disk1_folder.exists():
    for mp3 in sorted(disk1_folder.glob("*.mp3")):
        # Get track number from filename (01, 02, etc.)
        track_num = mp3.name[:2]
        rest_of_name = mp3.name[2:].lstrip()  # Remove leading spaces
        new_name = f"1-{track_num}{rest_of_name}"
        new_path = vol2_folder / new_name
        shutil.move(str(mp3), str(new_path))
        print(f"  {mp3.name} -> {new_name}")

# Step 4: Move Disc 3 tracks
print("\n=== Step 4: Move Disc 3 (World Chill) tracks ===")
disk3_folder = va_path / "Beginner's Guide To Worldmusic- Disk 3 W"
if disk3_folder.exists():
    for mp3 in sorted(disk3_folder.glob("*.mp3")):
        track_num = mp3.name[:2]
        rest_of_name = mp3.name[2:].lstrip()
        new_name = f"3-{track_num}{rest_of_name}"
        new_path = vol2_folder / new_name
        shutil.move(str(mp3), str(new_path))
        print(f"  {mp3.name} -> {new_name}")

# Step 5: Update metadata
print("\n=== Step 5: Update metadata ===")
for mp3 in sorted(vol2_folder.glob("*.mp3")):
    try:
        audio = MP3(str(mp3), ID3=EasyID3)

        # Determine disc number from filename prefix
        if mp3.name.startswith("1-"):
            disc = "1/3"
            disc_title = "World Party"
        elif mp3.name.startswith("3-"):
            disc = "3/3"
            disc_title = "World Chill"
        else:
            disc = "1/3"
            disc_title = ""

        # Update metadata
        audio['album'] = "Beginner's Guide to World Music, Vol. 2"
        audio['albumartist'] = "Various Artists"
        audio['discnumber'] = disc
        audio['genre'] = "World"
        audio.save()
        print(f"  Updated: {mp3.name} (Disc {disc})")
    except Exception as e:
        print(f"  Error on {mp3.name}: {e}")

# Also update World Cup Edition metadata
print("\n=== Step 6: Update World Cup Edition metadata ===")
if new_wc.exists():
    for mp3 in sorted(new_wc.glob("*.mp3")):
        try:
            audio = MP3(str(mp3), ID3=EasyID3)
            audio['album'] = "Beginner's Guide to World Music: 2006 World Cup Edition"
            audio['albumartist'] = "Various Artists"
            audio['discnumber'] = "2/3"
            audio['genre'] = "World"
            audio.save()
            print(f"  Updated: {mp3.name}")
        except Exception as e:
            print(f"  Error on {mp3.name}: {e}")

# Step 7: Clean up empty folders
print("\n=== Step 7: Clean up empty folders ===")
for folder in [disk1_folder, disk3_folder]:
    if folder.exists():
        remaining = list(folder.glob("*"))
        if len(remaining) == 0:
            folder.rmdir()
            print(f"Removed empty folder: {folder.name}")
        else:
            print(f"Folder not empty: {folder.name} ({len(remaining)} files)")

print("\n=== Complete ===")
