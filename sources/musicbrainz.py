#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MusicBrainz API adapter.
Free, no authentication required, but needs user agent.

API Documentation:
https://musicbrainz.org/doc/MusicBrainz_API

Rate Limits: 1 request per second per IP
"""

import requests
import re
from typing import List, Optional, Dict, Any
from .base import DataSource, AlbumMatch, TrackInfo


class MusicBrainzSource(DataSource):
    """
    MusicBrainz API data source.

    Primary source for album validation and metadata.
    """

    BASE_URL = "https://musicbrainz.org/ws/2"
    COVER_ART_URL = "https://coverartarchive.org"

    def __init__(self, user_agent: str = "MusicCleanup/1.0", rate_limit: float = 1.0):
        """
        Initialize MusicBrainz source.

        Args:
            user_agent: User agent string (required by API)
            rate_limit: Seconds between requests (1.0 required by API)
        """
        super().__init__(rate_limit)
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json"
        })

    @property
    def name(self) -> str:
        return "musicbrainz"

    def search_album(self, title: str, artist: str = "Various Artists") -> List[AlbumMatch]:
        """
        Search for albums by title and artist.

        Uses MusicBrainz release-group search for better results.

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
            # Search for compilations specifically
            query = f'release:"{clean_title}" AND (artist:"Various Artists" OR secondarytype:Compilation)'
        else:
            query = f'release:"{clean_title}" AND artist:"{artist}"'

        params = {
            "query": query,
            "fmt": "json",
            "limit": 25
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}/release",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.log(f"Search error: {e}")
            return []

        results = []
        for release in data.get("releases", []):
            # Get artist name
            artist_credit = release.get("artist-credit", [])
            if artist_credit:
                release_artist = artist_credit[0].get("name", "Unknown")
            else:
                release_artist = "Various Artists"

            match = AlbumMatch(
                source="musicbrainz",
                source_id=release.get("id"),
                title=release.get("title", ""),
                artist=release_artist,
                year=self._extract_year(release.get("date")),
                track_count=release.get("track-count", 0),
                tracks=[],
                cover_url=None,  # Need separate call for cover art
                confidence=release.get("score", 0) / 100.0,  # MB returns 0-100
                raw_data=release
            )
            results.append(match)

        return results

    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        """
        Get album details including tracks.

        Args:
            source_id: MusicBrainz release ID

        Returns:
            Album details with tracks
        """
        self._rate_limit_wait()

        params = {
            "fmt": "json",
            "inc": "recordings+artist-credits"
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}/release/{source_id}",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            release = response.json()
        except requests.RequestException as e:
            self.log(f"Lookup error: {e}")
            return None

        # Extract artist
        artist_credit = release.get("artist-credit", [])
        if artist_credit:
            artist_name = artist_credit[0].get("name", "Unknown")
        else:
            artist_name = "Various Artists"

        # Extract tracks from media
        tracks = []
        for medium in release.get("media", []):
            disc_number = medium.get("position", 1)
            for track in medium.get("tracks", []):
                recording = track.get("recording", {})

                # Get track artist if different
                track_artist = None
                if recording.get("artist-credit"):
                    track_artist = recording["artist-credit"][0].get("name")

                tracks.append(TrackInfo(
                    title=recording.get("title", track.get("title", "")),
                    track_number=track.get("position", 0),
                    disc_number=disc_number,
                    duration_ms=recording.get("length"),
                    artist=track_artist
                ))

        # Get cover art URL
        cover_url = self.get_cover_url(source_id)

        return AlbumMatch(
            source="musicbrainz",
            source_id=source_id,
            title=release.get("title", ""),
            artist=artist_name,
            year=self._extract_year(release.get("date")),
            track_count=len(tracks),
            tracks=sorted(tracks, key=lambda t: (t.disc_number, t.track_number)),
            cover_url=cover_url,
            confidence=1.0,  # Direct lookup is always correct
            raw_data=release
        )

    def get_cover_url(self, release_id: str) -> Optional[str]:
        """
        Get cover art URL from Cover Art Archive.

        Args:
            release_id: MusicBrainz release ID

        Returns:
            URL to front cover image
        """
        # Try Cover Art Archive
        try:
            response = requests.get(
                f"{self.COVER_ART_URL}/release/{release_id}",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                for image in data.get("images", []):
                    if image.get("front"):
                        # Get large thumbnail or original
                        thumbnails = image.get("thumbnails", {})
                        return (
                            thumbnails.get("1200") or
                            thumbnails.get("large") or
                            image.get("image")
                        )
        except:
            pass

        # Fallback to direct URL (may or may not exist)
        return f"{self.COVER_ART_URL}/release/{release_id}/front-1200"

    def check_cover_exists(self, release_id: str) -> bool:
        """
        Check if cover art exists for release.

        Args:
            release_id: MusicBrainz release ID

        Returns:
            True if cover art is available
        """
        try:
            response = requests.head(
                f"{self.COVER_ART_URL}/release/{release_id}/front",
                timeout=10,
                allow_redirects=True
            )
            return response.status_code == 200
        except:
            return False

    def search_by_recording_id(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up recording by MusicBrainz recording ID.
        Used with AcoustID fingerprint results.

        Args:
            recording_id: MusicBrainz recording ID

        Returns:
            Recording details including releases
        """
        self._rate_limit_wait()

        params = {
            "fmt": "json",
            "inc": "releases+artists"
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}/recording/{recording_id}",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.log(f"Recording lookup error: {e}")
            return None

    def _clean_title(self, title: str) -> str:
        """
        Clean album title for better search results.

        Removes:
        - Disc indicators (Disc 1, CD 1, etc.)
        - Brackets and their contents [Deluxe Edition]
        - Underscores (converted to spaces)
        """
        # Replace underscores with spaces
        title = title.replace("_", " ")

        # Remove disc indicators
        title = re.sub(r'\s*[\[\(]?(?:Disc|CD|Disk)\s*\d+[\]\)]?\s*$', '', title, flags=re.IGNORECASE)

        # Remove edition markers in brackets
        title = re.sub(r'\s*\[[^\]]*(?:Edition|Version|Deluxe|Remaster)[^\]]*\]', '', title, flags=re.IGNORECASE)

        # Clean up extra spaces
        title = ' '.join(title.split())

        return title.strip()


# Quick test
if __name__ == "__main__":
    source = MusicBrainzSource()

    print("Testing MusicBrainz API...")
    print()

    # Search for Various Artists album
    results = source.search_album("Buddha-Bar", "Various Artists")
    print(f"Found {len(results)} results for 'Buddha-Bar'")

    if results:
        best = results[0]
        print(f"  Best match: {best.title} by {best.artist}")
        print(f"  Year: {best.year}, Score: {best.confidence:.0%}")
        print(f"  Release ID: {best.source_id}")

        # Check cover art
        has_cover = source.check_cover_exists(best.source_id)
        print(f"  Has cover art: {has_cover}")

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
