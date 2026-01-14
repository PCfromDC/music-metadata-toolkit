#!/usr/bin/env python3
"""Batch add cover art to remaining Various Artists albums"""

import subprocess
import sys
import json
import urllib.request
import urllib.parse
import time

# Remaining albums that need cover art (excluding Putumayo already done)
albums = [
    ("African Lullaby", "African Lullaby"),
    ("Caviar at 3 A.M.", "Caviar at 3 AM"),
    ("Classical World - Volume III", "Classical World Volume 3"),
    ("Erotic Lounge [German Deluxe] Disc 1", "Erotic Lounge"),
    ("Erotic Lounge [German Deluxe] Disc 2", "Erotic Lounge"),
    ("Erotic Lounge, Vol. 2", "Erotic Lounge Vol 2"),
    ("Erotic Lounge, Vol. 4 Bare Jewels", "Erotic Lounge Vol 4"),
    ("Erotic Lounge, Vol. 5: Secret Affairs", "Erotic Lounge Vol 5"),
    ("Erotic Lounge, Vol. 6: Seductive Pearls", "Erotic Lounge Vol 6"),
    ("Cuban Lullaby", "Cuban Lullaby"),
    ("Latin Lullaby", "Latin Lullaby"),
    ("Mediterranean Lullaby", "Mediterranean Lullaby"),
    ("Lullaby: A Collection", "Lullaby A Collection"),
    ("Lazy Sunday", "Lazy Sunday"),
    ("Lazy Sunday 2", "Lazy Sunday 2"),
    ("Lazy Sunday 3", "Lazy Sunday 3"),
    ("Lazy Sunday 4", "Lazy Sunday 4"),
    ("Lazy Sunday 5", "Lazy Sunday 5"),
    ("Ambient Lounge, Vol. 5", "Ambient Lounge Vol 5"),
    ("Ambient Lounge, Vol. 8", "Ambient Lounge Vol 8"),
    ("Ambient Lounge, Vol. 9", "Ambient Lounge Vol 9"),
    ("Rio Lounge, Vol. 1", "Rio Lounge Vol 1"),
    ("Lounge For Lovers 3", "Lounge For Lovers 3"),
    ("Chill-Out, Vol. 2", "Chill Out Vol 2"),
    ("The Chillout Session [2001]", "Chillout Session 2001"),
    ("The Chillout Session [2002]", "Chillout Session 2002"),
    ("The Chillout Session [2006]", "Chillout Session 2006"),
    ("The Chillout Session: Summer Collection", "Chillout Session Summer"),
    ("Asia Lounge: Asian Flavoured Club Tunes", "Asia Lounge"),
    ("Nueva Bossa Nova", "Nueva Bossa Nova"),
    ("Cafe de Flore, Vol. 2", "Cafe de Flore Vol 2"),
    ("Cafe Arabesque", "Cafe Arabesque"),
    ("Cafe Buddha: The Cream of Lounge Cuisine", "Cafe Buddha"),
    ("Saint-Germain-Des-Pres Cafe, Vol. 3", "Saint Germain Des Pres Cafe Vol 3"),
    ("Saint-Germain-Des-Pres Cafe, Vol. 6", "Saint Germain Des Pres Cafe Vol 6"),
    ("Cantar Y Jugar", "Cantar Y Jugar"),
    ("Balada 1 Fem", "Balada 1 Fem"),
    ("Balada 3 Fem", "Balada 3 Fem"),
    ("Balada 3 masc.", "Balada 3 masc"),
]

def search_musicbrainz(album_name):
    """Search MusicBrainz for album release ID"""
    query = urllib.parse.quote(album_name)
    url = f"https://musicbrainz.org/ws/2/release/?query={query}&fmt=json&limit=1"

    try:
        time.sleep(1)  # Rate limiting
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read())
            if data.get('releases') and len(data['releases']) > 0:
                return data['releases'][0]['id']
    except Exception as e:
        print(f"  ERROR searching MusicBrainz: {e}")

    return None

def embed_cover(album_path, release_id):
    """Embed cover art using embed_cover.py"""
    cover_url = f"https://coverartarchive.org/release/{release_id}/front-1200"
    cmd = [
        "python", "utilities/embed_cover.py",
        album_path,
        cover_url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if "Done! Embedded cover art into" in line:
                    return line
        else:
            return f"ERROR: {result.stderr[:200]}"
    except Exception as e:
        return f"ERROR: {e}"

    return "ERROR: Unknown"

if __name__ == "__main__":
    print("=== Batch Remaining Albums Cover Art Embedding ===\n")
    print(f"Processing {len(albums)} albums...\n")

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, (folder_name, search_name) in enumerate(albums, 1):
        album_path = f"/path/to/music/Various Artists/{folder_name}"

        print(f"[{i}/{len(albums)}] {folder_name}")
        print(f"  Searching MusicBrainz for: {search_name}...")

        release_id = search_musicbrainz(search_name)

        if not release_id:
            print(f"  SKIP: Not found in MusicBrainz")
            skip_count += 1
            print()
            continue

        print(f"  Found: {release_id}")
        print(f"  Embedding cover art...")

        result = embed_cover(album_path, release_id)

        if "ERROR" in result:
            print(f"  {result}")
            error_count += 1
        else:
            print(f"  {result}")
            success_count += 1

        print()

    print("=== Summary ===")
    print(f"Success: {success_count}")
    print(f"Skipped (not found): {skip_count}")
    print(f"Errors: {error_count}")
    print(f"Total: {len(albums)}")
