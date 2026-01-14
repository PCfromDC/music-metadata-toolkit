"""Move track from Natural Acoustic to Ben Harper/Welcome to the Cruel World"""
import shutil
from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

# Source and destination
source = Path(r"/path/to/music/Various Artists/Natural Acoustic/01 Waiting on an Angel.mp3")
dest_folder = Path(r"/path/to/music/Ben Harper/Welcome to the Cruel World")
dest_file = dest_folder / "02 Waiting on an Angel.mp3"

# Move the file
print(f"Moving: {source.name}")
print(f"To: {dest_file}")
shutil.move(str(source), str(dest_file))
print("File moved successfully")

# Update metadata
print("\nUpdating metadata...")
audio = MP3(str(dest_file), ID3=EasyID3)

print(f"  Before:")
print(f"    Album: {audio.get('album', [''])[0]}")
print(f"    Album Artist: {audio.get('albumartist', [''])[0]}")
print(f"    Track: {audio.get('tracknumber', [''])[0]}")

# Update fields
audio['album'] = 'Welcome to the Cruel World'
audio['albumartist'] = 'Ben Harper'
audio['artist'] = 'Ben Harper'
audio['tracknumber'] = '2/12'
audio['date'] = '1994'
audio['genre'] = 'Rock'
audio.save()

print(f"  After:")
print(f"    Album: {audio.get('album', [''])[0]}")
print(f"    Album Artist: {audio.get('albumartist', [''])[0]}")
print(f"    Track: {audio.get('tracknumber', [''])[0]}")

# Check if source folder is now empty and can be deleted
source_folder = Path(r"/path/to/music/Various Artists/Natural Acoustic")
remaining = list(source_folder.glob("*"))
if len(remaining) == 0:
    print(f"\nRemoving empty folder: {source_folder}")
    source_folder.rmdir()
    print("Empty folder removed")
else:
    print(f"\nSource folder still has {len(remaining)} files, not removing")
