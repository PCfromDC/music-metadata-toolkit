"""Tests for the canonical multi-disc consolidator.

Builds a synth fixture tree with "Test Album [Disc 1]" and "Test Album [Disc 2]"
folders, then verifies detection, dry-run (no mutation), and a real consolidation
that merges tracks into one flat folder with discnumber metadata set and the
source folders removed.
"""

import pytest

from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

from tests.synth import make_audio
from utilities.disc_consolidator import DiscConsolidator


def _build_two_disc_album(root):
    """Create Test Album [Disc 1] and [Disc 2] with two MP3 tracks each."""
    disc1 = root / "Test Album [Disc 1]"
    disc2 = root / "Test Album [Disc 2]"
    disc1.mkdir()
    disc2.mkdir()
    make_audio(disc1 / "01 One.mp3", "libmp3lame")
    make_audio(disc1 / "02 Two.mp3", "libmp3lame")
    make_audio(disc2 / "01 Three.mp3", "libmp3lame")
    make_audio(disc2 / "02 Four.mp3", "libmp3lame")
    return disc1, disc2


def test_detect_multi_disc(tmp_path):
    _build_two_disc_album(tmp_path)
    sets = DiscConsolidator().detect_multi_disc(tmp_path)

    assert "Test Album" in sets
    discs = sets["Test Album"]
    assert [d.disc_number for d in discs] == [1, 2]
    assert all(d.track_count == 2 for d in discs)


@pytest.mark.parametrize("folder_name,expected", [
    ("Test Album [Disc 1]", ("Test Album", 1)),
    ("Test Album [CD 2]", ("Test Album", 2)),
    ("Test Album (Disc 3)", ("Test Album", 3)),
    ("Test Album Disc 1", ("Test Album", 1)),
    ("Test Album Disk 2", ("Test Album", 2)),
    ("Test Album CD1", ("Test Album", 1)),
    ("Test Album CD 2", ("Test Album", 2)),
    ("Test Album - Disc 2", ("Test Album", 2)),
    ("Plain Album", None),
])
def test_parse_folder_name(folder_name, expected):
    assert DiscConsolidator().parse_folder_name(folder_name) == expected


def test_dry_run_makes_no_changes(tmp_path):
    disc1, disc2 = _build_two_disc_album(tmp_path)
    results = DiscConsolidator().consolidate_all(tmp_path, dry_run=True)

    assert results["found"] == 1
    assert results["consolidated"] == 1
    # Source folders untouched; no merged target created.
    assert disc1.exists() and disc2.exists()
    assert not (tmp_path / "Test Album").exists()


def test_consolidate_merges_and_sets_metadata(tmp_path):
    disc1, disc2 = _build_two_disc_album(tmp_path)
    results = DiscConsolidator().consolidate_all(tmp_path, dry_run=False)

    assert results["found"] == 1
    assert results["consolidated"] == 1
    assert results["errors"] == 0

    target = tmp_path / "Test Album"
    assert target.is_dir()

    # All four tracks merged into one flat folder with disc-prefixed names.
    names = sorted(p.name for p in target.glob("*.mp3"))
    assert names == ["1-01 One.mp3", "1-02 Two.mp3", "2-01 Three.mp3", "2-02 Four.mp3"]

    # Source disc folders removed.
    assert not disc1.exists()
    assert not disc2.exists()

    # discnumber metadata set to "N/total" and album normalized.
    disc1_track = MP3(str(target / "1-01 One.mp3"), ID3=EasyID3)
    assert disc1_track["discnumber"][0] == "1/2"
    assert disc1_track["album"][0] == "Test Album"

    disc2_track = MP3(str(target / "2-01 Three.mp3"), ID3=EasyID3)
    assert disc2_track["discnumber"][0] == "2/2"


def test_orphaned_disc_not_consolidated(tmp_path):
    (tmp_path / "Lonely Album [Disc 1]").mkdir()
    make_audio(tmp_path / "Lonely Album [Disc 1]" / "01 Solo.mp3", "libmp3lame")

    consolidator = DiscConsolidator()
    results = consolidator.consolidate_all(tmp_path, dry_run=False)

    assert results["found"] == 0
    assert results["orphaned"] == 1
    assert "Lonely Album" in consolidator.orphaned_discs
    # Orphan left in place.
    assert (tmp_path / "Lonely Album [Disc 1]").exists()
