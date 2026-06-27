#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cloud-vision validator backed by Anthropic's Claude Messages API.

Uses Claude vision (base64 image blocks) to judge whether embedded cover art
matches an album. To keep the toolkit's zero-AI default true, this talks to the
Messages API over raw HTTP via ``requests`` (imported lazily) rather than
pulling in the ``anthropic`` SDK as a dependency. Any failure - missing key,
network error, refusal - degrades to an ``abstain`` verdict.

Config keys (from the ``ai_validation`` block):
  * ``endpoint``: base URL, default ``https://api.anthropic.com``
  * ``model``: vision-capable model, default ``claude-opus-4-8``
  * ``api_key``: Anthropic API key. Falls back to the ``ANTHROPIC_API_KEY``
    environment variable.
  * ``timeout``: seconds, default 60

Reference: POST {endpoint}/v1/messages with headers ``x-api-key`` and
``anthropic-version: 2023-06-01``; the image is a base64 ``image`` content block.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from ._prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    encode_image_b64,
    parse_verdict,
)
from .base import BaseAIValidator, Verdict

DEFAULT_ENDPOINT = "https://api.anthropic.com"
DEFAULT_MODEL = "claude-opus-4-8"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicValidator(BaseAIValidator):
    """Vision validator using Claude via the Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.endpoint = self.endpoint or DEFAULT_ENDPOINT
        self.model = self.model or DEFAULT_MODEL
        self.api_key = str(
            self.config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or ""
        )

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {"vision": True}

    def verify_cover_match(
        self, image_bytes: bytes, album_meta: Dict[str, Any]
    ) -> Verdict:
        if not image_bytes:
            return self._abstain("no image bytes provided")
        if not self.api_key:
            return self._abstain("ANTHROPIC_API_KEY not set")
        try:
            import requests
        except ImportError:
            return self._abstain("requests not installed")

        media_type = "image/png" if image_bytes[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        url = f"{self.endpoint}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": encode_image_b64(image_bytes),
                            },
                        },
                        {"type": "text", "text": build_user_prompt(album_meta)},
                    ],
                }
            ],
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # network/JSON/HTTP -> fail soft
            return self._abstain(f"anthropic request failed: {exc}")

        if data.get("stop_reason") == "refusal":
            return self._abstain("model refused the request")

        text = ""
        for block in data.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
        return parse_verdict(text, self.name)
