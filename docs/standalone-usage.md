# Standalone Usage Guide (Without Claude Code)

This guide explains how to use the Music Library Metadata Management System without Claude Code. The core functionality is 100% standalone Python with no AI dependencies.

## Quick Start

### Installation

```bash
# Required packages
pip install mutagen requests

# Optional (for YAML configs)
pip install pyyaml
```

### Verify Installation

```bash
python cli.py --help
```

Expected output:
```
usage: cli.py [-h] {scan,validate,consolidate,move-track,embed-cover,status,resume} ...

Music Library Metadata Management CLI
```

---

## Complete Cleanup Workflow

### Step 1: Scan and Extract Metadata

```bash
python cli.py scan "/path/to/music/Artist Name"
```

**What it does:**
- Scans all albums in the artist folder
- Extracts metadata from each track
- Generates JSON and CSV reports in `outputs/`

**Output files:**
- `outputs/artist_name_library_audit.json`
- `outputs/artist_name_library_audit.csv`

### Step 2: Validate and Fix Folder Names

```bash
# Preview only (no changes)
python cli.py validate "/path/to/music/Artist Name" --scan-only

# Apply fixes
python cli.py validate "/path/to/music/Artist Name"
```

**What it fixes:**
- Truncated folder names (e.g., `Album - Long Na...` → `Album - Long Name`)
- Character substitutions (e.g., `Album_ Subtitle` → `Album - Subtitle`)
- Windows-unsafe characters (removes `: ? * " < > |`)

### Step 3: Consolidate Multi-Disc Albums

```bash
# Preview only
python cli.py consolidate "/path/to/music/Artist Name" --scan-only

# Apply consolidation
python cli.py consolidate "/path/to/music/Artist Name"
```

**What it does:**
- Detects patterns: `[Disc 1]`, `Disc 1`, `CD1`, `- Disc 1`
- Renames files: `01 Track.mp3` → `1-01 Track.mp3`
- Updates metadata: Sets `discnumber` field
- Merges folders: Combines disc folders into base album folder

### Step 4: Embed Cover Art

```bash
# From URL
python utilities/embed_cover.py "path/to/album" "https://example.com/cover.jpg"

# From local file
python utilities/embed_cover.py "path/to/album" "/path/to/cover.jpg"

# Force replace existing
python utilities/embed_cover.py "path/to/album" "cover.jpg" --force
```

**Finding cover art URLs:**

Use iTunes Search API (free, no auth):
```bash
# Search for album cover
curl "https://itunes.apple.com/search?term=Artist+Album&entity=album&limit=5"
```

In the JSON response, find `artworkUrl100` and replace `100x100` with `1200x1200`:
```
"artworkUrl100": "https://...100x100bb.jpg"
→ Change to: "https://...1200x1200bb.jpg"
```

### Step 5: Generate Final Report

```bash
python utilities/extract_metadata.py "/path/to/music/Artist Name"
```

---

## Individual Utility Scripts

### Fix Single Track Metadata

```bash
# Fix artist
python utilities/fix_metadata.py artist "path/to/track.mp3" "Correct Artist"

# Fix title
python utilities/fix_metadata.py title "path/to/track.mp3" "Correct Title"

# Fix genre
python utilities/fix_metadata.py genre "path/to/track.mp3" "Rock"
```

### Batch Fix Genre

```bash
python utilities/batch_fix_metadata.py "path/to/album" "Rock"
```

### Move Track Between Albums

```bash
python cli.py move-track "source/track.mp3" "dest/album" \
    --album "New Album Name" \
    --artist "Artist Name" \
    --number "5/12"
```

### Sync folder.jpg from Embedded Art

```bash
python utilities/embed_cover.py "path/to/album" --sync-folder
```

### Extract Current Embedded Art

```bash
python utilities/embed_cover.py "path/to/album" --show-current
```

---

## Automation Scripts

### PowerShell (Windows)

```powershell
# cleanup-artist.ps1
param(
    [Parameter(Mandatory=$true)]
    [string]$ArtistPath
)

Write-Host "=== Music Library Cleanup ===" -ForegroundColor Cyan
Write-Host "Path: $ArtistPath"
Write-Host ""

Write-Host "Step 1: Scanning metadata..." -ForegroundColor Yellow
python cli.py scan $ArtistPath

Write-Host "Step 2: Validating folder names..." -ForegroundColor Yellow
python cli.py validate $ArtistPath

Write-Host "Step 3: Consolidating multi-disc albums..." -ForegroundColor Yellow
python cli.py consolidate $ArtistPath

Write-Host ""
Write-Host "Done! Check outputs/ for reports." -ForegroundColor Green
```

Usage:
```powershell
.\cleanup-artist.ps1 -ArtistPath "/path/to/music/Various Artists"
```

### Bash (Linux/macOS)

```bash
#!/bin/bash
# cleanup-artist.sh

if [ -z "$1" ]; then
    echo "Usage: ./cleanup-artist.sh <path>"
    exit 1
fi

ARTIST_PATH="$1"

echo "=== Music Library Cleanup ==="
echo "Path: $ARTIST_PATH"
echo ""

echo "Step 1: Scanning metadata..."
python cli.py scan "$ARTIST_PATH"

echo "Step 2: Validating folder names..."
python cli.py validate "$ARTIST_PATH"

echo "Step 3: Consolidating multi-disc albums..."
python cli.py consolidate "$ARTIST_PATH"

echo ""
echo "Done! Check outputs/ for reports."
```

Usage:
```bash
chmod +x cleanup-artist.sh
./cleanup-artist.sh "/mnt/music/Various Artists"
```

### Batch Process Multiple Artists

```powershell
# cleanup-all.ps1
$MusicRoot = "/path/to/music"

Get-ChildItem $MusicRoot -Directory | ForEach-Object {
    $artist = $_.Name
    Write-Host "Processing: $artist" -ForegroundColor Cyan

    python cli.py validate "$MusicRoot/$artist"
    python cli.py consolidate "$MusicRoot/$artist"
}
```

---

## Configuration Files

### music-config.yaml

```yaml
library:
  root: "/path/to/music"
  backup_enabled: true

thresholds:
  auto_approve: 0.95
  review_required: 0.80

naming:
  replace_colon_with: " -"
```

### YAML Batch Renames

Create `configs/active/my_renames.yaml`:

```yaml
base_path: "/path/to/music/Various Artists"
renames:
  - from: "Old Folder Name"
    to: "New Folder Name"
  - from: "Another Old"
    to: "Another New"
```

---

## Troubleshooting

### "mutagen not found"

```bash
pip install mutagen
```

### "UNC paths not supported" (Windows)

Use forward slashes for network paths:
```bash
# Wrong
python cli.py scan "\\openmediavault\music\Artist"

# Correct
python cli.py scan "/path/to/music/Artist"
```

### Permission denied on network drive

Run PowerShell/terminal as administrator, or map the network drive:
```cmd
net use Z: \\openmediavault\music
python cli.py scan "Z:/Artist"
```

### Unicode filename errors

The scripts handle UTF-8 by default. If you see encoding errors:
```bash
# Set Python UTF-8 mode
set PYTHONUTF8=1
python cli.py scan "path"
```

---

## What You're Missing Without Claude

The following features require Claude Code:

| Feature | Why It Needs Claude |
|---------|---------------------|
| `/verify-covers` | Uses Claude vision to visually inspect cover art |
| `/clean-music` autonomous mode | AI orchestrates all steps without prompts |
| Knowledge base learning | Logs corrections to `.claude/knowledge/` |
| Conflict resolution | AI decides between MusicBrainz vs iTunes data |

**Workarounds:**
- **Cover verification**: Manually open `folder.jpg` and compare to album
- **Autonomous mode**: Run the 5 steps in order using scripts above
- **Learning**: Keep notes in `issues/` folder manually
- **Conflicts**: Research on MusicBrainz.org and decide manually

---

## API Reference

### CLI Commands

| Command | Arguments | Options |
|---------|-----------|---------|
| `scan <path>` | Artist folder path | `--artist`, `--dry-run` |
| `validate <path>` | Artist folder path | `--scan-only`, `--dry-run` |
| `consolidate <path>` | Artist folder path | `--scan-only`, `--dry-run` |
| `move-track <src> <dest>` | Source file, dest folder | `--album`, `--artist`, `--number` |
| `embed-cover <path> <image>` | Album path, image URL/path | `--force` |

### Utility Scripts

| Script | Purpose |
|--------|---------|
| `extract_metadata.py` | Generate JSON/CSV reports |
| `fix_metadata.py` | Fix single track metadata |
| `batch_fix_metadata.py` | Batch fix genre for album |
| `embed_cover.py` | Embed/sync cover art |
| `folder_validator.py` | Validate folder names |
| `disc_consolidator.py` | Consolidate multi-disc albums |
| `track_mover.py` | Move tracks between albums |

---

## Getting Help

- **README.md** - Quick start guide
- **CLAUDE.md** - Comprehensive technical documentation
- **issues/** - Issue tracking and resolution examples

For bugs or feature requests, check the codebase documentation or modify scripts as needed - everything is open Python code.
