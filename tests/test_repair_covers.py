"""Tests for the corrupted-album-art repair tool.

These reproduce the original bug end to end: deliberately embed an EMPTY APIC
(which ffprobe reports as width=0) and assert the repair tool both FLAGS it and
restores real ffprobe dimensions after a re-embed.
"""

import pytest
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3

from tests.synth import make_audio, make_image_bytes
from utilities import repair_covers
from utilities.core.cover_art import extract_cover_from_file
from utilities.core.ffprobe import attached_pic_dims, ffprobe_available


def _embed_empty_apic(path):
    """Embed an APIC frame with empty data - reproduces the width=0 corruption."""
    audio = MP3(str(path), ID3=ID3)
    if audio.tags is None:
        audio.add_tags()
    audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=b""))
    audio.save()


def test_diagnose_flags_empty_apic(tmp_path):
    track = tmp_path / "track.mp3"
    make_audio(track, "libmp3lame")
    _embed_empty_apic(track)

    status = repair_covers.diagnose_file(track)
    assert status in (repair_covers.STATUS_CORRUPT, repair_covers.STATUS_MISSING)
    assert status != repair_covers.STATUS_OK


def test_diagnose_ok_for_valid_cover(tmp_path):
    from utilities.core import cover_art

    track = tmp_path / "track.mp3"
    make_audio(track, "libmp3lame")
    cover_art.embed_in_file(track, make_image_bytes("JPEG", size=(640, 640)))

    assert repair_covers.diagnose_file(track) == repair_covers.STATUS_OK


def test_diagnose_missing_when_no_art(tmp_path):
    track = tmp_path / "track.mp3"
    make_audio(track, "libmp3lame")
    assert repair_covers.diagnose_file(track) == repair_covers.STATUS_MISSING


def test_diagnose_album_needs_repair(tmp_path):
    bad = tmp_path / "bad.mp3"
    make_audio(bad, "libmp3lame")
    _embed_empty_apic(bad)

    diag = repair_covers.diagnose_album(tmp_path)
    assert diag["total"] == 1
    assert diag["needs_repair"] is True


def test_find_album_folders_skips_backups(tmp_path):
    album = tmp_path / "Album"
    album.mkdir()
    make_audio(album / "track.mp3", "libmp3lame")
    backups = album / "backups"
    backups.mkdir()
    make_audio(backups / "track.mp3", "libmp3lame")

    folders = repair_covers.find_album_folders(tmp_path)
    assert album in folders
    assert backups not in folders


def test_scan_only_makes_no_changes(tmp_path):
    track = tmp_path / "track.mp3"
    make_audio(track, "libmp3lame")
    _embed_empty_apic(track)

    summary = repair_covers.repair_library(tmp_path, scan_only=True)
    assert summary["needs_repair"] == 1
    assert summary["repaired"] == 0
    # No backups folder created in scan-only mode.
    assert not (tmp_path / "backups").exists()


def test_repair_with_cover_override_restores_dims(tmp_path):
    """Offline repair path: inject a valid local image and re-embed."""
    track = tmp_path / "track.mp3"
    make_audio(track, "libmp3lame")
    _embed_empty_apic(track)

    good = make_image_bytes("JPEG", size=(640, 640))
    summary = repair_covers.repair_library(tmp_path, cover_override=good)

    assert summary["repaired"] == 1
    assert summary["files_fixed"] == 1

    # Backup was created before modification.
    assert (tmp_path / "backups" / "track.mp3").exists()

    # The repaired bytes round-trip and ffprobe now sees real dimensions.
    assert extract_cover_from_file(track) == good
    if ffprobe_available():
        dims = attached_pic_dims(track)
        assert dims is not None and dims[0] > 0 and dims[1] > 0


def test_repair_skips_when_no_cover_found(tmp_path):
    """An invalid override yields no usable cover - album left untouched."""
    track = tmp_path / "track.mp3"
    make_audio(track, "libmp3lame")
    _embed_empty_apic(track)

    summary = repair_covers.repair_library(tmp_path, cover_override=b"not an image")
    assert summary["repaired"] == 0
    assert summary["skipped"] == 1
