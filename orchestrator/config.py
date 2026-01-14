#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration management for music cleanup orchestration.
Loads YAML config and credentials with environment variable support.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """
    Configuration manager that loads settings from YAML files.
    Supports environment variable expansion for sensitive values.
    """

    def __init__(self, config_path: str = "music-config.yaml"):
        self.config_path = Path(config_path)
        self.credentials_path = Path("credentials.yaml")
        self._config: Dict[str, Any] = {}
        self._credentials: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration and credentials files"""
        # Load main config
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            print(f"[Config] Warning: Config file not found: {self.config_path}")
            self._config = self._default_config()

        # Load credentials (optional)
        if self.credentials_path.exists():
            with open(self.credentials_path, 'r', encoding='utf-8') as f:
                self._credentials = yaml.safe_load(f) or {}

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            'library': {
                'root': '/path/to/music',
                'backup_enabled': True,
                'backup_path': 'D:/music_backup'
            },
            'sources': {
                'primary': 'musicbrainz',
                'fallback': ['itunes', 'discogs', 'acoustid']
            },
            'thresholds': {
                'auto_approve': 0.95,
                'review_required': 0.70,
                'auto_reject': 0.70
            },
            'output': {
                'reports_path': 'D:/music cleanup/outputs',
                'logs_path': 'D:/music cleanup/logs',
                'state_path': 'D:/music cleanup/state'
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value with dot notation.

        Examples:
            config.get('api.musicbrainz.rate_limit')
            config.get('library.root')

        Environment variables are expanded if value is like ${VAR_NAME}
        """
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
        """
        Get credential value with dot notation.

        Examples:
            config.get_credential('acoustid.api_key')
            config.get_credential('discogs.token')
        """
        keys = key.split('.')
        value = self._credentials

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

        return value

    def get_api_settings(self, source: str) -> Dict[str, Any]:
        """Get API settings for a specific source"""
        return self.get(f'api.{source}', {}) or {}

    @property
    def library_root(self) -> str:
        return self.get('library.root', '/path/to/music')

    @property
    def backup_enabled(self) -> bool:
        return self.get('library.backup_enabled', True)

    @property
    def backup_path(self) -> str:
        return self.get('library.backup_path', 'D:/music_backup')

    @property
    def state_path(self) -> str:
        return self.get('output.state_path', 'D:/music cleanup/state')

    @property
    def reports_path(self) -> str:
        return self.get('output.reports_path', 'D:/music cleanup/outputs')

    @property
    def logs_path(self) -> str:
        return self.get('output.logs_path', 'D:/music cleanup/logs')

    @property
    def auto_approve_threshold(self) -> float:
        return self.get('thresholds.auto_approve', 0.95)

    @property
    def review_threshold(self) -> float:
        return self.get('thresholds.review_required', 0.70)

    @property
    def primary_source(self) -> str:
        return self.get('sources.primary', 'musicbrainz')

    @property
    def fallback_sources(self) -> list:
        return self.get('sources.fallback', ['itunes', 'discogs'])

    def __repr__(self) -> str:
        return f"ConfigManager(config={self.config_path}, credentials={self.credentials_path})"
