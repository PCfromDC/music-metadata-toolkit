#!/usr/bin/env python3
"""Fix tracks with missing artist metadata"""

from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
import sys

# Tracks to fix based on research
fixes = [
    {
        'path': r'\\openmediavault\music\Various Artists - Holiday\Now That\'s What I Call Christmas! 3\22 O Holy Night.mp3',
        'artist': 'Al Green',
        'title': 'O Holy Night'
    },
    {
        'path': r'\\openmediavault\music\Various Artists - Holiday\Now That\'s What I Call Christmas! 3\32 Santa Baby.mp3',
        'artist': 'Pussycat Dolls',
        'title': 'Santa Baby'
    },
    {
        'path': r'\\openmediavault\music\Various Artists - Soundtracks\Grease\23 Love Is a Many Splendored Thing.mp3',
        'artist': 'Studio Orchestra',
        'title': 'Love Is a Many Splendored Thing'
    }
]

def fix_track(filepath, artist, title):
    """Fix artist metadata for a track"""
    try:
        print(f"\nFixing: {title}")
        print(f"  File: {filepath}")

        # Read current metadata
        audio = MP3(filepath, ID3=EasyID3)
        print(f"  BEFORE - Artist: {audio.get('artist', ['(none)'])[0]}")

        # Update artist
        audio['artist'] = artist
        audio.save()

        # Verify
        audio = MP3(filepath, ID3=EasyID3)
        print(f"  AFTER  - Artist: {audio.get('artist', ['(none)'])[0]}")
        print("  ✓ Fixed successfully")
        return True

    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("=== Fixing Tracks With Missing Artist Metadata ===\n")

    success_count = 0
    total = len(fixes)

    for fix in fixes:
        if fix_track(fix['path'], fix['artist'], fix['title']):
            success_count += 1

    print(f"\n=== Summary ===")
    print(f"Fixed: {success_count}/{total} tracks")

    if success_count == total:
        print("✓ All tracks fixed successfully!")
        sys.exit(0)
    else:
        print(f"✗ {total - success_count} tracks failed")
        sys.exit(1)
