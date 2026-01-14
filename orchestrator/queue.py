#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Queue management for processing pipeline.
Manages album processing order and status tracking.
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AlbumStatus(Enum):
    """Album processing status"""
    DISCOVERED = "discovered"
    SCANNED = "scanned"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FIXED = "fixed"
    VERIFIED = "verified"
    FAILED = "failed"
    SKIPPED = "skipped"


class Priority(Enum):
    """Processing priority levels"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class QueueManager:
    """
    Manages the processing queue for albums.
    Supports priority ordering and status filtering.
    """

    def __init__(self, queue_path: str = "state/queue.json"):
        self.queue_path = Path(queue_path)
        self._queue: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        """Load queue from file"""
        if self.queue_path.exists():
            try:
                with open(self.queue_path, 'r', encoding='utf-8') as f:
                    self._queue = json.load(f)
            except json.JSONDecodeError:
                self._queue = {}

    def save(self) -> None:
        """Save queue to file"""
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.queue_path, 'w', encoding='utf-8') as f:
            json.dump(self._queue, f, indent=2, ensure_ascii=False)

    def add(
        self,
        album_id: str,
        path: str,
        status: AlbumStatus = AlbumStatus.DISCOVERED,
        priority: Priority = Priority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add album to queue"""
        self._queue[album_id] = {
            "path": path,
            "status": status.value,
            "priority": priority.value,
            "added_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.save()

    def update_status(
        self,
        album_id: str,
        status: AlbumStatus,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update album status"""
        if album_id not in self._queue:
            return False

        self._queue[album_id]["status"] = status.value
        self._queue[album_id]["updated_at"] = datetime.now().isoformat()

        if metadata:
            self._queue[album_id]["metadata"].update(metadata)

        self.save()
        return True

    def update_priority(self, album_id: str, priority: Priority) -> bool:
        """Update album priority"""
        if album_id not in self._queue:
            return False

        self._queue[album_id]["priority"] = priority.value
        self._queue[album_id]["updated_at"] = datetime.now().isoformat()
        self.save()
        return True

    def get(self, album_id: str) -> Optional[Dict[str, Any]]:
        """Get album queue entry"""
        if album_id in self._queue:
            return {"id": album_id, **self._queue[album_id]}
        return None

    def remove(self, album_id: str) -> bool:
        """Remove album from queue"""
        if album_id in self._queue:
            del self._queue[album_id]
            self.save()
            return True
        return False

    def get_by_status(self, status: AlbumStatus) -> List[Dict[str, Any]]:
        """Get all albums with specific status, sorted by priority"""
        items = [
            {"id": k, **v}
            for k, v in self._queue.items()
            if v["status"] == status.value
        ]
        return sorted(items, key=lambda x: x.get("priority", 0), reverse=True)

    def get_pending(self, status: AlbumStatus) -> List[Dict[str, Any]]:
        """Alias for get_by_status"""
        return self.get_by_status(status)

    def get_review_queue(self) -> List[Dict[str, Any]]:
        """Get albums pending human review"""
        return self.get_by_status(AlbumStatus.NEEDS_REVIEW)

    def get_ready_to_fix(self) -> List[Dict[str, Any]]:
        """Get albums ready for fixing (validated or approved)"""
        validated = self.get_by_status(AlbumStatus.VALIDATED)
        approved = self.get_by_status(AlbumStatus.APPROVED)
        return validated + approved

    def count_by_status(self) -> Dict[str, int]:
        """Get count of albums by status"""
        counts = {status.value: 0 for status in AlbumStatus}
        for item in self._queue.values():
            status = item.get("status")
            if status in counts:
                counts[status] += 1
        return counts

    def get_statistics(self) -> Dict[str, Any]:
        """Get queue statistics"""
        counts = self.count_by_status()
        total = len(self._queue)

        return {
            "total": total,
            "counts": counts,
            "pending_scan": counts.get(AlbumStatus.DISCOVERED.value, 0),
            "pending_validation": counts.get(AlbumStatus.SCANNED.value, 0),
            "pending_review": counts.get(AlbumStatus.NEEDS_REVIEW.value, 0),
            "pending_fix": (
                counts.get(AlbumStatus.VALIDATED.value, 0) +
                counts.get(AlbumStatus.APPROVED.value, 0)
            ),
            "completed": (
                counts.get(AlbumStatus.VERIFIED.value, 0) +
                counts.get(AlbumStatus.FIXED.value, 0)
            ),
            "failed": counts.get(AlbumStatus.FAILED.value, 0),
            "skipped": (
                counts.get(AlbumStatus.REJECTED.value, 0) +
                counts.get(AlbumStatus.SKIPPED.value, 0)
            )
        }

    def set_priority_by_issues(self, album_id: str, issue_count: int) -> None:
        """Set priority based on number of issues (more issues = higher priority)"""
        if issue_count >= 5:
            priority = Priority.HIGH
        elif issue_count >= 2:
            priority = Priority.NORMAL
        else:
            priority = Priority.LOW

        self.update_priority(album_id, priority)

    def bulk_add(self, albums: List[Dict[str, Any]]) -> int:
        """
        Add multiple albums to queue.

        Args:
            albums: List of dicts with 'id', 'path', and optional 'priority'

        Returns:
            Number of albums added
        """
        count = 0
        for album in albums:
            album_id = album.get('id')
            path = album.get('path')
            if album_id and path:
                priority = Priority(album.get('priority', Priority.NORMAL.value))
                self.add(album_id, path, priority=priority)
                count += 1

        return count

    def clear(self) -> None:
        """Clear the entire queue"""
        self._queue = {}
        self.save()

    def __len__(self) -> int:
        return len(self._queue)

    def __repr__(self) -> str:
        stats = self.get_statistics()
        return f"QueueManager(total={stats['total']}, pending_review={stats['pending_review']})"
