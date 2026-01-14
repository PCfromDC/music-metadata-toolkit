"""
Track Mover - Move tracks between albums with metadata update

Moves a track from one album to another, updating metadata
and cleaning up empty source folders.
"""

from pathlib import Path
from typing import Optional
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    from mutagen.mp3 import MP3
    from mutagen.easyid3 import EasyID3
except ImportError:
    print("Error: mutagen library required. Install with: pip install mutagen")
    sys.exit(1)


class TrackMover:
    """Move tracks between albums with metadata updates."""

    def move(
        self,
        source: str | Path,
        dest_folder: str | Path,
        track_number: Optional[str] = None,
        album: Optional[str] = None,
        artist: Optional[str] = None,
        album_artist: Optional[str] = None,
        date: Optional[str] = None,
        genre: Optional[str] = None
    ) -> bool:
        """
        Move a track to a different album folder.

        Args:
            source: Path to the source track
            dest_folder: Destination album folder
            track_number: New track number (e.g., "5/12")
            album: New album name
            artist: Track artist
            album_artist: Album artist (defaults to artist if not specified)
            date: Release date/year
            genre: Genre

        Returns:
            True if successful, False otherwise
        """
        source_path = Path(source)
        dest_path = Path(dest_folder)

        if not source_path.exists():
            print(f"Source not found: {source_path}")
            return False

        if not dest_path.exists():
            print(f"Creating destination folder: {dest_path}")
            dest_path.mkdir(parents=True)

        # Determine destination filename
        dest_file = dest_path / source_path.name

        # If track number provided, may need to rename file
        if track_number:
            # Extract just the track number for filename
            track_num = track_number.split('/')[0].zfill(2)
            # Get title from current filename or metadata
            try:
                audio = MP3(str(source_path), ID3=EasyID3)
                title = audio.get('title', ['Unknown'])[0]
            except:
                title = source_path.stem

            new_filename = f"{track_num} {title}.mp3"
            dest_file = dest_path / new_filename

        print(f"Moving track:")
        print(f"  From: {source_path}")
        print(f"  To:   {dest_file}")

        # Move the file
        shutil.move(str(source_path), str(dest_file))

        # Update metadata
        updates = {}
        if album:
            updates['album'] = album
        if artist:
            updates['artist'] = artist
        if album_artist:
            updates['albumartist'] = album_artist
        elif artist:
            updates['albumartist'] = artist
        if track_number:
            updates['tracknumber'] = track_number
        if date:
            updates['date'] = date
        if genre:
            updates['genre'] = genre

        if updates:
            try:
                audio = MP3(str(dest_file), ID3=EasyID3)
                for key, value in updates.items():
                    audio[key] = value
                audio.save()
                print(f"  Updated metadata: {list(updates.keys())}")
            except Exception as e:
                print(f"  Warning: Could not update metadata: {e}")

        # Clean up empty source folder
        source_folder = source_path.parent
        remaining_mp3s = list(source_folder.glob("*.mp3"))
        if not remaining_mp3s:
            # Check for other files (cover art, etc.)
            remaining = list(source_folder.glob("*"))
            if not remaining:
                source_folder.rmdir()
                print(f"  Removed empty folder: {source_folder.name}")
            elif len(remaining) == 1 and remaining[0].name == "folder.jpg":
                # Only folder.jpg left, remove it and the folder
                remaining[0].unlink()
                source_folder.rmdir()
                print(f"  Removed empty folder: {source_folder.name}")

        print("  Move complete!")
        return True


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Move track between albums')
    parser.add_argument('source', help='Source track path')
    parser.add_argument('dest', help='Destination folder')
    parser.add_argument('--number', help='New track number (e.g., "5/12")')
    parser.add_argument('--album', help='New album name')
    parser.add_argument('--artist', help='Track/album artist')
    parser.add_argument('--album-artist', help='Album artist (if different from artist)')
    parser.add_argument('--date', help='Release date/year')
    parser.add_argument('--genre', help='Genre')

    args = parser.parse_args()

    mover = TrackMover()
    success = mover.move(
        source=args.source,
        dest_folder=args.dest,
        track_number=args.number,
        album=args.album,
        artist=args.artist,
        album_artist=args.album_artist,
        date=args.date,
        genre=args.genre
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
