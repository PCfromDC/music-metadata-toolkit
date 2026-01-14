#!/usr/bin/env python3
"""Retry albums that failed due to network errors"""

import subprocess
import sys
import time

# Albums that failed in batch_remaining_covers.py due to network errors
failed_albums = [
    ("African Lullaby", "45df427c-f554-4ab1-af9b-ad6277509fd9"),
    ("Caviar at 3 A.M.", "ca6212c8-daf4-481c-af67-1a15c5dedbd0"),
    ("Classical World - Volume III", "78c3c276-4657-44f6-aa5a-450c0279064d"),
    ("Erotic Lounge, Vol. 5: Secret Affairs", "a0cfb4ef-56c9-453d-8cac-826185cbc6fe"),
    ("Erotic Lounge, Vol. 6: Seductive Pearls", "a0cfb4ef-56c9-453d-8cac-826185cbc6fe"),
    ("Cuban Lullaby", "52524c6e-eb15-41f2-9906-a51cc21cc644"),
    ("Lullaby: A Collection", "4336745d-3adb-442b-b1b4-738ba552bf82"),
    ("Lazy Sunday", "16915781-4f8e-4961-8bc5-567e0c77f3a8"),
    ("Lazy Sunday 4", "f9b57207-e58a-40a2-874a-745858c3bf68"),
    ("The Chillout Session [2001]", "04ad97e8-1a0b-4ab5-8f24-6c388548fcc7"),
    ("The Chillout Session [2006]", "6ac10fb3-56de-4132-8e00-d9f3ff156306"),
    ("The Chillout Session: Summer Collection", "99190f20-0ad0-433e-b4dc-d7a797f04450"),
    ("Asia Lounge: Asian Flavoured Club Tunes", "f6e4b8e5-ed17-4ea1-a9ff-185a89298096"),
    ("Cafe de Flore, Vol. 2", "929a23df-4c02-4ac7-8b1e-37075fba4374"),
    ("Cafe Arabesque", "a6f7c34d-ffab-4b30-9367-17b813aa5650"),
    ("Cafe Buddha: The Cream of Lounge Cuisine", "668952c2-e342-4c91-887a-e7b865d9ad1f"),
    ("Saint-Germain-Des-Pres Cafe, Vol. 3", "a264521a-c558-4629-be19-0f5515890af8"),
    ("Saint-Germain-Des-Pres Cafe, Vol. 6", "a264521a-c558-4629-be19-0f5515890af8"),
    ("Cantar Y Jugar", "b101d503-52b6-48cc-88ed-804b191a0b6c"),
    ("Balada 1 Fem", "7518183f-2fcb-4ef2-8106-b542e178df0d"),
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
                    print(f"    Attempt {attempt + 1} failed, retrying in 3 seconds...")
                    time.sleep(3)
                    continue
                return ("ERROR", error_msg)
        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                print(f"    Attempt {attempt + 1} timed out, retrying...")
                time.sleep(3)
                continue
            return ("TIMEOUT", "Command timed out after 180 seconds")
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    Attempt {attempt + 1} exception: {str(e)[:100]}, retrying...")
                time.sleep(3)
                continue
            return ("ERROR", str(e)[:200])

    return ("ERROR", "All retry attempts failed")

if __name__ == "__main__":
    print("=== Retrying Failed Albums ===\n")
    print(f"Processing {len(failed_albums)} albums with retry logic...\n")

    success_count = 0
    error_count = 0
    timeout_count = 0

    for i, (folder_name, release_id) in enumerate(failed_albums, 1):
        album_path = f"/path/to/music/Various Artists/{folder_name}"

        print(f"[{i}/{len(failed_albums)}] {folder_name}")
        print(f"  Release ID: {release_id}")
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
        if i < len(failed_albums):
            time.sleep(2)

    print("=== Summary ===")
    print(f"Success: {success_count}")
    print(f"Timeouts: {timeout_count}")
    print(f"Errors: {error_count}")
    print(f"Total: {len(failed_albums)}")
