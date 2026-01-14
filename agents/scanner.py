#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scanner Agent - Discovers and catalogs albums in the music library.

Responsibilities:
- Traverse directory structure
- Extract metadata from audio files (MP3, M4A, FLAC)
- Detect embedded cover art
- Identify multi-disc sets
- Flag potential issues (missing metadata, truncated names)
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4

from .base import BaseAgent


@dataclass
class TrackData:
    """Scanned track information"""
    filepath: str
    filename: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    year: Optional[str] = None
    genre: Optional[str] = None
    has_cover: bool = False
    duration_ms: Optional[int] = None
    issues: List[str] = field(default_factory=list)


@dataclass
class AlbumData:
    """Scanned album information"""
    path: str
    folder_name: str
    album_id: str
    tracks: List[TrackData] = field(default_factory=list)
    has_cover: bool = False
    cover_source: Optional[str] = None  # 'embedded', 'folder.jpg', etc.
    is_multi_disc: bool = False
    disc_count: int = 1
    issues: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    @property
    def artist(self) -> Optional[str]:
        """Get most common artist across tracks"""
        artists = [t.album_artist or t.artist for t in self.tracks if t.album_artist or t.artist]
        if artists:
            from collections import Counter
            return Counter(artists).most_common(1)[0][0]
        return None

    @property
    def title(self) -> Optional[str]:
        """Get album title from tracks or folder name"""
        albums = [t.album for t in self.tracks if t.album]
        if albums:
            from collections import Counter
            return Counter(albums).most_common(1)[0][0]
        return self.folder_name

    @property
    def year(self) -> Optional[str]:
        """Get year from tracks"""
        years = [t.year for t in self.tracks if t.year]
        if years:
            return years[0]
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "album_id": self.album_id,
            "path": self.path,
            "folder_name": self.folder_name,
            "title": self.title,
            "artist": self.artist,
            "year": self.year,
            "track_count": self.track_count,
            "has_cover": self.has_cover,
            "cover_source": self.cover_source,
            "is_multi_disc": self.is_multi_disc,
            "disc_count": self.disc_count,
            "issues": self.issues,
            "tracks": [
                {
                    "filename": t.filename,
                    "title": t.title,
                    "track_number": t.track_number,
                    "disc_number": t.disc_number,
                    "artist": t.artist,
                    "has_cover": t.has_cover,
                    "issues": t.issues
                }
                for t in self.tracks
            ]
        }


class ScannerAgent(BaseAgent):
    """
    Scanner agent for discovering and cataloging albums.

    Scans directories for audio files, extracts metadata,
    and identifies issues that need attention.
    """

    AUDIO_EXTENSIONS = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wav', '.wma', '.aac'}
    COVER_FILENAMES = ['cover.jpg', 'cover.png', 'folder.jpg', 'folder.png',
                       'album.jpg', 'album.png', 'front.jpg', 'front.png']

    def __init__(self, config, state):
        super().__init__(config, state)

    @property
    def name(self) -> str:
        return "Scanner"

    def process(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single album directory.

        Args:
            item: Dictionary with 'path' key pointing to album folder

        Returns:
            Scan results including tracks and issues
        """
        album_path = item.get('path')
        if not album_path:
            return {"status": "error", "error": "No path provided"}

        try:
            album_data = self.scan_album(album_path)

            # Save state
            self.save_state(album_path, "SCANNED", album_data.to_dict())

            return {
                "status": "success",
                "path": album_path,
                "album_id": album_data.album_id,
                "track_count": album_data.track_count,
                "has_cover": album_data.has_cover,
                "issue_count": len(album_data.issues),
                "data": album_data.to_dict()
            }

        except Exception as e:
            self.log_error(f"Error scanning {album_path}: {e}")
            return {
                "status": "error",
                "path": album_path,
                "error": str(e)
            }

    def scan_album(self, album_path: str) -> AlbumData:
        """
        Scan a single album directory.

        Args:
            album_path: Path to album folder

        Returns:
            AlbumData with tracks and metadata
        """
        path = Path(album_path)
        folder_name = path.name
        album_id = self._generate_album_id(album_path)

        album = AlbumData(
            path=album_path,
            folder_name=folder_name,
            album_id=album_id
        )

        # Check for folder cover art
        folder_cover = self._check_folder_cover(path)
        if folder_cover:
            album.has_cover = True
            album.cover_source = folder_cover

        # Scan audio files
        audio_files = self._find_audio_files(path)

        for audio_file in sorted(audio_files):
            track = self._extract_track_metadata(audio_file)
            album.tracks.append(track)

            # Check if track has embedded cover
            if track.has_cover and not album.has_cover:
                album.has_cover = True
                album.cover_source = "embedded"

        # Detect multi-disc
        album.is_multi_disc, album.disc_count = self._detect_multi_disc(album.tracks)

        # Identify issues
        album.issues = self._identify_issues(album)

        return album

    def scan_artist(self, artist_path: str) -> List[AlbumData]:
        """
        Scan all albums for an artist.

        Args:
            artist_path: Path to artist folder

        Returns:
            List of AlbumData for each album found
        """
        path = Path(artist_path)
        albums = []

        for item in path.iterdir():
            if item.is_dir():
                # Check if it contains audio files
                audio_files = self._find_audio_files(item)
                if audio_files:
                    self.log(f"Scanning: {item.name}")
                    album = self.scan_album(str(item))
                    albums.append(album)

        return albums

    def scan_library(self, library_path: str) -> Dict[str, List[AlbumData]]:
        """
        Scan entire music library.

        Args:
            library_path: Root path of music library

        Returns:
            Dictionary of artist -> albums
        """
        path = Path(library_path)
        library = {}

        for artist_dir in path.iterdir():
            if artist_dir.is_dir():
                artist_name = artist_dir.name
                self.log(f"Scanning artist: {artist_name}")
                albums = self.scan_artist(str(artist_dir))
                if albums:
                    library[artist_name] = albums

        return library

    def _find_audio_files(self, path: Path) -> List[Path]:
        """Find all audio files in directory (non-recursive)"""
        files = []
        for item in path.iterdir():
            if item.is_file() and item.suffix.lower() in self.AUDIO_EXTENSIONS:
                files.append(item)
        return files

    def _extract_track_metadata(self, filepath: Path) -> TrackData:
        """Extract metadata from a single audio file"""
        track = TrackData(
            filepath=str(filepath),
            filename=filepath.name
        )

        try:
            ext = filepath.suffix.lower()

            if ext == '.mp3':
                track = self._extract_mp3_metadata(filepath, track)
            elif ext == '.flac':
                track = self._extract_flac_metadata(filepath, track)
            elif ext in ['.m4a', '.mp4']:
                track = self._extract_m4a_metadata(filepath, track)
            else:
                track = self._extract_generic_metadata(filepath, track)

            # Check for embedded cover
            track.has_cover = self._has_embedded_cover(filepath)

            # Identify track issues
            track.issues = self._identify_track_issues(track)

        except Exception as e:
            track.issues.append(f"read_error: {str(e)}")

        return track

    def _extract_mp3_metadata(self, filepath: Path, track: TrackData) -> TrackData:
        """Extract metadata from MP3 file"""
        try:
            audio = MP3(str(filepath), ID3=EasyID3)
            track.title = self._get_first(audio.get('title'))
            track.artist = self._get_first(audio.get('artist'))
            track.album = self._get_first(audio.get('album'))
            track.album_artist = self._get_first(audio.get('albumartist'))
            track.year = self._get_first(audio.get('date'))
            track.genre = self._get_first(audio.get('genre'))
            track.track_number = self._parse_track_number(audio.get('tracknumber'))
            track.disc_number = self._parse_track_number(audio.get('discnumber')) or 1
            track.duration_ms = int(audio.info.length * 1000) if audio.info else None
        except Exception:
            # Fallback to generic
            track = self._extract_generic_metadata(filepath, track)
        return track

    def _extract_flac_metadata(self, filepath: Path, track: TrackData) -> TrackData:
        """Extract metadata from FLAC file"""
        audio = FLAC(str(filepath))
        track.title = self._get_first(audio.get('title'))
        track.artist = self._get_first(audio.get('artist'))
        track.album = self._get_first(audio.get('album'))
        track.album_artist = self._get_first(audio.get('albumartist'))
        track.year = self._get_first(audio.get('date'))
        track.genre = self._get_first(audio.get('genre'))
        track.track_number = self._parse_track_number(audio.get('tracknumber'))
        track.disc_number = self._parse_track_number(audio.get('discnumber')) or 1
        track.duration_ms = int(audio.info.length * 1000) if audio.info else None
        return track

    def _extract_m4a_metadata(self, filepath: Path, track: TrackData) -> TrackData:
        """Extract metadata from M4A/MP4 file"""
        audio = MP4(str(filepath))
        if audio.tags:
            track.title = self._get_first(audio.tags.get('\xa9nam'))
            track.artist = self._get_first(audio.tags.get('\xa9ART'))
            track.album = self._get_first(audio.tags.get('\xa9alb'))
            track.album_artist = self._get_first(audio.tags.get('aART'))
            track.year = self._get_first(audio.tags.get('\xa9day'))
            track.genre = self._get_first(audio.tags.get('\xa9gen'))

            # Track number is tuple (track, total)
            trkn = audio.tags.get('trkn', [(None, None)])[0]
            track.track_number = trkn[0] if isinstance(trkn, tuple) else None

            # Disc number
            disk = audio.tags.get('disk', [(1, 1)])[0]
            track.disc_number = disk[0] if isinstance(disk, tuple) else 1

        track.duration_ms = int(audio.info.length * 1000) if audio.info else None
        return track

    def _extract_generic_metadata(self, filepath: Path, track: TrackData) -> TrackData:
        """Extract metadata using generic mutagen interface"""
        audio = mutagen.File(str(filepath), easy=True)
        if audio:
            track.title = self._get_first(audio.get('title'))
            track.artist = self._get_first(audio.get('artist'))
            track.album = self._get_first(audio.get('album'))
            track.track_number = self._parse_track_number(audio.get('tracknumber'))
        return track

    def _has_embedded_cover(self, filepath: Path) -> bool:
        """Check if file has embedded cover art"""
        try:
            ext = filepath.suffix.lower()
            if ext == '.mp3':
                audio = MP3(str(filepath))
                if audio.tags:
                    for tag in audio.tags.values():
                        if hasattr(tag, 'mime') and hasattr(tag, 'data'):
                            return True
            elif ext == '.flac':
                audio = FLAC(str(filepath))
                return bool(audio.pictures)
            elif ext in ['.m4a', '.mp4']:
                audio = MP4(str(filepath))
                return 'covr' in (audio.tags or {})
        except:
            pass
        return False

    def _check_folder_cover(self, path: Path) -> Optional[str]:
        """Check for cover art file in folder"""
        for cover_name in self.COVER_FILENAMES:
            cover_path = path / cover_name
            if cover_path.exists():
                return cover_name
        return None

    def _detect_multi_disc(self, tracks: List[TrackData]) -> Tuple[bool, int]:
        """Detect if album is multi-disc"""
        disc_numbers = set(t.disc_number for t in tracks if t.disc_number)
        if len(disc_numbers) > 1:
            return True, max(disc_numbers)
        return False, 1

    def _identify_issues(self, album: AlbumData) -> List[Dict[str, Any]]:
        """Identify issues with album"""
        issues = []

        # No cover art
        if not album.has_cover:
            issues.append({
                "type": "missing_cover",
                "severity": "medium",
                "message": "Album has no cover art"
            })

        # Truncated folder name
        if len(album.folder_name) >= 50 and album.folder_name.endswith('...'):
            issues.append({
                "type": "truncated_name",
                "severity": "low",
                "message": f"Folder name appears truncated: {album.folder_name}"
            })

        # Inconsistent metadata
        album_names = set(t.album for t in album.tracks if t.album)
        if len(album_names) > 1:
            issues.append({
                "type": "inconsistent_album",
                "severity": "medium",
                "message": f"Multiple album names found: {album_names}"
            })

        # Missing genre
        genres = [t.genre for t in album.tracks if t.genre]
        if not genres:
            issues.append({
                "type": "missing_genre",
                "severity": "low",
                "message": "No genre metadata found"
            })

        # Track count issues
        track_numbers = [t.track_number for t in album.tracks if t.track_number]
        if track_numbers:
            expected = set(range(1, max(track_numbers) + 1))
            actual = set(track_numbers)
            missing = expected - actual
            if missing:
                issues.append({
                    "type": "missing_tracks",
                    "severity": "medium",
                    "message": f"Missing track numbers: {sorted(missing)}"
                })

        return issues

    def _identify_track_issues(self, track: TrackData) -> List[str]:
        """Identify issues with individual track"""
        issues = []

        if not track.title:
            issues.append("missing_title")
        if not track.artist and not track.album_artist:
            issues.append("missing_artist")
        if not track.track_number:
            issues.append("missing_track_number")

        return issues

    def _get_first(self, value) -> Optional[str]:
        """Get first element from list or return string"""
        if isinstance(value, list):
            return value[0] if value else None
        return value

    def _parse_track_number(self, value) -> Optional[int]:
        """Parse track number from various formats"""
        if not value:
            return None

        if isinstance(value, list):
            value = value[0]

        if isinstance(value, int):
            return value

        value = str(value)

        # Handle "1/11" format
        if '/' in value:
            value = value.split('/')[0]

        try:
            return int(value)
        except ValueError:
            return None

    def _generate_album_id(self, path: str) -> str:
        """Generate consistent album ID from path"""
        return hashlib.md5(path.encode('utf-8')).hexdigest()[:12]
