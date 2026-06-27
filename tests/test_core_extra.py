"""Deterministic coverage of utilities/core beyond the round-trip happy path.

These tests deepen the foundation harness: magic-byte detection, the
:func:`validate_image` size policy (reject below MIN_DIMENSION, warn-but-pass
between MIN_DIMENSION and RECOMMENDED_DIMENSION), the ffprobe "no cover" case,
and the batch fail-soft accounting in :func:`embed_in_album`.

Helpers are reused from tests/synth.py (imported, never modified).
"""

import pytest

from tests.synth import make_audio, make_image_bytes
from utilities.core import cover_art
from utilities.core.cover_art import (
    MIN_DIMENSION,
    RECOMMENDED_DIMENSION,
    InvalidCoverArt,
)
from utilities.core.ffprobe import attached_pic_dims, ffprobe_available


# --------------------------------------------------------------------------- #
# detect_image_mime
# --------------------------------------------------------------------------- #


def test_detect_image_mime_jpeg():
    assert cover_art.detect_image_mime(make_image_bytes("JPEG")) == "image/jpeg"


def test_detect_image_mime_png():
    assert cover_art.detect_image_mime(make_image_bytes("PNG")) == "image/png"


def test_detect_image_mime_empty_is_none():
    assert cover_art.detect_image_mime(b"") is None


def test_detect_image_mime_short_input_is_none():
    # Shorter than the PNG magic and not a JPEG header: must not index out of range.
    assert cover_art.detect_image_mime(b"\x89PNG") is None
    assert cover_art.detect_image_mime(b"\xff") is None


def test_detect_image_mime_non_image_is_none():
    assert cover_art.detect_image_mime(b"<!DOCTYPE html>") is None


# --------------------------------------------------------------------------- #
# validate_image size policy
# --------------------------------------------------------------------------- #


def test_validate_image_low_res_passes_but_warns():
    # >= MIN_DIMENSION but < RECOMMENDED_DIMENSION: valid art, low-quality warning.
    low = make_image_bytes("PNG", size=(100, 100))
    assert cover_art.validate_image(low) == "image/png"
    warning = cover_art.quality_warning(low)
    assert warning is not None
    assert "low-resolution" in warning


def test_validate_image_at_min_dimension_boundary_passes():
    edge = make_image_bytes("PNG", size=(MIN_DIMENSION, MIN_DIMENSION))
    assert cover_art.validate_image(edge) == "image/png"


def test_validate_image_below_min_dimension_rejected():
    # Between 1 and MIN_DIMENSION - 1 px: a real, decodable image that is still
    # too small to be album art.
    tiny = make_image_bytes("PNG", size=(MIN_DIMENSION - 1, MIN_DIMENSION - 1))
    with pytest.raises(InvalidCoverArt):
        cover_art.validate_image(tiny)


def test_validate_image_non_image_rejected():
    with pytest.raises(InvalidCoverArt):
        cover_art.validate_image(b"this is plainly not an image")


def test_validate_image_empty_rejected():
    with pytest.raises(InvalidCoverArt):
        cover_art.validate_image(b"")


def test_quality_warning_none_for_recommended_size():
    big = make_image_bytes("JPEG", size=(RECOMMENDED_DIMENSION, RECOMMENDED_DIMENSION))
    assert cover_art.quality_warning(big) is None


# --------------------------------------------------------------------------- #
# ffprobe.attached_pic_dims
# --------------------------------------------------------------------------- #


def test_attached_pic_dims_none_when_no_cover(tmp_path):
    # A freshly synthesized audio file has no embedded cover stream, so ffprobe
    # (or the no-ffprobe fallback) must report None rather than (0, 0).
    path = make_audio(tmp_path / "no_cover.mp3", "libmp3lame")
    assert attached_pic_dims(path) is None


# --------------------------------------------------------------------------- #
# embed_in_album fail-soft accounting
# --------------------------------------------------------------------------- #


def test_embed_in_album_counts_failures_and_continues(tmp_path):
    # One genuine audio file plus one file with an audio extension but junk
    # content: the junk file fails to embed and is logged, the good one succeeds.
    make_audio(tmp_path / "good.mp3", "libmp3lame")
    (tmp_path / "broken.flac").write_bytes(b"not a real flac stream")

    result = cover_art.embed_in_album(tmp_path, make_image_bytes("JPEG"))

    assert result["total"] == 2
    assert result["embedded"] == 1
    assert result["failed"] == 1
    assert len(result["errors"]) == 1
    assert "broken.flac" in result["errors"][0]
    # folder.jpg is written because at least one file embedded successfully.
    assert (tmp_path / "folder.jpg").exists()


def test_embed_in_album_no_folder_jpg_when_all_fail(tmp_path):
    (tmp_path / "broken.mp3").write_bytes(b"junk bytes, not mp3")
    result = cover_art.embed_in_album(tmp_path, make_image_bytes("JPEG"))
    assert result["total"] == 1
    assert result["embedded"] == 0
    assert result["failed"] == 1
    assert not (tmp_path / "folder.jpg").exists()


# --------------------------------------------------------------------------- #
# PNG round-trip with ffprobe ground truth
# --------------------------------------------------------------------------- #


def test_png_cover_roundtrip_ffprobe_dims(tmp_path):
    path = make_audio(tmp_path / "track.mp3", "libmp3lame")
    data = make_image_bytes("PNG", size=(640, 640))
    cover_art.embed_in_file(path, data)

    if ffprobe_available():
        dims = attached_pic_dims(path)
        assert dims is not None
        assert dims[0] > 0 and dims[1] > 0

    assert cover_art.extract_cover_from_file(path) == data
