# Data Source Adapters
# Adapters for MusicBrainz, iTunes, AcoustID, Discogs, Spotify, etc.

from .base import DataSource, AlbumMatch, TrackInfo
from .musicbrainz import MusicBrainzSource
from .itunes import iTunesSource
from .acoustid import AcoustIDSource
from .spotify import SpotifySource
from .discogs import DiscogsSource

__all__ = [
    'DataSource',
    'AlbumMatch',
    'TrackInfo',
    'MusicBrainzSource',     # Priority 1 - CD-focused, authoritative
    'SpotifySource',         # Priority 2 - Largest catalog
    'DiscogsSource',         # Priority 3 - Rare/vinyl releases
    'iTunesSource',          # Priority 4 - Good for popular releases
    'AcoustIDSource'         # Audio fingerprinting
]
