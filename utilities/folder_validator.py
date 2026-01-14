"""
Folder Validator - Detect and auto-fix folder name issues

Detects:
- Truncated names (folder shorter than metadata)
- Character substitutions (_, café→cafe, etc.)
- Multi-disc indicators in folder names
"""

from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    from mutagen.mp3 import MP3
    from mutagen.easyid3 import EasyID3
except ImportError:
    print("Error: mutagen library required. Install with: pip install mutagen")
    sys.exit(1)


class IssueType(Enum):
    TRUNCATED = "truncated"
    SUBSTITUTION = "substitution"
    MULTI_DISC = "multi_disc"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


@dataclass
class FolderIssue:
    folder_path: Path
    folder_name: str
    metadata_album: str
    expected_name: str
    issue_type: IssueType
    confidence: float = 1.0


class FolderValidator:
    """Validate and fix folder names against track metadata."""

    # Characters unsafe for Windows filenames
    UNSAFE_CHARS = [':', '?', '*', '"', '<', '>', '|']

    # Substitution patterns
    SUBSTITUTIONS = [
        (r'[:\u2013\u2014]', ' -'),  # Colon and dashes → " -"
        (r'[éèê]', 'e'),              # Accented e
        (r'[àâ]', 'a'),               # Accented a
        (r'[ùû]', 'u'),               # Accented u
        (r'[îï]', 'i'),               # Accented i
        (r'[ôö]', 'o'),               # Accented o
        (r'[ç]', 'c'),                # Cedilla
        (r'[ñ]', 'n'),                # Tilde n
    ]

    def __init__(self):
        self.issues: List[FolderIssue] = []

    def make_windows_safe(self, name: str) -> str:
        """Convert album name to Windows-safe folder name."""
        result = name

        # Replace colon with ' -'
        result = result.replace(':', ' -')

        # Remove other unsafe characters
        for char in ['?', '*', '"', '<', '>', '|']:
            result = result.replace(char, '')

        # Normalize whitespace
        result = ' '.join(result.split())

        return result.strip()

    def get_album_metadata(self, folder: Path) -> Optional[str]:
        """Get album name from first MP3 in folder."""
        mp3s = list(folder.glob("*.mp3"))
        if not mp3s:
            return None

        try:
            audio = MP3(str(mp3s[0]), ID3=EasyID3)
            album = audio.get('album', [''])[0]
            return album if album else None
        except Exception:
            return None

    def categorize_issue(self, folder_name: str, metadata: str) -> IssueType:
        """Determine the type of mismatch."""
        safe_metadata = self.make_windows_safe(metadata)

        # Check for truncation
        if len(folder_name) < len(safe_metadata):
            # Folder appears to be truncated version of metadata
            if safe_metadata.lower().startswith(folder_name.lower()[:len(folder_name)-3]):
                return IssueType.TRUNCATED

        # Check for character substitution
        # Common patterns: _ vs :, café vs cafe, etc.
        if '_' in folder_name or 'é' in folder_name or 'à' in folder_name:
            return IssueType.SUBSTITUTION

        # Check for multi-disc indicator
        disc_patterns = [r'\[Disc\s*\d+\]', r'Disc\s*\d+', r'CD\s*\d+']
        for pattern in disc_patterns:
            if re.search(pattern, folder_name, re.IGNORECASE):
                return IssueType.MULTI_DISC
            if re.search(pattern, metadata, re.IGNORECASE):
                return IssueType.MULTI_DISC

        # General mismatch
        return IssueType.MISMATCH

    def scan(self, path: str | Path) -> List[FolderIssue]:
        """Scan all folders and return list of issues."""
        base_path = Path(path)
        self.issues = []

        if not base_path.exists():
            print(f"Path not found: {base_path}")
            return []

        folders = sorted([d for d in base_path.iterdir() if d.is_dir()])
        print(f"Scanning {len(folders)} folders...")

        for folder in folders:
            metadata = self.get_album_metadata(folder)
            if not metadata:
                continue

            expected = self.make_windows_safe(metadata)

            if folder.name != expected:
                issue_type = self.categorize_issue(folder.name, metadata)
                issue = FolderIssue(
                    folder_path=folder,
                    folder_name=folder.name,
                    metadata_album=metadata,
                    expected_name=expected,
                    issue_type=issue_type
                )
                self.issues.append(issue)

        return self.issues

    def fix_issue(self, issue: FolderIssue, dry_run: bool = False) -> bool:
        """Fix a single folder issue."""
        if issue.issue_type == IssueType.MULTI_DISC:
            # Skip multi-disc - handled by DiscConsolidator
            print(f"  SKIP (multi-disc): {issue.folder_name}")
            return False

        new_path = issue.folder_path.parent / issue.expected_name

        if new_path.exists():
            print(f"  SKIP (target exists): {issue.folder_name}")
            return False

        if dry_run:
            print(f"  WOULD RENAME: {issue.folder_name}")
            print(f"            TO: {issue.expected_name}")
            return True

        try:
            issue.folder_path.rename(new_path)
            print(f"  RENAMED: {issue.folder_name}")
            print(f"       TO: {issue.expected_name}")
            return True
        except Exception as e:
            print(f"  ERROR: {issue.folder_name} - {e}")
            return False

    def fix_all(self, path: str | Path, dry_run: bool = False) -> Dict:
        """Scan and fix all issues autonomously."""
        issues = self.scan(path)

        results = {
            'scanned': len(list(Path(path).iterdir())),
            'issues': len(issues),
            'fixed': 0,
            'skipped': 0,
            'errors': 0
        }

        if not issues:
            print("No issues found.")
            return results

        print(f"\n=== Found {len(issues)} issues ===\n")

        # Group by type
        by_type = {}
        for issue in issues:
            t = issue.issue_type.value
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(issue)

        # Process each type
        for issue_type, type_issues in by_type.items():
            print(f"\n--- {issue_type.upper()} ({len(type_issues)}) ---")
            for issue in type_issues:
                if self.fix_issue(issue, dry_run):
                    results['fixed'] += 1
                else:
                    results['skipped'] += 1

        return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate and fix folder names')
    parser.add_argument('path', help='Path to scan')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    parser.add_argument('--scan-only', action='store_true', help='Only scan, do not fix')

    args = parser.parse_args()

    validator = FolderValidator()

    if args.scan_only:
        issues = validator.scan(args.path)
        print(f"\n=== SCAN RESULTS ===")
        for issue in issues:
            print(f"\n[{issue.issue_type.value}]")
            print(f"  Folder:   {issue.folder_name}")
            print(f"  Metadata: {issue.metadata_album}")
            print(f"  Expected: {issue.expected_name}")
    else:
        results = validator.fix_all(args.path, dry_run=args.dry_run)
        print(f"\n=== SUMMARY ===")
        print(f"Scanned: {results['scanned']}")
        print(f"Issues:  {results['issues']}")
        print(f"Fixed:   {results['fixed']}")
        print(f"Skipped: {results['skipped']}")


if __name__ == '__main__':
    main()
