#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validator for a configurable Hermes/Jarvis-style gateway.

This is the "bring your own gateway" provider: it POSTs the image and album
metadata to a single HTTP endpoint you control (a local Hermes/Jarvis service,
a homelab inference gateway, or any small server that wraps a vision model).
The owner of this toolkit wires it to their own validator; the public can point
it at anything that speaks the simple request/response contract below.

Request (JSON POST to ``endpoint``):
    {
      "model": "<configured model or empty>",
      "album": {...album_meta...},
      "image_base64": "<base64 jpeg/png>",
      "prompt": "<text question>"
    }

Response (any of these shapes is accepted):
    {"verdict": "match|mismatch|uncertain", "confidence": 0.0-1.0, "notes": "..."}
  or a chat-style ``{"response": "<text>"}`` / ``{"content": "<text>"}`` /
  ``{"message": {"content": "<text>"}}`` that is parsed leniently.

``requests`` is imported lazily; any failure degrades to ``abstain``.

Config keys (from the ``ai_validation`` block):
  * ``endpoint``: full gateway URL to POST to (required; no default)
  * ``model``: optional model hint forwarded to the gateway
  * ``api_key``: optional bearer token. Falls back to ``HERMES_API_KEY``.
  * ``timeout``: seconds, default 60
"""

from __future__ import annotations

import os
from typing import Any, Dict

from ._prompt import build_user_prompt, encode_image_b64, parse_verdict
from .base import BaseAIValidator, Verdict


class HermesValidator(BaseAIValidator):
    """Vision validator that POSTs to a configurable gateway endpoint."""

    name = "hermes"

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = str(
            self.config.get("api_key") or os.environ.get("HERMES_API_KEY") or ""
        )

    @property
    def capabilities(self) -> Dict[str, bool]:
        # The gateway is assumed to wrap a vision model.
        return {"vision": True}

    def verify_cover_match(
        self, image_bytes: bytes, album_meta: Dict[str, Any]
    ) -> Verdict:
        if not image_bytes:
            return self._abstain("no image bytes provided")
        if not self.endpoint:
            return self._abstain("no gateway endpoint configured")
        try:
            import requests
        except ImportError:
            return self._abstain("requests not installed")

        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "album": album_meta,
            "image_base64": encode_image_b64(image_bytes),
            "prompt": build_user_prompt(album_meta),
        }
        try:
            resp = requests.post(
                self.endpoint, json=body, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # network/JSON/HTTP -> fail soft
            return self._abstain(f"hermes gateway request failed: {exc}")

        # Structured verdict straight from the gateway?
        if isinstance(data, dict) and data.get("verdict"):
            try:
                return Verdict(
                    verdict=str(data.get("verdict")).strip().lower(),
                    confidence=float(data.get("confidence", 0.5)),
                    notes=str(data.get("notes") or "")[:300],
                    provider=self.name,
                )
            except (ValueError, TypeError):
                pass  # fall through to lenient text parsing

        # Otherwise pull text out of a chat-style payload and parse leniently.
        text = _extract_text(data)
        return parse_verdict(text, self.name)


def _extract_text(data: Any) -> str:
    """Best-effort text extraction from a variety of gateway payload shapes."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("response", "content", "text", "output"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        message = data.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return ""
