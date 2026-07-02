#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music Library Cleanup - Command Line Interface

Usage:
    music-clean init <path> [--config <file>]
    music-clean scan [--artist <name>] [--album <path>] [--full]
    music-clean validate [--source <name>] [--threshold <n>]
    music-clean review [--list] [--approve <id>] [--reject <id>]
    music-clean fix [--dry-run] [--album <id>]
    music-clean status
    music-clean resume
"""

import argparse
import sys
from pathlib import Path

# Import agents
from agents import ScannerAgent, ValidatorAgent, FixerAgent

# Shared library-walk exclusion rules (recycle bins, system dirs, backups) so the
# orchestrator's album discovery skips the same non-album folders as every other
# walker (dedupe, cover-repair, folder-art).
from utilities.core.audio_file import is_excluded_dir

# Single source of truth for the lifecycle phase order (the parity anchor).
# Downstream code should import this rather than redefining the order.
#   from orchestrator.main import LIFECYCLE_PHASES
LIFECYCLE_PHASES = ["scan", "identify", "validate", "dedupe", "covers", "fix"]


def print_banner():
    """Print application banner"""
    print("=" * 60)
    print("  Music Library Cleanup Orchestrator")
    print("  Version 1.0")
    print("=" * 60)
    print()


def cmd_init(args):
    """Initialize project with library path"""
    from .config import ConfigManager
    from .state import StateStore

    print_banner()
    print(f"Initializing music cleanup project...")
    print(f"Library root: {args.path}")
    print(f"Config file: {args.config}")
    print()

    # Load or create config
    config = ConfigManager(args.config)
    state = StateStore(config.state_path)

    # Update session with library root
    session = state.get_session()
    session['library_root'] = args.path
    session['status'] = 'initialized'
    state.save_session(session)

    # Count artists/albums
    library_path = Path(args.path)
    if library_path.exists():
        artists = [d for d in library_path.iterdir() if d.is_dir()]
        print(f"Found {len(artists)} artist folders")
    else:
        print(f"Warning: Library path not accessible: {args.path}")

    print()
    print("Initialization complete!")
    print("Next: Run 'music-clean scan' to scan the library")


def cmd_scan(args):
    """Scan library for albums"""
    from .config import ConfigManager
    from .state import StateStore
    from .queue import QueueManager, AlbumStatus, Priority

    print_banner()

    config = ConfigManager()
    state = StateStore(config.state_path)
    queue = QueueManager()

    session = state.get_session()
    library_root = session.get('library_root')

    if not library_root:
        print("Error: Project not initialized. Run 'music-clean init <path>' first.")
        return 1

    print(f"Library root: {library_root}")

    if args.artist:
        print(f"Scanning artist: {args.artist}")
        scan_path = Path(library_root) / args.artist
    elif args.album:
        print(f"Scanning album: {args.album}")
        scan_path = Path(args.album)
    else:
        print("Scanning entire library...")
        scan_path = Path(library_root)

    if not scan_path.exists():
        print(f"Error: Path not found: {scan_path}")
        return 1

    # Initialize scanner agent
    scanner = ScannerAgent(config, state)

    # Collect albums to scan
    albums_to_scan = []
    if args.album or (scan_path.is_dir() and _has_audio_files(scan_path)):
        # Single album
        albums_to_scan.append(str(scan_path))
    else:
        # Multiple albums - scan subdirectories
        print("Discovering albums...")
        for item in scan_path.iterdir():
            if item.is_dir() and not is_excluded_dir(item.name):
                if _has_audio_files(item):
                    albums_to_scan.append(str(item))
                else:
                    # Check subdirectories (artist/album structure)
                    for subitem in item.iterdir():
                        if (subitem.is_dir() and not is_excluded_dir(subitem.name)
                                and _has_audio_files(subitem)):
                            albums_to_scan.append(str(subitem))

    print(f"Found {len(albums_to_scan)} albums to scan")
    print()

    # Process albums
    success_count = 0
    failed_count = 0
    total_tracks = 0
    issues_found = 0

    for i, album_path in enumerate(albums_to_scan, 1):
        album_name = Path(album_path).name
        print(f"[{i}/{len(albums_to_scan)}] Scanning: {album_name}")

        result = scanner.process({'path': album_path})

        if result.get('status') == 'success':
            success_count += 1
            total_tracks += result.get('track_count', 0)
            issues_found += result.get('issue_count', 0)

            # Add to queue
            album_id = result.get('album_id')
            queue.add(
                album_id=album_id,
                path=album_path,
                status=AlbumStatus.SCANNED,
                priority=Priority.HIGH if result.get('issue_count', 0) > 0 else Priority.NORMAL,
                metadata={
                    'title': result.get('data', {}).get('title'),
                    'artist': result.get('data', {}).get('artist'),
                    'track_count': result.get('track_count'),
                    'has_cover': result.get('has_cover'),
                    'issues': result.get('data', {}).get('issues', [])
                }
            )
        else:
            failed_count += 1
            print(f"  Error: {result.get('error', 'Unknown error')}")

    # Update session stats
    state.update_session_stats(**{
        'total_albums': len(albums_to_scan),
        'total_tracks': total_tracks,
        'processed.scanned': success_count
    })

    print()
    print("=" * 50)
    print(f"Scan complete!")
    print(f"  Albums scanned: {success_count}/{len(albums_to_scan)}")
    print(f"  Total tracks: {total_tracks}")
    print(f"  Issues found: {issues_found}")
    if failed_count > 0:
        print(f"  Failed: {failed_count}")
    print()
    print("Next: Run 'music-clean validate' to validate albums")

    return 0


def _has_audio_files(path: Path) -> bool:
    """Check if directory contains audio files"""
    audio_extensions = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wav', '.wma', '.aac'}
    for item in path.iterdir():
        if item.is_file() and item.suffix.lower() in audio_extensions:
            return True
    return False


def cmd_validate(args):
    """Validate scanned albums"""
    from .config import ConfigManager
    from .state import StateStore
    from .queue import QueueManager, AlbumStatus

    print_banner()

    config = ConfigManager()
    state = StateStore(config.state_path)
    queue = QueueManager()

    print(f"Validating albums against: {args.source}")
    print(f"Confidence threshold: {args.threshold}")
    print()

    # Get albums pending validation
    pending = queue.get_by_status(AlbumStatus.SCANNED)
    if not pending:
        print("No albums pending validation.")
        print("Run 'music-clean scan' first.")
        return 0

    print(f"Albums to validate: {len(pending)}")
    print()

    # Initialize validator agent
    validator = ValidatorAgent(config, state)

    # Stats
    auto_approved = 0
    needs_review = 0
    not_found = 0
    already_correct = 0

    for i, item in enumerate(pending, 1):
        album_path = item['path']
        album_name = Path(album_path).name
        metadata = item.get('metadata', {})

        print(f"[{i}/{len(pending)}] Validating: {album_name}")

        # Prepare validation data
        validation_data = {
            'path': album_path,
            'album_id': item['id'],
            'title': metadata.get('title') or album_name,
            'artist': metadata.get('artist') or 'Various Artists',
            'track_count': metadata.get('track_count', 0),
            'has_cover': metadata.get('has_cover', False)
        }

        result = validator.process(validation_data)

        if result.get('status') == 'success':
            validation_status = result.get('validation_status')
            confidence = result.get('confidence', 0)
            corrections_needed = result.get('corrections_needed', 0)

            # Update queue based on validation result
            if validation_status == 'auto_approved':
                auto_approved += 1
                if corrections_needed > 0:
                    queue.update_status(
                        item['id'],
                        AlbumStatus.VALIDATED,
                        metadata={'validation': result.get('data'), 'confidence': confidence}
                    )
                else:
                    already_correct += 1
                    queue.update_status(
                        item['id'],
                        AlbumStatus.VERIFIED,
                        metadata={'validation': result.get('data'), 'confidence': confidence}
                    )
                print(f"  -> Auto-approved ({confidence:.0%} confidence)")

            elif validation_status == 'needs_review':
                needs_review += 1
                queue.update_status(
                    item['id'],
                    AlbumStatus.NEEDS_REVIEW,
                    metadata={
                        'validation': result.get('data'),
                        'confidence': confidence,
                        'match': {
                            'title': result.get('data', {}).get('match_title'),
                            'artist': result.get('data', {}).get('match_artist'),
                            'confidence': confidence
                        }
                    }
                )
                print(f"  -> Needs review ({confidence:.0%} confidence)")

            elif validation_status == 'not_found':
                not_found += 1
                queue.update_status(
                    item['id'],
                    AlbumStatus.NEEDS_REVIEW,
                    metadata={'validation': result.get('data'), 'not_found': True}
                )
                print(f"  -> Not found in database")

            elif validation_status == 'rejected':
                queue.update_status(
                    item['id'],
                    AlbumStatus.NEEDS_REVIEW,
                    metadata={'validation': result.get('data'), 'low_confidence': True}
                )
                needs_review += 1
                print(f"  -> Low confidence ({confidence:.0%})")

        else:
            print(f"  Error: {result.get('error', 'Unknown error')}")
            state.log_error(album_path, "validation_error", result.get('error', 'Unknown'))

    # Summary
    print()
    print("=" * 50)
    print("Validation complete!")
    print(f"  Auto-approved: {auto_approved} ({auto_approved/len(pending)*100:.0f}%)")
    print(f"  Needs review: {needs_review} ({needs_review/len(pending)*100:.0f}%)")
    print(f"  Not found: {not_found}")
    print(f"  Already correct: {already_correct}")
    print()

    if needs_review > 0:
        print(f"Run 'music-clean review' to review {needs_review} albums")
    elif auto_approved > 0:
        print("Run 'music-clean fix' to apply corrections")

    return 0


def cmd_review(args):
    """Review pending albums"""
    from .config import ConfigManager
    from .state import StateStore
    from .queue import QueueManager, AlbumStatus

    config = ConfigManager()
    state = StateStore(config.state_path)
    queue = QueueManager()

    if args.list:
        # List pending reviews
        print_banner()
        pending = queue.get_review_queue()
        print(f"Pending reviews: {len(pending)}")
        print()
        for i, item in enumerate(pending, 1):
            print(f"{i}. [{item['id'][:8]}] {item.get('metadata', {}).get('title', 'Unknown')}")
            print(f"   Path: {item['path']}")
            print()
        return 0

    if args.approve:
        # Approve specific album
        success = queue.update_status(args.approve, AlbumStatus.APPROVED)
        if success:
            print(f"Approved: {args.approve}")
        else:
            print(f"Error: Album not found: {args.approve}")
            return 1
        return 0

    if args.reject:
        # Reject specific album
        success = queue.update_status(args.reject, AlbumStatus.REJECTED)
        if success:
            print(f"Rejected: {args.reject}")
        else:
            print(f"Error: Album not found: {args.reject}")
            return 1
        return 0

    # Interactive review
    print_banner()
    pending = queue.get_review_queue()

    if not pending:
        print("No albums pending review.")
        return 0

    print(f"Review queue: {len(pending)} albums")
    print()
    print("Commands: [a]pprove  [r]eject  [s]kip  [q]uit")
    print()

    for i, item in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] {item.get('metadata', {}).get('title', 'Unknown')}")
        print(f"Path: {item['path']}")

        metadata = item.get('metadata', {})
        if metadata.get('match'):
            print(f"Match: {metadata['match'].get('title')} ({metadata['match'].get('confidence', 0):.0%})")

        print()

        while True:
            choice = input("[a/r/s/q]: ").lower().strip()
            if choice == 'a':
                queue.update_status(item['id'], AlbumStatus.APPROVED)
                print("-> Approved")
                break
            elif choice == 'r':
                queue.update_status(item['id'], AlbumStatus.REJECTED)
                print("-> Rejected")
                break
            elif choice == 's':
                print("-> Skipped")
                break
            elif choice == 'q':
                print("Review session ended.")
                return 0
            else:
                print("Invalid choice. Use a/r/s/q")

        print()

    print("Review complete!")
    return 0


def cmd_fix(args):
    """Apply fixes to approved albums"""
    from .config import ConfigManager
    from .state import StateStore
    from .queue import QueueManager, AlbumStatus

    print_banner()

    config = ConfigManager()
    state = StateStore(config.state_path)
    queue = QueueManager()

    dry_run = args.dry_run
    if dry_run:
        print("DRY RUN - No changes will be made")
        print()

    ready = queue.get_ready_to_fix()
    print(f"Albums ready to fix: {len(ready)}")

    if args.album:
        print(f"Fixing specific album: {args.album}")
        ready = [r for r in ready if r['id'].startswith(args.album)]

    if not ready:
        print("No albums to fix.")
        return 0

    # Initialize fixer agent
    fixer = FixerAgent(config, state)

    # Stats
    fixed_count = 0
    failed_count = 0
    total_changes = 0

    for i, item in enumerate(ready, 1):
        album_path = item['path']
        album_name = Path(album_path).name
        metadata = item.get('metadata', {})

        print(f"[{i}/{len(ready)}] Fixing: {album_name}")

        # Get corrections from validation data
        validation = metadata.get('validation', {})
        corrections = validation.get('corrections', [])

        if not corrections:
            print(f"  -> No corrections needed")
            queue.update_status(item['id'], AlbumStatus.VERIFIED)
            continue

        print(f"  Corrections to apply: {len(corrections)}")
        for c in corrections:
            print(f"    - {c.get('type')}: {c.get('field')}")

        # Apply fixes
        fix_data = {
            'path': album_path,
            'corrections': corrections,
            'dry_run': dry_run
        }

        result = fixer.process(fix_data)

        if result.get('status') == 'success':
            fixed_count += 1
            changes = result.get('changes_made', 0)
            total_changes += changes

            # Update queue
            new_path = result.get('data', {}).get('new_path')
            if not dry_run:
                queue.update_status(
                    item['id'],
                    AlbumStatus.FIXED,
                    metadata={
                        'fix_result': result.get('data'),
                        'new_path': new_path
                    }
                )
                if new_path:
                    print(f"  -> Fixed (renamed to: {Path(new_path).name})")
                else:
                    print(f"  -> Fixed ({changes} changes)")
            else:
                print(f"  -> Would apply {changes} changes")

        elif result.get('status') == 'partial':
            # Some changes succeeded, some failed
            fixed_count += 1
            errors = result.get('errors', 0)
            changes = result.get('changes_made', 0)
            total_changes += changes

            if not dry_run:
                queue.update_status(
                    item['id'],
                    AlbumStatus.FIXED,
                    metadata={'fix_result': result.get('data'), 'has_errors': True}
                )
            print(f"  -> Partial: {changes} changes, {errors} errors")

        else:
            failed_count += 1
            error_msg = result.get('error', 'Unknown error')
            print(f"  -> Failed: {error_msg}")
            state.log_error(album_path, "fix_error", error_msg)

    # Summary
    print()
    print("=" * 50)
    if dry_run:
        print("DRY RUN complete!")
        print(f"  Would fix: {fixed_count} albums")
        print(f"  Total changes: {total_changes}")
    else:
        print("Fix operation complete!")
        print(f"  Albums fixed: {fixed_count}/{len(ready)}")
        print(f"  Total changes: {total_changes}")
        if failed_count > 0:
            print(f"  Failed: {failed_count}")

    print()
    if not dry_run and fixed_count > 0:
        print("Run 'music-clean status' to view current state")

    return 0


def _discover_albums(scan_path: Path) -> list:
    """Return album folders (dirs containing audio) under ``scan_path``.

    Mirrors the discovery logic in :func:`cmd_scan`: a single album folder, or
    one/two levels of subdirectories (artist/album layout).
    """
    albums = []
    if scan_path.is_dir() and _has_audio_files(scan_path):
        albums.append(str(scan_path))
        return albums
    for item in scan_path.iterdir():
        if item.is_dir() and not is_excluded_dir(item.name):
            if _has_audio_files(item):
                albums.append(str(item))
            else:
                for subitem in item.iterdir():
                    if (subitem.is_dir() and not is_excluded_dir(subitem.name)
                            and _has_audio_files(subitem)):
                        albums.append(str(subitem))
    return albums


def cmd_lifecycle(args):
    """Run the full lifecycle pipeline in canonical order over ``args.path``.

    Phases (LIFECYCLE_PHASES): scan -> identify -> validate -> dedupe -> covers -> fix.

    Safety: default is dry-run. Music is written ONLY under --execute. --scan-only
    and --dry-run never modify audio or move files.

    Queue strategy: archive the existing queue to state/history/ then clear it for
    a fresh run; append a dated run summary to state/run_history.json at the end.
    """
    from datetime import datetime

    from .config import ConfigManager
    from .state import StateStore
    from .queue import QueueManager, AlbumStatus, Priority
    from . import run_history

    print_banner()

    # Resolve mode (default = dry-run). Music is touched only under --execute.
    scan_only = bool(args.scan_only)
    execute = bool(args.execute)
    dry_run = not scan_only and not execute
    mode = "scan-only" if scan_only else ("execute" if execute else "dry-run")

    scan_path = Path(str(args.path).replace('\\', '/'))
    if not scan_path.exists():
        print(f"Error: Path not found: {scan_path}")
        return 1

    print(f"Lifecycle target: {scan_path}")
    print(f"Mode: {mode}")
    print(f"Phases: {' -> '.join(LIFECYCLE_PHASES)}")
    print()

    config = ConfigManager()
    state = StateStore(config.state_path)
    queue = QueueManager()

    # --- fresh queue: archive previous run, then clear ---
    archived = queue.archive("state/history")
    if archived:
        print(f"Archived previous queue -> {archived}")
    queue.clear()

    counts = {
        "scanned": 0, "identified": 0, "validated": 0, "needs_review": 0,
        "deduped_moved": 0, "covers_repaired": 0, "folderjpg_added": 0,
        "fixed": 0, "flagged": 0,
    }

    # =================== scan ===================
    print("\n--- Phase: scan ---")
    albums = _discover_albums(scan_path)
    print(f"Albums discovered: {len(albums)}")
    scanner = ScannerAgent(config, state)
    for album_path in albums:
        result = scanner.process({'path': album_path})
        if result.get('status') == 'success':
            counts["scanned"] += 1
            album_id = result.get('album_id')
            issue_count = result.get('issue_count', 0)
            queue.add(
                album_id=album_id,
                path=album_path,
                status=AlbumStatus.SCANNED,
                priority=Priority.HIGH if issue_count > 0 else Priority.NORMAL,
                metadata={
                    'title': result.get('data', {}).get('title'),
                    'artist': result.get('data', {}).get('artist'),
                    'track_count': result.get('track_count'),
                    'has_cover': result.get('has_cover'),
                    'issues': result.get('data', {}).get('issues', []),
                },
            )
    print(f"Scanned: {counts['scanned']}")

    validator = ValidatorAgent(config, state)

    # =================== identify ===================
    # Best-effort AcoustID song-ID for albums with weak/unknown metadata.
    # Fail-soft no-op when there is no API key or fpcalc binary.
    print("\n--- Phase: identify ---")
    for item in queue.get_by_status(AlbumStatus.SCANNED):
        meta = item.get('metadata', {})
        title = (meta.get('title') or '').strip()
        artist = (meta.get('artist') or '').strip()
        unknown = (not title) or (artist.lower() in ('', 'various artists', 'unknown'))
        if not unknown:
            continue
        hits = validator.identify_unknown_tracks(item['path'])
        if hits:
            counts["identified"] += 1
    print(f"Identified (AcoustID): {counts['identified']}")

    # =================== validate ===================
    # Read-only against MusicBrainz/iTunes; never writes to music.
    print("\n--- Phase: validate ---")
    pending = queue.get_by_status(AlbumStatus.SCANNED)
    for item in pending:
        meta = item.get('metadata', {})
        album_name = Path(item['path']).name
        data = {
            'path': item['path'],
            'album_id': item['id'],
            'title': meta.get('title') or album_name,
            'artist': meta.get('artist') or 'Various Artists',
            'track_count': meta.get('track_count', 0),
            'has_cover': meta.get('has_cover', False),
        }
        result = validator.process(data)
        if result.get('status') != 'success':
            continue
        vstatus = result.get('validation_status')
        confidence = result.get('confidence', 0)
        if vstatus == 'auto_approved':
            counts["validated"] += 1
            if result.get('corrections_needed', 0) > 0:
                queue.update_status(item['id'], AlbumStatus.VALIDATED,
                                    metadata={'validation': result.get('data'), 'confidence': confidence})
            else:
                queue.update_status(item['id'], AlbumStatus.VERIFIED,
                                    metadata={'validation': result.get('data'), 'confidence': confidence})
        else:
            counts["needs_review"] += 1
            queue.update_status(item['id'], AlbumStatus.NEEDS_REVIEW,
                                metadata={'validation': result.get('data'), 'confidence': confidence})
    print(f"Validated (auto): {counts['validated']}  |  Needs review: {counts['needs_review']}")

    # =================== dedupe ===================
    print("\n--- Phase: dedupe ---")
    from utilities.deduplicate import deduplicate_library
    dd = deduplicate_library(
        str(scan_path),
        backup_dir=args.backup_dir,
        scan_only=scan_only,
        dry_run=dry_run,
        aggressive=bool(args.aggressive),
        fingerprint=not bool(args.no_fingerprint),
    )
    counts["deduped_moved"] = dd.moved
    counts["flagged"] += dd.review_count
    dverb = "Moved" if execute else "Would move"
    print(f"{dverb} (strong): {dd.moved}  |  Review groups: {dd.review_count}")

    # =================== covers ===================
    print("\n--- Phase: covers ---")
    from utilities.repair_covers import repair_library
    from utilities.generate_folder_art import generate_folder_art
    rc = repair_library(str(scan_path), scan_only=scan_only, dry_run=dry_run)
    counts["covers_repaired"] = rc.get('repaired', 0) if execute else rc.get('needs_repair', 0)
    counts["flagged"] += rc.get('failed', 0)
    print(f"Covers needing repair: {rc.get('needs_repair', 0)}  |  "
          f"{'repaired' if execute else 'would repair'}: {counts['covers_repaired']}")
    gfa = generate_folder_art(str(scan_path), execute=execute)
    counts["folderjpg_added"] = gfa.get('written', 0)
    counts["flagged"] += gfa.get('failed', 0)

    # =================== fix ===================
    print("\n--- Phase: fix ---")
    if scan_only:
        print("(scan-only - fix phase skipped)")
    else:
        fixer = FixerAgent(config, state)
        ready = queue.get_ready_to_fix()
        print(f"Albums ready to fix: {len(ready)}")
        for item in ready:
            validation = item.get('metadata', {}).get('validation', {}) or {}
            corrections = validation.get('corrections', [])
            if not corrections:
                if execute:
                    queue.update_status(item['id'], AlbumStatus.VERIFIED)
                continue
            result = fixer.process({'path': item['path'], 'corrections': corrections,
                                    'dry_run': not execute})
            if result.get('status') in ('success', 'partial'):
                counts["fixed"] += 1
                if execute:
                    queue.update_status(item['id'], AlbumStatus.FIXED,
                                        metadata={'fix_result': result.get('data')})
        verb = "Fixed" if execute else "Would fix"
        print(f"{verb}: {counts['fixed']}")

    # --- run summary ---
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "target": str(scan_path),
        "mode": mode,
        "phases": counts,
    }
    run_history.append_run(record)

    print("\n" + "=" * 60)
    print("Lifecycle complete!")
    print(f"  Mode:            {mode}")
    print(f"  Scanned:         {counts['scanned']}")
    print(f"  Identified:      {counts['identified']}")
    print(f"  Validated:       {counts['validated']}")
    print(f"  Needs review:    {counts['needs_review']}")
    print(f"  Deduped moved:   {counts['deduped_moved']}")
    print(f"  Covers repaired: {counts['covers_repaired']}")
    print(f"  Folder.jpg added:{counts['folderjpg_added']}")
    print(f"  Fixed:           {counts['fixed']}")
    print(f"  Flagged:         {counts['flagged']}")
    if scan_only:
        print("\n(scan-only - no changes made)")
    elif dry_run:
        print("\n(dry-run - no changes made)")
    print(f"\nRun summary appended to state/run_history.json")
    return 0


def cmd_status(args):
    """Display current status"""
    from .config import ConfigManager
    from .state import StateStore
    from .queue import QueueManager

    print_banner()

    config = ConfigManager()
    state = StateStore(config.state_path)
    queue = QueueManager()

    session = state.get_session()
    stats = queue.get_statistics()

    print(f"Session ID: {session.get('session_id')}")
    print(f"Status: {session.get('status')}")
    print(f"Library: {session.get('library_root', 'Not set')}")
    print(f"Last checkpoint: {session.get('last_checkpoint', 'Never')}")
    print()

    print("Queue Status:")
    print(f"  Total albums: {stats['total']}")
    print(f"  Pending scan: {stats['pending_scan']}")
    print(f"  Pending validation: {stats['pending_validation']}")
    print(f"  Pending review: {stats['pending_review']}")
    print(f"  Ready to fix: {stats['pending_fix']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped: {stats['skipped']}")
    print()

    # Show errors if any
    errors = state.get_errors()
    if errors:
        print(f"Errors logged: {len(errors)}")
        for err in errors[-5:]:  # Show last 5 errors
            print(f"  - {err.get('error_type')}: {err.get('message')[:50]}")

    return 0


def cmd_resume(args):
    """Resume interrupted session"""
    from .config import ConfigManager
    from .state import StateStore

    print_banner()

    config = ConfigManager()
    state = StateStore(config.state_path)

    session = state.get_session()
    print(f"Resuming session: {session.get('session_id')}")
    print(f"Last checkpoint: {session.get('last_checkpoint')}")
    print()

    # TODO: Implement resume logic based on current phase
    print("Resume not yet implemented - use individual commands")

    return 0


def main():
    """Main entry point"""
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        prog='music-clean',
        description='Music Library Cleanup Orchestrator'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # init
    init_parser = subparsers.add_parser('init', help='Initialize project')
    init_parser.add_argument('path', help='Library root path')
    init_parser.add_argument('--config', default='music-config.yaml', help='Config file path')

    # scan
    scan_parser = subparsers.add_parser('scan', help='Scan library')
    scan_parser.add_argument('--artist', help='Scan specific artist')
    scan_parser.add_argument('--album', help='Scan specific album path')
    scan_parser.add_argument('--full', action='store_true', help='Full rescan')

    # validate
    validate_parser = subparsers.add_parser('validate', help='Validate albums')
    validate_parser.add_argument('--source', default='musicbrainz', help='Data source')
    validate_parser.add_argument('--threshold', type=float, default=0.70, help='Confidence threshold')

    # review
    review_parser = subparsers.add_parser('review', help='Review queue')
    review_parser.add_argument('--list', action='store_true', help='List pending reviews')
    review_parser.add_argument('--approve', metavar='ID', help='Approve album by ID')
    review_parser.add_argument('--reject', metavar='ID', help='Reject album by ID')

    # fix
    fix_parser = subparsers.add_parser('fix', help='Apply fixes')
    fix_parser.add_argument('--dry-run', action='store_true', help='Preview only')
    fix_parser.add_argument('--album', metavar='ID', help='Fix specific album')

    # lifecycle
    lifecycle_parser = subparsers.add_parser(
        'lifecycle', help='Run the full pipeline: scan->identify->validate->dedupe->covers->fix')
    lifecycle_parser.add_argument('path', help='Library / artist / album folder to process')
    lifecycle_parser.add_argument('--scan-only', action='store_true',
                                  help='report only; never modify anything')
    lifecycle_parser.add_argument('--dry-run', action='store_true',
                                  help='preview the plan without writing (default)')
    lifecycle_parser.add_argument('--execute', action='store_true',
                                  help='apply changes (the only mode that writes to music)')
    lifecycle_parser.add_argument('--backup-dir', default=r'D:\music_backup\_duplicates',
                                  help='where dedupe moves losing duplicates')
    lifecycle_parser.add_argument('--aggressive', action='store_true',
                                  help='dedupe also groups remaster/version variants')
    lifecycle_parser.add_argument('--no-fingerprint', action='store_true',
                                  help='dedupe matches on metadata only (skip fpcalc)')

    # status
    subparsers.add_parser('status', help='Show status')

    # resume
    subparsers.add_parser('resume', help='Resume session')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    commands = {
        'init': cmd_init,
        'scan': cmd_scan,
        'validate': cmd_validate,
        'review': cmd_review,
        'fix': cmd_fix,
        'lifecycle': cmd_lifecycle,
        'status': cmd_status,
        'resume': cmd_resume,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args) or 0

    return 1


if __name__ == '__main__':
    sys.exit(main())
