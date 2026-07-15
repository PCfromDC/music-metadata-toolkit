#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Album importer audio-quality ranking + duplicate-decision logic (offline units).

No network and no real audio files: the ranking works on plain quality dicts (as
``track_quality`` would produce from mutagen), so the ordering rules and the dedup
match are tested deterministically.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utilities.importer import (  # noqa: E402
    quality_key, aggregate_quality, quality_label, track_action,
    _find_existing, _norm, _clean_title, _clean_folder,
)


def _q(lossless=False, bitdepth=0, samplerate=44100, bitrate=0, fmt="AAC"):
    return {"lossless": lossless, "bitdepth": bitdepth, "samplerate": samplerate,
            "bitrate": bitrate, "fmt": fmt}


# ---------------- quality ranking ----------------

def test_lossless_always_beats_lossy():
    flac = _q(lossless=True, bitdepth=16, samplerate=44100, fmt="FLAC")
    aac320 = _q(bitrate=320000, fmt="AAC")
    # even a huge-bitrate lossy loses to a modest lossless
    assert quality_key(flac) > quality_key(aac320)
    assert quality_key(_q(lossless=True, bitdepth=16, samplerate=44100)) > quality_key(_q(bitrate=999000))


def test_within_lossy_same_codec_higher_bitrate_wins():
    # same codec -> the efficiency factor cancels, so bitrate decides
    assert quality_key(_q(bitrate=320000, fmt="MP3")) > quality_key(_q(bitrate=256000, fmt="MP3"))
    assert quality_key(_q(bitrate=256000, fmt="AAC")) > quality_key(_q(bitrate=192000, fmt="AAC"))
    assert quality_key(_q(bitrate=192000, fmt="MP3")) > quality_key(_q(bitrate=128000, fmt="MP3"))


def test_aac_preferred_over_mp3_at_similar_bitrate():
    aac256 = _q(bitrate=256000, fmt="AAC")
    mp3_320 = _q(bitrate=320000, fmt="MP3")
    # AAC 256k is treated as >= MP3 320k (codec efficiency): "keep the AAC"
    assert quality_key(aac256) >= quality_key(mp3_320)
    assert track_action(mp3_320, aac256) == "skip"                      # MP3 320 does NOT replace AAC 256
    assert track_action(aac256, _q(bitrate=192000, fmt="MP3")) == "upgrade"  # AAC beats low MP3


def test_within_lossless_higher_depth_x_rate_wins():
    hi = _q(lossless=True, bitdepth=24, samplerate=96000, fmt="FLAC")   # 24/96
    lo = _q(lossless=True, bitdepth=16, samplerate=44100, fmt="FLAC")   # 16/44.1
    assert quality_key(hi) > quality_key(lo)
    assert quality_key(_q(lossless=True, bitdepth=24, samplerate=48000)) > quality_key(lo)


def test_equal_quality_is_not_an_upgrade():
    a = _q(bitrate=256000)
    b = _q(bitrate=256000)
    assert not (quality_key(a) > quality_key(b))          # equal -> SKIP
    assert quality_key(None) == (0, 0, 0)                 # unknown ranks lowest


# ---------------- album aggregation ----------------

def test_aggregate_majority_lossless_and_median():
    # 2 FLAC + 1 AAC -> majority lossless; medians reported
    tracks = [
        _q(lossless=True, bitdepth=16, samplerate=44100, fmt="FLAC"),
        _q(lossless=True, bitdepth=16, samplerate=44100, fmt="FLAC"),
        _q(bitrate=256000, fmt="AAC"),
    ]
    agg = aggregate_quality(tracks)
    assert agg["lossless"] is True
    assert agg["tracks"] == 3
    assert agg["mixed"] is True                           # FLAC + AAC
    assert quality_key(agg)[0] == 1                        # ranks in the lossless tier


def test_aggregate_all_aac_is_lossy():
    agg = aggregate_quality([_q(bitrate=256000), _q(bitrate=256000)])
    assert agg["lossless"] is False and agg["mixed"] is False
    assert quality_key(agg) == (0, 0, round(256000 * 1.30))   # AAC codec-adjusted


def test_aggregate_empty_is_none():
    assert aggregate_quality([]) is None
    assert quality_label(None) == "?"


def test_quality_labels():
    assert quality_label(_q(lossless=True, bitdepth=24, samplerate=96000, fmt="FLAC")).startswith("FLAC 24/96")
    assert quality_label(_q(lossless=True, bitdepth=16, samplerate=44100, fmt="ALAC")).startswith("ALAC 16/44.1")
    assert quality_label(_q(bitrate=256000, fmt="AAC")) == "AAC 256k"


# ---------------- per-track action (add / upgrade / skip) ----------------

def test_track_added_when_no_existing_match():
    # a source track the library album is missing -> ADD (fills the album)
    assert track_action(_q(bitrate=256000), None) == "add"


def test_track_upgraded_when_higher_quality():
    # a single higher-quality source track upgrades the matching track in a full album
    assert track_action(_q(bitrate=256000), _q(bitrate=192000)) == "upgrade"
    assert track_action(_q(lossless=True, bitdepth=16, samplerate=44100), _q(bitrate=320000)) == "upgrade"


def test_track_skipped_when_equal_or_lower():
    assert track_action(_q(bitrate=256000), _q(bitrate=256000)) == "skip"
    assert track_action(_q(bitrate=192000), _q(bitrate=256000)) == "skip"
    # lossy never upgrades an existing lossless track
    assert track_action(_q(bitrate=320000), _q(lossless=True, bitdepth=16, samplerate=44100)) == "skip"


# ---------------- dedup match ----------------

def test_find_existing_by_mbid_then_artist_album():
    p1, p2 = Path("Music/U2/Achtung Baby"), Path("Music/Radiohead/OK Computer")
    index = {
        "mb:abc-123": p1,
        "aa:u2|achtungbaby": p1,
        "aa:radiohead|okcomputer": p2,
    }
    # MBID wins even if names differ
    assert _find_existing(index, "abc-123", "Different", "Whatever") == p1
    # normalized artist+album fallback (punctuation/case-insensitive)
    assert _find_existing(index, None, "Radiohead", "OK Computer!") == p2
    # no match -> None (new import)
    assert _find_existing(index, None, "Beck", "Odelay") is None


# ---------------- name cleaning + normalization ----------------

def test_clean_title_strips_quality_and_year_junk():
    assert _clean_title("Achtung Baby (1991)") == "Achtung Baby"
    assert _clean_title("Some Album (256 kbps)") == "Some Album"
    assert _clean_title("  Spaced   Out  ") == "Spaced Out"


def test_clean_folder_keeps_number_leading_album_names():
    # album folders never carry a track prefix, so a leading number is part of the name
    assert _clean_folder("18 Months") == "18 Months"
    assert _clean_folder("100 Hits - Movie Favorites") == "100 Hits - Movie Favorites"
    assert _clean_folder("1989") == "1989"
    assert _clean_folder("Achtung_ Baby") == "Achtung Baby"


def test_norm_transliterates_and_strips():
    assert _norm("OK Computer!") == "okcomputer"
    assert _norm("Sgt. Pepper's Lonely Hearts Club Band") == "sgtpepperslonelyheartsclubband"
    # accented / unicode normalizes to ASCII so dedup matches across tag vs folder
    assert _norm("Jack Ü") == _norm("Jack U")
    assert _norm("Café Tacvba") == _norm("Cafe Tacvba")
    assert _norm("18 Months") == "18months"


def test_number_leading_album_dedup_matches():
    # a source "18 Months" must match an existing library "18 Months" (not import as NEW)
    index = {"aa:calvinharris|18months": Path("Music/Calvin Harris/18 Months")}
    assert _find_existing(index, None, "Calvin Harris", "18 Months") is not None
