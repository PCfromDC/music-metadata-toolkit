"""Canonical Windows-safe naming helper for the music metadata toolkit.

This is the single source of truth for turning an album/track name into a
filesystem-safe folder name. The logic used to be copy-pasted into
``utilities/scan_folders.py`` and ``utilities/folder_validator.py`` (with subtle
differences), so it now lives here.

Transformations applied by :func:`make_windows_safe`:

* ``:`` becomes `` -`` (a colon is illegal on Windows; a dash reads naturally)
* the remaining Windows-illegal characters ``? * " < > |`` are stripped
* accented characters are transliterated to ASCII (``Cafe`` from ``Cafe``)
* runs of whitespace are collapsed to a single space and trimmed
* the result is capped at :data:`MAX_LENGTH` characters
"""

from __future__ import annotations

import unicodedata

# Windows-illegal characters that are simply removed (colon is handled
# separately because it maps to " -" rather than being deleted).
_STRIP_CHARS = ('?', '*', '"', '<', '>', '|')

# Cap folder names to a sane length well under the Windows MAX_PATH budget.
MAX_LENGTH = 200


def transliterate(name: str) -> str:
    """Return ``name`` with accented characters reduced to ASCII.

    Uses NFKD decomposition to split base letters from combining marks, drops
    the marks, then re-encodes to ASCII (dropping anything left untranslatable).
    """
    decomposed = unicodedata.normalize("NFKD", name)
    return decomposed.encode("ascii", "ignore").decode("ascii")


def make_windows_safe(name: str) -> str:
    """Convert an album/track name into a Windows-safe folder name."""
    if not name:
        return ""

    result = transliterate(name)

    # Replace colon with ' -' (subtitle separator).
    result = result.replace(':', ' -')

    # Remove the remaining Windows-illegal characters.
    for char in _STRIP_CHARS:
        result = result.replace(char, '')

    # Collapse runs of whitespace and trim.
    result = ' '.join(result.split())

    # Cap length to stay within filesystem limits.
    if len(result) > MAX_LENGTH:
        result = result[:MAX_LENGTH].strip()

    return result
