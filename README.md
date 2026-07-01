# Music Library Metadata Management System

A comprehensive Python-based toolset for auditing, cleaning, and maintaining music library metadata. Tested end to end on a **15,000+ track / 1,600+ album** library (covers validated 100% against ffprobe - the same engine Jellyfin uses).

## Quickstart

One install line, then one command runs the whole pipeline. The default is a safe
preview - nothing is written until you add `--execute`.

```bash
pip install mutagen requests pillow static-ffmpeg pyyaml

python cli.py lifecycle "//192.168.1.252/music" --dry-run   # preview the full pipeline
python cli.py lifecycle "//192.168.1.252/music" --execute   # apply changes
```

Prefer AI judgment? Inside Claude Code, the equivalent one-liner is
`/clean-music "//192.168.1.252/music"` (or `/lifecycle "<library>"`).

New here? Read **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** - it walks a
zero-knowledge reader through both paths, the six phases, and the safety model.

## The Unified Lifecycle (recommended workflow)

The headline workflow is a single command that runs every phase in one fixed,
canonical order:

```
scan -> identify -> validate -> dedupe -> covers -> fix
```

| Phase | What it does |
|-------|--------------|
| **scan** | Read every album's tags, count tracks, flag missing covers / metadata issues. |
| **identify** | Fingerprint the audio of weak/unknown tracks (AcoustID) to find the real song; skipped silently with no API key. |
| **validate** | Cross-check albums against MusicBrainz / iTunes, score the match, route to auto-apply or review. |
| **dedupe** | Find within-album duplicate tracks, keep the best, move the rest to backup (never deletes). |
| **covers** | ffprobe-validate embedded art, repair broken/missing art, write `folder.jpg` where missing. |
| **fix** | Apply the approved metadata and cover corrections. |

**Safety model (every phase):** `--scan-only` reports only, `--dry-run` (the
**default**) previews the plan without writing, and `--execute` is the only mode
that writes to your music. Duplicates are **moved to an off-library backup, never
deleted**, and cover art is validated with `ffprobe` - the same engine Jellyfin
uses - both before and after writing.

```bash
python cli.py lifecycle "<library>" --scan-only             # report only
python cli.py lifecycle "<library>" --dry-run               # preview (default)
python cli.py lifecycle "<library>" --execute               # apply
python cli.py lifecycle "<library>" --execute --backup-dir "D:/music_backup/_duplicates"
python cli.py lifecycle "<library>" --execute --aggressive  # dedupe also groups remaster/version variants
python cli.py lifecycle "<library>" --execute --no-fingerprint
```

**Fresh queue + run history.** Each lifecycle run archives the previous work queue
to `state/history/queue-<timestamp>.json` and clears it, so runs never contaminate
each other. A dated summary of every run is appended to `state/run_history.json`.

**Two orchestrators, one behavior (parity).** The pipeline is defined once, in
`orchestrator/main.py` (the canonical phase order lives in the module-level
`LIFECYCLE_PHASES` constant). `python cli.py lifecycle` is a thin wrapper that
delegates to it, and `python -m orchestrator.main lifecycle` calls it directly -
both accept identical flags and produce identical results. Use whichever entry
point you prefer.

You can still run any single phase on its own (see [CLI Commands](#cli-commands));
the lifecycle just chains them in the correct order with shared safety flags.

### Prerequisites
```bash
pip install mutagen requests
```

### Optional: API Credentials
For audio fingerprinting and extended metadata lookup, set up API credentials:
```bash
cp configs/templates/credentials.yaml.example configs/active/credentials.yaml
# Edit configs/active/credentials.yaml with your API keys
```

See `configs/README.md` for details on each service.

## Scanning a Library (With and Without Claude)

The toolkit works two ways. The Python core is **100% standalone** - no Claude, no
network beyond optional metadata lookups. Claude Code adds AI decision-making and
visual cover verification *on top of* the same core, so output is identical in
format; Claude just adds judgment calls a script can't make (which source to trust,
is this the right cover). Point either at a single artist folder **or your whole
library root**.

### Without Claude - pure Python

**Targeted, per artist/album, via `cli.py`:**
```bash
pip install mutagen requests pillow static-ffmpeg pyyaml

python cli.py scan          "/path/to/Music"                 # extract metadata, audit, report
python cli.py validate      "/path/to/Music"                 # detect + auto-fix folder-name issues
python cli.py consolidate   "/path/to/Music"                 # merge multi-disc sets
python cli.py repair-covers "/path/to/Music"                 # detect + re-embed corrupt/missing art
python cli.py embed-cover   "/path/to/Music/Artist/Album" "https://.../cover.jpg"

# Write folder.jpg from each album's embedded art where missing (additive, safe):
python utilities/generate_folder_art.py "/path/to/Music" --scan-only   # preview
python utilities/generate_folder_art.py "/path/to/Music" --execute     # write where missing
```

**Whole-library, stateful workflow, via the orchestrator** (scan -> review -> apply,
with confidence scoring and resumable state):
```bash
python -m orchestrator.main init     "/path/to/Music"   # register the library
python -m orchestrator.main scan                         # extract metadata + detect issues
python -m orchestrator.main validate                     # cross-check vs MusicBrainz / iTunes
python -m orchestrator.main review                       # inspect uncertain matches
python -m orchestrator.main fix --dry-run                # preview every change
python -m orchestrator.main fix                          # apply
python -m orchestrator.main status                       # progress; resume anytime
```

### With Claude - AI-assisted (run inside Claude Code)

Same operations, but Claude resolves cross-source conflicts and **visually verifies**
cover art (catching covers that are technically valid but wrong for the album):
```bash
/clean-music      "/path/to/Music/Various Artists"   # autonomous end-to-end, no prompts
/verify-covers    "/path/to/Music/Various Artists"   # AI vision: does the art match the album?
/validate-folders "/path/to/Music/Artist"            # fix folder-name mismatches
/consolidate-all  "/path/to/Music/Various Artists"   # find + merge every multi-disc set
/repair-covers    "/path/to/Music/Artist"            # re-fetch / re-embed bad covers
```

## Validation: Track ID, Album, Cover Art (the core)

This toolkit is built around **three validation layers** - the parts that make a
library *correct*, not just tidy. Each runs deterministically in Python, and
optionally with Claude for the judgment calls a script can't make.

### 1. Track identity - audio fingerprint
*Is this file actually the song its tags claim?* Tags lie: mislabeled rips,
wrong-version files, "Track 04". The toolkit fingerprints the **audio itself** with
Chromaprint (`fpcalc`) and looks it up via **AcoustID** to get the real recording
(artist / title / release). This is how a file tagged "Kung Fu Fighting (Jackie
Chan)" was identified as **Ash - "Kung Fu"** and corrected.
- Tools: `fpcalc` + `sources/acoustid.py`; agent `.claude/agents/fingerprint_validator.md`
- Needs a free AcoustID API key in `configs/active/credentials.yaml`.

### 2. Album / metadata validation
*Do the album, artist, track numbers, and titles match an authoritative release?*
The **ValidatorAgent** cross-checks against **MusicBrainz** and **iTunes** (with
**Discogs** / **Spotify** as backups), computes a **confidence score**, and routes by
threshold: high -> auto-apply, mid -> review, low -> reject. Claude's
`conflict_resolver` decides which source to trust when they disagree.
- Tools: `agents/validator.py`, `sources/*`; agents `metadata_validator`,
  `conflict_resolver`. Run via `cli.py validate` or the orchestrator
  `scan -> validate -> review -> fix` workflow (thresholds table under
  [Automation Thresholds](#automation-thresholds)).

### 3. Cover art validation - Jellyfin-safe
*Is the embedded art a real, decodable image Jellyfin can read - and is it the right
cover?* Two-engine validation (Pillow pre-gate + `ffprobe` ground truth, the same
engine Jellyfin uses) means art is never written `width=0`; plus repair, `folder.jpg`
generation, and an optional Claude **visual** match check.
- Full detail in the next section.

> Together: the fingerprint confirms *what the track is*, metadata validation confirms
> *the album is right*, and cover validation confirms *the art is valid and matches* -
> deterministic in Python, with Claude for the calls a script can't make.

## Cover Art & Jellyfin Validation

Cover art is the area this toolkit is most opinionated about, because it's where
"looks fine" and "actually works" diverge.

### The problem
Jellyfin - and anything built on **ffmpeg** - extracts embedded album art with
`ffprobe`. The toolkit was producing art that displayed in some tag editors but
ffprobe read as `width=0, height=0` (blank/broken in Jellyfin), because bytes were
embedded with **no validation** and the image format was guessed from the file
extension (or an unsafe `data[:8]` slice that defaulted to JPEG on empty bytes).

### The fix: one validated pipeline (Pillow + ffprobe)
Every download and embed routes through `utilities/core/cover_art.py`, with
**two-engine** validation:

- **Pillow pre-gate** (in memory, before writing): non-empty -> magic-byte sniff
  (JPEG/PNG) -> integrity `verify()` -> reopen + `load()` (actually decode pixels)
  -> dimensions > 0 -> reject below 50px (icons/junk).
- **ffprobe ground truth** (after writing): re-reads the saved file with the
  **same engine Jellyfin uses** and asserts the cover stream reports real
  `width>0 / height>0`. A short/corrupt write is rejected, never silently kept.

The unit layer **hard-fails** (raises, never writes bad bytes); batch layers
**fail-soft** (log, skip, continue). If `ffprobe`/`static-ffmpeg` isn't installed it
degrades to the Pillow check and flags consumer-parity as unverified. MIME and the
MP4 cover format are set from the detected magic bytes, not the extension; existing
art is cleared before re-embedding to avoid duplicate/stale frames.

### Two kinds of cover - both kept consistent
- **Embedded art** - ID3 `APIC` / MP4 `covr` / FLAC `Picture`, inside each track.
- **`folder.jpg` / `folder.png`** - the sidecar image Jellyfin and most scanners
  prefer for the album thumbnail.

A subtle real-world bug: art can be a perfectly valid JPEG standalone yet be embedded
in a malformed `APIC` that Pillow accepts but ffmpeg reads as `0x0`. The post-write
ffprobe check catches exactly this; the fix is to re-embed through the validated core.

### The cover toolset

| Tool | What it does |
|------|--------------|
| `cli.py embed-cover` / `utilities/embed_cover.py` / core `embed_in_album` | download -> validate -> embed into every track -> write `folder.jpg` -> post-write ffprobe check |
| `cli.py repair-covers` / `utilities/repair_covers.py` | scan with ffprobe for `width=0` / missing / corrupt embedded art, then re-fetch (iTunes -> MusicBrainz/Cover Art Archive -> Discogs) and re-embed, backing up the old art first |
| `utilities/generate_folder_art.py` | write `folder.jpg`/`folder.png` from each album's **validated** embedded art where a folder image is missing - **additive only** (never overwrites), **no audio writes**, validated + ffmpeg-verified before *and* after write |
| `/verify-covers` (Claude) | AI vision check: does the art actually **match the album**? Catches covers that are technically valid but visually wrong (look-alike auto-fetches) |
| `/ai-validate-covers` + `validators/` | optional pluggable AI "second opinion" (Ollama / OpenAI-compatible / Anthropic / Hermes / Null-by-default) |
| AcoustID fingerprint (`fpcalc` + `sources/acoustid.py`, `fingerprint_validator` agent) | identify mislabeled tracks by audio so the *right* cover can be fetched (e.g. a track tagged "Kung Fu Fighting" that is actually Ash - "Kung Fu") |

### End to end: clean a whole library's covers

**Without Claude (deterministic):**
```bash
python cli.py repair-covers "/path/to/Music"                        # fix width=0 / missing / corrupt embedded art
python utilities/generate_folder_art.py "/path/to/Music" --execute  # add folder.jpg where missing (additive)
```

**With Claude (adds visual correctness):**
```bash
/repair-covers "/path/to/Music/Artist"             # re-fetch/re-embed bad covers
/verify-covers "/path/to/Music/Various Artists"    # flag valid-but-wrong covers for replacement
```

This is the exact pass run on the reference library: validated to **100% ffprobe-clean
(0 `width=0`)** across 15,860 tracks, with **folder.jpg coverage brought to 100%**.

> Background: project memory `cover-art-validation.md`, `jellyfin-ffprobe-truth.md`,
> and `cover-remediation-method.md`. Full validator guide: [`docs/AI_VALIDATORS.md`](docs/AI_VALIDATORS.md).

## De-duplication

Run **after** validation (so each file's identity and quality are known) and **before**
the cover-art pass:

```
scan -> validate (track ID + album) -> DE-DUPE -> cover art
```

`cli.py dedupe` finds duplicate copies of the same track **within an album folder**,
keeps the best one (higher bitrate -> has embedded art -> no watermark/copy suffix ->
larger size), and **moves the losers to an off-library backup - it never deletes**.

- **Matching:** same normalized title in a folder, confirmed by identical Chromaprint
  fingerprint or duration within ±3s = **strong** (auto-moved); within ±10s =
  **probable** (review only). Copy suffixes (`Song 2`, `Song (2)`) are stripped;
  **distinct versions** (live / remix / remaster) are never merged unless `--aggressive`.
- **Cross-album** "duplicates" (the same song on several albums) are written to a review
  report, never auto-moved - that's usually intentional.
- Fingerprinting (fpcalc) is on by default and applied only to candidate groups. Strong
  moves are logged to `outputs/dedupe_moved.log` for undo.

```bash
python cli.py dedupe "/path/to/Music" --scan-only                                  # report duplicate groups
python cli.py dedupe "/path/to/Music" --dry-run                                    # keep/move plan, no writes
python cli.py dedupe "/path/to/Music" --backup-dir "D:/music_backup/_duplicates" --execute
```

Mirrors `.claude/agents/duplicate_detector.md`; Claude can adjudicate ambiguous/probable
groups, while this Python tool does the deterministic detection and safe moves.

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
│   ├── generate_folder_art.py  # Write folder.jpg from embedded art (additive)
│   ├── repair_covers.py        # Re-fetch/re-embed corrupt or wrong covers
│   ├── deduplicate.py          # Duplicate tracks -> backup (validate first; never deletes)
│   ├── core/                   # Validated cover-art pipeline (cover_art, ffprobe)
│   ├── fix_metadata.py
│   ├── batch_fix_metadata.py
│   └── scan_folders.py
│
├── configs/                # YAML configurations
│   ├── README.md           # Config documentation
│   ├── templates/          # Config templates
│   │   ├── credentials.yaml.example
│   │   ├── batch_rename.yaml
│   │   ├── consolidation.yaml
│   │   └── move_tracks.yaml
│   └── active/             # User's active configs (gitignored)
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

### Validated Cover Art (Jellyfin-safe)
All cover handling routes through one validated pipeline (Pillow pre-gate + `ffprobe`
ground-truth post-write check) so embedded art is never written `width=0`, plus tools
to repair existing libraries and generate `folder.jpg` from embedded art.
**See the dedicated [Cover Art & Jellyfin Validation](#cover-art--jellyfin-validation)
section for the full story and commands.**

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
│              ORCHESTRATOR (Python)                      │
│     Manages workflow, state, and agent coordination     │
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
   │           Claude AI Decision Layer                  │
   │  - Metadata validation & conflict resolution        │
   │  - Visual cover art verification                    │
   │  - Confidence scoring & automation thresholds       │
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
| `lifecycle <path>` | Run the full pipeline: scan -> identify -> validate -> dedupe -> covers -> fix (dry-run by default; `--execute` to apply) |
| `scan <path>` | Extract metadata from albums |
| `validate <path>` | Validate and fix folder names |
| `consolidate <path>` | Find and consolidate multi-disc albums |
| `move-track <src> <dest>` | Move track with metadata update |
| `embed-cover <path> <url>` | Embed cover art |
| `repair-covers <path>` | Detect + re-embed corrupt/missing embedded art |
| `dedupe <path>` | Move duplicate tracks to backup (validate first; never deletes) |
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

## Bring Your Own Validator (optional AI second opinion)

The deterministic cover checks in `utilities/core/` (Pillow + ffprobe) are
always-on and need no AI and no network. On top of them sits an **optional,
pluggable** AI layer that gives a "second opinion" on whether embedded album art
visually matches the album (catching art that is technically valid but wrong).

By default this layer is OFF and requires nothing:

```yaml
# music-config.yaml
ai_validation:
  enabled: false      # NullValidator: abstains on every album, zero network calls
  provider: null
```

Run a pass (default config runs the NullValidator with no AI and no network):

```bash
python utilities/ai_validate_covers.py "/path/to/music/Artist"
```

Owners can wire in their own validator (e.g. a local Hermes/Jarvis gateway) and
the public can bring **Ollama**, an **OpenAI-compatible** server, **Anthropic
Claude**, a custom **Hermes** gateway, or nothing at all. Selecting a provider:

```yaml
ai_validation:
  enabled: true
  provider: ollama            # or openai_compat | anthropic | hermes | <your contrib name>
  endpoint: "http://localhost:11434"
  model: "llava"
```

To add a validator without touching the toolkit, drop a `BaseAIValidator`
subclass in `validators/contrib/` (copy `validators/contrib/example_validator.py`)
or register an entry point in the `music_toolkit.validators` group. The pass is
non-destructive: high-confidence mismatches are logged to
`.claude/knowledge/patterns.json` for review, never auto-fixed.

See [`docs/AI_VALIDATORS.md`](docs/AI_VALIDATORS.md) for the full guide.

## Resources

- [MusicBrainz](https://musicbrainz.org/) - Music metadata database
- [Discogs](https://www.discogs.com/) - Release information
- [iTunes Search API](https://itunes.apple.com/search) - Apple metadata
- [Mutagen Documentation](https://mutagen.readthedocs.io/) - Python audio library

---

**Status:** Active Development
**Last Updated:** 2026-06-29
