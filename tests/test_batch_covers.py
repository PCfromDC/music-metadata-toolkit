"""Tests for the unified batch cover-art tool.

These exercise the offline paths (local --image source and --restore from
folder.jpg) so no network is required. The key assertion is the same one that
caught the original bug: after a batch run, ffprobe reports cover dimensions
greater than zero on every track.
"""

import pytest

from tests.synth import make_audio, make_image_bytes
from utilities import batch_covers
from utilities.core.cover_art import extract_cover_from_file
from utilities.core.ffprobe import attached_pic_dims, ffprobe_available


def _make_album(folder, *, with_audio=True):
    folder.mkdir(parents=True, exist_ok=True)
    if with_audio:
        make_audio(folder / "01 track.mp3", "libmp3lame")
        make_audio(folder / "02 track.flac", "flac")
    return folder


def _assert_dims_positive(audio_path):
    """Ground-truth check: ffprobe sees a real cover stream (the Jellyfin check)."""
    if ffprobe_available():
        dims = attached_pic_dims(audio_path)
        assert dims is not None
        assert dims[0] > 0 and dims[1] > 0


def test_album_has_valid_art_detects_missing(tmp_path):
    album = _make_album(tmp_path / "No Art")
    assert batch_covers.album_has_valid_art(album) is False


def test_iter_albums_finds_subfolders(tmp_path):
    _make_album(tmp_path / "Album A")
    _make_album(tmp_path / "Album B")
    (tmp_path / "not an album").mkdir()  # no audio -> ignored
    names = sorted(a.name for a in batch_covers.iter_albums(tmp_path))
    assert names == ["Album A", "Album B"]


def test_iter_albums_handles_single_album(tmp_path):
    album = _make_album(tmp_path / "Solo")
    assert [a.name for a in batch_covers.iter_albums(album)] == ["Solo"]


def test_missing_mode_with_local_image_embeds(tmp_path):
    library = tmp_path / "Various Artists"
    album = _make_album(library / "Album Needing Art")
    image = tmp_path / "cover.jpg"
    image.write_bytes(make_image_bytes("JPEG", size=(640, 640)))

    summary = batch_covers.run(str(library), "missing", image_path=str(image))

    assert summary["albums"] == 1
    assert summary["embedded"] == 1
    assert summary["files_embedded"] == 2
    assert (album / "folder.jpg").exists()
    for track in ("01 track.mp3", "02 track.flac"):
        assert extract_cover_from_file(album / track)
        _assert_dims_positive(album / track)


def test_missing_mode_skips_album_with_art(tmp_path):
    library = tmp_path / "lib"
    album = _make_album(library / "Already Done")
    image = tmp_path / "cover.jpg"
    image.write_bytes(make_image_bytes("JPEG", size=(640, 640)))

    first = batch_covers.run(str(library), "missing", image_path=str(image))
    assert first["embedded"] == 1

    # Second pass: art now present, so the album is skipped.
    second = batch_covers.run(str(library), "missing", image_path=str(image))
    assert second["embedded"] == 0
    assert second["skipped"] == 1


def test_restore_mode_embeds_from_folder_jpg(tmp_path):
    library = tmp_path / "lib"
    album = _make_album(library / "Has Folder Jpg")
    (album / "folder.jpg").write_bytes(make_image_bytes("JPEG", size=(640, 640)))

    summary = batch_covers.run(str(library), "restore")

    assert summary["embedded"] == 1
    for track in ("01 track.mp3", "02 track.flac"):
        _assert_dims_positive(album / track)


def test_restore_mode_no_folder_jpg_is_no_source(tmp_path):
    library = tmp_path / "lib"
    _make_album(library / "No Folder Jpg")
    summary = batch_covers.run(str(library), "restore")
    assert summary["embedded"] == 0
    assert summary["no_source"] == 1


def test_dry_run_writes_nothing(tmp_path):
    library = tmp_path / "lib"
    album = _make_album(library / "Album")
    image = tmp_path / "cover.jpg"
    image.write_bytes(make_image_bytes("JPEG", size=(640, 640)))

    summary = batch_covers.run(str(library), "missing", image_path=str(image), dry_run=True)

    assert summary["embedded"] == 1  # counted as would-embed
    assert not (album / "folder.jpg").exists()
    assert extract_cover_from_file(album / "01 track.mp3") is None


def test_invalid_local_image_raises(tmp_path):
    library = tmp_path / "lib"
    _make_album(library / "Album")
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(Exception):
        batch_covers.run(str(library), "missing", image_path=str(bad))
