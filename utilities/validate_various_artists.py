#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Various Artists Album Validation Utility

Purpose: Validate each album in Various Artists folder against MusicBrainz database.
Compares local metadata with authoritative data to identify corrections needed.

Usage:
    # Validate all albums and generate report
    python validate_various_artists.py "/path/to/music/Various Artists"

    # Validate specific album
    python validate_various_artists.py "/path/to/music/Various Artists" --album "Album Name"
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import time
from collections import defaultdict
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.easyid3 import EasyID3

# MusicBrainz API rate limiting
MUSICBRAINZ_RATE_LIMIT = 1.5  # seconds between requests

def get_local_album_metadata(album_path):
    """
    Extract metadata from local album folder.

    Returns:
        dict: {
            'folder_name': str,
            'track_count': int,
            'tracks': [{'filename': str, 'title': str, 'artist': str, 'track_num': int}, ...],
            'has_cover': bool,
            'album_title': str (from first track's metadata)
        }
    """
    result = {
        'folder_name': os.path.basename(album_path),
        'track_count': 0,
        'tracks': [],
        'has_cover': False,
        'album_title': None
    }

    if not os.path.exists(album_path):
        return result

    # Check for cover art files
    cover_files = ['folder.jpg', 'cover.jpg', 'album.jpg', 'front.jpg']
    for cover in cover_files:
        if os.path.exists(os.path.join(album_path, cover)):
            result['has_cover'] = True
            break

    # Get all audio files
    try:
        files = os.listdir(album_path)
        audio_files = [f for f in files if f.lower().endswith(('.mp3', '.m4a', '.flac'))]
        audio_files.sort()

        result['track_count'] = len(audio_files)

        for filename in audio_files:
            filepath = os.path.join(album_path, filename)
            track_info = {
                'filename': filename,
                'title': None,
                'artist': None,
                'track_num': None,
                'album': None,
                'has_embedded_cover': False
            }

            try:
                if filepath.lower().endswith('.mp3'):
                    audio = MP3(filepath, ID3=EasyID3)
                    track_info['title'] = audio.get('title', [None])[0]
                    track_info['artist'] = audio.get('artist', [None])[0]
                    track_info['album'] = audio.get('album', [None])[0]
                    track_num = audio.get('tracknumber', [None])[0]
                    if track_num:
                        # Handle "1/12" format
                        track_info['track_num'] = int(track_num.split('/')[0])

                    # Check for embedded cover
                    audio_full = MP3(filepath, ID3=ID3)
                    if audio_full.tags and any(key.startswith('APIC') for key in audio_full.tags.keys()):
                        track_info['has_embedded_cover'] = True

                elif filepath.lower().endswith('.m4a'):
                    audio = MP4(filepath)
                    track_info['title'] = audio.get('\xa9nam', [None])[0]
                    track_info['artist'] = audio.get('\xa9ART', [None])[0]
                    track_info['album'] = audio.get('\xa9alb', [None])[0]
                    track_num = audio.get('trkn', [None])[0]
                    if track_num:
                        track_info['track_num'] = track_num[0]

                    # Check for embedded cover
                    if 'covr' in audio.tags:
                        track_info['has_embedded_cover'] = True

                elif filepath.lower().endswith('.flac'):
                    audio = FLAC(filepath)
                    track_info['title'] = audio.get('title', [None])[0]
                    track_info['artist'] = audio.get('artist', [None])[0]
                    track_info['album'] = audio.get('album', [None])[0]
                    track_num = audio.get('tracknumber', [None])[0]
                    if track_num:
                        track_info['track_num'] = int(track_num.split('/')[0])

                    # Check for embedded cover
                    if audio.pictures:
                        track_info['has_embedded_cover'] = True

                # Use first track's album field as album title
                if result['album_title'] is None and track_info['album']:
                    result['album_title'] = track_info['album']

            except Exception as e:
                print(f"  Warning: Error reading {filename}: {e}")

            result['tracks'].append(track_info)

    except Exception as e:
        print(f"  Error reading album directory: {e}")

    return result

def search_musicbrainz(album_name, artist="Various Artists"):
    """
    Search MusicBrainz for album.

    Returns:
        dict: {
            'release_id': str,
            'title': str,
            'artist': str,
            'track_count': int,
            'tracks': [{'title': str, 'artist': str, 'position': int}, ...],
            'has_cover_art': bool
        } or None if not found
    """
    # Clean up album name for search
    search_name = album_name
    # Remove disc notation for search
    search_name = re.sub(r'\s*\[?Disc\s+\d+\]?$', '', search_name, flags=re.IGNORECASE)
    search_name = re.sub(r'\s*Disk\s+\d+$', '', search_name, flags=re.IGNORECASE)
    # Remove volume notation
    search_name = re.sub(r',\s*Vol\.\s*\d+$', '', search_name, flags=re.IGNORECASE)

    query = urllib.parse.quote(f'{search_name} AND artist:"{artist}"')
    url = f"https://musicbrainz.org/ws/2/release/?query={query}&fmt=json&limit=5"

    try:
        time.sleep(MUSICBRAINZ_RATE_LIMIT)
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())

            if not data.get('releases') or len(data['releases']) == 0:
                return None

            # Get the first (best match) release
            release = data['releases'][0]
            release_id = release['id']

            # Get detailed release info including tracks
            detail_url = f"https://musicbrainz.org/ws/2/release/{release_id}?inc=recordings+artist-credits&fmt=json"
            time.sleep(MUSICBRAINZ_RATE_LIMIT)

            with urllib.request.urlopen(detail_url, timeout=10) as detail_response:
                detail_data = json.loads(detail_response.read())

                result = {
                    'release_id': release_id,
                    'title': detail_data.get('title', ''),
                    'artist': release.get('artist-credit', [{}])[0].get('name', 'Various Artists'),
                    'track_count': detail_data.get('track-count', 0),
                    'tracks': [],
                    'has_cover_art': False  # Will check separately
                }

                # Extract track listing
                if 'media' in detail_data:
                    position = 1
                    for medium in detail_data['media']:
                        for track in medium.get('tracks', []):
                            track_info = {
                                'title': track.get('title', ''),
                                'artist': '',
                                'position': position
                            }

                            # Get track artist if different from album artist
                            if 'artist-credit' in track:
                                track_info['artist'] = track['artist-credit'][0].get('name', '')

                            result['tracks'].append(track_info)
                            position += 1

                # Check for cover art
                try:
                    cover_url = f"https://coverartarchive.org/release/{release_id}"
                    with urllib.request.urlopen(cover_url, timeout=5) as cover_response:
                        result['has_cover_art'] = True
                except:
                    result['has_cover_art'] = False

                return result

    except Exception as e:
        print(f"  MusicBrainz search error: {e}")
        return None

def compare_albums(local, musicbrainz):
    """
    Compare local album data with MusicBrainz data.

    Returns:
        dict: {
            'title_match': bool,
            'title_local': str,
            'title_correct': str,
            'track_count_match': bool,
            'track_count_local': int,
            'track_count_correct': int,
            'missing_tracks': [str, ...],
            'extra_tracks': [str, ...],
            'cover_status': 'ok' | 'missing_local' | 'available_online',
            'needs_attention': bool
        }
    """
    if musicbrainz is None:
        return {
            'title_match': None,
            'title_local': local['folder_name'],
            'title_correct': None,
            'track_count_match': None,
            'track_count_local': local['track_count'],
            'track_count_correct': None,
            'missing_tracks': [],
            'extra_tracks': [],
            'cover_status': 'unknown',
            'needs_attention': True,
            'error': 'Not found in MusicBrainz'
        }

    result = {
        'title_local': local['folder_name'],
        'title_correct': musicbrainz['title'],
        'track_count_local': local['track_count'],
        'track_count_correct': musicbrainz['track_count'],
        'missing_tracks': [],
        'extra_tracks': [],
        'musicbrainz_id': musicbrainz['release_id']
    }

    # Compare titles (normalized comparison)
    local_normalized = local['folder_name'].lower().strip()
    # Remove disc notation
    local_normalized = re.sub(r'\s*\[?disc\s+\d+\]?$', '', local_normalized)
    local_normalized = re.sub(r'\s*disk\s+\d+$', '', local_normalized)
    mb_normalized = musicbrainz['title'].lower().strip()

    result['title_match'] = (local_normalized == mb_normalized or
                             local_normalized in mb_normalized or
                             mb_normalized in local_normalized)

    # Compare track counts
    result['track_count_match'] = (local['track_count'] == musicbrainz['track_count'])

    # Compare track titles (simplified - just check if counts match for now)
    # Full track-by-track comparison could be added later

    # Check cover art status
    has_embedded = any(t.get('has_embedded_cover', False) for t in local['tracks'])

    if has_embedded or local['has_cover']:
        result['cover_status'] = 'ok'
    elif musicbrainz['has_cover_art']:
        result['cover_status'] = 'available_online'
    else:
        result['cover_status'] = 'missing_everywhere'

    # Determine if needs attention
    result['needs_attention'] = (not result['title_match'] or
                                 not result['track_count_match'] or
                                 result['cover_status'] != 'ok')

    return result

def validate_album(album_path, verbose=True):
    """
    Validate single album against MusicBrainz.

    Returns comparison dict.
    """
    album_name = os.path.basename(album_path)

    if verbose:
        print(f"\n[Validating] {album_name}")

    # Get local metadata
    if verbose:
        print(f"  Reading local files...")
    local = get_local_album_metadata(album_path)

    # Search MusicBrainz
    if verbose:
        print(f"  Searching MusicBrainz...")
    musicbrainz = search_musicbrainz(album_name)

    # Compare
    comparison = compare_albums(local, musicbrainz)

    if verbose:
        if musicbrainz is None:
            print(f"  [NOT FOUND] Not found in MusicBrainz")
        else:
            print(f"  MusicBrainz ID: {comparison['musicbrainz_id']}")

            if comparison['title_match']:
                print(f"  [OK] Title matches: {comparison['title_correct']}")
            else:
                print(f"  [MISMATCH] Title:")
                print(f"    Local:   {comparison['title_local']}")
                print(f"    Correct: {comparison['title_correct']}")

            if comparison['track_count_match']:
                print(f"  [OK] Track count: {comparison['track_count_local']}")
            else:
                print(f"  [MISMATCH] Track count:")
                print(f"    Local:   {comparison['track_count_local']}")
                print(f"    Correct: {comparison['track_count_correct']}")

            if comparison['cover_status'] == 'ok':
                print(f"  [OK] Cover art present")
            elif comparison['cover_status'] == 'available_online':
                print(f"  [MISSING] Cover art available online")
            else:
                print(f"  [MISSING] No cover art found")

    return comparison

def validate_all_albums(artist_path, output_file=None):
    """
    Validate all albums in Various Artists folder.
    """
    print(f"Validating albums in: {artist_path}\n")

    if not os.path.exists(artist_path):
        print(f"Error: Path does not exist: {artist_path}")
        return

    # Get all album folders
    try:
        all_folders = [d for d in os.listdir(artist_path)
                      if os.path.isdir(os.path.join(artist_path, d))]
        all_folders.sort()
    except Exception as e:
        print(f"Error reading directory: {e}")
        return

    print(f"Found {len(all_folders)} albums to validate\n")
    print("=" * 80)

    results = []

    for i, folder in enumerate(all_folders, 1):
        album_path = os.path.join(artist_path, folder)
        print(f"\n[{i}/{len(all_folders)}]", end=" ")

        try:
            comparison = validate_album(album_path, verbose=True)
            comparison['folder_name'] = folder
            results.append(comparison)
        except Exception as e:
            print(f"  [ERROR] {e}")
            results.append({
                'folder_name': folder,
                'error': str(e),
                'needs_attention': True
            })

    # Generate summary
    print("\n" + "=" * 80)
    print("\n=== VALIDATION SUMMARY ===\n")

    needs_attention = [r for r in results if r.get('needs_attention', False)]
    title_mismatches = [r for r in results if r.get('title_match') == False]
    track_mismatches = [r for r in results if r.get('track_count_match') == False]
    missing_covers = [r for r in results if r.get('cover_status') == 'available_online']
    not_found = [r for r in results if 'error' in r and 'Not found' in r.get('error', '')]

    print(f"Total albums: {len(results)}")
    print(f"Needs attention: {len(needs_attention)}")
    print(f"  - Title mismatches: {len(title_mismatches)}")
    print(f"  - Track count mismatches: {len(track_mismatches)}")
    print(f"  - Missing cover art: {len(missing_covers)}")
    print(f"  - Not found in MusicBrainz: {len(not_found)}")
    print(f"Perfect matches: {len(results) - len(needs_attention)}")

    # Save report
    if output_file:
        report = {
            'summary': {
                'total': len(results),
                'needs_attention': len(needs_attention),
                'title_mismatches': len(title_mismatches),
                'track_mismatches': len(track_mismatches),
                'missing_covers': len(missing_covers),
                'not_found': len(not_found)
            },
            'albums': results
        }

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\nValidation report saved: {output_file}")
        except Exception as e:
            print(f"\nError saving report: {e}")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Various Artists Album Validation')
    parser.add_argument('path', help='Path to Various Artists directory')
    parser.add_argument('--album', help='Validate specific album only')
    parser.add_argument('--output', default='D:/music cleanup/outputs/various_artists_validation.json',
                       help='Output file for validation report')

    args = parser.parse_args()

    if args.album:
        album_path = os.path.join(args.path, args.album)
        validate_album(album_path, verbose=True)
    else:
        validate_all_albums(args.path, output_file=args.output)

if __name__ == '__main__':
    main()
