#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validator Agent - Validates albums against external sources.

Responsibilities:
- Search MusicBrainz, iTunes for album matches
- Calculate confidence scores based on metadata comparison
- Identify corrections needed (title, cover art, etc.)
- Route low-confidence matches to review queue
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .base import BaseAgent
from sources.musicbrainz import MusicBrainzSource
from sources.itunes import iTunesSource
from sources.base import AlbumMatch


@dataclass
class ValidationResult:
    """Result of album validation"""
    album_path: str
    album_id: str
    local_title: str
    local_artist: str
    local_track_count: int

    # Best match info
    matched: bool = False
    match_source: Optional[str] = None
    match_id: Optional[str] = None
    match_title: Optional[str] = None
    match_artist: Optional[str] = None
    match_track_count: int = 0
    match_year: Optional[int] = None

    # Scores
    confidence: float = 0.0
    title_score: float = 0.0
    artist_score: float = 0.0
    track_count_score: float = 0.0

    # Status
    status: str = "pending"  # auto_approved, needs_review, not_found, rejected
    cover_available: bool = False
    cover_url: Optional[str] = None

    # Corrections needed
    corrections: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "album_path": self.album_path,
            "album_id": self.album_id,
            "local_title": self.local_title,
            "local_artist": self.local_artist,
            "local_track_count": self.local_track_count,
            "matched": self.matched,
            "match_source": self.match_source,
            "match_id": self.match_id,
            "match_title": self.match_title,
            "match_artist": self.match_artist,
            "match_track_count": self.match_track_count,
            "match_year": self.match_year,
            "confidence": self.confidence,
            "title_score": self.title_score,
            "artist_score": self.artist_score,
            "track_count_score": self.track_count_score,
            "status": self.status,
            "cover_available": self.cover_available,
            "cover_url": self.cover_url,
            "corrections": self.corrections
        }


class ValidatorAgent(BaseAgent):
    """
    Validator agent for comparing local albums against external sources.

    Uses MusicBrainz as primary source, with iTunes as fallback.
    Calculates confidence scores and determines approval status.
    """

    def __init__(self, config, state):
        super().__init__(config, state)

        # Initialize data sources
        self.musicbrainz = MusicBrainzSource(
            user_agent=config.get('api.musicbrainz.user_agent', 'MusicCleanup/1.0'),
            rate_limit=config.get('api.musicbrainz.rate_limit', 1.0)
        )
        self.itunes = iTunesSource(
            country=config.get('api.itunes.country', 'us'),
            rate_limit=config.get('api.itunes.rate_limit', 0.05)
        )

        # Thresholds from config
        self.auto_approve_threshold = config.get('thresholds.auto_approve', 0.95)
        self.review_threshold = config.get('thresholds.review_required', 0.70)

    @property
    def name(self) -> str:
        return "Validator"

    def process(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single album for validation.

        Args:
            item: Dictionary with album data from Scanner

        Returns:
            Validation results
        """
        album_path = item.get('path')
        if not album_path:
            return {"status": "error", "error": "No path provided"}

        try:
            # Get album info from scan data or item
            album_title = item.get('title') or item.get('folder_name', '')
            album_artist = item.get('artist', 'Various Artists')
            track_count = item.get('track_count', 0)
            album_id = item.get('album_id', '')
            has_cover = item.get('has_cover', False)

            # Validate
            result = self.validate_album(
                album_path=album_path,
                album_id=album_id,
                title=album_title,
                artist=album_artist,
                track_count=track_count,
                has_cover=has_cover
            )

            # Save state
            self.save_state(album_path, "VALIDATED", result.to_dict())

            return {
                "status": "success",
                "path": album_path,
                "validation_status": result.status,
                "confidence": result.confidence,
                "matched": result.matched,
                "corrections_needed": len(result.corrections),
                "data": result.to_dict()
            }

        except Exception as e:
            self.log_error(f"Error validating {album_path}: {e}")
            return {
                "status": "error",
                "path": album_path,
                "error": str(e)
            }

    def validate_album(
        self,
        album_path: str,
        album_id: str,
        title: str,
        artist: str,
        track_count: int,
        has_cover: bool = False
    ) -> ValidationResult:
        """
        Validate an album against external sources.

        Args:
            album_path: Path to album folder
            album_id: Unique album identifier
            title: Album title (from metadata or folder name)
            artist: Album artist
            track_count: Number of tracks in album
            has_cover: Whether album already has cover art

        Returns:
            ValidationResult with match info and corrections
        """
        result = ValidationResult(
            album_path=album_path,
            album_id=album_id,
            local_title=title,
            local_artist=artist,
            local_track_count=track_count
        )

        # Clean title for searching
        search_title = self._clean_title_for_search(title)
        self.log(f"Validating: {title}")

        # Try MusicBrainz first
        matches = self.musicbrainz.search_album(search_title, artist)

        if not matches:
            # Try iTunes as fallback
            self.log("  No MusicBrainz results, trying iTunes...")
            matches = self.itunes.search_album(search_title, artist)

        if not matches:
            result.status = "not_found"
            return result

        # Find best match
        best_match, confidence = self._find_best_match(
            matches, title, artist, track_count
        )

        if best_match:
            result.matched = True
            result.match_source = best_match.source
            result.match_id = best_match.source_id
            result.match_title = best_match.title
            result.match_artist = best_match.artist
            result.match_track_count = best_match.track_count
            result.match_year = best_match.year
            result.confidence = confidence

            # Calculate individual scores
            result.title_score = self._title_similarity(title, best_match.title)
            result.artist_score = self._artist_similarity(artist, best_match.artist)
            result.track_count_score = self._track_count_score(track_count, best_match.track_count)

            # Check cover art availability
            if best_match.cover_url:
                result.cover_available = True
                result.cover_url = best_match.cover_url
            elif best_match.source == "musicbrainz":
                # Check Cover Art Archive
                result.cover_available = self.musicbrainz.check_cover_exists(best_match.source_id)
                if result.cover_available:
                    result.cover_url = self.musicbrainz.get_cover_url(best_match.source_id)

            # Identify corrections needed
            result.corrections = self._identify_corrections(
                local_title=title,
                local_artist=artist,
                match=best_match,
                has_cover=has_cover,
                cover_available=result.cover_available
            )

            # Determine status based on confidence
            if confidence >= self.auto_approve_threshold:
                result.status = "auto_approved"
            elif confidence >= self.review_threshold:
                result.status = "needs_review"
            else:
                result.status = "rejected"
        else:
            result.status = "not_found"

        return result

    def _find_best_match(
        self,
        matches: List[AlbumMatch],
        local_title: str,
        local_artist: str,
        local_track_count: int
    ) -> Tuple[Optional[AlbumMatch], float]:
        """
        Find best match from search results.

        Args:
            matches: List of album matches from source
            local_title: Local album title
            local_artist: Local artist name
            local_track_count: Number of local tracks

        Returns:
            Tuple of (best match, confidence score)
        """
        best_match = None
        best_score = 0.0

        for match in matches:
            score = self._calculate_confidence(
                local_title, local_artist, local_track_count,
                match.title, match.artist, match.track_count
            )

            if score > best_score:
                best_score = score
                best_match = match

        return best_match, best_score

    def _calculate_confidence(
        self,
        local_title: str,
        local_artist: str,
        local_track_count: int,
        remote_title: str,
        remote_artist: str,
        remote_track_count: int
    ) -> float:
        """
        Calculate confidence score for a match.

        Weights:
        - Title similarity: 50%
        - Artist similarity: 30%
        - Track count match: 20%
        """
        title_score = self._title_similarity(local_title, remote_title)
        artist_score = self._artist_similarity(local_artist, remote_artist)
        track_score = self._track_count_score(local_track_count, remote_track_count)

        # Weighted average
        confidence = (
            title_score * 0.50 +
            artist_score * 0.30 +
            track_score * 0.20
        )

        return confidence

    def _title_similarity(self, local: str, remote: str) -> float:
        """Calculate title similarity score (0-1)"""
        if not local or not remote:
            return 0.0

        # Normalize titles
        local_norm = self._normalize_string(local)
        remote_norm = self._normalize_string(remote)

        # Exact match
        if local_norm == remote_norm:
            return 1.0

        # Sequence matching
        return SequenceMatcher(None, local_norm, remote_norm).ratio()

    def _artist_similarity(self, local: str, remote: str) -> float:
        """Calculate artist similarity score (0-1)"""
        if not local or not remote:
            return 0.0

        local_norm = self._normalize_string(local)
        remote_norm = self._normalize_string(remote)

        # Both are Various Artists
        if 'various' in local_norm and 'various' in remote_norm:
            return 1.0

        # Exact match
        if local_norm == remote_norm:
            return 1.0

        return SequenceMatcher(None, local_norm, remote_norm).ratio()

    def _track_count_score(self, local: int, remote: int) -> float:
        """Calculate track count match score (0-1)"""
        if local == 0 or remote == 0:
            return 0.5  # Unknown, neutral score

        if local == remote:
            return 1.0

        # Difference penalty
        diff = abs(local - remote)
        max_count = max(local, remote)

        # Allow some tolerance (compilations often have varying track counts)
        if diff <= 2:
            return 0.9
        elif diff <= 5:
            return 0.7

        return max(0.0, 1.0 - (diff / max_count))

    def _normalize_string(self, s: str) -> str:
        """Normalize string for comparison"""
        if not s:
            return ""

        # Lowercase
        s = s.lower()

        # Remove common variations
        s = s.replace('_', ' ')
        s = s.replace('-', ' ')
        s = s.replace(':', ' ')
        s = s.replace("'", '')
        s = s.replace('"', '')

        # Remove edition markers
        s = re.sub(r'\s*\([^)]*edition[^)]*\)', '', s, flags=re.IGNORECASE)
        s = re.sub(r'\s*\[[^\]]*edition[^\]]*\]', '', s, flags=re.IGNORECASE)
        s = re.sub(r'\s*\([^)]*remaster[^)]*\)', '', s, flags=re.IGNORECASE)
        s = re.sub(r'\s*\[[^\]]*remaster[^\]]*\]', '', s, flags=re.IGNORECASE)

        # Remove disc indicators
        s = re.sub(r'\s*[\[\(]?(?:disc|cd|disk)\s*\d+[\]\)]?', '', s, flags=re.IGNORECASE)

        # Remove volume indicators
        s = re.sub(r'\s*,?\s*vol(?:ume)?\.?\s*\d+', '', s, flags=re.IGNORECASE)

        # Clean whitespace
        s = ' '.join(s.split())

        return s.strip()

    def _clean_title_for_search(self, title: str) -> str:
        """Clean title for API search"""
        # Replace underscores
        title = title.replace('_', ' ')

        # Remove disc indicators
        title = re.sub(r'\s*[\[\(]?(?:disc|cd)\s*\d+[\]\)]?\s*$', '', title, flags=re.IGNORECASE)

        # Remove common edition markers that might confuse search
        title = re.sub(r'\s*\[.*?\]$', '', title)

        return title.strip()

    def _identify_corrections(
        self,
        local_title: str,
        local_artist: str,
        match: AlbumMatch,
        has_cover: bool,
        cover_available: bool
    ) -> List[Dict[str, Any]]:
        """Identify corrections needed based on match"""
        corrections = []

        # Title correction
        if self._normalize_string(local_title) != self._normalize_string(match.title):
            # Check if it's just a formatting difference
            local_clean = re.sub(r'[_\-:\[\]\(\)]', '', local_title.lower())
            remote_clean = re.sub(r'[_\-:\[\]\(\)]', '', match.title.lower())

            if local_clean == remote_clean:
                correction_type = "formatting_only"
            else:
                correction_type = "title_mismatch"

            corrections.append({
                "type": correction_type,
                "field": "title",
                "current": local_title,
                "suggested": match.title,
                "safe": correction_type == "formatting_only"
            })

        # Cover art
        if not has_cover and cover_available:
            corrections.append({
                "type": "missing_cover",
                "field": "cover_art",
                "current": None,
                "suggested": match.cover_url,
                "safe": True
            })

        return corrections
