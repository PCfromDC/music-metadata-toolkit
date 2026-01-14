#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apply corrections from validation report

Purpose: Rename albums and apply fixes based on MusicBrainz validation data.
Only applies "safe" corrections (formatting fixes, not completely different titles).
"""

import os
import sys
import json
import re

def is_safe_correction(local_title, correct_title):
    """
    Determine if title correction is "safe" to apply automatically.

    Safe corrections:
    - Underscore to colon: "Album_ Subtitle" -> "Album: Subtitle"
    - Bracket changes: "[Edition]" -> "(Edition)"
    - Minor punctuation/spacing
    - Vol. notation additions

    Unsafe corrections (require manual review):
    - Completely different album name
    - Major word differences

    Returns: (is_safe: bool, reason: str)
    """
    # Normalize for comparison
    local_norm = local_title.lower().strip()
    correct_norm = correct_title.lower().strip()

    # Remove common variations for comparison
    local_clean = re.sub(r'[_\-:\[\]\(\),.]', '', local_norm)
    correct_clean = re.sub(r'[_\-:\[\]\(\),.]', '', correct_norm)

    # Remove spaces
    local_clean = local_clean.replace(' ', '')
    correct_clean = correct_clean.replace(' ', '')

    # Check similarity (same words, just different formatting)
    if local_clean == correct_clean:
        return (True, "Formatting only")

    # Check if it's just adding volume info
    if local_clean in correct_clean and 'vol' in correct_clean:
        return (True, "Volume notation added")

    # Check for disc notation removal
    local_no_disc = re.sub(r'disc\s*\d+', '', local_clean)
    correct_no_disc = re.sub(r'disc\s*\d+', '', correct_clean)
    if local_no_disc == correct_no_disc:
        return (True, "Disc notation difference")

    # Calculate word overlap
    local_words = set(local_norm.split())
    correct_words = set(correct_norm.split())

    if not correct_words:
        return (False, "Empty correct title")

    overlap = len(local_words & correct_words) / len(correct_words)

    if overlap >= 0.7:  # 70% of words match
        return (True, f"High word overlap ({overlap:.0%})")

    return (False, f"Different titles (only {overlap:.0%} overlap)")

def apply_title_corrections(validation_file, artist_path, dry_run=True):
    """
    Apply title corrections from validation report.

    Args:
        validation_file: Path to validation JSON report
        artist_path: Path to Various Artists directory
        dry_run: If True, only show what would be done
    """
    print(f"Reading validation report: {validation_file}")

    with open(validation_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    albums = data['albums']

    # Filter to only title mismatches
    mismatches = [a for a in albums if a.get('title_match') == False]

    print(f"\nFound {len(mismatches)} albums with title mismatches")
    print(f"Analyzing for safe corrections...\n")

    safe_corrections = []
    manual_review = []

    for album in mismatches:
        local = album['title_local']
        correct = album['title_correct']

        is_safe, reason = is_safe_correction(local, correct)

        # Only apply "Formatting only" corrections automatically
        if is_safe and reason == "Formatting only":
            safe_corrections.append({
                'old_name': local,
                'new_name': correct,
                'reason': reason,
                'musicbrainz_id': album.get('musicbrainz_id')
            })
        else:
            manual_review.append({
                'old_name': local,
                'new_name': correct,
                'reason': reason,
                'musicbrainz_id': album.get('musicbrainz_id')
            })

    print(f"Safe corrections: {len(safe_corrections)}")
    print(f"Manual review needed: {len(manual_review)}")

    if dry_run:
        print(f"\n{'='*80}")
        print(f"[DRY RUN] Showing first 20 safe corrections:")
        print(f"{'='*80}\n")

        for i, item in enumerate(safe_corrections[:20], 1):
            print(f"{i}. {item['old_name']}")
            print(f"   -> {item['new_name']}")
            print(f"   Reason: {item['reason']}")
            print()

        if len(safe_corrections) > 20:
            print(f"... and {len(safe_corrections) - 20} more\n")
    else:
        print(f"\n{'='*80}")
        print(f"Applying {len(safe_corrections)} corrections...")
        print(f"{'='*80}\n")

        success_count = 0
        error_count = 0

        for i, item in enumerate(safe_corrections, 1):
            old_path = os.path.join(artist_path, item['old_name'])
            new_path = os.path.join(artist_path, item['new_name'])

            print(f"[{i}/{len(safe_corrections)}] {item['old_name']}")

            if not os.path.exists(old_path):
                print(f"  [ERROR] Folder not found")
                error_count += 1
                continue

            if os.path.exists(new_path):
                print(f"  [ERROR] Target already exists: {item['new_name']}")
                error_count += 1
                continue

            try:
                os.rename(old_path, new_path)
                print(f"  [OK] Renamed")
                success_count += 1
            except Exception as e:
                print(f"  [ERROR] {e}")
                error_count += 1

        print(f"\n{'='*80}")
        print(f"Corrections applied: {success_count}/{len(safe_corrections)}")
        if error_count > 0:
            print(f"Errors: {error_count}")
        print(f"{'='*80}\n")

    # Save manual review list
    manual_review_file = "D:/music cleanup/outputs/manual_review_needed.json"
    with open(manual_review_file, 'w', encoding='utf-8') as f:
        json.dump({
            'count': len(manual_review),
            'albums': manual_review
        }, f, indent=2, ensure_ascii=False)

    print(f"\nManual review list saved: {manual_review_file}")
    print(f"{len(manual_review)} albums need manual review (major title differences)")

    return {
        'safe_corrections': safe_corrections,
        'manual_review': manual_review,
        'success_count': 0 if dry_run else success_count,
        'error_count': 0 if dry_run else error_count
    }

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Apply corrections from validation report')
    parser.add_argument('--validation',
                       default='D:/music cleanup/outputs/various_artists_validation.json',
                       help='Path to validation JSON report')
    parser.add_argument('--path',
                       default='/path/to/music/Various Artists',
                       help='Path to Various Artists directory')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without making them')
    parser.add_argument('--apply', action='store_true',
                       help='Apply the corrections (use with caution)')

    args = parser.parse_args()

    dry_run = not args.apply

    if dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")
    else:
        print("\n*** APPLYING CORRECTIONS ***\n")
        response = input("Are you sure you want to apply corrections? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return

    apply_title_corrections(args.validation, args.path, dry_run=dry_run)

if __name__ == '__main__':
    main()
