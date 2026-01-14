#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base class for processing agents.
All agents (Scanner, Validator, Fixer, Verifier) inherit from this.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import time


class BaseAgent(ABC):
    """
    Abstract base class for processing agents.

    Agents are responsible for specific tasks in the pipeline:
    - Scanner: Discover and catalog albums
    - Validator: Compare against external sources
    - Fixer: Apply corrections
    - Verifier: Confirm changes were successful
    """

    def __init__(self, config, state):
        """
        Initialize agent with configuration and state store.

        Args:
            config: ConfigManager instance
            state: StateStore instance
        """
        self.config = config
        self.state = state
        self._start_time: Optional[float] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name identifier"""
        pass

    @abstractmethod
    def process(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single item (album).

        Args:
            item: Dictionary with album info including 'path'

        Returns:
            Dictionary with processing results
        """
        pass

    def process_batch(self, items: list, callback=None) -> Dict[str, Any]:
        """
        Process multiple items.

        Args:
            items: List of items to process
            callback: Optional callback(item, result, index) called after each item

        Returns:
            Summary of batch processing
        """
        results = {
            "total": len(items),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "items": []
        }

        self._start_time = time.time()

        for i, item in enumerate(items):
            try:
                result = self.process(item)

                if result.get("status") == "success":
                    results["success"] += 1
                elif result.get("status") == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1

                results["items"].append(result)

                if callback:
                    callback(item, result, i)

            except Exception as e:
                results["failed"] += 1
                results["items"].append({
                    "path": item.get("path"),
                    "status": "error",
                    "error": str(e)
                })
                self.log_error(f"Error processing {item.get('path')}: {e}")

        results["duration"] = time.time() - self._start_time
        return results

    def log(self, message: str) -> None:
        """Log a message with agent name prefix"""
        print(f"[{self.name}] {message}")

    def log_error(self, message: str) -> None:
        """Log an error message"""
        print(f"[{self.name}] ERROR: {message}")

    def log_progress(self, current: int, total: int, item_name: str = "") -> None:
        """Log progress update"""
        percent = (current / total * 100) if total > 0 else 0
        elapsed = time.time() - self._start_time if self._start_time else 0

        if elapsed > 0 and current > 0:
            rate = current / elapsed
            remaining = (total - current) / rate if rate > 0 else 0
            eta = f"ETA: {remaining:.0f}s"
        else:
            eta = ""

        self.log(f"[{current}/{total}] ({percent:.0f}%) {item_name} {eta}")

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def save_state(self, album_path: str, status: str, data: Dict[str, Any]) -> None:
        """Save album state"""
        self.state.save_album_state(album_path, status, data)

    def get_state(self, album_path: str) -> Optional[Dict[str, Any]]:
        """Get album state"""
        return self.state.get_album_state(album_path)
