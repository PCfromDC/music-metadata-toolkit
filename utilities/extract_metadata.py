import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.id3 import ID3
import os
import json
import csv
import sys

def get_cover_art_info(filepath):
    """Extract cover art information from audio file"""
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.mp3':
            audio = MP3(filepath)
            if audio.tags:
                for tag in audio.tags.values():
                    if hasattr(tag, 'mime') and hasattr(tag, 'data'):
                        return f"embedded:{tag.mime}:{len(tag.data)}bytes"
        elif ext == '.flac':
            audio = FLAC(filepath)
            if audio.pictures:
                pic = audio.pictures[0]
                return f"embedded:{pic.mime}:{len(pic.data)}bytes"
        elif ext in ['.m4a', '.mp4']:
            audio = MP4(filepath)
            if 'covr' in audio.tags:
                return f"embedded:image:{len(audio.tags['covr'][0])}bytes"
    except:
        pass

    # Check for cover art files in same directory
    dirname = os.path.dirname(filepath)
    cover_names = ['cover.jpg', 'cover.png', 'folder.jpg', 'folder.png', 'album.jpg', 'album.png', 'front.jpg', 'front.png']
    for cover in cover_names:
        cover_path = os.path.join(dirname, cover)
        if os.path.exists(cover_path):
            return cover_path
    return None

def extract_metadata(filepath):
    """Extract metadata from an audio file"""
    result = {
        'filepath': filepath,
        'artist': None,
        'album': None,
        'title': None,
        'tracknumber': None,
        'date': None,
        'genre': None,
        'cover_art': None,
        'missing_fields': []
    }

    try:
        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.mp3':
            try:
                audio = MP3(filepath, ID3=EasyID3)
                result['artist'] = audio.get('artist', [None])[0]
                result['album'] = audio.get('album', [None])[0]
                result['title'] = audio.get('title', [None])[0]
                result['tracknumber'] = audio.get('tracknumber', [None])[0]
                result['date'] = audio.get('date', [None])[0]
                result['genre'] = audio.get('genre', [None])[0]
            except:
                audio = mutagen.File(filepath, easy=True)
                if audio:
                    result['artist'] = audio.get('artist', [None])[0]
                    result['album'] = audio.get('album', [None])[0]
                    result['title'] = audio.get('title', [None])[0]
                    result['tracknumber'] = audio.get('tracknumber', [None])[0]
        elif ext == '.flac':
            audio = FLAC(filepath)
            result['artist'] = audio.get('artist', [None])[0]
            result['album'] = audio.get('album', [None])[0]
            result['title'] = audio.get('title', [None])[0]
            result['tracknumber'] = audio.get('tracknumber', [None])[0]
            result['date'] = audio.get('date', [None])[0]
            result['genre'] = audio.get('genre', [None])[0]
        elif ext in ['.m4a', '.mp4']:
            audio = MP4(filepath)
            result['artist'] = audio.tags.get('\xa9ART', [None])[0] if audio.tags else None
            result['album'] = audio.tags.get('\xa9alb', [None])[0] if audio.tags else None
            result['title'] = audio.tags.get('\xa9nam', [None])[0] if audio.tags else None
            trkn = audio.tags.get('trkn', [(None, None)])[0] if audio.tags else (None, None)
            result['tracknumber'] = str(trkn[0]) if trkn[0] else None
            result['date'] = audio.tags.get('\xa9day', [None])[0] if audio.tags else None
            result['genre'] = audio.tags.get('\xa9gen', [None])[0] if audio.tags else None
        else:
            # Generic fallback
            audio = mutagen.File(filepath, easy=True)
            if audio:
                result['artist'] = audio.get('artist', [None])[0]
                result['album'] = audio.get('album', [None])[0]
                result['title'] = audio.get('title', [None])[0]
                result['tracknumber'] = audio.get('tracknumber', [None])[0]

        result['cover_art'] = get_cover_art_info(filepath)

        # Track missing fields
        for field in ['artist', 'album', 'title', 'tracknumber']:
            if not result[field]:
                result['missing_fields'].append(field)

    except Exception as e:
        result['error'] = str(e)
        result['missing_fields'].append('error_reading_file')

    return result

def scan_directory(base_path):
    """Scan directory for audio files and extract metadata"""
    audio_extensions = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wav', '.wma'}
    results = []

    for root, dirs, files in os.walk(base_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in audio_extensions:
                filepath = os.path.join(root, file)
                print(f"Processing: {filepath}")
                metadata = extract_metadata(filepath)
                results.append(metadata)

    return results

def build_structured_json(results):
    """Build the structured JSON output format"""
    output = {}

    for r in results:
        artist = r.get('artist') or 'Unknown Artist'
        album = r.get('album') or 'Unknown Album'

        if artist not in output:
            output[artist] = {}

        if album not in output[artist]:
            output[artist][album] = {
                'CoverArt': None,
                'Date': None,
                'Genre': None,
                'Tracks': []
            }

        # Set cover art if not already set
        if r.get('cover_art') and not output[artist][album]['CoverArt']:
            output[artist][album]['CoverArt'] = r['cover_art']

        # Set date if not already set
        if r.get('date') and not output[artist][album]['Date']:
            output[artist][album]['Date'] = r['date']

        # Set genre if not already set
        if r.get('genre') and not output[artist][album]['Genre']:
            output[artist][album]['Genre'] = r['genre']

        # Parse track number
        track_num = r.get('tracknumber')
        if track_num:
            # Handle "1/11" format
            if '/' in str(track_num):
                track_num = str(track_num).split('/')[0]
            try:
                track_num = int(track_num)
            except:
                track_num = None

        output[artist][album]['Tracks'].append({
            'TrackNumber': track_num,
            'Title': r.get('title') or os.path.basename(r['filepath']),
            'FilePath': r['filepath'],
            'MissingFields': r.get('missing_fields', [])
        })

    # Sort tracks by track number
    for artist in output:
        for album in output[artist]:
            output[artist][album]['Tracks'].sort(
                key=lambda x: (x['TrackNumber'] or 999, x['Title'])
            )

    return output

def write_csv(results, output_path):
    """Write results to CSV file"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['FilePath', 'Artist', 'Album', 'CoverArtPath', 'TrackNumber', 'Title', 'Date', 'Genre', 'MissingOrUncertainFields'])

        for r in results:
            writer.writerow([
                r.get('filepath', ''),
                r.get('artist', ''),
                r.get('album', ''),
                r.get('cover_art', ''),
                r.get('tracknumber', ''),
                r.get('title', ''),
                r.get('date', ''),
                r.get('genre', ''),
                ';'.join(r.get('missing_fields', []))
            ])

if __name__ == "__main__":
    base_path = "/path/to/music/U2"
    output_dir = "D:/music cleanup/outputs"

    if len(sys.argv) > 1:
        # Scan specific album
        album_path = os.path.join(base_path, sys.argv[1])
        results = scan_directory(album_path)
    else:
        # Scan all
        results = scan_directory(base_path)

    # Print summary
    print(f"\n\nTotal files processed: {len(results)}")

    # Build structured output
    structured = build_structured_json(results)

    # Write JSON file
    json_path = os.path.join(output_dir, "u2_library_audit.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(structured, f, indent=2, ensure_ascii=False)
    print(f"JSON output written to: {json_path}")

    # Write CSV file
    csv_path = os.path.join(output_dir, "u2_library_audit.csv")
    write_csv(results, csv_path)
    print(f"CSV output written to: {csv_path}")

    # Print albums summary
    print("\n--- ALBUMS SUMMARY ---")
    for artist in structured:
        print(f"\n{artist}:")
        for album in sorted(structured[artist].keys()):
            album_data = structured[artist][album]
            track_count = len(album_data['Tracks'])
            has_cover = "Yes" if album_data['CoverArt'] else "No"
            missing_count = sum(1 for t in album_data['Tracks'] if t['MissingFields'])
            date = album_data.get('Date', 'Unknown')
            print(f"  {album} ({date}) - {track_count} tracks, Cover: {has_cover}, Issues: {missing_count}")
