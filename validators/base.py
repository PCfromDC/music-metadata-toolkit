#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base class for pluggable AI cover-art validators.

This mirrors the adapter pattern in ``sources/base.py``. Every AI "second
opinion" provider (Ollama, OpenAI-compatible, Anthropic, a Hermes/Jarvis
gateway, or a user's own contrib plugin) inherits from
:class:`BaseAIValidator` and returns a :class:`Verdict`.

Design rules that keep the toolkit usable by everyone:

  * The deterministic cover checks in ``utilities/core/`` are always-on and do
    not depend on anything here. This layer is an OPTIONAL second opinion.
  * The DEFAULT provider is :class:`~validators.null.NullValidator`, which
    always abstains and makes zero network calls and zero imports of network
    libraries.
  * A validator that cannot see images (``capabilities["vision"] is False``)
    MUST return an ``abstain`` verdict rather than guessing.
  * Network/SDK dependencies are imported lazily inside methods, never at
    module top level, so importing this package never requires ``requests`` or
    any provider SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict

# Allowed verdict labels. ``abstain`` means "I did not / could not judge".
VERDICTS = ("match", "mismatch", "uncertain", "abstain")


@dataclass
class Verdict:
    """Result of an AI cover-match check.

    Attributes:
        verdict: One of :data:`VERDICTS`. ``match`` = art fits the album,
            ``mismatch`` = wrong art, ``uncertain`` = looked but unsure,
            ``abstain`` = did not judge (default/null/non-vision/error).
        confidence: 0.0 - 1.0. Callers should treat ``abstain`` as 0.0.
        notes: Short human-readable explanation.
        provider: Name of the validator that produced this verdict.
    """

    verdict: str = "abstain"
    confidence: float = 0.0
    notes: str = ""
    provider: str = "unknown"

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(
                f"invalid verdict {self.verdict!r}; expected one of {VERDICTS}"
            )
        # Clamp confidence into [0, 1] so downstream thresholds are safe.
        try:
            self.confidence = max(0.0, min(1.0, float(self.confidence)))
        except (TypeError, ValueError):
            self.confidence = 0.0

    @property
    def is_mismatch(self) -> bool:
        """True only for an actual ``mismatch`` verdict."""
        return self.verdict == "mismatch"

    @property
    def abstained(self) -> bool:
        """True when no real judgement was made."""
        return self.verdict == "abstain"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict (for JSON logging)."""
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "notes": self.notes,
            "provider": self.provider,
        }


class BaseAIValidator(ABC):
    """Abstract base class for AI cover-match validators.

    Subclasses configure themselves from a plain ``config`` dict (typically the
    ``ai_validation`` block of ``music-config.yaml``) and implement
    :meth:`verify_cover_match`.
    """

    #: Stable identifier used in config (``provider:`` field) and the registry.
    name: str = "base"

    def __init__(self, config: Dict[str, Any] | None = None):
        """Store config. Do NOT open network connections here.

        Args:
            config: The ``ai_validation`` config block (or any subset). Common
                keys: ``endpoint``, ``model``, ``api_key``, ``timeout``.
        """
        self.config: Dict[str, Any] = dict(config or {})
        self.endpoint: str = str(self.config.get("endpoint") or "").rstrip("/")
        self.model: str = str(self.config.get("model") or "")
        self.timeout: int = int(self.config.get("timeout") or 60)

    @property
    def capabilities(self) -> Dict[str, bool]:
        """What this validator can do, e.g. ``{"vision": True}``.

        Non-vision providers MUST report ``{"vision": False}`` and abstain.
        """
        return {"vision": False}

    @abstractmethod
    def verify_cover_match(
        self, image_bytes: bytes, album_meta: Dict[str, Any]
    ) -> Verdict:
        """Judge whether ``image_bytes`` is the correct cover for an album.

        Args:
            image_bytes: Raw embedded cover-art bytes (JPEG/PNG).
            album_meta: Album context, e.g. ``{"album": ..., "artist": ...,
                "year": ...}``.

        Returns:
            A :class:`Verdict`. Implementations should NEVER raise for an
            expected failure (missing endpoint/key, network error); they should
            return an ``abstain`` verdict so the caller can fail soft.
        """
        raise NotImplementedError

    def _abstain(self, notes: str, confidence: float = 0.0) -> Verdict:
        """Helper to build an ``abstain`` verdict tagged with this provider."""
        return Verdict(
            verdict="abstain",
            confidence=confidence,
            notes=notes,
            provider=self.name,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, model={self.model!r})"
