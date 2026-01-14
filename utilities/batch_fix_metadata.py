import os
import sys
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

def fix_genre_batch(directory, new_genre):
    """Fix genre for all MP3 files in a directory"""
    mp3_files = [f for f in os.listdir(directory)
                 if f.lower().endswith('.mp3')]

    print(f"Found {len(mp3_files)} MP3 files in: {directory}")
    print(f"Will change genre to: {new_genre}\n")

    success_count = 0
    error_files = []

    for filename in sorted(mp3_files):
        filepath = os.path.join(directory, filename)
        try:
            audio = MP3(filepath, ID3=EasyID3)
            old_genre = audio.get('genre', ['Unknown'])[0]
            audio['genre'] = new_genre
            audio.save()

            print(f"  {filename}")
            print(f"    Changed: '{old_genre}' -> '{new_genre}'")
            success_count += 1
        except Exception as e:
            print(f"  ERROR: {filename}: {e}")
            error_files.append((filename, str(e)))

    print(f"\n--- Summary ---")
    print(f"Successfully updated: {success_count}/{len(mp3_files)}")
    if error_files:
        print(f"Errors: {len(error_files)}")
        for fname, err in error_files:
            print(f"  - {fname}: {err}")

    return success_count, error_files

def verify_genre_batch(directory, expected_genre):
    """Verify all MP3 files have the expected genre"""
    mp3_files = [f for f in os.listdir(directory)
                 if f.lower().endswith('.mp3')]

    mismatches = []
    for filename in sorted(mp3_files):
        filepath = os.path.join(directory, filename)
        try:
            audio = MP3(filepath, ID3=EasyID3)
            actual_genre = audio.get('genre', ['N/A'])[0]
            if actual_genre != expected_genre:
                mismatches.append((filename, actual_genre))
        except Exception as e:
            mismatches.append((filename, f"Error: {e}"))

    return mismatches

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python batch_fix_metadata.py <directory> <new_genre>")
        print("Example: python batch_fix_metadata.py '/path/to/music/U2/U218 Singles' 'Rock'")
        sys.exit(1)

    directory = sys.argv[1]
    new_genre = sys.argv[2]

    if not os.path.exists(directory):
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)

    # Fix genre
    success, errors = fix_genre_batch(directory, new_genre)

    # Verify changes
    print("\n--- Verification ---")
    mismatches = verify_genre_batch(directory, new_genre)
    if mismatches:
        print(f"Warning: {len(mismatches)} files don't match expected genre:")
        for fname, genre in mismatches:
            print(f"  - {fname}: {genre}")
    else:
        print(f"All files verified with genre: {new_genre}")
