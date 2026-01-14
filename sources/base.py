#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base class for data source adapters.
All sources (MusicBrainz, iTunes, AcoustID, Discogs) inherit from this.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time


@dataclass
class TrackInfo:
    """Track information from external source"""
    title: str
    track_number: int
    disc_number: int = 1
    duration_ms: Optional[int] = None
    artist: Optional[str] = None
    isrc: Optional[str] = None


@dataclass
class AlbumMatch:
    """Result from source lookup"""
    source: str
    source_id: str
    title: str
    artist: str
    year: Optional[int] = None
    track_count: int = 0
    tracks: List[TrackInfo] = field(default_factory=list)
    cover_url: Optional[str] = None
    confidence: float = 0.0
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "artist": self.artist,
            "year": self.year,
            "track_count": self.track_count,
            "tracks": [
                {
                    "title": t.title,
                    "track_number": t.track_number,
                    "disc_number": t.disc_number,
                    "duration_ms": t.duration_ms,
                    "artist": t.artist
                }
                for t in self.tracks
            ],
            "cover_url": self.cover_url,
            "confidence": self.confidence
        }


class DataSource(ABC):
    """
    Abstract base class for data sources.

    Data sources provide metadata from external services:
    - MusicBrainz: Primary metadata source
    - iTunes: Cover art and metadata
    - AcoustID: Audio fingerprinting
    - Discogs: Vinyl and rare releases
    """

    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize data source with rate limiting.

        Args:
            rate_limit: Minimum seconds between requests
        """
        self.rate_limit = rate_limit
        self._last_request: float = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """Source name identifier"""
        pass

    @abstractmethod
    def search_album(self, title: str, artist: str = "Various Artists") -> List[AlbumMatch]:
        """
        Search for album by title and artist.

        Args:
            title: Album title
            artist: Artist name (default: Various Artists)

        Returns:
            List of matching albums
        """
        pass

    @abstractmethod
    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        """
        Get album details by source-specific ID.

        Args:
            source_id: ID from this source (e.g., MusicBrainz release ID)

        Returns:
            Album details or None if not found
        """
        pass

    def get_cover_url(self, source_id: str) -> Optional[str]:
        """
        Get cover art URL for album.

        Args:
            source_id: Source-specific album ID

        Returns:
            URL to cover art image or None
        """
        album = self.get_album(source_id)
        return album.cover_url if album else None

    def _rate_limit_wait(self) -> None:
        """Wait if necessary to respect rate limits"""
        if self._last_request > 0:
            elapsed = time.time() - self._last_request
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        """Extract year from date string"""
        if date_str and len(date_str) >= 4:
            try:
                return int(date_str[:4])
            except ValueError:
                pass
        return None

    def log(self, message: str) -> None:
        """Log a message"""
        print(f"[{self.name}] {message}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(rate_limit={self.rate_limit})"
