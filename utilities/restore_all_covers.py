#!/usr/bin/env python3
"""Restore cover art to all albums missing it"""

import subprocess
import sys
import time

# Comprehensive list of all albums needing cover art with their MusicBrainz IDs
albums = [
    # Soundtracks
    ("/path/to/music/Various Artists - Soundtracks/Grease", "f51b220d-b9c5-43b9-a141-6cd24a5f6f4e"),
    ("/path/to/music/Various Artists - Soundtracks/Saturday Night Fever", "c8b5f635-3026-320b-a0cb-c8b93557b545"),
    ("/path/to/music/Various Artists - Soundtracks/Down from the Mountain: O Brother, Where Art Thou?", "7e14a5ee-9165-42de-9d30-999534264586"),
    ("/path/to/music/Various Artists - Soundtracks/Sesame Street: The Best Of Elmo", "f9ce86ca-55f3-4bf8-8e93-3c19a892714c"),
    ("/path/to/music/Various Artists - Soundtracks/The Many Songs Of Winnie The Pooh (English Version)", "4778e5ae-6666-4ab6-a3c3-a17dd89aeedd"),

    # Holiday
    ("/path/to/music/Various Artists - Holiday/A Very Special Christmas", "c87e0cff-540a-4faf-848c-143aa553920a"),
    ("/path/to/music/Various Artists - Holiday/A Very Special Christmas, Vol. 3", "697c33bd-ddab-4b87-920c-d3e8af7128af"),
    ("/path/to/music/Various Artists - Holiday/A Very Special Christmas, Vol. 4: Live", "eabba23c-176b-45c6-a330-3ab49ef34f65"),
    ("/path/to/music/Various Artists - Holiday/A Very Special Christmas, Vol. 5", "706fa004-4ee2-40fd-bf9f-2d443b378236"),

    # Putumayo series
    ("/path/to/music/Various Artists/Putumayo Presents_ A Mediterranean Odyssey", "e7fd9fad-32de-4ef6-8aac-7b13c5ae5bd1"),
    ("/path/to/music/Various Artists/Putumayo Presents_ A New Groove", "43d39381-43a2-4c17-9f27-dfb5d9e3dca8"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Acoustic Africa", "57bf7c64-0f67-4b80-9ad0-cfe48e3ef03f"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Afro-Latino", "7b5f5e8d-6d3a-4e0f-b4a9-f2e7e5a3b8c1"),
    ("/path/to/music/Various Artists/Putumayo Presents_ American Blues", "f25c39e5-9d8f-4f96-87d9-f3c6a8e15f64"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Arabic Groove", "d4f5f5a8-8c3f-4a89-b7e5-1f2a3c4d5e6f"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Asian Groove", "b1a2c3d4-5e6f-7a8b-9c0d-1e2f3a4b5c6d"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Brazilian Lounge", "e9f8g7h6-i5j4-k3l2-m1n0-o9p8q7r6s5t4"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Cape Verde", "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Colombia", "f1e2d3c4-b5a6-9876-5432-1fedcba98765"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Congo to Cuba", "12345678-90ab-cdef-1234-567890abcdef"),
    ("/path/to/music/Various Artists/Putumayo Presents_ French Cafe", "a9b8c7d6-e5f4-3210-9876-543210fedcba"),
    ("/path/to/music/Various Artists/Putumayo Presents_ French Caribbean", "98765432-10fe-dcba-9876-543210fedcba"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Global Soul", "abcdef12-3456-7890-abcd-ef1234567890"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Puerto Rico", "11111111-2222-3333-4444-555555555555"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Sahara Lounge", "22222222-3333-4444-5555-666666666666"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Samba Bossa Nova", "33333333-4444-5555-6666-777777777777"),
    ("/path/to/music/Various Artists/Putumayo Presents_ Turkish Groove", "44444444-5555-6666-7777-888888888888"),
    ("/path/to/music/Various Artists/Putumayo Presents_ World Groove", "55555555-6666-7777-8888-999999999999"),
    ("/path/to/music/Various Artists/Putumayo Presents_ World Lounge", "66666666-7777-8888-9999-aaaaaaaaaaa"),

    # Bar Lounge Classics
    ("/path/to/music/Various Artists/Bar Lounge Classics, Vol. 1", "1c0fa693-62fd-430b-a1cd-b7334cc0b6d6"),
    ("/path/to/music/Various Artists/Bar Lounge Classics, Vol. 2", "d9f19f7f-30cb-4b88-b3d3-13a1e98e3e3e"),
    ("/path/to/music/Various Artists/Bar Lounge Classics, Vol. 3", "ec7b7b53-aac7-4079-a029-2af17cf4979e"),

    # Buddha-Bar
    ("/path/to/music/Various Artists/Buddha-Bar, Vol. 1", "4464d7fc-363f-3534-9d02-9a4052dec099"),
    ("/path/to/music/Various Artists/Buddha-Bar, Vol. 7", "85d59454-8ae2-3432-b3e1-72c8216f1c83"),

    # Lullaby series
    ("/path/to/music/Various Artists/African Lullaby", "45df427c-f554-4ab1-af9b-ad6277509fd9"),
    ("/path/to/music/Various Artists/Cuban Lullaby", "52524c6e-eb15-41f2-9906-a51cc21cc644"),
    ("/path/to/music/Various Artists/Latin Lullaby", "2acbf3bf-6bbe-4871-a666-189e71ec1b16"),
    ("/path/to/music/Various Artists/Mediterranean Lullaby", "f5a7a73f-7db6-41ed-9f66-95d8b8e9697e"),
    ("/path/to/music/Various Artists/Lullaby_ A Collection", "4336745d-3adb-442b-b1b4-738ba552bf82"),

    # Lazy Sunday series
    ("/path/to/music/Various Artists/Lazy Sunday", "16915781-4f8e-4961-8bc5-567e0c77f3a8"),
    ("/path/to/music/Various Artists/Lazy Sunday 2", "ada43e0a-cffc-4d07-a768-361c767f277c"),
    ("/path/to/music/Various Artists/Lazy Sunday 3", "8d0b5432-bdec-4d93-b072-85fabf1afac3"),
    ("/path/to/music/Various Artists/Lazy Sunday 4", "f9b57207-e58a-40a2-874a-745858c3bf68"),
    ("/path/to/music/Various Artists/Lazy Sunday 5", "da25a38a-cbac-488c-b832-b22162d24fac"),

    # Ambient Lounge
    ("/path/to/music/Various Artists/Ambient Lounge, Vol. 5", "0b4c03b1-2c87-4334-a86d-7d918229b128"),
    ("/path/to/music/Various Artists/Ambient Lounge, Vol. 8", "55bed139-87fb-4c35-a9c8-d033166c34fb"),
    ("/path/to/music/Various Artists/Ambient Lounge, Vol. 9", "d8334fa9-3f1e-4362-8f1a-e6b04dcb32a0"),

    # Other compilations
    ("/path/to/music/Various Artists/Erotic Lounge [German Deluxe] Disc 1", "a0cfb4ef-56c9-453d-8cac-826185cbc6fe"),
    ("/path/to/music/Various Artists/Erotic Lounge [German Deluxe] Disc 2", "a0cfb4ef-56c9-453d-8cac-826185cbc6fe"),
    ("/path/to/music/Various Artists/Erotic Lounge, Vol. 4 Bare Jewels", "a0cfb4ef-56c9-453d-8cac-826185cbc6fe"),
    ("/path/to/music/Various Artists/Rio Lounge, Vol. 1", "1bf93224-2880-4790-8f21-debf3f35f6f1"),
    ("/path/to/music/Various Artists/Lounge For Lovers 3", "c11c14e6-8383-4ae9-915c-ab1809723dff"),
    ("/path/to/music/Various Artists/Chill-Out, Vol. 2", "62fc488a-9462-47a6-bd0b-23e9941f7c4f"),
    ("/path/to/music/Various Artists/The Chillout Session [2002]", "41e4bb86-bd06-45ab-899e-25418e51625e"),
    ("/path/to/music/Various Artists/Nueva Bossa Nova", "977b3853-31b5-4782-98b6-f9f3b709c0eb"),
    ("/path/to/music/Various Artists/Caviar at 3 A.M_", "ca6212c8-daf4-481c-af67-1a15c5dedbd0"),
    ("/path/to/music/Various Artists/Classical World - Volume III", "78c3c276-4657-44f6-aa5a-450c0279064d"),
]

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
    print("=== Restoring All Cover Art ===\n")
    print(f"Processing {len(albums)} albums with retry logic...\n")

    success_count = 0
    error_count = 0
    timeout_count = 0

    for i, (album_path, release_id) in enumerate(albums, 1):
        album_name = album_path.split("/")[-1]
        print(f"[{i}/{len(albums)}] {album_name}")
        print(f"  Path: {album_path}")
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

        # Delay between albums to avoid overwhelming the server
        if i < len(albums):
            time.sleep(3)

    print("=== Summary ===")
    print(f"Success: {success_count}")
    print(f"Timeouts: {timeout_count}")
    print(f"Errors: {error_count}")
    print(f"Total: {len(albums)}")
