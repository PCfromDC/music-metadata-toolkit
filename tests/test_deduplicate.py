"""Tests for the de-duplication utility.

The audio fingerprint is authoritative for a move: only fingerprint-identical tracks
are auto-moved. Pure-logic tests need no audio; the end-to-end tests synthesize real
tiny audio and control the fingerprint via monkeypatch, so the move/keep/backup logic
is exercised deterministically (independent of fpcalc behavior on very short clips).
"""
from pathlib import Path

import pytest

from tests.synth import make_audio, make_image_bytes
from utilities.core.ffprobe import ffprobe_available
from utilities import deduplicate as dd
from utilities.deduplicate import (
    Track, normalize_for_match, classify, quality_key, _is_generic_title, _copy_base,
)


def _t(name, dur=200.0, bitrate=128000, size=1000, art=False, lossless=False, fp=None, title=None):
    p = Path(name)
    return Track(path=p, title=title or p.stem, artist="A", album="Alb", duration=dur,
                 bitrate=bitrate, size=size, has_art=art, lossless=lossless, fingerprint=fp,
                 norm_title=normalize_for_match(title or p.stem))


# ---------------- normalization ----------------

def test_normalize_strips_explicit_copy_markers_only():
    assert normalize_for_match("Song") == "song"
    assert normalize_for_match("Song (2)") == "song"        # explicit copy marker stripped
    assert normalize_for_match("Song - Copy") == "song"
    assert normalize_for_match("Song 2") == "song 2"        # bare number KEPT (may be semantic)
    assert normalize_for_match("Smell, the Roses!") == normalize_for_match("Smell the Roses")


def test_normalize_keeps_version_words_by_default():
    assert normalize_for_match("Song (Live)") != normalize_for_match("Song")
    assert normalize_for_match("Song [Remastered]") != normalize_for_match("Song")
    assert normalize_for_match("Song (Live)", aggressive=True) == normalize_for_match("Song", aggressive=True)


# ---------------- placeholder titles / copy-base ----------------

def test_generic_titles_detected():
    for g in ["", "track", "track 4", "skit", "skit 5", "intro", "untitled track", "unknown", "7"]:
        assert _is_generic_title(g), g
    for real in ["more than a woman", "sabor a mi", "julia", "the walker"]:
        assert not _is_generic_title(real), real


def test_copy_base_only_for_real_titles():
    assert _copy_base("sabor a mi 2") == "sabor a mi"   # numbered copy of a real title
    assert _copy_base("track 4") is None                # generic base -> not a copy pair
    assert _copy_base("skit 5") is None
    assert _copy_base("song") is None                   # no trailing number


# ---------------- classify: fingerprint is authoritative ----------------

def test_classify_identical_fingerprint_is_strong():
    assert classify(_t("a.mp3", fp="X"), _t("b.mp3", dur=999.0, fp="X")) == "strong"


def test_classify_different_fingerprint_is_distinct_even_at_same_duration():
    # two different recordings of the same song at the same length are NOT a duplicate
    assert classify(_t("a.mp3", dur=197.0, fp="AAA"), _t("b.mp3", dur=197.0, fp="BBB")) == "distinct"


def test_classify_without_fingerprint_is_review_never_move():
    # no fingerprint -> cannot confirm identity -> probable (review), never strong
    assert classify(_t("a.mp3", dur=200.0), _t("b.mp3", dur=201.0)) == "probable"   # close
    assert classify(_t("a.mp3", dur=200.0), _t("b.mp3", dur=260.0)) == "distinct"   # far apart


# ---------------- keeper ranking ----------------

def test_quality_key_prefers_lossless_then_bitrate_then_art():
    flac = _t("x.flac", bitrate=900000, lossless=True)
    mp3_hi = _t("hi.mp3", bitrate=320000)
    mp3_lo = _t("lo.mp3", bitrate=128000)
    assert sorted([mp3_lo, flac, mp3_hi], key=quality_key, reverse=True) == [flac, mp3_hi, mp3_lo]
    a_art = _t("a.mp3", bitrate=320000, art=True)
    a_noart = _t("b.mp3", bitrate=320000, art=False)
    assert sorted([a_noart, a_art], key=quality_key, reverse=True)[0] is a_art
    clean = _t("Song.mp3", bitrate=320000)
    marked = _t("Song www.site.com.mp3", bitrate=320000)
    assert sorted([marked, clean], key=quality_key, reverse=True)[0] is clean


# ---------------- end-to-end (fingerprint controlled via monkeypatch) ----------------

def _fp_all_same(tracks, enabled):
    for t in tracks:
        t.fingerprint = "SAME"


def _fp_all_diff(tracks, enabled):
    for i, t in enumerate(tracks):
        t.fingerprint = f"FP{i}"


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_execute_moves_fingerprint_identical_copy(tmp_path, monkeypatch):
    lib = tmp_path / "Music"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    keeper = make_audio(album / "01 Song.mp3")
    loser = make_audio(album / "01 Song 2.mp3")
    from utilities.core import cover_art
    cover_art.embed_in_file(keeper, make_image_bytes())        # keeper is better (has art)
    monkeypatch.setattr(dd, "_add_fingerprints", _fp_all_same)  # identical audio

    backup = tmp_path / "backup"
    log = tmp_path / "moved.log"
    summ = dd.deduplicate_library(lib, backup_dir=backup, dry_run=False, fingerprint=True,
                                  log_path=str(log), review_path=str(tmp_path / "r.json"))

    assert summ.moved == 1
    assert keeper.exists() and not loser.exists()
    assert (backup / "Artist" / "Album" / "01 Song 2.mp3").exists()
    assert list(album.glob("*.mp3")) == [keeper]
    assert "01 Song 2.mp3" in log.read_text(encoding="utf-8")


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_different_fingerprint_never_moves(tmp_path, monkeypatch):
    # same title, DIFFERENT audio -> fingerprints differ -> not a duplicate -> nothing moved
    lib = tmp_path / "Music"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    a = make_audio(album / "01 Song.mp3")
    b = make_audio(album / "01 Song 2.mp3")
    monkeypatch.setattr(dd, "_add_fingerprints", _fp_all_diff)
    summ = dd.deduplicate_library(lib, backup_dir=tmp_path / "backup", dry_run=False, fingerprint=True)
    assert summ.moved == 0
    assert a.exists() and b.exists()


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    lib = tmp_path / "Music"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    a = make_audio(album / "01 Song.mp3")
    b = make_audio(album / "01 Song 2.mp3")
    monkeypatch.setattr(dd, "_add_fingerprints", _fp_all_same)
    backup = tmp_path / "backup"
    summ = dd.deduplicate_library(lib, backup_dir=backup, dry_run=True, fingerprint=True)
    assert summ.moved == 1                       # would move one
    assert a.exists() and b.exists() and not backup.exists()


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_placeholder_titles_not_grouped(tmp_path, monkeypatch):
    # "Track 4" vs "Track 10" are different songs sharing a placeholder title -> never grouped,
    # even if their fingerprints were identical.
    lib = tmp_path / "Music"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    from mutagen.easyid3 import EasyID3
    f1 = make_audio(album / "04 Track 4.mp3")
    f2 = make_audio(album / "10 Track 10.mp3")
    for f, ti in [(f1, "Track 4"), (f2, "Track 10")]:
        t = EasyID3(str(f)); t["title"] = ti; t.save()
    monkeypatch.setattr(dd, "_add_fingerprints", _fp_all_same)
    summ = dd.deduplicate_library(lib, backup_dir=tmp_path / "backup", dry_run=True, fingerprint=True)
    assert summ.moved == 0 and summ.review_count == 0


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg")
def test_distinct_versions_not_grouped(tmp_path):
    lib = tmp_path / "Music"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    from mutagen.easyid3 import EasyID3
    studio = make_audio(album / "01 Song.mp3")
    live = make_audio(album / "02 Song Live.mp3")
    for f, title in [(studio, "Song"), (live, "Song (Live)")]:
        t = EasyID3(str(f)); t["title"] = title; t.save()
    summ = dd.deduplicate_library(lib, backup_dir=tmp_path / "backup", dry_run=True, fingerprint=False)
    assert summ.moved == 0  # studio vs live are distinct -> not duplicates
