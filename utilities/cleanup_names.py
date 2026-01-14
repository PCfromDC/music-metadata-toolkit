#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Album and Filename Cleanup Utility

Purpose: Clean up album and file names by removing extra characters, fixing truncation,
and standardizing separators.

Usage:
    # Scan for issues (dry-run preview)
    python cleanup_names.py --scan "/path/to/music/Various Artists" --dry-run

    # Clean specific album
    python cleanup_names.py --clean "Album Name" --path "/path/to/music/Various Artists"

    # Batch clean all albums
    python cleanup_names.py --batch "/path/to/music/Various Artists"
"""

import os
import sys
import json
import argparse
import re
import urllib.request
import urllib.parse
import time
from collections import defaultdict

# Cache for MusicBrainz lookups to avoid repeated API calls
_musicbrainz_cache = {}

def clean_album_name(name):
    """
    Clean album folder name by applying standardization rules.

    Rules:
    1. Remove/replace underscores with proper separators
    2. Replace brackets with parentheses (except [Disc N])
    3. Standardize separators
    4. Fix spacing issues

    Args:
        name: Original album folder name

    Returns:
        Cleaned album name
    """
    original = name
    cleaned = name

    # Preserve disc notation temporarily
    disc_notation = None
    disc_patterns = [
        r'\s*\[Disc\s+(\d+)\]$',
        r'\s*Disc\s+(\d+)$',
        r'\s*Disk\s+(\d+)$',
    ]

    for pattern in disc_patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            disc_notation = f" [Disc {match.group(1)}]"
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
            break

    # Replace underscores with proper separators
    # Pattern 1: "Album_ Subtitle" → "Album: Subtitle"
    cleaned = re.sub(r'_\s+', ': ', cleaned)

    # Pattern 2: "Album_Year" → "Album (Year)" if followed by 4-digit year
    cleaned = re.sub(r'_(\d{4})', r' (\1)', cleaned)

    # Pattern 3: Any remaining underscores → space or hyphen
    cleaned = re.sub(r'_', ' ', cleaned)

    # Replace square brackets with parentheses (except disc notation which we removed)
    # Pattern: [Genre], [Country], [Edition] → (Genre), (Country), (Edition)
    cleaned = re.sub(r'\[([^\]]+)\]', r'(\1)', cleaned)

    # Standardize separators
    # Fix multiple spaces
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)

    # Fix spacing around colons
    cleaned = re.sub(r'\s*:\s*', ': ', cleaned)

    # Fix spacing around hyphens (but not in ranges like "2000-2005")
    cleaned = re.sub(r'(?<!\d)\s*-\s*(?!\d)', ' - ', cleaned)

    # Fix spacing around commas
    cleaned = re.sub(r'\s*,\s*', ', ', cleaned)

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    # Restore disc notation if present
    if disc_notation:
        cleaned += disc_notation

    return cleaned

def detect_truncation(name):
    """
    Detect if an album name appears to be truncated.

    Signs of truncation:
    - Ends with incomplete word (e.g., "Wo" instead of "World")
    - Ends with ellipsis (...)
    - Ends with punctuation mid-sentence

    Returns:
        Boolean indicating if name appears truncated
    """
    # Remove disc notation for analysis
    test_name = re.sub(r'\s*\[Disc\s+\d+\]$', '', name, flags=re.IGNORECASE)
    test_name = re.sub(r'\s*Disc\s+\d+$', '', test_name, flags=re.IGNORECASE)

    # Check for ellipsis
    if test_name.endswith('...'):
        return True

    # Check for truncated word (ends with underscore or unusual pattern)
    if re.search(r'_\s*$', test_name):
        return True

    # Check for suspiciously short last word (< 3 chars, not a valid short word)
    words = test_name.split()
    if len(words) > 0:
        last_word = words[-1].strip('.,!?;:')
        # Short words that are valid endings
        valid_short = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'II', 'III', 'IV', 'UK', 'US', 'CD', 'EP', 'LP']
        if len(last_word) < 3 and last_word not in valid_short and not last_word.isdigit():
            return True

    return False

def scan_albums(artist_path, dry_run=True):
    """
    Scan directory for albums that need name cleanup.

    Returns:
        dict: {
            'needs_cleaning': [(old_name, new_name, reason), ...],
            'truncated': [(album_name, path), ...],
            'clean': [album_name, ...]
        }
    """
    print(f"Scanning albums in: {artist_path}")

    if not os.path.exists(artist_path):
        print(f"Error: Path does not exist: {artist_path}")
        return {}

    try:
        all_folders = [d for d in os.listdir(artist_path)
                      if os.path.isdir(os.path.join(artist_path, d))]
    except Exception as e:
        print(f"Error reading directory: {e}")
        return {}

    results = {
        'needs_cleaning': [],
        'truncated': [],
        'clean': []
    }

    for folder in all_folders:
        cleaned_name = clean_album_name(folder)

        if cleaned_name != folder:
            # Determine reason for cleaning
            reasons = []
            if '_' in folder:
                reasons.append('underscores')
            if '[' in folder and 'Disc' not in folder:
                reasons.append('brackets')
            if '  ' in folder:
                reasons.append('spacing')

            reason = ', '.join(reasons)
            results['needs_cleaning'].append((folder, cleaned_name, reason))

        # Check for truncation
        if detect_truncation(folder):
            folder_path = os.path.join(artist_path, folder)
            results['truncated'].append((folder, folder_path))

        # Track clean albums
        if cleaned_name == folder and not detect_truncation(folder):
            results['clean'].append(folder)

    # Print summary
    print(f"\n=== SCAN SUMMARY ===")
    print(f"Albums needing cleanup: {len(results['needs_cleaning'])}")
    print(f"Albums with truncated names: {len(results['truncated'])}")
    print(f"Clean albums: {len(results['clean'])}")

    if results['needs_cleaning']:
        print(f"\n=== ALBUMS NEEDING CLEANUP ===")
        for old_name, new_name, reason in results['needs_cleaning'][:20]:  # Show first 20
            print(f"\n{old_name}")
            print(f"  -> {new_name}")
            print(f"  Reason: {reason}")

        if len(results['needs_cleaning']) > 20:
            print(f"\n... and {len(results['needs_cleaning']) - 20} more albums")

    if results['truncated']:
        print(f"\n=== TRUNCATED NAMES (Need Research) ===")
        for album_name, _ in results['truncated'][:10]:  # Show first 10
            print(f"  - {album_name}")

        if len(results['truncated']) > 10:
            print(f"  ... and {len(results['truncated']) - 10} more")

    return results

def rename_album_folder(old_path, new_name, dry_run=False):
    """
    Safely rename an album folder.

    Args:
        old_path: Full path to current folder
        new_name: New folder name (not full path)
        dry_run: If True, only show what would be done

    Returns:
        Boolean indicating success
    """
    parent_dir = os.path.dirname(old_path)
    old_name = os.path.basename(old_path)
    new_path = os.path.join(parent_dir, new_name)

    if old_path == new_path:
        print(f"  [SKIP] No change needed")
        return True

    print(f"  {old_name}")
    print(f"    -> {new_name}")

    if dry_run:
        print(f"    [DRY RUN] Would rename folder")
        return True

    # Check for conflicts
    if os.path.exists(new_path):
        print(f"    [ERROR] Target folder already exists: {new_name}")
        return False

    try:
        os.rename(old_path, new_path)
        print(f"    [OK] Renamed successfully")
        return True
    except Exception as e:
        print(f"    [ERROR] Rename failed: {e}")
        return False

def batch_cleanup(artist_path, dry_run=False):
    """
    Batch clean all albums in directory.

    Args:
        artist_path: Path to artist directory
        dry_run: If True, only preview changes
    """
    print(f"\n=== BATCH CLEANUP ===" + (" [DRY RUN]" if dry_run else ""))

    # Scan for albums needing cleanup
    results = scan_albums(artist_path, dry_run=True)

    if not results['needs_cleaning']:
        print("\nNo albums need cleanup!")
        return

    print(f"\nProcessing {len(results['needs_cleaning'])} albums...")

    success_count = 0
    error_count = 0

    for old_name, new_name, reason in results['needs_cleaning']:
        old_path = os.path.join(artist_path, old_name)

        if rename_album_folder(old_path, new_name, dry_run=dry_run):
            success_count += 1
        else:
            error_count += 1

    print(f"\n=== BATCH COMPLETE ===")
    print(f"Successfully renamed: {success_count}/{len(results['needs_cleaning'])}")
    if error_count > 0:
        print(f"Errors: {error_count}")

def save_cleanup_report(results, output_path):
    """Save cleanup analysis to JSON file."""
    try:
        # Convert results to serializable format
        report = {
            'needs_cleaning': [
                {'old_name': old, 'new_name': new, 'reason': reason}
                for old, new, reason in results['needs_cleaning']
            ],
            'truncated': [
                {'name': name, 'path': path}
                for name, path in results['truncated']
            ],
            'clean': results['clean']
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nCleanup report saved: {output_path}")
        return True
    except Exception as e:
        print(f"Error saving report: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Album and Filename Cleanup Utility')
    parser.add_argument('--scan', metavar='PATH', help='Scan directory for albums needing cleanup')
    parser.add_argument('--clean', metavar='ALBUM', help='Clean specific album by name')
    parser.add_argument('--path', metavar='PATH', help='Path to artist directory (used with --clean)')
    parser.add_argument('--batch', metavar='PATH', help='Batch clean all albums in directory')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without making them')
    parser.add_argument('--output-report', metavar='FILE', default='D:/music cleanup/outputs/name_cleanup_report.json',
                       help='Output path for cleanup report')

    args = parser.parse_args()

    if args.scan:
        # Scan for albums needing cleanup
        results = scan_albums(args.scan, dry_run=True)

        # Save report
        save_cleanup_report(results, args.output_report)

    elif args.clean and args.path:
        # Clean specific album
        old_path = os.path.join(args.path, args.clean)

        if not os.path.exists(old_path):
            print(f"Error: Album not found: {args.clean}")
            return

        new_name = clean_album_name(args.clean)
        rename_album_folder(old_path, new_name, dry_run=args.dry_run)

    elif args.batch:
        # Batch clean all albums
        batch_cleanup(args.batch, dry_run=args.dry_run)

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
