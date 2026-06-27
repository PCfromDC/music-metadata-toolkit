#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional AI second-opinion pass over embedded album cover art.

Scans a folder of albums, pulls the embedded cover bytes out of each album via
the always-on core pipeline (``utilities/core/cover_art.py``), and asks the
configured AI validator whether the art visually matches the album.

This is purely advisory and NON-DESTRUCTIVE: on a high-confidence ``mismatch``
it records a note in ``.claude/knowledge/patterns.json`` for a human to review.
It NEVER deletes or replaces art.

Defaults are zero-AI and zero-network: with the shipped ``music-config.yaml``
(``ai_validation.enabled: false`` / ``provider: null``) this runs the
:class:`~validators.null.NullValidator`, which abstains on every album and
makes no network calls.

Usage:
    python utilities/ai_validate_covers.py "/path/to/music/Artist"
    python utilities/ai_validate_covers.py "/path/to/album" --provider ollama
    python utilities/ai_validate_covers.py "/path/to/music/Artist" --config music-config.yaml

``fail_mode: soft`` (the default) means any AI/validator error is logged and the
scan continues; ``hard`` re-raises.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the project root importable when run as a script.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from utilities.core.audio_file import iter_audio_files  # read-only core import
from utilities.core.cover_art import extract_cover_from_file  # read-only core import
from validators import Verdict, get_validator

DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "music-config.yaml"
KNOWLEDGE_PATH = _PROJECT_ROOT / ".claude" / "knowledge" / "patterns.json"

# Below this we treat a verdict as advisory only and do not log it.
MISMATCH_LOG_THRESHOLD = 0.80

DEFAULT_AI_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "provider": "null",
    "endpoint": "",
    "model": "",
    "checks": {"cover_visual_match": True},
    "fail_mode": "soft",
    "timeout": 60,
}


def load_ai_config(config_path: Optional[Path]) -> Dict[str, Any]:
    """Load the ``ai_validation`` block from a YAML config, with safe defaults."""
    config = dict(DEFAULT_AI_CONFIG)
    if not config_path or not config_path.exists():
        return config
    try:
        import yaml  # optional dependency
    except ImportError:
        print("  (pyyaml not installed; using built-in AI defaults: disabled/null)")
        return config
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception as exc:
        print(f"  (could not read {config_path}: {exc}; using AI defaults)")
        return config
    block = data.get("ai_validation")
    if isinstance(block, dict):
        config.update(block)
    return config


def read_album_meta(album_path: Path) -> Dict[str, Any]:
    """Read minimal album metadata (album, artist, year) from the first track."""
    meta: Dict[str, Any] = {"album": album_path.name, "artist": "", "year": ""}
    for audio_file in iter_audio_files(album_path):
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(str(audio_file), easy=True)
        except Exception:
            break
        if not audio:
            break
        tags = getattr(audio, "tags", None) or {}

        def first(*keys: str) -> str:
            for key in keys:
                value = tags.get(key)
                if value:
                    return str(value[0]) if isinstance(value, list) else str(value)
            return ""

        meta["album"] = first("album") or meta["album"]
        meta["artist"] = first("albumartist", "artist") or meta["artist"]
        meta["year"] = first("date", "year")
        break
    return meta


def find_albums(root: Path) -> List[Path]:
    """Return album folders under ``root``.

    If ``root`` itself contains audio files, it is treated as a single album.
    Otherwise every immediate subdirectory that contains audio is an album.
    """
    if any(iter_audio_files(root)):
        return [root]
    albums = []
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and any(iter_audio_files(entry)):
            albums.append(entry)
    return albums


def extract_album_cover(album_path: Path) -> Optional[bytes]:
    """Return embedded cover bytes from the first track that has art."""
    for audio_file in iter_audio_files(album_path):
        data = extract_cover_from_file(audio_file)
        if data:
            return data
    return None


def log_mismatch(album_path: Path, meta: Dict[str, Any], verdict: Verdict) -> None:
    """Append a non-destructive mismatch note to the knowledge base."""
    KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    store: Dict[str, Any] = {}
    if KNOWLEDGE_PATH.exists():
        try:
            with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as handle:
                store = json.load(handle) or {}
        except (ValueError, OSError):
            store = {}
    if not isinstance(store, dict):
        # An unexpected top-level shape (e.g. a JSON list) must not crash the
        # scan; preserve the original payload and write our notes alongside it.
        store = {"_original": store}

    entries = store.setdefault("ai_cover_mismatches", [])
    entries.append(
        {
            "album_path": str(album_path),
            "album": meta.get("album"),
            "artist": meta.get("artist"),
            "verdict": verdict.verdict,
            "confidence": verdict.confidence,
            "notes": verdict.notes,
            "provider": verdict.provider,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    with open(KNOWLEDGE_PATH, "w", encoding="utf-8") as handle:
        json.dump(store, handle, indent=2)


def validate_path(path: Path, ai_config: Dict[str, Any]) -> Dict[str, int]:
    """Run the configured validator over every album under ``path``."""
    fail_mode = str(ai_config.get("fail_mode", "soft")).lower()
    checks = ai_config.get("checks") or {}
    enabled = bool(ai_config.get("enabled", False))
    provider = ai_config.get("provider") if enabled else "null"

    if not enabled:
        print("AI validation is disabled (ai_validation.enabled: false).")
        print("Running with NullValidator: every album will abstain, no network calls.")
    if not checks.get("cover_visual_match", True):
        print("cover_visual_match check is disabled; nothing to do.")
        return {"albums": 0, "checked": 0, "mismatches": 0, "abstained": 0, "errors": 0}

    validator = get_validator(provider, ai_config)
    print(f"Validator: {validator.name} (vision={validator.capabilities.get('vision')})")

    stats = {"albums": 0, "checked": 0, "mismatches": 0, "abstained": 0, "errors": 0}
    albums = find_albums(path)
    stats["albums"] = len(albums)

    for album in albums:
        cover = extract_album_cover(album)
        if not cover:
            print(f"  [skip] {album.name}: no embedded cover art")
            continue
        meta = read_album_meta(album)
        stats["checked"] += 1
        try:
            verdict = validator.verify_cover_match(cover, meta)
        except Exception as exc:
            stats["errors"] += 1
            print(f"  [error] {album.name}: {exc}")
            if fail_mode == "hard":
                raise
            continue

        if verdict.abstained:
            stats["abstained"] += 1
            print(f"  [abstain] {album.name}: {verdict.notes}")
        elif verdict.is_mismatch and verdict.confidence >= MISMATCH_LOG_THRESHOLD:
            stats["mismatches"] += 1
            print(
                f"  [MISMATCH] {album.name}: {verdict.confidence:.2f} - {verdict.notes}"
            )
            log_mismatch(album, meta, verdict)
        else:
            print(
                f"  [{verdict.verdict}] {album.name}: "
                f"{verdict.confidence:.2f} - {verdict.notes}"
            )

    return stats


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Optional AI second-opinion pass over embedded album cover art."
    )
    parser.add_argument("path", help="Album folder or artist folder of albums")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to music-config.yaml (default: project root)",
    )
    parser.add_argument("--provider", help="Override ai_validation.provider")
    parser.add_argument("--endpoint", help="Override ai_validation.endpoint")
    parser.add_argument("--model", help="Override ai_validation.model")
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Force-enable AI validation even if config has enabled: false",
    )
    args = parser.parse_args(argv)

    target = Path(args.path)
    if not target.exists():
        print(f"Path not found: {target}")
        return 1

    ai_config = load_ai_config(Path(args.config) if args.config else None)
    if args.enable:
        ai_config["enabled"] = True
    if args.provider:
        ai_config["provider"] = args.provider
        ai_config["enabled"] = True
    if args.endpoint:
        ai_config["endpoint"] = args.endpoint
    if args.model:
        ai_config["model"] = args.model

    print(f"Scanning: {target}")
    stats = validate_path(target, ai_config)
    print(
        "\nDone. "
        f"albums={stats['albums']} checked={stats['checked']} "
        f"mismatches={stats['mismatches']} abstained={stats['abstained']} "
        f"errors={stats['errors']}"
    )
    if stats["mismatches"]:
        print(f"Mismatches logged to {KNOWLEDGE_PATH} (no art was modified).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
