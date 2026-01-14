#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multi-Disc Album Consolidation Utility

Purpose: Merge multi-disc compilation albums into single folders while preserving disc information in metadata.

Usage:
    # Scan for multi-disc albums
    python consolidate_multidisc.py --scan "/path/to/music/Various Artists"

    # Consolidate specific album
    python consolidate_multidisc.py --consolidate "70's Disco Ball Party Pack" --path "/path/to/music/Various Artists"

    # Batch consolidate all detected albums
    python consolidate_multidisc.py --batch "/path/to/music/Various Artists"
"""

import os
import sys
import json
import shutil
import argparse
import re
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.id3 import ID3, TPOS
from mutagen.easyid3 import EasyID3
from collections import defaultdict

def identify_multidisc_sets(artist_path):
    """
    Scan directory for multi-disc album patterns.

    Patterns detected:
    - "Album Name Disc 1" + "Album Name Disc 2"
    - "Album Name CD1" + "Album Name CD2"
    - "Album Name [Disc 1]" + "Album Name [Disc 2]"
    - "Album Vol. 1" + "Album Vol. 2"

    Returns: dict of {base_name: [{'path': disc_path, 'disc_num': N, 'tracks': count}, ...]}
    """
    print(f"Scanning for multi-disc albums in: {artist_path}")

    if not os.path.exists(artist_path):
        print(f"Error: Path does not exist: {artist_path}")
        return {}

    # Get all subdirectories
    try:
        all_folders = [d for d in os.listdir(artist_path)
                      if os.path.isdir(os.path.join(artist_path, d))]
    except Exception as e:
        print(f"Error reading directory: {e}")
        return {}

    # Patterns to detect disc notation
    disc_patterns = [
        r'(.+?)\s+Disc\s+(\d+)$',       # "Album Disc 1"
        r'(.+?)\s+Disk\s+(\d+)$',       # "Album Disk 1"
        r'(.+?)\s+CD\s*(\d+)$',         # "Album CD1" or "Album CD 1"
        r'(.+?)\s+\[Disc\s+(\d+)\]$',   # "Album [Disc 1]"
        r'(.+?)\s+Vol\.\s+(\d+)$',      # "Album Vol. 1"
        r'(.+?)\s+(\d+)$',              # "Album 2" (numbered volumes, less specific)
    ]

    # Map: base album name → list of disc folders
    album_groups = defaultdict(list)

    for folder in all_folders:
        matched = False
        for pattern in disc_patterns:
            match = re.match(pattern, folder, re.IGNORECASE)
            if match:
                base_name = match.group(1).strip()
                disc_num = int(match.group(2))
                folder_path = os.path.join(artist_path, folder)

                # Count tracks in this disc folder
                try:
                    tracks = [f for f in os.listdir(folder_path)
                             if f.lower().endswith(('.mp3', '.m4a', '.flac'))]
                    track_count = len(tracks)
                except:
                    track_count = 0

                album_groups[base_name].append({
                    'path': folder_path,
                    'folder_name': folder,
                    'disc_num': disc_num,
                    'tracks': track_count
                })
                matched = True
                break

    # Filter to only include albums with multiple discs
    multidisc_sets = {}
    orphaned_discs = {}

    for base_name, discs in album_groups.items():
        if len(discs) > 1:
            # Sort by disc number
            discs.sort(key=lambda x: x['disc_num'])
            multidisc_sets[base_name] = discs
            print(f"  Found complete set: {base_name} ({len(discs)} discs, {sum(d['tracks'] for d in discs)} total tracks)")
        elif len(discs) == 1:
            orphaned_discs[base_name] = discs[0]
            print(f"  Found orphaned disc: {base_name} (Disc {discs[0]['disc_num']}, {discs[0]['tracks']} tracks)")

    return {
        'complete_sets': multidisc_sets,
        'orphaned_discs': orphaned_discs
    }

def set_disc_metadata(filepath, disc_number, total_discs):
    """
    Set disc metadata field in audio file.

    Args:
        filepath: Path to audio file
        disc_number: Current disc number (1, 2, etc.)
        total_discs: Total number of discs

    Format: "1/2", "2/2", etc.
    Preserves existing track numbers.
    """
    try:
        if filepath.lower().endswith('.mp3'):
            # MP3 with ID3 tags
            audio = MP3(filepath, ID3=ID3)

            # Set TPOS (Disc position) frame
            disc_value = f"{disc_number}/{total_discs}"
            audio.tags.add(TPOS(encoding=3, text=disc_value))
            audio.save()
            return True

        elif filepath.lower().endswith('.m4a'):
            # M4A with iTunes-style tags
            audio = MP4(filepath)
            # Set disk number (tuple: current, total)
            audio.tags['disk'] = [(disc_number, total_discs)]
            audio.save()
            return True

        else:
            print(f"  Warning: Unsupported format for disc metadata: {filepath}")
            return False

    except Exception as e:
        print(f"  Error setting disc metadata for {filepath}: {e}")
        return False

def consolidate_discs(base_name, disc_list, artist_path, dry_run=False):
    """
    Merge multiple disc folders into single folder.

    Steps:
    1. Create target folder (base album name)
    2. Copy all tracks from each disc
    3. Set discnumber metadata field for each track
    4. Verify all tracks copied successfully
    5. If verification passes, delete source disc folders

    Args:
        base_name: Album name without disc notation
        disc_list: List of disc info dicts
        artist_path: Parent directory path
        dry_run: If True, only show what would be done

    Returns: Success boolean
    """
    target_folder = os.path.join(artist_path, base_name)
    total_discs = len(disc_list)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Consolidating: {base_name}")
    print(f"  Target: {target_folder}")
    print(f"  Discs: {total_discs}")

    if dry_run:
        for disc in disc_list:
            print(f"    Would merge: {disc['folder_name']} ({disc['tracks']} tracks)")
        return True

    # Check if target already exists
    if os.path.exists(target_folder):
        print(f"  Error: Target folder already exists: {target_folder}")
        return False

    # Create target folder
    try:
        os.makedirs(target_folder)
        print(f"  Created target folder")
    except Exception as e:
        print(f"  Error creating target folder: {e}")
        return False

    # Copy tracks from each disc
    total_tracks_copied = 0
    track_manifest = []  # Track what was copied for verification

    for disc in disc_list:
        disc_num = disc['disc_num']
        disc_path = disc['path']

        print(f"  Processing Disc {disc_num} ({disc['tracks']} tracks)...")

        try:
            # Get all audio files
            audio_files = [f for f in os.listdir(disc_path)
                          if f.lower().endswith(('.mp3', '.m4a', '.flac'))]

            for filename in audio_files:
                source_path = os.path.join(disc_path, filename)
                target_path = os.path.join(target_folder, filename)

                # Check for filename collision
                if os.path.exists(target_path):
                    # Rename with disc prefix
                    name, ext = os.path.splitext(filename)
                    target_path = os.path.join(target_folder, f"Disc{disc_num}_{filename}")
                    print(f"    Warning: Filename collision, renaming: {filename} → Disc{disc_num}_{filename}")

                # Copy file
                shutil.copy2(source_path, target_path)

                # Set disc metadata
                set_disc_metadata(target_path, disc_num, total_discs)

                track_manifest.append({
                    'source': source_path,
                    'target': target_path,
                    'disc': disc_num
                })
                total_tracks_copied += 1

            print(f"    Copied {len(audio_files)} tracks from Disc {disc_num}")

        except Exception as e:
            print(f"  Error processing Disc {disc_num}: {e}")
            return False

    # Verify all tracks copied
    print(f"  Verification: Copied {total_tracks_copied} tracks total")
    if total_tracks_copied != sum(d['tracks'] for d in disc_list):
        print(f"  Warning: Track count mismatch!")
        return False

    # Copy cover art if present (from first disc with cover)
    for disc in disc_list:
        cover_files = [f for f in os.listdir(disc['path'])
                      if f.lower() in ['folder.jpg', 'cover.jpg', 'album.jpg', 'front.jpg']]
        if cover_files:
            for cover in cover_files:
                source = os.path.join(disc['path'], cover)
                target = os.path.join(target_folder, cover)
                shutil.copy2(source, target)
                print(f"  Copied cover art: {cover}")
            break

    print(f"  [OK] Consolidation complete")
    print(f"  Original disc folders preserved (not deleted)")
    print(f"  Manually delete after verification:")
    for disc in disc_list:
        print(f"    - {disc['folder_name']}")

    return True

def verify_consolidation(target_path, expected_tracks):
    """
    Verify all tracks present and disc metadata set correctly.

    Args:
        target_path: Path to consolidated folder
        expected_tracks: Expected total track count

    Returns: Verification result dict
    """
    print(f"\nVerifying consolidated album: {target_path}")

    if not os.path.exists(target_path):
        return {'success': False, 'error': 'Target folder does not exist'}

    try:
        # Count audio files
        audio_files = [f for f in os.listdir(target_path)
                      if f.lower().endswith(('.mp3', '.m4a', '.flac'))]
        actual_tracks = len(audio_files)

        print(f"  Tracks found: {actual_tracks} (expected: {expected_tracks})")

        if actual_tracks != expected_tracks:
            return {'success': False, 'error': f'Track count mismatch: {actual_tracks} != {expected_tracks}'}

        # Check disc metadata on sample tracks
        disc_metadata_count = 0
        for filename in audio_files[:5]:  # Check first 5 tracks
            filepath = os.path.join(target_path, filename)
            try:
                if filepath.lower().endswith('.mp3'):
                    audio = MP3(filepath, ID3=ID3)
                    if 'TPOS' in audio.tags:
                        disc_metadata_count += 1
                elif filepath.lower().endswith('.m4a'):
                    audio = MP4(filepath)
                    if 'disk' in audio.tags:
                        disc_metadata_count += 1
            except:
                pass

        print(f"  Tracks with disc metadata: {disc_metadata_count}/{min(5, actual_tracks)} sampled")

        return {
            'success': True,
            'tracks': actual_tracks,
            'disc_metadata_present': disc_metadata_count > 0
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

def save_analysis_report(analysis, output_path):
    """Save multi-disc analysis to JSON file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"\nAnalysis report saved: {output_path}")
        return True
    except Exception as e:
        print(f"Error saving report: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Multi-Disc Album Consolidation Utility')
    parser.add_argument('--scan', metavar='PATH', help='Scan directory for multi-disc albums')
    parser.add_argument('--consolidate', metavar='ALBUM', help='Consolidate specific album by name')
    parser.add_argument('--path', metavar='PATH', help='Path to artist directory (used with --consolidate)')
    parser.add_argument('--batch', metavar='PATH', help='Batch consolidate all detected albums in directory')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without making them')
    parser.add_argument('--output-report', metavar='FILE', default='D:/music cleanup/outputs/multidisc_analysis.json',
                       help='Output path for analysis report')

    args = parser.parse_args()

    if args.scan:
        # Scan for multi-disc albums
        analysis = identify_multidisc_sets(args.scan)

        # Print summary
        complete = len(analysis.get('complete_sets', {}))
        orphaned = len(analysis.get('orphaned_discs', {}))
        print(f"\n=== SUMMARY ===")
        print(f"Complete multi-disc sets: {complete}")
        print(f"Orphaned discs: {orphaned}")

        # Save report
        save_analysis_report(analysis, args.output_report)

    elif args.consolidate and args.path:
        # Consolidate specific album
        analysis = identify_multidisc_sets(args.path)
        complete_sets = analysis.get('complete_sets', {})

        if args.consolidate in complete_sets:
            disc_list = complete_sets[args.consolidate]
            success = consolidate_discs(args.consolidate, disc_list, args.path, args.dry_run)
            if success:
                print("\n[SUCCESS] Consolidation successful")
            else:
                print("\n[FAILED] Consolidation failed")
        else:
            print(f"Error: Album not found or not a complete multi-disc set: {args.consolidate}")
            print(f"Available albums:")
            for album_name in complete_sets.keys():
                print(f"  - {album_name}")

    elif args.batch:
        # Batch consolidate all detected albums
        analysis = identify_multidisc_sets(args.batch)
        complete_sets = analysis.get('complete_sets', {})

        if not complete_sets:
            print("No complete multi-disc sets found")
            return

        print(f"\n=== BATCH CONSOLIDATION ===")
        print(f"Found {len(complete_sets)} complete multi-disc sets")

        if args.dry_run:
            print("\n[DRY RUN MODE - No changes will be made]")

        success_count = 0
        for album_name, disc_list in complete_sets.items():
            if consolidate_discs(album_name, disc_list, args.batch, args.dry_run):
                success_count += 1

        print(f"\n=== BATCH COMPLETE ===")
        print(f"Successfully consolidated: {success_count}/{len(complete_sets)} albums")

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
