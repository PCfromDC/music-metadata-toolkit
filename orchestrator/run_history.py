#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run history for the lifecycle pipeline.

A tiny append-only log of pipeline runs, stored as a JSON list at
``state/run_history.json``. Each run appends one record so the most recent run
can be inspected later (e.g. by ``status`` or downstream tooling).

Record shape (see ``cmd_lifecycle``)::

    {
        "timestamp": "2026-06-29T12:34:56",
        "target":    "//192.168.1.252/music/U2",
        "mode":      "dry-run",            # scan-only | dry-run | execute
        "phases": {
            "scanned": 0, "identified": 0, "validated": 0, "needs_review": 0,
            "deduped_moved": 0, "covers_repaired": 0, "folderjpg_added": 0,
            "fixed": 0, "flagged": 0
        }
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = "state/run_history.json"


def _load(path: Path) -> List[Dict[str, Any]]:
    """Load the run-history list, tolerating a missing or corrupt file."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def append_run(record: Dict[str, Any], path: str = DEFAULT_PATH) -> Dict[str, Any]:
    """Append ``record`` to the JSON run-history list, creating dirs as needed.

    Returns the record that was appended.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = _load(p)
    data.append(record)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return record


def last_run(path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    """Return the most recent run record, or ``None`` if there is no history."""
    data = _load(Path(path))
    return data[-1] if data else None
