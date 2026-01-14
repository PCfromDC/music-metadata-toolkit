"""Rename Radio 1's Live Lounge folders"""
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')

va_path = Path(r"/path/to/music/Various Artists")

# Find and rename
for folder in va_path.iterdir():
    if folder.is_dir() and "Radio 1" in folder.name and "Volume" in folder.name:
        old_name = folder.name
        # Replace ", Volume" with " - Volume"
        new_name = old_name.replace(", Volume", " - Volume")
        if old_name != new_name:
            new_path = va_path / new_name
            folder.rename(new_path)
            print(f"OK: {old_name}")
            print(f"  → {new_name}")
