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
│   ├── README.md               # Config folder documentation
│   ├── templates/              # Config templates (copy to active/)
│   │   ├── credentials.yaml.example  # API credentials template
│   │   ├── batch_rename.yaml   # Batch folder renaming
│   │   ├── consolidation.yaml  # Multi-disc consolidation
│   │   └── move_tracks.yaml    # Track movement config
│   └── active/                 # User's active configs (gitignored)
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

### Cover Art Validation (core)

All cover and image handling now routes through a single validated module:
`utilities/core/cover_art.py`. Every embed, download, and folder-sync path
goes through it, so the same checks apply everywhere:

- Rejects empty or corrupt image bytes before they can be written.
- Uses Pillow plus `ffprobe` as ground truth for real pixel dimensions
  (not just file size or coverage).
- Performs a post-write `dims > 0` check to confirm the embedded art is valid.

This fixed the `width=0` / `height=0` artwork that Jellyfin reported on
previously "valid-looking" files. Background and rationale:
> See project memory: `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\cover-art-validation.md`
> and `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\jellyfin-ffprobe-truth.md` (indexed in MEMORY.md).

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

> Moved to project memory: see `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\multidisc-consolidation.md` (indexed in MEMORY.md).

## Album and Filename Cleanup

> Moved to project memory: see `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\naming-conventions.md` (indexed in MEMORY.md).

## Best Practices

> Moved to project memory: see `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\best-practices.md` (indexed in MEMORY.md).

## Lessons Learned from Cleanup Sessions

> Moved to project memory: see `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\lessons-learned.md` (indexed in MEMORY.md).

## Common Issues and Solutions

> Moved to project memory: see `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\troubleshooting.md` (indexed in MEMORY.md).

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

> Moved to project memory: see the extension and scaling notes under `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\` (indexed in MEMORY.md).

## U2 Library Case Study

> Moved to project memory: see `C:\Users\Admin\.claude\projects\D--music-cleanup\memory\u2-case-study.md` (indexed in MEMORY.md).

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

### 2026-06-27 (Docs slim + cover-art core)
- **Slimmed CLAUDE.md**: Moved large reference sections (Lessons Learned, U2
  Case Study, Best Practices, Multi-Disc background, Naming Conventions, Common
  Issues, Extending) into project memory; left pointers indexed in MEMORY.md.
- **Cover Art Validation (core)**: Documented that all cover/image logic now
  routes through `utilities/core/cover_art.py` (validated embeds, Pillow +
  ffprobe ground truth, post-write dims check) which fixed the width=0/height=0
  art Jellyfin reported.

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
The `.claude/agents/` folder contains 5 detailed agent definitions (metadata_validator, conflict_resolver, etc.), and `orchestrator/claude_agents.py` has infrastructure to invoke them. However, the main workflows don't actively call Claude for decisions; the agents function more as documentation than active components.

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

**Last Updated:** 2026-06-27
**Project Status:** Active Development (v4.0)
**Current Focus:** Various Artists folder organization and cleanup (273 albums, 4,762 tracks)
**Completed:** U2 library (261 tracks), Various Artists folder reorganization (Holiday/Soundtracks), Project refactoring
**Next Target:** Full music library expansion
