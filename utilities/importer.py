#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import music from an external source (e.g. an iTunes Music backup) into the
music library, de-duplicating by AUDIO QUALITY at the TRACK level.

iTunes holds a mix of individual purchased SONGS and full ALBUMS, so the unit of
import is the TRACK (not the whole album):

  * NEW album (artist/album not in the library) -> import all of its tracks.
  * EXISTING album (matches a library album) -> merge per track:
      - a source track that matches an existing track and is HIGHER audio quality
        UPGRADES that one track (the old track is deleted only AFTER the new copy
        is verified in place); even a single-song source folder upgrades the one
        matching track in a full album.
      - a source track that the library album is MISSING is ADDED.
      - equal-or-lower-quality tracks are left as-is.
      - a track that is NOT in the source is never touched (no track is ever lost).

Audio-quality rank (per track, via mutagen):
  1. LOSSLESS (FLAC/ALAC/WAV/AIFF/APE/...) always beats LOSSY (AAC/MP3).
  2. Within lossless: higher bit-depth x sample-rate wins (24/96 > 16/44.1).
  3. Within lossy: the codec-efficiency-adjusted bitrate wins - AAC/Vorbis/Opus are
     weighted up vs MP3, so AAC 256k ranks >= MP3 320k (a more-efficient codec is
     not downgraded to a higher-bitrate but less-efficient one).

Rules: COPY only (the source is left intact); three-mode safe (--scan-only /
--dry-run DEFAULT / --execute). Duplicate album match: MusicBrainz album id from
the tags when present, else normalized 'Artist - Album'. Each imported/updated
album gets folder.jpg (re)generated from its validated embedded art.
"""

from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utilities.core.naming import make_windows_safe, transliterate  # noqa: E402
from utilities.core.audio_file import AUDIO_EXTS, iter_audio_files, is_excluded_dir  # noqa: E402

# Lossless containers (extension-based); ALAC in an .m4a is detected by codec.
LOSSLESS_EXTS = {".flac", ".wav", ".wave", ".aiff", ".aif", ".aifc", ".ape", ".wv", ".alac", ".tta", ".dsf"}

_TRANSIENT_WINERRORS = {32, 59, 6, 64, 121, 1231}
_TRAILING_YEAR = re.compile(r"\s*\((19|20)\d{2}\)\s*$")
_ANY_YEAR = re.compile(r"(19|20)\d{2}")
_TRACK_PREFIX = re.compile(r"^\s*\d{1,3}[\s.\-_]+")
_QUALITY_SUFFIX = re.compile(r"\s*[\(\[]\s*\d{2,4}\s*k(bps|b)?\s*[\)\]]\s*$", re.I)


def _retry_iterdir(d, attempts: int = 5, delay: float = 1.0) -> List[Path]:
    """List a directory, retrying transient SMB faults (the NAS drops the session
    on long walks). Raises the last error if every attempt fails - callers that
    must NOT proceed on a partial listing (the library index) let it propagate and
    abort; per-item callers catch it and skip."""
    last: Optional[Exception] = None
    for i in range(attempts):
        try:
            return list(Path(d).iterdir())
        except OSError as exc:
            last = exc
            if getattr(exc, "winerror", None) not in _TRANSIENT_WINERRORS:
                raise
            time.sleep(delay * (i + 1))
    raise last or OSError(f"could not list {d}")


# --------------------------------------------------------------------------- #
# Audio quality (pure + testable)
# --------------------------------------------------------------------------- #
def track_quality(path) -> Optional[Dict[str, Any]]:
    """Return ``{lossless, bitdepth, samplerate, bitrate, fmt}`` for one track via
    mutagen, or ``None`` if it cannot be read."""
    from mutagen import File as MFile

    p = Path(path)
    ext = p.suffix.lower()
    try:
        f = MFile(str(p))
        if f is None or f.info is None:
            return None
        info = f.info
    except Exception:
        return None

    codec = str(getattr(info, "codec", "") or "").lower()   # MP4: 'alac' or 'mp4a.40.2'
    lossless = ext in LOSSLESS_EXTS or codec.startswith("alac")
    if codec.startswith("alac"):
        fmt = "ALAC"
    elif codec.startswith("mp4a") or ext in (".m4a", ".mp4"):
        fmt = "AAC"
    else:
        fmt = ext.lstrip(".").upper()
    return {
        "lossless": lossless,
        "bitdepth": int(getattr(info, "bits_per_sample", 0) or 0),
        "samplerate": int(getattr(info, "sample_rate", 0) or 0),
        "bitrate": int(getattr(info, "bitrate", 0) or 0),
        "fmt": fmt,
    }


def aggregate_quality(track_qs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Aggregate per-track quality dicts into one album-quality summary (for display:
    majority-lossless; median bit-depth/sample-rate/bitrate; mixed-format flag)."""
    qs = [q for q in track_qs if q]
    if not qs:
        return None
    n = len(qs)
    lossless = sum(1 for q in qs if q["lossless"]) * 2 >= n
    fmts = sorted({q["fmt"] for q in qs})

    def med(key: str) -> int:
        return int(median(sorted(q[key] for q in qs)))

    return {
        "lossless": lossless, "bitdepth": med("bitdepth"), "samplerate": med("samplerate"),
        "bitrate": med("bitrate"), "tracks": n, "mixed": len(fmts) > 1, "fmt": "/".join(fmts),
    }


def album_quality(album_dir) -> Optional[Dict[str, Any]]:
    """Album-quality summary for display (reads each track)."""
    return aggregate_quality([track_quality(t) for t in iter_audio_files(album_dir)])


# Lossy codec efficiency relative to MP3 (=1.0): AAC/Vorbis/Opus need fewer bits
# for the same perceived quality, so their bitrate is weighted up before comparing.
# Tuned so AAC 256k >= MP3 320k ("keep the AAC"): 256 * 1.30 = 332.8k effective > 320k.
_LOSSY_EFFICIENCY = {"AAC": 1.30, "OPUS": 1.60, "VORBIS": 1.25, "OGG": 1.25,
                     "MP3": 1.0, "MP2": 1.0, "WMA": 1.0, "AC3": 0.9}


def _codec_factor(fmt: Optional[str]) -> float:
    return _LOSSY_EFFICIENCY.get((fmt or "").upper(), 1.0)


def quality_key(q: Optional[Dict[str, Any]]) -> Tuple[int, int, int]:
    """Comparable quality key (track or album). Lossless beats lossy; within lossless
    bit-depth x sample-rate; within lossy the CODEC-EFFICIENCY-ADJUSTED bitrate (so
    AAC 256k ranks >= MP3 320k). Higher tuple = better."""
    if not q:
        return (0, 0, 0)
    if q.get("lossless"):
        return (1, (q.get("bitdepth") or 16) * (q.get("samplerate") or 44100), 0)
    eff = int(round((q.get("bitrate") or 0) * _codec_factor(q.get("fmt"))))
    return (0, 0, eff)


def track_action(src_q: Optional[Dict[str, Any]], ex_q: Optional[Dict[str, Any]]) -> str:
    """Per-track decision when merging into an existing album.

    ``"add"`` when the library album has no matching track; ``"upgrade"`` when the
    source track is higher audio quality than the existing one; else ``"skip"``.
    A single-song source still upgrades the one matching track in a full album."""
    if ex_q is None:
        return "add"
    return "upgrade" if quality_key(src_q) > quality_key(ex_q) else "skip"


def quality_label(q: Optional[Dict[str, Any]]) -> str:
    if not q:
        return "?"
    mixed = " (mixed)" if q.get("mixed") else ""
    if q.get("lossless"):
        if q.get("bitdepth") and q.get("samplerate"):
            return f"{q['fmt']} {q['bitdepth']}/{q['samplerate'] / 1000:g}kHz{mixed}"
        return f"{q['fmt']} lossless{mixed}"
    return f"{q['fmt']} {round((q.get('bitrate') or 0) / 1000)}k{mixed}"


# --------------------------------------------------------------------------- #
# Tag reading (identity + per-track keys)
# --------------------------------------------------------------------------- #
def _easy_tags(path) -> Dict[str, Any]:
    from mutagen import File as MFile
    try:
        return MFile(str(path), easy=True).tags or {}
    except Exception:
        return {}


def _g(tags, key) -> Optional[str]:
    if not tags:
        return None
    v = tags.get(key)
    if not v:
        return None
    first = v[0] if isinstance(v, list) else v
    return str(first).strip() or None


def _first_int(v) -> Optional[int]:
    if not v:
        return None
    s = str(v[0] if isinstance(v, list) else v)
    m = re.match(r"\s*(\d+)", s)
    return int(m.group(1)) if m else None


def _clean_title(s: Optional[str]) -> str:
    if not s:
        return ""
    s = _QUALITY_SUFFIX.sub("", str(s))
    s = _TRAILING_YEAR.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def _clean_folder(name: str) -> str:
    # Album/artist FOLDER names never carry a track-number prefix, so we do NOT
    # strip a leading number here - that would mangle "18 Months", "100 Hits",
    # "1989", "50" and break dedup on number-leading titles.
    return _clean_title(name.replace("_", " "))


def _norm(s: str) -> str:
    # Transliterate first so accented names normalize together ("Jack Ü" == "Jack U",
    # "Café" == "Cafe"), then strip to alphanumerics.
    return re.sub(r"[^a-z0-9]", "", transliterate(s or "").lower())


def _year(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    m = _ANY_YEAR.search(str(s))
    return m.group(0) if m else None


def album_identity(album_dir) -> Tuple[Optional[str], str, str, Optional[str]]:
    """``(mbid, artist, album, year)`` for an album folder, from a representative
    track's tags (mutagen easy interface), folder names as fallback."""
    album_dir = Path(album_dir)
    tracks = list(iter_audio_files(album_dir))
    tags = _easy_tags(tracks[0]) if tracks else {}
    mbid = _g(tags, "musicbrainz_albumid")
    album = _clean_title(_g(tags, "album")) or _clean_folder(album_dir.name)
    artist = (_g(tags, "albumartist") or _g(tags, "artist")
              or _clean_folder(album_dir.parent.name))
    year = _year(_g(tags, "date") or _g(tags, "year"))
    return mbid, artist, album, year


def _track_keys(path) -> List[Tuple]:
    """Keys to match a track across containers/filenames: (disc, track number) and
    normalized title; filename stem as a last resort."""
    tags = _easy_tags(path)
    keys: List[Tuple] = []
    trk = _first_int(tags.get("tracknumber"))
    disc = _first_int(tags.get("discnumber")) or 1
    if trk:
        keys.append(("n", disc, trk))
    title = _g(tags, "title")
    if title:
        keys.append(("t", _norm(title)))
    if not keys:
        # last resort: the filename stem, WITH its leading track-number prefix
        # stripped (track files legitimately start with "01 ", unlike folders).
        stem = _TRACK_PREFIX.sub("", Path(path).stem).replace("_", " ")
        keys.append(("f", _norm(_clean_title(stem))))
    return keys


def _build_track_index(album_dir) -> Dict[Tuple, Tuple[Path, Optional[Dict[str, Any]]]]:
    """Index an existing album's tracks by every match key -> (path, quality)."""
    index: Dict[Tuple, Tuple[Path, Optional[Dict[str, Any]]]] = {}
    for t in iter_audio_files(album_dir):
        q = track_quality(t)
        for k in _track_keys(t):
            index.setdefault(k, (t, q))
    return index


def _match_existing(src_track: Path, existing_index: Dict) -> Optional[Tuple[Path, Optional[Dict[str, Any]]]]:
    for k in _track_keys(src_track):
        if k in existing_index:
            return existing_index[k]
    return None


# --------------------------------------------------------------------------- #
# Destination index (album duplicate lookup, from folder names - fast)
# --------------------------------------------------------------------------- #
def _build_dest_index(dest: Path) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    if not dest.exists():
        return index
    for artist_dir in _retry_iterdir(dest):
        if not artist_dir.is_dir() or is_excluded_dir(artist_dir.name):
            continue
        artist_n = _norm(_clean_folder(artist_dir.name))
        try:
            albums = _retry_iterdir(artist_dir)
        except OSError:
            continue
        for album_dir in albums:
            if not album_dir.is_dir() or is_excluded_dir(album_dir.name):
                continue
            if not any(True for _ in iter_audio_files(album_dir)):
                continue
            album_n = _norm(_clean_folder(album_dir.name))
            index.setdefault(f"aa:{artist_n}|{album_n}", album_dir)
    return index


def _find_existing(index: Dict[str, Path], mbid, artist: str, album: str) -> Optional[Path]:
    if mbid and f"mb:{mbid}" in index:
        return index[f"mb:{mbid}"]
    return index.get(f"aa:{_norm(artist)}|{_norm(album)}")


# --------------------------------------------------------------------------- #
# Copy (chunked; NOT shutil.copy2) with SMB-drop retry
# --------------------------------------------------------------------------- #
def _verify_copy(src: Path, dst: Path) -> bool:
    try:
        return dst.exists() and dst.stat().st_size == src.stat().st_size
    except OSError:
        return False


def _raw_copy(src: Path, dst: Path, bufsize: int = 8 * 1024 * 1024) -> None:
    """Plain chunked read/write copy (like coreutils ``cp``).

    Deliberately NOT ``shutil.copy2``: on Windows/Python 3.13 that uses ``CopyFile2``,
    which attempts server-side copy-offload that a Samba NAS REJECTS on a same-server
    share->share copy (``WinError 58``, or a spurious ``WinError 112`` "disk full")."""
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        while True:
            buf = fsrc.read(bufsize)
            if not buf:
                break
            fdst.write(buf)
    try:
        shutil.copystat(str(src), str(dst))
    except OSError:
        pass


def _copy_with_retry(src: Path, dst: Path, attempts: int = 4) -> None:
    """Copy ``src`` -> ``dst`` via :func:`_raw_copy`, retrying transient SMB drops;
    deletes a partial before each retry and raises the last error if all fail."""
    last: Optional[Exception] = None
    for i in range(attempts):
        try:
            _raw_copy(src, dst)
            if _verify_copy(src, dst):
                return
            last = IOError("size mismatch after copy")
        except OSError as exc:
            last = exc
        try:
            if dst.exists():
                dst.unlink()
        except OSError:
            pass
        try:
            _ = list(dst.parent.parent.iterdir())
        except OSError:
            pass
        time.sleep(3 * (i + 1))
    raise last or IOError("copy failed")


def _place_track(src: Path, target_folder: Path, replace: Optional[Path] = None) -> None:
    """Copy one source track into ``target_folder`` (verify size), then - only after
    the new copy is verified in place - delete the ``replace`` track it upgrades."""
    target_folder.mkdir(parents=True, exist_ok=True)
    tmp = target_folder / (src.name + ".importing")
    _copy_with_retry(src, tmp)                       # verifies size; raises on failure
    if replace is not None and Path(replace).exists() and Path(replace) != tmp:
        Path(replace).unlink(missing_ok=True)        # old track gone only now
    final = target_folder / src.name
    if final.exists() and final != tmp:
        final.unlink(missing_ok=True)
    tmp.rename(final)


# --------------------------------------------------------------------------- #
# Source scan
# --------------------------------------------------------------------------- #
def _source_albums(source: Path) -> List[Path]:
    """Source album folders (iTunes is ``Artist/Album/tracks``; a folder that
    directly holds audio is also accepted)."""
    albums: List[Path] = []
    if not source.exists():
        return albums
    if source.is_dir() and any(True for _ in iter_audio_files(source)):
        return [source]
    for artist in sorted(_retry_iterdir(source)):
        if not artist.is_dir() or is_excluded_dir(artist.name):
            continue
        try:
            children = _retry_iterdir(artist)
        except OSError:
            continue
        if any(c.is_file() and c.suffix.lower() in AUDIO_EXTS for c in children):
            albums.append(artist)
            continue
        for album in sorted(children):
            if album.is_dir() and not is_excluded_dir(album.name) \
                    and any(True for _ in iter_audio_files(album)):
                albums.append(album)
    return albums


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #
def _enrich_album(target_folder: Path, *, config=None, metadata_check: bool = True,
                  flags: Optional[List[Dict[str, Any]]] = None) -> None:
    """Enrich one imported/updated album by reusing the existing pipeline. Fail-soft:
    enrichment never aborts an import. Anything needing human attention is appended
    to ``flags`` (metadata below the auto-approve bar; folder name vs metadata).

    Covers (always): folder.jpg from validated embedded art (``generate_folder_art``)
    + track<->folder.jpg consistency (``sync-covers``).
    Metadata (when ``metadata_check``): validate album vs MusicBrainz/iTunes
    (``ValidatorAgent``, flag-only) + folder-name-matches-metadata check.
    """
    album = Path(target_folder)
    label = f"{album.parent.name}/{album.name}"

    # --- covers: folder.jpg + track<->folder consistency (validates embedded art) ---
    try:
        from utilities.generate_folder_art import generate_folder_art
        generate_folder_art(str(album), execute=True)
    except Exception:
        pass
    try:
        from utilities.cover_consistency import sync_library
        sync_library(str(album), execute=True)
    except Exception:
        pass

    if not metadata_check:
        return

    # --- metadata + folder-name check (read-only; flags for review, never auto-fixes) ---
    try:
        from agents.scanner import ScannerAgent
        from agents.validator import ValidatorAgent
        from orchestrator.state import StateStore
        cfg = config
        if cfg is None:
            from orchestrator.config import ConfigManager
            cfg = ConfigManager()
        state = StateStore(cfg.get("output.state_path", "state"))
        scan = ScannerAgent(cfg, state).process({"path": str(album)})
        data = scan.get("data", {}) if scan.get("status") == "success" else {}
        vres = ValidatorAgent(cfg, state).process({
            "path": str(album),
            "title": data.get("title") or _clean_folder(album.name),
            "artist": data.get("artist") or _clean_folder(album.parent.name),
            "track_count": data.get("track_count", 0),
            "has_cover": data.get("has_cover", False),
        })
        vstatus = vres.get("validation_status")
        if flags is not None and vstatus and vstatus not in ("auto_approved", "verified", "validated"):
            flags.append({"album": label, "type": "metadata",
                          "status": vstatus, "confidence": vres.get("confidence")})
        alb_tag = data.get("title")
        if (flags is not None and alb_tag
                and _norm(_clean_folder(album.name)) != _norm(_clean_title(alb_tag))):
            flags.append({"album": label, "type": "folder_name",
                          "expected": _clean_title(alb_tag)})
    except Exception:
        pass


def _plan_existing(src_album: Path, existing: Path) -> List[Tuple[Path, str, Optional[Path]]]:
    """Per-track merge plan for a source album matched to an ``existing`` library
    album: list of ``(source_track, action, replace_path)`` where action is
    add / upgrade / skip."""
    idx = _build_track_index(existing)
    plan: List[Tuple[Path, str, Optional[Path]]] = []
    for st in iter_audio_files(src_album):
        match = _match_existing(st, idx)
        if match is None:
            plan.append((st, "add", None))
        else:
            ex_path, ex_q = match
            action = track_action(track_quality(st), ex_q)
            plan.append((st, action, ex_path if action == "upgrade" else None))
    return plan


def import_albums(
    source: str,
    dest: Optional[str] = None,
    *,
    scan_only: bool = False,
    dry_run: bool = True,
    execute: bool = False,
    config=None,
    enrich: bool = True,
    metadata_check: bool = True,
) -> Dict[str, Any]:
    """Import music from ``source`` into the ``dest`` library, de-duping by track
    audio quality. See the module docstring for the rules."""
    if config is None:
        try:
            from orchestrator.config import ConfigManager
            config = ConfigManager()
        except Exception:
            config = None

    def cget(key, default=None):
        try:
            return config.get(key, default) if config is not None else default
        except Exception:
            return default

    src = Path(str(source or cget("import.itunes_source", "")).replace("\\", "/"))
    dest_lib = Path(str(dest or cget("library.root", "")).replace("\\", "/"))

    report: Dict[str, Any] = {
        "mode": "scan-only" if scan_only else ("execute" if execute else "dry-run"),
        "source": str(src), "dest": str(dest_lib),
        "new": 0, "merged": 0, "skipped": 0, "failed": 0,
        "tracks_added": 0, "tracks_upgraded": 0, "bytes_planned": 0,
        "items": [], "flags": [],
    }
    if not src.exists():
        report["error"] = f"source not found: {src}"
        return report
    if not str(dest_lib) or dest_lib == Path("/path/to/music"):
        report["error"] = ("library root is not configured; pass --dest "
                           "(library.root in music-config.yaml is a placeholder)")
        return report

    try:
        index = _build_dest_index(dest_lib)
    except OSError as exc:
        report["error"] = f"could not index library (share unstable, retried): {exc}"
        return report
    try:
        source_albums = _source_albums(src)
    except OSError as exc:
        report["error"] = f"could not list source (share unstable, retried): {exc}"
        return report

    plan: List[Dict[str, Any]] = []
    for album in source_albums:
        mbid, artist, title, year = album_identity(album)
        sq = album_quality(album)
        existing = _find_existing(index, mbid, artist, title)

        entry: Dict[str, Any] = {
            "artist": artist, "album": title, "year": year,
            "source_quality": quality_label(sq), "tracks": (sq.get("tracks") if sq else 0),
            "decision": None, "existing": None, "existing_quality": None,
            "add": 0, "upgrade": 0,
        }

        if existing is None:
            entry["decision"] = "new"
            report["bytes_planned"] += sum((t.stat().st_size for t in iter_audio_files(album)
                                            if _safe_size(t)), 0)
            plan.append({"src": album, "entry": entry, "existing": None,
                         "artist": artist, "title": title})
        else:
            entry["existing"] = f"{existing.parent.name}/{existing.name}"
            entry["existing_quality"] = quality_label(album_quality(existing))
            track_plan = _plan_existing(album, existing)
            entry["add"] = sum(1 for _, a, _ in track_plan if a == "add")
            entry["upgrade"] = sum(1 for _, a, _ in track_plan if a == "upgrade")
            if entry["add"] + entry["upgrade"] == 0:
                entry["decision"] = "skip"
            else:
                entry["decision"] = "merge"
                report["bytes_planned"] += sum((t.stat().st_size for t, a, _ in track_plan
                                                if a in ("add", "upgrade") and _safe_size(t)), 0)
                plan.append({"src": album, "entry": entry, "existing": existing,
                             "track_plan": track_plan})

        report["items"].append(entry)
        if entry["decision"] == "new":
            report["new"] += 1
        elif entry["decision"] == "merge":
            report["merged"] += 1
            report["tracks_added"] += entry["add"]
            report["tracks_upgraded"] += entry["upgrade"]
        else:
            report["skipped"] += 1

    # Free-space guard before any execute copy.
    if execute and not scan_only and report["bytes_planned"]:
        try:
            free = shutil.disk_usage(str(dest_lib)).free
            if free < report["bytes_planned"] * 1.05:
                report["error"] = (f"insufficient free space on target: need "
                                   f"~{report['bytes_planned'] // (1024**2)} MB, "
                                   f"have {free // (1024**2)} MB")
                return report
        except OSError:
            pass

    if scan_only or dry_run or not execute:
        return report

    # -------------------- execute --------------------
    for item in plan:
        entry = item["entry"]
        try:
            if entry["decision"] == "new":
                artist_safe = make_windows_safe(item["artist"]) or "Unknown Artist"
                album_safe = make_windows_safe(item["title"]) or item["src"].name
                target = dest_lib / artist_safe / album_safe
                for t in iter_audio_files(item["src"]):
                    _place_track(t, target, replace=None)
            else:  # merge into the existing album folder
                target = item["existing"]
                for st, action, replace in item["track_plan"]:
                    if action in ("add", "upgrade"):
                        _place_track(st, target, replace=replace)
            if enrich:
                _enrich_album(target, config=config, metadata_check=metadata_check,
                              flags=report["flags"])
            entry["status"] = "done"
        except Exception as exc:  # fail-soft per album; never abort the batch
            report["failed"] += 1
            entry["error"] = str(exc)
            entry["status"] = "failed"
            if entry["decision"] == "new":
                report["new"] -= 1
            else:
                report["merged"] -= 1
                report["tracks_added"] -= entry["add"]
                report["tracks_upgraded"] -= entry["upgrade"]

    return report


def _safe_size(t: Path) -> bool:
    try:
        return t.stat().st_size >= 0
    except OSError:
        return False


def print_report(report: Dict[str, Any]) -> None:
    print(f"Import ({report['mode']})  {report['source']} -> {report['dest']}")
    if report.get("error"):
        print(f"  ERROR: {report['error']}")
        return
    verb = "imported" if report["mode"] == "execute" else "would import"
    gb = report.get("bytes_planned", 0) / (1024 ** 3)
    print(f"  new albums: {report['new']} | merged: {report['merged']} "
          f"(+{report['tracks_upgraded']} upgraded, +{report['tracks_added']} added tracks) | "
          f"skipped: {report['skipped']} | failed: {report['failed']}  ({verb}; ~{gb:.1f} GB)")
    for e in report["items"]:
        if e["decision"] == "new":
            line = f"  [NEW] {e['artist']} - {e['album']}  {e['source_quality']} ({e.get('tracks', 0)} trk)"
        elif e["decision"] == "merge":
            line = (f"  [MERGE] {e['artist']} - {e['album']}  "
                    f"+{e['upgrade']} upgraded, +{e['add']} added  "
                    f"vs existing '{e['existing']}' {e['existing_quality']}")
        else:
            line = f"  [SKIP] {e['artist']} - {e['album']}  vs existing '{e['existing']}' (already current)"
        if e.get("error"):
            line += f"  !! {e['error']}"
        print(line)
    flags = report.get("flags") or []
    if flags:
        print(f"\n  Review flags ({len(flags)}):")
        for fl in flags:
            if fl.get("type") == "metadata":
                print(f"    [metadata] {fl['album']}  status={fl.get('status')} "
                      f"confidence={fl.get('confidence')}")
            elif fl.get("type") == "folder_name":
                print(f"    [folder]   {fl['album']}  metadata album = '{fl.get('expected')}'")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Import music from iTunes into the library (per-track quality merge)")
    ap.add_argument("source", nargs="?", default=None)
    ap.add_argument("--dest", default=None)
    ap.add_argument("--scan-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    rep = import_albums(a.source, a.dest, scan_only=a.scan_only,
                        dry_run=a.dry_run or not (a.scan_only or a.execute),
                        execute=a.execute)
    print_report(rep)
