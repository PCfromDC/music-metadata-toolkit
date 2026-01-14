#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fixer Agent - Applies corrections to albums.

Responsibilities:
- Update metadata fields (title, artist, genre)
- Embed cover art into audio files
- Rename folders (Windows-safe)
- Backup before modifying
- Verify changes after applying
"""

import os
import re
import shutil
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, APIC

from .base import BaseAgent


@dataclass
class FixResult:
    """Result of fix operation"""
    album_path: str
    album_id: str
    success: bool = False
    changes_made: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    new_path: Optional[str] = None  # If renamed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "album_path": self.album_path,
            "album_id": self.album_id,
            "success": self.success,
            "changes_made": self.changes_made,
            "errors": self.errors,
            "new_path": self.new_path
        }


class FixerAgent(BaseAgent):
    """
    Fixer agent for applying corrections to albums.

    Handles metadata updates, cover art embedding, and folder renaming.
    Includes backup and verification steps.
    """

    # Characters not allowed in Windows filenames
    INVALID_CHARS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']

    def __init__(self, config, state):
        super().__init__(config, state)

        # Settings from config
        self.backup_enabled = config.get('library.backup_enabled', True)
        self.backup_path = config.get('library.backup_path', 'D:/music_backup')
        self.colon_replacement = config.get('naming.replace_colon_with', ' -')
        self.max_path_length = config.get('naming.max_path_length', 250)

    @property
    def name(self) -> str:
        return "Fixer"

    def process(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process fixes for a single album.

        Args:
            item: Dictionary with album path and corrections

        Returns:
            Fix results
        """
        album_path = item.get('path')
        corrections = item.get('corrections', [])
        dry_run = item.get('dry_run', False)

        if not album_path:
            return {"status": "error", "error": "No path provided"}

        if not corrections:
            return {"status": "skipped", "reason": "No corrections to apply"}

        try:
            result = self.apply_fixes(album_path, corrections, dry_run=dry_run)

            # Save state
            status = "FIXED" if result.success else "FIX_FAILED"
            self.save_state(album_path, status, result.to_dict())

            return {
                "status": "success" if result.success else "partial",
                "path": result.new_path or album_path,
                "changes_made": len(result.changes_made),
                "errors": len(result.errors),
                "data": result.to_dict()
            }

        except Exception as e:
            self.log_error(f"Error fixing {album_path}: {e}")
            return {
                "status": "error",
                "path": album_path,
                "error": str(e)
            }

    def apply_fixes(
        self,
        album_path: str,
        corrections: List[Dict[str, Any]],
        dry_run: bool = False
    ) -> FixResult:
        """
        Apply corrections to an album.

        Args:
            album_path: Path to album folder
            corrections: List of corrections to apply
            dry_run: If True, only preview changes

        Returns:
            FixResult with changes made and errors
        """
        result = FixResult(
            album_path=album_path,
            album_id=self.state.get_album_id(album_path)
        )

        if dry_run:
            self.log(f"[DRY RUN] Would apply {len(corrections)} corrections to {album_path}")
            for c in corrections:
                self.log(f"  - {c.get('type')}: {c.get('field')}")
                result.changes_made.append({
                    "type": c.get('type'),
                    "field": c.get('field'),
                    "status": "would_apply"
                })
            result.success = True
            return result

        # Backup if enabled
        if self.backup_enabled:
            backup_path = self._create_backup(album_path)
            if backup_path:
                self.log(f"Backup created: {backup_path}")

        current_path = album_path

        # Apply each correction
        for correction in corrections:
            try:
                change = self._apply_correction(current_path, correction)
                if change:
                    result.changes_made.append(change)

                    # Track if path changed
                    if change.get('new_path'):
                        current_path = change['new_path']
                        result.new_path = current_path

            except Exception as e:
                error_msg = f"{correction.get('type')}: {str(e)}"
                result.errors.append(error_msg)
                self.log_error(error_msg)

        result.success = len(result.errors) == 0
        return result

    def _apply_correction(
        self,
        album_path: str,
        correction: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Apply a single correction"""
        correction_type = correction.get('type')
        field = correction.get('field')

        if correction_type in ['formatting_only', 'title_mismatch'] and field == 'title':
            return self._rename_folder(album_path, correction.get('suggested'))

        elif correction_type == 'missing_cover' and field == 'cover_art':
            return self._embed_cover_art(album_path, correction.get('suggested'))

        elif field == 'genre':
            return self._update_genre(album_path, correction.get('suggested'))

        else:
            self.log(f"Unknown correction type: {correction_type}")
            return None

    def _rename_folder(self, album_path: str, new_name: str) -> Optional[Dict[str, Any]]:
        """
        Rename album folder with Windows-safe name.

        Args:
            album_path: Current folder path
            new_name: New folder name

        Returns:
            Change record or None
        """
        if not new_name:
            return None

        path = Path(album_path)
        old_name = path.name

        # Make Windows-safe
        safe_name = self._make_windows_safe(new_name)

        if safe_name == old_name:
            self.log(f"  Folder name already correct: {old_name}")
            return None

        new_path = path.parent / safe_name

        # Check if target exists
        if new_path.exists():
            self.log(f"  Target already exists: {new_path}")
            return None

        # Check path length
        if len(str(new_path)) > self.max_path_length:
            self.log(f"  Path too long: {len(str(new_path))} chars")
            return None

        try:
            os.rename(album_path, new_path)
            self.log(f"  Renamed: {old_name} -> {safe_name}")

            return {
                "type": "rename",
                "field": "folder_name",
                "old_value": old_name,
                "new_value": safe_name,
                "new_path": str(new_path),
                "status": "applied"
            }

        except OSError as e:
            raise Exception(f"Rename failed: {e}")

    def _make_windows_safe(self, name: str) -> str:
        """Make filename safe for Windows"""
        # Replace colons
        name = name.replace(':', self.colon_replacement)

        # Remove other invalid characters
        for char in self.INVALID_CHARS:
            if char != ':':  # Already handled
                name = name.replace(char, '')

        # Clean up extra spaces
        name = ' '.join(name.split())

        # Limit length
        if len(name) > 200:
            name = name[:200].strip()

        return name

    def _embed_cover_art(self, album_path: str, cover_url: str) -> Optional[Dict[str, Any]]:
        """
        Download and embed cover art into all audio files.

        Args:
            album_path: Path to album folder
            cover_url: URL to cover art image

        Returns:
            Change record or None
        """
        if not cover_url:
            return None

        self.log(f"  Downloading cover art...")

        # Download image
        try:
            response = requests.get(cover_url, timeout=60)
            response.raise_for_status()
            image_data = response.content

            # Detect image type
            if response.headers.get('content-type', '').startswith('image/png'):
                mime_type = 'image/png'
            else:
                mime_type = 'image/jpeg'

        except requests.RequestException as e:
            raise Exception(f"Download failed: {e}")

        # Embed in all audio files
        path = Path(album_path)
        audio_files = list(path.glob('*.mp3')) + list(path.glob('*.m4a')) + list(path.glob('*.flac'))

        embedded_count = 0
        for audio_file in audio_files:
            try:
                self._embed_cover_in_file(audio_file, image_data, mime_type)
                embedded_count += 1
            except Exception as e:
                self.log(f"    Failed to embed in {audio_file.name}: {e}")

        # Also save as folder.jpg
        folder_jpg = path / 'folder.jpg'
        try:
            with open(folder_jpg, 'wb') as f:
                f.write(image_data)
            self.log(f"  Saved folder.jpg")
        except:
            pass

        self.log(f"  Embedded cover in {embedded_count}/{len(audio_files)} files")

        return {
            "type": "cover_art",
            "field": "cover_art",
            "old_value": None,
            "new_value": f"embedded in {embedded_count} files",
            "source_url": cover_url,
            "status": "applied"
        }

    def _embed_cover_in_file(self, filepath: Path, image_data: bytes, mime_type: str) -> None:
        """Embed cover art in a single audio file"""
        ext = filepath.suffix.lower()

        if ext == '.mp3':
            self._embed_cover_mp3(filepath, image_data, mime_type)
        elif ext == '.m4a':
            self._embed_cover_m4a(filepath, image_data)
        elif ext == '.flac':
            self._embed_cover_flac(filepath, image_data, mime_type)

    def _embed_cover_mp3(self, filepath: Path, image_data: bytes, mime_type: str) -> None:
        """Embed cover in MP3 file"""
        try:
            audio = MP3(str(filepath))
            if audio.tags is None:
                audio.add_tags()
        except:
            audio = MP3(str(filepath))
            audio.add_tags()

        # Remove existing cover art
        audio.tags.delall('APIC')

        # Add new cover
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

    def _embed_cover_m4a(self, filepath: Path, image_data: bytes) -> None:
        """Embed cover in M4A file"""
        audio = MP4(str(filepath))

        # Detect format
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            cover = MP4Cover(image_data, imageformat=MP4Cover.FORMAT_PNG)
        else:
            cover = MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)

        audio.tags['covr'] = [cover]
        audio.save()

    def _embed_cover_flac(self, filepath: Path, image_data: bytes, mime_type: str) -> None:
        """Embed cover in FLAC file"""
        audio = FLAC(str(filepath))

        # Create picture
        picture = Picture()
        picture.type = 3  # Front cover
        picture.mime = mime_type
        picture.desc = 'Cover'
        picture.data = image_data

        # Remove existing pictures and add new
        audio.clear_pictures()
        audio.add_picture(picture)
        audio.save()

    def _update_genre(self, album_path: str, new_genre: str) -> Optional[Dict[str, Any]]:
        """Update genre for all tracks in album"""
        if not new_genre:
            return None

        path = Path(album_path)
        audio_files = list(path.glob('*.mp3')) + list(path.glob('*.m4a')) + list(path.glob('*.flac'))

        updated_count = 0
        for audio_file in audio_files:
            try:
                ext = audio_file.suffix.lower()
                if ext == '.mp3':
                    audio = MP3(str(audio_file), ID3=EasyID3)
                    audio['genre'] = new_genre
                    audio.save()
                elif ext == '.m4a':
                    audio = MP4(str(audio_file))
                    audio.tags['\xa9gen'] = [new_genre]
                    audio.save()
                elif ext == '.flac':
                    audio = FLAC(str(audio_file))
                    audio['genre'] = new_genre
                    audio.save()
                updated_count += 1
            except Exception as e:
                self.log(f"    Failed to update genre in {audio_file.name}: {e}")

        self.log(f"  Updated genre to '{new_genre}' in {updated_count} files")

        return {
            "type": "genre",
            "field": "genre",
            "old_value": None,
            "new_value": new_genre,
            "files_updated": updated_count,
            "status": "applied"
        }

    def _create_backup(self, album_path: str) -> Optional[str]:
        """Create backup of album folder"""
        try:
            path = Path(album_path)
            backup_dir = Path(self.backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create backup with timestamp
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{path.name}_{timestamp}"
            backup_path = backup_dir / backup_name

            # Copy folder
            shutil.copytree(album_path, backup_path)

            return str(backup_path)

        except Exception as e:
            self.log(f"  Backup failed: {e}")
            return None

    def sync_filenames_to_titles(self, album_path: str) -> Dict[str, Any]:
        """
        Rename audio files to match their metadata titles.

        Format: {track_number} {title}.{ext}

        Args:
            album_path: Path to album folder

        Returns:
            Dictionary with rename results
        """
        path = Path(album_path)
        audio_files = (
            list(path.glob('*.mp3')) +
            list(path.glob('*.m4a')) +
            list(path.glob('*.flac')) +
            list(path.glob('*.ogg')) +
            list(path.glob('*.wav'))
        )

        results = {
            'renamed': 0,
            'skipped': 0,
            'errors': [],
            'changes': []
        }

        for audio_file in sorted(audio_files):
            try:
                # Read metadata
                ext = audio_file.suffix.lower()
                title = None
                track_num = None

                if ext == '.mp3':
                    audio = EasyID3(str(audio_file))
                    title = audio.get('title', [None])[0]
                    track_num = audio.get('tracknumber', [''])[0].split('/')[0]
                elif ext == '.m4a':
                    audio = MP4(str(audio_file))
                    title = audio.get('\xa9nam', [None])[0]
                    track_info = audio.get('trkn', [(None, None)])[0]
                    track_num = str(track_info[0]) if track_info[0] else None
                elif ext == '.flac':
                    audio = FLAC(str(audio_file))
                    title = audio.get('title', [None])[0]
                    track_num = audio.get('tracknumber', [''])[0].split('/')[0]

                if not title:
                    results['skipped'] += 1
                    continue

                # Format track number
                if track_num:
                    track_num = track_num.zfill(2)
                else:
                    track_num = '00'

                # Create safe filename
                safe_title = self._make_filename_safe(title)
                new_name = f'{track_num} {safe_title}{ext}'
                new_path = path / new_name

                # Skip if already correct
                if audio_file.name == new_name:
                    results['skipped'] += 1
                    continue

                # Check if target exists (and is different file)
                if new_path.exists() and new_path != audio_file:
                    results['errors'].append(f"Target exists: {new_name}")
                    continue

                # Rename
                os.rename(str(audio_file), str(new_path))
                results['renamed'] += 1
                results['changes'].append({
                    'old': audio_file.name,
                    'new': new_name
                })
                self.log(f"  Renamed: {audio_file.name} -> {new_name}")

            except Exception as e:
                results['errors'].append(f"{audio_file.name}: {str(e)}")

        return results

    def _make_filename_safe(self, name: str) -> str:
        """
        Make a string safe for use as a filename.

        Args:
            name: Original string

        Returns:
            Safe filename string
        """
        # Replace problematic characters
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

        # Clean up multiple spaces
        name = ' '.join(name.split())

        # Limit length (leave room for track number and extension)
        if len(name) > 200:
            name = name[:200].strip()

        return name
