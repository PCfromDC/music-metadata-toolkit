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


def main():
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
