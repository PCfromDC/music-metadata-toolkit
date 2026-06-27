"""Shared core helpers for the music metadata toolkit.

This package is the single source of truth for logic that used to be copy-pasted
across utilities/, agents/, and orchestrator/ - most importantly album cover art
handling, which was producing invalid (width=0/height=0) embeds.

Import as:  from utilities.core import cover_art, ffprobe, audio_file
"""

from . import audio_file, cover_art, ffprobe  # noqa: F401

__all__ = ["audio_file", "cover_art", "ffprobe"]
