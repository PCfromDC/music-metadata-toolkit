import csv
from collections import defaultdict

print('=== ALBUMS WITHOUT COVER ART ===\n')

files = [
    ('Various Artists', 'D:/music cleanup/outputs/various_artists_audit.csv'),
    ('Holiday', 'D:/music cleanup/outputs/various_artists_-_holiday_audit.csv'),
    ('Soundtracks', 'D:/music cleanup/outputs/various_artists_-_soundtracks_audit.csv')
]

total_no_cover = 0

for name, csv_file in files:
    albums = defaultdict(lambda: {'tracks': 0, 'no_cover': 0})

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            album = row['Album']
            albums[album]['tracks'] += 1
            if not row['CoverArtPath']:
                albums[album]['no_cover'] += 1

    no_cover_albums = [(alb, data) for alb, data in albums.items() if data['no_cover'] == data['tracks']]
    total_no_cover += len(no_cover_albums)

    if no_cover_albums:
        print(f'{name}: {len(no_cover_albums)} albums without cover art')
        for album, data in sorted(no_cover_albums)[:10]:
            print(f'  - {album} ({data["tracks"]} tracks)')
        if len(no_cover_albums) > 10:
            print(f'  ... and {len(no_cover_albums) - 10} more')
        print()

print(f'TOTAL: {total_no_cover} albums need cover art across all collections')
