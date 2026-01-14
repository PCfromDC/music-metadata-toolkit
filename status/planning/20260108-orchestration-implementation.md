# Music Library Orchestration - Implementation Guide

**Date:** 2026-01-08
**Version:** 1.0
**Status:** Ready for Implementation

---

## Overview

This document provides step-by-step implementation details for the Music Library Orchestration System.

---

## Phase 1: Foundation

### 1.1 Project Structure

```bash
# Create directories
mkdir -p orchestrator agents sources models config state logs
touch orchestrator/__init__.py agents/__init__.py sources/__init__.py models/__init__.py
```

### 1.2 Configuration Management (`orchestrator/config.py`)

```python
"""
Configuration management for music cleanup orchestration.
Loads YAML config and credentials, with environment variable support.
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

class ConfigManager:
    def __init__(self, config_path: str = "music-config.yaml"):
        self.config_path = Path(config_path)
        self.credentials_path = Path("credentials.yaml")
        self._config: Dict[str, Any] = {}
        self._credentials: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load configuration and credentials"""
        # Load main config
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}

        # Load credentials (optional)
        if self.credentials_path.exists():
            with open(self.credentials_path, 'r', encoding='utf-8') as f:
                self._credentials = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value with dot notation (e.g., 'api.musicbrainz.rate_limit')"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        # Expand environment variables
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            env_var = value[2:-1]
            return os.environ.get(env_var, default)
        return value

    def get_credential(self, key: str) -> Optional[str]:
        """Get credential value"""
        keys = key.split('.')
        value = self._credentials
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value

    @property
    def library_root(self) -> str:
        return self.get('library.root', '/path/to/music')

    @property
    def backup_enabled(self) -> bool:
        return self.get('library.backup_enabled', True)

    @property
    def backup_path(self) -> str:
        return self.get('library.backup_path', 'D:/music_backup')
```

### 1.3 State Persistence (`orchestrator/state.py`)

```python
"""
State persistence for resumable operations.
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

class StateStore:
    def __init__(self, state_path: str = "state"):
        self.state_path = Path(state_path)
        self.state_path.mkdir(parents=True, exist_ok=True)
        self.albums_path = self.state_path / "albums"
        self.albums_path.mkdir(exist_ok=True)

    def get_album_id(self, path: str) -> str:
        """Generate consistent album ID from path"""
        return hashlib.md5(path.encode('utf-8')).hexdigest()[:12]

    def get_album_state(self, album_path: str) -> Optional[Dict[str, Any]]:
        """Load album state"""
        album_id = self.get_album_id(album_path)
        state_file = self.albums_path / f"{album_id}.json"
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_album_state(self, album_path: str, status: str, data: Dict[str, Any]):
        """Save album state"""
        album_id = self.get_album_id(album_path)
        state_file = self.albums_path / f"{album_id}.json"

        existing = self.get_album_state(album_path) or {
            "album_id": album_id,
            "path": album_path,
            "phases": {}
        }

        existing["status"] = status
        existing["phases"][status.lower()] = {
            "timestamp": datetime.now().isoformat(),
            "result": data
        }

        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def get_session(self) -> Dict[str, Any]:
        """Load session state"""
        session_file = self.state_path / "session.json"
        if session_file.exists():
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._create_session()

    def save_session(self, session: Dict[str, Any]):
        """Save session state"""
        session_file = self.state_path / "session.json"
        session["last_checkpoint"] = datetime.now().isoformat()
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session, f, indent=2)

    def _create_session(self) -> Dict[str, Any]:
        return {
            "session_id": datetime.now().strftime("%Y%m%d-%H%M%S"),
            "started_at": datetime.now().isoformat(),
            "status": "new",
            "statistics": {
                "processed": {},
                "pending": {},
                "errors": 0
            }
        }
```

### 1.4 CLI Framework (`orchestrator/main.py`)

```python
#!/usr/bin/env python3
"""
Music Library Cleanup - Command Line Interface

Usage:
    music-clean init <path> [--config <file>]
    music-clean scan [--artist <name>] [--album <path>] [--full]
    music-clean validate [--source <name>] [--threshold <n>]
    music-clean review [--list] [--approve <id>] [--reject <id>]
    music-clean fix [--dry-run] [--album <id>]
    music-clean status
    music-clean resume
"""
import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        prog='music-clean',
        description='Music Library Cleanup Orchestrator'
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # init
    init_parser = subparsers.add_parser('init', help='Initialize project')
    init_parser.add_argument('path', help='Library root path')
    init_parser.add_argument('--config', default='music-config.yaml')

    # scan
    scan_parser = subparsers.add_parser('scan', help='Scan library')
    scan_parser.add_argument('--artist', help='Scan specific artist')
    scan_parser.add_argument('--album', help='Scan specific album path')
    scan_parser.add_argument('--full', action='store_true', help='Full rescan')

    # validate
    validate_parser = subparsers.add_parser('validate', help='Validate albums')
    validate_parser.add_argument('--source', default='musicbrainz')
    validate_parser.add_argument('--threshold', type=float, default=0.70)

    # review
    review_parser = subparsers.add_parser('review', help='Review queue')
    review_parser.add_argument('--list', action='store_true')
    review_parser.add_argument('--approve', metavar='ID')
    review_parser.add_argument('--reject', metavar='ID')

    # fix
    fix_parser = subparsers.add_parser('fix', help='Apply fixes')
    fix_parser.add_argument('--dry-run', action='store_true')
    fix_parser.add_argument('--album', metavar='ID')

    # status
    subparsers.add_parser('status', help='Show status')

    # resume
    subparsers.add_parser('resume', help='Resume session')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Import orchestrator and dispatch
    from orchestrator.orchestrator import MusicLibraryOrchestrator

    if args.command == 'init':
        orchestrator = MusicLibraryOrchestrator(args.config)
        orchestrator.init(args.path)
    elif args.command == 'scan':
        orchestrator = MusicLibraryOrchestrator()
        orchestrator.scan(artist=args.artist, album=args.album, full=args.full)
    elif args.command == 'validate':
        orchestrator = MusicLibraryOrchestrator()
        orchestrator.validate(source=args.source, threshold=args.threshold)
    elif args.command == 'review':
        orchestrator = MusicLibraryOrchestrator()
        if args.list:
            orchestrator.review_list()
        elif args.approve:
            orchestrator.review_approve(args.approve)
        elif args.reject:
            orchestrator.review_reject(args.reject)
        else:
            orchestrator.review_interactive()
    elif args.command == 'fix':
        orchestrator = MusicLibraryOrchestrator()
        orchestrator.fix(dry_run=args.dry_run, album_id=args.album)
    elif args.command == 'status':
        orchestrator = MusicLibraryOrchestrator()
        orchestrator.status()
    elif args.command == 'resume':
        orchestrator = MusicLibraryOrchestrator()
        orchestrator.resume()

    return 0

if __name__ == '__main__':
    sys.exit(main())
```

---

## Phase 2: Data Sources

### 2.1 Base Source (`sources/base.py`)

```python
"""
Base class for data source adapters.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class AlbumMatch:
    """Result from source lookup"""
    source: str
    source_id: str
    title: str
    artist: str
    year: Optional[int]
    track_count: int
    tracks: List[Dict[str, Any]]
    cover_url: Optional[str]
    confidence: float
    raw_data: Dict[str, Any]

class DataSource(ABC):
    """Abstract base class for data sources"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Source name identifier"""
        pass

    @abstractmethod
    def search_album(self, title: str, artist: str = "Various Artists") -> List[AlbumMatch]:
        """Search for album by title and artist"""
        pass

    @abstractmethod
    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        """Get album details by source ID"""
        pass

    def get_cover_url(self, source_id: str) -> Optional[str]:
        """Get cover art URL for album"""
        album = self.get_album(source_id)
        return album.cover_url if album else None
```

### 2.2 iTunes Source (`sources/itunes.py`)

```python
"""
iTunes Search API adapter.
Free, no authentication required.
"""
import requests
import time
from typing import List, Optional
from .base import DataSource, AlbumMatch

class iTunesSource(DataSource):
    BASE_URL = "https://itunes.apple.com/search"

    def __init__(self, country: str = "us", rate_limit: float = 0.05):
        self.country = country
        self.rate_limit = rate_limit
        self._last_request = 0

    @property
    def name(self) -> str:
        return "itunes"

    def _rate_limit(self):
        """Respect rate limits"""
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    def search_album(self, title: str, artist: str = "Various Artists") -> List[AlbumMatch]:
        self._rate_limit()

        params = {
            "term": f"{artist} {title}",
            "entity": "album",
            "country": self.country,
            "limit": 10
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"[iTunes] Search error: {e}")
            return []

        results = []
        for item in data.get("results", []):
            match = AlbumMatch(
                source="itunes",
                source_id=str(item.get("collectionId")),
                title=item.get("collectionName", ""),
                artist=item.get("artistName", ""),
                year=self._extract_year(item.get("releaseDate")),
                track_count=item.get("trackCount", 0),
                tracks=[],  # iTunes doesn't return tracks in album search
                cover_url=self._get_large_artwork(item.get("artworkUrl100")),
                confidence=0.0,  # Calculated by validator
                raw_data=item
            )
            results.append(match)

        return results

    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        self._rate_limit()

        params = {
            "id": source_id,
            "entity": "song",
            "country": self.country
        }

        try:
            response = requests.get(
                "https://itunes.apple.com/lookup",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return None

        results = data.get("results", [])
        if not results:
            return None

        # First result is album, rest are tracks
        album_data = results[0]
        tracks = [
            {"title": t.get("trackName"), "track_number": t.get("trackNumber")}
            for t in results[1:]
            if t.get("wrapperType") == "track"
        ]

        return AlbumMatch(
            source="itunes",
            source_id=source_id,
            title=album_data.get("collectionName", ""),
            artist=album_data.get("artistName", ""),
            year=self._extract_year(album_data.get("releaseDate")),
            track_count=album_data.get("trackCount", 0),
            tracks=tracks,
            cover_url=self._get_large_artwork(album_data.get("artworkUrl100")),
            confidence=0.0,
            raw_data=album_data
        )

    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        if date_str and len(date_str) >= 4:
            try:
                return int(date_str[:4])
            except ValueError:
                pass
        return None

    def _get_large_artwork(self, url: Optional[str]) -> Optional[str]:
        """Convert 100x100 artwork URL to larger size"""
        if url:
            return url.replace("100x100bb", "1000x1000bb")
        return None
```

### 2.3 AcoustID Source (`sources/acoustid.py`)

```python
"""
AcoustID audio fingerprinting adapter.
Requires: fpcalc binary, pyacoustid library, API key
"""
import acoustid
from typing import List, Optional, Dict, Any
from .base import DataSource, AlbumMatch

class AcoustIDSource(DataSource):
    """Audio fingerprinting via AcoustID"""

    def __init__(self, api_key: str, chromaprint_path: Optional[str] = None):
        self.api_key = api_key
        if chromaprint_path:
            acoustid.chromaprint._fingerprint_cmd = chromaprint_path

    @property
    def name(self) -> str:
        return "acoustid"

    def fingerprint_file(self, audio_path: str) -> Optional[Dict[str, Any]]:
        """
        Generate fingerprint and lookup in AcoustID database.
        Returns MusicBrainz recording IDs if found.
        """
        try:
            results = acoustid.match(self.api_key, audio_path)

            for score, recording_id, title, artist in results:
                return {
                    "score": score,
                    "recording_id": recording_id,
                    "title": title,
                    "artist": artist
                }
        except acoustid.NoBackendError:
            print("[AcoustID] Error: Chromaprint (fpcalc) not found")
        except acoustid.FingerprintGenerationError:
            print(f"[AcoustID] Error: Could not fingerprint {audio_path}")
        except acoustid.WebServiceError as e:
            print(f"[AcoustID] API error: {e}")

        return None

    def search_album(self, title: str, artist: str = "Various Artists") -> List[AlbumMatch]:
        """Not applicable - use fingerprint_file for individual tracks"""
        return []

    def get_album(self, source_id: str) -> Optional[AlbumMatch]:
        """Not applicable - AcoustID identifies tracks, not albums"""
        return None
```

---

## Phase 3: Agents

### 3.1 Base Agent (`agents/base.py`)

```python
"""
Base class for processing agents.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
from orchestrator.config import ConfigManager
from orchestrator.state import StateStore

class BaseAgent(ABC):
    """Abstract base class for agents"""

    def __init__(self, config: ConfigManager, state: StateStore):
        self.config = config
        self.state = state

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def process(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process single item, return result"""
        pass

    def log(self, message: str):
        print(f"[{self.name}] {message}")
```

### 3.2 Scanner Agent (`agents/scanner.py`)

Key functionality refactored from `extract_metadata.py`:
- Traverse directories
- Extract metadata using Mutagen
- Detect embedded cover art
- Identify multi-disc sets
- Flag issues

### 3.3 Validator Agent (`agents/validator.py`)

Key functionality refactored from `validate_various_artists.py`:
- Search multiple sources
- Calculate confidence scores
- Compare track listings
- Check cover art availability
- Route to review queue if confidence < threshold

### 3.4 Fixer Agent (`agents/fixer.py`)

Key functionality combined from `fix_metadata.py` and `embed_cover.py`:
- Update metadata fields
- Embed cover art
- Rename folders (Windows-safe)
- Verify changes after applying

---

## Phase 4: Orchestration

### 4.1 Queue Manager (`orchestrator/queue.py`)

```python
"""
Queue management for processing pipeline.
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum

class AlbumStatus(Enum):
    DISCOVERED = "discovered"
    SCANNED = "scanned"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FIXED = "fixed"
    VERIFIED = "verified"
    FAILED = "failed"

class QueueManager:
    def __init__(self, queue_path: str = "state/queue.json"):
        self.queue_path = Path(queue_path)
        self._queue: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        if self.queue_path.exists():
            with open(self.queue_path, 'r', encoding='utf-8') as f:
                self._queue = json.load(f)

    def save(self):
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.queue_path, 'w', encoding='utf-8') as f:
            json.dump(self._queue, f, indent=2)

    def add(self, album_id: str, path: str, status: AlbumStatus = AlbumStatus.DISCOVERED):
        self._queue[album_id] = {
            "path": path,
            "status": status.value,
            "priority": 0
        }
        self.save()

    def update_status(self, album_id: str, status: AlbumStatus):
        if album_id in self._queue:
            self._queue[album_id]["status"] = status.value
            self.save()

    def get_pending(self, status: AlbumStatus) -> List[Dict[str, Any]]:
        """Get albums with specific status, sorted by priority"""
        items = [
            {"id": k, **v}
            for k, v in self._queue.items()
            if v["status"] == status.value
        ]
        return sorted(items, key=lambda x: x.get("priority", 0), reverse=True)

    def get_review_queue(self) -> List[Dict[str, Any]]:
        return self.get_pending(AlbumStatus.NEEDS_REVIEW)
```

### 4.2 Main Orchestrator (`orchestrator/orchestrator.py`)

```python
"""
Main orchestrator - coordinates all agents and manages pipeline.
"""
from .config import ConfigManager
from .state import StateStore
from .queue import QueueManager, AlbumStatus
from agents.scanner import ScannerAgent
from agents.validator import ValidatorAgent
from agents.fixer import FixerAgent

class MusicLibraryOrchestrator:
    def __init__(self, config_path: str = "music-config.yaml"):
        self.config = ConfigManager(config_path)
        self.state = StateStore(self.config.get('output.state_path', 'state'))
        self.queue = QueueManager()

        # Initialize agents
        self.scanner = ScannerAgent(self.config, self.state)
        self.validator = ValidatorAgent(self.config, self.state)
        self.fixer = FixerAgent(self.config, self.state)

    def init(self, library_path: str):
        """Initialize project with library path"""
        print(f"Initializing music cleanup project...")
        print(f"Library root: {library_path}")
        # Save to config, discover artists
        # ...

    def scan(self, artist: str = None, album: str = None, full: bool = False):
        """Scan library or specific artist/album"""
        # Use scanner agent
        # ...

    def validate(self, source: str = "musicbrainz", threshold: float = 0.70):
        """Validate scanned albums"""
        # Use validator agent
        # ...

    def review_interactive(self):
        """Interactive review of pending albums"""
        queue = self.queue.get_review_queue()
        for item in queue:
            # Display album info
            # Get user input
            # Update status
            pass

    def fix(self, dry_run: bool = True, album_id: str = None):
        """Apply fixes to approved albums"""
        # Use fixer agent
        # ...

    def status(self):
        """Display current status"""
        session = self.state.get_session()
        print(f"Session: {session.get('session_id')}")
        print(f"Status: {session.get('status')}")
        # ...

    def resume(self):
        """Resume interrupted session"""
        session = self.state.get_session()
        print(f"Resuming session {session.get('session_id')}...")
        # ...
```

---

## Configuration Files

### music-config.yaml (Template)

See plan file for complete configuration.

### credentials.yaml.example

```yaml
# Copy this file to credentials.yaml and fill in your values
# DO NOT commit credentials.yaml to version control

acoustid:
  api_key: "YOUR_ACOUSTID_API_KEY"

discogs:
  token: "YOUR_DISCOGS_TOKEN"

musicbrainz:
  user_agent: "MusicCleanup/1.0 (your@email.com)"
```

### .gitignore

```
# Credentials
credentials.yaml

# State
state/

# Logs
logs/

# Python
__pycache__/
*.pyc
*.pyo
.env

# IDE
.vscode/
.idea/
```

### requirements.txt

```
mutagen>=1.45.0
requests>=2.28.0
pyyaml>=6.0
pyacoustid>=1.2.0
```

---

## Testing Strategy

### Unit Tests
- Config loading
- State persistence
- Source adapters (mock HTTP)
- Confidence scoring

### Integration Tests
- Scanner on real album folder
- Validator with live APIs (rate limited)
- Fixer in dry-run mode

### End-to-End Tests
- Process single album through pipeline
- Test on Various Artists collection
- Verify checkpoint/resume

---

## Deployment

### Installation

```bash
# Clone/download project
cd "D:\music cleanup"

# Install dependencies
pip install -r requirements.txt

# Install Chromaprint (for fingerprinting)
# Windows: Download fpcalc.exe from https://acoustid.org/chromaprint
# Place in PATH or specify in config

# Copy and configure
cp credentials.yaml.example credentials.yaml
# Edit credentials.yaml with your API keys

# Initialize
python -m orchestrator.main init "/path/to/music"
```

---

## Document Complete

Ready for implementation. Start with Phase 1: Foundation.
