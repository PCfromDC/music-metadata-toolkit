"""Tests for the de-duplication utility.

Pure-logic tests (normalization, classify, keeper ranking, never-remove-all) need
no audio. The end-to-end move test synthesizes real tiny audio with the bundled
ffmpeg and asserts the lesser copy is moved to backup (never deleted), exactly one
copy remains, and the move is logged.
"""
import json
from pathlib import Path

import pytest

from tests.synth import make_audio, make_image_bytes
from utilities.core.ffprobe import ffprobe_available
from utilities import deduplicate as dd
from utilities.deduplicate import Track, normalize_for_match, classify, quality_key


def _t(name, dur=200.0, bitrate=128000, size=1000, art=False, lossless=False, fp=None, title=None):
    p = Path(name)
    return Track(path=p, title=title or p.stem, artist="A", album="Alb", duration=dur,
                 bitrate=bitrate, size=size, has_art=art, lossless=lossless, fingerprint=fp,
                 norm_title=normalize_for_match(title or p.stem))


# ---------------- normalization ----------------

def test_normalize_strips_copy_suffix_and_punct():
    assert normalize_for_match("Song") == "song"
    assert normalize_for_match("Song 2") == "song"
    assert normalize_for_match("Song (2)") == "song"
    assert normalize_for_match("Song - Copy") == "song"
    assert normalize_for_match("Sméll, the Roses!") == normalize_for_match("Smell the Roses")


def test_normalize_keeps_version_words_by_default():
    # live/remaster are NOT folded unless aggressive -> distinct keys -> never merged
    assert normalize_for_match("Song (Live)") != normalize_for_match("Song")
    assert normalize_for_match("Song [Remastered]") != normalize_for_match("Song")
    # aggressive folds parentheticals so variants group
    assert normalize_for_match("Song (Live)", aggressive=True) == normalize_for_match("Song", aggressive=True)


# ---------------- classify (matching rules) ----------------

def test_classify_fingerprint_identical_is_strong():
    a, b = _t("a.mp3", fp="ABC"), _t("b.mp3", dur=999.0, fp="ABC")
    assert classify(a, b) == "strong"  # identical fp wins even with different duration


def test_classify_duration_windows():
    assert classify(_t("a.mp3", dur=200.0), _t("b.mp3", dur=202.5)) == "strong"     # <=3s
    assert classify(_t("a.mp3", dur=200.0), _t("b.mp3", dur=208.0)) == "probable"   # <=10s
    assert classify(_t("a.mp3", dur=200.0), _t("b.mp3", dur=230.0)) == "distinct"   # >10s


# ---------------- keeper ranking ----------------

def test_quality_key_prefers_lossless_then_bitrate_then_art():
    flac = _t("x.flac", bitrate=900000, lossless=True)
    mp3_hi = _t("hi.mp3", bitrate=320000)
    mp3_lo = _t("lo.mp3", bitrate=128000)
    ranked = sorted([mp3_lo, flac, mp3_hi], key=quality_key, reverse=True)
    assert ranked[0] is flac and ranked[1] is mp3_hi and ranked[2] is mp3_lo

    a_art = _t("a.mp3", bitrate=320000, art=True)
    a_noart = _t("b.mp3", bitrate=320000, art=False)
    assert sorted([a_noart, a_art], key=quality_key, reverse=True)[0] is a_art

    clean = _t("Song.mp3", bitrate=320000)
    marked = _t("Song www.site.com.mp3", bitrate=320000)
    assert sorted([marked, clean], key=quality_key, reverse=True)[0] is clean


# ---------------- end-to-end move ----------------

@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg/ffprobe")
def test_execute_moves_loser_keeps_best(tmp_path, monkeypatch):
    lib = tmp_path / "Music"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    keeper = make_audio(album / "01 Song.mp3")
    loser = make_audio(album / "01 Song 2.mp3")

    # Make the keeper unambiguously better: give it embedded art.
    from utilities.core import cover_art
    cover_art.embed_in_file(keeper, make_image_bytes())

    backup = tmp_path / "backup"
    log = tmp_path / "moved.log"
    summ = dd.deduplicate_library(
        lib, backup_dir=backup, scan_only=False, dry_run=False,
        aggressive=False, fingerprint=False, log_path=str(log),
        review_path=str(tmp_path / "review.json"),
    )

    assert summ.moved == 1
    assert keeper.exists()                                   # best copy kept
    assert not loser.exists()                                # loser moved out
    moved_to = backup / "Artist" / "Album" / "01 Song 2.mp3"
    assert moved_to.exists()                                 # ...to mirrored backup path
    remaining = list(album.glob("*.mp3"))
    assert len(remaining) == 1 and remaining[0] == keeper    # exactly one kept
    assert "01 Song 2.mp3" in log.read_text(encoding="utf-8")  # logged for undo


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg/ffprobe")
def test_dry_run_writes_nothing(tmp_path):
    lib = tmp_path / "Music"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    a = make_audio(album / "01 Song.mp3")
    b = make_audio(album / "01 Song 2.mp3")
    backup = tmp_path / "backup"

    summ = dd.deduplicate_library(lib, backup_dir=backup, dry_run=True, fingerprint=False)

    assert summ.moved == 1            # would move one
    assert a.exists() and b.exists()  # but nothing actually moved
    assert not backup.exists()


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg/ffprobe")
def test_distinct_versions_not_grouped(tmp_path):
    lib = tmp_path / "Music"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    from mutagen.easyid3 import EasyID3
    studio = make_audio(album / "01 Song.mp3")
    live = make_audio(album / "02 Song Live.mp3")
    for f, title in [(studio, "Song"), (live, "Song (Live)")]:
        tags = EasyID3(str(f)) if True else None
        tags["title"] = title
        tags.save()

    summ = dd.deduplicate_library(lib, backup_dir=tmp_path / "backup", dry_run=True, fingerprint=False)
    assert summ.moved == 0  # studio vs live are distinct -> not duplicates
