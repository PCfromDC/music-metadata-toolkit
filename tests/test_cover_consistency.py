"""Tests for cover consistency (folder image <-> embedded art parity).

The album folder image is authoritative. Matching is PERCEPTUAL (dHash) so a cover
that was merely re-encoded/resized still matches, while a genuinely different
picture does not. Mismatched tracks get the folder image embedded so the whole
album matches folder.jpg.

Solid-color images have degenerate difference-hashes, so fixtures use gradient
images (distinct, non-trivial hashes).
"""
import io

import pytest
from PIL import Image

from tests.synth import make_audio
from utilities.core.ffprobe import ffprobe_available
from utilities.core import cover_art
from utilities import cover_consistency as cc
from utilities.cover_consistency import (
    dhash, hamming, images_match, find_folder_image, validate_folder_image,
    check_album, sync_album, sync_library,
    NO_FOLDER_IMAGE, FOLDER_INVALID, CONSISTENT, NEEDS_SYNC,
)


def gradient_jpeg(kind="A", size=(64, 64)) -> bytes:
    """Distinct patterned JPEGs so dHash is meaningful (not a flat image)."""
    img = Image.new("L", size)
    px = img.load()
    w, h = size
    for y in range(h):
        for x in range(w):
            if kind == "A":
                v = int(255 * x / (w - 1))          # horizontal gradient
            elif kind == "B":
                v = int(255 * y / (h - 1))          # vertical gradient (very different hash)
            else:
                v = (x * 13 + y * 7) % 256          # diagonal-ish pattern
            px[x, y] = v
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=90)
    return buf.getvalue()


# ---------------- perceptual hash ----------------

def test_same_picture_reencoded_matches():
    a = gradient_jpeg("A", (64, 64))
    a_small = gradient_jpeg("A", (32, 32))          # same picture, different size + re-encode
    assert images_match(dhash(a), dhash(a_small))   # perceptual match despite byte/size diff


def test_different_pictures_do_not_match():
    a, b = gradient_jpeg("A"), gradient_jpeg("B")
    assert not images_match(dhash(a), dhash(b))
    assert hamming(dhash(a), dhash(b)) > cc.MATCH_THRESHOLD


def test_images_match_requires_both_present():
    assert not images_match(None, dhash(gradient_jpeg("A")))
    assert not images_match(dhash(gradient_jpeg("A")), None)


def test_dhash_none_on_garbage():
    assert dhash(b"not an image") is None


# ---------------- folder image discovery + validation ----------------

def test_find_folder_image_prefers_folder_stem(tmp_path):
    (tmp_path / "cover.jpg").write_bytes(gradient_jpeg("A"))
    (tmp_path / "folder.jpg").write_bytes(gradient_jpeg("B"))
    assert find_folder_image(tmp_path).name == "folder.jpg"


def test_find_folder_image_none_when_absent(tmp_path):
    assert find_folder_image(tmp_path) is None


def test_validate_folder_image_rejects_garbage():
    assert validate_folder_image(b"\x00\x01\x02 not an image") is False


def test_validate_folder_image_accepts_real_cover():
    assert validate_folder_image(gradient_jpeg("A")) is True


# ---------------- per-album check (needs audio -> ffmpeg) ----------------

def _album(tmp_path, embeds, folder_kind=None):
    """Build an album: embeds is a list of image-kinds (or None) per track; when
    folder_kind is set, write that folder.jpg. Returns the album Path."""
    album = tmp_path / "Artist" / "Album"
    album.mkdir(parents=True)
    for i, kind in enumerate(embeds, 1):
        track = make_audio(album / f"{i:02d} Song {i}.mp3")
        if kind is not None:
            cover_art.embed_in_file(track, gradient_jpeg(kind), verify=False)
    if folder_kind is not None:
        (album / "folder.jpg").write_bytes(gradient_jpeg(folder_kind))
    return album


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_check_album_consistent(tmp_path):
    album = _album(tmp_path, ["A", "A", "A"], folder_kind="A")
    res = check_album(album)
    assert res.status == CONSISTENT
    assert res.total_tracks == 3 and res.mismatches == []


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_check_album_flags_mismatches(tmp_path):
    # folder=A; track1=A (match), track2=B (different), track3=no art
    album = _album(tmp_path, ["A", "B", None], folder_kind="A")
    res = check_album(album)
    assert res.status == NEEDS_SYNC
    reasons = {t.name: r for t, r in res.mismatches}
    assert reasons == {"02 Song 2.mp3": "different", "03 Song 3.mp3": "no_art"}


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_check_album_no_folder_image(tmp_path):
    album = _album(tmp_path, ["A", "A"], folder_kind=None)
    assert check_album(album).status == NO_FOLDER_IMAGE


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_check_album_invalid_folder_image(tmp_path):
    album = _album(tmp_path, ["A", "A"], folder_kind=None)
    (album / "folder.jpg").write_bytes(b"\x00 not an image \x01")
    res = check_album(album)
    assert res.status == FOLDER_INVALID
    # an invalid folder image is never propagated
    assert res.embedded == 0


# ---------------- execute / dry-run ----------------

@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_sync_album_execute_makes_all_match(tmp_path):
    album = _album(tmp_path, ["A", "B", None], folder_kind="A")
    res = sync_album(album, execute=True)
    assert res.embedded == 2 and res.failed == 0
    # a pristine backup was taken before rewriting
    assert (album / "backups").is_dir()
    # re-check: whole album now matches the folder image
    assert check_album(album).status == CONSISTENT


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_sync_library_dry_run_writes_nothing(tmp_path):
    album = _album(tmp_path, ["A", "B"], folder_kind="A")
    before = (album / "02 Song 2.mp3").read_bytes()
    summ = sync_library(tmp_path, dry_run=True)
    assert summ["needs_sync"] == 1
    assert summ["tracks_to_embed"] == 1
    assert summ["tracks_embedded"] == 0
    assert not (album / "backups").exists()
    assert (album / "02 Song 2.mp3").read_bytes() == before   # untouched


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_sync_library_execute_embeds_and_reports(tmp_path):
    _album(tmp_path, ["A", "B", None], folder_kind="A")
    summ = sync_library(tmp_path, execute=True)
    assert summ["mode"] == "execute"
    assert summ["needs_sync"] == 1
    assert summ["tracks_embedded"] == 2
    assert summ["consistent"] == 0        # it was needs_sync, now fixed


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_sync_library_scan_only_never_writes(tmp_path):
    album = _album(tmp_path, ["A", "B"], folder_kind="A")
    summ = sync_library(tmp_path, scan_only=True, execute=True)  # scan_only wins
    assert summ["mode"] == "scan-only"
    assert summ["tracks_embedded"] == 0
    assert not (album / "backups").exists()
