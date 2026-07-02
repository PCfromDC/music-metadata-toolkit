#!/usr/bin/env python3
"""
Music Library Cleanup CLI

Unified command-line interface for music metadata management.

Usage:
    python cli.py <command> [options]

Commands:
    scan <path>              Scan albums, extract metadata
    validate <path>          Validate and fix folder names vs metadata
    fix <path>               Apply metadata fixes
    consolidate <path>       Find and consolidate multi-disc albums
    move-track <src> <dest>  Move track between albums
    embed-cover <path>       Embed cover art from URL/file
    repair-covers <path>     Detect and repair corrupted embedded album art
    status                   Show processing status
    resume                   Resume interrupted session
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def cmd_scan(args):
    """Scan albums and extract metadata."""
    from orchestrator.music_metadata_system import MusicMetadataSystem

    system = MusicMetadataSystem()
    system.process_path(args.path)


def cmd_validate(args):
    """Validate folder names against metadata and auto-fix."""
    from utilities.folder_validator import FolderValidator

    validator = FolderValidator()
    results = validator.fix_all(args.path, dry_run=args.dry_run)

    print(f"\n=== Validation Results ===")
    print(f"Folders scanned: {results['scanned']}")
    print(f"Issues found: {results['issues']}")
    print(f"Fixed: {results['fixed']}")
    if args.dry_run:
        print("(Dry run - no changes made)")


def cmd_consolidate(args):
    """Find and consolidate multi-disc albums."""
    from utilities.disc_consolidator import DiscConsolidator

    consolidator = DiscConsolidator()
    results = consolidator.consolidate_all(args.path, dry_run=args.dry_run)

    print(f"\n=== Consolidation Results ===")
    print(f"Multi-disc sets found: {results['found']}")
    print(f"Consolidated: {results['consolidated']}")
    if args.dry_run:
        print("(Dry run - no changes made)")


def cmd_move_track(args):
    """Move a track to a different album."""
    from utilities.track_mover import TrackMover

    mover = TrackMover()
    mover.move(
        source=args.source,
        dest_folder=args.dest,
        track_number=args.number,
        album=args.album,
        artist=args.artist
    )


def cmd_embed_cover(args):
    """Embed cover art into album tracks."""
    from utilities.embed_cover import embed_cover_art

    embed_cover_art(args.path, args.cover)


def cmd_repair_covers(args):
    """Detect and repair corrupted embedded album art."""
    from utilities.repair_covers import repair_library

    summary = repair_library(
        args.path,
        scan_only=args.scan_only,
        dry_run=args.dry_run,
    )

    print(f"\n=== Repair Covers Summary ===")
    print(f"Album folders scanned: {summary['albums']}")
    print(f"Albums needing repair: {summary['needs_repair']}")
    if not args.scan_only and not args.dry_run:
        print(f"Albums repaired:       {summary['repaired']}")
        print(f"Tracks re-embedded:    {summary['files_fixed']}")
        print(f"Albums skipped:        {summary['skipped']}")
        print(f"Albums failed:         {summary['failed']}")
    if args.scan_only:
        print("(Scan only - no changes made)")
    if args.dry_run:
        print("(Dry run - no changes made)")


def cmd_sync_covers(args):
    """Reconcile embedded track art with the album folder image (folder.jpg authoritative)."""
    from utilities.cover_consistency import sync_library, _print_summary

    summary = sync_library(
        args.path,
        scan_only=args.scan_only,
        dry_run=args.dry_run or not (args.scan_only or args.execute),
        execute=args.execute,
        log_path=getattr(args, 'log', None),
    )
    _print_summary(summary)


def cmd_dedupe(args):
    """Find duplicate copies of a track in a folder; move losers to backup."""
    from utilities.deduplicate import deduplicate_library

    summ = deduplicate_library(
        args.path,
        backup_dir=args.backup_dir,
        scan_only=args.scan_only,
        dry_run=not args.execute and not args.scan_only,
        aggressive=args.aggressive,
        fingerprint=not args.no_fingerprint,
    )
    verb = "Moved" if args.execute else "Would move"
    print("\n=== De-duplication Summary ===")
    print(f"Albums scanned:           {summ.albums}")
    print(f"Tracks examined:          {summ.tracks}")
    print(f"Duplicate groups:         {summ.groups}")
    print(f"{verb} (strong):          {summ.moved}  (~{summ.space_recovered_kb // 1024} MB)")
    print(f"Probable/cross (review):  {summ.review_count}")
    if summ.failed:
        print(f"Failed:                   {summ.failed}")
    if args.scan_only:
        print("(scan-only - no changes made)")
    elif not args.execute:
        print("(dry-run - no changes made)")


def cmd_lifecycle(args):
    """Run the full lifecycle pipeline (scan->identify->validate->dedupe->covers->fix)."""
    from orchestrator.main import cmd_lifecycle as _orchestrator_lifecycle

    return _orchestrator_lifecycle(args)


def cmd_status(args):
    """Show processing status."""
    from orchestrator.state import SessionState

    state = SessionState.load()
    if state:
        print(f"Session: {state.session_id}")
        print(f"Status: {state.status}")
        print(f"Albums processed: {state.processed_count}")
        print(f"Albums remaining: {state.remaining_count}")
    else:
        print("No active session.")


def cmd_resume(args):
    """Resume interrupted session."""
    from orchestrator.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    orchestrator.resume()


def _force_utf8_console():
    """Make stdout/stderr UTF-8 so printing non-ASCII tags never crashes the run.

    On Windows the console/redirected pipe defaults to cp1252; printing an album or
    artist name with characters outside it raises UnicodeEncodeError and aborts the
    pipeline. errors='replace' keeps output flowing.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def main():
    _force_utf8_console()
    parser = argparse.ArgumentParser(
        prog='music-clean',
        description='Music Library Cleanup CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # scan command
    scan_parser = subparsers.add_parser('scan', help='Scan albums, extract metadata')
    scan_parser.add_argument('path', help='Path to scan')
    scan_parser.set_defaults(func=cmd_scan)

    # validate command
    validate_parser = subparsers.add_parser('validate', help='Validate and fix folder names')
    validate_parser.add_argument('path', help='Path to validate')
    validate_parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    validate_parser.set_defaults(func=cmd_validate)

    # consolidate command
    consolidate_parser = subparsers.add_parser('consolidate', help='Consolidate multi-disc albums')
    consolidate_parser.add_argument('path', help='Path to scan for multi-disc albums')
    consolidate_parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    consolidate_parser.set_defaults(func=cmd_consolidate)

    # move-track command
    move_parser = subparsers.add_parser('move-track', help='Move track between albums')
    move_parser.add_argument('source', help='Source track path')
    move_parser.add_argument('dest', help='Destination folder')
    move_parser.add_argument('--number', help='New track number (e.g., "5/12")')
    move_parser.add_argument('--album', help='New album name')
    move_parser.add_argument('--artist', help='New album artist')
    move_parser.set_defaults(func=cmd_move_track)

    # embed-cover command
    cover_parser = subparsers.add_parser('embed-cover', help='Embed cover art')
    cover_parser.add_argument('path', help='Album folder path')
    cover_parser.add_argument('cover', help='Cover image URL or file path')
    cover_parser.set_defaults(func=cmd_embed_cover)

    # repair-covers command
    repair_parser = subparsers.add_parser('repair-covers', help='Detect and repair corrupted embedded album art')
    repair_parser.add_argument('path', help='Library / artist / album folder to scan')
    repair_parser.add_argument('--scan-only', action='store_true', help='Report corrupted albums without making changes')
    repair_parser.add_argument('--dry-run', action='store_true', help='Show the repair plan without fetching or writing')
    repair_parser.set_defaults(func=cmd_repair_covers)

    # sync-covers command (folder image <-> embedded art parity)
    sync_parser = subparsers.add_parser(
        'sync-covers',
        help='Make each track match the album folder image (perceptual; folder.jpg authoritative)')
    sync_parser.add_argument('path', help='Library / artist / album folder')
    sync_parser.add_argument('--scan-only', action='store_true', help='report only; never write')
    sync_parser.add_argument('--dry-run', action='store_true', help='show the plan; write nothing (default)')
    sync_parser.add_argument('--execute', action='store_true',
                             help='embed the folder image into mismatched tracks')
    sync_parser.add_argument('--log', default=None, help='execute-mode log path')
    sync_parser.set_defaults(func=cmd_sync_covers)

    # dedupe command
    dedupe_parser = subparsers.add_parser('dedupe', help='Find duplicate tracks; move losers to backup (never deletes)')
    dedupe_parser.add_argument('path', help='Library / artist / album folder to scan')
    dedupe_parser.add_argument('--backup-dir', default=r'D:\music_backup\_duplicates',
                               help='where losing duplicates are moved (mirrors relative paths)')
    dedupe_parser.add_argument('--scan-only', action='store_true', help='report duplicate groups without changes')
    dedupe_parser.add_argument('--dry-run', action='store_true', help='show the keep/move plan without writing')
    dedupe_parser.add_argument('--execute', action='store_true', help='move strong duplicates to the backup dir')
    dedupe_parser.add_argument('--aggressive', action='store_true',
                               help='also group remaster/version variants and move probable matches')
    dedupe_parser.add_argument('--no-fingerprint', action='store_true', help='match on metadata only (skip fpcalc)')
    dedupe_parser.set_defaults(func=cmd_dedupe)

    # lifecycle command
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
    lifecycle_parser.set_defaults(func=cmd_lifecycle)

    # status command
    status_parser = subparsers.add_parser('status', help='Show processing status')
    status_parser.set_defaults(func=cmd_status)

    # resume command
    resume_parser = subparsers.add_parser('resume', help='Resume interrupted session')
    resume_parser.set_defaults(func=cmd_resume)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
