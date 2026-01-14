# Music Library Metadata Management System

A comprehensive Python-based toolset for auditing, cleaning, and maintaining music library metadata. Built and tested through the complete cleanup of a 261-track U2 collection and 273-album Various Artists folder (4,762 tracks).

## Quick Start

### Prerequisites
```bash
pip install mutagen requests
```

### Using the CLI

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
```

### Using Claude Commands (Fully Autonomous)

```bash
# Complete cleanup workflow - no prompts required
/clean-music /path/to/music/Various Artists

# Validate and fix folder names
/validate-folders /path/to/music/Artist Name

# Find and consolidate all multi-disc albums
/consolidate-all /path/to/music/Various Artists

# Move track between albums (interactive)
/move-track "path/to/track.mp3" "path/to/dest"
```

## Project Structure

```
D:\music cleanup\
├── cli.py                  # Unified CLI entry point
├── README.md               # This file
├── CLAUDE.md               # Detailed technical documentation
├── music-config.yaml       # Configuration
├── fpcalc.exe              # Audio fingerprinting (Chromaprint)
│
├── .claude/                # Claude Code AI configuration
│   ├── agents/             # AI agent role definitions
│   │   ├── metadata_validator.md
│   │   ├── metadata_enrichment.md
│   │   ├── conflict_resolver.md
│   │   ├── fingerprint_validator.md
│   │   └── report_generator.md
│   ├── commands/           # Slash command workflows
│   │   ├── clean-music.md
│   │   ├── validate-folders.md
│   │   ├── consolidate-all.md
│   │   ├── verify-covers.md
│   │   └── move-track.md
│   └── settings.local.json # Permissions & allowlist
│
├── orchestrator/           # Core orchestration engine
│   ├── main.py             # CLI commands
│   ├── music_metadata_system.py
│   ├── claude_agents.py    # Python ↔ Claude bridge
│   ├── config.py
│   ├── state.py
│   └── queue.py
│
├── agents/                 # Python processing agents
│   ├── base.py             # BaseAgent abstract class
│   ├── scanner.py          # ScannerAgent
│   ├── validator.py        # ValidatorAgent
│   └── fixer.py            # FixerAgent
│
├── sources/                # Data source adapters
│   ├── musicbrainz.py      # MusicBrainz API
│   ├── itunes.py           # iTunes Search API
│   ├── acoustid.py         # AcoustID fingerprinting
│   ├── spotify.py          # Spotify API
│   └── discogs.py          # Discogs API
│
├── utilities/              # Reusable CLI tools
│   ├── folder_validator.py     # Auto-fix folder names
│   ├── disc_consolidator.py    # Multi-disc consolidation
│   ├── track_mover.py          # Move tracks between albums
│   ├── embed_cover.py          # Cover art embedding
│   ├── fix_metadata.py
│   ├── batch_fix_metadata.py
│   └── scan_folders.py
│
├── configs/                # YAML configurations
│   ├── templates/          # Config templates
│   └── active/             # User's active configs
│
├── outputs/                # Generated reports (JSON/CSV)
├── state/                  # Session state & checkpoints
├── logs/                   # Processing logs
└── issues/                 # Issue documentation
```

## Key Features

### Autonomous Workflows
The `/clean-music` command runs **fully autonomously**:
1. Scans albums and extracts metadata
2. Auto-fixes folder names (truncated, character substitutions)
3. Consolidates multi-disc albums (adds disc prefixes, merges folders)
4. Fetches and embeds missing cover art
5. Reports all changes made

No permission prompts or confirmations required.

### Folder Validation
Automatically detects and fixes:
- **Truncated names**: `Album - Long Na...` → `Album - Long Name Complete`
- **Character substitutions**: `Album_ Subtitle` → `Album - Subtitle`
- **Windows-safe transforms**: Removes `: ? * " < > |`

### Multi-Disc Consolidation
Automatically handles:
- Pattern detection: `[Disc 1]`, `Disc 1`, `CD1`
- File renaming: `01 Track.mp3` → `1-01 Track.mp3`
- Metadata updates: Sets `discnumber` field
- Folder cleanup: Removes empty source folders

### YAML Batch Operations
Use config files for repeatable operations:
```yaml
# configs/active/my_renames.yaml
base_path: "/path/to/music/Various Artists"
renames:
  - from: "Old Folder Name"
    to: "New Folder Name"
```

## AI Integration & Automation

This project uses a **dual-agent architecture** combining Python processing agents with Claude AI for intelligent decision-making.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              ORCHESTRATOR (Python)                       │
│     Manages workflow, state, and agent coordination      │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐     ┌──────────┐     ┌─────────┐
   │ Scanner │     │Validator │     │  Fixer  │
   │  Agent  │     │  Agent   │     │  Agent  │
   │ (Python)│     │ (Python) │     │ (Python)│
   └─────────┘     └──────────┘     └─────────┘
        │               │                │
        └───────────────┼────────────────┘
                        ▼
   ┌─────────────────────────────────────────────────────┐
   │           Claude AI Decision Layer                   │
   │  - Metadata validation & conflict resolution         │
   │  - Visual cover art verification                     │
   │  - Confidence scoring & automation thresholds        │
   └─────────────────────────────────────────────────────┘
```

### Python Agents (`agents/` folder)

| Agent | Purpose |
|-------|---------|
| **ScannerAgent** | Scans folders, extracts metadata, detects issues |
| **ValidatorAgent** | Validates against MusicBrainz/iTunes, calculates confidence |
| **FixerAgent** | Applies corrections, embeds covers, renames folders |

See [`agents/README.md`](agents/README.md) for detailed documentation.

### Claude AI Agents (`.claude/agents/` folder)

| Agent | Purpose |
|-------|---------|
| **metadata_validator** | Validates metadata completeness and consistency |
| **metadata_enrichment** | Enriches from MusicBrainz, Spotify, iTunes |
| **conflict_resolver** | Resolves discrepancies between sources |
| **fingerprint_validator** | Validates audio fingerprints via AcoustID |
| **report_generator** | Generates JSON/CSV audit reports |

See [`.claude/README.md`](.claude/README.md) for detailed documentation.

### Automation Thresholds

The system uses confidence scoring to determine automation level:

| Confidence | Action | Description |
|------------|--------|-------------|
| **95%+** | Auto-approve | Formatting differences only |
| **85-94%** | Auto-apply | Apply with notification |
| **70-84%** | Manual review | Human verification required |
| **<70%** | Reject | Likely wrong match |

### How It Works

1. **Python agents** handle file operations (reading metadata, embedding covers, renaming)
2. **Claude agents** make intelligent decisions (which source to trust, what corrections to apply)
3. **Orchestrator** coordinates the workflow and maintains state
4. **Data sources** (MusicBrainz, iTunes, Discogs) provide reference metadata

## CLI Commands

| Command | Description |
|---------|-------------|
| `scan <path>` | Extract metadata from albums |
| `validate <path>` | Validate and fix folder names |
| `consolidate <path>` | Find and consolidate multi-disc albums |
| `move-track <src> <dest>` | Move track with metadata update |
| `embed-cover <path> <url>` | Embed cover art |
| `status` | Show processing status |
| `resume` | Resume interrupted session |

## Claude Commands

| Command | Description | Autonomous |
|---------|-------------|------------|
| `/clean-music <path>` | Complete cleanup workflow | Yes |
| `/validate-folders <path>` | Scan and fix folder names | Yes |
| `/consolidate-all <path>` | Consolidate all multi-disc sets | Yes |
| `/verify-covers <path>` | Visually verify cover art matches albums | Yes |
| `/check-in` | Security/code audit + git commit | Semi (asks for commit) |
| `/move-track <src> <dest>` | Move track between albums | No (asks for metadata) |
| `/consolidate-discs <path> <album>` | Consolidate specific multi-disc album | No (asks for confirmation) |

## Documentation

- **CLAUDE.md** - Comprehensive technical documentation
  - Detailed workflow guides
  - Best practices and common issues
  - YAML configuration reference
  - **Lessons Learned** - Insights from cleaning 273 albums:
    - Issue categories (truncated, substitutions, multi-disc)
    - Windows-safe transformations
    - Automation patterns
    - Research sources priority

- **issues/*.md** - Issue tracking reports

## Dependencies

```
mutagen    # Audio metadata manipulation
requests   # HTTP downloads for cover art
pyyaml     # Configuration files (optional)
```

## Running Without Claude Code

This project has a **hybrid architecture** - the core functionality is 100% standalone Python with **no Claude SDK dependencies**. Claude Code is an optional enhancement for AI-powered automation.

### What Works Standalone

| Feature | Python Command |
|---------|----------------|
| Scan metadata | `python cli.py scan "path"` |
| Fix folder names | `python cli.py validate "path"` |
| Consolidate multi-disc | `python cli.py consolidate "path"` |
| Move tracks | `python cli.py move-track "src" "dest" --album "Name"` |
| Embed cover art | `python utilities/embed_cover.py "path" "image.jpg"` |
| Extract reports | `python utilities/extract_metadata.py "path"` |
| Batch genre fix | `python utilities/batch_fix_metadata.py "path" "Rock"` |

### Claude-Only Features

These features require Claude Code:
- **Visual cover verification** (`/verify-covers`) - Uses Claude vision to verify cover art matches album
- **Autonomous orchestration** (`/clean-music`) - 6-step workflow with AI decision-making
- **Knowledge base learning** - Remembers corrections in `.claude/knowledge/`

### Quick Start (Standalone)

```bash
# Install dependencies
pip install mutagen requests

# Complete cleanup workflow using Python only
python cli.py scan "/path/to/music/Artist"
python cli.py validate "/path/to/music/Artist"
python cli.py consolidate "/path/to/music/Artist"

# Embed cover art
python utilities/embed_cover.py "path/to/album" "https://cover-url.jpg"
```

See [`docs/standalone-usage.md`](docs/standalone-usage.md) for a comprehensive standalone usage guide.

## Resources

- [MusicBrainz](https://musicbrainz.org/) - Music metadata database
- [Discogs](https://www.discogs.com/) - Release information
- [iTunes Search API](https://itunes.apple.com/search) - Apple metadata
- [Mutagen Documentation](https://mutagen.readthedocs.io/) - Python audio library

---

**Status:** Active Development
**Last Updated:** 2026-01-13
