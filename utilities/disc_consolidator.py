"""
Disc Consolidator - Detect and consolidate multi-disc albums.

This is the single, canonical multi-disc consolidation tool for the toolkit
(it replaces the former consolidate_discs.py and consolidate_multidisc.py).

Detects patterns:
- "Album Name [Disc 1]" / "Album Name [CD 1]"
- "Album Name (Disc 1)" / "Album Name (CD 1)"
- "Album Name Disc 1" / "Album Name Disk 1"
- "Album Name CD1" / "Album Name CD 1"
- "Album Name - Disc 1"

Consolidation behaviour:
- All tracks are merged into one flat folder named after the base album.
- Filenames get a disc prefix ("01 Track.mp3" -> "1-01 Track.mp3") so the
  per-disc track numbering is preserved and human-readable.
- The discnumber metadata is set to "N/total" (MP3/FLAC) or the disk tuple (M4A).
- Cover art (folder.jpg / cover.jpg / album.jpg / front.jpg) is carried over.
- Empty source folders are removed after their tracks move.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.stdout.reconfigure(encoding='utf-8')

try:
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4
    from mutagen.flac import FLAC
    from mutagen.easyid3 import EasyID3
except ImportError:
    print("Error: mutagen library required. Install with: pip install mutagen")
    sys.exit(1)

from utilities.core.audio_file import iter_audio_files

# Cover-art filenames carried over to the consolidated folder, in priority order.
COVER_NAMES = ["folder.jpg", "cover.jpg", "album.jpg", "front.jpg"]


@dataclass
class DiscInfo:
    folder: Path
    base_name: str
    disc_number: int
    track_count: int


class DiscConsolidator:
    """Detect and consolidate multi-disc albums."""

    # Patterns to detect disc indicators (base name, disc number).
    DISC_PATTERNS = [
        (r'^(.+?)\s*\[(?:Disc|Disk|CD)\s*(\d+)\]$', 'bracket'),   # "Album [Disc 1]" / "[CD 1]"
        (r'^(.+?)\s*\((?:Disc|Disk|CD)\s*(\d+)\)$', 'paren'),     # "Album (Disc 1)" / "(CD 1)"
        (r'^(.+?)\s*-\s*(?:Disc|Disk|CD)\s*(\d+)$', 'dash'),      # "Album - Disc 1"
        (r'^(.+?)\s*(?:Disc|Disk)\s*(\d+)$', 'suffix'),           # "Album Disc 1" / "Album Disk 1"
        (r'^(.+?)\s*CD\s*(\d+)$', 'suffix_cd'),                   # "Album CD1" / "Album CD 1"
    ]

    def __init__(self):
        self.disc_sets: Dict[str, List[DiscInfo]] = {}
        self.orphaned_discs: Dict[str, DiscInfo] = {}

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
        """Find all multi-disc sets in the given path.

        Sets with 2+ discs are stored in ``self.disc_sets``; lone discs are
        recorded in ``self.orphaned_discs`` for reporting (an incomplete set).
        """
        base_path = Path(path)
        self.disc_sets = {}
        self.orphaned_discs = {}

        if not base_path.exists():
            print(f"Path not found: {base_path}")
            return {}

        grouped: Dict[str, List[DiscInfo]] = {}

        for folder in (d for d in base_path.iterdir() if d.is_dir()):
            result = self.parse_folder_name(folder.name)
            if result:
                base_name, disc_num = result
                track_count = sum(1 for _ in iter_audio_files(folder))

                disc_info = DiscInfo(
                    folder=folder,
                    base_name=base_name,
                    disc_number=disc_num,
                    track_count=track_count
                )
                grouped.setdefault(base_name, []).append(disc_info)

        for name, discs in grouped.items():
            if len(discs) >= 2:
                self.disc_sets[name] = sorted(discs, key=lambda d: d.disc_number)
            else:
                self.orphaned_discs[name] = discs[0]

        return self.disc_sets

    @staticmethod
    def _set_track_metadata(filepath: Path, album: str, disc_number: int, total_discs: int) -> None:
        """Set album + disc-number metadata across MP3/M4A/FLAC formats."""
        ext = filepath.suffix.lower()
        if ext == '.mp3':
            audio = MP3(str(filepath), ID3=EasyID3)
            audio['album'] = album
            audio['discnumber'] = f"{disc_number}/{total_discs}"
            audio.save()
        elif ext in ('.m4a', '.mp4'):
            audio = MP4(str(filepath))
            audio['\xa9alb'] = [album]
            audio['disk'] = [(disc_number, total_discs)]
            audio.save()
        elif ext == '.flac':
            audio = FLAC(str(filepath))
            audio['album'] = album
            audio['discnumber'] = str(disc_number)
            audio['disctotal'] = str(total_discs)
            audio.save()

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

            for track in iter_audio_files(disc.folder):
                # Add disc prefix to filename if not already present.
                name = track.name
                if not re.match(r'^\d+-', name):
                    new_name = f"{disc_num}-{name}"
                else:
                    new_name = name

                # Move file into the flat target folder.
                dest = target_path / new_name
                if disc.folder != target_path:
                    shutil.move(str(track), str(dest))
                    print(f"    Moved: {name} -> {new_name}")
                elif name != new_name:
                    track.rename(dest)
                    print(f"    Renamed: {name} -> {new_name}")

                # Update album + disc metadata.
                try:
                    self._set_track_metadata(dest, target_name, disc_num, total_discs)
                except Exception as e:
                    print(f"    Warning: Could not update metadata: {e}")

            # Carry over cover art and remove the now-empty source folder.
            if disc.folder != target_path:
                self._carry_cover_art(disc.folder, target_path)
                remaining = list(disc.folder.iterdir())
                if not remaining:
                    disc.folder.rmdir()
                    print(f"  Removed empty folder: {disc.folder.name}")

        print(f"\n  Consolidation complete!")
        return True

    @staticmethod
    def _carry_cover_art(source: Path, target: Path) -> None:
        """Move the first available cover image into the target if it lacks one."""
        if any((target / name).exists() for name in COVER_NAMES):
            return
        for name in COVER_NAMES:
            candidate = source / name
            if candidate.exists():
                shutil.move(str(candidate), str(target / "folder.jpg"))
                return

    def consolidate_all(self, path: str | Path, dry_run: bool = False) -> Dict:
        """Detect and consolidate all multi-disc albums."""
        disc_sets = self.detect_multi_disc(path)

        results = {
            'found': len(disc_sets),
            'consolidated': 0,
            'skipped': 0,
            'errors': 0,
            'orphaned': len(self.orphaned_discs),
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
        if consolidator.orphaned_discs:
            print(f"\n=== ORPHANED DISCS ({len(consolidator.orphaned_discs)}) ===")
            for album, d in consolidator.orphaned_discs.items():
                print(f"  {album} (Disc {d.disc_number}, {d.track_count} tracks)")
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
        print(f"Orphaned: {results['orphaned']}")
        print(f"Errors: {results['errors']}")


if __name__ == '__main__':
    main()
