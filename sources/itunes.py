#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iTunes Search API adapter.
Free, no authentication required.

API Documentation:
https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/

Rate Limits: ~20 requests per minute recommended
"""

import requests
from typing import List, Optional
from .base import DataSource, AlbumMatch, TrackInfo


class iTunesSource(DataSource):
    """
    iTunes Search API data source.

    Provides album metadata and cover art URLs.
    No authentication required.
    """

    BASE_URL = "https://itunes.apple.com"

    def __init__(self, country: str = "us", rate_limit: float = 0.05):
        """
        Initialize iTunes source.

        Args:
            country: Two-letter country code for regional content
            rate_limit: Seconds between requests (default 0.05 = 20/sec)
        """
        super().__init__(rate_limit)
        self.country = country

    @property
    def name(self) -> str:
        return "itunes"

    def search_album(self, title: str, artist: str = "Various Artists") -> List[AlbumMatch]:
        """
        Search for albums by title and artist.

        Args:
            title: Album title to search for
            artist: Artist name (default: Various Artists)

        Returns:
            List of matching albums sorted by relevance
        """
        self._rate_limit_wait()

        params = {
            "term": f"{artist} {title}",
            "entity": "album",
            "country": self.country,
            "limit": 25
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.log(f"Search error: {e}")
            return []

        results = []
        for item in data.get("results", []):
            match = AlbumMatch(
                source="itunes",
                source_id=str(item.get("collectionId")),
                title=item.get("collectionName", ""),
                artist=item.get("artistName", ""),
                year=self._extract_year(item.get("releaseDate")),
                track_count=item.get("trackCount", 0),
                tracks=[],  # iTunes search doesn't return tracks
                cover_url=self._get_large_artwork(item.get("artworkUrl100")),
                confidence=0.0,  # Will be calculated by validator
                raw_data=item
            )
            results.append(match)

        return results

    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        """
        Get album details including track listing.

        Args:
            source_id: iTunes collection ID

        Returns:
            Album details with tracks or None
        """
        self._rate_limit_wait()

        params = {
            "id": source_id,
            "entity": "song",
            "country": self.country
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}/lookup",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.log(f"Lookup error: {e}")
            return None

        results = data.get("results", [])
        if not results:
            return None

        # First result is album info, rest are tracks
        album_data = results[0]

        # Extract track info
        tracks = []
        for item in results[1:]:
            if item.get("wrapperType") == "track":
                tracks.append(TrackInfo(
                    title=item.get("trackName", ""),
                    track_number=item.get("trackNumber", 0),
                    disc_number=item.get("discNumber", 1),
                    duration_ms=item.get("trackTimeMillis"),
                    artist=item.get("artistName")
                ))

        return AlbumMatch(
            source="itunes",
            source_id=source_id,
            title=album_data.get("collectionName", ""),
            artist=album_data.get("artistName", ""),
            year=self._extract_year(album_data.get("releaseDate")),
            track_count=album_data.get("trackCount", 0),
            tracks=sorted(tracks, key=lambda t: (t.disc_number, t.track_number)),
            cover_url=self._get_large_artwork(album_data.get("artworkUrl100")),
            confidence=0.0,
            raw_data=album_data
        )

    def search_track(self, title: str, artist: str = "") -> List[dict]:
        """
        Search for individual tracks.

        Args:
            title: Track title
            artist: Artist name (optional)

        Returns:
            List of matching tracks
        """
        self._rate_limit_wait()

        term = f"{artist} {title}" if artist else title
        params = {
            "term": term,
            "entity": "song",
            "country": self.country,
            "limit": 25
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.log(f"Track search error: {e}")
            return []

        results = []
        for item in data.get("results", []):
            if item.get("wrapperType") == "track":
                results.append({
                    "title": item.get("trackName"),
                    "artist": item.get("artistName"),
                    "album": item.get("collectionName"),
                    "album_id": str(item.get("collectionId")),
                    "track_number": item.get("trackNumber"),
                    "duration_ms": item.get("trackTimeMillis"),
                    "preview_url": item.get("previewUrl"),
                    "cover_url": self._get_large_artwork(item.get("artworkUrl100"))
                })

        return results

    def _get_large_artwork(self, url: Optional[str], size: int = 1000) -> Optional[str]:
        """
        Convert thumbnail URL to larger artwork.

        iTunes returns 100x100 by default, but supports up to 3000x3000.

        Args:
            url: Original artwork URL (100x100)
            size: Desired size (default 1000x1000)

        Returns:
            URL for larger artwork
        """
        if url:
            return url.replace("100x100bb", f"{size}x{size}bb")
        return None

    def download_cover(self, url: str) -> Optional[bytes]:
        """
        Download cover art from URL.

        Args:
            url: Cover art URL

        Returns:
            Image data as bytes or None
        """
        if not url:
            return None

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            self.log(f"Cover download error: {e}")
            return None


# Quick test
if __name__ == "__main__":
    source = iTunesSource()

    print("Testing iTunes Search API...")
    print()

    # Search for Various Artists album
    results = source.search_album("Buddha-Bar", "Various Artists")
    print(f"Found {len(results)} results for 'Buddha-Bar'")

    if results:
        best = results[0]
        print(f"  Best match: {best.title} by {best.artist}")
        print(f"  Year: {best.year}, Tracks: {best.track_count}")
        print(f"  Cover URL: {best.cover_url[:50] if best.cover_url else 'None'}...")

        # Get full details
        print()
        print("Getting full album details...")
        album = source.get_album(best.source_id)
        if album:
            print(f"  Tracks: {len(album.tracks)}")
            for i, track in enumerate(album.tracks[:5], 1):
                print(f"    {i}. {track.title}")
            if len(album.tracks) > 5:
                print(f"    ... and {len(album.tracks) - 5} more")
