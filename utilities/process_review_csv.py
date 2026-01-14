#!/usr/bin/env python3
"""Process review decisions from CSV file and update queue."""

import json
import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def main():
    csv_path = Path('D:/music cleanup/outputs/review_queue.csv')
    queue_path = Path('D:/music cleanup/state/queue.json')

    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        print("Run 'python utilities/generate_review_csv.py' first")
        sys.exit(1)

    # Load queue
    with open(queue_path, 'r', encoding='utf-8') as f:
        queue = json.load(f)

    # Read CSV decisions
    approved = []
    rejected = []
    unchanged = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            album_id = row.get('album_id', '').strip()
            approve = row.get('APPROVE', '').strip().upper()
            reject = row.get('REJECT', '').strip().upper()

            # Find matching album in queue (album_id is truncated, need to match prefix)
            full_id = None
            for qid in queue.keys():
                if qid.startswith(album_id):
                    full_id = qid
                    break

            if not full_id:
                print(f"Warning: Album not found in queue: {album_id}")
                continue

            if approve in ('X', 'Y', 'YES', '1', 'TRUE'):
                queue[full_id]['status'] = 'approved'
                approved.append(row.get('local_folder', album_id))
            elif reject in ('X', 'Y', 'YES', '1', 'TRUE'):
                queue[full_id]['status'] = 'rejected'
                rejected.append(row.get('local_folder', album_id))
            else:
                unchanged.append(row.get('local_folder', album_id))

    # Save updated queue
    with open(queue_path, 'w', encoding='utf-8') as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

    # Summary
    print("=" * 60)
    print("REVIEW PROCESSING COMPLETE")
    print("=" * 60)
    print(f"\nApproved: {len(approved)}")
    print(f"Rejected: {len(rejected)}")
    print(f"Unchanged: {len(unchanged)}")

    if approved:
        print("\n--- APPROVED FOR FIXING ---")
        for name in approved[:10]:
            print(f"  + {name}")
        if len(approved) > 10:
            print(f"  ... and {len(approved) - 10} more")

    if rejected:
        print("\n--- REJECTED (will skip) ---")
        for name in rejected[:10]:
            print(f"  - {name}")
        if len(rejected) > 10:
            print(f"  ... and {len(rejected) - 10} more")

    print("\n" + "=" * 60)
    print("Next steps:")
    print("  1. Run validation on remaining 'scanned' items if needed")
    print("  2. Run 'python -c \"from orchestrator import MusicLibraryOrchestrator; o = MusicLibraryOrchestrator(); o.init('/path/to/music'); print(o.fix(dry_run=True))\"' to preview fixes")
    print("  3. Run without dry_run=True to apply fixes")
    print("=" * 60)

if __name__ == '__main__':
    main()
