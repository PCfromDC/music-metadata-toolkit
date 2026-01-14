#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music Library Orchestrator - Main orchestration class.

Provides a programmatic interface to run the full cleanup pipeline:
    Scan -> Validate -> Review -> Fix -> Verify

Usage:
    from orchestrator import MusicLibraryOrchestrator

    orch = MusicLibraryOrchestrator('music-config.yaml')
    orch.init('/path/to/music')
    orch.scan_artist('Various Artists')
    orch.validate()
    orch.fix(dry_run=True)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from .config import ConfigManager
from .state import StateStore
from .queue import QueueManager, AlbumStatus, Priority

from agents import ScannerAgent, ValidatorAgent, FixerAgent


class MusicLibraryOrchestrator:
    """
    Central orchestrator for music library cleanup.

    Coordinates all agents and manages the processing pipeline.
    """

    def __init__(self, config_path: str = "music-config.yaml"):
        """
        Initialize orchestrator.

        Args:
            config_path: Path to configuration file
        """
        self.config = ConfigManager(config_path)
        self.state = StateStore(self.config.state_path)
        self.queue = QueueManager()

        # Initialize agents
        self.scanner = ScannerAgent(self.config, self.state)
        self.validator = ValidatorAgent(self.config, self.state)
        self.fixer = FixerAgent(self.config, self.state)

        # Callbacks
        self._progress_callback: Optional[Callable] = None

    def init(self, library_root: str) -> Dict[str, Any]:
        """
        Initialize project with library root.

        Args:
            library_root: Path to music library root

        Returns:
            Initialization result with artist/album counts
        """
        session = self.state.get_session()
        session['library_root'] = library_root
        session['status'] = 'initialized'
        self.state.save_session(session)

        # Count artists
        path = Path(library_root)
        artists = [d for d in path.iterdir() if d.is_dir()] if path.exists() else []

        return {
            'library_root': library_root,
            'artists': len(artists),
            'status': 'initialized'
        }

    @property
    def library_root(self) -> Optional[str]:
        """Get current library root"""
        session = self.state.get_session()
        return session.get('library_root')

    def set_progress_callback(self, callback: Callable[[str, int, int], None]) -> None:
        """
        Set progress callback for UI updates.

        Args:
            callback: Function(message, current, total)
        """
        self._progress_callback = callback

    def _progress(self, message: str, current: int = 0, total: int = 0) -> None:
        """Report progress"""
        if self._progress_callback:
            self._progress_callback(message, current, total)
        else:
            print(f"[Progress] {message} ({current}/{total})" if total else f"[Progress] {message}")

    # ==================== Scanning ====================

    def scan_album(self, album_path: str) -> Dict[str, Any]:
        """
        Scan a single album.

        Args:
            album_path: Path to album directory

        Returns:
            Scan result
        """
        result = self.scanner.process({'path': album_path})

        if result.get('status') == 'success':
            # Add to queue
            self.queue.add(
                album_id=result['album_id'],
                path=album_path,
                status=AlbumStatus.SCANNED,
                priority=Priority.HIGH if result.get('issue_count', 0) > 0 else Priority.NORMAL,
                metadata={
                    'title': result.get('data', {}).get('title'),
                    'artist': result.get('data', {}).get('artist'),
                    'track_count': result.get('track_count'),
                    'has_cover': result.get('has_cover')
                }
            )

        return result

    def scan_artist(self, artist_name: str) -> Dict[str, Any]:
        """
        Scan all albums for an artist.

        Args:
            artist_name: Artist folder name

        Returns:
            Summary of scan results
        """
        if not self.library_root:
            return {'status': 'error', 'error': 'Library not initialized'}

        artist_path = Path(self.library_root) / artist_name
        if not artist_path.exists():
            return {'status': 'error', 'error': f'Artist not found: {artist_name}'}

        albums = [d for d in artist_path.iterdir() if d.is_dir() and self._has_audio(d)]

        results = {
            'artist': artist_name,
            'albums_scanned': 0,
            'total_tracks': 0,
            'issues_found': 0,
            'errors': []
        }

        for i, album_dir in enumerate(albums, 1):
            self._progress(f"Scanning: {album_dir.name}", i, len(albums))

            result = self.scan_album(str(album_dir))

            if result.get('status') == 'success':
                results['albums_scanned'] += 1
                results['total_tracks'] += result.get('track_count', 0)
                results['issues_found'] += result.get('issue_count', 0)
            else:
                results['errors'].append({
                    'album': album_dir.name,
                    'error': result.get('error')
                })

        return results

    def scan_library(self) -> Dict[str, Any]:
        """
        Scan entire library.

        Returns:
            Summary of full library scan
        """
        if not self.library_root:
            return {'status': 'error', 'error': 'Library not initialized'}

        path = Path(self.library_root)
        artists = [d for d in path.iterdir() if d.is_dir()]

        results = {
            'artists_scanned': 0,
            'albums_scanned': 0,
            'total_tracks': 0,
            'issues_found': 0
        }

        for artist_dir in artists:
            self._progress(f"Scanning artist: {artist_dir.name}")

            artist_result = self.scan_artist(artist_dir.name)
            if artist_result.get('albums_scanned', 0) > 0:
                results['artists_scanned'] += 1
                results['albums_scanned'] += artist_result.get('albums_scanned', 0)
                results['total_tracks'] += artist_result.get('total_tracks', 0)
                results['issues_found'] += artist_result.get('issues_found', 0)

        return results

    # ==================== Validation ====================

    def validate(self, threshold: float = None) -> Dict[str, Any]:
        """
        Validate all scanned albums.

        Args:
            threshold: Optional confidence threshold override

        Returns:
            Validation summary
        """
        pending = self.queue.get_by_status(AlbumStatus.SCANNED)

        if not pending:
            return {'status': 'nothing_to_validate', 'count': 0}

        results = {
            'validated': 0,
            'auto_approved': 0,
            'needs_review': 0,
            'not_found': 0,
            'errors': []
        }

        for i, item in enumerate(pending, 1):
            album_path = item['path']
            metadata = item.get('metadata', {})

            self._progress(f"Validating: {Path(album_path).name}", i, len(pending))

            validation_data = {
                'path': album_path,
                'album_id': item['id'],
                'title': metadata.get('title') or Path(album_path).name,
                'artist': metadata.get('artist') or 'Various Artists',
                'track_count': metadata.get('track_count', 0),
                'has_cover': metadata.get('has_cover', False)
            }

            result = self.validator.process(validation_data)

            if result.get('status') == 'success':
                results['validated'] += 1
                validation_status = result.get('validation_status')
                confidence = result.get('confidence', 0)

                if validation_status == 'auto_approved':
                    results['auto_approved'] += 1
                    self.queue.update_status(
                        item['id'],
                        AlbumStatus.VALIDATED,
                        metadata={'validation': result.get('data'), 'confidence': confidence}
                    )
                elif validation_status == 'needs_review':
                    results['needs_review'] += 1
                    self.queue.update_status(
                        item['id'],
                        AlbumStatus.NEEDS_REVIEW,
                        metadata={'validation': result.get('data'), 'confidence': confidence}
                    )
                elif validation_status == 'not_found':
                    results['not_found'] += 1
                    self.queue.update_status(
                        item['id'],
                        AlbumStatus.NEEDS_REVIEW,
                        metadata={'validation': result.get('data'), 'not_found': True}
                    )
            else:
                results['errors'].append({
                    'album': Path(album_path).name,
                    'error': result.get('error')
                })

        return results

    # ==================== Review ====================

    def get_review_queue(self) -> List[Dict[str, Any]]:
        """Get albums pending review"""
        return self.queue.get_review_queue()

    def approve(self, album_id: str) -> bool:
        """Approve album for fixing"""
        return self.queue.update_status(album_id, AlbumStatus.APPROVED)

    def reject(self, album_id: str) -> bool:
        """Reject album (skip fixing)"""
        return self.queue.update_status(album_id, AlbumStatus.REJECTED)

    # ==================== Fixing ====================

    def fix(self, dry_run: bool = False, album_id: str = None) -> Dict[str, Any]:
        """
        Apply fixes to validated/approved albums.

        Args:
            dry_run: If True, only preview changes
            album_id: Optional specific album to fix

        Returns:
            Fix summary
        """
        ready = self.queue.get_ready_to_fix()

        if album_id:
            ready = [r for r in ready if r['id'] == album_id or r['id'].startswith(album_id)]

        if not ready:
            return {'status': 'nothing_to_fix', 'count': 0}

        results = {
            'fixed': 0,
            'changes': 0,
            'errors': []
        }

        for i, item in enumerate(ready, 1):
            album_path = item['path']
            metadata = item.get('metadata', {})

            self._progress(f"Fixing: {Path(album_path).name}", i, len(ready))

            validation = metadata.get('validation', {})
            corrections = validation.get('corrections', [])

            if not corrections:
                self.queue.update_status(item['id'], AlbumStatus.VERIFIED)
                continue

            fix_data = {
                'path': album_path,
                'corrections': corrections,
                'dry_run': dry_run
            }

            result = self.fixer.process(fix_data)

            if result.get('status') in ('success', 'partial'):
                results['fixed'] += 1
                results['changes'] += result.get('changes_made', 0)

                if not dry_run:
                    self.queue.update_status(
                        item['id'],
                        AlbumStatus.FIXED,
                        metadata={'fix_result': result.get('data')}
                    )
            else:
                results['errors'].append({
                    'album': Path(album_path).name,
                    'error': result.get('error')
                })

        results['dry_run'] = dry_run
        return results

    # ==================== Status ====================

    def get_status(self) -> Dict[str, Any]:
        """Get current processing status"""
        session = self.state.get_session()
        queue_stats = self.queue.get_statistics()

        return {
            'session_id': session.get('session_id'),
            'library_root': session.get('library_root'),
            'status': session.get('status'),
            'queue': queue_stats,
            'errors': len(self.state.get_errors())
        }

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get logged errors"""
        return self.state.get_errors()

    def create_checkpoint(self) -> str:
        """Create a checkpoint of current state"""
        return self.state.create_checkpoint()

    # ==================== Helpers ====================

    def _has_audio(self, path: Path) -> bool:
        """Check if directory contains audio files"""
        audio_extensions = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wav'}
        for item in path.iterdir():
            if item.is_file() and item.suffix.lower() in audio_extensions:
                return True
        return False


# Convenience function
def create_orchestrator(config_path: str = "music-config.yaml") -> MusicLibraryOrchestrator:
    """Create and return an orchestrator instance"""
    return MusicLibraryOrchestrator(config_path)
