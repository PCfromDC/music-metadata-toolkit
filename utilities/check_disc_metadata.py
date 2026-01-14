#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick check of disc metadata"""

from mutagen.mp3 import MP3
from mutagen.id3 import ID3
import sys

if __name__ == "__main__":
    filepath = sys.argv[1]

    try:
        audio = MP3(filepath, ID3=ID3)
        print(f"File: {filepath.split('/')[-1]}")

        # Check TPOS (disc number)
        if 'TPOS' in audio.tags:
            print(f"  Disc: {audio.tags['TPOS'].text[0]}")
        else:
            print(f"  Disc: NOT SET")

        # Check TRCK (track number)
        if 'TRCK' in audio.tags:
            print(f"  Track: {audio.tags['TRCK'].text[0]}")
        else:
            print(f"  Track: NOT SET")

    except Exception as e:
        print(f"Error: {e}")
