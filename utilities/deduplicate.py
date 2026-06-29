#!/usr/bin/env python3
"""
De-duplicate a music library: find duplicate copies of the same track within an
album folder, keep the best one, and MOVE the rest to an off-library backup
(never delete).

Runs in the workflow AFTER track-identity + album validation, so each file's true
identity and quality are known before choosing a keeper:

    scan -> validate (fingerprint + metadata) -> DEDUPE -> cover art

Mirrors the rules in `.claude/agents/duplicate_detector.md`:
  - Matching: same normalized title within a folder, confirmed by audio fingerprint
    (identical Chromaprint) OR duration within +/-3s = STRONG; within +/-10s = PROBABLE.
  - Distinct versions (live / remix / edit / remaster) are NOT duplicates unless
    --aggressive. Cross-folder same-song hits are review-only (a song legitimately
    appears on several albums).
  - Keeper rank: higher bitrate -> has embedded art -> no watermark/copy suffix in
    filename -> larger size. Exactly one copy is always kept.

Safety:
  - STRONG within-folder losers are moved to <backup_dir>/<relative path>
    (copy -> verify size -> remove source); never deleted; every move logged for undo.
  - PROBABLE and cross-folder groups are written to a review report, NOT moved
    (unless --aggressive promotes probable to a move).
  - --scan-only / --dry-run / --execute. Read-only modes write nothing.

Usage:
  python -m utilities.deduplicate "/path/to/Music" --backup-dir "D:/music_backup/_duplicates" --scan-only
  python -m utilities.deduplicate "/path/to/Music" --backup-dir "D:/music_backup/_duplicates" --dry-run
  python -m utilities.deduplicate "/path/to/Music" --backup-dir "D:/music_backup/_duplicates" --execute
(or via the CLI: `python cli.py dedupe "/path/to/Music" ...`)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mutagen import File as MutagenFile  # noqa: E402

from utilities.core.audio_file import AUDIO_EXTS, iter_audio_files  # noqa: E402
from utilities.core.cover_art import extract_cover_from_file  # noqa: E402
from utilities.core.naming import transliterate  # noqa: E402

EXC = {'.recycle', '@eadir', '#recycle', 'backups', '.cover_backup', '_duplicates'}

STRONG_SECONDS = 3.0
PROBABLE_SECONDS = 10.0

# Words that mark a *distinct* recording - never auto-merged unless --aggressive.
VERSION_MARKERS = (
    'live', 'remix', 'mix', 'edit', 'acoustic', 'instrumental', 'remaster',
    'remastered', 'demo', 'unplugged', 'reprise', 'version', 'session',
    'radio edit', 'extended', 'club', 'dub', 'a cappella', 'acappella', 'karaoke',
)
# Filename markers that indicate a watermarked / copied file (worse keeper).
WATERMARK_RE = re.compile(r'(www\.|\.com|\.net|music-?madness|-?\bcopy\b|_dup\b|\(\d+\)$|\s\d+$)', re.I)
# Trailing copy-suffixes stripped for matching ("Song 2", "Song (2)", "Song - copy").
COPY_SUFFIX_RE = re.compile(r'(\s*\(\d+\)|\s*-\s*copy|\s*_dup|\s+\d+)\s*$', re.I)
LOSSLESS_EXTS = {'.flac', '.wav', '.aiff', '.ape'}


@dataclass
class Track:
    path: Path
    title: str
    artist: str
    album: str
    duration: float = 0.0
    bitrate: int = 0
    size: int = 0
    has_art: bool = False
    lossless: bool = False
    fingerprint: Optional[str] = None
    norm_title: str = ''


@dataclass
class Summary:
    albums: int = 0
    tracks: int = 0
    groups: int = 0
    strong: int = 0
    probable: int = 0
    moved: int = 0
    space_recovered_kb: int = 0
    review_count: int = 0
    failed: int = 0
    review: List[dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _excluded(root: Path, p: Path) -> bool:
    return any(x.lower() in EXC or x.startswith(('.', '@', '#'))
               for x in p.relative_to(root).parts)


def normalize_for_match(text: str, aggressive: bool = False) -> str:
    """Normalized title key for grouping (mirrors duplicate_detector.md)."""
    s = transliterate(text or '').lower()
    s = COPY_SUFFIX_RE.sub('', s)            # drop "... 2" / "(2)" / "- copy"
    s = re.sub(r'\b(www\.\S+|music-?madness\S*)\b', '', s)  # watermark tokens
    if aggressive:
        # also fold edition/version parentheticals so remaster/deluxe variants group
        s = re.sub(r'[\(\[].*?[\)\]]', '', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s)        # strip punctuation
    return ' '.join(s.split()).strip()


def _has_version_marker(title: str) -> bool:
    t = ' ' + re.sub(r'[^a-z0-9 ]+', ' ', (title or '').lower()) + ' '
    return any(f' {m} ' in t for m in VERSION_MARKERS)


def _tag(meta, *keys) -> str:
    for k in keys:
        v = meta.get(k) if meta else None
        if v:
            return (v[0] if isinstance(v, list) else str(v)).strip()
    return ''


def read_track(path: Path, aggressive: bool = False) -> Optional[Track]:
    try:
        easy = MutagenFile(path, easy=True)
        raw = MutagenFile(path)
    except Exception:
        return None
    title = _tag(easy, 'title') or path.stem
    t = Track(
        path=path,
        title=title,
        artist=_tag(easy, 'albumartist', 'artist'),
        album=_tag(easy, 'album'),
        duration=float(getattr(getattr(raw, 'info', None), 'length', 0) or 0),
        bitrate=int(getattr(getattr(raw, 'info', None), 'bitrate', 0) or 0),
        size=path.stat().st_size,
        has_art=bool(extract_cover_from_file(path)),
        lossless=path.suffix.lower() in LOSSLESS_EXTS,
        norm_title=normalize_for_match(title, aggressive),
    )
    return t


def quality_key(t: Track):
    """Higher is better: lossless, then bitrate, then has-art, then clean name, then size."""
    clean = 0 if WATERMARK_RE.search(t.path.stem) else 1
    return (1 if t.lossless else 0, t.bitrate, 1 if t.has_art else 0, clean, t.size)


def _add_fingerprints(tracks: List[Track], enabled: bool) -> None:
    """Fingerprint only the given (candidate) tracks, in place. No-op if disabled/unavailable."""
    if not enabled:
        return
    try:
        from sources.acoustid import AcoustIDSource
        src = AcoustIDSource()
    except Exception:
        return
    if not getattr(src, 'fpcalc_path', None):
        return
    for t in tracks:
        if t.fingerprint is None:
            fp = src.fingerprint_only(str(t.path))
            if fp and fp.get('fingerprint'):
                t.fingerprint = fp['fingerprint']
                if not t.duration and fp.get('duration'):
                    t.duration = float(fp['duration'])


def classify(keeper: Track, other: Track) -> str:
    """'strong' | 'probable' | 'distinct' per the agent's matching rules."""
    if keeper.fingerprint and other.fingerprint and keeper.fingerprint == other.fingerprint:
        return 'strong'
    dd = abs(keeper.duration - other.duration)
    if keeper.duration and other.duration:
        if dd <= STRONG_SECONDS:
            return 'strong'
        if dd <= PROBABLE_SECONDS:
            return 'probable'
        return 'distinct'
    # no durations and no fingerprint match -> can't confirm; treat as probable
    return 'probable'


def _safe_move(src: Path, dest: Path) -> bool:
    """Copy -> verify size -> remove source. Returns True on success. Never deletes blindly."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest = dest.with_name(dest.stem + '_dup' + dest.suffix)
    shutil.copy2(str(src), str(dest))
    if dest.stat().st_size != src.stat().st_size:
        try:
            dest.unlink()
        except OSError:
            pass
        return False
    try:
        os.chmod(src, stat.S_IWRITE)
    except OSError:
        pass
    src.unlink()
    return True


def deduplicate_library(
    path,
    *,
    backup_dir,
    scan_only: bool = False,
    dry_run: bool = False,
    aggressive: bool = False,
    fingerprint: bool = True,
    log_path: Optional[str] = None,
    review_path: Optional[str] = None,
) -> Summary:
    root = Path(str(path).replace('\\', '/'))
    backup_root = Path(str(backup_dir).replace('\\', '/'))
    summ = Summary()
    do_write = not (scan_only or dry_run)

    log_fh = None
    if do_write:
        lp = Path(log_path or (Path(__file__).resolve().parent.parent / 'outputs' / 'dedupe_moved.log'))
        lp.parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(lp, 'a', encoding='utf-8')

    # cross-folder index for review (normalized title -> list of (album, path))
    cross: Dict[str, List[Track]] = defaultdict(list)

    try:
        for dp, dn, fn in os.walk(root):
            folder = Path(dp)
            if folder != root and _excluded(root, folder):
                dn[:] = []
                continue
            audio = [folder / n for n in fn if os.path.splitext(n)[1].lower() in AUDIO_EXTS]
            if not audio:
                continue
            summ.albums += 1
            tracks = [t for t in (read_track(p, aggressive) for p in sorted(audio)) if t]
            summ.tracks += len(tracks)

            by_title: Dict[str, List[Track]] = defaultdict(list)
            for t in tracks:
                if t.norm_title:
                    by_title[t.norm_title].append(t)
                    cross[(t.norm_title + '|' + normalize_for_match(t.artist, aggressive))].append(t)

            for norm, members in by_title.items():
                if len(members) < 2:
                    continue
                # protect distinct versions unless aggressive
                if not aggressive and any(_has_version_marker(m.title) for m in members) \
                        and len({_has_version_marker(m.title) for m in members}) > 1:
                    continue
                _add_fingerprints(members, fingerprint)
                members.sort(key=quality_key, reverse=True)
                keeper = members[0]
                strong_losers, probable, distinct = [], [], []
                for other in members[1:]:
                    s = classify(keeper, other)
                    (strong_losers if s == 'strong' else probable if s == 'probable' else distinct).append(other)
                if not strong_losers and not probable:
                    continue
                summ.groups += 1
                summ.strong += len(strong_losers)
                summ.probable += len(probable)

                if probable:
                    summ.review_count += len(probable)
                    summ.review.append({
                        'match_strength': 'probable',
                        'album': str(folder.relative_to(root)),
                        'keep': keeper.path.name,
                        'remove_candidates': [p.path.name for p in probable],
                        'requires_human_review': True,
                        'rationale': 'same title, duration within +/-10s, not fingerprint-confirmed',
                    })

                for loser in strong_losers:
                    if not do_write:
                        summ.moved += 1
                        summ.space_recovered_kb += loser.size // 1024
                        continue
                    try:
                        dest = backup_root / loser.path.relative_to(root)
                        if _safe_move(loser.path, dest):
                            summ.moved += 1
                            summ.space_recovered_kb += loser.size // 1024
                            log_fh.write(f'{loser.path}\t->\t{dest}\n')
                            log_fh.flush()
                        else:
                            summ.failed += 1
                            summ.errors.append(f'{loser.path.relative_to(root)} :: copy verify failed')
                    except Exception as exc:
                        summ.failed += 1
                        summ.errors.append(f'{loser.path.relative_to(root)} :: {exc}')
    finally:
        if log_fh:
            log_fh.close()

    # cross-folder same-song (review only, never moved)
    for key, items in cross.items():
        folders = {t.path.parent for t in items}
        if len(folders) > 1:
            summ.review.append({
                'match_strength': 'cross-folder',
                'title': key.split('|')[0],
                'paths': [str(t.path.relative_to(root)) for t in items],
                'requires_human_review': True,
                'rationale': 'same song appears in multiple albums - intentional? not moved',
            })
            summ.review_count += 1

    if do_write and summ.review:
        rp = Path(review_path or (Path(__file__).resolve().parent.parent / 'outputs' / 'dedupe_review.json'))
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(summ.review, indent=1, ensure_ascii=False), encoding='utf-8')

    return summ


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path', help='library / artist / album folder')
    ap.add_argument('--backup-dir', default=r'D:\music_backup\_duplicates',
                    help='where losing duplicates are moved (mirrors relative paths)')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--scan-only', action='store_true', help='report duplicate groups only')
    mode.add_argument('--dry-run', action='store_true', help='full keep/move plan, no writes (default)')
    mode.add_argument('--execute', action='store_true', help='move strong duplicates to backup')
    ap.add_argument('--aggressive', action='store_true',
                    help='also group remaster/edition/version variants and move probable matches')
    ap.add_argument('--no-fingerprint', action='store_true', help='match on metadata only (skip fpcalc)')
    args = ap.parse_args()

    if not Path(str(args.path).replace('\\', '/')).is_dir():
        print(f'ERROR: not a folder: {args.path}')
        sys.exit(2)

    summ = deduplicate_library(
        args.path,
        backup_dir=args.backup_dir,
        scan_only=args.scan_only,
        dry_run=not args.execute and not args.scan_only,
        aggressive=args.aggressive,
        fingerprint=not args.no_fingerprint,
    )
    verb = 'MOVED' if args.execute else 'WOULD MOVE'
    print('\n=== De-duplication Summary ===')
    print(f'Albums scanned:        {summ.albums}')
    print(f'Tracks examined:       {summ.tracks}')
    print(f'Duplicate groups:      {summ.groups}')
    print(f'{verb} (strong):       {summ.moved}  (~{summ.space_recovered_kb // 1024} MB)')
    print(f'Probable/cross (review): {summ.review_count}')
    if summ.failed:
        print(f'Failed:                {summ.failed}')
    if args.scan_only:
        print('(scan-only - no changes)')
    elif not args.execute:
        print('(dry-run - no changes)')
    if summ.errors:
        print('\n--- errors ---')
        for e in summ.errors[:20]:
            print('  ', e)


if __name__ == '__main__':
    main()
