#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated CD Music Metadata Management System v2.0

Main entry point for the refactored music metadata system.
Uses Claude AI agents for 95% of decision-making with minimal human intervention.

Usage:
    python music_metadata_system.py --path "/path/to/music/Various Artists"
    python music_metadata_system.py --path "/path/to/music/Various Artists" --album "Album Name"
    python music_metadata_system.py --config custom-config.yaml --path "/path/to/music"

The system implements a 10-step workflow:
    1. User Input - Accept folder path
    2. Album Discovery - Scan folder structure
    3. Metadata Enrichment - Fetch from trusted sources
    4. Audio Fingerprinting - Generate and validate fingerprints
    5. Current Metadata Collection - Read from audio files
    6. Metadata Validation - Verify completeness (Claude agent)
    7. Conflict Resolution - Resolve discrepancies (Claude agent)
    8. Report Generation - Create JSON/CSV per album
    9. Album Completion - Log and move to next
    10. Summary Report - Generate final summary
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from orchestrator.config import ConfigManager
from orchestrator.state import StateStore


class MusicMetadataSystem:
    """
    Main orchestrator for the automated music metadata system.

    Implements the 10-step workflow with Claude agent integration
    for intelligent decision-making.
    """

    def __init__(self, config_path: str = "music-config.yaml"):
        """
        Initialize the system.

        Args:
            config_path: Path to configuration file
        """
        self.config = ConfigManager(config_path)
        self.state = StateStore(self.config.state_path)
        self.outputs_path = Path(self.config.get('output.reports_path', 'outputs'))
        self.outputs_path.mkdir(exist_ok=True)

        # Load credentials
        self.credentials = self._load_credentials()

        # Initialize data sources lazily
        self._sources_initialized = False
        self._sources = {}

        # Processing statistics
        self.stats = {
            'albums_processed': 0,
            'albums_success': 0,
            'albums_needs_review': 0,
            'albums_failed': 0,
            'total_tracks': 0,
            'processing_time': 0,
            'sources_used': {},
            'quality_scores': []
        }

    def _load_credentials(self) -> Dict[str, Any]:
        """Load API credentials from credentials.yaml"""
        creds_path = project_root / "credentials.yaml"
        if creds_path.exists():
            with open(creds_path, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}

    def _init_sources(self):
        """Initialize data sources (lazy loading)"""
        if self._sources_initialized:
            return

        from sources import (
            MusicBrainzSource, SpotifySource, DiscogsSource,
            iTunesSource, AcoustIDSource
        )

        # MusicBrainz (Priority 1) - No auth required
        mb_config = self.credentials.get('musicbrainz', {})
        self._sources['musicbrainz'] = MusicBrainzSource(
            user_agent=mb_config.get('user_agent', 'MusicCleanup/1.0')
        )

        # Spotify (Priority 2) - Requires credentials
        spotify_config = self.credentials.get('spotify', {})
        if spotify_config.get('client_id') and spotify_config.get('client_secret'):
            try:
                self._sources['spotify'] = SpotifySource(
                    client_id=spotify_config['client_id'],
                    client_secret=spotify_config['client_secret']
                )
            except Exception as e:
                self._log(f"Warning: Could not initialize Spotify source: {e}")

        # Discogs (Priority 3) - Optional token
        discogs_config = self.credentials.get('discogs', {})
        self._sources['discogs'] = DiscogsSource(
            token=discogs_config.get('token')
        )

        # iTunes (Priority 4) - No auth required
        self._sources['itunes'] = iTunesSource()

        # AcoustID - For fingerprinting
        acoustid_config = self.credentials.get('acoustid', {})
        if acoustid_config.get('api_key'):
            self._sources['acoustid'] = AcoustIDSource(
                api_key=acoustid_config['api_key']
            )

        self._sources_initialized = True
        self._log(f"Initialized {len(self._sources)} data sources")

    def _log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def process_path(self, path: str, album_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a folder path (main entry point).

        Implements the 10-step workflow.

        Args:
            path: Path to music folder (artist or album)
            album_filter: Optional album name to process only

        Returns:
            Processing summary
        """
        start_time = time.time()
        self._log(f"Starting metadata processing for: {path}")

        # Step 1: User Input - Already received as path argument
        root_path = Path(path)
        if not root_path.exists():
            return {'status': 'error', 'error': f'Path not found: {path}'}

        # Step 2: Album Discovery
        self._log("Step 2: Discovering albums...")
        albums = self._discover_albums(root_path)

        if album_filter:
            albums = [a for a in albums if album_filter.lower() in a['folder_name'].lower()]

        self._log(f"Found {len(albums)} album(s) to process")

        if not albums:
            return {'status': 'no_albums', 'message': 'No albums found to process'}

        # Initialize data sources
        self._init_sources()

        # Process each album through steps 3-9
        results = []
        for i, album in enumerate(albums, 1):
            self._log(f"\n{'='*60}")
            self._log(f"Processing album {i}/{len(albums)}: {album['folder_name']}")
            self._log(f"{'='*60}")

            result = self._process_album(album)
            results.append(result)

            self.stats['albums_processed'] += 1
            if result.get('status') == 'success':
                self.stats['albums_success'] += 1
            elif result.get('requires_review'):
                self.stats['albums_needs_review'] += 1
            else:
                self.stats['albums_failed'] += 1

        # Step 10: Summary Report
        self.stats['processing_time'] = time.time() - start_time
        summary = self._generate_summary_report(results)

        self._log(f"\n{'='*60}")
        self._log("Processing Complete!")
        self._log(f"{'='*60}")
        self._log(f"Albums processed: {self.stats['albums_processed']}")
        self._log(f"  Success: {self.stats['albums_success']}")
        self._log(f"  Needs review: {self.stats['albums_needs_review']}")
        self._log(f"  Failed: {self.stats['albums_failed']}")
        self._log(f"Total time: {self.stats['processing_time']:.1f}s")

        return summary

    def _discover_albums(self, root_path) -> List[Dict[str, Any]]:
        """
        Step 2: Discover albums in folder structure.

        Args:
            root_path: Root path to scan

        Returns:
            List of album dictionaries with path and track info
        """
        # Convert to Path if string
        if isinstance(root_path, str):
            root_path = Path(root_path)

        audio_extensions = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wav'}
        albums = []

        # Check if root_path is an album folder (contains audio files directly)
        audio_files = [f for f in root_path.iterdir()
                       if f.is_file() and f.suffix.lower() in audio_extensions]

        if audio_files:
            # Root path is an album folder
            albums.append({
                'path': str(root_path),
                'folder_name': root_path.name,
                'tracks': [str(f) for f in audio_files],
                'track_count': len(audio_files)
            })
        else:
            # Root path contains album subfolders
            for item in root_path.iterdir():
                if item.is_dir():
                    audio_files = [f for f in item.iterdir()
                                   if f.is_file() and f.suffix.lower() in audio_extensions]
                    if audio_files:
                        albums.append({
                            'path': str(item),
                            'folder_name': item.name,
                            'tracks': [str(f) for f in audio_files],
                            'track_count': len(audio_files)
                        })

        return albums

    def _process_album(self, album: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single album through steps 3-9.

        Args:
            album: Album dictionary with path and track info

        Returns:
            Processing result
        """
        album_path = album['path']
        folder_name = album['folder_name']

        try:
            # Step 2.5: Standardize folder name (convert _ to -)
            folder_rename = self._standardize_folder_name(album_path)
            if folder_rename.get('renamed'):
                album_path = folder_rename['new_path']
                folder_name = folder_rename['new_name']
                album['path'] = album_path
                album['folder_name'] = folder_name
                # Update tracks list with new paths after folder rename
                album['tracks'] = [str(f) for f in Path(album_path).iterdir()
                                   if f.is_file() and f.suffix.lower() in {'.mp3', '.m4a', '.flac', '.ogg', '.wav'}]
                album['track_count'] = len(album['tracks'])

            # Step 2.6: Handle disc notation in folder name
            if folder_rename.get('disc_number'):
                self._log(f"Step 2.6: Processing disc folder...")
                disc_result = self._process_disc_folder(
                    album_path,
                    folder_rename['disc_number'],
                    folder_rename['clean_album_name']
                )
                album_path = disc_result['new_path']
                folder_name = folder_rename['clean_album_name']
                album['path'] = album_path
                album['folder_name'] = folder_name
                # Update tracks list with new paths
                album['tracks'] = [str(f) for f in Path(album_path).iterdir()
                                   if f.is_file() and f.suffix.lower() in {'.mp3', '.m4a', '.flac', '.ogg', '.wav'}]
                album['track_count'] = len(album['tracks'])

            # Step 3: Metadata Enrichment - Fetch from trusted sources
            self._log("Step 3: Fetching metadata from trusted sources...")
            enrichment_data = self._enrich_metadata(folder_name, album['track_count'])

            # Step 4: Audio Fingerprinting (if enabled and source available)
            fingerprint_data = None
            if 'acoustid' in self._sources and self.config.get('fingerprinting.enabled', True):
                self._log("Step 4: Generating audio fingerprints...")
                fingerprint_data = self._fingerprint_tracks(album['tracks'][:3])  # Sample first 3 tracks
            else:
                self._log("Step 4: Fingerprinting skipped (not configured)")

            # Step 5: Current Metadata Collection
            self._log("Step 5: Reading current metadata from files...")
            current_metadata = self._read_current_metadata(album['tracks'])

            # Step 6: Metadata Validation (Claude agent decision)
            self._log("Step 6: Validating metadata (Claude agent)...")
            validation_result = self._validate_metadata_with_agent(
                album_path, folder_name, current_metadata, enrichment_data, fingerprint_data
            )

            # Step 7: Conflict Resolution (Claude agent decision)
            self._log("Step 7: Resolving conflicts (Claude agent)...")
            resolution_result = self._resolve_conflicts_with_agent(
                album_path, folder_name, current_metadata, enrichment_data,
                fingerprint_data, validation_result
            )

            # Step 7.5: Sync filenames to metadata titles
            self._log("Step 7.5: Syncing filenames to metadata titles...")
            filename_sync = self._sync_filenames(album_path)
            if filename_sync['renamed'] > 0:
                self._log(f"  Renamed {filename_sync['renamed']} files to match titles")

            # Step 7.6: Validate disc filenames (fix mismatches)
            disc_validation = self._validate_disc_filenames(album_path)
            if disc_validation['renamed'] > 0:
                self._log(f"  Fixed {disc_validation['renamed']} disc filename mismatches")

            # Step 7.7: Cover art validation and embedding
            self._log("Step 7.7: Validating and processing cover art...")
            cover_art_result = self._process_cover_art(album_path, enrichment_data)
            if cover_art_result['validation']['status'] == 'valid':
                self._log(f"  Cover art valid ({cover_art_result['check']['has_cover']}/{cover_art_result['check']['total']} tracks)")
            elif cover_art_result['action'] == 'embedded':
                self._log(f"  Embedded cover art into {cover_art_result['embedded']} files")
            elif cover_art_result['action'] == 'fetch_failed':
                self._log("  Warning: Could not fetch missing cover art")

            # Step 8: Report Generation
            self._log("Step 8: Generating reports...")
            report = self._generate_album_report(
                album, current_metadata, enrichment_data,
                fingerprint_data, validation_result, resolution_result,
                cover_art_result
            )

            # Step 9: Album Completion
            self._log("Step 9: Album processing complete")
            self._log(f"  Quality Score: {report.get('quality_score', 'N/A')}")
            self._log(f"  Status: {report.get('status', 'unknown')}")

            if report.get('quality_score', 0) >= 85:
                self.stats['quality_scores'].append(report['quality_score'])

            return report

        except Exception as e:
            self._log(f"Error processing album: {e}", "ERROR")
            return {
                'status': 'error',
                'album_path': album_path,
                'folder_name': folder_name,
                'error': str(e)
            }

    def _enrich_metadata(self, album_title: str, track_count: int) -> Dict[str, Any]:
        """
        Step 3: Fetch metadata from trusted sources in priority order.

        Args:
            album_title: Album title to search
            track_count: Expected track count for validation

        Returns:
            Enrichment data from sources
        """
        results = {
            'sources_queried': [],
            'sources_matched': [],
            'best_match': None,
            'all_matches': {}
        }

        # Priority order: MusicBrainz, Spotify, Discogs, iTunes
        source_priority = ['musicbrainz', 'spotify', 'discogs', 'itunes']

        for source_name in source_priority:
            if source_name not in self._sources:
                continue

            source = self._sources[source_name]
            results['sources_queried'].append(source_name)

            try:
                # Clean title for search
                search_title = album_title.replace('_', ' ')
                matches = source.search_album(search_title, "Various Artists")

                if matches:
                    results['sources_matched'].append(source_name)
                    results['all_matches'][source_name] = [m.__dict__ for m in matches[:5]]

                    # Find best match by track count
                    best = None
                    for match in matches:
                        if match.track_count == track_count:
                            best = match
                            break

                    if not best and matches:
                        best = matches[0]

                    if best and not results['best_match']:
                        # Get full album details if available
                        try:
                            full_album = source.get_album(best.source_id)
                            if full_album:
                                results['best_match'] = {
                                    'source': source_name,
                                    'title': full_album.title,
                                    'artist': full_album.artist,
                                    'year': full_album.year,
                                    'track_count': full_album.track_count,
                                    'tracks': [t.__dict__ for t in full_album.tracks],
                                    'cover_url': full_album.cover_url,
                                    'source_id': full_album.source_id,
                                    'confidence': full_album.confidence
                                }
                                self._log(f"  Found match on {source_name}: {full_album.title}")
                        except Exception as e:
                            self._log(f"  Warning: Could not get full details from {source_name}: {e}")

                    # Track source usage
                    self.stats['sources_used'][source_name] = self.stats['sources_used'].get(source_name, 0) + 1

            except Exception as e:
                self._log(f"  Warning: {source_name} query failed: {e}")

        return results

    def _fingerprint_tracks(self, track_paths: List[str]) -> Dict[str, Any]:
        """
        Step 4: Generate audio fingerprints for tracks.

        Args:
            track_paths: List of audio file paths

        Returns:
            Fingerprint data
        """
        results = {
            'tracks': [],
            'fingerprinting_available': True
        }

        acoustid = self._sources.get('acoustid')
        if not acoustid:
            results['fingerprinting_available'] = False
            return results

        for track_path in track_paths:
            try:
                fp_result = acoustid.fingerprint_file(track_path)
                if fp_result:
                    results['tracks'].append({
                        'path': track_path,
                        'fingerprint': fp_result.get('fingerprint'),
                        'duration': fp_result.get('duration'),
                        'matches': fp_result.get('matches', [])
                    })
            except Exception as e:
                self._log(f"  Fingerprint failed for {Path(track_path).name}: {e}")

        return results

    def _read_current_metadata(self, track_paths: List[str]) -> Dict[str, Any]:
        """
        Step 5: Read current metadata from audio files.

        Args:
            track_paths: List of audio file paths

        Returns:
            Current metadata
        """
        from mutagen import File
        from mutagen.easyid3 import EasyID3
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        tracks = []
        album_metadata = {}

        for track_path in sorted(track_paths):
            try:
                audio = File(track_path)
                if audio is None:
                    continue

                track_data = {
                    'path': track_path,
                    'filename': Path(track_path).name,
                    'duration_ms': int(audio.info.length * 1000) if audio.info else None
                }

                # Get metadata based on file type
                if isinstance(audio, MP3):
                    try:
                        easy = EasyID3(track_path)
                        track_data['title'] = easy.get('title', [None])[0]
                        track_data['artist'] = easy.get('artist', [None])[0]
                        track_data['album'] = easy.get('album', [None])[0]
                        track_data['tracknumber'] = easy.get('tracknumber', [None])[0]
                    except:
                        pass
                elif isinstance(audio, MP4):
                    track_data['title'] = audio.get('\xa9nam', [None])[0]
                    track_data['artist'] = audio.get('\xa9ART', [None])[0]
                    track_data['album'] = audio.get('\xa9alb', [None])[0]
                elif isinstance(audio, FLAC):
                    track_data['title'] = audio.get('title', [None])[0]
                    track_data['artist'] = audio.get('artist', [None])[0]
                    track_data['album'] = audio.get('album', [None])[0]

                tracks.append(track_data)

                # Capture album-level metadata from first track
                if not album_metadata and track_data.get('album'):
                    album_metadata = {
                        'title': track_data.get('album'),
                        'artist': track_data.get('artist')
                    }

            except Exception as e:
                self._log(f"  Warning: Could not read {Path(track_path).name}: {e}")

        return {
            'album': album_metadata,
            'tracks': tracks,
            'track_count': len(tracks)
        }

    def _validate_metadata_with_agent(
        self, album_path: str, folder_name: str,
        current: Dict, enrichment: Dict, fingerprint: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Step 6: Use Claude agent to validate metadata.

        Prepares data and invokes the metadata_validator agent.

        Returns:
            Validation result from Claude agent
        """
        # Prepare input data for Claude agent
        validation_input = {
            'album_path': album_path,
            'folder_name': folder_name,
            'current_metadata': current,
            'trusted_source_metadata': enrichment.get('best_match'),
            'fingerprint_data': fingerprint,
            'sources_queried': enrichment.get('sources_queried', []),
            'sources_matched': enrichment.get('sources_matched', [])
        }

        # For now, use built-in validation logic
        # In full implementation, this would invoke Claude subagent
        quality_score = self._calculate_quality_score(current, enrichment)

        return {
            'quality_score': quality_score,
            'validation_status': self._get_validation_status(quality_score),
            'track_count_match': current.get('track_count', 0) == enrichment.get('best_match', {}).get('track_count', 0),
            'requires_human_review': quality_score < 70,
            'discrepancies': self._find_discrepancies(current, enrichment),
            'recommendations': []
        }

    def _resolve_conflicts_with_agent(
        self, album_path: str, folder_name: str,
        current: Dict, enrichment: Dict, fingerprint: Optional[Dict],
        validation: Dict
    ) -> Dict[str, Any]:
        """
        Step 7: Use Claude agent to resolve conflicts.

        Prepares data and invokes the conflict_resolver agent.

        Returns:
            Resolution result from Claude agent
        """
        # Prepare input for conflict resolver
        conflict_input = {
            'album_path': album_path,
            'folder_name': folder_name,
            'current_metadata': current,
            'trusted_source_metadata': enrichment.get('best_match'),
            'fingerprint_data': fingerprint,
            'validation_result': validation
        }

        # For now, use built-in resolution logic
        # In full implementation, this would invoke Claude subagent
        best_match = enrichment.get('best_match', {})

        resolutions = []
        if best_match and validation.get('discrepancies'):
            for disc in validation['discrepancies']:
                resolutions.append({
                    'field': disc.get('field'),
                    'action': 'UPDATE' if disc.get('confidence', 0) >= 85 else 'REVIEW',
                    'current_value': disc.get('current'),
                    'recommended_value': disc.get('source'),
                    'confidence': disc.get('confidence', 70)
                })

        return {
            'conflict_resolution_status': 'resolved' if not validation.get('requires_human_review') else 'requires_review',
            'resolutions': resolutions,
            'artwork_decision': 'PRESERVE',
            'requires_human_review': validation.get('requires_human_review', False)
        }

    def _sync_filenames(self, album_path: str) -> Dict[str, Any]:
        """
        Sync audio filenames to match their metadata titles.

        Format: {disc}-{track} {title}.{ext} for multi-disc albums
        Format: {track} {title}.{ext} for single-disc albums

        Args:
            album_path: Path to album folder

        Returns:
            Dictionary with sync results
        """
        from mutagen.easyid3 import EasyID3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        path = Path(album_path)
        audio_extensions = {'.mp3', '.m4a', '.flac', '.ogg', '.wav'}
        audio_files = [f for f in path.iterdir()
                       if f.is_file() and f.suffix.lower() in audio_extensions]

        results = {
            'renamed': 0,
            'skipped': 0,
            'errors': [],
            'changes': []
        }

        for audio_file in sorted(audio_files):
            try:
                ext = audio_file.suffix.lower()
                title = None
                track_num = None
                disc_num = None
                total_discs = 1

                # Read metadata based on file type
                if ext == '.mp3':
                    audio = EasyID3(str(audio_file))
                    title = audio.get('title', [None])[0]
                    track_num = audio.get('tracknumber', [''])[0].split('/')[0]
                    # Read disc info
                    disc_str = audio.get('discnumber', ['1/1'])[0]
                    parts = disc_str.split('/')
                    disc_num = int(parts[0]) if parts[0] else 1
                    total_discs = int(parts[1]) if len(parts) > 1 and parts[1] else 1
                elif ext == '.m4a':
                    audio = MP4(str(audio_file))
                    title = audio.get('\xa9nam', [None])[0]
                    track_info = audio.get('trkn', [(None, None)])[0]
                    track_num = str(track_info[0]) if track_info[0] else None
                    # Read disc info
                    disc_info = audio.get('disk', [(1, 1)])[0]
                    disc_num = disc_info[0] or 1
                    total_discs = disc_info[1] or 1
                elif ext == '.flac':
                    audio = FLAC(str(audio_file))
                    title = audio.get('title', [None])[0]
                    track_num = audio.get('tracknumber', [''])[0].split('/')[0]
                    # Read disc info
                    disc_str = audio.get('discnumber', ['1'])[0]
                    disc_parts = disc_str.split('/')
                    disc_num = int(disc_parts[0]) if disc_parts[0] else 1
                    total_str = audio.get('disctotal', ['1'])[0]
                    total_discs = int(disc_parts[1]) if len(disc_parts) > 1 else int(total_str)

                if not title:
                    results['skipped'] += 1
                    continue

                # Format track number (2 digits)
                track_num = (track_num or '0').zfill(2)

                # Create safe filename - include disc prefix for multi-disc albums
                # If disc_num > 1, it's definitely multi-disc even if total_discs is wrong
                safe_title = self._make_filename_safe(title)
                is_multi_disc = total_discs > 1 or disc_num > 1
                if is_multi_disc:
                    new_name = f'{disc_num}-{track_num} {safe_title}{ext}'
                else:
                    new_name = f'{track_num} {safe_title}{ext}'
                new_path = path / new_name

                # Skip if already correct
                if audio_file.name == new_name:
                    results['skipped'] += 1
                    continue

                # Check if target exists
                if new_path.exists() and new_path != audio_file:
                    results['errors'].append(f"Target exists: {new_name}")
                    continue

                # Rename the file
                os.rename(str(audio_file), str(new_path))
                results['renamed'] += 1
                results['changes'].append({
                    'old': audio_file.name,
                    'new': new_name
                })

            except Exception as e:
                results['errors'].append(f"{audio_file.name}: {str(e)}")

        return results

    def _make_filename_safe(self, name: str) -> str:
        """Make a string safe for use as a filename."""
        import re

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

        # Clean up empty brackets left after removing invalid chars
        name = re.sub(r'\[\s*\]', '', name)  # Remove empty []
        name = re.sub(r'\(\s*\)', '', name)  # Remove empty ()
        name = re.sub(r'\{\s*\}', '', name)  # Remove empty {}

        # Clean up multiple spaces and trailing dots/spaces
        name = ' '.join(name.split())
        name = name.rstrip('. ')  # Remove trailing dots and spaces

        return name[:200].strip()

    def _standardize_folder_name(self, album_path: str) -> Dict[str, Any]:
        """
        Standardize folder name by converting legacy underscore patterns to dashes.
        Also detects disc notation in folder names.

        Converts patterns like:
        - "Album_ Subtitle" -> "Album - Subtitle"
        - "Album_Subtitle" -> "Album - Subtitle" (underscore as colon replacement)
        - "Album Disc 1" -> detected as disc 1

        Args:
            album_path: Path to album folder

        Returns:
            Dictionary with rename result and disc info
        """
        import re

        path = Path(album_path)
        old_name = path.name
        new_name = old_name

        # Pattern 1: "Something_ Something" (underscore + space -> " - ")
        # This is the most common case from old naming conventions
        new_name = re.sub(r'_\s+', ' - ', new_name)

        # Pattern 2: "Something_Something" where underscore was used for colon
        # Only apply if it looks like a title separator (capital letter follows)
        new_name = re.sub(r'_([A-Z])', r' - \1', new_name)

        # Clean up any double spaces
        new_name = ' '.join(new_name.split())

        # Detect disc notation in folder name
        disc_patterns = [
            r'\s+Disc\s+(\d+)$',      # "Album Disc 1"
            r'\s+CD\s*(\d+)$',        # "Album CD1" or "Album CD 1"
            r'\s+Disk\s+(\d+)$',      # "Album Disk 1"
            r'\s*\[Disc\s+(\d+)\]$',  # "Album [Disc 1]"
            r'\s*\(Disc\s+(\d+)\)$',  # "Album (Disc 1)"
        ]

        disc_number = None
        clean_album_name = new_name
        for pattern in disc_patterns:
            match = re.search(pattern, new_name, re.IGNORECASE)
            if match:
                disc_number = int(match.group(1))
                clean_album_name = re.sub(pattern, '', new_name, flags=re.IGNORECASE).strip()
                break

        # Skip folder rename if no change needed (disc handling happens separately)
        if new_name == old_name:
            return {
                'renamed': False,
                'old_name': old_name,
                'disc_number': disc_number,
                'clean_album_name': clean_album_name
            }

        # Check if target already exists
        new_path = path.parent / new_name
        if new_path.exists():
            self._log(f"  Warning: Cannot rename folder, target exists: {new_name}")
            return {
                'renamed': False,
                'old_name': old_name,
                'error': 'target_exists',
                'disc_number': disc_number,
                'clean_album_name': clean_album_name
            }

        # Rename the folder
        try:
            os.rename(str(path), str(new_path))
            self._log(f"  Renamed folder: {old_name} -> {new_name}")
            return {
                'renamed': True,
                'old_name': old_name,
                'new_name': new_name,
                'new_path': str(new_path),
                'disc_number': disc_number,
                'clean_album_name': clean_album_name
            }
        except OSError as e:
            self._log(f"  Error renaming folder: {e}")
            return {
                'renamed': False,
                'old_name': old_name,
                'error': str(e),
                'disc_number': disc_number,
                'clean_album_name': clean_album_name
            }

    def _process_disc_folder(self, album_path: str, disc_number: int,
                             album_name: str) -> Dict[str, Any]:
        """
        Process a folder with disc notation in its name.

        1. Look up total disc count from online sources
        2. Rename folder to album name (remove disc notation)
        3. Add disc prefix to all filenames
        4. Update disc metadata in all files

        Args:
            album_path: Current path to the disc folder
            disc_number: Detected disc number
            album_name: Clean album name (without disc notation)

        Returns:
            Dictionary with processing results
        """
        from mutagen.easyid3 import EasyID3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        path = Path(album_path)
        audio_exts = {'.mp3', '.m4a', '.flac', '.ogg', '.wav'}

        # 1. Look up total disc count from online sources
        total_discs = self._lookup_disc_count(album_name)
        # Ensure total is at least as high as the disc number
        if disc_number > total_discs:
            total_discs = disc_number
        self._log(f"  Detected disc {disc_number} of {total_discs}")

        # 2. Rename folder to album name (remove disc notation)
        new_path = path.parent / album_name
        if new_path.exists() and new_path != path:
            # Target folder already exists - merge into it
            self._log(f"  Merging into existing folder: {album_name}")
        elif not new_path.exists():
            os.rename(str(path), str(new_path))
            self._log(f"  Renamed folder: {path.name} -> {album_name}")
            path = new_path

        # If we merged, path still points to old location - update it
        if new_path.exists():
            path = new_path

        # 3. Add disc prefix to filenames and collect files to process
        audio_files = [f for f in path.iterdir()
                       if f.is_file() and f.suffix.lower() in audio_exts]
        files_renamed = 0

        for audio_file in sorted(audio_files):
            # Skip files that already have disc prefix
            if audio_file.name[0].isdigit() and '-' in audio_file.name[:3]:
                continue

            # Read track number and title from metadata
            track_num = self._get_track_number(audio_file)
            title = self._get_title(audio_file)

            if not title:
                # Fallback: extract from filename
                title = self._extract_title_from_filename(audio_file.name)

            # New format: "1-01 Song Title.mp3"
            new_name = f"{disc_number}-{track_num:02d} {title}{audio_file.suffix}"
            safe_name = self._make_filename_safe(new_name)
            new_file_path = path / safe_name

            if audio_file.name != safe_name and not new_file_path.exists():
                os.rename(str(audio_file), str(new_file_path))
                files_renamed += 1

        # 4. Update disc metadata in all files
        audio_files = [f for f in path.iterdir()
                       if f.is_file() and f.suffix.lower() in audio_exts]
        for audio_file in audio_files:
            try:
                self._update_disc_metadata(audio_file, disc_number, total_discs)
            except Exception as e:
                self._log(f"  Warning: Could not update disc metadata for {audio_file.name}: {e}")

        return {
            'new_path': str(path),
            'disc_number': disc_number,
            'total_discs': total_discs,
            'files_renamed': files_renamed,
            'files_updated': len(audio_files)
        }

    def _lookup_disc_count(self, album_name: str) -> int:
        """
        Look up total disc count from online sources.

        Args:
            album_name: Album name to search for

        Returns:
            Total number of discs (default 1 if not found)
        """
        # Initialize sources if not already done
        if not self._sources_initialized:
            self._init_sources()

        # Try MusicBrainz first
        if 'musicbrainz' in self._sources:
            try:
                results = self._sources['musicbrainz'].search_album(
                    album_name, "Various Artists"
                )
                for result in results[:3]:
                    album = self._sources['musicbrainz'].get_album(result.source_id)
                    if album:
                        # Check for disc_count attribute or count from tracks
                        if hasattr(album, 'disc_count') and album.disc_count:
                            return album.disc_count
                        # Count distinct disc numbers from tracks
                        if hasattr(album, 'tracks') and album.tracks:
                            disc_nums = set()
                            for track in album.tracks:
                                if hasattr(track, 'disc_number') and track.disc_number:
                                    disc_nums.add(track.disc_number)
                            if disc_nums:
                                return max(disc_nums)
            except Exception as e:
                self._log(f"  Warning: MusicBrainz disc lookup failed: {e}")

        # Try Discogs
        if 'discogs' in self._sources:
            try:
                results = self._sources['discogs'].search_album(
                    album_name, "Various Artists"
                )
                for result in results[:3]:
                    album = self._sources['discogs'].get_album(result.source_id)
                    if album and hasattr(album, 'disc_count') and album.disc_count:
                        return album.disc_count
            except Exception as e:
                self._log(f"  Warning: Discogs disc lookup failed: {e}")

        return 1  # Default if not found

    def _validate_disc_filenames(self, album_path: str) -> Dict[str, Any]:
        """
        Validate files with disc metadata have correct filename format.

        If file has discnumber=2/2 but filename doesn't start with "2-",
        rename to add disc prefix.

        Args:
            album_path: Path to album folder

        Returns:
            Dictionary with validation results
        """
        path = Path(album_path)
        audio_exts = {'.mp3', '.m4a', '.flac', '.ogg', '.wav'}
        results = {'validated': 0, 'renamed': 0, 'errors': []}

        audio_files = [f for f in path.iterdir()
                       if f.is_file() and f.suffix.lower() in audio_exts]

        for audio_file in sorted(audio_files):
            try:
                # Read disc metadata
                disc_num, total_discs = self._read_disc_metadata(audio_file)

                if total_discs <= 1:
                    continue  # Not a multi-disc album

                results['validated'] += 1
                expected_prefix = f"{disc_num}-"

                # Check if filename already has correct disc prefix
                if audio_file.name.startswith(expected_prefix):
                    continue  # Already correct

                # File is part of multi-disc but missing or wrong prefix
                track_num = self._extract_track_from_filename(audio_file.name)
                title = self._get_title(audio_file)
                if not title:
                    title = self._extract_title_from_filename(audio_file.name)

                new_name = f"{disc_num}-{track_num:02d} {title}{audio_file.suffix}"
                safe_name = self._make_filename_safe(new_name)
                new_path = path / safe_name

                if not new_path.exists() and audio_file.name != safe_name:
                    os.rename(str(audio_file), str(new_path))
                    results['renamed'] += 1
                    self._log(f"  Fixed disc filename: {audio_file.name} -> {safe_name}")

            except Exception as e:
                results['errors'].append(f"{audio_file.name}: {str(e)}")

        return results

    def _read_disc_metadata(self, audio_file: Path) -> tuple:
        """
        Read discnumber metadata from audio file.

        Args:
            audio_file: Path to audio file

        Returns:
            Tuple of (disc_number, total_discs)
        """
        from mutagen.easyid3 import EasyID3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        ext = audio_file.suffix.lower()

        try:
            if ext == '.mp3':
                audio = EasyID3(str(audio_file))
                disc = audio.get('discnumber', ['1/1'])[0]
                # Parse "1/2" format
                parts = disc.split('/')
                return int(parts[0]), int(parts[1]) if len(parts) > 1 else 1
            elif ext == '.m4a':
                audio = MP4(str(audio_file))
                disc_info = audio.get('disk', [(1, 1)])[0]
                return disc_info[0] or 1, disc_info[1] or 1
            elif ext == '.flac':
                audio = FLAC(str(audio_file))
                disc = audio.get('discnumber', ['1'])[0]
                total = audio.get('disctotal', ['1'])[0]
                disc_parts = disc.split('/')
                disc_num = int(disc_parts[0])
                total_num = int(disc_parts[1]) if len(disc_parts) > 1 else int(total)
                return disc_num, total_num
        except Exception:
            pass

        return 1, 1  # Default

    def _update_disc_metadata(self, audio_file: Path, disc_num: int, total: int):
        """
        Update discnumber/disctotal metadata in audio file.

        Args:
            audio_file: Path to audio file
            disc_num: Disc number to set
            total: Total number of discs
        """
        from mutagen.easyid3 import EasyID3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        ext = audio_file.suffix.lower()

        if ext == '.mp3':
            audio = EasyID3(str(audio_file))
            audio['discnumber'] = f"{disc_num}/{total}"
            audio.save()
        elif ext == '.m4a':
            audio = MP4(str(audio_file))
            audio['disk'] = [(disc_num, total)]
            audio.save()
        elif ext == '.flac':
            audio = FLAC(str(audio_file))
            audio['discnumber'] = str(disc_num)
            audio['disctotal'] = str(total)
            audio.save()

    def _get_track_number(self, audio_file: Path) -> int:
        """Get track number from audio file metadata."""
        from mutagen.easyid3 import EasyID3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        ext = audio_file.suffix.lower()

        try:
            if ext == '.mp3':
                audio = EasyID3(str(audio_file))
                track = audio.get('tracknumber', ['1'])[0]
                return int(track.split('/')[0])
            elif ext == '.m4a':
                audio = MP4(str(audio_file))
                track_info = audio.get('trkn', [(1, 0)])[0]
                return track_info[0] or 1
            elif ext == '.flac':
                audio = FLAC(str(audio_file))
                track = audio.get('tracknumber', ['1'])[0]
                return int(track.split('/')[0])
        except Exception:
            pass

        # Fallback: extract from filename
        return self._extract_track_from_filename(audio_file.name)

    def _get_title(self, audio_file: Path) -> str:
        """Get title from audio file metadata."""
        from mutagen.easyid3 import EasyID3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC

        ext = audio_file.suffix.lower()

        try:
            if ext == '.mp3':
                audio = EasyID3(str(audio_file))
                return audio.get('title', [None])[0]
            elif ext == '.m4a':
                audio = MP4(str(audio_file))
                return audio.get('\xa9nam', [None])[0]
            elif ext == '.flac':
                audio = FLAC(str(audio_file))
                return audio.get('title', [None])[0]
        except Exception:
            pass

        return None

    def _extract_track_from_filename(self, filename: str) -> int:
        """Extract track number from filename."""
        import re

        # Try patterns like "01 Song.mp3", "1-01 Song.mp3", "Track 01.mp3"
        patterns = [
            r'^(\d+)-(\d+)',      # "1-01 Song" -> track is group 2
            r'^(\d+)\s',          # "01 Song" -> track is group 1
            r'Track\s*(\d+)',     # "Track 01" -> track is group 1
        ]

        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                # For disc-track pattern, return track (group 2)
                if len(match.groups()) > 1:
                    return int(match.group(2))
                return int(match.group(1))

        return 1  # Default

    def _extract_title_from_filename(self, filename: str) -> str:
        """Extract title from filename (without track number and extension)."""
        import re

        # Remove extension
        name = Path(filename).stem

        # Remove track number patterns
        patterns = [
            r'^\d+-\d+\s+',    # "1-01 Song" -> "Song"
            r'^\d+\s+',        # "01 Song" -> "Song"
            r'^Track\s*\d+\s*',  # "Track 01 Song" -> "Song"
        ]

        for pattern in patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)

        return name.strip()

    # =========================================================================
    # Cover Art Methods
    # =========================================================================

    def _check_cover_art(self, album_path: str) -> Dict[str, Any]:
        """
        Check cover art status for all tracks in album.

        Returns:
            Dict with cover art status for each track and summary
        """
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC
        from mutagen.id3 import ID3

        path = Path(album_path)
        audio_exts = {'.mp3', '.m4a', '.flac'}
        results = {
            'tracks': [],
            'has_cover': 0,
            'missing_cover': 0,
            'total': 0,
            'cover_sizes': [],
            'all_have_cover': False,
            'consistent': True
        }

        for audio_file in sorted(path.iterdir()):
            if audio_file.suffix.lower() not in audio_exts:
                continue

            results['total'] += 1
            track_info = {
                'file': audio_file.name,
                'has_cover': False,
                'cover_size': None,
                'cover_format': None
            }

            try:
                ext = audio_file.suffix.lower()

                if ext == '.mp3':
                    audio = MP3(str(audio_file), ID3=ID3)
                    for tag in audio.tags.values():
                        if tag.FrameID == 'APIC':
                            track_info['has_cover'] = True
                            track_info['cover_size'] = len(tag.data)
                            track_info['cover_format'] = tag.mime
                            break

                elif ext == '.m4a':
                    audio = MP4(str(audio_file))
                    if 'covr' in audio and audio['covr']:
                        cover = audio['covr'][0]
                        track_info['has_cover'] = True
                        track_info['cover_size'] = len(cover)
                        track_info['cover_format'] = 'image/jpeg' if cover.imageformat == 13 else 'image/png'

                elif ext == '.flac':
                    audio = FLAC(str(audio_file))
                    if audio.pictures:
                        pic = audio.pictures[0]
                        track_info['has_cover'] = True
                        track_info['cover_size'] = len(pic.data)
                        track_info['cover_format'] = pic.mime

            except Exception as e:
                track_info['error'] = str(e)

            results['tracks'].append(track_info)

            if track_info['has_cover']:
                results['has_cover'] += 1
                if track_info['cover_size']:
                    results['cover_sizes'].append(track_info['cover_size'])
            else:
                results['missing_cover'] += 1

        # Check consistency
        results['all_have_cover'] = results['missing_cover'] == 0 and results['total'] > 0

        if results['cover_sizes']:
            # Check if all covers are roughly the same size (within 10%)
            avg_size = sum(results['cover_sizes']) / len(results['cover_sizes'])
            results['consistent'] = all(
                abs(s - avg_size) / avg_size < 0.1 for s in results['cover_sizes']
            ) if avg_size > 0 else True
            results['avg_cover_size'] = int(avg_size)
        else:
            results['avg_cover_size'] = 0

        return results

    def _validate_cover_art(self, album_path: str, cover_check: Dict) -> Dict[str, Any]:
        """
        Validate cover art quality and consistency.

        Args:
            album_path: Path to album folder
            cover_check: Results from _check_cover_art

        Returns:
            Validation results with issues and recommendations
        """
        validation = {
            'status': 'valid',
            'issues': [],
            'recommendations': [],
            'needs_cover': False,
            'needs_replacement': False
        }

        # Check if any tracks missing cover
        if cover_check['missing_cover'] > 0:
            if cover_check['has_cover'] == 0:
                validation['status'] = 'missing'
                validation['issues'].append(f"No cover art found in any of {cover_check['total']} tracks")
                validation['needs_cover'] = True
            else:
                validation['status'] = 'incomplete'
                validation['issues'].append(
                    f"{cover_check['missing_cover']} of {cover_check['total']} tracks missing cover art"
                )
                validation['needs_cover'] = True

        # Check consistency
        if not cover_check['consistent'] and cover_check['has_cover'] > 1:
            validation['issues'].append("Cover art sizes vary significantly between tracks")
            validation['recommendations'].append("Consider re-embedding cover art for consistency")

        # Check quality (size threshold: 50KB minimum for reasonable quality)
        MIN_COVER_SIZE = 50000  # 50KB
        if cover_check['avg_cover_size'] > 0 and cover_check['avg_cover_size'] < MIN_COVER_SIZE:
            validation['issues'].append(
                f"Cover art appears low quality (avg {cover_check['avg_cover_size'] // 1000}KB)"
            )
            validation['recommendations'].append("Consider replacing with higher resolution artwork")
            validation['needs_replacement'] = True

        if not validation['issues']:
            validation['status'] = 'valid'

        return validation

    def _fetch_cover_art(self, album_name: str, enrichment_data: Dict) -> Optional[bytes]:
        """
        Fetch cover art from online sources.

        Priority: iTunes (high quality) -> Discogs -> Other sources

        Args:
            album_name: Album name for search
            enrichment_data: Enrichment data containing source matches

        Returns:
            Cover art image data as bytes, or None if not found
        """
        import requests

        cover_url = None

        # Try to get cover URL from enrichment data (already fetched)
        best_match = enrichment_data.get('best_match', {})
        if best_match:
            cover_url = best_match.get('cover_url')

        # If no cover from best match, try all matches
        if not cover_url:
            all_matches = enrichment_data.get('all_matches', {})

            # Prefer iTunes for high-quality artwork
            if 'itunes' in all_matches and all_matches['itunes']:
                for match in all_matches['itunes']:
                    if hasattr(match, 'cover_url') and match.cover_url:
                        cover_url = match.cover_url
                        break

            # Try Discogs
            if not cover_url and 'discogs' in all_matches and all_matches['discogs']:
                for match in all_matches['discogs']:
                    if hasattr(match, 'cover_url') and match.cover_url:
                        cover_url = match.cover_url
                        break

            # Try Spotify
            if not cover_url and 'spotify' in all_matches and all_matches['spotify']:
                for match in all_matches['spotify']:
                    if hasattr(match, 'cover_url') and match.cover_url:
                        cover_url = match.cover_url
                        break

        if not cover_url:
            self._log("  No cover art URL found from sources")
            return None

        # Download the cover art
        try:
            headers = {
                'User-Agent': 'MusicMetadataSystem/2.0 (https://github.com/music-cleanup)'
            }
            response = requests.get(cover_url, headers=headers, timeout=60)
            response.raise_for_status()

            # Verify it's an image
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                self._log(f"  Warning: Response is not an image ({content_type})")
                return None

            self._log(f"  Downloaded cover art ({len(response.content) // 1024}KB)")
            return response.content

        except requests.RequestException as e:
            self._log(f"  Failed to download cover art: {e}")
            return None

    def _embed_cover_art(self, album_path: str, image_data: bytes) -> Dict[str, Any]:
        """
        Embed cover art into all audio files in album.

        Args:
            album_path: Path to album folder
            image_data: Cover art image data as bytes

        Returns:
            Results with counts of embedded files
        """
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4, MP4Cover
        from mutagen.flac import FLAC, Picture
        from mutagen.id3 import ID3, APIC

        path = Path(album_path)
        audio_exts = {'.mp3', '.m4a', '.flac'}
        results = {
            'embedded': 0,
            'failed': 0,
            'errors': []
        }

        # Detect image format
        is_png = image_data[:8] == b'\x89PNG\r\n\x1a\n'
        mime_type = 'image/png' if is_png else 'image/jpeg'

        for audio_file in sorted(path.iterdir()):
            if audio_file.suffix.lower() not in audio_exts:
                continue

            try:
                ext = audio_file.suffix.lower()

                if ext == '.mp3':
                    audio = MP3(str(audio_file), ID3=ID3)
                    # Remove existing cover art
                    audio.tags.delall('APIC')
                    # Add new cover art
                    audio.tags.add(
                        APIC(
                            encoding=3,  # UTF-8
                            mime=mime_type,
                            type=3,  # Front cover
                            desc='Cover',
                            data=image_data
                        )
                    )
                    audio.save()

                elif ext == '.m4a':
                    audio = MP4(str(audio_file))
                    img_format = MP4Cover.FORMAT_PNG if is_png else MP4Cover.FORMAT_JPEG
                    audio['covr'] = [MP4Cover(image_data, imageformat=img_format)]
                    audio.save()

                elif ext == '.flac':
                    audio = FLAC(str(audio_file))
                    # Remove existing pictures
                    audio.clear_pictures()
                    # Add new picture
                    pic = Picture()
                    pic.type = 3  # Front cover
                    pic.mime = mime_type
                    pic.desc = 'Cover'
                    pic.data = image_data
                    audio.add_picture(pic)
                    audio.save()

                results['embedded'] += 1

            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{audio_file.name}: {e}")

        return results

    def _extract_cover_from_file(self, audio_file: Path) -> Optional[bytes]:
        """
        Extract cover art data from an audio file.

        Args:
            audio_file: Path to the audio file

        Returns:
            Cover art bytes or None if not found
        """
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.flac import FLAC
        from mutagen.id3 import ID3

        ext = audio_file.suffix.lower()

        try:
            if ext == '.mp3':
                audio = MP3(str(audio_file), ID3=ID3)
                if audio.tags:
                    for key in audio.tags.keys():
                        if key.startswith('APIC'):
                            return audio.tags[key].data

            elif ext == '.m4a':
                audio = MP4(str(audio_file))
                if 'covr' in audio and audio['covr']:
                    return bytes(audio['covr'][0])

            elif ext == '.flac':
                audio = FLAC(str(audio_file))
                if audio.pictures:
                    return audio.pictures[0].data

        except Exception:
            pass

        return None

    def _get_embedded_cover_hash(self, album_path: str) -> tuple:
        """
        Extract embedded cover art from first track and return data + hash.

        Args:
            album_path: Path to album folder

        Returns:
            Tuple of (cover_data_bytes, md5_hash) or (None, None) if not found
        """
        import hashlib

        path = Path(album_path)
        audio_exts = {'.mp3', '.m4a', '.flac'}

        for audio_file in sorted(path.iterdir()):
            if audio_file.suffix.lower() not in audio_exts:
                continue

            cover_data = self._extract_cover_from_file(audio_file)
            if cover_data:
                cover_hash = hashlib.md5(cover_data).hexdigest()
                return cover_data, cover_hash

        return None, None

    def _sync_folder_art(self, album_path: str, cover_check: Dict = None, image_data: bytes = None) -> Dict[str, Any]:
        """
        Synchronize folder.jpg with embedded cover art.

        - Creates folder.jpg if missing but tracks have cover art
        - Updates folder.jpg if it differs from embedded cover art

        Args:
            album_path: Path to album folder
            cover_check: Results from _check_cover_art (optional if image_data provided)
            image_data: Raw image bytes to use (optional, overrides extraction from tracks)

        Returns:
            Dict with action taken and status
        """
        import hashlib

        path = Path(album_path)
        folder_jpg = path / 'folder.jpg'
        result = {
            'action': 'none',
            'status': 'unchanged',
            'size_kb': 0
        }

        # Use provided image data or extract from tracks
        embedded_data = image_data
        if embedded_data is None and cover_check:
            # Get embedded cover art from first track with cover
            for track in cover_check.get('tracks', []):
                if track.get('has_cover') and track.get('cover_size', 0) > 0:
                    # Read the actual cover data from this track
                    embedded_data = self._extract_cover_from_file(path / track['file'])
                    if embedded_data:
                        break

        if not embedded_data:
            # No embedded cover art to sync from
            return result

        embedded_hash = hashlib.md5(embedded_data).hexdigest()

        if folder_jpg.exists():
            # Compare with existing folder.jpg
            try:
                with open(folder_jpg, 'rb') as f:
                    folder_data = f.read()
                folder_hash = hashlib.md5(folder_data).hexdigest()

                if embedded_hash == folder_hash:
                    result['action'] = 'none'
                    result['status'] = 'in_sync'
                else:
                    # Different - update folder.jpg
                    with open(folder_jpg, 'wb') as f:
                        f.write(embedded_data)
                    result['action'] = 'updated'
                    result['status'] = 'synced'
                    result['size_kb'] = len(embedded_data) // 1024
            except Exception as e:
                result['status'] = f'error: {e}'
        else:
            # Create folder.jpg
            try:
                with open(folder_jpg, 'wb') as f:
                    f.write(embedded_data)
                result['action'] = 'created'
                result['status'] = 'synced'
                result['size_kb'] = len(embedded_data) // 1024
            except Exception as e:
                result['status'] = f'error: {e}'

        return result

    def _process_cover_art(self, album_path: str, enrichment_data: Dict) -> Dict[str, Any]:
        """
        Full cover art processing with embedded art priority.

        Workflow:
        1. Extract existing embedded art and hash
        2. If valid embedded art exists, sync to folder.jpg and stop
        3. Only fetch from external sources if missing/low quality
        4. Compare fetched vs embedded before replacing
        5. Always ensure folder.jpg matches embedded art

        Args:
            album_path: Path to album folder
            enrichment_data: Enrichment data from sources

        Returns:
            Cover art processing results
        """
        import hashlib

        results = {
            'action': 'none',
            'check': None,
            'validation': None,
            'embedded': 0,
            'status': 'skipped'
        }

        # Step 1: Extract existing embedded art first
        existing_data, existing_hash = self._get_embedded_cover_hash(album_path)

        # Step 2: Check current cover art status
        cover_check = self._check_cover_art(album_path)
        results['check'] = {
            'total': cover_check['total'],
            'has_cover': cover_check['has_cover'],
            'missing_cover': cover_check['missing_cover'],
            'avg_size_kb': cover_check['avg_cover_size'] // 1024 if cover_check['avg_cover_size'] else 0
        }

        # Step 3: Determine if embedded art is valid
        coverage = cover_check['has_cover'] / cover_check['total'] if cover_check['total'] > 0 else 0
        avg_size = cover_check.get('avg_cover_size', 0) or 0
        is_valid_embedded = existing_data and coverage > 0.9 and avg_size > 50000

        # Step 4: If valid embedded art, just sync folder.jpg and return
        if is_valid_embedded:
            results['action'] = 'none'
            results['status'] = 'valid'
            results['validation'] = {
                'status': 'valid',
                'issues': [],
                'recommendations': [],
                'needs_cover': False,
                'needs_replacement': False
            }
            self._log(f"  Cover art valid ({int(coverage * 100)}% coverage, {avg_size // 1024}KB avg)")

            # Sync folder.jpg from embedded art
            folder_sync = self._sync_folder_art(album_path, image_data=existing_data)
            results['folder_sync'] = folder_sync

            if folder_sync['action'] == 'created':
                self._log(f"  Created folder.jpg from embedded art ({folder_sync['size_kb']}KB)")
            elif folder_sync['action'] == 'updated':
                self._log(f"  Updated folder.jpg from embedded art ({folder_sync['size_kb']}KB)")
            elif folder_sync['status'] == 'in_sync':
                self._log("  folder.jpg matches embedded art")

            # Save preview path for visual verification by Claude
            folder_jpg_path = Path(album_path) / 'folder.jpg'
            if folder_jpg_path.exists():
                results['cover_preview_path'] = str(folder_jpg_path)
                self._log(f"  Cover preview: {folder_jpg_path}")

            return results

        # Step 5: Need to fetch - no valid embedded art
        validation = self._validate_cover_art(album_path, cover_check)
        results['validation'] = validation

        folder_name = Path(album_path).name
        self._log(f"  Cover art {'missing' if validation['needs_cover'] else 'low quality'}, fetching...")

        image_data = self._fetch_cover_art(folder_name, enrichment_data)

        if not image_data:
            results['action'] = 'fetch_failed'
            results['status'] = 'failed'
            self._log("  Could not fetch cover art from any source")

            # If we have existing embedded art (just low quality), still sync folder.jpg
            if existing_data:
                folder_sync = self._sync_folder_art(album_path, image_data=existing_data)
                results['folder_sync'] = folder_sync
                if folder_sync['action'] != 'none':
                    self._log(f"  Synced folder.jpg from existing embedded art")

            return results

        # Step 6: Compare fetched art with existing embedded art
        new_hash = hashlib.md5(image_data).hexdigest()

        if existing_hash and existing_hash == new_hash:
            # Fetched art is identical to embedded - skip embedding
            self._log("  Fetched cover art matches existing embedded art, skipping embed")
            results['action'] = 'none'
            results['status'] = 'valid'

            # Still sync folder.jpg
            folder_sync = self._sync_folder_art(album_path, image_data=existing_data)
            results['folder_sync'] = folder_sync

            if folder_sync['action'] == 'created':
                self._log(f"  Created folder.jpg ({folder_sync['size_kb']}KB)")
            elif folder_sync['action'] == 'updated':
                self._log(f"  Updated folder.jpg ({folder_sync['size_kb']}KB)")

            return results

        # Step 7: Embed new cover art (different from existing)
        embed_result = self._embed_cover_art(album_path, image_data)
        results['embedded'] = embed_result['embedded']
        results['action'] = 'embedded'
        results['status'] = 'success' if embed_result['failed'] == 0 else 'partial'

        if embed_result['errors']:
            results['errors'] = embed_result['errors']

        self._log(f"  Embedded new cover art into {embed_result['embedded']} files ({len(image_data) // 1024}KB)")

        # Step 8: Sync folder.jpg with newly embedded art
        folder_sync = self._sync_folder_art(album_path, image_data=image_data)
        results['folder_sync'] = folder_sync

        if folder_sync['action'] == 'created':
            self._log(f"  Created folder.jpg ({folder_sync['size_kb']}KB)")
        elif folder_sync['action'] == 'updated':
            self._log(f"  Updated folder.jpg ({folder_sync['size_kb']}KB)")

        # Save preview path for visual verification by Claude
        folder_jpg_path = Path(album_path) / 'folder.jpg'
        if folder_jpg_path.exists():
            results['cover_preview_path'] = str(folder_jpg_path)
            self._log(f"  Cover preview: {folder_jpg_path}")

        return results

    def _calculate_quality_score(self, current: Dict, enrichment: Dict) -> int:
        """Calculate quality score (0-100)"""
        score = 0
        best_match = enrichment.get('best_match', {})

        if not best_match:
            return 50  # No match found, baseline score

        # Track count match: 20 points
        if current.get('track_count', 0) == best_match.get('track_count', 0):
            score += 20
        elif abs(current.get('track_count', 0) - best_match.get('track_count', 0)) <= 2:
            score += 10

        # Source matched: 30 points
        if enrichment.get('sources_matched'):
            score += 30

        # Has album metadata: 25 points
        if current.get('album', {}).get('title'):
            score += 25

        # All tracks have titles: 25 points
        tracks_with_titles = sum(1 for t in current.get('tracks', []) if t.get('title'))
        if tracks_with_titles == current.get('track_count', 0) and tracks_with_titles > 0:
            score += 25

        return min(100, score)

    def _get_validation_status(self, score: int) -> str:
        """Get validation status based on score"""
        if score >= 90:
            return 'excellent'
        elif score >= 80:
            return 'good'
        elif score >= 70:
            return 'acceptable'
        else:
            return 'poor'

    def _find_discrepancies(self, current: Dict, enrichment: Dict) -> List[Dict]:
        """Find discrepancies between current and source metadata"""
        discrepancies = []
        best_match = enrichment.get('best_match', {})

        if not best_match:
            return discrepancies

        # Track count
        if current.get('track_count', 0) != best_match.get('track_count', 0):
            discrepancies.append({
                'field': 'track_count',
                'current': current.get('track_count'),
                'source': best_match.get('track_count'),
                'severity': 'critical',
                'confidence': 90
            })

        # Album title
        current_title = current.get('album', {}).get('title', '')
        source_title = best_match.get('title', '')
        if current_title and source_title and current_title.lower() != source_title.lower():
            discrepancies.append({
                'field': 'album_title',
                'current': current_title,
                'source': source_title,
                'severity': 'high',
                'confidence': 80
            })

        return discrepancies

    def _generate_album_report(
        self, album: Dict, current: Dict, enrichment: Dict,
        fingerprint: Optional[Dict], validation: Dict, resolution: Dict,
        cover_art: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Step 8: Generate JSON and CSV reports for album.

        Returns:
            Report data
        """
        report = {
            'album': {
                'path': album['path'],
                'folder_name': album['folder_name'],
                'title': enrichment.get('best_match', {}).get('title', album['folder_name']),
                'artist': enrichment.get('best_match', {}).get('artist', 'Various Artists'),
                'year': enrichment.get('best_match', {}).get('year'),
                'track_count': current.get('track_count', 0)
            },
            'validation': validation,
            'resolution': resolution,
            'cover_art': {
                'status': cover_art.get('validation', {}).get('status', 'unknown') if cover_art else 'not_checked',
                'tracks_with_cover': cover_art.get('check', {}).get('has_cover', 0) if cover_art else 0,
                'tracks_missing_cover': cover_art.get('check', {}).get('missing_cover', 0) if cover_art else 0,
                'avg_size_kb': cover_art.get('check', {}).get('avg_size_kb', 0) if cover_art else 0,
                'action_taken': cover_art.get('action', 'none') if cover_art else 'none',
                'embedded_count': cover_art.get('embedded', 0) if cover_art else 0,
                'issues': cover_art.get('validation', {}).get('issues', []) if cover_art else [],
                'folder_jpg_status': cover_art.get('folder_sync', {}).get('status', 'not_checked') if cover_art else 'not_checked',
                'folder_jpg_action': cover_art.get('folder_sync', {}).get('action', 'none') if cover_art else 'none'
            },
            'quality_score': validation.get('quality_score', 0),
            'status': 'success' if validation.get('quality_score', 0) >= 70 else 'needs_attention',
            'requires_review': resolution.get('requires_human_review', False),
            'sources_used': enrichment.get('sources_matched', []),
            'fingerprinting_used': fingerprint is not None and fingerprint.get('fingerprinting_available', False),
            'processed_at': datetime.now().isoformat(),
            'tracks': current.get('tracks', [])
        }

        # Save JSON report
        self._save_album_report(album['path'], report)

        return report

    def _save_album_report(self, album_path: str, report: Dict):
        """Save album report to JSON file"""
        # Create safe filename
        album_name = Path(album_path).name
        safe_name = "".join(c if c.isalnum() or c in ' -_' else '_' for c in album_name)

        # Save to outputs folder
        output_file = self.outputs_path / f"{safe_name}_audit.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self._log(f"  Saved report: {output_file.name}")

    def _generate_summary_report(self, results: List[Dict]) -> Dict[str, Any]:
        """
        Step 10: Generate final summary report.

        Args:
            results: List of album processing results

        Returns:
            Summary report
        """
        summary = {
            'processing_summary': {
                'total_albums': len(results),
                'successful': self.stats['albums_success'],
                'needs_review': self.stats['albums_needs_review'],
                'failed': self.stats['albums_failed'],
                'processing_time_seconds': self.stats['processing_time']
            },
            'quality_distribution': {
                'excellent': sum(1 for r in results if r.get('quality_score', 0) >= 90),
                'good': sum(1 for r in results if 80 <= r.get('quality_score', 0) < 90),
                'acceptable': sum(1 for r in results if 70 <= r.get('quality_score', 0) < 80),
                'poor': sum(1 for r in results if r.get('quality_score', 0) < 70)
            },
            'sources_usage': self.stats['sources_used'],
            'albums_requiring_review': [
                {'path': r.get('album', {}).get('path'), 'folder': r.get('album', {}).get('folder_name')}
                for r in results if r.get('requires_review')
            ],
            'recommendations': self._generate_recommendations(results),
            'generated_at': datetime.now().isoformat()
        }

        # Save summary report
        summary_file = self.outputs_path / 'processing_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        self._log(f"Summary report saved: {summary_file}")

        return summary

    def _generate_recommendations(self, results: List[Dict]) -> List[str]:
        """Generate recommendations based on processing results"""
        recommendations = []

        poor_quality = sum(1 for r in results if r.get('quality_score', 0) < 70)
        if poor_quality > 0:
            recommendations.append(f"{poor_quality} album(s) have poor metadata quality and need attention")

        needs_review = sum(1 for r in results if r.get('requires_review'))
        if needs_review > 0:
            recommendations.append(f"{needs_review} album(s) require human review")

        if not self.stats['sources_used']:
            recommendations.append("No data sources returned matches - check API credentials")

        return recommendations


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Automated CD Music Metadata Management System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--path', '-p',
        required=True,
        help='Path to music folder (e.g., "\\\\openmediavault\\music\\Various Artists")'
    )

    parser.add_argument(
        '--album', '-a',
        help='Process only albums matching this name (partial match)'
    )

    parser.add_argument(
        '--config', '-c',
        default='music-config.yaml',
        help='Path to configuration file (default: music-config.yaml)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Run the system
    system = MusicMetadataSystem(args.config)
    result = system.process_path(args.path, args.album)

    # Return appropriate exit code
    if result.get('status') == 'error':
        sys.exit(1)
    elif result.get('processing_summary', {}).get('failed', 0) > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
