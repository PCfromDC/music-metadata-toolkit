# Music Library Metadata Management System

## Project Overview

This project provides a comprehensive toolset for auditing, verifying, and cleaning music library metadata. It was developed through the systematic cleanup of a U2 music collection (261 tracks across 20+ albums) and is designed to scale to entire music libraries.

## Project Structure

```
D:\music cleanup\
├── cli.py                      # Unified CLI entry point
├── README.md                   # Quick start guide
├── CLAUDE.md                   # This documentation
├── music-config.yaml           # Primary configuration
├── credentials.yaml            # API keys (gitignored)
├── fpcalc.exe                  # Audio fingerprinting binary
├── .gitignore
│
├── orchestrator/               # Core orchestration engine
│   ├── main.py                 # CLI commands
│   ├── music_metadata_system.py# Main processing system
│   ├── orchestrator.py
│   ├── config.py               # YAML configuration management
│   ├── state.py                # Session and album state
│   └── queue.py                # Processing queue
│
├── agents/                     # Specialized processing agents
│   ├── scanner.py              # Scans albums, extracts metadata
│   ├── validator.py            # Validates against MusicBrainz/iTunes
│   └── fixer.py                # Applies corrections, embeds covers
│
├── sources/                    # Data source adapters
│   ├── musicbrainz.py          # MusicBrainz API
│   ├── itunes.py               # iTunes Search API (free, no auth)
│   ├── spotify.py              # Spotify API
│   ├── acoustid.py             # Audio fingerprinting
│   └── discogs.py              # Discogs API
│
├── utilities/                  # Reusable tools
│   ├── folder_validator.py     # Auto-fix folder name mismatches
│   ├── disc_consolidator.py    # Multi-disc album consolidation
│   ├── track_mover.py          # Move tracks between albums
│   ├── scan_folders.py         # Compare folder names to metadata
│   ├── extract_metadata.py     # Metadata extraction
│   ├── fix_metadata.py         # Single-file metadata fixes
│   ├── batch_fix_metadata.py   # Batch metadata operations
│   ├── embed_cover.py          # Cover art embedding
│   └── consolidate_multidisc.py# Multi-disc consolidation
│
├── configs/                    # YAML configurations
│   ├── templates/              # Config templates
│   │   ├── batch_rename.yaml   # Batch folder renaming
│   │   ├── consolidation.yaml  # Multi-disc consolidation
│   │   └── move_tracks.yaml    # Track movement config
│   └── active/                 # User's active configs
│
├── scripts/                    # Script archive
│   └── completed/              # Archived one-off scripts
│
├── .claude/                    # AI configuration
│   └── commands/
│       ├── clean-music.md      # Fully autonomous cleanup
│       ├── consolidate-discs.md
│       ├── validate-folders.md # Auto-fix folder names
│       ├── consolidate-all.md  # Consolidate all multi-disc
│       └── move-track.md       # Move tracks between albums
│
├── outputs/                    # Generated reports
├── state/                      # Session state and checkpoints
├── logs/                       # Processing logs
└── issues/                     # Issue documentation
```

---

## Unified CLI (v3.0)

The project now includes a unified CLI entry point for all operations.

### Quick Start

```bash
# Scan and extract metadata
python cli.py scan "/path/to/music/Artist Name"

# Validate folder names against metadata (auto-fixes)
python cli.py validate "/path/to/music/Artist Name"

# Consolidate multi-disc albums
python cli.py consolidate "/path/to/music/Artist Name"

# Move a track to another album
python cli.py move-track "path/to/track.mp3" "path/to/dest/album" --album "Album Name" --artist "Artist"

# Embed cover art
python cli.py embed-cover "path/to/album" "https://example.com/cover.jpg"

# Check processing status
python cli.py status

# Resume interrupted session
python cli.py resume
```

### CLI Commands Reference

| Command | Description | Options |
|---------|-------------|---------|
| `scan <path>` | Extract metadata from albums | `--artist`, `--dry-run` |
| `validate <path>` | Validate and fix folder names | `--scan-only`, `--dry-run` |
| `consolidate <path>` | Find and consolidate multi-disc albums | `--scan-only`, `--dry-run` |
| `move-track <src> <dest>` | Move track with metadata update | `--album`, `--artist`, `--number` |
| `embed-cover <path> <url>` | Embed cover art | |
| `status` | Show processing status | |
| `resume` | Resume interrupted session | |

---

## Claude Commands (Fully Autonomous)

The following Claude commands run **without permission prompts**:

### /clean-music
Complete cleanup workflow for a music folder.

```bash
/clean-music /path/to/music/Various Artists
```

**Autonomous actions:**
1. Run metadata system
2. Auto-fix folder names (truncated, character substitutions)
3. Auto-consolidate multi-disc albums
4. Auto-fetch and embed missing cover art
5. Generate summary report

### /validate-folders
Scan and auto-fix folder name mismatches.

```bash
/validate-folders /path/to/music/Artist Name
```

**Issue types detected:**
- Truncated names
- Character substitutions (`_` → ` -`)
- Windows-unsafe characters
- Multi-disc patterns (skipped, use /consolidate-all)

### /consolidate-all
Find and consolidate all multi-disc album sets.

```bash
/consolidate-all /path/to/music/Various Artists
```

**Patterns detected:** `[Disc N]`, `Disc N`, `CD N`, `- Disc N`

### /move-track
Move a track between albums with metadata update.

```bash
/move-track "path/to/track.mp3" "path/to/dest/album"
```

**Note:** This command asks for metadata updates (album, artist, track number).

---

## Orchestration System

The project includes a full orchestration system for automated music library cleanup.

### Alternative CLI (orchestrator module)

```bash
# Initialize project with library
python -m orchestrator.main init "/path/to/music"

# Check status
python -m orchestrator.main status

# Scan albums
python -m orchestrator.main scan --artist "Various Artists"

# Validate against MusicBrainz/iTunes
python -m orchestrator.main validate

# Review uncertain matches
python -m orchestrator.main review

# Apply fixes (with preview)
python -m orchestrator.main fix --dry-run
python -m orchestrator.main fix
```

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                           │
│         (Config, State, Queue, CLI)                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     ▼                     ▼                     ▼
┌───────────┐       ┌────────────┐       ┌───────────┐
│  SCANNER  │       │ VALIDATOR  │       │   FIXER   │
│           │       │            │       │           │
│ Metadata  │──────>│ MusicBrainz│──────>│ Rename    │
│ Extraction│       │ iTunes     │       │ Cover Art │
│ Issues    │       │ Confidence │       │ Metadata  │
└───────────┘       └────────────┘       └───────────┘
```

### Data Sources

| Source      | Purpose                       | Auth Required        |
|-------------|-------------------------------|----------------------|
| MusicBrainz | Primary metadata, release IDs | No (user-agent only) |
| iTunes      | Cover art, metadata fallback  | No (free API)        |
| AcoustID    | Audio fingerprinting          | Free API key         |
| Discogs     | Rare releases                 | Optional token       |

### Confidence Scoring

Albums are scored based on metadata comparison:
- **95%+**: Auto-approved (formatting differences only)
- **80-95%**: Needs manual review
- **<80%**: Rejected (likely wrong match)

### Configuration (music-config.yaml)

```yaml
library:
  root: "/path/to/music"
  backup_enabled: true

thresholds:
  auto_approve: 0.95
  review_required: 0.80

naming:
  replace_colon_with: " -"  # Windows-safe

fingerprinting:
  enabled: true
  provider: acoustid
```

---

## Directory Organization

### utilities/
Contains all Python scripts for metadata operations. All scripts are designed to be run from the project root directory using relative paths.

### outputs/
Stores generated data files from extraction and auditing:
- **JSON files** - Structured metadata organized by Artist → Album → Tracks
- **CSV files** - Flat data format for spreadsheet analysis and filtering

### issues/
Maintains human-readable issue reports and tracking:
- **Issue reports** - Markdown files documenting problems found during audits
- **Resolution tracking** - Before/after comparisons
- **Best practices** - Lessons learned from cleanup operations

**Naming convention:** `{artist}_library_issues.md`

### Documentation Files

**README.md** - Project overview and quick start guide
- Getting started instructions
- Basic usage examples
- Feature highlights
- Quick reference for common tasks

**CLAUDE.md** - Comprehensive technical documentation (this file)
- Detailed workflows and best practices
- Complete utility documentation
- Extension guidelines and technical details
- Case studies and lessons learned

## Core Utilities

### 1. extract_metadata.py
**Purpose:** Comprehensive metadata extraction and library auditing

**Features:**
- Extracts metadata from MP3, M4A, FLAC, and other audio formats
- Generates structured JSON output organized by Artist → Album → Tracks
- Creates CSV files for spreadsheet analysis
- Detects missing or inconsistent metadata
- Extracts and reports on embedded cover art
- Supports both full library scans and targeted album scans

**Usage:**
```bash
# Scan entire artist directory
python utilities/extract_metadata.py "/path/to/music/U2"

# Scan specific album (provide relative path from artist directory)
python utilities/extract_metadata.py "/path/to/music/U2" "Achtung Baby"
```

**Output:**
- `outputs/u2_library_audit.json` - Structured metadata
- `outputs/u2_library_audit.csv` - Flat data for analysis
- Console summary with album statistics

### 2. fix_metadata.py
**Purpose:** Fix individual metadata fields in single audio files

**Supported Actions:**
- `artist` - Update artist tag
- `title` - Update track title
- `genre` - Update genre classification

**Features:**
- Shows BEFORE/AFTER verification
- Supports MP3 files with ID3 tags
- Safe single-file operations

**Usage:**
```bash
# Fix artist
python utilities/fix_metadata.py artist "path/to/track.mp3" "U2"

# Fix title
python utilities/fix_metadata.py title "path/to/track.mp3" "Beautiful Day"

# Fix genre
python utilities/fix_metadata.py genre "path/to/track.mp3" "Rock"
```

### 3. batch_fix_metadata.py
**Purpose:** Bulk metadata operations on entire albums/directories

**Features:**
- Process all MP3 files in a directory
- Per-file error handling
- Progress tracking with success/failure counts
- Built-in verification after changes
- Summary reports

**Usage:**
```bash
# Change genre for entire album
python utilities/batch_fix_metadata.py "/path/to/music/U2/U218 Singles" "Rock"
```

**Output:**
- Real-time progress updates
- Error reporting for failed files
- Verification confirmation

### 4. embed_cover.py
**Purpose:** Download and embed album artwork into audio files

**Features:**
- Download cover art from URLs
- Embed into MP3 (APIC frames) and M4A (covr atoms)
- Process entire albums at once
- Automatic format detection (JPEG/PNG)
- Support for local image files or URLs

**Usage:**
```bash
# Embed from URL
python utilities/embed_cover.py "/path/to/music/U2/Achtung Baby" "https://example.com/cover.jpg"

# Embed from local file
python utilities/embed_cover.py "/path/to/music/U2/Achtung Baby" "/path/to/cover.jpg"
```

### 5. folder_validator.py (NEW)
**Purpose:** Auto-detect and fix folder name mismatches against track metadata

**Features:**
- Scans all album folders and compares to embedded metadata
- Categorizes issues: truncated, substitution, multi-disc, mismatch
- Auto-applies Windows-safe transformations
- Skips multi-disc albums (handled by disc_consolidator.py)

**Issue Types:**
| Type | Detection | Auto-Fix |
|------|-----------|----------|
| Truncated | Folder shorter than metadata | Use full metadata name |
| Substitution | `_` where metadata has `:` | Replace `_` with ` -` |
| Multi-disc | Contains `[Disc N]` pattern | Skip (use consolidator) |
| Mismatch | General name difference | Apply Windows-safe transform |

**Usage:**
```bash
# Scan only (preview issues)
python utilities/folder_validator.py "/path/to/music/Artist" --scan-only

# Fix all issues
python utilities/folder_validator.py "/path/to/music/Artist"
```

### 6. disc_consolidator.py (NEW)
**Purpose:** Detect and consolidate multi-disc albums into single folders

**Features:**
- Pattern detection: `[Disc N]`, `Disc N`, `CD N`, `- Disc N`
- Adds disc prefix to filenames: `01 Track.mp3` → `1-01 Track.mp3`
- Updates metadata: sets `discnumber` field
- Removes empty source folders after consolidation

**Patterns Detected:**
| Pattern | Example |
|---------|---------|
| Bracket | `Album [Disc 1]`, `Album [Disc 2]` |
| Bracket CD | `Album [CD 1]`, `Album [CD 2]` |
| Suffix | `Album Disc 1`, `Album Disc 2` |
| Suffix CD | `Album CD1`, `Album CD2` |
| Dash | `Album - Disc 1`, `Album - Disc 2` |

**Usage:**
```bash
# Scan only (detect multi-disc sets)
python utilities/disc_consolidator.py "/path/to/music/Artist" --scan-only

# Consolidate all detected sets
python utilities/disc_consolidator.py "/path/to/music/Artist"

# Dry-run (preview changes)
python utilities/disc_consolidator.py "/path/to/music/Artist" --dry-run
```

### 7. track_mover.py (NEW)
**Purpose:** Move tracks between albums with metadata updates

**Features:**
- Moves track file to destination folder
- Updates metadata: album, albumartist, artist, tracknumber
- Optionally renames file based on track number
- Cleans up empty source folders

**Usage:**
```bash
python utilities/track_mover.py "source/track.mp3" "dest/folder" \
    --album "New Album" \
    --artist "Artist Name" \
    --number "5/12"
```

---

## YAML Configuration System

Batch operations can be defined in YAML config files for repeatability.

### Config Templates

Templates are located in `configs/templates/`. Copy to `configs/active/` and customize.

**batch_rename.yaml** - Batch folder renaming:
```yaml
base_path: "/path/to/music/Various Artists"
renames:
  - from: "Old Folder Name"
    to: "New Folder Name"
  - from: "Another Old Name"
    to: "Another New Name"
```

**consolidation.yaml** - Multi-disc consolidation:
```yaml
base_path: "/path/to/music/Various Artists"
consolidations:
  - source_folders:
      - "Album Name [Disc 1]"
      - "Album Name [Disc 2]"
    target: "Album Name"
    metadata:
      album: "Album Name"
      albumartist: "Various Artists"
```

**move_tracks.yaml** - Track movement:
```yaml
moves:
  - source: "//path/to/track.mp3"
    dest_folder: "//path/to/dest/album"
    metadata:
      album: "Destination Album"
      albumartist: "Artist Name"
      tracknumber: "5/12"
```

---

## Workflow: Complete Library Audit

### Phase 1: Initial Audit
1. **Extract metadata** from the entire library
   ```bash
   python utilities/extract_metadata.py "/path/to/music/Artist Name"
   ```

2. **Review outputs** in `outputs/` directory
   - Open CSV in spreadsheet software for analysis
   - Review JSON for programmatic processing
   - Check console output for immediate issues

3. **Create issues report** in `issues/` directory
   - Document missing cover art
   - Note incorrect metadata
   - Identify incomplete albums
   - Flag bootlegs/unofficial releases
   - Save as `{artist}_library_issues.md`

### Phase 2: Systematic Cleanup

**Priority Order:**
1. **Metadata fixes** (non-destructive)
   - Title typos
   - Genre standardization
   - Artist corrections

2. **Cover art** (adds data but safe)
   - Find high-quality album artwork
   - Embed using `embed_cover.py`

3. **File operations** (potentially risky - do last)
   - Rename files to remove watermarks
   - Delete duplicates
   - Reorganize folders

### Phase 3: Verification
1. **Re-run extraction** to verify all changes
   ```bash
   python utilities/extract_metadata.py "/path/to/music/Artist Name"
   ```

2. **Compare outputs** before/after
   - Check that all issues are resolved
   - Verify no new issues introduced

3. **Spot-check files** in media player
   - Confirm cover art displays
   - Verify metadata accuracy
   - Test gapless playback for live albums

## Multi-Disc Album Consolidation

### Purpose
Merge multi-disc compilation albums into single folders while preserving disc information in metadata.

### Workflow

1. **Identify Multi-Disc Sets**
   ```bash
   python utilities/consolidate_multidisc.py --scan "/path/to/music/Artist"
   ```

2. **Review Detection Report**
   - Check `outputs/multidisc_analysis.json` for complete and orphaned sets
   - Verify disc numbering is correct
   - Confirm album names match
   - **Note:** Volume-based series (e.g., "Now That's What I Call Music! Vol. 8, 11, 23") may be incorrectly detected as multi-disc sets. Review carefully before consolidating.

3. **Test Consolidation (Recommended)**
   ```bash
   # Dry-run first to preview changes
   python utilities/consolidate_multidisc.py --consolidate "Album Name" --path "/path/to/music/Artist" --dry-run

   # Then run actual consolidation
   python utilities/consolidate_multidisc.py --consolidate "Album Name" --path "/path/to/music/Artist"
   ```

4. **Verify Results**
   - Check that consolidated folder contains all tracks
   - Verify disc metadata is set correctly (discnumber field)
   - Test playback in music player
   - Original folders are preserved for verification

5. **Handle Orphaned Discs**
   - Rename with [Disc N] notation to indicate incomplete set
   - Document as incomplete in issues report
   - Keep in library until matching discs found

### Disc Metadata Strategy

- **Disc Number Field:** Store in `discnumber` tag (MP3: TPOS frame, M4A: disk tag)
  - Format: "1/2", "2/2", "3/3", etc.
- **Track Numbers:** Restart at 1 for each disc (Disc 1: 01-15, Disc 2: 01-16)
- **Folder Structure:** Flat - all tracks in single folder, no disc subfolders
- **File Naming:** No disc notation in filenames, disc info in metadata only

### Music Player Compatibility

Most music players support the `discnumber` field and can:
- Display disc info in track listings
- Group tracks by disc
- Sort tracks correctly across discs
- Show "Disc 1 of 2" in now-playing views

**Supported Players:** iTunes, Plex, Jellyfin, foobar2000, MusicBee, VLC

### Common Patterns Detected

**True Multi-Disc Albums:**
- "Album Name Disc 1" + "Album Name Disc 2" (sequential)
- "Album Name CD1" + "Album Name CD2"
- "Album Name [Disc 1]" + "Album Name [Disc 2]"

**Compilation Series (NOT multi-disc):**
- "Series Vol. 1", "Series Vol. 7" (non-sequential volumes)
- "Now That's What I Call Music! 8, 11, 23" (separate albums in series)
- Review carefully before consolidating

## Album and Filename Cleanup

### Purpose
Clean up album and file names by removing extra characters, fixing truncation, and standardizing separators.

### Naming Conventions

**Underscores:**
- Subtitles: `Album_ Subtitle` → `Album: Subtitle`
- Attribution: `Artist_ Album` → `Artist - Album`
- Metadata: `Album_Year` → `Album (Year)`

**Brackets vs Parentheses:**
- Genres/Countries: `[Rock]`, `[UK]` → `(Rock)`, `(UK)` or remove
- Disc Numbers: Keep `[Disc N]` to distinguish from other descriptors
- Editions: `[Deluxe]` → `(Deluxe)`

**Separators:**
- Subtitles: Use colon → `Album: Subtitle`
- Attribution: Use hyphen → `Artist - Album`
- Lists: Use comma → `Vol. 1, Vol. 2`
- Metadata: Use parentheses → `Album (Year)`

### Workflow

1. **Scan for Issues**
   ```bash
   python utilities/cleanup_names.py --scan "/path/to/music/Artist"
   ```

2. **Review Proposed Changes**
   - Check `outputs/name_cleanup_report.json`
   - Review albums needing cleanup
   - Identify truncated names that need research
   - Verify transformations are correct

3. **Test on Single Album**
   ```bash
   # Dry-run first
   python utilities/cleanup_names.py --clean "Album Name" --path "/path/to/music/Artist" --dry-run

   # Apply changes
   python utilities/cleanup_names.py --clean "Album Name" --path "/path/to/music/Artist"
   ```

4. **Apply Batch Changes**
   ```bash
   # Dry-run batch (preview all changes)
   python utilities/cleanup_names.py --batch "/path/to/music/Artist" --dry-run

   # Apply batch changes
   python utilities/cleanup_names.py --batch "/path/to/music/Artist"
   ```

### Truncation Detection

The script automatically detects albums with truncated names:
- Names ending with incomplete words (e.g., "Wo" instead of "World")
- Names ending with trailing underscores
- Names ending with suspiciously short words

**Example:**
- Truncated: `Beginner's Guide to World Music_ 2006 Wo`
- After cleanup: `Beginner's Guide to World Music: 2006 Wo` (still truncated)
- Manual research needed to find full name

### Example Transformations

```
Before: Absolute Dance_ Now & Then
After:  Absolute Dance: Now & Then

Before: Chillout 2000, Vol. 3_ Early Dawn Disc 3
After:  Chillout 2000, Vol. 3: Early Dawn [Disc 3]

Before: Best of the Rat Pack [Castle]
After:  Best of the Rat Pack (Castle)

Before: Asia Lounge_ Asian Flavoured Club Tunes
After:  Asia Lounge: Asian Flavoured Club Tunes
```

## Best Practices

### Metadata Management

1. **Use Album Artist vs Artist appropriately**
   - Album Artist: Main act (e.g., "U2")
   - Artist: Performer on specific track (e.g., "Jimi Hendrix" for guest performances)
   - Benefits: Keeps albums together while crediting collaborators

2. **Genre standardization**
   - Pick consistent genres: Rock, Pop, Live, House, etc.
   - Avoid "Other" - choose the most specific applicable genre
   - Live recordings should have Genre: "Live"

3. **Preserve iTunes metadata**
   - iTunNORM (Sound Check) - Volume normalization
   - iTunSMPB (Gapless playback) - Critical for live albums
   - COMM tags in MP3s - Technical encoding data
   - Recommendation: **Keep these tags** unless you have specific reasons to remove

4. **Cover art guidelines**
   - Minimum resolution: 500x500 pixels
   - Recommended: 1000x1000 or higher
   - Format: JPEG for smaller files, PNG for quality
   - Embed in files (don't rely on folder.jpg)

### File Operations Safety

1. **Always verify before deleting**
   - Check track lengths to identify duplicates
   - Verify against official sources (MusicBrainz, Discogs, iTunes)

2. **Order of operations**
   - Fix metadata first (reversible)
   - Add cover art next (adds data only)
   - Rename/delete files last (potentially destructive)

3. **Backup critical changes**
   - Before mass operations, backup the directory
   - Keep CSV/JSON snapshots before major changes

### Issue Tracking and Documentation

**Issue Report Structure:**
1. **Summary table** - Quick overview of problem types and counts
2. **Detailed issues** - Each issue with file paths and recommendations
3. **Album status** - Complete inventory with metadata completeness
4. **Recommended actions** - Prioritized by impact (High/Medium/Low)
5. **Sources** - Links to reference materials used

**Best Practices:**
- Create issue reports BEFORE making changes (baseline documentation)
- Update reports after fixes (track progress)
- Keep reports in `issues/` folder with consistent naming
- Use markdown for readability and version control
- Include file paths, current state, and target state

**Example workflow:**
```bash
# 1. Initial audit
python utilities/extract_metadata.py "/path/to/music/Artist"

# 2. Create issues report
# Review outputs/ and manually create issues/artist_library_issues.md

# 3. Fix issues systematically
# Work through High → Medium → Low priority items

# 4. Update issue report with resolutions
# Mark completed items, document changes made

# 5. Re-audit and verify
python utilities/extract_metadata.py "/path/to/music/Artist"
```

### Dealing with Bootlegs/Unofficial Releases

**Identification markers:**
- Incomplete metadata (missing dates, genres)
- Low-quality cover art
- Inconsistent track naming
- Non-standard album titles

**Recommendations:**
1. Research on u2songs.com, Discogs, or MusicBrainz
2. Categorize clearly (use Genre: "Live" for bootlegs)
3. Fix metadata to match actual content
4. Consider whether to keep or remove based on collection goals

---

## Lessons Learned from Cleanup Sessions

These insights were discovered during hands-on cleanup of 273 albums (4,762 tracks) in the Various Artists folder.

### The Discovery Workflow

When cleaning up a music library, we followed this repeatable workflow:

```
1. SCAN      → Run scan_folders.py to detect mismatched folders
2. CATEGORIZE → Group issues by type (truncated, substitution, multi-disc, etc.)
3. RESEARCH  → Use MusicBrainz/Discogs/iTunes to find correct album names
4. FIX       → Apply fixes (rename folders, consolidate discs, update metadata)
5. VERIFY    → Re-scan to confirm all issues resolved
```

### Issue Categories Discovered

From 64 folder mismatches, we identified 4 distinct categories:

| Category | Count | Pattern | Example |
|----------|-------|---------|---------|
| Truncated Names | 19 | Folder ends mid-word | `Putumayo Presents - Music from the Tea La` |
| Character Substitutions | 11 | `_` instead of `:` or ` -` | `Shine_ The Complete Classics` |
| Multi-Disc Albums | 8 | Same base name + disc indicator | `Album [Disc 1]`, `Album [Disc 2]` |
| Missing Info | ~26 | Needs web research | Both folder and metadata incomplete |

### Windows-Safe Transformations

Characters that cause issues on Windows file systems:

| Character | Replacement | Example |
|-----------|-------------|---------|
| `:` | ` -` | `Album: Subtitle` → `Album - Subtitle` |
| `_` (as separator) | ` -` | `Album_ Subtitle` → `Album - Subtitle` |
| `?` | Remove | `What?` → `What` |
| `*` | Remove | `Star*` → `Star` |
| `"` | Remove | `"Album"` → `Album` |
| `<>` | Remove | `Album<1>` → `Album 1` |
| `\|` | ` -` | `A\|B` → `A - B` |
| Accents | ASCII equivalent | `Café` → `Cafe` |

### Multi-Disc Consolidation Pattern

The repeatable 4-step pattern for consolidating multi-disc albums:

```python
# Step 1: Add disc prefix to filenames
# 01 Track.mp3 → 1-01 Track.mp3 (Disc 1)
# 01 Track.mp3 → 2-01 Track.mp3 (Disc 2)

# Step 2: Move all tracks to target folder
# Move files from [Disc 1] and [Disc 2] to base folder

# Step 3: Update metadata
audio['album'] = "Album Name"  # Remove disc indicator
audio['discnumber'] = "1/2"    # Set disc number (format: N/total)

# Step 4: Clean up
# Remove empty source folders
# Keep folder.jpg in target (don't duplicate)
```

### Research Sources Priority

When metadata is incomplete or truncated, use these sources in order:

1. **MusicBrainz** - Most authoritative for album names and track listings
2. **Discogs** - Good for compilations and rare releases
3. **iTunes Search API** - Good for cover art (free, no auth required)
4. **AllMusic** - Album credits and reviews

### Cover Art Sources

For embedding missing cover art, the iTunes API is preferred (high quality, free):

```python
# iTunes Search API
url = f"https://itunes.apple.com/search?term={album}&media=music&entity=album"
# In the response, replace "100x100" with "1200x1200" in artworkUrl100 field
# This gives high-resolution cover art

# Alternatives:
# - MusicBrainz Cover Art Archive (free)
# - Discogs API (requires token)
```

### Automation Insights

What we learned about automation vs. manual work:

| Task | Automatable? | How |
|------|--------------|-----|
| Detect truncated names | Yes | Compare folder length vs metadata length |
| Fix truncated names | Partially | Use metadata if complete, else needs research |
| Detect character substitutions | Yes | Pattern matching (`_` where metadata has `:`) |
| Fix character substitutions | Yes | Apply transformation rules |
| Detect multi-disc sets | Yes | Regex patterns: `[Disc N]`, `CD N`, etc. |
| Consolidate multi-disc | Yes | Add prefix, move, update metadata |
| Find correct album name | Sometimes | Web lookup, but may need human verification |
| Embed cover art | Yes | iTunes API → download → embed |

### Key Takeaways

1. **Pattern Recognition**: Most issues fall into predictable categories that can be automated
2. **Metadata is Gold**: When folder names are truncated, track metadata often has the complete album name
3. **Research First**: For ambiguous cases, spend time researching before making changes
4. **Verify After**: Always re-scan after batch operations to catch any issues
5. **Document Changes**: Keep a record of what was fixed for future reference

### Cover Art Verification (Lessons from Ben Harper Cleanup)

**Problem Discovered:** Embedded cover art may be technically valid (good size,
full coverage) but visually WRONG for the album.

**Case Study - Ben Harper (2026-01-13):**

| Album | Issue | Resolution |
|-------|-------|------------|
| Diamonds On The Inside | Wrong cover embedded (262KB, 100% coverage) | Re-embedded from iTunes |
| Fight For Your Mind | Wrong cover embedded (357KB, 100% coverage) | Re-embedded from iTunes |
| Welcome to the Cruel World | Correct | N/A |
| Both Sides of the Gun | Correct | N/A |

**Root Cause:** System accepted embedded art as "valid" because size/coverage
checked out, without verifying the art actually matched the album.

**Verification Workflow:**
1. When processing cover art, save a preview to `outputs/cover_preview.jpg`
2. Claude visually inspects the image during `/clean-music`
3. Compares visible text/imagery against album metadata
4. Flags mismatches for manual review

**On-Demand Verification:**
```bash
# Verify all folder.jpg files in a path
/verify-covers /path/to/music/Artist Name
```

**Manual Fix Commands:**
```bash
# Check what's currently embedded (syncs to folder.jpg)
python utilities/embed_cover.py "path/to/album" --sync-folder

# Search iTunes for correct cover
python -c "import requests; r=requests.get('https://itunes.apple.com/search?term=Artist+Album&entity=album'); print([a['artworkUrl100'].replace('100x100','1200x1200') for a in r.json()['results'][:3]])"

# Force replace with correct cover
python utilities/embed_cover.py "path/to/album" "https://correct_cover_url" --force
```

**Key Takeaway:** Size and coverage validation is necessary but not sufficient.
Visual verification catches cases where wrong art was previously embedded.

---

## Common Issues and Solutions

### Issue: Missing Cover Art
**Solution:**
1. Search iTunes Store, Amazon Music, or Discogs
2. Download high-quality artwork
3. Use `embed_cover.py` to embed in all tracks
```bash
python utilities/embed_cover.py "album/path" "cover_url_or_path"
```

### Issue: Inconsistent Genre Tags
**Solution:**
Use `batch_fix_metadata.py` for entire albums:
```bash
python utilities/batch_fix_metadata.py "album/path" "Rock"
```

### Issue: Title Typos
**Solution:**
Single-file fixes with `fix_metadata.py`:
```bash
python utilities/fix_metadata.py title "track/path" "Correct Title"
```

### Issue: Filename Watermarks (e.g., "track - music-madness.mp3")
**Solution:**
Python rename operation:
```bash
python -c "import os; os.rename('old_name.mp3', 'new_name.mp3')"
```

### Issue: Split Artist Entries (e.g., "U2 & Kygo" separate from "U2")
**Analysis Required:**
- Official collaborations: Keep split (correct metadata)
- Should be same artist: Fix Album Artist field to group properly

### Issue: Incomplete Albums
**Steps:**
1. Research complete tracklist on MusicBrainz
2. Determine if missing tracks are essential
3. Find missing tracks or accept incomplete album
4. Document in issues report

## Technical Details

### Supported Audio Formats
- **MP3** - ID3v1, ID3v2 tags (via mutagen)
- **M4A/MP4** - iTunes-style atoms (via mutagen)
- **FLAC** - Vorbis comments (via mutagen)

### Metadata Fields Extracted
- Artist (Album Artist and Track Artist)
- Album
- Title
- Track Number
- Date/Year
- Genre
- Cover Art (embedded)
- Comments (COMM tags, iTunes metadata)

### Library Dependencies
```python
mutagen          # Audio metadata manipulation
requests         # HTTP downloads for cover art
```

### File Encoding
- UTF-8 for all text operations
- Handles unicode characters in filenames and metadata
- Cross-platform path handling (Windows/Linux)

---

## Standalone Python Usage (Without Claude)

This project uses a **hybrid architecture** where the core functionality is 100% standalone Python. Claude Code provides optional AI enhancements but is not required.

### No Claude SDK Dependencies

The project has **zero imports** of the Anthropic SDK. All Python code works independently:

```bash
# Verify - no anthropic imports
grep -r "import anthropic" .  # Returns nothing
grep -r "from anthropic" .    # Returns nothing
```

### Required Dependencies

```bash
pip install mutagen requests pyyaml
```

| Package | Purpose | Required |
|---------|---------|----------|
| `mutagen` | Audio metadata manipulation | Yes |
| `requests` | HTTP downloads (cover art) | Yes |
| `pyyaml` | Configuration files | Optional |

### Feature Matrix: Python vs Claude

| Feature | Standalone Python | With Claude Code |
|---------|-------------------|------------------|
| Scan metadata | `python cli.py scan` | Same |
| Fix folder names | `python cli.py validate` | `/validate-folders` |
| Consolidate multi-disc | `python cli.py consolidate` | `/consolidate-all` |
| Move tracks | `python cli.py move-track` | `/move-track` |
| Embed cover art | `python utilities/embed_cover.py` | Same |
| Batch genre fix | `python utilities/batch_fix_metadata.py` | Same |
| Generate reports | `python utilities/extract_metadata.py` | Same |
| **Visual cover verification** | Manual inspection | `/verify-covers` (AI vision) |
| **Autonomous workflow** | Run steps manually | `/clean-music` (orchestrated) |
| **Learning from corrections** | Not available | `.claude/knowledge/` |

### Complete Workflow (Python Only)

```bash
# 1. Scan and extract metadata
python cli.py scan "/path/to/music/Artist"

# 2. Validate and fix folder names
python cli.py validate "/path/to/music/Artist"

# 3. Consolidate multi-disc albums
python cli.py consolidate "/path/to/music/Artist"

# 4. Embed cover art (find URL from iTunes/MusicBrainz manually)
python utilities/embed_cover.py "path/to/album" "https://cover-url.jpg"

# 5. Generate report
python utilities/extract_metadata.py "/path/to/music/Artist"
```

### PowerShell Automation Script

```powershell
# cleanup-artist.ps1 - Standalone cleanup without Claude
param([string]$ArtistPath)

Write-Host "Scanning: $ArtistPath"
python cli.py scan $ArtistPath

Write-Host "Validating folder names..."
python cli.py validate $ArtistPath

Write-Host "Consolidating multi-disc albums..."
python cli.py consolidate $ArtistPath

Write-Host "Done! Check outputs/ for reports."
```

### What Claude Adds

When you use Claude Code, you gain:

1. **Visual Cover Verification** - Claude vision inspects `folder.jpg` to verify it matches the album
2. **Autonomous Orchestration** - `/clean-music` runs all steps without prompts
3. **Intelligent Decisions** - AI resolves conflicts between MusicBrainz/iTunes data
4. **Learning** - Corrections logged to `.claude/knowledge/` for future sessions

### Graceful Degradation

The knowledge base logging in `embed_cover.py` is optional:

```python
# From embed_cover.py - handles missing knowledge base gracefully
kb_path = get_knowledge_base_path()
if not os.path.exists(kb_path):
    print(f"  Knowledge base not found, skipping learning")
    return  # Continues without error
```

---

## Extending the System

### Adding New Metadata Fields

To extract additional fields, modify `extract_metadata.py`:

```python
# In extract_metadata() function, add:
result['new_field'] = audio.get('new_field', [None])[0]

# In build_structured_json(), add to track data:
'NewField': track_info.get('new_field')
```

### Creating New Utilities

**Template for new script:**
```python
import sys
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

def process_file(filepath):
    """Your processing logic"""
    audio = MP3(filepath, ID3=EasyID3)
    # Your code here
    audio.save()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <filepath>")
        sys.exit(1)

    filepath = sys.argv[1]
    process_file(filepath)
```

### Scaling to Full Library

When processing multiple artists:

1. **Directory structure:**
   ```
   /music
   ├── Artist 1/
   ├── Artist 2/
   └── Artist 3/
   ```

2. **Batch processing:**
   ```bash
   for artist in /music/*; do
       python utilities/extract_metadata.py "$artist"
   done
   ```

3. **Output organization:**
   - Name outputs by artist: `artist_name_audit.json`
   - Or create subdirectories: `outputs/Artist Name/`

## U2 Library Case Study

### Project Statistics
- **Total tracks processed:** 261
- **Albums:** 20 official + 3 live bootlegs + 2 collaboration tracks
- **Issues resolved:** 20+ (cover art, metadata, typos, genres)
- **Time investment:** ~3-4 hours for complete audit and cleanup
- **Documentation:** See `issues/u2_library_issues.md` for detailed audit report

### Key Learnings

1. **Bootleg identification** - Research is essential
2. **Artist split tags** - Critical for proper organization
3. **iTunes metadata preservation** - Important for playback quality
4. **Systematic approach** - Metadata → Cover art → Files (in that order)
5. **Verification loops** - Always re-audit after changes
6. **Issues tracking** - Maintain detailed markdown reports for future reference

### Before/After
- **Before:** 10 albums missing cover art, genre inconsistencies, typos, watermarks
- **After:** All 261 tracks with cover art, standardized metadata, clean filenames
- **Artifacts:** JSON/CSV exports in `outputs/`, detailed report in `issues/`

## Future Enhancements

### Planned Features
- [ ] Automated cover art lookup via MusicBrainz API
- [ ] Duplicate detection algorithm
- [ ] Automated genre classification
- [ ] Batch file renaming with templates
- [ ] Support for additional audio formats (OGG, WMA, etc.)
- [ ] Web interface for library management
- [ ] Integration with MusicBrainz Picard workflow

### Stretch Goals
- [ ] Automated audio quality analysis
- [ ] Lyrics embedding
- [ ] Playlist generation based on metadata
- [ ] Smart album completion suggestions

## Resources

### Metadata Research
- [MusicBrainz](https://musicbrainz.org/) - Comprehensive music database
- [Discogs](https://www.discogs.com/) - Detailed release information
- [iTunes Search API](https://itunes.apple.com/search) - Official Apple metadata
- [u2songs.com](https://www.u2songs.com/) - Artist-specific discography

### Tools and Libraries
- [Mutagen Documentation](https://mutagen.readthedocs.io/) - Python audio metadata
- [ID3 Specification](https://id3.org/) - MP3 tag standards
- [MP4 Atom Reference](https://developer.apple.com/library/archive/documentation/QuickTime/QTFF/Metadata/Metadata.html)

### Community
- [Hydrogenaudio Forums](https://hydrogenaud.io/) - Audio metadata discussions
- [MusicBrainz Forums](https://community.metabrainz.org/) - Metadata best practices

## Changelog

### 2026-01-13 (v4.0 - Major Refactoring)
- **Unified CLI**: Created `cli.py` as single entry point for all operations
- **New Utilities**:
  - `folder_validator.py` - Auto-detect and fix folder name mismatches
  - `disc_consolidator.py` - Detect and consolidate multi-disc albums
  - `track_mover.py` - Move tracks between albums with metadata updates
- **Claude Commands**:
  - Updated `/clean-music` to be fully autonomous (no permission prompts)
  - Added `/validate-folders` command
  - Added `/consolidate-all` command
  - Added `/move-track` command
- **YAML Config System**: Added templates for batch operations in `configs/templates/`
- **Project Cleanup**:
  - Archived 11 one-off scripts to `scripts/completed/`
  - Deleted 143+ temp files (tmpclaude-*.cwd)
  - Moved `music_metadata_system.py` to `orchestrator/`
  - Moved `scan_folders.py` to `utilities/`
  - Reduced root directory from 28+ files to ~7 essential files
- **Documentation**: Updated README.md and CLAUDE.md with new structure

### 2025-12-16 (v3)
- Created comprehensive README.md for project overview
- Added Documentation Files section to CLAUDE.md
- Distinguished README.md (quick start) vs CLAUDE.md (technical details)

### 2025-12-16 (v2)
- Added issues/ folder for issue tracking and reports
- Reorganized project structure (utilities/, outputs/, issues/)
- Updated CLAUDE.md with directory organization section
- Enhanced workflow documentation with issues tracking

### 2025-12-16 (v1)
- Refactored project structure (utilities/ and outputs/ folders)
- Updated CLAUDE.md with comprehensive documentation
- Completed U2 library audit (261 tracks)
- Added batch metadata operations
- Extended genre support in fix_metadata.py

### Initial Development
- Created extract_metadata.py for library auditing
- Developed fix_metadata.py for single-file fixes
- Built embed_cover.py for artwork management
- Established CSV/JSON output formats

---

## AI Enhancement Roadmap

### Current State Assessment

**AI Effectiveness: ~60-70%**

The project has solid AI infrastructure but currently uses Claude primarily as a "smart script executor" rather than a true AI collaborator that learns and improves over time.

### Identified Gaps

#### 1. Claude Agents Underutilized
The `.claude/agents/` folder contains 5 detailed agent definitions (metadata_validator, conflict_resolver, etc.), and `orchestrator/claude_agents.py` has infrastructure to invoke them. However, the main workflows don't actively call Claude for decisions—the agents function more as documentation than active components.

#### 2. No Learning/Feedback Loop
- The Ben Harper cover art issue (wrong covers embedded for unknown duration) highlighted this gap
- No mechanism to remember corrections across sessions
- No pattern detection for similar issues
- Each session starts fresh with no memory of past work

#### 3. Reactive vs. Proactive
- User must manually invoke commands
- No background monitoring or suggestions
- No prioritization of issues by severity
- No "I noticed these albums might have issues" capability

#### 4. Sequential Processing
- Albums processed one at a time
- No intelligent batching of similar operations
- No parallelization of independent tasks

### Planned Improvements

#### Phase 1: Knowledge Base (In Progress)
Create `.claude/knowledge/` folder to persist learnings:
```
.claude/knowledge/
├── corrections.json       # Previously applied corrections
├── cover_art_mapping.json # Known correct cover URLs by album
└── patterns.json          # Learned problematic patterns
```

#### Phase 2: Cover Art Learning
When cover art is manually corrected:
1. Log the correction (album → correct cover URL)
2. On future scans, check if album matches a known correction
3. Proactively suggest applying known fixes

#### Phase 3: Proactive Suggestions
New `/suggest-fixes` command:
- Scan library for potential issues
- Cross-reference against knowledge base
- Prioritize by severity and confidence
- Generate actionable recommendations

#### Phase 4: Active Agent Integration
Modify workflows to consult Claude agents:
- Before auto-applying fixes, consult conflict_resolver
- Use metadata_validator to score albums
- Have report_generator create summaries

### How to Contribute

**Adding to the Knowledge Base:**
```bash
# After fixing an album's cover art, it should be logged automatically
# Manual addition:
# Edit .claude/knowledge/cover_art_mapping.json
{
  "Ben Harper/Diamonds On The Inside": {
    "correct_url": "https://...",
    "fixed_date": "2026-01-13",
    "previous_hash": "ae24ce5ef81c..."
  }
}
```

**Reporting Patterns:**
When you notice a recurring issue type, document it in `.claude/knowledge/patterns.json` so Claude can detect similar cases automatically.

---

## Quick Reference Commands

### Unified CLI (Recommended)
```bash
# Scan and extract metadata
python cli.py scan "/path/to/music/Artist"

# Validate and fix folder names
python cli.py validate "/path/to/music/Artist"

# Consolidate multi-disc albums
python cli.py consolidate "/path/to/music/Artist"

# Move track between albums
python cli.py move-track "source.mp3" "dest/folder" --album "Album" --artist "Artist"

# Embed cover art
python cli.py embed-cover "album/path" "image_url_or_path"
```

### Claude Commands (Fully Autonomous)
```bash
# Complete cleanup workflow
/clean-music /path/to/music/Various Artists

# Validate and fix folder names
/validate-folders /path/to/music/Artist

# Consolidate all multi-disc albums
/consolidate-all /path/to/music/Artist

# Move track (interactive)
/move-track "source.mp3" "dest/folder"
```

### Legacy Utilities
```bash
# Full library audit
python utilities/extract_metadata.py "/path/to/music/Artist"

# Fix single track metadata
python utilities/fix_metadata.py [artist|title|genre] "path/to/track.mp3" "new_value"

# Batch genre update
python utilities/batch_fix_metadata.py "album/path" "Rock"

# Embed cover art
python utilities/embed_cover.py "album/path" "image_url_or_path"

# Multi-disc consolidation (alternative)
python utilities/consolidate_multidisc.py --scan "/path/to/music/Artist"

# Rename file (remove watermark)
python -c "import os; os.rename('old.mp3', 'new.mp3')"
```

---

**Last Updated:** 2026-01-13
**Project Status:** Active Development (v4.0)
**Current Focus:** Various Artists folder organization and cleanup (273 albums, 4,762 tracks)
**Completed:** U2 library (261 tracks), Various Artists folder reorganization (Holiday/Soundtracks), Project refactoring
**Next Target:** Full music library expansion
