#!/usr/bin/env python3
"""Retry failed albums with proper MusicBrainz lookups"""

import subprocess
import sys
import json
import urllib.request
import urllib.parse
import time

# Albums that failed in restore_all_covers.py - need to look up real release IDs
failed_albums = [
    # Soundtracks
    ("/path/to/music/Various Artists - Soundtracks/Down from the Mountain_ O Brother, Where Art Thou?", "Down from the Mountain O Brother Where Art Thou"),
    ("/path/to/music/Various Artists - Soundtracks/Sesame Street_ The Best Of Elmo", "Sesame Street The Best Of Elmo"),
    ("/path/to/music/Various Artists - Soundtracks/The Many Songs Of Winnie The Pooh (English Version)", "The Many Songs Of Winnie The Pooh"),

    # Holiday
    ("/path/to/music/Various Artists - Holiday/A Very Special Christmas, Vol. 4_ Live", "A Very Special Christmas Vol 4 Live"),

    # Putumayo - using real search names from batch script
    ("/path/to/music/Various Artists/Putumayo Presents_ A Mediterranean Odyssey", "Putumayo Presents A Mediterranean Odyssey"),
    ("/path/to/music/Various Artists/Putumayo Presents_ A New Groove", "Putumayo Presents A New Groove"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Acoustic Africa", "Putumayo Presents Acoustic Africa"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Afro-Latino", "Putumayo Presents Afro Latino"),
    ("/path/to/music/Various Artists/Putumayo Presents_ American Blues", "Putumayo Presents American Blues"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Arabic Groove", "Putumayo Presents Arabic Groove"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Asian Groove", "Putumayo Presents Asian Groove"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Brazilian Lounge", "Putumayo Presents Brazilian Lounge"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Cape Verde", "Putumayo Presents Cape Verde"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Colombia", "Putumayo Presents Colombia"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Congo to Cuba", "Putumayo Presents Congo to Cuba"),
    ("/path/to/music/Various Artists/Putumayo Presents_ French Cafe", "Putumayo Presents French Cafe"),
    ("/path/to/music/Various Artists/Putumayo Presents_ French Caribbean", "Putumayo Presents French Caribbean"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Global Soul", "Putumayo Presents Global Soul"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Puerto Rico", "Putumayo Presents Puerto Rico"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Sahara Lounge", "Putumayo Presents Sahara Lounge"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Samba Bossa Nova", "Putumayo Presents Samba Bossa Nova"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Turkish Groove", "Putumayo Presents Turkish Groove"),
    ("/path/to/music/Various Artists/Putumayo Presents_ World Groove", "Putumayo Presents World Groove"),
    ("/path/to/music/Various Artists/Putumayo Presents_ World Lounge", "Putumayo Presents World Lounge"),

    # Others
    ("/path/to/music/Various Artists/Bar Lounge Classics, Vol. 2", "Bar Lounge Classics Vol 2"),
    ("/path/to/music/Various Artists/African Lullaby", "African Lullaby"),
    ("/path/to/music/Various Artists/Cuban Lullaby", "Cuban Lullaby"),
    ("/path/to/music/Various Artists/Lazy Sunday", "Lazy Sunday"),
    ("/path/to/music/Various Artists/Classical World - Volume III", "Classical World Volume 3"),
]

def search_musicbrainz(album_name):
    """Search MusicBrainz for album release ID"""
    query = urllib.parse.quote(album_name)
    url = f"https://musicbrainz.org/ws/2/release/?query={query}&fmt=json&limit=1"

    try:
        time.sleep(1.5)  # Rate limiting
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            if data.get('releases') and len(data['releases']) > 0:
                return data['releases'][0]['id']
    except Exception as e:
        print(f"    ERROR searching MusicBrainz: {e}")

    return None

def embed_cover(album_path, release_id, max_retries=3):
    """Embed cover art with retry logic"""
    cover_url = f"https://coverartarchive.org/release/{release_id}/front-1200"

    for attempt in range(max_retries):
        try:
            cmd = [
                "python", "utilities/embed_cover.py",
                album_path,
                cover_url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if "Done! Embedded cover art into" in line:
                        return ("SUCCESS", line)
                return ("ERROR", "Unknown error")
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unknown error"
                if attempt < max_retries - 1:
                    print(f"    Attempt {attempt + 1} failed, retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                return ("ERROR", error_msg)
        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                print(f"    Attempt {attempt + 1} timed out, retrying...")
                time.sleep(5)
                continue
            return ("TIMEOUT", "Command timed out after 180 seconds")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    Attempt {attempt + 1} exception: {str(e)[:100]}, retrying...")
                time.sleep(5)
                continue
            return ("ERROR", str(e)[:200])

    return ("ERROR", "All retry attempts failed")

if __name__ == "__main__":
    print("=== Retrying Failed Albums with MusicBrainz Lookup ===\n")
    print(f"Processing {len(failed_albums)} albums...\n")

    success_count = 0
    skip_count = 0
    error_count = 0
    timeout_count = 0

    for i, (album_path, search_name) in enumerate(failed_albums, 1):
        album_name = album_path.split("/")[-1]
        print(f"[{i}/{len(failed_albums)}] {album_name}")
        print(f"  Searching MusicBrainz for: {search_name}...")

        release_id = search_musicbrainz(search_name)

        if not release_id:
            print(f"  [SKIP] Not found in MusicBrainz")
            skip_count += 1
            print()
            continue

        print(f"  Found: {release_id}")
        print(f"  Embedding cover art...")

        status, message = embed_cover(album_path, release_id)

        if status == "SUCCESS":
            print(f"  [OK] {message}")
            success_count += 1
        elif status == "TIMEOUT":
            print(f"  [TIMEOUT] {message}")
            timeout_count += 1
        else:
            print(f"  [ERROR] {message}")
            error_count += 1

        print()

        # Delay between albums
        if i < len(failed_albums):
            time.sleep(2)

    print("=== Summary ===")
    print(f"Success: {success_count}")
    print(f"Skipped (not found): {skip_count}")
    print(f"Timeouts: {timeout_count}")
    print(f"Errors: {error_count}")
    print(f"Total: {len(failed_albums)}")
