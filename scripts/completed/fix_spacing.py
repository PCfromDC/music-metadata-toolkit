"""Fix filename spacing"""
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')

vol2_folder = Path(r"/path/to/music/Various Artists/Beginner's Guide to World Music, Vol. 2")

print(f"Checking folder: {vol2_folder}")
print(f"Exists: {vol2_folder.exists()}")

if vol2_folder.exists():
    mp3s = list(vol2_folder.glob("*.mp3"))
    print(f"Found {len(mp3s)} MP3 files")

    for mp3 in sorted(mp3s):
        name = mp3.name
        # Fix pattern like '1-01Title' to '1-01 Title'
        if len(name) > 4 and name[0].isdigit() and name[1] == '-' and name[2:4].isdigit() and name[4] != ' ':
            new_name = name[:4] + ' ' + name[4:]
            new_path = mp3.parent / new_name
            mp3.rename(new_path)
            print(f"  {name} -> {new_name}")
        else:
            print(f"  OK: {name}")
