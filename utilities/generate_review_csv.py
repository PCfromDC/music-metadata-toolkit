#!/usr/bin/env python3
"""Generate CSV file for review queue with approve/reject columns."""

import json
import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def main():
    # Load queue (format: {album_id: {path, status, metadata, ...}})
    queue_path = Path('D:/music cleanup/state/queue.json')
    with open(queue_path, 'r', encoding='utf-8') as f:
        queue = json.load(f)

    # Filter to needs_review items
    review_items = [
        {'id': album_id, **data}
        for album_id, data in queue.items()
        if data.get('status') == 'needs_review'
    ]

    print(f'Found {len(review_items)} items needing review')

    # Create CSV
    csv_path = Path('D:/music cleanup/outputs/review_queue.csv')
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'album_id',
            'local_folder',
            'match_title',
            'match_artist',
            'confidence',
            'source',
            'has_corrections',
            'not_found',
            'APPROVE',
            'REJECT',
            'NOTES'
        ])

        # Data rows - sorted by confidence descending
        sorted_items = sorted(review_items, key=lambda x: x.get('metadata', {}).get('confidence', 0), reverse=True)

        for item in sorted_items:
            album_id = item.get('id', '')[:12]  # Short ID
            path = item.get('path', '')
            local_folder = Path(path).name

            metadata = item.get('metadata', {})
            validation = metadata.get('validation', {})

            # Extract match data from validation
            match_title = validation.get('match_title', '')
            match_artist = validation.get('match_artist', '')

            confidence = metadata.get('confidence', validation.get('confidence', 0))
            source = validation.get('match_source', '')

            corrections = validation.get('corrections', [])
            has_corrections = 'Yes' if corrections else 'No'

            not_found = 'Yes' if not validation.get('matched', True) else 'No'

            # Format confidence
            if isinstance(confidence, float):
                conf_str = f'{confidence:.0%}'
            else:
                conf_str = str(confidence)

            writer.writerow([
                album_id,
                local_folder,
                match_title,
                match_artist,
                conf_str,
                source,
                has_corrections,
                not_found,
                '',  # APPROVE column - user fills with 'X' or 'Y'
                '',  # REJECT column - user fills with 'X' or 'Y'
                ''   # NOTES column - user fills
            ])

    print(f'Created: {csv_path}')
    print(f'Total rows: {len(review_items)}')
    print()
    print('Instructions:')
    print('1. Open the CSV in Excel or a text editor')
    print('2. For each row, mark APPROVE or REJECT column with "X"')
    print('3. Save the file')
    print('4. Run: python utilities/process_review_csv.py')

if __name__ == '__main__':
    main()
