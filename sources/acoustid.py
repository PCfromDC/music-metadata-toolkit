#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AcoustID audio fingerprinting adapter.
Requires: fpcalc binary (Chromaprint), API key

How it works:
1. Generate audio fingerprint using Chromaprint (fpcalc)
2. Look up fingerprint in AcoustID database
3. Returns MusicBrainz recording IDs that match

API Documentation:
https://acoustid.org/webservice

Get API Key (free):
https://acoustid.org/my-applications

Rate Limits: 3 requests per second
"""

import subprocess
import os
from typing import List, Optional, Dict, Any
from .base import DataSource, AlbumMatch


class AcoustIDSource(DataSource):
    """
    AcoustID audio fingerprinting source.

    Used for identifying unknown tracks or verifying track identity.
    Returns MusicBrainz recording IDs that can be used with MusicBrainzSource.
    """

    API_URL = "https://api.acoustid.org/v2/lookup"

    def __init__(self, api_key: str = "", rate_limit: float = 0.33, fpcalc_path: Optional[str] = None):
        """
        Initialize AcoustID source.

        Args:
            api_key: AcoustID API key (get free at acoustid.org)
            rate_limit: Seconds between requests (0.33 = 3/sec)
            fpcalc_path: Path to fpcalc binary (auto-detect if None)
        """
        super().__init__(rate_limit)
        self.api_key = api_key
        self.fpcalc_path = fpcalc_path or self._find_fpcalc()

    @property
    def name(self) -> str:
        return "acoustid"

    def _find_fpcalc(self) -> Optional[str]:
        """Find fpcalc binary in PATH or common locations"""
        # Check PATH
        try:
            result = subprocess.run(
                ["fpcalc", "-v"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return "fpcalc"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # Check common locations on Windows
        common_paths = [
            r"C:\Program Files\Chromaprint\fpcalc.exe",
            r"C:\Program Files (x86)\Chromaprint\fpcalc.exe",
            os.path.expanduser(r"~\fpcalc.exe"),
            r"D:\music cleanup\utilities\fpcalc.exe"
        ]

        for path in common_paths:
            if os.path.isfile(path):
                return path

        return None

    def is_available(self) -> bool:
        """Check if fingerprinting is available"""
        if not self.api_key:
            self.log("Warning: No API key configured")
            return False

        if not self.fpcalc_path:
            self.log("Warning: fpcalc not found - install Chromaprint")
            return False

        return True

    def fingerprint_file(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """
        Generate fingerprint and look up in AcoustID database.

        Args:
            audio_path: Path to audio file (MP3, FLAC, M4A, etc.)

        Returns:
            Dictionary with match results including MusicBrainz recording IDs
        """
        if not self.is_available():
            return None

        # Generate fingerprint using fpcalc
        fingerprint = self._generate_fingerprint(audio_path)
        if not fingerprint:
            return None

        # Look up in AcoustID
        return self._lookup_fingerprint(fingerprint['fingerprint'], fingerprint['duration'])

    def _generate_fingerprint(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """
        Generate audio fingerprint using Chromaprint.

        Args:
            audio_path: Path to audio file

        Returns:
            Dictionary with 'fingerprint' and 'duration'
        """
        if not self.fpcalc_path:
            return None

        try:
            result = subprocess.run(
                [self.fpcalc_path, "-json", audio_path],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                self.log(f"fpcalc error: {result.stderr}")
                return None

            import json
            data = json.loads(result.stdout)

            return {
                'fingerprint': data.get('fingerprint'),
                'duration': data.get('duration')
            }

        except subprocess.TimeoutExpired:
            self.log(f"fpcalc timeout for {audio_path}")
            return None
        except subprocess.SubprocessError as e:
            self.log(f"fpcalc error: {e}")
            return None
        except json.JSONDecodeError:
            self.log("fpcalc returned invalid JSON")
            return None

    def _lookup_fingerprint(self, fingerprint: str, duration: int) -> Optional[Dict[str, Any]]:
        """
        Look up fingerprint in AcoustID database.

        Args:
            fingerprint: Chromaprint fingerprint string
            duration: Audio duration in seconds

        Returns:
            Match results with recordings
        """
        self._rate_limit_wait()

        import requests

        params = {
            "client": self.api_key,
            "duration": str(int(duration)),
            "fingerprint": fingerprint,
            "meta": "recordings+releasegroups+compress"
        }

        try:
            response = requests.get(
                self.API_URL,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.log(f"AcoustID API error: {e}")
            return None

        if data.get("status") != "ok":
            error = data.get("error", {}).get("message", "Unknown error")
            self.log(f"AcoustID error: {error}")
            return None

        results = data.get("results", [])
        if not results:
            return {"status": "not_found", "results": []}

        # Process results
        matches = []
        for result in results:
            score = result.get("score", 0)
            for recording in result.get("recordings", []):
                matches.append({
                    "score": score,
                    "recording_id": recording.get("id"),
                    "title": recording.get("title"),
                    "artists": [a.get("name") for a in recording.get("artists", [])],
                    "releases": [
                        {
                            "id": rg.get("id"),
                            "title": rg.get("title"),
                            "type": rg.get("type")
                        }
                        for rg in recording.get("releasegroups", [])
                    ]
                })

        # Sort by score
        matches.sort(key=lambda x: x["score"], reverse=True)

        return {
            "status": "ok",
            "results": matches,
            "best_match": matches[0] if matches else None
        }

    def identify_track(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """
        Identify a track and return best match info.

        Convenience method that returns simplified results.

        Args:
            audio_path: Path to audio file

        Returns:
            Dictionary with track info or None if not found
        """
        result = self.fingerprint_file(audio_path)

        if not result or result.get("status") != "ok":
            return None

        best = result.get("best_match")
        if not best or best.get("score", 0) < 0.5:
            return None

        return {
            "confidence": best["score"],
            "recording_id": best["recording_id"],
            "title": best["title"],
            "artist": best["artists"][0] if best["artists"] else None,
            "releases": best["releases"]
        }

    # DataSource interface methods (not primary use case for AcoustID)
    def search_album(self, title: str, artist: str = "Various Artists") -> List[AlbumMatch]:
        """Not applicable - AcoustID identifies individual tracks, not albums"""
        return []

    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        """Not applicable - use recording_id with MusicBrainzSource instead"""
        return None


# Quick test
if __name__ == "__main__":
    # This requires API key and fpcalc to work
    print("AcoustID Source")
    print()

    source = AcoustIDSource()
    print(f"fpcalc found: {source.fpcalc_path}")
    print(f"Available: {source.is_available()}")

    if source.api_key:
        # Test with a sample file
        test_file = "/path/to/music/U2/Achtung Baby/01 Zoo Station.mp3"
        print(f"\nTesting with: {test_file}")

        result = source.identify_track(test_file)
        if result:
            print(f"  Title: {result['title']}")
            print(f"  Artist: {result['artist']}")
            print(f"  Confidence: {result['confidence']:.0%}")
        else:
            print("  No match found")
    else:
        print("\nNo API key configured. Get one at https://acoustid.org/my-applications")
