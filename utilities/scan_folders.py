"""Scan all folders for mismatched names vs album metadata"""
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
import sys
sys.stdout.reconfigure(encoding='utf-8')

va_path = Path(r"/path/to/music/Various Artists")

def make_windows_safe(name):
    # Replace colon with ' -', remove other unsafe chars
    name = name.replace(':', ' -')
    for char in ['?', '*', '"', '<', '>', '|']:
        name = name.replace(char, '')
    return name.strip()

mismatched = []
errors = []

folders = sorted([d for d in va_path.iterdir() if d.is_dir()])
print(f"Scanning {len(folders)} folders...")
print()

for folder in folders:
    try:
        mp3s = list(folder.glob("*.mp3"))
        if not mp3s:
            continue

        audio = MP3(str(mp3s[0]), ID3=EasyID3)
        album = audio.get('album', [''])[0]

        if not album:
            continue

        expected = make_windows_safe(album)

        if folder.name != expected:
            mismatched.append({
                'folder': folder.name,
                'metadata': album,
                'expected': expected
            })
    except Exception as e:
        errors.append(f"{folder.name}: {e}")

print(f"=== MISMATCHED FOLDERS ({len(mismatched)}) ===")
print()
for m in mismatched:
    print(f"Folder:   \"{m['folder']}\"")
    print(f"Metadata: \"{m['metadata']}\"")
    if m['metadata'] != m['expected']:
        print(f"Expected: \"{m['expected']}\" (Windows-safe)")
    print()

if errors:
    print(f"=== ERRORS ({len(errors)}) ===")
    for e in errors:
        print(f"  {e}")
