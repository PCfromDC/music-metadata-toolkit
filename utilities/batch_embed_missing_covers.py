#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch embed missing cover art from validation report
"""

import json
import subprocess
import time

def embed_missing_covers(validation_file, artist_path):
    """
    Embed cover art for albums marked as 'available_online' in validation report.
    """
    print("Reading validation report...")

    with open(validation_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter albums missing cover art but available online
    missing = [a for a in data['albums'] if a.get('cover_status') == 'available_online']

    print(f"\nFound {len(missing)} albums needing cover art\n")
    print("="*80)

    success_count = 0
    error_count = 0

    for i, album in enumerate(missing, 1):
        album_name = album['folder_name']
        release_id = album.get('musicbrainz_id')

        if not release_id:
            print(f"[{i}/{len(missing)}] {album_name}")
            print(f"  [SKIP] No MusicBrainz ID")
            error_count += 1
            continue

        album_path = f"{artist_path}/{album_name}"
        cover_url = f"https://coverartarchive.org/release/{release_id}/front-1200"

        print(f"[{i}/{len(missing)}] {album_name}")
        print(f"  MusicBrainz ID: {release_id}")
        print(f"  Downloading and embedding cover art...")

        try:
            # Call embed_cover.py utility
            result = subprocess.run(
                ['python', 'utilities/embed_cover.py', album_path, cover_url],
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode == 0:
                # Check for success message
                if "Done! Embedded cover art into" in result.stdout:
                    print(f"  [OK] Cover art embedded")
                    success_count += 1
                else:
                    print(f"  [ERROR] Unknown result")
                    error_count += 1
            else:
                error_msg = result.stderr[:150] if result.stderr else "Unknown error"
                print(f"  [ERROR] {error_msg}")
                error_count += 1

        except subprocess.TimeoutExpired:
            print(f"  [TIMEOUT] Command timed out")
            error_count += 1
        except Exception as e:
            print(f"  [ERROR] {str(e)[:150]}")
            error_count += 1

        print()

        # Small delay between albums
        if i < len(missing):
            time.sleep(2)

    print("="*80)
    print(f"\n=== SUMMARY ===")
    print(f"Success: {success_count}/{len(missing)}")
    print(f"Errors: {error_count}/{len(missing)}")

if __name__ == '__main__':
    validation_file = 'D:/music cleanup/outputs/various_artists_validation.json'
    artist_path = '/path/to/music/Various Artists'

    embed_missing_covers(validation_file, artist_path)
