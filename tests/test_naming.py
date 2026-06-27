"""Tests for the canonical Windows-safe naming helper and folder_validator reuse.

Covers the transform contract (colon -> " -", strip illegal chars, accent
transliteration, whitespace collapse, length cap) and exercises FolderValidator
end to end on a small synthesized fixture folder so the shared helper is proven
in the real scan/expected-name path.
"""

import pytest
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

from tests.synth import make_audio
from utilities.core.naming import MAX_LENGTH, make_windows_safe
from utilities.folder_validator import FolderValidator


def test_colon_becomes_dash():
    assert make_windows_safe("Album: X") == "Album - X"


def test_illegal_chars_stripped():
    assert make_windows_safe('What? Star* "Quote" <a> b|c') == "What Star Quote a bc"


def test_accents_transliterated():
    assert make_windows_safe('Café') == 'Cafe'          # precomposed e-acute
    assert make_windows_safe("Café") == "Cafe"          # e + combining acute (U+0301)
    assert make_windows_safe('Ñoño') == 'Nono'         # tilde N and n


def test_whitespace_collapsed_and_trimmed():
    assert make_windows_safe("  Album   Name  ") == "Album Name"


def test_empty_string():
    assert make_windows_safe("") == ""


def test_length_capped():
    result = make_windows_safe("A" * 500)
    assert len(result) <= MAX_LENGTH


def _set_album(folder, album):
    mp3 = folder / "01 Track.mp3"
    make_audio(mp3, "libmp3lame")
    audio = MP3(str(mp3), ID3=EasyID3)
    audio["album"] = album
    audio["title"] = "Track"
    audio.save()


def test_folder_validator_detects_and_fixes(tmp_path):
    # Folder name uses a colon-substituted form; metadata has the colon.
    bad = tmp_path / "Greatest Hits_ Volume 1"
    bad.mkdir()
    _set_album(bad, "Greatest Hits: Volume 1")

    # A folder that already matches its (windows-safe) metadata - no issue.
    good = tmp_path / "Clean Album"
    good.mkdir()
    _set_album(good, "Clean Album")

    validator = FolderValidator()
    issues = validator.scan(tmp_path)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.folder_name == "Greatest Hits_ Volume 1"
    assert issue.expected_name == "Greatest Hits - Volume 1"

    assert validator.fix_issue(issue) is True
    assert (tmp_path / "Greatest Hits - Volume 1").exists()
    assert not bad.exists()
