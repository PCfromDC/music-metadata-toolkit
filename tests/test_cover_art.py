"""Round-trip and negative tests for the validated cover-art pipeline.

The key assertion reproduces the exact check that flagged the original bug:
after embedding, ffprobe (the engine Jellyfin uses) must report a cover stream
with width > 0 and height > 0.
"""

import pytest

from tests.synth import make_audio, make_image_bytes
from utilities.core import cover_art
from utilities.core.cover_art import InvalidCoverArt
from utilities.core.ffprobe import attached_pic_dims, ffprobe_available

AUDIO = [("track.mp3", "libmp3lame"), ("track.m4a", "aac"), ("track.flac", "flac")]


@pytest.fixture(params=AUDIO, ids=[a[0] for a in AUDIO])
def audio_file(request, tmp_path):
    name, codec = request.param
    path = tmp_path / name
    make_audio(path, codec)
    return path


@pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
def test_embed_roundtrip_ffprobe_dims(audio_file, fmt):
    data = make_image_bytes(fmt=fmt, size=(640, 640))
    cover_art.embed_in_file(audio_file, data)

    # Ground truth: ffprobe sees a real cover stream (the Jellyfin check).
    if ffprobe_available():
        dims = attached_pic_dims(audio_file)
        assert dims is not None
        assert dims[0] > 0 and dims[1] > 0

    # And the bytes round-trip exactly.
    assert cover_art.extract_cover_from_file(audio_file) == data


def test_validate_image_returns_mime():
    assert cover_art.validate_image(make_image_bytes("JPEG")) == "image/jpeg"
    assert cover_art.validate_image(make_image_bytes("PNG")) == "image/png"


def test_empty_bytes_rejected(audio_file):
    with pytest.raises(InvalidCoverArt):
        cover_art.embed_in_file(audio_file, b"")


def test_html_payload_rejected(audio_file):
    with pytest.raises(InvalidCoverArt):
        cover_art.embed_in_file(audio_file, b"<!DOCTYPE html><html>not an image</html>")


def test_truncated_jpeg_rejected(audio_file):
    truncated = make_image_bytes("JPEG")[:50]  # valid magic bytes, undecodable
    with pytest.raises(InvalidCoverArt):
        cover_art.embed_in_file(audio_file, truncated)


def test_tiny_image_rejected(audio_file):
    tiny = make_image_bytes("PNG", size=(10, 10))  # below MIN_DIMENSION
    with pytest.raises(InvalidCoverArt):
        cover_art.embed_in_file(audio_file, tiny)


def test_existing_art_preserved_when_new_is_invalid(audio_file):
    good = make_image_bytes("JPEG", size=(640, 640))
    cover_art.embed_in_file(audio_file, good)
    with pytest.raises(InvalidCoverArt):
        cover_art.embed_in_file(audio_file, b"")  # invalid must not wipe good art
    assert cover_art.extract_cover_from_file(audio_file) == good


def test_embed_in_album_fail_soft(tmp_path):
    make_audio(tmp_path / "a.mp3", "libmp3lame")
    make_audio(tmp_path / "b.flac", "flac")
    result = cover_art.embed_in_album(tmp_path, make_image_bytes("JPEG"))
    assert result["total"] == 2
    assert result["embedded"] == 2
    assert result["failed"] == 0
    assert (tmp_path / "folder.jpg").exists()


def test_embed_in_album_invalid_source_raises(tmp_path):
    make_audio(tmp_path / "a.mp3", "libmp3lame")
    with pytest.raises(InvalidCoverArt):
        cover_art.embed_in_album(tmp_path, b"")
