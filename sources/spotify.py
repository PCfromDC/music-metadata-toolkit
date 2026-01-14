#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spotify Web API adapter.
Priority 2 source - largest catalog, good for popular releases.

API Documentation:
https://developer.spotify.com/documentation/web-api

Rate Limits: ~180 requests per minute (with backoff)
"""

import os
import re
from typing import List, Optional, Dict, Any

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

from .base import DataSource, AlbumMatch, TrackInfo


class SpotifySource(DataSource):
    """
    Spotify Web API data source.

    Second priority source with largest catalog.
    Requires client_id and client_secret from Spotify Developer Dashboard.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        rate_limit: float = 0.5
    ):
        """
        Initialize Spotify source.

        Args:
            client_id: Spotify API client ID (or SPOTIFY_CLIENT_ID env var)
            client_secret: Spotify API client secret (or SPOTIFY_CLIENT_SECRET env var)
            rate_limit: Seconds between requests (0.5 = ~120 req/min)
        """
        super().__init__(rate_limit)

        if not SPOTIPY_AVAILABLE:
            raise ImportError(
                "spotipy library not installed. Install with: pip install spotipy"
            )

        # Get credentials from args or environment
        self.client_id = client_id or os.environ.get("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("SPOTIFY_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Spotify credentials required. Set SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET environment variables or pass to constructor."
            )

        # Initialize Spotify client with client credentials flow
        auth_manager = SpotifyClientCredentials(
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        self.spotify = spotipy.Spotify(auth_manager=auth_manager)

    @property
    def name(self) -> str:
        return "spotify"

    def search_album(self, title: str, artist: str = "Various Artists") -> List[AlbumMatch]:
        """
        Search for albums by title and artist.

        Args:
            title: Album title to search for
            artist: Artist name (default: Various Artists)

        Returns:
            List of matching albums
        """
        self._rate_limit_wait()

        # Clean up title for better matching
        clean_title = self._clean_title(title)

        # Build query
        if artist.lower() == "various artists":
            query = f'album:"{clean_title}"'
        else:
            query = f'album:"{clean_title}" artist:"{artist}"'

        try:
            results = self.spotify.search(q=query, type="album", limit=20)
        except Exception as e:
            self.log(f"Search error: {e}")
            return []

        albums = results.get("albums", {}).get("items", [])
        matches = []

        for album in albums:
            # Get artist name
            artists = album.get("artists", [])
            album_artist = artists[0].get("name", "Unknown") if artists else "Various Artists"

            # Get cover art URL (largest image)
            images = album.get("images", [])
            cover_url = images[0].get("url") if images else None

            # Calculate confidence based on title similarity
            confidence = self._calculate_confidence(clean_title, album.get("name", ""))

            match = AlbumMatch(
                source="spotify",
                source_id=album.get("id"),
                title=album.get("name", ""),
                artist=album_artist,
                year=self._extract_year(album.get("release_date")),
                track_count=album.get("total_tracks", 0),
                tracks=[],  # Tracks fetched separately
                cover_url=cover_url,
                confidence=confidence,
                raw_data=album
            )
            matches.append(match)

        # Sort by confidence
        return sorted(matches, key=lambda m: m.confidence, reverse=True)

    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        """
        Get album details including tracks.

        Args:
            source_id: Spotify album ID

        Returns:
            Album details with tracks
        """
        self._rate_limit_wait()

        try:
            album = self.spotify.album(source_id)
        except Exception as e:
            self.log(f"Album lookup error: {e}")
            return None

        # Get artist name
        artists = album.get("artists", [])
        album_artist = artists[0].get("name", "Unknown") if artists else "Various Artists"

        # Get cover art URL
        images = album.get("images", [])
        cover_url = images[0].get("url") if images else None

        # Extract tracks
        tracks = []
        for item in album.get("tracks", {}).get("items", []):
            # Get track artist
            track_artists = item.get("artists", [])
            track_artist = track_artists[0].get("name") if track_artists else None

            # Get ISRC from external IDs if available
            isrc = None
            external_ids = item.get("external_ids", {})
            if external_ids:
                isrc = external_ids.get("isrc")

            tracks.append(TrackInfo(
                title=item.get("name", ""),
                track_number=item.get("track_number", 0),
                disc_number=item.get("disc_number", 1),
                duration_ms=item.get("duration_ms"),
                artist=track_artist,
                isrc=isrc
            ))

        return AlbumMatch(
            source="spotify",
            source_id=source_id,
            title=album.get("name", ""),
            artist=album_artist,
            year=self._extract_year(album.get("release_date")),
            track_count=len(tracks),
            tracks=sorted(tracks, key=lambda t: (t.disc_number, t.track_number)),
            cover_url=cover_url,
            confidence=1.0,  # Direct lookup is reliable
            raw_data=album
        )

    def get_track_isrc(self, track_id: str) -> Optional[str]:
        """
        Get ISRC code for a specific track.

        Args:
            track_id: Spotify track ID

        Returns:
            ISRC code or None
        """
        self._rate_limit_wait()

        try:
            track = self.spotify.track(track_id)
            external_ids = track.get("external_ids", {})
            return external_ids.get("isrc")
        except Exception as e:
            self.log(f"Track lookup error: {e}")
            return None

    def search_track(self, title: str, artist: str) -> List[Dict[str, Any]]:
        """
        Search for individual tracks.

        Args:
            title: Track title
            artist: Artist name

        Returns:
            List of matching tracks with details
        """
        self._rate_limit_wait()

        query = f'track:"{title}" artist:"{artist}"'

        try:
            results = self.spotify.search(q=query, type="track", limit=10)
        except Exception as e:
            self.log(f"Track search error: {e}")
            return []

        tracks = []
        for item in results.get("tracks", {}).get("items", []):
            track_artists = item.get("artists", [])
            track_artist = track_artists[0].get("name") if track_artists else "Unknown"

            external_ids = item.get("external_ids", {})

            tracks.append({
                "id": item.get("id"),
                "title": item.get("name"),
                "artist": track_artist,
                "album": item.get("album", {}).get("name"),
                "duration_ms": item.get("duration_ms"),
                "isrc": external_ids.get("isrc"),
                "popularity": item.get("popularity", 0)
            })

        return tracks

    def _clean_title(self, title: str) -> str:
        """
        Clean album title for better search results.
        """
        # Replace underscores with spaces
        title = title.replace("_", " ")

        # Remove disc indicators
        title = re.sub(
            r'\s*[\[\(]?(?:Disc|CD|Disk)\s*\d+[\]\)]?\s*$',
            '', title, flags=re.IGNORECASE
        )

        # Remove edition markers
        title = re.sub(
            r'\s*\[[^\]]*(?:Edition|Version|Deluxe|Remaster)[^\]]*\]',
            '', title, flags=re.IGNORECASE
        )

        # Clean extra spaces
        return ' '.join(title.split()).strip()

    def _calculate_confidence(self, query: str, result: str) -> float:
        """
        Calculate similarity confidence between query and result.

        Simple ratio-based comparison.
        """
        query = query.lower().strip()
        result = result.lower().strip()

        if query == result:
            return 1.0

        # Check if one contains the other
        if query in result or result in query:
            shorter = min(len(query), len(result))
            longer = max(len(query), len(result))
            return shorter / longer * 0.95

        # Simple character overlap
        query_chars = set(query.replace(" ", ""))
        result_chars = set(result.replace(" ", ""))

        if not query_chars or not result_chars:
            return 0.0

        overlap = len(query_chars & result_chars)
        total = len(query_chars | result_chars)

        return overlap / total * 0.8


# Quick test
if __name__ == "__main__":
    # Test requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars
    try:
        source = SpotifySource()
        print("Testing Spotify API...")
        print()

        # Search for Various Artists album
        results = source.search_album("Buddha-Bar", "Various Artists")
        print(f"Found {len(results)} results for 'Buddha-Bar'")

        if results:
            best = results[0]
            print(f"  Best match: {best.title} by {best.artist}")
            print(f"  Year: {best.year}, Confidence: {best.confidence:.0%}")
            print(f"  Album ID: {best.source_id}")
            print(f"  Cover URL: {best.cover_url}")

            # Get full details
            print()
            print("Getting full album details...")
            album = source.get_album(best.source_id)
            if album:
                print(f"  Tracks: {len(album.tracks)}")
                for i, track in enumerate(album.tracks[:5], 1):
                    print(f"    {i}. {track.title} ({track.artist})")
                if len(album.tracks) > 5:
                    print(f"    ... and {len(album.tracks) - 5} more")

    except ValueError as e:
        print(f"Configuration error: {e}")
    except ImportError as e:
        print(f"Import error: {e}")
