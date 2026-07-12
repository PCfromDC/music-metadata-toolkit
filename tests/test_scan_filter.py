"""The canonical library-walk exclusion rules (utilities.core.audio_file).

Every walker (scan, validate, dedupe, cover-repair, folder-art) shares these so a
NAS recycle bin or OS metadata dir can never be mistaken for an album. Real music
folders that merely *look* odd (leading dots, symbols) must still be scanned.
"""
import os

from utilities.core.audio_file import (
    is_excluded_dir, is_excluded_path, prune_dirs, EXCLUDED_DIR_NAMES,
)


# ---------------- excluded: recycle bins / system / backup dirs ----------------

def test_recycle_and_system_dirs_excluded():
    for name in [
        ".recycle", ".Recycle", "#recycle", "@eaDir", "#snapshot",
        "$RECYCLE.BIN", "System Volume Information", "recycler",
        ".Trashes", ".Trash-1000", ".Spotlight-V100", ".fseventsd",
        ".stfolder", ".DS_Store", "lost+found",
    ]:
        assert is_excluded_dir(name), name


def test_toolkit_own_stores_excluded():
    for name in ["backups", ".cover_backup", "_duplicates"]:
        assert is_excluded_dir(name), name


# ---------------- NOT excluded: real album / artist folders ----------------

def test_real_music_folders_not_excluded():
    # Bands/albums that start with a dot or symbol are still legitimate music.
    for name in [
        ".38 Special", "...And You Will Know Us by the Trail of Dead",
        "U2", "Achtung Baby", "Café Tacvba", "Sigur Rós",
        "Disc 1", "CD2", "Various Artists", "70's Disco Ball Party Pack",
    ]:
        assert not is_excluded_dir(name), name


# ---------------- path-level pruning ----------------

def test_is_excluded_path_prunes_nested_recycle():
    root = os.path.join("music")
    # anything under a .recycle component is excluded, however deep
    assert is_excluded_path(root, os.path.join("music", ".recycle", "x", "y", "z"))
    assert is_excluded_path(root, os.path.join("music", "Various Artists", "@eaDir"))
    # a clean album path is kept
    assert not is_excluded_path(root, os.path.join("music", "U2", "Achtung Baby"))


def test_is_excluded_dir_takes_basename():
    # Full paths are reduced to their final component before matching.
    assert is_excluded_dir(os.path.join("music", ".recycle"))
    assert not is_excluded_dir(os.path.join("music", "Achtung Baby"))


def test_prune_dirs_mutates_in_place():
    dirs = ["U2", ".recycle", "@eaDir", "Achtung Baby", "backups"]
    prune_dirs(dirs)
    assert dirs == ["U2", "Achtung Baby"]  # os.walk contract: same list object, filtered


def test_excluded_names_are_lowercase():
    # The set is compared case-insensitively; keep it normalized to avoid misses.
    assert all(n == n.lower() for n in EXCLUDED_DIR_NAMES)
