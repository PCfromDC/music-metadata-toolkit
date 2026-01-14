#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Disc Album Consolidation Utility

Consolidates separate disc folders into a single album folder with
{disc}-{track} filename format for human readability and Plex compatibility.

Usage:
    # Preview consolidation
    python utilities/consolidate_discs.py --preview "/path/to/music/Various Artists" "70's Disco Ball Party Pack"

    # Execute consolidation
    python utilities/consolidate_discs.py --consolidate "/path/to/music/Various Artists" "70's Disco Ball Party Pack"

Format:
    Before: Album Disc 1/01 Track.mp3, Album Disc 2/01 Track.mp3
    After:  Album/1-01 Track.mp3, Album/2-01 Track.mp3
"""

import argparse
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC


def find_disc_folders(parent_path: Path, album_name: str) -> List[Tuple[int, Path]]:
    """
    Find all disc folders for an album.

    Looks for patterns like:
    - "Album Disc 1", "Album Disc 2"
    - "Album CD1", "Album CD2"
    - "Album [Disc 1]", "Album [Disc 2]"

    Args:
        parent_path: Parent folder containing disc folders
        album_name: Base album name (without disc indicator)

    Returns:
        List of (disc_number, folder_path) tuples, sorted by disc number
    """
    disc_folders = []

    # Patterns to match disc indicators
    patterns = [
        rf"^{re.escape(album_name)}\s*(?:Disc|CD|Disk)\s*(\d+)$",
        rf"^{re.escape(album_name)}\s*\[(?:Disc|CD|Disk)\s*(\d+)\]$",
        rf"^{re.escape(album_name)}\s*\((?:Disc|CD|Disk)\s*(\d+)\)$",
    ]

    for item in parent_path.iterdir():
        if not item.is_dir():
            continue

        for pattern in patterns:
            match = re.match(pattern, item.name, re.IGNORECASE)
            if match:
                disc_num = int(match.group(1))
                disc_folders.append((disc_num, item))
                break

    return sorted(disc_folders, key=lambda x: x[0])


def get_audio_files(folder: Path) -> List[Path]:
    """Get all audio files in a folder, sorted by name."""
    extensions = {'.mp3', '.m4a', '.flac', '.ogg', '.wav'}
    files = [f for f in folder.iterdir()
             if f.is_file() and f.suffix.lower() in extensions]
    return sorted(files)


def extract_track_number(filename: str) -> Optional[int]:
    """Extract track number from filename."""
    # Match patterns like "01 Title", "1 Title", "01. Title"
    match = re.match(r'^(\d+)[\s.\-_]', filename)
    if match:
        return int(match.group(1))
    return None


def get_track_title(filepath: Path) -> Optional[str]:
    """Get track title from metadata."""
    ext = filepath.suffix.lower()
    try:
        if ext == '.mp3':
            audio = EasyID3(str(filepath))
            return audio.get('title', [None])[0]
        elif ext == '.m4a':
            audio = MP4(str(filepath))
            return audio.get('\xa9nam', [None])[0]
        elif ext == '.flac':
            audio = FLAC(str(filepath))
            return audio.get('title', [None])[0]
    except Exception:
        pass
    return None


def update_disc_metadata(filepath: Path, disc_number: int, total_discs: int) -> bool:
    """
    Update disc number in file metadata.

    Args:
        filepath: Path to audio file
        disc_number: Disc number to set
        total_discs: Total number of discs

    Returns:
        True if successful
    """
    ext = filepath.suffix.lower()
    try:
        if ext == '.mp3':
            audio = MP3(str(filepath), ID3=EasyID3)
            audio['discnumber'] = f"{disc_number}/{total_discs}"
            audio.save()
        elif ext == '.m4a':
            audio = MP4(str(filepath))
            audio['disk'] = [(disc_number, total_discs)]
            audio.save()
        elif ext == '.flac':
            audio = FLAC(str(filepath))
            audio['discnumber'] = str(disc_number)
            audio['disctotal'] = str(total_discs)
            audio.save()
        return True
    except Exception as e:
        print(f"  Warning: Could not update metadata for {filepath.name}: {e}")
        return False


def make_safe_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    replacements = {
        '/': ' - ',
        '\\': ' - ',
        ':': ' -',
        '"': "'",
        '<': '',
        '>': '',
        '|': '',
        '?': '',
        '*': '',
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return ' '.join(name.split()).strip()


def preview_consolidation(parent_path: Path, album_name: str) -> Dict:
    """
    Preview what consolidation would do.

    Returns:
        Dictionary with preview information
    """
    disc_folders = find_disc_folders(parent_path, album_name)

    if not disc_folders:
        return {
            'status': 'error',
            'error': f'No disc folders found for "{album_name}"',
            'searched_in': str(parent_path)
        }

    result = {
        'status': 'preview',
        'album_name': album_name,
        'target_folder': str(parent_path / album_name),
        'disc_count': len(disc_folders),
        'discs': [],
        'total_tracks': 0
    }

    for disc_num, disc_path in disc_folders:
        audio_files = get_audio_files(disc_path)

        disc_info = {
            'disc_number': disc_num,
            'source_folder': str(disc_path),
            'track_count': len(audio_files),
            'files': []
        }

        for audio_file in audio_files:
            track_num = extract_track_number(audio_file.name)
            title = get_track_title(audio_file) or audio_file.stem

            # Generate new filename
            if track_num:
                new_name = f"{disc_num}-{str(track_num).zfill(2)} {make_safe_filename(title)}{audio_file.suffix}"
            else:
                new_name = f"{disc_num}-00 {make_safe_filename(title)}{audio_file.suffix}"

            disc_info['files'].append({
                'original': audio_file.name,
                'new_name': new_name
            })

        result['discs'].append(disc_info)
        result['total_tracks'] += len(audio_files)

    return result


def consolidate_album(parent_path: Path, album_name: str, dry_run: bool = False) -> Dict:
    """
    Consolidate multi-disc album into single folder.

    Args:
        parent_path: Parent folder containing disc folders
        album_name: Base album name
        dry_run: If True, only preview changes

    Returns:
        Dictionary with results
    """
    disc_folders = find_disc_folders(parent_path, album_name)

    if not disc_folders:
        return {
            'status': 'error',
            'error': f'No disc folders found for "{album_name}"'
        }

    target_folder = parent_path / album_name
    total_discs = len(disc_folders)

    result = {
        'status': 'success',
        'album_name': album_name,
        'target_folder': str(target_folder),
        'disc_count': total_discs,
        'files_moved': 0,
        'metadata_updated': 0,
        'errors': [],
        'dry_run': dry_run
    }

    if not dry_run:
        # Create target folder if it doesn't exist
        target_folder.mkdir(exist_ok=True)

    for disc_num, disc_path in disc_folders:
        audio_files = get_audio_files(disc_path)

        print(f"\nProcessing Disc {disc_num} ({len(audio_files)} tracks)...")

        for audio_file in audio_files:
            track_num = extract_track_number(audio_file.name)
            title = get_track_title(audio_file) or audio_file.stem

            # Remove any existing disc-track prefix from title for clean filename
            clean_title = re.sub(r'^\d+-\d+\s*', '', title)
            clean_title = re.sub(r'^\d+\s*', '', clean_title)
            if not clean_title:
                clean_title = title

            # Generate new filename: {disc}-{track} {title}.{ext}
            track_str = str(track_num).zfill(2) if track_num else '00'
            new_name = f"{disc_num}-{track_str} {make_safe_filename(clean_title)}{audio_file.suffix}"
            new_path = target_folder / new_name

            print(f"  {audio_file.name} -> {new_name}")

            if not dry_run:
                try:
                    # Copy file to new location
                    shutil.copy2(str(audio_file), str(new_path))
                    result['files_moved'] += 1

                    # Update disc metadata
                    if update_disc_metadata(new_path, disc_num, total_discs):
                        result['metadata_updated'] += 1

                except Exception as e:
                    result['errors'].append(f"{audio_file.name}: {str(e)}")
            else:
                result['files_moved'] += 1

    if not dry_run and not result['errors']:
        # Ask about removing original folders
        result['original_folders'] = [str(p) for _, p in disc_folders]
        result['note'] = "Original disc folders preserved. Delete manually after verification."

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate multi-disc albums into single folder with {disc}-{track} format"
    )

    parser.add_argument(
        'parent_path',
        help='Parent folder containing disc folders (e.g., "/path/to/music/Various Artists")'
    )

    parser.add_argument(
        'album_name',
        help='Base album name without disc indicator (e.g., "70\'s Disco Ball Party Pack")'
    )

    parser.add_argument(
        '--preview', '-p',
        action='store_true',
        help='Preview consolidation without making changes'
    )

    parser.add_argument(
        '--consolidate', '-c',
        action='store_true',
        help='Execute consolidation'
    )

    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    parent_path = Path(args.parent_path)

    if not parent_path.exists():
        print(f"Error: Path not found: {parent_path}")
        return 1

    if args.preview or (not args.consolidate and not args.dry_run):
        # Preview mode
        result = preview_consolidation(parent_path, args.album_name)

        if result['status'] == 'error':
            print(f"Error: {result['error']}")
            return 1

        print(f"\n{'='*60}")
        print(f"Multi-Disc Consolidation Preview")
        print(f"{'='*60}")
        print(f"Album: {result['album_name']}")
        print(f"Target: {result['target_folder']}")
        print(f"Discs: {result['disc_count']}")
        print(f"Total tracks: {result['total_tracks']}")

        for disc in result['discs']:
            print(f"\n--- Disc {disc['disc_number']} ({disc['track_count']} tracks) ---")
            print(f"Source: {disc['source_folder']}")
            for f in disc['files'][:5]:
                print(f"  {f['original']}")
                print(f"    -> {f['new_name']}")
            if len(disc['files']) > 5:
                print(f"  ... and {len(disc['files']) - 5} more tracks")

        print(f"\nRun with --consolidate to execute.")

    elif args.consolidate or args.dry_run:
        # Consolidation mode
        result = consolidate_album(parent_path, args.album_name, dry_run=args.dry_run)

        if result['status'] == 'error':
            print(f"Error: {result['error']}")
            return 1

        print(f"\n{'='*60}")
        print(f"Consolidation {'Preview (Dry Run)' if args.dry_run else 'Complete'}")
        print(f"{'='*60}")
        print(f"Album: {result['album_name']}")
        print(f"Target: {result['target_folder']}")
        print(f"Files moved: {result['files_moved']}")
        print(f"Metadata updated: {result['metadata_updated']}")

        if result['errors']:
            print(f"\nErrors ({len(result['errors'])}):")
            for err in result['errors']:
                print(f"  - {err}")

        if result.get('note'):
            print(f"\nNote: {result['note']}")

    return 0


if __name__ == "__main__":
    exit(main())
