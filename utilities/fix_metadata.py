import sys
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

def fix_mp3_artist(filepath, new_artist):
    """Fix artist tag in MP3 file"""
    audio = MP3(filepath, ID3=EasyID3)
    print("BEFORE:")
    print(f"  Artist: {audio.get('artist', ['N/A'])[0]}")
    print(f"  Album: {audio.get('album', ['N/A'])[0]}")
    print(f"  Title: {audio.get('title', ['N/A'])[0]}")

    audio['artist'] = new_artist
    audio.save()

    # Verify
    audio = MP3(filepath, ID3=EasyID3)
    print("\nAFTER:")
    print(f"  Artist: {audio.get('artist', ['N/A'])[0]}")
    print(f"  Album: {audio.get('album', ['N/A'])[0]}")
    print(f"  Title: {audio.get('title', ['N/A'])[0]}")
    print("\nDone!")

def fix_mp3_title(filepath, new_title):
    """Fix title tag in MP3 file"""
    audio = MP3(filepath, ID3=EasyID3)
    print("BEFORE:")
    print(f"  Title: {audio.get('title', ['N/A'])[0]}")

    audio['title'] = new_title
    audio.save()

    # Verify
    audio = MP3(filepath, ID3=EasyID3)
    print("\nAFTER:")
    print(f"  Title: {audio.get('title', ['N/A'])[0]}")
    print("\nDone!")

def fix_mp3_genre(filepath, new_genre):
    """Fix genre tag in MP3 file"""
    audio = MP3(filepath, ID3=EasyID3)
    print("BEFORE:")
    print(f"  Genre: {audio.get('genre', ['N/A'])[0]}")
    print(f"  Artist: {audio.get('artist', ['N/A'])[0]}")
    print(f"  Album: {audio.get('album', ['N/A'])[0]}")
    print(f"  Title: {audio.get('title', ['N/A'])[0]}")

    audio['genre'] = new_genre
    audio.save()

    # Verify
    audio = MP3(filepath, ID3=EasyID3)
    print("\nAFTER:")
    print(f"  Genre: {audio.get('genre', ['N/A'])[0]}")
    print(f"  Artist: {audio.get('artist', ['N/A'])[0]}")
    print(f"  Album: {audio.get('album', ['N/A'])[0]}")
    print(f"  Title: {audio.get('title', ['N/A'])[0]}")
    print("\nDone!")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python fix_metadata.py <action> <filepath> <new_value>")
        print("Actions: artist, title, genre")
        sys.exit(1)

    action = sys.argv[1]
    filepath = sys.argv[2]
    new_value = sys.argv[3]

    if action == "artist":
        fix_mp3_artist(filepath, new_value)
    elif action == "title":
        fix_mp3_title(filepath, new_value)
    elif action == "genre":
        fix_mp3_genre(filepath, new_value)
    else:
        print(f"Unknown action: {action}")
