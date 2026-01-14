#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Discogs API adapter.
Priority 3 source - comprehensive, especially for rare and vinyl releases.

API Documentation:
https://www.discogs.com/developers

Rate Limits:
- Authenticated: 60 requests per minute
- Unauthenticated: 25 requests per minute
"""

import os
import re
from typing import List, Optional, Dict, Any

try:
    import discogs_client
    DISCOGS_AVAILABLE = True
except ImportError:
    DISCOGS_AVAILABLE = False

import requests
from .base import DataSource, AlbumMatch, TrackInfo


class DiscogsSource(DataSource):
    """
    Discogs API data source.

    Third priority source, comprehensive for rare releases.
    Requires personal access token from discogs.com/settings/developers
    """

    def __init__(
        self,
        token: Optional[str] = None,
        user_agent: str = "MusicCleanup/1.0",
        rate_limit: float = 1.0
    ):
        """
        Initialize Discogs source.

        Args:
            token: Discogs personal access token (or DISCOGS_TOKEN env var)
            user_agent: User agent string
            rate_limit: Seconds between requests (1.0 = 60 req/min)
        """
        super().__init__(rate_limit)

        self.token = token or os.environ.get("DISCOGS_TOKEN")
        self.user_agent = user_agent

        if DISCOGS_AVAILABLE and self.token:
            # Use official client if available
            self.client = discogs_client.Client(
                user_agent,
                user_token=self.token
            )
            self._use_client = True
        else:
            # Fallback to direct API calls
            self._use_client = False
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": user_agent,
                "Accept": "application/json"
            })
            if self.token:
                self.session.headers["Authorization"] = f"Discogs token={self.token}"

    @property
    def name(self) -> str:
        return "discogs"

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

        clean_title = self._clean_title(title)

        if self._use_client:
            return self._search_with_client(clean_title, artist)
        else:
            return self._search_with_api(clean_title, artist)

    def _search_with_client(self, title: str, artist: str) -> List[AlbumMatch]:
        """Search using discogs_client library"""
        try:
            # Search for releases
            if artist.lower() == "various artists":
                results = self.client.search(title, type="release")
            else:
                results = self.client.search(f"{artist} {title}", type="release")

            matches = []
            for i, result in enumerate(results):
                if i >= 20:  # Limit results
                    break

                try:
                    # Get basic info without fetching full release
                    match = AlbumMatch(
                        source="discogs",
                        source_id=str(result.id),
                        title=result.title.split(" - ", 1)[-1] if " - " in result.title else result.title,
                        artist=result.title.split(" - ", 1)[0] if " - " in result.title else "Various Artists",
                        year=getattr(result, 'year', None),
                        track_count=0,  # Not available in search results
                        tracks=[],
                        cover_url=getattr(result, 'thumb', None),
                        confidence=0.8,  # Default confidence
                        raw_data={"id": result.id, "title": result.title}
                    )
                    matches.append(match)
                except Exception:
                    continue

            return matches

        except Exception as e:
            self.log(f"Search error: {e}")
            return []

    def _search_with_api(self, title: str, artist: str) -> List[AlbumMatch]:
        """Search using direct API calls"""
        try:
            params = {
                "q": f"{title}",
                "type": "release",
                "per_page": 20
            }

            if artist.lower() != "various artists":
                params["artist"] = artist

            response = self.session.get(
                "https://api.discogs.com/database/search",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

        except requests.RequestException as e:
            self.log(f"Search error: {e}")
            return []

        matches = []
        for result in data.get("results", []):
            # Parse title (format: "Artist - Album")
            full_title = result.get("title", "")
            if " - " in full_title:
                release_artist, release_title = full_title.split(" - ", 1)
            else:
                release_artist = "Various Artists"
                release_title = full_title

            match = AlbumMatch(
                source="discogs",
                source_id=str(result.get("id")),
                title=release_title,
                artist=release_artist,
                year=result.get("year"),
                track_count=0,
                tracks=[],
                cover_url=result.get("cover_image") or result.get("thumb"),
                confidence=0.8,
                raw_data=result
            )
            matches.append(match)

        return matches

    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        """
        Get album details including tracks.

        Args:
            source_id: Discogs release ID

        Returns:
            Album details with tracks
        """
        self._rate_limit_wait()

        if self._use_client:
            return self._get_album_with_client(source_id)
        else:
            return self._get_album_with_api(source_id)

    def _get_album_with_client(self, source_id: str) -> Optional[AlbumMatch]:
        """Get album using discogs_client library"""
        try:
            release = self.client.release(int(source_id))

            # Extract tracks
            tracks = []
            for i, track in enumerate(release.tracklist, 1):
                # Parse duration (format: "M:SS")
                duration_ms = None
                if track.duration:
                    try:
                        parts = track.duration.split(":")
                        if len(parts) == 2:
                            duration_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                    except ValueError:
                        pass

                tracks.append(TrackInfo(
                    title=track.title,
                    track_number=i,
                    disc_number=1,  # Discogs doesn't always provide disc info
                    duration_ms=duration_ms,
                    artist=None  # Would need to parse credits
                ))

            # Get cover image
            images = release.images if hasattr(release, 'images') else []
            cover_url = images[0]['uri'] if images else None

            # Get artist
            artists = release.artists if hasattr(release, 'artists') else []
            artist_name = artists[0].name if artists else "Various Artists"

            return AlbumMatch(
                source="discogs",
                source_id=source_id,
                title=release.title,
                artist=artist_name,
                year=release.year if hasattr(release, 'year') else None,
                track_count=len(tracks),
                tracks=tracks,
                cover_url=cover_url,
                confidence=1.0,
                raw_data={"id": source_id}
            )

        except Exception as e:
            self.log(f"Album lookup error: {e}")
            return None

    def _get_album_with_api(self, source_id: str) -> Optional[AlbumMatch]:
        """Get album using direct API calls"""
        try:
            response = self.session.get(
                f"https://api.discogs.com/releases/{source_id}",
                timeout=30
            )
            response.raise_for_status()
            release = response.json()

        except requests.RequestException as e:
            self.log(f"Album lookup error: {e}")
            return None

        # Extract tracks
        tracks = []
        for i, track in enumerate(release.get("tracklist", []), 1):
            # Skip headings and other non-tracks
            if track.get("type_") != "track":
                continue

            # Parse duration
            duration_ms = None
            duration_str = track.get("duration", "")
            if duration_str:
                try:
                    parts = duration_str.split(":")
                    if len(parts) == 2:
                        duration_ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
                except ValueError:
                    pass

            # Get track artist from extraartists
            track_artist = None
            for extra in track.get("extraartists", []):
                if extra.get("role", "").lower() in ["vocal", "vocals", "featuring"]:
                    track_artist = extra.get("name")
                    break

            tracks.append(TrackInfo(
                title=track.get("title", ""),
                track_number=len(tracks) + 1,
                disc_number=1,
                duration_ms=duration_ms,
                artist=track_artist
            ))

        # Get cover image
        images = release.get("images", [])
        cover_url = None
        for img in images:
            if img.get("type") == "primary":
                cover_url = img.get("uri")
                break
        if not cover_url and images:
            cover_url = images[0].get("uri")

        # Get artist
        artists = release.get("artists", [])
        artist_name = artists[0].get("name", "Various Artists") if artists else "Various Artists"

        return AlbumMatch(
            source="discogs",
            source_id=source_id,
            title=release.get("title", ""),
            artist=artist_name,
            year=release.get("year"),
            track_count=len(tracks),
            tracks=tracks,
            cover_url=cover_url,
            confidence=1.0,
            raw_data=release
        )

    def _clean_title(self, title: str) -> str:
        """Clean album title for better search results."""
        # Replace underscores
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

        return ' '.join(title.split()).strip()


# Quick test
if __name__ == "__main__":
    try:
        source = DiscogsSource()
        print("Testing Discogs API...")
        print()

        # Search for Various Artists album
        results = source.search_album("Buddha-Bar", "Various Artists")
        print(f"Found {len(results)} results for 'Buddha-Bar'")

        if results:
            best = results[0]
            print(f"  Best match: {best.title} by {best.artist}")
            print(f"  Year: {best.year}")
            print(f"  Release ID: {best.source_id}")

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

    except Exception as e:
        print(f"Error: {e}")
