# Python Processing Agents

This folder contains Python agents that handle the actual file operations for music metadata management.

## Overview

The agents follow a **pipeline pattern**:
1. **ScannerAgent** discovers albums and extracts metadata
2. **ValidatorAgent** compares against external sources
3. **FixerAgent** applies corrections and embeds cover art

Each agent inherits from `BaseAgent` and implements the `process()` method.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    BaseAgent (base.py)                   │
│  - Abstract base class                                   │
│  - Common logging, config, state methods                 │
│  - Batch processing with error isolation                 │
└─────────────────────────┬───────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
  ┌───────────┐    ┌────────────┐    ┌───────────┐
  │ Scanner   │    │ Validator  │    │  Fixer    │
  │ Agent     │    │ Agent      │    │  Agent    │
  └───────────┘    └────────────┘    └───────────┘
       │                 │                 │
       ▼                 ▼                 ▼
  Discovers &      Validates vs.      Applies
  catalogs         MusicBrainz        corrections
  albums           iTunes             & embeds
```

## File Structure

```
agents/
├── README.md        # This documentation
├── __init__.py      # Package exports
├── base.py          # BaseAgent abstract class
├── scanner.py       # ScannerAgent implementation
├── validator.py     # ValidatorAgent implementation
├── fixer.py         # FixerAgent implementation
└── __pycache__/     # Python bytecode cache (auto-generated)
```

## BaseAgent (base.py)

Abstract base class providing common functionality.

### Key Methods

| Method | Purpose |
|--------|---------|
| `process(item)` | **Abstract** - Process a single item |
| `process_batch(items, callback)` | Process multiple items with optional callback |
| `log(message)` | Log info message |
| `log_error(message)` | Log error message |
| `log_progress(current, total)` | Log progress with ETA |
| `get_config(key, default)` | Get configuration value |
| `save_state(album_path, status, data)` | Persist album state |
| `get_state(album_path)` | Retrieve album state |

### Batch Processing

```python
# Process multiple albums with progress callback
def on_complete(item, result):
    print(f"Completed: {item['path']}")

results = agent.process_batch(albums, callback=on_complete)
# Returns: {'success': N, 'failed': N, 'skipped': N, 'results': [...]}
```

## ScannerAgent (scanner.py)

Discovers albums and extracts metadata from audio files.

### Data Classes

**TrackData** - Single track information:
```python
@dataclass
class TrackData:
    filepath: str
    filename: str
    title: str
    artist: str
    album: str
    album_artist: str
    track_number: int
    disc_number: int
    year: int
    genre: str
    has_cover: bool
    duration_ms: int
    issues: List[str]
```

**AlbumData** - Complete album information:
```python
@dataclass
class AlbumData:
    path: str
    folder_name: str
    album_id: str
    tracks: List[TrackData]
    has_cover: bool
    cover_source: str
    is_multi_disc: bool
    disc_count: int
    issues: List[str]
```

### Supported Formats

| Format | Library | Tag Type |
|--------|---------|----------|
| MP3 | mutagen.mp3 | ID3 (EasyID3) |
| FLAC | mutagen.flac | Vorbis comments |
| M4A/MP4 | mutagen.mp4 | iTunes atoms |
| OGG | mutagen.oggvorbis | Vorbis comments |

### Issue Detection

- Missing cover art (embedded or folder.jpg)
- Truncated folder names (>50 chars ending with "...")
- Inconsistent album names across tracks
- Missing genre metadata
- Missing track numbers

### Usage

```python
from agents import ScannerAgent

scanner = ScannerAgent(config, state)

# Scan single album
result = scanner.scan_album('/path/to/album')

# Scan entire artist
results = scanner.scan_artist('/path/to/artist')

# Scan full library
results = scanner.scan_library('/path/to/music')
```

## ValidatorAgent (validator.py)

Compares scanned albums against external data sources.

### Data Class

**ValidationResult**:
```python
@dataclass
class ValidationResult:
    # Local info
    path: str
    album_id: str
    title: str
    artist: str
    track_count: int

    # Match info
    matched: bool
    source: str          # 'musicbrainz', 'itunes', etc.
    match_id: str
    match_title: str
    match_artist: str
    match_track_count: int

    # Scoring
    confidence: float    # 0.0 - 1.0
    title_score: float
    artist_score: float
    track_count_score: float

    # Status
    status: str          # 'auto_approved', 'needs_review', 'rejected'
    corrections: List[dict]
    cover_url: str
```

### Confidence Scoring

Weighted combination:
- **Title similarity**: 50%
- **Artist similarity**: 30%
- **Track count match**: 20%

### Decision Thresholds

| Confidence | Status | Action |
|------------|--------|--------|
| 95%+ | `auto_approved` | Apply automatically |
| 70-94% | `needs_review` | Human verification |
| <70% | `rejected` | Likely wrong match |

### Data Sources

Sources are queried in priority order:
1. **MusicBrainz** (primary, no auth required)
2. **iTunes API** (fallback, no auth required)

### Usage

```python
from agents import ValidatorAgent

validator = ValidatorAgent(config, state)

# Validate album
result = validator.validate_album({
    'path': '/path/to/album',
    'title': 'Album Name',
    'artist': 'Artist Name',
    'track_count': 12
})

# Check result
if result.status == 'auto_approved':
    print(f"Match: {result.match_title} ({result.confidence:.0%})")
```

## FixerAgent (fixer.py)

Applies validated corrections to albums.

### Data Class

**FixResult**:
```python
@dataclass
class FixResult:
    album_path: str
    album_id: str
    success: bool
    changes_made: List[str]
    errors: List[str]
    new_path: str        # If folder was renamed
```

### Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| Rename folder | `_rename_folder()` | Windows-safe folder rename |
| Embed cover | `_embed_cover_art()` | Download + embed in all tracks |
| Update genre | `_update_genre()` | Set genre across all tracks |
| Sync filenames | `sync_filenames_to_titles()` | Match filenames to metadata titles |

### Cover Art Embedding

Supports all formats:
- **MP3**: APIC frame (ID3)
- **M4A**: `covr` atom
- **FLAC**: Picture block

```python
# Embed cover from URL
fixer._embed_cover_art(album_path, 'https://example.com/cover.jpg')
```

### Windows-Safe Transformations

Invalid characters are replaced:
| Character | Replacement |
|-----------|-------------|
| `:` | ` -` |
| `?` `*` `"` `<` `>` `\|` | removed |
| Path > 250 chars | truncated |

### Usage

```python
from agents import FixerAgent

fixer = FixerAgent(config, state)

# Apply corrections (with dry-run preview)
result = fixer.apply_fixes(album_path, corrections, dry_run=True)

# Actually apply
result = fixer.apply_fixes(album_path, corrections, dry_run=False)

# Check results
for change in result.changes_made:
    print(f"Applied: {change}")
```

## Integration

### With Orchestrator

```python
# orchestrator/orchestrator.py
from agents import ScannerAgent, ValidatorAgent, FixerAgent

class Orchestrator:
    def __init__(self, config, state):
        self.scanner = ScannerAgent(config, state)
        self.validator = ValidatorAgent(config, state)
        self.fixer = FixerAgent(config, state)

    def process_album(self, path):
        # Scan
        album_data = self.scanner.scan_album(path)

        # Validate
        validation = self.validator.validate_album(album_data)

        # Fix (if auto-approved)
        if validation.status == 'auto_approved':
            result = self.fixer.apply_fixes(path, validation.corrections)
```

### With CLI

```python
# orchestrator/main.py
from agents import ScannerAgent

def cmd_scan(args):
    scanner = ScannerAgent(config, state)
    results = scanner.scan_artist(args.path)

    for album in results:
        print(f"{album.folder_name}: {album.track_count} tracks")
```

## File Notes

### __init__.py

Exports the public API:
```python
from .base import BaseAgent
from .scanner import ScannerAgent
from .validator import ValidatorAgent
from .fixer import FixerAgent

__all__ = ['BaseAgent', 'ScannerAgent', 'ValidatorAgent', 'FixerAgent']
```

This allows clean imports:
```python
from agents import ScannerAgent  # Instead of agents.scanner.ScannerAgent
```

### __pycache__/

Auto-generated by Python. Contains compiled bytecode (`.pyc` files) for faster imports.

- **Safe to delete**: Will be recreated on next import
- **Git ignored**: Should be in `.gitignore`
- **Per-version**: Separate files for different Python versions

## Testing

```python
# Test scanner
scanner = ScannerAgent(config, state)
album = scanner.scan_album('/test/album')
assert album.track_count > 0

# Test validator
validator = ValidatorAgent(config, state)
result = validator.validate_album({
    'path': '/test/album',
    'title': 'Test Album',
    'artist': 'Test Artist',
    'track_count': 10
})
assert result.confidence > 0

# Test fixer (dry-run)
fixer = FixerAgent(config, state)
result = fixer.apply_fixes('/test/album', corrections, dry_run=True)
assert result.success
```

---

**Last Updated:** 2026-01-13
