#!/usr/bin/env python3
"""Batch add cover art to Putumayo albums"""

import subprocess
import sys
import json
import urllib.request
import urllib.parse

# Putumayo albums remaining (already done: Cuba, Brasileiro, Paris, Acoustic Brazil)
albums = [
    "Putumayo Presents: A Mediterranean Odyssey",
    "Putumayo Presents: A New Groove",
    "Putumayo Presents: Acoustic Africa",
    "Putumayo Presents: Afro-Latino",
    "Putumayo Presents: American Blues",
    "Putumayo Presents: Arabic Groove",
    "Putumayo Presents: Asian Groove",
    "Putumayo Presents: Baila- A Latin Dance Party",
    "Putumayo Presents: Brazilian Lounge",
    "Putumayo Presents: Cape Verde",
    "Putumayo Presents: Colombia",
    "Putumayo Presents: Congo to Cuba",
    "Putumayo Presents: French Cafe",
    "Putumayo Presents: French Caribbean",
    "Putumayo Presents: Global Soul",
    "Putumayo Presents: Gypsy Caravan",
    "Putumayo Presents: Italian Café",
    "Putumayo Presents: Jamaica",
    "Putumayo Presents: Latin Lounge",
    "Putumayo Presents: Music from the Chocolate Lands",
    "Putumayo Presents: Music from the Tea Lands",
    "Putumayo Presents: Music from the Wine Lands",
    "Putumayo Presents: Puerto Rico",
    "Putumayo Presents: Sahara Lounge",
    "Putumayo Presents: Salsa Around the World",
    "Putumayo Presents: Samba Bossa Nova",
    "Putumayo Presents: Turkish Groove",
    "Putumayo Presents: Women of Latin America",
    "Putumayo Presents: World Groove",
    "Putumayo Presents: World Lounge"
]

def search_musicbrainz(album_name):
    """Search MusicBrainz for album release ID"""
    query = urllib.parse.quote(album_name)
    url = f"https://musicbrainz.org/ws/2/release/?query={query}&fmt=json&limit=1"

    try:
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
            # Count how many files were embedded
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if "Done! Embedded cover art into" in line:
                    return line
        else:
            return f"ERROR: {result.stderr}"
    except Exception as e:
        return f"ERROR: {e}"

    return "ERROR: Unknown"

if __name__ == "__main__":
    print("=== Batch Putumayo Cover Art Embedding ===\n")
    print(f"Processing {len(albums)} albums...\n")

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, album in enumerate(albums, 1):
        # Convert album name to folder name (replace special chars)
        folder_name = album.replace(": ", "_ ").replace(":", "_")
        album_path = f"/path/to/music/Various Artists/{folder_name}"

        print(f"[{i}/{len(albums)}] {album}")
        print(f"  Searching MusicBrainz...")

        release_id = search_musicbrainz(album)

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
