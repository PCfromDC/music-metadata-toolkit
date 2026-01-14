#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
State persistence for resumable operations.
Stores session state and per-album processing state.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateStore:
    """
    Persistent state storage for music library processing.
    Stores session info and per-album processing state.
    """

    def __init__(self, state_path: str = "state"):
        self.state_path = Path(state_path)
        self.state_path.mkdir(parents=True, exist_ok=True)
        self.albums_path = self.state_path / "albums"
        self.albums_path.mkdir(exist_ok=True)
        self.checkpoints_path = self.state_path / "checkpoints"
        self.checkpoints_path.mkdir(exist_ok=True)

    def get_album_id(self, path: str) -> str:
        """Generate consistent album ID from path"""
        return hashlib.md5(path.encode('utf-8')).hexdigest()[:12]

    # ==================== Album State ====================

    def get_album_state(self, album_path: str) -> Optional[Dict[str, Any]]:
        """Load album state from file"""
        album_id = self.get_album_id(album_path)
        state_file = self.albums_path / f"{album_id}.json"

        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return None

        return None

    def save_album_state(self, album_path: str, status: str, data: Dict[str, Any]) -> None:
        """
        Save album state with phase data.

        Args:
            album_path: Full path to album folder
            status: Current status (SCANNED, VALIDATED, FIXED, etc.)
            data: Phase-specific data to store
        """
        album_id = self.get_album_id(album_path)
        state_file = self.albums_path / f"{album_id}.json"

        # Load existing or create new
        existing = self.get_album_state(album_path) or {
            "album_id": album_id,
            "path": album_path,
            "created_at": datetime.now().isoformat(),
            "phases": {}
        }

        # Update state
        existing["status"] = status
        existing["updated_at"] = datetime.now().isoformat()
        existing["phases"][status.lower()] = {
            "timestamp": datetime.now().isoformat(),
            "result": data
        }

        # Save
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def get_album_status(self, album_path: str) -> Optional[str]:
        """Get current status of an album"""
        state = self.get_album_state(album_path)
        return state.get("status") if state else None

    def list_albums_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all albums with a specific status"""
        results = []

        for state_file in self.albums_path.glob("*.json"):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("status") == status:
                        results.append(data)
            except (json.JSONDecodeError, IOError):
                continue

        return results

    # ==================== Session State ====================

    def get_session(self) -> Dict[str, Any]:
        """Load current session state"""
        session_file = self.state_path / "session.json"

        if session_file.exists():
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass

        return self._create_session()

    def save_session(self, session: Dict[str, Any]) -> None:
        """Save session state"""
        session_file = self.state_path / "session.json"
        session["last_checkpoint"] = datetime.now().isoformat()

        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session, f, indent=2)

    def _create_session(self) -> Dict[str, Any]:
        """Create new session state"""
        return {
            "session_id": datetime.now().strftime("%Y%m%d-%H%M%S"),
            "started_at": datetime.now().isoformat(),
            "library_root": None,
            "status": "new",
            "current_phase": None,
            "statistics": {
                "total_artists": 0,
                "total_albums": 0,
                "total_tracks": 0,
                "processed": {
                    "scanned": 0,
                    "validated": 0,
                    "reviewed": 0,
                    "fixed": 0,
                    "verified": 0
                },
                "pending": {
                    "scan": 0,
                    "validation": 0,
                    "review": 0,
                    "fix": 0,
                    "verify": 0
                },
                "errors": 0
            },
            "last_checkpoint": None
        }

    def update_session_stats(self, **kwargs) -> None:
        """Update session statistics"""
        session = self.get_session()

        for key, value in kwargs.items():
            if '.' in key:
                # Handle nested keys like 'processed.scanned'
                parts = key.split('.')
                target = session['statistics']
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = value
            else:
                session['statistics'][key] = value

        self.save_session(session)

    # ==================== Checkpoints ====================

    def create_checkpoint(self) -> str:
        """Create a checkpoint of current state"""
        session = self.get_session()
        checkpoint_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        checkpoint_file = self.checkpoints_path / f"checkpoint_{checkpoint_id}.json"

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "created_at": datetime.now().isoformat(),
            "session": session,
            "album_count": len(list(self.albums_path.glob("*.json")))
        }

        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2)

        return checkpoint_id

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all checkpoints"""
        checkpoints = []

        for cp_file in sorted(self.checkpoints_path.glob("checkpoint_*.json")):
            try:
                with open(cp_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    checkpoints.append({
                        "id": data.get("checkpoint_id"),
                        "created": data.get("created_at"),
                        "albums": data.get("album_count", 0)
                    })
            except (json.JSONDecodeError, IOError):
                continue

        return checkpoints

    # ==================== Error Logging ====================

    def log_error(self, album_path: str, error_type: str, message: str) -> None:
        """Log an error for later review"""
        errors_file = self.state_path / "errors.json"

        # Load existing errors
        errors = []
        if errors_file.exists():
            try:
                with open(errors_file, 'r', encoding='utf-8') as f:
                    errors = json.load(f)
            except json.JSONDecodeError:
                errors = []

        # Add new error
        errors.append({
            "timestamp": datetime.now().isoformat(),
            "album_id": self.get_album_id(album_path),
            "album_path": album_path,
            "error_type": error_type,
            "message": message
        })

        # Save
        with open(errors_file, 'w', encoding='utf-8') as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)

        # Update session error count
        session = self.get_session()
        session['statistics']['errors'] = len(errors)
        self.save_session(session)

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get all logged errors"""
        errors_file = self.state_path / "errors.json"

        if errors_file.exists():
            try:
                with open(errors_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass

        return []

    def clear_errors(self) -> None:
        """Clear all logged errors"""
        errors_file = self.state_path / "errors.json"
        if errors_file.exists():
            errors_file.unlink()

    def __repr__(self) -> str:
        return f"StateStore(path={self.state_path})"
