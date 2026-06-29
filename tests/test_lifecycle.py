"""Tests for the lifecycle pipeline plumbing.

Covers the pieces the lifecycle runner chains together:

  * Queue archive + clear at run start: a non-empty queue is copied to a history
    dir then emptied (orchestrator.queue.QueueManager.archive + clear).
  * run_history.append_run grows a JSON list and last_run returns the newest.
  * End-to-end DRY-RUN over a synthetic 2-album library (one with a duplicate
    track, one missing folder.jpg): reports a would-move + a would-create, writes
    a run-history record, and touches no music.
  * End-to-end EXECUTE over the same fixture: the duplicate is MOVED to backup
    (never deleted) and a real folder.jpg is created in the missing-art album.

The audio fixtures are genuine tiny streams (tests/synth.make_audio), so the
ffmpeg/ffprobe-dependent end-to-end tests are guarded by ffprobe_available().
Everything is hermetic (tmp_path), no network, no real library.
"""
import json
from pathlib import Path

import pytest

from tests.synth import make_audio, make_image_bytes
from utilities.core.ffprobe import ffprobe_available
from orchestrator.queue import QueueManager, AlbumStatus, Priority
from orchestrator import run_history


# ---------------- queue archive + clear ----------------

def test_archive_copies_then_clear_empties(tmp_path):
    qpath = tmp_path / "state" / "queue.json"
    history = tmp_path / "state" / "history"

    q = QueueManager(queue_path=str(qpath))
    q.add("artist/album", str(tmp_path / "Music" / "artist" / "album"),
          status=AlbumStatus.SCANNED, priority=Priority.HIGH)
    assert len(q) == 1
    assert qpath.exists()

    # Archive to history with a fixed stamp, then clear for a fresh run.
    archived = q.archive(history, timestamp="20260629-120000")
    assert archived is not None
    assert archived == history / "queue-20260629-120000.json"
    assert archived.exists()

    # Archived copy preserves the queued item...
    saved = json.loads(archived.read_text(encoding="utf-8"))
    assert "artist/album" in saved
    assert saved["artist/album"]["status"] == AlbumStatus.SCANNED.value

    # ...and clearing empties both the in-memory queue and the on-disk file.
    q.clear()
    assert len(q) == 0
    assert json.loads(qpath.read_text(encoding="utf-8")) == {}


def test_archive_noop_on_empty_queue(tmp_path):
    q = QueueManager(queue_path=str(tmp_path / "state" / "queue.json"))
    assert len(q) == 0
    assert q.archive(tmp_path / "history") is None
    # Nothing written when there is nothing to archive.
    assert not (tmp_path / "history").exists()


# ---------------- run_history ----------------

def _record(target="//srv/Music/U2", mode="dry-run", **phase_overrides):
    phases = {
        "scanned": 0, "identified": 0, "validated": 0, "needs_review": 0,
        "deduped_moved": 0, "covers_repaired": 0, "folderjpg_added": 0,
        "fixed": 0, "flagged": 0,
    }
    phases.update(phase_overrides)
    return {"timestamp": "2026-06-29T12:00:00", "target": target,
            "mode": mode, "phases": phases}


def test_append_run_grows_list_and_last_run_is_newest(tmp_path):
    path = tmp_path / "state" / "run_history.json"

    assert run_history.last_run(str(path)) is None  # no history yet

    run_history.append_run(_record(mode="dry-run", scanned=2), path=str(path))
    run_history.append_run(_record(mode="execute", scanned=5, deduped_moved=1), path=str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 2

    newest = run_history.last_run(str(path))
    assert newest is not None
    assert newest["mode"] == "execute"
    assert newest["phases"]["scanned"] == 5
    assert newest["phases"]["deduped_moved"] == 1


def test_append_run_tolerates_corrupt_file(tmp_path):
    path = tmp_path / "state" / "run_history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not json", encoding="utf-8")

    run_history.append_run(_record(mode="execute"), path=str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 1


# ---------------- end-to-end fixture ----------------

def _build_library(tmp_path):
    """Synthetic 2-album library.

    Album 'Dupes': two tracks, same title + (identical) duration, the keeper made
    unambiguously better with embedded art; it already has a folder.jpg so the
    folder-art phase ignores it. Album 'NeedsArt': one track with embedded art and
    NO folder image -> a folder.jpg should be generated for it.

    Returns (lib, keeper, loser, needs_art_track, needs_art_album).
    """
    from utilities.core import cover_art

    lib = tmp_path / "Music"

    dupes = lib / "Artist" / "Dupes"
    dupes.mkdir(parents=True)
    keeper = make_audio(dupes / "01 Song.mp3")
    loser = make_audio(dupes / "01 Song 2.mp3")
    cover_art.embed_in_file(keeper, make_image_bytes())  # keeper wins ranking
    # Pre-existing folder image so generate_folder_art skips this album.
    (dupes / "folder.jpg").write_bytes(make_image_bytes())

    needs_art_album = lib / "Artist" / "NeedsArt"
    needs_art_album.mkdir(parents=True)
    needs_art_track = make_audio(needs_art_album / "01 Tune.mp3")
    cover_art.embed_in_file(needs_art_track, make_image_bytes())

    return lib, keeper, loser, needs_art_track, needs_art_album


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg/ffprobe")
def test_lifecycle_dry_run_reports_but_changes_nothing(tmp_path):
    from utilities.deduplicate import deduplicate_library
    from utilities.generate_folder_art import generate_folder_art

    lib, keeper, loser, needs_art_track, needs_art_album = _build_library(tmp_path)
    backup = tmp_path / "backup"
    run_history_path = tmp_path / "state" / "run_history.json"

    # dedupe (dry-run): would move the lesser duplicate, but touches nothing.
    dd = deduplicate_library(str(lib), backup_dir=backup, dry_run=True, fingerprint=False)
    assert dd.moved == 1

    # covers/folder-art (dry-run): would create one folder.jpg (NeedsArt only).
    gfa = generate_folder_art(str(lib), execute=False)
    assert gfa["written"] == 1
    assert gfa["executed"] is False

    # A run-history record is produced (mirroring what cmd_lifecycle appends).
    record = _record(target=str(lib), mode="dry-run",
                     deduped_moved=dd.moved, folderjpg_added=gfa["written"])
    run_history.append_run(record, path=str(run_history_path))
    last = run_history.last_run(str(run_history_path))
    assert last["mode"] == "dry-run"
    assert last["phases"]["deduped_moved"] == 1
    assert last["phases"]["folderjpg_added"] == 1

    # NO music / files changed.
    assert keeper.exists() and loser.exists()
    assert not backup.exists()
    assert not (needs_art_album / "folder.jpg").exists()
    assert not (needs_art_album / "folder.png").exists()
    assert needs_art_track.exists()


@pytest.mark.skipif(not ffprobe_available(), reason="needs bundled ffmpeg/ffprobe")
def test_lifecycle_execute_moves_dupe_and_writes_folder_art(tmp_path):
    from utilities.deduplicate import deduplicate_library
    from utilities.generate_folder_art import generate_folder_art

    lib, keeper, loser, needs_art_track, needs_art_album = _build_library(tmp_path)
    backup = tmp_path / "backup"
    run_history_path = tmp_path / "state" / "run_history.json"

    # dedupe (execute): loser MOVED to mirrored backup path, keeper kept (not deleted).
    dd = deduplicate_library(str(lib), backup_dir=backup, scan_only=False,
                             dry_run=False, fingerprint=False)
    assert dd.moved == 1
    assert keeper.exists()
    assert not loser.exists()
    moved_to = backup / "Artist" / "Dupes" / "01 Song 2.mp3"
    assert moved_to.exists()  # moved out, never deleted

    # folder-art (execute): a real folder image is created in the missing-art album.
    gfa = generate_folder_art(str(lib), execute=True)
    assert gfa["written"] == 1
    assert gfa["executed"] is True
    created = list(needs_art_album.glob("folder.*"))
    assert len(created) == 1
    folder_img = created[0]
    assert folder_img.suffix.lower() in (".jpg", ".png")
    assert folder_img.stat().st_size > 0

    record = _record(target=str(lib), mode="execute",
                     deduped_moved=dd.moved, folderjpg_added=gfa["written"])
    run_history.append_run(record, path=str(run_history_path))
    assert run_history.last_run(str(run_history_path))["mode"] == "execute"
