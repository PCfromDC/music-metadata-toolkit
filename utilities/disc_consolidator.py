"""
Disc Consolidator - Detect and consolidate multi-disc albums

Detects patterns:
- "Album Name [Disc 1]", "Album Name [Disc 2]"
- "Album Name Disc 1", "Album Name Disc 2"
- "Album Name CD1", "Album Name CD2"
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    from mutagen.mp3 import MP3
    from mutagen.easyid3 import EasyID3
except ImportError:
    print("Error: mutagen library required. Install with: pip install mutagen")
    sys.exit(1)


@dataclass
class DiscInfo:
    folder: Path
    base_name: str
    disc_number: int
    track_count: int


class DiscConsolidator:
    """Detect and consolidate multi-disc albums."""

    # Patterns to detect disc indicators
    DISC_PATTERNS = [
        (r'^(.+?)\s*\[Disc\s*(\d+)\]$', 'bracket'),      # "Album [Disc 1]"
        (r'^(.+?)\s*\[CD\s*(\d+)\]$', 'bracket_cd'),     # "Album [CD 1]"
        (r'^(.+?)\s*Disc\s*(\d+)$', 'suffix'),           # "Album Disc 1"
        (r'^(.+?)\s*CD\s*(\d+)$', 'suffix_cd'),          # "Album CD 1"
        (r'^(.+?)\s*-\s*Disc\s*(\d+)$', 'dash'),         # "Album - Disc 1"
    ]

    def __init__(self):
        self.disc_sets: Dict[str, List[DiscInfo]] = {}

    def parse_folder_name(self, name: str) -> Optional[Tuple[str, int]]:
        """Extract base album name and disc number from folder name."""
        for pattern, _ in self.DISC_PATTERNS:
            match = re.match(pattern, name, re.IGNORECASE)
            if match:
                base_name = match.group(1).strip()
                disc_num = int(match.group(2))
                return base_name, disc_num
        return None

    def detect_multi_disc(self, path: str | Path) -> Dict[str, List[DiscInfo]]:
        """Find all multi-disc sets in the given path."""
        base_path = Path(path)
        self.disc_sets = {}

        if not base_path.exists():
            print(f"Path not found: {base_path}")
            return {}

        folders = [d for d in base_path.iterdir() if d.is_dir()]

        for folder in folders:
            result = self.parse_folder_name(folder.name)
            if result:
                base_name, disc_num = result
                track_count = len(list(folder.glob("*.mp3")))

                disc_info = DiscInfo(
                    folder=folder,
                    base_name=base_name,
                    disc_number=disc_num,
                    track_count=track_count
                )

                if base_name not in self.disc_sets:
                    self.disc_sets[base_name] = []
                self.disc_sets[base_name].append(disc_info)

        # Filter to only include actual sets (2+ discs)
        self.disc_sets = {
            name: sorted(discs, key=lambda d: d.disc_number)
            for name, discs in self.disc_sets.items()
            if len(discs) >= 2
        }

        return self.disc_sets

    def consolidate(
        self,
        album_name: str,
        discs: List[DiscInfo],
        target_folder: Optional[str] = None,
        dry_run: bool = False
    ) -> bool:
        """Consolidate a multi-disc set into a single folder."""
        if not discs:
            return False

        base_path = discs[0].folder.parent
        target_name = target_folder or album_name
        target_path = base_path / target_name

        total_discs = max(d.disc_number for d in discs)

        print(f"\n=== Consolidating: {album_name} ===")
        print(f"  Discs found: {len(discs)}")
        print(f"  Target: {target_name}")

        if dry_run:
            for disc in discs:
                print(f"  [Disc {disc.disc_number}] {disc.folder.name} ({disc.track_count} tracks)")
            print("  (Dry run - no changes)")
            return True

        # Create target folder if needed
        target_path.mkdir(exist_ok=True)

        for disc in discs:
            disc_num = disc.disc_number
            print(f"\n  Processing Disc {disc_num}...")

            for mp3 in sorted(disc.folder.glob("*.mp3")):
                # Add disc prefix to filename if not present
                name = mp3.name
                if not re.match(r'^\d+-', name):
                    new_name = f"{disc_num}-{name}"
                else:
                    new_name = name

                # Move file
                dest = target_path / new_name
                if disc.folder != target_path:
                    shutil.move(str(mp3), str(dest))
                    print(f"    Moved: {name} -> {new_name}")
                elif name != new_name:
                    mp3.rename(dest)
                    print(f"    Renamed: {name} -> {new_name}")

                # Update metadata
                try:
                    audio = MP3(str(dest), ID3=EasyID3)
                    audio['album'] = target_name
                    audio['discnumber'] = f"{disc_num}/{total_discs}"
                    audio.save()
                except Exception as e:
                    print(f"    Warning: Could not update metadata: {e}")

            # Remove empty source folder
            if disc.folder != target_path:
                remaining = list(disc.folder.glob("*"))
                # Keep folder.jpg if present
                folder_jpg = disc.folder / "folder.jpg"
                if folder_jpg.exists() and not (target_path / "folder.jpg").exists():
                    shutil.move(str(folder_jpg), str(target_path / "folder.jpg"))
                    remaining = [f for f in remaining if f.name != "folder.jpg"]

                if not remaining:
                    disc.folder.rmdir()
                    print(f"  Removed empty folder: {disc.folder.name}")

        print(f"\n  Consolidation complete!")
        return True

    def consolidate_all(self, path: str | Path, dry_run: bool = False) -> Dict:
        """Detect and consolidate all multi-disc albums."""
        disc_sets = self.detect_multi_disc(path)

        results = {
            'found': len(disc_sets),
            'consolidated': 0,
            'skipped': 0,
            'errors': 0
        }

        if not disc_sets:
            print("No multi-disc sets found.")
            return results

        print(f"\n=== Found {len(disc_sets)} multi-disc sets ===")

        for album_name, discs in disc_sets.items():
            try:
                if self.consolidate(album_name, discs, dry_run=dry_run):
                    results['consolidated'] += 1
                else:
                    results['skipped'] += 1
            except Exception as e:
                print(f"Error consolidating {album_name}: {e}")
                results['errors'] += 1

        return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Consolidate multi-disc albums')
    parser.add_argument('path', help='Path to scan')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    parser.add_argument('--scan-only', action='store_true', help='Only detect, do not consolidate')
    parser.add_argument('--album', help='Consolidate specific album only')

    args = parser.parse_args()

    consolidator = DiscConsolidator()

    if args.scan_only:
        disc_sets = consolidator.detect_multi_disc(args.path)
        print(f"\n=== MULTI-DISC SETS FOUND ({len(disc_sets)}) ===")
        for album, discs in disc_sets.items():
            print(f"\n{album}:")
            for d in discs:
                print(f"  [Disc {d.disc_number}] {d.folder.name} ({d.track_count} tracks)")
    elif args.album:
        disc_sets = consolidator.detect_multi_disc(args.path)
        if args.album in disc_sets:
            consolidator.consolidate(args.album, disc_sets[args.album], dry_run=args.dry_run)
        else:
            print(f"Album not found: {args.album}")
    else:
        results = consolidator.consolidate_all(args.path, dry_run=args.dry_run)
        print(f"\n=== SUMMARY ===")
        print(f"Found: {results['found']}")
        print(f"Consolidated: {results['consolidated']}")
        print(f"Skipped: {results['skipped']}")
        print(f"Errors: {results['errors']}")


if __name__ == '__main__':
    main()
